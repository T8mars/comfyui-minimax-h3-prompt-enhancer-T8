import importlib.util
import json
import sys
import unittest
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


transport = load_module("t8_provider_transport_test", "provider_transport.py")
diagnostics = load_module("t8_execution_diagnostics_test", "execution_diagnostics.py")


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class StreamResponse(Response):
    def __init__(self, lines):
        super().__init__(200, {})
        self.headers = {"Content-Type": "text/event-stream; charset=utf-8"}
        self.lines = list(lines)
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        del decode_unicode
        for item in self.lines:
            if isinstance(item, BaseException):
                raise item
            yield item

    def close(self):
        self.closed = True


class WrongCharsetStreamResponse(StreamResponse):
    def __init__(self, lines):
        super().__init__(lines)
        self.headers = {"Content-Type": "text/event-stream; charset=iso-8859-1"}
        self.decode_unicode_flags = []

    def iter_lines(self, decode_unicode=True):
        self.decode_unicode_flags.append(decode_unicode)
        for item in self.lines:
            raw = item.encode("utf-8") if isinstance(item, str) else item
            if decode_unicode and isinstance(raw, bytes):
                yield raw.decode("iso-8859-1")
            else:
                yield raw


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class Platform11Tests(unittest.TestCase):
    @staticmethod
    def stream_request(response, checkpoints=None):
        session = Session([response])
        result = transport.request_chat_completion(
            session=session,
            url="https://provider.invalid/v1/chat/completions",
            api_key="placeholder-not-a-live-secret",
            payload={"messages": [], "stream": True},
            timeout=(1, 2),
            retry_delays=(0.25, 0.5),
            retryable_status_codes=frozenset(),
            route_kwargs=lambda _attempt, _has_retry: {},
            is_retryable_network_error=lambda _error: True,
            sleep=lambda _delay: None,
            network_error=lambda _error, attempt, delays: RuntimeError(
                f"network attempt={attempt} remaining_policy={len(delays)}"
            ),
            http_error=lambda *_args: None,
            invalid_json_error=lambda: RuntimeError("json"),
            missing_content_error=lambda: RuntimeError("missing"),
            empty_content_error=lambda: RuntimeError("empty"),
            on_checkpoint=(
                (lambda text, complete, response_id: checkpoints.append((text, complete, response_id)))
                if checkpoints is not None
                else None
            ),
        )
        return session, result

    def test_stream_transport_returns_complete_checkpoint_and_response_id(self):
        checkpoints = []
        response = StreamResponse([
            'data: {"id":"chatcmpl-test","choices":[{"delta":{"content":"hello "}}]}',
            'data: {"id":"chatcmpl-test","choices":[{"delta":{"content":"world"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ])
        session, result = self.stream_request(response, checkpoints)
        self.assertEqual(result.text, "hello world")
        self.assertEqual(result.response_id, "chatcmpl-test")
        self.assertEqual(len(session.calls), 1)
        self.assertTrue(response.closed)
        self.assertTrue(checkpoints[-1][1])

    def test_stream_transport_decodes_raw_sse_bytes_as_utf8_despite_bad_charset(self):
        expected = "镜头稳定跟随舞者，雨夜街道的倒影自然变化。"
        event = json.dumps(
            {"id": "chatcmpl-utf8", "choices": [{"delta": {"content": expected}, "finish_reason": "stop"}]},
            ensure_ascii=False,
        )
        response = WrongCharsetStreamResponse([f"data: {event}", "data: [DONE]"])
        _session, result = self.stream_request(response)
        self.assertEqual(result.text, expected)
        self.assertEqual(response.decode_unicode_flags, [False])

    def test_stream_disconnect_after_finish_marker_returns_without_resubmit(self):
        response = StreamResponse([
            'data: {"id":"chatcmpl-finished","choices":[{"delta":{"content":"complete"},"finish_reason":"stop"}]}',
            requests.exceptions.ProxyError("proxy dropped during final close"),
        ])
        session, result = self.stream_request(response)
        self.assertEqual(result.text, "complete")
        self.assertEqual(len(session.calls), 1)

    def test_stream_disconnect_before_finish_never_resubmits_paid_request(self):
        checkpoints = []
        response = StreamResponse([
            'data: {"id":"chatcmpl-partial","choices":[{"delta":{"content":"partial"}}]}',
            requests.exceptions.ProxyError("proxy dropped mid-stream"),
        ])
        with self.assertRaisesRegex(RuntimeError, "remaining_policy=0"):
            self.stream_request(response, checkpoints)
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0][0], "partial")
    def test_shared_transport_retries_and_preserves_content_parts(self):
        session = Session([
            Response(503, {}),
            Response(200, {"choices": [{"message": {"content": [
                {"type": "text", "text": "first"},
                {"type": "text", "text": " second"},
            ]}}]}),
        ])
        sleeps = []
        events = []
        result = transport.request_chat_completion(
            session=session,
            url="https://provider.invalid/v1/chat/completions",
            api_key="placeholder-not-a-live-secret",
            payload={"messages": []},
            timeout=(1, 2),
            retry_delays=(0.25,),
            retryable_status_codes=frozenset({503}),
            route_kwargs=lambda _attempt, _has_retry: {"proxies": {}},
            is_retryable_network_error=lambda _error: False,
            sleep=sleeps.append,
            network_error=lambda *_args: RuntimeError("network"),
            http_error=lambda response, _attempt: (_ for _ in ()).throw(RuntimeError(str(response.status_code))),
            invalid_json_error=lambda: RuntimeError("json"),
            missing_content_error=lambda: RuntimeError("missing"),
            empty_content_error=lambda: RuntimeError("empty"),
            on_attempt=lambda attempt, event: events.append((attempt, event)),
        )
        self.assertEqual(result.text, "first second")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(len(session.calls), 2)
        self.assertIn((1, "retry_http_503"), events)
        self.assertIn((2, "success"), events)

    def test_shared_transport_removes_inline_reasoning_from_cloud_content(self):
        session = Session([
            Response(200, {"choices": [{"message": {
                "reasoning_content": "separate private trace",
                "content": "<think source=\"provider\">inline private trace</think>\nFINAL PROMPT",
            }}]}),
        ])
        result = transport.request_chat_completion(
            session=session,
            url="https://provider.invalid/v1/chat/completions",
            api_key="placeholder-not-a-live-secret",
            payload={"messages": []},
            timeout=(1, 2),
            retry_delays=(),
            retryable_status_codes=frozenset(),
            route_kwargs=lambda _attempt, _has_retry: {},
            is_retryable_network_error=lambda _error: False,
            sleep=lambda _delay: None,
            network_error=lambda *_args: RuntimeError("network"),
            http_error=lambda *_args: None,
            invalid_json_error=lambda: RuntimeError("json"),
            missing_content_error=lambda: RuntimeError("missing"),
            empty_content_error=lambda: RuntimeError("empty"),
        )
        self.assertEqual(result.text, "FINAL PROMPT")
        self.assertNotIn("private trace", result.text)

    def test_shared_transport_rejects_reasoning_only_cloud_content(self):
        session = Session([
            Response(200, {"choices": [{"message": {
                "content": "<think>private trace without a final answer</think>",
            }}]}),
        ])
        with self.assertRaisesRegex(RuntimeError, "empty"):
            transport.request_chat_completion(
                session=session,
                url="https://provider.invalid/v1/chat/completions",
                api_key="placeholder-not-a-live-secret",
                payload={"messages": []},
                timeout=(1, 2),
                retry_delays=(),
                retryable_status_codes=frozenset(),
                route_kwargs=lambda _attempt, _has_retry: {},
                is_retryable_network_error=lambda _error: False,
                sleep=lambda _delay: None,
                network_error=lambda *_args: RuntimeError("network"),
                http_error=lambda *_args: None,
                invalid_json_error=lambda: RuntimeError("json"),
                missing_content_error=lambda: RuntimeError("missing"),
                empty_content_error=lambda: RuntimeError("empty"),
            )

    def test_diagnostics_are_allowlisted_and_redact_urls_keys_and_error_text(self):
        secret = "sk-" + "x" * 32
        run = diagnostics.DiagnosticsRun(
            component=f"H3 {secret}",
            provider="OpenAI https://private.example/v1",
            total_stages=2,
            emit_progress=False,
        )
        run.advance("upload", attempts=2, asset_count=3, api_key=secret, prompt="private prompt")
        run.complete("error", RuntimeError(f"private prompt {secret}"))
        snapshot = diagnostics.diagnostics_snapshot()
        encoded = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("private.example", encoded)
        self.assertNotIn("private prompt", encoded)
        record = snapshot["recent"][0]
        self.assertEqual(set(record), {
            "schema_version", "component", "provider", "outcome", "duration_ms",
            "stages", "error_type", "error_category",
        })
        self.assertEqual(set(record["stages"][0]), {"stage", "duration_ms", "attempts", "asset_count"})

    def test_compatibility_matrix_matches_frontend_migration_contracts(self):
        matrix = (ROOT / "COMPATIBILITY.md").read_text(encoding="utf-8")
        expected = {
            "web/js/minimax_h3_prompt_enhancer.js": (31, "16, 17, 19, or 21"),
            "web/js/seedance20_prompt_enhancer.js": (35, "23 or 25"),
            "web/js/music3_prompt_enhancer.js": (38, "31-value"),
        }
        for relative, (count, legacy) in expected.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            block = source.split("const SERIALIZED_WIDGET_NAMES = [", 1)[1].split("];", 1)[0]
            self.assertEqual(block.count('"') // 2, count)
            self.assertIn(legacy, matrix)

    def test_recovery_button_is_present_on_three_core_nodes_without_resubmitting_http(self):
        helper = (ROOT / "web/js/completion_recovery_ui.mjs").read_text(encoding="utf-8")
        core = (ROOT / "web/js/completion_recovery_core.mjs").read_text(encoding="utf-8")
        self.assertIn("恢复上次云端结果（不重新生成）", helper)
        self.assertIn("restoreCompletionResult", helper)
        self.assertIn("t8_completion_recovery_slot", core)
        self.assertIn("await queuePrompt(0, 1, [String(node.id)])", core)
        self.assertNotIn("/v1/chat/completions", helper + core)
        self.assertNotIn('method: "POST"', helper + core)
        for relative in (
            "web/js/minimax_h3_prompt_enhancer.js",
            "web/js/seedance20_prompt_enhancer.js",
            "web/js/music3_prompt_enhancer.js",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('import { addCompletionRecoveryButton }', source, relative)
            self.assertIn("addCompletionRecoveryButton(this, NODE_ID", source, relative)

    def test_template_browser_is_lazy_persistent_and_responsive(self):
        source = (ROOT / "web/js/template_browser.js").read_text(encoding="utf-8")
        for contract in (
            'localStorage.getItem',
            'localStorage.setItem',
            'image.loading = "lazy"',
            'window.innerWidth < 780',
            'window.addEventListener("resize", applyResponsiveLayout)',
            'window.removeEventListener("resize", applyResponsiveLayout)',
            'activeBrowser?.dismiss?.()',
            'GIF 仅供人类选择时预览，不会发送给 LLM',
        ):
            self.assertIn(contract, source)
        case_ui = (ROOT / "web/js/case_template_ui.js").read_text(encoding="utf-8")
        self.assertIn("node.widgets.splice(detailIndex, 0, browserWidget)", case_ui)
        self.assertIn("preview_manager: previewManagerAction()", case_ui)
        browser = (ROOT / "web/js/template_browser.js").read_text(encoding="utf-8")
        self.assertIn('managePreviews.dataset.t8PreviewManagerAction = "true"', browser)
        self.assertIn("首次使用或 GIF 未显示？请先检查并更新动态预览。", browser)
        self.assertIn("openPreviewAssetManager(catalog)", browser)
        menu_preview = (ROOT / "web/js/template_menu_preview.js").read_text(encoding="utf-8")
        self.assertIn("activeCleanup?.()", menu_preview)
        self.assertIn("if (cleaned) return", menu_preview)
        self.assertIn('manage.dataset.t8PreviewManagerAction = "true"', menu_preview)
        preview_manager = (ROOT / "web/js/preview_asset_ui.js").read_text(encoding="utf-8")
        self.assertIn("activeManager?.dismiss?.()", preview_manager)

    def test_h3_secure_api_key_draw_does_not_schedule_a_redraw_loop(self):
        source = (ROOT / "web/js/minimax_h3_prompt_enhancer.js").read_text(encoding="utf-8")
        secure_widget = source.split("const secureWidget = node.addDOMWidget", 1)[1].split(
            "node.t8ApiKeySecureWidget", 1
        )[0]
        on_draw = secure_widget.split("onDraw(widget)", 1)[1].split("},", 1)[0]
        self.assertIn("delete widget.width", on_draw)
        self.assertNotIn("setDirtyCanvas", on_draw)

    def test_release_tools_and_routes_remain_importable_without_initialized_comfy_server(self):
        verifier = (ROOT / "tools/verify_repository.py").read_text(encoding="utf-8")
        self.assertIn("except ModuleNotFoundError", verifier)
        self.assertIn("import tomli as tomllib", verifier)
        for relative in ("case_library_routes.py", "local_qwen_routes.py", "diagnostics_routes.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn('sys.modules.get("server")', source)
                self.assertNotIn("from server import PromptServer", source)
        music_source = (ROOT / "music3.py").read_text(encoding="utf-8")
        self.assertIn('sys.modules.get("comfy.model_management")', music_source)
        self.assertNotIn("from comfy import model_management", music_source)


if __name__ == "__main__":
    unittest.main()
