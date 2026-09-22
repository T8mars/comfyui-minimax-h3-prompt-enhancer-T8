"""Regression for linked music briefs during ComfyUI's graph-validation pass."""

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
