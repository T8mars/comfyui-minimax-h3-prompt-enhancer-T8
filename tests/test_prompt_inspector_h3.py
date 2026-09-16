"""CPU-only H3 inspector regressions; import no provider or model runtime."""

import importlib.util
import json
import re
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
import comfy.cli_args

comfy.cli_args.args.cpu = True
PACKAGE_NAME = "t8_h3_inspector_cpu_tests"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE_NAME] = package
spec = importlib.util.spec_from_file_location(f"{PACKAGE_NAME}.prompt_inspector", ROOT / "prompt_inspector.py")
inspector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inspector
spec.loader.exec_module(inspector)


def base_prompt(body="[Shot 1] A woman walks past the window."):
    return "\n\n".join((
        f"integrated_multimodal_description: {body}",
        "overall_soundscape: Soft room tone and footsteps.",
        "non_diegetic_music: N/A",
    ))


def reference_prompt(body="[Shot 1] <Subject 1> walks past the window."):
    return "\n\n".join((
        "subject_definitions:\n<Subject 1> is the woman in <Picture 1>. "
        "<Picture 2> is the first frame of [Shot 1].",
        "summary:\n[reference generation] <Subject 1> walks in the referenced room.",
        "retention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved - identity.\n"
        "<Picture 2> ([Shot 1] first frame): fully_preserved - composition.",
        f"detailed_description:\nThe video is cinematic.\n{body}",
        "overall_soundscape:\nSoft room tone and footsteps.",
        "non_diegetic_music:\nN/A",
    ))


