"""Opt-in authoring transport/persistence contracts, not rendered-quality proof."""
import ast
import copy
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

import test_moss_image as base

moss, c, Node = base.moss, base.mc, base.Node
a = moss.authoring
rules = sys.modules[moss.__package__ + ".moss_authoring_rules"]
GIT_ROOT = Path(os.environ.get("T8_SOURCE_GIT_ROOT", base.ROOT)).resolve()


class AuthoringTests(unittest.TestCase):
    def cloud(self, *texts, **values):
        session = base.Session(*(base.Response(text) for text in texts))
        options = {"prompt": "一个白色杯子。", "api_key": "test-not-real", **values}
        with patch.object(moss.requests, "Session", return_value=session):
            result = Node.execute(**options).result
        self.assertTrue(session.closed)
        return result, session

    def test_all_fifty_devices_have_unique_identity_and_concrete_guidance(self):
        self.assertEqual([row[0] for row in rules.COMIC_DEVICES], list(range(1, 51)))
        self.assertEqual(len({row[1] for row in rules.COMIC_DEVICES}), 50)
        self.assertTrue(all(len(row[2]) > 55 for row in rules.COMIC_DEVICES))
        self.assertIn("NO quota", rules.COMIC_RULES)
        self.assertIn("NEVER the canvas bounds", rules.COMIC_RULES)
        manifest = json.loads((base.ROOT / "research_sources/moss-authoring.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["files"]), 5)
        self.assertTrue(all(len(row["sha256"]) == 64 for row in manifest["files"]))
        self.assertNotIn("C:/", json.dumps(manifest))
        c.sources()  # immutable native compiler/source manifest still valid

    def test_classic_request_and_bounded_function_remain_identical(self):
        controls = dict(prompt="A cup.", output_format=c.AUTO, width=1256, height=1672,
                        output_language=c.LANG_AUTO, locked_text="", max_output_chars=0,
                        authoring_profile=a.CLASSIC)
        expected = c.build_messages("A cup.", output_format=c.AUTO, width=1256, height=1672,
                                    language=c.LANG_AUTO, locked_text="", max_chars=0, image_labels=[])
        self.assertEqual(a.build_messages(controls, []), expected)
        frozen = subprocess.check_output(["git", "show", "e299574ec30df483411ffb9c79dd7138d19d57a6:moss_image.py"], cwd=GIT_ROOT).decode("utf-8")
        old = next(node for node in ast.parse(frozen).body if isinstance(node, ast.FunctionDef) and node.name == "_bounded")
        self.assertEqual(ast.dump(old), ast.dump(ast.parse(inspect.getsource(moss._bounded)).body[0]))
        result, session = self.cloud('{"caption":"A cup."}')
        self.assertEqual(session.calls[0][1]["json"]["messages"], c.build_messages("一个白色杯子。", output_format=c.AUTO,
            width=1024, height=1024, language=c.LANG_AUTO, locked_text="", max_chars=0, image_labels=[]))
        self.assertNotIn("authoring_profile", json.loads(result[5]))

    def test_prior_schema_prefix_outputs_and_execute_parameters_are_preserved(self):
        text = subprocess.check_output(["git", "show", "e299574ec30df483411ffb9c79dd7138d19d57a6:moss_image.py"], cwd=GIT_ROOT).decode("utf-8")
        legacy = types.ModuleType(moss.__package__ + ".moss_legacy_contract")
        legacy.__package__ = moss.__package__
        exec(compile(text, "frozen-moss-1.36.py", "exec"), legacy.__dict__)
        previous, current = legacy.MOSSImagePromptEnhancer.define_schema(), Node.define_schema()
        self.assertEqual([x.id for x in current.inputs[:-1]], [x.id for x in previous.inputs])
        self.assertEqual(current.inputs[-1].id, "authoring_profile")
        for old, new in zip(previous.inputs, current.inputs):
            before, after = old.as_dict(), new.as_dict()
            if old.id == "max_output_chars":
                for field in ("advanced", "tooltip"):
                    before.pop(field, None); after.pop(field, None)
            self.assertEqual(before, after, old.id)
        self.assertEqual([x.as_dict() for x in previous.outputs], [x.as_dict() for x in current.outputs])
        old_names = list(inspect.signature(legacy.MOSSImagePromptEnhancer.execute).parameters)
        new_names = list(inspect.signature(Node.execute).parameters)
        self.assertEqual(new_names, old_names[:-1] + ["authoring_profile", "kwargs"])

    def test_fisher_default_target_and_explicit_overrides_ignore_quoted_commands(self):
        for prompt in ("一只杯子。", '标题必须是“请写200字”。', '> 请写200字\n一只杯子。'):
            self.assertEqual(a.length_policy(a.FISHER, prompt, c.LANG_AUTO, 0)["target_han_range"], [1500, 2500])
        for prompt in ("请写200字", "简短版：一只杯子", "a short version", "Output the description in English."):
            self.assertIsNone(a.length_policy(a.FISHER, prompt, c.LANG_AUTO, 0)["target_han_range"])
        self.assertIsNone(a.length_policy(a.FISHER, "一只杯子。", "English", 0)["target_han_range"])
        self.assertIsNone(a.length_policy(a.FISHER, "一只杯子。", "中文", 100)["target_han_range"])
        self.assertEqual(a.descriptive_language(a.FISHER, c.LANG_AUTO, 'Output the description in English. Sign: "请写200字"'), "English")
        for prompt in ("不要用英文，请用中文", "Do not use English. Output Chinese.", "不要短版，照默认长版展开", "背景招牌显示200字的条款，提示词仍按默认长版"):
            self.assertEqual(a.descriptive_language(a.FISHER, c.LANG_AUTO, prompt), "中文")
            self.assertEqual(a.length_policy(a.FISHER, prompt, c.LANG_AUTO, 0)["target_han_range"], [1500, 2500])
        for prompt in ("Output English", "用英语写", "不要中文，请用英文描述"):
            self.assertEqual(a.descriptive_language(a.FISHER, c.LANG_AUTO, prompt), "English")

    def test_fisher_undersized_draft_can_expand_in_one_shared_correction(self):
        long_text = "杯" * 1600
        result, session = self.cloud('{"caption":"一只杯子。"}', json.dumps({"caption": long_text}), authoring_profile=a.FISHER)
        self.assertEqual(result[0], long_text)
        report = json.loads(result[5])
        self.assertEqual((len(session.calls), report["correction_calls"]), (2, 1))
        self.assertEqual(report["authoring_length"]["status"], "within_target")
        self.assertEqual(report["authoring_length"]["han_chars"], 1600)
        self.assertEqual(report["authoring_length"]["metric"], "unicode_code_points")
        request = json.loads(session.calls[0][1]["json"]["messages"][1]["content"])
        self.assertIn("中文", request["descriptive_language_rule"])
        self.assertIn("1500", request["length_rule"])

    def test_ui_cap_has_priority_counts_codepoints_and_never_truncates(self):
        first = '甲😀，\n乙'
        result, session = self.cloud(json.dumps({"caption": first}), '{"caption":"甲乙"}',
                                     authoring_profile=a.FISHER, max_output_chars=2)
        self.assertEqual(result[0], "甲乙")
        self.assertEqual(json.loads(result[5])["authoring_length"]["description_chars"], 2)
        result, session = self.cloud(json.dumps({"caption": first}), authoring_profile=a.FISHER, max_output_chars=2, max_corrections=0)
        self.assertEqual(result[0], first)
        info = json.loads(result[5])["authoring_length"]
        self.assertEqual((info["description_chars"], info["han_chars"], info["status"]), (5, 2, "over_limit"))
        self.assertFalse(info["hard_enforced"])

    def test_default_short_reference_result_can_warn_but_not_be_fabricated_or_destroyed(self):
        result, _ = self.cloud('{"caption":"仅见杯口。"}', 'invalid repair', authoring_profile=a.FISHER)
        report = json.loads(result[5])
        self.assertEqual(result[0], "仅见杯口。")
        self.assertTrue(report["repair_failed"])
        self.assertEqual(report["authoring_length"]["status"], "below_target")
        result, _ = self.cloud('{"caption":"仅见杯口。"}', authoring_profile=a.FISHER, max_corrections=0)
        self.assertIn("fisher_length_target_unmet", json.loads(result[5])["warnings"])

    def test_english_with_chinese_quoted_length_does_not_trigger_han_expansion(self):
        result, session = self.cloud('{"caption":"Only the visible front of the cropped cup."}', authoring_profile=a.FISHER,
            prompt='Output the image description in English. The sign must read "请写200字". Do not invent the hidden rear.')
        self.assertEqual(len(session.calls), 1)
        self.assertIsNone(json.loads(result[5])["authoring_length"]["target_han_range"])

    def test_fisher_batch_expansion_refuses_silent_merge_before_any_provider(self):
        with patch.object(moss, "_resolved_values", side_effect=AssertionError("no credentials")):
            with self.assertRaises(moss.MossImageError):
                Node.execute(prompt="分别强化，不合并。", authoring_profile=a.FISHER,
                             reference_images={"reference_image_0": np.zeros((2, 8, 8, 3), dtype=np.float32)})

    def test_invalid_profile_is_rejected_before_transport_but_compile_ignores_it(self):
        self.assertIs(Node.validate_inputs(prompt=None, authoring_profile=None), True)
        self.assertIsInstance(Node.validate_inputs(prompt="A cup.", authoring_profile="bad"), str)
        with patch.object(moss, "_resolved_values", side_effect=AssertionError("no transport")):
            with self.assertRaises(moss.MossImageError): Node.execute(prompt="A cup.", authoring_profile="bad")
        result = Node.execute(operation=c.COMPILE, draft_json='{"caption":"A cup."}', authoring_profile="bad").result
        self.assertEqual(result[0], "A cup.")

    def test_comic_native_layout_and_caption_keep_six_outputs_and_visible_words(self):
        source = base.layout(1256, 1672)
        source["items"][0]["bbox"] = [0, 0, 700, 1500]
        source["items"][1]["bbox"] = [704, 200, 1200, 448]
        source["summary"]["canvas"] = "multi_panel"
        source["items"][0]["tags"] = ["comic_panel"]
        text = source["items"][1]["text"]
        result, session = self.cloud(json.dumps(source), authoring_profile=a.COMIC,
                                     output_format=c.LAYOUT, width=1256, height=1672, locked_text=text)
        self.assertEqual(len(result), 6)
        self.assertEqual(result[1:3], (1256, 1672))
        self.assertEqual(json.loads(result[4]), source)
        self.assertIn("No quota".lower(), session.calls[0][1]["json"]["messages"][0]["content"].lower())
        self.assertIn("comic_panel", session.calls[0][1]["json"]["messages"][1]["content"])
        result, _ = self.cloud('{"caption":"A quiet comic illustration."}', authoring_profile=a.COMIC, output_format=c.CAPTION)
        self.assertEqual(result[3], "caption")

    def test_new_typed_cache_restores_historical_mode_and_validates_counts(self):
        slot = "t8-authoring-cache-profile"
        result, _ = self.cloud('{"caption":"杯"}', authoring_profile=a.FISHER, max_corrections=0, recovery_slot=slot)
        with patch.object(moss, "_generate", side_effect=AssertionError("no model")):
            restored = Node.execute(recovery_action="restore_last", recovery_slot=slot, authoring_profile="bad", provider_config={"bad": True})
        self.assertEqual(restored.result, result)
        for key, bad in (("description_chars", True), ("han_chars", 2), ("metric", "tokens"), ("hard_enforced", True), ("status", []), ("status", {})):
            encoded = [str(value) for value in result]
            report = json.loads(encoded[5]); report["authoring_length"][key] = bad; encoded[5] = json.dumps(report)
            with self.assertRaises(c.MossContractError): c.decode_cached(encoded)

    def test_soft_length_fallback_never_swallows_identity_or_cancellation(self):
        for error in (moss.StrataProviderError("changed", "identity_changed"), KeyboardInterrupt()):
            calls = []
            def complete(messages, repair):
                calls.append(repair)
                if repair: raise error
                return '{"caption":"杯"}'
            validator = lambda raw: c.compile_draft(c.strict_json(raw))
            with self.assertRaises(type(error)):
                a.bounded(complete, [], validator, 1, {"correction_calls": 0},
                          {"max_output_chars": 0, "target_han_range": [1500, 2500]}, moss._authoring_soft_error)
            self.assertEqual(calls, [False, True])


if __name__ == "__main__":
    unittest.main()
