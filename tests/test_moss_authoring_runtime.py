"""Director transport/lifecycle fixtures; never uses a real model or paid API."""
from __future__ import annotations

import copy
import importlib
import json
import sys
import unittest
from unittest.mock import patch

import numpy as np

import test_moss_image as base
from test_moss_authoring_contract import comic

r = importlib.import_module(base.moss.__package__ + ".moss_authoring_runtime")
m, a, c, b, native = r.m, r.a, r.c, r.b, r.native
providers = importlib.import_module(m.__package__ + ".provider_config")


def controls(**updates):
    return {"brief": "简短版：红帽人物在窗前安静地伸手。", "profile": a.COMIC, "width": 1256, "height": 1672,
        "max_output_chars": 0, "max_corrections": 1, "page_count": 2, "reference_mode": "independent",
        "descriptive_language": native.LANG_AUTO, "preserve_layout": True,
        "continuity_context": "User fact: the same character keeps the red hat.", "locked_text": "",
        "layout_context_json": "", "seed": 7, **updates}


def journal():
    return {"logical_generation_calls": 0, "chat_post_attempts": 0, "correction_calls": 0, "failed_raw": ""}, {"units": [], "stage_records": []}


def page_plan(key, *, refs=()):
    source, _sidecar = comic()
    return {"unit_id": key, "objective": "The character reaches toward the window.", "entry_state": "At the window.",
        "change": "One small gesture.", "exit_state": "The hand stays near the frame.", "layout_intent": "One quiet view.",
        "reference_indices": list(refs), "reference_selection_reason": "",
        "locked_visible_blocks": c.visible_blocks(source)}


def plan(count=2, *, ids=None, refs=()):
    return {"shared_facts": "Derived note: the window stays in place.",
            "units": [page_plan(key, refs=refs) for key in (ids or [f"page-{index}" for index in range(1, count + 1)])]}


def source_reply():
    source, sidecar = comic()
    sidecar["state"]["identity_anchors"] = {"actor": "red hat"}
    return {"source": source, "sidecar": sidecar}


def translation_reply():
    return {"summary_caption": "安静的一页。", "item_captions": {"frame": "手越过黑色画框。", "actor": "戴红帽的人伸出手。", "words": "小对白框。"}}


def encode(value):
    return value if isinstance(value, (str, BaseException, base.Response)) else json.dumps(value, ensure_ascii=False)


def payload_request(payload):
    content = payload["messages"][1]["content"]
    return json.loads(content[0]["text"] if isinstance(content, list) else content)


def image_urls(payload):
    return [part["image_url"]["url"] for message in payload["messages"] if isinstance(message["content"], list)
            for part in message["content"] if part["type"] == "image_url"]


