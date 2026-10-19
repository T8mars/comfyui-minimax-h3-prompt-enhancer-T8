"""Independent CPU authoring for the existing H3 v1 interchange record.

No reference-plugin imports, inference, cropping or global node replacement.
The file loader and preview share exactly the same RGB/EXIF conversion.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io as byte_io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from comfy_api.latest import io

from . import h3_visual_marker as vm

EMPTY_SPEC = '{"markers":[],"relations":[]}'
MODES = ["render_rectangles", "provided_marked"]
MAX_SPEC_BYTES = 65536


def source_path(name):
    import folder_paths
    if type(name) is not str or not name.strip() or len(name) > 4096:
        raise ValueError("请先上传参考图 / Upload a source image first.")
    # Only the configured Comfy input directory, including safe upload subfolders.
    candidate = Path(name.replace("\\", "/"))
    if candidate.is_absolute() or ":" in name or ".." in candidate.parts:
        raise ValueError("源图路径无效 / Invalid input image path.")
    root = Path(folder_paths.get_input_directory()).resolve()
    path = (root / candidate).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("参考图不存在或不在input目录 / Source must be inside ComfyUI input.")
    return path


def load_source(name):
    path = source_path(name)
    try:
        with Image.open(path) as opened:
            if getattr(opened, "n_frames", 1) != 1:
                raise ValueError("请选择单张静态图 / A single still image is required.")
            width, height = opened.size
            if min(width, height) < 2 or width * height > vm.MAX_PIXELS:
                raise ValueError("v1标记参考图需2×2以上且不超过4MP；不会自动缩图。")
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
            return (np.array(rgb, dtype=np.float32) / np.float32(255))[None]
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("无法解码参考图，请使用单张PNG/JPG / Cannot decode source image.") from error


def normalize_spec(raw):
    vm._text(raw, MAX_SPEC_BYTES)
    data = vm._json(raw)
    vm._keys(data, ("markers", "relations"))
    if type(data["markers"]) is not list or type(data["relations"]) is not list:
        raise ValueError("标记与动作需要数组 / Markers and relations must be arrays.")
    if not 2 <= len(data["markers"]) <= 64 or not 1 <= len(data["relations"]) <= 128:
        raise ValueError("请至少画一个人物框、一个目标框并填写动作关系（v1最多64框/128关系）。")
    markers = []
    for item in data["markers"]:
        if type(item) is not dict or not {"marker_id", "kind", "color", "description"} <= item.keys() or item.keys() - {
                "marker_id", "kind", "role_id", "color", "description", "xyxy"}:
            raise ValueError("标记字段无效 / Invalid marker fields.")
        color = vm._text(item["color"], 32).lower()
        markers.append(dict(marker_id=item["marker_id"], kind=item["kind"],
            role_id=item.get("role_id"), color_label=color, color_rgb=vm._COLORS.get(color, color),
            description=item["description"], xyxy=item.get("xyxy")))
    return dict(markers=markers, relations=data["relations"])


@dataclass(frozen=True)
class SpatialMarkerPlan:
    record_json: str
    marked_image: object
    clean_image: object


def prepare_spatial_image(image, markers_json, mode="render_rectangles", line_width=3, expected_source_sha256=""):
    if mode not in MODES or type(line_width) is not int or not 1 <= line_width <= 32:
        raise ValueError("绘框模式或线宽无效 / Invalid mode or line width (1..32).")
    spec = normalize_spec(markers_json)
    source = vm._pixels(image).copy()
    identity = vm._pixel_identity(source)
    if type(expected_source_sha256) is not str or (expected_source_sha256 and not vm._SHA.fullmatch(expected_source_sha256)):
        raise ValueError("预览源校验值无效 / Invalid preview source digest.")
    if expected_source_sha256 and identity["sha256"] != expected_source_sha256:
        raise ValueError("参考图已变化，请重新打开编辑器加载并核对框选 / Source changed; reload the editor.")
    _, height, width, _ = source.shape
    boxes = []
    # Let the existing full v1 validator check IDs, colors, relations and geometry
    # before any integer conversion or rendering. Placeholder identity is valid.
    for marker in spec["markers"]:
        xy = marker["xyxy"]
        if xy is not None and (type(xy) is not list or len(xy) != 4 or any(
                type(n) not in (int, float) or not 0 <= n <= 1 for n in xy) or not xy[0] < xy[2] or not xy[1] < xy[3]):
            raise ValueError("框选坐标必须是源图内的非零矩形 / Invalid normalized rectangle.")
        box = None if xy is None else [math.floor(xy[0]*width), math.floor(xy[1]*height),
            math.ceil(xy[2]*width), math.ceil(xy[3]*height)]
        boxes.append(dict(marker_id=marker["marker_id"], source_pixel_xyxy=box,
            geometry_observation="rendered_source_rectangle" if mode == MODES[0] else
            "unobserved" if box is None else "user_declared_not_detected"))
    record = dict(schema=vm.PLAN_SCHEMA, mode=mode, source_rgb=identity,
        clean_rgb=identity if mode == MODES[0] else None, marked_rgb=identity,
        source_dimensions=[width, height], spec=spec, pixel_rectangles=boxes,
        line_width=line_width if mode == MODES[0] else None,
        pixel_rounding="floor_start_ceil_exclusive_end_clamped" if mode == MODES[0] else None,
        coordinate_space=vm.COORDINATES, binding_verified=False, native_picture_ordinal=None,
        warnings=["Soft source-image annotations only; rendered video and downstream binding are not verified."],
        editor_preview_source_verified=bool(expected_source_sha256))
    record["sha256"] = vm._digest(record)
    _, codes = vm._record(vm._canonical(record))
    marked = source.copy()
    if mode == MODES[0]:
        for marker, geometry in zip(spec["markers"], boxes):
            left, top, right, bottom = geometry["source_pixel_xyxy"]
            thickness = min(line_width, right-left, bottom-top)
            color = np.array([int(marker["color_rgb"][i:i+2], 16) for i in (1, 3, 5)], dtype=np.float32) / np.float32(255)
            region = marked[0, top:bottom, left:right]
            region[:thickness, :] = color
            region[-thickness:, :] = color
            region[:, :thickness] = color
            region[:, -thickness:] = color
    record["marked_rgb"] = vm._pixel_identity(marked)
    record.pop("sha256")
    record["sha256"] = vm._digest(record)
    import torch
    tensor = torch.from_numpy(marked)
    plan = SpatialMarkerPlan(vm._canonical(record), tensor,
        torch.from_numpy(source.copy()) if mode == MODES[0] else None)
    # This is the same actual-pixel boundary used by the H3 configuration.
    vm.build_visual_marker_config(vm.ON, 0, plan)
    return tensor, plan, record, codes


def image_png(pixels):
    value = vm._pixels(pixels)[0]
    out = byte_io.BytesIO()
    Image.fromarray(np.rint(value * 255).astype(np.uint8)).save(out, format="PNG")
    return out.getvalue()


class T8H3SpatialMarkerCanvas(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        import folder_paths
        root = Path(folder_paths.get_input_directory())
        images = sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in
            {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}) if root.is_dir() else []
        return io.Schema(node_id="T8H3SpatialMarkerCanvas", display_name="T8 H3 手动空间画框 / Spatial Marker Canvas",
            category="T8/MiniMax H3", description="上传图片，点击手动画框，添加人物/目标及动作。纯CPU，不裁图、不调用模型；旧audio插件无需修改。",
            inputs=[io.Combo.Input("image", options=["", *images], default="", upload=io.UploadType.image,
                        display_name="参考图 / Upload image"),
                    io.Combo.Input("mode", options=MODES, default=MODES[0], display_name="绘框 / Existing marks"),
                    io.String.Input("markers_json", default=EMPTY_SPEC, multiline=True, advanced=True,
                        display_name="标记数据（画框自动填写）"),
                    io.Int.Input("line_width", default=3, min=1, max=32, display_name="线宽 / Stroke"),
                    io.String.Input("expected_source_sha256", default="", advanced=True,
                        display_name="源图校验（自动填写）")],
            outputs=[io.Image.Output(display_name="marked_image"), vm.PLAN_IO.Output(display_name="marker_plan"),
                     io.Image.Output(display_name="source_image"), io.String.Output(display_name="markers_json"),
                     io.String.Output(display_name="report_json")])

    @classmethod
    def validate_inputs(cls, image=None, mode=None, markers_json=None, line_width=None, expected_source_sha256=None):
        try:
            if image is not None: source_path(image)
            if mode is not None and mode not in MODES: raise ValueError("Invalid marker mode")
            if markers_json is not None: normalize_spec(markers_json)
            if line_width is not None and (type(line_width) is not int or not 1 <= line_width <= 32):
                raise ValueError("Invalid line width")
            if expected_source_sha256 is not None and (type(expected_source_sha256) is not str or (
                    expected_source_sha256 and not vm._SHA.fullmatch(expected_source_sha256))):
                raise ValueError("Invalid source digest")
        except ValueError as error:
            return str(error)
        return True

    @classmethod
    def fingerprint_inputs(cls, image, **kwargs):
        try:
            with source_path(image).open("rb") as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024*1024), b""): digest.update(chunk)
                return digest.hexdigest()
        except (ValueError, OSError):
            return float("nan")

    @classmethod
    def execute(cls, image, mode=MODES[0], markers_json=EMPTY_SPEC, line_width=3, expected_source_sha256=""):
        source = load_source(image)
        marked, plan, record, codes = prepare_spatial_image(source, markers_json, mode, line_width, expected_source_sha256)
        import torch
        report = dict(schema="t8-h3-spatial-editor-report/v1", source_dimensions=record["source_dimensions"],
            preview_source_verified=record["editor_preview_source_verified"], marker_count=len(record["spec"]["markers"]),
            relation_count=len(record["spec"]["relations"]), warning_codes=list(codes),
            downstream_verified=False, semantic_verified=False, model_calls=0)
        return io.NodeOutput(marked, plan, torch.from_numpy(source.copy()), markers_json, vm._canonical(report))
