"""CPU contracts, not LLM compliance or rendered emotion measurements."""
from __future__ import annotations

import copy
import importlib
import inspect
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from test_directional_skills import (
    GIT_ROOT, ROOT, RecordingLocalProvider, execute_inputs, h3, h3_args,
    local_parameters, native_draft, original_function, primary_text, relay_draft,
    sd, sd_args, test_seedance20,
)

perf = importlib.import_module(h3.__package__ + ".performance_director")
emotion = importlib.import_module(h3.__package__ + ".emotion_performance")
direction = importlib.import_module(h3.__package__ + ".directional_skills")
BASELINE = "3c3bbae97b32a4981866b73c0991c1adfd7130db"


def enabled():
    return perf.build_performance_director_config(perf.PERFORMANCE_TUDOU)


class EmotionPerformanceTests(unittest.TestCase):
    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("No network in CPU tests")))
        for module in (h3, sd):
            guards.enter_context(patch.object(module, "LocalQwenProvider", side_effect=AssertionError("No real GGUF in CPU tests")))

    def test_native_config_and_source_are_additive(self):
        schema = perf.T8PerformanceDirectorConfig.define_schema()
        self.assertEqual([item.id for item in schema.inputs], ["mode"])
        self.assertEqual(perf.PERFORMANCE_MODES[:4], [perf.PERFORMANCE_AUTO, perf.PERFORMANCE_STRONG, perf.PERFORMANCE_OFF, perf.PERFORMANCE_EXTREME])
        self.assertEqual(perf.PERFORMANCE_MODES[-1], emotion.EMOTION_MODE)
        self.assertEqual(perf.T8PerformanceDirectorConfig.execute()[0], perf.build_performance_director_config())
        self.assertEqual(enabled()["schema_version"], "t8-performance-director-config/v1")
        self.assertEqual(perf.T8PerformanceDirectorConfig.execute(perf.PERFORMANCE_TUDOU)[0], enabled())
        lock = json.loads((ROOT / "research_sources/tudou-emotion.lock.json").read_text(encoding="utf-8"))
        self.assertEqual({item["path"]: item["sha256"] for item in lock["files"]}, emotion.SOURCE_FILES)
        self.assertEqual(lock["adaptation_revision"], emotion.EMOTION_REVISION)
        self.assertNotIn("G:", json.dumps(enabled()))
        self.assertNotIn("repository", enabled()["source"])
        for workflow in ("verify.yml", "publish_action.yml"):
            source = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
            self.assertTrue(any("fetch --no-tags" in line and BASELINE in line for line in source.splitlines()), workflow)

    def test_all_legacy_helpers_and_messages_equal_frozen_release(self):
        for name in ("build_performance_director_config", "h3_performance_instruction", "seedance_performance_instruction", "storyboard_performance_instruction"):
            old = original_function("performance_director.py", name, perf, BASELINE)
            for mode in perf.PERFORMANCE_MODES[:4]:
                with self.subTest(helper=name, mode=mode):
                    if name.startswith("build_"):
                        self.assertEqual(getattr(perf, name)(mode), old(mode))
                    else:
                        cfg = perf.build_performance_director_config(mode)
                        positional = ("MiniMax H3", cfg) if name.startswith("storyboard") else (cfg,)
                        self.assertEqual(getattr(perf, name)(*positional, fixed_shot_count=2, source_prompt="红色瞳孔，原句‘等我。’"), old(*positional, fixed_shot_count=2, source_prompt="红色瞳孔，原句‘等我。’"))
        old_coordinated = original_function("directional_skills.py", "coordinated_performance_instruction", direction, BASELINE)
        for mode in perf.PERFORMANCE_MODES[:4]:
            values = dict(config=perf.build_performance_director_config(mode), source_prompt="保留红衣", shot_count=1, model_target="MiniMax H3")
            self.assertEqual(direction.coordinated_performance_instruction(**values), old_coordinated(**values))
        for module, filename, args in ((h3, "nodes.py", h3_args), (sd, "seedance20.py", sd_args)):
            old = original_function(filename, "_build_messages", module, BASELINE)
            self.assertEqual(inspect.signature(module._build_messages), inspect.signature(old))
            for mode in (None, *[perf.build_performance_director_config(m) for m in perf.PERFORMANCE_MODES[:4]]):
                for skill in direction.DIRECTOR_LABELS:
                    values = args(director_skill=skill, performance_director_config=mode)
                    self.assertEqual(module._build_messages(**values), old(**values))

    def test_shared_method_stays_compact_and_native(self):
        for fn in (perf.h3_performance_instruction, perf.seedance_performance_instruction, perf.storyboard_performance_instruction):
            positional = ("MiniMax H3", enabled()) if fn is perf.storyboard_performance_instruction else (enabled(),)
            rule = fn(*positional, fixed_shot_count=2, source_prompt="瞳孔变金色，原句‘等我。’")
            self.assertEqual(rule.count(emotion.EMOTION_MARKER), 1)
            self.assertLess(len(rule.split()), 1000)
            for requirement in ("Separate emotional quality", "meaningful residue", "once", "closed whitelist", "no reaction", "mask-break", "Relay events are not cuts", "exactly 2 shots", "瞳孔", "等我。"):
                self.assertIn(requirement, rule)
            for excluded in ("six-second", "extraction_only", "[whimpering]", "subject_definitions:", "one primary state change"):
                self.assertNotIn(excluded, rule)
        sd_rule = perf.seedance_performance_instruction(enabled())
        for token in ("<d>", "(S1)", "[Shot 1]", "overall_soundscape:"):
            self.assertNotIn(token, sd_rule)
        ir = perf.storyboard_performance_instruction("MiniMax H3", enabled())
        for field in perf.PERFORMANCE_IR_DEFAULTS:
            self.assertIn(field, ir)
        self.assertIn("add no keys", ir)

    def test_all_tasks_skills_bibles_and_media_keep_original_user_message(self):
        parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}}]
        for module, args, tasks, task_key in ((h3, h3_args, h3.TASK_TYPES, "task_type"), (sd, sd_args, sd.TASK_INTENTS, "task_intent")):
            for task in tasks:
                for skill in direction.DIRECTOR_LABELS:
                    values = args(**{task_key: task}, director_skill=skill, media_parts=parts, shot_count=1)
                    frozen = copy.deepcopy(values)
                    before = module._build_messages(**values)
                    after = module._build_messages(**values, performance_director_config=enabled())
                    self.assertEqual(after[1], before[1])
                    self.assertEqual(after[0]["content"].count(emotion.EMOTION_MARKER), 1)
                    self.assertEqual(values, frozen)
                    self.assertIn(module.COMMON_SYSTEM_RULES, after[0]["content"])
                    if direction.normalize_director_skill(skill) in direction.AUTHORING_SKILLS:
                        self.assertIn("actual user's explicit scope", after[0]["content"])
                    else:
                        self.assertIn("Never invent, extend or rewrite dialogue.", after[0]["content"])

    def test_real_cloud_and_local_message_paths_single_logical_call(self):
        for module, function in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            response = native_draft() if module is h3 else "Shot 1: The woman retains the ticket and continues walking."
            values = dict(prompt="Keep the ticket.", output_language="English", performance_director_config=enabled())
            session = test_seedance20.SequencedChatSession([response])
            self.assertEqual(function(**values, session=session, api_key="test-placeholder"), response)
            self.assertEqual(len(session.chat_requests), 1)
            self.assertEqual(session.chat_requests[0]["json"]["messages"][0]["content"].count(emotion.EMOTION_MARKER), 1)
            providers = []
            def factory(settings, *, vision):
                provider = RecordingLocalProvider(settings, vision=vision, responses=[response])
                providers.append(provider)
                return provider
            with patch.object(module, "LocalQwenProvider", side_effect=factory), patch.object(module, "_build_messages", wraps=module._build_messages) as builds:
                self.assertEqual(function(**values, api_mode=module.LOCAL_QWEN_API_MODE, **local_parameters(module)), response)
            self.assertEqual(builds.call_count, 2)
            self.assertEqual(len(providers[0].calls), 1)
            self.assertTrue(providers[0].closed)
            self.assertEqual(providers[0].calls[0]["messages"][0]["content"].count(emotion.EMOTION_MARKER), 1)

    def test_bible_camera_causal_combinations_do_not_replace_each_other(self):
        film = importlib.import_module(h3.__package__ + ".film_workflow")
        camera = importlib.import_module(h3.__package__ + ".combat_camera")
        bibles = film.build_character_performance_set([
            film.build_character_performance_bible("Alice", "让Bob等她", "门仍关闭", voice_lock="Alice低声", tactics="询问\n请求"),
            film.build_character_performance_bible("Bob", "等Alice", "门仍关闭", voice_lock="Bob清楚", gaze_and_listening="不回应，不说话"),
        ])
        cfg = camera.build_combat_camera_config(mode=camera.CAMERA_STRONG)
        for module, args, target in ((h3, h3_args, "h3"), (sd, sd_args, "seedance20")):
            for skill in ("none", "drama_scene", "situational_drama", "wushu_combat"):
                values = args(director_skill=skill, creation_mode="causal", character_performance_bible=bibles, performance_director_config=enabled(), combat_camera_config=cfg)
                messages = module._build_messages(**values)
                self.assertEqual(messages[0]["content"].count(emotion.EMOTION_MARKER), 1)
                self.assertIn(camera.combat_camera_instruction(cfg, target), messages[0]["content"])
                for term in ("Alice低声", "Bob清楚", "不回应", "询问", "请求", "CAUSAL"):
                    self.assertIn(term, messages[0]["content"])
                self.assertIn("every listed character separate", messages[0]["content"])

    def test_language_repair_keeps_method_without_duplicate_media(self):
        for module, args, function in ((h3, h3_args, h3.enhance_prompt), (sd, sd_args, sd.enhance_seedance20_prompt)):
            original = module._build_messages(**args(media_parts=[{"type": "image_url", "image_url": {"url": "private-image"}}]), performance_director_config=enabled())
            repair = module.preserve_director_on_repair([{"role": "system", "content": "repair"}, {"role": "user", "content": "draft"}], original, "none", performance_director_config=enabled())
            self.assertEqual(repair[0]["content"].count(emotion.EMOTION_MARKER), 1)
            self.assertIn(primary_text(original[1]["content"]), repair[1]["content"])
            self.assertNotIn("private-image", str(repair))
            responses = [native_draft(), native_draft(True)] if module is h3 else ["Shot 1: The woman holds the ticket and walks slowly beside the station wall without changing her identity or adding another person. The camera follows her steady forward motion while her gaze remains directed toward the closed doorway at the end of the corridor.", "镜头1：女人持稳车票沿站墙向前走。"]
            for local in (False, True):
                values = dict(prompt="保留人物和车票。", output_language="中文", performance_director_config=enabled())
                if not local:
                    session = test_seedance20.SequencedChatSession(responses)
                    result = function(**values, session=session, api_key="test-placeholder")
                    messages = [item["json"]["messages"] for item in session.chat_requests]
                else:
                    providers = []
                    def factory(settings, *, vision):
                        provider = RecordingLocalProvider(settings, vision=vision, responses=responses)
                        providers.append(provider)
                        return provider
                    with patch.object(module, "LocalQwenProvider", side_effect=factory):
                        result = function(**values, api_mode=module.LOCAL_QWEN_API_MODE)
                    messages = [item["messages"] for item in providers[0].calls]
                    self.assertTrue(providers[0].closed)
                self.assertEqual(result, responses[-1])
                self.assertEqual(len(messages), 2)
                self.assertEqual(messages[1][0]["content"].count(emotion.EMOTION_MARKER), 1)

    def test_relay_and_quality_repairs_keep_method_and_last_complete_draft(self):
        broken = json.loads(relay_draft())
        broken["native_prompt"] = ""
        responses = [json.dumps(broken), relay_draft(), relay_draft(True)]
        session = test_seedance20.SequencedChatSession(responses)
        self.assertEqual(h3.enhance_prompt("保留红色袖口。", output_language="中文", duration_seconds=8, performance_director_config=enabled(), relay_config={"event_count": 2, "time_ranges": "0-4\n4-8"}, session=session, api_key="test-placeholder"), responses[-1])
        self.assertEqual(len(session.chat_requests), 3)
        for call in session.chat_requests:
            self.assertEqual(call["json"]["messages"][0]["content"].count(emotion.EMOTION_MARKER), 1)
        pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
        messages = h3._build_messages(**h3_args(), performance_director_config=enabled())
        complete = Mock(side_effect=RuntimeError("offline correction failure"))
        result, report = pipeline.h3_quality_result(native_draft(), mode="repair", messages=messages, complete=complete, task_type="T2VA", duration=12, shot_count=2, language="AUTO", source="")
        self.assertEqual(result, native_draft())
        self.assertEqual(report["result"], "correction_failed_draft_kept")
        complete.assert_called_once()
        self.assertEqual(complete.call_args.args[0][:2], messages)

    def test_preflight_and_recovery_are_safe_and_metadata_atomic(self):
        recovery = sys.modules[h3.begin_recovery_record.__module__]
        metadata = perf.performance_metadata(enabled())
        self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
        for item in ({"emotion_strategy": "tudou_emotion"}, {"emotion_revision": "1.0.0"}, {**metadata, "emotion_revision": "future"}):
            self.assertEqual(recovery.safe_director_metadata(item), {})
        self.assertEqual(perf.performance_metadata(None), {})
        for module, cls, function in ((h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt"), (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            component = cls.define_schema().node_id
            slot = "emotion-preflight-" + component
            module.begin_recovery_record(component, slot, "test-provider", metadata=metadata)
            module.complete_recovery_record(component, slot, ("previous paid result",))
            before = recovery.recovery_status(component, slot)
            with patch.object(module, function, side_effect=AssertionError("No provider")), patch.object(module, "begin_recovery_record", wraps=module.begin_recovery_record) as begin:
                with self.assertRaises(module.PromptEnhancerError):
                    cls.execute(**execute_inputs(module), recovery_slot=slot, performance_director_config={"schema_version": "future"})
            begin.assert_not_called()
            self.assertEqual(recovery.recovery_status(component, slot), before)
            with patch.object(module, function, side_effect=AssertionError("Recovery must not regenerate")):
                result = cls.execute(**execute_inputs(module), recovery_slot=slot, recovery_action="restore_last", performance_director_config={"schema_version": "future"})
            self.assertEqual(result[0], "previous paid result")

    def test_storyboard_uses_existing_compact_ir_and_single_call(self):
        creative = importlib.import_module(h3.__package__ + ".creative_suite")
        result_type = creative.CompletionResult
        payload = {"global_prompt": "人物保持克制", "shots": [{"index": 1, "start_seconds": 0, "end_seconds": 8, "subject_action": "含泪说完原句", "dramatic_trigger": "已有等待", "reception_beat": "看向门", "primary_performance_beat": "低声回应", "observable_cues": ["视线", "嘴型"], "speech_span": "原句", "state_transition_strategy": "紧张残留"}]}
        with patch.object(creative, "_run_completion", return_value=result_type(text=json.dumps(payload), provider="test-provider")) as call:
            result = creative.T8StoryboardPack.execute("保留原句和紧张余绪。", duration_seconds=8, shot_count="1", performance_director_config=enabled())
        call.assert_called_once()
        self.assertEqual(call.call_args.kwargs["system"].count(emotion.EMOTION_MARKER), 1)
        self.assertEqual(call.call_args.kwargs["max_output_tokens"], 2048)
        self.assertEqual(json.loads(result[1])["shots"][0]["state_transition_strategy"], "紧张残留")

    def test_widgets_and_bundled_workflows_are_byte_frozen(self):
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASELINE, "--", "example_workflows", "web/js/minimax_h3_prompt_enhancer.js", "web/js/seedance20_prompt_enhancer.js"], cwd=GIT_ROOT, text=True).splitlines()
        for path in paths:
            if path.endswith((".json", ".js")):
                old = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=GIT_ROOT).replace(b"\r\n", b"\n")
                current=(ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                if path == "web/js/minimax_h3_prompt_enhancer.js":
                    for addition in ('    Hybrid: "Hybrid（关键帧+参考混合生成）",\n',
                                     '                if (["hybrid", "Hybrid — 关键帧+参考混合生成"].includes(taskTypeWidget?.value)) taskTypeWidget.value = TASK_TYPE_LABELS.Hybrid;\n'):
                        encoded=addition.encode("utf8")
                        self.assertEqual(current.count(encoded),1)
                        current=current.replace(encoded,b"")
                self.assertEqual(current, old, path)


if __name__ == "__main__":
    unittest.main()
