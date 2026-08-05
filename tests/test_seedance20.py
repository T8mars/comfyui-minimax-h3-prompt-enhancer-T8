import asyncio
import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = PROJECT_ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_prompt_enhancer_test_package",
    PROJECT_ROOT / "__init__.py",
    submodule_search_locations=[str(PROJECT_ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.headers = {}

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, completion="最终提示词", chat_status=200):
        self.completion = completion
        self.chat_status = chat_status
        self.uploads = []
        self.chat_requests = []
        self.chat_urls = []

    def post(self, url, **kwargs):
        if "files" in kwargs:
            filename, data, mime_type = kwargs["files"]["file"]
            self.uploads.append((filename, data, mime_type, url))
            return FakeResponse(200, {"url": f"https://assets.example/{filename}"})
        self.chat_requests.append(kwargs)
        self.chat_urls.append(url)
        if self.chat_status != 200:
            return FakeResponse(self.chat_status, {"error": {"message": "upstream failed"}})
        return FakeResponse(200, {
            "choices": [{"finish_reason": "stop", "message": {"content": self.completion}}]
        })

    def close(self):
        pass


class FakeVideo:
    def __init__(self, duration=3.0, data=b"complete-video", container="mp4"):
        self.duration = duration
        self.data = data
        self.container = container

    def get_stream_source(self):
        return io.BytesIO(self.data)

    def get_duration(self):
        return self.duration

    def get_container_format(self):
        return self.container


class Seedance20PromptEnhancerTests(unittest.TestCase):
    def run_enhancer(self, session=None, **kwargs):
        values = {
            "prompt": "一名舞者在雨夜完成一次连续旋转。",
            "api_key": "test-secret-key",
            "session": session or FakeSession(),
        }
        values.update(kwargs)
        return seedance20.enhance_seedance20_prompt(**values)

    def messages(self, session):
        return session.chat_requests[-1]["json"]["messages"]

    def test_package_registers_h3_and_seedance20_as_separate_nodes(self):
        async def registered_ids():
            extension = await package.comfy_entrypoint()
            return [node.define_schema().node_id for node in await extension.get_node_list()]

        self.assertEqual(
            asyncio.run(registered_ids()),
            ["MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8"],
        )

    def test_schema_has_seedance20_options_and_no_audio_port_or_h3_fields(self):
        schema = seedance20.Seedance20PromptEnhancer.define_schema()
        names = [item.id for item in schema.inputs]
        self.assertEqual(schema.node_id, "Seedance20PromptEnhancerT8")
        self.assertEqual(schema.category, "T8/Seedance 2.0")
        self.assertNotIn("audio", " ".join(names).lower())
        self.assertNotIn("description_word_target", names)
        self.assertNotIn("task_type", names)
        self.assertIn("task_intent", names)
        self.assertIn("complexity_mode", names)
        self.assertIn("reference_syntax", names)
        shot_count = next(item for item in schema.inputs if item.id == "shot_count")
        duration = next(item for item in schema.inputs if item.id == "duration_seconds")
        self.assertEqual(shot_count.options[1:], [str(value) for value in range(1, 21)])
        self.assertEqual(duration.options[1:], [str(value) for value in range(4, 16)])
        self.assertIn("rejected input_audio", schema.description)

    def test_official_prompt_uses_seedance20_rules_without_h3_contract(self):
        session = FakeSession("可直接使用的提示词")
        result = self.run_enhancer(session, task_intent="T2V", duration_seconds="8", shot_count="3")
        system = self.messages(session)[0]["content"]
        self.assertEqual(result, "可直接使用的提示词")
        self.assertIn("official Seedance 2.0", system)
        self.assertIn("fixed at exactly 3", system)
        self.assertIn("镜头1 through 镜头3", system)
        self.assertIn("Do not attach absolute seconds", system)
        self.assertNotIn("integrated_multimodal_description", system)
        self.assertNotIn("[Shot N] At MM:SS", system)
        self.assertNotIn("overall_soundscape:", system)

    def test_fixed_shot_count_overrides_approximate_user_count_without_timestamps(self):
        session = FakeSession()
        self.run_enhancer(
            session,
            prompt="大约十个镜头展现夜市",
            task_intent="T2V",
            complexity_mode="复杂分镜式",
            duration_seconds="12",
            shot_count="4",
        )
        combined = json.dumps(self.messages(session), ensure_ascii=False)
        self.assertIn("fixed at exactly 4", combined)
        self.assertIn("overrides an approximate count", combined)
        self.assertIn("12 seconds", combined)
        self.assertIn("without assigning absolute per-shot timestamps", combined)

    def test_shot_count_accepts_twenty_and_rejects_twenty_one(self):
        session = FakeSession()
        self.run_enhancer(session, task_intent="T2V", shot_count="20")
        self.assertIn("fixed at exactly 20", self.messages(session)[0]["content"])
        self.assertIn("镜头1 through 镜头20", self.messages(session)[0]["content"])
        with self.assertRaisesRegex(seedance20.Seedance20PromptEnhancerError, "from 1 to 20"):
            self.run_enhancer(FakeSession(), task_intent="T2V", shot_count="21")

    def test_reference_syntax_controls_labels_and_uploads_complete_video(self):
        image = torch.zeros((1, 16, 16, 3), dtype=torch.float32)
        session = FakeSession()
        self.run_enhancer(
            session,
            task_intent="MultiRef",
            reference_syntax=seedance20.REFERENCE_SYNTAXES[1],
            reference_images={"reference_image_0": image},
            reference_videos={"reference_video_0": FakeVideo(data=b"whole-stream")},
        )
        messages = self.messages(session)
        user_content = messages[1]["content"]
        self.assertEqual([part["type"] for part in user_content], ["text", "text", "image_url", "text", "video_url"])
        self.assertIn("@Image 1", user_content[0]["text"])
        self.assertIn("@Video 1", user_content[0]["text"])
        self.assertEqual(session.uploads[1][1], b"whole-stream")
        self.assertIn("complete action, cuts, camera", user_content[3]["text"])

    def test_official_chinese_syntax_uses_no_space_before_number(self):
        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        session = FakeSession()
        self.run_enhancer(
            session,
            task_intent="MultiRef",
            reference_images={"reference_image_0": image},
        )
        combined = json.dumps(self.messages(session), ensure_ascii=False)
        self.assertIn("@图片1", combined)
        self.assertNotIn("@Image 1 (reference image)", combined)

    def test_task_media_validation_matrix(self):
        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        cases = [
            ({"task_intent": "T2V", "first_frame": image}, "T2V does not accept media"),
            ({"task_intent": "I2V"}, "I2V requires only first_frame"),
            ({"task_intent": "FL-I2V", "first_frame": image}, "FL-I2V requires first_frame and last_frame only"),
            ({"task_intent": "MultiRef"}, "MultiRef requires at least one image or video"),
            ({"task_intent": "VideoEdit"}, "VideoEdit requires at least one reference video"),
            ({"task_intent": "VideoExtend", "reference_videos": {"reference_video_0": FakeVideo(), "reference_video_1": FakeVideo()}}, "exactly one"),
            ({"task_intent": "TrackFill", "reference_videos": {"reference_video_0": FakeVideo()}}, "2 or 3"),
            ({"task_intent": "Combined", "reference_videos": {"reference_video_0": FakeVideo()}}, "at least one other"),
        ]
        for values, message in cases:
            with self.subTest(values=values), self.assertRaisesRegex(seedance20.Seedance20PromptEnhancerError, message):
                self.run_enhancer(FakeSession(), **values)

    def test_video_edit_and_extend_use_direct_video_references(self):
        for task in ("VideoEdit", "VideoExtend"):
            session = FakeSession()
            self.run_enhancer(
                session,
                task_intent=task,
                reference_videos={"reference_video_0": FakeVideo()},
            )
            system = self.messages(session)[0]["content"]
            self.assertIn("directly", system)
            self.assertIn("@视频1", system)
            self.assertIn("never call it a reference", system)
            self.assertIn("source video to", self.messages(session)[1]["content"][0]["text"])

    def test_template_fusion_is_required_then_included_as_inspiration_only(self):
        with self.assertRaisesRegex(seedance20.Seedance20PromptEnhancerError, "reference_template is required"):
            self.run_enhancer(FakeSession(), prompt_mode="参考模板融合")
        session = FakeSession()
        self.run_enhancer(
            session,
            prompt_mode="参考模板融合",
            reference_template="镜头1先静后动；镜头2快速甩镜。",
        )
        combined = json.dumps(self.messages(session), ensure_ascii=False)
        self.assertIn("Synthesize rather than copy", combined)
        self.assertIn("镜头1先静后动", combined)
        self.assertIn("structure/style inspiration only", combined)

    def test_length_target_is_soft_and_arbitrary_nonempty_output_passes_through(self):
        upstream = "上游没有按任何固定格式返回，但内容非空，应原样放行。"
        session = FakeSession(upstream)
        self.assertEqual(self.run_enhancer(session, custom_length_target=350), upstream)
        combined = json.dumps(self.messages(session), ensure_ascii=False)
        self.assertIn("approximately 350 Chinese characters", combined)
        self.assertIn("upstream response does not match", combined)

    def test_no_audio_claim_and_textual_audio_reference_is_preserved(self):
        session = FakeSession()
        self.run_enhancer(session, prompt="让环境音参考文字标记 @音频1，但不上传音频")
        combined = json.dumps(self.messages(session), ensure_ascii=False)
        self.assertIn("No audio attachment is provided", combined)
        self.assertIn("never claim to have heard or analyzed", combined)
        self.assertIn("@音频1", combined)

    def test_openai_compatible_chat_and_media_upload_urls(self):
        session = FakeSession()
        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        self.run_enhancer(
            session,
            task_intent="MultiRef",
            reference_images={"reference_image_0": image},
            api_mode=seedance20.OPENAI_API_MODE,
            openai_base_url="https://provider.example/v1",
            openai_upload_url="https://uploads.example/files",
        )
        self.assertEqual(session.chat_urls, ["https://provider.example/v1/chat/completions"])
        self.assertEqual(session.uploads[0][3], "https://uploads.example/files")

    def test_api_key_like_text_is_rejected_without_leaking_secret(self):
        fake_secret = "sk-" + "x" * 24
        with self.assertRaises(seedance20.Seedance20PromptEnhancerError) as captured:
            self.run_enhancer(FakeSession(), prompt=f"画面中出现 {fake_secret}")
        self.assertNotIn(fake_secret, str(captured.exception))

    def test_frontend_has_secure_key_run_modes_and_responsive_dom_widget(self):
        source = (PROJECT_ROOT / "web" / "js" / "seedance20_prompt_enhancer.js").read_text(encoding="utf-8")
        for snippet in (
            'const NODE_ID = "Seedance20PromptEnhancerT8"',
            'input.type = "password"',
            "💾 保存到工作流",
            'clear.textContent = "清空"',
            "▶ 运行 Seedance 2.0 提示词优化",
            "app.queuePrompt(0, 1, [String(this.id)])",
            "https://api.seedance.nz/sign-up?aff=5f4w",
            'value === "参考模板融合"',
            'mode === OPENAI_API_MODE',
            "delete secureWidget.width",
            'find("custom_length_target")',
            '"control_after_generate"',
        ):
            self.assertIn(snippet, source)

    def test_example_workflow_is_importable_and_contains_no_api_key(self):
        path = PROJECT_ROOT / "example" / "seedance20_prompt_enhancer_example.json"
        workflow = json.loads(path.read_text(encoding="utf-8"))
        node = next(item for item in workflow["nodes"] if item["type"] == "Seedance20PromptEnhancerT8")
        self.assertEqual(node["type"], "Seedance20PromptEnhancerT8")
        self.assertEqual(len(node["widgets_values"]), 23)
        self.assertEqual(node["widgets_values"][1], seedance20.TASK_INTENT_LABELS["AUTO"])
        self.assertEqual(node["widgets_values"][18], seedance20.SEEDANCE_API_MODE)
        self.assertNotIn("sk-", path.read_text(encoding="utf-8"))

    def test_real_paid_smoke_fixture_passes_seedance20_temporal_evaluation(self):
        smoke_spec = importlib.util.spec_from_file_location(
            "seedance20_live_smoke_test_module",
            PROJECT_ROOT / "seedance20_live_smoke.py",
        )
        smoke = importlib.util.module_from_spec(smoke_spec)
        smoke_spec.loader.exec_module(smoke)
        output = (PROJECT_ROOT / "tests" / "fixtures" / "seedance20_paid_smoke_output_2026-08-05.txt").read_text(encoding="utf-8")
        self.assertEqual(smoke.evaluate_result(output), [])
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            smoke.run_paid_smoke(False)


if __name__ == "__main__":
    unittest.main()
