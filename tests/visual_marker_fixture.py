"""Small portable v1 data fixture, not a replacement for producer integration."""
import hashlib
import json
from types import SimpleNamespace

import torch


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identity(image):
    raw = image.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return dict(shape=list(image.shape), dtype=str(image.dtype), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def material(*, rendered=False):
    clean = torch.zeros((1, 32, 48, 3), dtype=torch.float32)
    marked = clean.clone()
    marked[:, 1:3, 3:15, 1] = 1
    marked[:, 23:25, 29:44, 0] = 1
    markers = [dict(marker_id="actor_A", kind="actor", role_id="A", color_rgb="#00dfff", color_label="cyan",
                    description="the woman in the red coat", xyxy=[0, 0, .5, .5] if rendered else None),
               dict(marker_id="target_A", kind="target", role_id=None, color_rgb="#ffdf00", color_label="yellow",
                    description="the doorway on the right", xyxy=[.5, .5, 1, 1] if rendered else None)]
    record = dict(schema="t8.h3.visual-marker-plan/v1", mode="render_rectangles" if rendered else "provided_marked",
        source_rgb=identity(clean if rendered else marked), clean_rgb=identity(clean) if rendered else None,
        marked_rgb=identity(marked), source_dimensions=[48, 32],
        spec=dict(markers=markers, relations=[dict(actor_marker_id="actor_A", target_marker_id="target_A",
            action="walk through the doorway and keep moving; do not stop")]),
        pixel_rectangles=[dict(marker_id=m["marker_id"], source_pixel_xyxy=box if rendered else None,
            geometry_observation="rendered_source_rectangle" if rendered else "unobserved")
            for m, box in zip(markers, ([0, 0, 24, 16], [24, 16, 48, 32]))],
        line_width=3 if rendered else None,
        pixel_rounding="floor_start_ceil_exclusive_end_clamped" if rendered else None,
        coordinate_space="source_reference_image_normalized_xyxy_not_generated_video",
        binding_verified=False, native_picture_ordinal=None,
        warnings=["Soft image guidance only."], editor_preview_source_verified=False)
    record["sha256"] = digest(record)
    return SimpleNamespace(record_json=canonical(record), marked_image=marked,
                           clean_image=clean if rendered else None)


def change_record(plan, edit, *, resign=True):
    record = json.loads(plan.record_json)
    edit(record)
    if resign:
        record.pop("sha256", None)
        record["sha256"] = digest(record)
    plan.record_json = canonical(record)
    return plan
