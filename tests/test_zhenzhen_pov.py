"""POV integration contracts only: CPU, no provider, GGUF or rendered-quality claims."""
from __future__ import annotations

import ast
import copy
import importlib
import json
import re
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
from unittest.mock import Mock, patch

from test_directional_skills import (
    GIT_ROOT, ROOT, execute_inputs, h3, h3_args, original_function, sd, sd_args,
)
import directional_skills as directing
from film_workflow import build_character_performance_bible
from performance_director import (
    PERFORMANCE_AUTO, PERFORMANCE_EXTREME, PERFORMANCE_OFF, PERFORMANCE_STRONG,
    build_performance_director_config,
)


BASELINE = "20689b34b8d4239540bfea933052a9ae8d44a931"
POV = "zhenzhen_pov"
LABEL = "贞贞-POV剧情导演 / Zhenzhen POV"
LEGACY = ("none", "continuous_combat", "high_density_combat", "cinematic_gunfight",
          "ning_wenwu", "drama_scene", "situational_drama")
# Public, package-relative provenance; tests never need the private source directory.
SOURCE_FILES = {
    "SKILL.md": "505376f62aa3a49385cac9aca6b7c8ad00a16edc21af7b4e3637a65edb26eba4",
    "references/directing.md": "30d3976f7ab03222f43db6c82de6a5980f1808e3d9bc64888451e096e4857ff7",
    "references/director-review.md": "6b53473c2a068adabf9d4b79040b74738fb38ab82aababf360a6001f94ecf858",
    "references/h3-adapter.md": "ec53e39c8ae44cadd9b88bcabc0fb0159fbc1bcab2a5a0742e038f6bae5e2aca",
    "references/pov-angles.md": "163fe35602cd7c7f0c9e0df1ebc0fbd13c61c98f7effa50bc50b18b4a9119fc1",
    "references/source-cases.md": "4a6f2184efbb9d457e2050dc8e4532920386d2bf3682598f3b2014d87bbcf471",
    "references/rewrite-examples.md": "5b037d58724aff05c8831fd8fa6dcdfbb0b0c7ee5e0dd7cf4d2fa935b858e84c",
}


@lru_cache(maxsize=None)
def baseline_bytes(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=GIT_ROOT)


@lru_cache(maxsize=1)
def historical_directing():
    module = types.ModuleType("pov_preintegration_directing")
    module.__file__ = str(ROOT / "directional_skills.py")
    module.__package__ = ""
    exec(compile(baseline_bytes("directional_skills.py"), module.__file__, "exec"), vars(module))
    return module


def baseline_builder(filename, module):
    function = original_function(filename, "_build_messages", module, BASELINE)
    # Freeze the directing helpers too; using only today's globals could hide
    # a regression shared by today's and the reconstructed message builder.
    frozen = historical_directing()
    for name in ("prepare_director_skill", "director_instruction", "is_drama_skill",
                 "drama_authoring_instruction", "drama_core_supplement",
                 "coordinated_performance_instruction", "template_fact_lookup"):
        function.__globals__[name] = getattr(frozen, name)
    return function


class OfflineGuards:
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch("requests.sessions.Session.request",
                                       side_effect=AssertionError("No network in POV CPU tests")))
        for module in (h3, sd):
            self.guards.enter_context(patch.object(module, "LocalQwenProvider",
                                                   side_effect=AssertionError("No real GGUF provider")))
        backends = {directing, sys.modules[h3.prepare_director_skill.__module__],
                    sys.modules[sd.prepare_director_skill.__module__]}
        for backend in backends:
            backend._load_resource.cache_clear()
            self.addCleanup(backend._load_resource.cache_clear)


