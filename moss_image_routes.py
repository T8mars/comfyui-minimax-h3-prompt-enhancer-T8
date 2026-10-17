"""Read-only, opt-in MOSS failed-draft inspection. Never invokes a provider."""
from __future__ import annotations

import sys

from . import moss_image_state as state
from .completion_recovery_routes import _same_origin_request

_REGISTERED = False


def _safe_same_origin(request):
    try:
        return _same_origin_request(request)
    except (ValueError, TypeError):
        return False


def register_moss_image_routes():
    global _REGISTERED
    if _REGISTERED:
        return True
    # A plain node/schema import must not import Comfy's server/execution/model
    # graph. In CPU tooling that can eagerly initialize optional CUDA kernels.
    # A real Comfy host loads server before loading custom-node extensions.
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
            return web.json_response({"error": "No retained failed draft / 无可用失败草稿。"}, status=404,
                                     headers={"Cache-Control": "no-store"})
        return web.json_response(result, headers={"Cache-Control": "no-store"})

    instance.routes.get("/t8-prompt-enhancer/moss-image/status/{slot}")(inspect_status)
    instance.routes.get("/t8-prompt-enhancer/moss-image/draft/{slot}")(inspect_draft)
    _REGISTERED = True
    return True
