from __future__ import annotations

import sys
from typing import Any

from .local_qwen_runtime import runtime_status


_REGISTERED = False


def register_local_qwen_routes() -> None:
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

    async def status_route(request: Any) -> Any:
        refresh = str(request.query.get("refresh", "")).casefold() in {"1", "true", "yes"}
        return web.json_response(
            {
                **runtime_status(refresh=refresh),
                "provider": "local_llama_cpp_gguf",
                "vision_mode": "timestamped_sampled_frames_no_audio",
                "music_mode": "text_only_no_mmproj",
                "install_command": "python install_local_qwen.py",
            },
            headers={"Cache-Control": "no-store"},
        )

    try:
        prompt_server.routes.get("/t8-prompt-enhancer/local-qwen/status")(status_route)
    except RuntimeError as error:
        if "already registered" not in str(error).lower():
            raise
    _REGISTERED = True


__all__ = ["register_local_qwen_routes"]
