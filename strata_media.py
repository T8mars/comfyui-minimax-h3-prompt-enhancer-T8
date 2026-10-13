"""Inline image/video bridge with bounded CPU sampling and source-role fidelity."""
from __future__ import annotations

import base64
import io
import math
from typing import Any

try:
    from .strata_provider import StrataProviderError, interrupted, require_strata_run
    from .strata_vendor import video as adapter, video_shared as shared
except ImportError:
    from strata_provider import StrataProviderError, interrupted, require_strata_run
    from strata_vendor import video as adapter, video_shared as shared


EVIDENCE_BOUNDARY = (
    "STRATA_VISUAL_EVIDENCE_BOUNDARY: Images retain their original source labels and roles. "
    "Each strata_video is only ordered timestamped visual samples of its named Video source, "
    "not additional Picture references. Preserve observed temporal order; never claim continuous "
    "frame coverage or invent unseen actions. No audio was decoded or analyzed: do not claim "
    "speech transcription, music recognition, BPM detection or audio reuse. Written user dialogue "
    "and sound design are creative instructions, not evidence of an audio track."
)


def video_info(video):
    run = require_strata_run()
    cache = run.video_cache.setdefault(id(video), {})
    if "info" in cache:
        return cache["info"]
    interrupted()
    kind = adapter.official_type(video)
    if kind == "VideoFromFile":
        state, crop, source = adapter.file_source(video)
        start, duration = adapter.file_timing(state, adapter.metadata_guard(source))
        info = {"kind": kind, "duration": duration, "start": start, "crop": crop}
    elif kind == "VideoFromComponents":
        state = set(vars(video))
        if state not in ({"_VideoFromComponents__components"}, {"_VideoFromComponents__components", "_VideoFromComponents__bit_depth"}, {"_VideoFromComponents__components", "_VideoFromComponents__bit_depth", "_VideoFromComponents__color_space"}):
            raise StrataProviderError("Unsupported official VIDEO component layout.", "media")
        # v0.33 get_components() rebuilds the dataclass without alpha. The exact
        # audited private state holds the original, already existing tensors.
        component = vars(video)["_VideoFromComponents__components"]
        if not hasattr(component.images, "shape") or len(component.images.shape) != 4:
            raise StrataProviderError("VIDEO components need a frame tensor.", "media")
        rate = adapter.number(float(component.frame_rate), "fps", high=240, positive=True)
        info = {"kind": kind, "duration": component.images.shape[0] / rate, "start": 0., "crop": None}
    else:
        if set(vars(video)) != {"videos", "complete_audio", "_VideoFromList__buffer"} or not isinstance(video.videos, list) or not 1 <= len(video.videos) <= 64:
            raise StrataProviderError("Unsupported official VIDEO list layout.", "media")
        if any(adapter.official_type(item) != "VideoFromFile" for item in video.videos):
            raise StrataProviderError("VIDEO list must contain bounded official file videos.", "media")
        info = {"kind": kind, "duration": sum(video_info(item)["duration"] for item in video.videos), "start": 0., "crop": None}
    if not math.isfinite(info["duration"]) or not 0 < info["duration"] <= 3600:
        raise StrataProviderError("Strata 当前协议的有效视频窗口需在 0–3600 秒内；请上游裁剪 / Select a supported video window.", "media_budget")
    interrupted()
    cache["info"] = info
    return info


def _sample_list(video, settings):
    duration = video_info(video)["duration"]
    targets = shared.sampling_schedule(0., duration, settings.video_sample_fps, settings.video_max_frames)
    candidates, offset = [], 0.
    for index, component in enumerate(video.videos):
        interrupted()
        length = video_info(component)["duration"]
        wanted = [target - offset for target in targets if offset <= target < offset + length]
        if wanted:
            sampled = adapter.file_adapter(component, start_s=0., end_s=length,
                                           sampling_fps=settings.video_sample_fps, max_frames=max(2, min(64, len(wanted) + 1)),
                                           max_pixels=589824, cancel=interrupted, target_times=wanted)
            for frame in sampled.frames:
                candidates.append((offset + frame.timestamp_s, frame, index))
        offset += length
    if not candidates:
        raise StrataProviderError("VIDEO list produced no samples.", "media")
    chosen = [candidates[0]]
    for target in targets[1:-1]:
        candidate = next((item for item in candidates if item[0] >= target), candidates[-1])
        if candidate[0] > chosen[-1][0]:
            chosen.append(candidate)
    if candidates[-1][0] > chosen[-1][0]:
        chosen.append(candidates[-1])
    result = shared.sample_images([item[1].image for item in chosen], timestamps=[item[0] for item in chosen],
                                  source_duration_s=duration, preselected=True,
                                  sampling_fps=settings.video_sample_fps, max_frames=settings.video_max_frames,
                                  max_pixels=589824, cancel=interrupted)
    result.manifest["source"].update(kind="video_list", timestamp_basis="composite_media_clock")
    for row, item in zip(result.manifest["frames"], chosen):
        row.update(component_index=item[2], component_source_timestamp_s=item[1].source_timestamp_s)
    return result


