"""Pinned-source integration and offline compatibility; not inference quality."""
from __future__ import annotations

import copy
import ast
import re
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

import numpy as np
import directional_skills as directing
from test_directional_skills import GIT_ROOT, ROOT, execute_inputs, h3, h3_args, sd, sd_args
from test_zhenzhen_pov import OfflineGuards
from combat_camera import CAMERA_STRONG, build_combat_camera_config
from performance_director import PERFORMANCE_EXTREME, build_performance_director_config

BASELINE = "62d5440fb8f04924efd1ff18db2490c856bb94c0"
SKILL = "wushu_combat"
LABEL = "Jojocodex-武术打斗 / Wushu combat"


@lru_cache(maxsize=None)
def frozen_bytes(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=GIT_ROOT)


@lru_cache(maxsize=1)
def frozen_directing():
    import types
    module = types.ModuleType("wushu_preintegration_directing")
    module.__file__ = str(ROOT / "directional_skills.py")
    module.__package__ = ""
    exec(compile(frozen_bytes("directional_skills.py"), module.__file__, "exec"), vars(module))
    return module


class WushuIntegrationTests(OfflineGuards, unittest.TestCase):
    def without_legacy_reference_duration_caps(self, function):
        """Allow only the reviewed duration fix; freeze every other validator AST."""
        expected = copy.deepcopy(function)
        duration_assignment = next(
            node for node in expected.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "video_durations" for target in node.targets)
        )
        source_loop = next(
            node for node in expected.body if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name) and node.iter.id == "reference_video_values"
        )
        if function.name == "_validate_inputs":
            append = source_loop.body[-1].value
            self.assertEqual(ast.unparse(append.func), "video_durations.append")
            source_loop.body[-1] = ast.Expr(value=append.args[0])
        else:
            self.assertIsInstance(duration_assignment.value, ast.ListComp)
            source_loop.body.append(ast.Expr(value=duration_assignment.value.elt))
        removed = []
        for node in expected.body:
            if node is duration_assignment:
                removed.append(node)
            elif isinstance(node, ast.For) and ast.unparse(node.iter) == "enumerate(video_durations, start=1)":
                self.assertEqual(ast.unparse(node.body[0].test), "not 2 <= duration <= 15")
                removed.append(node)
            elif isinstance(node, ast.If) and ast.unparse(node.test) == "sum(video_durations) > 15.001":
                removed.append(node)
        self.assertEqual(len(removed), 3)
        expected.body = [node for node in expected.body if node not in removed]
        return expected

    def restore_frozen_reference_tooltip(self, method, path):
        """Only the reviewed video tooltip may differ inside the native schema."""
        current = copy.deepcopy(method)
        changed = 0
        prefix = ("Ref2VA 参考视频" if path == "nodes.py" else "Seedance 2.0 参考/编辑/延长视频")
        new_tooltip = prefix + "：节点不限制单段或合计时长；渠道和模型资源限制仍适用。 / No per-video or total duration cap in this enhancer; provider/model resource limits still apply."
        old_tooltip = ("Ref2VA temporal reference video (2-15 seconds)." if path == "nodes.py"
                       else "Seedance 2.0 完整参考/编辑/延长视频（2-15 秒）。")
        for node in ast.walk(current):
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "io.Video.Input":
                for keyword in node.keywords:
                    if keyword.arg == "tooltip" and isinstance(keyword.value, ast.Constant):
                        self.assertEqual(keyword.value.value, new_tooltip)
                        keyword.value.value = old_tooltip
                        changed += 1
        self.assertEqual(changed, 1)
        return current

    def test_append_only_choices_no_authoring_or_shot_policy_side_effect(self):
        self.assertEqual(tuple(directing.DIRECTOR_LABELS.items()),
                         (*frozen_directing().DIRECTOR_LABELS.items(), (LABEL, SKILL)))
        self.assertEqual(directing.AUTHORING_SKILLS, frozen_directing().AUTHORING_SKILLS)
        self.assertFalse(directing.uses_authoring_contract(SKILL))
        for value in (SKILL, LABEL, "  wushu_combat  "):
            self.assertEqual(directing.normalize_director_skill(value), SKILL)
        for count in (0, 1, 2, 9, 20):
            self.assertEqual(directing.prepare_director_skill(SKILL, count), (SKILL, count))

    def test_old_runtime_schemas_widgets_resources_and_every_example_keep_frozen_bytes(self):
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", BASELINE, "--", "directional_skills", "example_workflows"],
            cwd=GIT_ROOT, text=True,
        ).splitlines()
        paths += ["provider_config.py", "combat_camera.py"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_bytes().replace(b"\r\n", b"\n"),
                                 frozen_bytes(path).replace(b"\r\n", b"\n"))
        # Emotion opt-in wiring intentionally changes H3 / Seedance
        # functions and execute's preflight/metadata. Freeze other methods and
        # all native schemas/signatures, except the exact reviewed reference
        # duration guards/tooltips (covered by test_reference_video_duration).
        for module, path, allowed in ((h3, "nodes.py", {"_build_messages", "_h3_language_repair_messages", "_next_relay_correction", "enhance_prompt"}),
                                      (sd, "seedance20.py", {"_build_messages", "enhance_seedance20_prompt"})):
            previous = ast.parse(frozen_bytes(path))
            current = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            current_by_name = {node.name: node for node in current.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
            for old_node in previous.body:
                if isinstance(old_node, ast.FunctionDef) and old_node.name not in allowed:
                    expected = (self.without_legacy_reference_duration_caps(old_node)
                                if old_node.name in {"_validate_inputs", "_validate_media"} else old_node)
                    self.assertEqual(ast.dump(current_by_name[old_node.name]), ast.dump(expected), old_node.name)
                if isinstance(old_node, ast.ClassDef):
                    new_methods = {node.name: node for node in current_by_name[old_node.name].body if isinstance(node, ast.FunctionDef)}
                    for method in old_node.body:
                        if isinstance(method, ast.FunctionDef):
                            if method.name == "execute":
                                self.assertEqual(ast.dump(new_methods[method.name].args), ast.dump(method.args))
                            else:
                                current_method = (self.restore_frozen_reference_tooltip(new_methods[method.name], path)
                                                  if method.name == "define_schema" else new_methods[method.name])
                                self.assertEqual(ast.dump(current_method), ast.dump(method), method.name)

    def test_old_widget_order_and_ui_are_frozen_except_reviewed_reload_fixes(self):
        # #20 changes configure/serialize hooks intentionally. Keep the widget
        # contract and unrelated node-creation UI frozen, rather than requiring
        # the broken reload implementation to remain byte-for-byte unchanged.
        for path in ("web/js/minimax_h3_prompt_enhancer.js", "web/js/seedance20_prompt_enhancer.js"):
            current = (ROOT / path).read_text(encoding="utf-8")
            previous = frozen_bytes(path).decode("utf-8").replace("\r\n", "\n")
            pattern = r"const SERIALIZED_WIDGET_NAMES = \[[\s\S]*?\];"
            self.assertEqual(re.search(pattern, current).group(), re.search(pattern, previous).group())
            prefix = current.split("nodeType.prototype.onConfigure = function ()")[0]
            self.assertEqual(prefix.replace("    syncNamedWidgetSerialization,\n", ""),
                             previous.split("nodeType.prototype.onConfigure = function ()")[0])
        self.assertTrue((ROOT / "web/js/widget_state.mjs").read_text(encoding="utf-8").startswith(
            frozen_bytes("web/js/widget_state.mjs").decode("utf-8").replace("\r\n", "\n")))

    def test_old_method_messages_match_frozen_helpers_with_camera_and_acting(self):
        from test_directional_skills import original_function
        old = frozen_directing()
        helpers = ("prepare_director_skill", "director_instruction", "is_drama_skill",
                   "drama_authoring_instruction", "drama_core_supplement",
                   "coordinated_performance_instruction", "template_fact_lookup")
        for module, filename, args in ((h3, "nodes.py", h3_args), (sd, "seedance20.py", sd_args)):
            builder = original_function(filename, "_build_messages", module, BASELINE)
            for name in helpers:
                builder.__globals__[name] = getattr(old, name)
            for skill in old.DIRECTOR_LABELS.values():
                for language in ("中文", "English"):
                    for camera in (None, build_combat_camera_config(mode=CAMERA_STRONG)):
                        with self.subTest(platform=filename, skill=skill, language=language, camera=camera):
                            values = args(director_skill=skill, output_language=language, shot_count=1,
                                          combat_camera_config=camera,
                                          performance_director_config=build_performance_director_config(PERFORMANCE_EXTREME))
                            self.assertEqual(module._build_messages(**values), builder(**values))
                target = "h3" if module is h3 else "seedance20"
                self.assertEqual(directing.director_instruction(skill, target), old.director_instruction(skill, target))
                fields = dict(language="中文", mode=h3.NORMAL if module is h3 else "Seedance 2.0", shot_count=2)
                self.assertEqual(directing.director_metadata(skill, **fields), old.director_metadata(skill, **fields))

    def test_resource_provenance_scope_budget_and_native_format_boundary(self):
        text, meta = directing._load_resource(SKILL)
        self.assertEqual(meta["source_author"], "Jojocodex")
        self.assertEqual(meta["source_version"], "2026-09-29b")
        self.assertEqual(meta["source_commit"], "991ddf56ef48badf9018adb2f8b7bdf3f9d5e762")
        self.assertEqual(meta["source_sha256"], "ad4661a01089302783d5be35df4c442afa5e6df0afc4d6583930cd403dd529ca")
        self.assertIn(meta["source_commit"], meta["source_url"])
        self.assertIn("other", meta["source_license_observation"])
        self.assertNotIn("authoring_revision", meta)
        self.assertLessEqual(len(text.split()), 650)
        self.assertEqual({p.name for p in (ROOT / "directional_skills" / SKILL).iterdir()},
                         {"SKILL.md", "meta.json", "NOTICE.md"})
        for required in ("A miss stays a miss", "A defense may hold its ground", "first/last-frame anchors",
                         "unfinished action", "sound whitelists", "Do not add wushu_action", "Solo practice stays solo"):
            self.assertIn(required, text)
        for forbidden in ("```", "subject_definitions:", "<d>", "[Shot 1]", "CFG", "sampler="):
            self.assertNotIn(forbidden, text)
        for target in ("h3", "seedance20"):
            rule = directing.director_instruction(SKILL, target)
            self.assertEqual(rule.count(text), 1)
            self.assertNotIn("Show a few distinct causal changes", rule)
            self.assertIn("stillness, non-response", rule)
            self.assertIn("This check is internal", rule)
        seedance = directing.director_instruction(SKILL, "seedance20")
        for forbidden in ("subject_definitions:", "<d>", "(S1)", "[Shot 1]"):
            self.assertNotIn(forbidden, seedance)

    def test_h3_modes_and_seedance_tasks_preserve_media_and_constraints(self):
        text = directing._load_resource(SKILL)[0]
        pressure = "LOCK: wait two seconds, keep fixed camera; do not add contact, blood, weapons or a winner."
        for module, args, tasks in ((h3, h3_args, h3.TASK_RULES), (sd, sd_args, sd.TASK_INTENTS)):
            for task in tasks:
                for language in ("中文", "English"):
                    with self.subTest(platform=module.__name__, task=task, language=language):
                        if module is h3:
                            count = {"T2VA": 0, "I2VA": 1, "FL2VA": 2, "L2VA": 1, "Ref2VA": 2}[task]
                            roles = {"I2VA": "first frame", "L2VA": "last frame"}
                            plan = [{"label": f"<Picture {i + 1}>", "kind": "image",
                                     "role": ("first frame" if i == 0 else "last frame") if task == "FL2VA"
                                     else roles.get(task, "identity only")} for i in range(count)]
                        else:
                            image = {"label": "@图片1", "kind": "image", "role": "user reference"}
                            end = {"label": "@图片2", "kind": "image", "role": "last frame"}
                            video = {"label": "@视频1", "kind": "video", "role": "source video"}
                            plan = {"AUTO": [], "T2V": [], "I2V": [image], "FL-I2V": [image, end],
                                    "MultiRef": [image, video], "VideoEdit": [video, image],
                                    "VideoExtend": [video], "TrackFill": [video], "Combined": [video, image]}[task]
                        parts = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,fixture{i}"}}
                                 for i in range(sum(p["kind"] == "image" for p in plan))]
                        values = args(director_skill=SKILL, output_language=language, duration_seconds=30,
                                      shot_count=2, prompt=pressure, constraints=pressure, media_plan=plan, media_parts=parts)
                        values["task_type" if module is h3 else "task_intent"] = task
                        original = copy.deepcopy(values)
                        messages = module._build_messages(**values)
                        self.assertIn(module.TASK_RULES[task], messages[0]["content"])
                        self.assertEqual(messages[0]["content"].count(text), 1)
                        user = messages[1]["content"]
                        if parts:
                            self.assertEqual(user[1:], parts)
                        self.assertIn(pressure, user[0]["text"] if isinstance(user, list) else user)
                        self.assertEqual(values, original)

    def test_bad_resource_fails_before_upload_provider_or_recovery_mutation(self):
        _, good = directing._load_resource(SKILL)
        for module, cls, upload in ((h3, h3.MiniMaxH3PromptEnhancer, "_upload_media_plan"),
                                    (sd, sd.Seedance20PromptEnhancer, "_upload_seedance20_media_plan")):
            backend = sys.modules[module.prepare_director_skill.__module__]
            for failure in ("missing", "json", "mapping", "id", "version", "empty"):
                with self.subTest(platform=module.__name__, failure=failure), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    child = root / SKILL
                    if failure != "missing":
                        child.mkdir()
                        meta = {**good, **({failure: "wrong"} if failure in {"id", "version"} else {})}
                        raw = "{" if failure == "json" else "[]" if failure == "mapping" else json.dumps(meta)
                        (child / "meta.json").write_text(raw, encoding="utf-8")
                        (child / "SKILL.md").write_text("" if failure == "empty" else "test-only rule", encoding="utf-8")
                    for api_mode in (module.SEEDANCE_API_MODE, module.LOCAL_QWEN_API_MODE):
                        backend._load_resource.cache_clear()
                        with ExitStack() as stack:
                            stack.enter_context(patch.object(backend, "_ROOT", root))
                            guards = [stack.enter_context(patch.object(module, name)) for name in
                                      (upload, "LocalQwenProvider", "_provider_config", "begin_recovery_record")]
                            inputs = execute_inputs(module)
                            inputs.update(api_mode=api_mode, director_skill=SKILL,
                                          first_frame=np.zeros((1, 16, 16, 3), dtype=np.float32))
                            inputs["task_type" if module is h3 else "task_intent"] = "I2VA" if module is h3 else "I2V"
                            error = h3.PromptEnhancerError if module is h3 else sd.Seedance20PromptEnhancerError
                            with self.assertRaises(error) as caught:
                                cls.execute(**inputs)
                            self.assertNotIn(tmp, str(caught.exception))
                            for guard in guards:
                                guard.assert_not_called()
                            self.assertEqual(backend.prepare_director_skill("none", 2), ("none", 2))

    def test_nine_review_pressure_cases_retain_requests_not_prove_model_obedience(self):
        cases = (
            ("solo_still", "单人守门，保持静止，无回应，固定机位，门仍关闭。"),
            ("multiple_exchanges", "两人10秒连续徒手攻防，指定10次回应，不加招数，不强制停顿。"),
            ("near_miss", "A出拳打空，不增加接触或命中声，沿原转身继续动作。"),
            ("stable_block", "B站稳格挡，不后退，不流血，不产生位移。"),
            ("authorized_magic", "允许原角色用已有剑发出一次蓝色剑光；不可增加其他能力或声音。"),
            ("no_armor", "两人只穿原有衣服，袖口不是装备；不加盔甲、护具或武器。"),
        )
        for case, source in cases:
            for module, args in ((h3, h3_args), (sd, sd_args)):
                with self.subTest(case=case, platform=module.__name__):
                    values = args(prompt=source, constraints=source, director_skill=SKILL,
                                  shot_count=1, duration_seconds=10,
                                  combat_camera_config=build_combat_camera_config(mode=CAMERA_STRONG),
                                  performance_director_config=build_performance_director_config(PERFORMANCE_EXTREME))
                    before = copy.deepcopy(values)
                    messages = module._build_messages(**values)
                    self.assertIn(source, messages[1]["content"])
                    self.assertIn(directing._load_resource(SKILL)[0], messages[0]["content"])
                    self.assertEqual(values, before)
        for task, source, roles in (
            ("Ref2VA", "两张图仅绑定红袖和蓝袖身份；不是首帧，不增加其他人。", ("red identity", "blue identity")),
            ("FL2VA", "由首帧动作接到尾帧站姿；尾帧双脚着地，原剑仍右手持有。", ("first frame", "last frame")),
        ):
            with self.subTest(case=task):
                parts = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{i}"}} for i in range(2)]
                plan = [{"label": f"<Picture {i + 1}>", "kind": "image"} for i in range(2)]
                # H3's actual public role supplement is reference_context;
                # arbitrary role keys inside a media plan are not an API.
                context = "\n".join(f"{p['label']}: {role}" for p, role in zip(plan, roles))
                values = h3_args(prompt=source, constraints=source, director_skill=SKILL, task_type=task,
                                 media_plan=plan, media_parts=parts, shot_count=1, reference_context=context)
                before = copy.deepcopy(values)
                messages = h3._build_messages(**values)
                self.assertIn(source, messages[1]["content"][0]["text"])
                self.assertEqual(messages[1]["content"][1:], parts)
                for role in roles:
                    self.assertIn(role, messages[1]["content"][0]["text"])
                for part in plan:
                    self.assertIn(part["label"], messages[1]["content"][0]["text"])
                self.assertEqual(values, before)
        relay = {"event_count": 3, "time_ranges": "0-3\n3-6\n6-9"}
        source = "9秒一镜到底，三个动作事件，不切镜，最后保持原站姿。"
        values = h3_args(prompt=source, constraints=source, director_skill=SKILL,
                         relay_config=relay, duration_seconds=9, shot_count=1)
        before = copy.deepcopy(values)
        messages = h3._build_messages(**values)
        self.assertIn(h3.relay_instruction(9, 3, relay["time_ranges"], "T2VA"), messages[0]["content"])
        self.assertIn("Relay events are not camera cuts", messages[0]["content"])
        self.assertIn(source, messages[1]["content"])
        self.assertEqual(directing.prepare_director_skill(SKILL, 1), (SKILL, 1))
        self.assertEqual(values, before)

    def test_repair_and_restore_keep_original_method_without_regeneration(self):
        for module, cls, args, completion in ((h3, h3.MiniMaxH3PromptEnhancer, h3_args, "enhance_prompt"),
                                              (sd, sd.Seedance20PromptEnhancer, sd_args, "enhance_seedance20_prompt")):
            messages = module._build_messages(**args(director_skill=SKILL, shot_count=1,
                combat_camera_config=build_combat_camera_config(mode=CAMERA_STRONG)))
            repair = [{"role": "system", "content": "language only"}, {"role": "user", "content": "draft"}]
            repaired = directing.preserve_director_on_repair(repair, messages, SKILL)
            self.assertIn(directing._load_resource(SKILL)[0], repaired[0]["content"])
            self.assertIn("COMBAT CAMERA", repaired[0]["content"])
            self.assertEqual(repair[0]["content"], "language only")
            recovery = sys.modules[module.begin_recovery_record.__module__]
            component = cls.define_schema().node_id
            slot = "t8-wushu-contract-" + component
            metadata = directing.director_metadata(SKILL, language="中文",
                                                   mode=h3.NORMAL if module is h3 else "Seedance 2.0", shot_count=2)
            self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
            self.assertEqual(recovery.safe_director_metadata({**metadata, "prompt": "PRIVATE", "authoring_revision": "1.0.0"}), metadata)
            module.begin_recovery_record(component, slot, "test-provider", metadata=metadata)
            module.complete_recovery_record(component, slot, ("original native result",))
            backend = sys.modules[module.prepare_director_skill.__module__]
            with patch.object(module, completion) as generate, patch.object(backend, "_load_resource") as load:
                result = cls.execute(**execute_inputs(module), director_skill="future_unknown",
                                     recovery_action="restore_last", recovery_slot=slot)
            outputs = result["result"] if isinstance(result, dict) else result.result
            self.assertEqual(outputs[0], "original native result")
            generate.assert_not_called()
            load.assert_not_called()
            self.assertEqual(recovery.recovery_status(component, slot)["creation_metadata"], metadata)


if __name__ == "__main__":
    unittest.main()
