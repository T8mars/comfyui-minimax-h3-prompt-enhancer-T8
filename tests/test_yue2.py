import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
SPEC = importlib.util.spec_from_file_location("t8_yue2_tests", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
yue = sys.modules[SPEC.name + ".yue2"]
transport = sys.modules[SPEC.name + ".provider_transport"]
config = sys.modules[SPEC.name + ".provider_config"]

LYRICS = "[Verse]\n车窗留着雨的形状\n旧地图折进了衣裳\n\n[Chorus]\n把明天唱给远方\n让灯火接住目光\n\n[Verse]\n绕过没说完的惆怅\n路牌已换新的方向\n\n[Chorus]\n把明天唱给远方\n让灯火接住目光\n"
STYLE = "Mandarin acoustic pop, warm female voice, piano and guitar, 88 BPM, restrained verses build to an uplifting chorus, a gentle piano ending."
ABC = 'X:1\nT:\nM:4/4\nL:1/32\nQ:1/4=88\nV: Vocal clef=treble name="Vocal Melody" snm="Vocal"\nV: Ins clef=treble name="Ins Melody" snm="Inst."\nK:C\n% verse\nV: Vocal\n"C"C8D8E8G8|\nV: Ins\nZ|\n'


class Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, data, finish="stop"):
        self.data, self.finish = data, finish
    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self.data, ensure_ascii=False)}, "finish_reason": self.finish}]}


class Session:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.replies:
            value = self.replies.pop(0)
            return value if isinstance(value, Response) else Response(value)
        system = kwargs["json"]["messages"][0]["content"]
        if "independent textual critic" in system:
            return Response({"scores": {k: 17 for k in yue.RUBRIC}, "issues": [], "revision_needed": False})
        if "replacement body ONLY" in system:
            return Response({"lyrics": "把黎明留在手上\n让远方回应歌唱"})
        return Response({"style": STYLE} if "style input" in system else {"lyrics": LYRICS})


