"""Director node boundary/recovery tests; fixtures never call real providers."""
from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

import test_moss_authoring_runtime as fixtures

r, m, a, c, b, native = fixtures.r, fixtures.m, fixtures.a, fixtures.c, fixtures.b, fixtures.native
nodes = importlib.import_module(m.__package__ + ".moss_authoring_nodes")
Director, Page, state = nodes.MOSSAuthoringDirector, nodes.MOSSAuthoringPage, nodes.state

NAMES = ["brief", "profile", "width", "height", "max_output_chars", "max_corrections", "page_count", "reference_mode",
    "descriptive_language", "locked_text", "continuity_context", "layout_context_json", "preserve_layout",
    "llm_max_tokens", "seed", "recovery_slot", "recovery_action"]


def values(**updates):
    result = fixtures.controls(**updates)
    if result["descriptive_language"] == native.LANG_AUTO:
        result["descriptive_language"] = nodes.DIRECTOR_AUTO
    return result


def provider():
    return fixtures.providers.build_provider_config(provider=fixtures.providers.PROVIDER_OPENAI,
        custom_model="director-fixture", openai_base_url="https://unit.test/v1")


def context(value, edits=()):
    return c.encode({"schema_version": r.CONTEXT_SCHEMA, "mode": "full_layout", "bundle": value, "edit_unit_ids": list(edits)})


