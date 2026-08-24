from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CATALOG_SCHEMA = "t8-case-template-catalog/v2"
LIBRARY_SCHEMA = "t8-unofficial-case-library/v2"
COMMUNITY_LIBRARY_SCHEMA = "t8-standalone-community-skill-handoff/v1"
BATCH_SCHEMA = "comfyui-handoff-batch/v1"
NO_CASE_TEMPLATE = "无（不使用 T8 案例）"
TARGETS = ("h3", "seedance20")
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
URL_RE = re.compile(r"https?://", re.IGNORECASE)
DEPRECATED_SORAN_ID = "t8-case-audio-cause-lead-ladder-v1"
DEPRECATED_SORAN_LABEL = "声画错位递进"
EXPECTED_RECORD_COUNT = 216
EXPECTED_SELECTOR_COUNT = 186
EXPECTED_EVIDENCE_COUNT = 30
EXPECTED_PENDING_COUNT = 0
EXPECTED_COMMUNITY_SKILL_COUNT = 2
EXPECTED_TOTAL_SELECTOR_COUNT = 188
EXPECTED_CONTRACT = {
    "stable_template_id_is_machine_key": True,
    "dropdown_label_is_human_ui_name": True,
    "recommended_input_is_editable_prefill": True,
    "required_anchors_need_semantic_validation": True,
    "preview_gif_is_required": True,
    "preview_gif_is_model_reference": False,
    "source_video_is_model_reference": False,
    "official_minimax_skills_included": False,
}

H3_GUIDANCE = (
    "MiniMax H3 native adapter. Realize every required mechanism anchor as a concrete visible event inside the "
    "native H3 integrated description or Ref2VA detailed description. Preserve the exact H3 Base/Ref2VA field "
    "order, [Shot N] timeline, camera continuity, soundscape and music separation. Do not emit Seedance 镜头N or "
    "@图片N syntax. The case mechanism is lower priority than user intent, observable media, hard constraints, "
    "duration, fixed shot count, official H3 rules, official creative presets and a manual reference template."
)
SEEDANCE20_GUIDANCE = (
    "Seedance 2.0 native adapter. Realize every required mechanism anchor as a concrete filmable event inside one "
    "compact paragraph or consecutive 镜头N sequence chosen from the task complexity. Use Seedance subject binding, "
    "asset roles, coherent motion and sound syntax; never emit H3 field names, [Shot N], alignment lines or absolute "
    "per-shot time ranges. The case mechanism is lower priority than user intent, observable media, hard constraints, "
    "duration, fixed shot count, official Seedance rules and a manual reference template."
)


