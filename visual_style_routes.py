"""Read-only, same-origin packaged style browser; no arbitrary file access."""
import sys
from urllib.parse import urlsplit
from .completion_recovery_routes import _same_origin_request
from .visual_styles import load_catalog, load_resource, selection_label

_REGISTERED = False


def catalog_payload():
    catalog, digest = load_catalog()
    return {"schema_version": "t8-visual-style-browser/v1", "revision": catalog["revision"], "digest": digest,
            "entries": [{**{k: row[k] for k in ("id", "label_zh", "label_en", "category", "creator_role")},
                         "selection": selection_label(row)} for row in catalog["entries"]]}


def detail_payload(kind, style_id):
    resource, entry, digest = load_resource(kind, style_id)
    return {"schema_version": "t8-visual-style-detail/v1", "kind": kind, "resource": resource,
            "selection": selection_label(entry), "digest": digest, "model_calls": 0}


def register_visual_style_routes():
    global _REGISTERED
    if _REGISTERED:
        return True
    instance = getattr(getattr(sys.modules.get("server"), "PromptServer", None), "instance", None)
    if instance is None:
        return False
    from aiohttp import web

    async def respond(request, detail=False):
        headers = {"Cache-Control": "no-store"}
        try:
            same_origin = _same_origin_request(request)
            origin = str(request.headers.get("Origin", "")).strip()
            if same_origin and origin:
                parsed = urlsplit(origin)
                same_origin = (parsed.scheme in {"http", "https"} and parsed.scheme == request.scheme
                               and not (parsed.path or parsed.query or parsed.fragment)
                               and parsed.username is None and parsed.password is None)
        except ValueError:  # Malformed Origin URLs are denied, never HTTP 500.
            same_origin = False
        if not same_origin:
            return web.json_response({"error": "Same-origin access required"}, status=403, headers=headers)
        try:
            data = detail_payload(request.match_info["kind"], request.match_info["style_id"]) if detail else catalog_payload()
            return web.json_response(data, headers=headers)
        except (ValueError, TypeError, OSError):
            return web.json_response({"error": "风格资料不可用，请刷新或重装。 / Style data unavailable; refresh or reinstall."}, status=400, headers=headers)

    async def catalog(request):
        return await respond(request)

    async def detail(request):
        return await respond(request, True)

    instance.routes.get("/t8-prompt-enhancer/visual-styles/catalog")(catalog)
    instance.routes.get("/t8-prompt-enhancer/visual-styles/{kind}/{style_id}")(detail)
    _REGISTERED = True
    return True
