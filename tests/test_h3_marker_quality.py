"""Regression: spatial records are independent evidence, not a speech timeline."""
import importlib
import unittest
from unittest.mock import Mock
from test_h3_visual_marker import h3, vm, config, media, material, change_record
from test_h3_quality import reference
from test_nodes import FakeSession

q = importlib.import_module(h3.__package__ + ".h3_quality")
pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
speech = importlib.import_module(h3.__package__ + ".speech_reference")
output = importlib.import_module(h3.__package__ + ".speech_output")


def plan_for(*actions):
    plan = material()
    change_record(plan, lambda r: r["spec"].update(relations=[
        dict(actor_marker_id="actor_A", target_marker_id="target_A", action=action) for action in actions]))
    return plan


def contract_for(*actions):
    plan = plan_for(*actions)
    _, evidence = vm.bind_visual_marker(config(plan), media(plan), "Ref2VA")
    return vm.visual_marker_literal_contract(evidence)


def spoken(*words, tail=""):
    return reference("[Shot 1] <Subject 1> walks through the doorway. " + " ".join(
        "<Subject 1> (S1) says: <d>[English] " + word + "</d>" for word in words) + " " + tail)


class MarkerQualityRegressionTests(unittest.TestCase):
    def check(self, draft, contract, *, source="", mode="check", complete=None):
        return pipeline.h3_quality_result(draft, mode=mode, messages=[],
            complete=complete or Mock(side_effect=AssertionError("Unexpected model correction")),
            task_type="Ref2VA", duration=8, shot_count=1, language="English", source=source,
            media_labels=["<Picture 1>"], extra_contract=contract)

    def test_duplicate_edges_and_main_declaration_do_not_multiply_speech(self):
        contract = contract_for('She says “Wait for me.” once.', 'She says “Wait for me.” once.')
        self.assertEqual(len(contract.literals), 1)
        draft = spoken("Wait for me.")
        result, metrics = self.check(draft, contract, source='She says “Wait for me.” once.')
        self.assertEqual(result, draft)
        self.assertNotIn("semantic_exact_text_missing", metrics["issue_codes"])
        self.assertNotIn("h3_marker_literal_missing", metrics["issue_codes"])
        self.assertEqual(metrics["correction_calls"], 0)
        recovery = importlib.import_module(h3.__package__ + ".completion_recovery")
        self.assertEqual(recovery.safe_quality_metadata({"result":"checked","issue_codes":["h3_marker_literal_missing","PRIVATE"]})["issue_codes"],["h3_marker_literal_missing"])

    def test_main_user_repeat_count_remains_authoritative(self):
        contract = contract_for('She says “Wait.” once.')
        source = 'She says “Wait.”. She says “Wait.” again.'
        _, metrics = self.check(spoken("Wait."), contract, source=source)
        self.assertIn("semantic_exact_text_missing", metrics["issue_codes"])
        _, metrics = self.check(spoken("Wait.", "Wait."), contract, source=source)
        self.assertNotIn("semantic_exact_text_missing", metrics["issue_codes"])

    def test_relation_order_is_not_a_dialogue_timeline(self):
        contract = contract_for('She says “First.”.', 'She says “Second.”.')
        _, metrics = self.check(spoken("Second.", "First."), contract)
        self.assertNotIn("semantic_exact_text_missing", metrics["issue_codes"])
        self.assertNotIn("h3_marker_literal_missing", metrics["issue_codes"])
        _, metrics = self.check(spoken("Second.", "First."), contract,
            source='She says “First.” then says “Second.”.')
        self.assertIn("semantic_exact_text_missing", metrics["issue_codes"])

    def test_fields_do_not_inherit_each_others_quote_kind(self):
        contract = contract_for('She says “Wait.”.', 'The sign reads “EXIT”.')
        self.assertEqual([p.kind for p in contract.literals], ["vocal", "visible"])
        self.assertEqual(contract.issue_codes(spoken("Wait.", tail='The sign reads "EXIT".')), [])
        self.assertEqual(contract.issue_codes(spoken("Wait.", "EXIT")), ["h3_marker_literal_missing"])

    def test_existing_satisfied_literals_cannot_be_swapped_during_repair(self):
        contract = contract_for('She says “A.”.', 'She says “B.”.', 'She says “C.”.')
        before, after = spoken("A."), spoken("B.")
        self.assertFalse(contract.accept_monotonic(before, after))
        self.assertTrue(contract.accept_monotonic(before, spoken("A.", "B.")))
        # A candidate that fixes another issue but drops A must retain the draft.
        wrong = before.replace("overall_soundscape:", "unavailable_soundscape:")
        complete = Mock(return_value=after)
        result, metrics = self.check(wrong, contract, mode="repair", complete=complete)
        self.assertEqual(result, wrong)
        self.assertEqual(metrics["result"], "candidate_rejected")
        self.assertEqual(complete.call_count, 1)

    def test_cloud_call_has_one_generation_for_duplicate_evidence(self):
        plan = plan_for('She says “Wait.” once.', 'She says “Wait.” once.')
        events = []
        session = FakeSession(spoken("Wait."))
        h3.enhance_prompt(prompt='She says “Wait.” once.', task_type="Ref2VA", output_language="English",
            reference_images={"reference_image_0":plan.marked_image}, visual_marker_config=config(plan),
            quality_mode="质量纠正（最多追加1次） / Repair", session=session, api_key="test-placeholder",
            progress_callback=lambda stage, **metrics: events.append(metrics))
        self.assertEqual(len(session.chat_requests), 1)
        self.assertNotIn("semantic_exact_text_missing", str(events))

    def test_marker_is_not_permission_to_voice_reference_transcript(self):
        contract = contract_for('She says “Wait.”.')
        ref = speech.provided_reference("Wait.", purpose="reference")
        errors = output._check(spoken("Wait."), ref, target="h3", language="English", original_prompt="Walk quietly.",
            relay_config=None, task_type="Ref2VA", duration=8, shot_count=1)
        self.assertIn("speech_reference_copied", errors)
        self.assertEqual(contract.issue_codes(spoken("Wait.")), [])

    def test_marker_only_missing_words_can_be_repaired_once(self):
        for action, candidate in [('She says “Wait.”.', spoken("Wait.")),
                ('The sign reads “EXIT”.', spoken(tail='The sign reads "EXIT".'))]:
            with self.subTest(action=action):
                contract = contract_for(action)
                complete = Mock(return_value=candidate)
                result, metrics = self.check(spoken(), contract, mode="repair", complete=complete)
                self.assertEqual(result, candidate)
                self.assertEqual(metrics["result"], "corrected")
                self.assertEqual(complete.call_count, 1)

    def test_marker_repair_cannot_add_extra_repetitions_or_replace_a_known_voice(self):
        contract = contract_for('She says “Wait.”.')
        for original, candidate in [(spoken(), spoken("Wait.", "Wait.")),
                (spoken("Existing."), spoken("Wait.")),
                (spoken("Wait.").replace("(S1)", "(S2)"), spoken("Wait."))]:
            if "S2" in original:
                contract = contract_for('<Subject 1> (S1) says: <d>[English] Wait.</d>')
            complete = Mock(return_value=candidate)
            result, metrics = self.check(original, contract, mode="repair", complete=complete)
            self.assertEqual(result, original)
            self.assertEqual(metrics["correction_calls"], 1)

    def test_plain_field_text_never_uses_h3_field_headers_as_boundaries(self):
        contract = contract_for('She says “Wait.”.\noverall_soundscape: quiet\nsummary: a door')
        self.assertEqual([p.text for p in contract.literals], ["Wait."])

    def test_explicit_negative_examples_do_not_become_required_output(self):
        for action in ['She must not say “Wait.”; walk silently.', 'Do not add dialogue: “No.”',
                       'Do not add any new dialogue "Wait.".', 'She mustn\'t say "Wait.".',
                       'She shouldn\'t sing "Wait.".', 'She won\'t say "Wait.".',
                       'Do not show or display text "EXIT".', 'Never say or sing "Wait.".',
                       '不要说或唱“等我”。',
                       '不得新增台词“等我”。', '她不再说“回来”。', '禁止说：<d>[Chinese] 等我。</d>',
                       '不得显示“EXIT”。', 'Do not show the text “EXIT”.', '屏幕不再出现“ERROR”。']:
            self.assertEqual(contract_for(action).literals, (), action)
        for action in ['She says “Do not go.”.', '她说“别走”。', '不要改变她说的“别走”。',
                       'Do not change the words she says: “Don\'t go.”', '不得删除文字“EXIT”。',
                       'Do not change visible text “EXIT”.', '不要去掉招牌上的“STOP”。']:
            self.assertEqual(len(contract_for(action).literals), 1, action)
        contract = contract_for('She must not say “A.”; then she says “B.”', '不要显示“OLD”，改为显示“NEW”。')
        self.assertEqual([p.text for p in contract.literals], ["B.", "NEW"])
        for action, word in [('Do not say "A". Keep the caption "EXIT".', "EXIT"),
                             ('Do not show "OLD", but display text "NEW".', "NEW"),
                             ('Do not show the text "OLD". Keep the title "NEW".', "NEW"),
                             ('Do not say <d invalid>[English] Bad.</d>; she (S1) says <d>[English] Wait.</d>', "Wait.")]:
            self.assertEqual([p.text for p in contract_for(action).literals], [word], action)

    def test_continued_native_speech_is_one_literal_and_can_be_restored(self):
        action = 'Alice (S1) says: <d>[English] Hello <scenetrans></d> Alice (S1) says: <d>[English] <scenetrans>world.</d>'
        contract = contract_for(action)
        self.assertEqual([p.text for p in contract.literals], ["Hello world."])
        candidate = reference("[Shot 1] " + action)
        complete = Mock(return_value=candidate)
        result, metrics = self.check(spoken(), contract, mode="repair", complete=complete)
        self.assertEqual(result, candidate)
        self.assertEqual(metrics["result"], "corrected")

    def test_speech_repair_cannot_drop_marker_visible_words(self):
        contract = contract_for('The sign reads “EXIT”.')
        ref = speech.provided_reference("Wait.", purpose="keep_dialogue", speaker_map={"default":"S1"})
        initial = spoken(tail='The sign reads "EXIT".')
        complete = Mock(return_value=spoken("Wait."))
        with self.assertRaisesRegex(output.SpeechOutputError, "h3_marker_literal_missing"):
            output.finish_speech_output(initial, ref, target="h3", language="English", original_prompt="Walk quietly.",
                messages=[], complete=complete, task_type="Ref2VA", duration=8, shot_count=1, extra_contract=contract)
        self.assertEqual(complete.call_count, 1)

    def test_keep_dialogue_two_cues_still_require_two_utterances(self):
        contract = contract_for('She says “Wait.”.', 'She says “Wait.”.')
        raw = '{"contract_version":1,"timeline":"input","status":"complete","cues":[' \
            '{"id":"a","start_s":0,"end_s":1,"text":"Wait.","language":"English","speaker":null,"timing_method":"vad_segment"},' \
            '{"id":"b","start_s":2,"end_s":3,"text":"Wait.","language":"English","speaker":null,"timing_method":"vad_segment"}]}'
        ref = speech.provided_reference(raw, purpose="keep_dialogue", speaker_map={"default":"S1"})
        complete = Mock(return_value=spoken("Wait.", "Wait."))
        result = output.finish_speech_output(spoken("Wait."), ref, target="h3", language="English", original_prompt="Walk quietly.",
            messages=[], complete=complete, task_type="Ref2VA", duration=8, shot_count=1, extra_contract=contract)
        self.assertEqual(result, spoken("Wait.", "Wait."))
        self.assertEqual(complete.call_count, 1)
