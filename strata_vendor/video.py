"""CPU video adapters and ordered-frame requests; no imports perform I/O or GPU work."""
from __future__ import annotations
import bisect
import io
import json
import math
from pathlib import Path
import sys
import time
from . import core

MAX_FRAMES = 64
MAX_INPUT_BYTES = 256 * 1024**2
MAX_DURATION = 3600


def shared():
    from . import video_shared
    return video_shared


def number(value, name, low=0, high=MAX_DURATION, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise core.StrataError(f'Invalid video {name}')
    try:
        value = float(value)
    except OverflowError:
        raise core.StrataError(f'Invalid video {name}') from None
    if not math.isfinite(value) or not low <= value <= high or positive and value <= low:
        raise core.StrataError(f'Invalid video {name}')
    return value


def timestamps(text, count, fps):
    if not isinstance(text, str):
        raise core.StrataError('Video timestamps must be a JSON array in seconds')
    values = core.json_loads(text) if text.strip() else [i / fps for i in range(count)]
    if not isinstance(values, list) or len(values) != count:
        raise core.StrataError('Supply one timestamp for each input frame')
    values = [number(v, 'timestamp', high=86400) for v in values]
    if any(a >= b for a, b in zip(values, values[1:])):
        raise core.StrataError('Video timestamps must be strictly increasing')
    return values


def pil_frame(tensor, max_pixels, alpha=None):
    import numpy as np
    from PIL import Image
    core.interrupted()
    array = tensor.detach().to('cpu').float().numpy()
    if not np.isfinite(array).all():
        raise core.StrataError('IMAGE contains non-finite pixel values')
    if alpha is not None:
        core.interrupted()
        mask = alpha.detach().to('cpu').float().numpy()
        if mask.ndim == 3 and mask.shape[-1] == 1:
            mask = mask[..., 0]
        if mask.shape != array.shape[:2] or not np.isfinite(mask).all():
            raise core.StrataError('VIDEO alpha must contain finite values matching its image dimensions')
        mask = np.clip(mask, 0, 1)
        if array.shape[-1] == 4:
            mask = mask * np.clip(array[..., 3], 0, 1)
        array = np.clip(array[..., :3], 0, 1) * mask[..., None] + (1 - mask[..., None])
    image = Image.fromarray((np.clip(array, 0, 1) * 255).round().astype(np.uint8))
    if image.mode == 'RGBA':
        rgb = Image.new('RGB', image.size, 'white')
        rgb.paste(image, mask=image.getchannel('A'))
        image = rgb
    else:
        image = image.convert('RGB')
    scale = min(1, (max_pixels / (image.width * image.height))**.5)
    if scale < 1:
        width, height = max(1, int(image.width * scale)), max(1, int(image.height * scale))
        if width * height > max_pixels:
            if width >= height:
                width = max(1, max_pixels // height)
            else:
                height = max(1, max_pixels // width)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    core.interrupted()
    return image


def sample_tensor(images, *, fps, timestamps_json='', start_s=0, end_s=None,
                  sampling_fps=1, max_frames=64, max_pixels=589824, alpha=None):
    if (not hasattr(images, 'shape') or len(images.shape) != 4 or images.shape[-1] not in (3, 4)
            or not 1 <= images.shape[0] <= 180000 or images.shape[1] < 1 or images.shape[2] < 1
            or images.shape[1] * images.shape[2] > 16 * 1048576):
        raise core.StrataError('Video IMAGE must be a bounded [frames, height, width, RGB/RGBA] tensor')
    if alpha is not None and (not hasattr(alpha, 'shape')
            or tuple(alpha.shape) not in (tuple(images.shape[:3]), (*images.shape[:3], 1))):
        raise core.StrataError('VIDEO alpha must match its image frame count and dimensions')
    values = timestamps(timestamps_json, images.shape[0], fps)
    source_duration = values[-1] + 1 / fps
    if not math.isfinite(source_duration):
        raise core.StrataError('Video source duration must be finite; supply a usable fps')
    stop = source_duration if end_s is None else min(end_s, source_duration)
    if stop <= start_s or stop - start_s > MAX_DURATION:
        raise core.StrataError('Select a nonempty IMAGE window of at most 3600 seconds')
    candidates = [i for i, t in enumerate(values) if start_s <= t < stop]
    if not candidates:
        raise core.StrataError('Video time range contains no frames')
    # Only selected tensor slices reach CPU; never .cpu() the entire video batch.
    selected = []
    for target in shared().sampling_schedule(start_s, stop, sampling_fps, max_frames):
        index = bisect.bisect_left(values, target)
        if index < len(values) and values[index] < stop and (not selected or index != selected[-1]):
            selected.append(index)
    # The end-exclusive final target lies after the last real CFR/PTS frame.
    # Preserve that actual endpoint instead of duplicating the previous sample.
    if len(candidates) > 1 and max_frames > 1 and candidates[-1] not in selected:
        if len(selected) >= max_frames:
            selected[-1] = candidates[-1]
        else:
            selected.append(candidates[-1])
    if not selected:
        raise core.StrataError('Video time range contains no frames')
    pictures = [pil_frame(images[i], max_pixels, alpha[i]) if alpha is not None else pil_frame(images[i], max_pixels)
                for i in selected]
    result = shared().sample_images(pictures, fps=fps, timestamps=[values[i] for i in selected],
                                   start_s=start_s, end_s=stop, sampling_fps=sampling_fps,
                                   max_frames=max_frames, max_pixels=max_pixels,
                                   max_duration_s=MAX_DURATION, cancel=core.interrupted,
                                   source_duration_s=source_duration, source_indices=selected, preselected=True)
    # Tensor batches cannot recover original decoder PTS unless supplied explicitly.
    result.manifest.setdefault('source', {}).update({'timestamp_basis': 'provided' if timestamps_json.strip() else 'estimated_cfr',
                                                    'input_frame_count': int(images.shape[0]),
                                                    'duration_s': source_duration})
    if alpha is not None:
        result.manifest['source']['alpha_compositing'] = 'white'
    result.manifest.setdefault('coverage', {}).update({'requested_start_s': start_s, 'requested_end_s': stop})
    for frame, index in zip(result.manifest['frames'], selected):
        frame['input_frame_index'] = index
        frame['timestamp_kind'] = 'provided' if timestamps_json.strip() else 'estimated'
    result.manifest['coverage']['timestamp_kind'] = 'provided' if timestamps_json.strip() else 'estimated'
    return result


def official_type(video):
    cls = type(video)
    module = sys.modules.get(cls.__module__)
    if (cls.__module__ not in ('comfy_api.latest._input_impl.video_types', 'comfy_api.input_impl.video_types')
            or cls.__name__ not in ('VideoFromFile', 'VideoFromComponents', 'VideoFromList')
            or getattr(module, cls.__name__, None) is not cls):
        raise core.StrataError('Unsupported VIDEO implementation; use official Load Video or an IMAGE adapter')
    return cls.__name__


def file_source(video):
    """Read the audited official file/trim/crop state without materializing VIDEO.

    The abstract VIDEO API has no crop getter. Recognized layouts are exact:
    file-only, the v0.33 file/trim object, or current file/trim/crop. Metadata supplies
    the raw duration and the audited state supplies trim/crop. Unknown layouts
    fail before decoding instead of calling unbounded get_components.
    """
    state = vars(video)
    old = {'_VideoFromFile__file'}
    trimmed = old | {'_VideoFromFile__start_time', '_VideoFromFile__duration'}
    current = trimmed | {'_VideoFromFile__crop'}
    if set(state) not in (old, trimmed, current):
        raise core.StrataError('Unsupported official VIDEO state layout; update the adapter or use IMAGE frames')
    crop = state.get('_VideoFromFile__crop')
    if crop is not None and (not isinstance(crop, tuple) or len(crop) != 4
            or any(type(value) is not int for value in crop) or min(crop[:2]) < 0 or min(crop[2:]) < 1):
        raise core.StrataError('Unsupported official VIDEO crop layout')
    try:
        source = video.get_stream_source()
        if isinstance(source, (str, Path)):
            if '://' in str(source) or not Path(source).is_file():
                raise core.StrataError('VIDEO source must be a local regular file')
            size = Path(source).stat().st_size
        elif isinstance(source, io.BytesIO):
            size = source.getbuffer().nbytes
        else:
            raise core.StrataError('VIDEO source must be a bounded local file or BytesIO')
    except (OSError, ValueError):
        raise core.StrataError('VIDEO source is unavailable or closed; reload the local video') from None
    if size > MAX_INPUT_BYTES:
        raise core.StrataError('VIDEO source exceeds 256 MiB; select a smaller source file')
    return state, crop, source


def metadata_guard(source):
    """Return bounded track duration without full-decode duration getters.

    The official fallback counts an entire decoded stream when metadata is
    absent. Reject that branch and correct container PTS offsets before trim.
    """
    import av
    core.interrupted()
    try:
        with av.open(source, mode='r', timeout=(10, 10),
                     options={'protocol_whitelist': 'file,pipe',
                              'format_whitelist': 'mov,matroska,webm,avi,flv,mpeg,mpegts,ogg,gif'}) as container:
            stream = next(iter(container.streams.video), None)
            if stream is None:
                raise core.StrataError('VIDEO source has no video stream')
            try:
                shared().video_color_precheck(stream)
            except ValueError as error:
                raise core.StrataError(str(error)) from None
            duration = shared().video_duration(container, stream)
            if duration is None and stream.frames and stream.average_rate:
                duration = float(stream.frames / stream.average_rate)
            if duration is None:
                raise core.StrataError('VIDEO duration metadata is missing; export a bounded video file or use IMAGE with timestamps')
            duration = number(duration, 'source duration', high=86400, positive=True)
    except (av.FFmpegError, OSError) as error:
        raise core.StrataError(f'VIDEO metadata could not be read: {error}') from None
    core.interrupted()
    return duration


def file_timing(state, raw_duration):
    """Apply the official trim rules to the bounded, corrected video-track duration."""
    raw_duration = number(raw_duration, 'source duration', high=86400, positive=True)
    start = number(state.get('_VideoFromFile__start_time', 0), 'source trim', low=-86400, high=86400)
    requested = number(state.get('_VideoFromFile__duration', 0), 'source trim duration', high=86400)
    original_start = max(raw_duration + start, 0.) if start < 0 else start
    remaining = raw_duration - original_start
    duration = min(requested, remaining) if requested else remaining
    return original_start, number(duration, 'duration', high=86400, positive=True)


def file_adapter(video, *, start_s, end_s, sampling_fps, max_frames, max_pixels, cancel, target_times=None):
    state, crop, source = file_source(video)
    original_start, duration = file_timing(state, metadata_guard(source))
    stop = duration if end_s is None else min(duration, end_s)
    if stop <= start_s or stop - start_s > MAX_DURATION:
        raise core.StrataError('Select a nonempty VIDEO window of at most 3600 seconds')
    result = shared().sample_video(source, start_s=original_start + start_s,
                                   end_s=original_start + stop, sampling_fps=sampling_fps,
                                   max_frames=max_frames, max_pixels=max_pixels, max_duration_s=MAX_DURATION,
                                   max_input_bytes=MAX_INPUT_BYTES, cancel=cancel, crop=crop,
                                   target_times=[original_start + value for value in target_times] if target_times is not None else None)
    result.manifest['source'].update({'adapter': 'official_file_state_v1', 'input_time_origin_s': start_s,
                                     'input_duration_s': duration, 'source_pts_preserved': True,
                                     'original_media_time_origin_s': original_start + start_s,
                                     'crop_after_rotation': list(crop) if crop is not None else None})
    result.manifest['coverage'].update({'input_window_start_s': start_s, 'input_window_end_s': stop})
    for frame in result.manifest['frames']:
        frame['input_timestamp_s'] = start_s + frame['timestamp_s']
        frame['original_media_timestamp_s'] = original_start + start_s + frame['timestamp_s']
    return result


def list_adapter(video, *, start_s, end_s, sampling_fps, max_frames, max_pixels):
    state = vars(video)
    if (set(state) != {'videos', 'complete_audio', '_VideoFromList__buffer'} or not isinstance(video.videos, list)
            or not 1 <= len(video.videos) <= 64):
        raise core.StrataError('Unsupported accumulated VIDEO layout')
    deadline = time.monotonic() + 180
    def check():
        core.interrupted()
        if time.monotonic() >= deadline:
            raise core.StrataError('Accumulated VIDEO sampling exceeded its CPU time limit')
    durations = []
    for item in video.videos:
        check()
        if official_type(item) != 'VideoFromFile':
            raise core.StrataError('Accumulated VIDEO must contain bounded official file videos')
        item_state, _, source = file_source(item)
        raw_duration = metadata_guard(source)
        check()
        durations.append(file_timing(item_state, raw_duration)[1])
        check()
    duration = sum(durations)
    stop = duration if end_s is None else min(end_s, duration)
    if stop <= start_s or stop - start_s > MAX_DURATION:
        raise core.StrataError('Select an accumulated VIDEO window of at most 3600 seconds')
    targets = shared().sampling_schedule(start_s, stop, sampling_fps, max_frames)
    step = targets[1] - targets[0] if len(targets) > 1 else max(1 / sampling_fps, stop - start_s)
    pictures, times, details = [], [], []
    offset = 0.
    for component_index, (component, component_duration) in enumerate(zip(video.videos, durations)):
        check()
        component_targets = [target - offset for target in targets if offset <= target < offset + component_duration]
        if component_targets:
            local_start = component_targets[0]
            local_end = min(component_duration, stop - offset, component_targets[-1] + step)
            sampled = file_adapter(component, start_s=local_start, end_s=local_end, sampling_fps=1 / step,
                                   max_frames=len(component_targets), max_pixels=max_pixels, cancel=check)
            for frame in sampled.frames:
                pictures.append(frame.image)
                times.append(offset + local_start + frame.timestamp_s)
                details.append({'component_index': component_index,
                                'component_source_timestamp_s': frame.source_timestamp_s})
        offset += component_duration
    result = shared().sample_images(pictures, fps=sampling_fps, timestamps=times, source_duration_s=duration,
                                    preselected=True, start_s=start_s, end_s=stop, sampling_fps=sampling_fps,
                                    max_frames=max_frames, max_pixels=max_pixels, cancel=check)
    result.manifest['source'].update({'kind': 'video_list', 'timestamp_basis': 'composite_media_clock'})
    result.manifest['coverage']['timestamp_kind'] = 'composite'
    for frame, detail in zip(result.manifest['frames'], details):
        frame.update(detail, timestamp_kind='composite')
    return result


def sample_input(video=None, images=None, *, fps=24, timestamps_json='', start_s=0, end_s=None,
                 sampling_fps=1, max_frames=64, max_pixels=589824):
    fps = number(fps, 'fps', high=240, positive=True)
    sampling_fps = number(sampling_fps, 'sampling_fps', high=30, positive=True)
    if fps < .001 or sampling_fps < .01:
        raise core.StrataError('Video fps must be at least 0.001 and sampling_fps at least 0.01')
    if not isinstance(timestamps_json, str):
        raise core.StrataError('Video timestamps must be JSON text')
    core.text_unicode(timestamps_json)
    start_s = number(start_s, 'start_s', high=86400)
    if end_s is not None:
        end_s = number(end_s, 'end_s', high=86400, positive=True)
        if end_s <= start_s:
            raise core.StrataError('Video end must be later than start')
    if type(max_frames) is not int or not 1 <= max_frames <= MAX_FRAMES:
        raise core.StrataError('Video max_frames must be between 1 and 64')
    if type(max_pixels) is not int or not 65536 <= max_pixels <= 1048576:
        raise core.StrataError('Video max_pixels must be between 65536 and 1048576')
    if (video is None) == (images is None):
        raise core.StrataError('Connect exactly one VIDEO or IMAGE input')
    if images is not None:
        return sample_tensor(images, fps=fps, timestamps_json=timestamps_json, start_s=start_s,
                             end_s=end_s, sampling_fps=sampling_fps, max_frames=max_frames, max_pixels=max_pixels)
    if timestamps_json.strip():
        raise core.StrataError('Explicit timestamps apply to IMAGE input only')
    name = official_type(video)
    if name == 'VideoFromComponents':
        state = set(vars(video))
        if state not in ({'_VideoFromComponents__components'},
                         {'_VideoFromComponents__components', '_VideoFromComponents__bit_depth'},
                         {'_VideoFromComponents__components', '_VideoFromComponents__bit_depth', '_VideoFromComponents__color_space'}):
            raise core.StrataError('Unsupported official VIDEO components state layout')
        components = vars(video)['_VideoFromComponents__components']  # Preserve v0.33 alpha, without materialization.
        if '_VideoFromComponents__color_space' in state and video.get_color_space() != 'sRGB':
            raise core.StrataError('Unsupported VIDEO color space; convert component images to sRGB before analysis')
        try:
            if isinstance(components.frame_rate, bool):
                raise ValueError('Boolean component fps')
            component_fps = number(float(components.frame_rate), 'component fps', high=240, positive=True)
        except (TypeError, ValueError, OverflowError):
            raise core.StrataError('Invalid video component fps') from None
        if component_fps < .001:
            raise core.StrataError('Video component fps must be at least 0.001')
        return sample_tensor(components.images, fps=component_fps, start_s=start_s,
                             end_s=end_s, sampling_fps=sampling_fps, max_frames=max_frames, max_pixels=max_pixels,
                             alpha=getattr(components, 'alpha', None))
    if name == 'VideoFromList':
        return list_adapter(video, start_s=start_s, end_s=end_s, sampling_fps=sampling_fps,
                            max_frames=max_frames, max_pixels=max_pixels)
    return file_adapter(video, start_s=start_s, end_s=end_s, sampling_fps=sampling_fps,
                        max_frames=max_frames, max_pixels=max_pixels, cancel=core.interrupted)


