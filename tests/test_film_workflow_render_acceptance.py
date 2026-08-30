from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "t8_film_workflow_render_acceptance_test_module",
    ROOT / "film_workflow_render_acceptance.py",
)
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


def review(**overrides):
    payload = {
        "reviewer": "T8 QA",
        "evidence_notes": "逐镜查看身份、因果、表演、世界规则与可看性。",
        "identity_continuity": 5,
        "causality_visibility": 4,
        "performance_readability": 4,
        "world_rule_compliance": 5,
        "overall_watchability": 4,
    }
    payload.update(overrides)
    return payload


class FilmWorkflowRenderAcceptanceTests(unittest.TestCase):
    def test_actual_render_manifest_records_hash_probe_and_named_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "h3.mp4"
            video.write_bytes(b"not-a-real-video-but-probe-is-controlled")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": acceptance.SCHEMA,
                "cases": [{
                    "case_id": "h3-causality-01",
                    "model_family": "MiniMax H3",
                    "variant": "enhanced",
                    "video_path": video.name,
                    "expected_duration_seconds": 12,
                    "human_review": review(),
                }],
            }, ensure_ascii=False), encoding="utf-8")
            with patch.object(acceptance, "_probe_video", return_value={
                "available": True,
                "valid": True,
                "duration_seconds": 12.1,
                "streams": [{"codec_type": "video"}],
            }):
                report = acceptance.evaluate_manifest(manifest, require_ffprobe=True)
        self.assertTrue(report["passed"])
        self.assertEqual(report["case_count"], 1)
        self.assertEqual(report["results"][0]["human_score_average"], 4.4)
        self.assertEqual(len(report["results"][0]["video_sha256"]), 64)
        self.assertFalse(report["video_content_stored"])
        self.assertFalse(report["credentials_stored"])

    def test_missing_video_and_invalid_human_score_fail_with_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": acceptance.SCHEMA,
                "cases": [{
                    "case_id": "seedance-invalid",
                    "model_family": "Seedance 2.0",
                    "video_path": "missing.mp4",
                    "human_review": review(overall_watchability=6),
                }],
            }, ensure_ascii=False), encoding="utf-8")
            report = acceptance.evaluate_manifest(manifest)
        errors = report["results"][0]["errors"]
        self.assertFalse(report["passed"])
        self.assertIn("video_missing_or_empty", errors)
        self.assertIn("invalid_score:overall_watchability", errors)

    def test_boolean_score_is_rejected_and_not_averaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "seedance.mp4"
            video.write_bytes(b"render-evidence")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": acceptance.SCHEMA,
                "cases": [{
                    "case_id": "seedance-bool-score",
                    "model_family": "Seedance 2.0",
                    "video_path": video.name,
                    "human_review": review(identity_continuity=True),
                }],
            }), encoding="utf-8")
            with patch.object(acceptance, "_probe_video", return_value={"available": False}):
                report = acceptance.evaluate_manifest(manifest)
        result = report["results"][0]
        self.assertIn("invalid_score:identity_continuity", result["errors"])
        self.assertIsNone(result["human_score_average"])


if __name__ == "__main__":
    unittest.main()
