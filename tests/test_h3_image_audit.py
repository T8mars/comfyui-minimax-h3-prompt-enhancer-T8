"""Independent fault injection for H3 Image cache and runtime boundaries."""
import copy
import json
import importlib
import threading
import unittest
from unittest.mock import patch

from test_h3_image_node import h, Node, reply
from test_moss_image import Session, Response
import numpy as np


class H3ImageAuditTests(unittest.TestCase):
    def good(self, slot):
        session = Session(Response(reply()))
        with patch.object(h.requests, "Session", return_value=session):
            return Node.execute(prompt="A cup.", api_key="test-not-real", recovery_slot=slot).result

    def test_corrupt_cached_report_shapes_have_controlled_errors(self):
        slot = "t8-h3-image-audit-report-shape"
        good = self.good(slot)
        for value in (None, [], "bad", 7):
            with self.subTest(value=value):
                values = (*good[:3], json.dumps(value))
                with patch.object(h, "recover_outputs", return_value=values), self.assertRaises(h.H3ImageError):
                    Node.execute(recovery_slot=slot, recovery_action="restore_last")

    def test_corrupt_cached_report_cannot_claim_incorrect_word_count(self):
        slot = "t8-h3-image-audit-report-words"
        good = self.good(slot)
        report = json.loads(good[3]); report["caption_words"] += 100
        recovery = __import__(h.__package__ + ".completion_recovery", fromlist=["complete_recovery_record"])
        recovery.complete_recovery_record(h.NODE_ID, slot, (*good[:3], json.dumps(report)))
        with self.assertRaises(h.H3ImageError):
            Node.execute(recovery_slot=slot, recovery_action="restore_last")

    def test_local_repair_context_failure_closes_owned_provider_without_second_call(self):
        created = []
        class Provider:
            def __init__(self, settings, vision): self.calls = 0; self.closed = False; created.append(self)
            def __enter__(self): return self
            def __exit__(self, *_): self.closed = True
            def complete(self, messages, **kwargs): self.calls += 1; return "invalid JSON"
        from test_h3_image_node import h as module
        with patch.object(h, "LocalQwenProvider", Provider), patch.object(h, "local_output_token_budget", side_effect=[8192, 8192, RuntimeError("context preflight")]):
            with self.assertRaisesRegex(RuntimeError, "context preflight"):
                Node.execute(prompt="A cup.", api_mode=h.LOCAL_QWEN_API_MODE)
        self.assertEqual(created[0].calls, 1)
        self.assertTrue(created[0].closed)

    def test_local_sixteen_images_and_inactive_alias_reach_one_owned_request(self):
        created = []
        class Provider:
            def __init__(self, settings, vision): self.settings, self.vision, self.calls, self.closed = settings, vision, [], False; created.append(self)
            def __enter__(self): return self
            def __exit__(self, *_): self.closed = True
            def complete(self, messages, **kwargs):
                self.calls.append(messages)
                return reply(h.contract.EDIT)
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        config = config_module.build_provider_config(provider="Local Qwen", local_context_size=65536, local_max_tokens=8192,
            credential_alias="missing-cloud-alias")
        refs = {f"reference_image_{i}": np.zeros((1, 7, 9, 3), dtype=np.float32) for i in range(16)}
        with patch.object(h, "LocalQwenProvider", Provider):
            result = Node.execute(prompt="Use the supplied references.", task_type=h.contract.EDIT, reference_images=refs,
                provider_config=config, llm_max_tokens=0)
        messages = created[0].calls[0]
        self.assertEqual(sum(part["type"] == "image_url" for part in messages[0]["content"]), 16)
        self.assertTrue(created[0].vision)
        self.assertTrue(created[0].closed)
        self.assertEqual(created[0].settings.max_tokens, 8192)
        self.assertEqual(len(json.loads(result.result[3])["image_map"]), 16)

    def test_unicode_layout_breaks_split_before_cloud_without_trimming_or_losing_duplicates(self):
        for separator in ("\r\n", "\r", "\n", "\u0085", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                session = Session(Response(reply(text="The first line reads '  SALE  '; the next line reads '  SALE  '.")))
                with patch.object(h.requests, "Session", return_value=session):
                    output = Node.execute(prompt="A two-line SALE poster.", locked_text="  SALE  " + separator + "  SALE  ",
                        api_key="test-not-real", max_corrections=0)
                self.assertEqual(len(session.calls), 1)
                self.assertEqual(json.loads(output.result[3])["locked_line_count"], 2)
                self.assertNotIn(separator, json.loads(output.result[2])["expanded_caption"])

    def test_valid_local_repaired_and_nonascii_cached_results_still_restore(self):
        created = []
        class Provider:
            def __init__(self, settings, vision): self.calls = 0; created.append(self)
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def complete(self, messages, **kwargs):
                self.calls += 1
                return "bad" if self.calls == 1 else reply(text="海报写着‘你好’。")
        slot = "t8-h3-image-audit-local-repaired"
        with patch.object(h, "LocalQwenProvider", Provider):
            original = Node.execute(prompt="A poster.", api_mode=h.LOCAL_QWEN_API_MODE, recovery_slot=slot,
                locked_text="你好", target_words=1500).result
        with patch.object(h, "_generate", side_effect=AssertionError("restore must not generate")):
            restored = Node.execute(prompt=None, task_type="invalid", target_words=-1, recovery_slot=slot, recovery_action="restore_last").result
        self.assertEqual(original[:3], restored[:3])
        report = json.loads(restored[3])
        self.assertEqual(report["logical_generation_calls"], 2)
        self.assertEqual(report["caption_words"], 0)
        self.assertEqual(report["word_count_delta"], -1500)
        self.assertEqual(report["chat_post_attempts"], 0)

    def test_late_old_run_cannot_overwrite_new_success_or_new_failure(self):
        recovery = importlib.import_module(h.__package__ + ".completion_recovery")
        for new_succeeds in (True, False):
            with self.subTest(new_succeeds=new_succeeds):
                slot = "t8-h3-image-audit-thread-" + str(new_succeeds)
                known = self.good(slot)
                old_ready = threading.Event(); finish_old = threading.Event(); outcomes = []
                def old_run():
                    token = h.state.begin(slot); old_ready.set()
                    if not finish_old.wait(5): raise RuntimeError("test barrier timeout")
                    outcomes.append(h.state.commit(slot, token, ("late old", *known[1:])))
                thread = threading.Thread(target=old_run); thread.start()
                try:
                    self.assertTrue(old_ready.wait(5))
                    newest = h.state.begin(slot)
                    expected = known
                    if new_succeeds:
                        expected = ("new success", *known[1:])
                        self.assertTrue(h.state.commit(slot, newest, expected))
                    finish_old.set(); thread.join(5)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(outcomes, [False])
                    self.assertEqual(recovery.recover_outputs(h.NODE_ID, slot, 4), expected)
                finally:
                    finish_old.set(); thread.join(5)

    def test_image_slot_aliases_and_single_image_dimensions_are_explicit(self):
        a = np.zeros((7, 11, 3), dtype=np.float32)
        b = np.zeros((1, 13, 5, 4), dtype=np.float32)
        media, mapping = h.image_plan({"reference_image_15": b, "reference_image_0": a, "reference_image_3": None})
        self.assertEqual([row["label"] for row in mapping], ["<Picture 1>", "<Picture 2>"])
        self.assertEqual([row["aspect_ratio"] for row in mapping], ["11:7", "5:13"])
        self.assertEqual(len(h.image_plan({"reference_image_0": a}, {"reference_images.reference_image_0": a})[0]), 1)
        for refs in ({"reference_image_0": np.zeros((7, 11, 1))}, {"reference_image_0": np.zeros((0, 7, 11, 3))},
                     {"reference_image_0": np.zeros((2, 7, 11, 3))}, {"reference_image_-1": a}, {"reference_image_16": a}):
            with self.subTest(keys=list(refs)), self.assertRaises((h.H3ImageError, h.PromptEnhancerError)):
                h.image_plan(refs)
        with self.assertRaises(h.H3ImageError):
            h.image_plan({"reference_image_0": a}, {"reference_images.reference_image_0": a.copy()})

    def test_strata_faults_do_not_retry_or_replace_lastgood_and_close_owned_run(self):
        from test_strata_provider import http_fixture, status
        strata = importlib.import_module(h.__package__ + ".strata_provider")
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        cases = (("malformed", 200, {"model": "model-test", "choices": []}, 1),
                 ("length", 200, {"model": "model-test", "choices": [{"finish_reason": "length", "message": {"content": reply()}}]}, 1),
                 ("wrong-model", 200, {"model": "changed-model", "choices": [{"finish_reason": "stop", "message": {"content": reply()}}]}, 1),
                 ("service-error", 503, {"error": {"message": "private-upstream-body"}}, 1),
                 ("contract-invalid", 200, {"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": "not JSON"}}]}, 2))
        original_close = strata.StrataRun.close
        for label, code, response, expected_posts in cases:
            with self.subTest(label=label):
                slot = "t8-h3-image-strata-audit-" + label
                good = self.good(slot); closed = []
                def close(run):
                    result = original_close(run)
                    closed.append(run._client is None)
                    return result
                with http_fixture(response=response, post_code=code) as (url, calls), patch.object(strata.StrataRun, "close", close):
                    config = config_module.build_provider_config(provider="Strata", strata_url=url)
                    with self.assertRaises((h.H3ImageError, strata.StrataProviderError)) as error:
                        Node.execute(prompt="A cup.", provider_config=config, recovery_slot=slot)
                self.assertNotIn("private-upstream-body", str(error.exception))
                self.assertEqual(sum(row[0] == "POST" for row in calls), expected_posts)
                self.assertTrue(closed); self.assertTrue(all(closed))
                self.assertEqual(Node.execute(recovery_slot=slot, recovery_action="restore_last").result[:3], good[:3])

    def test_strata_identity_change_after_post_prevents_new_cache_commit(self):
        from test_strata_provider import http_fixture, status
        strata = importlib.import_module(h.__package__ + ".strata_provider")
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        slot = "t8-h3-image-strata-audit-identity"
        good = self.good(slot); metadata = status(); identity = strata.StrataRun.identity
        def changed(run):
            if run.requests > 0:
                metadata["model"] = "changed-after-submit"
            return identity(run)
        with http_fixture(status=metadata, response={"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": reply()}}]}) as (url, calls):
            config = config_module.build_provider_config(provider="Strata", strata_url=url)
            with patch.object(strata.StrataRun, "identity", changed), self.assertRaises(strata.StrataProviderError) as caught:
                Node.execute(prompt="A cup.", provider_config=config, recovery_slot=slot)
        self.assertEqual(caught.exception.category, "identity_changed")
        self.assertEqual(sum(row[0] == "POST" for row in calls), 1)
        self.assertEqual(Node.execute(recovery_slot=slot, recovery_action="restore_last").result[:3], good[:3])

    def test_oversize_and_unconfigured_recovery_do_not_break_valid_generation(self):
        slot = "t8-h3-image-audit-oversize"
        self.good(slot)
        caption = "a" * 130000
        session = Session(Response(reply(text=caption)))
        with patch.object(h.requests, "Session", return_value=session):
            output = Node.execute(prompt="A poster.", api_key="test-not-real", recovery_slot=slot).result
        self.assertEqual(output[0], caption)
        self.assertFalse(json.loads(output[3])["recovery_saved"])
        recovery = importlib.import_module(h.__package__ + ".completion_recovery")
        self.assertEqual(recovery.recovery_status(h.NODE_ID, slot)["state"], "unavailable_oversize")
        session = Session(Response(reply()))
        with patch.object(h.requests, "Session", return_value=session):
            output = Node.execute(prompt="A cup.", api_key="test-not-real", recovery_slot="").result
        self.assertEqual(json.loads(output[3])["recovery_unavailable_reason"], "no_slot")


if __name__ == "__main__": unittest.main()