class CapturedSession:
    def __init__(self, replies, seen):
        self.replies, self.calls, self.close_count = replies, [], 0
        seen.append(self)
    def post(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        response = self.replies.pop(0)
        if isinstance(response, BaseException): raise response
        return response if isinstance(response, base.Response) else base.Response(encode(response))
    def close(self): self.close_count += 1


class RuntimeTests(unittest.TestCase):
    def cloud_current(self):
        config = providers.build_provider_config(provider=providers.PROVIDER_OPENAI,
            custom_model="authoring-fixture", openai_base_url="https://unit.test/v1")
        current = r.provider_values(config, 16384)
        current["api_key"] = "test-not-real"
        return current

    def cloud(self, values, replies, *, references=None, prepared=None, counters=None, progress=None, current=None):
        pending, seen = [encode(reply) for reply in replies], []
        prepared = prepared or r.prepare(values, references)
        counters, progress = (counters, progress) if counters is not None else journal()
        with patch.object(m.requests, "Session", side_effect=lambda: CapturedSession(pending, seen)):
            result = r.run(current or self.cloud_current(), values, prepared, counters, progress)
        self.assertEqual(pending, [], "No undeclared model requests or dropped planned responses")
        self.assertTrue(all(session.close_count == 1 for session in seen))
        return result, seen, counters, progress

    def test_two_comic_pages_have_one_plan_four_page_stages_and_shared_geometry(self):
        value, sessions, counters, progress = self.cloud(controls(), [plan(), source_reply(), translation_reply(), source_reply(), translation_reply()])
        self.assertEqual(len(sessions), 1)
        self.assertEqual((counters["logical_generation_calls"], counters["chat_post_attempts"], counters["correction_calls"]), (5, 5, 0))
        self.assertEqual(value["report"]["logical_generation_calls"], 5)
        self.assertTrue(value["report"]["bilingual_complete"])
        self.assertEqual(len(progress["units"]), 2)
        requests = [payload_request(call[1]["json"]) for call in sessions[0].calls]
        self.assertEqual([request["stage"] for request in requests], ["plan", "source", "translation", "source", "translation"])
        self.assertEqual(requests[3]["prior_validated_pages"][0]["unit_id"], "page-1")
        self.assertIn("User fact", requests[3]["human_continuity_context"])
        self.assertEqual(requests[3]["prior_validated_pages"][0]["sidecar"]["state"]["identity_anchors"], {"actor": "red hat"})
        for unit in value["units"]:
            self.assertEqual(unit["available_languages"], ["en", "zh"])
            self.assertTrue(c.same_json(c.without_captions(unit["sources"]["en"]), c.without_captions(unit["sources"]["zh"])))
            self.assertEqual(unit["sources"]["en"]["items"][0]["label"], "comic_panel")

    def test_each_stage_gets_only_one_correction_with_stage_specific_response_schema(self):
        value, sessions, counters, _progress = self.cloud(controls(page_count=1),
            ["not plan JSON", plan(1), {"source": {}}, source_reply(), {"summary_caption": "missing items"}, translation_reply()])
        self.assertEqual((counters["logical_generation_calls"], counters["correction_calls"]), (6, 3))
        self.assertEqual([record["calls"] for record in value["report"]["stage_records"]], [2, 2, 2])
        self.assertEqual([record["corrections"] for record in value["report"]["stage_records"]], [1, 1, 1])
        payloads = [call[1]["json"] for call in sessions[0].calls]
        self.assertIn("summary_caption,item_captions", payloads[-1]["messages"][-1]["content"])
        self.assertIn("{source,sidecar}", payloads[3]["messages"][-1]["content"])
        self.assertEqual(len(payloads[1]["messages"]), 4)

    def test_stream_clean_eof_accepts_complete_plan_source_and_translation_mapping(self):
        replies = [base.StreamResponse(encode(reply)) for reply in (plan(1), source_reply(), translation_reply())]
        current = self.cloud_current(); current["api_mode"] = m.SEEDANCE_API_MODE
        value, sessions, counts, _progress = self.cloud(controls(page_count=1), replies, current=current)
        self.assertEqual(counts["logical_generation_calls"], 3)
        self.assertTrue(value["report"]["bilingual_complete"])
        self.assertTrue(all(reply.closed for reply in replies))
        self.assertTrue(all(call[1]["json"]["stream"] for call in sessions[0].calls))
        self.assertEqual([len(call[1]["json"]["messages"]) for call in sessions[0].calls], [2, 2, 2])

    def test_bad_translation_keeps_completed_english_source_in_inspection_journal(self):
        pending = [encode(reply) for reply in [plan(1), source_reply(), {"item_captions": {}}, {"item_captions": {}}]]
        seen, (counters, progress) = [], journal()
        values = controls(page_count=1)
        with patch.object(m.requests, "Session", side_effect=lambda: CapturedSession(pending, seen)), self.assertRaises(native.MossContractError):
            r.run(self.cloud_current(), values, r.prepare(values), counters, progress)
        self.assertEqual((counters["logical_generation_calls"], counters["correction_calls"]), (4, 1))
        self.assertEqual([record["kind"] for record in progress["stage_records"]], ["plan", "source"])
        self.assertEqual(len(progress["units"]), 1, "A validated English page must survive failed Chinese translation for inspection")
        self.assertEqual(progress["units"][0]["available_languages"], ["en"])
        self.assertEqual(progress["units"][0]["sources"]["en"], source_reply()["source"])
        self.assertTrue(all(session.close_count == 1 for session in seen))

    def test_context_revises_only_selected_page_and_copies_all_others_exactly(self):
        original, _sessions, _counts, _progress = self.cloud(controls(), [plan(), source_reply(), translation_reply(), source_reply(), translation_reply()])
        context = {"schema_version": r.CONTEXT_SCHEMA, "mode": "full_layout", "bundle": original, "edit_unit_ids": ["page-2"]}
        values = controls(layout_context_json=c.encode(context), continuity_context="Latest user fact: keep the same hat.")
        result, sessions, counters, _progress = self.cloud(values, [plan(ids=["page-2"]), source_reply(), translation_reply()])
        self.assertEqual(result["units"][0], original["units"][0])
        self.assertEqual(result["edited_unit_ids"], ["page-2"])
        self.assertEqual(counters["logical_generation_calls"], 3)
        request = payload_request(sessions[0].calls[0][1]["json"])
        self.assertEqual(request["existing_context"]["edit_unit_ids"], ["page-2"])
        self.assertIn("Previous explicitly supplied human facts", request["human_continuity_context"])
        self.assertIn("Latest explicit human updates", request["human_continuity_context"])
        context["edit_unit_ids"] = []
        values = controls(layout_context_json=c.encode(context), brief="", page_count=0)
        prepared = r.prepare(values)
        counts, progress = journal()
        with patch.object(m.requests, "Session", side_effect=AssertionError("no transport")), patch.object(m, "LocalQwenProvider", side_effect=AssertionError("no model")):
            copied = r.run({}, values, prepared, counts, progress)
        self.assertEqual(copied["units"], original["units"])
        self.assertEqual(copied["report"]["logical_generation_calls"], 0)
        self.assertEqual(counts["logical_generation_calls"], 0)

    def test_fixed_layout_changes_are_rejected_but_opt_out_does_not_unlock_visible_copy(self):
        original, *_ = self.cloud(controls(page_count=1), [plan(1), source_reply(), translation_reply()])
        context = {"schema_version": r.CONTEXT_SCHEMA, "mode": "full_layout", "bundle": original, "edit_unit_ids": ["page-1"]}
        values = controls(page_count=1, max_corrections=0, layout_context_json=c.encode(context))
        changed = source_reply(); changed["source"]["items"][1]["bbox"][0] += 1
        pending, seen = [encode(reply) for reply in [plan(1), changed]], []
        with patch.object(m.requests, "Session", side_effect=lambda: CapturedSession(pending, seen)), self.assertRaises(native.MossContractError) as caught:
            counts, progress = journal(); r.run(self.cloud_current(), values, r.prepare(values), counts, progress)
        self.assertEqual(caught.exception.code, "fixed_layout_changed")
        self.assertTrue(all(session.close_count == 1 for session in seen))
        values["preserve_layout"] = False
        allowed, *_ = self.cloud(values, [plan(1), changed, translation_reply()])
        self.assertEqual(allowed["units"][0]["sources"]["en"]["items"][1]["bbox"][0], changed["source"]["items"][1]["bbox"][0])
        changed["source"]["items"][2]["text"] = "changed copy"
        pending = [encode(reply) for reply in [plan(1), changed]]
        with patch.object(m.requests, "Session", side_effect=lambda: CapturedSession(pending, [])), self.assertRaises(native.MossContractError):
            counts, progress = journal(); r.run(self.cloud_current(), values, r.prepare(values), counts, progress)

    def test_fisher_two_distinct_batch_images_are_independent_or_explicitly_fused(self):
        images = np.zeros((2, 16, 16, 3), dtype=np.float32)
        images[0, :, :, 0] = 1; images[1, :, :, 2] = 1
        values = controls(profile=a.FISHER, descriptive_language="中文", page_count=None)
        result, sessions, counts, _progress = self.cloud(values, [{"caption": "第一个红色主体。"}, {"caption": "第二个蓝色主体。"}],
                                                          references={"reference_image_0": images})
        self.assertEqual((len(sessions), counts["logical_generation_calls"]), (2, 2))
        self.assertEqual([unit["reference_indices"] for unit in result["units"]], [[1], [2]])
        self.assertEqual([row["batch_index"] for row in result["reference_map"]], [0, 1])
        payloads = [session.calls[0][1]["json"] for session in sessions]
        self.assertTrue(all(len(image_urls(payload)) == 1 for payload in payloads))
        self.assertNotEqual(image_urls(payloads[0]), image_urls(payloads[1]))
        self.assertNotIn("第一个红色主体", json.dumps(payloads[1], ensure_ascii=False))
        self.assertEqual(payload_request(payloads[1])["prior_validated_pages"], [])
        self.assertEqual([len(payload["messages"]) for payload in payloads], [2, 2])
        values["reference_mode"] = "fusion"
        result, sessions, counts, _progress = self.cloud(values, [{"caption": "红色与蓝色按明确贡献融合。"}], references={"reference_image_0": images})
        self.assertEqual((len(result["units"]), len(sessions), counts["logical_generation_calls"]), (1, 1, 1))
        self.assertEqual(len(image_urls(sessions[0].calls[0][1]["json"])), 2)
        self.assertEqual(result["units"][0]["reference_indices"], [1, 2])

    def test_comic_references_reach_plan_and_sources_but_not_translation(self):
        values = controls(page_count=1)
        result, sessions, _counts, _progress = self.cloud(values, [plan(1, refs=[1]), source_reply(), translation_reply()],
            references={"reference_image_3": np.ones((1, 8, 8, 3), dtype=np.float32)})
        self.assertEqual(result["reference_map"][0]["source_slot"], "reference_image_3")
        self.assertEqual([len(image_urls(call[1]["json"])) for call in sessions[0].calls], [1, 1, 0])

    def test_context_image_digest_order_and_page_count_are_preflight_errors(self):
        images = np.ones((1, 8, 8, 3), dtype=np.float32)
        values = controls(profile=a.FISHER)
        original, *_ = self.cloud(values, [{"caption": "一个原始主体。"}], references={"reference_image_0": images})
        context = {"schema_version": r.CONTEXT_SCHEMA, "mode": "full_layout", "bundle": original, "edit_unit_ids": ["image-1"]}
        values["layout_context_json"] = c.encode(context)
        with patch.object(m.requests, "Session", side_effect=AssertionError("no transport")):
            for refs in (None, {"reference_image_0": np.zeros_like(images)}, {"reference_image_1": images}):
                with self.subTest(refs=refs), self.assertRaises(native.MossContractError): r.prepare(values, refs)
            prepared = r.prepare(values, {"reference_image_0": images})
            self.assertEqual(prepared["reference_map"], original["reference_map"])
        for mutation in ({"width": 17}, {"preserve_layout": None}, {"page_count": 17}, {"max_output_chars": True}):
            with self.subTest(mutation=mutation), self.assertRaises((native.MossContractError, m.MossImageError)):
                r.prepare(controls(**mutation))
        with self.assertRaises(native.MossContractError): r.provider_values(None, 16384)

    def local_fixture(self, values, replies, *, references=None, budget_hook=None, interrupt=None):
        seen = {"enter": 0, "exit": [], "calls": [], "instances": []}
        pending = [encode(reply) for reply in replies]
        class Local:
            def __init__(self, settings, *, vision): seen["instances"].append((settings, vision))
            def __enter__(self): seen["enter"] += 1; return self
            def __exit__(self, *args): seen["exit"].append(args[0])
            def complete(self, messages, **kwargs):
                seen["calls"].append((copy.deepcopy(messages), kwargs)); result = pending.pop(0)
                if isinstance(result, BaseException): raise result
                return result
        config = providers.build_provider_config(provider=providers.PROVIDER_LOCAL, local_model="fixture.gguf")
        current = r.provider_values(config, "inactive cloud budget")
        counts, progress = journal()
        with patch.object(m, "LocalQwenProvider", Local), patch.object(m, "_provider_config", side_effect=AssertionError("no cloud credential lookup")):
            if budget_hook:
                with patch.object(m, "local_output_token_budget", side_effect=budget_hook):
                    result = r.run(current, values, r.prepare(values, references), counts, progress)
            elif interrupt:
                with patch.object(m, "interrupted", side_effect=lambda: interrupt(counts)):
                    result = r.run(current, values, r.prepare(values, references), counts, progress)
            else:
                result = r.run(current, values, r.prepare(values, references), counts, progress)
        return result, seen, counts, progress

    def test_local_collection_owns_one_provider_and_releases_it_after_all_stages(self):
        result, seen, counts, _progress = self.local_fixture(controls(), [plan(), source_reply(), translation_reply(), source_reply(), translation_reply()])
        self.assertEqual((seen["enter"], len(seen["instances"]), len(seen["exit"])), (1, 1, 1))
        self.assertIsNone(seen["exit"][0])
        self.assertEqual((counts["logical_generation_calls"], counts["chat_post_attempts"]), (5, 0))
        self.assertEqual(result["report"]["logical_generation_calls"], 5)
        self.assertTrue(all(call[1]["require_complete"] for call in seen["calls"]))
        self.assertTrue(all(call[1]["seed"] == 7 for call in seen["calls"]))

    def test_local_fisher_reuses_one_vision_provider_but_each_unit_sees_only_its_image(self):
        images = np.zeros((2, 8, 8, 3), dtype=np.float32)
        images[0, :, :, 0] = 1; images[1, :, :, 2] = 1
        result, seen, counts, _progress = self.local_fixture(controls(profile=a.FISHER),
            [{"caption": "红色主体。"}, {"caption": "蓝色主体。"}], references={"reference_image_0": images})
        self.assertEqual((seen["enter"], len(seen["instances"]), len(seen["exit"])), (1, 1, 1))
        self.assertTrue(seen["instances"][0][1])
        payloads = [{"messages": call[0]} for call in seen["calls"]]
        self.assertEqual([len(image_urls(payload)) for payload in payloads], [1, 1])
        self.assertNotEqual(image_urls(payloads[0]), image_urls(payloads[1]))
        self.assertNotIn("红色主体", json.dumps(payloads[1], ensure_ascii=False))
        self.assertEqual((len(result["units"]), counts["logical_generation_calls"]), (2, 2))

    def test_local_oversized_initial_stage_fails_before_provider_entry(self):
        config = providers.build_provider_config(provider=providers.PROVIDER_LOCAL, local_model="fixture.gguf")
        current = r.provider_values(config, "inactive")
        values = controls(profile=a.FISHER)
        counts, progress = journal()
        with patch.object(m, "local_visual_part_budget", side_effect=m.LocalQwenProviderError("No context budget")), \
             patch.object(m, "LocalQwenProvider", side_effect=AssertionError("Model entry is forbidden")) as model, \
             self.assertRaises(m.LocalQwenProviderError):
            r.run(current, values, r.prepare(values), counts, progress)
        model.assert_not_called()
        self.assertEqual(counts["logical_generation_calls"], 0)

    def test_local_correction_budget_is_recomputed_before_second_model_call_and_cancel_releases(self):
        settings = providers.build_provider_config(provider=providers.PROVIDER_LOCAL, local_model="fixture.gguf")
        current = r.provider_values(settings, "unused")
        seen = {"entered": 0, "exits": [], "calls": 0, "budgets": []}
        class Local:
            def __init__(self, *_args, **_kwargs): pass
            def __enter__(self): seen["entered"] += 1; return self
            def __exit__(self, *args): seen["exits"].append(args[0])
            def complete(self, messages, **kwargs): seen["calls"] += 1; return "invalid source"
        def budget(messages, _settings):
            seen["budgets"].append(len(messages))
            if len(messages) == 4: raise m.LocalQwenProviderError("Correction does not fit context")
            return 4096
        values = controls(profile=a.FISHER)
        counts, progress = journal()
        with patch.object(m, "LocalQwenProvider", Local), patch.object(m, "local_output_token_budget", side_effect=budget), self.assertRaises(m.LocalQwenProviderError):
            r.run(current, values, r.prepare(values), counts, progress)
        self.assertEqual(seen["calls"], 1)
        self.assertIn(4, seen["budgets"])
        self.assertEqual(seen["exits"], [m.LocalQwenProviderError])
        self.assertEqual(counts["correction_calls"], 1)
        seen.update(entered=0, exits=[], calls=0)
        def interrupt():
            if seen["calls"]: raise KeyboardInterrupt()
        counts, progress = journal()
        with patch.object(m, "LocalQwenProvider", Local), patch.object(m, "interrupted", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            r.run(current, values, r.prepare(values), counts, progress)
        self.assertEqual(seen["exits"], [KeyboardInterrupt])

    def test_invalid_plan_and_http_or_truncation_failures_never_resend_implicitly(self):
        for replies, expected in ((["not json"], 1), ([base.Response("ignored", status=401)], 1),
                                  ([base.Response('{"caption":"incomplete"}', finish="length")], 1)):
            values = controls(page_count=1, max_corrections=0)
            pending, sessions = list(replies), []
            counts, progress = journal()
            with patch.object(m.requests, "Session", side_effect=lambda: CapturedSession(pending, sessions)), self.assertRaises(Exception):
                r.run(self.cloud_current(), values, r.prepare(values), counts, progress)
            self.assertEqual(sum(len(session.calls) for session in sessions), expected)
            self.assertTrue(all(session.close_count == 1 for session in sessions))
            self.assertEqual(progress["units"], [])

    def test_strata_uses_one_run_identity_and_total_deadline_across_independent_units(self):
        from test_strata_provider import http_fixture, status
        strata = importlib.import_module(m.__package__ + ".strata_provider")
        media = {"reference_image_0": np.zeros((2, 8, 8, 3), dtype=np.float32)}
        values = controls(profile=a.FISHER)
        prepared = r.prepare(values, media)
        for failure in ("identity", "deadline", "cancel"):
            status_value = status()
            response = {"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": '{"caption":"一张独立图片。"}'}}]}
            counts, progress = journal()
            seen = []
            original = strata.StrataRun.complete
            def complete(run, messages, **kwargs):
                seen.append(id(run))
                if len(seen) == 2:
                    if failure == "identity": status_value["model"] = "changed-model"
                    if failure == "deadline": run.deadline = run.started - 1
                    if failure == "cancel": raise KeyboardInterrupt()
                return original(run, messages, **kwargs)
            @m.strata_execution
            def execute(provider_config, seed=7):
                return r.run(r.provider_values(provider_config, "inactive"), values, prepared, counts, progress)
            with http_fixture(status=status_value, response=response) as (url, calls):
                config = providers.build_provider_config(provider="Strata", strata_url=url)
                error_type = KeyboardInterrupt if failure == "cancel" else m.StrataProviderError
                with patch.object(strata.StrataRun, "complete", complete), self.assertRaises(error_type): execute(config)
            self.assertEqual(len(set(seen)), 1)
            self.assertEqual(sum(method == "POST" for method, *_ in calls), 1)
            self.assertEqual(len(progress["units"]), 1)
            self.assertIsNone(strata.current_strata_run())
            self.assertFalse(any("load" in path or "unload" in path for _method, path, *_ in calls))


if __name__ == "__main__":
    unittest.main()
