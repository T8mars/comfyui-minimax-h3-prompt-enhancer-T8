"""Real isolated HTTP fault tests; no model, GPU or external service calls."""
import contextlib
import http.server
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
strata = importlib.import_module("strata_provider")
recovery = importlib.import_module("completion_recovery")


def status(model="model-test"):
    return {"service": "strata", "protocol_version": 1, "model": model, "loaded": True,
            "auto_load": True, "started": 100, "instance_id": None, "context": {"native": 32768},
            "concurrency": {"serving": 1}, "vision": {"enabled": True, "available": True},
            "capabilities": {"video": {"contract_version": 1, "modes": ["frames", "native"],
                                       "native_verified": True, "limits": {"max_frames": 64}}}}


@contextlib.contextmanager
def http_fixture(**options):
    seen = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def answer(self, code, data):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except OSError:  # Expected when the client cancels its owned socket.
                pass
        def do_GET(self):
            seen.append(("GET", self.path, self.headers.get("Authorization"), None))
            if self.path == "/v1/models":
                self.answer(200, {"data": [{"id": "alias-test", "alias_of": "model-test"}]})
            else:
                self.answer(options.get("get_code", 200), options.get("status", status()))
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(("POST", self.path, self.headers.get("Authorization"), body))
            time.sleep(options.get("delay", 0))
            self.answer(options.get("post_code", 200), options.get("response", {
                "model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": "中文正文"}}]}))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


