from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CATALOG_SCHEMA = "t8-case-template-catalog/v2"
LIBRARY_SCHEMA = "t8-unofficial-case-library/v2"
NO_CASE_TEMPLATE = "无（不使用 T8 案例）"
TARGETS = ("h3", "seedance20")
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
URL_RE = re.compile(r"https?://", re.IGNORECASE)
DEPRECATED_SORAN_ID = "t8-case-audio-cause-lead-ladder-v1"
DEPRECATED_SORAN_LABEL = "声画错位递进"
EXPECTED_RECORD_COUNT = 39
EXPECTED_SELECTOR_COUNT = 37
EXPECTED_EVIDENCE_COUNT = 2
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


def _load_creative_dna(record: dict[str, Any]) -> tuple[str, dict[str, str]]:
    recipes: dict[str, dict[str, Any]] = {}
    actual_hashes: dict[str, str] = {}
    for target in TARGETS:
        path = Path(str(record["models"][target]["adapter_path"])).resolve()
        recipe = _read_json(path)
        if recipe.get("case_id") != record["case_id"] or recipe.get("target") != target:
            raise LibraryImportError(f"Adapter identity mismatch: {path}")
        if recipe.get("node_execution") is not True or recipe.get("media_connections") != []:
            raise LibraryImportError(f"Built-in selector must be a text-only node recipe: {path}")
        inputs = recipe.get("inputs")
        if not isinstance(inputs, dict):
            raise LibraryImportError(f"Adapter inputs are missing: {path}")
        for field in ("api_key", "custom_model", "openai_base_url", "openai_video_urls"):
            if inputs.get(field) != "":
                raise LibraryImportError(f"Provider/secret field must be empty: {path}: {field}")
        if "openai_upload_url" in inputs:
            raise LibraryImportError(f"Removed openai_upload_url found: {path}")
        recipes[target] = recipe
        actual_hashes[target] = _sha256(path)
        if record["models"][target].get("adapter_sha256") != actual_hashes[target]:
            raise LibraryImportError(f"Adapter SHA-256 mismatch: {path}")
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


def build_catalog(library_path: Path, existing_catalog_path: Path | None = None) -> dict[str, Any]:
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
    declared_counts = (
        library.get("case_count"),
        library.get("selector_template_count"),
        library.get("evidence_variant_count"),
    )
    actual_counts = (len(records), len(selectors), len(evidence))
    expected_counts = (EXPECTED_RECORD_COUNT, EXPECTED_SELECTOR_COUNT, EXPECTED_EVIDENCE_COUNT)
    if declared_counts != expected_counts or actual_counts != expected_counts:
        raise LibraryImportError("Expected 39 records: 37 selectors and two evidence variants")
    by_template: dict[str, list[dict[str, Any]]] = {}
    validated_recipes: dict[str, tuple[str, dict[str, str]]] = {}
    seen_cases: set[str] = set()
    for record in records:
        case_id = str(record.get("case_id", ""))
        template_id = str(record.get("template_id", ""))
        action = record.get("template_action")
        if not case_id or case_id in seen_cases or not template_id or action not in {"selector", "evidence_variant"}:
            raise LibraryImportError(f"Invalid or duplicate case identity: {case_id}")
        for field in ("dropdown_label", "short_summary", "input_format", "recommended_input"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise LibraryImportError(f"Case UX field is missing: {case_id}/{field}")
        anchors = record.get("required_anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 5:
            raise LibraryImportError(f"Case requires 2-5 mechanism anchors: {case_id}")
        if not all(isinstance(anchor, str) and anchor.strip() for anchor in anchors):
            raise LibraryImportError(f"Case contains an empty mechanism anchor: {case_id}")
        by_template.setdefault(template_id, []).append(record)
        if record.get("state") != "released" or record.get("review_status") != "approved":
            raise LibraryImportError(f"Case is not released and approved: {case_id}")
        if not all(record.get("models", {}).get(target, {}).get("validation_passed") for target in TARGETS):
            raise LibraryImportError(f"Case lacks validated dual-model adapters: {case_id}")
        rights = record.get("rights", {})
        required_rights = {
            "local_preview": True,
            "model_reference": False,
            "redistribute": False,
            "gif_connected_to_model": False,
            "source_video_connected_to_model": False,
        }
        if not isinstance(rights, dict) or any(rights.get(key) is not value for key, value in required_rights.items()):
            raise LibraryImportError(f"Preview/model-reference rights mismatch: {case_id}")
        _validate_preview(record)
        validated_recipes[case_id] = _load_creative_dna(record)
        seen_cases.add(case_id)

    selector_by_template = {str(record["template_id"]): record for record in selectors}
    for evidence_record in evidence:
        primary = selector_by_template.get(str(evidence_record["template_id"]))
        if primary is None or evidence_record.get("duplicate_of") != primary.get("case_id"):
            raise LibraryImportError("Evidence variant must bind to its selector's primary case")

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
    return {
        "schema_version": CATALOG_SCHEMA,
        "catalog_id": "t8-unofficial-case-library-v2",
        "authority": "T8 原创案例模板（非官方）",
        "default": NO_CASE_TEMPLATE,
        "source_case_count": len(records),
        "selector_template_count": len(selectors),
        "evidence_variant_count": len(evidence),
        "official_minimax_skills_included": False,
        "templates": templates,
    }


def sync_source_batches(catalog: dict[str, Any], source_batch_dir: Path) -> None:
    by_case = {item["source"]["case_id"]: item for item in catalog["templates"]}
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
    parser = argparse.ArgumentParser(description="Import the 39-record T8 unofficial case-library v2 handoff.")
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--existing-catalog", type=Path)
    parser.add_argument("--source-batch-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    catalog = build_catalog(
        args.library.resolve(),
        args.existing_catalog.resolve() if args.existing_catalog else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.source_batch_dir:
        sync_source_batches(catalog, args.source_batch_dir.resolve())
    print(
        f"Wrote {catalog['selector_template_count']} selectors and "
        f"{catalog['evidence_variant_count']} evidence "
        f"{'variant' if catalog['evidence_variant_count'] == 1 else 'variants'} to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
