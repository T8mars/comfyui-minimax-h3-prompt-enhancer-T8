from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .case_templates import CASE_TEMPLATES, public_case_catalog


LOCAL_CONFIG_PATH = Path(__file__).resolve().parent / ".t8-case-library.local.json"
MANIFEST_ENV = "T8_UNOFFICIAL_CASE_LIBRARY_V2"
COMMUNITY_MANIFEST_ENV = "T8_STANDALONE_COMMUNITY_SKILLS_V1"
LIBRARY_SCHEMA = "t8-unofficial-case-library/v2"
COMMUNITY_LIBRARY_SCHEMA = "t8-standalone-community-skill-handoff/v1"
_REGISTERED = False


class CasePreviewError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_config() -> dict[str, Any]:
    if not LOCAL_CONFIG_PATH.is_file():
        return {}
    try:
        config = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CasePreviewError(f"Cannot read local case-library config: {exc}") from exc
    if not isinstance(config, dict):
        raise CasePreviewError("Local case-library config must be a JSON object")
    return config


def configured_manifest_path() -> Path | None:
    env_path = str(os.environ.get(MANIFEST_ENV, "")).strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    manifest_path = str(_local_config().get("manifest_path", "")).strip()
    return Path(manifest_path).expanduser().resolve() if manifest_path else None


def configured_community_manifest_path() -> Path | None:
    env_path = str(os.environ.get(COMMUNITY_MANIFEST_ENV, "")).strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    config_path = str(_local_config().get("community_skills_manifest_path", "")).strip()
    if config_path:
        return Path(config_path).expanduser().resolve()
    case_manifest = configured_manifest_path()
    sibling = case_manifest.parent / "standalone-community-skills-v1.json" if case_manifest else None
    return sibling.resolve() if sibling and sibling.is_file() else None


