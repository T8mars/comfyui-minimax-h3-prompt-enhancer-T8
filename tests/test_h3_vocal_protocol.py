"""Production-response replay plus adversarial CPU vocal-format contracts."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import h3_quality as q
import h3_vocal_protocol as protocol
import quality_pipeline as pipeline
from h3_prompt_relay import compile_relay_response
from test_h3_quality import base, reference


def payloads(text):
    # Normalize only the language HEADER for comparison; actual words, quotes,
    # continuations, whitespace and punctuation remain exactly unchanged.
    return [protocol.VOCAL.fullmatch(m.group()).group("words") if protocol.VOCAL.fullmatch(m.group())
            else m.group() for m in q.LITERAL_RE.finditer(q.body_for(text))]


class VocalProtocolTests(unittest.TestCase):
    def normalize(self, text, **kwargs):
        fixed, changes, unresolved = protocol.normalize_h3_vocals(text, **kwargs)
        self.assertEqual(payloads(text), payloads(fixed))
        self.assertEqual(protocol.normalize_h3_vocals(fixed, **kwargs)[0], fixed)
        return fixed, changes, unresolved

    def test_fullwidth_and_explicit_language_alias_not_literal_contents(self):
        draft = base('[Shot 1] Alice （S1） says: <d>[中文] Keep （S2） and [中文] exactly.</d> A card reads "（S3）".')
        fixed, changes, unresolved = self.normalize(draft)
        self.assertIn('Alice (S1) says: <d>[Chinese]', fixed)
        self.assertIn('Keep （S2） and [中文] exactly.</d>', fixed)
        self.assertIn('reads "（S3）"', fixed)
        self.assertEqual(changes, ['vocal_id_punctuation', 'vocal_language_alias'])
        self.assertFalse(unresolved)

    def test_one_unnumbered_actual_vocal_can_receive_s1(self):
        text = base('[Shot 1] 成年女人低声说：<d>[Chinese] 等我。</d> 她看向门口。')
        fixed, changes, unresolved = self.normalize(text, source='成年女人独自说“等我。”一次。')
        self.assertIn('(S1) <d>[Chinese] 等我。</d>', fixed)
        self.assertEqual(changes, ['vocal_id_binding'])
        self.assertFalse(unresolved)

    def test_existing_source_id_is_not_renumbered(self):
        for annotation in ('(S7)', '（S7）'):
            source = base('[Shot 1] Alice ' + annotation + ' says: <d>[English] Wait.</d>')
            fixed, _, unresolved = self.normalize(base('[Shot 1] Alice says: <d>[English] Wait.</d>'), source=source)
            self.assertIn('Alice (S7) says:', fixed)
            self.assertFalse(unresolved)

    def test_missing_ids_reuse_later_explicit_binding_across_cuts(self):
        text = base('[Shot 1] Alice says: <d>[English] Wait.</d> [Shot 2] At 00:03.000, Alice (S7) says: <d>[English] Go.</d>')
        fixed, _, unresolved = self.normalize(text)
        self.assertEqual([e.speaker for e in q.vocal_events(q.body_for(fixed))], ['S7', 'S7'])
        self.assertFalse(unresolved)

    def test_same_name_different_lines_stays_stable(self):
        text = base('[Shot 1] Alice says: <d>[English] Wait.</d> Bob replies: <d>[English] No.</d> Alice says: <d>[English] Fine.</d>')
        fixed, _, unresolved = self.normalize(text)
        self.assertEqual([(e.entity, e.speaker) for e in q.vocal_events(q.body_for(fixed))], [('Alice', 'S1'), ('Bob', 'S2'), ('Alice', 'S1')])
        self.assertFalse(unresolved)

    def test_explicit_input_line_binding_not_nearest_listener(self):
        text = base('[Shot 1] Alice looks at Bob, then whispers: <d>[English] Wait.</d> Bob looks at Alice and says: <d>[English] No.</d>')
        source = 'Alice says "Wait.". Bob says "No.".'
        fixed, _, unresolved = self.normalize(text, source=source)
        self.assertEqual([e.speaker for e in q.vocal_events(q.body_for(fixed))], ['S1', 'S2'])
        self.assertFalse(unresolved)

    def test_repeated_words_with_two_input_owners_are_not_guessed(self):
        text = base('[Shot 1] 她说：<d>[English] Wait.</d> 他回答：<d>[English] Wait.</d>')
        fixed, changes, unresolved = self.normalize(text, source='Alice says "Wait.". Bob says "Wait.".')
        self.assertEqual(fixed, text)
        self.assertFalse(changes)
        self.assertEqual(unresolved, ['h3_missing_speaker'])

    def test_multiple_unnamed_voices_or_conflicting_name_ids_are_not_collapsed(self):
        for text in (base('[Shot 1] 她说：<d>[Chinese] 等我。</d> 他回答：<d>[Chinese] 好。</d>'),
                     base('[Shot 1] Alice (S1) says: <d>[English] One.</d> Alice (S2) says: <d>[English] Two.</d> Alice says: <d>[English] Three.</d>')):
            fixed, changes, unresolved = self.normalize(text)
            self.assertEqual(fixed, text)
            self.assertFalse(changes)
            self.assertEqual(unresolved, ['h3_missing_speaker'])

    def test_source_ownership_conflict_is_not_hidden_with_a_new_id(self):
        text = base('[Shot 1] Bob says: <d>[English] Wait.</d>')
        self.assertEqual(self.normalize(text, source='Alice says "Wait.".'), (text, [], ['h3_missing_speaker']))

    def test_pronouns_are_not_assumed_to_name_distinct_stable_speakers(self):
        text = base('[Shot 1] She says: <d>[English] Wait.</d> He replies: <d>[English] No.</d>')
        self.assertEqual(self.normalize(text), (text, [], ['h3_missing_speaker']))

    def test_one_utterance_by_a_group_does_not_invent_a_single_speaker(self):
        for clause in ('Alice and Bob sing together:', 'The two children sing:', '两个人齐声说：'):
            text = base('[Shot 1] ' + clause + '<d>[English] Wait.</d>')
            self.assertEqual(self.normalize(text), (text, [], ['h3_missing_speaker']))

    def test_live_api_evidence_has_three_outputs_one_call_each_and_real_raw_fix(self):
        path = ROOT / 'tests/fixtures/h3_vocal_protocol_api_2026-10-04.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), 'd785f9acf6b0cf61e9d7372a713ff1e5826888c01074e5a6604c74534574ed4f')
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(data['tests']), 3)
        self.assertEqual(data['settings']['quality'], 'off')
        modified = 0
        for test in data['tests']:
            case = next(c for c in data['cases'] if c['id'] == test['case_id'])
            self.assertEqual((test['outcome'], test['logical_calls']), ('success', 1))
            self.assertEqual(test['contract_check']['issues'], [])
            request = test['requests'][0]
            self.assertEqual(request['model_id'], 'bytedance/doubao-seed-evolving')
            self.assertEqual([h['status'] for h in request['http_attempts']], [200])
            raw, final = request['output'], test['output']
            if case['target'] == 'relay':
                before, after = json.loads(raw), json.loads(final)
                self.assertEqual(before['events'], after['events'])
                self.assertEqual(before['global_prompt'], after['global_prompt'])
                raw, final = before['native_prompt'], after['native_prompt']
            fixed, edits, unresolved = self.normalize(raw, source=case['prompt'])
            self.assertEqual(final, fixed)
            self.assertFalse(unresolved)
            modified += bool(edits)
        self.assertEqual(modified, 1, 'One genuine returned fullwidth ID was locally corrected')

    def test_final_code_live_evidence_and_hashes_are_not_prototype_claims(self):
        path = ROOT / 'tests/fixtures/h3_vocal_protocol_final_api_2026-10-04.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), 'b6bbaab47f016ef35f6d71c62b435dbb2c33f643a5b9c5439fcfd299994e4673')
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(data['tests']), 2)
        for name in ('h3_vocal_protocol.py', 'quality_pipeline.py'):
            actual = hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            self.assertEqual(actual, data['settings']['code_sha256'][name])
            self.assertEqual(actual, data['post_run_output_code_sha256'][name])
        modified = 0
        for test in data['tests']:
            self.assertEqual((test['outcome'], test['logical_calls']), ('success', 1))
            self.assertFalse(test['contract_check']['issues'])
            request = test['requests'][0]
            self.assertEqual(request['model_id'], 'bytedance/doubao-seed-evolving')
            self.assertEqual([h['status'] for h in request['http_attempts']], [200])
            case = next(c for c in data['cases'] if c['id'] == test['case_id'])
            fixed, edits, unresolved = self.normalize(request['output'], source=case['prompt'])
            self.assertEqual(fixed, test['output'])
            self.assertFalse(unresolved)
            modified += bool(edits)
        self.assertEqual(modified, 1)

    def test_subject_number_is_not_speaker_order(self):
        text = reference('[Shot 1] <Subject 2> says: <d>[English] Wait.</d> <Subject 1> says: <d>[English] No.</d>',
                         definitions='<Subject 1> is Alice in <Picture 1>.\n<Subject 2> is Bob in <Picture 2>.',
                         retention='<Subject 1>: fully_preserved - identity.\n<Subject 2>: fully_preserved - identity.')
        fixed, _, unresolved = self.normalize(text)
        self.assertEqual([(e.entity, e.speaker) for e in q.vocal_events(q.body_for(fixed))], [('Subject 2', 'S1'), ('Subject 1', 'S2')])
        self.assertFalse(unresolved)
        self.assertEqual(q.sections(fixed)[0].value, q.sections(text)[0].value)
        self.assertEqual(q.sections(fixed)[2].value, q.sections(text)[2].value)

    def test_compound_speakers_and_cross_cut_words_preserved(self):
        text = base('[Shot 1] Alice and Bob （S1，S2） sing: <d>[English] Wait,<scenetrans></d> [Shot 2] At 00:04.000, Alice and Bob （S1，S2） sing: <d>[English] <scenetrans>for us.<cutoff></d>')
        fixed, _, unresolved = self.normalize(text)
        self.assertEqual([e.speaker for e in q.vocal_events(q.body_for(fixed))], ['S1,S2', 'S1,S2'])
        self.assertFalse(unresolved)

    def test_audio_only_lyrics_never_get_an_invented_speaker(self):
        text = reference('[Shot 1] When <Audio 1> reaches the phrase <d>[English] Wait.</d>, <Subject 1> waves without speaking.',
                         definitions='<Subject 1> is Alice in <Picture 1>.\n<Audio 1> is the reused soundtrack.',
                         retention='<Subject 1>: fully_preserved - identity.\n<Audio 1>: fully_copy - soundtrack.')
        self.assertEqual(self.normalize(text), (text, [], []))

    def test_earlier_listener_annotation_is_not_later_speakers_id(self):
        text = base('[Shot 1] Alice （S1） listens. Bob says: <d>[English] Wait.</d>')
        fixed, _, unresolved = self.normalize(text)
        self.assertIn('Alice （S1） listens. Bob (S2) says:', fixed)
        self.assertFalse(unresolved)

    def test_valid_unknown_language_silent_and_non_native_outputs_byte_identical(self):
        for text in (base('[Shot 1] Alice (S1) says: <d>[Swedish] Vänta.</d>'), base(),
                     'Alice says "Wait.".', base('[Shot 1] A card reads "<d>[中文] words</d>".')):
            self.assertEqual(self.normalize(text), (text, [], []))

    def test_captured_real_api_outputs_all_28_speaker_defects_fixed_without_provider(self):
        path = ROOT / 'tests/fixtures/tudou_emotion_api_2026-10-04.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), '9d2cdcf15e0d99c433755d628533c82b624284bc6821c1f5fd4a254546c41f60')
        data = json.loads(path.read_text(encoding='utf-8'))
        total, broken, remaining, changed = 0, 0, 0, 0
        for phase in data['phases'].values():
            for test in phase['tests']:
                case = next(c for c in phase['cases'] if c['id'] == test['case_id'])
                if not test.get('output') or case['target'] == 'seedance20':
                    continue
                text = json.loads(test['output'])['native_prompt'] if case['target'] == 'relay' else test['output']
                with self.subTest(case=test['case_id'], repeat=test['repeat'], arm=test['arm']):
                    fixed, edits, unresolved = self.normalize(text, source=case['prompt'])
                    self.assertFalse(unresolved)
                    before = {i['code'] for i in q.check_h3(text)['issues']}
                    after = {i['code'] for i in q.check_h3(fixed)['issues']}
                    self.assertFalse(after - before, 'Formatting must not introduce another contract failure')
                    broken += 'h3_missing_speaker' in before
                    remaining += 'h3_missing_speaker' in after
                    total += 1
                    changed += bool(edits)
                    if not edits:
                        self.assertEqual(fixed, text)
        self.assertEqual((total, broken, remaining, changed), (51, 28, 0, 28))


class OutputBoundaryTests(unittest.TestCase):
    def run_h3(self, draft, **kwargs):
        complete = Mock(side_effect=AssertionError('Vocal protocol normalization is not a paid request'))
        values = dict(mode=q.QUALITY_OFF, messages=[], complete=complete, task_type='T2VA', duration=8,
                      shot_count=1, language='AUTO', source='')
        values.update(kwargs)
        result = pipeline.h3_quality_result(draft, **values)
        complete.assert_not_called()
        return result

    def test_all_quality_modes_normalize_without_extra_calls(self):
        draft = base('[Shot 1] Alice says: <d>[English] Wait.</d>')
        for mode in q.QUALITY_OPTIONS:
            with self.subTest(mode=mode):
                fixed, metrics = self.run_h3(draft, mode=mode)
                self.assertIn('Alice (S1) says:', fixed)
                self.assertEqual(metrics['correction_calls'], 0)
                self.assertEqual(metrics['result'], 'corrected')

    def test_relay_changes_only_native_prompt_not_execution_or_weights(self):
        data = dict(global_prompt='Alice stands.', events=[dict(prompt='Alice says: <d>[English] Wait.</d>', end_state='Alice waits.', weight=1),
                                                          dict(prompt='Alice waits.', end_state='Alice waits.', weight=3)],
                    native_prompt=base('[Shot 1] Alice says: <d>[English] Wait.</d>'))
        frozen = copy.deepcopy(data)
        fixed, _ = self.run_h3(json.dumps(data), relay_config=dict(event_count=2, time_ranges='0-2\n2-8'))
        after = json.loads(fixed)
        self.assertEqual(after['events'], frozen['events'])
        self.assertEqual(after['global_prompt'], frozen['global_prompt'])
        self.assertIn('Alice (S1)', after['native_prompt'])
        compiled = compile_relay_response(fixed, 8, 2, '0-2\n2-8', 'T2VA', 'AUTO')
        self.assertEqual((compiled['relay_length'], compiled['time_ranges']), (192, '0-2\n2-8'))

    def test_ambiguous_output_retained_and_diagnostic_not_silent_success(self):
        text = base('[Shot 1] 她说：<d>[Chinese] 等我。</d> 他回答：<d>[Chinese] 好。</d>')
        progress = Mock()
        fixed, metrics = self.run_h3(text, progress=progress)
        self.assertEqual(fixed, text)
        self.assertIn('h3_missing_speaker', metrics['issue_codes'])
        self.assertEqual(metrics['protocol_edits'], 0)
        progress.assert_called_once()

    def test_correction_candidate_is_normalized_before_acceptance_without_a_second_request(self):
        original = base('[Shot 1] Alice says: <d>[English] Wait.</d> ' + 'Alice walks to the door. ' * 10)
        candidate = base('[Shot 1] Alice （S1） says: <d>[English] Wait.</d> ' + '她走向门口，镜头静止跟随人物，不添加道具或剧情。' * 5, sound='只有房间环境声。')
        complete = Mock(return_value=candidate)
        fixed, metrics = pipeline.h3_quality_result(original, mode=q.QUALITY_REPAIR, messages=[], complete=complete,
            task_type='T2VA', duration=8, shot_count=1, language='中文', source='Alice says "Wait.".')
        self.assertIn('Alice (S1)', fixed)
        self.assertNotIn('Alice （S1）', fixed)
        self.assertEqual(metrics['correction_calls'], 1)
        complete.assert_called_once()


class RealProductionBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_directional_skills as doubles
        cls.d = doubles

    def test_cloud_local_and_restore_use_corrected_final_not_raw_draft(self):
        module = self.d.h3
        draft = base('[Shot 1] Alice says: <d>[English] Wait.</d>')
        expected = draft.replace('Alice says:', 'Alice (S1) says:')
        for transport in ('cloud', 'local'):
            with self.subTest(transport=transport):
                values = self.d.execute_inputs(module)
                values.update(prompt='Alice says "Wait.".', output_language='English', recovery_slot='vocal-' + transport)
                provider = self.d.RecordingLocalProvider(None, vision=False, responses=[draft])
                session = self.d.test_seedance20.SequencedChatSession([draft])
                if transport == 'cloud':
                    values['api_key'] = 'test-placeholder'
                    # execute's normal provider session, not an alternate node.
                    with patch.object(module.requests, 'Session', return_value=session):
                        result = module.MiniMaxH3PromptEnhancer.execute(**values)
                    self.assertEqual(len(session.chat_requests), 1)
                else:
                    values['api_mode'] = module.LOCAL_QWEN_API_MODE
                    with patch.object(module, 'LocalQwenProvider', return_value=provider):
                        result = module.MiniMaxH3PromptEnhancer.execute(**values)
                    self.assertEqual(len(provider.calls), 1)
                    self.assertTrue(provider.closed)
                self.assertEqual(result[0], expected)
                with patch.object(module, 'enhance_prompt', side_effect=AssertionError('No rebilling on restore')):
                    restored = module.MiniMaxH3PromptEnhancer.execute(**{**values, 'recovery_action': module.RECOVERY_ACTION_RESTORE})
                self.assertEqual(restored[0], expected)


if __name__ == '__main__':
    unittest.main()
