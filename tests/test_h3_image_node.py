"""H3 Image integration contracts; synthetic providers, no paid inference."""
import asyncio
import base64
import copy
import importlib
import io
import json
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import requests
from test_moss_image import moss, Session, Response, StreamResponse

h = importlib.import_module(moss.__package__ + ".h3_image")
c = h.contract
Node = h.MiniMaxH3ImagePromptEnhancer


def reply(task=c.T2I, text="A quiet ivory cup on the left, with warm window light.", ratio="4:3"):
    return json.dumps({"expanded_caption": text, "aspect_ratio" if task == c.T2I else "target_aspect_ratio": ratio}, ensure_ascii=False)


class H3ImageNodeTests(unittest.TestCase):
    def cloud(self, *responses, **kwargs):
        session = Session(*(responses or (Response(reply()),)))
        with patch.object(h.requests, "Session", return_value=session):
            output = Node.execute(prompt="A cup.", api_key="test-not-real", **kwargs)
        return output, session

    def test_cloud_modes_keep_same_official_contract_and_close_session(self):
        for mode in h.API_MODES[:3]:
            out, session = self.cloud(api_mode=mode, openai_base_url="http://127.0.0.1:12345/v1", custom_model="model-test", target_words=5000)
            payload = session.calls[0][1]["json"]
            self.assertEqual(len(session.calls), 1)
            self.assertIn("approximately 5000 English words", str(payload["messages"]))
            self.assertNotIn("response_format", payload)
            self.assertTrue(session.closed)
            self.assertEqual(out.result[1], "4:3")
            self.assertEqual(json.loads(out.result[3])["target_words"], 5000)

    def test_edit_sparse_slots_preserve_picture_order_original_ratio_and_pixels(self):
        a = np.zeros((1, 17, 23, 3), dtype=np.float32); a[..., 0] = 1
        b = np.zeros((1, 29, 13, 3), dtype=np.float32); b[..., 2] = 1
        out, session = self.cloud(Response(reply(c.EDIT, ratio="23:17")), task_type=c.EDIT,
            reference_images={"reference_image_15": b, "reference_image_3": None, "reference_image_0": a}, api_mode=h.OPENAI_API_MODE,
            openai_base_url="http://127.0.0.1:12345/v1", custom_model="model-test")
        parts = session.calls[0][1]["json"]["messages"][0]["content"]
        self.assertEqual(parts[2]["text"], "Reference Media:\n- <Picture 1> [aspect_ratio 23:17]")
        self.assertEqual(parts[4]["text"], "Reference Media:\n- <Picture 2> [aspect_ratio 13:29]")
        for index, size, color in ((3, (23, 17), (255, 0, 0)), (5, (13, 29), (0, 0, 255))):
            encoded = parts[index]["image_url"]["url"].split(",", 1)[1]
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as picture:
                self.assertEqual(picture.size, size); self.assertEqual(picture.getpixel((0, 0)), color)
        mapping = json.loads(out.result[3])["image_map"]
        self.assertEqual([row["source_slot"] for row in mapping], ["reference_image_0", "reference_image_15"])

    def test_sixteen_slots_all_reach_cloud_and_invalid_batches_make_zero_posts(self):
        refs = {f"reference_image_{i}": np.zeros((1, 5 + i, 7 + i, 3)) for i in range(16)}
        out, session = self.cloud(Response(reply(c.EDIT)), task_type=c.EDIT, reference_images=refs, api_mode=h.AI_WORKSHOP_API_MODE)
        self.assertEqual(sum(part["type"] == "image_url" for part in session.calls[0][1]["json"]["messages"][0]["content"]), 16)
        for bad in ({"reference_image_0": np.zeros((2, 3, 4, 3))}, {"reference_image_16": np.zeros((1, 3, 4, 3))}):
            with patch.object(h.requests, "Session") as factory, self.assertRaises(h.H3ImageError):
                Node.execute(prompt="Edit.", task_type=c.EDIT, reference_images=bad)
            factory.assert_not_called()

    def test_invalid_preflight_has_no_provider_ownership(self):
        cases = [{"task_type": c.EDIT}, {"task_type": c.T2I, "reference_images": {"reference_image_0": np.zeros((1, 2, 3, 3))}},
                 {"target_words": -1}, {"target_words": True}, {"aspect_ratio": "7:5"}, {"max_corrections": 2}, {"prompt": ""}]
        for values in cases:
            with patch.object(h, "_generate") as generate, self.assertRaises((h.H3ImageError, ValueError)):
                Node.execute(**{"prompt": "A cup.", **values})
            generate.assert_not_called()

    def test_only_complete_contract_failure_gets_one_repair(self):
        out, session = self.cloud(Response('prefix ' + reply()), Response(reply()))
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[1][1]["json"]["messages"][:2], session.calls[0][1]["json"]["messages"])
        self.assertEqual(json.loads(out.result[3])["correction_calls"], 1)
        for response in (Response(reply(), finish="length"), Response(reply(), status=401), requests.Timeout("private"), Response("")):
            session = Session(response)
            with patch.object(h.requests, "Session", return_value=session), self.assertRaises(Exception):
                Node.execute(prompt="A cup.", api_key="test-not-real")
            self.assertEqual(len(session.calls), 1); self.assertTrue(session.closed)
        for repairs in (0, 1):
            session = Session(Response("bad"), Response("still bad"))
            with patch.object(h.requests, "Session", return_value=session), self.assertRaises(h.H3ImageError):
                Node.execute(prompt="A cup.", api_key="test-not-real", max_corrections=repairs)
            self.assertEqual(len(session.calls), repairs + 1)

    def test_valid_complete_stream_disconnect_and_literal_think_are_preserved(self):
        literal = "A sign reads '<think>keep</think>' and '<think>unfinished'."
        out, session = self.cloud(StreamResponse(reply(text=literal), error=requests.exceptions.ChunkedEncodingError("disconnect")),
                                  locked_text="<think>keep</think>\n<think>unfinished")
        self.assertEqual(out.result[0], literal); self.assertEqual(len(session.calls), 1)

    def test_shared_cloud_policy_and_schema_conflict_preflight(self):
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        config = config_module.build_provider_config(provider="OpenAI Compatible", openai_base_url="https://api.kimi.com/coding/v1",
            custom_model="model-test", extra_parameters_json={"max_completion_tokens": 2048})
        out, session = self.cloud(provider_config=config)
        payload = session.calls[0][1]["json"]
        self.assertNotIn("temperature", payload); self.assertNotIn("max_tokens", payload)
        self.assertEqual(payload["max_completion_tokens"], 2048)
        original = copy.deepcopy(config)
        config["provider_request_options"]["extra_parameters"]["response_format"] = {"type": "text"}
        with patch.object(h.requests, "Session") as factory, self.assertRaises(h.H3ImageError):
            Node.execute(prompt="A cup.", provider_config=config)
        factory.assert_not_called()
        self.assertNotIn("response_format", original["provider_request_options"]["extra_parameters"])

    def test_local_budget_schema_shared_override_and_cleanup(self):
        class Provider:
            def __init__(self, settings, vision): self.settings, self.vision, self.calls, self.closed = settings, vision, [], False; created.append(self)
            def __enter__(self): return self
            def __exit__(self, *_): self.closed = True
            def complete(self, messages, **kw): self.calls.append((messages, kw)); return replies.pop(0)
        for replies in ([reply()], ["bad", reply()], ["bad", "bad"], [""]):
            created = []; fails = replies[-1] in ("bad", "")
            with patch.object(h, "LocalQwenProvider", Provider):
                if fails:
                    with self.assertRaises(h.H3ImageError): Node.execute(prompt="A cup.", api_mode=h.LOCAL_QWEN_API_MODE)
                else:
                    Node.execute(prompt="A cup.", api_mode=h.LOCAL_QWEN_API_MODE, llm_max_tokens=256)
            provider = created[0]; self.assertTrue(provider.closed)
            for _, options in provider.calls:
                self.assertTrue(options["require_complete"]); self.assertEqual(options["response_format"], c.response_format(c.T2I))
            self.assertEqual(provider.settings.max_tokens, h.DEFAULT_MAX_TOKENS)

    def test_official_cloud_response_schema_name_is_compatible_and_preserved(self):
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        response_format = json.loads((c.VENDOR / "prompt/t2i/request_params.json").read_text(encoding="utf-8"))["response_format"]
        config = config_module.build_provider_config(provider="OpenAI Compatible", openai_base_url="http://127.0.0.1:12345/v1",
            custom_model="model-test", extra_parameters_json={"response_format": response_format})
        before = copy.deepcopy(config)
        _, session = self.cloud(provider_config=config, aspect_ratio="4:3")
        self.assertEqual(session.calls[0][1]["json"]["response_format"], response_format)
        self.assertEqual(config, before)

    def test_strata_real_loopback_edit(self):
        from test_strata_provider import http_fixture
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        with http_fixture(response={"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": reply(c.EDIT)}}]}) as (url, calls):
            config = config_module.build_provider_config(provider="Strata", strata_url=url)
            out = Node.execute(prompt="Edit.", task_type=c.EDIT, provider_config=config,
                reference_images={"reference_image_0": np.zeros((1, 13, 17, 3))})
        posts = [row[3] for row in calls if row[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertIn("aspect_ratio 17:13", str(posts[0]["messages"]))
        self.assertEqual(json.loads(out.result[3])["chat_post_attempts"], 1)

    def test_failed_run_preserves_cache_and_restore_ignores_current_inputs(self):
        slot = "t8-h3-image-cache-unit"
        good, _ = self.cloud(recovery_slot=slot)
        with patch.object(h, "_generate", side_effect=RuntimeError("failure")), self.assertRaises(RuntimeError):
            Node.execute(prompt="New brief", recovery_slot=slot)
        with patch.object(h, "_generate", side_effect=AssertionError("must skip")):
            restored = Node.execute(prompt=None, task_type="invalid", target_words=-5, provider_config={"bad": "invalid"},
                                    reference_images="invalid", recovery_slot=slot, recovery_action="restore_last")
        self.assertEqual(restored.result[:3], good.result[:3]); self.assertEqual(json.loads(restored.result[3])["origin"], "cache")
        token_a = h.state.begin(slot); token_b = h.state.begin(slot)
        with patch.object(h.state, "complete_recovery_record") as complete:
            self.assertFalse(h.state.commit(slot, token_a, good.result)); complete.assert_not_called()
            h.state.commit(slot, token_b, good.result); complete.assert_called_once()

    def test_linked_null_lazy_autogrow_and_schema(self):
        self.assertTrue(Node.validate_inputs(prompt=None, target_words=None, aspect_ratio=None, locked_text=None))
        self.assertNotEqual(Node.validate_inputs(prompt=""), True)
        self.assertEqual(Node.check_lazy_status(provider_config=None), ["provider_config"])
        self.assertEqual(Node.check_lazy_status(prompt="x", api_key=None, provider_config={"provider": "Local Qwen"},
            reference_images={"reference_image_3": (None, "reference_images.reference_image_3")}), ["reference_images.reference_image_3"])
        self.assertEqual(Node.check_lazy_status(recovery_action="restore_last", prompt=None, provider_config=None), [])
        schema = Node.define_schema()
        self.assertEqual(len(schema.outputs), 4)
        target = next(i for i in schema.inputs if i.id == "target_words")
        self.assertEqual(target.max, 9007199254740991)
        self.assertFalse(next(i for i in schema.inputs if i.id == "seed").control_after_generate)


if __name__ == "__main__": unittest.main()
