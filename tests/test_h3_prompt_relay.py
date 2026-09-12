"""Pure CPU/string tests: intentionally do not import the ComfyUI package."""

import ast
import hashlib
import importlib.util
import json
import math
import os
import re
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "t8_h3_prompt_relay_pure_tests", Path(__file__).resolve().parents[1] / "h3_prompt_relay.py"
)
relay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(relay)


NATIVE = (
    "integrated_multimodal_description: [Shot 1] She hands over the ticket.\n\n"
    "overall_soundscape: Quiet platform ambience.\n\nnon_diegetic_music: N/A"
)
REF_NATIVE = (
    "subject_definitions: <Subject 1> is the woman in <Picture 1>.\n\n"
    "summary: [reference generation] A woman hands over a ticket.\n\n"
    "retention_analysis: <Subject 1>: fully_preserved - Appearance.\n\n"
    "detailed_description: Live action. [Shot 1] <Subject 1> hands over the ticket.\n\n"
    "overall_soundscape: Platform ambience.\n\nnon_diegetic_music: N/A"
)


def payload(count=3, **overrides):
    result = {
        "global_prompt": "Stable identity and clothing, continuous shot, quiet ambience.",
        "events": [
            {"prompt": f"Action {i + 1}.", "end_state": f"Settled pose {i + 1}.", "weight": 1}
            for i in range(count)
        ],
        "native_prompt": NATIVE,
    }
    result.update(overrides)
    return result


def compile_payload(data=None, duration=8, **kwargs):
    return relay.compile_relay_response(json.dumps(data or payload(), ensure_ascii=False), duration, **kwargs)


def frames(output):
    return [tuple(round(float(value) * 24) for value in line.split("-"))
            for line in output["time_ranges"].splitlines()]


