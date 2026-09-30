"""CPU transport/compatibility contracts; no LLM or rendered-quality claims."""
from __future__ import annotations

import ast
import asyncio
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
from performance_director import PERFORMANCE_EXTREME, build_performance_director_config

camera = importlib.import_module(h3.__package__ + ".combat_camera")
BASELINE = "db1121b99730a570bff0c84cc854c0c6948eed77"


def enabled():
    return camera.build_combat_camera_config(
        mode=camera.CAMERA_STRONG, continuity=camera.CONTINUITY_CONTINUOUS,
        impact=camera.IMPACT_STYLIZED,
    )


class CombatCameraTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("CPU tests forbid network")))
        for module in (h3, sd):
            self.guards.enter_context(patch.object(module, "LocalQwenProvider", side_effect=AssertionError("CPU tests forbid real GGUF load")))

    def test_config_has_three_native_widgets_and_finite_payload(self):
        schema = camera.T8CombatCameraConfig.define_schema()
        self.assertEqual(schema.node_id, "T8CombatCameraConfig")
        self.assertEqual([item.id for item in schema.inputs], ["mode", "continuity", "impact"])
        payload = camera.T8CombatCameraConfig.execute()[0]
        self.assertEqual(payload, camera.build_combat_camera_config())
        self.assertEqual(set(payload), {"schema_version", "mode", "continuity", "impact"})
        self.assertEqual(payload["schema_version"], "t8-combat-camera-config/v1")
        self.assertIsNone(camera.resolve_combat_camera_config(None))
        self.assertIsNone(camera.resolve_combat_camera_config(camera.build_combat_camera_config(mode=camera.CAMERA_OFF)))
        valid = enabled()
        normalized = camera.resolve_combat_camera_config({**valid, "instruction": "PRIVATE_SENTINEL"})
        self.assertEqual(normalized, valid)
        self.assertIsNot(normalized, valid)
        self.assertNotIn("PRIVATE_SENTINEL", camera.combat_camera_instruction({**valid, "instruction": "PRIVATE_SENTINEL"}))

    def test_invalid_inputs_do_not_echo_arbitrary_values(self):
        for invalid in (False, 1, [], "PRIVATE_SENTINEL", {},
                        {**enabled(), "schema_version": "PRIVATE_SENTINEL"},
                        {**enabled(), "mode": "PRIVATE_SENTINEL"},
                        {**enabled(), "continuity": []}, {**enabled(), "impact": "PRIVATE_SENTINEL"}):
            with self.subTest(value=invalid), self.assertRaises(ValueError) as caught:
                camera.resolve_combat_camera_config(invalid)
            self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))

    def test_live_regression_contract_preserves_wardrobe_and_eye_owned_hands(self):
        for target in ("h3", "seedance20"):
            rule = camera.combat_camera_instruction(enabled(), target)
            self.assertIn("sleeve is clothing", rule)
            self.assertIn("near-miss as a near-miss", rule)
            self.assertIn("requested total duration and shot count", rule)
            self.assertIn("not a handheld camera operator", rule)
            self.assertIn("hands or held objects may remain in view", rule)
        self.assertEqual(camera.combat_camera_instruction(None), "")
        self.assertEqual(camera.combat_camera_instruction(camera.build_combat_camera_config(mode=camera.CAMERA_OFF)), "")

    def test_unconnected_and_off_messages_match_published_baseline(self):
        for module, filename, args in ((h3, "nodes.py", h3_args), (sd, "seedance20.py", sd_args)):
            old = original_function(filename, "_build_messages", module, BASELINE)
            for skill in ("none", "continuous_combat", "high_density_combat", "cinematic_gunfight", "ning_wenwu", "drama_scene", "situational_drama", "zhenzhen_pov"):
                for language in ("中文", "English"):
                    values = args(director_skill=skill, shot_count=1, output_language=language,
                                  performance_director_config=build_performance_director_config(PERFORMANCE_EXTREME))
                    expected = old(**values)
                    for config in (None, camera.build_combat_camera_config(mode=camera.CAMERA_OFF)):
                        with self.subTest(target=filename, skill=skill, language=language, config=config):
                            self.assertEqual(module._build_messages(**values, combat_camera_config=config), expected)

    def test_modifier_keeps_existing_source_and_media_contract(self):
        parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,fixture"}}]
        for module, args, target in ((h3, h3_args, "h3"), (sd, sd_args, "seedance20")):
            rule = camera.combat_camera_instruction(enabled(), model_target=target)
            self.assertTrue(rule)
            self.assertLess(len(rule.split()), 1000)
            for skill, shots in (("none", 0), ("none", 3), ("continuous_combat", 1), ("zhenzhen_pov", 2)):
                values = args(director_skill=skill, shot_count=shots, media_parts=parts,
                              prompt="固定机位，独自练拳，不增加对手；最后站稳。")
                frozen = copy.deepcopy(values)
                before = module._build_messages(**values)
                after = module._build_messages(**values, combat_camera_config=enabled())
                self.assertEqual(after[1], before[1])
                self.assertEqual(after[0]["content"].count(rule), 1)
                self.assertEqual(values, frozen)
                self.assertIn(module.COMMON_SYSTEM_RULES, after[0]["content"])
                self.assertEqual(after[1]["content"][1:], parts)

    def test_all_seedance_tasks_keep_native_task_binding(self):
        plan = [{"label": "@视频1", "kind": "video", "role": "track source video 1"},
                {"label": "@视频2", "kind": "video", "role": "track source video 2"}]
        for task in sd.TASK_INTENTS:
            messages = sd._build_messages(**sd_args(task_intent=task, media_plan=plan), combat_camera_config=enabled())
            self.assertIn(sd.TASK_RULES[task], messages[0]["content"])
            self.assertIn(sd._task_asset_instruction(task, plan), messages[0]["content"])
        rule = camera.combat_camera_instruction(enabled(), model_target="seedance20")
        for forbidden in ("subject_definitions:", "<d>", "[Shot 1]", "0.15", "0.3"):
            self.assertNotIn(forbidden, rule)

    def test_published_workflows_and_main_widget_serializers_remain_unchanged(self):
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", BASELINE, "--", "example_workflows"],
            cwd=GIT_ROOT, text=True,
        ).splitlines()
        paths += ["web/js/minimax_h3_prompt_enhancer.js", "web/js/seedance20_prompt_enhancer.js"]
        for path in paths:
            if not path.endswith((".json", ".js")):
                continue
            with self.subTest(path=path):
                published = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=GIT_ROOT)
                self.assertEqual((ROOT / path).read_bytes().replace(b"\r\n", b"\n"), published.replace(b"\r\n", b"\n"))

    def test_execute_passes_active_config_without_changing_output_contract(self):
        for module, cls, function in ((h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                                      (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            with patch.object(module, function, return_value="completed native prompt") as complete:
                output = cls.execute(**execute_inputs(module), combat_camera_config=enabled())
            self.assertEqual(complete.call_args.kwargs["combat_camera_config"], enabled())
            self.assertEqual(tuple(output.result), ("completed native prompt", "", "", "", 0, "") if module is h3 else ("completed native prompt",))

    def test_six_budget_local_and_cloud_build_paths_keep_same_config_and_call_count(self):
        for module, target, function in ((h3, "h3", h3.enhance_prompt), (sd, "seedance20", sd.enhance_seedance20_prompt)):
            response = native_draft() if module is h3 else "Shot 1: The woman holds the ticket while stepping forward."
            rule = camera.combat_camera_instruction(enabled(), model_target=target)
            inputs = dict(prompt="Keep the red sleeve and ticket.", output_language="English", combat_camera_config=enabled())
            with self.subTest(target=target, provider="cloud"):
                session = test_seedance20.SequencedChatSession([response])
                with patch.object(module, "_build_messages", wraps=module._build_messages) as builds:
                    result = function(**inputs, session=session, api_key="test-placeholder")
                self.assertEqual(result, response)
                self.assertEqual(len(session.chat_requests), 1)
                self.assertEqual(builds.call_count, 1)
                self.assertIn(rule, session.chat_requests[0]["json"]["messages"][0]["content"])
            with self.subTest(target=target, provider="local"):
                providers = []
                def factory(settings, *, vision):
                    provider = RecordingLocalProvider(settings, vision=vision, responses=[response])
                    providers.append(provider)
                    return provider
                with patch.object(module, "LocalQwenProvider", side_effect=factory), \
                        patch.object(module, "_build_messages", wraps=module._build_messages) as builds, \
                        patch.object(module, "local_visual_part_budget", wraps=module.local_visual_part_budget) as budget:
                    result = function(**inputs, api_mode=module.LOCAL_QWEN_API_MODE, **local_parameters(module))
                self.assertEqual(result, response)
                self.assertEqual(builds.call_count, 2)
                for call in builds.call_args_list:
                    bound = inspect.signature(builds._mock_wraps).bind(*call.args, **call.kwargs).arguments
                    self.assertEqual(bound["combat_camera_config"], enabled())
                self.assertEqual(len(providers), 1)
                self.assertTrue(providers[0].closed)
                self.assertEqual(len(providers[0].calls), 1)
                sent = providers[0].calls[0]["messages"]
                self.assertIn(rule, sent[0]["content"])
                self.assertEqual(budget.call_args.args[0][0], sent[0])

    def test_camera_only_language_repair_retains_rules_once_without_readding_images(self):
        parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,fixture"}}]
        for module, args, target in ((h3, h3_args, "h3"), (sd, sd_args, "seedance20")):
            for skill in ("none", "high_density_combat"):
                original = module._build_messages(**args(director_skill=skill, media_parts=parts), combat_camera_config=enabled())
                frozen = copy.deepcopy(original)
                raw = [{"role": "system", "content": "Repair language only"}, {"role": "user", "content": "draft"}]
                repair = module.preserve_director_on_repair(raw, original, skill, combat_camera_config=enabled())
                rule = camera.combat_camera_instruction(enabled(), model_target=target)
                self.assertEqual(repair[0]["content"].count(rule), 1)
                self.assertIn(primary_text(original[1]["content"]), repair[1]["content"])
                self.assertTrue(all(isinstance(message["content"], str) for message in repair))
                self.assertEqual(original, frozen)
            self.assertIs(module.preserve_director_on_repair(raw, original, "none", combat_camera_config=None), raw)

    def test_language_repair_is_wired_through_both_transports(self):
        for module, target, function in ((h3, "h3", h3.enhance_prompt), (sd, "seedance20", sd.enhance_seedance20_prompt)):
            responses = [native_draft(), native_draft(True)] if module is h3 else [
                "Shot 1: The woman holds the ticket securely in her right hand and moves forward beside the station wall, keeping the red sleeve visible while the camera follows her existing motion.",
                "镜头1：女人保留红色袖口，持稳车票向前走。"]
            for transport in ("cloud", "local"):
                with self.subTest(target=target, transport=transport):
                    inputs = dict(prompt="保留红色袖口，不加对手。", output_language="中文", combat_camera_config=enabled())
                    if transport == "cloud":
                        session = test_seedance20.SequencedChatSession(responses)
                        result = function(**inputs, session=session, api_key="test-placeholder")
                        messages = [call["json"]["messages"] for call in session.chat_requests]
                    else:
                        providers = []
                        def factory(settings, *, vision):
                            provider = RecordingLocalProvider(settings, vision=vision, responses=responses)
                            providers.append(provider)
                            return provider
                        with patch.object(module, "LocalQwenProvider", side_effect=factory):
                            result = function(**inputs, api_mode=module.LOCAL_QWEN_API_MODE)
                        messages = [call["messages"] for call in providers[0].calls]
                        self.assertTrue(providers[0].closed)
                    self.assertEqual(result, responses[-1])
                    self.assertEqual(len(messages), 2)
                    rule = camera.combat_camera_instruction(enabled(), model_target=target)
                    self.assertEqual(messages[1][0]["content"].count(rule), 1)

    def test_relay_format_and_language_repair_keep_modifier(self):
        malformed = json.loads(relay_draft())
        malformed["native_prompt"] = ""
        responses = [json.dumps(malformed), relay_draft(), relay_draft(True)]
        session = test_seedance20.SequencedChatSession(responses)
        result = h3.enhance_prompt("保留红色袖口。", output_language="中文", duration_seconds=8,
                                  combat_camera_config=enabled(), relay_config={"event_count": 2, "time_ranges": "0-4\n4-8"},
                                  session=session, api_key="test-placeholder")
        self.assertEqual(result, responses[-1])
        self.assertEqual(len(session.chat_requests), 3)
        rule = camera.combat_camera_instruction(enabled(), model_target="h3")
        for call in session.chat_requests:
            self.assertEqual(call["json"]["messages"][0]["content"].count(rule), 1)

    def test_quality_correction_carries_existing_messages_without_extra_camera_pass(self):
        pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
        messages = h3._build_messages(**h3_args(), combat_camera_config=enabled())
        complete = Mock(side_effect=RuntimeError("offline correction failure"))
        draft = native_draft()
        result, report = pipeline.h3_quality_result(draft, mode="repair", messages=messages, complete=complete,
                                                   task_type="T2VA", duration=12, shot_count=2, language="AUTO", source="")
        self.assertEqual(result, draft)
        self.assertEqual(report["result"], "correction_failed_draft_kept")
        complete.assert_called_once()
        corrected_messages = complete.call_args.args[0]
        self.assertEqual(corrected_messages[:2], messages)

    def test_invalid_config_fails_before_provider_and_preserves_prior_recovery(self):
        for module, cls, function in ((h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt"), (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            recovery = sys.modules[module.begin_recovery_record.__module__]
            component = cls.define_schema().node_id
            slot = "combat-preserve-" + component
            module.begin_recovery_record(component, slot, "test-provider", metadata=camera.camera_metadata(enabled()))
            module.complete_recovery_record(component, slot, ("previous paid result",))
            before = recovery.recovery_status(component, slot)
            with patch.object(module, function, side_effect=AssertionError("No provider after invalid config")) as generate, \
                    patch.object(module, "begin_recovery_record", wraps=module.begin_recovery_record) as begin:
                with self.assertRaises(module.PromptEnhancerError):
                    cls.execute(**execute_inputs(module), recovery_slot=slot, combat_camera_config={"schema_version": "future"})
            generate.assert_not_called()
            begin.assert_not_called()
            self.assertEqual(recovery.recovery_status(component, slot), before)
            with patch.object(module, function, side_effect=AssertionError("Recovery must not regenerate")):
                result = cls.execute(**execute_inputs(module), recovery_slot=slot, recovery_action="restore_last",
                                     combat_camera_config={"schema_version": "future"})
            self.assertEqual(tuple(result.result), ("previous paid result", "", "", "", 0, "") if module is h3 else ("previous paid result",))
            upload_name = "_upload_media_plan" if module is h3 else "_upload_seedance20_media_plan"
            with patch.object(module, upload_name, side_effect=AssertionError("No media before invalid config")), \
                    patch.object(module, "LocalQwenProvider", side_effect=AssertionError("No runtime before invalid config")):
                with self.assertRaises(module.PromptEnhancerError):
                    getattr(module, function)(prompt="test", combat_camera_config={"schema_version": "future"}, api_mode=module.LOCAL_QWEN_API_MODE)

    def test_camera_metadata_is_atomic_and_old_director_summary_is_unchanged(self):
        recovery = sys.modules[h3.begin_recovery_record.__module__]
        metadata = camera.camera_metadata(enabled())
        self.assertEqual(set(metadata), {"combat_camera_mode", "combat_camera_continuity", "combat_camera_impact", "combat_camera_revision"})
        self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
        self.assertEqual(camera.camera_metadata(None), {})
        self.assertEqual(camera.camera_metadata(camera.build_combat_camera_config(mode=camera.CAMERA_OFF)), {})
        old = {"director_skill": "high_density_combat", "director_revision": "1.0.0", "effective_shot_count": 2}
        self.assertEqual(recovery.safe_director_metadata({**old, **metadata, "prompt": "PRIVATE"}), {**old, **metadata})
        for field in metadata:
            incomplete = {key: value for key, value in metadata.items() if key != field}
            self.assertEqual(recovery.safe_director_metadata(incomplete), {})
            self.assertEqual(recovery.safe_director_metadata({**old, **incomplete}), old)

    def test_schema_signatures_and_registration_append_without_reordering(self):
        for module, filename, cls, name in ((h3, "nodes.py", h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                                            (sd, "seedance20.py", sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            source = subprocess.check_output(["git", "show", f"{BASELINE}:{filename}"], cwd=GIT_ROOT).decode("utf-8")
            tree = ast.parse(source)
            for function in (name, "_build_messages"):
                old = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function)
                names = [arg.arg for arg in old.args.args]
                current = list(inspect.signature(getattr(module, function)).parameters)
                self.assertEqual(current, names + ["combat_camera_config"])
            old_cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls.__name__)
            old_schema = next(node for node in old_cls.body if isinstance(node, ast.FunctionDef) and node.name == "define_schema")
            old_schema.decorator_list = []
            namespace = dict(vars(module))
            exec(compile(ast.Module(body=[old_schema], type_ignores=[]), filename, "exec"), namespace)
            old_inputs = [item.id for item in namespace["define_schema"](cls).inputs]
            current_inputs = [item.id for item in cls.define_schema().inputs]
            self.assertEqual(current_inputs, old_inputs + ["combat_camera_config"])
        package = sys.modules[h3.__package__]
        extension = asyncio.run(package.comfy_entrypoint())
        current_ids = [cls.define_schema().node_id for cls in asyncio.run(extension.get_node_list())]
        old_init = subprocess.check_output(["git", "show", f"{BASELINE}:__init__.py"], cwd=GIT_ROOT).decode("utf-8")
        old_tree = ast.parse(old_init)
        old_cls = next(node for node in old_tree.body if isinstance(node, ast.ClassDef) and node.name == "T8PromptEnhancerExtension")
        method = next(node for node in old_cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_node_list")
        namespace = dict(vars(package))
        exec(compile(ast.Module(body=[method], type_ignores=[]), "__init__.py", "exec"), namespace)
        old_ids = [cls.define_schema().node_id for cls in asyncio.run(namespace["get_node_list"](extension))]
        self.assertEqual(len(old_ids), 28)
        self.assertEqual(current_ids, old_ids + ["T8CombatCameraConfig"])


if __name__ == "__main__":
    unittest.main()
