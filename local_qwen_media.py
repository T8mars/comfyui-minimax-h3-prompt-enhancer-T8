from __future__ import annotations

import base64
import io
import math
import re
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


class LocalQwenMediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class SampledFrame:
    timestamp: float
    image: Image.Image


def _tensor_to_image(value: Any) -> Image.Image:
    array = value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)
    if array.ndim == 4:
        if int(array.shape[0]) != 1:
            raise LocalQwenMediaError("Each local IMAGE attachment must contain exactly one image.")
        array = array[0]
    if array.ndim != 3 or array.shape[-1] not in (3, 4):
        raise LocalQwenMediaError(f"Unsupported IMAGE shape for local Qwen: {array.shape}")
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    if np.issubdtype(array.dtype, np.floating):
        array = np.rint(np.clip(array, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        array = np.clip(array, 0, 255).astype(np.uint8)
    image = Image.fromarray(array)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def _fit_image(image: Image.Image, max_edge: int = 1280) -> Image.Image:
    image = image.convert("RGB")
    width, height = image.size
    scale = min(1.0, float(max_edge) / max(width, height))
    if scale < 1.0:
        image = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )
    return image


def _jpeg_data_url(image: Image.Image, quality: int = 88) -> str:
    buffer = io.BytesIO()
    _fit_image(image).save(buffer, format="JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def image_part(value: Any, label: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": f"The next attached image is {label}."},
        {"type": "image_url", "image_url": {"url": _jpeg_data_url(_tensor_to_image(value))}},
    ]


def _video_window(video: Any) -> tuple[float, float]:
    if not hasattr(video, "get_duration"):
        raise LocalQwenMediaError("VIDEO input does not expose duration metadata.")
    try:
        full_duration = float(video.get_duration())
    except (OSError, TypeError, ValueError) as error:
        raise LocalQwenMediaError("Could not read VIDEO duration metadata.") from error
    if not math.isfinite(full_duration) or full_duration <= 0:
        raise LocalQwenMediaError("VIDEO duration metadata is invalid.")
    start = 0.0
    duration = full_duration
    if hasattr(video, "get_active_trim_window"):
        try:
            trim_start, trim_duration = video.get_active_trim_window()
            trim_start = float(trim_start)
            trim_duration = float(trim_duration)
        except (OSError, TypeError, ValueError) as error:
            raise LocalQwenMediaError("Could not read VIDEO trim metadata.") from error
        if math.isfinite(trim_start) and trim_start > 0:
            start = trim_start
        if math.isfinite(trim_duration) and trim_duration > 0:
            duration = trim_duration
    duration = min(duration, max(0.0, full_duration - start))
    if duration <= 0:
        raise LocalQwenMediaError("VIDEO trim window is empty.")
    return start, duration


def _stream_source(video: Any) -> Any:
    if not hasattr(video, "get_stream_source"):
        raise LocalQwenMediaError("VIDEO input must come from a native ComfyUI video node.")
    try:
        source = video.get_stream_source()
    except (OSError, TypeError, ValueError) as error:
        raise LocalQwenMediaError("Could not open the VIDEO stream source.") from error
    if isinstance(source, (str, os.PathLike)):
        path = os.fspath(source)
        if not os.path.isfile(path):
            raise LocalQwenMediaError("VIDEO stream source no longer exists.")
    elif not hasattr(source, "read"):
        raise LocalQwenMediaError("VIDEO stream source is not readable.")
    return source


