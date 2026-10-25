"""Engineering contracts, not real model or rendered-video quality evidence."""
import ast
import subprocess
from visual_style_baseline_projection import project_style_ast
import asyncio
import copy
import importlib
import inspect
import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from test_directional_skills import (ROOT, RecordingLocalProvider, execute_inputs, h3, h3_args,
    local_parameters, native_draft, original_function, relay_draft, sd, sd_args, test_seedance20)

styles = importlib.import_module(h3.__package__ + '.visual_styles')
helpers = importlib.import_module(h3.__package__ + '.visual_style_nodes')
recovery = importlib.import_module(h3.__package__ + '.completion_recovery')
BASELINE = '5f0029e3f8bf35ce216c8a69769d11ad4bbabd46'
SOCKETS = ['color_style_config', 'creator_style_config']


def active(kind='color', style_id='001'):
    return styles.build_style_config(kind, styles.ON, style_id)


class VisualStyleTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('No network')))
        for module in (h3, sd):
            self.guards.enter_context(patch.object(module, 'LocalQwenProvider', side_effect=AssertionError('No real model')))

    def test_only_reviewed_visual_ast_additions_to_existing_modules(self):
        from test_directional_skills import GIT_ROOT
        for name in ('nodes.py', 'seedance20.py'):
            old = subprocess.check_output(['git', 'show', BASELINE + ':' + name], cwd=GIT_ROOT).decode('utf-8')
            current = (ROOT / name).read_text(encoding='utf-8')
            self.assertEqual(ast.dump(project_style_ast(current)), ast.dump(ast.parse(old)), name)

    def test_none_off_are_frozen_for_every_native_task_language_and_director(self):
        for module, filename, args, key, tasks in ((h3, 'nodes.py', h3_args, 'task_type', h3.TASK_TYPES),
                                                  (sd, 'seedance20.py', sd_args, 'task_intent', sd.TASK_INTENTS)):
            old = original_function(filename, '_build_messages', module, BASELINE)
            for task in tasks:
                for skill in ('none', 'ning_wenwu', 'continuous_combat'):
                    for language in ('中文', 'English'):
                        values = args(**{key: task}, director_skill=skill, shot_count=1, output_language=language)
                        expected = old(**values)
                        for color, creator in ((None, None), (styles.build_style_config('color'), styles.build_style_config('creator'))):
                            self.assertEqual(module._build_messages(**values, color_style_config=color, creator_style_config=creator), expected)

    def test_original_signature_prefix_and_node_schemas(self):
        for module, file, cls, function in ((h3, 'nodes.py', h3.MiniMaxH3PromptEnhancer, 'enhance_prompt'),
                                           (sd, 'seedance20.py', sd.Seedance20PromptEnhancer, 'enhance_seedance20_prompt')):
            for name in (function, '_build_messages'):
                current = inspect.signature(getattr(module, name))
                self.assertEqual(list(current.parameters)[-2:], SOCKETS)
                self.assertEqual(current.replace(parameters=list(current.parameters.values())[:-2]),
                                 inspect.signature(original_function(file, name, module, BASELINE)))
            schema = cls.define_schema()
            self.assertEqual([v.id for v in schema.inputs[-2:]], SOCKETS)
            self.assertTrue(all(v.optional and v.lazy for v in schema.inputs[-2:]))
            self.assertEqual(len(schema.outputs), 6 if module is h3 else 1)
            self.assertEqual(cls.check_lazy_status(), [])
            self.assertEqual(cls.check_lazy_status(**dict.fromkeys(SOCKETS)), SOCKETS)
            self.assertEqual(cls.check_lazy_status(recovery_action='restore_last', **dict.fromkeys(SOCKETS)), [])
            self.assertIs(cls.fingerprint_inputs(), False)
            self.assertIs(cls.fingerprint_inputs(color_style_config=None, recovery_action='restore_last'), False)
        for cls, names in ((helpers.T8ColorStyleConfig, ['mode', 'palette', 'scope']), (helpers.T8CreatorStyleConfig, ['mode', 'creator'])):
            schema = cls.define_schema()
            self.assertEqual([v.id for v in schema.inputs], names)
            self.assertTrue(all(v.socketless for v in schema.inputs))
            self.assertEqual(schema.inputs[0].default, styles.OFF)
            self.assertEqual(len(schema.inputs[1].options), 201)
        package = importlib.import_module(h3.__package__)
        extension = asyncio.run(package.comfy_entrypoint())
        classes = asyncio.run(extension.get_node_list())
        self.assertEqual(len(classes), 38)
        self.assertEqual([v.define_schema().node_id for v in classes[-2:]], ['T8ColorStyleConfig', 'T8CreatorStyleConfig'])

    def test_configs_are_identity_only_strict_and_errors_do_not_echo(self):
        for kind in ('color', 'creator'):
            good = active(kind)
            self.assertEqual(styles.resolve_style_config(good, kind), good)
            for bad in (False, 1, [], {}, 'PRIVATE', {**good, 'instruction': 'PRIVATE'}, {**good, 'style_id': '../PRIVATE'},
                        {**good, 'resource_revision': '99.0.0'}, {**good, 'resource_sha256': '0' * 64},
                        {**good, 'mode': []}, {**good, 'style_id': []}):
                with self.subTest(kind=kind, bad=bad), self.assertRaises(ValueError) as caught:
                    styles.resolve_style_config(bad, kind)
                self.assertNotIn('PRIVATE', str(caught.exception))
            with self.assertRaises(ValueError):
                styles.build_style_config(kind, styles.ON)
        self.assertIsNone(styles.resolve_color_style(styles.build_style_config('color')))

    def test_independent_rules_and_single_shot_filter(self):
        color, creator = active(), active('creator')
        for module, args, target in ((h3, h3_args, 'h3'), (sd, sd_args, 'seedance20')):
            for c, d in ((color, None), (None, creator), (color, creator)):
                values = args(shot_count=1, prompt='LOCK: red sleeve, exact text “等我”, same ending.', duration_seconds=3600)
                before = module._build_messages(**values)
                after = module._build_messages(**values, color_style_config=c, creator_style_config=d)
                rule = styles.visual_style_instruction(c, d, target, fixed_shot_count=1)
                self.assertEqual(after[0]['content'].count(styles.MARKER), 1)
                self.assertEqual(after[0]['content'].replace('\n\n' + rule, ''), before[0]['content'])
                self.assertEqual(after[1:], before[1:])
                self.assertIn('no duration cap', rule)
                self.assertIn('Exactly one shot', rule)
                if c is None:
                    self.assertNotIn('COLOR REFERENCE', rule)
                    self.assertNotIn('#', rule)
                if d is None:
                    self.assertNotIn('CREATOR PRESENTATION ONLY', rule)
        light = styles.build_style_config('color', styles.ON, '001', styles.COLOR_LIGHT)
        self.assertNotIn('OPTIONAL LIGHTING:', styles.visual_style_instruction(color))
        self.assertIn('OPTIONAL LIGHTING:', styles.visual_style_instruction(light))
        for style_id in styles.IDS:
            cfg = active('creator', style_id)
            methods = styles.load_resource('creator', style_id)[0]['methods']
            single = styles.visual_style_instruction(creator=cfg, fixed_shot_count=1)
            for m in methods:
                self.assertEqual(m['text_en'] in single, not m['requires_cuts'])

    def test_language_repairs_preserve_exactly_once_without_old_features(self):
        repair = [{'role': 'system', 'content': 'Translate'}, {'role': 'user', 'content': 'draft'}]
        for c, d in ((active(), None), (None, active('creator')), (active(), active('creator'))):
            messages = h3._build_messages(**h3_args(), color_style_config=c, creator_style_config=d)
            first = styles.preserve_visual_styles_on_repair(repair, messages, c, d)
            self.assertEqual(first, styles.preserve_visual_styles_on_repair(first, messages, c, d))
            self.assertEqual(first[0]['content'].count(styles.MARKER), 1)
            actual = h3._h3_language_repair_messages('draft', 'English', None, messages, color_style_config=c, creator_style_config=d)
            self.assertEqual(actual[0]['content'].count(styles.MARKER), 1)
        self.assertEqual(styles.preserve_visual_styles_on_repair(repair, messages), repair)

    def test_cloud_local_budgets_single_requests_and_language_repair(self):
        for module, fn in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            draft = native_draft() if module is h3 else 'Shot 1: The woman keeps the red sleeve and ticket, and continues walking.'
            values = dict(prompt='Keep red sleeve and ticket.', duration_seconds=3600, shot_count='1', output_language='English',
                          color_style_config=active(), creator_style_config=active('creator'))
            for mode in (module.SEEDANCE_API_MODE, module.AI_WORKSHOP_API_MODE, module.OPENAI_API_MODE):
                session = test_seedance20.SequencedChatSession([draft])
                self.assertEqual(fn(**values, api_mode=mode, session=session, api_key='test-placeholder',
                                    openai_base_url='https://example.invalid/v1', custom_model='test-model'), draft)
                self.assertEqual(len(session.chat_requests), 1)
                self.assertEqual(session.uploads, [])
                self.assertEqual(session.chat_requests[0]['json']['messages'][0]['content'].count(styles.MARKER), 1)
            providers = []
            def factory(settings, *, vision):
                provider = RecordingLocalProvider(settings, vision=vision, responses=[draft])
                providers.append(provider)
                return provider
            with patch.object(module, 'LocalQwenProvider', side_effect=factory), patch.object(module, '_build_messages', wraps=module._build_messages) as builds:
                self.assertEqual(fn(**values, api_mode=module.LOCAL_QWEN_API_MODE, **local_parameters(module)), draft)
                self.assertEqual(builds.call_count, 2)
                rules = [module._build_messages(*v.args, **v.kwargs)[0]['content'] for v in list(builds.call_args_list)]
                self.assertTrue(all(s.count(styles.MARKER) == 1 for s in rules))
            self.assertEqual(len(providers[0].calls), 1)
            self.assertTrue(providers[0].closed)
            wrong = native_draft(True) if module is h3 else '女人保留红袖口并拿稳车票继续向前走。' * 20
            session = test_seedance20.SequencedChatSession([wrong, draft])
            with patch.object(module, 'needs_local_language_repair', side_effect=[True]):
                self.assertEqual(fn(**values, api_mode=module.SEEDANCE_API_MODE, session=session, api_key='test-placeholder'), draft)
            self.assertEqual(len(session.chat_requests), 2)
            self.assertEqual(session.chat_requests[-1]['json']['messages'][0]['content'].count(styles.MARKER), 1)

    def test_invalid_preflight_preserves_checkpoint_and_restore_skips_current_styles(self):
        for module, cls, function in ((h3, h3.MiniMaxH3PromptEnhancer, 'enhance_prompt'),
                                       (sd, sd.Seedance20PromptEnhancer, 'enhance_seedance20_prompt')):
            arguments = execute_inputs(module)
            slot = 'visual-style-restore-' + module.__name__.split('.')[-1]
            component = cls.define_schema().node_id
            original = ('old result',)
            recovery.begin_recovery_record(component, slot, 'test', metadata=styles.style_metadata(active(), active('creator')))
            recovery.complete_recovery_record(component, slot, original)
            with patch.object(module, function, side_effect=AssertionError('No model call')):
                result = cls.execute(**arguments, recovery_action='restore_last', recovery_slot=slot, color_style_config={'bad': 'PRIVATE'})
                self.assertEqual(result[0], 'old result')
                with self.assertRaises(Exception):
                    cls.execute(**arguments, recovery_slot=slot, creator_style_config={'bad': 'PRIVATE'})
            self.assertEqual(recovery.recover_outputs(component, slot, 1), original)

    def test_local_language_repairs_keep_both_styles_without_other_helpers(self):
        for module, function in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            responses = [native_draft(), native_draft(True)] if module is h3 else [
                'Shot 1: The woman holds the ticket and walks beside the station wall without changing her identity or adding another person. The camera follows her steady forward motion while her gaze remains directed toward the doorway at the end of the corridor.',
                '镜头1：女人持稳车票沿站墙向前走。']
            provider = RecordingLocalProvider({}, vision=False, responses=responses)
            with patch.object(module, 'LocalQwenProvider', return_value=provider):
                result = function('保留人物和车票。', output_language='中文',
                    api_mode=module.LOCAL_QWEN_API_MODE, **local_parameters(module),
                    color_style_config=active(), creator_style_config=active('creator'))
            self.assertEqual(result, responses[-1])
            self.assertEqual(len(provider.calls), 2)
            self.assertTrue(provider.closed)
            for call in provider.calls:
                self.assertEqual(call['messages'][0]['content'].count(styles.MARKER), 1)

    def test_relay_format_then_language_corrections_preserve_both_styles(self):
        responses = ['malformed JSON', relay_draft(), relay_draft(True)]
        values = dict(prompt='保留红色袖口。', duration_seconds=8, output_language='中文',
            relay_config={'event_count': 2, 'time_ranges': '0-4\n4-8'},
            color_style_config=active(), creator_style_config=active('creator'))
        for local in (False, True):
            if local:
                provider = RecordingLocalProvider({}, vision=False, responses=responses)
                with patch.object(h3, 'LocalQwenProvider', return_value=provider):
                    result = h3.enhance_prompt(**values, api_mode=h3.LOCAL_QWEN_API_MODE, **local_parameters(h3))
                calls = [call['messages'] for call in provider.calls]
                self.assertTrue(provider.closed)
            else:
                session = test_seedance20.SequencedChatSession(responses)
                result = h3.enhance_prompt(**values, api_key='test-placeholder', session=session)
                calls = [call['json']['messages'] for call in session.chat_requests]
            self.assertEqual(result, responses[-1])
            self.assertEqual(len(calls), 3)
            for messages in calls:
                self.assertEqual(messages[0]['content'].count(styles.MARKER), 1)
                self.assertIn('COLOR REFERENCE', messages[0]['content'])
                self.assertIn('CREATOR PRESENTATION ONLY', messages[0]['content'])

    def test_relay_failures_do_not_expand_correction_budget(self):
        for responses in (['invalid JSON', 'still invalid'], [relay_draft(), relay_draft()]):
            for local in (False, True):
                values = dict(prompt='保留人物和原事件。', duration_seconds=8, output_language='中文',
                    relay_config={'event_count': 2, 'time_ranges': '0-4\n4-8'},
                    color_style_config=active(), creator_style_config=active('creator'))
                if local:
                    provider = RecordingLocalProvider({}, vision=False, responses=responses)
                    with patch.object(h3, 'LocalQwenProvider', return_value=provider), self.assertRaises(h3.PromptEnhancerError):
                        h3.enhance_prompt(**values, api_mode=h3.LOCAL_QWEN_API_MODE, **local_parameters(h3))
                    calls = provider.calls
                else:
                    session = test_seedance20.SequencedChatSession(responses)
                    with self.assertRaises(h3.PromptEnhancerError):
                        h3.enhance_prompt(**values, session=session, api_key='test-placeholder')
                    calls = session.chat_requests
                self.assertEqual(len(calls), 2)

    def test_multimodal_repairs_preserve_styles_and_do_not_upload_again(self):
        from test_h3_hybrid import IMAGE, draft
        from test_nodes import FakeVideo
        plan = [{'role': 'first_frame', 'label': '<Picture 1>'},
                {'role': 'reference_image', 'label': '<Picture 2>'},
                {'role': 'reference_video', 'label': '<Video 1>'}]
        for module, function in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            values = dict(prompt='保留全部形状和实际素材职责。', duration_seconds=8, output_language='中文',
                reference_images={'reference_image_0': IMAGE}, reference_videos={'reference_video_0': FakeVideo()},
                color_style_config=active(), creator_style_config=active('creator'))
            if module is h3:
                values.update(task_type='Hybrid', first_frame=IMAGE)
                responses = [draft(plan, chinese=False), draft(plan)]
            else:
                values.update(task_intent='MultiRef')
                responses = ['Shot 1: The red disc slides continuously along the gray track while the blue box and all the existing shapes remain visible. Preserve the original objects and the reference video motion without adding any new elements.',
                             '镜头1：红圆沿灰轨平移，保留蓝框和全部形状。']
            session = test_seedance20.SequencedChatSession(responses)
            result = function(**values, session=session, api_key='test-placeholder')
            self.assertEqual(result, responses[-1])
            self.assertEqual(len(session.uploads), 3 if module is h3 else 2)
            self.assertEqual(len(session.chat_requests), 2)
            repair = session.chat_requests[1]['json']['messages']
            self.assertTrue(all(isinstance(m['content'], str) for m in repair))
            self.assertNotIn('https://assets.example/', json.dumps(repair))
            self.assertEqual(json.dumps(repair).count(styles.MARKER), 1)
            if module is h3:
                self.assertEqual(json.dumps(repair).count('T8_HYBRID_ASSET_ROLES'), 1)

    def test_quality_and_speech_corrections_retain_original_styles(self):
        from unittest.mock import Mock
        pipeline = importlib.import_module(h3.__package__ + '.quality_pipeline')
        speech = importlib.import_module(h3.__package__ + '.speech_reference')
        output = importlib.import_module(h3.__package__ + '.speech_output')
        messages = h3._build_messages(**h3_args(), color_style_config=active(), creator_style_config=active('creator'))
        complete = Mock(side_effect=RuntimeError('offline correction failure'))
        result, report = pipeline.h3_quality_result(native_draft(), mode='repair', messages=messages,
            complete=complete, task_type='T2VA', duration=12, shot_count=2, language='AUTO', source='')
        self.assertEqual(result, native_draft())
        self.assertEqual(report['result'], 'correction_failed_draft_kept')
        complete.assert_called_once()
        self.assertEqual(complete.call_args.args[0][:2], messages)
        reference = speech.provided_reference('等我回来。', purpose='keep_dialogue', speaker_map={'default': '角色A'})
        for target in ('h3', 'seedance'):
            correct = Mock(side_effect=RuntimeError('offline correction failure'))
            with self.assertRaises(output.SpeechOutputError):
                output.finish_speech_output(native_draft(), reference, target=target, language='English',
                    original_prompt='Keep the dialogue.', messages=messages, complete=correct, task_type='T2VA', duration=12)
            correct.assert_called_once()
            self.assertEqual(correct.call_args.args[0][:2], messages)

    def test_recovery_atomic_finite_and_catalog_independent(self):
        metadata = styles.style_metadata(active(), active('creator'))
        with patch.object(styles, 'load_catalog', side_effect=AssertionError('No historical remap')):
            self.assertEqual(styles.safe_style_metadata(metadata), metadata)
            self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
        for key in metadata['color_style']:
            bad = copy.deepcopy(metadata); bad['color_style'][key] = 'PRIVATE'
            self.assertEqual(styles.safe_style_metadata(bad), {'creator_style': metadata['creator_style']})
        bad = copy.deepcopy(metadata); bad['color_style']['extra'] = 'PRIVATE'
        self.assertNotIn('color_style', styles.safe_style_metadata(bad))

    def test_cache_hooks_v3_helper_and_external_consumer(self):
        old = styles.load_catalog()
        cfg = active()
        baseline_helper = helpers.T8ColorStyleConfig.fingerprint_inputs(styles.ON, '001')
        baseline_external = h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=None)
        with patch.object(styles, 'load_catalog', return_value=(old[0], 'f' * 64)):
            self.assertNotEqual(helpers.T8ColorStyleConfig.fingerprint_inputs(styles.ON, '001'), baseline_helper)
            self.assertNotEqual(h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=None), baseline_external)
            self.assertEqual(h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=cfg),
                             h3.MiniMaxH3PromptEnhancer.fingerprint_inputs(color_style_config=None))
            self.assertEqual(helpers.T8ColorStyleConfig.fingerprint_inputs(), 'visual-style-off')
            self.assertIs(sd.Seedance20PromptEnhancer.fingerprint_inputs(), False)


if __name__ == '__main__':
    unittest.main()
