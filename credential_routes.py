from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlsplit

from .credential_store import (
    CredentialStoreError,
    delete_credential,
    get_credential,
    list_credential_aliases,
    save_credential,
)

try:
    from . import credential_connection_probe as _credential_connection_probe
    test_cloud_connection = _credential_connection_probe.test_cloud_connection
    requests = _credential_connection_probe.requests
except ImportError:
    requests = None
    test_cloud_connection = None


_REGISTERED = False


def _connection_target(provider: str, base_url: str, model: str) -> tuple[str, str]:
    from .nodes import (
        AI_WORKSHOP_CHAT_COMPLETIONS_URL,
        AI_WORKSHOP_DEFAULT_MODEL,
        CHAT_COMPLETIONS_URL,
        MODEL_ID,
        _openai_chat_url,
    )

    if provider == "Seedance NZ":
        return CHAT_COMPLETIONS_URL, MODEL_ID
    if provider == "T8 AI Workshop":
        return AI_WORKSHOP_CHAT_COMPLETIONS_URL, model.strip() or AI_WORKSHOP_DEFAULT_MODEL
    if provider == "OpenAI Compatible":
        if not model.strip():
            raise CredentialStoreError("Custom model ID is required for an OpenAI-compatible connection test.")
        try:
            return _openai_chat_url(base_url), model.strip()
        except Exception as exc:
            raise CredentialStoreError("OpenAI-compatible Base URL is invalid.") from exc
    raise CredentialStoreError("Connection testing is available for cloud providers only.")


def _test_cloud_connection(alias, provider, base_url="", model="") -> dict[str, object]:
    secret = get_credential(alias)
    chat_url, model_id = _connection_target(str(provider or ""), str(base_url or ""), str(model or ""))
    if test_cloud_connection is None:
        return {"connected": False, "category": "github_full_install_required"}
    return test_cloud_connection(secret, chat_url, model_id)


def _same_origin_request(request) -> bool:
    fetch_site = str(request.headers.get("Sec-Fetch-Site", "")).lower()
    if fetch_site and fetch_site not in {"same-origin", "same-site", "none"}:
        return False
    origin = str(request.headers.get("Origin", "")).strip()
    if origin:
        parsed = urlsplit(origin)
        return parsed.netloc.casefold() == str(request.host or "").casefold()
    remote = str(getattr(request, "remote", "") or "")
    return fetch_site in {"same-origin", "same-site", "none"} or remote in {"127.0.0.1", "::1"}


def register_credential_routes() -> bool:
    global _REGISTERED
    if _REGISTERED:
        return True
    server_module = sys.modules.get("server")
    if server_module is None:
        return False
    try:
        from aiohttp import web
    except ImportError:
        return False
    PromptServer = getattr(server_module, "PromptServer", None)
    prompt_server = getattr(PromptServer, "instance", None) if PromptServer is not None else None
    if prompt_server is None:
        return False

    async def list_route(request):
        if not _same_origin_request(request):
            raise web.HTTPForbidden(text="same-origin request required")
        try:
            aliases = list_credential_aliases()
        except CredentialStoreError:
            raise web.HTTPInternalServerError(text="credential store unavailable")
        return web.json_response(
            {"schema_version": "t8-credential-aliases/v1", "aliases": aliases},
            headers={"Cache-Control": "no-store"},
        )

    async def update_route(request):
        if not _same_origin_request(request):
            raise web.HTTPForbidden(text="same-origin request required")
        if request.content_length is not None and request.content_length > 8192:
            raise web.HTTPRequestEntityTooLarge(max_size=8192, actual_size=request.content_length)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid JSON")
        action = str(body.get("action", ""))
        try:
            if action == "save":
                save_credential(body.get("alias"), body.get("secret"))
                result = {"saved": True}
            elif action == "delete":
                if body.get("confirmed") is not True:
                    raise web.HTTPBadRequest(text="explicit confirmation required")
                result = {"deleted": delete_credential(body.get("alias"))}
            elif action == "check":
                get_credential(body.get("alias"))
                result = {"configured": True}
            elif action == "test_connection":
                result = await asyncio.to_thread(
                    _test_cloud_connection,
                    body.get("alias"),
                    body.get("provider"),
                    body.get("base_url"),
                    body.get("model"),
                )
            else:
                raise web.HTTPBadRequest(text="unsupported action")
        except CredentialStoreError as error:
            raise web.HTTPBadRequest(text=str(error))
        return web.json_response(
            {"schema_version": "t8-credential-operation/v1", **result},
            headers={"Cache-Control": "no-store"},
        )

    try:
        prompt_server.routes.get("/t8-prompt-enhancer/credentials")(list_route)
        prompt_server.routes.post("/t8-prompt-enhancer/credentials")(update_route)
    except RuntimeError as error:
        if "already registered" not in str(error).lower():
            raise
    _REGISTERED = True
    return True


__all__ = ["register_credential_routes", "_test_cloud_connection"]