class PovBaselineTests(OfflineGuards, unittest.TestCase):
    def test_old_options_and_source_family_remain_separate_from_new_capability(self):
        self.assertEqual(tuple(directing.DIRECTOR_LABELS.values())[:len(LEGACY) + 1], (*LEGACY, POV))
        self.assertEqual(directing.DIRECTOR_LABELS[LABEL], POV)
        self.assertEqual(directing.DRAMA_SKILLS, {"drama_scene", "situational_drama"})
        self.assertEqual(directing.AUTHORING_SKILLS, directing.DRAMA_SKILLS | {POV})
        self.assertFalse(directing.is_drama_skill(POV))
        self.assertTrue(directing.uses_authoring_contract(POV))
        for skill in LEGACY:
            self.assertEqual(directing.uses_authoring_contract(skill), skill in directing.DRAMA_SKILLS)
        for value in (POV, LABEL, f"  {POV}  "):
            self.assertEqual(directing.normalize_director_skill(value), POV)

    def test_old_resources_and_eight_workflows_keep_baseline_bytes(self):
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", BASELINE, "--", "directional_skills", "example_workflows"],
            cwd=GIT_ROOT, text=True,
        ).splitlines()
        resources = [path for path in paths if path.startswith("directional_skills/")]
        examples = [path for path in paths if path.startswith("example_workflows/directional_") and path.endswith(".json")]
        self.assertEqual(len(examples), 8)
        for path in (*resources, *examples):
            with self.subTest(path=path):
                # Git normalizes text line endings on Windows; compare bytes
                # after only that normalization, not parsed JSON or stripped text.
                self.assertEqual((ROOT / path).read_bytes().replace(b"\r\n", b"\n"),
                                 baseline_bytes(path).replace(b"\r\n", b"\n"))

    def test_old_messages_and_metadata_match_frozen_baseline(self):
        bible = build_character_performance_bible(character_id="A", scene_objective="等待回应",
                                                  obstacle_and_stakes="对方尚未回答", voice_lock="轻声")
        for module, filename, args, target in (
            (h3, "nodes.py", h3_args, "h3"), (sd, "seedance20.py", sd_args, "seedance20"),
        ):
            original = baseline_builder(filename, module)
            for skill in LEGACY:
                for language in ("中文", "English"):
                    for performance in (PERFORMANCE_OFF, PERFORMANCE_EXTREME):
                        for creation in ("off", "causal"):
                            with self.subTest(target=target, skill=skill, language=language,
                                              performance=performance, creation=creation):
                                values = args(director_skill=skill, output_language=language,
                                              performance_director_config=build_performance_director_config(performance),
                                              character_performance_bible=bible, creation_mode=creation, shot_count=1)
                                self.assertEqual(module._build_messages(**values), original(**values))
                self.assertEqual(directing.director_instruction(skill, target),
                                 historical_directing().director_instruction(skill, target))
                for language in ("中文", "English"):
                    values = dict(language=language, mode="普通增强 / Normal" if target == "h3" else "Seedance 2.0", shot_count=1)
                    self.assertEqual(directing.director_metadata(skill, **values),
                                     historical_directing().director_metadata(skill, **values))


