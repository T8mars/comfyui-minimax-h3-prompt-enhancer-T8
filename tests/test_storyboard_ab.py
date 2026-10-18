import copy
import importlib.util
from pathlib import Path
import random
import unittest

spec = importlib.util.spec_from_file_location("storyboard_ab", Path(__file__).resolve().parents[1] / "tools/storyboard_ab.py")
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


class StoryboardABTests(unittest.TestCase):
    def experiment(self):
        manifest, observations = ab.plan("fixture-model", "fixture-provider")
        for record in observations["records"]:
            record.update(outcome="success", output="Captured fixture output", output_sha256=ab.digest("Captured fixture output"), logical_calls=1, http_attempts=1)
        return manifest, observations

    def test_eight_classes_both_targets_pairs_and_long_duration(self):
        manifest, observations = ab.plan("fixture", "fixture")
        self.assertEqual(len(manifest["slots"]), 32)
        self.assertEqual(len(ab.CASES), 8)
        self.assertEqual(max(s["input"]["duration_seconds"] for s in manifest["slots"]), 3600)
        with self.assertRaises(ValueError):
            ab.blind(manifest, observations)

    def test_blind_hides_arm_keeps_failed_slots_and_hashes(self):
        manifest, observations = self.experiment()
        observations["records"][0].update(outcome="failed", output="", output_sha256=ab.digest(""), error_category="timeout")
        blind, mapping = ab.blind(manifest, observations, rng=random.Random(0))
        self.assertEqual(len(blind["candidates"]), 32)
        self.assertEqual(sum(c["outcome"] == "failed" for c in blind["candidates"]), 1)
        self.assertTrue(all("on" not in c and "slot_id" not in c for c in blind["candidates"]))
        self.assertEqual(mapping["observations_sha256"], ab.digest(observations))
        self.assertTrue(all(c["usage"]["input_tokens"] is None for c in mapping["mapping"]))

    def test_missing_duplicate_changed_settings_output_and_empty_success_rejected(self):
        for fault in ("missing", "duplicate", "settings", "output", "empty", "nan", "usage", "currency"):
            manifest, observations = self.experiment()
            first = observations["records"][0]
            if fault == "missing": observations["records"].pop()
            if fault == "duplicate": observations["records"][-1] = copy.deepcopy(first)
            if fault == "settings": first["settings_sha256"] = "different"
            if fault == "output": first["output"] = "changed"
            if fault == "empty": first.update(output="", output_sha256=ab.digest(""))
            if fault == "nan": first["elapsed_seconds"] = float("nan")
            if fault == "usage": first["usage"]["cost"] = -1
            if fault == "currency": first["usage"]["currency"] = "PRIVATE_DATA"
            with self.subTest(fault=fault), self.assertRaises(ValueError): ab.blind(manifest, observations)

    def test_unpaired_inputs_cannot_be_blinded(self):
        manifest, observations = self.experiment()
        manifest["slots"][0]["input"]["duration_seconds"] = 10
        observations["manifest_sha256"] = ab.digest(manifest)
        with self.assertRaisesRegex(ValueError, "mismatched"):
            ab.blind(manifest, observations)

    def test_empty_experiment_rejected_but_custom_complete_pair_allowed(self):
        for size in (0, 2):
            manifest, observations = self.experiment()
            manifest["slots"] = manifest["slots"][:size]
            observations["records"] = observations["records"][:size]
            observations["manifest_sha256"] = ab.digest(manifest)
            if size == 0:
                with self.assertRaisesRegex(ValueError, "Empty experiment"):
                    ab.blind(manifest, observations)
            else:
                self.assertEqual(len(ab.blind(manifest, observations)[0]["candidates"]), 2)

    def test_paired_review_focus_cannot_reveal_arm_or_change_rubric(self):
        for value in ("Off baseline arm", None, ["same instruction"]):
            manifest, observations = self.experiment()
            manifest["slots"][0]["focus"] = value
            if not isinstance(value, str):
                manifest["slots"][1]["focus"] = value
            observations["manifest_sha256"] = ab.digest(manifest)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "review focus"):
                ab.blind(manifest, observations)

    def test_counts_are_integers_but_time_cost_can_be_fractional(self):
        for key in ("logical_calls", "http_attempts", "input_tokens", "output_tokens"):
            for value in (0.5, True, -1, float("inf"), float("nan")):
                manifest, observations = self.experiment()
                record = observations["records"][0]
                container = record["usage"] if key.endswith("tokens") else record
                container[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    ab.blind(manifest, observations)
        manifest, observations = self.experiment()
        for record in observations["records"]:
            record.update(http_attempts=0, elapsed_seconds=0.5)
            record["usage"]["cost"] = 0.25
        blind, mapping = ab.blind(manifest, observations)
        self.assertEqual(len(blind["candidates"]), 32)
        self.assertTrue(all(r["usage"]["input_tokens"] is None for r in mapping["mapping"]))
        for invalid in (None, [], "invalid"):
            observations["records"][0]["usage"] = invalid
            with self.assertRaisesRegex(ValueError, "Usage must"):
                ab.blind(manifest, observations)
