"""MOSS contracts and actual provider wiring, offline. Not model-quality evidence."""
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1]))
import comfy.cli_args
comfy.cli_args.args.cpu = True
import moss_image_contract as c
from moss_vendor.scripts import test_compile_prompt as upstream_compile_tests


class UpstreamMossCompilerTests(upstream_compile_tests.PromptEnhancerTests):
    def test_cli_writes_output_without_overwriting_draft(self):
        # Upstream's test reads UTF-8 CLI output with the Windows locale (GBK).
        # Keep its source/hash unchanged, adapt only the test reader's encoding.
        original = Path.read_text
        def utf8_reader(path, encoding=None, errors=None):
            return original(path, encoding=encoding or "utf-8", errors=errors)
        with patch.object(Path, "read_text", utf8_reader):
            super().test_cli_writes_output_without_overwriting_draft()

PACKAGE_NAME = "t8_moss_unit_package"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE_NAME] = package
spec = importlib.util.spec_from_file_location(PACKAGE_NAME + ".moss_image", ROOT / "moss_image.py")
moss = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = moss
spec.loader.exec_module(moss)
Node = moss.MOSSImagePromptEnhancer
mc = moss.contract


def layout(width=1536, height=1024):
    return {"width": width, "height": height, "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": {"caption": "A calm ceramic campaign."}, "items": [
                {"label": "object", "caption": "An ivory cup on the left.", "bbox": [176, 224, 800, 864]},
                {"label": "text", "caption": "Dark green headline on the right.", "text": "把日常，过成诗。\n\"MOSS\" 🪴", "bbox": [928, 272, 1408, 448]}]}


class Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, text, status=200, finish="stop"):
        self.text = "hidden upstream body"
        self.status_code, self.content, self.finish = status, text, finish
    def json(self):
        return {"choices": [{"finish_reason": self.finish, "message": {"content": self.content}}]}
    def close(self): pass


class Session:
    def __init__(self, *responses):
        self.responses, self.calls, self.closed = list(responses), [], False
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, BaseException): raise result
        return result
    def close(self): self.closed = True


class StreamResponse(Response):
    headers = {"Content-Type": "text/event-stream; charset=iso-8859-1"}
    def __init__(self, body, *, finish=None, error=None):
        self.body, self.finish, self.error, self.closed = body, finish, error, False
    def iter_lines(self, decode_unicode=False):
        assert not decode_unicode
        yield ("data: " + json.dumps({"id": "unit-stream", "choices": [{"delta": {"content": self.body}, "finish_reason": self.finish}]}, ensure_ascii=False)).encode("utf-8")
        if self.error:
            raise self.error
    def close(self): self.closed = True


