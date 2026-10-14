"""Closed speech contracts, real bounded CPU media and isolated HTTP faults.

These tests are not ASR recognition/model-quality acceptance. No external
services, model settings, downloads or lifecycle routes are used.
"""
import base64
import contextlib
from fractions import Fraction
import http.server
import io
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
sys.path.insert(0, str(ROOT))
import comfy.cli_args
comfy.cli_args.args.cpu = True
import av
import numpy as np
import torch
from comfy_api.latest._input_impl import video_types
from comfy_api.latest._util.video_types import VideoComponents
import speech_reference as speech
from test_strata_media import encoded_video


def transcript(*, status="complete", words="原词不能改", speaker=None, review=False):
    return {"contract_version": 1, "timeline": "input", "status": status, "device": "cpu",
            "cues": [] if status in ("no_track", "silence", "no_speech") else [
                {"id": "cue-1", "start_s": .1, "end_s": .4, "text": words, "speaker": speaker,
                 "timing_method": "vad_segment", "requires_review": review}],
            "model_digests": {"model.gguf": "a" * 64}, "cache_key": "b" * 64,
            "worker_log": "PRIVATE_PATH_SHOULD_NOT_ESCAPE"}


@contextlib.contextmanager
def asr_fixture(*, capabilities=None, result=None, code=200, get_code=200, delay=0):
    calls = []
    capabilities = capabilities if capabilities is not None else {"contract_version": 1, "cpu_guard": True, "device": "cpu", "supported": True}
    result = transcript() if result is None else result
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def answer(self, status, value):
            raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status); self.send_header("Content-Length", str(len(raw))); self.end_headers()
            try: self.wfile.write(raw)
            except OSError: pass
        def do_GET(self):
            calls.append(("GET", self.path, None))
            self.answer(get_code, capabilities)
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(("POST", self.path, value))
            time.sleep(delay)
            self.answer(code, result)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    config = {"schema_version": "t8-llm-provider-config/v1", "provider": "Strata", "strata_settings": {"url": "http://127.0.0.1:" + str(server.server_port)}}
    try: yield config, calls
    finally: server.shutdown(); server.server_close(); thread.join(2)