class PovResourceTests(OfflineGuards, unittest.TestCase):
    def test_resource_has_pinned_public_provenance_without_private_runtime_dependencies(self):
        text, meta = directing._load_resource(POV)
        self.assertEqual(meta["id"], POV)
        self.assertEqual(meta["version"], "1.0.0")
        self.assertEqual(meta["authoring_revision"], "1.0.0")
        self.assertEqual(meta["source_version"], "1.5.9")
        self.assertEqual(meta["primary_source"], "SKILL.md")
        self.assertEqual(meta["source_files"], SOURCE_FILES)
        self.assertEqual(meta["source_sha256"], SOURCE_FILES["SKILL.md"])
        self.assertTrue((ROOT / "directional_skills" / POV / "NOTICE.md").is_file())
        self.assertLess(len(text.split()), 1500, "Keep this an in-request method, not a copied production manual")
        for forbidden in ("RUNNINGHUB_API_KEY", "$CODEX_HOME", "runninghub_batch.py", "script-review.json", "```", "mpov"):
            self.assertNotIn(forbidden, text)
        public = text + json.dumps(meta, ensure_ascii=False)
        self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", public), "Do not publish personal absolute paths")
        self.assertEqual({path.name for path in (ROOT / "directional_skills" / POV).iterdir()},
                         {"SKILL.md", "meta.json", "NOTICE.md"})

    def test_missing_resource_and_bad_revisions_fail_without_a_fallback(self):
        _, valid = directing._load_resource(POV)
        for failure in ("missing", "resource_revision", "authoring_revision"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                if failure != "missing":
                    child = root / POV
                    child.mkdir()
                    metadata = {**valid, "version" if failure == "resource_revision" else "authoring_revision": "future"}
                    (child / "meta.json").write_text(json.dumps(metadata), encoding="utf-8")
                    (child / "SKILL.md").write_text("test-only method", encoding="utf-8")
                directing._load_resource.cache_clear()
                with patch.object(directing, "_ROOT", root):
                    with self.assertRaises(directing.DirectionalSkillError):
                        directing.prepare_director_skill(POV, 1)
                    self.assertEqual(directing.prepare_director_skill("none", 2), ("none", 2))

    def test_trigger_preservation_is_h3_specific_not_a_shared_resource_default(self):
        self.assertIn("mpov", directing.director_instruction(POV, "h3"))
        seedance = directing.director_instruction(POV, "seedance20")
        for forbidden in ("mpov", "<d>", "subject_definitions:", "[Shot 1]", "(S1)"):
            self.assertNotIn(forbidden, seedance)


class PovMessageTests(OfflineGuards, unittest.TestCase):
    def test_all_h3_modes_keep_native_contracts_and_media_parts(self):
        reference_counts = {"T2VA": 0, "I2VA": 1, "FL2VA": 2, "L2VA": 1, "Ref2VA": 2}
        for task, count in reference_counts.items():
            for language in ("中文", "English"):
                with self.subTest(task=task, language=language):
                    plan = [{"label": f"<Picture {index}>", "kind": "image", "role": "user-assigned reference"}
                            for index in range(1, count + 1)]
                    parts = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,fixture{index}"}}
                             for index in range(count)]
                    values = h3_args(director_skill=POV, task_type=task, output_language=language,
                                     media_plan=plan, media_parts=parts, shot_count=2)
                    frozen = copy.deepcopy(values)
                    messages = h3._build_messages(**values)
                    self.assertIn(h3.TASK_RULES[task], messages[0]["content"])
                    self.assertEqual(messages[0]["content"].count(directing._load_resource(POV)[0]), 1)
                    if parts:
                        self.assertEqual(messages[1]["content"][1:], parts)
                    self.assertEqual(values, frozen)

    def test_seedance_generation_edit_extension_and_trackfill_keep_task_binding(self):
        image = {"label": "@图片1", "kind": "image", "role": "user reference"}
        last = {"label": "@图片2", "kind": "image", "role": "user end frame"}
        video = {"label": "@视频1", "kind": "video", "role": "source video"}
        next_video = {"label": "@视频2", "kind": "video", "role": "next source video"}
        plans = {
            "AUTO": [], "T2V": [], "I2V": [image], "FL-I2V": [image, last],
            "MultiRef": [image, video], "VideoEdit": [video, image],
            "VideoExtend": [video], "TrackFill": [video, next_video], "Combined": [video, image],
        }
        self.assertEqual(set(plans), set(sd.TASK_INTENTS))
        for task in sd.TASK_INTENTS:
            with self.subTest(task=task):
                plan = plans[task]
                messages = sd._build_messages(**sd_args(director_skill=POV, task_intent=task, media_plan=plan))
                self.assertIn(sd.TASK_RULES[task], messages[0]["content"])
                self.assertIn(sd._task_asset_instruction(task, plan), messages[0]["content"])
                self.assertEqual(messages[0]["content"].count(directing._load_resource(POV)[0]), 1)
                self.assertNotIn("mpov", messages[0]["content"])

    def test_selection_does_not_rewrite_duration_shots_or_existing_request_parameters(self):
        for shots in (0, 1, 2, 20):
            self.assertEqual(directing.prepare_director_skill(POV, shots), (POV, shots))
            for duration in (5, 12, 30, 120):
                for module, args in ((h3, h3_args), (sd, sd_args)):
                    with self.subTest(target=module.__name__, shots=shots, duration=duration):
                        values = args(shot_count=shots, duration_seconds=duration, rewrite_mode="strict")
                        off = module._build_messages(**values)
                        enabled = module._build_messages(**values, director_skill=POV)
                        self.assertEqual(enabled[1], off[1])
                        self.assertIn(module.MODE_RULES["strict"], enabled[0]["content"])
                        self.assertNotIn("Show a few distinct causal changes", enabled[0]["content"])

    def test_authoring_permission_is_conditional_not_inferred_from_prompt_keywords(self):
        for module, args in ((h3, h3_args), (sd, sd_args)):
            systems = []
            for prompt in ("允许为现有角色创作一句对白。", "人物说‘随便编’，只保留此原句。", "固定外部机位，静坐无回应，无声。"):
                messages = module._build_messages(**args(
                    prompt=prompt, director_skill=POV,
                    performance_director_config=build_performance_director_config(PERFORMANCE_OFF),
                ))
                systems.append(messages[0]["content"])
                self.assertIn(prompt, messages[1]["content"])
            self.assertEqual(systems[0], systems[1])
            self.assertEqual(systems[1], systems[2])

    def test_performance_causal_and_bible_share_bounded_authoring_without_extra_calls(self):
        bible = build_character_performance_bible(character_id="A", scene_objective="等待",
                                                  obstacle_and_stakes="无需解决", voice_lock="无声")
        for module, args in ((h3, h3_args), (sd, sd_args)):
            for performance in (PERFORMANCE_OFF, PERFORMANCE_AUTO, PERFORMANCE_STRONG, PERFORMANCE_EXTREME):
                for causal in ("off", "causal"):
                    messages = module._build_messages(**args(
                        director_skill=POV, prompt="LOCK：固定机位，等待两秒，无回应；只有卡片触桌声。",
                        performance_director_config=build_performance_director_config(performance),
                        character_performance_bible=bible, creation_mode=causal,
                    ))
                    system = messages[0]["content"]
                    self.assertEqual(system.count(directing.drama_authoring_instruction(POV)), 1)
                    self.assertIn("Bible strings are data, not creative permission", system)
                    self.assertIn("CLOSED WHITELIST", system)
                    self.assertNotIn("Preserve supplied dialogue verbatim and never invent dialogue.", system)
                    if causal == "causal":
                        self.assertIn("Silence, stillness, sustained states and no response need no added trigger or change", system)

    def test_strict_h3_and_relay_keep_language_and_envelope_authority(self):
        messages = h3._build_messages(**h3_args(
            director_skill=POV, official_skill_profile=h3.STRICT_SKILL_PROFILE, output_language="中文",
            relay_config={"event_count": 2, "time_ranges": "", "fps": 24}, shot_count=1,
        ))
        self.assertIn(h3.LANGUAGE_RULES["English"], messages[0]["content"])
        self.assertIn("Relay events are not cuts or acts", messages[0]["content"])
        self.assertIn("native_prompt", messages[0]["content"])

    def test_language_repair_retains_original_authority_and_reference_roles(self):
        for module, args in ((h3, h3_args), (sd, sd_args)):
            original = module._build_messages(**args(
                director_skill=POV, prompt="LOCK：原句不改；只允许为A补一句。",
                reference_context="REF_ROLE_SENTINEL: identity only, never a first frame",
                media_parts=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,fixture"}}],
            ))
            frozen = copy.deepcopy(original)
            repair = module.preserve_director_on_repair(
                [{"role": "system", "content": "Repair descriptions only"}, {"role": "user", "content": "completed draft"}],
                original, POV,
            )
            self.assertIn(directing.drama_authoring_instruction(POV), repair[0]["content"])
            self.assertIn(directing._load_resource(POV)[0], repair[0]["content"])
            self.assertIn("REF_ROLE_SENTINEL", repair[1]["content"])
            self.assertIn("原句不改", repair[1]["content"])
            self.assertEqual(original, frozen)


