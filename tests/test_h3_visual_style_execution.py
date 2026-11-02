"""H3 style execution request contracts; CPU transport doubles, not model quality."""
import copy
import importlib
import json
import subprocess
import types
from collections import OrderedDict
from contextlib import ExitStack
from functools import lru_cache
import unittest
from unittest.mock import patch

from test_directional_skills import (
    GIT_ROOT, RecordingLocalProvider, execute_inputs, h3, h3_args, local_parameters, native_draft,
    original_function, primary_text, sd, sd_args, test_seedance20,
)


styles = h3.visual_styles
helpers = importlib.import_module(h3.__package__ + ".visual_style_nodes")
recovery = importlib.import_module(h3.__package__ + ".completion_recovery")
BASELINE = "421733faaeef5e997d52520d192e14665ede124e"


def active(kind):
    return styles.build_style_config(kind, styles.ON_EXPERIMENTAL, "022")


def ordinary(kind):
    return styles.build_style_config(kind, styles.ON, "022")


@lru_cache(maxsize=1)
def baseline_styles():
    """Load actual published guide code, not today's guide behind an old builder."""
    source = subprocess.check_output(
        ["git", "show", BASELINE + ":visual_styles.py"], cwd=GIT_ROOT
    ).decode("utf-8")
    module = types.ModuleType("published_visual_styles_1_38_4")
    # Packaged resource identities are unchanged; resolve them from the checkout.
    module.__file__ = styles.__file__
    exec(compile(source, str(styles.__file__), "exec"), module.__dict__)
    return module


def published_builder(filename, module):
    function = original_function(filename, "_build_messages", module, BASELINE)
    function.__globals__["visual_styles"] = baseline_styles()
    return function


def message_text(messages):
    return "\n".join(primary_text(message["content"]) for message in messages)


