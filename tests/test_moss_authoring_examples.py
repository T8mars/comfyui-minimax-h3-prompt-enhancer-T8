"""Additive MOSS lessons: CPU structure/selection, not model or image-quality proof."""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
examples = importlib.import_module("build_moss_authoring_workflows")


class MOSSAuthoringExamples(unittest.TestCase):
    def setUp(self):
        self.workflows = examples.generate()

    def test_exact_json_thumbnails_links_and_no_credentials(self):
        self.assertEqual(tuple(self.workflows), examples.STEMS)
        examples.check()
        for value in self.workflows.values():
            self.assertFalse(any(node["type"] == "T8PromptText" for node in value["nodes"]))

    def test_main_saved_prefix_and_opt_in_long_short_comic(self):
        for stem in examples.STEMS[:3]:
            main = next(node for node in self.workflows[stem]["nodes"] if node["type"] == "MOSSImagePromptEnhancerT8")
            values = main["widgets_values_named"]
            self.assertEqual(tuple(values)[:27], examples.OLD_NAMES)
            self.assertEqual(len(values), 28)
            self.assertEqual(values, main["properties"]["t8_moss_widgets_v1"])
            self.assertNotIn("api_key", values)
            self.assertEqual(values["recovery_slot"], "")
            self.assertEqual(values["recovery_action"], "normal")
        long_values = self.workflows[examples.STEMS[0]]["nodes"][1]["widgets_values_named"]
        short_values = self.workflows[examples.STEMS[1]]["nodes"][1]["widgets_values_named"]
        self.assertEqual(long_values["authoring_profile"], examples.authoring.FISHER)
        self.assertIsNotNone(examples.authoring.length_policy(examples.authoring.FISHER, long_values["prompt"], long_values["output_language"], 0)["target_han_range"])
        short_policy = examples.authoring.length_policy(examples.authoring.FISHER, short_values["prompt"], short_values["output_language"], short_values["max_output_chars"])
        self.assertIsNone(short_policy["target_han_range"])
        self.assertEqual(short_values["max_output_chars"], 300)
        self.assertEqual(self.workflows[examples.STEMS[2]]["nodes"][1]["widgets_values_named"]["authoring_profile"], examples.authoring.COMIC)

    def test_director_named_fields_and_bilingual_page_connections(self):
        for stem in (examples.STEMS[3], examples.STEMS[4], examples.STEMS[5], examples.STEMS[7]):
            director = next(node for node in self.workflows[stem]["nodes"] if node["type"] == "MOSSAuthoringDirectorT8")
            self.assertEqual(tuple(director["widgets_values_named"]), examples.DIRECTOR_NAMES)
            self.assertEqual(len(director["widgets_values"]), 17)
            self.assertEqual(director["widgets_values_named"], director["properties"]["t8_moss_authoring_widgets_v1"])
            self.assertEqual(director["widgets_values_named"]["recovery_action"], "normal")
        pages = [node for node in self.workflows[examples.STEMS[3]]["nodes"] if node["type"] == "MOSSAuthoringPageT8"]
        self.assertEqual([node["widgets_values"][1:] for node in pages], [[1, "en"], [1, "zh"]])
        self.assertTrue(all(node["inputs"][0]["link"] is not None for node in pages))

    def test_fisher_two_loadimage_order_independent_versus_explicit_fusion(self):
        for stem, mode in ((examples.STEMS[4], "independent"), (examples.STEMS[5], "fusion")):
            value = self.workflows[stem]
            director = value["nodes"][1]
            self.assertEqual(director["widgets_values_named"]["profile"], examples.authoring.FISHER)
            self.assertEqual(director["widgets_values_named"]["reference_mode"], mode)
            self.assertEqual([item["name"] for item in director["inputs"]][1:],
                             ["reference_images.reference_image_0", "reference_images.reference_image_1"])
            images = [node for node in value["nodes"] if node["type"] == "LoadImage"]
            self.assertEqual([node["widgets_values"][0] for node in images],
                             [examples.STEMS[4] + ".jpg", examples.STEMS[5] + ".jpg"])
            self.assertTrue(all((examples.EXAMPLES / node["widgets_values"][0]).is_file() for node in images))
            notes = "\n".join(node["widgets_values"][0] for node in value["nodes"] if node["type"] == "Note")
            self.assertIn("上传", notes)
            self.assertIn("不自动写入", notes)

    def test_cpu_bundle_zero_calls_selector_same_geometry_and_exact_words(self):
        value = self.workflows[examples.STEMS[6]]
        self.assertFalse(any(node["type"] in ("T8LLMProviderConfig", "MOSSAuthoringDirectorT8", "LoadImage") for node in value["nodes"]))
        pages = [node for node in value["nodes"] if node["type"] == "MOSSAuthoringPageT8"]
        self.assertEqual(pages[0]["widgets_values"][0], pages[1]["widgets_values"][0])
        data = examples.bundle.validate_bundle(pages[0]["widgets_values"][0])
        self.assertEqual(data["report"]["logical_generation_calls"], 0)
        self.assertEqual(data["edited_unit_ids"], [])
        self.assertTrue(data["report"]["bilingual_complete"])
        for index in (1, 2):
            en = examples.bundle.select(data, index, "en")
            zh = examples.bundle.select(data, index, "zh")
            self.assertEqual(en[1:3], (1256, 1672))
            self.assertEqual(en[1:4], zh[1:4])
            self.assertEqual(json.loads(en[5])["logical_generation_calls"], 0)
            self.assertEqual(json.loads(en[6])["items"][0]["label"], "comic_panel")
            self.assertEqual(json.loads(en[4])["items"][0]["label"], "object")
            self.assertEqual(examples.contract.without_captions(json.loads(en[6])),
                             examples.contract.without_captions(json.loads(zh[6])))
            self.assertEqual(json.loads(en[6])["items"][2]["text"], "先走一步。" if index == 1 else "我们出发！")

    def test_typed_fixed_layout_context_contains_full_bundle_and_page2_only(self):
        director = self.workflows[examples.STEMS[7]]["nodes"][1]
        values = director["widgets_values_named"]
        context = json.loads(values["layout_context_json"])
        self.assertEqual(context["schema_version"], "t8-moss-authoring-context/v1")
        self.assertEqual(context["mode"], "full_layout")
        self.assertEqual(context["edit_unit_ids"], ["page-2"])
        self.assertEqual(context["bundle"], examples.teaching_bundle())
        self.assertTrue(values["preserve_layout"])
        self.assertEqual(len(examples.bundle.validate_bundle(context["bundle"])["units"]), 2)
        self.assertEqual(director["inputs"], [{"name": "provider_config", "type": "T8_LLM_PROVIDER_CONFIG", "link": 1, "shape": 7}])

    def test_generator_mutations_are_detached_and_checker_detects_exact_drift(self):
        changed = copy.deepcopy(self.workflows)
        changed[examples.STEMS[0]]["nodes"][1]["widgets_values"][0] = "changed"
        self.assertNotEqual(changed, examples.generate())
        first = examples.EXAMPLES / (examples.STEMS[0] + ".json")
        original = first.read_bytes()
        # Do not mutate a repository file to prove failure: replace read_bytes
        # for this invocation only, preserving normal reads of other artifacts.
        method = Path.read_bytes
        with mock.patch.object(Path, "read_bytes", lambda path: original + b" " if path == first else method(path)):
            with self.assertRaisesRegex(AssertionError, "canonical workflow bytes differ"):
                examples.check()


if __name__ == "__main__":
    unittest.main()
