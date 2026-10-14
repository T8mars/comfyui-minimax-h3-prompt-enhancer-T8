"""Read-only speech readiness and finite recovery metadata, no real ASR/LLM."""
import asyncio
import importlib
import gzip
import json
import sys
import types
import unittest
from unittest.mock import patch

from test_directional_skills import h3

routes = importlib.import_module(h3.__package__ + ".strata_routes")
speech = importlib.import_module(h3.__package__ + ".speech_reference")
recovery = importlib.import_module(h3.__package__ + ".completion_recovery")


class SpeechRouteTests(unittest.TestCase):
    def test_actual_http_probe_bounds_decompressed_body_before_service_lookup(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        async def exercise():
            table = web.RouteTableDef()
            server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=table)))
            with patch.dict(sys.modules, {"server": server}), patch.object(routes, "_REGISTERED", False):
                self.assertTrue(routes.register_strata_routes())
            app = web.Application(); app.add_routes(table)
            async with TestClient(TestServer(app)) as client:
                origin = str(client.make_url("/")).rstrip("/")
                headers = {"Origin": origin, "Content-Encoding": "gzip", "Content-Type": "application/json"}
                with patch.object(routes, "probe_speech", return_value={"read_only": True}) as probe:
                    raw = b'{"strata_url":"http://127.0.0.1:8080"}' + b' ' * 9000
                    response = await client.post("/t8-prompt-enhancer/speech/capabilities", data=gzip.compress(raw), headers=headers)
                    self.assertEqual(response.status, 400)
                    probe.assert_not_called()
                    response = await client.post("/t8-prompt-enhancer/speech/capabilities", data=gzip.compress(b'{}'), headers=headers)
                    self.assertEqual(response.status, 200)
                    probe.assert_called_once_with({})
        asyncio.run(exercise())

    def test_actual_http_probe_rejects_ambiguous_duplicate_settings(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        async def exercise():
            table = web.RouteTableDef()
            server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=table)))
            with patch.dict(sys.modules, {"server": server}), patch.object(routes, "_REGISTERED", False):
                routes.register_strata_routes()
            app = web.Application(); app.add_routes(table)
            async with TestClient(TestServer(app)) as client:
                headers = {"Origin": str(client.make_url("/")).rstrip("/"), "Content-Type": "application/json"}
                with patch.object(routes, "probe_speech", return_value={"read_only": True}) as probe:
                    response = await client.post("/t8-prompt-enhancer/speech/capabilities", data=b'{"strata_timeout_s":5,"strata_timeout_s":10}', headers=headers)
                    self.assertEqual(response.status, 400)
                    probe.assert_not_called()
        asyncio.run(exercise())

    def test_probe_is_asr_only_and_redacts_service_paths(self):
        caps = dict(supported=True, device="cpu", timing_precision="segment", cpu_guard=True,
                    contract_version=1, missing=["private-path"], model="private-model")
        with patch.object(speech.SpeechASRClient, "request", return_value=caps) as request:
            result = routes.probe_speech()
        self.assertEqual(request.call_args.args, ("/v1/asr/capabilities",))
        self.assertEqual(result, dict(connected=True, supported=True, device="cpu", cpu_guard=True,
                                     timing_precision="segment", read_only=True, asr_post_count=0))
        for value in (True, "1", None, 0):
            with patch.object(speech.SpeechASRClient, "request", return_value={**caps, "contract_version": value}):
                self.assertFalse(routes.probe_speech()["cpu_guard"])
        for value in ({**caps, "supported": 1}, {**caps, "device": "other"}, {**caps, "timing_precision": "word"}):
            with patch.object(speech.SpeechASRClient, "request", return_value=value), self.assertRaises(routes.StrataProviderError):
                routes.probe_speech()

    def test_route_same_origin_bounded_fields_and_no_service_post(self):
        registered = {}
        class Router:
            def post(self, path):
                return lambda callback: registered.setdefault(path, callback)
        server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=Router())))
        class Request:
            headers = {"Origin": "http://127.0.0.1:8188"}
            host = "127.0.0.1:8188"
            remote = "127.0.0.1"
            content_length = 2
            def __init__(self, body):
                self.body = body
                class Content:
                    def __init__(self, raw): self.raw = raw
                    async def read(self, amount):
                        chunk, self.raw = self.raw[:amount], self.raw[amount:]
                        return chunk
                self.content = Content(json.dumps(body).encode("utf-8"))
            async def json(self): return self.body
        with patch.dict(sys.modules, {"server": server}), patch.object(routes, "_REGISTERED", False):
            self.assertTrue(routes.register_strata_routes())
            self.assertTrue(routes.register_strata_routes())
        callback = registered["/t8-prompt-enhancer/speech/capabilities"]
        for fields in ({"api_key": "private"}, {"strata_max_tokens": 10}, [], {"device": "cuda"}):
            with patch.object(routes, "probe_speech") as probe:
                self.assertEqual(asyncio.run(callback(Request(fields))).status, 400)
                probe.assert_not_called()
        for length in (None, 8193):
            request = Request({}); request.content_length = length
            with patch.object(routes, "probe_speech") as probe:
                self.assertEqual(asyncio.run(callback(request)).status, 400)
                probe.assert_not_called()
        request = Request({}); request.headers = {"Origin": "https://evil.invalid"}
        with patch.object(routes, "probe_speech") as probe:
            self.assertEqual(asyncio.run(callback(request)).status, 403); probe.assert_not_called()
        with patch.object(routes, "probe_speech", return_value={"read_only": True}) as probe:
            result = asyncio.run(callback(Request({})))
        self.assertEqual(result.status, 200); self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(result.body), {"read_only": True}); probe.assert_called_once_with({})

    def test_speech_metadata_never_persists_source_words_paths_or_roles(self):
        value = speech.provided_reference("private utterance", purpose="keep_dialogue", speaker_map={"default": "private role"})
        metadata = speech.speech_metadata(value)
        actual = recovery.safe_director_metadata({"speech_reference": {**metadata, "text": "private utterance", "path": "private-path", "speaker_map": value["speaker_map"]}})
        finite = {key: metadata[key] for key in ("schema_version", "purpose", "source", "status", "cue_count", "timed", "requires_review")}
        self.assertEqual(actual, {"speech_reference": finite})
        self.assertNotIn("private", json.dumps(actual))
        for key, invalid in (("cue_count", True), ("purpose", []), ("status", {}), ("source", "private"), ("timed", 1)):
            self.assertEqual(recovery.safe_director_metadata({"speech_reference": {**metadata, key: invalid}}), {})

    def test_new_speech_failure_codes_survive_finite_quality_metadata(self):
        actual = recovery.safe_quality_metadata({"result": "candidate_rejected", "correction_calls": 1,
            "issue_codes": ["speech_extra_words", "speech_vocal_language_changed", "speech_native_dialogue", "PRIVATE WORDS"], "text": "PRIVATE"})
        self.assertEqual(actual["issue_codes"], ["speech_extra_words", "speech_vocal_language_changed", "speech_native_dialogue"])
        self.assertNotIn("PRIVATE", json.dumps(actual))


if __name__ == "__main__":
    unittest.main()