class MossContractTests(unittest.TestCase):
    def test_non_text_format_is_a_controlled_error(self):
        for bad in ([], {}, None, True, 1):
            with self.assertRaises(c.MossContractError): c.normalize_format(bad)
    def test_unpaired_unicode_is_a_controlled_repairable_contract_error(self):
        for raw in ('{"caption":"\\ud800"}', '{"\\ud800":"x"}', '\ud800'):
            with self.assertRaises(c.MossContractError): c.strict_json(raw)

    def test_all_upstream_sources_match_normalized_hashes(self):
        manifest = c.sources()
        self.assertEqual(manifest["commit"], c.SOURCE_COMMIT)
        for row in manifest["files"]:
            self.assertEqual(hashlib.sha256((c.VENDOR / row["path"]).read_text(encoding="utf-8").encode()).hexdigest(), row["sha256"])

    def test_caption_preserves_paragraphs_quotes_and_literal_text(self):
        caption = 'A cup says "茶".\nA quiet second paragraph.'
        result = c.compile_draft({"caption": caption}, locked_text="茶")
        self.assertEqual(result[:4], (caption, 1024, 1024, "caption"))
        self.assertEqual(result[-1]["moss_token_check"], {"status": "unverified", "limit": 4096, "measured": None})

    def test_layout_compiles_non_square_without_mutation(self):
        draft = layout()
        before = copy.deepcopy(draft)
        result = c.compile_draft(draft, width=1536, height=1024)
        final = json.loads(result[0])
        self.assertEqual(final["items"][0]["bbox"], [-288, -592, 352, 32])
        self.assertEqual(final["items"][1]["text"], draft["items"][1]["text"])
        self.assertNotIn("\n", result[0])
        self.assertNotIn("width", final)
        self.assertNotIn("height", final)
        self.assertEqual(draft, before)

    def test_json_rejects_duplicates_constants_partial_or_mixed_answers(self):
        values = ['{"caption":"one","caption":"two"}', '{"a":{"x":1,"x":2}}', '{"caption":NaN}',
                  '{"caption":Infinity}', '{"caption":"unfinished}', '{}{}', 'answer: {"caption":"A cup."}',
                  '[' * 1000 + '0' + ']' * 1000]
        for value in values:
            with self.subTest(value=value[:40]), self.assertRaises(c.MossContractError): c.strict_json(value)
        self.assertEqual(c.strict_json('```json\n{"caption":"A cup."}\n```'), {"caption": "A cup."})

    def test_invalid_and_already_compiled_drafts_are_not_rewritten(self):
        for fields in ({"children": []}, {"bbox_coord_space": "abs_centralized"}, {"width": True}, {"height": 1023}):
            value = layout()
            value.update(fields)
            with self.subTest(fields=fields), self.assertRaises(c.MossContractError): c.compile_draft(value, width=1536)
        value = layout()
        value["items"][0]["bbox"] = [0, 0, 1e999, 200]
        with self.assertRaises(c.MossContractError): c.compile_draft(value, width=1536)

    def test_mode_and_canvas_are_hard_constraints(self):
        with self.assertRaises(c.MossContractError): c.compile_draft({"caption": "A cup."}, output_format=c.LAYOUT)
        with self.assertRaises(c.MossContractError): c.compile_draft(layout())
        self.assertEqual(c.compile_draft(layout(), fixed_canvas=False)[1:3], (1536, 1024))
        for value in (False, 0, -16, 1024.0, 1023):
            with self.assertRaises(c.MossContractError): c.canvas(value, 1024)

    def test_eight_pixel_canvas_preserves_dimensions_and_native_coordinate_arithmetic(self):
        for width, height in ((1256, 1672), (1256, 1024), (1024, 1672), (24, 24)):
            draft = {"width": width, "height": height, "bbox_coord_space": "abs", "bbox_format": "xyxy",
                     "summary": {"caption": "A full canvas composition."}, "items": [
                         {"label": "object", "caption": "One object.", "bbox": [0, 0, width, height]},
                         {"label": "text", "caption": "Corner copy.", "text": "原文", "bbox": [width - 8.1, height - 8.1, width, height]}]}
            before = copy.deepcopy(draft)
            result = c.compile_draft(draft, width=width, height=height, locked_text="原文")
            compiled = json.loads(result[0])
            self.assertEqual(result[1:3], (width, height))
            self.assertEqual(compiled["items"][0]["bbox"], [-height // 2, -width // 2, height // 2, width // 2])
            self.assertEqual(compiled["items"][1]["bbox"], [height // 2 - 9, width // 2 - 9, height // 2, width // 2])
            self.assertEqual(json.loads(result[4]), before)
            self.assertEqual(draft, before)
        self.assertEqual(c.compile_draft({"caption": "One cup."}, width=1256, height=1672)[1:3], (1256, 1672))

    def test_eight_pixel_adapter_never_accepts_boxes_in_the_validation_padding(self):
        draft = layout(1256, 1672)
        for bad_box in ([1255, 0, 1257, 20], [0, 1671, 20, 1673], [0, 0, 1264, 1680], [2, 2, 1, 1]):
            draft["items"][0]["bbox"] = bad_box
            with self.subTest(box=bad_box), self.assertRaises(c.MossContractError): c.compile_draft(draft, width=1256, height=1672)
        draft["items"][0]["bbox"] = [0, 0, 40, 40]
        draft["items"][0]["unknown_field"] = "must not be dropped"
        with self.assertRaises(c.MossContractError): c.compile_draft(draft, width=1256, height=1672)

    def test_eight_pixel_generation_messages_do_not_reintroduce_sixteen_only_canvas_rule(self):
        messages = c.build_messages("One cup.", output_format=c.LAYOUT, width=1256, height=1672,
                                    language="中文", locked_text="", max_chars=0, image_labels=[])
        self.assertNotIn("positive multiples of 16", messages[0]["content"])
        self.assertNotIn("positive integer multiples of 16", messages[0]["content"])
        self.assertIn("multiples of 8", messages[0]["content"])
        request = json.loads(messages[1]["content"])
        self.assertEqual((request["width"], request["height"]), (1256, 1672))

    def test_locked_blocks_compare_whole_items_and_multiplicity(self):
        value = layout()
        phrase = value["items"][1]["text"]
        c.compile_draft(value, width=1536, locked_text=json.dumps([phrase], ensure_ascii=False))
        value["items"].append(copy.deepcopy(value["items"][1]))
        with self.assertRaises(c.MossContractError): c.compile_draft(value, width=1536, locked_text=phrase)
        c.compile_draft(value, width=1536, locked_text=json.dumps([phrase, phrase]))
        value["items"][1]["text"] = phrase.replace("\n", " ")
        with self.assertRaises(c.MossContractError): c.compile_draft(value, width=1536, locked_text=json.dumps([phrase, phrase]))

    def test_caption_copy_blocks_with_substrings_allocate_original_spans(self):
        for blocks, text in ((["SALE", "SALE NOW"], 'A poster reads "SALE" and "SALE NOW".'),
                             (["春日", "春日来信"], '标题“春日”，副标题“春日来信”。'),
                             (["SALE", "SALE NOW", "SALE"], '"SALE" and "SALE NOW" and "SALE"')):
            c.compile_draft({"caption": text}, locked_text=json.dumps(blocks, ensure_ascii=False))
        for blocks, text in ((["SALE", "SALE NOW"], 'Only "SALE NOW"'), (["SALE", "SALE NOW"], '"SALE" "SALE NOW" "SALE"'),
                             (["AA", "aa"], "aAAa")):
            with self.assertRaises(c.MossContractError): c.compile_draft({"caption": text}, locked_text=json.dumps(blocks))

    def test_bracket_copy_remains_literal_and_bad_json_arrays_still_fail(self):
        self.assertEqual(c.locked_blocks("[VIP] Early bird"), ["[VIP] Early bird"])
        self.assertEqual(c.locked_blocks("[2026] 春日"), ["[2026] 春日"])
        for value in ('["bad",]', '[1,2]', '[]', '[null]'):
            with self.assertRaises(c.MossContractError): c.locked_blocks(value)

    def test_length_is_soft_and_excludes_json_keys_and_boxes(self):
        value = layout()
        expected = len(value["summary"]["caption"]) + sum(len(i["caption"]) for i in value["items"])
        result = c.compile_draft(value, width=1536, max_chars=1)
        self.assertTrue(result[-1]["over_limit"])
        self.assertEqual(result[-1]["description_chars"], expected)
        self.assertEqual(json.loads(result[0])["items"][1]["text"], value["items"][1]["text"])

    def test_messages_are_native_and_do_not_instruct_file_execution(self):
        messages = c.build_messages("Minimal cup, no title.", output_format=c.AUTO, width=1024, height=1024,
                                    language="中文", locked_text="", max_chars=0, image_labels=[])
        self.assertIn("NO tools", messages[0]["content"])
        self.assertNotIn("python3 /path", messages[0]["content"])
        self.assertNotIn("Compile and deliver", messages[0]["content"])
        request = json.loads(messages[1]["content"])
        self.assertIn("中文", request["descriptive_language_rule"])
        self.assertEqual(request["locked_visible_text_blocks"], [])


class MossNodeTests(unittest.TestCase):
    def setUp(self):
        moss.state.clear()
        sys.modules[PACKAGE_NAME + ".completion_recovery"].clear_recovery_records()

    def cloud(self, *responses, **kwargs):
        session = Session(*responses)
        with patch.object(moss.requests, "Session", return_value=session):
            output = Node.execute(prompt="A quiet cup.", api_key="test-not-a-real-key", **kwargs)
        self.assertTrue(session.closed)
        return output, session

    def test_schema_has_six_typed_outputs_and_no_video_or_qwen_fields(self):
        schema = Node.define_schema()
        self.assertEqual(schema.node_id, moss.NODE_ID)
        self.assertEqual(len(schema.outputs), 6)
        inputs = [i.id for i in schema.inputs]
        for missing in ("transparent_alpha", "input_mode", "local_video_sample_fps", "negative_prompt"): self.assertNotIn(missing, inputs)
        self.assertIn("reference_images", inputs)
        self.assertEqual(schema.outputs[1].get_io_type(), "INT")
        self.assertEqual(schema.outputs[2].get_io_type(), "INT")

    def test_unresolved_linked_prompt_and_images_validate(self):
        self.assertTrue(Node.validate_inputs(prompt=None, reference_images={"reference_image_0": None}))
        self.assertIsInstance(Node.validate_inputs(prompt=""), str)
        self.assertTrue(Node.validate_inputs(operation=mc.COMPILE, prompt="", draft_json=None))
        self.assertEqual(Node.check_lazy_status(operation=mc.COMPILE, prompt=None, api_key=None, provider_config=None, draft_json="{}"), [])
        self.assertEqual(Node.check_lazy_status(recovery_action="restore_last"), [])
        self.assertEqual(Node.check_lazy_status(prompt="A cup.", provider_config=None, api_key=None), ["provider_config"])
        self.assertNotIn("api_key", Node.check_lazy_status(prompt="A cup.", api_mode=moss.LOCAL_QWEN_API_MODE, api_key=None))
        self.assertNotIn("api_key", Node.check_lazy_status(prompt="A cup.", provider_config={"provider": "Strata"}, api_key=None))

    def test_v3_dynamic_lazy_image_tuples_resolve_original_graph_keys(self):
        original = "reference_images.reference_image_0"
        result = Node.check_lazy_status(prompt="A cup.", reference_images={"reference_image_0": (None, original)})
        self.assertIn(original, result)
        result = Node.check_lazy_status(prompt="A cup.", reference_images={"reference_image_0": (np.zeros((1, 8, 8, 3)), original)})
        self.assertNotIn(original, result)
        self.assertIn(original, Node.check_lazy_status(prompt="A cup.", reference_images={"reference_image_0": None}))

    def test_linked_int_controls_are_unresolved_at_validation_but_strict_before_inference(self):
        self.assertIs(Node.validate_inputs(prompt=None, width=None, height=None, max_output_chars=None,
                                          max_corrections=None, output_format=None, output_language=None), True)
        self.assertIs(Node.validate_inputs(prompt="", operation=None), True)
        self.assertIsInstance(Node.validate_inputs(prompt="A cup.", width=17, height=None), str)
        with patch.object(moss, "_generate", side_effect=AssertionError("no inference")):
            for width in (None, 17, True):
                with self.subTest(width=width), self.assertRaises(moss.MossImageError):
                    Node.execute(prompt="A cup.", width=width)

    def test_compile_only_skips_credentials_models_and_inactive_inputs(self):
        with patch.object(moss, "_resolved_values", side_effect=AssertionError("credentials must not be read")), \
             patch.object(moss, "_generate", side_effect=AssertionError("no inference")), \
             patch.object(moss, "reference_inputs", side_effect=AssertionError("no media processing")):
            output = Node.execute(operation=mc.COMPILE, draft_json=json.dumps(layout()), prompt=None,
                                  width=0, height=False, api_mode="broken", provider_config={"broken": True}, reference_images=object())
        self.assertEqual(output.result[1:4], (1536, 1024, "layout"))
        self.assertEqual(json.loads(output.result[5])["logical_generation_calls"], 0)

    def test_flat_nested_aliases_numeric_order_and_batch_budget(self):
        a = np.zeros((2, 8, 8, 3), dtype=np.float32)
        b = np.zeros((1, 8, 8, 3), dtype=np.float32)
        slots = moss.reference_inputs({"reference_image_2": b}, {"reference_images.reference_image_0": a})
        plan, mapping = moss.image_plan(slots)
        self.assertEqual(len(plan), 3)
        self.assertEqual([i["source_slot"] for i in mapping], ["reference_image_0", "reference_image_0", "reference_image_2"])
        with self.assertRaises(moss.MossImageError): moss.reference_inputs({"reference_image_0": a}, {"reference_image_0": b})
        with self.assertRaises(moss.MossImageError): moss.image_plan(moss.reference_inputs({"reference_image_0": np.zeros((11, 8, 8, 3))}))

    def test_cloud_generation_uses_candidate_model_and_strict_transport(self):
        output, session = self.cloud(Response('{"caption":"A quiet cup."}'))
        self.assertEqual(output.result[:4], ("A quiet cup.", 1024, 1024, "caption"))
        report = json.loads(output.result[5])
        self.assertEqual(report["logical_generation_calls"], 1)
        self.assertEqual(report["chat_post_attempts"], 1)
        self.assertFalse(report["image_generation_performed"])
        self.assertEqual(session.calls[0][1]["json"]["model"], moss.DEFAULT_LLM_MODEL)
        self.assertEqual(session.calls[0][1]["json"]["max_tokens"], 16384)

    def test_eight_pixel_cloud_compile_and_typed_recovery_keep_requested_dimensions(self):
        slot = "t8-moss-eight-pixel-canvas"
        output, session = self.cloud(Response('{"caption":"A quiet cup."}'), width=1256, height=1672, recovery_slot=slot)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(output.result[1:3], (1256, 1672))
        self.assertEqual(Node.execute(recovery_slot=slot, recovery_action="restore_last").result, output.result)
        report = json.loads(output.result[5])
        self.assertIn("eight_pixel_canvas_downstream_unverified", report["warnings"])

    def test_openai_and_workshop_model_options_remain_overridable(self):
        config = sys.modules[PACKAGE_NAME + ".provider_config"]
        shared = config.build_provider_config(provider=config.PROVIDER_OPENAI, custom_model="verified-chat", openai_base_url="https://unit.test/v1",
                                               extra_parameters_json='{"max_completion_tokens":24000}')
        output, session = self.cloud(Response('{"caption":"A cup."}'), provider_config=shared)
        payload = session.calls[0][1]["json"]
        self.assertEqual(payload["model"], "verified-chat")
        self.assertEqual(payload["max_completion_tokens"], 24000)
        self.assertNotIn("max_tokens", payload)
        output, session = self.cloud(Response('{"caption":"A cup."}'), api_mode=moss.AI_WORKSHOP_API_MODE,
                                      ai_workshop_model="Custom（自定义）", custom_model="custom-model")
        self.assertEqual(session.calls[0][1]["json"]["model"], "custom-model")

    def test_one_combined_repair_and_zero_correction_mode(self):
        output, session = self.cloud(Response('{"caption":"bad","items":[]}'), Response('{"caption":"A quiet cup."}'))
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(json.loads(output.result[5])["correction_calls"], 1)
        with self.assertRaises(moss.MossImageError): self.cloud(Response('{"caption":"bad","items":[]}'), max_corrections=0)

    def test_valid_first_draft_survives_bad_optional_length_repair(self):
        output, session = self.cloud(Response('{"caption":"A quiet cup."}'), Response('invalid'), max_output_chars=1)
        self.assertEqual(output.result[0], "A quiet cup.")
        self.assertTrue(json.loads(output.result[5])["repair_failed"])

    def test_hard_failure_retains_draft_without_overwriting_last_good(self):
        slot = "t8-moss-last-good-test"
        good, _ = self.cloud(Response('{"caption":"A quiet cup."}'), recovery_slot=slot)
        with self.assertRaises(moss.MossImageError):
            self.cloud(Response('{"caption":"bad","items":[]}'), Response('still invalid'), recovery_slot=slot)
        self.assertTrue(moss.state.status(slot)["failed_draft_available"])
        with patch.object(moss, "_generate", side_effect=AssertionError("must not infer")):
            restored = Node.execute(recovery_slot=slot, recovery_action="restore_last", width=777, provider_config={"invalid": True})
        self.assertEqual(restored.result, good.result)
        self.assertIs(type(restored.result[1]), int)
        self.assertIs(type(restored.result[2]), int)

    def test_failed_raw_is_not_in_diagnostic_report(self):
        slot = "t8-moss-raw-inspection"
        with self.assertRaises(moss.MossImageError): self.cloud(Response('PRIVATE_UNVALIDATED_BODY'), recovery_slot=slot, max_corrections=0)
        self.assertNotIn("PRIVATE", json.dumps(moss.state.status(slot)))
        self.assertIn("PRIVATE", moss.state.draft(slot)["draft"])
        self.assertIsNone(moss.state.draft("invalid/slot"))

    def test_old_inflight_run_cannot_replace_newer_success(self):
        slot = "t8-moss-concurrent-slot"
        first, _ = moss.state.begin(slot)
        second, _ = moss.state.begin(slot)
        self.assertFalse(moss.state.commit(slot, first, ("stale",)))
        self.assertTrue(moss.state.commit(slot, second, ("fresh",)))

    def test_api_error_and_ambiguous_timeout_are_not_resent(self):
        for response in (Response("ignored", status=401), requests.exceptions.ProxyError("private error"), Response('{"caption":"seems complete"}', finish="length")):
            session = Session(response)
            with patch.object(moss.requests, "Session", return_value=session), self.assertRaises(Exception):
                Node.execute(prompt="A cup.", api_key="test-not-real")
            self.assertEqual(len(session.calls), 1)
            self.assertTrue(session.closed)

    def test_canvas_conflict_and_blank_input_fail_before_any_provider(self):
        with patch.object(moss, "_generate", side_effect=AssertionError("no provider")):
            for text in ("", "最终画布：1536×1024。画一个杯子。"):
                with self.assertRaises(moss.MossImageError): Node.execute(prompt=text)
        moss._canvas_conflict("The laptop screen is 1536x1024.", 1024, 1024)

    def test_quoted_referenced_and_negated_canvas_sizes_are_not_output_instructions(self):
        for text in (
            '海报只显示文案“canvas: 1920x1080”，这是文字而不是出图尺寸，最终按节点1024平方。',
            "不要使用 canvas 1536x1024，按节点的1024方图。",
            "参考图片上有 output resolution: 3840x2160 的水印，不要复制水印，画一幅1024方图。",
            'Show the exact title "canvas: 1920x1080" on a square poster.',
            "Do not use output size: 1536x1024. Use the node's square canvas.",
        ):
            with self.subTest(text=text): moss._canvas_conflict(text, 1024, 1024)
        for text in ("最终画布：1536×1024", "先画一只杯子，最终画布：1536×1024。", "Canvas size: 1536x1024"):
            with self.subTest(text=text), self.assertRaises(moss.MossImageError): moss._canvas_conflict(text, 1024, 1024)

    def test_local_wiring_does_not_read_cloud_credential_and_uses_language(self):
        seen = {}
        class Local:
            def __init__(self, settings, *, vision): seen["vision"] = vision
            def __enter__(self): return self
            def __exit__(self, *args): seen["released"] = True
            def complete(self, messages, **kwargs):
                seen["messages"], seen["kwargs"] = messages, kwargs
                return '{"caption":"一只安静的陶瓷杯。"}'
        with patch.object(moss, "LocalQwenProvider", Local), patch.object(moss, "_provider_config", side_effect=AssertionError("no API key lookup")):
            output = Node.execute(prompt="一个杯子。", output_language="中文", api_mode=moss.LOCAL_QWEN_API_MODE, llm_max_tokens="inactive")
        self.assertEqual(output.result[3], "caption")
        self.assertFalse(seen["vision"])
        self.assertTrue(seen["released"])
        self.assertIn("中文", seen["messages"][1]["content"])
        self.assertTrue(seen["kwargs"]["require_complete"])

    def test_strata_real_http_fixture_uses_only_running_service(self):
        from test_strata_provider import http_fixture
        config = sys.modules[PACKAGE_NAME + ".provider_config"]
        with http_fixture(response={"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": '{"caption":"A quiet cup."}'}}]}) as (url, calls):
            shared = config.build_provider_config(provider="Strata", strata_url=url)
            output = Node.execute(prompt="A cup.", provider_config=shared)
        self.assertEqual(output.result[0], "A quiet cup.")
        self.assertEqual(sum(method == "POST" for method, *_ in calls), 1)
        self.assertFalse(any("load" in path or "unload" in path for _, path, *_ in calls))

    def test_local_oversized_text_is_rejected_before_model_loading(self):
        with patch.object(moss, "LocalQwenProvider", side_effect=AssertionError("MODEL_LOAD_REACHED")) as loader:
            with self.assertRaises(moss.LocalQwenProviderError):
                Node.execute(prompt="word " * 10000, api_mode=moss.LOCAL_QWEN_API_MODE,
                             local_context_size=8192, local_max_tokens=1024)
        loader.assert_not_called()

    def test_strata_post_count_records_submissions_not_preflight_attempts(self):
        class Run:
            requests = 0
            submitted = False
            def complete(self, *_args, **_kwargs):
                if self.submitted: self.requests += 1
                raise moss.StrataProviderError("test refusal", "identity_changed")
        run = Run()
        for submitted in (False, True):
            run.submitted = submitted
            counters = {"logical_generation_calls": 0, "chat_post_attempts": 0}
            completion = moss._CloudCompletion({"api_mode": moss.API_MODES[-1]}, "model-test", [], counters, None)
            with patch.object(moss, "require_strata_run", return_value=run), self.assertRaises(moss.StrataProviderError):
                completion([], False)
            self.assertEqual(counters["chat_post_attempts"], int(submitted))

    def test_strata_identity_change_during_optional_repair_cannot_return_first_draft(self):
        from test_strata_provider import http_fixture, status
        strata = sys.modules[PACKAGE_NAME + ".strata_provider"]
        config = sys.modules[PACKAGE_NAME + ".provider_config"]
        metadata = status()
        original = strata.StrataRun.identity
        count = 0
        def identity(run):
            nonlocal count
            count += 1
            if count == 4: metadata["model"] = "changed-model"
            return original(run)
        slot = "t8-moss-strata-identity-repair"
        good = Node.execute(operation=mc.COMPILE, draft_json='{"caption":"Known good."}', recovery_slot=slot)
        with http_fixture(status=metadata, response={"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": '{"caption":"A quiet cup."}'}}]}) as (url, calls):
            shared = config.build_provider_config(provider="Strata", strata_url=url)
            with patch.object(strata.StrataRun, "identity", identity), self.assertRaises(moss.StrataProviderError) as caught:
                Node.execute(prompt="A cup.", provider_config=shared, max_output_chars=1, recovery_slot=slot)
            self.assertEqual(caught.exception.category, "identity_changed")
        self.assertEqual(sum(method == "POST" for method, *_ in calls), 1)
        self.assertEqual(Node.execute(recovery_slot=slot, recovery_action="restore_last").result, good.result)

    def test_non_string_failed_draft_preserves_original_error_and_finishes_state(self):
        slot = "t8-moss-invalid-upstream-draft"
        good = Node.execute(operation=mc.COMPILE, draft_json='{"caption":"Known good."}', recovery_slot=slot)
        for draft in (None, 123, {}):
            with self.subTest(draft=draft), self.assertRaises(moss.MossImageError) as caught:
                Node.execute(operation=mc.COMPILE, draft_json=draft, recovery_slot=slot)
            self.assertNotIsInstance(caught.exception.__cause__, TypeError)
            self.assertEqual(moss.state.status(slot)["phase"], "failed")
            self.assertFalse(moss.state.status(slot)["failed_draft_available"])
            self.assertNotIn("draft is retained", str(caught.exception))
            self.assertEqual(Node.execute(recovery_slot=slot, recovery_action="restore_last").result, good.result)
        with self.assertRaises(moss.MossImageError) as caught:
            Node.execute(operation=mc.COMPILE, draft_json="not json")
        self.assertNotIn("draft is retained", str(caught.exception))

    def test_stream_clean_eof_and_disconnect_accept_only_hard_valid_complete_answer(self):
        for error in (None, requests.exceptions.ChunkedEncodingError("test disconnect")):
            response = StreamResponse('{"caption":"一只白瓷杯。"}', error=error)
            output, session = self.cloud(response)
            self.assertEqual(output.result[0], "一只白瓷杯。")
            self.assertEqual(len(session.calls), 1)
            self.assertTrue(response.closed)

    def test_stream_partial_reasoning_and_explicit_length_are_not_retried_or_repaired(self):
        for body, finish in (('{"caption":"unfinished', None), ('<think>still thinking', None), ('{"caption":"A cup."}', "length")):
            response = StreamResponse(body, finish=finish)
            session = Session(response)
            with patch.object(moss.requests, "Session", return_value=session), self.assertRaises(Exception):
                Node.execute(prompt="A cup.", api_key="test-not-real")
            self.assertEqual(len(session.calls), 1)
            self.assertTrue(response.closed)

    def test_missing_snapshot_only_blocks_new_moss_node(self):
        with patch.object(mc, "VENDOR", ROOT / "not-an-installed-snapshot"):
            with self.assertRaises(mc.MossContractError): mc.compile_draft({"caption": "A cup."})
            utility = __import__(PACKAGE_NAME + ".text_utilities", fromlist=["T8PromptText"])
            self.assertEqual(utility.T8PromptText.execute("Original node still works.").result, ("Original node still works.",))

    def test_corrupt_cache_counts_or_prompt_cannot_be_promoted_to_success(self):
        output = Node.execute(operation=mc.COMPILE, draft_json='{"caption":"A cup."}')
        strings = [str(v) for v in output.result]
        self.assertEqual(mc.decode_cached(strings)[:4], output.result[:4])
        wrong_prompt = strings[:]
        wrong_prompt[0] = "A different cup."
        with self.assertRaises(mc.MossContractError): mc.decode_cached(wrong_prompt)
        wrong_report = json.loads(strings[5])
        wrong_report["logical_generation_calls"] = "0"
        strings[5] = json.dumps(wrong_report)
        with self.assertRaises(mc.MossContractError): mc.decode_cached(strings)

    def test_failed_draft_ttl_size_bound_and_status_redaction(self):
        slot = "t8-moss-state-limits"
        token, _ = moss.state.begin(slot)
        moss.state.failed(slot, token, "中" * 100000, "invalid_draft")
        self.assertLessEqual(len(moss.state.draft(slot)["draft"].encode()), moss.state.MAX_FAILED_BYTES)
        self.assertTrue(moss.state.status(slot)["failed_draft_truncated"])
        self.assertNotIn("draft", moss.state.status(slot))
        moss.state.failed(slot, token, "bad surrogate \ud800", "invalid_text_encoding")
        self.assertIsNotNone(moss.state.draft(slot))
        now = moss.state.time.monotonic()
        with patch.object(moss.state.time, "monotonic", return_value=now + moss.state.TTL_SECONDS + 1):
            self.assertIsNone(moss.state.draft(slot))

    def test_local_cancel_releases_and_cannot_replace_last_good(self):
        released = []
        class Local:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): released.append(True)
            def complete(self, *args, **kwargs): raise KeyboardInterrupt("test cancellation")
        slot = "t8-moss-cancelled-run"
        before = Node.execute(operation=mc.COMPILE, draft_json='{"caption":"A cup."}', recovery_slot=slot).result
        with patch.object(moss, "LocalQwenProvider", Local), self.assertRaises(KeyboardInterrupt):
            Node.execute(prompt="A cup.", api_mode=moss.LOCAL_QWEN_API_MODE, recovery_slot=slot)
        self.assertEqual(released, [True])
        self.assertEqual(Node.execute(recovery_action="restore_last", recovery_slot=slot).result, before)

    def test_local_capacity_failure_happens_before_loading_without_dropping_images(self):
        images = {"reference_image_0": np.zeros((10, 8, 8, 3), dtype=np.float32)}
        with patch.object(moss, "LocalQwenProvider", side_effect=AssertionError("must not load")):
            with self.assertRaises(moss.LocalQwenProviderError):
                Node.execute(prompt="Keep all references.", api_mode=moss.LOCAL_QWEN_API_MODE,
                             reference_images=images, local_context_size=8192, local_max_tokens=1024)

    def test_diagnostics_has_own_component_and_no_prompt_draft_or_credential(self):
        Node.execute(operation=mc.COMPILE, draft_json='{"caption":"PRIVATE-MOSS-DRAFT"}')
        diagnostics = __import__(PACKAGE_NAME + ".execution_diagnostics", fromlist=["diagnostics_snapshot"])
        record = diagnostics.diagnostics_snapshot()["recent"][0]
        self.assertEqual(record["component"], moss.NODE_ID)
        self.assertEqual(record["outcome"], "success")
        self.assertNotIn("PRIVATE-MOSS-DRAFT", json.dumps(record))

    def test_route_registration_does_not_import_missing_host_server(self):
        import builtins
        routes = __import__(PACKAGE_NAME + ".moss_image_routes", fromlist=["register_moss_image_routes"])
        original = builtins.__import__
        def forbid_server(name, *args, **kwargs):
            if name == "server": raise AssertionError("must not import the host model graph")
            return original(name, *args, **kwargs)
        with patch.dict(sys.modules, {"server": None}), patch.object(builtins, "__import__", forbid_server), patch.object(routes, "_REGISTERED", False):
            self.assertFalse(routes.register_moss_image_routes())

    def test_moss_routes_reject_bad_origins_without_exceptions_or_caching(self):
        routes = __import__(PACKAGE_NAME + ".moss_image_routes", fromlist=["register_moss_image_routes"])
        handlers = {}
        class Routes:
            def get(self, path):
                def add(handler): handlers[path] = handler; return handler
                return add
        server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=Routes())))
        with patch.dict(sys.modules, {"server": server}), patch.object(routes, "_REGISTERED", False):
            self.assertTrue(routes.register_moss_image_routes())
        for handler in handlers.values():
            for origin, expected in (("http://[", 403), ("http://another.invalid", 403), ("http://local.test", None)):
                request = types.SimpleNamespace(headers={"Origin": origin}, host="local.test", remote="127.0.0.1",
                                                match_info={"slot": "t8-moss-no-draft"})
                response = asyncio.run(handler(request))
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                if expected: self.assertEqual(response.status, expected)
                else: self.assertIn(response.status, (200, 404))


if __name__ == "__main__":
    unittest.main()
