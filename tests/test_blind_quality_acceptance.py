"""Blinding must not disclose group/model or silently discard failed evidence."""
import copy
import hashlib
import json
import unittest

from tools.blind_quality_acceptance import prepare


class BlindEvidenceTests(unittest.TestCase):
    def source(self):
        prompt = "A toy car continues rolling."
        digest = hashlib.sha256(json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return {"source_sha256": "production", "tests": [{"case_id": "case-a", "repeat": 0, "on": True,
            "outcome": "success", "output": prompt, "output_sha256": digest,
            "input": {"task": "T2VA", "seconds": 8, "shots": "1", "prompt": "Do not freeze."},
            "requests": [{"model": "private-model", "messages": "private-settings"}]}]}

    def test_groups_and_model_are_only_in_separate_mapping(self):
        source = self.source()
        original = copy.deepcopy(source)
        blind, mapping = prepare(source)
        self.assertEqual(source, original)
        self.assertEqual(len(blind["candidates"]), 1)
        candidate = blind["candidates"][0]
        self.assertEqual(set(candidate), {"candidate_id", "request", "prompt"})
        self.assertNotIn("private-model", json.dumps(blind))
        self.assertNotIn("private-settings", json.dumps(blind))
        self.assertNotIn("production", json.dumps(blind))
        self.assertTrue(mapping["mapping"][0]["on"])

    def test_failed_or_hash_changed_sample_is_never_silently_included(self):
        for field, value in (("outcome", "failed"), ("output_sha256", "wrong")):
            source = self.source()
            source["tests"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare(source)


if __name__ == "__main__":
    unittest.main()
