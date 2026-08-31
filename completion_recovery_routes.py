from __future__ import annotations

import sys
from urllib.parse import urlsplit

from .completion_recovery import CompletionRecoveryError, recovery_status


_REGISTERED = False


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


def register_completion_recovery_routes() -> bool:
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

    async def status_route(request):
        if not _same_origin_request(request):
            raise web.HTTPForbidden(text="same-origin request required")
        try:
            result = recovery_status(request.match_info.get("component"), request.match_info.get("slot"))
        except CompletionRecoveryError as error:
            raise web.HTTPBadRequest(text=str(error))
        return web.json_response(
            {"schema_version": "t8-completion-recovery-status/v1", **result},
            headers={"Cache-Control": "no-store"},
        )

    try:
        prompt_server.routes.get(
            "/t8-prompt-enhancer/completion-recovery/{component}/{slot}"
        )(status_route)
    except RuntimeError as error:
        if "already registered" not in str(error).lower():
            raise
    _REGISTERED = True
    return True


__all__ = ["register_completion_recovery_routes"]
