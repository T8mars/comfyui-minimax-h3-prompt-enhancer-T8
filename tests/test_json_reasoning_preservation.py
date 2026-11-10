"""Structured literal data survives provider/cloud/local normalization."""
import importlib
import json
from pathlib import Path
import sys
import unittest

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import provider_transport as transport
import h3_image_contract as contract


class StreamResponse:
    status_code = 200
    headers = {"Content-Type": "text/event-stream"}
    def __init__(self, chunks, finish="stop", disconnect=False):
        self.chunks, self.finish, self.disconnect, self.closed = chunks, finish, disconnect, False
    def iter_lines(self, decode_unicode=False):
        for chunk in self.chunks:
            yield ("data: " + json.dumps({"choices": [{"delta": {"content": chunk}}]}, ensure_ascii=False)).encode("utf-8")
        if self.finish is not None:
            yield ("data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": self.finish}]})).encode("utf-8")
        if self.disconnect:
            raise requests.ConnectionError("test disconnect")
        if self.finish is not None:
            yield b"data: [DONE]"
    def close(self): self.closed = True


class Session:
    def __init__(self, response): self.response, self.calls = response, 0
    def post(self, *args, **kwargs):
        self.calls += 1
        return self.response


def request(response):
    session = Session(response)
    def accept(text):
        try:
            contract.parse_result(text, contract.T2I)
            return True
        except contract.H3ImageContractError:
            return False
    returned = transport.request_chat_completion(
        session=session, url="https://example.invalid/v1/chat/completions", api_key="test-placeholder",
        payload={"stream": True}, timeout=1, retry_delays=(), retryable_status_codes=frozenset(),
        route_kwargs=lambda *_: {}, is_retryable_network_error=lambda _: False, sleep=lambda _: None,
        network_error=lambda *_: RuntimeError("network"), http_error=lambda *_: None,
        invalid_json_error=lambda: RuntimeError("invalid"), missing_content_error=lambda: RuntimeError("missing"),
        empty_content_error=lambda: RuntimeError("empty"), require_complete=True, stream_acceptor=accept)
    return returned.text, session.calls


class JsonReasoningPreservationTests(unittest.TestCase):
    def test_complete_json_tags_are_data_not_reasoning(self):
        for caption in ("'<think>keep</think>'", "'<think>'", "'</think>'", "'<THINK role=x>keep</THINK>'"):
            raw = json.dumps({"expanded_caption": caption, "aspect_ratio": "1:1"})
            with self.subTest(caption=caption):
                self.assertEqual(transport.strip_inline_reasoning(raw), raw)
                self.assertEqual(transport.strip_inline_reasoning(" \n" + raw + "\n"), " \n" + raw + "\n")
                self.assertEqual(transport.strip_inline_reasoning("<think>private</think>\n" + raw), raw)
                self.assertEqual(transport.strip_inline_reasoning("</think>\n" + raw), raw)

    def test_pure_json_fence_preserves_all_internal_tags(self):
        raw = json.dumps({"expanded_caption": "<think>keep</think> <think>", "aspect_ratio": "1:1"})
        fenced = "```json\n" + raw + "\n```"
        self.assertEqual(transport.strip_inline_reasoning(fenced), fenced)
        self.assertEqual(transport.strip_inline_reasoning("<think>private</think>\n" + fenced), fenced)

    def test_existing_plain_text_cleanup_and_unclosed_reasoning(self):
        for original, expected in [("ordinary  text", "ordinary  text"),
                                    ("<think>private</think>\nfinal answer", "final answer"),
                                    ("</think>\nfinal answer", "final answer"),
                                    ("final<think>private", "final"),
                                    ("<think>not closed {\"x\":1}", "")]:
            self.assertEqual(transport.strip_inline_reasoning(original), expected)

    def test_both_runtime_wrappers_share_literal_protection_and_preserve_think_on(self):
        raw = json.dumps({"expanded_caption": "'<think>keep</think>' and '<think>'", "aspect_ratio": "1:1"})
        for name in ("local_qwen_standalone_runtime", "local_qwen_python_runtime"):
            runtime = importlib.import_module(name)
            with self.subTest(runtime=name):
                self.assertEqual(runtime._finalize_local_content(raw, think_mode=False), raw)
                self.assertEqual(runtime._finalize_local_content("<think>private</think>" + raw, think_mode=False), raw)
                self.assertEqual(runtime._finalize_local_content("<think>private</think>" + raw, think_mode=True), "<think>private</think>" + raw)
                self.assertEqual(runtime._finalize_local_content([{"type": "text", "text": raw[:23]}, {"type": "text", "text": raw[23:]}], think_mode=False), raw)

    def test_fragmented_sse_does_not_commit_cleaned_partial_literal(self):
        raw = json.dumps({"expanded_caption": "标牌 '<think>keep</think>' then '<think>'", "aspect_ratio": "1:1"}, ensure_ascii=False)
        text = "<think>private</think>\n" + raw
        response = StreamResponse([text[index:index + 3] for index in range(0, len(text), 3)])
        output, calls = request(response)
        self.assertEqual(output, raw)
        self.assertEqual(calls, 1)
        self.assertTrue(response.closed)

    def test_complete_disconnect_accepted_only_by_strict_contract_and_never_reposted(self):
        raw = json.dumps({"expanded_caption": "'<think>keep</think>'", "aspect_ratio": "1:1"})
        output, calls = request(StreamResponse([raw], finish=None, disconnect=True))
        self.assertEqual(output, raw)
        self.assertEqual(calls, 1)
        with self.assertRaises(RuntimeError):
            request(StreamResponse([raw[:-1]], finish=None, disconnect=True))

    def test_length_marker_rejects_even_complete_json(self):
        raw = json.dumps({"expanded_caption": "'<think>keep</think>'", "aspect_ratio": "1:1"})
        with self.assertRaises(transport.ChatCompletionTruncatedError):
            request(StreamResponse([raw], finish="length"))


if __name__ == "__main__":
    unittest.main()
