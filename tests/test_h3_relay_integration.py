import json
import unittest
from unittest.mock import patch

from test_nodes import nodes, FakeSession


class RelayIntegrationTests(unittest.TestCase):
    def draft(self):
        return json.dumps({
            "global_prompt": "A locked camera shows a quiet station. No background music.",
            "events": [
                {"prompt": "The woman picks up the ticket.", "end_state": "She holds the ticket.", "weight": 1},
                {"prompt": "She hands the ticket to the passenger.", "end_state": "The passenger holds the ticket; both stand still.", "weight": 1},
            ],
            "native_prompt": "integrated_multimodal_description: [Shot 1] A woman picks up a ticket and hands it to a passenger.\noverall_soundscape: Quiet station ambience.\nnon_diegetic_music: N/A",
        })

    def inputs(self, **extra):
        return dict(prompt="A woman returns a ticket.", task_type="T2VA", duration_seconds=8,
                    rewrite_mode="balanced", description_word_target=0, output_language="English", **extra)

    def chinese_draft(self):
        return json.dumps({
            "global_prompt": "固定镜头拍摄安静车站，保持人物身份、服装、场景与晨光连续一致，全程没有配乐。",
            "events": [
                {"prompt": "女生弯腰捡起地上的车票。", "end_state": "女生站稳并拿着车票。", "weight": 1},
                {"prompt": "女生把车票交给乘客，乘客接过后点头。", "end_state": "乘客拿稳车票，两人自然站立。", "weight": 1},
            ],
            "native_prompt": (
                "integrated_multimodal_description: 固定镜头拍摄安静车站。女生捡起车票交给乘客，"
                "乘客接过后点头，两人自然站立，人物身份、服装和场景始终一致。\n"
                "overall_soundscape: 安静车站的自然环境声。\nnon_diegetic_music: 无配乐。"
            ),
        }, ensure_ascii=False)

    def test_normal_keeps_first_output_and_does_not_enable_relay(self):
        with patch.object(nodes, "enhance_prompt", return_value="unchanged") as completion:
            result = nodes.MiniMaxH3PromptEnhancer.execute(**self.inputs())
        self.assertEqual(tuple(result.result), ("unchanged", "", "", "", 0, ""))
        self.assertNotIn("relay_config", completion.call_args.kwargs)

    def test_relay_execute_and_restore_preserve_integer_output(self):
        with patch.object(nodes, "enhance_prompt", return_value=self.draft()) as completion:
            args = self.inputs(relay_mode=nodes.RELAY, relay_duration_seconds=25.29, recovery_slot="t8-relay-integration-01")
            result = nodes.MiniMaxH3PromptEnhancer.execute(**args)
            self.assertEqual(completion.call_args.kwargs["duration_seconds"], 25.29)
        self.assertEqual(result[4], 617)
        self.assertEqual(len(result[2].splitlines()), 2)
        with patch.object(nodes, "enhance_prompt", side_effect=AssertionError("Must not resubmit")):
            restored = nodes.MiniMaxH3PromptEnhancer.execute(**args, recovery_action=nodes.RECOVERY_ACTION_RESTORE)
        self.assertEqual(tuple(restored.result), tuple(result.result))
        self.assertIsInstance(restored[4], int)

    def test_cloud_messages_preserve_relay_contract(self):
        session = FakeSession(self.draft())
        raw = nodes.enhance_prompt(**self.inputs(), api_key="test-placeholder", session=session,
                                  relay_config={"event_count": 2, "time_ranges": "0-4\n4-8"})
        self.assertEqual(raw, self.draft())
        system = session.chat_requests[0]["json"]["messages"][0]["content"]
        self.assertIn("global_prompt", system)
        self.assertIn("native_prompt", system)

    def test_bad_timeline_rejected_before_paid_call(self):
        with patch.object(nodes, "enhance_prompt", side_effect=AssertionError("Must validate first")):
            with self.assertRaises((ValueError, nodes.PromptEnhancerError)):
                nodes.MiniMaxH3PromptEnhancer.execute(**self.inputs(relay_mode=nodes.RELAY, relay_time_ranges="0-2\n3-8"))

    def test_fractional_relay_duration_is_not_truncated_by_media_validation(self):
        session = FakeSession(self.draft())
        args = self.inputs()
        args["duration_seconds"] = 0.5
        result = nodes.enhance_prompt(**args, api_key="test-placeholder", session=session,
                                     relay_config={"event_count": 2, "time_ranges": "0-0.25\n0.25-0.5"})
        self.assertEqual(result, self.draft())

    def test_structural_repair_counts_both_cloud_attempts(self):
        calls = []
        responses = iter(["{}", self.draft()])
        def complete(*args, **kwargs):
            kwargs["attempts_callback"](1)
            return next(responses)
        with patch.object(nodes, "_request_completion", side_effect=complete):
            result = nodes.enhance_prompt(**self.inputs(), api_key="test-placeholder", session=FakeSession(""),
                                         relay_config={"event_count": 2, "time_ranges": ""},
                                         progress_callback=lambda stage, **details: calls.append((stage, details)))
        self.assertEqual(result, self.draft())
        self.assertEqual(next(details["attempts"] for stage, details in calls if stage == "llm_completed"), 2)

    def test_relay_language_validation_checks_each_decoded_output_section(self):
        data = json.loads(self.chinese_draft())
        data["global_prompt"] = (
            "A static camera records a quiet railway station in warm morning light. "
            "Keep identities, clothing and scenery consistent with no background music."
        )
        mixed = json.dumps(data, ensure_ascii=False)
        escaped_chinese = json.dumps(json.loads(self.chinese_draft()), ensure_ascii=True)
        config = {"event_count": 2, "time_ranges": ""}
        self.assertTrue(nodes._needs_h3_language_repair(mixed, "中文", config))
        self.assertFalse(nodes._needs_h3_language_repair(escaped_chinese, "中文", config))

    def test_format_repair_is_followed_by_one_language_repair(self):
        data = json.loads(self.chinese_draft())
        data["global_prompt"] = (
            "A static camera records a quiet railway station in warm morning light. "
            "Keep identities, clothing and scenery consistent with no background music."
        )
        mixed = json.dumps(data, ensure_ascii=False)
        responses = iter(["{}", mixed, self.chinese_draft()])
        calls = []

        def complete(*args, **kwargs):
            calls.append(args[2])
            kwargs["attempts_callback"](1)
            return next(responses)

        args = self.inputs()
        args["output_language"] = "中文"
        with patch.object(nodes, "_request_completion", side_effect=complete):
            result = nodes.enhance_prompt(
                **args, api_key="test-placeholder", session=FakeSession(""),
                relay_config={"event_count": 2, "time_ranges": ""},
            )
        self.assertEqual(len(calls), 3)
        self.assertEqual(result, self.chinese_draft())
        self.assertFalse(nodes._needs_h3_language_repair(result, "中文", {"event_count": 2}))

    def test_relay_corrections_fail_closed_after_each_budget_is_used(self):
        data = json.loads(self.chinese_draft())
        data["global_prompt"] = "A static railway station remains unchanged through the full scene."
        mixed = json.dumps(data, ensure_ascii=False)
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "selected output language"):
            nodes._next_relay_correction(
                mixed, 8, {"event_count": 2, "time_ranges": ""}, "T2VA", [], "中文",
                format_used=False, language_used=True,
            )

    def test_repair_preserves_json_and_normal_repair_is_unchanged(self):
        self.assertEqual(nodes._h3_language_repair_messages("text", "中文", None), nodes.local_language_repair_messages("text", "中文"))
        self.assertIn("Relay JSON", nodes._h3_language_repair_messages("{}", "中文", {"event_count": 0})[0]["content"])

    def test_all_cloud_routes_keep_relay_envelope(self):
        for mode in (nodes.SEEDANCE_API_MODE, nodes.AI_WORKSHOP_API_MODE, nodes.OPENAI_API_MODE):
            with self.subTest(mode=mode):
                session = FakeSession(self.draft())
                result = nodes.enhance_prompt(**self.inputs(), api_mode=mode, api_key="test-placeholder",
                    custom_model="test/model", openai_base_url="https://provider.example/v1", session=session,
                    relay_config={"event_count": 2, "time_ranges": ""})
                self.assertEqual(result, self.draft())
                self.assertEqual(len(session.chat_requests), 1)
                self.assertIn("H3 PROMPT RELAY", session.chat_requests[0]["json"]["messages"][0]["content"])

    def test_local_mock_keeps_relay_and_releases_context(self):
        from test_local_qwen import FakeLocalProvider
        FakeLocalProvider.instances = []
        FakeLocalProvider.response = self.draft()
        with patch.object(nodes, "LocalQwenProvider", FakeLocalProvider):
            result = nodes.enhance_prompt(**self.inputs(), api_mode=nodes.LOCAL_QWEN_API_MODE,
                relay_config={"event_count": 2, "time_ranges": ""}, local_max_tokens=24576)
        instance = FakeLocalProvider.instances[-1]
        self.assertEqual(result, self.draft())
        self.assertEqual(instance.settings.max_tokens, 24576)
        self.assertEqual(instance.closed, [False])
        self.assertIn("H3 PROMPT RELAY", instance.messages[0][0]["content"])

    def test_local_mock_uses_the_same_bounded_format_then_language_repairs(self):
        from test_local_qwen import FakeLocalProvider
        data = json.loads(self.chinese_draft())
        data["global_prompt"] = "A static railway station stays visually consistent for the complete scene."
        responses = iter(["{}", json.dumps(data, ensure_ascii=False), self.chinese_draft()])
        FakeLocalProvider.instances = []
        FakeLocalProvider.response = lambda _messages: next(responses)
        args = self.inputs()
        args["output_language"] = "中文"
        with patch.object(nodes, "LocalQwenProvider", FakeLocalProvider):
            result = nodes.enhance_prompt(
                **args, api_mode=nodes.LOCAL_QWEN_API_MODE,
                relay_config={"event_count": 2, "time_ranges": ""},
            )
        instance = FakeLocalProvider.instances[-1]
        self.assertEqual(result, self.chinese_draft())
        self.assertEqual(len(instance.calls), 3)
        self.assertEqual(instance.closed, [False])


if __name__ == "__main__":
    unittest.main()
