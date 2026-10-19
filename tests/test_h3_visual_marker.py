"""CPU authoring contracts. No model/video-benefit or downstream-binding claims."""
import asyncio
import ast
import copy
import importlib
import inspect
import json
import sys
import subprocess
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import numpy as np
import torch

from test_directional_skills import (h3, sd, h3_args, execute_inputs, original_function,
    primary_text, local_parameters, RecordingLocalProvider, ROOT, GIT_ROOT)
from test_nodes import FakeSession, reference_output
from visual_marker_fixture import material, change_record, canonical

vm = importlib.import_module(h3.__package__ + ".h3_visual_marker")
recovery = sys.modules[h3.begin_recovery_record.__module__]
BASELINE = "794e4b2bfde346df41d5a4459bf7172319007110"


def config(plan=None, selector=0):
    return vm.build_visual_marker_config(vm.ON, selector, plan or material())


def media(plan, **changes):
    entry = dict(kind="image", label="<Picture 1>", value=plan.marked_image[0])
    entry.update(changes)
    return [entry]


class VisualMarkerTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("No external network")))
        self.guards.enter_context(patch.object(h3, "LocalQwenProvider", side_effect=AssertionError("No model load")))

    def enhance(self, plan, **changes):
        args = dict(prompt="Keep the woman's identity; walk through the doorway without stopping.",
            task_type="Ref2VA", reference_images={"reference_image_1": plan.marked_image},
            visual_marker_config=config(plan), output_language="English", api_key="test-placeholder")
        args.update(changes)
        return h3.enhance_prompt(**args)

    def test_schema_default_off_lazy_and_linked_int_validation(self):
        node = vm.T8H3VisualMarkerConfig
        schema = node.define_schema()
        self.assertEqual([x.id for x in schema.inputs], ["mode", "picture_selector", "marker_plan"])
        self.assertEqual(vm.resolve_visual_marker_config(node.execute()[0]), None)
        self.assertEqual(node.execute(marker_plan=object(), picture_selector=999)[0], node.execute()[0])
        self.assertEqual(node.check_lazy_status(mode=vm.OFF, marker_plan=None), [])
        self.assertEqual(node.check_lazy_status(mode=vm.ON, marker_plan=None), ["marker_plan"])
        self.assertEqual(node.check_lazy_status(mode=vm.ON), [])
        self.assertIs(node.validate_inputs(mode=None, picture_selector=None), True)
        for value in (True, 1.5, -1, 12, "1"):
            self.assertIsNot(node.validate_inputs(picture_selector=value), True)
            with self.assertRaises(ValueError):
                config(selector=value)
        with self.assertRaises(ValueError):
            node.execute(mode=vm.ON)
        self.assertEqual(h3.MiniMaxH3PromptEnhancer.check_lazy_status(visual_marker_config=None), ["visual_marker_config"])
        self.assertEqual(h3.MiniMaxH3PromptEnhancer.check_lazy_status(visual_marker_config=None, recovery_action="restore_last"), [])

    def test_foreign_data_fields_not_class_identity_or_methods(self):
        plan = material()
        # Deliberately an unrelated class; no producer import or verify call.
        class Foreign:
            def verify(self):
                raise AssertionError("Never call foreign code")
        obj = Foreign()
        obj.__dict__.update(vars(plan))
        actual = config(obj)
        self.assertEqual(actual, config(plan))
        self.assertNotIn("marked_image", actual)
        self.assertNotIn("clean_image", actual)
        with self.assertRaises(ValueError):
            vm.build_visual_marker_config(vm.ON, 0, plan.record_json)

    def test_source_and_geometry_validation_and_sanitized_errors(self):
        mutations = [lambda r: r.update(schema="PRIVATE"), lambda r: r.update(extra="PRIVATE"),
            lambda r: r.update(binding_verified=True), lambda r: r.update(native_picture_ordinal=1),
            lambda r: r.update(coordinate_space="PRIVATE"),
            lambda r: r["spec"]["markers"][0].update(xyxy=[0, 0, 0, 1]),
            lambda r: r["spec"]["markers"][0].update(xyxy=[False, 0, 1, 1]),
            lambda r: r["spec"]["markers"][0].update(xyxy=[10**1000, 0, 1, 1]),
            lambda r: r["spec"]["markers"][0].update(role_id=None),
            lambda r: r["spec"]["markers"][1].update(marker_id="actor_A"),
            lambda r: r["spec"]["relations"][0].update(target_marker_id="PRIVATE"),
            lambda r: r["spec"]["relations"][0].update(extra="PRIVATE"),
            lambda r: r["spec"]["markers"][0].update(color_rgb="#ffffff"),
            lambda r: r.update(pixel_rectangles=[]), lambda r: r["marked_rgb"].update(bytes=1),
            lambda r: r.update(warnings=["x"*257]), lambda r: r.update(source_dimensions=[1, 1])]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError) as caught:
                config(change_record(material(), mutate))
            self.assertNotIn("PRIVATE", str(caught.exception))
        for raw in ('{"schema":1,"schema":2}', '{"v":NaN}', "x"*(vm.MAX_RECORD_BYTES+1)):
            plan = material()
            plan.record_json = raw
            with self.assertRaises(ValueError):
                config(plan)
        plan = change_record(material(), lambda r: r["spec"]["markers"][0].update(description="changed"), resign=False)
        with self.assertRaisesRegex(ValueError, "digest"):
            config(plan)
        for value in (False, 0.0):
            plan = change_record(material(rendered=True), lambda r: r["pixel_rectangles"][0]["source_pixel_xyxy"].__setitem__(0, value))
            with self.assertRaisesRegex(ValueError, "Pixel rectangles"):
                config(plan)

    def test_actual_pixels_and_clean_provenance_checked(self):
        for rendered in (False, True):
            plan = material(rendered=rendered)
            config(plan)
            plan.marked_image[0, 0, 0, 0] = .9
            with self.assertRaisesRegex(ValueError, "pixels"):
                config(plan)
        plan = material(rendered=True)
        plan.clean_image[0, 0, 0, 0] = .7
        with self.assertRaisesRegex(ValueError, "Clean"):
            config(plan)
        for bad in (torch.zeros(1, 32, 48, 4), torch.full((1,32,48,3), float("nan")), torch.zeros(1,32,48,3,dtype=torch.float16)):
            plan = material()
            plan.marked_image = bad
            with self.assertRaises(ValueError):
                config(plan)

    def test_handdrawn_same_role_color_shared_target_duplicate_edges_legal(self):
        plan = material()
        def edit(r):
            actor = {**r["spec"]["markers"][0], "marker_id": "actor_B"}
            r["spec"]["markers"].append(actor)
            r["pixel_rectangles"].append(dict(marker_id="actor_B", source_pixel_xyxy=None, geometry_observation="unobserved"))
            r["spec"]["relations"].append({**r["spec"]["relations"][0], "actor_marker_id": "actor_B"})
            r["spec"]["relations"].append(dict(r["spec"]["relations"][0]))
        change_record(plan, edit)
        _, evidence = vm.bind_visual_marker(config(plan), media(plan), "Ref2VA")
        self.assertEqual(len(json.loads(evidence.evidence_json)["relations"]), 3)
        self.assertTrue({"hand_drawn_unobserved", "shared_role", "shared_actor_color", "shared_target"} <= set(evidence.warning_codes))

    def test_unique_exact_match_selector_and_hybrid_keyframe_warning(self):
        plan = material()
        items = [dict(kind="image", label="<Picture 1>", value=plan.marked_image[0], role="first_frame"),
                 dict(kind="image", label="<Picture 2>", value=torch.zeros(32,48,3), role="reference_image"),
                 dict(kind="image", label="<Picture 3>", value=plan.marked_image[0], role="reference_image")]
        frozen, evidence = vm.bind_visual_marker(config(plan), items, "Hybrid")
        self.assertEqual(evidence.picture, 3)
        self.assertIn("marker_also_keyframe", evidence.warning_codes)
        self.assertIs(frozen[0], items[0])
        duplicate = [*items, {**items[-1], "label": "<Picture 4>"}]
        with self.assertRaisesRegex(ValueError, "Multiple"):
            vm.bind_visual_marker(config(plan), duplicate, "Hybrid")
        self.assertEqual(vm.bind_visual_marker(config(plan, 4), duplicate, "Hybrid")[1].picture, 4)
        for selector in (1, 2, 5):
            with self.assertRaises(ValueError):
                vm.bind_visual_marker(config(plan, selector), items, "Hybrid")
        with self.assertRaises(ValueError):
            vm.bind_visual_marker(config(plan), media(plan, value=torch.zeros(32,48,3)), "Ref2VA")

    def test_request_pixels_are_independent_and_plan_order_not_changed(self):
        plan = material()
        items = media(plan)
        frozen, evidence = vm.bind_visual_marker(config(plan), items, "Ref2VA")
        before = frozen[0]["value"].copy()
        plan.marked_image.fill_(0)
        np.testing.assert_array_equal(frozen[0]["value"], before)
        self.assertFalse(frozen[0]["value"].flags.writeable)
        self.assertTrue(torch.equal(items[0]["value"], torch.zeros(32,48,3)))
        self.assertFalse(json.loads(evidence.evidence_json)["downstream_verified"])

    def test_no_duration_limit_and_ref_batch_matches_actual_third_picture(self):
        plan = material()
        batch = torch.cat([torch.zeros_like(plan.marked_image), plan.marked_image], 0)
        session = FakeSession(reference_output())
        self.enhance(plan, session=session, duration_seconds=3600,
            reference_images={"reference_image_7": batch, "reference_image_1": torch.ones_like(plan.marked_image)})
        messages = session.chat_requests[0]["json"]["messages"]
        self.assertEqual(len(session.chat_requests), 1)
        self.assertEqual(len(session.uploads), 3)
        data = primary_text(messages[1]["content"])
        self.assertIn('"picture":"<Picture 3>"', data)
        self.assertIn("3600", data)
        self.assertEqual(messages[0]["content"].count(vm.RULE_MARKER), 1)

    def test_none_off_messages_match_release_all_old_tasks(self):
        old = original_function("nodes.py", "_build_messages", h3, BASELINE)
        for task in h3.TASK_TYPES:
            for lang in ("中文", "English"):
                values = h3_args(task_type=task, output_language=lang)
                for off in (None, vm.build_visual_marker_config()):
                    self.assertEqual(h3._build_messages(**values, visual_marker_config=off), old(**values))

    def test_normal_old_calls_and_new_three_cloud_paths(self):
        plan = material()
        for mode in (h3.SEEDANCE_API_MODE, h3.AI_WORKSHOP_API_MODE, h3.OPENAI_API_MODE):
            for active in (False, True):
                session = FakeSession(reference_output())
                self.enhance(plan, api_mode=mode, openai_base_url="https://example.invalid/v1", custom_model="fixture",
                    session=session, visual_marker_config=config(plan) if active else vm.build_visual_marker_config())
                self.assertEqual(len(session.chat_requests), 1)
                messages = session.chat_requests[0]["json"]["messages"]
                self.assertEqual(vm.RULE_MARKER in messages[0]["content"], active)
                self.assertEqual(vm.EVIDENCE_MARKER in primary_text(messages[1]["content"]), active)

    def test_local_budget_and_actual_messages_have_same_evidence(self):
        plan = material()
        providers = []
        def factory(settings, *, vision):
            self.assertTrue(vision)
            p = RecordingLocalProvider(settings, vision=vision, responses=[reference_output()])
            providers.append(p)
            return p
        with patch.object(h3, "LocalQwenProvider", side_effect=factory), patch.object(h3, "_build_messages", wraps=h3._build_messages) as builds:
            self.enhance(plan, api_mode=h3.LOCAL_QWEN_API_MODE, **local_parameters(h3))
        self.assertEqual(builds.call_count, 2)
        a, b = [call.kwargs["visual_marker_config"] for call in builds.call_args_list]
        self.assertIs(a, b)
        self.assertEqual(len(providers[0].calls), 1)
        self.assertEqual(primary_text(providers[0].calls[0]["messages"][1]["content"]).count(vm.EVIDENCE_MARKER), 1)

    def test_preflight_errors_never_call_provider_or_replace_cache(self):
        plan = material()
        slot = "marker-preflight-test"
        h3.begin_recovery_record("MiniMaxH3PromptEnhancerT8", slot, "fixture")
        recovery.complete_recovery_record("MiniMaxH3PromptEnhancerT8", slot, ("old paid draft",))
        before = recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot)
        with patch.object(h3, "enhance_prompt", side_effect=AssertionError("Must preflight")):
            with self.assertRaises(h3.PromptEnhancerError):
                h3.MiniMaxH3PromptEnhancer.execute(**{**execute_inputs(h3), "task_type": "Ref2VA"},
                    reference_images={"reference_image_1": torch.zeros_like(plan.marked_image)},
                    visual_marker_config=config(plan), recovery_slot=slot)
        self.assertEqual(recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot), before)
        for task, relay in (("I2VA", False), ("Ref2VA", True)):
            with self.assertRaisesRegex(ValueError, "Normal"):
                vm.bind_visual_marker(config(plan), media(plan), task, relay=relay)
        change_record(plan, lambda r: r["spec"]["relations"][0].update(action="sk-"+"a"*40))
        with self.assertRaisesRegex(h3.PromptEnhancerError, "API-key-like"):
            self.enhance(plan, session=FakeSession("must not run"))

    def test_restore_ignores_today_config_and_preserves_finite_metadata(self):
        plan = material()
        _, ev = vm.bind_visual_marker(config(plan), media(plan), "Ref2VA")
        metadata = vm.visual_marker_metadata(ev)
        self.assertEqual(recovery.safe_director_metadata(metadata), metadata)
        polluted = copy.deepcopy(metadata)
        polluted["h3_visual_marker"]["private"] = "PRIVATE"
        self.assertNotIn("PRIVATE", str(recovery.safe_director_metadata(polluted)))
        for old_on in (False, True):
            slot = "marker-restore-"+str(old_on)
            h3.begin_recovery_record("MiniMaxH3PromptEnhancerT8", slot, "fixture", metadata=metadata if old_on else None)
            recovery.complete_recovery_record("MiniMaxH3PromptEnhancerT8", slot, ("original native draft",))
            before = recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot)
            with patch.object(h3, "enhance_prompt", side_effect=AssertionError("Restore must not regenerate")):
                result = h3.MiniMaxH3PromptEnhancer.execute(**execute_inputs(h3), recovery_slot=slot,
                    recovery_action="restore_last", visual_marker_config={"malformed": "today"})
            self.assertEqual(result[0], "original native draft")
            self.assertEqual(recovery.recovery_status("MiniMaxH3PromptEnhancerT8", slot), before)

    def test_repair_explicit_activation_idempotence_and_no_media_reupload(self):
        plan = material()
        cfg = config(plan)
        values = h3_args(task_type="Ref2VA", media_plan=media(plan),
            media_parts=[dict(type="image_url", image_url={"url": "PRIVATE_MEDIA"})])
        original = h3._build_messages(**values, visual_marker_config=cfg)
        for active in (None, cfg):
            repair = h3._h3_language_repair_messages("draft", "English", None, original,
                                                   visual_marker_config=active)
            self.assertEqual(vm.RULE_MARKER in str(repair), active is not None)
            self.assertNotIn("PRIVATE_MEDIA", str(repair))
            self.assertEqual(vm.preserve_visual_marker_on_repair(repair, original, active), repair)
        for module in (sd,):
            self.assertNotIn("visual_marker_config", inspect.signature(module.enhance_seedance20_prompt).parameters)

    def test_append_only_interface_and_non_h3_nodes_unmodified(self):
        for name in ("enhance_prompt", "_build_messages"):
            old = inspect.signature(original_function("nodes.py", name, h3, BASELINE))
            now = inspect.signature(getattr(h3, name))
            self.assertEqual(list(now.parameters)[-1], "visual_marker_config")
            self.assertEqual(now.replace(parameters=list(now.parameters.values())[:-1]), old)
        schema = h3.MiniMaxH3PromptEnhancer.define_schema()
        tree = ast.parse(subprocess.check_output(["git", "show", BASELINE+":nodes.py"], cwd=GIT_ROOT).decode("utf-8"))
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MiniMaxH3PromptEnhancer")
        method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "define_schema")
        method.decorator_list = []
        namespace = dict(vars(h3))
        exec(compile(ast.Module(body=[method], type_ignores=[]), "nodes.py", "exec"), namespace)
        old_schema = namespace["define_schema"](h3.MiniMaxH3PromptEnhancer)
        self.assertEqual([x.as_dict() for x in schema.inputs[:-1]], [x.as_dict() for x in old_schema.inputs])
        self.assertEqual([x.as_dict() for x in schema.outputs], [x.as_dict() for x in old_schema.outputs])
        for path in ("seedance20.py", "moss_image.py", "music3.py", "yue2.py", "qwen_image21.py",
                     "web/js/minimax_h3_prompt_enhancer.js"):
            old = subprocess.check_output(["git", "show", BASELINE+":"+path], cwd=GIT_ROOT)
            self.assertEqual((ROOT/path).read_bytes().replace(b"\r\n", b"\n"), old.replace(b"\r\n", b"\n"), path)
        self.assertEqual([x.id for x in schema.inputs][-2:], ["storyboard_director_config", "visual_marker_config"])
        self.assertEqual(len(schema.outputs), 6)
        package = sys.modules[h3.__package__]
        extension = asyncio.run(package.comfy_entrypoint())
        nodes = asyncio.run(extension.get_node_list())
        self.assertEqual(len(nodes), 34)
        self.assertEqual(nodes[-2].define_schema().node_id, "T8H3VisualMarkerConfig")
        self.assertEqual(nodes[-1].define_schema().node_id, "T8H3SpatialMarkerCanvas")
        for node in nodes:
            if node is not h3.MiniMaxH3PromptEnhancer:
                self.assertNotIn("visual_marker_config", [i.id for i in node.define_schema().inputs])

    def test_quality_source_does_not_lock_json_syntax_or_action_language(self):
        quality = importlib.import_module(h3.__package__ + ".h3_quality")
        plan = material()
        _, evidence = vm.bind_visual_marker(config(plan), media(plan), "Ref2VA")
        self.assertEqual(vm.visual_marker_literal_contract(evidence).literals, ())
        change_record(plan, lambda r: r["spec"]["relations"][0].update(action='She says “Wait for me.” then walks through.'))
        _, evidence = vm.bind_visual_marker(config(plan), media(plan), "Ref2VA")
        literals = vm.visual_marker_literal_contract(evidence).literals
        self.assertEqual([p.text for p in literals], ["Wait for me."])
        events = []
        self.enhance(material(), session=FakeSession(reference_output(False)), quality_mode="质量检查 / Check",
                     progress_callback=lambda stage, **metrics: events.append(metrics))
        self.assertNotIn("semantic_exact_text_missing", str(events))

    def test_combined_storyboard_speech_hybrid_repair_keeps_evidence_once(self):
        from test_speech_integration import reference
        storyboard = importlib.import_module(h3.__package__ + ".storyboard_director")
        plan = material()
        cfg = config(plan)
        story = storyboard.build_storyboard_director_config(storyboard.STORYBOARD_ON)
        values = h3_args(task_type="Hybrid", media_plan=[dict(kind="image", label="<Picture 1>", role="first_frame", value=torch.zeros(32,48,3)),
            dict(kind="image",label="<Picture 2>",role="reference_image",value=plan.marked_image[0])],
            storyboard_director_config=story, speech_reference=reference())
        original = h3._build_messages(**values, visual_marker_config=cfg)
        repair = h3._h3_language_repair_messages("draft", "English", None, original,
            storyboard_director_config=story, visual_marker_config=cfg)
        self.assertEqual(str(repair).count(vm.RULE_MARKER),1)
        self.assertEqual(str(repair).count(vm.EVIDENCE_MARKER),1)
        self.assertIn("<Picture 2>",str(repair))
        self.assertIn("等我回来",str(repair))


