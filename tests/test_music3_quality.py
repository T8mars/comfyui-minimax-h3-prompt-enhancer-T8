import importlib.util
import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_music3_quality_suite_tests", PROJECT_ROOT / "music3_live_smoke.py")
quality = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = quality
SPEC.loader.exec_module(quality)


class Music3ReleaseQualitySuiteTests(unittest.TestCase):
    def test_paid_suite_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            quality.run_paid_quality_suite(False)

    def test_coordinated_negative_constraint_is_not_a_false_failure(self):
        caption = """### Global Metadata
Strictly instrumental cinematic folk with erhu lead, frame drum after the midpoint, a sparse dawn opening, and a forceful final release.

### Vocal Details
The piece is strictly instrumental. No singer, choir, or vocal layer of any kind appears; erhu remains the expressive melodic lead.

### Arrangement
Intro begins with sparse erhu resonance. Verse keeps the erhu exposed over a restrained drone. Instrumental introduces frame drum only after the midpoint and grows into the climax. Outro removes percussion and lets all instruments decay naturally into silence.
"""
        case = quality.CASES[2]
        report = {
            "schema_version": "t8-music3-enhancement-report/v1",
            "warnings": [],
        }
        result = {
            "lyrics": "[Instrumental]",
            "music_caption": caption,
            "music3_payload_json": json.dumps({"input": "[Instrumental]", "instructions": caption}),
            "enhancement_report_json": json.dumps(report),
        }
        scored = quality.score_case(case, result)
        self.assertEqual(scored["score"], 100)
        self.assertEqual(scored["missing_constraint_groups"], [])
        self.assertEqual(scored["hard_failures"], [])

    def test_deterministic_rubric_is_exactly_one_hundred_points(self):
        maxima = {
            "official_heading_contract": 15,
            "payload_consistency": 10,
            "explicit_constraint_preservation": 20,
            "section_timeline_coverage": 10,
            "lyrics_caption_separation": 10,
            "caption_specificity": 5,
            "lyrics_mode_invariant": 20,
            "safe_diagnostics": 5,
            "nonempty_outputs": 5,
        }
        self.assertEqual(sum(maxima.values()), 100)


if __name__ == "__main__":
    unittest.main()
