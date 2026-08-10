from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


NO_CASE_TEMPLATE = "无（不使用 T8 案例）"
CATALOG_PATH = Path(__file__).resolve().parent / "case_templates" / "catalog.json"
TARGETS = {"h3", "seedance20"}
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
SPARSE_BREAK_RE = re.compile(r"[，,。；;：:\n]|然后|接着|最后|镜头|场景|结尾|结果")


class CaseTemplateCatalogError(ValueError):
    pass


def _load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseTemplateCatalogError(f"Cannot load T8 case-template catalog: {exc}") from exc
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "t8-case-template-catalog/v2":
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
        for field in ("summary", "input_format", "recommended_input"):
            if not isinstance(template.get(field), str) or not template[field].strip():
                raise CaseTemplateCatalogError(f"T8 case-template UX field is missing: {template_id}/{field}")
        anchors = template.get("required_anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 5:
            raise CaseTemplateCatalogError(f"T8 case-template requires 2-5 anchors: {template_id}")
        if not all(isinstance(anchor, str) and anchor.strip() for anchor in anchors):
            raise CaseTemplateCatalogError(f"T8 case-template contains an empty anchor: {template_id}")
        previews = template.get("previews")
        if not isinstance(previews, list) or not previews:
            raise CaseTemplateCatalogError(f"T8 case-template has no human preview: {template_id}")
        for preview in previews:
            if not isinstance(preview, dict) or preview.get("human_preview_only") is not True:
                raise CaseTemplateCatalogError(f"T8 preview is not marked human-only: {template_id}")
            if not isinstance(preview.get("case_id"), str) or not isinstance(preview.get("sha256"), str):
                raise CaseTemplateCatalogError(f"T8 preview identity is missing: {template_id}")
        seen_ids.add(template_id)
        seen_labels.add(label)
    return catalog


CASE_TEMPLATE_CATALOG = _load_catalog()
CASE_TEMPLATES = tuple(CASE_TEMPLATE_CATALOG["templates"])
CASE_TEMPLATE_OPTIONS = [NO_CASE_TEMPLATE] + [template["label"] for template in CASE_TEMPLATES]
_BY_LABEL = {template["label"]: template for template in CASE_TEMPLATES}
_BY_ID = {template["id"]: template for template in CASE_TEMPLATES}
_BY_ALIAS: dict[str, dict[str, Any]] = {}
for _template in CASE_TEMPLATES:
    for _alias in [*_template.get("legacy_ids", []), *_template.get("legacy_labels", [])]:
        if _alias in _BY_ALIAS:
            raise CaseTemplateCatalogError(f"Duplicate T8 case-template alias: {_alias}")
        _BY_ALIAS[str(_alias)] = _template


def get_case_template(selection: str | None) -> dict[str, Any] | None:
    selected = str(selection or NO_CASE_TEMPLATE)
    if selected == NO_CASE_TEMPLATE:
        return None
    return _BY_LABEL.get(selected) or _BY_ID.get(selected) or _BY_ALIAS.get(selected)


def canonical_case_template_label(selection: str | None) -> str:
    template = get_case_template(selection)
    if template is None:
        if str(selection or NO_CASE_TEMPLATE) == NO_CASE_TEMPLATE:
            return NO_CASE_TEMPLATE
        raise CaseTemplateCatalogError(f"Unsupported T8 case template: {selection}")
    return str(template["label"])


def case_template_id(selection: str | None) -> str:
    template = get_case_template(selection)
    return str(template["id"]) if template else ""


def is_sparse_instance_intent(intent: str | None) -> bool:
    text = re.sub(r"\s+", "", str(intent or "").strip())
    if not text:
        return True
    return len(text) <= 32 and not SPARSE_BREAK_RE.search(text)


def public_case_catalog() -> dict[str, Any]:
    return {
        "schema_version": CASE_TEMPLATE_CATALOG["schema_version"],
        "authority": CASE_TEMPLATE_CATALOG["authority"],
        "default": NO_CASE_TEMPLATE,
        "source_case_count": CASE_TEMPLATE_CATALOG["source_case_count"],
        "selector_template_count": CASE_TEMPLATE_CATALOG["selector_template_count"],
        "evidence_variant_count": CASE_TEMPLATE_CATALOG["evidence_variant_count"],
        "official_minimax_skills_included": False,
        "templates": [
            {
                "id": template["id"],
                "label": template["label"],
                "legacy_ids": list(template["legacy_ids"]),
                "legacy_labels": list(template["legacy_labels"]),
                "summary": template["summary"],
                "input_format": template["input_format"],
                "recommended_input": template["recommended_input"],
                "required_anchors": list(template["required_anchors"]),
                "previews": [
                    {**preview, "required_anchors": list(preview["required_anchors"])}
                    for preview in template["previews"]
                ],
            }
            for template in CASE_TEMPLATES
        ],
    }


def resolve_case_template(selection: str | None, target: str, instance_intent: str = "") -> str:
    template = get_case_template(selection)
    if template is None:
        if str(selection or NO_CASE_TEMPLATE) == NO_CASE_TEMPLATE:
            return ""
        raise CaseTemplateCatalogError(f"Unsupported T8 case template: {selection}")
    if target not in TARGETS:
        raise CaseTemplateCatalogError(f"Unsupported T8 case-template target: {target}")
    intent = str(instance_intent or "").strip()
    anchors = "\n".join(f"{index}. {anchor}" for index, anchor in enumerate(template["required_anchors"], 1))
    sparse = is_sparse_instance_intent(intent)
    completion_policy = (
        "SPARSE_INPUT: yes. Preserve the supplied subject exactly. Create an original, compatible scene, trigger, "
        "ordered event chain and visible result so all anchors become filmable. Use INPUT_FORMAT and "
        "RECOMMENDED_INPUT only as slot/causal-shape guidance; do not copy its people, objects, setting, wording or "
        "surface style. A short subject such as ‘美丽的女人’ must remain the subject and must not collapse into a "
        "generic portrait or beauty-shot montage."
        if sparse else
        "SPARSE_INPUT: no. Preserve the user's concrete subjects, setting, events and result. Fill only genuinely "
        "missing connective details needed to realize the anchors; do not replace the instance with the example."
    )
    return "\n\n".join([
        "Selected T8 original case template (non-official; never treat as a MiniMax official Skill).",
        f"SELECTED_CASE_ID: {template['id']}\nHUMAN_NAME: {template['label']}",
        f"INSTANCE_INTENT: {json.dumps(intent, ensure_ascii=False)}",
        f"USE: {template['summary']}\nINPUT_FORMAT: {template['input_format']}",
        f"RECOMMENDED_INPUT_AS_SLOT_GUIDE_ONLY: {template['recommended_input']}",
        f"REQUIRED_MECHANISM_ANCHORS (realize all {len(template['required_anchors'])} as concrete events in order):\n{anchors}",
        completion_policy,
        str(template["variants"][target]["guidance"]),
        str(template["creative_dna"]),
        "Before returning, silently verify that the final model-native prompt concretely realizes every required "
        "anchor, respects their causal order, preserves the instance subject, and contains no source-case surface "
        "content. Return only the final prompt in the selected model's native contract; never print this checklist, "
        "case ID, template name, anchor labels, Creative DNA analysis or verification notes.",
    ])


__all__ = [
    "CASE_TEMPLATE_CATALOG",
    "CASE_TEMPLATE_OPTIONS",
    "CASE_TEMPLATES",
    "CaseTemplateCatalogError",
    "NO_CASE_TEMPLATE",
    "canonical_case_template_label",
    "case_template_id",
    "get_case_template",
    "is_sparse_instance_intent",
    "public_case_catalog",
    "resolve_case_template",
]