class MarkerStrataLoopbackTests(unittest.TestCase):
    def test_strata_owned_http_on_off_and_preflight(self):
        from test_strata_provider import http_fixture
        response = {"model":"model-test","choices":[{"finish_reason":"stop","message":{"content":reference_output(False)}}]}
        plan = material()
        with http_fixture(response=response) as (url,seen):
            values = dict(prompt="Walk through the door without stopping.",task_type="Ref2VA",output_language="English",
                reference_images={"reference_image_0":plan.marked_image},api_mode=h3.STRATA_API_MODE,
                provider_request_options={"strata_settings":{"url":url}})
            for active in (False, True):
                h3.enhance_prompt(**values,visual_marker_config=config(plan) if active else vm.build_visual_marker_config())
                posts = [s for s in seen if s[0]=="POST"]
                self.assertEqual(len(posts),2 if active else 1)
                self.assertEqual(vm.RULE_MARKER in str(posts[-1][3]),active)
            count = len(seen)
            with self.assertRaises(h3.PromptEnhancerError):
                h3.enhance_prompt(**{**values,"reference_images":{"reference_image_0":torch.zeros_like(plan.marked_image)}},visual_marker_config=config(plan))
            self.assertEqual(len(seen),count)


if __name__ == "__main__":
    unittest.main()
