import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_film_workflow_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
film = sys.modules[f"{SPEC.name}.film_workflow"]
creative = sys.modules[f"{SPEC.name}.creative_suite"]
h3 = sys.modules[f"{SPEC.name}.nodes"]
seedance = sys.modules[f"{SPEC.name}.seedance20"]


def completion(payload, provider="test-provider"):
    return creative.CompletionResult(
        text=json.dumps(payload, ensure_ascii=False),
        provider=provider,
    )


def project_state(**overrides):
    values = {
        "project_title": "雨夜证词",
        "mode": film.PROJECT_MODES[3],
        "target_stage": film.STAGE_OPTIONS[-1],
        "project_brief": "证人必须在天亮前交出证据。",
        "authoritative_inputs": "screenplay-v03\ncharacter-v02",
        "confirmed_stages": "01 02 03 04 05 06 07 08",
        "changed_stage": film.STAGE_OPTIONS[4],
        "revision_note": "第八场动机被修正",
        "world_rules": "能力只能读取触碰过的物件\n使用后会失去一段记忆",
        "ability_costs_and_limits": "不能读取活体\n3秒后能力失效",
        "knowledge_gaps": "证人不知道警探已看过录像",
        "continuity_anchors": "红色证物袋始终在左手",
    }
    values.update(overrides)
    return film.T8FilmProjectRouter.execute(**values)[0]


def performance_bible():
    return film.build_character_performance_bible(
        "证人 / <Picture 1>",
        "迫使警探相信证词",
        "警探掌握矛盾录像；失败会失去保护",
        "拖延\n试探\n交出证物",
        "双手折叠证物袋；上一镜的急促呼吸延续",
        "低声、短句；只在说话时使用",
        "警探说出录像时间时，镇定面具破裂",
        "先看证物袋，再看警探；回答前先接收信息",
    )


