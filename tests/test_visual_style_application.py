"""Style activation regressions: request evidence only, not model compliance."""
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from test_directional_skills import h3, sd, h3_args, sd_args
from test_visual_styles import styles, helpers, test_seedance20
from test_h3_hybrid import IMAGE
from performance_director import build_performance_director_config, PERFORMANCE_EXTREME


def selected(kind):
    return styles.build_style_config(kind, styles.ON, '022')


class VisualStyleApplicationTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('No network')))
        for module in (h3, sd):
            self.guards.enter_context(patch.object(module, 'LocalQwenProvider', side_effect=AssertionError('No real model')))

    def test_reported_ref2va_022_extreme_combination_reaches_the_single_request(self):
        prompt = '参考图女子坐在卧室床上直视镜头，保留身份与黑色上衣，说：“今天介绍一次更新。”'
        # Deliberately bland response: this tests transport, not a fabricated successful rewrite.
        draft = ('subject_definitions: 女子。\n\nsummary: 女子坐在床边说话。\n\n'
                 'retention_analysis: 保留身份与黑色上衣。\n\n'
                 'detailed_description: [Shot 1] 暖灯下，镜头缓慢推进，女子说：“今天介绍一次更新。”\n\n'
                 'overall_soundscape: 安静卧室。\n\nnon_diegetic_music: N/A')
        session = test_seedance20.SequencedChatSession([draft])
        color, creator = selected('color'), selected('creator')
        before = copy.deepcopy((color, creator))
        result = h3.enhance_prompt(prompt=prompt, task_type='Ref2VA', duration_seconds=13,
            shot_count='AUTO', output_language='中文', api_mode=h3.SEEDANCE_API_MODE,
            session=session, api_key='test-placeholder', reference_images={'reference_image_0': IMAGE},
            performance_director_config=build_performance_director_config(PERFORMANCE_EXTREME),
            color_style_config=color, creator_style_config=creator)
        self.assertEqual(result, draft, 'Never mechanically append a palette or silently pay for another call')
        self.assertEqual((len(session.chat_requests), len(session.uploads)), (1, 1))
        self.assertEqual((color, creator), before)
        system = session.chat_requests[0]['json']['messages'][0]['content']
        for part in ('EXTREME PERFORMANCE REWRITE CONTRACT', 'ENABLED STYLE APPLICATION',
                     'COLOR REALIZATION', 'CREATOR REALIZATION', 'COORDINATE DIMENSIONS',
                     'C01 #1A0A1F 30% (深紫色 / deep purple)', 'Layer existing glass',
                     'move laterally or observe closely'):
            self.assertIn(part, system)
        self.assertEqual(system.count(styles.EXPERIMENTAL_MARKER), 1)
        messages = session.chat_requests[0]['json']['messages']
        self.assertEqual(messages[1]['content'][0]['text'].count(styles.H3_STYLE_EXECUTION_MARKER), 1)
        self.assertNotIn('An already suitable passage may remain unchanged.', system)

    def test_each_target_keeps_acting_and_user_locks_while_enabling_separate_visual_dimensions(self):
        performance = build_performance_director_config(PERFORMANCE_EXTREME)
        for module, args, target in ((h3, h3_args, 'h3'), (sd, sd_args, 'seedance20')):
            for color, creator in ((selected('color'), None), (None, selected('creator')),
                                   (selected('color'), selected('creator'))):
                values = args(prompt='LOCK: 黑色上衣，固定机位，原台词“等我”。', shot_count=1,
                              performance_director_config=performance)
                before = module._build_messages(**values)
                messages = module._build_messages(**values, color_style_config=color, creator_style_config=creator)
                rule = styles.visual_style_instruction(color, creator, target, fixed_shot_count=1)
                self.assertEqual(messages[0]['content'].replace('\n\n' + rule, ''), before[0]['content'])
                expected_user = copy.deepcopy(before[1:])
                if module is h3:
                    reminder = styles.h3_style_execution_reminder(color, creator)
                    self.assertTrue(reminder)
                    expected_user[0]['content'] += '\n\n' + reminder
                    self.assertEqual(messages[1]['content'].count(styles.H3_STYLE_EXECUTION_MARKER), 1)
                self.assertEqual(messages[1:], expected_user)
                self.assertIn('does not cancel these separately enabled', rule)
                self.assertIn('explicit lock', rule)
                self.assertEqual('COLOR REALIZATION' in rule, color is not None)
                self.assertEqual('CREATOR REALIZATION' in rule, creator is not None)
                self.assertIn('Exactly one shot', rule)

    def test_color_words_do_not_import_emotional_swatch_labels_or_enable_lighting(self):
        for kind in ('color', 'creator'):
            rule = styles.visual_style_instruction(**{kind: selected(kind)})
            if kind == 'creator':
                self.assertNotIn('#1A0A1F', rule)
            else:
                self.assertIn('深紫色 / deep purple', rule)
                self.assertIn('COLOR ONLY: do not change lighting setup', rule)
                self.assertNotIn('OPTIONAL LIGHTING:', rule)
                self.assertIn('all relevant colors are explicitly locked', rule)
        for value, expected in (('#000000', '黑色 / black'), ('#FFFFFF', '白色 / white'),
                                ('#808080', '灰色 / gray'), ('#C41E3A', '红色 / red'),
                                ('#006B54', '深青绿色 / deep teal')):
            self.assertEqual(styles._hue_description(value), expected)
        rule = styles.visual_style_instruction(styles.build_style_config('color', styles.ON, '001'))
        self.assertIn('C04 #C41E3A 8% (红色 / red)', rule)
        self.assertNotIn('恐惧', rule)
        self.assertNotIn('Terror', rule)

    def test_instruction_revision_invalidates_on_and_external_consumer_caches_without_resource_migration(self):
        cfg = selected('color')
        current_helper = helpers.T8ColorStyleConfig.fingerprint_inputs(styles.ON, '022')
        current_consumer = h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=None)
        with patch.object(styles, 'INSTRUCTION_REVISION', '1.0.4'):
            self.assertNotEqual(helpers.T8ColorStyleConfig.fingerprint_inputs(styles.ON, '022'), current_helper)
            self.assertNotEqual(h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=None), current_consumer)
            self.assertEqual(selected('color'), cfg)
        self.assertEqual(cfg['resource_revision'], '1.0.0')
        self.assertEqual(cfg['adapter_revision'], '1.0.0')
        self.assertEqual(styles.resolve_color_style(cfg), cfg)
        self.assertEqual(helpers.T8ColorStyleConfig.fingerprint_inputs(), 'visual-style-off')
        for cls in (h3.MiniMaxH3PromptEnhancer, sd.Seedance20PromptEnhancer):
            self.assertIs(cls.fingerprint_inputs(), False)
            self.assertIs(cls.fingerprint_inputs(color_style_config=None, recovery_action='restore_last'), False)
            self.assertEqual(cls.fingerprint_inputs(color_style_config=cfg), current_consumer)

    def test_repairs_keep_application_contract_once_and_preserve_the_exact_source(self):
        color, creator = selected('color'), selected('creator')
        messages = h3._build_messages(**h3_args(prompt='LOCK: exact words “不要走”。', shot_count=1),
                                      color_style_config=color, creator_style_config=creator)
        repair = h3._h3_language_repair_messages('draft', '中文', None, messages,
                    color_style_config=color, creator_style_config=creator)
        self.assertEqual(repair[0]['content'].count(styles.EXPERIMENTAL_MARKER), 1)
        self.assertEqual(repair[1]['content'].count(styles.H3_STYLE_EXECUTION_MARKER), 1)
        self.assertIn('COLOR REALIZATION', repair[0]['content'])
        self.assertIn('CREATOR REALIZATION', repair[0]['content'])
        self.assertIn('exact words “不要走”', repair[1]['content'])
        self.assertEqual(styles.preserve_visual_styles_on_repair(repair, messages, color, creator), repair)


if __name__ == '__main__':
    unittest.main()
