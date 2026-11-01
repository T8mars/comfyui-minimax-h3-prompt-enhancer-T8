"""Evidence-driven style request regressions, not model/video quality assertions."""
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from test_directional_skills import h3, sd, h3_args, sd_args
from test_visual_styles import styles


def selected(kind, ident='022'):
    return styles.build_style_config(kind, styles.ON, ident)


def text_part(message):
    content = message['content']
    if isinstance(content, str):
        return content
    return '\n'.join(part['text'] for part in content if part.get('type') == 'text')


class VisualStyleEffectReviewTests(unittest.TestCase):
    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        guards.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('No network')))
        for module in (h3, sd):
            guards.enter_context(patch.object(module, 'LocalQwenProvider', side_effect=AssertionError('No model')))


    def test_both_targets_none_and_off_leave_complete_messages_equal(self):
        for module, args in ((h3, h3_args), (sd, sd_args)):
            values = args(prompt='不启用任何风格。', shot_count=1)
            baseline = module._build_messages(**values)
            for color, creator in ((None, None), (styles.build_style_config('color'),
                                                 styles.build_style_config('creator'))):
                self.assertEqual(module._build_messages(**values, color_style_config=color,
                                                        creator_style_config=creator), baseline)


    def test_neutral_grays_keep_lightness_information_and_original_hex(self):
        dark = styles._hue_description('#404040')
        middle = styles._hue_description('#808080')
        light = styles._hue_description('#D0D0D0')
        self.assertTrue(dark.startswith('深灰'), dark)
        self.assertTrue(middle.startswith('灰色'), middle)
        self.assertTrue(light.startswith('浅灰'), light)
        self.assertEqual(len({dark, middle, light}), 3)
        for ident in sorted(styles.IDS):
            color = selected('color', ident)
            resource, _, _ = styles.load_resource('color', ident)
            rule = styles.visual_style_instruction(color=color)
            for swatch in resource['primary']:
                self.assertIn(swatch['hex'], rule)

    def test_language_repairs_keep_phase_scope_last_and_idempotent(self):
        color, creator = selected('color'), selected('creator')
        scope = styles.REPAIR_STYLE_SCOPE
        self.assertTrue(scope)
        for module, args in ((h3, h3_args), (sd, sd_args)):
            for language in ('中文', 'English'):
                source = 'LOCK exact quote: “不要走”。黑上衣不变。'
                messages = module._build_messages(**args(prompt=source, output_language=language),
                    color_style_config=color, creator_style_config=creator)
                before = copy.deepcopy(messages)
                if module is h3:
                    repaired = module._h3_language_repair_messages('Plain draft.', language, None,
                        messages, color_style_config=color, creator_style_config=creator)
                else:
                    repaired = styles.preserve_visual_styles_on_repair(
                        module.local_language_repair_messages('Plain draft.', language), messages, color, creator)
                self.assertTrue(repaired[0]['content'].endswith(scope))
                self.assertEqual(repaired[0]['content'].count(scope), 1)
                self.assertEqual(repaired[0]['content'].count(styles.MARKER), 1)
                self.assertIn(source, text_part(repaired[1]))
                self.assertEqual(styles.preserve_visual_styles_on_repair(repaired, messages, color, creator), repaired)
                self.assertEqual(messages, before)

    def test_repair_off_does_not_append_a_scope_or_modify_the_repair_request(self):
        original = h3._build_messages(**h3_args(prompt='保持原文。'))
        repair = h3.local_language_repair_messages('A plain draft.', '中文')
        snapshot = copy.deepcopy(repair)
        for color, creator in ((None, None), (styles.build_style_config('color'),
                                             styles.build_style_config('creator'))):
            self.assertIs(styles.preserve_visual_styles_on_repair(repair, original, color, creator), repair)
            self.assertEqual(repair, snapshot)

    def test_editing_rules_allow_only_existing_permitted_cuts_and_honor_auto_no_cut_locks(self):
        creator = selected('creator', '038')
        method = styles.load_resource('creator', '038')[0]['methods'][1]['text_en']
        for target in ('h3', 'seedance20'):
            auto = styles.visual_style_instruction(creator=creator, target=target, fixed_shot_count=0)
            multiple = styles.visual_style_instruction(creator=creator, target=target, fixed_shot_count=3)
            single = styles.visual_style_instruction(creator=creator, target=target, fixed_shot_count=1)
            self.assertIn(method, auto)
            self.assertIn(method, multiple)
            self.assertNotIn(method, single)
            self.assertIn('existing permitted cuts', multiple)
            self.assertIn('AUTO', auto)
            self.assertIn('no-cut', auto)


    def test_all_200_creator_rules_preserve_both_languages_and_single_shot_filter(self):
        checked = 0
        for ident in sorted(styles.IDS):
            creator = selected('creator', ident)
            snapshot = copy.deepcopy(creator)
            resource, _, _ = styles.load_resource('creator', ident)
            for target in ('h3', 'seedance20'):
                for shots in (0, 1, 3):
                    rule = styles.visual_style_instruction(creator=creator, target=target, fixed_shot_count=shots)
                    for method in resource['methods']:
                        expected = not (shots == 1 and method['requires_cuts'])
                        for language in ('text_zh', 'text_en'):
                            self.assertEqual(method[language] in rule, expected, (ident, target, shots, language))
                    self.assertIn('same method', rule.lower())
                    checked += 1
            self.assertEqual(creator, snapshot)
            self.assertEqual(styles.resolve_creator_style(creator), snapshot)
        self.assertEqual(checked, 1200)
        rule = styles.visual_style_instruction(creator=selected('creator', '022'))
        self.assertIn('缓慢横移', rule)


if __name__ == '__main__':
    unittest.main()
