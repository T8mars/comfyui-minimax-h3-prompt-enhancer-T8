from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


NO_CASE_TEMPLATE = "无（不使用 T8 案例）"
CATALOG_PATH = Path(__file__).resolve().parent / "case_templates" / "catalog.json"
TARGETS = {"h3", "seedance20"}
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


class CaseTemplateCatalogError(ValueError):
    pass


def _load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseTemplateCatalogError(f"Cannot load T8 case-template catalog: {exc}") from exc
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "t8-case-template-catalog/v1":
        raise CaseTemplateCatalogError("Unsupported T8 case-template catalog schema")
    if catalog.get("default") != NO_CASE_TEMPLATE:
        raise CaseTemplateCatalogError("T8 case-template catalog default has drifted")
    templates = catalog.get("templates")
    if not isinstance(templates, list) or not templates:
        raise CaseTemplateCatalogError("T8 case-template catalog has no templates")
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for template in templates:
        if not isinstance(template, dict):
            raise CaseTemplateCatalogError("T8 case-template record is not an object")
        template_id = template.get("id")
        label = template.get("label")
        if not isinstance(template_id, str) or not isinstance(label, str) or not template_id or not label:
            raise CaseTemplateCatalogError("T8 case-template ID or label is missing")
        if template_id in seen_ids or label in seen_labels:
            raise CaseTemplateCatalogError(f"Duplicate T8 case-template ID or label: {template_id}")
        if template.get("status") != "active" or template.get("official") is not False:
            raise CaseTemplateCatalogError(f"Only active non-official templates may be exposed: {template_id}")
        dna = template.get("creative_dna")
        if not isinstance(dna, str) or not dna.strip() or SECRET_RE.search(dna):
            raise CaseTemplateCatalogError(f"Invalid Creative DNA for T8 case template: {template_id}")
        variants = template.get("variants")
        if not isinstance(variants, dict) or set(variants) != TARGETS:
            raise CaseTemplateCatalogError(f"T8 case template lacks exact dual-model variants: {template_id}")
        for target in TARGETS:
            guidance = variants[target].get("guidance") if isinstance(variants[target], dict) else None
            if not isinstance(guidance, str) or not guidance.strip():
                raise CaseTemplateCatalogError(f"T8 case-template guidance is missing: {template_id}/{target}")
        seen_ids.add(template_id)
        seen_labels.add(label)
    return catalog


CASE_TEMPLATE_CATALOG = _load_catalog()
CASE_TEMPLATES = tuple(CASE_TEMPLATE_CATALOG["templates"])
CASE_TEMPLATE_OPTIONS = [NO_CASE_TEMPLATE] + [template["label"] for template in CASE_TEMPLATES]
_BY_LABEL = {template["label"]: template for template in CASE_TEMPLATES}


def resolve_case_template(selection: str | None, target: str) -> str:
    selected = str(selection or NO_CASE_TEMPLATE)
    if selected == NO_CASE_TEMPLATE:
        return ""
    if target not in TARGETS:
        raise CaseTemplateCatalogError(f"Unsupported T8 case-template target: {target}")
    template = _BY_LABEL.get(selected)
    if template is None:
        raise CaseTemplateCatalogError(f"Unsupported T8 case template: {selected}")
    return "\n\n".join([
        f"Selected non-official T8 case template: {template['label']}",
        str(template["summary"]),
        str(template["variants"][target]["guidance"]),
        str(template["creative_dna"]),
    ])


__all__ = [
    "CASE_TEMPLATE_CATALOG",
    "CASE_TEMPLATE_OPTIONS",
    "CASE_TEMPLATES",
    "CaseTemplateCatalogError",
    "NO_CASE_TEMPLATE",
    "resolve_case_template",
]