class YuE2Tests(unittest.TestCase):
    def run_node(self, **values):
        return yue.enhance_yue2_prompt(music_idea="中文公路歌，温暖女声，钢琴吉他", api_key="test-key", session=values.pop("session", Session()), **values)

    def test_snapshot_and_registration(self):
        self.assertEqual(yue.official_snapshot()["commit"], yue.SOURCE_COMMIT)
        extension = asyncio.run(package.comfy_entrypoint())
        ids = [n.define_schema().node_id for n in asyncio.run(extension.get_node_list())]
        self.assertEqual(ids[-1], yue.NODE_ID)
        self.assertEqual(len(ids), len(set(ids)))
        schema = yue.YuE2MusicPromptEnhancer.define_schema()
        self.assertEqual(len(schema.outputs), 5)

    def test_generate_official_payload(self):
        session = Session()
        style, lyrics, abc, payload, report = self.run_node(session=session)
        data = json.loads(payload)
        yue.validate_request(data)
        self.assertEqual(data, {"style": style, "lyrics": lyrics, "cot": "full", "seed": 831001, "id": "song"})
        self.assertEqual(abc, "")
        self.assertEqual(len(session.calls), 2)
        self.assertTrue(json.loads(report)["checks"]["lyrics_language"])
        for _, call in session.calls:
            self.assertEqual(call["json"]["max_tokens"], yue.DEFAULT_MAX_TOKENS)
            self.assertEqual(call["headers"]["Authorization"], "Bearer test-key")

    def test_preserve_byte_exact_and_one_call(self):
        session = Session()
        original = LYRICS.replace("\n", "\r\n")
        result = self.run_node(lyrics=original, session=session)
        self.assertEqual(result[1], original)
        self.assertEqual(len(session.calls), 1)

    def test_edit_only_second_chorus(self):
        result = self.run_node(lyrics_mode=yue.EDIT, lyrics=LYRICS, edit_section="Chorus", edit_occurrence=2, edit_request="更有希望")
        start, end = yue.edit_span(LYRICS, "Chorus", 2)
        self.assertEqual(result[1][:start], LYRICS[:start])
        self.assertIn("把黎明留在手上", result[1][start:])
        self.assertTrue(json.loads(result[4])["checks"]["outside_edit_preserved"])

    def test_language_repair_then_validate(self):
        session = Session([{"lyrics": "[Verse]\nWe drive into the morning"}, {"lyrics": LYRICS}, {"style": STYLE}])
        result = self.run_node(session=session)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(result[1], LYRICS.strip())

    def test_wrong_language_twice_fails(self):
        session = Session([{"lyrics": "English only"}, {"lyrics": "Still English"}])
        with self.assertRaisesRegex(yue.YuE2PromptError, "语言"):
            self.run_node(session=session)
        self.assertEqual(len(session.calls), 2)

    def test_english_lyrics_with_chinese_style(self):
        session = Session([{"lyrics": "[Verse]\nRain taps the glass\nWe leave the past\n[Chorus]\nCarry the light home"}, {"style": "英语民谣，温暖女声，钢琴与吉他，主歌克制，副歌明亮。"}])
        self.run_node(lyrics_language="English", style_language="中文", session=session)

    def test_review_score_is_not_audio_score(self):
        result = self.run_node(quality_mode=yue.REVIEW)
        report = json.loads(result[4])
        self.assertEqual(report["review"]["total"], 85)
        self.assertFalse(report["audio_generated"])
        self.assertEqual(report["requests"], 3)

    def test_review_cannot_edit_preserved_lyrics(self):
        replies = [{"style": STYLE}, {"scores": {k: 14 for k in yue.RUBRIC}, "issues": ["Needs brighter ending"], "revision_needed": True}, {"style": STYLE + " A bright final refrain."}]
        result = self.run_node(lyrics=LYRICS, quality_mode=yue.REVIEW, session=Session(replies))
        self.assertEqual(result[1], LYRICS)
        self.assertEqual(json.loads(result[4])["review"]["score_applies_to"], "pre_repair_draft")

    def test_abc_keep_and_strip_preserve_both_voices(self):
        text, report = yue.prepare_abc(ABC, "full", yue.ABC_KEEP, 88, "4/4", "C")
        self.assertEqual(text, ABC)
        stripped, report = yue.prepare_abc(ABC, "melody", yue.ABC_STRIP, 0, "AUTO", "")
        self.assertNotIn('"C"', stripped)
        self.assertIn('name="Vocal Melody"', stripped)
        self.assertTrue(report["invariants"]["match"])
        self.assertEqual(report["invariants"]["compared_voices"], ["Vocal", "Ins"])
        self.run_node(abc=ABC, cot="melody", abc_action=yue.ABC_STRIP)

    def test_conflicts_fail_before_paid_call(self):
        for values in [{"abc": ABC, "cot": "off"}, {"abc": ABC, "cot": "melody"},
                       {"lyrics_mode": yue.PRESERVE}, {"lyrics_mode": yue.EDIT, "lyrics": LYRICS},
                       {"lyrics_mode": yue.EDIT, "lyrics": LYRICS, "edit_request": "改词", "edit_occurrence": 8},
                       {"song_id": "../outside"}, {"cot": "wrong"}]:
            with self.subTest(values=values):
                session = Session()
                with self.assertRaises(yue.YuE2PromptError):
                    self.run_node(session=session, **values)
                self.assertEqual(session.calls, [])

    def test_bad_abc_outside_helper_scope(self):
        with self.assertRaisesRegex(yue.YuE2PromptError, "整个 ABC"):
            yue.prepare_abc(ABC.replace('"C"C8', '(3C8'), "full", yue.ABC_KEEP, 0, "AUTO", "")

    def test_token_length_never_success_even_valid_json(self):
        session = Session([Response({"lyrics": LYRICS}, "length")])
        with self.assertRaisesRegex(yue.YuE2PromptError, "截断"):
            self.run_node(session=session)

    def test_instrumental_no_lyrics_generation(self):
        session = Session()
        result = self.run_node(lyrics_mode=yue.INSTRUMENTAL, session=session)
        self.assertEqual(result[1], "")
        self.assertEqual(len(session.calls), 1)
        self.assertTrue(json.loads(session.calls[0][1]["json"]["messages"][1]["content"])["brief"]["instrumental"])

    def test_provider_modes_and_custom_params(self):
        for mode, model, url in [(yue.SEEDANCE_API_MODE, "", ""), (yue.AI_WORKSHOP_API_MODE, "", ""), (yue.OPENAI_API_MODE, "vendor/text", "https://example.test/v1")]:
            with self.subTest(mode=mode):
                session = Session()
                self.run_node(lyrics=LYRICS, api_mode=mode, custom_model=model, openai_base_url=url, session=session,
                              provider_request_options={"temperature_policy": "omit", "extra_parameters": {"max_completion_tokens": 19000}})
                payload = session.calls[0][1]["json"]
                self.assertNotIn("temperature", payload)
                self.assertNotIn("max_tokens", payload)
                self.assertEqual(payload["max_completion_tokens"], 19000)
                if model:
                    self.assertEqual(payload["model"], model)
                    self.assertEqual(session.calls[0][0], url + "/chat/completions")

    def test_local_all_text_settings_are_consumed(self):
        class Local:
            instances = []
            def __init__(self, settings, vision):
                self.settings, self.vision, self.closed, self.calls = settings, vision, False, []
                self.instances.append(self)
            def close(self):
                self.closed = True
            def complete(self, messages, **kwargs):
                self.calls.append(kwargs)
                return json.dumps({"style": STYLE} if "style input" in messages[0]["content"] else {"lyrics": LYRICS})
        with patch.object(yue, "LocalQwenProvider", Local):
            result = self.run_node(api_mode=yue.LOCAL_QWEN_API_MODE, local_model="custom.gguf", local_context_size=16384,
                                  local_max_tokens=8192, local_reasoning_effort="xhigh", seed=21)
        local = Local.instances[0]
        self.assertFalse(local.vision)
        self.assertEqual(local.settings.model_filename, "custom.gguf")
        self.assertEqual(local.settings.context_size, 16384)
        self.assertEqual(local.settings.max_tokens, 8192)
        self.assertEqual(local.settings.reasoning_effort, "xhigh")
        self.assertEqual(local.calls[0]["seed"], 21)
        self.assertTrue(local.closed)
        self.assertEqual(local.calls[0]["response_format"]["schema"]["required"], ["lyrics"])
        self.assertEqual(local.calls[1]["response_format"]["schema"]["required"], ["style"])
        self.assertTrue(local.calls[0]["require_complete"])
        self.assertEqual(json.loads(result[4])["provider"], "Local llama.cpp GGUF")

    def test_shared_provider_overrides_node_widgets(self):
        shared = config.build_provider_config(provider=config.PROVIDER_OPENAI, custom_model="shared/model", openai_base_url="https://shared.test/v1")
        with patch.object(yue, "enhance_yue2_prompt", return_value=("s", "l", "", "{}", "{}")) as run:
            yue.YuE2MusicPromptEnhancer.execute(music_idea="音乐", provider_config=shared, custom_model="old", api_key="connected-key")
        self.assertEqual(run.call_args.kwargs["custom_model"], "shared/model")
        self.assertEqual(run.call_args.kwargs["api_key"], "connected-key")

    def test_manual_recovery_zero_paid_requests(self):
        slot = "test-yue-recovery-123"
        outputs = (STYLE, LYRICS, "", "{}", "{}")
        yue.begin_recovery_record(yue.NODE_ID, slot, "Seedance")
        yue.complete_recovery_record(yue.NODE_ID, slot, outputs)
        with patch.object(yue, "enhance_yue2_prompt", side_effect=AssertionError("paid call")):
            result = yue.YuE2MusicPromptEnhancer.execute(recovery_slot=slot, recovery_action=yue.RECOVERY_ACTION_RESTORE)
        self.assertEqual(tuple(result), outputs)

    def test_workflows_match_runtime_widget_order_and_outputs(self):
        schema = yue.YuE2MusicPromptEnhancer.define_schema()
        info = schema.get_v1_info(yue.YuE2MusicPromptEnhancer)
        names = info.input_order["required"]
        self.assertEqual(names, list(yue.DEFAULTS))
        paths = list((ROOT / "example_workflows").glob("yue2_*.json"))
        self.assertEqual(len(paths), 4)
        for path in paths:
            workflow = json.loads(path.read_text(encoding="utf-8"))
            node = next(n for n in workflow["nodes"] if n["type"] == yue.NODE_ID)
            self.assertEqual(dict(zip(names, node["widgets_values"])), node["properties"]["t8_yue2_widgets_v1"])
            self.assertEqual(len(node["widgets_values"]), len(names))
            self.assertEqual(len(node["outputs"]), 5)
            self.assertTrue(all(output["links"] for output in node["outputs"]))

    def test_local_format_and_truncation_are_opt_in(self):
        local_module = sys.modules[yue.LocalQwenProvider.__module__]
        provider = yue.LocalQwenProvider(yue.settings_from_values(), vision=False)
        provider.server = object()
        with patch.object(local_module.LOCAL_QWEN_MANAGER, "complete", return_value=("partial", {"finish_reason": "length"})) as complete:
            self.assertEqual(provider.complete([], temperature=0.4, seed=7), "partial")
            self.assertNotIn("response_format", complete.call_args.kwargs)
            with self.assertRaisesRegex(local_module.LocalQwenProviderError, "truncated"):
                provider.complete([], temperature=0.4, seed=7, require_complete=True, response_format={"type": "json_object"})
            self.assertEqual(complete.call_args.kwargs["response_format"], {"type": "json_object"})

    def test_stream_length_rejected_and_legacy_behavior_preserved(self):
        class StreamResponse:
            status_code = 200
            headers = {"Content-Type": "text/event-stream"}
            def iter_lines(self, **kwargs):
                yield ("data: " + json.dumps({"choices": [{"delta": {"content": json.dumps({"lyrics": LYRICS})}, "finish_reason": "length"}]})).encode()
                yield b"data: [DONE]"
            def close(self):
                pass
        session = Session()
        session.post = lambda *args, **kwargs: StreamResponse()
        with self.assertRaisesRegex(yue.YuE2PromptError, "截断"):
            self.run_node(session=session)

    def test_duration_advisory_not_native_field(self):
        result = self.run_node(target_duration_seconds=360)
        self.assertNotIn("duration", json.loads(result[3]))
        self.assertTrue(any("时长" in warning for warning in json.loads(result[4])["warnings"]))

    def test_preserve_and_score_conflicts_warn_without_overwriting(self):
        result = self.run_node(lyrics="[Verse]\nHello tomorrow", lyrics_mode=yue.PRESERVE)
        self.assertEqual(result[1], "[Verse]\nHello tomorrow")
        self.assertFalse(json.loads(result[4])["checks"]["lyrics_language"])
        session = Session()
        result = self.run_node(abc=ABC, bpm=99, meter="3/4", key_scale="G", session=session)
        self.assertEqual(result[2], ABC)
        brief = json.loads(session.calls[-1][1]["json"]["messages"][1]["content"])["brief"]
        self.assertEqual((brief["bpm"], brief["meter"], brief["key_scale"]), (88, "4/4", "C"))
        self.assertEqual(len(json.loads(result[4])["abc"]["control_conflicts"]), 3)

    def test_invalid_review_never_fabricates_score(self):
        for scores, needed, issues in [(None, False, []), ({k: 17 for k in yue.RUBRIC}, "false", []), ({k: 17 for k in yue.RUBRIC}, False, [{}])]:
            with self.subTest(scores=scores, needed=needed):
                session = Session([{"lyrics": LYRICS}, {"style": STYLE}, {"scores": scores, "revision_needed": needed, "issues": issues}])
                with self.assertRaisesRegex(yue.YuE2PromptError, "评分"):
                    self.run_node(quality_mode=yue.REVIEW, session=session)

    def test_json_schema_reaches_all_local_backends(self):
        standalone = importlib.import_module(SPEC.name + ".local_qwen_standalone_runtime")
        registry = importlib.import_module(SPEC.name + ".local_qwen_python_runtime")
        schema = {"type": "json_object", "schema": yue.REVIEW_SCHEMA}
        options = dict(messages=[], seed=7, max_tokens=8192, temperature=0.4,
                       think_mode=False, reasoning_effort="medium", response_format=schema)
        for backend in (standalone.LlamaServer, standalone.LlamaPythonRuntime, registry.LlamaPythonRuntime):
            with self.subTest(backend=backend):
                captured = {}
                def complete(**kwargs):
                    captured.update(kwargs)
                    return {"choices": [{"message": {"content": '{"style":"complete"}'}, "finish_reason": "stop"}],
                            "usage": {"completion_tokens": 5}}
                runtime = object.__new__(backend)
                if backend is standalone.LlamaServer:
                    runtime.process = type("Process", (), {"poll": lambda self: None})()
                    runtime._chat_sync = lambda payload: complete(**payload)
                else:
                    runtime.llm = type("Llama", (), {"create_chat_completion": staticmethod(complete)})()
                    runtime.think_mode = False
                    runtime.mmproj = None
                text, usage = runtime.chat(**options)
                self.assertEqual(captured["response_format"], schema)
                self.assertEqual(captured["max_tokens"], 8192)
                self.assertEqual(json.loads(text), {"style": "complete"})
                self.assertEqual(usage["finish_reason"], "stop")


if __name__ == "__main__":
    unittest.main()
