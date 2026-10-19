"""Same-origin CPU preview. Reads only explicitly selected Comfy input images."""
import base64
import json
import sys

from .completion_recovery_routes import _same_origin_request
from . import h3_spatial_editor as editor

_REGISTERED = False
MAX_BODY = 160 * 1024  # 64 KiB spec may expand again inside its JSON string.


def preview_payload(data):
    if type(data) is not dict or set(data) not in ({"image"}, {"image", "mode", "markers_json", "line_width"}):
        raise ValueError("Invalid preview fields")
    source = editor.load_source(data["image"])
    value, codes = source, ()
    if "markers_json" in data:
        value, _, _, codes = editor.prepare_spatial_image(source, data["markers_json"], data["mode"], data["line_width"])
    return dict(png="data:image/png;base64," + base64.b64encode(editor.image_png(value)).decode("ascii"),
        width=int(source.shape[2]), height=int(source.shape[1]),
        source_sha256=editor.vm._pixel_identity(source)["sha256"], warning_codes=list(codes), model_calls=0)


def register_spatial_editor_routes():
    global _REGISTERED
    if _REGISTERED: return True
    instance = getattr(getattr(sys.modules.get("server"), "PromptServer", None), "instance", None)
    if instance is None: return False
    from aiohttp import web
    import asyncio

    async def preview(request):
        headers = {"Cache-Control": "no-store"}
        try:
            if not _same_origin_request(request):
                return web.json_response({"error": "Same-origin access required"}, status=403, headers=headers)
            if request.content_length is not None and request.content_length > MAX_BODY:
                return web.json_response({"error": "Preview request too large"}, status=413, headers=headers)
            body = bytearray()
            async for part in request.content.iter_chunked(8192):
                body.extend(part)
                if len(body) > MAX_BODY:
                    return web.json_response({"error": "Preview request too large"}, status=413, headers=headers)
            data = json.loads(body, object_pairs_hook=editor.vm._pairs)
            result = await asyncio.to_thread(preview_payload, data)
            return web.json_response(result, headers=headers)
        except (ValueError, TypeError, UnicodeError, RecursionError, OSError):
            return web.json_response({"error": "无法预览：检查input源图、框选和动作数据 / Check input image and marker data."}, status=400, headers=headers)

    instance.routes.post("/t8-prompt-enhancer/h3-spatial-editor/preview")(preview)
    _REGISTERED = True
    return True