class H3InspectorTests(unittest.TestCase):
    def test_vocal_language_protocol_is_english_without_rewriting_words_or_visible_text(self):
        bad = base_prompt('[Shot 1] 女人 (S1) 说：<d>[中文] 保留（S1）原文。</d>')
        _, codes = self.inspect(bad)
        self.assertIn('vocal_language_tag', codes)
        good = base_prompt('[Shot 1] 女人 (S1) 说：<d>[Chinese] 保留（S1）原文。</d>')
        _, codes = self.inspect(good)
        self.assertNotIn('vocal_language_tag', codes)
        visible = base_prompt('[Shot 1] 招牌准确写着 "<d>[中文] 原文</d>"，女人走过。')
        _, codes = self.inspect(visible)
        self.assertNotIn('vocal_language_tag', codes)

    def inspect(self, prompt, **options):
        passthrough, report_json, summary = inspector.inspect_prompt(
            prompt, prompt_family=inspector.FAMILY_H3, **options,
        )
        self.assertEqual(passthrough, prompt)
        self.assertIn("仅本地结构检查", summary)
        report = json.loads(report_json)
        self.assertEqual(report["schema_version"], "t8-prompt-inspector/v1")
        self.assertIn("not a creative-quality judgment", report["score_scope"])
        return report, {item["code"] for item in report["warnings"]}

    def test_valid_base_modes_keep_one_target_shot(self):
        alignments = {
            "T2VA": "",
            "I2VA": "For the target video, at 0.00 seconds into the target video, "
                    "<Picture 1> (from [Shot 1]) is fully referenced.\n\n",
            "FL2VA": "How the reference pictures align with the target video — Picture 1 "
                     "(from Shot 1) aligns with the 0.00-second mark of the target video; "
                     "Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.\n\n",
            "L2VA": "How the reference pictures align with the target video — <Picture 1> "
                    "(from [Shot 1]) aligns with the 8.00-second mark of the target video.\n\n",
        }
        for mode, alignment in alignments.items():
            with self.subTest(mode=mode):
                report, codes = self.inspect(alignment + base_prompt(), task_intent=mode,
                                             expected_shot_count="1", duration_seconds=8)
                self.assertEqual(report["detected_shots"], 1)
                self.assertEqual(report["structural_score"], 100, codes)

    def test_valid_reference_fields_and_metadata_shots(self):
        report, codes = self.inspect(reference_prompt(), task_intent="Ref2VA",
                                     expected_shot_count="1", duration_seconds=8)
        self.assertEqual(report["detected_shots"], 1)
        self.assertEqual(report["structural_score"], 100, codes)
        self.assertNotIn("h3_missing_core_fields", codes)

    def test_auto_recognizes_reference_mode_even_without_sound_fields(self):
        prompt = reference_prompt().split("overall_soundscape:", 1)[0]
        _, report_json, _ = inspector.inspect_prompt(prompt)
        report = json.loads(report_json)
        self.assertEqual(report["family"], inspector.FAMILY_H3)
        missing = next(item for item in report["warnings"] if item["code"] == "h3_missing_core_fields")
        self.assertIn("overall_soundscape", missing["message"])
        self.assertNotIn("integrated_multimodal_description", missing["message"])

    def test_reference_without_body_does_not_count_retention_as_timeline(self):
        prompt = reference_prompt().replace("detailed_description:\nThe video is cinematic.\n"
                                            "[Shot 1] <Subject 1> walks past the window.\n\n", "")
        report, codes = self.inspect(prompt, expected_shot_count="1")
        self.assertEqual(report["detected_shots"], 0)
        self.assertIn("h3_missing_core_fields", codes)
        self.assertIn("shot_count_mismatch", codes)

    def test_dialogue_and_visible_text_literals_are_not_shots_or_cut_times(self):
        body = ('[Shot 1] A woman (S1) says: <d>[English] Wait at 00:59.000 for '
                '[Shot 9].</d> A sign displays the exact text "[Shot 7] At 00:58.000". '
                'A card reads “镜头6：[Shot 6] At 00:57.000”. '
                '[Shot 2] At 00:03.500, the camera cuts to her hand.')
        report, codes = self.inspect(base_prompt(body), expected_shot_count="2", duration_seconds=8)
        self.assertEqual(report["detected_shots"], 2)
        self.assertEqual(report["structural_score"], 100, codes)

    def test_literal_fake_field_header_does_not_close_the_timeline(self):
        body = ('[Shot 1] A woman (S1) says: <d>[English] The card reads:\n'
                'retention_analysis: [Shot 8] At 00:58.000.</d> '
                '[Shot 2] At 00:03.500, the camera cuts to her hand.')
        report, codes = self.inspect(base_prompt(body), expected_shot_count="2", duration_seconds=8)
        self.assertEqual(report["detected_shots"], 2)
        self.assertNotIn("h3_missing_core_fields", codes)
        self.assertNotIn("h3_field_order", codes)

    def test_valid_speaker_forms(self):
        forms = (
            'The woman with a quiet voice (S1) says: <d>[English] Wait for me.</d>',
            'The two children (S1,S2) shout together, <d>[English] Wait!</d>',
            'The man (S1) says in an off-screen voiceover: <d>[English] I remember.</d> '
            'while his lips remain completely closed.',
            '<Subject 1> (S1) turns and says, <d>[Chinese] 等我。</d>',
        )
        for form in forms:
            with self.subTest(form=form):
                _, codes = self.inspect(base_prompt("[Shot 1] " + form))
                self.assertNotIn("speaker_contract", codes)

    def test_reused_audio_lyric_cue_needs_no_invented_speaker(self):
        body = '[Shot 1] When <Audio 1> reaches the phrase <d>[English] Wait for me.</d>, ' \
               '<Subject 1> raises a hand without speaking.'
        _, codes = self.inspect(reference_prompt(body))
        self.assertNotIn("speaker_contract", codes)

    def test_physical_singer_cannot_use_audio_label_instead_of_speaker(self):
        body = '[Shot 1] <Subject 1> sings using <Audio 1> as a timbre reference: ' \
               '<d>[English] Wait for me.</d>'
        _, codes = self.inspect(reference_prompt(body))
        self.assertIn("speaker_contract", codes)

    def test_real_missing_speaker_is_reported(self):
        for body in (
            '[Shot 1] She says: <d>[English] Wait for me.</d>',
            '[Shot 1] <d>[English] Wait for me.</d>',
            '[Shot 1] She says: Wait for me.',
            '[Shot 1] A card reads "(S1)". She says: <d>[English] Wait.</d>',
        ):
            with self.subTest(body=body):
                _, codes = self.inspect(base_prompt(body))
                self.assertIn("speaker_contract", codes)

    def test_speaker_in_definition_or_previous_shot_does_not_hide_missing_event_id(self):
        body = '[Shot 1] <Subject 1> (S1) says: <d>[English] Wait.</d> ' \
               '[Shot 2] At 00:03.500, <Subject 2> says: <d>[English] No.</d>'
        _, codes = self.inspect(reference_prompt(body))
        self.assertIn("speaker_contract", codes)
        _, codes = self.inspect(reference_prompt('[Shot 1] She says: <d>[English] Wait.</d>')
                               .replace('is the woman in <Picture 1>', 'is the woman (S1) in <Picture 1>'))
        self.assertIn("speaker_contract", codes)

    def test_no_dialogue_and_quoted_sign_do_not_need_a_speaker(self):
        _, codes = self.inspect(base_prompt('[Shot 1] No dialogue or narration. '
                                            'A sign reading the exact text "营业中" glows.'))
        self.assertNotIn("speaker_contract", codes)

    def test_visible_literal_dialogue_tag_is_not_a_vocal_event(self):
        body = '[Shot 1] A card displays the exact text "<d>[English] [Shot 8] At 00:59.000.</d>".'
        report, codes = self.inspect(base_prompt(body), expected_shot_count="1", duration_seconds=8)
        self.assertEqual(report["detected_shots"], 1)
        self.assertNotIn("speaker_contract", codes)
        self.assertNotIn("duration_budget", codes)

    def test_missing_and_empty_fields_still_warn(self):
        for prompt in (
            base_prompt().replace("non_diegetic_music: N/A", ""),
            reference_prompt().replace("non_diegetic_music:\nN/A", "non_diegetic_music:"),
        ):
            with self.subTest(prompt=prompt):
                _, codes = self.inspect(prompt)
                self.assertIn("h3_missing_core_fields", codes)

    def test_explicit_mode_does_not_accept_a_hybrid_schema(self):
        _, codes = self.inspect(reference_prompt(), task_intent="I2VA")
        self.assertIn("h3_missing_core_fields", codes)
        _, codes = self.inspect(base_prompt() + "\n\nsubject_definitions: A woman.", task_intent="T2VA")
        self.assertIn("h3_field_order", codes)

    def test_actual_shot_count_sequence_and_cut_order_defects_still_warn(self):
        cases = (
            ('[Shot 1] A woman walks. [Shot 3] At 00:02.000, a door opens.', "shot_sequence"),
            ('[Shot 1] A woman walks. [Shot 2] At 00:04.000, a door opens. '
             '[Shot 3] At 00:03.000, she leaves.', "non_monotonic_timecodes"),
            ('[Shot 1] A woman walks. [Shot 2] At 00:03.000, a door opens. '
             '[Shot 3] At 00:03.000, she leaves.', "non_monotonic_timecodes"),
            ('[Shot 1] A woman walks. [Shot 2] At 00:00.000, a door opens.', "non_monotonic_timecodes"),
        )
        for body, warning in cases:
            with self.subTest(warning=warning, body=body):
                _, codes = self.inspect(base_prompt(body), duration_seconds=8)
                self.assertIn(warning, codes)
        _, codes = self.inspect(base_prompt(), expected_shot_count="2")
        self.assertIn("shot_count_mismatch", codes)

    def test_cut_at_or_after_target_end_is_out_of_budget(self):
        for time in ("00:08.000", "00:09.000"):
            with self.subTest(time=time):
                _, codes = self.inspect(base_prompt('[Shot 1] A woman walks. '
                    f'[Shot 2] At {time}, the camera cuts to the door.'), duration_seconds=8)
                self.assertIn("duration_budget", codes)

    def test_malformed_or_missing_cut_times_still_warn(self):
        for body in (
            '[Shot 1] At 00:00.000, a woman walks.',
            '[Shot 1] A woman walks. [Shot 2] The camera cuts to a door.',
            '[Shot 1] A woman walks. [Shot 2] At 00:03.5, the camera cuts to a door.',
            '[Shot 1] A woman walks. [Shot 2] At 00:63.000, the camera cuts to a door.',
        ):
            with self.subTest(body=body):
                _, codes = self.inspect(base_prompt(body))
                self.assertIn("h3_shot_timecode", codes)

    def test_native_official_examples_have_no_false_contract_warnings(self):
        for guide in ("base-en.txt", "ref-en.txt"):
            text = (ROOT / "official_skills" / "h3-prompt-writing" / "references" / guide).read_text(encoding="utf-8")
            blocks = re.findall(r"```text\n(.*?)\n```", text, re.DOTALL)
            examples = [block for block in blocks if "overall_soundscape:" in block
                        and "non_diegetic_music:" in block and "[Shot 1]" in block and "..." not in block]
            self.assertTrue(examples, guide)
            for index, example in enumerate(examples):
                with self.subTest(guide=guide, index=index):
                    _, codes = self.inspect(example)
                    self.assertFalse(codes & {"shot_sequence", "h3_missing_core_fields",
                                              "non_monotonic_timecodes", "speaker_contract", "h3_field_order"}, codes)

    def test_original_node_schema_and_execute_passthrough_are_unchanged(self):
        schema = inspector.T8PromptInspector.define_schema()
        self.assertEqual(schema.node_id, "T8PromptInspector")
        self.assertEqual([item.id for item in schema.inputs], ["prompt", "prompt_family",
            "expected_shot_count", "expected_language", "instrumental", "task_intent", "duration_seconds", "source_prompt"])
        self.assertEqual([item.display_name for item in schema.outputs], ["original_prompt", "warnings_json", "summary"])
        prompt = "  [Shot 7] A malformed draft.\r\n"
        result = inspector.T8PromptInspector.execute(prompt, prompt_family=inspector.FAMILY_H3)
        self.assertEqual(result.result[0], prompt)

    def test_seedance_and_music_behavior_stays_native_and_nonblocking(self):
        prompt = "镜头2：人物出现。"
        passthrough, report_json, _ = inspector.inspect_prompt(prompt, inspector.FAMILY_SEEDANCE, "2")
        self.assertEqual(passthrough, prompt)
        self.assertIn("shot_sequence", {item["code"] for item in json.loads(report_json)["warnings"]})
        music = "### Global Metadata\nInstrumental\n### Vocal Details\nNone\n### Arrangement\nPiano."
        _, report_json, _ = inspector.inspect_prompt(music)
        self.assertEqual(json.loads(report_json)["family"], inspector.FAMILY_MUSIC)
        self.assertEqual(json.loads(report_json)["structural_score"], 100)

    def test_cpu_only_import_does_not_start_cuda_or_load_model_runtimes(self):
        import torch
        self.assertFalse(torch.cuda.is_initialized())
        for name in ("nodes", "local_qwen_provider", "local_qwen_runtime", "local_qwen_standalone_runtime"):
            self.assertNotIn(f"{PACKAGE_NAME}.{name}", sys.modules)


if __name__ == "__main__":
    unittest.main()
