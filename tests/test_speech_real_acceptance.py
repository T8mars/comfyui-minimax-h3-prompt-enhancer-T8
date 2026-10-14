"""Safety/matrix contracts for the explicit opt-in acceptance runner; no inference."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("speech_acceptance_runner_test", ROOT / "tools/speech_real_acceptance.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class AcceptanceRunnerTests(unittest.TestCase):
    def test_four_cases_are_sixteen_total_not_thirty_two(self):
        cases = runner.matrix_cases()
        self.assertEqual(len(cases), 4)
        self.assertEqual([case["target"] for case in cases].count("h3"), 2)
        self.assertEqual([case["target"] for case in cases].count("seedance"), 2)
        self.assertEqual(len({(case["id"], enabled, repeat) for case in cases
                              for enabled in (False, True) for repeat in (1, 2)}), 16)

    def test_active_only_is_eight_and_default_order_is_unchanged(self):
        self.assertEqual(runner.active_states(), (False, True))
        self.assertEqual(runner.active_states(True), (True,))
        for active_only, expected in ((False, 16), (True, 8)):
            runs = [(case["id"], repeat, active) for case in runner.matrix_cases()
                    for repeat in (1, 2) for active in runner.active_states(active_only)]
            self.assertEqual(len(runs), expected)
            if active_only:
                self.assertTrue(all(active for _, _, active in runs))

    def test_correction_accounting_is_not_all_extra_requests(self):
        semantic = {"messages": [{"role": "system", "content": "Return only the complete corrected artifact. Deterministic issue codes: speech_missing_words"}]}
        legacy = {"messages": [{"role": "system", "content": "Strict language-correction editor"}]}
        self.assertEqual(runner.request_kind(semantic, first=True), "initial")
        self.assertEqual(runner.request_kind(semantic, first=False), "speech_semantic_correction")
        self.assertEqual(runner.request_kind(legacy, first=False), "legacy_correction")
        data_not_policy = {"messages": [{"role": "user", "content": semantic["messages"][0]["content"]}]}
        self.assertEqual(runner.request_kind(data_not_policy, first=False), "legacy_correction")

    def test_response_evidence_never_keeps_reasoning_or_private_extras(self):
        value = {"model": "public-fixture", "api_key": "DO-NOT-SAVE", "choices": [{"finish_reason": "stop",
                 "message": {"content": "visible artifact", "reasoning_content": "DO-NOT-SAVE", "private": "DO-NOT-SAVE"}}]}
        evidence = runner.public_completion(value)
        self.assertNotIn("DO-NOT-SAVE", str(evidence))
        self.assertEqual(evidence["choices"][0]["content"], "visible artifact")

    def test_output_cannot_write_to_either_source_tree(self):
        source = ROOT.parent / "Strata-source-fixture"
        for output in (ROOT, ROOT / "runtime/acceptance", source, source / "cache"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                runner.output_directory(output, source)
        destination = ROOT.parent / "external-acceptance-fixture"
        self.assertEqual(runner.output_directory(destination, source), destination.resolve())

    def test_loopback_root_only_without_secrets_redirect_target_or_query(self):
        self.assertEqual(runner.loopback_url("http://127.0.0.1:8081/v1"), "http://127.0.0.1:8081")
        for url in ("http://example.com", "http://127.0.0.1:0", "http://user:password@localhost",
                    "http://localhost/api", "http://localhost?token=secret", "file:///tmp/source"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                runner.loopback_url(url)

    def test_identity_strips_private_status_text(self):
        raw = {"model": "fixture", "started": 1, "loaded": True, "context": {"native": 32768},
               "api_key": "DO-NOT-SAVE", "text": "DO-NOT-SAVE", "error": "DO-NOT-SAVE",
               "processes": {"engine": {"pid": 10, "loaded": True, "running": True, "private": "DO-NOT-SAVE"},
                             "vision": {"pid": 11, "loaded": True, "running": True}}}
        identity = runner.service_identity(raw)
        self.assertNotIn("DO-NOT-SAVE", str(identity))
        runner.assert_residency(identity, runner.service_identity(raw))
        changed = runner.service_identity(raw)
        changed["processes"]["engine"]["pid"] = 12
        with self.assertRaises(AssertionError):
            runner.assert_residency(identity, changed)

    def test_real_confirmation_is_required_before_any_work(self):
        with self.assertRaises(SystemExit) as error:
            runner.main([])
        self.assertEqual(error.exception.code, 2)

    def test_helper_adapter_uses_declared_fields_without_chat(self):
        captured = {}
        class Output:
            result = ({"enabled": True}, "words", '{"status":"complete"}', "srt")
        class Helper:
            @classmethod
            def execute(cls, **kwargs):
                captured.update(kwargs)
                return Output()
        class Speech:
            T8SpeechReference = Helper
        value = runner.prepare_reference(Speech, source_mode="audio", audio={"fixture": True},
                                         start_s=2., end_s=5., url="http://127.0.0.1:12345")
        self.assertEqual(captured["mode"], "Enabled")
        self.assertEqual(captured["source_mode"], "AUDIO")
        self.assertEqual(captured["duration_s"], 3.)
        self.assertEqual(captured["purpose"], "reference")
        self.assertNotIn("end_s", captured)
        self.assertEqual(value["timed"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
