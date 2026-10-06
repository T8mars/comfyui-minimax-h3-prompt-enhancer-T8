"""Hybrid contracts, real CPU media and isolated transports (not inference)."""
import ast
import copy
import json
import io
import hashlib
import subprocess
import unittest
from unittest.mock import patch

import numpy as np
import requests
from test_local_qwen import nodes, FakeLocalProvider, NativeVideo, encoded_video_bytes
from test_nodes import FakeSession, FakeVideo, reference_output
from test_directional_skills import ROOT, GIT_ROOT, original_function, h3_args, execute_inputs
from h3_hybrid import HYBRID, HYBRID_ALIASES, HYBRID_MARKER, asset_roles, hybrid_metadata
from h3_quality import check_h3, QUALITY_OFF, QUALITY_CHECK, QUALITY_REPAIR
from quality_pipeline import h3_quality_result
from h3_prompt_relay import compile_relay_response, relay_instruction
from completion_recovery import safe_director_metadata
from prompt_inspector import _h3_required_fields, H3_REFERENCE_FIELDS
from performance_director import build_performance_director_config, PERFORMANCE_EXTREME
from combat_camera import build_combat_camera_config, CAMERA_STRONG
from directional_skills import DIRECTOR_LABELS

BASELINE = "d6ad140020f39da6182fe4dfd3e2ded11c5f5557"
IMAGE = np.zeros((1, 16, 16, 3), dtype=np.float32)


def draft(plan, *, chinese=True, seconds=8):
    descriptions = "红色圆片与蓝框的形状、位置和白色背景保持清晰不变。" if chinese else "A red disc on a gray track, a blue box at the right, on a plain white background."
    definitions, retained = [], []
    for item in plan:
        role, label = item["role"], item["label"]
        if role in {"first_frame", "last_frame"}:
            at = 0 if role == "first_frame" else seconds
            definitions.append(f"{label}: {role} @{at:.2f}s - {descriptions}")
        else:
            definitions.append(f"{label}: {descriptions}")
        retained.append(f"{label}: fully_preserved - {descriptions}")
    body = ("红圆从实际首帧沿灰轨平移并渐慢，持续保留大小，最后抵达蓝框；镜头连续观察，末态匹配实际尾帧，不新增物体。" if chinese else
            "The red disc slides continuously along the gray track, slows toward the blue box and settles at the actual end frame; preserve its size, track, box and white background, with a steady camera and no new objects.")
    sound = "轻微滑动摩擦声连续可闻，无对白或音频素材复用。" if chinese else "Quiet sliding friction accompanies the disc, with no speech or reused soundtrack."
    return ("subject_definitions:\n" + "\n".join(definitions) + "\n\nsummary:\n[keyframe completion + reference generation] " + descriptions
            + "\n\nretention_analysis:\n" + "\n".join(retained) + "\n\ndetailed_description:\n[Shot 1] "
            + " ".join(i["label"] for i in plan) + " " + body + "\n\noverall_soundscape:\n" + sound + "\n\nnon_diegetic_music:\nN/A")


class HybridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_bytes = encoded_video_bytes(frame_count=32, fps=1)

    def setUp(self):
        guard = patch.object(requests.sessions.Session, "request", side_effect=AssertionError("Unexpected real network"))
        guard.start()
        self.addCleanup(guard.stop)
        FakeLocalProvider.instances.clear()

    def plan(self, **changes):
        values = dict(prompt="Preserve geometry.", task_type=HYBRID, duration_seconds=8, rewrite_mode="balanced",
                      description_word_target=0, output_language="中文", prompt_mode="官方增强", reference_template="",
                      first_frame=IMAGE, last_frame=None, reference_images={"reference_image_0": IMAGE},
                      reference_videos=None, official_skill_profile=nodes.COMPAT_SKILL_PROFILE,
                      creative_preset=nodes.NO_CREATIVE_PRESET)
        values.update(changes)
        return nodes._validate_inputs(**values)

    def enhance(self, **changes):
        values = dict(prompt="Preserve the geometry and use only visual references.", task_type=HYBRID,
                      first_frame=IMAGE, reference_images={"reference_image_0": IMAGE}, duration_seconds=8,
                      output_language="中文", api_key="fixture-not-a-live-secret", quality_mode=QUALITY_OFF)
        values.update(changes)
        return nodes.enhance_prompt(**values)

    def check(self, text, plan):
        return check_h3(text, task_type=HYBRID, duration=8, shot_count=1, language="中文",
                        media_labels=[i["label"] for i in plan], asset_roles=asset_roles(plan))

    def test_append_only_task_options_and_exact_aliases(self):
        self.assertEqual(nodes.TASK_TYPES, ["T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA", "Hybrid"])
        # Actions checks out one commit; explicitly fetch the compatibility
        # baseline rather than relying on the developer's complete Git history.
        for workflow in ("verify.yml", "publish_action.yml"):
            source = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
            self.assertTrue(any("fetch --no-tags" in line and BASELINE in line
                                for line in source.splitlines()), workflow)
        for alias in HYBRID_ALIASES:
            self.assertEqual(nodes._canonical_task_type(alias), HYBRID)
            self.assertEqual(_h3_required_fields({}, alias), H3_REFERENCE_FIELDS)
            self.assertIn("Task: Hybrid", relay_instruction(8, task_type=alias))
        self.assertEqual(nodes._canonical_task_type("HybridFuture"), "HybridFuture")

    def test_additive_examples_are_complete_linked_and_match_generator(self):
        from tools.build_h3_hybrid_workflows import check,workflows
        self.assertEqual(check(),3)
        for name,graph in workflows():
            by_id={n["id"]:n for n in graph["nodes"]}
            enhancer=by_id[10]
            self.assertEqual(len(enhancer["widgets_values"]),38,name)
            self.assertEqual(enhancer["widgets_values"][1],nodes.TASK_TYPE_LABELS[HYBRID])
            self.assertEqual(by_id[4]["widgets_values"],[""])
            for ident,source,out_slot,target,in_slot,kind in graph["links"]:
                self.assertEqual(by_id[target]["inputs"][in_slot]["link"],ident)
                self.assertIn(ident,by_id[source]["outputs"][out_slot]["links"])
                self.assertEqual(by_id[target]["inputs"][in_slot]["type"],kind)
                self.assertEqual(by_id[source]["outputs"][out_slot]["type"],kind)
            self.assertEqual({p["name"] for p in enhancer["inputs"] if p["link"] is not None},
                {"api_key", "first_frame", "last_frame", "reference_videos.reference_video_0"} if "video" in name else
                {"api_key", "last_frame" if "last_image" in name else "first_frame", "reference_images.reference_image_0"})

    def test_first_last_both_with_images_or_videos_and_sparse_slots(self):
        for first, last in ((IMAGE, None), (None, IMAGE), (IMAGE, IMAGE)):
            for use_video in (False, True):
                plan = self.plan(first_frame=first, last_frame=last,
                                 reference_images={} if use_video else {"reference_image_8": IMAGE, "reference_image_2": IMAGE, "reference_image_0": None},
                                 reference_videos={"reference_video_2": FakeVideo(duration=3600)} if use_video else {})
                roles = [i["role"] for i in plan]
                self.assertEqual(roles[:int(first is not None)+int(last is not None)],
                                 [r for r, v in (("first_frame", first), ("last_frame", last)) if v is not None])
                pictures = [i for i in plan if i["kind"] == "image"]
                self.assertEqual([i["label"] for i in pictures], [f"<Picture {i+1}>" for i in range(len(pictures))])
                if use_video:
                    self.assertEqual(plan[-1]["label"], "<Video 1>")
                    self.assertEqual(plan[-1]["source_slot"], "reference_video_2")
                else:
                    self.assertEqual([i["source_slot"] for i in plan[-2:]], ["reference_image_2", "reference_image_8"])
                self.assertEqual(self.check(draft(plan), plan)["issues"], [])

    def test_eleven_pictures_and_three_long_videos_allowed(self):
        plan = self.plan(last_frame=IMAGE, reference_images={f"reference_image_{i}": IMAGE for i in range(9)},
                         reference_videos={f"reference_video_{i}": FakeVideo(duration=300+i) for i in range(3)})
        self.assertEqual(len(plan), 14)
        self.assertEqual(plan[10]["label"], "<Picture 11>")
        self.assertEqual(hybrid_metadata(plan)["hybrid_video_count"], 3)
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "9 extra"):
            self.plan(reference_images={str(i): IMAGE for i in range(10)})

    def test_invalid_inputs_zero_transport_or_model_calls(self):
        bad = [dict(first_frame=None), dict(reference_images={}), dict(first_frame=np.zeros((2,16,16,3))),
               dict(reference_images={"reference_image_0":np.zeros((2,16,16,3))}),
               dict(reference_videos={"reference_video_0":FakeVideo(duration=float("nan"))})]
        for api_mode in nodes.API_MODES:
            for change in bad:
                with self.subTest(api_mode=api_mode, change=list(change)):
                    session = FakeSession("never generated")
                    with patch.object(nodes, "LocalQwenProvider") as local:
                        with self.assertRaises(nodes.PromptEnhancerError):
                            self.enhance(api_mode=api_mode, session=session, **change)
                        local.assert_not_called()
                    self.assertEqual(session.uploads, [])
                    self.assertEqual(session.chat_requests, [])
        # Ref2VA's historical batch flattening is deliberately preserved.
        self.assertEqual(len(self.plan(task_type="Ref2VA", first_frame=None,
                                      reference_images={"reference_image_0":np.zeros((2,16,16,3))})), 2)

    def test_real_cpu_video_and_all_four_transports_preserve_order_roles(self):
        video = NativeVideo(self.video_bytes, 32)
        plan = self.plan(last_frame=IMAGE, reference_videos={"reference_video_2":video})
        text = draft(plan)
        for api_mode in nodes.API_MODES:
            with self.subTest(provider=api_mode), patch.object(nodes, "LocalQwenProvider", FakeLocalProvider), patch.object(FakeLocalProvider, "response", text):
                session = FakeSession(text)
                result = self.enhance(last_frame=IMAGE, reference_videos={"reference_video_2":video}, session=session,
                                      api_mode=api_mode, api_key="" if api_mode==nodes.LOCAL_QWEN_API_MODE else "fixture-not-a-live-secret",
                                      openai_base_url="http://127.0.0.1:9000/v1", custom_model="vision-fixture", local_video_sample_fps=0.25)
                self.assertEqual(result, text)
                if api_mode == nodes.LOCAL_QWEN_API_MODE:
                    instance=FakeLocalProvider.instances[-1]
                    messages=instance.messages[0]
                    self.assertEqual(len(instance.calls), 1)
                    self.assertEqual(instance.closed, [False])
                    self.assertIn("covering 32.000 seconds", json.dumps(messages))
                else:
                    self.assertEqual(len(session.chat_requests), 1)
                    messages=session.chat_requests[0]["json"]["messages"]
                self.assertIn(HYBRID_MARKER, messages[0]["content"])
                self.assertIn("references/ref-en.txt", messages[0]["content"])
                user=json.dumps(messages[1]["content"], ensure_ascii=False)
                for role in ("<Picture 1>: first_frame @0.00s", "<Picture 2>: last_frame @8.00s", "<Picture 3>: reference_image", "<Video 1>: reference_video"):
                    self.assertIn(role, user)
                self.assertNotIn("reference_video_2", user)

    def test_local_budget_rejects_before_provider_without_dropping_anchor(self):
        session=FakeSession("never generated")
        with patch.object(nodes, "LocalQwenProvider") as local:
            with self.assertRaisesRegex(nodes.PromptEnhancerError, "visual|context|budget"):
                self.enhance(last_frame=IMAGE, reference_images={f"reference_image_{i}":IMAGE for i in range(9)},
                             api_mode=nodes.LOCAL_QWEN_API_MODE, api_key="", session=session,
                             local_context_size=4096, local_max_tokens=3072)
            local.assert_not_called()

    def test_trim_rejected_cloud_and_honored_local(self):
        video=NativeVideo(self.video_bytes, 32, trim=(4.0,20.0))
        with self.assertRaisesRegex(nodes.PromptEnhancerError, "Trimmed VIDEO"):
            self.plan(reference_videos={"reference_video_0":video})
        plan=self.plan(reference_videos={"reference_video_0":video}, allow_trimmed_video=True)
        with patch.object(nodes, "LocalQwenProvider", FakeLocalProvider), patch.object(FakeLocalProvider, "response", draft(plan)):
            self.enhance(reference_videos={"reference_video_0":video}, api_mode=nodes.LOCAL_QWEN_API_MODE, api_key="", local_video_sample_fps=0.25)
        self.assertIn("covering 20.000 seconds", json.dumps(FakeLocalProvider.instances[-1].messages))

    def test_quality_six_fields_roles_literal_spoofing_audio_and_unknown_scope(self):
        plan=self.plan(last_frame=IMAGE)
        good=draft(plan)
        self.assertEqual(self.check(good, plan)["issues"], [])
        corruptions = [(good.replace("first_frame", "last_frame"), "h3_hybrid_anchor_roles"),
                       (good.replace("last_frame @8.00s", "last_frame @9.00s"), "h3_hybrid_anchor_roles"),
                       (good.replace("[keyframe completion + reference generation]", "[reference generation]"), "h3_hybrid_summary"),
                       (good.replace("<Picture 1>: first_frame @0.00s -", '"<Picture 1>: first_frame @0.00s -"'), "h3_hybrid_anchor_roles"),
                       (good.replace("N/A", "<Audio 1>"), "h3_unavailable_asset")]
        for text, code in corruptions:
            self.assertIn(code, [i["code"] for i in self.check(text, plan)["issues"]])
        report=check_h3(reference_output(), task_type=HYBRID, language="English")
        self.assertEqual(report["mode"], HYBRID)
        self.assertIn("hybrid_resolved_asset_roles", report["unchecked"])
        report=check_h3("integrated_multimodal_description: [Shot 1] x", task_type=HYBRID)
        self.assertIn("h3_missing_core_fields", [i["code"] for i in report["issues"]])

    def test_quality_off_check_and_rejected_repair_keep_draft(self):
        plan=self.plan()
        good=draft(plan)
        for mode in (QUALITY_OFF, QUALITY_CHECK, QUALITY_REPAIR):
            calls=[]
            def complete(messages):
                calls.append(messages)
                return "broken candidate"
            bad=good.replace("first_frame", "last_frame")
            result, metrics=h3_quality_result(bad, mode=mode, messages=[], complete=complete, task_type=HYBRID,
                duration=8, shot_count=1, language="中文", source="", media_labels=[i["label"] for i in plan], asset_roles=asset_roles(plan))
            self.assertEqual(result, bad)
            self.assertEqual(len(calls), int(mode==QUALITY_REPAIR))
            if mode==QUALITY_REPAIR:
                self.assertEqual(metrics["result"], "candidate_rejected")

    def test_hybrid_protected_dialogue_and_visible_text_are_checked_in_actual_body(self):
        plan=self.plan()
        source='Woman (S1) says: <d>[Chinese]让开。</d> A sign displays the exact text "出口".'
        text=draft(plan).replace("[Shot 1]",'[Shot 1] Woman (S1) says: <d>[Chinese]让开。</d> A sign displays the exact text "出口".')
        def checked(value):
            return check_h3(value,task_type=HYBRID,duration=8,shot_count=1,language="中文",source=source,
                            media_labels=[a["label"] for a in plan],asset_roles=asset_roles(plan))
        self.assertEqual(checked(text)["issues"],[])
        for changed,code in ((text.replace("让开。","坐下。"),"semantic_exact_text_missing"),
                             (text.replace("出口","入口"),"h3_visible_text_changed")):
            self.assertIn(code,[i["code"] for i in checked(changed)["issues"]])
        with patch.object(nodes,"LocalQwenProvider",FakeLocalProvider),patch.object(FakeLocalProvider,"response",text):
            result=self.enhance(prompt=source,api_mode=nodes.LOCAL_QWEN_API_MODE,api_key="",quality_mode=QUALITY_CHECK)
        self.assertEqual(result,text)

    def test_language_repair_preserves_hybrid_for_auto_extreme_and_directors(self):
        plan=self.plan(last_frame=IMAGE)
        for performance in (None, build_performance_director_config(PERFORMANCE_EXTREME)):
            for director in (nodes.DIRECTOR_OFF, "continuous_combat"):
                for camera in (None, build_combat_camera_config(mode=CAMERA_STRONG)):
                    messages=nodes._build_messages(**h3_args(task_type=HYBRID, media_plan=plan, media_parts=[{"type":"image_url", "image_url":{"url":"data:image/png;base64,fixture"}}],
                        performance_director_config=performance, director_skill=director, combat_camera_config=camera))
                    corrected=nodes._h3_language_repair_messages(draft(plan,chinese=False), "中文", None, messages, director,
                                                               performance_director_config=performance, combat_camera_config=camera)
                    self.assertEqual(corrected[0]["content"].count(HYBRID_MARKER), 1)
                    self.assertEqual(corrected[1]["content"].count("T8_HYBRID_ASSET_ROLES"), 1)
                    self.assertIn("<Picture 2>: last_frame @8.00s", corrected[1]["content"])
                    self.assertNotIn("data:image", json.dumps(corrected))

    def test_relay_compiles_six_fields_and_preserves_requested_ending_before_padding(self):
        plan=self.plan(last_frame=IMAGE)
        text=json.dumps({"global_prompt":"保持白底与红圆形状。", "events":[{"prompt":"红圆沿灰轨平移到蓝框。", "end_state":"红圆已在蓝框内，位置与尾帧一致。", "weight":1}], "native_prompt":draft(plan)},ensure_ascii=False)
        compiled=compile_relay_response(text,8,task_type=HYBRID,output_language="中文")
        self.assertEqual(compiled["enhanced_prompt"],draft(plan))
        self.assertEqual(json.loads(compiled["relay_report"])["task_type"], HYBRID)
        padded=compile_relay_response(text.replace("last_frame @8.00s", "last_frame @8.10s"),8.1,task_type=HYBRID,output_language="中文")
        self.assertIn("不增加新动作",padded["local_prompts"])
        self.assertEqual(json.loads(compiled["relay_report"])["delivery_frames"],192)
        with self.assertRaisesRegex(ValueError,"each official field"):
            compile_relay_response(text.replace("detailed_description:","integrated_multimodal_description:"),8,task_type=HYBRID)
        with self.assertRaisesRegex(ValueError,"each official field"):
            mixed=json.loads(text)
            mixed["native_prompt"]=mixed["native_prompt"].replace("detailed_description:","integrated_multimodal_description: invalid\n\ndetailed_description:")
            compile_relay_response(json.dumps(mixed),8,task_type=HYBRID)

    def test_bad_hybrid_execute_preserves_paid_cache_and_restore_is_byte_identical(self):
        component, slot="MiniMaxH3PromptEnhancerT8", "hybrid-test-preserve-paid"
        nodes.begin_recovery_record(component,slot,nodes.SEEDANCE_API_MODE,metadata=hybrid_metadata(self.plan()))
        stored=(draft(self.plan()), "global", "local", "0-8", "192", "report")
        nodes.complete_recovery_record(component,slot,stored)
        values=dict(prompt="Preserve geometry.",task_type=HYBRID,duration_seconds=8,rewrite_mode="balanced",
                    description_word_target=0,output_language="中文")
        values.update(task_type=HYBRID,first_frame=IMAGE,reference_images={},recovery_slot=slot)
        with patch.object(nodes,"enhance_prompt") as enhance:
            with self.assertRaisesRegex(nodes.PromptEnhancerError,"visual reference"):
                nodes.MiniMaxH3PromptEnhancer.execute(**values)
            enhance.assert_not_called()
            self.assertEqual(nodes.recover_outputs(component,slot,6),stored)
            values.update(recovery_action="restore_last",relay_mode=nodes.RELAY)
            self.assertEqual(tuple(nodes.MiniMaxH3PromptEnhancer.execute(**values).result), (*stored[:4],192,stored[5]))
            enhance.assert_not_called()

    def test_metadata_independent_finite_and_private_fields_excluded(self):
        expected=hybrid_metadata(self.plan())
        self.assertEqual(safe_director_metadata({**expected,"source_slot":"private","api_key":"private","url":"private"}),expected)
        for key in expected:
            bad=dict(expected)
            bad.pop(key)
            self.assertEqual(safe_director_metadata(bad),{})
        self.assertEqual(safe_director_metadata({**expected,"hybrid_picture_count":True}),{})

    def test_invalid_pixel_shape_before_cache_and_literal_marker_repair(self):
        values=dict(prompt="Preserve geometry.",task_type=HYBRID,duration_seconds=8,rewrite_mode="balanced",
                    description_word_target=0,output_language="中文",reference_images={"reference_image_0":IMAGE})
        for image in (np.zeros((1,2,2,2)),np.zeros((1,0,2,3))):
            with patch.object(nodes,"begin_recovery_record") as begin:
                with self.assertRaises(nodes.PromptEnhancerError):
                    nodes.MiniMaxH3PromptEnhancer.execute(**values,first_frame=image)
                begin.assert_not_called()
        plan=self.plan(first_frame=None,last_frame=IMAGE)
        messages=nodes._build_messages(**h3_args(task_type=HYBRID,media_plan=plan))
        output=draft(plan).replace("[Shot 1]", '[Shot 1] A sign reads "T8_HYBRID_ASSET_ROLES".')
        repaired=nodes._h3_language_repair_messages(output,"中文",None,messages)
        self.assertIn("<Picture 1>: last_frame @8.00s",repaired[1]["content"])
        self.assertIn("Original user intent",repaired[1]["content"])

    def test_video_payload_preflight_is_nonconsuming_and_preserves_cache(self):
        class BufferVideo(FakeVideo):
            def __init__(self,buffer):
                super().__init__(duration=8)
                self.buffer=buffer
            def get_stream_source(self): return self.buffer
        for stream in (io.BytesIO(b""),io.StringIO("text-not-binary"),io.BytesIO(b"12345")):
            stream.seek(0)
            video=BufferVideo(stream)
            cap=4 if isinstance(stream,io.BytesIO) and len(stream.getvalue()) else nodes.MAX_FILE_BYTES
            with patch.object(nodes,"begin_recovery_record") as begin, patch.object(nodes,"MAX_FILE_BYTES",cap):
                with self.assertRaises(nodes.PromptEnhancerError):
                    nodes.MiniMaxH3PromptEnhancer.execute(prompt="Preserve geometry.",task_type=HYBRID,duration_seconds=8,
                        rewrite_mode="balanced",description_word_target=0,output_language="中文",first_frame=IMAGE,
                        reference_videos={"reference_video_2":video})
                begin.assert_not_called()
            self.assertEqual(stream.tell(),0)
        buffer=io.BytesIO(b"complete-video-bytes")
        buffer.seek(5)
        self.plan(reference_videos={"reference_video_0":BufferVideo(buffer)})
        self.assertEqual(buffer.tell(),5)

    def test_old_five_modes_messages_match_1292_with_all_existing_optional_controls(self):
        builder=original_function("nodes.py","_build_messages",nodes,BASELINE)
        for name in ("_official_h3_source_instruction","_length_target_instruction","_build_user_instruction"):
            builder.__globals__[name]=original_function("nodes.py",name,nodes,BASELINE)
        for task in nodes.TASK_TYPES[:5]:
            for language in ("中文","English"):
                for director in DIRECTOR_LABELS:
                    for perf in (None,build_performance_director_config(PERFORMANCE_EXTREME)):
                        for camera in (None,build_combat_camera_config(mode=CAMERA_STRONG)):
                            values=h3_args(task_type=task,output_language=language,director_skill=director,
                                           performance_director_config=perf,combat_camera_config=camera)
                            self.assertEqual(nodes._build_messages(**values),builder(**values))
        self.assertIn('version = "1.29.2"',subprocess.check_output(["git","show",f"{BASELINE}:pyproject.toml"],cwd=GIT_ROOT).decode("utf8"))

    def test_captured_paid_api_evidence_is_immutable_and_replays_without_network(self):
        path = ROOT / "tests/fixtures/h3_hybrid_api_2026-10-06.json"
        payload = path.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         "288b016d36c9da35d19aa897cb0826b6ddeef8d52cf98859a6ba362f58d03edf")
        data = json.loads(payload)
        self.assertEqual(data["source_sha256"],
                         "96744d0468eea342c3b65f1a780955e88b233c4ea5e977025470928d18f5adcc")
        # This is the API-start snapshot, not an assertion that the subsequent
        # preflight-only fixes were tested by these historical paid requests.
        self.assertEqual((data["initial_calls"], data["correction_calls"],
                          data["http_chat_attempts"], data["uploads"]), (24, 0, 24, 56))
        expected = [(f"{anchors}_{kind}", repeat, group)
                    for anchors in ("first", "last", "both")
                    for kind in ("image", "video") for repeat in range(2)
                    for group in ("Ref2VA_control", "Hybrid")]
        self.assertEqual([(t["case"], t["repeat"], t["group"]) for t in data["tests"]], expected)
        self.assertNotRegex(payload.decode("utf-8"),
                            r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}|https?://|Authorization|Bearer")
        total_tokens = 0
        for test in data["tests"]:
            self.assertEqual(test["outcome"], "success")
            self.assertEqual(len(test["requests"]), 1)
            request = test["requests"][0]
            self.assertEqual(request["kind"], "initial")
            self.assertEqual(request["output"], test["output"])
            self.assertEqual(len(request["attempts"]), 1)
            attempt = request["attempts"][0]
            self.assertEqual((attempt["status"], attempt["finish_reason"]), (200, "stop"))
            self.assertEqual(attempt["response_model"], "bytedance/doubao-seed-evolving")
            self.assertEqual(attempt["parameters"],
                             {"model": "bytedance/doubao-seed-evolving", "stream": True, "temperature": 0.7})
            total_tokens += attempt["usage"]["total_tokens"]
            anchors, kind = test["case"].split("_")
            plan = self.plan(first_frame=IMAGE if anchors in {"first", "both"} else None,
                             last_frame=IMAGE if anchors in {"last", "both"} else None,
                             reference_images={"reference_image_2": IMAGE} if kind == "image" else {},
                             reference_videos={"reference_video_2": FakeVideo(duration=8)} if kind == "video" else {})
            options = {"asset_roles": asset_roles(plan)} if test["group"] == "Hybrid" else {}
            report = check_h3(test["output"], task_type=test["group"].replace("_control", ""),
                              duration=8, shot_count=1, language="中文",
                              media_labels=[a["label"] for a in plan], **options)
            self.assertEqual({k:v for k,v in report.items() if not k.startswith("_")}, test["report"])
            self.assertEqual(report["issues"], [])
            self.assertEqual(report["language_status"], "match")
            self.assertIn("rendered_video_quality", report["unchecked"])
            if options:
                self.assertIn("hybrid_pixel_and_transition_semantics", report["unchecked"])
        self.assertEqual(total_tokens, 418077)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(path.relative_to(ROOT).as_posix() + " -text", attributes)


if __name__ == "__main__":
    unittest.main()
