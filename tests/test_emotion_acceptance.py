"""Validate the offline evaluator before any opt-in paid observations."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from test_directional_skills import h3, sd, native_draft, relay_draft
from tools import emotion_acceptance as runner
from tools.emotion_acceptance import CASES, assess_text


class EmotionAcceptanceTests(unittest.TestCase):
    def test_frozen_matrix_has_48_slots_and_native_evaluator_signatures(self):
        self.assertEqual(len(CASES), 12)
        self.assertEqual(len({c["id"] for c in CASES}), 12)
        quality = Mock()
        quality.check_h3.side_effect = lambda text, *, task_type, duration, shot_count, language, source: {"issues": []}
        quality.check_seedance.side_effect = lambda text, *, language, source, shot_count: {"issues": []}
        for case in CASES:
            text = relay_draft(True) if case["target"] == "relay" else native_draft(True)
            self.assertEqual(assess_text(quality, h3, case, text), {"issues": []})
        self.assertEqual(quality.check_h3.call_count, 10)
        self.assertEqual(quality.check_seedance.call_count, 2)

    def test_all_48_slots_and_resume_run_offline_without_transport_or_key_files(self):
        def answer(**kwargs):
            return relay_draft(True) if kwargs.get("relay_config") else native_draft(True)
        with tempfile.TemporaryDirectory() as output, patch.object(runner, "load_package", return_value=(h3, sd, None)), patch.object(runner.getpass, "getpass", return_value="test-private-credential"), patch.object(h3, "enhance_prompt", side_effect=answer) as h3_call, patch.object(sd, "enhance_seedance20_prompt", return_value="镜头1：女人保持平静。") as sd_call, patch("requests.sessions.Session.request", side_effect=AssertionError("No network")), patch("builtins.print"):
            with patch("sys.argv", ["runner", "--output-dir", output]):
                runner.main()
            document = json.loads((Path(output) / "observations.json").read_text(encoding="utf-8"))
            self.assertEqual(len(document["tests"]), 48)
            self.assertEqual(h3_call.call_count, 40)
            self.assertEqual(sd_call.call_count, 8)
            self.assertTrue(all(t["outcome"] == "success" for t in document["tests"]))
            self.assertNotIn("test-private-credential", json.dumps(document))
            self.assertEqual(len(json.loads((Path(output) / "blind-texts.json").read_text(encoding="utf-8"))), 48)
            with patch("sys.argv", ["runner", "--output-dir", output, "--resume"]):
                runner.main()
            self.assertEqual(h3_call.call_count, 40)
            self.assertEqual(sd_call.call_count, 8)

    def test_interrupted_generation_is_retained_and_not_implicitly_retried(self):
        with tempfile.TemporaryDirectory() as output, patch.object(runner, "load_package", return_value=(h3, sd, None)), patch.object(runner.getpass, "getpass", return_value="test-private-credential"), patch.object(h3, "enhance_prompt", side_effect=KeyboardInterrupt) as generate, patch("builtins.print"), patch("sys.argv", ["runner", "--output-dir", output, "--case", "restrained_tears", "--arm", "tudou", "--repeats", "1"]):
            with self.assertRaises(SystemExit):
                runner.main()
            document = json.loads((Path(output) / "observations.json").read_text(encoding="utf-8"))
            self.assertEqual(len(document["tests"]), 1)
            self.assertEqual(document["tests"][0]["outcome"], "interrupted")
            self.assertEqual(generate.call_count, 1)
            with patch("sys.argv", ["runner", "--output-dir", output, "--case", "restrained_tears", "--arm", "tudou", "--repeats", "1", "--resume"]):
                runner.main()
            self.assertEqual(generate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
