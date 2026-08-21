from __future__ import annotations

import sys

from .execution_diagnostics import diagnostics_snapshot


_REGISTERED = False


def register_diagnostics_routes() -> bool:
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
    if PromptServer is None:
        return False

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        return False

    async def diagnostics_route(_request):
        return web.json_response(
            diagnostics_snapshot(),
            headers={"Cache-Control": "no-store"},
        )

    try:
        prompt_server.routes.get("/t8-prompt-enhancer/diagnostics")(diagnostics_route)
    except RuntimeError as error:
        if "already registered" not in str(error).lower():
            raise

    _REGISTERED = True
    return True