class StrataProviderTests(unittest.TestCase):
    def setUp(self):
        recovery.clear_recovery_records()

    def test_default_settings_are_independent_of_cloud_and_gguf(self):
        value = strata.StrataSettings.from_values({"local_max_tokens": 8192, "custom_model": "cloud", "api_key": "cloud-key"})
        self.assertEqual(value.max_tokens, 0)
        self.assertEqual(value.model, "AUTO")
        self.assertEqual(value.reasoning_effort, "none")

    def test_invalid_settings_are_rejected_including_dataclass_instances(self):
        for values in ({"max_tokens": True}, {"video_max_frames": 65}, {"timeout_s": float("nan")},
                       {"url": "http://user:password@127.0.0.1:8080"}, {"url": "http://127.0.0.1:8080/?key=x"},
                       {"url": "http://127.0.0.1:8080/v1/chat/completions"}, {"url": "https://example.com"},
                       strata.StrataSettings(max_tokens=-1)):
            with self.subTest(value=values), self.assertRaises(strata.StrataProviderError):
                strata.StrataSettings.from_values(values)

    def test_json_rejects_duplicates_nonfinite_and_surrogates(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '{"x":"\\ud800"}'):
            with self.assertRaises(strata.StrataProviderError):
                strata.strict_json(raw)
        cycle = []; cycle.append(cycle)
        with self.assertRaises(strata.StrataProviderError):
            strata.request_bytes(cycle)

    def test_key_only_uses_strata_environment(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "old-cloud-key", "SEEDANCE_API_KEY": "old-key", "STRATA_API_KEY": ""}):
            self.assertEqual(strata.resolve_key(strata.StrataSettings()), "")
        with patch.dict(os.environ, {"STRATA_API_KEY": "service-test-key"}):
            self.assertEqual(strata.resolve_key(strata.StrataSettings()), "service-test-key")

    def test_named_alias_missing_does_not_fall_back_to_environment(self):
        with patch.dict(os.environ, {"STRATA_API_KEY": "service-test-key"}), patch("credential_store.get_credential", side_effect=RuntimeError):
            with self.assertRaises(strata.StrataProviderError):
                strata.resolve_key(strata.StrataSettings(credential_alias="missing"))

    def test_metadata_and_complete_real_http_keep_chinese_and_options(self):
        with http_fixture() as (url, seen):
            run = strata.StrataRun({"url": url}, seed=19)
            try:
                with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "STRATA_API_KEY": ""}):
                    answer = run.complete([{"role": "user", "content": "图文测试"}], temperature=.7)
                self.assertEqual(answer, "中文正文")
                payload = next(row[3] for row in seen if row[0] == "POST")
                self.assertEqual(payload["model"], "model-test")
                self.assertEqual(payload["max_tokens"], 0)
                self.assertEqual(payload["reasoning_effort"], "none")
                self.assertEqual(payload["seed"], 19)
                self.assertFalse(payload["stream"])
                self.assertNotIn("max_completion_tokens", payload)
                self.assertTrue(all(row[2] is None for row in seen))
                self.assertEqual(run.requests, 1)
            finally:
                run.close()

    def test_alias_resolves_to_canonical_wire_model(self):
        with http_fixture() as (url, seen):
            run = strata.StrataRun({"url": url, "model": "alias-test"})
            try:
                run.complete([{"role": "user", "content": "test"}], temperature=.2)
                self.assertEqual(next(row[3] for row in seen if row[0] == "POST")["model"], "model-test")
            finally:
                run.close()

    def test_unknown_model_fails_without_post(self):
        with http_fixture() as (url, seen):
            run = strata.StrataRun({"url": url, "model": "unknown"})
            try:
                with self.assertRaisesRegex(strata.StrataProviderError, "Model mismatch"):
                    run.complete([{"role": "user", "content": "test"}], temperature=.2)
                self.assertFalse(any(row[0] == "POST" for row in seen))
            finally:
                run.close()

    def test_wrong_service_and_auth_fail_without_post(self):
        for options in ({"status": {**status(), "service": "other"}}, {"get_code": 401}):
            with http_fixture(**options) as (url, seen):
                run = strata.StrataRun({"url": url})
                try:
                    with self.assertRaises(strata.StrataProviderError):
                        run.complete([{"role": "user", "content": "test"}], temperature=.2)
                    self.assertFalse(any(row[0] == "POST" for row in seen))
                finally:
                    run.close()

    def test_truncation_empty_and_model_mismatch_are_not_success(self):
        for response in ({"model": "model-test", "choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
                         {"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": "<think>thinking</think>"}}]},
                         {"model": "different", "choices": [{"finish_reason": "stop", "message": {"content": "wrong"}}]}):
            with http_fixture(response=response) as (url, seen):
                run = strata.StrataRun({"url": url})
                try:
                    with self.assertRaises(strata.StrataProviderError):
                        run.complete([{"role": "user", "content": "test"}], temperature=.2)
                    self.assertEqual(sum(row[0] == "POST" for row in seen), 1)
                finally:
                    run.close()

    def test_audio_remote_image_and_video_url_fail_before_post(self):
        for part in ({"type": "video_url", "video_url": {"url": "https://example.test"}},
                     {"type": "input_audio", "input_audio": {}},
                     {"type": "image_url", "image_url": {"url": "C:/private.png"}}):
            with http_fixture() as (url, seen):
                run = strata.StrataRun({"url": url})
                try:
                    with self.assertRaises(strata.StrataProviderError):
                        run.complete([{"role": "user", "content": [part]}], temperature=.2)
                    self.assertFalse(any(row[0] == "POST" for row in seen))
                finally:
                    run.close()

    def test_native_unverified_is_not_silently_downgraded(self):
        value = status(); value["capabilities"]["video"]["native_verified"] = False
        with http_fixture(status=value) as (url, seen):
            run = strata.StrataRun({"url": url, "video_mode": "native"})
            try:
                with self.assertRaisesRegex(strata.StrataProviderError, "not verified"):
                    run.complete([{"role": "user", "content": [{"type": "strata_video", "frames": []}]}], temperature=.2)
                self.assertFalse(any(row[0] == "POST" for row in seen))
            finally:
                run.close()

    def test_cancel_pending_body_closes_only_owned_connection(self):
        with http_fixture(delay=2) as (url, seen):
            client = strata.StrataClient({"url": url}, key="")
            started = time.monotonic()
            def cancel():
                if time.monotonic() - started > .2:
                    raise RuntimeError("cancelled")
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                client.request("/v1/chat/completions", {"messages": []}, timeout=5, check=cancel)
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(sum(row[0] == "POST" for row in seen), 1)

    def test_post_is_not_retried_and_errors_hide_upstream_body(self):
        with http_fixture(post_code=503, response={"error": {"message": "private-user-text"}}) as (url, seen):
            run = strata.StrataRun({"url": url})
            try:
                with self.assertRaises(strata.StrataProviderError) as raised:
                    run.complete([{"role": "user", "content": "test"}], temperature=.2)
                self.assertNotIn("private-user-text", str(raised.exception))
                self.assertEqual(sum(row[0] == "POST" for row in seen), 1)
            finally:
                run.close()

    def test_preflight_does_not_overwrite_prior_recovery(self):
        recovery.begin_recovery_record("node-test", "slot-test-123", "old-provider")
        recovery.complete_recovery_record("node-test", "slot-test-123", ("old-result",))
        with http_fixture(get_code=401) as (url, _seen):
            run = strata.StrataRun({"url": url})
            token = strata._RUN.set(run)
            try:
                recovery.begin_recovery_record("node-test", "slot-test-123", "Strata")
                with self.assertRaises(strata.StrataProviderError):
                    run.complete([{"role": "user", "content": "test"}], temperature=.2)
                recovery.mark_recovery_failed("node-test", "slot-test-123", RuntimeError())
                self.assertEqual(recovery.recover_outputs("node-test", "slot-test-123", 1), ("old-result",))
            finally:
                strata._RUN.reset(token); run.close()

    def test_only_chat_post_can_start_recovery(self):
        with http_fixture() as (url, _seen):
            run = strata.StrataRun({"url": url}); token = strata._RUN.set(run)
            try:
                recovery.begin_recovery_record("node-test", "slot-test-123", "Strata")
                run.identity()
                self.assertEqual(recovery.recovery_status("node-test", "slot-test-123")["state"], "missing")
                run.complete([{"role": "user", "content": "test"}], temperature=.2)
                recovery.complete_recovery_record("node-test", "slot-test-123", ("final-result",))
                self.assertEqual(recovery.recover_outputs("node-test", "slot-test-123", 1), ("final-result",))
            finally:
                strata._RUN.reset(token); run.close()


if __name__ == "__main__":
    unittest.main()
