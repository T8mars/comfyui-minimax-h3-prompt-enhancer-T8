from __future__ import annotations

import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .case_templates import CASE_TEMPLATES, public_case_catalog
from .preview_asset_manager import PreviewAssetError, preview_asset_manager

try:
    from .environment_defaults import optional_environment_value
except ImportError:
    try:
        from environment_defaults import optional_environment_value
    except ImportError:
        def optional_environment_value(_name: str) -> str:
            return ""


LOCAL_CONFIG_PATH = Path(__file__).resolve().parent / ".t8-case-library.local.json"
MANIFEST_ENV = "T8_UNOFFICIAL_CASE_LIBRARY_V2"
COMMUNITY_MANIFEST_ENV = "T8_STANDALONE_COMMUNITY_SKILLS_V1"
LIBRARY_SCHEMA = "t8-unofficial-case-library/v2"
COMMUNITY_LIBRARY_SCHEMA = "t8-standalone-community-skill-handoff/v1"
BUNDLED_PREVIEW_SCHEMA = "t8-bundled-case-previews/v1"
BUNDLED_PREVIEW_ROOT = Path(__file__).resolve().parent / "web" / "js" / "assets" / "t8-case-previews"
BUNDLED_PREVIEW_MANIFEST = BUNDLED_PREVIEW_ROOT / "manifest.json"
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
    env_path = optional_environment_value(MANIFEST_ENV)
    if env_path:
        return Path(env_path).expanduser().resolve()
    manifest_path = str(_local_config().get("manifest_path", "")).strip()
    return Path(manifest_path).expanduser().resolve() if manifest_path else None


def configured_community_manifest_path() -> Path | None:
    env_path = optional_environment_value(COMMUNITY_MANIFEST_ENV)
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


@lru_cache(maxsize=1)
def _bundled_preview_records() -> dict[str, dict[str, Any]]:
    if not BUNDLED_PREVIEW_MANIFEST.is_file():
        return {}
    try:
        manifest = json.loads(BUNDLED_PREVIEW_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CasePreviewError(f"Cannot read bundled T8 preview manifest: {exc}") from exc
    entries = manifest.get("previews") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != BUNDLED_PREVIEW_SCHEMA
        or manifest.get("catalog_id") != "t8-unofficial-case-library-v2"
        or not isinstance(entries, list)
        or manifest.get("preview_count") != len(entries)
    ):
        raise CasePreviewError("Unsupported bundled T8 preview manifest")
    allowed = _allowed_previews()
    records: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise CasePreviewError("Bundled T8 preview entry is not an object")
        case_id = str(entry.get("case_id", ""))
        filename = Path(str(entry.get("file", "")))
        expected = allowed.get(case_id)
        if (
            not case_id
            or case_id in records
            or expected is None
            or entry.get("human_preview_only") is not True
            or entry.get("source_sha256") != expected.get("sha256")
            or filename.name != str(filename)
            or filename.suffix.lower() != ".gif"
        ):
            raise CasePreviewError(f"Bundled T8 preview identity mismatch: {case_id}")
        path = (BUNDLED_PREVIEW_ROOT / filename).resolve()
        try:
            path.relative_to(BUNDLED_PREVIEW_ROOT.resolve())
        except ValueError as exc:
            raise CasePreviewError("Bundled T8 preview path escapes its asset directory") from exc
        if not path.is_file():
            continue
        if path.stat().st_size != int(entry.get("bytes", -1)):
            raise CasePreviewError(f"Bundled T8 preview file is truncated: {case_id}")
        with path.open("rb") as handle:
            if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
                raise CasePreviewError(f"Bundled T8 preview is not a GIF: {case_id}")
        if _sha256(path) != entry.get("sha256"):
            raise CasePreviewError(f"Bundled T8 preview SHA-256 mismatch: {case_id}")
        records[case_id] = {
            **entry,
            "_template_kind": "bundled",
            "_path": path,
        }
    return records


def _resolve_local_preview(
    case_id: str,
    allowed: dict[str, Any],
    runtime: dict[str, Any],
    *,
    verify_hash: bool,
) -> tuple[Path, dict[str, Any]]:
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


def resolve_preview(case_id: str, *, verify_hash: bool = True) -> tuple[Path, dict[str, Any]]:
    preview_id = str(case_id)
    allowed = _allowed_previews().get(preview_id)
    if allowed is None:
        raise CasePreviewError("Unknown T8 preview identity")
    runtime = _runtime_records().get(preview_id)
    local_error: CasePreviewError | None = None
    if runtime is not None:
        try:
            return _resolve_local_preview(preview_id, allowed, runtime, verify_hash=verify_hash)
        except CasePreviewError as exc:
            local_error = exc
    bundled = _bundled_preview_records().get(preview_id)
    if bundled is not None:
        return Path(bundled["_path"]), bundled
    cached = preview_asset_manager().cached_path(
        preview_id, _allowed_previews(), verify_hash=verify_hash
    )
    if cached is not None:
        return cached
    if local_error is not None:
        raise local_error
    raise CasePreviewError("T8 preview is neither bundled nor configured locally")