def sample_asset(video):
    run = require_strata_run()
    cache = run.video_cache.setdefault(id(video), {})
    if "samples" not in cache:
        info = video_info(video)
        try:
            if info["kind"] == "VideoFromList":
                samples = _sample_list(video, run.settings)
            else:
                samples = adapter.sample_input(video=video, sampling_fps=run.settings.video_sample_fps,
                                               max_frames=run.settings.video_max_frames, max_pixels=589824)
            shared.validate_manifest(samples.manifest, len(samples.frames))
        except (ValueError, OSError, TimeoutError) as error:
            raise StrataProviderError(f"Strata 视频采样失败 / Video sampling failed: {type(error).__name__}.", "media") from error
        interrupted()
        cache["samples"] = samples
    return cache["samples"]


def _image(value):
    import numpy as np
    from PIL import Image
    interrupted()
    if hasattr(value, "detach"):
        array = value.detach().to("cpu").float().numpy()
    else:
        array = np.asarray(value)
    if array.ndim == 4:
        if array.shape[0] != 1:
            raise StrataProviderError("Strata image part requires one image.", "media")
        array = array[0]
    if array.ndim != 3 or array.shape[-1] not in (3, 4) or min(array.shape[:2]) < 1 or array.shape[0] * array.shape[1] > 16_777_216 or not np.isfinite(array).all():
        raise StrataProviderError("Invalid or oversized Strata IMAGE.", "media")
    image = Image.fromarray((np.clip(array, 0, 1) * 255).round().astype(np.uint8))
    return shared.bounded_image(image, 1048576)


def _data_url(image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    interrupted()
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def build_strata_media_parts(media_plan):
    run = require_strata_run()
    key = tuple((asset.get("kind"), asset.get("label"), asset.get("role"), id(asset.get("value"))) for asset in media_plan)
    if key in run.media_cache:
        return run.media_cache[key]
    parts = []
    for asset in media_plan:
        interrupted()
        label = str(asset.get("label") or "")
        if asset.get("kind") == "image":
            parts.extend([{"type": "text", "text": f"The next attached image is {label}."},
                          {"type": "image_url", "image_url": {"url": _data_url(_image(asset["value"]))}}])
        elif asset.get("kind") == "video":
            sampled = sample_asset(asset["value"])
            source, sampling = sampled.manifest["source"], sampled.manifest["sampling"]
            origin = source.get("time_origin_s", 0.) + sampling["start_s"]
            frames = [{"source": _data_url(frame.image), "timestamp_s": frame.timestamp_s,
                       "source_timestamp_s": frame.source_timestamp_s, "index": frame.index} for frame in sampled.frames]
            part = {"type": "strata_video", "contract_version": 1, "mode": run.settings.video_mode, "frames": frames,
                    "metadata": {"duration_s": sampling["end_s"] - sampling["start_s"], "time_origin_s": origin,
                                 "sampling_fps": run.settings.video_sample_fps}}
            parts.extend([{"type": "text", "text": f"The following sampled visual clip is {label}. {EVIDENCE_BOUNDARY}"}, part])
            run.media_reports.append({"label": label, "mode": run.settings.video_mode, "sample_count": len(frames),
                                      "first_sample_s": frames[0]["timestamp_s"], "last_sample_s": frames[-1]["timestamp_s"],
                                      "max_sample_gap_s": max((b["timestamp_s"] - a["timestamp_s"] for a, b in zip(frames, frames[1:])), default=0.),
                                      "window_duration_s": part["metadata"]["duration_s"], "audio_analyzed": False,
                                      "continuous_observation": False, "endpoint_policy": "first_last_valid"})
        else:
            raise StrataProviderError("Strata 不支持音频或未知媒体 / Unsupported media source.", "media")
    run.media_cache[key] = parts
    return parts