def _runtime_case_records() -> dict[str, dict[str, Any]]:
    manifest_path = configured_manifest_path()
    if manifest_path is None or not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CasePreviewError(f"Cannot read local unofficial case library: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != LIBRARY_SCHEMA:
        raise CasePreviewError("Unsupported local unofficial case-library schema")
    if manifest.get("contract", {}).get("official_minimax_skills_included") is not False:
        raise CasePreviewError("Local library mixes official MiniMax Skills into the unofficial cases")
    records: dict[str, dict[str, Any]] = {}
    for record in manifest.get("records", []):
        if isinstance(record, dict) and isinstance(record.get("case_id"), str):
            records[str(record["case_id"])] = {**record, "_template_kind": "case"}
    return records


def _runtime_community_records() -> dict[str, dict[str, Any]]:
    manifest_path = configured_community_manifest_path()
    if manifest_path is None or not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CasePreviewError(f"Cannot read local community-Skill manifest: {exc}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != COMMUNITY_LIBRARY_SCHEMA
        or manifest.get("official") is not False
    ):
        raise CasePreviewError("Unsupported local standalone community-Skill manifest")
    source_index = Path(str(manifest.get("source_index", ""))).resolve()
    if not source_index.is_file():
        raise CasePreviewError("Local community-Skill source index is missing")
    try:
        source_index_data = json.loads(source_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CasePreviewError(f"Cannot read local community-Skill source index: {exc}") from exc
    indexed_ids = {
        str(item.get("id"))
        for item in source_index_data.get("skills", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(source_index_data, dict) else set()
    if (
        not isinstance(source_index_data, dict)
        or source_index_data.get("schema_version") != "public-community-skill-index/v1"
        or source_index_data.get("official") is not False
    ):
        raise CasePreviewError("Unsupported local community-Skill source index")
    records: dict[str, dict[str, Any]] = {}
    for record in manifest.get("records", []):
        if not isinstance(record, dict) or not isinstance(record.get("skill_id"), str):
            continue
        if record["skill_id"] not in indexed_ids:
            raise CasePreviewError("Community Skill is absent from the configured source index")
        preview_id = f"community-skill--{record['skill_id']}"
        records[preview_id] = {
            **record,
            "_template_kind": "community_skill",
            "_source_index": str(source_index),
        }
    return records


def _runtime_records() -> dict[str, dict[str, Any]]:
    records = _runtime_case_records()
    community = _runtime_community_records()
    if set(records).intersection(community):
        raise CasePreviewError("Local case and community preview identities collide")
    records.update(community)
    return records


def _allowed_previews() -> dict[str, dict[str, Any]]:
    allowed: dict[str, dict[str, Any]] = {}
    for template in CASE_TEMPLATES:
        for preview in template["previews"]:
            allowed[preview["case_id"]] = preview
    return allowed


def resolve_preview(case_id: str, *, verify_hash: bool = True) -> tuple[Path, dict[str, Any]]:
    allowed = _allowed_previews().get(str(case_id))
    runtime = _runtime_records().get(str(case_id))
    if allowed is None or runtime is None:
        raise CasePreviewError("Local preview is not configured for this case")
    preview = runtime.get("preview", {})
    if preview.get("sha256") != allowed.get("sha256"):
        raise CasePreviewError("Local preview metadata does not match the installed selector catalog")
    if runtime.get("_template_kind") == "community_skill":
        policy = runtime.get("import_policy", {})
        if (
            runtime.get("official") is not False
            or policy.get("preview_only") is not True
            or policy.get("source_media_connected") is not False
            or policy.get("create_selector") is not True
        ):
            raise CasePreviewError("This community Skill is not authorized for local human preview")
        preview_path = Path(str(preview.get("path", ""))).resolve()
        preview_root = Path(str(runtime.get("_source_index", ""))).resolve().parent
        try:
            preview_path.relative_to(preview_root)
        except ValueError as exc:
            raise CasePreviewError("Community preview path escapes the indexed preview directory") from exc
    else:
        rights = runtime.get("rights", {})
        if rights.get("local_preview") is not True or rights.get("model_reference") is not False:
            raise CasePreviewError("This case is not authorized for local human preview")
        case_root = Path(str(runtime.get("case_path", ""))).resolve()
        relative = Path(str(preview.get("path", "preview.gif")))
        if relative.is_absolute() or ".." in relative.parts:
            raise CasePreviewError("Unsafe preview path")
        preview_path = (case_root / relative).resolve()
        try:
            preview_path.relative_to(case_root)
        except ValueError as exc:
            raise CasePreviewError("Preview path escapes its case directory") from exc
    if preview_path.suffix.lower() != ".gif" or not preview_path.is_file():
        raise CasePreviewError("Local preview file is missing")
    with preview_path.open("rb") as handle:
        if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
            raise CasePreviewError("Local preview file is not a GIF")
    if verify_hash and _sha256(preview_path) != allowed["sha256"]:
        raise CasePreviewError("Local preview hash does not match the installed selector catalog")
    return preview_path, runtime


def runtime_public_catalog() -> dict[str, Any]:
    catalog = public_case_catalog()
    runtime = _runtime_records()
    for template in catalog["templates"]:
        for preview in template["previews"]:
            record = runtime.get(preview["case_id"])
            preview["available"] = False
            preview["preview_url"] = ""
            preview["source_url"] = ""
            if record is None:
                continue
            try:
                resolve_preview(preview["case_id"], verify_hash=False)
            except CasePreviewError:
                continue
            preview["available"] = True
            preview["preview_url"] = f"/t8-prompt-enhancer/case-preview/{preview['case_id']}"
            if record.get("_template_kind") == "case":
                source_url = str(record.get("source", {}).get("canonical_url", ""))
                preview["source_url"] = source_url if source_url.startswith(("https://", "http://")) else ""
    catalog["preview_manifest_configured"] = any(
        path is not None for path in (configured_manifest_path(), configured_community_manifest_path())
    )
    catalog["preview_policy"] = "GIF is for local human preview only and is never sent to the LLM."
    return catalog


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return
    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        return

    async def catalog_route(_request: Any) -> Any:
        try:
            return web.json_response(runtime_public_catalog(), headers={"Cache-Control": "no-store"})
        except CasePreviewError as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def preview_route(request: Any) -> Any:
        try:
            path, _record = resolve_preview(request.match_info["case_id"], verify_hash=True)
            return web.FileResponse(
                path,
                headers={"Cache-Control": "private, max-age=300", "X-T8-Preview-Only": "human"},
            )
        except CasePreviewError as exc:
            return web.json_response({"error": str(exc)}, status=404)

    try:
        prompt_server.routes.get("/t8-prompt-enhancer/case-library")(catalog_route)
        prompt_server.routes.get("/t8-prompt-enhancer/case-preview/{case_id}")(preview_route)
    except RuntimeError as exc:
        if "already registered" not in str(exc).lower():
            raise
    _REGISTERED = True


__all__ = [
    "CasePreviewError",
    "configured_community_manifest_path",
    "configured_manifest_path",
    "register_routes",
    "resolve_preview",
    "runtime_public_catalog",
]
