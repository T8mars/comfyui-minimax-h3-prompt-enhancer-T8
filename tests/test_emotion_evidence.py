import hashlib
import json
from pathlib import Path
import unittest
from tools.export_emotion_evidence import digest, sanitized


class EmotionEvidenceTests(unittest.TestCase):
    def document(self):
        return {"settings": {}, "cases": [], "tests": [{"case_id": "a", "repeat": 0, "arm": "tudou", "outcome": "success", "output": "synthetic answer", "output_sha256": digest("synthetic answer"), "api_key": "PRIVATE_SENTINEL", "calls": [{"messages": "PRIVATE_SENTINEL", "headers": "PRIVATE_SENTINEL", "http_attempts": [{"status": 200, "headers": "PRIVATE_SENTINEL", "usage": {"total_tokens": 30}}]}]}]}

    def test_allowlist_keeps_actual_metrics_and_drops_private_payloads(self):
        source = self.document()
        result = sanitized(source, 1)
        self.assertNotIn("PRIVATE_SENTINEL", str(result))
        self.assertEqual(result["tests"][0]["requests"][0]["http_attempts"][0]["usage"]["total_tokens"], 30)

    def test_failed_slot_is_retained_and_incomplete_or_corrupt_sets_rejected(self):
        source = self.document()
        source["tests"][0] = {"case_id": "a", "repeat": 0, "arm": "extreme", "outcome": "failed", "error_type": "PromptEnhancerError"}
        self.assertEqual(sanitized(source, 1)["tests"][0]["outcome"], "failed")
        with self.assertRaises(ValueError):
            sanitized(source, 2)
        broken = self.document()
        broken["tests"][0]["output_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            sanitized(broken, 1)

    def test_recorded_synthetic_phases_are_complete_hashed_and_not_mixed(self):
        path = Path(__file__).parent / "fixtures/tudou_emotion_api_2026-10-04.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        for name, count, completed, checked in (("frozen_ab", 48, 47, 24), ("native_followup", 8, 8, 3), ("quality_followup", 4, 4, 4)):
            phase = evidence["phases"][name]
            records = phase["tests"]
            self.assertEqual(len(records), count)
            self.assertEqual(len({(r["case_id"], r["repeat"], r["arm"]) for r in records}), count)
            self.assertEqual(sum(r["outcome"] == "success" for r in records), completed)
            self.assertEqual(sum(r["outcome"] == "success" and not r["contract_check"]["issues"] for r in records), checked)
            for record in records:
                if record.get("output"):
                    self.assertEqual(digest(record["output"]), record["output_sha256"])
                for request in record["requests"]:
                    if request.get("output"):
                        self.assertEqual(digest(request["output"]), request["output_sha256"])
                    self.assertNotIn("messages", request)
                    self.assertNotIn("headers", request)
        phases = evidence["phases"]
        self.assertNotEqual(phases["frozen_ab"]["settings"]["code_sha256"]["emotion_performance.py"], phases["native_followup"]["settings"]["code_sha256"]["emotion_performance.py"])
        self.assertEqual(phases["native_followup"]["settings"]["code_sha256"], phases["quality_followup"]["settings"]["code_sha256"])
        self.assertEqual(phases["quality_followup"]["settings"]["quality"], "repair")

    def test_exploratory_review_retains_hard_exclusions_and_unpaired_failure(self):
        root = Path(__file__).parent / "fixtures"
        raw = (root / "tudou_emotion_api_2026-10-04.json").read_bytes()
        evidence = json.loads(raw)
        review = json.loads((root / "tudou_emotion_review_2026-10-04.json").read_text(encoding="utf-8"))
        attributes = (root.parents[1] / ".gitattributes").read_text(encoding="utf-8")
        for name in ("tudou_emotion_api_2026-10-04.json", "tudou_emotion_review_2026-10-04.json"):
            self.assertIn("tests/fixtures/" + name + " text eol=lf", attributes)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), review["evidence_sha256"])
        observed = {(r["case_id"], r["repeat"], r["arm"]): r for r in evidence["phases"]["frozen_ab"]["tests"]}
        self.assertEqual(len(review["records"]), 48)
        self.assertEqual({(r["case_id"], r["repeat"], r["arm"]) for r in review["records"]}, set(observed))
        self.assertEqual(len({r["label"] for r in review["records"]}), 48)
        self.assertEqual(sum(r["status"] == "eligible" for r in review["records"]), 20)
        self.assertEqual(sum(r["status"] == "control" for r in review["records"]), 4)
        self.assertEqual(sum(r["status"] == "failed" for r in review["records"]), 1)
        for record in review["records"]:
            observation = observed[(record["case_id"], record["repeat"], record["arm"])]
            if record["status"] == "eligible":
                self.assertEqual(observation["outcome"], "success")
                self.assertEqual(observation["contract_check"]["issues"], [])
                self.assertEqual(len(record["scores"]), 4)
                self.assertTrue(all(value is None or isinstance(value, int) and 0 <= value <= 4 for value in record["scores"]))
            else:
                self.assertIsNone(record["scores"])
            if record["status"] == "excluded_native":
                self.assertTrue(observation["contract_check"]["issues"])
            if record["status"] == "failed":
                self.assertEqual(observation["outcome"], "failed")


if __name__ == "__main__":
    unittest.main()
