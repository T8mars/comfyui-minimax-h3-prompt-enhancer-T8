"""Explicit real CPU ASR and H3/Seedance acceptance (16 mixed or 8 active).

Never starts/stops/loads/unloads the user's LLM service. Its GET status and chat
POST are the only allowed calls. A separate, owned random-port ASR-only service
uses copied source/CPU runtime and existing read-only model files. MockEngine is
only the ASR server's constructor placeholder: its chat endpoint is forbidden.
Results are evidence for human review, not a rendered-video quality benchmark.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import hashlib
import http.client
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_WORDS = ("这是一段视频测试", "红色圆圈正在向右移动", "现在背景变成蓝色")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(text):
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE)


def output_directory(value, strata_source):
    destination = Path(value).resolve()
    for protected in (ROOT, Path(strata_source).resolve()):
        if destination == protected or protected in destination.parents:
            raise ValueError("Acceptance output must be outside both source repositories")
    if destination == Path(destination.anchor):
        raise ValueError("Use a dedicated acceptance artifact directory")
    return destination


def loopback_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") not in ("", "/v1")):
        raise ValueError("Real acceptance requires an explicit loopback service root without credentials")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid service port")
    return value.rstrip("/").removesuffix("/v1")


def service_identity(value):
    """Only bounded identity/residency fields, never monitor text or credentials."""
    processes = value.get("processes", {})
    return {"model": value.get("model"), "started": value.get("started"),
            "instance_id": value.get("instance_id"), "package_version": value.get("package_version"),
            "loaded": value.get("loaded"), "context": (value.get("context") or {}).get("native"),
            "processes": {kind: {key: processes.get(kind, {}).get(key) for key in ("pid", "loaded", "running")}
                          for kind in ("engine", "vision")}}


def assert_residency(before, after):
    for key in ("model", "started", "instance_id", "context"):
        if before[key] != after[key]:
            raise AssertionError("User service identity changed: " + key)
    if not before["loaded"] or not after["loaded"]:
        raise AssertionError("User main model must remain loaded")
    for kind in ("engine", "vision"):
        if before["processes"][kind] != after["processes"][kind]:
            raise AssertionError("User process/residency changed: " + kind)


def matrix_cases():
    """Four cases total, each Off/On x two repetitions = sixteen generations."""
    common = ("只使用用户明确给出的事实。若未提供语音内容，不要猜具体台词。"
              "不得添加字幕、配乐、说话人身份识别或声学测量结论。")
    return [
        {"id": "h3-story", "target": "h3", "purpose": "reference", "prompt": "一位讲解者展示圆形运动测试，按语音参考理解事件顺序，写成连续的简短演示，不照搬对白。" + common},
        {"id": "h3-dialogue", "target": "h3", "purpose": "keep_dialogue", "prompt": "我明确指派语音参考的全部语句由目标片的讲解者发声，不代表原片说话人识别。若有语音参考，在15秒内按顺序说完全部三句，原词原语言不改，动作只作简单演示。" + common},
        {"id": "sd-story", "target": "seedance", "purpose": "reference", "prompt": "用一个简单演示讲解圆形运动与背景变化，语音参考仅供理解剧情，不照搬对白，镜头清晰克制。" + common},
        {"id": "sd-dialogue", "target": "seedance", "purpose": "keep_dialogue", "prompt": "我明确指派全部语音参考语句给目标片讲解者，不是自动识别人声。若有语音参考，15秒内依次完整说出原文三句，保持原语言原词，画面仅以极简几何变化辅助。" + common},
    ]


def active_states(active_only=False):
    """Keep the original matrix/order unchanged unless explicitly selected."""
    return (True,) if active_only else (False, True)


def request_kind(body, *, first):
    if first:
        return "initial"
    systems = [item.get("content", "") for item in body.get("messages", []) if item.get("role") == "system"]
    if any(isinstance(value, str) and "Deterministic issue codes:" in value
           and "Return only the complete corrected" in value for value in systems):
        return "speech_semantic_correction"
    return "legacy_correction"


def public_completion(value):
    """Only final visible content, never reasoning, credentials or headers."""
    choices = value.get("choices", [])
    return {"model": value.get("model"), "choices": [
        {"finish_reason": item.get("finish_reason"),
         "content": (item.get("message") or {}).get("content")}
        for item in choices if isinstance(item, dict)]}


class Workers:
    def __init__(self, owned_root):
        self.root = str(Path(owned_root).resolve()).replace("\\", "/").lower()
        self.observed = {}
        self.stop = threading.Event()
        self.thread = None

    def current(self):
        import psutil
        rows = []
        for process in psutil.process_iter(("pid", "ppid", "cmdline")):
            try:
                command = " ".join(process.info.get("cmdline") or ()).replace("\\", "/").lower()
                if self.root in command and ("/serve/asr/worker.py" in command or "/serve/media_worker.py" in command):
                    rows.append({"pid": process.info["pid"], "ppid": process.info["ppid"],
                                 "kind": "asr" if "/serve/asr/worker.py" in command else "media"})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return rows

    def poll(self):
        while not self.stop.is_set():
            for row in self.current():
                self.observed.setdefault(row["pid"], {**row, "first_seen": time.monotonic()})
            self.stop.wait(.08)

    def __enter__(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(3)

    def wait_empty(self, timeout=30):
        deadline = time.monotonic() + timeout
        while self.current() and time.monotonic() < deadline:
            time.sleep(.1)
        if self.current():
            raise AssertionError("Owned ASR/media worker did not exit")


class OwnedASR:
    def __init__(self, source, destination, models, vad):
        self.source, self.root = Path(source).resolve(), Path(destination).resolve()
        self.models, self.vad = Path(models).resolve(), Path(vad).resolve() if vad else None
        self.requests = []
        self.http = None
        self.previous_temp = tempfile.tempdir
        self.previous_local = os.environ.get("LOCALAPPDATA")

    def _start(self):
        if self.root.exists():
            raise ValueError("Owned ASR root already exists; choose a fresh --output directory for ASR")
        self.root.mkdir(parents=True)
        for name in ("serve", "tools"):
            shutil.copytree(self.source / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
        # No junction permissions or model copies. Copy only the CPU runtime.
        for name in ("python", "native-cpu"):
            shutil.copytree(self.source / "runtime/asr" / name, self.root / "runtime/asr" / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        settings = {"model_dir": str(self.models), "vad_dir": str(self.vad) if self.vad else "",
                    "quantization": "Q4_K_M", "device": "cpu", "language": "Chinese"}
        save(self.root / "asr-settings.json", settings)
        for name in ("meta.json", "features.json"):
            shutil.copy2(self.source / name, self.root / name)
        self.root.joinpath("temp").mkdir()
        tempfile.tempdir = str(self.root / "temp")
        os.environ["LOCALAPPDATA"] = str(self.root / "local-appdata")
        if "serve.server" in sys.modules:
            raise RuntimeError("Run acceptance in a fresh interpreter; serve.server is already imported")
        sys.path.insert(0, str(self.root))
        server = importlib.import_module("serve.server")
        if server.ROOT.resolve() != self.root:
            raise AssertionError("Strata server import escaped the isolated root")
        from serve.frontend import ChatTemplate
        self.service = server.Service(server.MockEngine(server.ByteTokenizer(), ""), server.ByteTokenizer(),
            ChatTemplate(self.root / "serve/chat_template.jinja"), model_name="ASR-only-placeholder-DO-NOT-USE")
        base = server.make_handler(self.service)
        owner = self

        class ASROnlyHandler(base):
            def do_GET(self):
                path = self.path.split("?", 1)[0].rstrip("/")
                owner.requests.append({"method": "GET", "path": path, "at": time.monotonic()})
                if path not in ("/v1/asr/capabilities", "/v1/asr/status"):
                    self._json(403, {"error": {"type": "acceptance_forbidden"}})
                    return
                super().do_GET()

            def do_POST(self):
                path = self.path.split("?", 1)[0].rstrip("/")
                self.acceptance_request = {"method": "POST", "path": path, "at": time.monotonic()}
                owner.requests.append(self.acceptance_request)
                if path not in ("/v1/audio/transcribe", "/v1/video/transcribe", "/v1/asr/transcript/parse"):
                    self._json(403, {"error": {"type": "acceptance_forbidden"}})
                    return
                super().do_POST()

            def _request_json(self):
                value = super()._request_json()
                if isinstance(value, dict):
                    row = getattr(self, "acceptance_request", None)
                    if row is not None:
                        row.update(payload_bytes=len(self.request_body),
                                   request_keys=sorted(value), expected_device=value.get("expected_device"))
                        encoded = value.get("data")
                        if isinstance(encoded, str):
                            row["encoded_data_sha256"] = hashlib.sha256(encoded.encode("ascii")).hexdigest()
                        for key in ("start_s", "end_s", "language", "audio_track", "channel", "offset_ms"):
                            if key in value:
                                row[key] = value[key]
                return value

            def _json(self, status, value, *positional, **keywords):
                row = getattr(self, "acceptance_request", None)
                if row is not None and isinstance(value, dict):
                    row.update(response_status=status, response_contract_version=value.get("contract_version"),
                               response_status_name=value.get("status"), response_device=value.get("device"))
                    audio = value.get("audio")
                    if isinstance(audio, dict):
                        row["response_audio_clock"] = {key: audio[key] for key in (
                            "source_origin_s", "window_start_s", "window_end_s", "track", "sample_rate",
                            "audio_covered_samples", "gap_samples", "clock") if key in audio}
                return super()._json(status, value, *positional, **keywords)

        self.service.host_names = server.host_names_for("127.0.0.1", [], [])
        self.http = server.Server(("127.0.0.1", 0), ASROnlyHandler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        return self

    def __enter__(self):
        try:
            return self._start()
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *unused):
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()
        tempfile.tempdir = self.previous_temp
        if self.previous_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.previous_local


def load_plugin():
    # Import the actual implementation, with Comfy's CPU configuration only.
    sys.argv = [sys.argv[0], "--cpu"]
    sys.path.insert(0, str(ROOT.parents[1]))
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    name = "_t8_speech_real_acceptance"
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return {key: importlib.import_module(name + "." + key)
            for key in ("nodes", "seedance20", "speech_reference", "strata_provider", "h3_quality")}


def pcm48_stereo(path):
    import av
    import numpy as np
    with av.open(str(path)) as source:
        converter = av.AudioResampler(format="fltp", layout="stereo", rate=48000)
        frames = []
        for frame in source.decode(audio=0):
            frames.extend(converter.resample(frame))
        frames.extend(converter.resample(None))
    return np.concatenate([frame.to_ndarray() for frame in frames], axis=1).astype(np.float32)


def video_without_audio(path):
    import av
    import numpy as np
    with av.open(str(path), "w", format="mp4") as output:
        stream = output.add_stream("libx264", rate=4)
        stream.width, stream.height, stream.pix_fmt = 32, 32, "yuv420p"
        for _ in range(4):
            frame = av.VideoFrame.from_ndarray(np.zeros((32, 32, 3), np.uint8), format="rgb24")
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)


def nonzero_pts_video(path, pcm):
    """Known presentation origin 5s and speech delay 0.5s, without re-timing by FPS."""
    from fractions import Fraction
    import av
    import numpy as np
    with av.open(str(path), "w", format="matroska") as output:
        video = output.add_stream("ffv1", rate=4)
        video.width, video.height, video.pix_fmt = 32, 32, "yuv420p"
        audio = output.add_stream("pcm_f32le", rate=48000)
        audio.layout = "stereo"
        packets = []
        for index in range(40):
            frame = av.VideoFrame.from_ndarray(np.zeros((32, 32, 3), np.uint8), format="rgb24")
            frame.pts, frame.time_base = 20 + index, Fraction(1, 4)
            packets.extend(video.encode(frame))
        packets.extend(video.encode())
        for first in range(0, pcm.shape[1], 1024):
            frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(pcm[:, first:first+1024]), format="fltp", layout="stereo")
            frame.sample_rate, frame.pts, frame.time_base = 48000, 264000 + first, Fraction(1, 48000)
            packets.extend(audio.encode(frame))
        packets.extend(audio.encode())
        for packet in sorted(packets, key=lambda value: float(value.dts * value.time_base)):
            output.mux(packet)


def prepare_reference(speech, *, source_mode, audio=None, video=None, start_s=0., end_s=0., offset_ms=0, url=""):
    """Actual helper adapter; its public fields are checked, never guessed at runtime."""
    config = {"schema_version": "t8-llm-provider-config/v1", "provider": "Strata", "strata_settings": {"url": url}}
    output = speech.T8SpeechReference.execute(mode="Enabled", source_mode=source_mode.upper(), audio=audio, video=video,
        start_s=start_s, duration_s=end_s-start_s, offset_ms=offset_ms, provider_config=config,
        language="Chinese", purpose="reference")
    values = output.result
    return {"reference": values[0], "text": values[1], "timed": json.loads(values[2]) if values[2] else None, "srt": values[3]}


def post_guarded(session, url, path, data, **options):
    payload = {"data": base64.b64encode(data).decode("ascii"), "expected_device": "cpu", **options}
    response = session.post(url + path, json=payload, timeout=1800, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise AssertionError("ASR response was not HTTP 200; redirects are forbidden")
    result = response.json()
    if type(result.get("contract_version")) is not int or result["contract_version"] != 1:
        raise AssertionError("Invalid real ASR transcript contract")
    return result


def cancel_owned(session, owned, workers, data):
    payload = json.dumps({"data": base64.b64encode(data).decode("ascii"), "expected_device": "cpu",
                          "context": "independent cancellation acceptance"}).encode("utf-8")
    endpoint = urlsplit(owned.url)
    connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=1800)
    outcome = {}

    def request():
        try:
            connection.request("POST", "/v1/audio/transcribe", payload, {"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            outcome["http_status"] = response.status
        except Exception as error:
            outcome["exception_type"] = type(error).__name__

    thread = threading.Thread(target=request, daemon=True)
    initial = set(workers.observed)
    thread.start()
    deadline = time.monotonic() + 90
    observed = []
    while time.monotonic() < deadline:
        observed = [row for row in workers.current() if row["kind"] == "asr" and row["pid"] not in initial]
        if observed or not thread.is_alive():
            break
        time.sleep(.05)
    if not observed:
        raise AssertionError("Cancellation did not observe a real owned ASR worker")
    transport = connection.sock
    if transport is not None:
        with contextlib.suppress(OSError):
            transport.shutdown(socket.SHUT_RDWR)
    connection.close()
    thread.join(30)
    workers.wait_empty()
    if thread.is_alive():
        raise AssertionError("Cancelled client request did not finish")
    progress = owned.service.asr_manager.progress()
    if progress.get("phase") != "cancelled":
        raise AssertionError("Owned ASR service did not acknowledge cancellation")
    return {"observed_workers": observed, "client": outcome, "service_phase": progress.get("phase")}


def run_asr(args, modules, session, identity):
    import numpy as np
    import torch
    from comfy_api.latest._input_impl.video_types import VideoFromFile
    fixtures = args.strata_source / ".portable-build/asr-development-20261014"
    sound, movie = fixtures / "speech-zh.wav", fixtures / "speech-visual.mp4"
    twelve = args.strata_source / ".portable-build/audit-video-speech-20261014/twelve-seconds.mp4"
    for path in (sound, movie, twelve):
        if not path.is_file():
            raise FileNotFoundError("Existing synthetic acceptance fixture is missing: " + str(path))
    source_hashes = {path.name: sha256(path) for path in (sound, movie, twelve)}
    pcm = pcm48_stereo(sound)
    audio = {"waveform": torch.from_numpy(pcm[None].copy()), "sample_rate": 48000}
    silent = {"waveform": torch.zeros((1, 2, 48000 * 2)), "sample_rate": 48000}
    quiet = {"waveform": audio["waveform"] * .03, "sample_rate": 48000}
    no_track = args.output / "fixtures/no-track.mp4"
    no_track.parent.mkdir(parents=True, exist_ok=True)
    video_without_audio(no_track)
    nonzero = args.output / "fixtures/nonzero-origin-delayed-speech.mkv"
    nonzero_pts_video(nonzero, pcm)
    result = {"source_hashes": source_hashes, "cases": [], "native_cpu_asr": True, "mock_chat_requests": 0}
    owned_root = args.output / "owned-asr"
    with OwnedASR(args.strata_source, owned_root, args.asr_model_dir, args.vad_dir) as owned, Workers(owned_root) as workers:
        capability_response = session.get(owned.url + "/v1/asr/capabilities", timeout=10, allow_redirects=False)
        if capability_response.status_code != 200:
            raise AssertionError("ASR capability response must be HTTP 200 without redirect")
        caps = capability_response.json()
        if type(caps.get("contract_version")) is not int or caps["contract_version"] != 1 or caps.get("cpu_guard") is not True:
            raise AssertionError("Owned service lacks the explicit CPU guard contract")
        if caps.get("supported") is not True or caps.get("device") != "cpu":
            raise AssertionError("Existing CPU ASR model/runtime is not ready")
        result["capabilities"] = caps
        selections = [
            ("audio-48k-stereo", dict(source_mode="audio", audio=audio, start_s=0., end_s=9.), "complete"),
            ("file-aac", dict(source_mode="video", video=VideoFromFile(str(movie)), start_s=0., end_s=9.), "complete"),
            ("file-trim", dict(source_mode="video", video=VideoFromFile(str(movie), start_time=2., duration=4.), start_s=.5, end_s=3.5), "complete"),
            ("audio-offset", dict(source_mode="audio", audio=audio, start_s=0., end_s=9., offset_ms=250), "complete"),
            ("audio-offset-large", dict(source_mode="audio", audio=audio, start_s=0., end_s=9., offset_ms=10000), "complete"),
            ("audio-offset-negative", dict(source_mode="audio", audio=audio, start_s=0., end_s=9., offset_ms=-1000), "complete"),
            ("digital-silence", dict(source_mode="audio", audio=silent, start_s=0., end_s=2.), "silence"),
            ("no-track", dict(source_mode="video", video=VideoFromFile(str(no_track)), start_s=0., end_s=1.), "no_track"),
            ("low-volume-nonzero", dict(source_mode="audio", audio=quiet, start_s=0., end_s=9.), None),
            ("twelve-second-file", dict(source_mode="video", video=VideoFromFile(str(twelve)), start_s=0., end_s=12.), "complete"),
            ("file-nonzero-pts", dict(source_mode="video", video=VideoFromFile(str(nonzero)), start_s=0., end_s=10.), "complete"),
        ]
        selected = set(args.only.split(",")) if args.only else None
        if selected and selected - {row[0] for row in selections} - {"cancel-and-new-request"}:
            raise ValueError("Unknown explicit ASR follow-up case")
        baseline = None
        for case_id, options, expected_status in selections:
            if selected and case_id not in selected:
                continue
            start = time.monotonic()
            initial_requests, initial_workers = len(owned.requests), set(workers.observed)
            before = identity()
            row = {"id": case_id, "passed": False}
            try:
                prepared = prepare_reference(modules["speech_reference"], url=owned.url, **options)
                transcript = prepared["timed"]
                if transcript is None:
                    raise AssertionError("Actual helper did not return timed_json")
                if expected_status and transcript["status"] != expected_status:
                    raise AssertionError("Unexpected ASR status: " + transcript["status"])
                if case_id in ("audio-48k-stereo", "file-aac", "twelve-second-file", "file-nonzero-pts"):
                    text = normalized(prepared["text"])
                    positions = [text.find(words) for words in EXPECTED_WORDS]
                    if any(position < 0 for position in positions) or positions != sorted(positions):
                        raise AssertionError("Known synthetic speech words/order not preserved")
                if case_id == "file-nonzero-pts":
                    received = [item for item in owned.requests[initial_requests:] if item["method"] == "POST"]
                    clock = received[0].get("response_audio_clock", {}) if received else {}
                    if abs(clock.get("source_origin_s", -999) - 5.) > .001:
                        raise AssertionError("Actual decoded video presentation origin was not 5 seconds")
                    if not .4 < transcript["cues"][0]["start_s"] < 1.:
                        raise AssertionError("Audio delay was collapsed or container origin added twice")
                    row["fixture_clock"] = {"container_origin_s": 5., "audio_delay_s": .5,
                                            "file_sha256": sha256(nonzero), "actual_service_clock": clock}
                if case_id == "audio-48k-stereo":
                    baseline = prepared
                    save(args.output / "speech-reference.json", prepared)
                if case_id in {"audio-offset", "audio-offset-large", "audio-offset-negative"}:
                    if baseline is None or len(transcript["cues"]) != len(baseline["timed"]["cues"]):
                        raise AssertionError("Offset changed transcript cue count")
                    for original, shifted in zip(baseline["timed"]["cues"], transcript["cues"]):
                        offset = options["offset_ms"] / 1000
                        if (original["id"] != shifted["id"] or original["text"] != shifted["text"]
                                or abs(shifted["start_s"] - max(0, original["start_s"] + offset)) > 1 / 16000
                                or abs(shifted["end_s"] - original["end_s"] - offset) > 1 / 16000):
                            raise AssertionError("Offset was not applied exactly once")
                    posts = [item for item in owned.requests[initial_requests:] if item["method"] == "POST"]
                    if len(posts) != 1 or posts[0].get("offset_ms") != 0:
                        raise AssertionError("Manual calibration reached the service's local clock")
                if case_id == "low-volume-nonzero" and transcript["status"] not in ("complete", "no_speech", "partial"):
                    raise AssertionError("Nonzero low-volume audio was skipped as digital silence")
                row.update(passed=True, transcript=prepared)
            except Exception as error:
                row.update(error_type=type(error).__name__, error=str(error)[:500])
            workers.wait_empty()
            after = identity()
            assert_residency(before, after)
            row.update(seconds=round(time.monotonic()-start, 3), requests=copy.deepcopy(owned.requests[initial_requests:]),
                       new_workers=[value for pid, value in workers.observed.items() if pid not in initial_workers],
                       user_residency_before=before, user_residency_after=after)
            result["cases"].append(row)
            save(args.output / "asr-results.json", result)
            print(json.dumps({key: row.get(key) for key in ("id", "passed", "seconds", "error")}, ensure_ascii=False), flush=True)
        # Whole utterances from a real transcript remain whole in overlapping windows.
        if baseline and baseline["timed"]["cues"]:
            from serve.asr.contract import relevant
            cue = baseline["timed"]["cues"][0]
            middle = (cue["start_s"] + cue["end_s"]) / 2
            actual_cues = {"contract_version": 1, "timeline": baseline["timed"]["timeline"],
                           "status": baseline["timed"]["status"], "cues": baseline["timed"]["cues"]}
            left = relevant(actual_cues, cue["start_s"], middle)
            right = relevant(actual_cues, middle, cue["end_s"])
            same = left["cues"][0]["id"] == right["cues"][0]["id"] and left["cues"][0]["text"] == right["cues"][0]["text"]
            result["cases"].append({"id": "real-cue-cross-window", "passed": same, "left": left, "right": right})
        if selected is None or "cancel-and-new-request" in selected:
            before = identity()
            cancellation = cancel_owned(session, owned, workers, sound.read_bytes())
            recovered = post_guarded(session, owned.url, "/v1/audio/transcribe", sound.read_bytes(), context="independent post-cancellation recovery")
            workers.wait_empty()
            assert_residency(before, identity())
            result["cases"].append({"id": "cancel-and-new-request", "passed": recovered["status"] == "complete", "cancellation": cancellation,
                                    "recovered": recovered, "user_residency_before": before, "user_residency_after": identity()})
        result["requests"] = owned.requests
        if any(row.get("expected_device") != "cpu" for row in owned.requests if row["method"] == "POST"):
            raise AssertionError("An actual ASR POST did not contain expected_device=cpu")
        result["copied_source_sha256"] = {str(path.relative_to(owned_root)).replace("\\", "/"): sha256(path)
                                         for path in (owned_root / "serve/asr").rglob("*.py")}
        for relative in ("serve/server.py", "serve/media_jobs.py", "serve/media_worker.py"):
            result["copied_source_sha256"][relative] = sha256(owned_root / relative)
        result["workers_observed"] = list(workers.observed.values())
        result["owned_workers_after"] = workers.current()
        result["mock_chat_requests"] = sum(row["path"] == "/v1/chat/completions" for row in owned.requests)
        if result["mock_chat_requests"]:
            raise AssertionError("ASR placeholder was incorrectly requested as a chat model")
    save(args.output / "asr-results.json", result)
    return result


def run_llm(args, modules, session, identity):
    reference_path = args.reference or args.output / "speech-reference.json"
    prepared = json.loads(reference_path.read_text(encoding="utf-8"))
    reference = modules["speech_reference"].resolve_speech_reference(prepared["reference"])
    sp = modules["strata_provider"]
    records, calls = [], []
    original = sp.StrataClient.request
    current = {"id": None}

    def measured(client, path, body=None, **options):
        if client.settings.url.rstrip("/").removesuffix("/v1") != args.llm_url:
            raise AssertionError("LLM acceptance escaped the explicitly selected service")
        if path not in ("/v1/status", "/v1/models", "/v1/chat/completions"):
            raise AssertionError("Lifecycle or arbitrary endpoint requested")
        row = {"case": current["id"], "method": "POST" if body is not None else "GET", "path": path}
        artifact = f"{current['id']}-{len(calls)}.json"
        if body is not None:
            wire = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            row.update(payload_sha256=hashlib.sha256(wire).hexdigest(), bytes=len(wire),
                       source_words_present=[words in normalized(wire.decode("utf-8")) for words in EXPECTED_WORDS])
            row["kind"] = request_kind(body, first=not any(call["case"] == current["id"] and call["method"] == "POST" for call in calls))
            row["submitted"] = False
            previous_submit = options.get("on_submit")
            def submitted():
                row["submitted"] = True
                if previous_submit:
                    previous_submit()
            options["on_submit"] = submitted
            save(args.output / "llm-requests" / artifact, body)
        calls.append(row)
        start = time.monotonic()
        try:
            value = original(client, path, body, **options)
            row["response_received"] = True
            if body is not None:
                save(args.output / "llm-responses" / artifact, public_completion(value))
            return value
        except Exception as error:
            row.update(error_type=type(error).__name__, error_category=getattr(error, "category", ""))
            raise
        finally:
            row["seconds"] = round(time.monotonic() - start, 3)

    sp.StrataClient.request = measured
    try:
        for case in matrix_cases():
            if args.only and case["id"] not in set(args.only.split(",")):
                continue
            for repeat in (1, 2):
                for active in active_states(args.active_only):
                    selected_reference = copy.deepcopy(reference)
                    selected_reference["purpose"] = case["purpose"]
                    selected_reference["speaker_map"] = {"default": "讲解者"} if case["purpose"] == "keep_dialogue" else {}
                    selected_reference = modules["speech_reference"].resolve_speech_reference(selected_reference)
                    case_id = f"{case['id']}-{'on' if active else 'off'}-{repeat}"
                    current["id"] = case_id
                    before, initial = identity(), len(calls)
                    start = time.monotonic()
                    row = {"id": case_id, "target": case["target"], "active": active, "repeat": repeat, "passed": False}
                    progress = []
                    def captured_progress(stage, **details):
                        if stage == "speech_output_checked":
                            metadata = details.get("quality_metadata", {})
                            progress.append({"stage": stage, "quality_metadata": {key: metadata.get(key)
                                for key in ("result", "correction_calls", "protocol_edits", "issue_codes", "unchecked")}})
                        elif stage == "llm_completed":
                            progress.append({"stage": stage, "attempts": details.get("attempts")})
                    try:
                        function = modules["nodes"].enhance_prompt if case["target"] == "h3" else modules["seedance20"].enhance_seedance20_prompt
                        result = function(prompt=case["prompt"], duration_seconds=15, output_language="中文", seed=731 + repeat,
                            api_mode=sp.STRATA_API_MODE, speech_reference=selected_reference if active else None,
                            progress_callback=captured_progress,
                            provider_request_options={"strata_settings": {"url": args.llm_url, "max_tokens": 4096,
                                "reasoning_effort": "none", "timeout_s": 1800}})
                        if not isinstance(result, str) or not result.strip():
                            raise AssertionError("Actual main enhancer returned empty text")
                        checker = modules["h3_quality"].check_h3 if case["target"] == "h3" else modules["h3_quality"].check_seedance
                        report = checker(result, **({"task_type": "T2VA", "duration": 15, "language": "中文"} if case["target"] == "h3" else {"language": "中文"}))
                        post = [call for call in calls[initial:] if call["method"] == "POST"]
                        if not post or any(call["path"] != "/v1/chat/completions" for call in post):
                            raise AssertionError("No actual user-service LLM POST was observed")
                        if active and not all(post[0]["source_words_present"]):
                            raise AssertionError("Typed transcript did not reach the real LLM request")
                        locked = all(cue["text"] in result for cue in selected_reference["cues"]) if active and case["purpose"] == "keep_dialogue" else None
                        row.update(passed=not report.get("issues") and locked is not False, transport_passed=True,
                                   native_format_passed=not report.get("issues"), locked_dialogue_preserved=locked,
                                   purpose=case["purpose"], output=result, native_quality_report=report,
                                   human_review_required=True, speech_reference_sha256=hashlib.sha256(json.dumps(selected_reference, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if active else None)
                        (args.output / "llm-results").mkdir(exist_ok=True)
                        (args.output / "llm-results" / (case_id + ".txt")).write_text(result, encoding="utf-8")
                    except Exception as error:
                        row.update(error_type=type(error).__name__, error=str(error)[:500])
                    after = identity()
                    assert_residency(before, after)
                    post = [call for call in calls[initial:] if call["method"] == "POST"]
                    semantic = sum(call["kind"] == "speech_semantic_correction" for call in post)
                    if semantic > 1:
                        raise AssertionError("Active semantic correction exceeded its one-request bound")
                    row.update(seconds=round(time.monotonic()-start, 3), requests=len(post), correction_requests=max(0, len(post)-1),
                               submitted_requests=sum(call.get("submitted", False) for call in post),
                               semantic_correction_requests=semantic,
                               legacy_correction_requests=sum(call["kind"] == "legacy_correction" for call in post),
                               progress=progress,
                               calls=calls[initial:], user_residency_before=before, user_residency_after=after)
                    records.append(row)
                    save(args.output / "llm-results.json", {"cases": records, "calls": calls, "four_cases_total": True,
                         "active_only": args.active_only, "human_review_required": True})
                    print(json.dumps({key: row.get(key) for key in ("id", "passed", "seconds", "requests", "error")}, ensure_ascii=False), flush=True)
    finally:
        sp.StrataClient.request = original
    save(args.output / "human-review-template.json", {"not_a_quality_certificate": True,
         "criteria": ["台词原词/语言保真", "源事件顺序与目标时轴合理", "角色为用户指派而非自动推断", "无虚假BPM/音色/环境声观察", "H3/Seedance原生格式", "On相对Off的实际内容收益与代价"],
         "rows": [{"id": row["id"], "reviewed": False, "notes": "", "factuality_0_to_4": None, "native_format_0_to_4": None} for row in records]})
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strata-source", type=Path, required=True)
    parser.add_argument("--asr-model-dir", type=Path, required=True)
    parser.add_argument("--vad-dir", type=Path)
    parser.add_argument("--llm-url", required=True)
    parser.add_argument("--phase", choices=("asr", "llm", "all"), default="all")
    parser.add_argument("--only", default="", help="Explicit ASR/LLM follow-up case IDs for the selected phase; never an automatic retry")
    parser.add_argument("--reference", type=Path, help="Completed speech-reference.json for an explicitly separate LLM follow-up output directory")
    parser.add_argument("--active-only", action="store_true", help="Only On x two repetitions for each of four cases: eight results, no Off baseline changes")
    args = parser.parse_args(argv)
    args.llm_url = loopback_url(args.llm_url)
    args.strata_source = args.strata_source.resolve()
    args.output = output_directory(args.output, args.strata_source)
    for phase in (("asr", "llm") if args.phase == "all" else (args.phase,)):
        if (args.output / f"{phase}-results.json").exists():
            raise ValueError("Acceptance evidence already exists; use a fresh --output and --reference for LLM follow-up")
    args.output.mkdir(parents=True, exist_ok=True)
    import requests
    session = requests.Session()
    session.trust_env = False

    def identity():
        response = session.get(args.llm_url + "/v1/status", timeout=10, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise AssertionError("LLM status must be HTTP 200 without redirect")
        value = response.json()
        if value.get("service") != "strata" or value.get("protocol_version") != 1:
            raise AssertionError("Selected LLM is not a verified Strata protocol-1 service")
        return service_identity(value)

    before = identity()
    manifest = {"user_service_before": before, "started_at": time.time(),
                "no_user_service_lifecycle_calls": True, "source_sha256": {p.name: sha256(p) for p in ROOT.glob("*.py")},
                "runner_sha256": sha256(Path(__file__)), "phase": args.phase, "active_only": args.active_only,
                "reference_sha256": sha256(args.reference) if args.reference else None,
                "interpretation": "Real native CPU ASR and real enhancer text only; human review and rendered-video acceptance are separate"}
    save(args.output / f"manifest-{args.phase}.json", manifest)
    modules = load_plugin()
    asr = run_asr(args, modules, session, identity) if args.phase in ("asr", "all") else None
    llm = run_llm(args, modules, session, identity) if args.phase in ("llm", "all") else None
    after = identity()
    assert_residency(before, after)
    manifest.update(user_service_after=after, completed_at=time.time(),
                    source_after_sha256={p.name: sha256(p) for p in ROOT.glob("*.py")},
                    asr_passed=sum(row["passed"] for row in asr["cases"]) if asr else None,
                    asr_total=len(asr["cases"]) if asr else None,
                    llm_passed=sum(row["passed"] for row in llm) if llm is not None else None,
                    llm_total=len(llm) if llm is not None else None)
    save(args.output / f"manifest-{args.phase}.json", manifest)
    print(json.dumps({key: manifest.get(key) for key in ("phase", "asr_passed", "asr_total", "llm_passed", "llm_total")}, ensure_ascii=False), flush=True)
    return 0 if (asr is None or all(row["passed"] for row in asr["cases"])) and (llm is None or all(row["passed"] for row in llm)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