class H3VisualStyleExecutionTests(unittest.TestCase):
    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("No network")))
        for module in (h3, sd):
            guards.enter_context(patch.object(module, "LocalQwenProvider", side_effect=AssertionError("No real model")))

    def marker(self):
        return styles.H3_STYLE_EXECUTION_MARKER

    def test_none_and_off_leave_the_complete_existing_request_unchanged(self):
        old_build = published_builder("nodes.py", h3)
        for task in h3.TASK_TYPES:
            for language in ("中文", "English"):
                values = h3_args(task_type=task, output_language=language,
                                 prompt='原文\r\n保留“不是对白的引号”。', shot_count=1)
                expected = old_build(**values)
                for color, creator in ((None, None),
                                       (styles.build_style_config("color"), styles.build_style_config("creator"))):
                    self.assertEqual(styles.h3_style_execution_reminder(color, creator), "")
                    actual = h3._build_messages(**values, color_style_config=color, creator_style_config=creator)
                    self.assertEqual(actual, expected)
                    self.assertNotIn(self.marker(), message_text(actual))

    def test_ordinary_on_uses_the_complete_published_style_guide_and_request(self):
        published = baseline_styles()
        self.assertEqual(styles.MARKER, published.MARKER)
        self.assertFalse(hasattr(published, "ON_EXPERIMENTAL"))
        old_build = published_builder("nodes.py", h3)
        for kind in ("color", "creator"):
            self.assertEqual(ordinary(kind), published.build_style_config(kind, published.ON, "022"))
        pairs = ((ordinary("color"), None), (None, ordinary("creator")),
                 (ordinary("color"), ordinary("creator")))
        for task in h3.TASK_TYPES:
            for language in ("中文", "English"):
                for color, creator in pairs:
                    with self.subTest(task=task, language=language, color=bool(color), creator=bool(creator)):
                        values = h3_args(task_type=task, output_language=language, shot_count=1,
                                         prompt='原文\r\n旁白：“今天继续。”屏幕文字“标题”不发声。')
                        expected = old_build(**values, color_style_config=color, creator_style_config=creator)
                        actual = h3._build_messages(**values, color_style_config=color, creator_style_config=creator)
                        self.assertEqual(actual, expected)
                        self.assertEqual(styles.h3_style_execution_reminder(color, creator), "")
                        self.assertNotIn(styles.EXPERIMENTAL_MARKER, message_text(actual))
                        self.assertNotIn(self.marker(), message_text(actual))

    def test_seedance_experimental_configs_are_identical_to_published_ordinary_on(self):
        old_build = published_builder("seedance20.py", sd)
        pairs = ((active("color"), None), (None, active("creator")),
                 (active("color"), active("creator")),
                 (active("color"), ordinary("creator")),
                 (ordinary("color"), active("creator")))
        for task in sd.TASK_INTENTS:
            for language in ("中文", "English"):
                for color, creator in pairs:
                    values = sd_args(task_intent=task, output_language=language, shot_count=1)
                    normal = dict(color_style_config=ordinary("color") if color else None,
                                  creator_style_config=ordinary("creator") if creator else None)
                    expected = old_build(**values, **normal)
                    self.assertEqual(sd._build_messages(**values, **normal), expected)
                    actual = sd._build_messages(**values, color_style_config=color, creator_style_config=creator)
                    self.assertEqual(actual, expected)
                    self.assertNotIn(self.marker(), message_text(actual))
                    self.assertNotIn(styles.EXPERIMENTAL_MARKER, message_text(actual))

    def test_each_active_dimension_adds_only_one_tail_and_keeps_original_user_text(self):
        old_build = original_function("nodes.py", "_build_messages", h3, BASELINE)
        source = '原文\r\n无人产品画面，画外旁白说：“今天继续。”屏幕文字“保持安静”不发声。'
        values = h3_args(prompt=source, shot_count=1)
        for color, creator in ((active("color"), None), (None, active("creator")),
                               (active("color"), active("creator"))):
            snapshot = copy.deepcopy((color, creator))
            before = old_build(**values, color_style_config=color, creator_style_config=creator)
            after = h3._build_messages(**values, color_style_config=color, creator_style_config=creator)
            reminder = styles.h3_style_execution_reminder(color, creator)
            self.assertTrue(reminder.startswith(self.marker()))
            self.assertEqual(reminder, reminder.strip())
            self.assertEqual(after[0], before[0])
            self.assertEqual(after[1]["content"], before[1]["content"] + "\n\n" + reminder)
            self.assertEqual(message_text(after).count(self.marker()), 1)
            self.assertIn(json.dumps(source, ensure_ascii=False), after[1]["content"])
            self.assertEqual((color, creator), snapshot)
        seedance = sd._build_messages(**sd_args(), color_style_config=active("color"),
                                     creator_style_config=active("creator"))
        self.assertNotIn(self.marker(), message_text(seedance))

    def test_multimodal_parts_keep_their_original_order_and_values(self):
        old_build = original_function("nodes.py", "_build_messages", h3, BASELINE)
        parts = [
            {"type": "text", "text": "Reference image <Picture 1>"},
            {"type": "image_url", "image_url": {"url": "https://example.invalid/one.png", "detail": "high"}},
            {"type": "text", "text": "Reference image <Picture 2>"},
            {"type": "image_url", "image_url": {"url": "https://example.invalid/two.png"}},
        ]
        values = h3_args(task_type="Ref2VA", prompt='精确保留\r\n“原文”。', media_parts=parts,
                         media_plan=[{"role": "reference_image", "label": "<Picture 1>"},
                                     {"role": "reference_image", "label": "<Picture 2>"}])
        snapshot = copy.deepcopy(values)
        color, creator = active("color"), active("creator")
        before = old_build(**values, color_style_config=color, creator_style_config=creator)
        after = h3._build_messages(**values, color_style_config=color, creator_style_config=creator)
        self.assertEqual(after[1]["content"][1:], before[1]["content"][1:])
        self.assertEqual(after[1]["content"][1:], parts)
        self.assertEqual(after[1]["content"][0]["text"], before[1]["content"][0]["text"] + "\n\n" +
                         styles.h3_style_execution_reminder(color, creator))
        self.assertEqual(values, snapshot)

    def test_reminder_keeps_dimensions_separate_and_preserves_speech_authorization(self):
        color_only = styles.h3_style_execution_reminder(active("color"))
        creator_only = styles.h3_style_execution_reminder(creator=active("creator"))
        self.assertIn("\n色彩：", color_only)
        self.assertNotIn("\n导演：", color_only)
        self.assertIn("\n导演：", creator_only)
        self.assertNotIn("\n色彩：", creator_only)
        for reminder in (color_only, creator_only):
            # Pin the reviewed instruction boundary, not a fabricated model response.
            self.assertIn("画面无人不等于没有发声", reminder)
            self.assertIn("画外音/离屏说话", reminder)
            self.assertIn("只对原任务已有或明确授权", reminder)
            self.assertIn("不要把标题、文字标识或任意引文当成对白", reminder)
            self.assertIn("(S1)", reminder)
            self.assertIn("<d>[英文语言名称]准确原词</d>", reminder)
            self.assertIn("明确静音时保持静音", reminder)
            self.assertIn("原任务已有或要求的声音照常保留", reminder)
            self.assertIn("颜色、灯光、景深或构图本身不生成声音", reminder)
            self.assertIn("风格选择不授权新增", reminder)
        self.assertIn("床单的许可不等于整张床或人物的许可", color_only)
        self.assertIn("不能把画外区域的配色当作画面效果", color_only)
        self.assertIn("固定机位", creator_only)
        self.assertIn("缺少必要空间、物件或许可时不用该方法", creator_only)

    def test_mixed_modes_strengthen_only_the_experimental_dimension(self):
        for color, creator, dimension, excluded in (
            (active("color"), ordinary("creator"), "色彩", "导演"),
            (ordinary("color"), active("creator"), "导演", "色彩"),
        ):
            reminder = styles.h3_style_execution_reminder(color, creator)
            self.assertEqual(reminder.count("\n" + dimension + "："), 1)
            self.assertNotIn("\n" + excluded + "：", reminder)
            self.assertEqual(reminder.count("\n原生发声："), 1)
            self.assertEqual(reminder.count("\n声音与媒介："), 1)
            messages = h3._build_messages(**h3_args(), color_style_config=color, creator_style_config=creator)
            self.assertEqual(message_text(messages).count(self.marker()), 1)
            self.assertEqual(messages[0]["content"].count(styles.EXPERIMENTAL_MARKER), 1)
            # Ordinary On retains its source guide; it only opts out of the new tail dimension.
            self.assertIn("COLOR REFERENCE", messages[0]["content"])
            self.assertIn("CREATOR PRESENTATION ONLY", messages[0]["content"])
            self.assertTrue(primary_text(messages[1]["content"]).endswith(reminder))

    def test_mode_validation_is_strict_and_existing_config_identity_is_unchanged(self):
        self.assertEqual(styles.MODES, [styles.OFF, styles.ON, styles.ON_EXPERIMENTAL])
        for kind, cls, selection_name in (
            ("color", helpers.T8ColorStyleConfig, "palette"),
            ("creator", helpers.T8CreatorStyleConfig, "creator"),
        ):
            normal, experimental = ordinary(kind), active(kind)
            self.assertEqual({**experimental, "mode": "on"}, normal)
            self.assertEqual(experimental["mode"], "on_experimental")
            self.assertEqual(styles.resolve_style_config(experimental, kind), experimental)
            self.assertIs(cls.validate_inputs(mode=styles.ON_EXPERIMENTAL, **{selection_name: "022"}), True)
            self.assertEqual(cls.execute(mode=styles.ON_EXPERIMENTAL, **{selection_name: "022"})[0], experimental)
            for value in (None, False, 1, [], {}, "on_experimental", "On (H3 experimental)", " 开启 / On"):
                with self.subTest(kind=kind, mode=value), self.assertRaises(ValueError):
                    styles.build_style_config(kind, value, "022")
                self.assertIsNot(cls.validate_inputs(mode=value, **{selection_name: "022"}), True)
            for value in (None, False, 1, [], {}, styles.ON_EXPERIMENTAL, "ON_EXPERIMENTAL", "on_experimental "):
                bad = {**experimental, "mode": value}
                with self.subTest(kind=kind, canonical_mode=value), self.assertRaises(ValueError):
                    styles.resolve_style_config(bad, kind)
            with self.assertRaises(ValueError):
                styles.resolve_style_config({**experimental, "execution_mode": "h3_experimental"}, kind)

    def test_metadata_preserves_experimental_identity_and_historical_restore_needs_no_catalog(self):
        normal = styles.style_metadata(ordinary("color"), ordinary("creator"))
        self.assertEqual(normal, baseline_styles().style_metadata(ordinary("color"), ordinary("creator")))
        for color, creator in ((active("color"), active("creator")),
                               (active("color"), ordinary("creator")),
                               (ordinary("color"), active("creator"))):
            metadata = styles.style_metadata(color, creator)
            for kind, config in (("color", color), ("creator", creator)):
                block = metadata[kind + "_style"]
                expected = dict(normal[kind + "_style"])
                if config["mode"] == "on_experimental":
                    expected["execution_mode"] = "h3_experimental"
                self.assertEqual(block, expected)
            with patch.object(styles, "load_catalog", side_effect=AssertionError("No historical remap")):
                self.assertEqual(styles.safe_style_metadata(metadata), metadata)
                self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
            for invalid in (None, False, [], {}, "on_experimental", "on", "PRIVATE"):
                bad = copy.deepcopy(metadata)
                bad["color_style"]["execution_mode"] = invalid
                self.assertEqual(styles.safe_style_metadata(bad), {"creator_style": metadata["creator_style"]})

        metadata = styles.style_metadata(active("color"), active("creator"))
        # Isolated in-memory checkpoint, never a user's live recovery record.
        with patch.object(recovery, "_RECORDS", OrderedDict()):
            for module, cls, function in (
                (h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt"),
            ):
                component = cls.define_schema().node_id
                slot = "test-h3-experimental-restore-" + component
                self.assertTrue(recovery.begin_recovery_record(component, slot, "test", metadata=metadata))
                self.assertTrue(recovery.complete_recovery_record(component, slot, ("historical result",)))
                with patch.object(styles, "load_catalog", side_effect=AssertionError("No historical remap")), \
                        patch.object(module, function, side_effect=AssertionError("No new model call")):
                    restored = cls.execute(**execute_inputs(module), recovery_action="restore_last", recovery_slot=slot,
                                           color_style_config={"invalid_current": True}, creator_style_config={"invalid_current": True})
                    self.assertEqual(restored[0], "historical result")
                    self.assertEqual(recovery.recovery_status(component, slot)["creation_metadata"], metadata)

    def test_mode_changes_invalidate_helper_and_consumer_caches_but_restore_is_exempt(self):
        for kind, cls, selection_name in (
            ("color", helpers.T8ColorStyleConfig, "palette"),
            ("creator", helpers.T8CreatorStyleConfig, "creator"),
        ):
            normal = cls.fingerprint_inputs(mode=styles.ON, **{selection_name: "022"})
            experimental = cls.fingerprint_inputs(mode=styles.ON_EXPERIMENTAL, **{selection_name: "022"})
            self.assertNotEqual(normal, experimental)
            self.assertEqual(experimental, styles.helper_fingerprint(kind, styles.ON_EXPERIMENTAL, "022"))
        pairs = ((ordinary("color"), ordinary("creator")),
                 (active("color"), ordinary("creator")),
                 (ordinary("color"), active("creator")),
                 (active("color"), active("creator")))
        for cls in (h3.MiniMaxH3PromptEnhancer, sd.Seedance20PromptEnhancer):
            fingerprints = [cls.fingerprint_inputs(color_style_config=color, creator_style_config=creator)
                            for color, creator in pairs]
            for index, fingerprint in enumerate(fingerprints):
                self.assertNotIn(fingerprint, fingerprints[:index])
            self.assertIs(cls.fingerprint_inputs(), False)
            self.assertIs(cls.fingerprint_inputs(color_style_config=active("color"),
                                                 recovery_action="restore_last"), False)
            self.assertIs(cls.fingerprint_inputs(color_style_config={"invalid_current": True},
                                                 recovery_action="restore_last"), False)

    def assert_execution_and_language_order(self, messages):
        text = message_text(messages)
        self.assertEqual(text.count(self.marker()), 1)
        user = primary_text(messages[1]["content"])
        self.assertIn("FINAL LOCAL OUTPUT LANGUAGE LOCK", user)
        self.assertLess(user.index(self.marker()), user.rindex("FINAL LOCAL OUTPUT LANGUAGE LOCK"))

    def test_cloud_actual_entry_points_include_one_reminder_without_style_retry(self):
        draft = native_draft()
        for mode in (h3.SEEDANCE_API_MODE, h3.AI_WORKSHOP_API_MODE, h3.OPENAI_API_MODE):
            session = test_seedance20.SequencedChatSession([draft])
            result = h3.enhance_prompt(prompt="Keep the red sleeve and the ticket.", duration_seconds=13,
                shot_count="1", output_language="English", api_mode=mode, session=session,
                api_key="test-placeholder", openai_base_url="https://example.invalid/v1", custom_model="test-model",
                color_style_config=active("color"), creator_style_config=active("creator"))
            self.assertEqual(result, draft, "The reminder must not append style text or add a style correction call")
            self.assertEqual(len(session.chat_requests), 1)
            self.assertEqual(session.uploads, [])
            self.assert_execution_and_language_order(session.chat_requests[0]["json"]["messages"])

    def test_local_actual_entry_builds_twice_but_calls_once_for_each_dimension(self):
        for color, creator in ((active("color"), None), (None, active("creator")),
                               (active("color"), active("creator"))):
            provider = RecordingLocalProvider({}, vision=False, responses=[native_draft()])
            with patch.object(h3, "LocalQwenProvider", return_value=provider), \
                    patch.object(h3, "_build_messages", wraps=h3._build_messages) as builds:
                result = h3.enhance_prompt(prompt="Keep the red sleeve and the ticket.", duration_seconds=13,
                    output_language="English", api_mode=h3.LOCAL_QWEN_API_MODE, **local_parameters(h3),
                    color_style_config=color, creator_style_config=creator)
                self.assertEqual(builds.call_count, 2)
            self.assertEqual(result, native_draft())
            self.assertEqual(len(provider.calls), 1)
            self.assertTrue(provider.closed)
            self.assert_execution_and_language_order(provider.calls[0]["messages"])

    def test_existing_offscreen_speech_and_visible_quotes_are_not_reclassified(self):
        # These are transport/normalizer fixtures, not claims that a model obeys the reminder.
        cases = [
            ('画面只有水杯，无可见人物。画外旁白说：“今天继续。”',
             'integrated_multimodal_description: [Shot 1] 水杯保持静止。画外说话人 (S1) says in an off-screen voiceover: '
             '<d>[Chinese] 今天继续。</d> 画面无可见人物。\n\noverall_soundscape: 安静室内。\n\nnon_diegetic_music: N/A'),
            ('画面只有无人的水杯和屏幕。屏幕文字“保持安静”不发声；完全静音。',
             'integrated_multimodal_description: [Shot 1] 水杯与屏幕保持静止，屏幕显示"保持安静"。'
             '\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A'),
        ]
        for source, draft in cases:
            session = test_seedance20.SequencedChatSession([draft])
            result = h3.enhance_prompt(prompt=source, duration_seconds=8, output_language="中文",
                session=session, api_key="test-placeholder", color_style_config=active("color"))
            self.assertEqual(result, draft)
            self.assertEqual(len(session.chat_requests), 1)
            if "完全静音" in source:
                self.assertNotIn("<d>", result)
                self.assertNotIn("(S1)", result)
            else:
                self.assertIn("says in an off-screen voiceover", result)
                self.assertIn("<d>[Chinese] 今天继续。</d>", result)

    def test_language_repairs_keep_one_execution_reminder_and_translation_scope_last(self):
        color, creator = active("color"), active("creator")
        for local in (False, True):
            responses = [native_draft(), native_draft(True)]
            values = dict(prompt='保留原文\r\n“显示文字”与人物红袖口。', output_language="中文",
                          color_style_config=color, creator_style_config=creator)
            if local:
                provider = RecordingLocalProvider({}, vision=False, responses=responses)
                with patch.object(h3, "LocalQwenProvider", return_value=provider), \
                        patch.object(h3, "needs_local_language_repair", return_value=True):
                    result = h3.enhance_prompt(**values, api_mode=h3.LOCAL_QWEN_API_MODE, **local_parameters(h3))
                calls = [call["messages"] for call in provider.calls]
                self.assertTrue(provider.closed)
            else:
                session = test_seedance20.SequencedChatSession(responses)
                with patch.object(h3, "needs_local_language_repair", return_value=True):
                    result = h3.enhance_prompt(**values, session=session, api_key="test-placeholder")
                calls = [call["json"]["messages"] for call in session.chat_requests]
            self.assertEqual(result, responses[-1])
            self.assertEqual(len(calls), 2, "Only the pre-existing language correction may add a call")
            first, repaired = calls
            self.assertEqual(message_text(first).count(self.marker()), 1)
            self.assertEqual(message_text(repaired).count(self.marker()), 1)
            self.assertIn(primary_text(first[1]["content"]), repaired[1]["content"])
            self.assertTrue(repaired[0]["content"].endswith(styles.REPAIR_STYLE_SCOPE))
            self.assertEqual(repaired[0]["content"].count(styles.REPAIR_STYLE_SCOPE), 1)
            self.assertEqual(styles.preserve_visual_styles_on_repair(repaired, first, color, creator), repaired)


if __name__ == "__main__":
    unittest.main()
