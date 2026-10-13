"""Regression for linked music briefs during ComfyUI's graph-validation pass."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
SPEC = importlib.util.spec_from_file_location(
    "t8_music_planner_validation_tests", ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
planners = sys.modules[f"{SPEC.name}.music_planners"]


class LinkedBriefValidationTests(unittest.TestCase):
    def test_linked_string_placeholder_is_deferred_for_both_planners(self):
        for node in (planners.T8LyricWriter, planners.T8ArrangementPlanner):
            with self.subTest(node=node.__name__):
                self.assertIs(node.validate_inputs(music_idea=None), True)
                self.assertIs(node.validate_inputs(music_idea="上游传入的创作主题"), True)
                self.assertIsInstance(node.validate_inputs(music_idea=""), str)

    def test_resolved_empty_brief_is_rejected_before_paid_request(self):
        with patch.object(planners.yue2, "YuE2Runner", side_effect=AssertionError("paid request started")):
            for node in (planners.T8LyricWriter, planners.T8ArrangementPlanner):
                with self.subTest(node=node.__name__):
                    with self.assertRaises(planners.MusicPlanError):
                        node.execute(music_idea="   ")

    def test_strata_preserve_lyrics_never_requires_service_metadata_or_inference(self):
        strata = sys.modules[f"{SPEC.name}.strata_provider"]
        config = {"schema_version": "t8-llm-provider-config/v1", "provider": "Strata", "strata_settings": {}}
        lyrics = "[Verse]\nWalk down the road\n[Chorus]\nHome again"
        for options in ({"api_mode": strata.STRATA_API_MODE}, {"provider_config": config}):
            with self.subTest(options=options), patch.object(strata, "StrataClient", side_effect=AssertionError("No service contact in Preserve mode")):
                result = planners.T8LyricWriter.execute(music_idea="Keep the original song", lyrics_mode=planners.LYRIC_MODES[1],
                                                        existing_lyrics=lyrics, quality_mode=planners.QUALITY_OPTIONS[1], **options)
                self.assertEqual(result.result[0], lyrics)
                report = json.loads(result.result[2])
                self.assertEqual(report["status"], "success")
                self.assertEqual(report["stages"], [])
                self.assertEqual(report["model"], "")
                self.assertEqual(result.ui["strata_bridge"][0]["request_count"], 0)


if __name__ == "__main__":
    unittest.main()