def sample_video(video: Any, frames_per_second: float) -> tuple[list[SampledFrame], float]:
    try:
        import av
    except ImportError as error:
        raise LocalQwenMediaError(
            "PyAV is required for local Qwen video sampling. Install/restore ComfyUI's av dependency."
        ) from error
    fps = float(frames_per_second)
    if not math.isfinite(fps) or fps < 0.25 or fps > 8.0:
        raise LocalQwenMediaError("Local video sample rate must be between 0.25 and 8 frames per second.")
    start, duration = _video_window(video)
    source = _stream_source(video)
    original_position: int | None = None
    if not isinstance(source, (str, os.PathLike)) and hasattr(source, "tell"):
        try:
            original_position = int(source.tell())
        except (OSError, TypeError, ValueError):
            original_position = None
    if hasattr(source, "seek"):
        try:
            source.seek(0)
        except (OSError, TypeError, ValueError):
            pass
    targets = [
        start + index / fps
        for index in range(max(1, int(math.ceil(duration * fps))))
        if start + index / fps < start + duration - 1e-6
    ] or [start]
    sampled: list[SampledFrame] = []
    container = None
    try:
        container = av.open(source)
        streams = [stream for stream in container.streams if stream.type == "video"]
        if not streams:
            raise LocalQwenMediaError("VIDEO contains no decodable video stream.")
        stream = streams[0]
        target_index = 0
        last_candidate: SampledFrame | None = None
        decoded_index = 0
        for frame in container.decode(stream):
            if frame.time is not None:
                timestamp = float(frame.time)
            elif frame.pts is not None and stream.time_base is not None:
                timestamp = float(frame.pts * stream.time_base)
            else:
                average_rate = float(stream.average_rate) if stream.average_rate else 24.0
                timestamp = float(decoded_index) / max(average_rate, 1e-6)
            decoded_index += 1
            if timestamp < start - 1e-3:
                continue
            if timestamp > start + duration + 1e-3:
                break
            candidate = SampledFrame(timestamp=max(0.0, timestamp - start), image=frame.to_image().convert("RGB"))
            last_candidate = candidate
            while target_index < len(targets) and timestamp + 1e-6 >= targets[target_index]:
                sampled.append(candidate)
                target_index += 1
            if target_index >= len(targets):
                break
        while target_index < len(targets) and last_candidate is not None:
            sampled.append(last_candidate)
            target_index += 1
    except LocalQwenMediaError:
        raise
    except Exception as error:
        raise LocalQwenMediaError(f"Local Qwen could not decode VIDEO: {type(error).__name__}.") from error
    finally:
        if container is not None:
            container.close()
        if original_position is not None and hasattr(source, "seek"):
            try:
                source.seek(original_position)
            except (OSError, TypeError, ValueError):
                pass
    if not sampled:
        raise LocalQwenMediaError("VIDEO sampling produced no frames.")
    return sampled, duration


def _balanced_chunks(items: list[SampledFrame], count: int) -> list[list[SampledFrame]]:
    count = max(1, min(int(count), len(items)))
    chunks: list[list[SampledFrame]] = []
    for index in range(count):
        start = round(index * len(items) / count)
        end = round((index + 1) * len(items) / count)
        chunks.append(items[start:max(start + 1, end)])
    return chunks