class LibraryImportError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryImportError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LibraryImportError(f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_text_asset(asset: Any, *, label: str) -> tuple[str, str]:
    if not isinstance(asset, dict):
        raise LibraryImportError(f"Community Skill asset is missing: {label}")
    path = Path(str(asset.get("path", ""))).resolve()
    expected_hash = str(asset.get("sha256", ""))
    if not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise LibraryImportError(f"Community Skill asset is invalid: {label}: {path}")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise LibraryImportError(f"Community Skill asset SHA-256 mismatch: {label}: {path}")
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise LibraryImportError(f"Cannot read community Skill asset: {label}: {path}: {exc}") from exc
    if not text or SECRET_RE.search(text):
        raise LibraryImportError(f"Community Skill asset is empty or contains a secret: {label}")
    return text, actual_hash


def _community_preview_id(skill_id: str) -> str:
    return f"community-skill--{skill_id}"


def _validate_community_preview(record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    skill_id = str(record.get("skill_id", ""))
    preview = record.get("preview")
    if not isinstance(preview, dict):
        raise LibraryImportError(f"Community Skill preview metadata is missing: {skill_id}")
    path = Path(str(preview.get("path", ""))).resolve()
    expected_hash = str(preview.get("sha256", ""))
    if path.suffix.lower() != ".gif" or not path.is_file():
        raise LibraryImportError(f"Community Skill preview GIF is missing: {path}")
    with path.open("rb") as handle:
        if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
            raise LibraryImportError(f"Community Skill preview is not a GIF: {path}")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise LibraryImportError(f"Community Skill preview GIF SHA-256 mismatch: {path}")
    return {
        "case_id": _community_preview_id(skill_id),
        "label": record["dropdown_label"],
        "short_summary": record["short_summary"],
        "recommended_input": record["recommended_input"],
        "required_anchors": list(record["required_anchors"]),
        "sha256": actual_hash,
        "width": 0,
        "height": 0,
        "duration_seconds": 0,
        "human_preview_only": True,
    }, actual_hash


def _creative_dna_from_case_file(record: dict[str, Any]) -> str:
    case_id = str(record.get("case_id", ""))
    case_root = Path(str(record.get("case_path", ""))).resolve()
    path = (case_root / "creative-dna.json").resolve()
    try:
        path.relative_to(case_root)
    except ValueError as exc:
        raise LibraryImportError(f"Creative DNA escapes its case directory: {case_id}") from exc
    expected_hash = str(record.get("creative_dna_sha256", ""))
    if not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise LibraryImportError(f"Creative DNA asset is missing or invalid: {case_id}")
    if _sha256(path) != expected_hash:
        raise LibraryImportError(f"Creative DNA SHA-256 mismatch: {case_id}")
    source = _read_json(path)
    mechanism = str(source.get("mechanism", "")).strip()
    invariants = source.get("invariants")
    slots = source.get("slots")
    failure_modes = source.get("failure_modes")
    if not mechanism or not isinstance(invariants, list) or not 2 <= len(invariants) <= 5:
        raise LibraryImportError(f"Creative DNA mechanism/invariants are invalid: {case_id}")
    invariant_rules = [str(item.get("rule", "")).strip() for item in invariants if isinstance(item, dict)]
    if len(invariant_rules) != len(invariants) or not all(invariant_rules):
        raise LibraryImportError(f"Creative DNA contains an empty invariant: {case_id}")
    if not isinstance(slots, list) or not slots:
        raise LibraryImportError(f"Creative DNA transferable slots are missing: {case_id}")
    slot_lines: list[str] = []
    for item in slots:
        if not isinstance(item, dict):
            raise LibraryImportError(f"Creative DNA contains an invalid slot: {case_id}")
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not name or not description:
            raise LibraryImportError(f"Creative DNA contains an empty slot: {case_id}")
        slot_lines.append(f"- {name}: {description}")
    if not isinstance(failure_modes, list) or not failure_modes:
        raise LibraryImportError(f"Creative DNA failure repairs are missing: {case_id}")
    repair_lines: list[str] = []
    for item in failure_modes:
        if not isinstance(item, dict):
            raise LibraryImportError(f"Creative DNA contains an invalid failure repair: {case_id}")
        failure = str(item.get("failure", "")).strip()
        repair = str(item.get("repair", "")).strip()
        if not failure or not repair:
            raise LibraryImportError(f"Creative DNA contains an empty failure repair: {case_id}")
        repair_lines.append(f"- {failure} -> {repair}")
    text = "\n".join([
        "Reusable Creative DNA (mechanism and production grammar only)",
        "Authority: T8 original case template (non-official).",
        "",
        "MECHANISM:",
        mechanism,
        "",
        "INVARIANTS:",
        *(f"{index}. {rule}" for index, rule in enumerate(invariant_rules, start=1)),
        "",
        "TRANSFERABLE SLOTS:",
        *slot_lines,
        "",
        "FAILURE REPAIRS:",
        *repair_lines,
        "",
        "Do not copy from the source:",
        "Change subject identity, wardrobe, setting, props, palette, sound and performance surface for every new "
        "instance. Preserve only the abstract causal mechanism and ordered anchors.",
    ]).strip()
    if SECRET_RE.search(text) or URL_RE.search(text):
        raise LibraryImportError(f"Creative DNA contains a secret or URL: {case_id}")
    return text


def _load_creative_dna(record: dict[str, Any]) -> tuple[str, dict[str, str]]:
    recipes: dict[str, dict[str, Any]] = {}
    actual_hashes: dict[str, str] = {}
    recipe_modes: set[str] = set()
    for target in TARGETS:
        path = Path(str(record["models"][target]["adapter_path"])).resolve()
        recipe = _read_json(path)
        if recipe.get("case_id") != record["case_id"] or recipe.get("target") != target:
            raise LibraryImportError(f"Adapter identity mismatch: {path}")
        if recipe.get("node_execution") is True:
            recipe_modes.add("node_recipe")
            if recipe.get("media_connections") != []:
                raise LibraryImportError(f"Built-in selector must be a text-only node recipe: {path}")
            inputs = recipe.get("inputs")
            if not isinstance(inputs, dict):
                raise LibraryImportError(f"Adapter inputs are missing: {path}")
            for field in ("api_key", "custom_model", "openai_base_url", "openai_video_urls"):
                if inputs.get(field) != "":
                    raise LibraryImportError(f"Provider/secret field must be empty: {path}: {field}")
            if "openai_upload_url" in inputs:
                raise LibraryImportError(f"Removed openai_upload_url found: {path}")
        elif recipe.get("direct_final") is True and recipe.get("node_execution") is False:
            recipe_modes.add("direct_final")
            if (
                recipe.get("media_connections") != []
                or recipe.get("node") is not None
                or recipe.get("inputs") != {}
            ):
                raise LibraryImportError(f"Direct-final adapter must remain disconnected and input-free: {path}")
            compiled_prompt = recipe.get("compiled_prompt")
            if not isinstance(compiled_prompt, str) or not compiled_prompt.strip() or SECRET_RE.search(compiled_prompt):
                raise LibraryImportError(f"Direct-final adapter prompt is missing or contains a secret: {path}")
            prompt_hash = hashlib.sha256(compiled_prompt.encode("utf-8")).hexdigest()
            validation_hash = str(recipe.get("prompt_validation_context", {}).get("prompt_sha256", ""))
            if prompt_hash != validation_hash:
                raise LibraryImportError(f"Direct-final adapter prompt SHA-256 mismatch: {path}")
        else:
            raise LibraryImportError(f"Unsupported adapter execution contract: {path}")
        recipes[target] = recipe
        actual_hashes[target] = _sha256(path)
        if record["models"][target].get("adapter_sha256") != actual_hashes[target]:
            raise LibraryImportError(f"Adapter SHA-256 mismatch: {path}")
    if len(recipe_modes) != 1:
        raise LibraryImportError(f"Dual-model adapter modes do not match: {record['case_id']}")
    if recipe_modes == {"direct_final"}:
        return _creative_dna_from_case_file(record), actual_hashes
    h3_dna = str(recipes["h3"]["inputs"].get("reference_template", "")).strip()
    seedance_dna = str(recipes["seedance20"]["inputs"].get("reference_template", "")).strip()
    if not h3_dna or h3_dna != seedance_dna:
        raise LibraryImportError(f"Dual-model Creative DNA mismatch: {record['case_id']}")
    if SECRET_RE.search(h3_dna) or URL_RE.search(h3_dna):
        raise LibraryImportError(f"Creative DNA contains a secret or URL: {record['case_id']}")
    return h3_dna, actual_hashes


def _validate_preview(record: dict[str, Any]) -> None:
    preview = record.get("preview")
    if not isinstance(preview, dict):
        raise LibraryImportError(f"Preview metadata is missing: {record.get('case_id')}")
    case_root = Path(str(record.get("case_path", ""))).resolve()
    relative = Path(str(preview.get("path", "")))
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise LibraryImportError(f"Unsafe preview path: {record.get('case_id')}")
    path = (case_root / relative).resolve()
    try:
        path.relative_to(case_root)
    except ValueError as exc:
        raise LibraryImportError(f"Preview escapes its case directory: {path}") from exc
    if path.suffix.lower() != ".gif" or not path.is_file():
        raise LibraryImportError(f"Required preview GIF is missing: {path}")
    with path.open("rb") as handle:
        if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
            raise LibraryImportError(f"Preview is not a GIF: {path}")
    if preview.get("sha256") != _sha256(path):
        raise LibraryImportError(f"Preview GIF SHA-256 mismatch: {path}")


def _preview_record(record: dict[str, Any]) -> dict[str, Any]:
    preview = record["preview"]
    return {
        "case_id": record["case_id"],
        "label": record["dropdown_label"],
        "short_summary": record["short_summary"],
        "recommended_input": record["recommended_input"],
        "required_anchors": list(record["required_anchors"]),
        "sha256": preview["sha256"],
        "width": preview["width"],
        "height": preview["height"],
        "duration_seconds": preview["duration_seconds"],
        "human_preview_only": True,
    }


def _build_community_templates(community_library_path: Path) -> list[dict[str, Any]]:
    manifest = _read_json(community_library_path)
    if manifest.get("schema_version") != COMMUNITY_LIBRARY_SCHEMA:
        raise LibraryImportError("Unsupported standalone community-Skill handoff schema")
    if manifest.get("official") is not False or manifest.get("authority") != "t8_user_contributed_skill":
        raise LibraryImportError("Standalone community-Skill authority is invalid")
    records = manifest.get("records")
    if (
        not isinstance(records, list)
        or manifest.get("skill_count") != EXPECTED_COMMUNITY_SKILL_COUNT
        or manifest.get("selector_count") != EXPECTED_COMMUNITY_SKILL_COUNT
        or len(records) != EXPECTED_COMMUNITY_SKILL_COUNT
    ):
        raise LibraryImportError("Expected two standalone community Skill selectors")
    source_index_path = Path(str(manifest.get("source_index", ""))).resolve()
    source_index = _read_json(source_index_path)
    indexed_skills = source_index.get("skills")
    indexed_ids = {
        str(item.get("id"))
        for item in indexed_skills
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(indexed_skills, list) else set()
    if (
        source_index.get("schema_version") != "public-community-skill-index/v1"
        or source_index.get("official") is not False
        or source_index.get("skill_count") != EXPECTED_COMMUNITY_SKILL_COUNT
        or indexed_ids != {str(record.get("skill_id")) for record in records}
    ):
        raise LibraryImportError("Standalone community Skill source index does not close over the handoff records")

    templates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for record in records:
        skill_id = str(record.get("skill_id", ""))
        template_id = str(record.get("template_id", ""))
        label = str(record.get("dropdown_label", ""))
        if (
            not skill_id
            or template_id != f"community-skill/{skill_id}"
            or template_id in seen_ids
            or not label
            or label in seen_labels
            or record.get("template_action") != "selector"
            or record.get("official") is not False
            or record.get("source_classification") != "user-contributed"
            or record.get("models") != list(TARGETS)
        ):
            raise LibraryImportError(f"Invalid standalone community Skill identity: {skill_id}")
        for field in ("short_summary", "input_format", "recommended_input"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise LibraryImportError(f"Community Skill UX field is missing: {skill_id}/{field}")
        anchors = record.get("required_anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 5:
            raise LibraryImportError(f"Community Skill requires 2-5 mechanism anchors: {skill_id}")
        if not all(isinstance(anchor, str) and anchor.strip() for anchor in anchors):
            raise LibraryImportError(f"Community Skill contains an empty mechanism anchor: {skill_id}")
        expected_policy = {
            "create_selector": True,
            "merge_into_case_registry": False,
            "source_media_connected": False,
            "preview_only": True,
            "node_modification_authorized": False,
        }
        policy = record.get("import_policy")
        if not isinstance(policy, dict) or any(policy.get(key) is not value for key, value in expected_policy.items()):
            raise LibraryImportError(f"Community Skill import policy mismatch: {skill_id}")

        _skill_text, skill_hash = _verified_text_asset(record.get("skill"), label=f"{skill_id}/SKILL.md")
        summary, summary_hash = _verified_text_asset(record.get("summary"), label=f"{skill_id}/summary")
        h3_guidance, h3_hash = _verified_text_asset(
            record.get("guidance", {}).get("h3"), label=f"{skill_id}/h3"
        )
        seedance_guidance, seedance_hash = _verified_text_asset(
            record.get("guidance", {}).get("seedance20"), label=f"{skill_id}/seedance20"
        )
        for label_name, content in (
            ("summary", summary), ("h3", h3_guidance), ("seedance20", seedance_guidance),
        ):
            if URL_RE.search(content):
                raise LibraryImportError(f"Community Skill distributable text contains a URL: {skill_id}/{label_name}")
        preview, preview_hash = _validate_community_preview(record)
        templates.append({
            "id": template_id,
            "label": label,
            "legacy_ids": [],
            "legacy_labels": [],
            "summary": record["short_summary"],
            "input_format": record["input_format"],
            "recommended_input": record["recommended_input"],
            "required_anchors": list(anchors),
            "status": "active",
            "authority": "T8 社区 Skill（非官方·用户贡献）",
            "official": False,
            "template_kind": "community_skill",
            "source": {
                "skill_id": skill_id,
                "skill_sha256": skill_hash,
                "summary_sha256": summary_hash,
                "preview_sha256": preview_hash,
                "h3_guidance_sha256": h3_hash,
                "seedance20_guidance_sha256": seedance_hash,
            },
            "previews": [preview],
            "creative_dna": (
                "Reusable Creative DNA (mechanism and production grammar only)\n"
                "Authority: non-official, user-contributed community Skill.\n\n"
                + summary
            ),
            "variants": {
                "h3": {"guidance": H3_GUIDANCE + "\n\n" + h3_guidance},
                "seedance20": {"guidance": SEEDANCE20_GUIDANCE + "\n\n" + seedance_guidance},
            },
        })
        seen_ids.add(template_id)
        seen_labels.add(label)
    return templates


def build_catalog(
    library_path: Path,
    community_library_path: Path,
    existing_catalog_path: Path | None = None,
) -> dict[str, Any]:
    library = _read_json(library_path)
    if library.get("schema_version") != LIBRARY_SCHEMA:
        raise LibraryImportError("Unsupported unofficial case-library schema")
    contract = library.get("contract", {})
    if not isinstance(contract, dict) or any(contract.get(key) is not value for key, value in EXPECTED_CONTRACT.items()):
        raise LibraryImportError("Unofficial case-library contract does not match the v2 node handoff")
    records = library.get("records")
    if not isinstance(records, list):
        raise LibraryImportError("Library records are missing")
    selectors = [record for record in records if record.get("template_action") == "selector"]
    evidence = [record for record in records if record.get("template_action") == "evidence_variant"]
    pending = [record for record in records if record.get("template_action") == "pending"]
    declared_counts = (
        library.get("case_count"),
        library.get("selector_template_count"),
        library.get("evidence_variant_count"),
        library.get("pending_completion_count"),
    )
    actual_counts = (len(records), len(selectors), len(evidence), len(pending))
    expected_counts = (
        EXPECTED_RECORD_COUNT,
        EXPECTED_SELECTOR_COUNT,
        EXPECTED_EVIDENCE_COUNT,
        EXPECTED_PENDING_COUNT,
    )
    if declared_counts != expected_counts or actual_counts != expected_counts:
        raise LibraryImportError(
            "Expected 216 records: 186 selectors, 30 evidence variants, and no pending cases"
        )
    by_template: dict[str, list[dict[str, Any]]] = {}
    validated_recipes: dict[str, tuple[str, dict[str, str]]] = {}
    seen_cases: set[str] = set()
    for record in records:
        case_id = str(record.get("case_id", ""))
        template_id = str(record.get("template_id", ""))
        action = record.get("template_action")
        if not case_id or case_id in seen_cases or not template_id or action not in {
            "selector", "evidence_variant", "pending",
        }:
            raise LibraryImportError(f"Invalid or duplicate case identity: {case_id}")
        for field in ("dropdown_label", "short_summary", "input_format", "recommended_input"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise LibraryImportError(f"Case UX field is missing: {case_id}/{field}")
        anchors = record.get("required_anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 5:
            raise LibraryImportError(f"Case requires 2-5 mechanism anchors: {case_id}")
        if not all(isinstance(anchor, str) and anchor.strip() for anchor in anchors):
            raise LibraryImportError(f"Case contains an empty mechanism anchor: {case_id}")
        if action == "pending":
            blockers = record.get("blockers")
            if (
                record.get("state") == "released"
                or record.get("review_status") == "approved"
                or record.get("release_score") is not None
                or not isinstance(blockers, list)
                or not blockers
                or not all(isinstance(blocker, str) and blocker.strip() for blocker in blockers)
            ):
                raise LibraryImportError(f"Pending case release gate is inconsistent: {case_id}")
            for target in TARGETS:
                model = record.get("models", {}).get(target, {})
                if model.get("adapter_path") is not None or model.get("adapter_sha256") is not None:
                    raise LibraryImportError(f"Pending case must not ship an adapter: {case_id}/{target}")
            rights = record.get("rights", {})
            if (
                rights.get("model_reference") is not False
                or rights.get("redistribute") is not False
                or rights.get("gif_connected_to_model") is not False
                or rights.get("source_video_connected_to_model") is not False
            ):
                raise LibraryImportError(f"Pending case rights/model-reference boundary mismatch: {case_id}")
            seen_cases.add(case_id)
            continue
        by_template.setdefault(template_id, []).append(record)
        if record.get("state") != "released" or record.get("review_status") != "approved":
            raise LibraryImportError(f"Case is not released and approved: {case_id}")
        if not all(record.get("models", {}).get(target, {}).get("validation_passed") for target in TARGETS):
            raise LibraryImportError(f"Case lacks validated dual-model adapters: {case_id}")
        rights = record.get("rights", {})
        required_preview_boundary = {
            "local_preview": True,
            "model_reference": False,
            "gif_connected_to_model": False,
            "source_video_connected_to_model": False,
        }
        if (
            not isinstance(rights, dict)
            or any(rights.get(key) is not value for key, value in required_preview_boundary.items())
            or not isinstance(rights.get("redistribute"), bool)
        ):
            raise LibraryImportError(f"Preview/model-reference rights mismatch: {case_id}")
        _validate_preview(record)
        validated_recipes[case_id] = _load_creative_dna(record)
        seen_cases.add(case_id)

    selector_by_template = {str(record["template_id"]): record for record in selectors}
    record_by_case = {str(record["case_id"]): record for record in records}
    for evidence_record in evidence:
        template_id = str(evidence_record["template_id"])
        primary = selector_by_template.get(template_id)
        if primary is None:
            raise LibraryImportError("Evidence variant must bind to an existing selector template")
        cursor = evidence_record
        visited = {str(evidence_record["case_id"])}
        while cursor.get("duplicate_of") != primary.get("case_id"):
            parent_id = str(cursor.get("duplicate_of", ""))
            parent = record_by_case.get(parent_id)
            if (
                not parent_id
                or parent_id in visited
                or parent is None
                or parent.get("template_action") != "evidence_variant"
                or str(parent.get("template_id")) != template_id
            ):
                raise LibraryImportError(
                    "Evidence variant chain must stay inside one template and resolve to its primary case"
                )
            visited.add(parent_id)
            cursor = parent

    existing: dict[str, dict[str, Any]] = {}
    if existing_catalog_path and existing_catalog_path.is_file():
        old = _read_json(existing_catalog_path)
        existing = {str(item.get("id")): item for item in old.get("templates", []) if isinstance(item, dict)}

    templates: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for record in selectors:
        template_id = str(record["template_id"])
        label = str(record["dropdown_label"])
        if template_id in {item["id"] for item in templates} or label in seen_labels:
            raise LibraryImportError(f"Duplicate selector identity: {template_id} / {label}")
        dna, adapter_hashes = validated_recipes[str(record["case_id"])]
        legacy_labels: list[str] = []
        old = existing.get(template_id)
        if old:
            legacy_labels.extend(str(value) for value in old.get("legacy_labels", []))
        if old and old.get("label") != label:
            legacy_labels.append(str(old["label"]))
        legacy_ids: list[str] = [str(value) for value in old.get("legacy_ids", [])] if old else []
        if template_id == "t8-case-scale-contraction-evidence-funnel-v1":
            legacy_ids.append(DEPRECATED_SORAN_ID)
            legacy_labels.append(DEPRECATED_SORAN_LABEL)
        variants = by_template[template_id]
        templates.append({
            "id": template_id,
            "label": label,
            "legacy_ids": sorted(set(legacy_ids)),
            "legacy_labels": sorted(set(legacy_labels)),
            "summary": record["short_summary"],
            "input_format": record["input_format"],
            "recommended_input": record["recommended_input"],
            "required_anchors": list(record["required_anchors"]),
            "status": "active",
            "authority": "T8 原创案例模板（非官方）",
            "official": False,
            "template_kind": "case",
            "source": {
                "case_id": record["case_id"],
                "case_sha256": record["case_sha256"],
                "release_score": record["release_score"],
                "creative_dna_sha256": record["creative_dna_sha256"],
                "h3_adapter_sha256": adapter_hashes["h3"],
                "seedance20_adapter_sha256": adapter_hashes["seedance20"],
            },
            "previews": [_preview_record(item) for item in variants],
            "creative_dna": dna,
            "variants": {
                "h3": {"guidance": H3_GUIDANCE},
                "seedance20": {"guidance": SEEDANCE20_GUIDANCE},
            },
        })
        seen_labels.add(label)
    community_templates = _build_community_templates(community_library_path)
    existing_ids = {template["id"] for template in templates}
    existing_labels = {template["label"] for template in templates}
    for template in community_templates:
        if template["id"] in existing_ids or template["label"] in existing_labels:
            raise LibraryImportError(f"Community selector collides with a case selector: {template['id']}")
        templates.append(template)
        existing_ids.add(template["id"])
        existing_labels.add(template["label"])
    if len(templates) != EXPECTED_TOTAL_SELECTOR_COUNT:
        raise LibraryImportError("Expected 188 total non-official selectors")
    return {
        "schema_version": CATALOG_SCHEMA,
        "catalog_id": "t8-unofficial-case-library-v2",
        "authority": "T8 非官方模板（案例 / 社区 Skill）",
        "default": NO_CASE_TEMPLATE,
        "source_case_count": len(records),
        "case_selector_template_count": len(selectors),
        "community_skill_count": len(community_templates),
        "selector_template_count": len(templates),
        "evidence_variant_count": len(evidence),
        "pending_completion_count": len(pending),
        "official_minimax_skills_included": False,
        "templates": templates,
    }


def build_source_batch(
    batch_path: Path,
    library_path: Path,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    batch = _read_json(batch_path)
    library = _read_json(library_path)
    if batch.get("schema_version") != BATCH_SCHEMA:
        raise LibraryImportError("Unsupported increment-batch schema")
    if library.get("schema_version") != LIBRARY_SCHEMA:
        raise LibraryImportError("Unsupported cumulative case-library schema")
    records = batch.get("records")
    if not isinstance(records, list):
        raise LibraryImportError("Increment batch records are missing")

    selectors = [item for item in records if item.get("template_action") == "selector"]
    evidence = [item for item in records if item.get("template_action") == "evidence_variant"]
    pending = [item for item in records if item.get("template_action") == "pending"]
    declared_counts = (
        batch.get("record_count"),
        batch.get("adapter_ready_count"),
        batch.get("selector_template_count"),
        batch.get("evidence_variant_count"),
        batch.get("pending_completion_count"),
    )
    actual_counts = (
        len(records),
        sum(item.get("case_handoff_status") == "adapter-ready" for item in records),
        len(selectors),
        len(evidence),
        len(pending),
    )
    if declared_counts != actual_counts or pending:
        raise LibraryImportError(
            f"Increment batch count or readiness mismatch: declared={declared_counts}, actual={actual_counts}"
        )

    closure = batch.get("inventory_closure")
    expected_closure = {
        "scope": "increment",
        "increment_records": len(records),
        "cumulative_case_records": EXPECTED_RECORD_COUNT,
        "cumulative_case_selectors": EXPECTED_SELECTOR_COUNT,
        "cumulative_evidence_variants": EXPECTED_EVIDENCE_COUNT,
        "standalone_community_skills": EXPECTED_COMMUNITY_SKILL_COUNT,
        "total_nonofficial_selectors": EXPECTED_TOTAL_SELECTOR_COUNT,
        "official_minimax_skills_excluded": 9,
    }
    if not isinstance(closure, dict) or any(closure.get(key) != value for key, value in expected_closure.items()):
        raise LibraryImportError("Increment batch inventory closure does not match the cumulative library")

    canonical_by_case = {
        str(item.get("case_id")): item
        for item in library.get("records", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    catalog_by_case = {
        str(item.get("source", {}).get("case_id")): item
        for item in catalog.get("templates", [])
        if isinstance(item, dict) and item.get("template_kind") == "case"
    }
    source_cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for record in records:
        case_id = str(record.get("case_id", ""))
        action = str(record.get("template_action", ""))
        canonical = canonical_by_case.get(case_id)
        if not case_id or case_id in seen_cases or canonical is None:
            raise LibraryImportError(f"Increment case is missing or duplicated: {case_id or '<unknown>'}")
        if (
            canonical.get("template_id") != record.get("template_id")
            or canonical.get("template_action") != action
            or canonical.get("case_sha256") != record.get("case_sha256")
            or canonical.get("creative_dna_sha256") != record.get("creative_dna_sha256")
        ):
            raise LibraryImportError(f"Increment/cumulative case identity drift: {case_id}")
        for target in TARGETS:
            target_hash = canonical.get("models", {}).get(target, {}).get("adapter_sha256")
            if target_hash != record.get(f"{target}_adapter_sha256"):
                raise LibraryImportError(f"Increment/cumulative adapter drift: {case_id}/{target}")
        seen_cases.add(case_id)
        if action != "selector":
            continue

        template = catalog_by_case.get(case_id)
        if template is None or template.get("id") != record.get("template_id"):
            raise LibraryImportError(f"Increment selector is absent from the compiled catalog: {case_id}")
        source = template["source"]
        for field in (
            "case_sha256", "creative_dna_sha256", "h3_adapter_sha256", "seedance20_adapter_sha256",
        ):
            if source.get(field) != record.get(field):
                raise LibraryImportError(f"Increment/catalog hash drift: {case_id}/{field}")
        fingerprint = str(record.get("mechanism_fingerprint", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise LibraryImportError(f"Invalid increment mechanism fingerprint: {case_id}")
        source_cases.append({
            "case_id": case_id,
            "template_id": template["id"],
            "label": template["label"],
            "summary": template["summary"],
            "case_sha256": source["case_sha256"],
            "creative_dna_sha256": source["creative_dna_sha256"],
            "h3_adapter_sha256": source["h3_adapter_sha256"],
            "seedance20_adapter_sha256": source["seedance20_adapter_sha256"],
            "mechanism_fingerprint": fingerprint,
        })

    if len(source_cases) != batch.get("selector_template_count"):
        raise LibraryImportError("Increment source-batch selector count mismatch")
    batch_id = str(batch.get("batch_id", "")).removeprefix("batch-")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-[a-z0-9]+)+", batch_id):
        raise LibraryImportError(f"Invalid increment batch ID: {batch_id}")
    source_batch = {
        "schema_version": "t8-case-template-batch/v1",
        "batch_id": batch_id,
        "authority": "T8 精选案例（非官方）",
        "cases": source_cases,
    }
    serialized = json.dumps(source_batch, ensure_ascii=False)
    if SECRET_RE.search(serialized) or URL_RE.search(serialized) or re.search(r"[A-Za-z]:\\", serialized):
        raise LibraryImportError("Sanitized source batch contains a secret, URL, or local path")
    return source_batch


def sync_source_batches(catalog: dict[str, Any], source_batch_dir: Path) -> None:
    by_case = {
        item["source"]["case_id"]: item
        for item in catalog["templates"]
        if item.get("template_kind") == "case" and item.get("source", {}).get("case_id")
    }
    for path in sorted(source_batch_dir.glob("*.json")):
        batch = _read_json(path)
        changed = False
        for item in batch.get("cases", []):
            template = by_case.get(item.get("case_id"))
            if not template:
                continue
            item["template_id"] = template["id"]
            item["label"] = template["label"]
            item["summary"] = template["summary"]
            for field in (
                "case_sha256", "creative_dna_sha256", "h3_adapter_sha256", "seedance20_adapter_sha256",
            ):
                if template["source"].get(field):
                    item[field] = template["source"][field]
            changed = True
        if changed:
            path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import the 216-record case handoff: 186 selectors, 30 evidence variants, "
            "no pending cases, plus two standalone community Skills."
        )
    )
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--community-skills", required=True, type=Path)
    parser.add_argument("--existing-catalog", type=Path)
    parser.add_argument("--source-batch-dir", type=Path)
    parser.add_argument("--increment-batch", type=Path)
    parser.add_argument("--source-batch-output", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if bool(args.increment_batch) != bool(args.source_batch_output):
        parser.error("--increment-batch and --source-batch-output must be provided together")
    catalog = build_catalog(
        args.library.resolve(),
        args.community_skills.resolve(),
        args.existing_catalog.resolve() if args.existing_catalog else None,
    )
    source_batch = None
    if args.increment_batch:
        source_batch = build_source_batch(args.increment_batch.resolve(), args.library.resolve(), catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if source_batch is not None:
        args.source_batch_output.parent.mkdir(parents=True, exist_ok=True)
        args.source_batch_output.write_text(
            json.dumps(source_batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.source_batch_dir:
        sync_source_batches(catalog, args.source_batch_dir.resolve())
    print(
        f"Wrote {catalog['case_selector_template_count']} case selectors, "
        f"{catalog['community_skill_count']} community Skills, and "
        f"{catalog['evidence_variant_count']} evidence "
        f"{'variant' if catalog['evidence_variant_count'] == 1 else 'variants'}; "
        f"held back {catalog['pending_completion_count']} pending cases; wrote {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
