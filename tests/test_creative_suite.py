import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import torch


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_creative_suite_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
creative = sys.modules[f"{SPEC.name}.creative_suite"]

LIVE_SPEC = importlib.util.spec_from_file_location(
    "t8_creative_suite_live_smoke_test_module",
    ROOT / "creative_suite_live_smoke.py",
)
live_smoke = importlib.util.module_from_spec(LIVE_SPEC)
LIVE_SPEC.loader.exec_module(live_smoke)


def completion(payload, provider="test-provider"):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return creative.CompletionResult(text=text, provider=provider)


class FakeVideo:
    def get_stream_source(self):
        return io.BytesIO(b"video")

    def get_duration(self):
        return 2.0

    def get_container_format(self):
        return "mp4"


class FakeResponse:
    headers = {}
    text = ""

    def __init__(self, content, status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text

    def json(self):
        if self.status_code != 200:
            return {"error": {"message": self.content}}
        return {"choices": [{"message": {"content": self.content}}]}


class FakeSession:
    def __init__(self, content):
        self.content = content
        self.requests = []
        self.closed = False

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return FakeResponse(self.content)

    def close(self):
        self.closed = True


class SequenceSession(FakeSession):
    def __init__(self, responses):
        super().__init__("")
        self.responses = list(responses)

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


class CreativeSuiteTests(unittest.TestCase):
    def test_paid_acceptance_fixture_is_redacted_and_complete(self):
        path = ROOT / "tests" / "fixtures" / "creative_suite_paid_acceptance_2026-08-28.json"
        source = path.read_text(encoding="utf-8")
        payload = json.loads(source)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["overall_contract_score"], 100)
        self.assertEqual(len(payload["successful_feature_cases"]), 7)
        self.assertFalse(payload["response_text_stored"])
        self.assertFalse(payload["credentials_stored"])
        self.assertNotRegex(source, r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")

    def test_live_smoke_requires_explicit_paid_confirmation_and_key(self):
        with self.assertRaisesRegex(RuntimeError, "explicit confirmation"):
            live_smoke.run_paid_smoke(confirm_paid=False)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SEEDANCE_API_KEY"):
                live_smoke.run_paid_smoke(confirm_paid=True)

    def test_live_smoke_scoring_is_deterministic_and_redacted(self):
        scored = live_smoke._check(
            "sample",
            {"one": True, "two": False, "three": True},
            {"count": 2},
        )
        self.assertFalse(scored["passed"])
        self.assertEqual(scored["score"], 67)
        self.assertEqual(scored["failed_checks"], ["two"])
        self.assertNotIn("api", json.dumps(scored).lower())

    def test_all_new_node_ids_are_unique_and_core_nodes_remain_first(self):
        import asyncio

        extension = asyncio.run(package.comfy_entrypoint())
        node_classes = asyncio.run(extension.get_node_list())
        ids = [node.define_schema().node_id for node in node_classes]
        self.assertEqual(ids[:3], [
            "MiniMaxH3PromptEnhancerT8",
            "Seedance20PromptEnhancerT8",
            "MiniMaxMusic3PromptEnhancerT8",
        ])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[-13:], [node.define_schema().node_id for node in creative.CREATIVE_SUITE_NODES])

    def test_creative_director_is_local_and_preserves_dimension_policies(self):
        result = creative.T8CreativeDirector.execute(
            premise="一名舞者在雨夜寻找失落的声音",
            character_identity="红色雨衣、短发",
            identity_policy=creative.LOCK_POLICY,
            visual_language="冷蓝街灯与红色人物对比",
            visual_policy=creative.EVOLVE_POLICY,
        )
        brief = result[0]
        self.assertEqual(brief["schema_version"], creative.BRIEF_SCHEMA)
        dimensions = {item["id"]: item for item in brief["dimensions"]}
        self.assertEqual(dimensions["character_identity"]["policy"], "LOCK")
        self.assertIn("红色雨衣", result[1])
        self.assertEqual(json.loads(result[2])["premise"], brief["premise"])

    def test_context_assembler_outputs_string_for_existing_core_nodes(self):
        brief = creative.T8CreativeDirector.execute(premise="雨夜追逐")[0]
        result = creative.T8CreativeContextAssembler.execute(
            creative_brief=brief,
            extra_constraints="结尾必须回到同一盏路灯",
        )
        self.assertIsInstance(result[0], str)
        self.assertIn("creative_brief", result[0])
        self.assertIn("结尾必须", result[0])
        self.assertEqual(json.loads(result[1])["operation"], "context_assembly")

    def test_directed_revision_uses_one_response_and_generates_local_diff(self):
        payload = {
            "revised_prompt": "人物仍穿红衣。镜头节奏加快。",
            "change_summary": ["加快节奏"],
            "preserved_anchors": ["红衣"],
            "warnings": [],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8DirectedRevision.execute(
                "人物仍穿红衣。镜头缓慢。", "只加快镜头节奏", "红衣"
            )
        self.assertEqual(mocked.call_count, 1)
        self.assertIn("镜头节奏加快", result[0])
        self.assertIn("-人物仍穿红衣。镜头缓慢。", result[2])

    def test_non_json_revision_is_released_instead_of_rejected(self):
        with patch.object(creative, "_run_completion", return_value=completion("直接可用的非 JSON 修订结果")):
            result = creative.T8DirectedRevision.execute("旧结果", "修改节奏")
        self.assertEqual(result[0], "直接可用的非 JSON 修订结果")
        self.assertFalse(json.loads(result[1])["structured_response"])

    def test_long_form_schedule_covers_total_duration_without_gap(self):
        schedule = creative._segment_schedule(38, 15)
        self.assertEqual(schedule, [
            {"segment_index": 1, "start_seconds": 0, "end_seconds": 15, "duration_seconds": 15},
            {"segment_index": 2, "start_seconds": 15, "end_seconds": 30, "duration_seconds": 15},
            {"segment_index": 3, "start_seconds": 30, "end_seconds": 38, "duration_seconds": 8},
        ])

    def test_long_form_planner_separates_h3_and_seedance_outputs(self):
        payload = {
            "global_continuity_brief": "人物衣着和空间方向锁定",
            "segments": [
                {"segment_index": 1, "start_state": "门外", "end_state": "入门", "h3_prompt": "H3-A", "seedance20_prompt": "S-A"},
                {"segment_index": 2, "start_state": "入门", "end_state": "落座", "h3_prompt": "H3-B", "seedance20_prompt": "S-B"},
            ],
            "handoffs": [{"from": 1, "to": 2, "locked_state": "入门"}],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8LongFormPlanner.execute("人物走入房间", total_duration_seconds=20, segment_duration_seconds=10)
        self.assertEqual(result[0], "人物衣着和空间方向锁定")
        self.assertEqual(json.loads(result[1])["segments"][0]["h3_prompt"], "H3-A")
        self.assertEqual(json.loads(result[2])["segments"][0]["seedance20_prompt"], "S-A")
        self.assertEqual(len(json.loads(result[3])["handoffs"]), 1)

    def test_reference_mapper_uses_only_connected_media_labels(self):
        payload = {
            "assets": [{"label": "<Picture 1>", "roles": ["identity"]}],
            "conflicts": [], "coverage_gaps": ["environment"],
            "enhancer_reference_context": "<Picture 1> only controls identity.",
        }
        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8ReferenceRoleMapper.execute(
                "人物广告", reference_images={"reference_image_0": image}
            )
        sent_plan = mocked.call_args.kwargs["media_plan"]
        self.assertEqual([item["label"] for item in sent_plan], ["<Picture 1>"])
        self.assertNotIn("gif", json.dumps(result[0]).lower())
        self.assertIn("identity", result[3])

    def test_reference_mapper_accepts_stale_autogrow_values_in_schema_validation(self):
        self.assertTrue(creative.T8ReferenceRoleMapper.validate_inputs({"old": 1}, {"old": 2}))

    def test_candidate_lab_and_selector(self):
        payload = {"candidates": [
            {"name": "叙事", "creative_axis": "story", "prompt": "方案一"},
            {"name": "奇观", "creative_axis": "spectacle", "prompt": "方案二"},
            {"name": "表演", "creative_axis": "performance", "prompt": "方案三"},
        ], "comparison": ["三者机制不同"]}
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8CreativeCandidateLab.execute("一位舞者穿越城市")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result[2:5], ("方案一", "方案二", "方案三"))
        selected = creative.T8CreativeCandidateSelector.execute(result[0], 2)
        self.assertEqual(selected[0], "方案二")

    def test_storyboard_pack_keeps_structured_outputs_separate(self):
        payload = {
            "global_prompt": "全局提示词",
            "shots": [{"index": 1, "start_seconds": 0, "end_seconds": 5}],
            "keyframe_prompts": [{"index": 1, "prompt": "静态关键帧"}],
            "transition_sound": [{"index": 1, "sound": "风声"}],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8StoryboardPack.execute("人物奔跑", duration_seconds=5, shot_count="1")
        self.assertEqual(result[0], "全局提示词")
        self.assertEqual(json.loads(result[1])["shots"][0]["end_seconds"], 5)
        self.assertEqual(json.loads(result[2])["keyframe_prompts"][0]["prompt"], "静态关键帧")

    def test_storyboard_pack_derives_duplicate_delivery_tables_locally(self):
        payload = {
            "global_prompt": "全局提示词",
            "shots": [{
                "index": 1,
                "start_seconds": 0,
                "end_seconds": 5,
                "purpose": "建立",
                "composition": "全景",
                "subject_action": "人物进入",
                "camera": "跟拍",
                "continuity": "红衣",
                "media_bindings": [],
                "dialogue_or_text": "",
                "sound": "脚步",
                "keyframe_prompt": "雨夜红衣人物全景",
                "transition_in": "淡入",
                "transition_out": "硬切",
            }],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8StoryboardPack.execute("人物奔跑", duration_seconds=5, shot_count="1")
        self.assertIn("global_prompt and shots only", mocked.call_args.kwargs["system"])
        self.assertEqual(json.loads(result[2])["keyframe_prompts"][0]["prompt"], "雨夜红衣人物全景")
        derived = json.loads(result[3])["transition_sound"][0]
        self.assertEqual(derived["sound"], "脚步")
        self.assertEqual(derived["transition_out"], "硬切")

    def test_dna_mixer_is_local_anti_copy_and_rejects_duplicate_roles(self):
        option_a, option_b = creative.CASE_TEMPLATE_OPTIONS[1:3]
        result = creative.T8CreativeDNAMixer.execute("一只猫打开神秘盒子", option_a, option_b)
        self.assertEqual(result[0]["schema_version"], creative.DNA_MIX_SCHEMA)
        self.assertIn("Never copy", result[1])
        self.assertNotIn("previews", result[2])
        with self.assertRaises(creative.CreativeSuiteError):
            creative.T8CreativeDNAMixer.execute("内容", option_a, option_a)

    def test_personal_preset_stays_workflow_local_and_contains_no_media(self):
        result = creative.T8PersonalCreativePreset.execute(
            "我的雨夜镜头", "城市短片", "主体+动作+收尾", "先静后动\n红色视觉锚点", "不改变人物身份"
        )
        self.assertEqual(result[0]["schema_version"], creative.PERSONAL_PRESET_SCHEMA)
        self.assertFalse(result[0]["media_included"])
        self.assertIn("user-owned", result[1].lower())

    def test_music_lab_locks_requested_chinese_lyrics_language(self):
        payload = {"candidates": [{"name": "A", "title": "归途", "lyrics": "[Verse]\n走过长街\n[Chorus]\n回到你身边"}]}
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8MusicCreativeLab.execute(
                operation=creative.MUSIC_LAB_MODES[0], music_idea="温暖中文流行歌", lyrics_language="中文"
            )
        self.assertIn("Requested language: 中文", mocked.call_args.kwargs["user"])
        self.assertIn("走过长街", result[0])
        self.assertFalse(json.loads(result[3])["local_text_qa"]["script_warning"])

    def test_music_caption_candidates_receive_only_lyric_tags_not_lyrics_text(self):
        payload = {"candidates": [{"name": "A", "caption": "### Global Metadata\nPop\n### Vocal Details\nWarm\n### Arrangement\nVerse to Chorus"}]}
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            creative.T8MusicCreativeLab.execute(
                operation=creative.MUSIC_LAB_MODES[1], music_idea="流行歌",
                source_lyrics="[Verse]\n秘密歌词\n[Chorus]\n不要泄露",
            )
        user = mocked.call_args.kwargs["user"]
        self.assertIn("[Verse] [Chorus]", user)
        self.assertNotIn("秘密歌词", user)
        self.assertNotIn("不要泄露", user)

    def test_version_stack_selects_and_diffs_without_llm(self):
        result = creative.T8CreativeVersionStack.execute(
            "第一版\n保留结尾",
            versions={"version_0": "第二版\n保留结尾", "version_1": "第三版\n保留结尾"},
            selected_version=2,
            version_notes="初稿\n节奏修改\n镜头修改",
        )
        self.assertEqual(result[0], "第二版\n保留结尾")
        self.assertEqual(json.loads(result[1])["selected_version"], 2)
        self.assertIn("-第一版", result[2])

    def test_beat_sheet_declares_text_only_evidence_boundary(self):
        payload = {
            "evidence_boundary": "仅根据文字规划",
            "rhythm_arc": "慢到快",
            "beat_events": [{"start_seconds": 0, "end_seconds": 5, "evidence_source": "user lyric tag"}],
            "h3_direction": "H3节拍约束",
            "seedance20_direction": "Seedance节拍约束",
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8MusicVideoBeatSheet.execute("公路MV", lyrics="[Verse]\n出发")
        self.assertEqual(result[0]["schema_version"], creative.BEAT_SHEET_SCHEMA)
        self.assertEqual(result[2], "H3节拍约束")
        self.assertEqual(result[3], "Seedance节拍约束")

    def test_seedance_provider_path_uses_existing_transport_without_logging_secret(self):
        fake = FakeSession('{"ok": true}')
        result = creative._run_completion(
            system="system", user="user", api_key="sk-aaaaaaaaaaaaaaaaaaaa",
            provider_config=None, rewrite_mode="balanced", seed=1, session=fake,
        )
        self.assertEqual(result.text, '{"ok": true}')
        self.assertEqual(result.provider, "Seedance")
        self.assertEqual(len(fake.requests), 1)
        _url, kwargs = fake.requests[0]
        self.assertNotIn("sk-aaaaaaaaaaaaaaaaaaaa", json.dumps(kwargs["json"]))
        self.assertEqual(kwargs["json"]["max_tokens"], 3072)

        overridden = FakeSession('{"ok": true}')
        provider_config = {
            "schema_version": "t8-llm-provider-config/v1",
            "provider": creative.PROVIDER_SEEDANCE,
            "provider_request_options": {
                "temperature_policy": "auto",
                "extra_parameters": {"max_completion_tokens": 777},
            },
        }
        creative._run_completion(
            system="system", user="user", api_key="sk-aaaaaaaaaaaaaaaaaaaa",
            provider_config=provider_config, rewrite_mode="balanced", seed=1,
            session=overridden, max_output_tokens=1024,
        )
        payload = overridden.requests[0][1]["json"]
        self.assertEqual(payload["max_completion_tokens"], 777)
        self.assertNotIn("max_tokens", payload)

        openai = FakeSession('{"ok": true}')
        openai_config = {
            "schema_version": "t8-llm-provider-config/v1",
            "provider": creative.PROVIDER_OPENAI,
            "openai_base_url": "https://example.com/v1",
            "custom_model": "custom-vision-model",
            "provider_request_options": None,
        }
        creative._run_completion(
            system="system", user="user", api_key="sk-aaaaaaaaaaaaaaaaaaaa",
            provider_config=openai_config, rewrite_mode="balanced", seed=1,
            session=openai, max_output_tokens=1024,
        )
        openai_payload = openai.requests[0][1]["json"]
        self.assertNotIn("max_tokens", openai_payload)
        self.assertNotIn("max_completion_tokens", openai_payload)

    def test_creative_suite_retries_transient_seedance_gateway_and_hides_body(self):
        fake = SequenceSession([
            FakeResponse("origin timeout", status_code=524, text="<html>private proxy page</html>"),
            FakeResponse("origin timeout", status_code=524, text="<html>private proxy page</html>"),
            FakeResponse('{"ok": true}'),
        ])
        with patch.object(creative.h3.time, "sleep", return_value=None):
            result = creative._run_completion(
                system="system", user="user", api_key="sk-aaaaaaaaaaaaaaaaaaaa",
                provider_config=None, rewrite_mode="balanced", seed=1, session=fake,
            )
        self.assertEqual(result.text, '{"ok": true}')
        self.assertEqual(len(fake.requests), 3)

        final_failure = SequenceSession([
            FakeResponse("origin timeout", status_code=524, text="<html>private proxy page</html>")
            for _ in range(6)
        ])
        with patch.object(creative.h3.time, "sleep", return_value=None):
            with self.assertRaises(creative.CreativeSuiteError) as raised:
                creative._run_completion(
                    system="system", user="user", api_key="sk-aaaaaaaaaaaaaaaaaaaa",
                    provider_config=None, rewrite_mode="balanced", seed=1, session=final_failure,
                )
        message = str(raised.exception)
        self.assertIn("HTTP 524", message)
        self.assertIn("hidden for privacy", message)
        self.assertNotIn("private proxy page", message)
        self.assertEqual(len(final_failure.requests), 6)


if __name__ == "__main__":
    unittest.main()
