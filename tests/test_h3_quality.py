"""Independent CPU-only contracts for H3 quality; no provider or Comfy import.

Negative cases are regression requirements, not assumptions that generation is
always correct. Semantic/physical feasibility remains explicitly unverified.
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import h3_quality as quality


def base(body="[Shot 1] Alice walks toward the window.", *, sound="Quiet room ambience and footsteps.", music="N/A"):
    return "\n\n".join((f"integrated_multimodal_description: {body}",
                         f"overall_soundscape: {sound}", f"non_diegetic_music: {music}"))


def reference(body="[Shot 1] <Subject 1> walks toward the window.", *,
              definitions="<Subject 1> is Alice in <Picture 1>, wearing a red coat.",
              summary="[reference generation] <Subject 1> walks in the referenced room.",
              retention="<Subject 1>: fully_preserved - identity and red coat.",
              sound="Quiet room ambience and footsteps.", music="N/A"):
    return "\n\n".join((f"subject_definitions:\n{definitions}", f"summary:\n{summary}",
                         f"retention_analysis:\n{retention}", f"detailed_description:\n{body}",
                         f"overall_soundscape:\n{sound}", f"non_diegetic_music:\n{music}"))


def vocal(words, *, speaker="S1", entity="Alice", language="Chinese"):
    return f"{entity} ({speaker}) says: <d>[{language}] {words}</d>"


class H3QualityTests(unittest.TestCase):
    def inspect(self, text, **kwargs):
        report = quality.check_h3(text, **kwargs)
        self.assertEqual(report["schema_version"], "t8-h3-quality/v1")
        self.assertIn("physical_plausibility", report["unchecked"])
        self.assertIn("rendered_video_quality", report["unchecked"])
        self.assertIn("semantic_ownership_wait_and_ending", report["unchecked"])
        return report, {item["code"] for item in report["issues"]}

    def assert_valid(self, text, **kwargs):
        report, codes = self.inspect(text, **kwargs)
        self.assertEqual(codes, set(), report["issues"])
        self.assertEqual(report["deterministic_status"], "passed_checked_scope")
        return report

    def assert_invalid(self, text, code=None, **kwargs):
        report, codes = self.inspect(text, **kwargs)
        self.assertTrue(codes, report)
        self.assertEqual(report["deterministic_status"], "failed")
        if code is not None:
            self.assertIn(code, codes, report["issues"])
        return report

    def test_direct_import_is_cpu_only_in_a_fresh_process(self):
        script = (
            "import sys; sys.path.insert(0, sys.argv[1]); import h3_quality; "
            "assert not any(x == 'torch' or x.startswith('comfy') or "
            "x.startswith('local_qwen') or x == 'requests' for x in sys.modules)"
        )
        subprocess.run([sys.executable, "-B", "-c", script, str(ROOT)], check=True,
                       capture_output=True, text=True, timeout=15)

    def test_quality_and_creation_default_off_and_known_aliases(self):
        for value in (None, "", "off", "none", quality.QUALITY_OFF):
            self.assertEqual(quality.normalize_quality(value), quality.QUALITY_OFF)
        self.assertEqual(quality.normalize_quality("check"), quality.QUALITY_CHECK)
        self.assertEqual(quality.normalize_quality("repair"), quality.QUALITY_REPAIR)
        for value in (None, "", "off", "none", quality.CREATION_OFF):
            self.assertEqual(quality.normalize_creation(value), quality.CREATION_OFF)
        self.assertEqual(quality.normalize_creation("causal"), quality.CREATION_CAUSAL)

    def test_unknown_or_non_string_modes_are_not_silently_off(self):
        for normalize in (quality.normalize_quality, quality.normalize_creation):
            for value in ([], {}, 0, False, True, "future-mode"):
                with self.subTest(function=normalize.__name__, value=value):
                    with self.assertRaises(ValueError):
                        normalize(value)

    def test_all_complete_official_examples_are_valid(self):
        count = 0
        for name in ("base-en.txt", "ref-en.txt"):
            guide = (ROOT / "official_skills/h3-prompt-writing/references" / name).read_text(encoding="utf-8-sig")
            for index, example in enumerate(re.findall(r"```text\n(.*?)\n```", guide, re.S)):
                if not all(part in example for part in ("overall_soundscape:", "non_diegetic_music:", "[Shot 1]")) or "..." in example:
                    continue
                with self.subTest(guide=name, index=index):
                    self.assert_valid(example)
                count += 1
        self.assertGreaterEqual(count, 5)

    def test_valid_modes_use_native_fields_and_exact_alignment(self):
        for mode in ("T2VA", "I2VA", "FL2VA", "L2VA"):
            with self.subTest(mode=mode):
                prefix = quality.alignment_sentence(mode, 8, 1)
                text = (prefix + "\n\n" if prefix else "") + base()
                report = self.assert_valid(text, task_type=mode, duration=8, shot_count=1)
                self.assertEqual(report["mode"], mode)
        self.assert_valid(reference(), task_type="Ref2VA", duration=8, shot_count=1,
                          media_labels=["<Picture 1>"])

    def test_i2va_missing_or_non_first_alignment_is_invalid(self):
        self.assert_invalid(base(), "h3_alignment", task_type="I2VA", duration=8)
        text = base() + "\n\n" + quality.alignment_sentence("I2VA", 8, 1)
        self.assert_invalid(text, "h3_alignment", task_type="I2VA", duration=8)

    def test_fl2va_and_l2va_alignment_checks_actual_last_shot_and_duration(self):
        for mode in ("FL2VA", "L2VA"):
            for seconds, last_shot in ((99, 1), (8, 9)):
                with self.subTest(mode=mode, seconds=seconds, last_shot=last_shot):
                    text = quality.alignment_sentence(mode, seconds, last_shot) + "\n\n" + base()
                    self.assert_invalid(text, "h3_alignment", task_type=mode, duration=8)

    def test_unknown_duration_still_checks_known_last_shot_alignment(self):
        text = quality.alignment_sentence("L2VA", 8, 9) + "\n\n" + base()
        self.assert_invalid(text, "h3_alignment", task_type="L2VA")

    def test_t2va_unexpected_alignment_or_explanation_prefix_is_invalid(self):
        self.assert_invalid(quality.alignment_sentence("I2VA", 8, 1) + "\n\n" + base(),
                            "h3_unexpected_prefix", task_type="T2VA")
        self.assert_invalid("Here is the prompt:\n\n" + base(), "h3_unexpected_prefix", task_type="T2VA")

    def test_hybrid_duplicate_missing_and_empty_schema_fields_are_invalid(self):
        for text in (base().replace("non_diegetic_music: N/A", ""),
                     base().replace("non_diegetic_music: N/A", "non_diegetic_music:"),
                     base() + "\n\nsubject_definitions: Extra mixed mode.",
                     base() + "\n\nnon_diegetic_music: N/A", reference()):
            with self.subTest(text=text):
                self.assert_invalid(text, task_type="T2VA")
        self.assert_invalid(base(), "h3_missing_core_fields", task_type="Ref2VA")

    def test_metadata_and_literals_cannot_supply_missing_first_shot(self):
        self.assert_invalid(base("A woman walks."), "h3_missing_first_shot")
        self.assert_invalid(base('A sign displays the exact text "[Shot 1]".'), "h3_missing_first_shot")
        self.assert_invalid(reference("A woman walks.", retention="<Subject 1> ([Shot 1]): fully_preserved - identity."),
                            "h3_missing_first_shot", task_type="Ref2VA")

    def test_literal_fake_shots_fields_times_and_speakers_are_not_protocol(self):
        words = "retention_analysis:\n[Shot 9] At 00:59.000, （S1）"
        text = base("[Shot 1] " + vocal(words, language="English") +
                    ' A card displays the exact text "[Shot 8] At 00:58.000, <d>[中文] 假标签</d>".' +
                    " [Shot 2] At 00:03.500, the camera cuts to her hand.")
        self.assert_valid(text, task_type="T2VA", duration=8, shot_count=2)
        self.assertEqual([p.name for p in quality.sections(text)], list(quality.BASE_FIELDS))

    def test_invalid_cut_protocol_sequence_order_and_end_boundary(self):
        cases = (
            ("[Shot 1] At 00:00.000, Alice walks.", "h3_shot_timecode"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:03.500，the camera cuts.", "h3_shot_timecode"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:03.500 the camera cuts.", "h3_shot_timecode"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:03.5, the camera cuts.", "h3_shot_timecode"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:63.000, the camera cuts.", "h3_shot_timecode"),
            ("[Shot 1] Alice walks. [Shot 3] At 00:03.500, the camera cuts.", "shot_sequence"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:00.000, the camera cuts.", "non_monotonic_timecodes"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:04.000, a cut. [Shot 3] At 00:03.000, another cut.", "non_monotonic_timecodes"),
            ("[Shot 1] Alice walks. [Shot 2] At 00:08.000, the camera cuts.", "duration_budget"),
        )
        for body, code in cases:
            with self.subTest(code=code, body=body):
                self.assert_invalid(base(body), code, duration=8)
        self.assert_invalid(base(), "shot_count_mismatch", shot_count=2)

    def test_description_language_excludes_long_foreign_dialogue_and_visible_text(self):
        english = ("Alice stands by the station window, checks her watch, grips the folded ticket in her right hand, "
                   "and slowly walks forward toward the waiting train. The camera follows her without cutting "
                   "and keeps the platform geometry stable.")
        chinese = "女人缓缓走到车站窗前，核对手中的车票，再向等候的列车迈步。镜头始终连续跟拍，保持站台布局和人物衣着一致。"
        long_chinese = "我们到了车站以后不要马上上车，请先确认车次与座位，再一起慢慢走过去。" * 3
        long_english = "Please wait until I check the platform and the departure time before we board the train together. " * 3
        english_text = base("[Shot 1] " + english + " " + vocal(long_chinese) +
                            ' A sign displays the exact text "' + long_chinese + '".')
        chinese_text = base("[Shot 1] " + chinese + " " + vocal(long_english, language="English"),
                            sound="车站环境声和布料摩擦声持续，脚步声音与人物运动同步。")
        self.assertEqual(quality.language_status(english_text, "中文"), "mismatch")
        self.assert_invalid(english_text, "h3_descriptive_language", language="中文")
        self.assertEqual(quality.language_status(chinese_text, "中文"), "match")
        self.assertEqual(quality.language_status(chinese_text, "English"), "mismatch")

    def test_short_or_unspecified_language_is_unknown_not_creative_pass(self):
        self.assertEqual(quality.language_status("好。", "中文"), "unknown")
        self.assertEqual(quality.language_status(base(), "AUTO"), "unknown")
        report = self.assert_valid(base())
        self.assertIn("descriptive_language", report["unchecked"])

    def test_ref2va_wrong_language_in_body_is_not_hidden_by_chinese_metadata(self):
        english = ("Alice slowly walks along the narrow platform toward the waiting train while the camera follows "
                   "her from the side and maintains the same spatial relationship to the window and exit door.")
        text = reference("[Shot 1] " + english,
                         definitions="<Subject 1> 是 <Picture 1> 中的女人。" + "穿红色外套，站在车站窗边，人物身份和衣着保持一致。" * 4,
                         summary="[reference generation] " + "女人准备上车，镜头沿着站台观察她的行动。" * 4,
                         retention="<Subject 1>: fully_preserved - " + "人物身份和车站布局保持一致。" * 4,
                         sound="安静的车站环境声。")
        self.assert_invalid(text, "h3_descriptive_language", task_type="Ref2VA", language="中文")

    def test_native_unquoted_and_quoted_dialogue_is_protected_in_actual_event(self):
        correct = base("[Shot 1] " + vocal("让开。"))
        changed = base("[Shot 1] " + vocal("我改主意了。"))
        for source in (correct, "女人说：让开。", "女人说：“让开。”", 'Alice says: "让开。"'):
            with self.subTest(source=source):
                self.assert_valid(correct, source=source)
                self.assert_invalid(changed, "semantic_exact_text_missing", source=source)

    def test_summary_or_retention_containing_old_dialogue_does_not_satisfy_vocal_event(self):
        text = reference("[Shot 1] " + vocal("我改主意了。", entity="<Subject 1>"),
                         summary="[reference generation] The requested exact line was 让开。",
                         retention="<Subject 1>: fully_preserved - supplied words 让开。")
        self.assert_invalid(text, "semantic_exact_text_missing", source="女人说：“让开。”", task_type="Ref2VA")

    def test_native_dialogue_speaker_is_preserved(self):
        source = base("[Shot 1] " + vocal("等我。"))
        self.assert_invalid(base("[Shot 1] " + vocal("等我。", speaker="S2")),
                            "h3_dialogue_source_changed", source=source)

    def test_two_people_cannot_share_one_speaker_and_one_person_cannot_be_renumbered(self):
        definitions = "<Subject 1> is Alice in <Picture 1>.\n<Subject 2> is Bob in <Picture 2>."
        retention = "<Subject 1>: fully_preserved - identity.\n<Subject 2>: fully_preserved - identity."
        shared = reference("[Shot 1] " + vocal("等我。", entity="<Subject 1>") + " " +
                           vocal("不。", entity="<Subject 2>"), definitions=definitions, retention=retention)
        self.assert_invalid(shared, "h3_speaker_identity", task_type="Ref2VA")
        renamed = reference("[Shot 1] " + vocal("等我。", entity="<Subject 1>") + " " +
                            vocal("再见。", entity="<Subject 1>", speaker="S2"))
        self.assert_invalid(renamed, "h3_speaker_identity", task_type="Ref2VA")

    def test_actual_vocal_event_requires_native_speaker_and_english_language_tag(self):
        for body in ("[Shot 1] Alice says: <d>[Chinese] 等我。</d>",
                     "[Shot 1] Alice （S1） says: <d>[Chinese] 等我。</d>",
                     "[Shot 1] Alice (S1) says: <d>[中文] 等我。</d>",
                     "[Shot 1] Alice (S1) says: <d>等我。</d>",
                     "[Shot 1] Alice (S1) says: <d>[Chinese] 等我。"):
            with self.subTest(body=body):
                self.assert_invalid(base(body))

    def test_audio_cue_does_not_invent_human_speaker_but_physical_singer_needs_one(self):
        defs = "<Subject 1> is Alice in <Picture 1>.\n<Audio 1> is a reused complete soundtrack."
        retention = "<Subject 1>: fully_preserved - identity.\n<Audio 1>: fully_copy - soundtrack."
        cue = reference("[Shot 1] When <Audio 1> reaches <d>[English] Wait for me.</d>, <Subject 1> waves without speaking.",
                        definitions=defs, retention=retention)
        self.assert_valid(cue, task_type="Ref2VA")
        physical = reference("[Shot 1] <Subject 1> sings using <Audio 1> as a voice reference: <d>[English] Wait for me.</d>",
                             definitions=defs, retention=retention)
        self.assert_invalid(physical, task_type="Ref2VA")

    def test_intended_duplicate_dialogue_count_and_order_are_preserved(self):
        source = base("[Shot 1] " + vocal("等我。") + " " + vocal("等我。"))
        self.assert_invalid(base("[Shot 1] " + vocal("等我。")), "semantic_exact_text_missing", source=source)
        source = base("[Shot 1] " + vocal("第一句。") + " " + vocal("第二句。"))
        reversed_words = base("[Shot 1] " + vocal("第二句。") + " " + vocal("第一句。"))
        self.assert_invalid(reversed_words, source=source)

    def test_explicit_no_extra_dialogue_does_not_allow_duplicating_supplied_line(self):
        source = "女人说：“等我。”\n不得新增或重复台词。"
        self.assert_invalid(base("[Shot 1] " + vocal("等我。") + " " + vocal("等我。")), source=source)

    def test_cross_cut_native_line_preserves_words_and_speaker(self):
        source = base("[Shot 1] " + vocal("等等，别走。"))
        two_parts = base("[Shot 1] " + vocal("等等，<scenetrans>") +
                         " [Shot 2] At 00:03.500, " + vocal("<scenetrans>别走。"))
        self.assert_valid(two_parts, source=source, duration=8)
        wrong_speaker = two_parts.replace("[Shot 2] At 00:03.500, Alice (S1)", "[Shot 2] At 00:03.500, Alice (S2)")
        self.assert_invalid(wrong_speaker, source=source, duration=8)

    def test_cross_cut_three_parts_preserve_one_original_line(self):
        source = base("[Shot 1] " + vocal("等等，别走，听我说。"))
        three = base("[Shot 1] " + vocal("等等，<scenetrans>") +
                     " [Shot 2] At 00:02.000, " + vocal("<scenetrans>别走，<scenetrans>") +
                     " [Shot 3] At 00:04.000, " + vocal("<scenetrans>听我说。"))
        self.assert_valid(three, source=source, duration=8)

    def test_visible_text_is_protected_in_body_not_summary_or_dialogue(self):
        source = '招牌逐字写着“营业中”。'
        self.assert_valid(base('[Shot 1] A sign displays the exact text "营业中".'), source=source)
        self.assert_invalid(base('[Shot 1] A sign displays the exact text "休息中".'), "h3_visible_text_changed", source=source)
        self.assert_invalid(reference('[Shot 1] <Subject 1> walks past a blank sign.',
                                      summary='[reference generation] The original sign said "营业中".'),
                            "h3_visible_text_changed", source=source, task_type="Ref2VA")
        self.assert_invalid(base("[Shot 1] " + vocal("营业中")), "h3_visible_text_changed", source=source)

    def test_multiple_visible_instances_are_not_silently_deduplicated(self):
        source = '第一块招牌写着“出口”，第二块招牌也写着“出口”。'
        self.assert_invalid(base('[Shot 1] Only one sign displays the exact text "出口".'), source=source)

    def test_escaped_visible_quotes_preserve_same_written_text(self):
        text = base('[Shot 1] A sign displays the exact text "He said \\"Go\\".".')
        self.assert_valid(text, source=text)

    def test_reference_missing_definition_and_new_summary_label_are_invalid(self):
        self.assert_invalid(reference("[Shot 1] <Subject 9> walks."), "h3_undefined_reference", task_type="Ref2VA")
        self.assert_invalid(reference(summary="[reference generation] <Subject 9> walks."),
                            "h3_undefined_reference", task_type="Ref2VA")

    def test_same_identity_may_use_multiple_actual_images_without_extra_picture_retention(self):
        text = reference(definitions="<Subject 1> is Alice, with identity from <Picture 1> and clothing from <Picture 2>.")
        self.assert_valid(text, task_type="Ref2VA", media_labels=["<Picture 1>", "<Picture 2>"])

    def test_actual_asset_set_rejects_invented_visual_or_audio_sources(self):
        text = reference(definitions="<Subject 1> is Alice in <Picture 9>.")
        self.assert_invalid(text, "h3_unavailable_asset", task_type="Ref2VA", media_labels=["<Picture 1>"])
        audio = reference(definitions="<Subject 1> is Alice in <Picture 1>.\n<Audio 1> is the analyzed audio of <Video 1>.",
                          retention="<Subject 1>: fully_preserved - identity.\n<Audio 1>: reference - voice.")
        self.assert_invalid(audio, "h3_unavailable_asset", task_type="Ref2VA", media_labels=["<Picture 1>", "<Video 1>"])
        self.assert_invalid(quality.alignment_sentence("I2VA", 8, 1) + "\n\n" + base(),
                            "h3_unavailable_asset", task_type="I2VA", duration=8, media_labels=[])

    def test_unknown_asset_inventory_is_not_assumed_to_be_empty(self):
        self.assert_valid(reference(), task_type="Ref2VA", media_labels=None)

    def test_retention_marker_classes_and_tracked_rows_are_validated(self):
        self.assert_invalid(reference(retention="<Subject 1>: fully_copy - identity."),
                            "h3_retention_marker", task_type="Ref2VA")
        text = reference(definitions="<Subject 1> is Alice in <Picture 1>.\n<Audio 1> is a voice reference.",
                         retention="<Subject 1>: fully_preserved - identity.\n<Audio 1>: fully_preserved - voice.")
        self.assert_invalid(text, "h3_retention_marker", task_type="Ref2VA")
        for retention in ("<Subject 1>: fully_preserved identity.",
                          "<Picture 1>: fully_preserved - source frame.",
                          "<Subject 9>: fully_preserved - unknown person."):
            with self.subTest(retention=retention):
                self.assert_invalid(reference(retention=retention), task_type="Ref2VA")

    def test_duplicate_explicit_tracked_definitions_are_not_ignored(self):
        text = reference(definitions="<Subject 1> is Alice in <Picture 1>.\n<Subject 1> is Bob in <Picture 2>.")
        self.assert_invalid(text, task_type="Ref2VA")

    def test_full_dialogue_is_not_duplicated_in_soundscape_or_music(self):
        for layer in ("sound", "music"):
            with self.subTest(layer=layer):
                text = base("[Shot 1] " + vocal("等我。"), **{layer: vocal("等我。")})
                self.assert_invalid(text, "h3_vocal_wrong_layer")
                text = base("[Shot 1] " + vocal("等我。"), **{layer: 'The woman says the exact words "等我。".'})
                self.assert_invalid(text, "h3_vocal_wrong_layer")

    def test_normal_physical_sound_overview_is_allowed_across_fields(self):
        self.assert_valid(base("[Shot 1] Alice opens the door with a click and walks with soft footsteps.",
                               sound="A door click and soft footsteps accompany quiet room ambience."))
        self.assert_valid(base("[Shot 1] " + vocal("等我。") + " Paper rustles as Alice raises the letter.",
                               sound="Paper rustle and quiet room ambience."))

    def test_explicit_character_audible_music_cannot_be_the_audience_only_layer(self):
        self.assert_invalid(base("[Shot 1] A radio plays soft piano music audible to Alice.",
                                 music="The same radio piano music is audible to Alice in the room."))
        self.assert_valid(base("[Shot 1] A radio plays soft piano music audible to Alice.",
                               music="A separate audience-only cello score remains inaudible to the characters."))

    def test_group_speech_and_nonhuman_mechanical_scene_do_not_need_invented_people(self):
        self.assert_valid(base('[Shot 1] Two children (S1,S2) shout: <d>[English] Wait!</d>'))
        self.assert_valid(base('[Shot 1] A faceless four-legged robot steps across two stones, then transfers weight to a bridge.',
                               sound='Metal feet click against stone; a motor hum continues.'))

    def test_offscreen_voiceover_uses_closed_lips_without_mutating_words(self):
        text = base('[Shot 1] Alice (S1) says in an off-screen voiceover: <d>[English] I remember.</d> while her lips remain completely closed.')
        self.assert_valid(text, source=text)

    def test_unpaired_cross_cut_tags_do_not_change_original_words(self):
        source = base('[Shot 1] ' + vocal('等等，别走。'))
        text = base('[Shot 1] ' + vocal('等等，<scenetrans>') +
                    ' [Shot 2] At 00:03.500, ' + vocal('别走。'))
        self.assert_invalid(text, source=source, duration=8)

    def test_repair_protocol_is_local_preserves_literals_and_is_idempotent(self):
        body = ('[Shot 1] Alice （S1） says: <d>[Chinese] 请保留（S1）和[Shot 9] At 00:99.000，原文。</d> '
                'A sign displays the exact text "（S2） [Shot 2] At 00:03.500，". '
                '[Shot 2] At 00:03.500，the camera cuts to her hand.')
        text = base(body)
        repaired, changes = quality.repair_protocol(text, task_type="T2VA", duration=8)
        self.assertTrue(changes)
        self.assertIn('Alice (S1) says:', repaired)
        self.assertIn('[Shot 2] At 00:03.500,the camera cuts', repaired)
        self.assertIn('<d>[Chinese] 请保留（S1）和[Shot 9] At 00:99.000，原文。</d>', repaired)
        self.assertIn('"（S2） [Shot 2] At 00:03.500，"', repaired)
        again, changes = quality.repair_protocol(repaired, task_type="T2VA", duration=8)
        self.assertEqual(again, repaired)
        self.assertEqual(changes, [])

    def test_repair_missing_cut_comma_also_handles_shot10(self):
        body = "[Shot 1] Alice walks. " + " ".join(
            f"[Shot {n}] At 00:{n:02d}.000 the camera cuts to another view." for n in range(2, 11)
        )
        repaired, _ = quality.repair_protocol(base(body), task_type="T2VA", duration=15)
        self.assertIn("[Shot 10] At 00:10.000, the camera cuts", repaired)
        self.assert_valid(repaired, duration=15, shot_count=10)

    def test_repair_does_not_change_non_vocal_fullwidth_annotation_or_invent_speaker(self):
        text = base('[Shot 1] The mechanical part is labeled （S1）, and remains still.')
        self.assertEqual(quality.repair_protocol(text), (text, []))
        text = base('[Shot 1] Alice says: <d>[Chinese] 等我。</d>')
        repaired, _ = quality.repair_protocol(text)
        self.assertEqual(repaired, text)
        self.assertNotIn('(S1)', repaired)

    def test_repair_never_rewrites_timestamps_or_brackets_inside_true_visible_text(self):
        text = base('[Shot 1] A sign displays the exact text "[Shot 10] At 00:10.000 （S1）".')
        self.assertEqual(quality.repair_protocol(text, task_type='T2VA', duration=15), (text, []))

    def test_alignment_repair_uses_explicit_parameters_and_never_changes_body(self):
        body = base('[Shot 1] Alice keeps the closed umbrella and gradually opens it.')
        for mode in ("I2VA", "FL2VA", "L2VA"):
            with self.subTest(mode=mode):
                repaired, changes = quality.repair_protocol(body, task_type=mode, duration=8)
                self.assertEqual(repaired, quality.alignment_sentence(mode, 8, 1) + "\n\n" + body)
                self.assertIn("alignment_from_explicit_parameters", changes)
        text = 'User explanation that must not be deleted.\n\n' + body
        self.assertEqual(quality.repair_protocol(text, task_type="I2VA", duration=8), (text, []))
        self.assertEqual(quality.repair_protocol(body, task_type="L2VA", duration=0), (body, []))

    def test_creation_instruction_is_off_empty_and_native_per_platform(self):
        self.assertEqual(quality.creation_instruction("unsupported", quality.CREATION_OFF), "")
        h3 = quality.creation_instruction("h3", "causal")
        sd = quality.creation_instruction("seedance20", "causal")
        self.assertIn("native H3", h3)
        self.assertIn("native Seedance", sd)
        self.assertNotIn("integrated_multimodal_description:", sd)
        self.assertNotIn("<d>", sd)
        self.assertNotIn("At MM:SS.mmm", sd)
        for content in (h3, sd):
            self.assertIn("Do not invent", content)
            self.assertIn("requested ending", content)
            self.assertIn("pending paired validation", content)
            self.assertNotIn("350-500", content)
        with self.assertRaises(ValueError):
            quality.creation_instruction("music", "causal")

    def test_correction_prompt_preserves_original_multimodal_messages_without_mutation(self):
        messages = [{"role": "system", "content": "Native H3 and exact text constraints."},
                    {"role": "user", "content": [{"type": "text", "text": "Wait two seconds. Keep the ticket."},
                                                 {"type": "image_url", "image_url": {"url": "data:image/png;base64,TEST"}}]}]
        before = copy.deepcopy(messages)
        report = quality.check_h3(base(), task_type="I2VA", duration=8)
        repaired = quality.correction_messages(messages, base(), report)
        self.assertEqual(messages, before)
        self.assertEqual(repaired[:2], before)
        self.assertEqual(repaired[-2], {"role": "assistant", "content": base()})
        self.assertIn("ONE BOUNDED", repaired[-1]["content"])
        self.assertIn("h3_alignment", repaired[-1]["content"])

    def test_accept_correction_requires_reduced_issues_without_new_failures(self):
        source = base('[Shot 1] Alice walks.')
        bad = base('[Shot 1] Alice walks. [Shot 2] At 00:03.500，the camera cuts to her hand.')
        good, _ = quality.repair_protocol(bad)
        before = quality.check_h3(bad, duration=8)
        after = quality.check_h3(good, duration=8)
        self.assertTrue(quality.accept_correction(bad, good, before, after))
        self.assertFalse(quality.accept_correction(bad, "", before, after))
        self.assertFalse(quality.accept_correction(bad, bad, before, before))
        worse = good.replace("At 00:03.500,", "At 00:09.500,")
        self.assertFalse(quality.accept_correction(bad, worse, before, quality.check_h3(worse, duration=8)))
        self.assertFalse(quality.accept_correction(source, source, quality.check_h3(source), quality.check_h3(source)))

    def test_accept_correction_preserves_all_original_vocal_and_visible_content(self):
        original = base('[Shot 1] ' + vocal('等我。') + ' A sign displays the exact text "营业中". '
                        '[Shot 2] At 00:03.500，the camera cuts to her hand.')
        correct, _ = quality.repair_protocol(original)
        before = quality.check_h3(original, duration=8)
        self.assertFalse(quality.accept_correction(original, correct.replace("等我。", "再见。"), before,
                                                  quality.check_h3(correct.replace("等我。", "再见。"), duration=8)))
        self.assertFalse(quality.accept_correction(original, correct.replace("营业中", "休息中"), before,
                                                  quality.check_h3(correct.replace("营业中", "休息中"), duration=8)))

    def test_accept_correction_cannot_erase_other_valid_dialogue_to_fix_one_bad_line(self):
        source = base('[Shot 1] ' + vocal('让开。') + ' ' + vocal('等我。', speaker='S2', entity='Bob'))
        original = base('[Shot 1] ' + vocal('我改主意了。') + ' ' + vocal('等我。', speaker='S2', entity='Bob'))
        candidate = base('[Shot 1] ' + vocal('让开。'))
        before = quality.check_h3(original, source=source)
        after = quality.check_h3(candidate, source=source)
        self.assertFalse(quality.accept_correction(original, candidate, before, after))

    def test_accept_correction_requires_preserving_explicit_source_facts(self):
        source = 'LOCK: 红色袖口；车票始终在右手；不得改变物品归属。'
        original = base('[Shot 1] 女人保留红色袖口，车票始终在右手。 '
                        '[Shot 2] At 00:03.500，镜头切到她的手。', sound='车站环境声和脚步摩擦声。')
        candidate, _ = quality.repair_protocol(original)
        candidate = candidate.replace('红色袖口', '蓝色袖口').replace('在右手', '在左手')
        before = quality.check_h3(original, duration=8, source=source)
        after = quality.check_h3(candidate, duration=8, source=source)
        self.assertFalse(quality.accept_correction(original, candidate, before, after))

    def audio_reference(self, body):
        return reference(body,
            definitions='<Subject 1> is Alice in <Picture 1>.\n<Audio 1> is the supplied song.',
            retention='<Subject 1>: fully_preserved - identity.\n<Audio 1>: fully_copy - original song.')

    def test_audio_reuse_official_phrase_is_not_a_separate_human_speaker(self):
        for cue in ('reaches', 'reaches the phrase'):
            with self.subTest(cue=cue):
                body = '[Shot 1] When <Audio 1> ' + cue + ' <d>[English] Keep moving.</d>, <Subject 1> raises a hand.'
                self.assert_valid(self.audio_reference(body), task_type='Ref2VA',
                                  media_labels=['<Audio 1>', '<Picture 1>'])

    def test_audio_cue_exemption_cannot_hide_later_actual_subject_dialogue(self):
        reused = '[Shot 1] When <Audio 1> reaches <d>[English] Keep moving.</d>, <Subject 1> raises a hand.'
        for later in (' <Subject 1> says: <d>[English] Wait here.</d>',
                      ' [Shot 2] At 00:03.000, <Subject 1> says: <d>[English] Wait here.</d>'):
            with self.subTest(later=later[:40]):
                self.assert_invalid(self.audio_reference(reused + later), 'h3_missing_speaker',
                                    task_type='Ref2VA', duration=8, media_labels=['<Audio 1>', '<Picture 1>'])
                numbered = later.replace('<Subject 1> says:', '<Subject 1> (S1) says:')
                self.assert_valid(self.audio_reference(reused + numbered), task_type='Ref2VA',
                                  duration=8, media_labels=['<Audio 1>', '<Picture 1>'])

    def test_subject_mention_is_not_a_definition_but_inline_picture_source_is_valid(self):
        actual = reference('[Shot 1] <Subject 1> walks.',
                           definitions='<Subject 1> is Alice in <Picture 1>.',
                           retention='<Subject 1>: fully_preserved - identity.')
        self.assert_valid(actual, task_type='Ref2VA', media_labels=['<Picture 1>'])
        undefined = reference('[Shot 1] <Subject 2> walks.',
            definitions='<Subject 1> is Alice in <Picture 1>. She is not <Subject 2>.',
            retention='<Subject 1>: fully_preserved - identity.')
        self.assert_invalid(undefined, 'h3_undefined_reference', task_type='Ref2VA', media_labels=['<Picture 1>'])
        properly_defined = reference('[Shot 1] <Subject 2> walks.',
            definitions='<Subject 1> is Alice in <Picture 1>.\n<Subject 2> is the station wall in <Picture 1>.',
            retention='<Subject 1>: fully_preserved - identity.\n<Subject 2>: fully_preserved - wall texture.')
        self.assert_valid(properly_defined, task_type='Ref2VA', media_labels=['<Picture 1>'])

    def test_explicit_non_diegetic_and_negated_audio_are_not_wrong_layer(self):
        for music in ('A non-diegetic orchestral score for the audience only.',
                      'This music is not diegetic and is not audible to the characters.',
                      'A quiet orchestral score for the audience only.'):
            with self.subTest(music=music):
                self.assert_valid(base(music=music))
        for music in ('The on-screen radio plays a soft tune audible to Alice.',
                      'Diegetic radio music that the characters hear in the room.'):
            with self.subTest(music=music):
                self.assert_invalid(base(music=music), 'h3_diegetic_music_layer')

    def test_visible_sign_or_screen_says_is_not_an_actor_utterance(self):
        for source, words in (('The sign says "EXIT".', 'EXIT'),
                              ('The screen says "READY".', 'READY'),
                              ('招牌写着“出口”。', '出口')):
            with self.subTest(source=source):
                self.assertEqual([p.kind for p in quality.protected_text(source)], ['visible'])
                correct = base('[Shot 1] Alice stands beside the sign displaying "' + words + '".')
                self.assert_valid(correct, source=source)
                self.assert_invalid(correct.replace(words, 'CHANGED'), 'h3_visible_text_changed', source=source)
        source = 'Alice says "EXIT".'
        self.assertEqual([p.kind for p in quality.protected_text(source)], ['vocal'])
        self.assert_invalid(base('[Shot 1] The sign displays "EXIT".'), 'semantic_exact_text_missing', source=source)
        self.assert_valid(base('[Shot 1] ' + vocal('EXIT', language='English')), source=source)

    def multilingual_fixtures(self):
        english = ('Alice stands by the station window, checks her watch, grips the folded ticket in her right hand, '
                   'and then carefully shifts her weight forward while the camera follows continuously from the side.')
        chinese = '爱丽丝站在车站窗边查看时间，右手握紧折叠车票，随后保持持有状态向前重心转移，镜头从侧面持续跟随。'
        return english, chinese

    def test_each_base_natural_language_field_is_checked_independently(self):
        english, chinese = self.multilingual_fixtures()
        for field in ('overall_soundscape', 'non_diegetic_music'):
            with self.subTest(field=field):
                opts = {'sound': chinese, 'music': chinese}
                self.assert_valid(base('[Shot 1] ' + chinese, **opts), language='中文')
                opts['sound' if field == 'overall_soundscape' else 'music'] = english
                self.assert_invalid(base('[Shot 1] ' + chinese, **opts), 'h3_descriptive_language', language='中文')

    def test_each_reference_natural_language_field_is_checked_independently(self):
        english, chinese = self.multilingual_fixtures()
        original = dict(definitions='<Subject 1> 是 <Picture 1> 中的爱丽丝，外观与红色袖口保持一致。',
                        summary='[reference generation] <Subject 1> 沿车站窗边向前行走并持续持有车票。',
                        retention='<Subject 1>: fully_preserved - 人物身份、外观与红色袖口保持一致。',
                        sound=chinese, music=chinese)
        for field in ('definitions', 'summary', 'retention', 'sound', 'music'):
            with self.subTest(field=field):
                self.assert_valid(reference('[Shot 1] <Subject 1> ' + chinese, **original),
                                  task_type='Ref2VA', language='中文', media_labels=['<Picture 1>'])
                opts = dict(original)
                opts[field] = ('<Subject 1> in <Picture 1>: ' if field == 'definitions' else
                               '<Subject 1>: fully_preserved - ' if field == 'retention' else '') + english
                self.assert_invalid(reference('[Shot 1] <Subject 1> ' + chinese, **opts), 'h3_descriptive_language',
                                    task_type='Ref2VA', language='中文', media_labels=['<Picture 1>'])

    def test_multifield_language_keeps_protocol_and_foreign_original_words_exempt(self):
        english, chinese = self.multilingual_fixtures()
        body = '[Shot 1] <Subject 1> ' + chinese + ' ' + vocal(english, entity='<Subject 1>', language='English')
        text = reference(body,
            definitions='<Subject 1> 是 <Picture 1> 中的人物，服装和外观保持一致。',
            summary='[reference generation] <Subject 1> 继续在原车站场景中走动并持有车票。',
            retention='<Subject 1>: fully_preserved - 外观、身份和红色袖口保持一致。',
            sound='车站环境声与连续脚步摩擦保持可闻，空间反射自然延续。', music='N/A')
        self.assert_valid(text, task_type='Ref2VA', language='中文', media_labels=['<Picture 1>'])
        # A short/empty-information music field is not evidence of a mismatch.
        self.assert_valid(base('[Shot 1] ' + chinese, sound='房间环境声与脚步摩擦。', music='N/A'), language='中文')

    def test_source_original_language_is_preserved_even_with_description_translation(self):
        english, chinese = self.multilingual_fixtures()
        source = base('[Shot 1] ' + vocal('Wait here.', language='English'))
        old = base('[Shot 1] ' + english + ' ' + vocal('Wait here.', language='English'))
        good = base('[Shot 1] ' + chinese + ' ' + vocal('Wait here.', entity='爱丽丝', language='English'), sound=chinese)
        bad = good.replace('<d>[English]', '<d>[Chinese]')
        before = quality.check_h3(old, language='中文', source=source)
        good_report = self.assert_valid(good, language='中文', source=source)
        self.assertTrue(quality.accept_correction(old, good, before, good_report))
        bad_report = self.assert_invalid(bad, language='中文', source=source)
        self.assertFalse(quality.accept_correction(old, bad, before, bad_report))

    def test_legitimate_missing_speaker_fix_is_locally_allowed(self):
        words = 'Please wait here until I bring the key.'
        source = 'Alice says "' + words + '".'
        old = base('[Shot 1] Alice says: <d>[English] ' + words + '</d>')
        good = old.replace('Alice says:', 'Alice (S1) says:')
        before = self.assert_invalid(old, 'h3_missing_speaker', source=source)
        after = self.assert_valid(good, source=source)
        with self.subTest(candidate='legitimate numbered fix'):
            self.assertTrue(quality.accept_correction(old, good, before, after))
        for changed in (good.replace(words, 'I changed the words.'), good.replace('[English]', '[Chinese]')):
            with self.subTest(changed=changed[-80:]):
                self.assertFalse(quality.accept_correction(old, changed, before, quality.check_h3(changed, source=source)))

    def test_one_missing_speaker_cannot_unlock_other_events_valid_ids_or_languages(self):
        old = base('[Shot 1] ' + vocal('Wait here.', language='English') +
                   ' Bob says: <d>[English] Bring the key.</d>')
        good = old.replace('Bob says:', 'Bob (S2) says:')
        before = self.assert_invalid(old, 'h3_missing_speaker')
        after = self.assert_valid(good)
        with self.subTest(candidate='legitimate missing Bob ID only'):
            self.assertTrue(quality.accept_correction(old, good, before, after))
        for changed in (good.replace('Alice (S1)', 'Alice (S3)'),
                        good.replace('[English] Wait here.', '[Chinese] Wait here.'),
                        good.replace('Wait here.', 'Keep running.')):
            with self.subTest(changed=changed[:130]):
                self.assertFalse(quality.accept_correction(old, changed, before, quality.check_h3(changed)))

    def test_valid_original_vocal_language_is_protected_without_source_contract(self):
        original = base('[Shot 1] ' + vocal('Wait here.', language='English') +
                        ' [Shot 2] At 00:03.000，Alice walks toward the door.')
        corrected, _ = quality.repair_protocol(original)
        before = self.assert_invalid(original, 'h3_shot_timecode', duration=8)
        after = self.assert_valid(corrected, duration=8)
        self.assertTrue(quality.accept_correction(original, corrected, before, after))
        changed_language = corrected.replace('<d>[English]', '<d>[Chinese]')
        self.assertFalse(quality.accept_correction(original, changed_language, before,
                                                  quality.check_h3(changed_language, duration=8)))

    def test_unknown_english_language_name_is_preserved_and_marked_for_confirmation(self):
        for language in ('Swedish', 'Scottish Gaelic', 'Swedish'):
            with self.subTest(language=language):
                text = base('[Shot 1] ' + vocal('Vänta här tills jag kommer tillbaka.', language=language))
                report = self.assert_valid(text, source=text)
                self.assertIn('vocal_language', report['unchecked'])
                self.assertEqual(quality.repair_protocol(text), (text, []))
        for language in ('中文', '日本語'):
            with self.subTest(language=language):
                self.assert_invalid(base('[Shot 1] ' + vocal('等我。', language=language)), 'h3_vocal_language')

    def test_natural_no_extra_or_repeated_dialogue_wording_checks_actual_counter(self):
        first, second = vocal('Wait here.', language='English'), vocal('Bring the key.', speaker='S2', entity='Bob', language='English')
        correct = base('[Shot 1] ' + first + ' ' + second)
        for prohibition in ('只有这两句，不新增重复或翻译。', '不增加或重复台词。'):
            source = correct + '\n' + prohibition
            with self.subTest(prohibition=prohibition, variant='correct'):
                self.assert_valid(correct, source=source)
            for suffix in (first, vocal('Keep running.', language='English')):
                with self.subTest(prohibition=prohibition, variant=suffix):
                    self.assert_invalid(base('[Shot 1] ' + first + ' ' + second + ' ' + suffix),
                                        'h3_extra_dialogue', source=source)
        # Without a prohibition, a valid repeated line is not silently removed
        # or reported extra merely because it was not in the source once more.
        self.assert_valid(base('[Shot 1] ' + first + ' ' + second + ' ' + first), source=correct)

    def test_native_source_known_language_alias_is_safely_normalized_not_translated(self):
        source = base('[Shot 1] ' + vocal('等我。', language='中文'))
        proper = source.replace('[中文]', '[Chinese]')
        before = self.assert_invalid(source, 'h3_vocal_language', source=source)
        with self.subTest(candidate='static Chinese-language label alias only'):
            after = self.assert_valid(proper, source=source)
            self.assertTrue(quality.accept_correction(source, proper, before, after))
        for candidate in (proper.replace('[Chinese]', '[English]'),
                          proper.replace('等我。', 'Wait for me.'),
                          proper.replace('(S1)', '(S2)')):
            with self.subTest(candidate=candidate[:100]):
                self.assertFalse(quality.accept_correction(source, candidate, before,
                                                          quality.check_h3(candidate, source=source)))
        unknown = base('[Shot 1] ' + vocal('等我。', language='未知语言'))
        guessed = unknown.replace('[未知语言]', '[English]')
        for contract in (unknown, ''):
            with self.subTest(candidate='unknown non-English label is not permission to guess', source=bool(contract)):
                report = self.assert_invalid(unknown, 'h3_vocal_language', source=contract)
                self.assertFalse(quality.accept_correction(unknown, guessed, report,
                                                          quality.check_h3(guessed, source=contract)))

    def test_audio_used_as_source_requires_independent_definition_and_retention(self):
        visible = '<Subject 1> is Alice in <Picture 1>, whose walking motion comes from <Video 1>.'
        keep_visible = '<Subject 1>: fully_preserved - identity and walking motion.'
        available = ['<Picture 1>', '<Video 1>', '<Audio 1>']
        with self.subTest(variant='Picture and Video pure provenance may stay inline'):
            self.assert_valid(reference('[Shot 1] <Subject 1> walks.', definitions=visible, retention=keep_visible),
                              task_type='Ref2VA', media_labels=available[:2])
        voice_body = '[Shot 1] <Subject 1> (S1) follows <Audio 1>\'s voice timbre and says: <d>[English] Wait here.</d>'
        with self.subTest(variant='Audio voice source cannot be merely mentioned inside Subject definition'):
            self.assert_invalid(reference(voice_body, definitions=visible + ' Her voice comes from <Audio 1>.',
                                          retention=keep_visible), task_type='Ref2VA', media_labels=available)
        defined = visible + '\n<Audio 1> is the voice-timbre reference for <Subject 1> (S1).'
        with self.subTest(variant='standalone Audio still needs its retention row'):
            self.assert_invalid(reference(voice_body, definitions=defined, retention=keep_visible),
                                'h3_retention_missing', task_type='Ref2VA', media_labels=available)
        with self.subTest(variant='complete Audio definition and reference retention are valid'):
            self.assert_valid(reference(voice_body, definitions=defined,
                                        retention=keep_visible + '\n<Audio 1>: reference - the same voice timbre, not a copied signal.'),
                              task_type='Ref2VA', media_labels=available)

    def test_seedance_wrong_quote_can_restore_source_but_not_erase_correct_words(self):
        source = 'Alice says: "Hello." Bob says: "Wait."'
        original = 'Alice says: "Bye." Bob says: "Wait."'
        candidate = 'Alice says: "Hello." Bob says: "Wait."'
        before = quality.check_seedance(original, source=source)
        after = quality.check_seedance(candidate, source=source)
        self.assertTrue(quality.accept_correction(original, candidate, before, after))
        result, metrics = quality.run_quality(original, mode='repair', messages=[],
            check=lambda text: quality.check_seedance(text, source=source), complete=lambda messages: candidate)
        self.assertEqual(result, candidate)
        self.assertEqual(metrics['correction_calls'], 1)
        for bad in ('Alice says: "Hello."', candidate + ' Bob says: "New words."'):
            self.assertFalse(quality.accept_correction(original, bad, before,
                quality.check_seedance(bad, source=source)))

    def test_static_language_alias_fix_is_per_event_and_preserves_other_original_bindings(self):
        aliases = [('中文', 'Chinese'), ('汉语', 'Chinese'), ('普通话', 'Chinese'),
                   ('日本語', 'Japanese'), ('한국어', 'Korean'), ('粤语', 'Cantonese')]
        for native, canonical in aliases:
            source = base('[Shot 1] ' + vocal('Original words.', language=native) + ' ' +
                          vocal('Keep this voice.', language='Swedish', speaker='S2', entity='Bob'))
            candidate = source.replace('[' + native + ']', '[' + canonical + ']')
            for authority in (source, ''):
                with self.subTest(alias=native, source=bool(authority)):
                    before = self.assert_invalid(source, 'h3_vocal_language', source=authority)
                    after = self.assert_valid(candidate, source=authority)
                    self.assertIn('vocal_language', after['unchecked'])
                    self.assertTrue(quality.accept_correction(source, candidate, before, after))
                    for bad in (candidate.replace('[Swedish]', '[English]'),
                                candidate.replace('Bob (S2)', 'Bob (S3)'),
                                candidate.replace('Keep this voice.', 'Different words.')):
                        self.assertFalse(quality.accept_correction(source, bad, before,
                            quality.check_h3(bad, source=authority)))

    def test_audio_voice_provenance_needs_tracking_even_without_body_audio_label(self):
        source = '<Subject 1> is Alice in <Picture 1>, whose voice timbre comes from <Audio 1>.'
        retention = '<Subject 1>: fully_preserved - appearance and voice identity.'
        self.assert_invalid(reference('[Shot 1] <Subject 1> walks silently.', definitions=source,
                                      retention=retention), 'h3_undefined_reference',
                            task_type='Ref2VA', media_labels=['<Picture 1>', '<Audio 1>'])
        complete = source + '\n<Audio 1> is the voice-timbre reference for <Subject 1> (S1).'
        proper = reference('[Shot 1] <Subject 1> walks silently.', definitions=complete,
                           retention=retention + '\n<Audio 1>: weak_reference - voice-timbre guidance.')
        self.assert_valid(proper, task_type='Ref2VA', media_labels=['<Picture 1>', '<Audio 1>'])
        self.assert_invalid(proper, 'h3_unavailable_asset', task_type='Ref2VA', media_labels=['<Picture 1>'])

    def test_seedance_quote_restoration_cannot_duplicate_existing_or_restored_source_words(self):
        source = 'Alice says: "Hello." Bob says: "Wait."'
        original = 'Alice says: "Bye." Bob says: "Wait."'
        correct = 'Alice says: "Hello." Bob says: "Wait."'
        before = quality.check_seedance(original, source=source)
        self.assertTrue(quality.accept_correction(original, correct, before,
                                                quality.check_seedance(correct, source=source)))
        for extra in (' Bob says: "Wait."', ' Alice says: "Hello."', ' Alice says: "New words."'):
            with self.subTest(extra=extra):
                candidate = correct + extra
                self.assertFalse(quality.accept_correction(original, candidate, before,
                    quality.check_seedance(candidate, source=source)))
        # A repeated source line is not an invented extra: use source counts,
        # not a global ban on every duplicate utterance.
        repeated_source = source + ' Bob says: "Wait."'
        repeated_candidate = correct + ' Bob says: "Wait."'
        repeated_before = quality.check_seedance(original, source=repeated_source)
        self.assertTrue(quality.accept_correction(original, repeated_candidate, repeated_before,
            quality.check_seedance(repeated_candidate, source=repeated_source)))

    def test_partial_source_repair_cannot_erase_other_valid_speech_with_same_remaining_code(self):
        source = base('[Shot 1] ' + vocal('让开。') + ' ' + vocal('等我。', speaker='S2', entity='Bob'))
        original = base('[Shot 1] ' + vocal('错词。') + ' ' + vocal('等我。', speaker='S2', entity='Bob') +
                        ' [Shot 2] At 00:03.000，Alice walks.')
        candidate = base('[Shot 1] ' + vocal('让开。') + ' [Shot 2] At 00:03.000, Alice walks.')
        before = quality.check_h3(original, duration=8, source=source)
        after = quality.check_h3(candidate, duration=8, source=source)
        self.assertLess(len(after['issues']), len(before['issues']))
        self.assertFalse(quality.accept_correction(original, candidate, before, after))
        full = base('[Shot 1] ' + vocal('让开。') + ' ' + vocal('等我。', speaker='S2', entity='Bob') +
                    ' [Shot 2] At 00:03.000, Alice walks.')
        self.assertTrue(quality.accept_correction(original, full, before, quality.check_h3(full, duration=8, source=source)))

    def test_native_source_subject_binding_and_language_multiplicity_remain_exact(self):
        source = reference('[Shot 1] ' + vocal('Wait.', entity='<Subject 1>', language='English'),
            definitions='<Subject 1> is Alice in <Picture 1>.\n<Subject 2> is Bob in <Picture 1>.',
            retention='<Subject 1>: fully_preserved - identity.\n<Subject 2>: fully_preserved - identity.')
        bad = source.replace('<Subject 1> (S1)', '<Subject 2> (S1)')
        self.assert_invalid(bad, 'h3_dialogue_source_changed', source=source, task_type='Ref2VA')
        twice = base('[Shot 1] ' + vocal('Wait.', language='English') + ' ' + vocal('Wait.', language='English'))
        changed = twice.replace('<d>[English]', '<d>[Chinese]', 1)
        self.assert_invalid(changed, 'h3_dialogue_source_changed', source=twice)


if __name__ == "__main__":
    unittest.main()
