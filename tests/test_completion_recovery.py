import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_completion_recovery_test", ROOT / "completion_recovery.py")
recovery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recovery
SPEC.loader.exec_module(recovery)


class CompletionRecoveryTests(unittest.TestCase):
    def setUp(self):
        recovery.clear_recovery_records()

    def test_completed_outputs_are_memory_only_and_exactly_recoverable(self):
        slot = "t8-test-complete-0001"
        self.assertTrue(recovery.begin_recovery_record("MiniMaxH3PromptEnhancerT8", slot, "Seedance"))
        recovery.checkpoint_recovery_text(
            "MiniMaxH3PromptEnhancerT8",
            slot,
            "stream text",
            complete=True,
            response_id="chatcmpl-safe-id",
        )
        recovery.complete_recovery_record("MiniMaxH3PromptEnhancerT8", slot, ("final output",))
        self.assertEqual(
            recovery.recover_outputs("MiniMaxH3PromptEnhancerT8", slot, 1),
            ("final output",),
        )
        status = recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot)
        self.assertTrue(status["recoverable"])
        self.assertTrue(status["memory_only"])

    def test_partial_stream_is_reported_but_never_returned_as_complete(self):
        slot = "t8-test-partial-0001"
        recovery.begin_recovery_record("Seedance20PromptEnhancerT8", slot, "Seedance")
        recovery.checkpoint_recovery_text("Seedance20PromptEnhancerT8", slot, "truncated", complete=False)
        recovery.mark_recovery_ambiguous(
            "Seedance20PromptEnhancerT8",
            slot,
            RuntimeError("private upstream details"),
        )
        status = recovery.recovery_status("Seedance20PromptEnhancerT8", slot)
        self.assertEqual(status["state"], "ambiguous_partial")
        self.assertEqual(status["partial_chars"], len("truncated"))
        with self.assertRaisesRegex(recovery.CompletionRecoveryError, "incomplete stream checkpoint"):
            recovery.recover_outputs("Seedance20PromptEnhancerT8", slot, 1)

    def test_zero_byte_ambiguous_run_is_not_resubmitted_or_claimed_recoverable(self):
        slot = "t8-test-zero-byte-0001"
        recovery.begin_recovery_record("MiniMaxMusic3PromptEnhancerT8", slot, "Seedance")
        recovery.mark_recovery_ambiguous(
            "MiniMaxMusic3PromptEnhancerT8",
            slot,
            RuntimeError("provider response was not received"),
        )
        status = recovery.recovery_status("MiniMaxMusic3PromptEnhancerT8", slot)
        self.assertEqual(status["state"], "ambiguous_no_checkpoint")
        self.assertFalse(status["recoverable"])
        with self.assertRaisesRegex(recovery.CompletionRecoveryError, "no response bytes"):
            recovery.recover_outputs("MiniMaxMusic3PromptEnhancerT8", slot, 4)

    def test_status_never_contains_provider_url_key_prompt_or_output(self):
        slot = "t8-test-privacy-0001"
        secret = "sk-" + "x" * 32
        recovery.begin_recovery_record(
            "MiniMaxH3PromptEnhancerT8",
            slot,
            f"Seedance https://private.example/v1 {secret}",
        )
        recovery.complete_recovery_record(
            "MiniMaxH3PromptEnhancerT8",
            slot,
            ("private prompt and final output",),
        )
        encoded = json.dumps(
            recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot),
            ensure_ascii=False,
        )
        self.assertNotIn(secret, encoded)
        self.assertNotIn("private.example", encoded)
        self.assertNotIn("private prompt", encoded)

    def test_empty_optional_slot_is_a_noop(self):
        self.assertFalse(recovery.begin_recovery_record("MiniMaxH3PromptEnhancerT8", "", "Seedance"))
        recovery.checkpoint_recovery_text("MiniMaxH3PromptEnhancerT8", "", "ignored")
        recovery.mark_recovery_failed("MiniMaxH3PromptEnhancerT8", "", RuntimeError("ignored"))

    def test_oversized_output_disables_recovery_without_raising(self):
        slot = "t8-test-oversize-0001"
        recovery.begin_recovery_record("MiniMaxH3PromptEnhancerT8", slot, "Seedance")
        stored = recovery.complete_recovery_record(
            "MiniMaxH3PromptEnhancerT8",
            slot,
            ("x" * (recovery.MAX_RECOVERY_TEXT_CHARS + 1),),
        )
        self.assertFalse(stored)
        self.assertEqual(
            recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot)["state"],
            "unavailable_oversize",
        )


if __name__ == "__main__":
    unittest.main()
