import ast
import hashlib
import json
import os
import subprocess
import unittest
from unittest.mock import patch

import numpy as np
from test_qwen_image21 import PROJECT_ROOT, qwen

edit = qwen.edit
FROZEN_REVISION = "637036b0bd0ef4e966691983c20e82c2435761ea"


def image_map(count=2):
    return [{"tag": f"<image{i + 1}>", "source_slot": f"reference_image_{i}",
             "batch_index": 0, "width": 1080 + i, "height": 1590 + i} for i in range(count)]


def payload(prompt="把<image1>的背景换成浅灰墙，其他内容保持原图。", ratio="", follow="<image1>"):
    return {"rewritten_prompt": prompt, "wh_ratio": ratio, "ratio_follow": follow}


class PureEditContractTests(unittest.TestCase):
    def validate(self, data=None, **kwargs):
        return edit.validate(data or payload(), **{
            "brief": "把图1的背景换成浅灰墙", "image_map": image_map(),
            "requested_ratio": "auto", "transparent": False, "max_chars": 0, **kwargs,
        })

    def test_resource_checksum_and_independent_contract(self):
        self.assertEqual(hashlib.sha256(edit.load_contract().encode()).hexdigest(), edit.CONTRACT_SHA256)
        self.assertNotIn("four to five hundred words", edit.load_contract())
        self.assertIn("not a dedicated PE checkpoint", edit.load_contract())

    def test_checksum_mismatch_is_not_silently_used(self):
        with patch.object(type(edit.CONTRACT_PATH), "read_text", return_value="wrong"):
            with self.assertRaisesRegex(edit.EditContractError, "checksum"):
                edit.load_contract()

    def test_string_aware_json_and_leading_reasoning(self):
        data = payload('文字写着 "a {brace} and \\"quote\\" <think>"。')
        serialized = json.dumps(data)
        self.assertEqual(edit.extract_json(serialized), data)
        self.assertEqual(edit.extract_json("<think>private</think>\n```json\n" + serialized + "\n```"), data)
        for invalid in [serialized + serialized, serialized + " explanation", "Here is " + serialized,
                        serialized[:-1], "<think>unfinished", "```json\n" + serialized,
                        '{"wh_ratio":"1:1","wh_ratio":"2:1"}', "[" + serialized + "]"]:
            with self.subTest(invalid=invalid[:30]):
                self.assertIsNone(edit.extract_json(invalid))

    def test_language_is_not_visible_lettering_language(self):
        cases = [("把图1招牌改成“OPEN”，其他不变", "中文"),
                 ('Change the sign to "你好世界".', "English"),
                 ('输出语言：英文，文字写上“新年快乐”', "English"),
                 ('用中文描述，招牌写上 "OPEN"', "中文"),
                 ('Rewrite in English; sign says "中文".', "English")]
        for brief, expected in cases:
            with self.subTest(brief=brief):
                self.assertEqual(edit.descriptive_language(brief)[0], expected)

    def test_ratio_priority_original_dimensions_and_no_nearest_conversion(self):
        _, ratio, details = self.validate()
        self.assertEqual(ratio, "36:53")
        self.assertEqual(details["decision"], {"wh_ratio": "", "ratio_follow": "<image1>"})
        self.assertIn("nonpreset_ratio_check_downstream", details["warnings"])
        self.assertFalse(details["semantics_verified"])
        self.assertEqual(self.validate(payload(ratio="9:12", follow=""), requested_ratio="3:4")[1], "3:4")
        self.assertEqual(self.validate(payload(ratio="2:3", follow=""), brief="输出尺寸：1024x1536，换背景")[1], "2:3")
        self.assertEqual(self.validate(payload(ratio="1:1", follow=""), brief="目标比例：2:3，换背景", requested_ratio="1:1")[1], "1:1")
        self.assertEqual(edit.explicit_brief_ratio('文字写上 "1:1"，背景不变'), "")
        self.assertEqual(edit.explicit_brief_ratio("提高清晰度，4K，无噪点"), "")
        self.assertEqual(edit.explicit_brief_ratio("输出尺寸：100x200，目标比例：3:4"), "")

    def test_invalid_fields_ratios_and_follow(self):
        invalids = [payload(ratio="1:1"), payload(follow=""), payload(follow="<image3>"),
                    payload(ratio="auto", follow=""), payload(ratio="0:1", follow=""),
                    payload(ratio="1.5:1", follow=""), {**payload(), "reason": "private"},
                    {**payload(), "wh_ratio": 1}, payload(""), payload("first\nsecond")]
        for data in invalids:
            with self.subTest(data=data):
                with self.assertRaises(edit.EditContractError):
                    self.validate(data)
        with self.assertRaisesRegex(edit.EditContractError, "Fixed ratio"):
            self.validate(requested_ratio="1:1")

    def test_tags_validate_sources_not_quoted_letters(self):
        for bad in ["把图1放入图2", "只换背景，不说明是哪张图", "把<image3>放入<image1>", "把<Image 1>改背景",
                    "Use <image1> as the person in the second image.", "Use image A for the clothes of <image2>."]:
            with self.subTest(bad=bad):
                with self.assertRaises(edit.EditContractError):
                    self.validate(payload(bad))
        self.validate(payload('把<image1>招牌改成 "<image99>"，保持其他内容。'), brief='招牌写上 "<image99>"')
        self.validate(payload("把照片背景换成灰墙，其他内容保留。"), image_map=image_map(1))
        self.assertIn("unreferenced_images", self.validate()[2]["warnings"])

    def test_lettering_is_exact_and_job_instructions_are_not_echoed(self):
        self.validate(payload('把<image1>标语改成 "OPEN 24/7"，其他不变。'), brief='文字写着“OPEN 24/7”')
        for bad in ['把<image1>标语改成 "营业中"。', "把<image1>标语改成 OPEN 24/7。"]:
            with self.assertRaisesRegex(edit.EditContractError, "quoted"):
                self.validate(payload(bad), brief='文字写着“OPEN 24/7”')
        self.validate(brief='换背景，指令为“不要添加多余物体”')
        self.validate(payload('把<image1>标语改成 "不要停车"，其他不变。'), brief='标语写着“不要停车”')

    def test_canvas_dimensions_exclude_quoted_lettering(self):
        self.validate(payload('把<image1>招牌改成 "1:1 4K"。'), brief='文字写上 "1:1 4K"')
        for bad in ["把<image1>改为1:1画布。", "把<image1>渲染成4K图像。", "把<image1>改为1024x1536。"]:
            with self.assertRaisesRegex(edit.EditContractError, "canvas"):
                self.validate(payload(bad))

    def test_alpha_and_language_guards(self):
        self.validate(payload("将<image1>主体提取为RGBA图像，具有alpha通道，背景是透明的。"), transparent=True)
        self.validate(payload("Extract <image1> into an RGBA image with an alpha channel and a transparent background."),
                      brief="Extract the subject with transparency", transparent=True)
        for bad in ["<image1>是一张RGBA图像。", "<image1>有alpha通道，RGBA，背景不透明。", "Change the wall of <image1> to gray."]:
            with self.assertRaises(edit.EditContractError):
                self.validate(payload(bad), transparent=not bad.startswith("Change"))
        with self.assertRaises(edit.EditContractError):
            self.validate(brief="Change the wall to gray.")

    def test_constraint_messages_do_not_include_raw_images(self):
        media = [{"type": "image_url", "image_url": {"url": "https://example.test/image"}}]
        messages = edit.messages("换背景", image_map(), "auto", 200, False, media)
        self.assertEqual(messages[0]["content"], edit.load_contract())
        self.assertEqual(messages[1]["content"][1:], media)
        self.assertIn('"width": 1080', messages[1]["content"][0]["text"])


