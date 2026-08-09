from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


NO_CASE_TEMPLATE = "无（不使用 T8 案例）"
H3_GUIDANCE = (
    "Target adapter: MiniMax H3. Apply the selected non-official T8 Creative DNA only as a lower-priority "
    "composition mechanism. Translate compatible invariants and slots into the required H3 top-level fields, "
    "[Shot N] timeline, camera continuity, soundscape, and music rules. Never copy source surface content, never "
    "invent readable copy or claims, and never let this case override the user's intent, observable media, hard "
    "constraints, fixed duration, fixed shot count, official H3 contract, selected MiniMax official creative preset, "
    "or a more specific manual template."
)
SEEDANCE20_GUIDANCE = (
    "Target adapter: Seedance 2.0. Apply the selected non-official T8 Creative DNA only as a lower-priority "
    "composition mechanism. Express compatible invariants and slots through the chosen Seedance task, compact "
    "paragraph or ordered 镜头N structure, media-reference syntax, motion continuity, and sound intent. Never emit "
    "H3 field names or absolute H3 timestamps, never copy source surface content, and never let this case override "
    "the user's intent, observable media, hard constraints, fixed duration, fixed shot count, official Seedance "
    "rules, or a more specific manual template."
)
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
URL_RE = re.compile(r"https?://", re.IGNORECASE)


