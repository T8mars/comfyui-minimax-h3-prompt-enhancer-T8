"""Independent bounded quality pipeline regressions: CPU, no network or GGUF."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import h3_quality as q
import quality_pipeline as pipeline
from h3_prompt_relay import compile_relay_response
from test_h3_quality import base, vocal

EN_BODY = ("Alice stands by the station window, checks her watch, grips the folded ticket in her right hand, "
           "and then carefully shifts her weight forward while the camera follows continuously from the side.")
ZH_BODY = "爱丽丝站在车站窗边查看时间，右手握紧折叠车票，随后保持持有状态向前重心转移，镜头从侧面持续跟随。"


class BoundedPipelineTests(unittest.TestCase):
    def run_h3(self, draft, complete, **kwargs):
        values = dict(mode=q.QUALITY_REPAIR, messages=[{"role": "user", "content": "Keep the red coat."}],
                      complete=complete, task_type="T2VA", duration=8, shot_count=1,
                      language="English", source="", media_labels=[])
        values.update(kwargs)
        return pipeline.h3_quality_result(draft, **values)

    def test_off_never_checks_repairs_or_calls_provider(self):
        checked, repaired, complete = Mock(side_effect=AssertionError), Mock(side_effect=AssertionError), Mock(side_effect=AssertionError)
        self.assertEqual(q.run_quality("draft", mode=q.QUALITY_OFF, messages=[], check=checked,
                                      complete=complete, repair=repaired), ("draft", {}))
        for callback in (checked, repaired, complete):
            callback.assert_not_called()

    def test_check_reports_without_any_repair_or_billing(self):
        draft = base("[Shot 1] " + ZH_BODY)
        complete = Mock(side_effect=AssertionError("Check is never a generation"))
        repaired = Mock(side_effect=AssertionError("Check must preserve original protocol too"))
        result, report = q.run_quality(draft, mode=q.QUALITY_CHECK, messages=[],
            check=lambda t: q.check_h3(t, task_type="T2VA", language="English"),
            complete=complete, repair=repaired)
        self.assertEqual(result, draft)
        self.assertIn("h3_descriptive_language", report["issue_codes"])
        self.assertEqual(report["correction_calls"], 0)
        complete.assert_not_called()
        repaired.assert_not_called()

    def test_surgical_protocol_fix_has_zero_provider_calls_and_is_idempotent(self):
        original = base("[Shot 1] Alice says: （S1） <d>[English] Keep （S1） in these words.</d>\n[Shot 2] At 00:04.000 Alice walks.")
        complete = Mock(side_effect=AssertionError)
        fixed, metrics = self.run_h3(original, complete, shot_count=2)
        self.assertEqual(metrics["correction_calls"], 0)
        self.assertGreater(metrics["protocol_edits"], 0)
        self.assertIn("Alice says: (S1)", fixed)
        self.assertIn("<d>[English] Keep （S1） in these words.</d>", fixed)
        self.assertIn("At 00:04.000,", fixed)
        again, second = self.run_h3(fixed, complete, shot_count=2)
        self.assertEqual(again, fixed)
        self.assertEqual(second["protocol_edits"], 0)
        complete.assert_not_called()

    def test_one_correction_preserves_multimodal_source_and_exact_words(self):
        old = base("[Shot 1] " + EN_BODY + " " + vocal("别走", language="Chinese"))
        corrected = base("[Shot 1] " + ZH_BODY + " " + vocal("别走", entity="爱丽丝", language="Chinese"), sound="安静房间环境声与脚步。")
        messages = [{"role": "system", "content": "Source authority"}, {"role": "user", "content": [{"type": "text", "text": "说：别走"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,fixture"}}]}]
        frozen = copy.deepcopy(messages)
        complete = Mock(return_value=corrected)
        result, metrics = self.run_h3(old, complete, language="中文", source="说：别走", messages=messages)
        self.assertEqual(result, corrected)
        self.assertEqual(metrics["correction_calls"], 1)
        self.assertEqual(metrics["result"], "corrected")
        complete.assert_called_once()
        self.assertEqual(complete.call_args.args[0][:2], frozen)
        self.assertEqual(messages, frozen)
        self.assertIn("ONE BOUNDED QUALITY CORRECTION", complete.call_args.args[0][-1]["content"])

    def test_candidates_cannot_change_protected_dialogue_or_introduce_regression(self):
        old = base("[Shot 1] " + EN_BODY + " " + vocal("别走"))
        good = base("[Shot 1] " + ZH_BODY + " " + vocal("别走", entity="爱丽丝"), sound="安静房间环境声与脚步。")
        for candidate in (good.replace("别走", "再见"), good.replace("[Shot 1]", "[Shot 2]"), "", old):
            with self.subTest(candidate=candidate[:40]):
                complete = Mock(return_value=candidate)
                result, report = self.run_h3(old, complete, language="中文")
                self.assertEqual(result, old)
                self.assertEqual(report["correction_calls"], 1)
                self.assertNotEqual(report["result"], "corrected")
                complete.assert_called_once()

    def test_transport_or_candidate_checker_failure_keeps_complete_original(self):
        old = base("[Shot 1] " + EN_BODY)
        for error in (RuntimeError("transport"), ValueError("empty transport body")):
            with self.subTest(error=type(error).__name__):
                complete = Mock(side_effect=error)
                result, report = self.run_h3(old, complete, language="中文")
                self.assertEqual(result, old)
                self.assertEqual(report["result"], "correction_failed_draft_kept")
                self.assertEqual(report["correction_calls"], 1)
        checker = Mock(side_effect=[{"issues": [{"code": "bad"}]}, RuntimeError("candidate checker")])
        result, report = q.run_quality(old, mode=q.QUALITY_REPAIR, messages=[], check=checker, complete=Mock(return_value="candidate"))
        self.assertEqual(result, old)
        self.assertEqual(report["result"], "correction_failed_draft_kept")

    def test_initial_checker_or_protocol_failure_retains_draft(self):
        checker = Mock(side_effect=RuntimeError("checker unavailable"))
        complete = Mock(side_effect=AssertionError)
        result, report = q.run_quality("paid draft", mode=q.QUALITY_REPAIR, messages=[], check=checker, complete=complete)
        self.assertEqual(result, "paid draft")
        self.assertEqual(report["result"], "check_failed_draft_kept")
        complete.assert_not_called()
        result, report = q.run_quality("paid draft", mode=q.QUALITY_REPAIR, messages=[],
            check=lambda _: {"issues": []}, repair=Mock(side_effect=RuntimeError("repair failed")), complete=complete)
        self.assertEqual(result, "paid draft")
        self.assertEqual(report["result"], "protocol_repair_failed_draft_kept")
        complete.assert_not_called()

    def test_used_budget_never_calls_second_generation(self):
        old = base("[Shot 1] " + EN_BODY)
        complete = Mock(side_effect=AssertionError)
        result, report = self.run_h3(old, complete, language="中文", budget_used=True)
        self.assertEqual(result, old)
        self.assertEqual(report["result"], "budget_exhausted_draft_kept")
        self.assertEqual(report["correction_calls"], 0)
        complete.assert_not_called()

    def test_quality_candidate_fullwidth_speaker_is_locally_repaired_before_acceptance(self):
        words = 'Keep （S1） unchanged in these original words.'
        old = base('[Shot 1] Alice says: <d>[English] ' + words + '</d>')
        candidate = old.replace('Alice says:', 'Alice （S1） says:')
        expected = old.replace('Alice says:', 'Alice (S1) says:')
        complete = Mock(return_value=candidate)
        result, metrics = self.run_h3(old, complete, source='Alice says "' + words + '".')
        self.assertEqual(result, expected)
        self.assertEqual(metrics['correction_calls'], 1)
        self.assertEqual(metrics['result'], 'corrected')
        self.assertGreater(metrics['protocol_edits'], 0)
        self.assertIn('<d>[English] ' + words + '</d>', result)
        complete.assert_called_once()
        self.assertEqual(q.repair_protocol(result), (result, []))

    def test_candidate_protocol_repair_cannot_normalize_protected_text_or_valid_other_id(self):
        old = base('[Shot 1] ' + vocal('Keep （S1） in the original words.', language='English') +
                   ' Bob says: <d>[English] Bring the key.</d>')
        valid_candidate = old.replace('Bob says:', 'Bob （S2） says:')
        expected = old.replace('Bob says:', 'Bob (S2) says:')
        complete = Mock(return_value=valid_candidate)
        good, metrics = self.run_h3(old, complete)
        with self.subTest(candidate='valid candidate normalized locally'):
            self.assertEqual(good, expected)
            self.assertEqual(metrics['result'], 'corrected')
            self.assertEqual(metrics['correction_calls'], 1)
        for changed in (valid_candidate.replace('Alice (S1)', 'Alice (S3)'),
                        valid_candidate.replace('[English] Keep', '[Chinese] Keep'),
                        valid_candidate.replace('Keep （S1）', 'Keep (S1)')):
            with self.subTest(changed=changed[:130]):
                complete = Mock(return_value=changed)
                result, report = self.run_h3(old, complete)
                self.assertEqual(result, old)
                self.assertEqual(report['result'], 'candidate_rejected')
                self.assertEqual(report['correction_calls'], 1)
                complete.assert_called_once()

    def test_unknown_valid_english_language_name_does_not_trigger_paid_rewrite(self):
        draft = base('[Shot 1] ' + EN_BODY + ' ' + vocal('Vänta här tills jag kommer tillbaka.', language='Swedish'))
        complete = Mock(side_effect=AssertionError('Unknown language confirmation is not an instruction to rewrite'))
        result, metrics = self.run_h3(draft, complete, source=draft)
        self.assertEqual(result, draft)
        self.assertEqual(metrics['correction_calls'], 0)
        self.assertIn('vocal_language', metrics['unchecked'])
        complete.assert_not_called()

    def relay(self, native=None):
        return {"global_prompt": "Alice remains beside the window in the red coat.",
                "events": [{"prompt": "Alice holds the ticket in her right hand.", "end_state": "The ticket stays in Alice's right hand.", "weight": 1},
                           {"prompt": "Alice moves sideways while holding the ticket.", "end_state": "Alice remains moving with the ticket in her right hand.", "weight": 3}],
                "native_prompt": native or base("[Shot 1] " + EN_BODY)}

    def test_relay_protocol_repair_retains_envelope_and_native_compilation(self):
        original = self.relay(base("[Shot 1] Alice walks.\n[Shot 2] At 00:04.000 Alice keeps walking."))
        complete = Mock(side_effect=AssertionError)
        result, report = self.run_h3(json.dumps(original), complete, shot_count=2,
                                    relay_config={"event_count": 2, "time_ranges": "0-2\n2-8"})
        actual = json.loads(result)
        for key in ("global_prompt", "events"):
            self.assertEqual(actual[key], original[key])
        self.assertIn("At 00:04.000,", actual["native_prompt"])
        compiled = compile_relay_response(result, 8, 2, "0-2\n2-8", "T2VA", "English")
        self.assertEqual(compiled["relay_length"], 192)
        self.assertEqual(compiled["enhanced_prompt"], actual["native_prompt"])
        self.assertEqual(compiled["time_ranges"], "0-2\n2-8")
        self.assertEqual(report["correction_calls"], 0)
        complete.assert_not_called()

    def test_relay_invalid_or_changed_weight_candidate_cannot_replace_original(self):
        original = self.relay()
        for variant in ("invalid", "weight", "count"):
            candidate = copy.deepcopy(original)
            candidate["native_prompt"] = base("[Shot 1] " + ZH_BODY, sound="房间环境声与脚步。")
            if variant == "invalid":
                candidate["events"][0]["prompt"] = "bad|pipeline"
            elif variant == "weight":
                candidate["events"][0]["weight"] = 4
            else:
                candidate["events"].pop()
            with self.subTest(variant=variant):
                serialized = json.dumps(original)
                complete = Mock(return_value=json.dumps(candidate, ensure_ascii=False))
                result, report = self.run_h3(serialized, complete, language="中文", relay_config={"event_count": 2, "time_ranges": ""})
                self.assertEqual(result, serialized)
                self.assertEqual(report["correction_calls"], 1)
                self.assertEqual(report["result"], "candidate_rejected")

    def test_relay_native_only_translation_is_not_full_language_correction(self):
        original = self.relay()
        original["global_prompt"] = EN_BODY
        candidate = copy.deepcopy(original)
        candidate["native_prompt"] = base("[Shot 1] " + ZH_BODY, sound="车站环境声与脚步摩擦。")
        serialized = json.dumps(original)
        result, report = self.run_h3(serialized, Mock(return_value=json.dumps(candidate, ensure_ascii=False)),
                                    language="中文", relay_config={"event_count": 2, "time_ranges": ""})
        self.assertEqual(result, serialized)
        self.assertEqual(report["result"], "candidate_rejected")
        self.assertIn("h3_descriptive_language", report["issue_codes"])

    def test_cleanup_failure_keeps_enabled_draft_but_not_off_or_body_failure(self):
        class Provider:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                raise RuntimeError("cleanup failure")
        progress = Mock()
        with pipeline.retained_draft_provider(Provider(), {"draft": "paid draft"}, enabled=True, progress=progress):
            pass
        progress.assert_called_once()
        for enabled, state in ((False, {"draft": "paid draft"}), (True, {})):
            with self.subTest(enabled=enabled), self.assertRaisesRegex(RuntimeError, "cleanup failure"):
                with pipeline.retained_draft_provider(Provider(), state, enabled=enabled):
                    pass
        with self.assertRaisesRegex(ValueError, "original body failure"):
            with pipeline.retained_draft_provider(Provider(), {"draft": "paid draft"}, enabled=True):
                raise ValueError("original body failure")


class RealBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Existing public test doubles import the real Comfy node package in CPU
        # mode; neither a llama runtime nor a real transport is constructed.
        import test_directional_skills as doubles
        cls.d = doubles

    def responses(self, module):
        if module is self.d.h3:
            return base("[Shot 1] " + EN_BODY), base("[Shot 1] " + ZH_BODY, sound="车站环境声与脚步摩擦。")
        return EN_BODY, ZH_BODY

    def test_cloud_and_local_branches_send_creation_and_correct_once(self):
        for module in (self.d.h3, self.d.sd):
            function = module.enhance_prompt if module is self.d.h3 else module.enhance_seedance20_prompt
            old, fixed = self.responses(module)
            for transport in ("cloud", "local"):
                with self.subTest(platform=module.__name__, transport=transport):
                    inputs = self.d.execute_inputs(module)
                    inputs.update(output_language="中文", quality_mode=q.QUALITY_REPAIR, creation_mode=q.CREATION_CAUSAL, seed=12345)
                    progress = Mock()
                    inputs["progress_callback"] = progress
                    if transport == "cloud":
                        session = self.d.test_seedance20.SequencedChatSession([old, fixed])
                        result = function(**inputs, session=session, api_key="test-placeholder")
                        calls = [{"messages": c["json"]["messages"]} for c in session.chat_requests]
                    else:
                        instances = []
                        def factory(settings, *, vision):
                            instance = self.d.RecordingLocalProvider(settings, vision=vision, responses=[old, fixed])
                            instances.append(instance)
                            return instance
                        with patch.object(module, "LocalQwenProvider", side_effect=factory):
                            result = function(**inputs, api_mode=module.LOCAL_QWEN_API_MODE, **self.d.local_parameters(module))
                        calls = instances[0].calls
                        self.assertTrue(instances[0].closed)
                        self.assertEqual(instances[0].calls[1]["kwargs"], {"temperature": 0.1, "seed": 12345})
                    self.assertEqual(result, fixed)
                    self.assertEqual(len(calls), 2)
                    self.assertIn("ONE BOUNDED QUALITY CORRECTION", calls[-1]["messages"][-1]["content"])
                    self.assertIn("CAUSAL", calls[0]["messages"][0]["content"])
                    reports = [c.kwargs["quality_metadata"] for c in progress.call_args_list if "quality_metadata" in c.kwargs]
                    self.assertEqual(reports[-1]["correction_calls"], 1)
                    self.assertEqual(reports[-1]["result"], "corrected")
                    if module is self.d.sd:
                        self.assertNotIn("integrated_multimodal_description:", calls[0]["messages"][0]["content"])

    def test_relay_format_then_shared_language_quality_are_each_bounded(self):
        module = self.d.h3
        broken = json.loads(self.d.relay_draft())
        broken["native_prompt"] = ""
        for transport in ("cloud", "local"):
            with self.subTest(transport=transport):
                middle = json.loads(self.d.relay_draft())
                middle["native_prompt"] = base("[Shot 1] " + EN_BODY)
                final = json.loads(self.d.relay_draft(True))
                final["native_prompt"] = base("[Shot 1] " + ZH_BODY, sound="车站环境声与脚步摩擦。")
                responses = [json.dumps(broken), json.dumps(middle), json.dumps(final, ensure_ascii=False)]
                inputs = dict(prompt="保持红色袖口，车票始终在右手。", output_language="中文", duration_seconds=8,
                              quality_mode=q.QUALITY_REPAIR, relay_config={"event_count": 2, "time_ranges": "0-4\n4-8"})
                if transport == "cloud":
                    session = self.d.test_seedance20.SequencedChatSession(responses)
                    result = module.enhance_prompt(**inputs, api_key="test-placeholder", session=session)
                    calls = session.chat_requests
                else:
                    provider = self.d.RecordingLocalProvider(None, vision=False, responses=responses)
                    with patch.object(module, "LocalQwenProvider", return_value=provider):
                        result = module.enhance_prompt(**inputs, api_mode=module.LOCAL_QWEN_API_MODE)
                    calls = provider.calls
                self.assertEqual(len(calls), 3, "Existing Relay format repair is separate; language and quality share one correction")
                self.assertEqual(result, responses[2])

    def test_real_execute_recovery_keeps_final_draft_and_restores_without_generation(self):
        for module, cls, name in ((self.d.h3, self.d.h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                                  (self.d.sd, self.d.sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            for failure in (False, True):
                with self.subTest(platform=name, correction_failure=failure):
                    old, fixed = self.responses(module)
                    provider = self.d.RecordingLocalProvider(None, vision=False, responses=[old, fixed])
                    if failure:
                        original_complete = provider.complete
                        def complete(messages, **kwargs):
                            if provider.calls:
                                provider.calls.append({"messages": copy.deepcopy(messages), "kwargs": dict(kwargs)})
                                raise RuntimeError("repair transport failed")
                            return original_complete(messages, **kwargs)
                        provider.complete = complete
                    slot = "t8-quality-test-" + name + str(failure)
                    inputs = self.d.execute_inputs(module)
                    inputs.update(output_language="中文", api_mode=module.LOCAL_QWEN_API_MODE,
                                  quality_mode=q.QUALITY_REPAIR, creation_mode=q.CREATION_CAUSAL,
                                  recovery_slot=slot)
                    with patch.object(module, "LocalQwenProvider", return_value=provider):
                        output = cls.execute(**inputs)
                    expected = old if failure else fixed
                    self.assertEqual(output[0], expected)
                    self.assertEqual(len(provider.calls), 2)
                    with patch.object(module, name, side_effect=AssertionError("Restore must never rebill")) as generate:
                        restored = cls.execute(**{**inputs, "prompt": "", "quality_mode": "invalid", "creation_mode": "invalid",
                                                "recovery_action": module.RECOVERY_ACTION_RESTORE})
                    generate.assert_not_called()
                    self.assertEqual(restored[0], expected)
                    self.assertTrue(provider.closed)

    def test_real_import_and_execution_never_initialize_cuda(self):
        import torch
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