class EditExecutionTests(unittest.TestCase):
    def run_cloud(self, answers, **kwargs):
        images = {"reference_image_0": np.zeros((53, 36, 3), dtype=np.float32)}
        with patch.object(qwen, "_provider_config", return_value=("test-key", "https://example.test/chat", "", "test")), \
                patch.object(qwen, "_upload_media_plan", return_value=[]), \
                patch.object(qwen, "_inline_media_plan", return_value=[]), \
                patch.object(qwen, "_openai_media_plan", return_value=[]), \
                patch.object(qwen, "_request_completion", side_effect=answers) as request:
            output = qwen.QwenImage21PromptEnhancer.execute(**{
                "prompt": "把背景换成灰墙", "input_mode": qwen.INPUT_MODE_EDIT,
                "reference_images": images, "rewrite_profile": edit.EDIT_PROFILE,
                "api_key": "test-credential", **kwargs,
            })
        return output, request

    def test_original_image_map_numeric_sort_aliases_and_batches(self):
        first = np.zeros((2, 9, 7, 3), dtype=np.float32)
        last = np.zeros((6, 5, 3), dtype=np.float32)
        assets, mapping = qwen._edit_image_plan({"reference_image_10": last,
            "reference_image_2": first, "reference_images.reference_image_2": first})
        self.assertEqual([a["label"] for a in assets], ["<image1>", "<image2>", "<image3>"])
        self.assertEqual([(m["source_slot"], m["batch_index"], m["width"], m["height"]) for m in mapping],
                         [("reference_image_2", 0, 7, 9), ("reference_image_2", 1, 7, 9), ("reference_image_10", 0, 5, 6)])
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen._edit_image_plan({"reference_image_0": first, "reference_images.reference_image_0": last})
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen._edit_image_plan({"reference_image_0": np.zeros((11, 1, 1, 3))})

    def test_cloud_modes_keep_four_outputs_and_v2_metadata(self):
        for mode, model in [(qwen.SEEDANCE_API_MODE, qwen.QWEN_IMAGE_MODEL_ID),
                            (qwen.AI_WORKSHOP_API_MODE, qwen.AI_WORKSHOP_DEFAULT_MODEL),
                            (qwen.OPENAI_API_MODE, "vendor/vision")]:
            with self.subTest(mode=mode):
                output, request = self.run_cloud([json.dumps(payload())], api_mode=mode, custom_model="vendor/vision")
                self.assertEqual(len(tuple(output)), 4)
                self.assertEqual(output[1], "36:53")
                metadata, report = json.loads(output[2]), json.loads(output[3])
                self.assertTrue(metadata["schema_version"].endswith("/v2"))
                self.assertEqual(metadata["image_map"][0]["width"], 36)
                self.assertEqual(metadata["rewritten_prompt"], output[0])
                self.assertEqual(report["logical_generation_calls"], 1)
                self.assertFalse(report["semantics_verified"])
                self.assertEqual(request.call_args.args[-1], model)
                accept = request.call_args.kwargs["stream_acceptor"]
                self.assertTrue(accept(json.dumps(payload())))
                self.assertFalse(accept(json.dumps(payload())[:-1]))

    def test_text_mode_profile_has_no_effect_and_legacy_report_is_v1(self):
        output, request = self.run_cloud([json.dumps({"rewritten_prompt": "A square icon.", "wh_ratio": "1:1"})],
            input_mode=qwen.INPUT_MODE_TEXT, reference_images=None)
        self.assertEqual(json.loads(output[3])["schema_version"], "t8-qwen-image-21-report/v1")
        self.assertIn("frozen source contract", request.call_args.args[2][0]["content"])

    def test_ten_sources_are_mapped_and_not_silently_dropped(self):
        images = {f"reference_image_{i}": np.zeros((20 + i, 10 + i, 3)) for i in range(10)}
        answer = payload("把<image1>人物加入<image10>场景，其余图片不参与本次修改。", follow="<image10>")
        with patch.object(qwen, "_provider_config", return_value=("test", "https://example.test/chat", "", "test")), \
                patch.object(qwen, "_upload_media_plan", return_value=[]) as upload, \
                patch.object(qwen, "_request_completion", return_value=json.dumps(answer)):
            output = qwen.QwenImage21PromptEnhancer.execute(prompt="图1人物加入图10场景", input_mode=qwen.INPUT_MODE_EDIT,
                reference_images=images, rewrite_profile=edit.EDIT_PROFILE)
        self.assertEqual(len(upload.call_args.args[2]), 10)
        mapping = json.loads(output[2])["image_map"]
        self.assertEqual(mapping[-1]["source_slot"], "reference_image_9")
        self.assertEqual(output[1], "19:29")
        self.assertEqual(json.loads(output[3])["image_count"], 10)

    def test_linked_validation_and_blank_runtime_fail_before_paid_request(self):
        self.assertTrue(qwen.QwenImage21PromptEnhancer.validate_inputs(prompt=None, input_mode=qwen.INPUT_MODE_EDIT,
            reference_images={"reference_image_0": None}, rewrite_profile=edit.EDIT_PROFILE))
        with patch.object(qwen, "_request_completion", side_effect=AssertionError("must not charge")):
            with self.assertRaisesRegex(qwen.QwenImage21PromptEnhancerError, "prompt is required"):
                self.run_cloud([], prompt="")
        self.assertNotEqual(qwen.QwenImage21PromptEnhancer.validate_inputs(rewrite_profile="unknown"), True)
        ten = np.zeros((10, 1, 1, 3))
        self.assertTrue(qwen.QwenImage21PromptEnhancer.validate_inputs(prompt="改背景", input_mode=qwen.INPUT_MODE_EDIT,
            reference_images={"reference_images.reference_image_0": ten}, reference_image_0=ten,
            rewrite_profile=edit.EDIT_PROFILE))

    def test_single_correction_when_length_repair_has_invalid_ratio(self):
        first = payload("把照片背景换成灰墙，其他内容和画面构图都保持原图。")
        second = payload("换背景。", follow="<image99>")
        output, request = self.run_cloud([json.dumps(first), json.dumps(second)], max_output_chars=5)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(output[0], first["rewritten_prompt"])
        report = json.loads(output[3])
        self.assertEqual(report["correction_calls"], 1)
        self.assertEqual(report["logical_generation_calls"], 2)
        self.assertTrue(report["used_first_draft"])
        self.assertTrue(report["over_limit"])

    def test_provider_failure_during_repair_keeps_valid_draft(self):
        output, request = self.run_cloud([json.dumps(payload()), qwen.PromptEnhancerError("private upstream response body")], max_output_chars=1)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(output[0], payload()["rewritten_prompt"])
        self.assertTrue(json.loads(output[3])["repair_failed"])
        self.assertNotIn("private upstream", output[3])

    def test_invalid_format_returns_flagged_draft_without_fake_follow(self):
        output, request = self.run_cloud([json.dumps(payload(follow="<image99>")), "invalid correction"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(output[0], payload()["rewritten_prompt"])
        self.assertEqual(output[1], "")
        self.assertIsNone(json.loads(output[2])["decision"])
        self.assertFalse(json.loads(output[3])["structured_response"])
        output, _ = self.run_cloud(["<think>not closed", json.dumps(payload())])
        self.assertNotIn("think", output[0])

    def test_unclosed_reasoning_is_never_exposed_as_final_draft(self):
        with self.assertRaisesRegex(qwen.QwenImage21PromptEnhancerError, "No complete final text"):
            self.run_cloud(["<think>not closed", "<think>also unfinished"])

    def test_recovery_is_exactly_four_strings_without_generation_or_upload(self):
        original, _ = self.run_cloud([json.dumps(payload())], recovery_slot="t8-edit-recovery-regression")
        with patch.object(qwen, "_request_completion", side_effect=AssertionError("no generation")), \
                patch.object(qwen, "_upload_media_plan", side_effect=AssertionError("no upload")):
            recovered = qwen.QwenImage21PromptEnhancer.execute(prompt="", recovery_action=qwen.RECOVERY_ACTION_RESTORE,
                recovery_slot="t8-edit-recovery-regression", rewrite_profile=edit.LEGACY_PROFILE)
        self.assertEqual(tuple(recovered), tuple(original))

    def test_status_cannot_break_four_port_return_for_bad_cached_metadata(self):
        values = ("a completed prompt", "1:1", "{}", "[]")
        self.assertEqual(tuple(qwen._output_with_status(values)), values)

    def test_local_no_key_settings_language_and_context_exit_preserved(self):
        calls = []
        class FakeLocal:
            def __init__(self, settings, vision):
                calls.append(("init", settings, vision))
            def __enter__(self):
                return self
            def __exit__(self, *args):
                calls.append(("exit",))
            def complete(self, messages, **options):
                calls.append(("complete", messages, options))
                return json.dumps(payload())
        with patch.object(qwen, "LocalQwenProvider", FakeLocal), \
                patch.object(qwen, "local_qwen_settings", return_value="settings") as settings, \
                patch.object(qwen, "local_visual_part_budget", return_value=1), \
                patch.object(qwen, "build_local_multimodal_parts", return_value=([], {})), \
                patch.object(qwen, "apply_local_language_lock", side_effect=lambda msgs, language: msgs) as lock, \
                patch.object(qwen, "_provider_config", side_effect=AssertionError("no cloud")):
            output = qwen.QwenImage21PromptEnhancer.execute(prompt="换背景", input_mode=qwen.INPUT_MODE_EDIT,
                reference_image_0=np.zeros((53, 36, 3)), api_mode=qwen.LOCAL_QWEN_API_MODE,
                rewrite_profile=edit.EDIT_PROFILE, seed=123, local_max_tokens=17000)
        self.assertEqual(len(tuple(output)), 4)
        self.assertEqual(settings.call_args.kwargs["local_max_tokens"], 17000)
        self.assertTrue(all(call.args[1] == "中文" for call in lock.call_args_list))
        self.assertEqual(calls[-1], ("exit",))
        self.assertEqual(calls[-2][2], {"temperature": 0.2, "seed": 123, "require_complete": True})

    def test_shared_config_overrides_provider_and_preserves_budget(self):
        def merge(current, config, **kwargs):
            return {**current, "api_mode": qwen.OPENAI_API_MODE, "custom_model": "shared/vision",
                    "provider_request_options": {"extra_parameters": {"max_completion_tokens": 24000}}}
        with patch.object(qwen, "merge_provider_config", side_effect=merge):
            _, request = self.run_cloud([json.dumps(payload())], provider_config={"provider": "shared"})
        self.assertEqual(request.call_args.args[-1], "shared/vision")
        self.assertEqual(request.call_args.kwargs["provider_request_options"]["extra_parameters"], {"max_completion_tokens": 24000})


class FrozenClassicCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_source = subprocess.check_output(["git", "show", f"{FROZEN_REVISION}:qwen_image21.py"],
            cwd=os.environ.get("T8_SOURCE_GIT_ROOT", str(PROJECT_ROOT))).decode("utf-8")
        cls.old_tree = ast.parse(cls.old_source)
        cls.current_tree = ast.parse((PROJECT_ROOT / "qwen_image21.py").read_text(encoding="utf-8"))

    def test_original_core_functions_are_identical(self):
        for name in ["_load_skill", "_build_messages", "_image_plan", "_extract_json", "_validate_output",
                     "_cloud_request_options", "_resolve_image_model", "_report"]:
            old = next(n for n in self.old_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            now = next(n for n in self.current_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            with self.subTest(name=name):
                self.assertEqual(ast.dump(now), ast.dump(old))

    def test_schema_is_only_appended_and_execute_argument_prefix_unchanged(self):
        old_class = next(n for n in self.old_tree.body if isinstance(n, ast.ClassDef) and n.name == "QwenImage21PromptEnhancer")
        new_class = next(n for n in self.current_tree.body if isinstance(n, ast.ClassDef) and n.name == old_class.name)
        old_schema = next(n for n in old_class.body if n.name == "define_schema")
        new_schema = next(n for n in new_class.body if n.name == "define_schema")
        def field(tree, name):
            return next(k.value for k in tree.body[0].value.keywords if k.arg == name)
        self.assertEqual(ast.dump(field(old_schema, "outputs")), ast.dump(field(new_schema, "outputs")))
        old_inputs, new_inputs = field(old_schema, "inputs").elts, field(new_schema, "inputs").elts
        self.assertEqual([ast.dump(n) for n in old_inputs], [ast.dump(n) for n in new_inputs[:-1]])
        old_args = next(n for n in old_class.body if n.name == "execute").args
        new_args = next(n for n in new_class.body if n.name == "execute").args
        self.assertEqual([n.arg for n in old_args.args], [n.arg for n in new_args.args[:-1]])
        self.assertEqual([ast.dump(n) for n in old_args.defaults], [ast.dump(n) for n in new_args.defaults[:-1]])
        self.assertEqual(new_args.defaults[-1].attr, "LEGACY_PROFILE")

    def test_legacy_length_failure_has_only_one_repair(self):
        first = json.dumps({"rewritten_prompt": "A complete but very long scene.", "wh_ratio": "1:1"})
        invalid_repair = json.dumps({"rewritten_prompt": "short", "wh_ratio": "auto"})
        with patch.object(qwen, "_provider_config", return_value=("test", "https://example.test/chat", "", "test")), \
                patch.object(qwen, "_request_completion", side_effect=[first, invalid_repair]) as request:
            output = qwen.QwenImage21PromptEnhancer.execute(prompt="square icon", wh_ratio="1:1", max_output_chars=5)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(output[0], "A complete but very long scene.")
        self.assertEqual(json.loads(output[3])["correction_calls"], 1)


if __name__ == "__main__":
    unittest.main()