class DirectorTests(unittest.TestCase):
    def setUp(self):
        state.clear()

    def tearDown(self):
        state.clear()

    def cloud(self, replies, **updates):
        pending, seen = [fixtures.encode(reply) for reply in replies], []
        options = values(**updates)
        options["provider_config"] = provider()
        with patch.object(m.requests, "Session", side_effect=lambda: fixtures.CapturedSession(pending, seen)), \
             patch.object(m, "_provider_config", return_value=("test-not-real", "https://unit.test/v1/chat/completions", "", "fixture")):
            output = Director.execute(**options)
        self.assertEqual(pending, [])
        self.assertTrue(all(session.close_count == 1 for session in seen))
        return output, seen

    def comic(self, **updates):
        return self.cloud([fixtures.plan(1), fixtures.source_reply(), fixtures.translation_reply()], page_count=1, **updates)

    def test_native_schema_has_exact_seventeen_widget_order_and_only_four_collection_outputs(self):
        schema = Director.define_schema()
        self.assertEqual(schema.node_id, "MOSSAuthoringDirectorT8")
        inputs = {item.id: item for item in schema.inputs}
        self.assertEqual([item.id for item in schema.inputs],
                         [*NAMES[:9], "provider_config", "reference_images", *NAMES[9:]],
                         "Check the complete schema, not only recognized widget names")
        names = [item.id for item in schema.inputs if item.id not in ("provider_config", "reference_images")]
        self.assertEqual(names, NAMES)
        self.assertEqual(names[:9], NAMES[:9], "All required native widgets remain before optional fields")
        source = (Path(__file__).resolve().parents[1] / "web/js/moss_authoring_ui.mjs").read_text(encoding="utf-8")
        frontend = ast.literal_eval(source.split("export const DIRECTOR_NAMES = ", 1)[1].split(";", 1)[0])
        self.assertEqual(frontend, NAMES)
        self.assertEqual([item.get_io_type() for item in schema.outputs], ["STRING", "INT", "STRING", "STRING"])
        self.assertNotIn("positive_prompt", [item.id for item in schema.outputs])
        self.assertIn("NOT a positive prompt", schema.description)
        self.assertNotIn("api_key", inputs)
        self.assertTrue(inputs["provider_config"].lazy)
        self.assertTrue(inputs["provider_config"].optional)
        for name in ("brief", "locked_text", "continuity_context", "layout_context_json"):
            self.assertTrue(inputs[name].lazy)
            self.assertFalse(inputs[name].as_dict()["dynamicPrompts"])
        for name in ("recovery_slot", "recovery_action"):
            self.assertTrue(inputs[name].as_dict()["socketless"])
        for name in ("width", "height"):
            self.assertEqual(inputs[name].as_dict()["step"], 8)
        # Merely excluding a declared input is insufficient: ComfyUI creates an
        # extra widget for a seed unless this metadata explicitly disables it.
        self.assertIs(inputs["seed"].as_dict()["control_after_generate"], False)
        self.assertNotIn("control_after_generate", inputs)

    def test_static_validation_defers_linked_none_but_rejects_literal_errors(self):
        self.assertIs(Director.validate_inputs(brief=None, profile=None, width=None, height=None,
            max_output_chars=None, max_corrections=None, page_count=None, reference_mode=None,
            descriptive_language=None, preserve_layout=None, layout_context_json=None,
            locked_text=None, continuity_context=None), True)
        self.assertIs(Director.validate_inputs(brief="", layout_context_json=None), True,
                      "The unresolved context could be a zero-edit copy")
        for update in ({"brief": ""}, {"brief": 3}, {"width": 17}, {"profile": "Classic / 原版"},
                       {"max_output_chars": True}, {"max_corrections": 2}, {"page_count": 17},
                       {"preserve_layout": 1}, {"layout_context_json": "not JSON"}):
            options = {"brief": "A quiet comic.", **update}
            with self.subTest(update=update): self.assertIsInstance(Director.validate_inputs(**options), str)

    def test_lazy_context_first_v3_tuples_provider_resolution_and_restore_skip(self):
        self.assertEqual(Director.check_lazy_status(layout_context_json=None, brief=None, provider_config=None,
            reference_images={"reference_image_0": (None, "reference_images.reference_image_0")}), ["layout_context_json"])
        required = Director.check_lazy_status(layout_context_json="", brief=None, locked_text=None, continuity_context=None, provider_config=None)
        self.assertEqual(required, ["provider_config", "brief", "continuity_context", "locked_text"])
        original = "reference_images.reference_image_0"
        needs = Director.check_lazy_status(layout_context_json="", brief="A page.",
            provider_config={"provider": "Local Qwen"}, reference_images={"reference_image_0": (None, original)})
        self.assertIn(original, needs)
        self.assertNotIn("api_key", needs)
        self.assertNotIn(original, Director.check_lazy_status(layout_context_json="", brief="A page.",
            provider_config={"provider": "Strata"}, reference_images={"reference_image_0": (np.zeros((1, 8, 8, 3)), original)}))
        self.assertEqual(Director.check_lazy_status(recovery_action="restore_last", layout_context_json=None,
            brief=None, provider_config=None, reference_images=None), [])
        self.assertIs(Director.validate_inputs(recovery_action="restore_last", brief=None, width=17,
            profile="bad", layout_context_json="bad JSON"), True)

    def test_mock_cloud_comic_returns_bundle_count_report_reading_not_a_compiled_positive(self):
        output, sessions = self.comic(recovery_slot="t8-director-node-comic")
        self.assertEqual(len(output.result), 4)
        text, count, report, reading = output.result
        self.assertIs(type(count), int)
        self.assertEqual(count, 1)
        value = b.validate_bundle(text)
        self.assertEqual(json.loads(report), value["report"])
        self.assertEqual(value["report"]["logical_generation_calls"], 3)
        self.assertTrue(value["report"]["bilingual_complete"])
        self.assertLess(reading.index("English / en"), reading.index("中文 / zh"))
        self.assertNotIn("caption", json.loads(text), "A collection is not a native Caption")
        self.assertNotIn("summary", json.loads(text), "A collection is not one native Layout")
        self.assertEqual(sum(len(session.calls) for session in sessions), 3)
        status = json.loads(output.ui["t8_moss_authoring_result"][0])
        self.assertEqual((status["origin"], status["unit_count"], status["calls"]), ("current", 1, 3))
        with self.assertRaises(native.MossContractError):
            native.compile_draft(json.loads(text))

    def test_mock_fisher_uses_selected_language_one_unit_and_page_outputs_one_native_prompt(self):
        output, sessions = self.cloud([{"caption": "Only one ivory cup, seen from the supplied front."}],
            profile=a.FISHER, descriptive_language="English", recovery_slot="t8-director-node-fisher")
        self.assertEqual(len(output.result), 4)
        value = b.validate_bundle(output.result[0])
        self.assertEqual(value["units"][0]["available_languages"], ["en"])
        self.assertEqual(value["report"]["logical_generation_calls"], 1)
        self.assertEqual(sum(len(session.calls) for session in sessions), 1)
        selected = Page.execute(output.result[0], page_index=1, language="en")
        self.assertEqual(len(selected.result), 9)
        self.assertEqual(selected.result[:4], ("Only one ivory cup, seen from the supplied front.", 1256, 1672, "caption"))
        self.assertEqual(json.loads(selected.result[5])["logical_generation_calls"], 0)
        with self.assertRaises(native.MossContractError): Page.execute(output.result[0], language="zh")

    def test_cache_restore_ignores_all_bad_current_generation_settings_and_performs_zero_posts(self):
        slot = "t8-director-node-restore"
        first, _sessions = self.comic(recovery_slot=slot)
        with patch.object(r, "prepare", side_effect=AssertionError("No generation preflight")), \
             patch.object(r, "provider_values", side_effect=AssertionError("No credentials")), \
             patch.object(r, "execute_run", side_effect=AssertionError("No generation")), \
             patch.object(m.requests, "Session", side_effect=AssertionError("No POST")), \
             patch.object(m, "LocalQwenProvider", side_effect=AssertionError("No model")):
            restored = Director.execute(recovery_slot=slot, recovery_action="restore_last", brief=None,
                profile=[], width=None, height=False, max_output_chars=True, provider_config={"invalid": "settings"},
                reference_images=object(), layout_context_json="bad", locked_text=None, continuity_context=None, seed=True)
        self.assertEqual(restored.result, first.result)
        status = json.loads(restored.ui["t8_moss_authoring_result"][0])
        self.assertEqual((status["origin"], status["calls"], status["source_generation_calls"]), ("cache", 0, 3))
        self.assertEqual(status["profile"], a.COMIC)

    def test_failed_chinese_translation_keeps_english_inspection_and_prior_last_good(self):
        slot = "t8-director-node-failed"
        first, _sessions = self.comic(recovery_slot=slot)
        pending = [fixtures.encode(reply) for reply in [fixtures.plan(1), fixtures.source_reply(), {"item_captions": {}}, {"item_captions": {}}]]
        seen = []
        with patch.object(m.requests, "Session", side_effect=lambda: fixtures.CapturedSession(pending, seen)), \
             patch.object(m, "_provider_config", return_value=("test-not-real", "https://unit.test/v1/chat/completions", "", "fixture")), \
             self.assertRaises(m.MossImageError):
            Director.execute(**values(page_count=1, recovery_slot=slot), provider_config=provider())
        self.assertEqual(pending, [])
        self.assertEqual(sum(len(session.calls) for session in seen), 4)
        self.assertTrue(all(session.close_count == 1 for session in seen))
        inspection = state.draft(slot)
        self.assertIs(inspection["complete"], False)
        self.assertIs(inspection["inspection_only"], True)
        self.assertEqual(inspection["units"][0]["available_languages"], ["en"])
        self.assertEqual(inspection["units"][0]["sources"]["en"], fixtures.source_reply()["source"])
        self.assertEqual([record["kind"] for record in inspection["stage_records"]], ["plan", "source"])
        self.assertEqual(state.recover(slot), b.validate_bundle(first.result[0]))
        with self.assertRaises(native.MossContractError): Page.execute(c.encode(inspection))
        with patch.object(r, "execute_run", side_effect=AssertionError("No generation")):
            self.assertEqual(Director.execute(recovery_slot=slot, recovery_action="restore_last").result, first.result)

    def test_missing_provider_never_falls_back_and_seed_or_context_conflicts_fail_before_credentials(self):
        with patch.object(m, "_provider_config", side_effect=AssertionError("No default cloud credentials")) as credential, \
             patch.object(m.requests, "Session", side_effect=AssertionError("No transport")), \
             self.assertRaises(m.MossImageError):
            Director.execute(**values(page_count=1), provider_config=None)
        credential.assert_not_called()
        with patch.object(r, "provider_values", side_effect=AssertionError("Preflight first")) as config:
            for seed in (None, True, -1, 2**64):
                with self.subTest(seed=seed), self.assertRaises(m.MossImageError):
                    Director.execute(**values(page_count=1, seed=seed), provider_config=provider())
        config.assert_not_called()
        output, _sessions = self.comic()
        value = b.validate_bundle(output.result[0])
        typed = context(value, ["page-1"])
        with patch.object(r, "provider_values", side_effect=AssertionError("Context conflict before credentials")) as config:
            for update in ({"page_count": 2}, {"profile": a.FISHER}, {"brief": "最终画布：1024×1024。"}):
                with self.subTest(update=update), self.assertRaises(m.MossImageError):
                    Director.execute(**values(**{"page_count": 1, "layout_context_json": typed, **update}), provider_config=provider())
        config.assert_not_called()

    def test_zero_edit_context_skips_lazy_none_and_bad_inactive_settings_without_any_provider(self):
        output, _sessions = self.comic()
        original = b.validate_bundle(output.result[0])
        typed = context(original, [])
        self.assertEqual(Director.check_lazy_status(layout_context_json=typed, brief=None, provider_config=None,
            continuity_context=None, locked_text=None, reference_images=None), [])
        self.assertIs(Director.validate_inputs(layout_context_json=typed, brief=None, profile=None, width=17, max_output_chars=True), True)
        with patch.object(r, "provider_values", side_effect=AssertionError("No provider")), \
             patch.object(m, "image_plan", side_effect=AssertionError("No inactive image processing")), \
             patch.object(m.requests, "Session", side_effect=AssertionError("No POST")), \
             patch.object(m, "LocalQwenProvider", side_effect=AssertionError("No model")):
            copied = Director.execute(layout_context_json=typed, brief=None, profile=None, width=None, height=False,
                max_output_chars=True, max_corrections=None, page_count=None, reference_mode=None,
                descriptive_language=None, provider_config=None, reference_images=None, locked_text=None,
                continuity_context=None, preserve_layout=None, llm_max_tokens=None, seed=True)
        value = b.validate_bundle(copied.result[0])
        self.assertEqual(value["units"], original["units"])
        self.assertEqual(value["profile"], original["profile"])
        self.assertEqual(value["continuity_context"], original["continuity_context"])
        self.assertEqual(value["edited_unit_ids"], [])
        self.assertEqual(value["report"]["logical_generation_calls"], 0)


if __name__ == "__main__":
    unittest.main()
