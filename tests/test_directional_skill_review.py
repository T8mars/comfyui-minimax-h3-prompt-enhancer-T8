"""Blind evidence building is local-only, including identical-output ties."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("directional_review_tool", ROOT / "tools/build_directional_skill_review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
acceptance_spec = importlib.util.spec_from_file_location("directional_acceptance_tool", ROOT / "tools/directional_skill_acceptance.py")
acceptance = importlib.util.module_from_spec(acceptance_spec)
acceptance_spec.loader.exec_module(acceptance)


def snapshot(*, quality="repair", output="same draft"):
    return {"provider": "cloud", "performance": "off", "quality": quality, "creation": "off",
            "cases": [{"id": "scene", "prompt": "A listens.", "duration": 8, "shots": "1"}],
            "tests": [{"target": "h3", "case_id": "scene", "repeat": 0,
                       "director_skill": skill, "outcome": "success", "output": output}
                      for skill in ("none", "ning_wenwu")]}


class DirectionalReviewTests(unittest.TestCase):
    def test_wire_confirmation_finds_exact_source_in_text_and_multimodal_messages(self):
        source = 'Wait 2 seconds after "stop".\nKeep the key.'
        for messages in ([{"role": "user", "content": "Source: " + source}],
                         [{"role": "user", "content": [{"type": "text", "text": source}, {"type": "image_url", "image_url": {"url": "data:image/mock"}}]}]):
            self.assertTrue(acceptance.contains_text(messages, source))
        self.assertFalse(acceptance.contains_text([{"content": "Wait, keep the key."}], source))

    def run_tool(self, directory, current, baseline=None):
        source = directory / "current.json"
        source.write_text(json.dumps(current), encoding="utf-8")
        output = directory / "blind"
        argv = [str(spec.origin), str(source), "--rubric", "ning", "--output-dir", str(output)]
        if baseline is not None:
            prior = directory / "baseline.json"
            prior.write_text(json.dumps(baseline), encoding="utf-8")
            argv.extend(["--baseline", str(prior)])
        with patch.object(sys, "argv", argv):
            review.main()
        return (json.loads((output / "current-blind.json").read_text(encoding="utf-8")),
                json.loads((output / "current-mapping.json").read_text(encoding="utf-8")))

    def test_identical_drafts_keep_two_blind_candidates_and_both_conditions(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle, mapping = self.run_tool(Path(temporary), snapshot())
        candidates = bundle["groups"][0]["candidates"]
        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(candidates[0]["candidate_id"], candidates[1]["candidate_id"])
        self.assertEqual(candidates[0]["output"], candidates[1]["output"])
        self.assertEqual({item["director_skill"] for item in mapping.values()}, {"none", "ning_wenwu"})
        self.assertNotIn("director_skill", json.dumps(bundle))
        self.assertEqual(len(bundle["rubric"]), 5)
        self.assertEqual(sum(bundle["rubric"].values()), 10)

    def test_baseline_rejects_unlike_auxiliary_settings_and_facts(self):
        for field, value in (("quality", "off"), ("performance", "default"), ("provider", "local"), ("creation", "causal"), ("cases", [{"id": "scene", "prompt": "different"}])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                prior = snapshot()
                prior[field] = value
                with self.assertRaises(SystemExit):
                    self.run_tool(Path(temporary), snapshot(), prior)

    def test_matching_baseline_uses_only_off_and_retains_new_on(self):
        prior, current = snapshot(output="prior draft"), snapshot(output="new draft")
        current["tests"] = current["tests"][1:]
        with tempfile.TemporaryDirectory() as temporary:
            bundle, mapping = self.run_tool(Path(temporary), current, prior)
        self.assertEqual({item["output"] for item in bundle["groups"][0]["candidates"]}, {"prior draft", "new draft"})
        self.assertEqual({item["director_skill"] for item in mapping.values()}, {"none", "ning_wenwu"})


if __name__ == "__main__":
    unittest.main()
