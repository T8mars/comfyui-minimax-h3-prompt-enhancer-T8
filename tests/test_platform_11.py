import importlib.util
import json
import sys
import unittest
from pathlib import Path


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


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class Platform11Tests(unittest.TestCase):
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
        menu_preview = (ROOT / "web/js/template_menu_preview.js").read_text(encoding="utf-8")
        self.assertIn("activeCleanup?.()", menu_preview)
        self.assertIn("if (cleaned) return", menu_preview)

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
