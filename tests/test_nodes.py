import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import requests
import torch


COMFYUI_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(COMFYUI_ROOT))
NODES_PATH = Path(__file__).resolve().parents[1] / "nodes.py"
SPEC = importlib.util.spec_from_file_location("minimax_h3_prompt_enhancer_nodes", NODES_PATH)
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)

SMOKE_SPEC = importlib.util.spec_from_file_location("minimax_h3_prompt_enhancer_live_smoke", NODES_PATH.parent / "live_smoke.py")
live_smoke = importlib.util.module_from_spec(SMOKE_SPEC)
SMOKE_SPEC.loader.exec_module(live_smoke)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, completion, chat_status=200, chat_payload=None, chat_exception=None, upload_status=200):
        self.completion = completion
        self.chat_status = chat_status
        self.chat_payload = chat_payload
        self.chat_exception = chat_exception
        self.upload_status = upload_status
        self.uploads = []
        self.upload_urls = []
        self.chat_requests = []
        self.chat_urls = []
        self.closed = False

    def post(self, url, **kwargs):
        if "files" in kwargs:
            filename, data, mime_type = kwargs["files"]["file"]
            self.uploads.append((filename, data, mime_type, kwargs))
            self.upload_urls.append(url)
            if self.upload_status != 200:
                return FakeResponse(self.upload_status, {"error": {"message": "upload failed"}})
            return FakeResponse(200, {"url": f"https://assets.example/{filename}", "expires_in": 86400})

        if "json" in kwargs:
            self.chat_requests.append(kwargs)
            self.chat_urls.append(url)
            if self.chat_exception:
                raise self.chat_exception
            if self.chat_status != 200:
                return FakeResponse(self.chat_status, self.chat_payload or {"error": {"message": "chat failed"}})
            payload = self.chat_payload
            if payload is None:
                payload = {
                    "choices": [{
                        "finish_reason": "stop",
                        "message": {"content": self.completion},
                    }]
                }
            return FakeResponse(200, payload)

        raise AssertionError(f"Unexpected URL: {url}")

    def close(self):
        self.closed = True


class AnchorAwareH3Session(FakeSession):
    def __init__(self):
        super().__init__("")

    def post(self, url, **kwargs):
        if "json" in kwargs:
            system = kwargs["json"]["messages"][0]["content"]
            block = system.split("REQUIRED_MECHANISM_ANCHORS", 1)[1].split("SPARSE_INPUT", 1)[0]
            anchors = re.findall(r"^\d+\. (.+)$", block, re.MULTILINE)
            self.completion = (
                "integrated_multimodal_description: [Shot 1] "
                + "；".join(f"画面以可见事件实现{anchor}" for anchor in anchors)
                + "。\n\noverall_soundscape: 环境与动作声依次响应这些可见状态。"
                + "\n\nnon_diegetic_music: 克制配乐随因果推进后稳定收束。"
            )
        return super().post(url, **kwargs)


class SequencedChatSession(FakeSession):
    def __init__(self, outcomes):
        super().__init__("")
        self.outcomes = list(outcomes)

    def post(self, url, **kwargs):
        if "json" not in kwargs:
            return super().post(url, **kwargs)
        self.chat_requests.append(kwargs)
        self.chat_urls.append(url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeVideo:
    def __init__(self, data=b"complete-video-stream", duration=3.0, container="mp4"):
        self.data = data
        self.duration = duration
        self.container = container

    def get_stream_source(self):
        return io.BytesIO(self.data)

    def get_duration(self):
        return self.duration

    def get_container_format(self):
        return self.container


def basic_output(task_type="T2VA", duration=5, shots=1):
    description = "[Shot 1] A medium shot shows a cyclist crossing a quiet street under soft daylight."
    if shots > 1:
        description += " [Shot 2] At 00:03.000, the camera cuts to the bicycle wheels rolling over wet pavement."
    fields = (
        f"integrated_multimodal_description: {description}\n\n"
        "overall_soundscape: Light traffic and bicycle-chain sounds continue beneath distant birds.\n\n"
        "non_diegetic_music: N/A"
    )
    if task_type == "T2VA":
        return fields
    if task_type == "I2VA":
        return f"{nodes.I2VA_INSTRUCTION}\n\n{fields}"
    if task_type == "FL2VA":
        return (
            "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with "
            f"the 0.00-second mark of the target video; Picture 2 (from Shot {shots}) aligns with "
            f"the {duration:.2f}-second mark of the target video.\n\n{fields}"
        )
    if task_type == "L2VA":
        return (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot {shots}]) aligns with the {duration:.2f}-second mark of the target video.\n\n{fields}"
        )
    raise AssertionError(task_type)


def basic_output_with_word_count(words=180):
    description = "[Shot 1] " + " ".join("detail" for _ in range(words - 2))
    return (
        f"integrated_multimodal_description: {description}\n\n"
        "overall_soundscape: Quiet room tone.\n\n"
        "non_diegetic_music: N/A"
    )


