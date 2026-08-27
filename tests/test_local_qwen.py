import importlib.util
import hashlib
import inspect
import io
import json
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = PROJECT_ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_local_qwen_test_package",
    PROJECT_ROOT / "__init__.py",
    submodule_search_locations=[str(PROJECT_ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
nodes = sys.modules[f"{SPEC.name}.nodes"]
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]
music3 = sys.modules[f"{SPEC.name}.music3"]
media = sys.modules[f"{SPEC.name}.local_qwen_media"]
provider = sys.modules[f"{SPEC.name}.local_qwen_provider"]
runtime = sys.modules[f"{SPEC.name}.local_qwen_runtime"]
catalog = sys.modules[f"{SPEC.name}.local_gguf_catalog"]
shared_config = sys.modules[f"{SPEC.name}.provider_config"]
INSTALLER_SPEC = importlib.util.spec_from_file_location("t8_local_qwen_installer_test", PROJECT_ROOT / "install_local_qwen.py")
installer = importlib.util.module_from_spec(INSTALLER_SPEC)
sys.modules[INSTALLER_SPEC.name] = installer
INSTALLER_SPEC.loader.exec_module(installer)


class NativeVideo:
    def __init__(self, data: bytes, duration: float, trim=(0.0, 0.0)):
        self.data = data
        self.duration = duration
        self.trim = trim

    def get_duration(self):
        return self.duration

    def get_active_trim_window(self):
        return self.trim

    def get_stream_source(self):
        return io.BytesIO(self.data)

    def get_container_format(self):
        return "mp4"


def encoded_video_bytes(frame_count=24, fps=24):
    import av

    destination = io.BytesIO()
    with av.open(destination, mode="w", format="mp4") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width = 64
        stream.height = 48
        stream.pix_fmt = "yuv420p"
        for index in range(frame_count):
            image = np.zeros((48, 64, 3), dtype=np.uint8)
            image[:, :, index % 3] = min(255, 20 + index * 8)
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return destination.getvalue()


class FakeLocalProvider:
    instances = []
    response = ""

    def __init__(self, settings, *, vision):
        self.settings = settings
        self.vision = vision
        self.messages = []
        self.closed = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(force=exc_type is not None)

    def complete(self, messages, **_kwargs):
        self.messages.append(messages)
        if callable(self.__class__.response):
            return self.__class__.response(messages)
        return self.__class__.response

    def close(self, *, force=False):
        self.closed.append(force)


class LocalQwenUnitTests(unittest.TestCase):
    def setUp(self):
        FakeLocalProvider.instances.clear()
        music3.clear_music3_stage_cache()

    def test_settings_and_seed_contract(self):
        settings = provider.settings_from_values(local_context_size=32768, local_max_tokens=4096)
        self.assertEqual(settings.context_size, 32768)
        self.assertEqual(runtime.normalize_llama_seed(0xFFFFFFFF), 0)
        self.assertEqual(runtime.normalize_llama_seed(0x100000001), 2)
        with self.assertRaises(provider.LocalQwenProviderError):
            provider.settings_from_values(local_context_size=8192, local_max_tokens=8192)
        with self.assertRaises(runtime.LocalQwenRuntimeError):
            runtime.resolve_model_path("../escape.gguf", label="model", required=False)

    def test_legacy_local_mode_remains_executable_after_generic_label_upgrade(self):
        key, chat_url, upload_url, provider_name = nodes._provider_config(
            provider.LEGACY_LOCAL_QWEN_API_MODE,
            "",
            "",
        )
        self.assertEqual((key, chat_url, upload_url), ("", "", ""))
        self.assertIn("llama.cpp", provider_name)
        self.assertNotEqual(provider.LOCAL_QWEN_API_MODE, provider.LEGACY_LOCAL_QWEN_API_MODE)

    def test_stale_local_catalog_values_do_not_block_cloud_workflows(self):
        cases = (
            (
                nodes.MiniMaxH3PromptEnhancer,
                ("local_model", "local_mmproj", "reference_images", "reference_videos"),
            ),
            (
                seedance20.Seedance20PromptEnhancer,
                ("local_model", "local_mmproj", "reference_images", "reference_videos"),
            ),
            (music3.MiniMaxMusic3PromptEnhancer, ("local_model",)),
            (shared_config.T8LLMProviderConfig, ("local_model", "local_mmproj")),
        )
        for node_class, names in cases:
            with self.subTest(node=node_class.__name__):
                parameters = inspect.signature(node_class.validate_inputs).parameters
                self.assertEqual(tuple(parameters)[: len(names)], names)
                stale = {name: f"missing/{name}.gguf" for name in names}
                if "reference_images" in stale:
                    self.assertEqual(parameters["extra_inputs"].kind, inspect.Parameter.VAR_KEYWORD)
                    stale["reference_images"] = {"reference_image_0": object()}
                    stale["reference_videos"] = {"reference_video_0": object()}
                    self.assertTrue(
                        node_class.validate_inputs(
                            **stale,
                            future_reference_group={"reference_image_99": object()},
                        )
                    )
                else:
                    self.assertEqual(tuple(parameters), names)
                    self.assertTrue(node_class.validate_inputs(**stale))

    def test_runtime_auto_falls_back_to_existing_llama_cpp_python(self):
        python_spec = runtime.PythonRuntimeSpec(version="test-version")
        with (
            patch.object(runtime, "RUNTIME_CONFIG_PATH", PROJECT_ROOT / "missing-runtime.json"),
            patch.object(runtime, "_path_runtime_spec", return_value=None),
            patch.object(runtime, "load_python_runtime_spec", return_value=python_spec),
        ):
            specs, warnings = runtime.available_runtime_specs()
            selected = runtime.select_runtime_spec()
        self.assertEqual(specs, [python_spec])
        self.assertEqual(warnings, [])
        self.assertEqual(selected.backend, "llama-cpp-python")

    def test_recursive_catalog_reads_metadata_and_auto_pairs_projector(self):
        def gguf_string(value):
            encoded = value.encode("utf-8")
            return struct.pack("<Q", len(encoded)) + encoded

        def write_gguf(path, metadata):
            payload = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, len(metadata)))
            for key, value in metadata.items():
                payload.extend(gguf_string(key))
                if isinstance(value, bool):
                    payload.extend(struct.pack("<I?", 7, value))
                elif isinstance(value, int):
                    payload.extend(struct.pack("<IQ", 10, value))
                else:
                    payload.extend(struct.pack("<I", 8))
                    payload.extend(gguf_string(str(value)))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            model_path = root / "Qwen3" / "Qwen3-4B-Q4_K_M.gguf"
            projector_path = root / "Qwen3" / "mmproj-Qwen3-4B-F16.gguf"
            write_gguf(
                model_path,
                {
                    "general.architecture": "qwen3vl",
                    "general.type": "model",
                    "general.name": "Qwen3 4B",
                    "qwen3vl.context_length": 32768,
                    "tokenizer.chat_template": "{{ messages }}",
                },
            )
            write_gguf(
                projector_path,
                {
                    "general.architecture": "clip",
                    "general.type": "mmproj",
                    "general.name": "Qwen3 4B",
                    "clip.projector_type": "qwen3vl_merger",
                    "clip.has_vision_encoder": True,
                },
            )
            with (
                patch.object(catalog, "_registered_model_roots", return_value=(root,)),
                patch.object(catalog, "llm_model_directory", return_value=root),
                patch.object(catalog, "legacy_qwen_model_directory", return_value=root / "Qwen3.8"),
            ):
                catalog._CATALOG_CACHE = None
                payload = catalog.catalog_public_payload(refresh=True)
                model = payload["models"][0]
                resolved = catalog.resolve_gguf_path(model["identifier"], label="model")
                projector = catalog.resolve_projector_path(
                    catalog.AUTO_MMPROJ,
                    model_identifier=model["identifier"],
                )
            catalog._CATALOG_CACHE = None
        self.assertEqual(model["architecture"], "qwen3vl")
        self.assertTrue(model["has_chat_template"])
        self.assertEqual(model["recommended_projector"], "Qwen3/mmproj-Qwen3-4B-F16.gguf")
        self.assertEqual(resolved, model_path)
        self.assertEqual(projector, projector_path)

    def test_thinking_payload_uses_qwen_official_sampling_contract(self):
        class RunningProcess:
            @staticmethod
            def poll():
                return None

        server = object.__new__(runtime.LlamaServer)
        server.process = RunningProcess()
        captured = {}

        def fake_chat(payload):
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        server._chat_sync = fake_chat
        content, _usage = server.chat(
            [{"role": "user", "content": "test"}],
            seed=1,
            max_tokens=256,
            temperature=0.2,
            think_mode=True,
            reasoning_effort="xhigh",
        )
        self.assertEqual(content, "ok")
        self.assertEqual(captured["temperature"], 1.0)
        self.assertEqual(captured["presence_penalty"], 0.0)
        self.assertEqual(captured["repeat_penalty"], 1.0)
        self.assertEqual(captured["reasoning_effort"], "xhigh")

    def test_nonthinking_server_starts_reasoning_off_and_removes_leaked_trace(self):
        spec = runtime.RuntimeSpec(
            executable=PROJECT_ROOT / "fake-llama-server",
            library_dirs=(),
            backend="test",
            fit=False,
        )
        server = object.__new__(runtime.LlamaServer)
        server.spec = spec
        server.model = PROJECT_ROOT / "fake-model.gguf"
        server.mmproj = None
        server.context_size = 32768
        server.think_mode = False
        server.token = "test-token"
        server.port = 12345
        with patch.object(runtime, "_supports_server_reasoning_switch", return_value=True):
            arguments = server._start_arguments()
        reasoning_index = arguments.index("--reasoning")
        self.assertEqual(arguments[reasoning_index + 1], "off")

        class RunningProcess:
            @staticmethod
            def poll():
                return None

        server.process = RunningProcess()
        captured = {}

        def fake_chat(payload):
            captured.update(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "reasoning_content": "private server-side reasoning",
                            "content": "<think>private inline reasoning</think>\n\n最终提示词",
                        }
                    }
                ]
            }

        server._chat_sync = fake_chat
        content, _usage = server.chat(
            [{"role": "user", "content": "test"}],
            seed=1,
            max_tokens=256,
            temperature=0.2,
            think_mode=False,
            reasoning_effort="medium",
        )
        self.assertEqual(content, "最终提示词")
        self.assertNotIn("reasoning", content)
        self.assertFalse(captured["chat_template_kwargs"]["enable_thinking"])
        self.assertFalse(captured["chat_template_kwargs"]["preserve_thinking"])

    def test_thinking_output_is_preserved_only_when_explicitly_enabled(self):
        value = "<think>private trace</think>\n\nfinal answer"
        self.assertEqual(
            runtime._finalize_local_content(value, think_mode=True),
            value,
        )
        self.assertEqual(
            runtime._finalize_local_content("</think>\nfinal answer", think_mode=False),
            "final answer",
        )
        self.assertEqual(runtime.LOCAL_REASONING_OPTIONS, ["low", "medium", "xhigh"])

    def test_projector_auto_match_rejects_parameter_scale_mismatch(self):
        model = catalog.GGUFModelInfo(
            identifier="Qwen3.8/new-9b.gguf",
            path=str(PROJECT_ROOT / "Qwen3.8" / "new-9b.gguf"),
            filename="Qwen3.8-9B-heretic-Q6_K.gguf",
            size=1,
            architecture="qwen35",
            name="Qwen3.8 9B Heretic",
            metadata_readable=True,
        )
        wrong = catalog.GGUFModelInfo(
            identifier="Qwen3.8/mmproj-27b.gguf",
            path=str(PROJECT_ROOT / "Qwen3.8" / "mmproj-27b.gguf"),
            filename="mmproj-Qwen3.8-27B-F16.gguf",
            size=1,
            architecture="clip",
            model_type="mmproj",
            name="Qwen3.8 27B",
            projector_type="qwen3vl_merger",
            has_vision_encoder=True,
            metadata_readable=True,
        )
        correct = catalog.GGUFModelInfo(
            identifier="mmproj-Qwen3.5-9B-BF16.gguf",
            path=str(PROJECT_ROOT / "mmproj-Qwen3.5-9B-BF16.gguf"),
            filename="mmproj-Qwen3.5-9B-BF16.gguf",
            size=1,
            architecture="clip",
            model_type="mmproj",
            name="Qwen3.5 9B",
            projector_type="qwen3vl_merger",
            has_vision_encoder=True,
            metadata_readable=True,
        )
        with (
            patch.object(catalog, "model_info_for", return_value=model),
            patch.object(catalog, "scan_gguf_catalog", return_value=(model, wrong, correct)),
        ):
            selected = catalog.recommended_projector(model.identifier)
        self.assertEqual(selected, correct)

    def test_local_http_error_hides_response_and_token(self):
        class Response:
            status_code = 500
            text = "private prompt, lyric and bearer-token"

        server = object.__new__(runtime.LlamaServer)
        server.port = 1
        server.token = "bearer-token"
        with patch.object(runtime.requests, "post", return_value=Response()):
            with self.assertRaises(runtime.LocalQwenRuntimeError) as raised:
                server._chat_sync({"messages": [{"role": "user", "content": "private prompt"}]})
        message = str(raised.exception)
        self.assertIn("HTTP 500", message)
        self.assertNotIn("private prompt", message)
        self.assertNotIn("bearer-token", message)

    def test_local_chat_cancellation_stops_server(self):
        class RunningProcess:
            @staticmethod
            def poll():
                return None

        server = object.__new__(runtime.LlamaServer)
        server.process = RunningProcess()
        stopped = threading.Event()

        def blocking_chat(_payload):
            stopped.wait(2)
            return {"choices": [{"message": {"content": "late"}}]}

        server._chat_sync = blocking_chat
        with patch.object(server, "stop", side_effect=stopped.set) as stop:
            with patch.object(runtime, "_throw_if_interrupted", side_effect=RuntimeError("cancelled")):
                with self.assertRaisesRegex(RuntimeError, "cancelled"):
                    server.chat(
                        [{"role": "user", "content": "cancel me"}],
                        seed=1,
                        max_tokens=256,
                        temperature=0.2,
                        think_mode=False,
                        reasoning_effort="medium",
                    )
        stop.assert_called_once()
        self.assertTrue(stopped.is_set())

    def test_image_parts_are_base64_and_token_accounting_includes_visuals(self):
        image = np.zeros((1, 32, 48, 3), dtype=np.float32)
        parts = media.image_part(image, "reference_image_0")
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        tokens = media.estimate_message_tokens([{"role": "user", "content": parts}])
        self.assertGreaterEqual(tokens, 1024)

    def test_cjk_token_estimate_is_conservative(self):
        cjk = "中文提示词" * 100
        tokens = media.estimate_message_tokens([{"role": "user", "content": cjk}])
        self.assertGreaterEqual(tokens, len(cjk) + 256)

    def test_zero_visual_budget_rejects_connected_media(self):
        settings = provider.settings_from_values()
        image = np.zeros((1, 32, 48, 3), dtype=np.float32)
        with self.assertRaises(provider.LocalQwenProviderError):
            provider.build_local_multimodal_parts(
                [{"kind": "image", "label": "reference_image_0", "value": image}],
                settings,
                max_visual_parts=0,
            )

    def test_video_sampling_uses_real_timestamps_and_contact_sheets(self):
        data = encoded_video_bytes(frame_count=48, fps=24)
        video = NativeVideo(data, duration=2.0, trim=(0.25, 1.0))
        frames, duration = media.sample_video(video, 2.0)
        self.assertAlmostEqual(duration, 1.0, places=3)
        self.assertEqual(len(frames), 2)
        self.assertLessEqual(frames[0].timestamp, frames[-1].timestamp)
        parts, report = media.build_local_media_parts(
            [{"kind": "video", "label": "reference_video_0", "value": video}],
            video_sample_fps=2.0,
        )
        self.assertEqual(report["video_count"], 1)
        self.assertFalse(report["audio_analyzed"])
        self.assertTrue(any(part.get("type") == "image_url" for part in parts))
        self.assertIn("no audio was analyzed", json.dumps(parts))
        self.assertIn("observation ledger sorted by the printed timestamps", json.dumps(parts))
        self.assertIn("first-appearance timestamp order", json.dumps(parts))

    def test_high_rate_frames_are_uniformly_reduced_without_dropping_the_end(self):
        data = encoded_video_bytes(frame_count=48, fps=24)
        video = NativeVideo(data, duration=2.0)
        frames, _duration = media.sample_video(video, 8.0)
        reduced = media._uniform_samples(frames, 9)
        self.assertEqual(len(reduced), 9)
        self.assertEqual(reduced[-1].timestamp, frames[-1].timestamp)
        _parts, report = media.build_local_media_parts(
            [{"kind": "video", "label": "reference_video_0", "value": video}],
            video_sample_fps=8.0,
            max_visual_parts=1,
        )
        video_report = report["videos"][0]
        self.assertEqual(video_report["sent_frame_count"], 9)
        self.assertGreater(video_report["uniformly_reduced_frame_count"], 0)

    def test_h3_local_provider_needs_no_key_and_preserves_output_policy(self):
        FakeLocalProvider.response = (
            "integrated_multimodal_description: [Shot 1] 一名骑手穿过安静街道。\n\n"
            "overall_soundscape: 车轮与微风。\n\nnon_diegetic_music: N/A"
        )
        with patch.object(nodes, "LocalQwenProvider", FakeLocalProvider):
            result = nodes.enhance_prompt(
                "骑手穿过街道",
                api_mode=nodes.LOCAL_QWEN_API_MODE,
                api_key="",
            )
        self.assertTrue(result.startswith("integrated_multimodal_description:"))
        self.assertEqual(len(FakeLocalProvider.instances), 1)
        self.assertFalse(FakeLocalProvider.instances[0].vision)

    def test_seedance_local_provider_accepts_nonempty_content(self):
        FakeLocalProvider.response = "镜头从静止全景缓慢推进，主体抬头后沿光线方向前行。"
        with patch.object(seedance20, "LocalQwenProvider", FakeLocalProvider):
            result = seedance20.enhance_seedance20_prompt(
                "主体沿光线前行",
                api_mode=seedance20.LOCAL_QWEN_API_MODE,
                api_key="",
            )
        self.assertIn("主体", result)
        self.assertFalse(FakeLocalProvider.instances[0].vision)

    def test_trimmed_native_video_is_allowed_only_for_local_sampling(self):
        data = encoded_video_bytes(frame_count=96, fps=24)
        video = NativeVideo(data, duration=4.0, trim=(0.5, 2.0))
        FakeLocalProvider.response = (
            "integrated_multimodal_description: [Shot 1] visible sampled sequence.\n\n"
            "overall_soundscape: N/A\n\nnon_diegetic_music: N/A"
        )
        with patch.object(nodes, "LocalQwenProvider", FakeLocalProvider):
            h3_result = nodes.enhance_prompt(
                "Use the trimmed sequence",
                task_type="Ref2VA",
                reference_videos={"reference_video_0": video},
                api_mode=nodes.LOCAL_QWEN_API_MODE,
            )
        self.assertIn("sampled sequence", h3_result)
        with self.assertRaises(nodes.PromptEnhancerError):
            nodes.enhance_prompt(
                "Use the trimmed sequence",
                task_type="Ref2VA",
                reference_videos={"reference_video_0": video},
                api_mode=nodes.SEEDANCE_API_MODE,
                api_key="placeholder-not-a-live-secret",
            )

        FakeLocalProvider.response = "镜头1：按裁剪窗口中的可见顺序推进。"
        with patch.object(seedance20, "LocalQwenProvider", FakeLocalProvider):
            seedance_result = seedance20.enhance_seedance20_prompt(
                "Use the trimmed sequence",
                task_intent="MultiRef",
                reference_videos={"reference_video_0": video},
                api_mode=seedance20.LOCAL_QWEN_API_MODE,
            )
        self.assertIn("裁剪窗口", seedance_result)
        seedance_system = FakeLocalProvider.instances[-1].messages[0][0]["content"]
        self.assertIn("Sort observations by printed timestamp before drafting", seedance_system)
        self.assertIn("do not mention a later-phase identifier", seedance_system)

    def test_music_local_provider_is_text_only_and_reused_for_caption(self):
        caption = (
            "### Global Metadata\nWarm Mandarin pop ballad with a restrained-to-open arc.\n\n"
            "### Vocal Details\nA clear lead vocal in Mandarin grows toward the chorus.\n\n"
            "### Arrangement\n[Verse] piano and guitar remain intimate. [Chorus] drums widen the frame."
        )
        FakeLocalProvider.response = caption
        fake_model = SimpleNamespace(
            stat=lambda: SimpleNamespace(st_size=1, st_mtime_ns=1),
        )
        with (
            patch.object(music3, "LocalQwenProvider", FakeLocalProvider),
            patch.object(music3, "resolve_model_path", return_value=fake_model),
        ):
            lyrics, output_caption, payload, report = music3.enhance_music3_prompt(
                "温暖的中文公路民谣",
                lyrics_mode=music3.PRESERVE_LYRICS_MODE,
                lyrics="[Verse]\n沿着微光继续走",
                lyrics_language="中文",
                quality_mode=music3.FAST_QUALITY_MODE,
                api_mode=music3.LOCAL_QWEN_API_MODE,
                api_key="",
            )
        self.assertEqual(lyrics, "[Verse]\n沿着微光继续走")
        self.assertEqual(output_caption, caption)
        self.assertEqual(json.loads(payload)["instructions"], caption)
        report_data = json.loads(report)
        self.assertEqual(report_data["request_count"], 1)
        self.assertEqual(report_data["stages"][0]["source"], "local_model")
        self.assertEqual(len(FakeLocalProvider.instances), 1)
        self.assertFalse(FakeLocalProvider.instances[0].vision)

    def test_local_options_are_in_all_three_schemas_and_frontends(self):
        self.assertIn(nodes.LOCAL_QWEN_API_MODE, nodes.API_MODES)
        self.assertIn(seedance20.LOCAL_QWEN_API_MODE, seedance20.API_MODES)
        self.assertIn(music3.LOCAL_QWEN_API_MODE, music3.MUSIC_API_MODES)
        for filename in (
            "minimax_h3_prompt_enhancer.js",
            "seedance20_prompt_enhancer.js",
            "music3_prompt_enhancer.js",
        ):
            source = (PROJECT_ROOT / "web" / "js" / filename).read_text(encoding="utf-8")
            self.assertIn("本地 Qwen3.8-27B", source)
            self.assertIn("本地 GGUF（llama.cpp / Qwen，离线）", source)
            self.assertIn("检查本地 Qwen 安装", source)
            self.assertIn("获取 llama-cpp-python 预编译 Wheel", source)
            self.assertIn("ComfyUI/models/LLM", source)

        status_source = (PROJECT_ROOT / "web" / "js" / "local_qwen_status.js").read_text(encoding="utf-8")
        self.assertIn("llama-cpp-python", status_source)
        self.assertIn("https://github.com/JamePeng/llama-cpp-python/releases", status_source)
        self.assertIn("verification_tier", status_source)
        self.assertIn("projector_options", status_source)

        self.assertEqual(
            runtime.LLAMA_CPP_PYTHON_WHEELS_URL,
            "https://github.com/JamePeng/llama-cpp-python/releases",
        )

        music_source = (PROJECT_ROOT / "web" / "js" / "music3_prompt_enhancer.js").read_text(encoding="utf-8")
        self.assertIn("values.length === SERIALIZED_WIDGET_NAMES.length", music_source)
        self.assertIn("values.length !== PUBLISHED_V1_WIDGET_NAMES.length", music_source)

    def test_idle_ttl_callback_cannot_stop_an_active_run(self):
        class FakeServer:
            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        class FakeTimer:
            instance = None

            def __init__(self, _seconds, callback):
                self.callback = callback
                self.daemon = False
                self.cancelled = False
                self.__class__.instance = self

            def start(self):
                pass

            def cancel(self):
                self.cancelled = True

        manager = runtime.LocalQwenManager()
        server = FakeServer()
        manager._server = server
        with patch.object(runtime.threading, "Timer", FakeTimer):
            manager.finish(runtime.LOCAL_IDLE_TTL)
            manager._run_lock.acquire()
            try:
                FakeTimer.instance.callback()
            finally:
                manager._run_lock.release()
        self.assertFalse(server.stopped)
        manager.release()

    def test_installer_repairs_complete_partial_and_classifies_bad_files(self):
        good = b"verified-model-bytes"
        item = installer.Download("tiny.gguf", len(good), hashlib.sha256(good).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / item.filename
            partial = target.with_suffix(target.suffix + ".part")

            partial.write_bytes(good)
            self.assertTrue(installer._prepare_existing(item, target, offline=True))
            self.assertEqual(target.read_bytes(), good)
            self.assertFalse(partial.exists())

            target.write_bytes(b"x" * len(good))
            self.assertFalse(installer._prepare_existing(item, target, offline=False))
            self.assertFalse(target.exists())
            self.assertTrue(any(root.glob("tiny.gguf.invalid-*")))

            partial.write_bytes(b"y" * len(good))
            self.assertFalse(installer._prepare_existing(item, target, offline=False))
            self.assertFalse(partial.exists())
            self.assertTrue(any(root.glob("tiny.gguf.part.invalid-*")))

            partial.write_bytes(b"z" * (len(good) - 1))
            with self.assertRaises(RuntimeError):
                installer._download_with_resume(item, target, offline=True)

    def test_installer_exposes_all_pinned_model_variants(self):
        official = installer.model_files_for_variant(installer.MODEL_VARIANT_OFFICIAL)
        uncensored = installer.model_files_for_variant(installer.MODEL_VARIANT_UNCENSORED)
        heretic_9b = installer.model_files_for_variant(installer.MODEL_VARIANT_HERETIC_9B)
        combined = installer.model_files_for_variant(installer.MODEL_VARIANT_ALL)
        self.assertEqual(
            [item.filename for item in official],
            ["Qwen3.8-27B-Q4_K_M.gguf", "mmproj-F16.gguf"],
        )
        self.assertEqual(
            [item.filename for item in uncensored],
            ["qwen3.8-27b-uncensored-fp8-q4_k_m.gguf", "mmproj-F16.gguf"],
        )
        self.assertEqual(
            [item.filename for item in heretic_9b],
            ["Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf"],
        )
        self.assertEqual(len({item.filename for item in combined}), 4)
        alternate = uncensored[0]
        self.assertIn("theresa00l/Qwen3.8-27B-Uncensored-FP8-Q4_K_M-GGUF", alternate.url)
        self.assertIn("5bdf224e6f9b1e18c7598fea63e238e014ee8e3e", alternate.url)
        self.assertEqual(
            alternate.sha256,
            "66bb238d41de38b11dd406d932d8fb97433d529022cef60f2f422b9221cae743",
        )
        compact = heretic_9b[0]
        self.assertIn("mradermacher/Qwen3.8-9B-heretic-uncensored-i1-GGUF", compact.url)
        self.assertIn("e3ab55e2befeb35fcf5bfebd0874afcbb8372593", compact.url)
        self.assertEqual(compact.size, 7_359_260_416)
        self.assertEqual(
            compact.sha256,
            "dfedf8412ee4a7f1200916783d224ebedb87044784434b75f4068b4b5e25f780",
        )
        with self.assertRaises(ValueError):
            installer.model_files_for_variant("unknown")

    def test_runtime_status_accepts_uncensored_model_as_text_and_vision_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            alternate = root / runtime.UNCENSORED_MODEL_FILENAME
            projector = root / runtime.DEFAULT_MMPROJ_FILENAME
            alternate.write_bytes(b"model")
            projector.write_bytes(b"projector")
            known = {
                runtime.DEFAULT_MODEL_FILENAME: (999, "unused"),
                runtime.UNCENSORED_MODEL_FILENAME: (len(b"model"), "unused"),
            }
            fake_spec = runtime.RuntimeSpec(
                executable=PROJECT_ROOT / "fake-llama-server",
                library_dirs=(),
                backend="test",
            )
            with (
                patch.object(runtime, "qwen_model_directory", return_value=root),
                patch.object(runtime, "KNOWN_MODEL_FILES", known),
                patch.object(runtime, "DEFAULT_MMPROJ_SIZE", len(b"projector")),
                patch.object(runtime, "available_runtime_specs", return_value=([fake_spec], [])),
            ):
                status = runtime.runtime_status()
        self.assertFalse(status["model_installed"])
        self.assertTrue(status["uncensored_model_installed"])
        self.assertTrue(status["text_ready"])
        self.assertTrue(status["vision_ready"])
        self.assertEqual(
            status["available_verified_models"],
            [runtime.UNCENSORED_MODEL_FILENAME],
        )

    def test_runtime_status_recognizes_pinned_heretic_9b_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            compact = root / runtime.HERETIC_9B_MODEL_FILENAME
            compact.write_bytes(b"compact")
            known = {
                runtime.DEFAULT_MODEL_FILENAME: (999, "unused"),
                runtime.UNCENSORED_MODEL_FILENAME: (998, "unused"),
                runtime.HERETIC_9B_MODEL_FILENAME: (len(b"compact"), "unused"),
            }
            fake_spec = runtime.RuntimeSpec(
                executable=PROJECT_ROOT / "fake-llama-server",
                library_dirs=(),
                backend="test",
            )
            with (
                patch.object(runtime, "qwen_model_directory", return_value=root),
                patch.object(runtime, "KNOWN_MODEL_FILES", known),
                patch.object(runtime, "available_runtime_specs", return_value=([fake_spec], [])),
            ):
                status = runtime.runtime_status()
        self.assertTrue(status["heretic_9b_model_installed"])
        self.assertTrue(status["text_ready"])
        self.assertEqual(status["available_verified_models"], [runtime.HERETIC_9B_MODEL_FILENAME])

    def test_heretic_9b_live_compatibility_evidence_is_redacted_and_passing(self):
        path = PROJECT_ROOT / "tests" / "fixtures" / "local_qwen_heretic_9b_compatibility_2026-08-25.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["passed"])
        self.assertTrue(all(payload["checks"].values()))
        self.assertEqual(payload["model"]["filename"], runtime.HERETIC_9B_MODEL_FILENAME)
        self.assertEqual(payload["model"]["size"], runtime.HERETIC_9B_MODEL_SIZE)
        self.assertEqual(payload["model"]["sha256"], runtime.HERETIC_9B_MODEL_SHA256)
        self.assertNotIn("diagnostic_outputs", payload)
        self.assertNotIn("data:image", json.dumps(payload).casefold())


if __name__ == "__main__":
    unittest.main()