def runtime_public_catalog() -> dict[str, Any]:
    catalog = public_case_catalog()
    runtime = _runtime_records()
    bundled = _bundled_preview_records()
    allowed = _allowed_previews()
    manager = preview_asset_manager()
    preview_settings = manager.settings()
    for template in catalog["templates"]:
        for preview in template["previews"]:
            record = runtime.get(preview["case_id"])
            preview["available"] = False
            preview["preview_url"] = ""
            preview["source_url"] = ""
            preview.update(manager.availability(preview["case_id"], allowed))
            preview["auto_download"] = preview_settings["mode"] != "manual"
            try:
                resolve_preview(preview["case_id"], verify_hash=False)
            except CasePreviewError:
                continue
            preview["available"] = True
            preview["preview_url"] = f"/t8-prompt-enhancer/case-preview/{preview['case_id']}"
            if record is not None and record.get("_template_kind") == "case":
                source_url = str(record.get("source", {}).get("canonical_url", ""))
                preview["source_url"] = source_url if source_url.startswith(("https://", "http://")) else ""
    catalog["preview_manifest_configured"] = any(
        path is not None for path in (configured_manifest_path(), configured_community_manifest_path())
    )
    catalog["bundled_preview_count"] = len(bundled)
    catalog["bundled_previews_included"] = len(bundled) == sum(
        len(template["previews"]) for template in catalog["templates"]
    )
    catalog["preview_asset_status"] = manager.status(allowed)
    catalog["preview_policy"] = (
        "GIF is a bundled/local/cached human UI preview only and is never sent to the LLM."
    )
    return catalog


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    server_module = sys.modules.get("server")
    if server_module is None:
        return
    try:
        from aiohttp import web
    except ImportError:
        return
    PromptServer = getattr(server_module, "PromptServer", None)
    if PromptServer is None:
        return
    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        return

    async def catalog_route(_request: Any) -> Any:
        try:
            catalog = runtime_public_catalog()
            preview_asset_manager().schedule_full_install(_allowed_previews())
            return web.json_response(catalog, headers={"Cache-Control": "no-store"})
        except CasePreviewError as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def preview_route(request: Any) -> Any:
        try:
            path, record = resolve_preview(request.match_info["case_id"], verify_hash=True)
            cache_control = (
                "public, max-age=31536000, immutable"
                if record.get("_template_kind") in {"bundled", "cache"}
                else "private, max-age=300"
            )
            return web.FileResponse(
                path,
                headers={"Cache-Control": cache_control, "X-T8-Preview-Only": "human"},
            )
        except CasePreviewError as exc:
            return web.json_response({"error": str(exc)}, status=404)

    async def asset_status_route(_request: Any) -> Any:
        return web.json_response(
            preview_asset_manager().status(_allowed_previews()),
            headers={"Cache-Control": "no-store"},
        )

    async def asset_check_route(_request: Any) -> Any:
        try:
            await preview_asset_manager().check_remote(_allowed_previews())
            return web.json_response(preview_asset_manager().status(_allowed_previews()))
        except PreviewAssetError as exc:
            return web.json_response({"error": str(exc)}, status=502)

    async def asset_ensure_route(request: Any) -> Any:
        case_id = str(request.match_info.get("case_id") or "")
        try:
            await preview_asset_manager().ensure(case_id, _allowed_previews())
            return web.json_response({
                "case_id": case_id,
                "available": True,
                "preview_url": f"/t8-prompt-enhancer/case-preview/{case_id}",
            })
        except PreviewAssetError as exc:
            return web.json_response({"error": str(exc)}, status=502)

    async def asset_install_all_route(_request: Any) -> Any:
        try:
            result = await preview_asset_manager().install_all(_allowed_previews())
            return web.json_response(result)
        except PreviewAssetError as exc:
            return web.json_response({"error": str(exc)}, status=502)

    async def asset_repair_route(_request: Any) -> Any:
        try:
            result = await preview_asset_manager().install_all(
                _allowed_previews(), verify_existing=True
            )
            return web.json_response(result)
        except PreviewAssetError as exc:
            return web.json_response({"error": str(exc)}, status=502)

    async def asset_clear_route(_request: Any) -> Any:
        try:
            preview_asset_manager().clear()
            return web.json_response(preview_asset_manager().status(_allowed_previews()))
        except PreviewAssetError as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def asset_settings_route(request: Any) -> Any:
        try:
            payload = await request.json()
            result = preview_asset_manager().set_mode(
                str(payload.get("mode") or "") if isinstance(payload, dict) else ""
            )
            preview_asset_manager().schedule_full_install(_allowed_previews())
            return web.json_response(result)
        except (PreviewAssetError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    try:
        prompt_server.routes.get("/t8-prompt-enhancer/case-library")(catalog_route)
        prompt_server.routes.get("/t8-prompt-enhancer/case-preview/{case_id}")(preview_route)
        prompt_server.routes.get("/t8-prompt-enhancer/preview-assets/status")(asset_status_route)
        prompt_server.routes.post("/t8-prompt-enhancer/preview-assets/check")(asset_check_route)
        prompt_server.routes.post("/t8-prompt-enhancer/preview-assets/ensure/{case_id}")(asset_ensure_route)
        prompt_server.routes.post("/t8-prompt-enhancer/preview-assets/install-all")(asset_install_all_route)
        prompt_server.routes.post("/t8-prompt-enhancer/preview-assets/repair")(asset_repair_route)
        prompt_server.routes.delete("/t8-prompt-enhancer/preview-assets/cache")(asset_clear_route)
        prompt_server.routes.put("/t8-prompt-enhancer/preview-assets/settings")(asset_settings_route)
    except RuntimeError as exc:
        if "already registered" not in str(exc).lower():
            raise
    _REGISTERED = True


__all__ = [
    "CasePreviewError",
    "BUNDLED_PREVIEW_MANIFEST",
    "BUNDLED_PREVIEW_ROOT",
    "configured_community_manifest_path",
    "configured_manifest_path",
    "register_routes",
    "resolve_preview",
    "runtime_public_catalog",
]