def reference_output(include_video=True):
    video_definition = "\n<Video 1> supplies the source action order and cut rhythm." if include_video else ""
    video_retention = "\n<Video 1> (action and cut structure): weak_reference - its temporal order guides the target sequence." if include_video else ""
    return (
        "subject_definitions:\n"
        "<Picture 1> is the visual identity and composition reference for <Subject 1>."
        f"{video_definition}\n\n"
        "summary:\n"
        "[reference generation] The target video uses <Picture 1> for the subject and follows the referenced motion structure.\n\n"
        "retention_analysis:\n"
        "<Picture 1> ([Shot 1] identity reference): fully_preserved - the observable subject and composition are retained."
        f"{video_retention}\n\n"
        "detailed_description:\n"
        "The target video uses a natural cinematic style with soft daylight.\n"
        "[Shot 1] <Subject 1> appears in the composition established by <Picture 1> and performs the referenced action smoothly.\n\n"
        "overall_soundscape:\n"
        "Quiet environmental ambience and soft movement sounds continue throughout.\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )


class PromptEnhancerTests(unittest.TestCase):
    def run_enhancer(self, session, **kwargs):
        defaults = {
            "prompt": "A cyclist crosses the street.",
            "task_type": "T2VA",
            "duration_seconds": 5,
            "rewrite_mode": "balanced",
            "description_word_target": 0,
            "session": session,
        }
        defaults.update(kwargs)
        with patch.dict(os.environ, {"SEEDANCE_API_KEY": "secret-key"}):
            return nodes.enhance_prompt(**defaults)

    def test_schema_has_one_model_free_string_output_and_native_autogrow_media(self):
        schema = nodes.MiniMaxH3PromptEnhancer.define_schema()
        input_names = [item.id for item in schema.inputs]
        self.assertEqual(schema.node_id, "MiniMaxH3PromptEnhancerT8")
        self.assertNotIn("model", input_names)
        self.assertIn("api_key", input_names)
        self.assertIn("output_language", input_names)
        self.assertIn("prompt_mode", input_names)
        self.assertIn("official_skill_profile", input_names)
        self.assertIn("creative_preset", input_names)
        self.assertIn("case_template", input_names)
        self.assertIn("reference_template", input_names)
        self.assertIn("api_mode", input_names)
        self.assertIn("ai_workshop_model", input_names)
        self.assertIn("custom_model", input_names)
        self.assertIn("openai_base_url", input_names)
        self.assertIn("openai_video_urls", input_names)
        self.assertNotIn("openai_upload_url", input_names)
        self.assertIn("seed", input_names)
        self.assertIn("shot_count", input_names)
        self.assertLess(input_names.index("api_key"), input_names.index("output_language"))
        self.assertEqual([output.display_name for output in schema.outputs], ["enhanced_prompt"])
        images = next(item for item in schema.inputs if item.id == "reference_images")
        videos = next(item for item in schema.inputs if item.id == "reference_videos")
        api_key = next(item for item in schema.inputs if item.id == "api_key")
        reference_context = next(item for item in schema.inputs if item.id == "reference_context")
        constraints = next(item for item in schema.inputs if item.id == "constraints")
        output_language = next(item for item in schema.inputs if item.id == "output_language")
        prompt_mode = next(item for item in schema.inputs if item.id == "prompt_mode")
        official_skill_profile = next(item for item in schema.inputs if item.id == "official_skill_profile")
        creative_preset = next(item for item in schema.inputs if item.id == "creative_preset")
        case_template = next(item for item in schema.inputs if item.id == "case_template")
        task_type = next(item for item in schema.inputs if item.id == "task_type")
        api_mode = next(item for item in schema.inputs if item.id == "api_mode")
        ai_workshop_model = next(item for item in schema.inputs if item.id == "ai_workshop_model")
        seed = next(item for item in schema.inputs if item.id == "seed")
        shot_count = next(item for item in schema.inputs if item.id == "shot_count")
        self.assertEqual((images.template.min, images.template.max), (0, 9))
        self.assertEqual((videos.template.min, videos.template.max), (0, 3))
        self.assertTrue(api_key.force_input)
        self.assertIsNone(api_key.socketless)
        self.assertTrue(reference_context.advanced)
        self.assertTrue(constraints.advanced)
        self.assertEqual(output_language.default, "中文")
        self.assertEqual(prompt_mode.default, "官方增强")
        self.assertEqual(official_skill_profile.default, nodes.COMPAT_SKILL_PROFILE)
        self.assertEqual(official_skill_profile.options, nodes.OFFICIAL_SKILL_PROFILES)
        self.assertEqual(creative_preset.default, nodes.NO_CREATIVE_PRESET)
        self.assertEqual(creative_preset.options, nodes.CREATIVE_PRESET_OPTIONS)
        self.assertEqual(len(creative_preset.options), 10)
        self.assertEqual(creative_preset.display_name, "MiniMax 官方创意预设")
        self.assertEqual(case_template.default, nodes.NO_CASE_TEMPLATE)
        self.assertEqual(case_template.options, nodes.CASE_TEMPLATE_OPTIONS)
        self.assertEqual(len(case_template.options), 38)
        self.assertEqual(case_template.display_name, "T8 原创案例模板（非官方）")
        self.assertEqual(task_type.default, "T2VA（文生音视频）")
        self.assertEqual(task_type.options, list(nodes.TASK_TYPE_LABELS.values()))
        self.assertEqual(api_mode.default, nodes.SEEDANCE_API_MODE)
        self.assertEqual(api_mode.options, nodes.API_MODES)
        self.assertEqual(ai_workshop_model.default, nodes.AI_WORKSHOP_DEFAULT_MODEL)
        self.assertEqual(ai_workshop_model.options, nodes.AI_WORKSHOP_MODEL_OPTIONS)
        self.assertTrue(seed.optional)
        self.assertEqual((seed.default, seed.min, seed.max), (0, 0, 0xffffffffffffffff))
        self.assertTrue(seed.control_after_generate)
        self.assertEqual(shot_count.default, nodes.AUTO_SHOT_COUNT)
        self.assertEqual(shot_count.options, nodes.SHOT_COUNT_OPTIONS)
        self.assertEqual(shot_count.options[1:], [str(count) for count in range(1, 21)])
        self.assertEqual(input_names.index("shot_count"), input_names.index("duration_seconds") + 1)
        self.assertFalse(any(item.id.lower().startswith("audio") for item in schema.inputs))

    def test_frontend_masks_api_key_and_has_signup_button(self):
        source = (NODES_PATH.parent / "web" / "js" / "minimax_h3_prompt_enhancer.js").read_text(encoding="utf-8")
        self.assertIn('input.type = "password"', source)
        self.assertIn("💾 保存到工作流", source)
        self.assertIn('clear.textContent = "清空"', source)
        self.assertIn("node.t8CommitApiKey = commit", source)
        self.assertIn("node.graph?.change?.()", source)
        self.assertIn("this.t8CommitApiKey?.()", source)
        self.assertIn("https://api.seedance.nz/sign-up?aff=5f4w", source)
        self.assertIn("https://ai.t8star.org/register?aff=dP7j", source)
        self.assertIn("window.open", source)
        self.assertIn("⚙️ 高级选项（可选）", source)
        self.assertIn("const advancedWidgets = [referenceContextWidget, constraintsWidget]", source)
        self.assertIn("API_KEY_PATTERN.test(value)", source)
        self.assertIn('T2VA: "T2VA（文生音视频）"', source)
        self.assertIn('const OPENAI_API_MODE = "OpenAI兼容接口（备用）"', source)
        self.assertIn("addApiModeBehavior", source)
        self.assertIn("▶ 运行提示词优化", source)
        self.assertIn("app.queuePrompt(0, 1, [String(this.id)])", source)
        self.assertIn('mode === "参考模板融合"', source)
        self.assertIn('widget.name === "reference_template"', source)
        self.assertIn('normalizeChoice(outputLanguageWidget, ["中文", "English"], "中文")', source)
        self.assertIn('normalizeChoice(promptModeWidget, ["官方增强", "参考模板融合"], "官方增强")', source)
        self.assertIn("OFFICIAL_SKILL_PROFILES", source)
        self.assertIn("CREATIVE_PRESET_OPTIONS", source)
        self.assertIn("normalizeChoice(officialSkillProfileWidget", source)
        self.assertIn("normalizeChoice(creativePresetWidget", source)
        self.assertIn("LEGACY_UI_VALUES.has(String(templateWidget.value", source)
        self.assertIn("SERIALIZED_WIDGET_NAMES.map", source)
        self.assertIn("nodeType.prototype.onSerialize", source)
        self.assertIn("beforeResize()", source)
        self.assertIn("afterResize(resizedNode)", source)
        self.assertIn('delete secureWidget.width', source)
        self.assertIn('"control_after_generate"', source)
        self.assertIn('seedControlWidget.label = "种子状态（运行后）"', source)
        self.assertIn('const AUTO_SHOT_COUNT = "AUTO（系统自动判断）"', source)
        self.assertIn('"shot_count"', source)
        self.assertIn("[16, 17, 19, 21].includes(serialized.widgets_values.length)", source)
        self.assertIn("widgets_values.splice(3, 0, AUTO_SHOT_COUNT)", source)
        self.assertIn("widgets_values.splice(8, 0, COMPAT_SKILL_PROFILE, NO_CREATIVE_PRESET)", source)
        self.assertIn('widgets_values.splice(11, 0, AI_WORKSHOP_DEFAULT_MODEL, "")', source)
        self.assertIn("widgets_values.splice(10, 0, NO_CASE_TEMPLATE)", source)
        self.assertIn('const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（图片/视频）"', source)
        self.assertIn('const AI_WORKSHOP_DEFAULT_MODEL = "gemini-3.5-flash"', source)
        self.assertIn('widget.name === "openai_video_urls"', source)
        self.assertIn('compatible || (workshop && modelWidget.value === CUSTOM_MODEL_OPTION)', source)
        self.assertIn('customModelWidget.label = compatible ? "OpenAI 模型 ID（必填）"', source)
        self.assertIn('widget.element.style.display = visible ? widget.t8OriginalDisplay : "none"', source)
        self.assertIn("widget.hidden = visible ? widget.t8OriginalHidden : true", source)
        self.assertIn('const MV_CREATIVE_PRESET = "音乐 MV 动态字幕（官方）"', source)
        self.assertIn('const LEGACY_MV_CREATIVE_PRESET = "MV / 歌词贴字"', source)
        self.assertIn('"歌词原文（逐字锁定，可空）："', source)
        self.assertIn('"无歌词时：器乐 / 允许生成原创歌词"', source)
        self.assertIn('"已知 BPM、歌词时间点或节拍事件（可空，节点不分析音频）："', source)
        self.assertIn("MV_REFERENCE_CONTEXT_TOOLTIP", source)
        self.assertIn("<Picture 3>=字体包装，只参考字体、版式和动效", source)
        self.assertIn("function addMvPresetBehavior", source)
        self.assertIn("preset === MV_CREATIVE_PRESET", source)
        self.assertIn("creativePresetWidget?.value === LEGACY_MV_CREATIVE_PRESET", source)
        self.assertIn("input.placeholder = isMv && mvPlaceholder", source)
        self.assertIn("requestAnimationFrame(() => update())", source)
        self.assertIn("this.t8UpdateMvPreset?.()", source)
        self.assertIn("改写模式只控制扩写幅度", source)
        self.assertIn("官方 Skill 协议控制说明正文语言与协议", source)

    def test_example_workflow_is_importable_and_contains_no_api_key(self):
        path = NODES_PATH.parent / "example" / "minimax_h3_prompt_enhancer_example.json"
        source = path.read_text(encoding="utf-8")
        workflow = json.loads(source)
        node = workflow["nodes"][0]
        self.assertEqual(node["type"], "MiniMaxH3PromptEnhancerT8")
        self.assertEqual(len(node["widgets_values"]), 22)
        self.assertEqual(node["widgets_values"][1], "T2VA（文生音视频）")
        self.assertEqual(node["widgets_values"][3], nodes.AUTO_SHOT_COUNT)
        self.assertEqual(
            node["widgets_values"][6:12],
            ["中文", "官方增强", nodes.COMPAT_SKILL_PROFILE, nodes.NO_CREATIVE_PRESET, nodes.NO_CASE_TEMPLATE, nodes.SEEDANCE_API_MODE],
        )
        self.assertEqual(node["widgets_values"][12:14], [nodes.AI_WORKSHOP_DEFAULT_MODEL, ""])
        self.assertIn("openai_video_urls", [item["name"] for item in node["inputs"]])
        self.assertNotIn("openai_upload_url", [item["name"] for item in node["inputs"]])
        self.assertEqual(node["widgets_values"][-2:], [0, "randomize"])
        self.assertNotRegex(source, r"sk-[A-Za-z0-9_-]{8,}")

    def test_output_language_rules_and_length_units_reach_the_model(self):
        chinese_session = FakeSession(basic_output())
        self.run_enhancer(chinese_session, description_word_target=200)
        chinese_messages = chinese_session.chat_requests[0]["json"]["messages"]
        self.assertIn("Output language: Simplified Chinese", chinese_messages[0]["content"])
        self.assertIn("Selected output language: 中文", chinese_messages[1]["content"])
        self.assertIn("approximately 200 Chinese characters", chinese_messages[1]["content"])

        english_session = FakeSession(basic_output())
        self.run_enhancer(english_session, output_language="English", description_word_target=200)
        english_messages = english_session.chat_requests[0]["json"]["messages"]
        self.assertIn("Output language: English", english_messages[0]["content"])
        self.assertIn("approximately 200 English words", english_messages[1]["content"])

        legacy_session = FakeSession(basic_output())
        self.run_enhancer(legacy_session, output_language="", prompt_mode="")
        legacy_messages = legacy_session.chat_requests[0]["json"]["messages"]
        self.assertIn("Output language: Simplified Chinese", legacy_messages[0]["content"])
        self.assertIn("Prompt construction mode: 官方增强", legacy_messages[1]["content"])

    def test_official_skill_strict_profile_forces_english_contract_without_breaking_compatibility(self):
        compatibility_session = FakeSession(basic_output())
        self.run_enhancer(
            compatibility_session,
            output_language="中文",
            description_word_target=200,
            official_skill_profile=nodes.COMPAT_SKILL_PROFILE,
        )
        compatibility_messages = compatibility_session.chat_requests[0]["json"]["messages"]
        self.assertIn("Output language: Simplified Chinese", compatibility_messages[0]["content"])
        self.assertIn("approximately 200 Chinese characters", compatibility_messages[1]["content"])

        strict_session = FakeSession(basic_output())
        self.run_enhancer(
            strict_session,
            output_language="中文",
            description_word_target=200,
            official_skill_profile=nodes.STRICT_SKILL_PROFILE,
        )
        strict_messages = strict_session.chat_requests[0]["json"]["messages"]
        self.assertIn("strict all-English contract", strict_messages[0]["content"])
        self.assertIn("Output language: English", strict_messages[0]["content"])
        self.assertNotIn("Output language: Simplified Chinese", strict_messages[0]["content"])
        self.assertIn("Effective descriptive output language: English", strict_messages[1]["content"])
        self.assertIn("approximately 200 English words", strict_messages[1]["content"])

        strict_ref_session = FakeSession(reference_output(include_video=False))
        self.run_enhancer(
            strict_ref_session,
            task_type="Ref2VA",
            reference_images={"reference_image_0": torch.zeros((1, 1, 1, 3))},
            output_language="中文",
            official_skill_profile=nodes.STRICT_SKILL_PROFILE,
        )
        strict_ref_user = strict_ref_session.chat_requests[0]["json"]["messages"][1]["content"][0]["text"]
        self.assertIn("detailed_description is normally 350-500 English words", strict_ref_user)

    def test_official_core_contract_and_frozen_source_reach_the_model(self):
        session = FakeSession(basic_output())
        self.run_enhancer(session)
        system = session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertEqual(nodes.OFFICIAL_SKILL_SOURCE_SHA, "093f3129a3f7bd27c74928b1cd31a54fbdebe057")
        for required in (
            "Simultaneous group speech uses a compact group identifier such as (S1,S2)",
            "place <scenetrans> on both sides of the cut",
            "Never put (S1), (S2), or other speaker identifiers in retention_analysis",
            "ordinary sound embedded in <Video N> does not automatically create an <Audio N> role",
            "newly requested action or background is not by itself evidence",
        ):
            self.assertIn(required, system)

    def test_all_official_creative_presets_are_available_and_injected_as_prompt_profiles(self):
        expected = {
            nodes.NO_CREATIVE_PRESET: ("Creative preset: none", "only the H3 core contract"),
            nodes.AUTO_CREATIVE_PRESET: ("Creative preset: AUTO", "Infer at most one"),
            "极简产品广告": ("minimalist product advertisement", "one concise single-line text event"),
            "3D 动画短片": ("3D animation short", "squash-and-stretch"),
            "品牌宣传短片": ("brand promotional video", "never fabricate a capability or claim"),
            nodes.MV_CREATIVE_PRESET: ("official music-video-subtitle-generator", "isolated character/scene/typography"),
            "双人合作游戏开场": ("two-player cooperative game intro", "five main colors"),
            "纸拼贴讲解": ("paper-collage explainer", "press-flat"),
            "立体纸艺停格讲解": ("papercraft stop-motion explainer", "pull-tabs"),
            "手绘实拍融合": ("hand-drawn/live-action fusion", "first 20 percent"),
        }
        self.assertEqual(list(expected), nodes.CREATIVE_PRESET_OPTIONS)
        for preset, markers in expected.items():
            with self.subTest(preset=preset):
                session = FakeSession(basic_output())
                self.run_enhancer(session, creative_preset=preset)
                messages = session.chat_requests[0]["json"]["messages"]
                for marker in markers:
                    self.assertIn(marker, messages[0]["content"])
                self.assertIn("prompt-writing profile only", messages[0]["content"])
                self.assertIn(f"Creative preset: {preset}", messages[1]["content"])

    def test_official_mv_skill_source_and_legacy_workflow_value_are_preserved(self):
        self.assertEqual(nodes.OFFICIAL_MV_SKILL_VERSION, "0.6.6")
        self.assertEqual(nodes.OFFICIAL_MV_SKILL_SOURCE_SHA, "b7227fa6a6206e9fb30562383d39e53cf3866a48")
        self.assertNotIn(nodes.LEGACY_MV_CREATIVE_PRESET, nodes.CREATIVE_PRESET_OPTIONS)

        session = FakeSession(basic_output())
        self.run_enhancer(session, creative_preset=nodes.LEGACY_MV_CREATIVE_PRESET)
        system = session.chat_requests[0]["json"]["messages"][0]["content"]
        user = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertIn("Official MiniMax music-video-subtitle-generator Skill v0.6.6", system)
        self.assertIn(f"commit {nodes.OFFICIAL_MV_SKILL_SOURCE_SHA}", system)
        self.assertIn(f"Creative preset: {nodes.MV_CREATIVE_PRESET}", user)


    def test_mv_skill_deep_rules_and_user_sources_reach_the_model(self):
        lyrics = "歌词原文：夜色落在我肩上，别回头。"
        role_map = (
            "<Picture 1>=人物外观；<Picture 2>=场景与灯光；"
            "<Picture 3>=字体包装，只参考字体、版式和动效，不参考人物与场景。"
        )
        session = FakeSession(basic_output())
        self.run_enhancer(
            session,
            prompt=f"暗色抒情 MV。{lyrics}",
            duration_seconds=15,
            creative_preset=nodes.MV_CREATIVE_PRESET,
            reference_context=role_map,
        )
        messages = session.chat_requests[0]["json"]["messages"]
        system = messages[0]["content"]
        user = messages[1]["content"]

        for required in (
            "User-supplied lyrics are locked lyrics",
            "explicitly authorizes this official preset to create original lyrics",
            "Without that explicit authorization, do not invent lyrics",
            "write the exact phrase as <d>[Language] exact source text</d>",
            "Do not add a singer, lip sync, readable lyrics, or a vocal performance",
            "Keep an off-screen vocal source off-screen",
            "put <scenetrans> on both sides",
            "foreground, midground, or background graphic layer",
            "one principal reading focus at a time",
            "must not block eyes, the main facial expression, or the mouth",
            "timestamp, BPM, drop, snare, 808 event",
            "never claim beat, BPM, hook, chorus, or audio-file analysis",
            "conditional Trap, Dark-pop, or Cyber-grunge grammar",
            "A character reference controls only",
            "Never copy sample words",
            "It does not prove an independent <Audio N>, Master Audio, BPM",
            "Fold them naturally into integrated_multimodal_description or Ref2VA detailed_description",
            "a 15-second MV often needs only 2-4 readable shots",
            "Do not output asset cards",
            "This node adapts only the rules that can be expressed in one 4-15 second H3 prompt",
            "MV rewrite scope: balanced",
            "MV request context: H3 task=T2VA; duration=15.00s; AUTO",
        ):
            self.assertIn(required, system)
        self.assertIn(lyrics, user)
        self.assertIn(role_map, user)

    def test_mv_skill_is_conditional_and_context_aware(self):
        no_preset_session = FakeSession(basic_output())
        self.run_enhancer(no_preset_session, prompt="产品标题贴字动画")
        no_preset_system = no_preset_session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertNotIn("MV Skill — locked lyrics", no_preset_system)

        auto_product_session = FakeSession(basic_output())
        self.run_enhancer(
            auto_product_session,
            prompt="产品标题贴字动画",
            creative_preset=nodes.AUTO_CREATIVE_PRESET,
        )
        auto_product_system = auto_product_session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertIn("no explicit MV intent was found", auto_product_system)
        self.assertIn("ordinary product text, captions, titles, UI copy", auto_product_system)
        self.assertNotIn("MV Skill — locked lyrics", auto_product_system)

        auto_mv_session = FakeSession(basic_output())
        self.run_enhancer(auto_mv_session, prompt="制作歌词 MV", creative_preset=nodes.AUTO_CREATIVE_PRESET)
        auto_mv_system = auto_mv_session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertIn("explicit trusted text matches", auto_mv_system)
        self.assertIn("MV Skill — locked lyrics", auto_mv_system)

        template = "陌生角色演唱模板歌词，120 BPM，固定 8 镜头。"
        fused_session = FakeSession(basic_output())
        self.run_enhancer(
            fused_session,
            prompt="器乐 MV，只使用抽象文字形状，不出现歌手和可读歌词。",
            duration_seconds=4,
            shot_count="20",
            rewrite_mode="creative",
            creative_preset=nodes.MV_CREATIVE_PRESET,
            prompt_mode="参考模板融合",
            reference_template=template,
        )
        fused_messages = fused_session.chat_requests[0]["json"]["messages"]
        fused_system = fused_messages[0]["content"]
        fused_user = fused_messages[1]["content"]
        self.assertIn("Fixed: honor exactly 20 shots", fused_system)
        self.assertIn("duration=4.00s", fused_system)
        self.assertIn("MV rewrite scope: creative", fused_system)
        self.assertIn("Template people, lyrics, BPM, titles, plot, and shot count remain non-authoritative", fused_system)
        self.assertIn("Instrumental, pure-typography, montage, and off-screen-vocal MVs remain valid", fused_system)
        self.assertIn(template, fused_user)

    def test_mv_rules_preserve_h3_tasks_and_rewrite_mode_boundaries(self):
        for rewrite_mode, marker in nodes.MV_REWRITE_MODE_RULES.items():
            with self.subTest(rewrite_mode=rewrite_mode):
                session = FakeSession(basic_output())
                self.run_enhancer(
                    session,
                    rewrite_mode=rewrite_mode,
                    creative_preset=nodes.MV_CREATIVE_PRESET,
                )
                system = session.chat_requests[0]["json"]["messages"][0]["content"]
                self.assertIn(marker, system)
                self.assertIn("Output exactly these three fields in order", system)
                self.assertNotIn("Master Audio instructions", session.chat_requests[0]["json"]["messages"][1]["content"])

        ref_session = FakeSession(reference_output(include_video=False))
        self.run_enhancer(
            ref_session,
            task_type="Ref2VA",
            reference_images={"reference_image_0": torch.zeros((1, 1, 1, 3))},
            creative_preset=nodes.MV_CREATIVE_PRESET,
            official_skill_profile=nodes.STRICT_SKILL_PROFILE,
            output_language="中文",
        )
        ref_system = ref_session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertIn("Output exactly these six fields in order", ref_system)
        self.assertIn("Output language: English", ref_system)
        self.assertIn("Preserve their exact language, wording, punctuation", ref_system)

    def test_invalid_skill_profile_and_preset_fail_before_network(self):
        for kwargs, phrase in (
            ({"official_skill_profile": "future-profile"}, "official_skill_profile"),
            ({"creative_preset": "future-preset"}, "creative_preset"),
            ({"case_template": "future-case"}, "case_template"),
        ):
            with self.subTest(kwargs=kwargs):
                session = FakeSession(basic_output())
                with self.assertRaisesRegex(nodes.PromptEnhancerError, phrase):
                    self.run_enhancer(session, **kwargs)
                self.assertEqual(session.uploads, [])
                self.assertEqual(session.chat_requests, [])

    def test_non_official_case_catalog_is_separate_dual_model_safe_and_injected(self):
        self.assertEqual(nodes.CASE_TEMPLATE_OPTIONS[0], nodes.NO_CASE_TEMPLATE)
        self.assertEqual(len(nodes.CASE_TEMPLATE_OPTIONS), 38)
        self.assertEqual(len(set(nodes.CASE_TEMPLATE_OPTIONS)), 38)

        no_case_session = FakeSession(basic_output())
        self.run_enhancer(no_case_session)
        no_case_system = no_case_session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertNotIn("Selected T8 original case template", no_case_system)
        self.assertNotIn("Reusable Creative DNA (mechanism and production grammar only)", no_case_system)

        for selection in nodes.CASE_TEMPLATE_OPTIONS[1:]:
            with self.subTest(selection=selection):
                session = FakeSession(basic_output())
                self.run_enhancer(session, case_template=selection)
                system = session.chat_requests[0]["json"]["messages"][0]["content"]
                self.assertIn(f"HUMAN_NAME: {selection}", system)
                self.assertIn("SELECTED_CASE_ID:", system)
                self.assertIn("REQUIRED_MECHANISM_ANCHORS", system)
                anchor_block = system.split("REQUIRED_MECHANISM_ANCHORS", 1)[1].split("SPARSE_INPUT", 1)[0]
                anchors = re.findall(r"^\d+\. (.+)$", anchor_block, re.MULTILINE)
                self.assertIn(len(anchors), {4, 5})
                self.assertIn(f"realize all {len(anchors)} as concrete events in order", system)
                self.assertIn("Reusable Creative DNA (mechanism and production grammar only)", system)
                self.assertIn("MiniMax H3 native adapter", system)
                self.assertIn("native H3 integrated description", system)
                self.assertIn("never treat as a MiniMax official Skill", system)
                self.assertNotIn("Seedance 2.0 native adapter", system)
                self.assertNotIn("preview.gif", system)
                self.assertNotIn("/case-preview/", system)

        manual = "只参考三段式节奏，第二段必须保持一镜到底。"
        combined_session = FakeSession(basic_output())
        self.run_enhancer(
            combined_session,
            case_template=nodes.CASE_TEMPLATE_OPTIONS[1],
            creative_preset="品牌宣传短片",
            prompt_mode="参考模板融合",
            reference_template=manual,
        )
        messages = combined_session.chat_requests[0]["json"]["messages"]
        self.assertIn("brand promotional video", messages[0]["content"])
        self.assertIn("Selected T8 original case template", messages[0]["content"])
        self.assertIn(manual, messages[1]["content"])

    def test_subject_only_case_intent_is_preserved_and_completed_by_all_37_selectors(self):
        for selection in nodes.CASE_TEMPLATE_OPTIONS[1:]:
            with self.subTest(selection=selection):
                session = FakeSession(basic_output())
                self.run_enhancer(session, prompt="美丽的女人", case_template=selection)
                system = session.chat_requests[0]["json"]["messages"][0]["content"]
                self.assertIn('INSTANCE_INTENT: "美丽的女人"', system)
                self.assertIn("SPARSE_INPUT: yes", system)
                self.assertIn("Create an original, compatible scene, trigger, ordered event chain and visible result", system)
                self.assertIn("must remain the subject", system)
                self.assertIn("must not collapse into a generic portrait", system)

    def test_stable_ids_and_legacy_case_values_resolve_to_current_human_labels(self):
        cases = {
            "t8c001-product-proof-state-machine": "产品广告｜功能证据递进",
            "T8-C001｜产品证明状态机": "产品广告｜功能证据递进",
            "t8-case-audio-cause-lead-ladder-v1": "景别收紧｜从世界到眼神",
            "声画错位递进": "景别收紧｜从世界到眼神",
        }
        for saved_value, current_label in cases.items():
            with self.subTest(saved_value=saved_value):
                session = FakeSession(basic_output())
                self.run_enhancer(session, case_template=saved_value)
                system = session.chat_requests[0]["json"]["messages"][0]["content"]
                self.assertIn(f"HUMAN_NAME: {current_label}", system)

    def test_case_contract_keeps_concrete_changed_surface_intent_and_all_ordered_anchors(self):
        selection = "角色登场｜细节到全身揭晓"
        prompt = "一位蒸汽朋克女飞行员在飞艇甲板亮相，先看护目镜，最后全身站定。"
        session = FakeSession(basic_output())
        self.run_enhancer(session, prompt=prompt, case_template=selection)
        system = session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertIn(json.dumps(prompt, ensure_ascii=False), system)
        self.assertIn("SPARSE_INPUT: no", system)
        expected = ["从可识别细节开始", "揭晓尺度逐步扩大", "角色只做一次代表动作", "以全身定格完成身份确认"]
        offsets = [system.index(anchor) for anchor in expected]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("[Shot N] timeline", system)
        self.assertNotIn("consecutive 镜头N sequence", system)

    def test_fake_h3_provider_outputs_all_case_anchors_in_native_structure_and_order(self):
        for selection in nodes.CASE_TEMPLATE_OPTIONS[1:]:
            with self.subTest(selection=selection):
                session = AnchorAwareH3Session()
                output = self.run_enhancer(session, prompt="美丽的女人", case_template=selection)
                system = session.chat_requests[0]["json"]["messages"][0]["content"]
                block = system.split("REQUIRED_MECHANISM_ANCHORS", 1)[1].split("SPARSE_INPUT", 1)[0]
                anchors = re.findall(r"^\d+\. (.+)$", block, re.MULTILINE)
                self.assertTrue(output.startswith("integrated_multimodal_description: [Shot 1]"))
                self.assertEqual(output.count("overall_soundscape:"), 1)
                self.assertEqual(output.count("non_diegetic_music:"), 1)
                offsets = [output.index(anchor) for anchor in anchors]
                self.assertEqual(offsets, sorted(offsets))
                self.assertLess(offsets[-1], output.index("overall_soundscape:"))

    def test_distributable_case_catalog_contains_only_active_text_abstractions(self):
        catalog_path = NODES_PATH.parent / "case_templates" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], "t8-case-template-catalog/v2")
        self.assertEqual(len(catalog["templates"]), 37)
        self.assertEqual(catalog["source_case_count"], 39)
        self.assertEqual(catalog["selector_template_count"], 37)
        self.assertEqual(catalog["evidence_variant_count"], 2)
        self.assertFalse(catalog["official_minimax_skills_included"])
        by_id = {template["id"]: template for template in catalog["templates"]}
        imported_ids = {
            "t8-case-evidence-ladder-reality-v1",
            "t8-case-threshold-inspection-passage-v1",
            "t8-case-imperfect-memory-farewell-v1",
            "t8-case-deadpan-chain-failure-v1",
            "t8-case-layered-dossier-activation-v1",
            "t8-case-created-mark-boundary-crossing-v1",
            "t8-case-material-progress-clock-v1",
            "t8-case-staged-character-reveal-v1",
            "t8-case-mechanical-convoy-proof-v1",
            "t8-case-flat-geometry-reconstruction-v1",
            "t8-case-scale-contraction-evidence-funnel-v1",
            "t8-case-recurring-identity-board-v1",
            "t8-case-dual-system-convergence-proof-v1",
            "t8-case-alternating-obstacle-goal-corridor-v1",
            "t8-case-calm-dense-decisive-delay-v1",
            "t8-case-monotonic-route-loss-threshold-v1",
            "t8-case-procedure-mismatch-nested-proof-v1",
            "t8-case-base-loop-skill-ladder-v1",
            "t8-case-inert-scale-active-intervention-v1",
            "t8-case-material-role-traversal-ladder-v1",
            "t8-case-earnest-upgrade-displacement-v1",
            "t8-case-recorder-overlay-memory-route-v1",
            "t8-case-performance-fall-rise-arc-v1",
            "t8-case-first-person-testimonial-proof-v1",
            "t8-case-persistent-selector-subject-swap-v1",
            "t8-case-kinetic-text-obstacle-break-v1",
            "t8-case-asymmetric-mass-control-fight-v1",
            "t8-case-reversible-material-typography-loop-v1",
            "t8-case-observer-follow-encounter-v1",
            "t8-case-two-turn-pause-reaction-v1",
        }
        self.assertTrue(imported_ids.issubset(by_id))
        self.assertIn("微缩闯关｜同一材质连续变形", nodes.CASE_TEMPLATE_OPTIONS)
        self.assertIn("升级讽刺｜新物登场旧爱被移走", nodes.CASE_TEMPLATE_OPTIONS)
        self.assertEqual(len(by_id["t8-case-material-role-traversal-ladder-v1"]["required_anchors"]), 5)
        self.assertEqual(len(by_id["t8-case-earnest-upgrade-displacement-v1"]["required_anchors"]), 5)
        source = catalog_path.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"https?://")
        self.assertNotRegex(source, r"sk-[A-Za-z0-9_-]{16,}")
        self.assertNotIn("case_directory", source)
        self.assertNotIn("compiled_prompt", source)
        self.assertNotIn("openai_upload_url", source)
        self.assertNotIn("music-video-subtitle-generator", source)
        self.assertNotIn("t8-case-audio-cause-lead-ladder-v1", {template["id"] for template in catalog["templates"]})
        preview_count = 0
        for template in catalog["templates"]:
            self.assertEqual(template["status"], "active")
            self.assertFalse(template["official"])
            self.assertRegex(template["label"], r"[\u4e00-\u9fff]")
            self.assertEqual(set(template["variants"]), {"h3", "seedance20"})
            self.assertTrue(template["source"]["case_sha256"])
            self.assertNotIn("integrated_multimodal_description:", template["creative_dna"])
            self.assertTrue(template["summary"])
            self.assertTrue(template["input_format"])
            self.assertTrue(template["recommended_input"])
            self.assertGreaterEqual(len(template["required_anchors"]), 2)
            self.assertLessEqual(len(template["required_anchors"]), 5)
            self.assertTrue(template["previews"])
            self.assertTrue(all(preview["human_preview_only"] for preview in template["previews"]))
            preview_count += len(template["previews"])
        self.assertEqual(preview_count, 39)
        self.assertEqual(len(by_id["t8-case-flat-geometry-reconstruction-v1"]["previews"]), 2)
        self.assertEqual(len(by_id["t8-case-recurring-identity-board-v1"]["previews"]), 2)
        soran = by_id["t8-case-scale-contraction-evidence-funnel-v1"]
        self.assertIn("t8-case-audio-cause-lead-ladder-v1", soran["legacy_ids"])
        self.assertIn("声画错位递进", soran["legacy_labels"])
        batch_01_ids = {
            "t8-case-evidence-ladder-reality-v1",
            "t8-case-threshold-inspection-passage-v1",
            "t8-case-imperfect-memory-farewell-v1",
            "t8-case-deadpan-chain-failure-v1",
            "t8-case-layered-dossier-activation-v1",
            "t8-case-created-mark-boundary-crossing-v1",
            "t8-case-material-progress-clock-v1",
            "t8-case-staged-character-reveal-v1",
            "t8-case-mechanical-convoy-proof-v1",
            "t8-case-flat-geometry-reconstruction-v1",
        }
        for template_id in imported_ids:
            imported = by_id[template_id]
            self.assertRegex(imported["source"]["creative_dna_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("Do not copy from the source:", imported["creative_dna"])

    def test_source_batches_reconstruct_the_catalog_identity_and_provenance(self):
        root = NODES_PATH.parent
        catalog = json.loads((root / "case_templates" / "catalog.json").read_text(encoding="utf-8"))
        catalog_by_case = {template["source"]["case_id"]: template for template in catalog["templates"]}
        source_cases = []
        for path in sorted((root / "case_templates" / "source_batches").glob("*.json")):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"https?://")
            self.assertNotRegex(source, r"[A-Za-z]:\\")
            batch = json.loads(source)
            self.assertEqual(batch["schema_version"], "t8-case-template-batch/v1")
            source_cases.extend(batch["cases"])
        self.assertEqual(len(source_cases), 37)
        self.assertEqual({item["case_id"] for item in source_cases}, set(catalog_by_case))
        for item in source_cases:
            template = catalog_by_case[item["case_id"]]
            self.assertEqual(template["id"], item["template_id"])
            self.assertEqual(template["label"], item["label"])
            self.assertEqual(template["summary"], item["summary"])
            for field in ("case_sha256", "creative_dna_sha256"):
                if field in item:
                    self.assertEqual(template["source"][field], item[field])

    def test_case_template_frontend_shows_preview_and_safe_recommended_fill(self):
        root = NODES_PATH.parent
        shared = (root / "web" / "js" / "case_template_ui.js").read_text(encoding="utf-8")
        menu = (root / "web" / "js" / "template_menu_preview.js").read_text(encoding="utf-8")
        official = (root / "web" / "js" / "official_preset_previews.js").read_text(encoding="utf-8")
        h3_ui = (root / "web" / "js" / "minimax_h3_prompt_enhancer.js").read_text(encoding="utf-8")
        seedance_ui = (root / "web" / "js" / "seedance20_prompt_enhancer.js").read_text(encoding="utf-8")
        self.assertIn("填入推荐示例", shared)
        self.assertIn("已有输入，未覆盖", shared)
        self.assertIn("适用范围", shared)
        self.assertIn("推荐输入格式", shared)
        self.assertIn("此 GIF 推荐示例", shared)
        self.assertIn("if (String(promptWidget?.value || \"\").trim())", shared)
        self.assertIn("仅供人类本地预览，不会发送给 LLM", shared)
        self.assertIn("查看来源", shared)
        self.assertIn("serializedCaseTemplateValue", h3_ui)
        self.assertIn("serializedCaseTemplateValue", seedance_ui)
        self.assertIn("addCaseTemplateUI", h3_ui)
        self.assertIn("addCaseTemplateUI", seedance_ui)
        self.assertIn("registerTemplateMenuPreview(node, caseWidget", shared)
        self.assertIn('entry.addEventListener("pointerenter"', menu)
        self.assertIn('filter?.addEventListener("keydown"', menu)
        self.assertIn("rootRect.right + gap", menu)
        self.assertIn("rootRect.left - panelRect.width - gap", menu)
        self.assertIn("addOfficialPresetMenuPreview(this, creativePresetWidget)", h3_ui)
        self.assertIn("MiniMax 官方示例 GIF", official)
        self.assertIn("不会发送给 LLM", official)

    def test_all_official_preset_gifs_are_bundled_and_hash_pinned(self):
        root = NODES_PATH.parent
        asset_root = root / "web" / "js" / "assets" / "official-previews"
        source = (root / "web" / "js" / "official_preset_previews.js").read_text(encoding="utf-8")
        expected = {
            "极简产品广告": ("minimalist-product-ad-generator.gif", "f25d9b4f9c2a8d881d8bbefdb3076a4d79fd46246d11b75d1a5ee278b5cc38f7"),
            "3D 动画短片": ("3d-animation-short-generator.gif", "1bf1ad020c4d8548a23902133c4704b2c2503efef1de40889cf0eb3a92467285"),
            "品牌宣传短片": ("brand-promo-video-generator.gif", "1346688e90749b42ca15f94fc80078ebb7d98a9bf23f409f6a2f11d6f55c5ba5"),
            nodes.MV_CREATIVE_PRESET: ("music-video-subtitle-generator.gif", "e266707a77965622d175d012370a638cb2bef660532950634c28434fd87697e2"),
            "双人合作游戏开场": ("co-op-game-intro-generator.gif", "b6c12f7ac0e476645b8228e4b6b6cb9650c3b92d7e773b3d68c1dadac733cdde"),
            "纸拼贴讲解": ("paper-collage-explainer-generator.gif", "f89d8c00943dbe02fae0b709ebb5705fc80a75bfd13bbb0cefdb01eb31b4a8f3"),
            "立体纸艺停格讲解": ("papercraft-stop-motion-explainer.gif", "6bc26e1724e6dbe250fe10b22924fa914602d98f1634b3410bf208dfc05ec59f"),
            "手绘实拍融合": ("handdrawn-live-video-generator.gif", "4bbc23442baedd2463e3c111221946fce59bd55d498e2c522d3da9b295083e55"),
        }
        self.assertEqual({path.name for path in asset_root.glob("*.gif")}, {item[0] for item in expected.values()})
        for label, (filename, digest) in expected.items():
            with self.subTest(label=label):
                self.assertIn(f'"{label}"', source)
                self.assertIn(f'file: "{filename}"', source)
                self.assertEqual(hashlib.sha256((asset_root / filename).read_bytes()).hexdigest(), digest)
        self.assertIn('const OFFICIAL_COMMIT = "b7227fa6a6206e9fb30562383d39e53cf3866a48"', source)

    def test_reference_template_mode_requires_and_sends_template(self):
        missing_session = FakeSession(basic_output())
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "reference_template is required"):
            self.run_enhancer(missing_session, prompt_mode="参考模板融合")
        self.assertEqual(missing_session.chat_requests, [])

        legacy_session = FakeSession(basic_output())
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "reference_template is required"):
            self.run_enhancer(
                legacy_session,
                prompt_mode="参考模板融合",
                reference_template="打开 Seedance 注册页面",
            )
        self.assertEqual(legacy_session.chat_requests, [])

        template = "[镜头1] 水墨滴落；[镜头2] 高频快切；最后收束为纯白背景。"
        reference_session = FakeSession(basic_output())
        self.run_enhancer(
            reference_session,
            prompt_mode="参考模板融合",
            reference_template=template,
        )
        reference_messages = reference_session.chat_requests[0]["json"]["messages"]
        self.assertIn("reference-template fusion", reference_messages[0]["content"])
        self.assertIn("Compress, merge, or redesign template beats", reference_messages[0]["content"])
        self.assertIn(template, reference_messages[1]["content"])

        official_session = FakeSession(basic_output())
        self.run_enhancer(
            official_session,
            prompt_mode="官方增强",
            reference_template=template,
        )
        self.assertNotIn(template, official_session.chat_requests[0]["json"]["messages"][1]["content"])

    def test_fixed_model_and_mode_temperature_mapping(self):
        for mode, temperature in nodes.MODE_TEMPERATURES.items():
            with self.subTest(mode=mode):
                session = FakeSession(basic_output())
                self.run_enhancer(session, rewrite_mode=mode)
                request = session.chat_requests[0]
                self.assertEqual(request["json"]["model"], "bytedance/doubao-seed-evolving")
                self.assertEqual(request["json"]["temperature"], temperature)
                self.assertFalse(request["json"]["stream"])

    def test_seed_reaches_the_prompt_as_a_variation_marker_not_an_undocumented_api_field(self):
        first_session = FakeSession(basic_output())
        self.run_enhancer(first_session, seed=123456)
        first_request = first_session.chat_requests[0]["json"]
        self.assertNotIn("seed", first_request)
        self.assertIn("Variation seed: 123456", first_request["messages"][1]["content"])
        self.assertIn("Never print it in the result", first_request["messages"][1]["content"])

        second_session = FakeSession(basic_output())
        self.run_enhancer(second_session, seed=654321)
        self.assertNotEqual(
            first_request["messages"][1]["content"],
            second_session.chat_requests[0]["json"]["messages"][1]["content"],
        )

    def test_auto_and_fixed_shot_count_rules_reach_the_model(self):
        auto_session = FakeSession(basic_output())
        self.run_enhancer(auto_session)
        auto_messages = auto_session.chat_requests[0]["json"]["messages"]
        self.assertIn("Shot count mode: AUTO", auto_messages[0]["content"])
        self.assertIn("Shot count control: AUTO", auto_messages[1]["content"])

        fixed_session = FakeSession(basic_output())
        result = self.run_enhancer(fixed_session, shot_count="12")
        fixed_request = fixed_session.chat_requests[0]["json"]
        self.assertEqual(result, basic_output())
        self.assertNotIn("shot_count", fixed_request)
        self.assertIn("exactly 12 shots", fixed_request["messages"][0]["content"])
        self.assertIn("from [Shot 1] through [Shot 12]", fixed_request["messages"][0]["content"])
        self.assertIn("overrides any approximate shot-count number or range", fixed_request["messages"][0]["content"])
        self.assertIn("Shot count control: exactly 12", fixed_request["messages"][1]["content"])

    def test_labeled_task_type_is_normalized_to_the_fixed_h3_contract(self):
        session = FakeSession(basic_output())
        result = self.run_enhancer(session, task_type="T2VA（文生音视频）")
        self.assertEqual(result, basic_output())
        self.assertIn("H3 task type: T2VA", session.chat_requests[0]["json"]["messages"][1]["content"])

    def test_openai_compatible_mode_uses_one_base_url_and_custom_model(self):
        session = FakeSession(basic_output())
        with patch.dict(os.environ, {}, clear=True):
            result = nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                api_key="compatible-key",
                api_mode=nodes.OPENAI_API_MODE,
                openai_base_url="https://gateway.example/v1",
                custom_model="provider/vision-model",
                session=session,
            )
        self.assertEqual(result, basic_output())
        self.assertEqual(session.chat_urls, ["https://gateway.example/v1/chat/completions"])
        self.assertEqual(session.chat_requests[0]["json"]["model"], "provider/vision-model")
        self.assertEqual(session.chat_requests[0]["headers"]["Authorization"], "Bearer compatible-key")

    def test_ai_workshop_uses_default_model_and_inline_complete_image_and_video(self):
        session = FakeSession(reference_output())
        video_bytes = b"complete-video-including-final-segment"
        with patch.dict(os.environ, {}, clear=True):
            result = nodes.enhance_prompt(
                prompt="Transfer the complete temporal reference to the pictured subject.",
                task_type="Ref2VA",
                reference_images={"reference_image_0": torch.zeros((1, 2, 2, 3))},
                reference_videos={"reference_video_0": FakeVideo(data=video_bytes)},
                api_key="workshop-key",
                api_mode=nodes.AI_WORKSHOP_API_MODE,
                session=session,
            )
        self.assertEqual(result, reference_output())
        self.assertEqual(session.uploads, [])
        self.assertEqual(session.chat_urls, [nodes.AI_WORKSHOP_CHAT_COMPLETIONS_URL])
        request = session.chat_requests[0]
        self.assertEqual(request["json"]["model"], nodes.AI_WORKSHOP_DEFAULT_MODEL)
        parts = request["json"]["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "image_url", "text", "image_url"])
        image_url = parts[2]["image_url"]["url"]
        video_url = parts[4]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/png;base64,"))
        self.assertTrue(video_url.startswith("data:video/mp4;base64,"))
        self.assertEqual(base64.b64decode(video_url.split(",", 1)[1]), video_bytes)

    def test_ai_workshop_custom_model_is_explicit_and_required(self):
        session = FakeSession(basic_output())
        with patch.dict(os.environ, {}, clear=True):
            nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                api_key="workshop-key",
                api_mode=nodes.AI_WORKSHOP_API_MODE,
                ai_workshop_model=nodes.CUSTOM_MODEL_OPTION,
                custom_model="gemini-3.5-flash-thinking-low",
                session=session,
            )
        self.assertEqual(session.chat_requests[0]["json"]["model"], "gemini-3.5-flash-thinking-low")

        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(nodes.PromptEnhancerError, "custom_model is empty"):
            nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                api_key="workshop-key",
                api_mode=nodes.AI_WORKSHOP_API_MODE,
                ai_workshop_model=nodes.CUSTOM_MODEL_OPTION,
                session=FakeSession(basic_output()),
            )

    def test_openai_compatible_image_is_inlined_as_base64_without_upload(self):
        session = FakeSession(basic_output("I2VA"))
        with patch.dict(os.environ, {}, clear=True):
            nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                task_type="I2VA（首帧图生音视频）",
                first_frame=torch.zeros((1, 1, 1, 3)),
                api_key="compatible-key",
                api_mode=nodes.OPENAI_API_MODE,
                openai_base_url="https://gateway.example",
                custom_model="provider/vision-model",
                session=session,
            )
        self.assertEqual(session.uploads, [])
        self.assertEqual(session.chat_urls, ["https://gateway.example/v1/chat/completions"])
        parts = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "image_url"])
        self.assertTrue(parts[2]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_openai_compatible_mode_requires_custom_model(self):
        session = FakeSession(basic_output())
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(nodes.PromptEnhancerError, "requires custom_model"):
            nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                api_key="compatible-key",
                api_mode=nodes.OPENAI_API_MODE,
                openai_base_url="https://gateway.example/v1",
                session=session,
            )
        self.assertEqual(session.uploads, [])
        self.assertEqual(session.chat_requests, [])

    def test_openai_compatible_video_supports_direct_url_then_base64_fallback(self):
        session = FakeSession(reference_output())
        second_video = b"second-complete-video"
        with patch.dict(os.environ, {}, clear=True):
            nodes.enhance_prompt(
                prompt="Transfer the referenced action to the pictured subject.",
                task_type="Ref2VA（参考图/视频生音视频）",
                reference_images={"reference_image_0": torch.zeros((1, 1, 1, 3))},
                reference_videos={
                    "reference_video_0": FakeVideo(),
                    "reference_video_1": FakeVideo(data=second_video),
                },
                api_key="compatible-key",
                api_mode=nodes.OPENAI_API_MODE,
                openai_base_url="https://gateway.example/v1/chat/completions",
                openai_video_urls="https://media.example/reference-one.mp4",
                custom_model="provider/video-vision-model",
                session=session,
            )
        self.assertEqual(session.chat_urls, ["https://gateway.example/v1/chat/completions"])
        self.assertEqual(session.uploads, [])
        parts = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertEqual(
            [part["type"] for part in parts],
            ["text", "text", "image_url", "text", "video_url", "text", "video_url"],
        )
        self.assertTrue(parts[2]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(parts[4]["video_url"]["url"], "https://media.example/reference-one.mp4")
        fallback_url = parts[6]["video_url"]["url"]
        self.assertTrue(fallback_url.startswith("data:video/mp4;base64,"))
        self.assertEqual(base64.b64decode(fallback_url.split(",", 1)[1]), second_video)

    def test_node_api_key_overrides_environment_key(self):
        session = FakeSession(basic_output())
        self.run_enhancer(session, api_key="node-key")
        self.assertEqual(session.chat_requests[0]["headers"]["Authorization"], "Bearer node-key")

    def test_legacy_workflow_key_and_button_values_are_migrated_before_request(self):
        session = FakeSession(basic_output())
        migrated_key = "sk-" + "legacy-workflow-key-1234567890"
        with patch.dict(os.environ, {}, clear=True):
            result = nodes.enhance_prompt(
                prompt="A cyclist crosses the street.",
                reference_context=migrated_key,
                constraints="收起",
                api_key="打开 Seedance 注册页面",
                session=session,
            )
        self.assertEqual(result, basic_output())
        self.assertEqual(session.chat_requests[0]["headers"]["Authorization"], f"Bearer {migrated_key}")
        user_content = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertNotIn(migrated_key, user_content)
        self.assertNotIn("收起", user_content)

    def test_legacy_button_value_is_cleared_from_openai_compatible_url(self):
        session = FakeSession(basic_output())
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "requires openai_base_url"):
            self.run_enhancer(
                session,
                api_mode=nodes.OPENAI_API_MODE,
                api_key="test-key",
                openai_base_url="提交当前工作流",
            )
        self.assertEqual(session.chat_requests, [])

    def test_api_key_like_secret_inside_prompt_fields_fails_before_network(self):
        session = FakeSession(basic_output())
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "Remove the API-key-like secret"):
            self.run_enhancer(
                session,
                prompt_mode="参考模板融合",
                reference_template="镜头模板中误粘贴 " + "sk-" + "secret-value-1234567890 请删除",
            )
        self.assertEqual(session.chat_requests, [])

    def test_existing_positional_enhance_prompt_call_remains_compatible(self):
        session = FakeSession(basic_output())
        with patch.dict(os.environ, {"SEEDANCE_API_KEY": "secret-key"}):
            result = nodes.enhance_prompt(
                "A cyclist crosses the street.", "T2VA", 5, "balanced", 0,
                None, None, None, None, "", "", "", session,
            )
        self.assertEqual(result, basic_output())

    def test_t2va_has_no_upload_and_returns_raw_nonempty_prompt(self):
        expected = basic_output()
        raw = f"```text\n{expected}\n```"
        session = FakeSession(raw)
        result = self.run_enhancer(session)
        self.assertEqual(result, raw)
        self.assertEqual(session.uploads, [])
        self.assertIsInstance(session.chat_requests[0]["json"]["messages"][1]["content"], str)

    def test_i2va_uploads_first_frame_as_picture_one(self):
        session = FakeSession(basic_output("I2VA"))
        image = torch.zeros((1, 2, 3, 3), dtype=torch.float32)
        result = self.run_enhancer(session, task_type="I2VA", first_frame=image)
        self.assertTrue(result.startswith(nodes.I2VA_INSTRUCTION))
        self.assertEqual(session.uploads[0][0:3:2], ("picture_1.png", "image/png"))
        parts = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "image_url"])
        self.assertEqual(parts[2]["image_url"]["url"], "https://assets.example/picture_1.png")

    def test_fl2va_uploads_first_and_last_frames_in_order(self):
        session = FakeSession(basic_output("FL2VA", duration=8, shots=1))
        first = torch.zeros((1, 2, 2, 3))
        last = torch.ones((1, 2, 2, 3))
        result = self.run_enhancer(
            session,
            task_type="FL2VA",
            duration_seconds=8,
            first_frame=first,
            last_frame=last,
        )
        self.assertIn("8.00-second", result.splitlines()[0])
        self.assertEqual([upload[0] for upload in session.uploads], ["picture_1.png", "picture_2.png"])

    def test_l2va_uploads_only_last_frame(self):
        session = FakeSession(basic_output("L2VA", duration=6, shots=1))
        result = self.run_enhancer(
            session,
            task_type="L2VA",
            duration_seconds=6,
            last_frame=torch.zeros((1, 2, 2, 3)),
        )
        self.assertIn("[Shot 1]", result.splitlines()[0])
        self.assertEqual([upload[0] for upload in session.uploads], ["picture_1.png"])

    def test_ref2va_sends_complete_image_and_video_in_one_chat_request(self):
        session = FakeSession(reference_output())
        video_bytes = b"not-frames-the-complete-video-file"
        result = self.run_enhancer(
            session,
            task_type="Ref2VA",
            reference_images={"reference_image_0": torch.zeros((1, 2, 2, 3))},
            reference_videos={"reference_video_0": FakeVideo(video_bytes)},
        )
        self.assertTrue(result.startswith("subject_definitions:"))
        self.assertEqual([upload[0] for upload in session.uploads], ["picture_1.png", "video_1.mp4"])
        self.assertEqual(session.uploads[1][1], video_bytes)
        parts = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertEqual(
            [part["type"] for part in parts],
            ["text", "text", "image_url", "text", "video_url"],
        )
        self.assertEqual(len(session.chat_requests), 1)

    def test_ref2va_expands_image_batches_and_uses_numeric_slot_order(self):
        output = reference_output(include_video=False).replace(
            "<Picture 1> is the visual identity and composition reference for <Subject 1>.",
            "<Picture 1> and <Picture 2> are visual identity and composition references for <Subject 1>.",
        )
        output = output.replace(
            "<Picture 1> ([Shot 1] identity reference): fully_preserved -",
            "<Picture 1> and <Picture 2> ([Shot 1] identity reference): fully_preserved -",
        )
        session = FakeSession(output)
        self.run_enhancer(
            session,
            task_type="Ref2VA",
            reference_images={"reference_image_2": torch.zeros((2, 1, 1, 3))},
        )
        self.assertEqual([upload[0] for upload in session.uploads], ["picture_1.png", "picture_2.png"])

    def test_ref2va_orders_multiple_complete_videos_in_one_request(self):
        output = reference_output().replace(
            "<Video 1> supplies the source action order and cut rhythm.",
            "<Video 1> supplies the first action order.\n<Video 2> supplies the second action order.",
        ).replace(
            "<Video 1> (action and cut structure): weak_reference - its temporal order guides the target sequence.",
            "<Video 1> (first action): weak_reference - its order guides phase one.\n"
            "<Video 2> (second action): weak_reference - its order guides phase two.",
        )
        session = FakeSession(output)
        self.run_enhancer(
            session,
            task_type="Ref2VA",
            reference_images={"reference_image_0": torch.zeros((1, 1, 1, 3))},
            reference_videos={
                "reference_video_10": FakeVideo(b"second-complete-video"),
                "reference_video_2": FakeVideo(b"first-complete-video"),
            },
        )
        self.assertEqual(
            [upload[0] for upload in session.uploads],
            ["picture_1.png", "video_1.mp4", "video_2.mp4"],
        )
        self.assertEqual(session.uploads[1][1], b"first-complete-video")
        self.assertEqual(session.uploads[2][1], b"second-complete-video")
        parts = session.chat_requests[0]["json"]["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts].count("video_url"), 2)
        self.assertEqual(len(session.chat_requests), 1)

    def test_multilingual_intent_and_exact_language_rules_reach_the_model(self):
        output = basic_output().replace(
            "A medium shot shows a cyclist crossing a quiet street under soft daylight.",
            'A woman says <d>[Chinese] 你好，世界！</d> beside the visible sign "星港-7".',
        )
        session = FakeSession(output)
        result = self.run_enhancer(
            session,
            prompt='女孩说“你好，世界！”，画面文字是 "星港-7"。 Keep the camera locked.',
            constraints="对白、标点和画面文字必须逐字保留。",
            rewrite_mode="strict",
        )
        messages = session.chat_requests[0]["json"]["messages"]
        self.assertIn("你好，世界！", messages[1]["content"])
        self.assertIn("星港-7", messages[1]["content"])
        self.assertIn("对白、标点和画面文字必须逐字保留。", messages[1]["content"])
        self.assertIn("Preserve user-provided dialogue, lyrics, and visible on-screen text verbatim", messages[0]["content"])
        self.assertIn("<d>[Chinese] 你好，世界！</d>", result)
        self.assertIn('"星港-7"', result)

    def test_task_specific_missing_or_irrelevant_media_fails_before_network(self):
        cases = [
            {"task_type": "I2VA"},
            {"task_type": "FL2VA", "first_frame": torch.zeros((1, 1, 1, 3))},
            {"task_type": "L2VA"},
            {"task_type": "Ref2VA"},
            {"task_type": "T2VA", "first_frame": torch.zeros((1, 1, 1, 3))},
        ]
        for case in cases:
            with self.subTest(case=case):
                session = FakeSession(basic_output())
                with self.assertRaises(nodes.PromptEnhancerError):
                    self.run_enhancer(session, **case)
                self.assertEqual(session.uploads, [])
                self.assertEqual(session.chat_requests, [])

    def test_duration_word_target_and_shot_count_boundaries(self):
        four_second = FakeSession(basic_output(shots=2))
        self.run_enhancer(four_second, duration_seconds=4)
        fifteen_second_output = basic_output(shots=2).replace("00:03.000", "00:14.999")
        self.run_enhancer(FakeSession(fifteen_second_output), duration_seconds=15)

        for kwargs in (
            {"duration_seconds": 3},
            {"duration_seconds": 16},
            {"description_word_target": 79},
            {"description_word_target": 1001},
            {"shot_count": -1},
            {"shot_count": 21},
            {"shot_count": "many"},
        ):
            with self.subTest(kwargs=kwargs):
                session = FakeSession(basic_output())
                with self.assertRaises(nodes.PromptEnhancerError):
                    self.run_enhancer(session, **kwargs)
                self.assertEqual(session.uploads, [])
                self.assertEqual(session.chat_requests, [])

    def test_ref2va_limits_are_checked_before_upload(self):
        cases = [
            {"reference_images": {"reference_image_0": torch.zeros((10, 1, 1, 3))}},
            {"reference_videos": {f"reference_video_{i}": FakeVideo() for i in range(4)}},
            {"reference_videos": {"reference_video_0": FakeVideo(duration=1.9)}},
            {
                "reference_videos": {
                    "reference_video_0": FakeVideo(duration=8),
                    "reference_video_1": FakeVideo(duration=8),
                }
            },
        ]
        for case in cases:
            with self.subTest(case=list(case)):
                session = FakeSession(reference_output())
                with self.assertRaises(nodes.PromptEnhancerError):
                    self.run_enhancer(session, task_type="Ref2VA", **case)
                self.assertEqual(session.uploads, [])
                self.assertEqual(session.chat_requests, [])

    def test_unsupported_video_never_falls_back_to_frames_or_text(self):
        session = FakeSession(reference_output())
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "MP4, AVI, MOV, or MKV"):
            self.run_enhancer(
                session,
                task_type="Ref2VA",
                reference_videos={"reference_video_0": FakeVideo(container="webm")},
            )
        self.assertEqual(session.uploads, [])
        self.assertEqual(session.chat_requests, [])

    def test_native_trimmed_video_is_rejected_before_untrimmed_source_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mp4"
            live_smoke.make_video_fixture(path)
            trimmed = live_smoke.VideoFromFile(str(path), start_time=1, duration=2)
            session = FakeSession(reference_output())
            with self.assertRaisesRegex(nodes.PromptEnhancerError, "Trimmed VIDEO inputs cannot be uploaded safely"):
                self.run_enhancer(
                    session,
                    task_type="Ref2VA",
                    reference_videos={"reference_video_0": trimmed},
                )
            self.assertEqual(session.uploads, [])
            self.assertEqual(session.chat_requests, [])

    def test_word_target_and_mode_rules_are_in_messages(self):
        session = FakeSession(basic_output_with_word_count())
        self.run_enhancer(session, rewrite_mode="strict", output_language="English", description_word_target=200)
        messages = session.chat_requests[0]["json"]["messages"]
        self.assertIn("Rewrite mode: strict", messages[0]["content"])
        self.assertIn("approximately 200 English words", messages[1]["content"])

    def test_word_target_is_soft_and_short_upstream_output_is_returned(self):
        short_output = basic_output()
        session = FakeSession(short_output)
        self.assertEqual(self.run_enhancer(session, description_word_target=350), short_output)
        self.assertEqual(len(session.chat_requests), 1)

    def test_non_retryable_http_errors_are_actionable_and_do_not_retry_chat(self):
        for status, phrase in ((401, "configured API Key"), (402, "insufficient balance"), (429, "rate limited")):
            with self.subTest(status=status):
                session = FakeSession("", chat_status=status)
                with self.assertRaisesRegex(nodes.PromptEnhancerError, phrase):
                    self.run_enhancer(session)
                self.assertEqual(len(session.chat_requests), 1)

        gateway_response = FakeResponse(502, ValueError("not json"), text="<html><h1>502 Bad Gateway</h1><p>nginx</p></html>")
        gateway = SequencedChatSession([gateway_response, gateway_response, gateway_response])
        with patch.object(nodes.time, "sleep") as sleep:
            with self.assertRaisesRegex(nodes.PromptEnhancerError, "after 3 automatic attempts") as raised:
                self.run_enhancer(gateway)
        self.assertEqual(len(gateway.chat_requests), 3)
        self.assertEqual([args[0] for args, _ in sleep.call_args_list], [0.5, 1.0])
        self.assertNotIn("<html>", str(raised.exception))

    def test_seedance_ssl_retry_returns_the_successful_generation(self):
        expected = basic_output()
        success = FakeResponse(200, {"choices": [{"message": {"content": expected}}]})
        session = SequencedChatSession([
            requests.exceptions.SSLError("regional TLS failure"),
            requests.exceptions.ConnectionError("temporary route reset"),
            success,
        ])
        with patch.object(nodes.time, "sleep") as sleep:
            self.assertEqual(self.run_enhancer(session), expected)
        self.assertEqual(len(session.chat_requests), 3)
        self.assertEqual([args[0] for args, _ in sleep.call_args_list], [0.5, 1.0])

    def test_seedance_gateway_retry_returns_the_successful_generation(self):
        expected = basic_output()
        success = FakeResponse(200, {"choices": [{"message": {"content": expected}}]})
        session = SequencedChatSession([
            FakeResponse(502, {"error": {"message": "bad gateway"}}),
            FakeResponse(504, {"error": {"message": "gateway timeout"}}),
            success,
        ])
        with patch.object(nodes.time, "sleep") as sleep:
            self.assertEqual(self.run_enhancer(session), expected)
        self.assertEqual(len(session.chat_requests), 3)
        self.assertEqual([args[0] for args, _ in sleep.call_args_list], [0.5, 1.0])

    def test_custom_openai_endpoint_does_not_inherit_seedance_paid_retry_policy(self):
        session = SequencedChatSession([
            requests.exceptions.SSLError("custom provider TLS failure"),
            FakeResponse(200, {"choices": [{"message": {"content": basic_output()}}]}),
        ])
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "not retried automatically"):
            nodes._request_completion(
                session,
                "secret-key",
                [{"role": "user", "content": "hello"}],
                "balanced",
                chat_url="https://llm.example/v1/chat/completions",
                provider_name="OpenAI-compatible",
            )
        self.assertEqual(len(session.chat_requests), 1)

    def test_http_error_redacts_api_keys(self):
        leaked_key = "sk-" + "leaked-value-1234567890"
        session = FakeSession(
            "",
            chat_status=401,
            chat_payload={"error": {"message": f"bad secret-key and {leaked_key}"}},
        )
        with self.assertRaises(nodes.PromptEnhancerError) as raised:
            self.run_enhancer(session)
        self.assertNotIn("secret-key", str(raised.exception))
        self.assertNotIn(leaked_key, str(raised.exception))

    def test_timeout_is_not_retried(self):
        session = FakeSession("", chat_exception=requests.exceptions.ReadTimeout("secret-key must not leak"))
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "response state is ambiguous"):
            self.run_enhancer(session)
        self.assertEqual(len(session.chat_requests), 1)

    def test_free_upload_429_retries_once_without_duplicate_chat(self):
        class RateLimitedUploadSession(FakeSession):
            def post(self, url, **kwargs):
                if url == nodes.UPLOAD_URL and not self.uploads:
                    filename, data, mime_type = kwargs["files"]["file"]
                    self.uploads.append((filename, data, mime_type, kwargs))
                    return FakeResponse(429, {"error": {"message": "slow down"}}, headers={"Retry-After": "1"})
                return super().post(url, **kwargs)

        session = RateLimitedUploadSession(basic_output("I2VA"))
        with patch.object(nodes.time, "sleep") as sleep:
            self.run_enhancer(session, task_type="I2VA", first_frame=torch.zeros((1, 1, 1, 3)))
        sleep.assert_called_once_with(1)
        self.assertEqual(len(session.uploads), 2)
        self.assertEqual(len(session.chat_requests), 1)

    def test_invalid_json_and_empty_responses_fail_but_length_content_is_returned(self):
        payloads = [
            ValueError("not json"),
            {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
        ]
        for payload in payloads:
            with self.subTest(payload=type(payload).__name__):
                if isinstance(payload, Exception):
                    session = FakeSession("", chat_payload=payload)
                else:
                    session = FakeSession("", chat_payload=payload)
                with self.assertRaises(nodes.PromptEnhancerError):
                    self.run_enhancer(session)

        truncated = basic_output().replace("non_diegetic_music: N/A", "non_diegetic_music: par")
        session = FakeSession(
            "",
            chat_payload={"choices": [{"finish_reason": "length", "message": {"content": truncated}}]},
        )
        self.assertEqual(self.run_enhancer(session), truncated)

    def test_reasoning_content_is_never_included_in_string_output(self):
        expected = basic_output()
        session = FakeSession(
            "",
            chat_payload={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {
                        "reasoning_content": "private upstream chain of thought",
                        "content": expected,
                    },
                }]
            },
        )
        result = self.run_enhancer(session)
        self.assertEqual(result, expected)
        self.assertNotIn("private upstream chain of thought", result)

    def test_nonempty_upstream_format_variants_are_returned_unchanged(self):
        outputs = [
            basic_output().replace("overall_soundscape:", "missing_soundscape:"),
            basic_output().replace("overall_soundscape: Light traffic and bicycle-chain sounds continue beneath distant birds.", "overall_soundscape: "),
            basic_output().replace("non_diegetic_music: N/A", "non_diegetic_music: "),
            basic_output().replace("[Shot 1]", "[Shot N]"),
            basic_output(shots=2).replace("00:03.000", "00:05.000"),
            basic_output().replace("integrated_multimodal_description:", "Here is the prompt:\nintegrated_multimodal_description:"),
            basic_output(shots=2).replace("00:03.000,", "0:03.000，"),
            basic_output().replace("integrated_multimodal_description:", "**integrated_multimodal_description：**", 1),
            basic_output().replace("\n", "\r\n"),
        ]
        for output in outputs:
            with self.subTest(output=output[:30]):
                self.assertEqual(self.run_enhancer(FakeSession(output)), output)

    def test_complete_out_of_order_i2va_fields_are_reordered(self):
        description = "[Shot 1] A red square moves right."
        soundscape = "A quiet electronic hum."
        music = "N/A"
        upstream_order = (
            f"{nodes.I2VA_INSTRUCTION}\n\n"
            f"overall_soundscape: {soundscape}\n"
            f"non_diegetic_music: {music}\n"
            f"integrated_multimodal_description: {description}"
        )

        result = self.run_enhancer(
            FakeSession(upstream_order),
            task_type="I2VA",
            first_frame=torch.zeros((1, 1, 1, 3)),
        )
        expected = (
            f"{nodes.I2VA_INSTRUCTION}\n\n"
            f"integrated_multimodal_description: {description}\n\n"
            f"overall_soundscape: {soundscape}\n\n"
            f"non_diegetic_music: {music}"
        )
        self.assertEqual(result, expected)

    def test_incomplete_or_duplicate_field_sets_are_returned_unchanged(self):
        expected = basic_output("I2VA")
        missing = expected.replace("overall_soundscape:", "missing_soundscape:")
        duplicate = expected + "\n\noverall_soundscape: duplicate"

        for output in (missing, duplicate):
            with self.subTest(output=output[-80:]):
                result = self.run_enhancer(
                    FakeSession(output),
                    task_type="I2VA",
                    first_frame=torch.zeros((1, 1, 1, 3)),
                )
                self.assertEqual(result, output)

    def test_missing_api_key_fails_without_network(self):
        session = FakeSession(basic_output())
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(nodes.PromptEnhancerError, "SEEDANCE_API_KEY"):
                nodes.enhance_prompt("A cyclist", session=session)
        self.assertEqual(session.uploads, [])
        self.assertEqual(session.chat_requests, [])

    def test_live_smoke_requires_explicit_paid_confirmation(self):
        with patch.object(live_smoke, "run_paid_smoke") as run_paid_smoke:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                live_smoke.main([])
        run_paid_smoke.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            live_smoke.run_paid_smoke()

    def test_ai_workshop_live_smoke_guard_and_visual_evaluator(self):
        smoke_spec = importlib.util.spec_from_file_location(
            "ai_workshop_live_smoke_test_module",
            NODES_PATH.parent / "workshop_live_smoke.py",
        )
        smoke = importlib.util.module_from_spec(smoke_spec)
        smoke_spec.loader.exec_module(smoke)
        verified = (
            f"{smoke.IMAGE_CODE} magenta triangle yellow circle "
            f"{smoke.EARLY_VIDEO_CODE} blue square moves left to right "
            f"{smoke.LATE_VIDEO_CODE} green circle moves top to bottom"
        )
        self.assertEqual(smoke.evaluate_result(verified), [])
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            smoke.run_paid_smoke(False)

    def test_live_smoke_fixture_is_a_four_second_temporal_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.mp4"
            live_smoke.make_video_fixture(path)
            self.assertGreater(path.stat().st_size, 1_000)
            video = live_smoke.av.open(str(path))
            try:
                stream = video.streams.video[0]
                self.assertAlmostEqual(float(stream.duration * stream.time_base), 4.0, places=1)
                self.assertEqual(stream.frames, 96)
                frames = [frame.to_ndarray(format="rgb24") for frame in video.decode(video=0)]
                self.assertEqual(len(frames), 96)
                first_blue = frames[0][175, 80]
                second_green = frames[60][150, 320]
                self.assertGreater(int(first_blue[2]), int(first_blue[0]) + 80)
                self.assertGreater(int(second_green[1]), int(second_green[0]) + 80)
                self.assertGreater(int(frames[0][300, 600].mean()), int(frames[60][300, 600].mean()) + 100)
            finally:
                video.close()

        image = live_smoke.make_image_fixture()[0].numpy()
        triangle = image[150, 190]
        circle = image[170, 490]
        self.assertGreater(float(triangle[0]), float(triangle[1]) + 0.4)
        self.assertGreater(float(circle[0]), 0.8)
        self.assertGreater(float(circle[1]), 0.6)

    def test_live_smoke_result_checks_both_media_and_temporal_order(self):
        valid = (
            "subject_definitions:\n<Picture 1> carries MANGO-47 with a magenta triangle and yellow circle. "
            "<Video 1> carries RIVER-83, with a blue square before a hard cut and then a green circle.\n\n"
            "retention_analysis:\n<Subject 1>: attribute_transfer - picture identity follows video motion.\n\n"
            "detailed_description:\n[Shot 1] In phase one, the magenta triangle moves left-to-right. "
            "[Shot 2] At 00:02.500, a hard cut starts phase two, where the yellow circle moves downward.\n\n"
            "overall_soundscape:\nN/A"
        )
        self.assertEqual(live_smoke.evaluate_result(valid), [])
        failures = live_smoke.evaluate_result(valid.replace("MANGO-47", "missing").replace("blue square", "green circle"))
        self.assertTrue(any("image code" in failure for failure in failures))
        self.assertTrue(any("blue square" in failure for failure in failures))

        real_response = (NODES_PATH.parent / "tests" / "fixtures" / "live_smoke_2026-08-04.txt").read_text(encoding="utf-8")
        self.assertEqual(live_smoke.evaluate_result(real_response), [])


if __name__ == "__main__":
    unittest.main()
