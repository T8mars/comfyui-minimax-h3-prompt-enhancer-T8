import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_performance_director_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
performance = sys.modules[f"{SPEC.name}.performance_director"]
inspector = sys.modules[f"{SPEC.name}.prompt_inspector"]
nodes = sys.modules[f"{SPEC.name}.nodes"]
seedance = sys.modules[f"{SPEC.name}.seedance20"]
creative = sys.modules[f"{SPEC.name}.creative_suite"]

BENCH_SPEC = importlib.util.spec_from_file_location(
    "t8_performance_benchmark_test_module",
    ROOT / "tools" / "performance_benchmark.py",
)
benchmark = importlib.util.module_from_spec(BENCH_SPEC)
sys.modules[BENCH_SPEC.name] = benchmark
BENCH_SPEC.loader.exec_module(benchmark)

VERIFY_SPEC = importlib.util.spec_from_file_location(
    "t8_research_source_verifier_test_module",
    ROOT / "tools" / "verify_research_source.py",
)
source_verifier = importlib.util.module_from_spec(VERIFY_SPEC)
sys.modules[VERIFY_SPEC.name] = source_verifier
VERIFY_SPEC.loader.exec_module(source_verifier)


class PerformanceDirectorTests(unittest.TestCase):
    def test_source_lock_is_pinned_and_marks_evidence_limits(self):
        lock = json.loads((ROOT / "research_sources" / "h3-storyboard-skill.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], "t8-research-source-lock/v1")
        self.assertEqual(lock["source"]["commit"], performance.STORYBOARD_SOURCE_COMMIT)
        self.assertEqual(lock["source"]["license"], "MIT")
        self.assertEqual(len(lock["files"]), 5)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in lock["files"]))
        self.assertIn("Seedance 2.0 was not evaluated by the source.", lock["limitations"])
        self.assertTrue(any("official" in item.lower() for item in lock["prohibited_overclaims"]))
        self.assertEqual(source_verifier.validate_lock(lock), [])

    def test_source_verifier_compares_exact_bytes_and_sha256(self):
        content = b"pinned bytes\n"
        digest = __import__("hashlib").sha256(content).hexdigest()
        lock = {
            "schema_version": source_verifier.LOCK_SCHEMA,
            "source": {
                "repository": "https://github.com/phileiny/h3-storyboard-skill",
                "commit": "a" * 40,
                "license": "MIT",
            },
            "files": [{"path": "README.md", "bytes": len(content), "sha256": digest}],
            "limitations": ["narrow"],
            "prohibited_overclaims": ["not official"],
        }
        results = source_verifier.verify_remote(lock, fetcher=lambda _url: content)
        self.assertTrue(results[0]["verified"])
        with self.assertRaises(source_verifier.SourceVerificationError):
            source_verifier.verify_remote(lock, fetcher=lambda _url: b"changed")

    def test_benchmark_matrix_is_deterministic_paired_and_pending(self):
        first = benchmark.build_manifest()
        second = benchmark.build_manifest()
        self.assertEqual(first, second)
        self.assertEqual(len(first["cases"]), 200)
        pair_ids = {item["pair_id"] for item in first["cases"]}
        self.assertEqual(len(pair_ids), 100)
        for pair_id in pair_ids:
            pair = [item for item in first["cases"] if item["pair_id"] == pair_id]
            self.assertEqual({item["arm"] for item in pair}, {"control", "treatment"})
            self.assertEqual({item["blind_label"] for item in pair}, {"A", "B"})
        self.assertEqual(benchmark.validate_manifest(first), [])
        report = benchmark.summarize_manifest(first)
        self.assertEqual(report["evidence_state"], "no_observations")
        self.assertFalse(report["experiment_executed"])
        self.assertFalse(report["claims"]["external_findings_independently_validated"])
        self.assertFalse(report["claims"]["experiment_complete"])

    def test_benchmark_rejects_fake_render_and_full_frame_psnr_proxy(self):
        manifest = benchmark.build_manifest()
        manifest["cases"][0]["result"] = {
            "status": "rendered",
            "artifact_sha256": "",
            "metrics": {"full_frame_psnr": 0.9},
            "notes": "",
        }
        errors = benchmark.validate_manifest(manifest, require_results=True)
        self.assertTrue(any("unregistered metrics" in item for item in errors))
        self.assertTrue(any("artifact_sha256" in item for item in errors))
        self.assertTrue(any("model_metadata" in item for item in errors))

    def test_benchmark_summarizes_only_real_paired_rows(self):
        manifest = benchmark.build_manifest()
        manifest["model_metadata"] = {
            "model": "test-model",
            "model_version": "immutable-build",
            "provider_or_runtime": "test-runtime",
            "node_version": "test-node",
        }
        pair_id = manifest["cases"][0]["pair_id"]
        pair = [item for item in manifest["cases"] if item["pair_id"] == pair_id]
        for item in pair:
            item["result"] = {
                "status": "rendered",
                "artifact_sha256": ("a" if item["arm"] == "control" else "b") * 64,
                "metrics": {"beat_realization_rate": 0.4 if item["arm"] == "control" else 0.8},
                "notes": "",
            }
        treatment_label = next(item["blind_label"] for item in pair if item["arm"] == "treatment")
        manifest["pair_reviews"] = [{"pair_id": pair_id, "preference": treatment_label}]
        self.assertEqual(benchmark.validate_manifest(manifest, require_results=True), [])
        report = benchmark.summarize_manifest(copy.deepcopy(manifest))
        self.assertEqual(report["evidence_state"], "partial_observations")
        self.assertEqual(report["complete_rendered_pairs"], 1)
        metric = report["automatic_or_annotated_metrics"]["metrics"]["beat_realization_rate"]
        self.assertAlmostEqual(metric["unpaired_mean_delta"], 0.4)
        self.assertEqual(report["blinded_human_review"]["counts"]["treatment"], 1)
        self.assertFalse(report["claims"]["external_findings_independently_validated"])

    def test_benchmark_rejects_pre_registration_drift(self):
        manifest = benchmark.build_manifest()
        manifest["cases"][0]["arm_instruction"] = "post-hoc changed treatment"
        errors = benchmark.validate_manifest(manifest)
        self.assertTrue(any("pre-registered field" in item for item in errors))

    def test_config_node_has_stable_custom_type_and_three_modes(self):
        schema = performance.T8PerformanceDirectorConfig.define_schema()
        self.assertEqual(schema.node_id, "T8PerformanceDirectorConfig")
        self.assertEqual(performance.PERFORMANCE_MODES, [
            performance.PERFORMANCE_AUTO,
            performance.PERFORMANCE_STRONG,
            performance.PERFORMANCE_OFF,
        ])
        config = performance.T8PerformanceDirectorConfig.execute(performance.PERFORMANCE_STRONG)[0]
        self.assertEqual(config["schema_version"], performance.PERFORMANCE_CONFIG_SCHEMA)
        self.assertEqual(config["mode"], performance.PERFORMANCE_STRONG)
        self.assertIn("not an official", config["source"]["relationship"])

    def test_invalid_config_is_rejected_and_off_is_exactly_empty(self):
        with self.assertRaises(performance.PerformanceDirectorConfigError):
            performance.resolve_performance_mode({"schema_version": "wrong", "mode": "AUTO"})
        off = performance.build_performance_director_config(performance.PERFORMANCE_OFF)
        self.assertEqual(performance.h3_performance_instruction(off), "")
        self.assertEqual(performance.seedance_performance_instruction(off), "")

    def test_h3_director_preserves_priority_dialogue_and_fixed_count(self):
        rule = performance.h3_performance_instruction(
            None,
            fixed_shot_count=4,
            source_prompt="女人的瞳孔变成金色，她说：“我会回来。”",
        )
        self.assertIn("trigger -> reception -> one primary response -> settled/end state", rule)
        self.assertIn("fixed the shot count at 4", rule)
        self.assertIn("verbatim", rule)
        self.assertIn("never invent dialogue", rule)
        self.assertIn("official H3 contract", rule)
        self.assertIn("HARD CUE BUDGET", rule)
        self.assertIn("no more than three", rule)
        self.assertIn("Protected literal terms: 瞳孔; 金色", rule)
        self.assertIn("Protected quoted text: 我会回来。", rule)
        self.assertLess(len(rule), 4000)

    def test_seedance_director_is_native_and_has_no_h3_serialization_syntax(self):
        rule = performance.seedance_performance_instruction(
            None,
            fixed_shot_count=3,
            source_prompt="镜中少年的瞳孔连续变成金色",
        )
        self.assertIn("fixed exactly 3 shots", rule)
        self.assertIn("native media references", rule)
        self.assertIn("continuously visible transformation", rule)
        self.assertIn("Protected literal terms: 瞳孔; 金色; 镜中", rule)
        for forbidden in ("<d>", "[Shot", "integrated_multimodal_description", "(S1)"):
            self.assertNotIn(forbidden, rule)

    def test_semantic_anchor_guard_detects_neighbor_substitution_and_missing_literals(self):
        source = "少年看向右侧镜子，瞳孔连续变成金色，并说：“别过来。”"
        output = "少年看向左侧镜子，虹膜逐渐变成蓝色。"
        anchors = performance.extract_semantic_anchors(source)
        self.assertEqual(anchors["concrete_terms"], ["瞳孔"])
        self.assertEqual(anchors["colors"], ["金色"])
        self.assertEqual(anchors["directions"], ["右侧"])
        self.assertEqual(anchors["quoted_text"], ["别过来。"])
        risks = performance.semantic_anchor_warnings(source, output, inspector.FAMILY_SEEDANCE)
        codes = {item["code"] for item in risks}
        self.assertEqual(codes, {
            "semantic_exact_text_missing",
            "semantic_anchor_missing",
            "semantic_neighbor_substitution_risk",
        })
        self.assertTrue(all(item["severity"] == "warning" for item in risks))

    def test_semantic_anchor_guard_accepts_preserved_attribute_and_related_context(self):
        source = "镜中少年的瞳孔连续变成金色"
        output = "镜中少年的瞳孔连续变成金色，虹膜边缘保持原色。"
        risks = performance.semantic_anchor_warnings(source, output, inspector.FAMILY_SEEDANCE)
        self.assertEqual(risks, [])

        risky_output = "镜中少年的瞳孔先变亮，金色随后从虹膜中心向外晕开。"
        risky = performance.semantic_anchor_warnings(source, risky_output, inspector.FAMILY_SEEDANCE)
        self.assertEqual([item["code"] for item in risky], ["semantic_neighbor_substitution_risk"])

    def test_semantic_anchor_guard_allows_product_component_detail_when_source_anchor_remains(self):
        source = "冷光沿表壳移动，表盘指针精准推进"
        output = "冷光沿表壳移动并扫过表圈，表盘指针精准推进，秒针平稳扫过刻度"
        self.assertEqual(
            performance.semantic_anchor_warnings(source, output, inspector.FAMILY_H3),
            [],
        )

    def test_density_advisory_counts_cue_channels_per_beat_and_per_character(self):
        dense = "镜头1：她看向门口，眼睑绷紧，呼吸停住，肩膀抬起，手指握紧。"
        dense_codes = {item["code"] for item in performance.performance_risk_warnings(dense, inspector.FAMILY_SEEDANCE)}
        self.assertIn("performance_beat_density", dense_codes)

        balanced_two_person = (
            "镜头1：女人看向门口，呼吸放慢，嘴唇闭合；"
            "男人肩膀下沉，手指握紧，眉头轻收。"
        )
        balanced_codes = {
            item["code"] for item in performance.performance_risk_warnings(
                balanced_two_person,
                inspector.FAMILY_SEEDANCE,
            )
        }
        self.assertNotIn("performance_beat_density", balanced_codes)

    def test_core_message_builders_apply_auto_and_allow_off(self):
        h3_kwargs = dict(
            prompt="她听见消息后沉默",
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
            shot_count=2,
            official_skill_profile=nodes.COMPAT_SKILL_PROFILE,
            creative_preset=nodes.NO_CREATIVE_PRESET,
            case_template=nodes.NO_CASE_TEMPLATE,
        )
        auto_h3 = nodes._build_messages(**h3_kwargs)[0]["content"]
        self.assertIn("PERFORMANCE DIRECTOR", auto_h3)
        off = performance.build_performance_director_config(performance.PERFORMANCE_OFF)
        off_h3 = nodes._build_messages(**h3_kwargs, performance_director_config=off)[0]["content"]
        self.assertNotIn("PERFORMANCE DIRECTOR", off_h3)

        seed_kwargs = dict(
            prompt="她听见消息后沉默",
            task_intent="T2V",
            complexity_mode=seedance.COMPLEXITY_OPTIONS[0],
            duration_seconds=5,
            shot_count=2,
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
        )
        auto_seedance = seedance._build_messages(**seed_kwargs)[0]["content"]
        self.assertIn("PERFORMANCE DIRECTION", auto_seedance)
        off_seedance = seedance._build_messages(**seed_kwargs, performance_director_config=off)[0]["content"]
        self.assertNotIn("PERFORMANCE DIRECTION", off_seedance)

    def test_core_schemas_add_only_optional_connection_before_existing_provider_config(self):
        for cls in (nodes.MiniMaxH3PromptEnhancer, seedance.Seedance20PromptEnhancer):
            schema = cls.define_schema()
            self.assertEqual(schema.inputs[-2].id, "performance_director_config")
            self.assertEqual(schema.inputs[-1].id, "provider_config")

    def test_storyboard_ir_is_additive_and_normalized(self):
        shots = performance.normalize_storyboard_performance_fields([{
            "index": 1,
            "purpose": "建立角色",
            "observable_cues": "肩膀下沉",
        }])
        self.assertEqual(shots[0]["purpose"], "建立角色")
        self.assertEqual(shots[0]["observable_cues"], ["肩膀下沉"])
        for field in performance.PERFORMANCE_IR_DEFAULTS:
            self.assertIn(field, shots[0])
        instruction = performance.storyboard_performance_instruction("Seedance 2.0", None, fixed_shot_count=2)
        self.assertIn("dramatic_trigger", instruction)
        self.assertIn("native natural language", instruction)

    def test_performance_advisories_do_not_reduce_structural_score(self):
        prompt = "\n".join((
            "integrated_multimodal_description: A sad character remains still.",
            "overall_soundscape: quiet room tone",
            "non_diegetic_music: none",
        ))
        _, report_json, _ = inspector.inspect_prompt(prompt, inspector.FAMILY_H3)
        report = json.loads(report_json)
        codes = {item["code"] for item in report["warnings"]}
        self.assertIn("performance_abstract_only", codes)
        self.assertEqual(report["structural_score"], 100)
        advisory = next(item for item in report["warnings"] if item["code"] == "performance_abstract_only")
        self.assertEqual(advisory["severity"], "advisory")
        self.assertIn("evidence_level", advisory)

    def test_prompt_inspector_compares_optional_source_prompt_without_rewriting_output(self):
        source = "镜中少年的瞳孔连续变成金色"
        output = "镜中少年的虹膜连续变成蓝色"
        passthrough, report_json, _ = inspector.inspect_prompt(
            output,
            inspector.FAMILY_SEEDANCE,
            source_prompt=source,
        )
        report = json.loads(report_json)
        codes = {item["code"] for item in report["warnings"]}
        self.assertEqual(passthrough, output)
        self.assertIn("semantic_anchor_missing", codes)
        self.assertIn("semantic_neighbor_substitution_risk", codes)
        self.assertLess(report["structural_score"], 100)

    def test_prompt_inspector_schema_appends_optional_source_socket(self):
        schema = inspector.T8PromptInspector.define_schema()
        self.assertEqual(schema.inputs[-1].id, "source_prompt")
        self.assertTrue(schema.inputs[-1].optional)

    def test_seedance_h3_syntax_leak_remains_a_scoring_warning(self):
        _, report_json, _ = inspector.inspect_prompt(
            "integrated_multimodal_description: character looks at camera",
            inspector.FAMILY_SEEDANCE,
        )
        report = json.loads(report_json)
        leak = next(item for item in report["warnings"] if item["code"] == "seedance_h3_syntax_leak")
        self.assertEqual(leak["severity"], "warning")
        self.assertLess(report["structural_score"], 100)


if __name__ == "__main__":
    unittest.main()