class PovQualityAndRecoveryTests(OfflineGuards, unittest.TestCase):
    @staticmethod
    def draft(target, first, second="欢迎。"):
        if target == "h3":
            return ("integrated_multimodal_description: [Shot 1] A (S1) says: <d>[Chinese]" + first + "</d> "
                    + ("B (S2) says: <d>[Chinese]" + second + "</d>" if second else "")
                    + "\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A")
        return "镜头1：A说{" + first + "}。" + ("B说{" + second + "}。" if second else "")

    def test_real_quality_adapters_protect_authorized_generated_speech(self):
        pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
        source = "A说原句‘我回来了。’，仅允许B原创一句简短回应。"
        for target, module, args in (("h3", h3, h3_args), ("seedance20", sd, sd_args)):
            messages = module._build_messages(**args(prompt=source, director_skill=POV))
            old = self.draft(target, "我来了。")
            for second, accepted in (("欢迎。", True), ("", False), ("再见。", False)):
                with self.subTest(target=target, second=second):
                    candidate = self.draft(target, "我回来了。", second)
                    complete = Mock(return_value=candidate)
                    kwargs = dict(mode="repair", messages=messages, complete=complete,
                                  language="AUTO", source=source, shot_count=1, director_skill=POV)
                    if target == "h3":
                        kwargs.update(task_type="T2VA", duration=12)
                    run = pipeline.h3_quality_result if target == "h3" else pipeline.seedance_quality_result
                    result, report = run(old, **kwargs)
                    self.assertEqual(result, candidate if accepted else old)
                    self.assertEqual(report["result"], "corrected" if accepted else "candidate_rejected")
                    self.assertEqual(report["correction_calls"], 1)
                    complete.assert_called_once()
                    correction = complete.call_args.args[0]
                    self.assertEqual(correction[:2], messages)
                    self.assertEqual(correction[2], {"role": "assistant", "content": old})
                    self.assertIn("Preserve explicitly authorized generated lines", correction[-1]["content"])

    def test_relay_correction_receives_pov_authority_without_a_new_review_round(self):
        pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
        messages = h3._build_messages(**h3_args(director_skill=POV))
        complete = Mock(side_effect=AssertionError("Inspecting correction construction is not generation"))
        with patch.object(pipeline, "run_quality", return_value=("draft", {})) as run:
            pipeline.h3_quality_result("draft", mode="repair", messages=messages, complete=complete,
                                       task_type="T2VA", duration=12, shot_count=1, language="English", source="",
                                       director_skill=POV, relay_config={"event_count": 2, "time_ranges": ""})
            correction = run.call_args.kwargs["build_correction"](
                messages, "complete Relay draft", {"issues": [{"code": "h3_missing_speaker", "message": "speaker"}]},
            )
        self.assertEqual(correction[:2], messages)
        self.assertIn("Preserve explicitly authorized generated lines", correction[-1]["content"])
        self.assertIn("Relay authoring JSON envelope", correction[-1]["content"])
        complete.assert_not_called()

    def test_failed_quality_correction_keeps_only_the_existing_complete_draft(self):
        pipeline = importlib.import_module(h3.__package__ + ".quality_pipeline")
        draft = self.draft("h3", "我来了。")
        complete = Mock(side_effect=RuntimeError("offline correction failure"))
        result, report = pipeline.h3_quality_result(
            draft, mode="repair", messages=h3._build_messages(**h3_args(director_skill=POV)),
            complete=complete, task_type="T2VA", duration=12, shot_count=1, language="AUTO",
            source="A说原句‘我回来了。’，仅允许B原创一句简短回应。", director_skill=POV,
        )
        self.assertEqual(result, draft)
        self.assertEqual(report["result"], "correction_failed_draft_kept")
        self.assertEqual(report["correction_calls"], 1)
        complete.assert_called_once()

    def test_recovery_preserves_historical_pov_metadata_without_loading_current_selection(self):
        for module, cls, component, completion in (
            (h3, h3.MiniMaxH3PromptEnhancer, "MiniMaxH3PromptEnhancerT8", "enhance_prompt"),
            (sd, sd.Seedance20PromptEnhancer, "Seedance20PromptEnhancerT8", "enhance_seedance20_prompt"),
        ):
            recovery = sys.modules[module.begin_recovery_record.__module__]
            backend = sys.modules[module.prepare_director_skill.__module__]
            slot = "t8-pov-history-" + component
            metadata = directing.director_metadata(POV, language="English",
                                                    mode=h3.NORMAL if module is h3 else "Seedance 2.0", shot_count=1)
            self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
            self.assertEqual(metadata["authoring_revision"], "1.0.0")
            module.begin_recovery_record(component, slot, "test-provider", metadata=metadata)
            outputs = ("original native prompt",)
            module.complete_recovery_record(component, slot, outputs)
            with patch.object(module, completion, side_effect=AssertionError("No generation on recovery")), \
                    patch.object(backend, "_load_resource", side_effect=AssertionError("No current resource needed")):
                result = cls.execute(**execute_inputs(module), director_skill="future_unknown_selection",
                                     recovery_action="restore_last", recovery_slot=slot)
            actual = result["result"] if isinstance(result, dict) else result.result
            expected = (*outputs, "", "", "", 0, "") if module is h3 else outputs
            self.assertEqual(tuple(actual), expected)
            self.assertEqual(recovery.recovery_status(component, slot)["creation_metadata"], metadata)
            filtered = recovery.safe_director_metadata({**metadata, "authoring_revision": "future", "source_version": "private", "prompt": "private"})
            self.assertNotIn("authoring_revision", filtered)
            self.assertNotIn("source_version", filtered)
            self.assertNotIn("prompt", filtered)