class H3PromptRelayTests(unittest.TestCase):
    def test_modes_and_output_slots(self):
        self.assertEqual(relay.NORMAL, "普通增强 / Normal")
        self.assertEqual(relay.RELAY, "Prompt Relay 编排")
        result = compile_payload()
        self.assertEqual(set(result), {
            "enhanced_prompt", "global_prompt", "local_prompts", "time_ranges", "relay_length", "relay_report",
        })
        self.assertEqual(result["enhanced_prompt"], NATIVE)
        self.assertEqual(result["relay_length"], 192)
        self.assertEqual(frames(result), [(0, 64), (64, 128), (128, 192)])
        self.assertEqual(len(result["local_prompts"].splitlines()), 3)

    def test_native_text_is_preserved_byte_for_byte(self):
        native = "  " + NATIVE + "\n"
        result = compile_payload(payload(native_prompt=native))
        self.assertEqual(result["enhanced_prompt"], native)
        self.assertNotIn("Global scene:", result["enhanced_prompt"])

    def test_explicit_seconds_override_weights(self):
        data = payload()
        data["events"][0]["weight"] = 999
        result = compile_payload(data, time_ranges="0-2.5\n2.5-5\n5-8")
        self.assertEqual(frames(result), [(0, 60), (60, 120), (120, 192)])
        self.assertEqual(result["time_ranges"], "0-2.5\n2.5-5\n5-8")
        self.assertEqual(json.loads(result["relay_report"])["timing_source"], "explicit_seconds")

    def test_padding_extends_only_final_range_and_keeps_delivery_state(self):
        data = payload(2)
        data["events"][-1]["prompt"] = "(S1) says: <d>[普通话] 你的车票。</d> She lets go."
        data["events"][-1]["end_state"] = "The passenger holds the ticket; both hands are still."
        result = compile_payload(data, duration=25.29, time_ranges="0-12\n12-25.29")
        report = json.loads(result["relay_report"])
        self.assertEqual(report["delivery_frames"], 607)
        self.assertEqual(report["padding_frames"], 10)
        self.assertEqual(result["relay_length"], 617)
        self.assertEqual(frames(result), [(0, 288), (288, 617)])
        self.assertEqual(report["events"][1]["delivery_frames"], [288, 607])
        lines = result["local_prompts"].splitlines()
        self.assertNotIn("only hold", lines[0])
        self.assertIn("before 25.291667 seconds", lines[1])
        self.assertIn("From 25.291667 to 25.708333 seconds", lines[1])
        self.assertIn("no new action, dialogue", lines[1])
        self.assertEqual(lines[1].count("你的车票。"), 1)
        self.assertIn(data["events"][-1]["end_state"], lines[1])

    def test_already_aligned_timeline_has_no_padding_instruction(self):
        result = compile_payload()
        self.assertEqual(json.loads(result["relay_report"])["padding_frames"], 0)
        self.assertNotIn("only hold", result["local_prompts"])

    def test_weighted_integer_allocation_is_deterministic_and_positive(self):
        data = payload(3)
        for event, weight in zip(data["events"], [1, 2, 3]):
            event["weight"] = weight
        result = compile_payload(data)
        self.assertEqual(frames(result), [(0, 35), (35, 99), (99, 192)])
        self.assertEqual(result, compile_payload(data))

    def test_weight_extremes_never_overflow_or_starve_events(self):
        data = payload(3)
        for event, weight in zip(data["events"], [1e308, 1e308, 1e-308]):
            event["weight"] = weight
        spans = frames(compile_payload(data))
        self.assertEqual(spans, [(0, 94), (94, 187), (187, 192)])

    def test_all_exactly_five_frames_before_padding(self):
        result = compile_payload(payload(3), duration=15 / 24)
        report = json.loads(result["relay_report"])
        self.assertEqual([event["delivery_frames"] for event in report["events"]], [[0, 5], [5, 10], [10, 15]])
        self.assertEqual(result["relay_length"], 22)

    def test_too_many_events_for_duration_fail_before_padding_can_hide_it(self):
        with self.assertRaisesRegex(ValueError, "at least 5"):
            compile_payload(payload(3), duration=14 / 24)
        with self.assertRaisesRegex(ValueError, "at least 5"):
            relay.relay_instruction(14 / 24, 3)

    def test_event_limit_32_and_33(self):
        result = compile_payload(payload(32))
        self.assertEqual(len(frames(result)), 32)
        with self.assertRaisesRegex(ValueError, "1..32"):
            compile_payload(payload(33))

    def test_zero_events_are_not_confused_with_auto_event_count(self):
        with self.assertRaisesRegex(ValueError, "zero-event bypass"):
            compile_payload(payload(0))
        self.assertEqual(len(frames(compile_payload(payload(1), event_count=0))), 1)

    def test_single_event_reports_no_competitive_route(self):
        result = compile_payload(payload(1))
        self.assertEqual(frames(result), [(0, 192)])
        self.assertTrue(any("单事件" in item for item in json.loads(result["relay_report"])["warnings"]))

    def test_explicit_and_requested_event_counts_must_match(self):
        for kwargs in [{"event_count": 2}, {"time_ranges": "0-4\n4-8"}]:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, "Expected 2 events"):
                compile_payload(**kwargs)
        with self.assertRaisesRegex(ValueError, "event_count does not match"):
            relay.relay_instruction(8, 3, "0-4\n4-8")

    def test_event_line_breaks_and_pipe_are_rejected_not_sanitized(self):
        for separator in ["|", "\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]:
            for key in ["prompt", "end_state"]:
                for value in ["A" + separator + "B", "A" + separator]:
                    data = payload()
                    data["events"][0][key] = value
                    with self.subTest(separator=repr(separator), key=key), self.assertRaisesRegex(ValueError, "newline or ASCII"):
                        compile_payload(data)

    def test_end_state_speech_tags_warn_without_semantic_rejection(self):
        for speech in ["<d>[English] Next!</d>", "<D>Next!</D>", "<scenetrans>", "<cutoff>"]:
            data = payload()
            data["events"][-1]["end_state"] = speech
            with self.subTest(speech=speech):
                report = json.loads(compile_payload(data)["relay_report"])
                self.assertTrue(any("end_state 含语音标签" in warning for warning in report["warnings"]))

    def test_compiler_deadlines_and_padding_follow_effective_language(self):
        data = payload(2)
        data["events"][0].update(prompt="她捡起车票。", end_state="车票已在她手中。")
        data["events"][1].update(prompt="她将车票交还乘客。", end_state="车票已交还乘客。")
        result = compile_payload(data, duration=7, output_language="中文")
        self.assertIn("秒之前完成本事件的动作与对白", result["local_prompts"])
        self.assertIn("只延续上述已经完成的稳定末态", result["local_prompts"])
        self.assertNotIn("Complete this event", result["local_prompts"])
        self.assertNotIn("Settled end state", result["local_prompts"])
        self.assertEqual(result["enhanced_prompt"], NATIVE)

    def test_unicode_dialogue_and_punctuation_are_not_rewritten(self):
        dialogue = '(S1) says: <d>[普通话] “你好！”——别走……</d> The sign reads "左→右".'
        data = payload()
        data["events"][1]["prompt"] = dialogue
        result = compile_payload(data)
        self.assertIn(dialogue, result["local_prompts"])

    def test_empty_required_strings_fail(self):
        for key in ["global_prompt", "native_prompt"]:
            for value in ["", "  ", None, 5]:
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "non-empty"):
                    compile_payload(payload(**{key: value}))
        for key in ["prompt", "end_state"]:
            data = payload()
            data["events"][0][key] = " "
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "non-empty"):
                compile_payload(data)

    def test_bad_weight_types_and_values_fail(self):
        for value in [0, -1, True, None, "1", [], {}, float("nan"), float("inf"), -float("inf"), 10 ** 400]:
            data = payload()
            data["events"][0]["weight"] = value
            with self.subTest(value=str(value)[:25]), self.assertRaisesRegex(ValueError, "finite|non-finite"):
                compile_payload(data)

    def test_malformed_json_and_wrong_envelopes_fail_closed(self):
        for raw in ["", "not JSON", "{}", "[]", '"plain"', "null", json.dumps({"prompt": NATIVE}),
                    "prefix " + json.dumps(payload()), json.dumps(payload()) + " suffix", "{bad}", "[] []"]:
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                relay.compile_relay_response(raw, 8)

    def test_duplicate_json_keys_are_rejected(self):
        raw = json.dumps(payload()).replace('"weight": 1', '"weight": 1, "weight": 2', 1)
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            relay.compile_relay_response(raw, 8)

    def test_events_must_be_objects_with_required_fields(self):
        for events in ["text", None, [None], [{"prompt": "A", "end_state": "B"}]]:
            with self.subTest(events=events), self.assertRaises(ValueError):
                compile_payload(payload(events=events))

    def test_extra_json_fields_are_ignored_with_a_report_warning(self):
        data = payload(notes="Authoring notes")
        data["events"][0].update(start=999, end=1000, additional_note="Note")
        result = compile_payload(data)
        self.assertEqual(frames(result), [(0, 64), (64, 128), (128, 192)])
        self.assertTrue(any("额外" in warning for warning in json.loads(result["relay_report"])["warnings"]))

    def test_whole_code_fence_is_allowed_but_surrounding_prose_is_not(self):
        for tag in ["json", "JSON", ""]:
            raw = f"```{tag}\n{json.dumps(payload())}\n```"
            self.assertEqual(relay.compile_relay_response(raw, 8)["enhanced_prompt"], NATIVE)
        with self.assertRaisesRegex(ValueError, "Malformed JSON code fence"):
            relay.compile_relay_response("```json\n" + json.dumps(payload()), 8)

    def test_native_requires_correct_nonempty_ordered_fields(self):
        bad = [json.dumps({"integrated_multimodal_description": "A", "overall_soundscape": "B", "non_diegetic_music": "C"}),
               "```text\n" + NATIVE + "\n```", "global_prompt: Summary only",
               NATIVE.replace("overall_soundscape:", "missing_soundscape:"),
               NATIVE.replace("Quiet platform ambience.", ""),
               "non_diegetic_music: N/A\n" + NATIVE, REF_NATIVE]
        for native in bad:
            with self.subTest(native=native[:40]), self.assertRaisesRegex(ValueError, "native_prompt"):
                compile_payload(payload(native_prompt=native))

    def test_ref2va_uses_six_native_fields(self):
        result = compile_payload(payload(native_prompt=REF_NATIVE), task_type="Ref2VA")
        self.assertEqual(result["enhanced_prompt"], REF_NATIVE)
        with self.assertRaisesRegex(ValueError, "native_prompt"):
            compile_payload(task_type="Ref2VA")

    def test_keyframe_alignment_declaration_is_preserved(self):
        for task, line in [
            ("I2VA", "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."),
            ("FL2VA", "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video."),
            ("L2VA", "How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 8.00-second mark of the target video."),
        ]:
            native = line + "\n\n" + NATIVE
            with self.subTest(task=task):
                self.assertEqual(compile_payload(payload(native_prompt=native), task_type=task)["enhanced_prompt"], native)

    def test_bad_time_syntax_or_coverage_is_not_repaired_silently(self):
        for ranges in ["00:00.000-00:04.000\n4-8", "0-4s\n4-8", "0-4|4-8", "0-4\n4-8\n8-9",
                       "0-3\n4-8", "0-5\n4-8", "1-4\n4-8", "0-4\n4-7", "4-8\n0-4",
                       "0-0.1\n0.1-8", "0-4\n4-9", "0-1e0\n1-8", "-1-4\n4-8", "0-4\n4-4"]:
            with self.subTest(ranges=ranges), self.assertRaisesRegex(ValueError, "time_ranges"):
                compile_payload(payload(2), time_ranges=ranges)

    def test_parser_compatible_range_separators_and_blank_lines(self):
        for separator in ["-", ":", "–", "—"]:
            result = compile_payload(payload(2), time_ranges=f" \n 0 {separator} 4\r\n4 {separator} 8\n ")
            self.assertEqual(result["time_ranges"], "0-4\n4-8")

    def test_explicit_padding_as_user_timeline_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "alignment padding"):
            compile_payload(payload(2), duration=25.29, time_ranges="0-12\n12-25.708333")

    def test_python_round_ties_to_even_for_delivery_and_boundaries(self):
        result = compile_payload(payload(2), duration=1.1875, time_ranges="0-0.4375\n0.4375-1.1875")
        report = json.loads(result["relay_report"])
        self.assertEqual(report["delivery_frames"], 28)  # 28.5 -> 28, not 29.
        self.assertEqual(report["events"][0]["delivery_frames"], [0, 10])  # 10.5 -> 10.
        self.assertEqual(report["events"][1]["delivery_frames"], [10, 28])

    def test_round_trip_six_decimals_for_every_frame_in_node_range(self):
        for frame in range(3610):
            seconds = relay._seconds(frame)
            self.assertEqual(round(float(seconds) * 24), frame)
            self.assertLessEqual(len(seconds.partition(".")[2]), 6)

    def test_alignment_math_across_durations_and_event_counts(self):
        for delivery in [5, 6, 21, 22, 23, 124, 125, 160, 191, 192, 193, 583, 607, 3600]:
            for count in [1, min(3, delivery // 5), min(32, delivery // 5)]:
                result = compile_payload(payload(count), duration=delivery / 24)
                report = json.loads(result["relay_report"])
                spans = frames(result)
                self.assertEqual((result["relay_length"] - 5) % 17, 0)
                self.assertGreaterEqual(result["relay_length"], delivery)
                self.assertLess(result["relay_length"] - delivery, 17)
                self.assertEqual(spans[0][0], 0)
                self.assertEqual(spans[-1][1], result["relay_length"])
                self.assertTrue(all(end - start >= 5 for start, end in spans))
                self.assertTrue(all(spans[i][1] == spans[i + 1][0] for i in range(count - 1)))
                self.assertEqual(report["delivery_frames"], delivery)
        self.assertEqual(compile_payload(payload(1), duration=150)["relay_length"], 3609)

    def test_invalid_request_parameters_fail_before_api_instruction(self):
        for duration in [0, -1, True, "8", None, float("nan"), float("inf"), 1e308, 0.1, 10 ** 400]:
            with self.subTest(duration=str(duration)[:20]), self.assertRaises(ValueError):
                relay.relay_instruction(duration)
        for count in [-1, 33, True, 1.5, "2", None]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                relay.relay_instruction(8, count)
        with self.assertRaisesRegex(ValueError, "task_type"):
            relay.relay_instruction(8, task_type="unknown")

    def test_instruction_explicit_times_take_precedence_over_auto_count(self):
        instruction = relay.relay_instruction(8, 0, "0-2.5\n2.5-5\n5-8", "Ref2VA")
        for snippet in ["Return exactly 3 events", "native_prompt", "end_state", "retention_analysis", "same"]:
            self.assertIn(snippet.lower(), instruction.lower())
        self.assertIn("0-2.5", instruction)
        self.assertNotIn("Choose 1..", instruction)

    def test_instruction_auto_count_respects_minimum_frames(self):
        self.assertIn("Choose 1..2", relay.relay_instruction(10 / 24))
        self.assertIn("Choose 1..32", relay.relay_instruction(8))

    def test_report_does_not_claim_runtime_validation_or_emit_plan_hash(self):
        report = json.loads(compile_payload()["relay_report"])
        self.assertEqual(report["status"], "static_validation_passed")
        self.assertIn("未生成视频", report["validation_scope"])
        self.assertNotIn("plan_hash", report)
        self.assertNotIn("binding_hash", report)
        wiring = " ".join(report["wiring_requirements"])
        for snippet in ["prompt_relay_events disconnected", "timing_mode=seconds", "apply_exp", "segment_prompts_json empty", "joint_av_exp", "lock_source"]:
            self.assertIn(snippet, wiring)


@unittest.skipUnless(os.environ.get("T8_RELAY_EXECUTION_ROOT"), "Optional real parser contract: set T8_RELAY_EXECUTION_ROOT")
class DownstreamParserContractTests(unittest.TestCase):
    """Execute selected actual pure parser AST nodes, NOT the model module.

    Opt in with the reviewed execution project's root. No imports from its
    ComfyUI/Torch/GPU dependencies are evaluated, and no code is copied here.
    """

    @classmethod
    def setUpClass(cls):
        root = Path(os.environ["T8_RELAY_EXECUTION_ROOT"])
        source = root / "h3_t8" / "prompt_relay_advanced.py"
        core = root / "h3_t8" / "core.py"
        functions = {
            "_canonical_json", "_sha256_json", "_local_prompt_lines", "_parse_range",
            "_explicit_ranges", "_auto_equal_ranges", "_validate_ranges", "_paper_parameters",
            "_legacy_parameters", "build_prompt_relay_plan",
        }
        constants = {
            "_RANGE_RE", "MATH_PROFILES", "TIMING_MODES", "PROMPT_RELAY_PLAN_TYPE", "PROMPT_RELAY_PLAN_SCHEMA",
        }
        body = []
        for node in ast.parse(core.read_text(encoding="utf-8-sig"), filename=str(core)).body:
            if isinstance(node, ast.FunctionDef) and node.name == "align_frame_count":
                body.append(node)
        for node in ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source)).body:
            if isinstance(node, ast.FunctionDef) and node.name in functions:
                body.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in constants for target in node.targets):
                body.append(node)
        cls.namespace = {"FPS": 24, "json": json, "hashlib": hashlib, "math": math, "re": re}
        exec(compile(ast.Module(body=body, type_ignores=[]), str(source), "exec"), cls.namespace)
        cls.source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    def check_contract(self, result):
        plan, _, length, timeline, report = self.namespace["build_prompt_relay_plan"](
            global_prompt=result["global_prompt"], local_prompts=result["local_prompts"],
            time_ranges=result["time_ranges"], length=result["relay_length"], timing_mode="seconds",
            math_profile="paper_v1", epsilon=0.1, allow_gaps=False, allow_overlaps=False,
        )
        self.assertEqual(length, result["relay_length"])
        self.assertEqual([(e["start_frame"], e["end_frame_exclusive"]) for e in plan["events"]], frames(result))
        self.assertEqual(len(json.loads(timeline)["events"]), len(frames(result)))
        self.assertEqual(json.loads(report)["status"], "plan_ready")

    def test_actual_parser_accepts_eight_second_explicit_and_weighted(self):
        for explicit in ["", "0-2.5\n2.5-5\n5-8"]:
            data = payload()
            for event, weight in zip(data["events"], [1, 2, 4]):
                event["weight"] = weight
            with self.subTest(explicit=bool(explicit)):
                self.check_contract(compile_payload(data, time_ranges=explicit))

    def test_actual_parser_accepts_617_frame_explicit_and_weighted(self):
        for explicit in ["", "0-5\n5-17\n17-25.29"]:
            data = payload()
            for event, weight in zip(data["events"], [2, 4, 1]):
                event["weight"] = weight
            with self.subTest(explicit=bool(explicit)):
                result = compile_payload(data, duration=25.29, time_ranges=explicit, output_language="中文")
                self.assertEqual(result["relay_length"], 617)
                self.check_contract(result)


if __name__ == "__main__":
    unittest.main()
