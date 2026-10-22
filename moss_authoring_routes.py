"""Explicit, same-origin Director inspection; never invokes a provider."""
from __future__ import annotations

import sys

from . import moss_authoring_state as state
from .completion_recovery_routes import _same_origin_request

_REGISTERED = False


def _safe_same_origin(request):
    try:
        return _same_origin_request(request)
    except (ValueError, TypeError):
        return False


def register_moss_authoring_routes():
    global _REGISTERED
    if _REGISTERED:
        return True
    # Registration must not import the host's graph/model stack on CPU tooling.
    server = sys.modules.get("server")
    PromptServer = getattr(server, "PromptServer", None)
    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return False
    try:
        from aiohttp import web
    except ImportError:
        return False

    async def inspect_status(request):
        if not _safe_same_origin(request):
            return web.json_response({"error": "Same-origin access required"}, status=403, headers={"Cache-Control": "no-store"})
        return web.json_response(state.status(request.match_info.get("slot", "")), headers={"Cache-Control": "no-store"})

    async def inspect_draft(request):
        if not _safe_same_origin(request):
            return web.json_response({"error": "Same-origin access required"}, status=403, headers={"Cache-Control": "no-store"})
        result = state.draft(request.match_info.get("slot", ""))
        if result is None:
            return web.json_response({"error": "No retained inspection draft / 无保留检查稿。"}, status=404,
                                     headers={"Cache-Control": "no-store"})
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    instance.routes.get("/t8-prompt-enhancer/moss-authoring/status/{slot}")(inspect_status)
    instance.routes.get("/t8-prompt-enhancer/moss-authoring/draft/{slot}")(inspect_draft)
    _REGISTERED = True
    return True
