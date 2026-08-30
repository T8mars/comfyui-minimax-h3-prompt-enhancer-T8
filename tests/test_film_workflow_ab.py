from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_film_workflow_ab_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)

AB_SPEC = importlib.util.spec_from_file_location(
    f"{SPEC.name}.film_workflow_ab_benchmark_test_module",
    ROOT / "film_workflow_ab_benchmark.py",
)
ab = importlib.util.module_from_spec(AB_SPEC)
AB_SPEC.loader.exec_module(ab)


class FilmWorkflowABTests(unittest.TestCase):
    def test_suite_has_six_bounded_real_ab_groups(self):
        self.assertEqual(len(ab.CASES), 6)
        self.assertEqual({case["kind"] for case in ab.CASES}, {"storyboard", "longform"})
        self.assertEqual(len({case["id"] for case in ab.CASES}), len(ab.CASES))

    def test_paid_runner_requires_confirmation_before_key_resolution(self):
        with self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            ab.run_paid_ab(confirm_paid=False, prompt_for_key=False)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SEEDANCE_API_KEY"):
                ab.run_paid_ab(confirm_paid=True, prompt_for_key=False)

    def test_storyboard_scoring_is_deterministic_and_enforces_cue_budget(self):
        case = dict(ab.CASES[2])
        shots = []
        for index in range(1, 5):
            shots.append({
                "index": index,
                "start_seconds": (index - 1) * 3,
                "end_seconds": index * 3,
                "purpose": "推进签字谈判",
                "subject_action": "沈乔端着玻璃杯",
                "camera": "中景",
                "causal_link": "前一策略失败",
                "value_before": f"拒绝前{index}",
                "value_after": f"拒绝后{index}",
                "scene_necessity": "删除会破坏策略升级",
                "setup_elements": [],
                "payoff_elements": [],
                "primary_performance_beat": ["示弱", "交换条件", "沉默施压", "不签字"][index - 1],
                "observable_cues": ["视线", "手部", "呼吸"],
            })
        payload = {"shots": shots, "global_prompt": "客户三次拒绝，沈乔始终端玻璃杯，最终不签字"}
        first = ab._score(case, payload)
        second = ab._score(case, payload)
        self.assertEqual(first, second)
        self.assertEqual(first["score"], 100)
        payload["shots"][0]["observable_cues"].append("肩膀")
        self.assertIn("cue_budget", ab._score(case, payload)["failed_checks"])

    def test_report_validator_rejects_secrets_and_accepts_hash_only_records(self):
        safe = {
            "response_text_stored": False,
            "credentials_stored": False,
            "cases": [{"sha256": "a" * 64, "score": 88}],
        }
        ab._validate_redacted(safe)
        unsafe = dict(safe, credential="sk-" + "abcdefghijklmnopqrstuvwxyz")
        with self.assertRaisesRegex(RuntimeError, "API-key-like"):
            ab._validate_redacted(unsafe)

    def test_matching_redacted_baselines_can_be_reused_without_response_text(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prior.json"
            path.write_text(json.dumps({
                "provider": ab.PROVIDER_NAME,
                "response_text_stored": False,
                "cases": [{
                    "case_id": ab.CASES[0]["id"],
                    "seed": 2026083001,
                    "baseline_contract_sha256": ab._baseline_contract_hash(ab.CASES[0]),
                    "baseline": {"score": 38, "sha256": "a" * 64},
                }],
            }), encoding="utf-8")
            reused = ab._load_reusable_baselines(path, ab.CASES)
        self.assertEqual(reused[ab.CASES[0]["id"]]["score"], 38)

    def test_baseline_reuse_rejects_changed_contract(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prior.json"
            path.write_text(json.dumps({
                "provider": ab.PROVIDER_NAME,
                "response_text_stored": False,
                "cases": [{
                    "case_id": ab.CASES[0]["id"],
                    "seed": 2026083001,
                    "baseline_contract_sha256": "0" * 64,
                    "baseline": {"score": 100, "sha256": "a" * 64},
                }],
            }), encoding="utf-8")
            reused = ab._load_reusable_baselines(path, ab.CASES)
        self.assertEqual(reused, {})

    def test_repository_metadata_and_cross_model_config_are_redacted(self):
        metadata = ab._repository_metadata()
        self.assertIn("repository_version", metadata)
        self.assertIn("git_commit", metadata)
        cloud_models = ["vendor/model-x", "vendor/model-y"]
        for model in cloud_models:
            config = ab._benchmark_provider_config(777, model)
            resolved = ab.creative._resolve_provider("test-key", config)
            self.assertEqual(config["custom_model"], model)
            self.assertEqual(resolved["custom_model"], model)
            self.assertNotIn("api_key", config)
        local = ab.shared_provider.build_provider_config(
            provider=ab.shared_provider.PROVIDER_LOCAL,
            local_model="Qwen3.8-test-Q4_K_M.gguf",
            local_max_tokens=777,
        )
        local_resolved = ab.creative._resolve_provider("", local)
        self.assertEqual(local_resolved["local_model"], "Qwen3.8-test-Q4_K_M.gguf")
        self.assertTrue(ab.creative.is_local_qwen_api_mode(local_resolved["api_mode"]))

    def test_paid_fixture_is_redacted_when_present(self):
        path = ab.DEFAULT_REPORT
        if not path.is_file():
            self.skipTest("paid fixture is generated only by the explicitly confirmed live run")
        source = path.read_text(encoding="utf-8")
        payload = json.loads(source)
        self.assertEqual(payload["group_count"], 6)
        self.assertEqual(payload["paid_request_count"], 12)
        self.assertEqual(payload["paid_requests_executed_this_run"], 6)
        self.assertEqual(payload["paid_responses_reused_from_matching_report_or_checkpoint"], 6)
        self.assertEqual(payload["enhanced_average"], 100)
        self.assertTrue(payload["all_enhanced_scores_at_least_baseline"])
        self.assertFalse(payload["response_text_stored"])
        self.assertFalse(payload["credentials_stored"])
        self.assertEqual(payload["run_metadata"]["model"], "qwen/qwen3.6-flash")
        self.assertIn("capture_status", payload["run_metadata"])
        self.assertNotRegex(source, r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")


if __name__ == "__main__":
    unittest.main()