class FilmWorkflowTests(unittest.TestCase):
    def test_new_connection_only_inputs_are_appended_after_prior_socket_contracts(self):
        h3_ids = [item.id for item in h3.MiniMaxH3PromptEnhancer.define_schema().inputs]
        seedance_ids = [item.id for item in seedance.Seedance20PromptEnhancer.define_schema().inputs]
        longform_ids = [item.id for item in creative.T8LongFormPlanner.define_schema().inputs]
        storyboard_ids = [item.id for item in creative.T8StoryboardPack.define_schema().inputs]
        self.assertEqual(
            h3_ids[-3:],
            ["performance_director_config", "provider_config", "character_performance_bible"],
        )
        self.assertEqual(
            seedance_ids[-3:],
            ["performance_director_config", "provider_config", "character_performance_bible"],
        )
        self.assertEqual(longform_ids[-2:], ["film_project_state", "contract_failure_policy"])
        self.assertLess(longform_ids.index("provider_config"), longform_ids.index("film_project_state"))
        self.assertEqual(
            storyboard_ids[-3:],
            ["film_project_state", "character_performance_bible", "contract_failure_policy"],
        )
        self.assertLess(storyboard_ids.index("provider_config"), storyboard_ids.index("film_project_state"))

    def test_router_tracks_revision_authority_and_transitive_invalidation(self):
        state = project_state()
        self.assertEqual(state["schema_version"], film.FILM_PROJECT_SCHEMA)
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["changed_stage"], "05-screenplay")
        self.assertEqual(state["invalidated_stages"], ["06-assets", "07-acting", "08-prompt"])
        self.assertEqual(state["confirmed_invalidated_stages"], ["06-assets", "07-acting", "08-prompt"])
        self.assertIn("3秒后能力失效", state["world_contract"]["costs_and_limits"])
        self.assertTrue(state["policy"]["authority_isolation"])
        self.assertFalse(state["policy"]["automatic_downstream_regeneration"])

    def test_router_previous_json_increments_revision_without_mutating_previous(self):
        first = project_state()
        second = project_state(previous_state_json=json.dumps(first, ensure_ascii=False))
        self.assertEqual(second["revision"], 2)
        self.assertEqual(first["revision"], 1)

    def test_router_rejects_secrets_and_preserves_leading_numeric_facts(self):
        with self.assertRaisesRegex(film.FilmWorkflowError, "secret"):
            project_state(project_brief="sk-ABCDEFGHIJKLMNOPQRSTUV")
        state = project_state(world_rules="3秒后门会关闭\n2个人才能启动\n1.5秒后能力失效")
        self.assertEqual(
            state["world_contract"]["rules"],
            ["3秒后门会关闭", "2个人才能启动", "1.5秒后能力失效"],
        )

    def test_router_direct_state_inherits_blank_authoritative_fields(self):
        first = project_state(
            project_brief="不可丢失的权威剧情",
            world_rules="1.5秒后能力失效",
            continuity_anchors="红色证物袋始终在左手",
        )
        second = film.T8FilmProjectRouter.execute(
            project_title="未命名影视项目",
            mode=film.PROJECT_MODES[2],
            target_stage=film.STAGE_OPTIONS[-1],
            previous_state=first,
        )[0]
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["project_title"], first["project_title"])
        self.assertEqual(second["project_brief"], "不可丢失的权威剧情")
        self.assertEqual(second["world_contract"]["rules"], ["1.5秒后能力失效"])
        self.assertEqual(second["continuity_anchors"], ["红色证物袋始终在左手"])

    def test_router_can_selectively_clear_inherited_fields(self):
        first = project_state(
            project_brief="保留项目简述",
            world_rules="需要删除的旧规则",
            continuity_anchors="继续保留的连续性锚点",
        )
        second = film.T8FilmProjectRouter.execute(
            project_title="未命名影视项目",
            mode=film.PROJECT_MODES[2],
            target_stage=film.STAGE_OPTIONS[-1],
            previous_state=first,
            world_rules="[清空继承]",
            confirmed_stages="[CLEAR_INHERITED]",
        )[0]
        self.assertEqual(second["project_brief"], "保留项目简述")
        self.assertEqual(second["world_contract"]["rules"], [])
        self.assertEqual(second["confirmed_stages"], [])
        self.assertEqual(second["continuity_anchors"], ["继续保留的连续性锚点"])
        self.assertEqual(second["cleared_inherited_fields"], ["confirmed_stages", "rules"])

    def test_router_rejects_conflicting_direct_and_json_previous_state(self):
        first = project_state()
        conflicting = {**first, "revision": 99}
        with self.assertRaisesRegex(film.FilmWorkflowError, "不一致"):
            film.T8FilmProjectRouter.execute(
                project_title="A",
                mode=film.PROJECT_MODES[2],
                target_stage=film.STAGE_OPTIONS[-1],
                previous_state=first,
                previous_state_json=json.dumps(conflicting, ensure_ascii=False),
            )

    def test_router_rejects_invalid_previous_revision_with_domain_error(self):
        first = project_state()
        first["revision"] = "not-an-integer"
        with self.assertRaisesRegex(film.FilmWorkflowError, "revision"):
            film.T8FilmProjectRouter.execute(
                project_title="A",
                mode=film.PROJECT_MODES[2],
                target_stage=film.STAGE_OPTIONS[-1],
                previous_state=first,
            )

    def test_router_frontend_exposes_invalidation_status_without_animation(self):
        ui_source = (ROOT / "web" / "js" / "film_workflow_ui.js").read_text(encoding="utf-8")
        view_source = (ROOT / "web" / "js" / "film_workflow_status.mjs").read_text(encoding="utf-8")
        combined = ui_source + view_source
        self.assertIn("film_project_status", combined)
        self.assertIn("invalidated_stages", combined)
        self.assertIn("cleared_inherited_fields", combined)
        self.assertIn("creative_contract_status", combined)
        self.assertIn("T8LongFormPlanner", combined)
        self.assertIn("T8StoryboardPack", combined)
        self.assertIn("validation_errors", combined)
        self.assertIn("hideOnZoom: true", combined)
        self.assertIn("Comfy.Locale", combined)
        self.assertIn("estimateStatusCardHeight", combined)
        self.assertIn('const BIBLE_NODE_ID = "T8CharacterPerformanceBible"', ui_source)
        self.assertIn("const BIBLE_ADVANCED_WIDGET_NAMES = [", ui_source)
        self.assertIn('"gaze_and_listening",', ui_source)
        self.assertIn("installBibleAdvancedToggle(this)", ui_source)
        self.assertIn("⚙️ 高级表演选项（5 项选填）/ Advanced optional fields", ui_source)
        self.assertIn('toggle.value = expanded ? "收起 / Collapse" : "展开 / Expand"', ui_source)
        self.assertIn('node.addDOMWidget("t8_character_bible_help"', ui_source)
        self.assertIn("必填 / Required", ui_source)
        self.assertIn("高级选填 / Optional", ui_source)
        self.assertIn("只把绿色“角色表演圣经”输出", ui_source)
        self.assertIn("serialize: false", ui_source)
        self.assertIn("hideOnZoom: true", ui_source)
        self.assertNotIn("requestAnimationFrame", combined)

    def test_character_bible_has_bounded_observable_compiler_contract(self):
        bible = performance_bible()
        self.assertEqual(bible["schema_version"], film.CHARACTER_PERFORMANCE_SCHEMA)
        self.assertEqual(len(bible["tactics"]), 3)
        self.assertEqual(bible["compiler_contract"]["observable_cue_channels_per_beat"], 3)
        instruction = film.character_performance_instruction(bible, model_target="MiniMax H3")
        self.assertIn("迫使警探相信证词", instruction)
        self.assertIn("no more than three", instruction)
        self.assertIn("never invent dialogue", instruction)

    def test_character_bible_runs_with_only_the_three_required_fields(self):
        bible, contract, encoded = film.T8CharacterPerformanceBible.execute(
            "哥哥",
            "让妹妹交出车钥匙",
            "妹妹拒绝；失败会错过末班车",
        )
        self.assertEqual(bible["character_id"], "哥哥")
        self.assertEqual(bible["tactics"], [])
        self.assertEqual(bible["voice_lock"], "")
        self.assertNotIn("voice_lock", contract)
        self.assertEqual(json.loads(encoded)["obstacle_and_stakes"], "妹妹拒绝；失败会错过末班车")

    def test_character_bible_is_connection_only_for_both_core_nodes(self):
        for node in (h3.MiniMaxH3PromptEnhancer, seedance.Seedance20PromptEnhancer):
            ids = [item.id for item in node.define_schema().inputs]
            self.assertEqual(ids[-3:], [
                "performance_director_config",
                "provider_config",
                "character_performance_bible",
            ])

    def test_character_bible_schema_uses_bilingual_nonpersistent_examples(self):
        schema = film.T8CharacterPerformanceBible.define_schema()
        inputs = {item.id: item for item in schema.inputs}
        required_ids = [
            "character_id",
            "scene_objective",
            "obstacle_and_stakes",
        ]
        optional_ids = [
            "tactics",
            "physical_task_and_inertia",
            "voice_lock",
            "mask_break_trigger",
            "gaze_and_listening",
        ]
        guided_ids = [
            "scene_objective",
            "obstacle_and_stakes",
            *optional_ids,
        ]
        self.assertEqual([item.id for item in schema.inputs], [*required_ids, *optional_ids])
        schema_info = schema.get_v1_info(film.T8CharacterPerformanceBible)
        self.assertEqual(schema_info.input_order["required"], required_ids)
        self.assertEqual(schema_info.input_order["optional"], optional_ids)
        for input_id in required_ids:
            self.assertFalse(inputs[input_id].optional, input_id)
            self.assertFalse(inputs[input_id].advanced, input_id)
            self.assertIn("必填 / Required", inputs[input_id].display_name, input_id)
        for input_id in required_ids[1:]:
            self.assertIn("(Required)", inputs[input_id].placeholder, input_id)
        for input_id in optional_ids:
            self.assertTrue(inputs[input_id].optional, input_id)
            self.assertTrue(inputs[input_id].advanced, input_id)
            self.assertIn("选填 / Optional", inputs[input_id].display_name, input_id)
            self.assertIn("(Optional)", inputs[input_id].placeholder, input_id)
        for input_id in guided_ids:
            item = inputs[input_id]
            self.assertEqual(item.default, "", input_id)
            self.assertIn("示例 / Example", item.placeholder, input_id)
            self.assertRegex(item.placeholder, r"[\u4e00-\u9fff]", input_id)
            self.assertRegex(item.placeholder, r"[A-Za-z]", input_id)
            self.assertIn("/", item.display_name, input_id)
        self.assertIn("让妹妹交钥匙", inputs["scene_objective"].placeholder)
        self.assertIn("One tactic per line", inputs["tactics"].placeholder)

    def test_character_bible_reaches_h3_and_seedance_native_compilers(self):
        bible = performance_bible()
        h3_messages = h3._build_messages(
            prompt="证人交出证物袋",
            task_type="T2VA",
            duration_seconds=5,
            rewrite_mode="balanced",
            description_word_target=0,
            output_language="中文",
            prompt_mode="官方增强",
            reference_template="",
            reference_context="",
            constraints="",
            media_plan=[],
            media_parts=[],
            seed=1,
            shot_count=1,
            official_skill_profile=h3.COMPAT_SKILL_PROFILE,
            creative_preset=h3.NO_CREATIVE_PRESET,
            case_template=h3.NO_CASE_TEMPLATE,
            character_performance_bible=bible,
        )[0]["content"]
        self.assertIn("CHARACTER PERFORMANCE BIBLES for MiniMax H3", h3_messages)
        seedance_messages = seedance._build_messages(
            prompt="证人交出证物袋",
            task_intent="T2V",
            complexity_mode=seedance.COMPLEXITY_OPTIONS[0],
            duration_seconds=5,
            shot_count=1,
            rewrite_mode="balanced",
            output_detail=seedance.OUTPUT_DETAILS[0],
            custom_length_target=0,
            output_language="中文",
            prompt_mode="官方优化",
            reference_syntax=seedance.REFERENCE_SYNTAXES[0],
            subtitle_policy=seedance.SUBTITLE_POLICIES[0],
            stability_constraints=seedance.STABILITY_POLICIES[0],
            reference_roles="",
            reference_context="",
            constraints="",
            reference_template="",
            seed=1,
            media_plan=[],
            media_parts=[],
            case_template=seedance.NO_CASE_TEMPLATE,
            character_performance_bible=bible,
        )[0]["content"]
        self.assertIn("CHARACTER PERFORMANCE BIBLES for Seedance 2.0", seedance_messages)

    def test_character_bible_stack_keeps_characters_separate(self):
        first = performance_bible()
        second = film.build_character_performance_bible(
            "警探",
            "核验证词",
            "证人持续拖延；失败会放走嫌疑人",
            "展示录像\n追问时间",
        )
        bible_set = film.build_character_performance_set({"a": first, "b": second})
        self.assertEqual(bible_set["schema_version"], film.CHARACTER_PERFORMANCE_SET_SCHEMA)
        self.assertEqual([item["character_id"] for item in bible_set["characters"]], ["证人 / <Picture 1>", "警探"])
        instruction = film.character_performance_instruction(bible_set, model_target="MiniMax H3")
        self.assertIn("Keep every listed character separate", instruction)
        self.assertIn("警探", instruction)

    def test_character_bible_stack_rejects_duplicate_character_ids(self):
        first = performance_bible()
        with self.assertRaisesRegex(film.FilmWorkflowError, "重复"):
            film.build_character_performance_set([first, dict(first)])

    def test_long_form_receives_world_cost_knowledge_and_stale_contract(self):
        state = project_state()
        payload = {
            "global_continuity_brief": "证物袋与记忆代价锁定",
            "segments": [{
                "segment_index": 1,
                "start_state": "未触碰",
                "end_state": "失去记忆",
                "continuity_anchors": ["红袋左手"],
                "media_bindings": [],
                "world_rule_checks": ["仅触碰后读取"],
                "knowledge_state": {"证人": "不知道录像已被看过"},
                "downstream_status": ["08-prompt stale"],
                "h3_prompt": "H3",
                "seedance20_prompt": "Seedance",
            }],
            "handoffs": [],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8LongFormPlanner.execute(
                "证人使用能力",
                film_project_state=state,
                total_duration_seconds=15,
                segment_duration_seconds=15,
            )
        sent = mocked.call_args.kwargs
        self.assertIn("3秒后能力失效", sent["user"])
        self.assertIn("required_literal_anchor", sent["user"])
        self.assertIn("Missing facts remain unknown", sent["system"])
        segment = json.loads(result[1])["segments"][0]
        self.assertEqual(segment["knowledge_state"]["证人"], "不知道录像已被看过")
        self.assertEqual(json.loads(result[3])["project_revision"], 1)

    def test_storyboard_returns_narrative_audit_without_quality_claim(self):
        state = project_state()
        bible = performance_bible()
        payload = {
            "global_prompt": "证人交证物",
            "shots": [
                {
                    "index": 1,
                    "start_seconds": 0,
                    "end_seconds": 3,
                    "causal_link": "初始条件：警探拒绝相信",
                    "value_before": "不信任",
                    "value_after": "动摇",
                    "scene_necessity": "建立录像矛盾",
                    "setup_elements": ["录像时间"],
                    "payoff_elements": [],
                    "observable_cues": ["视线落袋", "呼吸停顿"],
                },
                {
                    "index": 2,
                    "start_seconds": 3,
                    "end_seconds": 6,
                    "causal_link": "因为警探说出录像时间",
                    "value_before": "动摇",
                    "value_after": "暂时相信",
                    "scene_necessity": "兑现录像矛盾",
                    "setup_elements": [],
                    "payoff_elements": ["录像时间"],
                },
            ],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)) as mocked:
            result = creative.T8StoryboardPack.execute(
                "警探核验证词",
                film_project_state=state,
                character_performance_bible=bible,
                duration_seconds=6,
                shot_count="2",
            )
        sent = mocked.call_args.kwargs
        self.assertIn("scene_necessity", sent["system"])
        self.assertIn("迫使警探相信证词", sent["system"])
        self.assertIn("identical label", sent["system"])
        shot_payload = json.loads(result[1])
        audit = shot_payload["narrative_audit"]
        self.assertEqual(audit["coverage"]["causal_link"], {"present": 2, "required": 2})
        self.assertEqual(audit["unmatched_setups"], [])
        self.assertIn("not an objective creative-quality score", audit["contract"])
        self.assertEqual(shot_payload["project_revision"], 1)

    def test_storyboard_audit_flags_missing_fields_and_open_setup(self):
        audit = creative.build_storyboard_narrative_audit([
            {"index": 1, "setup_elements": "钥匙；照片"},
        ])
        codes = {warning["code"] for warning in audit["warnings"]}
        self.assertEqual(audit["setup_elements"], ["钥匙", "照片"])
        self.assertTrue({"causality_missing", "value_shift_missing", "scene_necessity_missing", "setup_without_payoff"}.issubset(codes))

    def test_storyboard_rejects_wrong_structured_top_level_and_reports_keys(self):
        payload = {"storyboard": [{"index": 1}], "global_prompt": "wrong alias"}
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8StoryboardPack.execute("一镜测试", duration_seconds=3, shot_count="1")
        report = json.loads(result[1])
        self.assertFalse(report["structured_response"])
        self.assertEqual(report["shots"], [])
        self.assertEqual(report["response_schema"]["received_top_level_keys"], ["global_prompt", "storyboard"])
        self.assertIn("storyboard", report["unparsed_response"])
        status = json.loads(result.ui["creative_contract_status"][0])
        self.assertFalse(status["contract_valid"])
        self.assertEqual(status["operation"], "storyboard_planning")
        self.assertIn("unexpected_top_level_keys", status["validation_error_codes"])
        self.assertFalse(status["downstream_blocked"])
        self.assertIsNone(result.block_execution)

    def test_longform_rejects_wrong_structured_top_level_and_reports_keys(self):
        payload = {"plan": [], "global_continuity_brief": "wrong alias"}
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8LongFormPlanner.execute(
                "两段测试",
                total_duration_seconds=24,
                segment_duration_seconds=12,
            )
        report = json.loads(result[1])
        self.assertFalse(report["structured_response"])
        self.assertEqual(len(report["segments"]), 2)
        self.assertTrue(all(not item["h3_prompt"] for item in report["segments"]))
        self.assertEqual(report["response_schema"]["received_top_level_keys"], ["global_continuity_brief", "plan"])
        self.assertIn("plan", report["unparsed_response"])
        status = json.loads(result.ui["creative_contract_status"][0])
        self.assertFalse(status["contract_valid"])
        self.assertEqual(status["operation"], "long_form_planning")
        self.assertEqual(status["expected_item_count"], 2)
        self.assertEqual(status["received_item_count"], 0)

    def test_invalid_longform_can_strictly_block_downstream_without_losing_ui_diagnostics(self):
        payload = {"plan": [], "global_continuity_brief": "wrong alias"}
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8LongFormPlanner.execute(
                "两段测试",
                total_duration_seconds=24,
                segment_duration_seconds=12,
                contract_failure_policy=creative.CONTRACT_FAILURE_BLOCK,
            )
        status = json.loads(result.ui["creative_contract_status"][0])
        self.assertTrue(status["downstream_blocked"])
        self.assertEqual(status["failure_policy"], creative.CONTRACT_FAILURE_BLOCK)
        self.assertIn("contract validation failed", result.block_execution)
        self.assertEqual(len(result.args), 4)
        self.assertIn("validation_errors", result.args[3])

    def test_longform_valid_contract_emits_green_ui_status_payload(self):
        payload = {
            "global_continuity_brief": "保持主体和方向连续",
            "segments": [{
                "segment_index": 1,
                "start_state": "人物在门外",
                "end_state": "人物进入门内",
                "continuity_anchors": [],
                "media_bindings": [],
                "world_rule_checks": [],
                "knowledge_state": {},
                "downstream_status": [],
                "h3_prompt": "人物推门进入",
                "seedance20_prompt": "人物推门进入",
            }],
            "handoffs": [],
        }
        with patch.object(creative, "_run_completion", return_value=completion(payload)):
            result = creative.T8LongFormPlanner.execute(
                "人物推门进入",
                total_duration_seconds=15,
                segment_duration_seconds=15,
            )
        status = json.loads(result.ui["creative_contract_status"][0])
        self.assertTrue(status["contract_valid"])
        self.assertEqual(status["validation_error_count"], 0)
        self.assertEqual(status["expected_item_count"], 1)
        self.assertEqual(status["received_item_count"], 1)
        self.assertIsNone(result.block_execution)

    def test_longform_rejects_partial_schedule_extra_keys_and_missing_anchor(self):
        state = project_state()
        payload = {
            "global_continuity_brief": "不完整",
            "segments": [{
                "segment_index": 1,
                "continuity_anchors": [],
                "media_bindings": [],
                "world_rule_checks": [],
                "knowledge_state": {},
                "downstream_status": [],
                "h3_prompt": "H3",
                "seedance20_prompt": "S2",
            }],
            "handoffs": [],
            "unexpected": True,
        }
        outputs = creative._normalize_plan_response(
            json.dumps(payload, ensure_ascii=False),
            creative._segment_schedule(30, 15),
            creative.MODEL_TARGETS[2],
            "test",
            state,
            state["continuity_anchors"],
        )
        report = json.loads(outputs[1])
        codes = {item["code"] for item in report["validation_errors"]}
        self.assertFalse(report["structured_response"])
        self.assertIn("unexpected_top_level_keys", codes)
        self.assertIn("segment_schedule_mismatch", codes)
        self.assertIn("required_literal_anchors_missing", codes)
        self.assertIn("segment_field_missing", codes)
        self.assertEqual(report["segments"][1]["h3_prompt"], "")

    def test_storyboard_auto_count_still_rejects_empty_shot_array(self):
        with patch.object(creative, "_run_completion", return_value=completion({"global_prompt": "通用", "shots": []})):
            result = creative.T8StoryboardPack.execute("空分镜不应成功", shot_count="AUTO（系统自动判断）")
        report = json.loads(result[1])
        self.assertFalse(report["structured_response"])
        self.assertIn("shots_empty", {item["code"] for item in report["validation_errors"]})

    def test_storyboard_rejects_wrong_count_timeline_cue_budget_and_missing_anchor(self):
        state = project_state()
        shot = {
            "index": 1,
            "start_seconds": 5,
            "end_seconds": 99,
            "purpose": "推进",
            "composition": "中景",
            "subject_action": "走路",
            "camera": "固定",
            "continuity": "连续",
            "media_bindings": [],
            "dialogue_or_text": "",
            "sound": "",
            "keyframe_prompt": "人物走路",
            "transition_in": "",
            "transition_out": "",
            "causal_link": "初始",
            "value_before": "静止",
            "value_after": "移动",
            "scene_necessity": "推进故事",
            "setup_elements": [],
            "payoff_elements": [],
            "observable_cues": ["视线", "呼吸", "手部", "肩膀"],
        }
        with patch.object(creative, "_run_completion", return_value=completion({"global_prompt": "通用", "shots": [shot]})):
            result = creative.T8StoryboardPack.execute(
                "走路",
                film_project_state=state,
                duration_seconds=12,
                shot_count="4",
            )
        report = json.loads(result[1])
        codes = {item["code"] for item in report["validation_errors"]}
        self.assertFalse(report["contract_valid"])
        self.assertTrue({
            "shot_count_mismatch",
            "timeline_does_not_start_at_zero",
            "timeline_duration_mismatch",
            "observable_cue_budget_exceeded",
            "required_literal_anchors_missing",
        }.issubset(codes))


if __name__ == "__main__":
    unittest.main()