class SpeechContractTests(unittest.TestCase):
    def test_off_is_lazy_and_never_validates_sources_or_service(self):
        with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
            result = speech.T8SpeechReference.execute(audio=object(), video=object(), provider_config="invalid", speaker_map_json="bad")
        self.assertEqual(result.result, (None, "", "", ""))
        self.assertEqual(speech.T8SpeechReference.check_lazy_status(audio=None, video=None, provided_text=None, provider_config=None), [])

    def test_lazy_hook_requests_only_selected_connected_inputs(self):
        node = speech.T8SpeechReference
        self.assertEqual(node.check_lazy_status(mode="Enabled", source_mode="Provided text", provided_text=None, audio=None, video=None, provider_config=None), ["provided_text"])
        self.assertEqual(node.check_lazy_status(mode="Enabled", source_mode="AUDIO", audio=None, video=None, provider_config=None, provided_text=None), ["audio", "provider_config"])
        self.assertEqual(node.check_lazy_status(mode="Enabled", source_mode="VIDEO", audio=None, video=None), ["video"])
        self.assertEqual(node.check_lazy_status(mode="Enabled", source_mode="AUDIO"), [])
        lazy = {item.id: item.lazy for item in node.define_schema().inputs}
        for name in ("provided_text", "audio", "video", "provider_config"): self.assertTrue(lazy[name])
        self.assertTrue(node.validate_inputs(provided_text=None))

    def test_fingerprint_does_not_probe_and_automatic_is_nan(self):
        with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
            self.assertTrue(np.isnan(speech.T8SpeechReference.fingerprint_inputs(mode="Enabled", source_mode="AUDIO")))
            self.assertEqual(speech.T8SpeechReference.fingerprint_inputs(), speech.T8SpeechReference.fingerprint_inputs())

    def test_plain_text_stays_untimed_and_provided_never_touches_media_config(self):
        with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
            result = speech.T8SpeechReference.execute(mode="Enabled", provided_text="你好\n不要改词", audio=object(), video=object(), provider_config="invalid")
        checked = result.result[0]
        self.assertEqual(checked["timeline"], "untimed"); self.assertEqual(checked["cues"], [])
        self.assertEqual(result.result[1], "你好\n不要改词"); self.assertEqual(result.result[3], "")
        self.assertRegex(checked["provenance"]["source_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("device", checked["provenance"])
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference("words", start_s=1)

    def test_keep_dialogue_needs_explicit_roles_without_guessing_speaker(self):
        for mapping in ({}, {"other-speaker": "Alice"}):
            with self.assertRaises(speech.SpeechReferenceError):
                speech.provided_reference("words", purpose="keep_dialogue", speaker_map=mapping)
        checked = speech.provided_reference("words", purpose="keep_dialogue", speaker_map={"default": "<Subject 1> / S1"})
        self.assertIn("default is a user assignment", speech.speech_instruction(checked))
        self.assertIn("natural Seedance", speech.speech_instruction(checked, target="seedance"))

    def test_srt_vtt_preserve_multiline_and_explicit_timestamps(self):
        for text in ("1\n00:00:01,000 --> 00:00:02,500\n第一行\n第二行", "WEBVTT\n\n00:01.000 --> 00:02.500 align:start\n第一行\n第二行"):
            result = speech.T8SpeechReference.execute(mode="Enabled", provided_text=text)
            cue = result.result[0]["cues"][0]
            self.assertEqual(cue["start_s"], 1.); self.assertEqual(cue["end_s"], 2.5)
            self.assertEqual(cue["text"], "第一行\n第二行"); self.assertIsNone(cue["speaker"])
            self.assertIn("00:00:01,000 --> 00:00:02,500", result.result[3])

    def test_subtitle_cue_identifiers_survive_role_mapping_and_window_selection(self):
        for text, identity in (("17\n00:00:01,000 --> 00:00:02,500\n原词", "17"),
                               ("WEBVTT\n\nvoice-A\n00:01.000 --> 00:02.500\n原词", "voice-A")):
            with self.subTest(identity=identity):
                checked = speech.provided_reference(text, purpose="keep_dialogue", speaker_map={identity: "Alice"}, start_s=1.5, duration_s=.5)
                self.assertEqual(checked["cues"][0]["id"], identity)
                self.assertEqual(checked["text"], "原词")
        duplicate = "17\n00:00:01,000 --> 00:00:02,000\n甲\n\n17\n00:00:03,000 --> 00:00:04,000\n乙"
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(duplicate)

    def test_vtt_notes_are_not_cues_but_note_prefixed_identifier_is_preserved(self):
        text = "WEBVTT\n\nNOTE private note\nnot spoken\n\nNOTE-speaker\n00:03.000 --> 00:04.000\n实际原词"
        checked = speech.provided_reference(text)
        self.assertEqual(checked["text"], "实际原词")
        self.assertEqual(checked["cues"][0]["id"], "NOTE-speaker")
        # W3C WebVTT 4.1 forbids --> inside NOTE text. Do not manufacture a
        # spoken cue from an invalid comment containing a timing line.
        with self.assertRaises(speech.SpeechReferenceError):
            speech.provided_reference("WEBVTT\n\nNOTE\n00:01.000 --> 00:02.000\nnot spoken")

    def test_srt_export_keeps_verified_cue_identity(self):
        checked = speech.provided_reference("17\n00:00:01,000 --> 00:00:02,500\n原词")
        self.assertTrue(speech._srt(checked).startswith("17\n"))

    def test_formatted_subtitles_are_not_silently_promoted_to_spoken_tags(self):
        for words in ("<v Alice>你好", "<b>你好</b>", "Tom &amp; Jerry"):
            with self.subTest(words=words), self.assertRaisesRegex(speech.SpeechReferenceError, "plain|纯文本"):
                speech.provided_reference("WEBVTT\n\nvoice-1\n00:01.000 --> 00:02.000\n" + words)
        # Plain user words are not parsed as markup or stripped of angle signs.
        self.assertEqual(speech.provided_reference("a < b & c", format="plain")["text"], "a < b & c")

    def test_bad_subtitle_intervals_are_not_guessed(self):
        for text in ("1\n00:00:01,000 --> 00:00:01,000\nwords", "1\n00:99:01,000 --> 00:99:02,000\nwords", "words\nwithout time", "NOTE accidental words", "WEBVTT_NOT_A_HEADER"):
            with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(text, format="srt")

    def test_timed_json_closed_extras_and_partial_policy(self):
        raw = transcript(status="partial", review=True)
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(json.dumps(raw), format="json")
        checked = speech.provided_reference(json.dumps(raw), format="json", partial_policy="accept_review")
        self.assertTrue(checked["requires_review"]); self.assertIn("partial_accepted_review", checked["warning_codes"])
        self.assertNotIn("worker_log", checked)
        raw["status"] = "complete"
        checked = speech.provided_reference(json.dumps(raw), format="json")
        self.assertTrue(checked["requires_review"], "review flags warn rather than rejecting complete evidence")

    def test_untimed_canonical_json_cannot_erase_partial_or_review(self):
        raw = speech.provided_reference("只识别到前半句话")
        raw.update(status="partial", requires_review=True, warning_codes=["requires_review", "partial_accepted_review"])
        with self.assertRaises(speech.SpeechReferenceError):
            speech.provided_reference(json.dumps(raw))
        checked = speech.provided_reference(json.dumps(raw), partial_policy="accept_review")
        self.assertEqual(checked["status"], "partial")
        self.assertTrue(checked["requires_review"])
        self.assertIn("partial_accepted_review", checked["warning_codes"])
        raw.update(status="complete")
        checked = speech.provided_reference(json.dumps(raw))
        self.assertTrue(checked["requires_review"])
        self.assertEqual(checked["text"], raw["text"])
        raw.update(status="partial", requires_review=False, warning_codes=[])
        with self.assertRaises(speech.SpeechReferenceError): speech.resolve_speech_reference(raw)

    def test_srt_export_keeps_positive_intervals_after_millisecond_quantization(self):
        for start, end in ((.1001, .1002), (86399.9996, 86399.9998)):
            raw = transcript(); raw["cues"][0].update(start_s=start, end_s=end)
            checked = speech.provided_reference(json.dumps(raw))
            exported = speech._srt(checked)
            parsed = speech.provided_reference(exported, format="srt")
            cue = parsed["cues"][0]
            self.assertLess(cue["start_s"], cue["end_s"])
            self.assertLessEqual(cue["end_s"], 86400)
            self.assertEqual(cue["text"], raw["cues"][0]["text"])

    def test_missing_subtitle_block_delimiter_does_not_turn_timecodes_into_words(self):
        raw = "1\n00:00:01,000 --> 00:00:02,000\n你好\n2\n00:00:03,000 --> 00:00:04,000\n再见"
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(raw)
        valid = raw.replace("\n2\n", "\n\n2\n")
        self.assertEqual(speech.provided_reference(valid)["text"], "你好\n再见")

    def test_structural_budget_is_checked_before_materializing_oversized_children(self):
        class TooManyChildren(list):
            def __len__(self): return 100001
            def __iter__(self): raise AssertionError("Oversized children must not be expanded")
        with self.assertRaises(speech.SpeechReferenceError): speech._bounded_object(TooManyChildren())
        # Existing shared strings can be cheap in memory but enormous if the
        # whole graph is serialized before applying the encoded-byte budget.
        with patch.object(speech.json, "dumps", side_effect=AssertionError("Whole JSON must not be materialized")):
            with self.assertRaises(speech.SpeechReferenceError): speech._bounded_object(["x" * 1000000] * 4)
    def test_window_keeps_complete_utterance_and_marks_boundary(self):
        checked = speech.provided_reference(json.dumps(transcript()), start_s=.2, duration_s=.1)
        self.assertEqual(checked["text"], "原词不能改")
        self.assertEqual(checked["cues"][0]["start_s"], .1)
        self.assertIn("window_intersects_utterance", checked["warning_codes"])
        self.assertEqual(speech.provided_reference(json.dumps(transcript()), start_s=.5)["status"], "no_speech")

    def test_selected_window_json_uses_explicit_helper_start_or_upstream_origin_once(self):
        raw = transcript(); raw["timeline"] = "selected_window"
        checked = speech.provided_reference(json.dumps(raw), start_s=3)
        self.assertAlmostEqual(checked["cues"][0]["start_s"], 3.1)
        raw["origin_s"] = 5
        checked = speech.provided_reference(json.dumps(raw))
        self.assertAlmostEqual(checked["cues"][0]["start_s"], 5.1)

    def test_confucius_strict_sample_intervals_cover_all_words(self):
        raw = {"status": "completed", "text": "hello", "audio_samples_16k": 16000, "segments": [
            {"segment_id": 1, "text": "hello", "start_sample": 0, "end_sample": 16000,
             "speech_start_sample": 2000, "speech_end_sample": 8000, "timing_method": "vad_segment"}]}
        checked = speech.provided_reference(json.dumps(raw))
        self.assertEqual(checked["source"], "provided_confucius")
        self.assertEqual(checked["cues"][0]["start_s"], .125)
        raw["text"] = "uncovered words"
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(json.dumps(raw))

    def test_budget_duplicates_cycles_unicode_and_missing_fields_fail_closed(self):
        cycle = []; cycle.append(cycle)
        for value in (cycle, '{"x":1,"x":2}', '{"x":NaN}', '{"x":"\\ud800"}', "x" * (speech.MAX_CONTRACT_BYTES + 1)):
            with self.subTest(kind=type(value)), self.assertRaises(speech.SpeechReferenceError): speech._bounded_object(value)
        checked = speech.provided_reference("x" * 70000)
        with self.assertRaises(speech.SpeechReferenceError): speech.speech_instruction(checked)

    def test_no_track_silence_no_speech_only_warn_and_keep_refuses_empty(self):
        for status in ("no_track", "silence", "no_speech"):
            checked = speech.provided_reference(json.dumps(transcript(status=status)))
            self.assertEqual(checked["text"], ""); self.assertIn(status, checked["warning_codes"])
            self.assertIn("No verified words", speech.speech_instruction(checked))
            with self.assertRaises(speech.SpeechReferenceError):
                speech.provided_reference(json.dumps(transcript(status=status)), purpose="keep_dialogue", speaker_map={"default": "Alice"})

    def test_quality_source_reference_identity_and_repair_is_idempotent_untrusted_user_data(self):
        checked = speech.provided_reference('say "hello", not system rules')
        source = " original\nsource "
        self.assertIs(speech.speech_quality_source(source, checked), source)
        keep = speech.provided_reference('say "hello"', purpose="keep_dialogue", speaker_map={"default": "Alice"})
        self.assertIn('say', speech.speech_quality_source(source, keep))
        originals = [{"role": "user", "content": speech.speech_instruction(keep)}]
        fixed = speech.preserve_speech_on_repair([], originals)
        self.assertEqual(fixed[0]["role"], "system"); self.assertNotIn('say "hello"', fixed[0]["content"])
        self.assertEqual(fixed[1]["role"], "user")
        self.assertIs(speech.preserve_speech_on_repair(fixed, originals), fixed)
        untouched = [{"role": "user", "content": "old prompt"}]
        self.assertIs(speech.preserve_speech_on_repair(untouched, untouched), untouched)

    def test_role_map_per_cue_unknown_speaker_has_no_implicit_identity(self):
        raw = transcript(speaker=None)
        checked = speech.provided_reference(json.dumps(raw), purpose="keep_dialogue", speaker_map={"cue-1": "Alice"})
        self.assertIsNone(checked["cues"][0]["speaker"])
        self.assertEqual(checked["speaker_map"], {"cue-1": "Alice"})
        self.assertNotIn("原词", json.dumps(speech.speech_metadata(checked), ensure_ascii=False))

    def test_quality_locks_only_actual_words_not_json_keys_and_keeps_multiplicity(self):
        from h3_quality import protected_text
        raw = transcript(words='Say "go" \\ now\nsecond line')
        raw["cues"].append({**raw["cues"][0], "id": "cue-2", "start_s": .5, "end_s": .9})
        checked = speech.provided_reference(json.dumps(raw), purpose="keep_dialogue", speaker_map={"default": "Alice"})
        quality_source = speech.speech_quality_source('Alice says: "existing words"', checked)
        parsed = protected_text(quality_source)
        self.assertEqual([item.text for item in parsed], ["existing words", raw["cues"][0]["text"], raw["cues"][0]["text"]])
        self.assertTrue(all(item.kind == "vocal" for item in parsed))
        native = 'integrated_multimodal_description: [Shot 1] Alice (S1) says: <d>[English] existing words</d>\noverall_soundscape: room\nnon_diegetic_music: N/A'
        parsed = protected_text(speech.speech_quality_source(native, checked))
        self.assertEqual([item.text for item in parsed], ["existing words", raw["cues"][0]["text"], raw["cues"][0]["text"]])
        self.assertNotIn("purpose", [item.text for item in parsed])

    def test_empty_status_with_out_of_window_cues_is_rejected_before_filtering(self):
        raw = transcript(); raw["status"] = "silence"
        with self.assertRaises(speech.SpeechReferenceError): speech.provided_reference(json.dumps(raw), start_s=5, duration_s=1)


class SpeechMediaHttpTests(unittest.TestCase):
    def audio(self, samples=16000, channels=1, value=.02):
        return {"sample_rate": 16000, "waveform": torch.full((1, channels, samples), value)}

    def test_ieee_float32_wav_retains_quiet_nonzero_and_amplitudes(self):
        audio = self.audio(samples=400, value=1e-9)
        audio["waveform"][0, 0, 1] = 1.5
        raw, options, shift, seconds = speech._audio_payload(audio, 0, 0)
        with av.open(io.BytesIO(raw)) as container:
            frames = list(container.decode(audio=0))
        values = np.concatenate([frame.to_ndarray().ravel() for frame in frames])
        self.assertTrue(np.all(values > 0)); self.assertAlmostEqual(values[1], 1.5)
        self.assertEqual(options["start_s"], 0.); self.assertEqual(shift, 0.); self.assertEqual(seconds, .025)

    def test_audio_budget_before_copy_and_large_existing_source_short_slice(self):
        class Huge:
            shape = (1, 8, 192000 * 3600)
            def __getitem__(self, _key): raise AssertionError("budget must reject before slicing/copying")
        with self.assertRaises(speech.SpeechReferenceError):
            speech._audio_payload({"sample_rate": 192000, "waveform": Huge()}, 0, 0)
        class LongSource:
            shape = (1, 1, 16000 * 3600)
            def __getitem__(self, key):
                window = key[2]
                return np.zeros((1, 1, window.stop - window.start), dtype=np.float32)
        raw, _, shift, seconds = speech._audio_payload({"sample_rate": 16000, "waveform": LongSource()}, 100, 5)
        self.assertLess(len(raw), 400000); self.assertEqual(shift, 100); self.assertEqual(seconds, 5)

    def test_invalid_audio_types_finite_rate_and_channels_fail_before_service(self):
        cases = ({"sample_rate": True, "waveform": torch.zeros((1, 1, 10))},
                 {"sample_rate": 7999, "waveform": torch.zeros((1, 1, 10))},
                 {"sample_rate": 16000, "waveform": torch.zeros((2, 1, 10))},
                 {"sample_rate": 16000, "waveform": torch.full((1, 1, 10), float("nan"))},
                 {"sample_rate": 16000, "waveform": torch.zeros((1, 1, 10), dtype=torch.complex64)})
        for audio in cases:
            with self.subTest(audio=audio["sample_rate"]), patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
                with self.assertRaises(speech.SpeechReferenceError): speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=audio)

    def test_actual_http_audio_transcribe_has_cpu_guard_and_no_chat_or_lifecycle(self):
        with asr_fixture() as (config, calls):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), provider_config=config)
        self.assertEqual([row[:2] for row in calls], [("GET", "/v1/asr/capabilities"), ("POST", "/v1/audio/transcribe")])
        payload = calls[1][2]
        self.assertEqual(payload["expected_device"], "cpu"); self.assertNotIn("contract_version", payload)
        self.assertTrue(base64.b64decode(payload["data"]).startswith(b"RIFF"))
        self.assertEqual(output.result[1], "原词不能改")
        self.assertEqual(output.result[0]["provenance"]["device"], "cpu")
        self.assertNotIn("PRIVATE_PATH", json.dumps(output.result, ensure_ascii=False))

    def test_missing_cpu_guard_never_posts_even_continue_policy(self):
        for caps in ({"supported": True, "device": "cpu"}, {"contract_version": 1, "cpu_guard": True, "device": "cuda", "supported": True}):
            with asr_fixture(capabilities=caps) as (config, calls):
                with self.assertRaises(speech.SpeechReferenceError) as raised:
                    speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), provider_config=config, failure_policy="continue_empty")
                self.assertEqual(raised.exception.category, "cpu_guard")
                self.assertEqual(len(calls), 1)

    def test_atomic_guard_conflict_cannot_be_swallowed_by_continue_policy(self):
        # Caps were CPU, but the guarded POST can observe a later CUDA profile.
        # All ASR conflicts conservatively stop; private text is not classified.
        with asr_fixture(code=409, result={"error": {"type": "asr_error", "message": "PRIVATE_PATH_OR_SETTINGS"}}) as (config, calls):
            with self.assertRaises(speech.SpeechReferenceError) as raised:
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(),
                    provider_config=config, failure_policy="continue_empty")
            self.assertEqual(raised.exception.category, "asr_conflict")
            self.assertNotIn("PRIVATE", str(raised.exception))
            self.assertEqual([row[0] for row in calls], ["GET", "POST"])

    def test_missing_guard_endpoint_cannot_silently_continue_or_post(self):
        with asr_fixture(get_code=404) as (config, calls):
            with self.assertRaises(speech.SpeechReferenceError) as raised:
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(),
                    provider_config=config, failure_policy="continue_empty")
            self.assertEqual(raised.exception.category, "cpu_guard")
            self.assertEqual([row[0] for row in calls], ["GET"])

    def test_operation_error_can_explicitly_continue_but_is_not_retried_or_leaked(self):
        with asr_fixture(code=503, result={"error": {"message": "PRIVATE_PATH_OR_LYRICS"}}) as (config, calls):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), provider_config=config, failure_policy="continue_empty")
        self.assertEqual(output.result[0]["status"], "unavailable")
        self.assertEqual(output.result[1], ""); self.assertNotIn("PRIVATE_PATH", json.dumps(output.result))
        self.assertEqual(sum(row[0] == "POST" for row in calls), 1)

    def test_audio_track_error_cannot_continue(self):
        for options in ({"audio_track": 1},):
            with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")), self.assertRaises(speech.SpeechReferenceError):
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), failure_policy="continue_empty", **options)

    def test_inactive_cached_media_cannot_change_explicit_source_selection(self):
        # Comfy may pass None for a cold lazy branch but an actual cached value
        # when another consumer has already evaluated it. Neither is selected.
        for cached in (None, object()):
            with self.subTest(cached=cached is not None), asr_fixture() as (config, calls):
                value = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), video=cached, provider_config=config)
                self.assertEqual(value.result[1], "原词不能改")
                self.assertEqual([row[1] for row in calls], ["/v1/asr/capabilities", "/v1/audio/transcribe"])
            video = video_types.VideoFromComponents(VideoComponents(images=torch.zeros((2, 16, 16, 3)), frame_rate=Fraction(2), audio=None))
            with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
                value = speech.T8SpeechReference.execute(mode="Enabled", source_mode="VIDEO", video=video, audio=cached)
                self.assertEqual(value.result[0]["status"], "no_track")

    def test_missing_selected_media_stops_before_transport_despite_inactive_cache(self):
        for source, options in (("AUDIO", {"video": object()}), ("VIDEO", {"audio": object()})):
            with self.subTest(source=source), patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")):
                with self.assertRaises(speech.SpeechReferenceError) as raised:
                    speech.T8SpeechReference.execute(mode="Enabled", source_mode=source, failure_policy="continue_empty", **options)
                self.assertEqual(raised.exception.category, "source_conflict")

    def test_explicit_automatic_source_ignores_hidden_provided_text_cache(self):
        with asr_fixture() as (config, calls):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(),
                provider_config=config, provided_text="旧字幕仅为切换前的缓存", provided_format="srt")
        self.assertEqual(output.result[1], "原词不能改")
        self.assertNotIn("旧字幕", json.dumps(calls, ensure_ascii=False))

    def test_components_audio_track_is_checked_before_transport(self):
        video = video_types.VideoFromComponents(VideoComponents(images=torch.zeros((2, 16, 16, 3)), frame_rate=Fraction(2), audio=self.audio()))
        with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service must not be touched")):
            with self.assertRaises(speech.SpeechReferenceError) as raised:
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="VIDEO", video=video, audio_track=1, failure_policy="continue_empty")
        self.assertEqual(raised.exception.category, "source_conflict")

    def test_manual_offset_applies_once_after_source_window_selection(self):
        # The guarded server receives unshifted audio; all word selection is in
        # source time. A later calibrated subtitle clock cannot erase the cue.
        for offset in (5000, -1000):
            with self.subTest(offset=offset), asr_fixture() as (config, calls):
                output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(samples=64000),
                    provider_config=config, start_s=2., duration_s=1., offset_ms=offset)
                self.assertEqual(calls[1][2]["offset_ms"], 0)
                self.assertEqual(output.result[1], "原词不能改")
                self.assertAlmostEqual(output.result[0]["cues"][0]["start_s"], 2.1 + offset / 1000)
                self.assertEqual(output.result[0]["window"], {"start_s": 2., "end_s": 3.})

    def test_negative_offset_cannot_silently_discard_an_entire_utterance(self):
        with asr_fixture() as (config, calls):
            with self.assertRaises(speech.SpeechReferenceError):
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(),
                    provider_config=config, offset_ms=-1000)
            self.assertEqual(sum(row[0] == "POST" for row in calls), 1)

    def test_negative_offset_clips_only_time_marks_review_and_retains_words(self):
        with asr_fixture() as (config, calls):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(),
                provider_config=config, offset_ms=-200)
        checked = output.result[0]
        self.assertEqual(checked["text"], "原词不能改")
        self.assertEqual(checked["cues"][0]["id"], "cue-1")
        self.assertEqual(checked["cues"][0]["start_s"], 0)
        self.assertAlmostEqual(checked["cues"][0]["end_s"], .2)
        self.assertTrue(checked["requires_review"])
        self.assertEqual(calls[1][2]["offset_ms"], 0)

    def test_original_chat_client_allowlist_is_not_expanded(self):
        with asr_fixture() as (config, calls):
            client = speech.StrataClient(config["strata_settings"])
            with self.assertRaises(speech.StrataProviderError): client.request("/v1/audio/transcribe", {})
            asr = speech.SpeechASRClient(config["strata_settings"])
            for path in ("/v1/asr/settings", "/v1/load", "/v1/chat/completions"):
                with self.assertRaises(speech.StrataProviderError): asr.request(path, {})
            self.assertEqual(calls, [])

    def test_cancel_propagates_and_no_incomplete_words_are_returned(self):
        class ComfyCancel(BaseException): pass
        with asr_fixture(delay=2) as (config, calls):
            client = speech.SpeechASRClient(config["strata_settings"])
            started = time.monotonic()
            def cancel():
                if time.monotonic() - started > .2: raise ComfyCancel()
            with self.assertRaises(ComfyCancel): client.request("/v1/audio/transcribe", {}, timeout=5, check=cancel)
            self.assertLess(time.monotonic() - started, 1.)
            self.assertEqual(sum(row[0] == "POST" for row in calls), 1)

    def test_official_file_keeps_raw_bytes_trim_and_never_local_audio_decode(self):
        raw = encoded_video(count=24, fps=4)
        video = video_types.VideoFromFile(io.BytesIO(raw), start_time=1, duration=2)
        response = transcript(); response["cues"][0].update(start_s=1.1, end_s=1.4)
        with asr_fixture(result=response) as (config, calls), patch.object(video_types.VideoFromFile, "get_components", side_effect=AssertionError("No full materialization")):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="VIDEO", video=video, provider_config=config)
        payload = calls[1][2]
        self.assertEqual(calls[1][1], "/v1/video/transcribe")
        self.assertEqual(base64.b64decode(payload["data"]), raw)
        self.assertEqual(payload["start_s"], 1.); self.assertEqual(payload["end_s"], 3.)
        self.assertAlmostEqual(output.result[0]["cues"][0]["start_s"], .1)

    def test_components_use_only_existing_audio_and_no_track_stays_offline(self):
        video = video_types.VideoFromComponents(VideoComponents(images=torch.zeros((2, 16, 16, 3)), frame_rate=Fraction(2), audio=None))
        with patch.object(speech, "SpeechASRClient", side_effect=AssertionError("service touched")), patch.object(video_types.VideoFromComponents, "get_components", side_effect=AssertionError("Do not materialize")):
            output = speech.T8SpeechReference.execute(mode="Enabled", source_mode="VIDEO", video=video)
        self.assertEqual(output.result[0]["status"], "no_track")
        self.assertNotIn("source_id", output.result[0]["provenance"])

    def test_unknown_and_list_video_are_explicitly_rejected(self):
        videos = [object()]
        if hasattr(video_types, "VideoFromList"):
            videos.append(video_types.VideoFromList([video_types.VideoFromFile(io.BytesIO(encoded_video()))]))
        for video in videos:
            with self.assertRaises(speech.SpeechReferenceError): speech.T8SpeechReference.execute(mode="Enabled", source_mode="VIDEO", video=video)

    def test_deadline_includes_validation_and_audio_encoding_before_asr_post(self):
        actual = speech._audio_payload
        def encoded(*args):
            result = actual(*args)
            clock[0] += 10
            return result
        clock = [100.]
        with asr_fixture() as (config, calls), patch.object(speech, "_audio_payload", side_effect=encoded), patch.object(speech.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(speech.SpeechReferenceError) as raised:
                speech.T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", audio=self.audio(), provider_config=config, timeout_s=5)
            self.assertEqual(raised.exception.category, "timeout")
            self.assertFalse(any(row[0] == "POST" for row in calls))


if __name__ == "__main__": unittest.main()
