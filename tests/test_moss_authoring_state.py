"""Director-only memory/route checks, with no host service or model execution."""
from __future__ import annotations

import asyncio
import builtins
import copy
import importlib
import json
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

import moss_authoring as a
import moss_authoring_bundle as bundles
import moss_authoring_contract as contract
import moss_authoring_state as state
import moss_image_contract as native

from test_moss_authoring_bundle import fisher_unit, stages


def good_bundle(text="PRIVATE-DIRECTOR-SOURCE"):
    unit = fisher_unit()
    unit["sources"]["zh"]["caption"] = text
    return bundles.build_bundle(a.FISHER, "independent", [unit], [], ["image-1"], "", stages([unit], a.FISHER), 1)


def good_text(text="PRIVATE-DIRECTOR-SOURCE"):
    return contract.encode(good_bundle(text))


class StateTests(unittest.TestCase):
    def setUp(self):
        state.clear()

    def tearDown(self):
        state.clear()

    def test_independent_namespace_slots_empty_slot_and_invalid_shapes(self):
        self.assertEqual(state.NODE_ID, "MOSSAuthoringDirectorT8")
        for slot in ("abcdefgh", "A" * 160, "t8-test.slot:001"):
            self.assertTrue(state.valid_slot(slot))
        for slot in (None, True, 7, "", "short", "A" * 161, "空间abcdef", "../outside", "C:/folder"):
            self.assertFalse(state.valid_slot(slot))
        token = state.begin("")
        self.assertIsInstance(token, str)
        self.assertFalse(state.commit("", token, good_text()))
        state.failed("", token, {"raw": "not retained"}, "invalid_draft")
        self.assertEqual(state.status("")["phase"], "unconfigured")
        self.assertIsNone(state.draft(""))
        with self.assertRaises(native.MossContractError): state.recover("")
        for slot in (None, True, "short", "A" * 161):
            with self.subTest(slot=slot), self.assertRaises(native.MossContractError): state.begin(slot)

    def test_commit_validates_full_bundle_then_recovery_is_detached_and_without_provider(self):
        slot = "t8-director-good"
        token = state.begin(slot)
        value = good_bundle()
        self.assertTrue(state.commit(slot, token, contract.encode(value)))
        self.assertEqual(state.status(slot), {"recoverable": True, "phase": "completed", "code": "",
                                           "failed_draft_available": False, "truncated": False})
        restored = state.recover(slot)
        self.assertEqual(restored, value)
        restored["units"][0]["sources"]["zh"]["caption"] = "changed by caller"
        self.assertEqual(state.recover(slot), value)
        self.assertIsNone(state.draft(slot))
        with self.assertRaises(native.MossContractError): state.commit(slot, token, {"not": "text"})
        for invalid in ('{"complete":false}', '{"schema_version":"t8-moss-authoring-bundle/v1","complete":true}', "not JSON"):
            with self.subTest(invalid=invalid), self.assertRaises(native.MossContractError): state.commit(slot, token, invalid)
        self.assertEqual(state.recover(slot), value)

    def test_begin_and_failed_keep_last_good_but_never_promote_inspection_partial(self):
        slot = "t8-director-lastgood"
        old = state.begin(slot); state.commit(slot, old, good_text("last-good"))
        token = state.begin(slot)
        self.assertEqual(state.status(slot)["phase"], "running")
        self.assertEqual(state.recover(slot)["units"][0]["sources"]["zh"]["caption"], "last-good")
        partial = {"units": [fisher_unit()], "stage_records": stages([fisher_unit()], a.FISHER), "raw": "unfinished raw output"}
        state.failed(slot, token, partial, "translation_failed")
        status = state.status(slot)
        self.assertTrue(status["recoverable"])
        self.assertTrue(status["failed_draft_available"])
        self.assertEqual(status["phase"], "failed")
        self.assertEqual(status["code"], "translation_failed")
        self.assertNotIn("unfinished", json.dumps(status))
        inspection = state.draft(slot)
        self.assertTrue(inspection["inspection_only"])
        self.assertIs(inspection["complete"], False)
        self.assertEqual(inspection["units"], partial["units"])
        self.assertEqual(inspection["stage_records"], partial["stage_records"])
        with self.assertRaises(native.MossContractError): bundles.select(inspection, 1, "zh")
        self.assertEqual(state.recover(slot)["units"][0]["sources"]["zh"]["caption"], "last-good")
        inspection["raw"] = "modified by viewer"
        self.assertEqual(state.draft(slot)["raw"], "unfinished raw output")
        partial["units"][0]["sources"]["zh"]["caption"] = "modified by runner"
        self.assertNotEqual(state.draft(slot)["units"], partial["units"])

    def test_old_run_tokens_cannot_commit_or_fail_over_new_success(self):
        slot = "t8-director-token"
        old = state.begin(slot); new = state.begin(slot)
        current = good_text("new complete result")
        self.assertTrue(state.commit(slot, new, current))
        self.assertFalse(state.commit(slot, old, good_text("stale old result")))
        state.failed(slot, old, {"raw": "old failure"}, "old_failure")
        self.assertEqual(state.recover(slot), bundles.validate(current))
        self.assertEqual(state.status(slot)["phase"], "completed")
        self.assertIsNone(state.draft(slot))
        self.assertFalse(state.commit("t8-director-missing", old, current))

    def test_token_is_rechecked_after_slow_failure_sanitization(self):
        slot = "t8-director-race"
        old = state.begin(slot)
        entered, resume = threading.Event(), threading.Event()
        original = state._inspection
        failures = []
        def slow(partial, code):
            entered.set()
            if not resume.wait(5): raise AssertionError("test synchronization timed out")
            return original(partial, code)
        def worker():
            try: state.failed(slot, old, {"raw": "stale partial"}, "old_failure")
            except BaseException as error: failures.append(error)
        with patch.object(state, "_inspection", slow):
            thread = threading.Thread(target=worker)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                new = state.begin(slot)
                state.commit(slot, new, good_text("newest"))
            finally:
                resume.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(state.recover(slot)["units"][0]["sources"]["zh"]["caption"], "newest")
        self.assertEqual(state.status(slot)["phase"], "completed")

    def test_failures_and_new_runs_cannot_extend_the_old_success_own_ttl(self):
        now = [0.0]
        with patch.object(state.time, "monotonic", side_effect=lambda: now[0]):
            slot = "t8-director-ttl"
            token = state.begin(slot); state.commit(slot, token, good_text("expires at 3600"))
            now[0] = 3590
            new = state.begin(slot); state.failed(slot, new, {"raw": "new failure"}, "failed")
            self.assertTrue(state.status(slot)["recoverable"])
            now[0] = 3600
            self.assertFalse(state.status(slot)["recoverable"])
            self.assertTrue(state.status(slot)["failed_draft_available"])
            with self.assertRaises(native.MossContractError): state.recover(slot)
            now[0] = 7190
            self.assertEqual(state.status(slot)["phase"], "missing")
            self.assertIsNone(state.draft(slot))

    def test_capacity_is_fifty_slots_and_reading_never_renews_expiry(self):
        first = "t8-director-cap-first"
        token = state.begin(first); state.commit(first, token, good_text())
        for index in range(49): state.begin(f"t8-director-cap-{index:03d}")
        self.assertEqual(len(state._RUNS), 50)
        self.assertTrue(state.status(first)["recoverable"])
        state.begin("t8-director-cap-overflow")
        self.assertEqual(len(state._RUNS), 50)
        self.assertEqual(state.status(first)["phase"], "missing")

    def test_failed_artifact_redacts_keys_bounds_json_bytes_and_handles_malformed_partial(self):
        slot = "t8-director-draft-budget"
        token = state.begin(slot)
        secret = "sk-" + "A" * 40
        state.failed(slot, token, {"units": [], "stage_records": [],
                     "raw": secret + "\n" + "文\r\n\x00" * 600000}, "https://private.invalid/key")
        artifact = state.draft(slot)
        encoded = json.dumps(artifact, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.assertLessEqual(len(encoded), state.MAX_FAILED_BYTES)
        self.assertTrue(artifact["truncated"])
        self.assertNotIn(secret, encoded.decode("utf-8"))
        self.assertIn("[REDACTED]", artifact["raw"])
        self.assertEqual(artifact["code"], "authoring_failed")
        self.assertTrue(state.status(slot)["truncated"])
        for partial in (None, [], {"units": [{}], "stage_records": [{"calls": True}], "raw": "\ud800"},
                        {"units": "bad", "stage_records": None, "raw": {}}, {"unknown": "must not retain"}):
            with self.subTest(partial=partial):
                state.failed(slot, token, partial, "invalid_partial")
                artifact = state.draft(slot)
                self.assertTrue(artifact["truncated"])
                json.dumps(artifact, ensure_ascii=False).encode("utf-8")
                self.assertNotIn("unknown", artifact)

    def test_recover_revalidates_cached_success_and_cannot_read_old_main_cache(self):
        slot = "t8-director-cache-boundary"
        with self.assertRaises(native.MossContractError): state.recover(slot)
        token = state.begin(slot); state.commit(slot, token, good_text())
        with state._LOCK:
            state._RUNS[slot]["last_good"] = '{"complete":true}'
        with self.assertRaises(native.MossContractError): state.recover(slot)
        # The module must not acquire the old main/shared result codec at all.
        source = Path(state.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from .completion_recovery", source)
        self.assertNotIn("from .moss_image_state", source)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        name = "t8_authoring_routes_cpu_test"
        package = types.ModuleType(name); package.__path__ = [str(root)]
        sys.modules[name] = package
        cls.routes = importlib.import_module(name + ".moss_authoring_routes")

    def setUp(self):
        self.routes.state.clear()

    def tearDown(self):
        self.routes.state.clear()

    def handlers(self):
        handlers = {}
        class Routes:
            def get(self, path):
                def add(handler): handlers[path] = handler; return handler
                return add
        server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=Routes())))
        with patch.dict(sys.modules, {"server": server}), patch.object(self.routes, "_REGISTERED", False):
            self.assertTrue(self.routes.register_moss_authoring_routes())
            self.assertTrue(self.routes.register_moss_authoring_routes())
        self.assertEqual(len(handlers), 2)
        return handlers

    def test_registration_does_not_import_absent_host_server_or_start_any_service(self):
        original = builtins.__import__
        def no_server(name, *args, **kwargs):
            if name == "server": raise AssertionError("must not import the host model graph")
            return original(name, *args, **kwargs)
        with patch.dict(sys.modules, {"server": None}), patch.object(builtins, "__import__", no_server), patch.object(self.routes, "_REGISTERED", False):
            self.assertFalse(self.routes.register_moss_authoring_routes())

    def test_same_origin_get_status_is_finite_and_draft_is_explicit_nostore(self):
        handlers = self.handlers()
        slot = "t8-director-route"
        token = self.routes.state.begin(slot)
        self.routes.state.failed(slot, token, {"units": [], "stage_records": [], "raw": "PRIVATE-INSPECTION"}, "source_failed")
        for path, handler in handlers.items():
            request = types.SimpleNamespace(headers={"Origin": "http://local.test"}, host="local.test", remote="127.0.0.1", match_info={"slot": slot})
            response = asyncio.run(handler(request))
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            data = json.loads(response.text)
            if "/status/" in path:
                self.assertEqual(set(data), {"recoverable", "phase", "code", "failed_draft_available", "truncated"})
                self.assertNotIn("PRIVATE-INSPECTION", response.text)
            else:
                self.assertEqual(data["raw"], "PRIVATE-INSPECTION")
                self.assertIs(data["complete"], False)
                self.assertIs(data["inspection_only"], True)
        self.assertTrue(all("{slot}" in path for path in handlers))

    def test_cross_origin_malformed_origin_and_missing_drafts_do_not_expose_data(self):
        handlers = self.handlers()
        for path, handler in handlers.items():
            for origin in ("http://another.invalid", "http://[", "https://local.test.evil"):
                request = types.SimpleNamespace(headers={"Origin": origin}, host="local.test", remote="127.0.0.1", match_info={"slot": "t8-director-missing"})
                response = asyncio.run(handler(request))
                self.assertEqual(response.status, 403)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            request = types.SimpleNamespace(headers={"Origin": "http://local.test"}, host="local.test", remote="127.0.0.1", match_info={"slot": "../../private"})
            response = asyncio.run(handler(request))
            self.assertEqual(response.status, 200 if "/status/" in path else 404)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertNotIn("private", response.text)


if __name__ == "__main__":
    unittest.main()