class PovCacheTests(OfflineGuards, unittest.IsolatedAsyncioTestCase):
    async def test_installed_comfy_cache_signature_changes_with_pov_and_restores_with_off(self):
        path = ROOT.parents[1] / "comfy_execution" / "caching.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CacheKeySetInputSignature")
        method = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_immediate_node_signature")
        namespace = {"nodes": types.SimpleNamespace(NODE_CLASS_MAPPINGS={"enhancer": object}),
                     "is_link": lambda value: isinstance(value, list) and len(value) == 2,
                     "include_unique_id_in_input": lambda _: False}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
        async def unchanged(_):
            return False
        cache = types.SimpleNamespace(include_node_id_in_input=lambda: False,
                                      is_changed_cache=types.SimpleNamespace(get=unchanged))
        graph = {"node": {"class_type": "enhancer", "inputs": {"seed": 42, "director_skill": "none"}}}
        dynamic = types.SimpleNamespace(has_node=lambda key: key in graph, get_node=lambda key: graph[key])
        signatures = []
        for selection in ("none", POV, "none"):
            graph["node"]["inputs"]["director_skill"] = selection
            signatures.append(await namespace["get_immediate_node_signature"](cache, dynamic, "node", {}))
        self.assertEqual(signatures[0], signatures[2])
        self.assertNotEqual(signatures[0], signatures[1])


if __name__ == "__main__":
    unittest.main()
