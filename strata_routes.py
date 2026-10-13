"""Same-origin/local, read-only service probe; never POSTs to Strata."""
from __future__ import annotations

import asyncio
import sys
import time

from .strata_provider import StrataSettings, StrataClient, StrataProviderError, validate_status

_REGISTERED = False


def probe_strata(values=None):
    settings = StrataSettings.from_values(values)
    client = StrataClient(settings)
    status = validate_status(client.request("/v1/status", timeout=5, check=None))
    model = status["model"]
    import re
    if not re.fullmatch(r"[A-Za-z0-9._/+\-]{1,128}", model) or re.search(r"sk-[A-Za-z0-9_-]{16,}", model):
        model = "[redacted-model]"
    capability = (status.get("capabilities") or {}).get("video", {})
    return {"connected": True, "provider": "Strata", "model": model, "context": status["context"]["native"],
            "loaded": status["loaded"], "vision_enabled": status["vision"]["enabled"],
            "video_modes": [mode for mode in capability.get("modes", []) if mode in {"frames", "native"}],
            "native_verified": capability.get("native_verified") is True, "checked_at": int(time.time()),
            "read_only": True, "generation_requests": 0}


def register_strata_routes():
    global _REGISTERED
    if _REGISTERED:
        return True
    server = sys.modules.get("server")
    instance = getattr(getattr(server, "PromptServer", None), "instance", None)
    if instance is None:
        return False
    from aiohttp import web
    from .credential_routes import _same_origin_request
    async def status(request):
        if not _same_origin_request(request):
            return web.json_response({"connected": False, "category": "forbidden"}, status=403)
        if request.content_length is None or request.content_length > 8192:
            return web.json_response({"connected": False, "category": "configuration"}, status=400)
        try:
            values = await request.json()
            if not isinstance(values, dict) or any(not key.startswith("strata_") for key in values):
                raise StrataProviderError("Invalid probe settings.", "configuration")
            result = await asyncio.to_thread(probe_strata, values)
            return web.json_response(result, headers={"Cache-Control": "no-store"})
        except StrataProviderError as error:
            return web.json_response({"connected": False, "category": error.category}, status=400,
                                     headers={"Cache-Control": "no-store"})
        except Exception:
            return web.json_response({"connected": False, "category": "connection"}, status=400,
                                     headers={"Cache-Control": "no-store"})
    instance.routes.post("/t8-prompt-enhancer/strata/status")(status)
    _REGISTERED = True
    return True