class CatalogImportError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogImportError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogImportError(f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _adapter(case_dir: Path, case_id: str, target: str) -> tuple[dict[str, Any], Path]:
    path = case_dir / "adapters" / f"comfyui-t8-{target}.json"
    recipe = _read_json(path)
    if recipe.get("case_id") != case_id or recipe.get("target") != target:
        raise CatalogImportError(f"Adapter identity mismatch: {path}")
    if recipe.get("node_execution") is not True:
        raise CatalogImportError(f"Template catalog requires a node-execution recipe: {path}")
    if recipe.get("media_connections") != []:
        raise CatalogImportError(f"Built-in case templates must be text-only: {path}")
    inputs = recipe.get("inputs")
    if not isinstance(inputs, dict):
        raise CatalogImportError(f"Adapter inputs are missing: {path}")
    for field in ("api_key", "custom_model", "openai_base_url", "openai_video_urls"):
        if inputs.get(field) != "":
            raise CatalogImportError(f"Adapter secret/provider field must remain empty: {path}: {field}")
    if "openai_upload_url" in inputs:
        raise CatalogImportError(f"Removed legacy field found in adapter: {path}")
    template = inputs.get("reference_template")
    if not isinstance(template, str) or not template.strip():
        raise CatalogImportError(f"Adapter has no reusable template: {path}")
    return recipe, path


def build_catalog(registry_path: Path, batch_paths: Path | list[Path]) -> dict[str, Any]:
    registry = _read_json(registry_path)
    if isinstance(batch_paths, Path):
        batch_paths = [batch_paths]
    if not batch_paths:
        raise CatalogImportError("At least one source batch is required")
    batches = [_read_json(path) for path in batch_paths]
    for batch in batches:
        if batch.get("schema_version") != "t8-case-template-batch/v1":
            raise CatalogImportError("Unsupported source-batch schema")
    authorities = {batch.get("authority", "T8 精选案例（非官方）") for batch in batches}
    if len(authorities) != 1:
        raise CatalogImportError("Source batches disagree on template authority")
    records = {
        item.get("case_id"): item
        for item in registry.get("records", [])
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    templates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for batch in batches:
        for item in batch.get("cases", []):
            if not isinstance(item, dict):
                raise CatalogImportError("Source batch contains a non-object case")
            case_id = str(item.get("case_id", "")).strip()
            template_id = str(item.get("template_id", "")).strip()
            label = str(item.get("label", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if not case_id or not template_id or not label or not summary:
                raise CatalogImportError(f"Incomplete source-batch metadata for case: {case_id or '<unknown>'}")
            if template_id in seen_ids or label in seen_labels:
                raise CatalogImportError(f"Duplicate template ID or label: {template_id} / {label}")
            if not re.fullmatch(r"(?:t8c\d{3}|t8-case)-[a-z0-9-]+", template_id):
                raise CatalogImportError(f"Invalid stable template ID: {template_id}")
            record = records.get(case_id)
            if not record or record.get("case_handoff_status") != "adapter-ready":
                raise CatalogImportError(f"Case is not adapter-ready in the handoff registry: {case_id}")
            if set(record.get("models", [])) != {"h3", "seedance20"}:
                raise CatalogImportError(f"Case lacks both model targets: {case_id}")
            case_dir = Path(str(record.get("case_path", ""))).resolve()
            case_path = case_dir / "case.json"
            case = _read_json(case_path)
            if case.get("case_id") != case_id or case.get("state") != "released":
                raise CatalogImportError(f"Canonical case is not released or has drifted: {case_id}")
            h3_recipe, h3_path = _adapter(case_dir, case_id, "h3")
            seed_recipe, seed_path = _adapter(case_dir, case_id, "seedance20")
            shared_template = h3_recipe["inputs"]["reference_template"].strip()
            if shared_template != seed_recipe["inputs"]["reference_template"].strip():
                raise CatalogImportError(f"Dual-model adapters disagree on Creative DNA: {case_id}")
            if SECRET_RE.search(shared_template) or URL_RE.search(shared_template):
                raise CatalogImportError(f"Template contains a secret-like token or URL: {case_id}")
            if str(case_dir).lower() in shared_template.lower():
                raise CatalogImportError(f"Template leaks a local case path: {case_id}")
            actual_hashes = {
                "case_sha256": _sha256(case_path),
                "creative_dna_sha256": _sha256(case_dir / "creative-dna.json"),
                "h3_adapter_sha256": _sha256(h3_path),
                "seedance20_adapter_sha256": _sha256(seed_path),
            }
            for field, actual in actual_hashes.items():
                expected = str(item.get(field, "")).strip().lower()
                if expected and expected != actual:
                    raise CatalogImportError(f"Source-batch hash drift: {case_id}: {field}")
            source = {
                "batch_id": batch.get("batch_id"),
                "case_id": case_id,
                "case_sha256": actual_hashes["case_sha256"],
                "release_score": record.get("release_score"),
                "h3_adapter_sha256": actual_hashes["h3_adapter_sha256"],
                "seedance20_adapter_sha256": actual_hashes["seedance20_adapter_sha256"],
            }
            if item.get("creative_dna_sha256"):
                source["creative_dna_sha256"] = actual_hashes["creative_dna_sha256"]
            if item.get("mechanism_fingerprint"):
                mechanism_fingerprint = str(item["mechanism_fingerprint"]).strip().lower()
                if not re.fullmatch(r"[0-9a-f]{64}", mechanism_fingerprint):
                    raise CatalogImportError(f"Invalid mechanism fingerprint: {case_id}")
                source["mechanism_fingerprint"] = mechanism_fingerprint
            templates.append({
                "id": template_id,
                "label": label,
                "summary": summary,
                "status": "active",
                "authority": batch.get("authority", "T8 精选案例（非官方）"),
                "official": False,
                "source": source,
                "creative_dna": shared_template,
                "variants": {
                    "h3": {"guidance": H3_GUIDANCE},
                    "seedance20": {"guidance": SEEDANCE20_GUIDANCE},
                },
            })
            seen_ids.add(template_id)
            seen_labels.add(label)
    if not templates:
        raise CatalogImportError("Source batch produced no active templates")
    return {
        "schema_version": "t8-case-template-catalog/v1",
        "catalog_id": f"t8-curated-{str(batches[-1].get('batch_id')).removeprefix('batch-')}",
        "authority": next(iter(authorities)),
        "default": NO_CASE_TEMPLATE,
        "templates": templates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the distributable T8 non-official case-template catalog.")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    catalog = build_catalog(args.registry.resolve(), [path.resolve() for path in args.batch])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog['templates'])} templates to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