def _uniform_samples(items: list[SampledFrame], limit: int) -> list[SampledFrame]:
    limit = max(1, int(limit))
    if len(items) <= limit:
        return list(items)
    if limit == 1:
        return [items[len(items) // 2]]
    indices = [round(index * (len(items) - 1) / (limit - 1)) for index in range(limit)]
    return [items[index] for index in indices]


def _contact_sheet(frames: list[SampledFrame], video_label: str) -> Image.Image:
    if len(frames) > 9:
        raise LocalQwenMediaError("A local Qwen contact sheet cannot contain more than 9 frames.")
    columns = min(3, max(1, math.ceil(math.sqrt(len(frames)))))
    rows = math.ceil(len(frames) / columns)
    tile_width, tile_height, label_height = 400, 225, 24
    sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, sample in enumerate(frames):
        image = sample.image.copy()
        image.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + label_height)
        pad_x = x + (tile_width - image.width) // 2
        pad_y = y + (tile_height - image.height) // 2
        sheet.paste(image, (pad_x, pad_y))
        draw.rectangle((x, y + tile_height, x + tile_width, y + tile_height + label_height), fill=(18, 18, 18))
        draw.text(
            (x + 7, y + tile_height + 5),
            f"{video_label}  t={sample.timestamp:.3f}s",
            fill=(245, 245, 245),
        )
    return sheet


def build_local_media_parts(
    media_plan: list[dict[str, Any]],
    *,
    video_sample_fps: float,
    max_visual_parts: int = 16,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    max_visual_parts = int(max_visual_parts)
    if max_visual_parts < 0:
        raise LocalQwenMediaError("Local Qwen visual budget cannot be negative.")
    image_assets = [asset for asset in media_plan if asset.get("kind") == "image"]
    video_assets = [asset for asset in media_plan if asset.get("kind") == "video"]
    if len(image_assets) > max_visual_parts:
        raise LocalQwenMediaError(
            f"Local Qwen visual budget allows at most {max_visual_parts} image parts; received {len(image_assets)}."
        )
    parts: list[dict[str, Any]] = []
    for asset in image_assets:
        parts.extend(image_part(asset["value"], str(asset["label"])))

    sampled_videos: list[tuple[dict[str, Any], list[SampledFrame], float]] = []
    for asset in video_assets:
        frames, duration = sample_video(asset["value"], video_sample_fps)
        sampled_videos.append((asset, frames, duration))

    remaining_parts = max_visual_parts - len(image_assets)
    if sampled_videos and remaining_parts < len(sampled_videos):
        raise LocalQwenMediaError(
            "Too many image attachments leave no visual-token budget for every connected video."
        )
    sheet_counts: list[int] = []
    remaining_videos = len(sampled_videos)
    for _asset, frames, _duration in sampled_videos:
        allocated = max(1, remaining_parts // max(1, remaining_videos))
        natural = max(1, math.ceil(len(frames) / 6))
        count = min(allocated, natural)
        sheet_counts.append(count)
        remaining_parts -= count
        remaining_videos -= 1

    video_reports: list[dict[str, Any]] = []
    for (asset, frames, duration), sheet_count in zip(sampled_videos, sheet_counts):
        label = str(asset["label"])
        sent_frames = _uniform_samples(frames, sheet_count * 9)
        parts.append(
            {
                "type": "text",
                "text": (
                    f"The following {sheet_count} contact sheet(s) are ordered sampled visual evidence for {label}, "
                    f"covering {duration:.3f} seconds. Read timestamps left-to-right and top-to-bottom. "
                    "Before drafting, build an internal observation ledger sorted by the printed timestamps. "
                    "In the final response, introduce every visible phase, code, and action in first-appearance "
                    "timestamp order; never move a later phase ahead merely because it is more visually salient. "
                    "Infer only visible temporal changes; no audio was analyzed."
                ),
            }
        )
        for number, chunk in enumerate(_balanced_chunks(sent_frames, sheet_count), start=1):
            parts.append(
                {
                    "type": "text",
                    "text": f"{label} contact sheet {number}/{sheet_count}.",
                }
            )
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _jpeg_data_url(_contact_sheet(chunk, label), quality=86)},
                }
            )
        video_reports.append(
            {
                "label": label,
                "duration_seconds": round(duration, 6),
                "sampled_frame_count": len(frames),
                "sent_frame_count": len(sent_frames),
                "uniformly_reduced_frame_count": len(frames) - len(sent_frames),
                "contact_sheet_count": sheet_count,
            }
        )
    visual_count = len(image_assets) + sum(sheet_counts)
    return parts, {
        "visual_part_count": visual_count,
        "image_count": len(image_assets),
        "video_count": len(video_assets),
        "video_sample_fps": float(video_sample_fps),
        "videos": video_reports,
        "audio_analyzed": False,
    }


def estimate_message_tokens(messages: list[dict[str, Any]], visual_tokens_each: int = 1024) -> int:
    text_characters = 0
    visual_parts = 0
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str):
            text_characters += len(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "image_url":
                    visual_parts += 1
                elif part.get("type") == "text":
                    text_characters += len(str(part.get("text") or ""))
    joined_text = ""
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str):
            joined_text += content
        elif isinstance(content, list):
            joined_text += "".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
    cjk_characters = len(
        re.findall(
            r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]",
            joined_text,
        )
    )
    non_cjk_characters = max(0, len(joined_text) - cjk_characters)
    # Qwen tokenization is close to one token per CJK character. English and
    # punctuation are budgeted more conservatively than the common 4 chars/token.
    text_tokens = cjk_characters + math.ceil(non_cjk_characters / 3.0)
    return text_tokens + visual_parts * int(visual_tokens_each) + 256


__all__ = [
    "LocalQwenMediaError",
    "build_local_media_parts",
    "estimate_message_tokens",
    "image_part",
    "sample_video",
]
