"""Speech wiring and frozen old paths; inference doubles are not ASR acceptance."""
import asyncio
import copy
import importlib
import inspect
import json
import subprocess
import unittest
from unittest.mock import patch

from test_directional_skills import (GIT_ROOT, ROOT, h3, sd, h3_args, sd_args,
    original_function, native_draft, relay_draft, execute_inputs, RecordingLocalProvider, test_seedance20)

speech = importlib.import_module(h3.__package__ + ".speech_reference")
BASELINE = "c55bb0d733a5929a123dd60842dff2bb0d187b62"


def reference(purpose="reference"):
    return speech.provided_reference("等我回来。", purpose=purpose,
        speaker_map={"default": "角色A"} if purpose == "keep_dialogue" else {})


class SpeechIntegrationTests(unittest.TestCase):
    def test_old_messages_are_identical_to_1_31_1(self):
        for module, filename, args in ((h3, "nodes.py", h3_args), (sd, "seedance20.py", sd_args)):
            old = original_function(filename, "_build_messages", module, BASELINE)
            for skill in ("none", "high_density_combat", "drama_scene"):
                values = args(director_skill=skill)
                self.assertEqual(module._build_messages(**values, speech_reference=None), old(**values))

    def test_source_evidence_is_quoted_not_native_audio_and_fanout_does_not_mutate(self):
        value = reference(); before = copy.deepcopy(value)
        for module, args in ((h3, h3_args), (sd, sd_args), (sd, sd_args), (h3, h3_args)):
            messages = module._build_messages(**args(), speech_reference=value)
            text = json.dumps(messages, ensure_ascii=False)
            self.assertIn("等我回来。", text)
            self.assertIn("REFERENCE ONLY", text)
            self.assertNotIn('"input_audio"', text)
            self.assertEqual(value, before)

    def test_old_signatures_schema_outputs_and_workflows_are_frozen_prefixes(self):
        import ast
        for module, filename, cls, fn in ((h3, "nodes.py", h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                                         (sd, "seedance20.py", sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            source = subprocess.check_output(["git", "show", BASELINE + ":" + filename], cwd=GIT_ROOT).decode()
            tree = ast.parse(source)
            for name in (fn, "_build_messages"):
                old = original_function(filename, name, module, BASELINE)
                current = inspect.signature(getattr(module, name))
                self.assertEqual(list(current.parameters)[-1], "speech_reference")
                self.assertIsNone(current.parameters["speech_reference"].default)
                self.assertEqual(current.replace(parameters=list(current.parameters.values())[:-1]), inspect.signature(old))
            klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls.__name__)
            method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "define_schema")
            method.decorator_list = []
            namespace = dict(vars(module)); exec(compile(ast.Module(body=[method], type_ignores=[]), filename, "exec"), namespace)
            old_schema, now = namespace["define_schema"](cls), cls.define_schema()
            self.assertEqual([x.as_dict() for x in now.inputs[:-1]], [x.as_dict() for x in old_schema.inputs])
            self.assertEqual([x.as_dict() for x in now.outputs], [x.as_dict() for x in old_schema.outputs])
            self.assertEqual(now.inputs[-1].id, "speech_reference")
            self.assertTrue(now.inputs[-1].optional); self.assertTrue(now.inputs[-1].lazy)
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASELINE, "--", "example_workflows"], cwd=GIT_ROOT, text=True).splitlines()
        for path in paths:
            old = subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=GIT_ROOT)
            self.assertEqual((ROOT / path).read_bytes().replace(b"\r\n", b"\n"), old.replace(b"\r\n", b"\n"), path)

    def test_main_lazy_never_requests_missing_input_or_speech_on_restore(self):
        for cls in (h3.MiniMaxH3PromptEnhancer, sd.Seedance20PromptEnhancer):
            self.assertEqual(cls.check_lazy_status(), [])
            self.assertEqual(cls.check_lazy_status(speech_reference=None), ["speech_reference"])
            self.assertEqual(cls.check_lazy_status(speech_reference=reference()), [])
            self.assertEqual(cls.check_lazy_status(speech_reference=None, recovery_action="restore_last"), [])

    def test_execute_validates_new_reference_before_checkpoint_and_keeps_restore(self):
        for module, cls, name, count in ((h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt", 6),
                                        (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt", 1)):
            recovery = sysmodule(module.begin_recovery_record)
            slot = "speech-integration-restore-" + str(count)
            recovery.begin_recovery_record(cls.define_schema().node_id, slot, "fixture")
            previous = ("previous completed prompt", "", "", "", 0, "") if count == 6 else ("previous completed prompt",)
            recovery.complete_recovery_record(cls.define_schema().node_id, slot, previous[:1])
            with patch.object(module, name, side_effect=AssertionError("No model on restore")):
                actual = cls.execute(**execute_inputs(module), recovery_action="restore_last", recovery_slot=slot,
                    speech_reference={"schema_version": "invalid"})
            self.assertEqual(tuple(actual.result), previous)
            with patch.object(module, "begin_recovery_record") as begin, patch.object(module, name) as model:
                with self.assertRaises(speech.SpeechReferenceError):
                    cls.execute(**execute_inputs(module), speech_reference={"schema_version": "invalid"})
            begin.assert_not_called(); model.assert_not_called()

    def test_cloud_local_and_budget_builds_carry_speech_once(self):
        for module, function in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            response = native_draft() if module is h3 else "Shot 1: A woman holds a ticket and waits by the door."
            values = dict(prompt="A woman waits by the door.", output_language="English", speech_reference=reference())
            session = test_seedance20.SequencedChatSession([response])
            result = function(**values, session=session, api_key="fixture-placeholder")
            self.assertEqual(result, response); self.assertEqual(len(session.chat_requests), 1)
            sent = session.chat_requests[0]["json"]["messages"]
            self.assertEqual(json.dumps(sent).count("T8_SPEECH_REFERENCE_BEGIN"), 1)
            providers = []
            def factory(settings, *, vision):
                value = RecordingLocalProvider(settings, vision=vision, responses=[response]); providers.append(value); return value
            with patch.object(module, "LocalQwenProvider", side_effect=factory), patch.object(module, "_build_messages", wraps=module._build_messages) as builds:
                result = function(**values, api_mode=module.LOCAL_QWEN_API_MODE)
            self.assertEqual(result, response); self.assertEqual(builds.call_count, 2)
            self.assertTrue(providers[0].closed)
            for call in builds.call_args_list:
                self.assertEqual(call.kwargs["speech_reference"], reference())

    def test_language_repairs_keep_data_with_directors_off(self):
        for module, function in ((h3, h3.enhance_prompt), (sd, sd.enhance_seedance20_prompt)):
            outputs = [native_draft(), native_draft(True)] if module is h3 else [
                "Shot 1: The woman waits beside the station door with a red sleeve and a ticket, keeping her posture and gaze steady while the camera slowly moves closer.",
                "镜头1：女人拿着车票在门边等待，保持原有姿态。"]
            session = test_seedance20.SequencedChatSession(outputs)
            result = function(prompt="女人在门边等待。", output_language="中文", speech_reference=reference(), session=session, api_key="fixture-placeholder")
            self.assertEqual(result, outputs[-1]); self.assertEqual(len(session.chat_requests), 2)
            correction = session.chat_requests[1]["json"]["messages"]
            self.assertIn("等我回来。", json.dumps(correction, ensure_ascii=False))
            self.assertEqual(json.dumps(correction).count("T8_SPEECH_REFERENCE_BEGIN"), 1)

    def test_relay_format_and_quality_corrections_retain_speech_without_new_media_types(self):
        session = test_seedance20.SequencedChatSession(["not-json", relay_draft()])
        result = h3.enhance_prompt(prompt="The woman steps forward with a ticket.", output_language="English",
            speech_reference=reference(), relay_config={"event_count": 2, "time_ranges": ""},
            api_key="fixture-placeholder", session=session, duration_seconds=8)
        self.assertEqual(result, relay_draft()); self.assertEqual(len(session.chat_requests), 2)
        corrected = session.chat_requests[1]["json"]["messages"]
        self.assertEqual(json.dumps(corrected).count("T8_SPEECH_REFERENCE_BEGIN"), 1)
        self.assertIn("等我回来。", json.dumps(corrected, ensure_ascii=False))

    def test_active_output_ui_discloses_speech_even_when_quality_is_off(self):
        for module, cls, function in ((h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt"),
                                      (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt")):
            with patch.object(module, function, return_value=native_draft() if module is h3 else "Plain prompt"):
                output = cls.execute(**execute_inputs(module), speech_reference=reference())
            metadata = json.loads(output.ui["t8_quality_status"][0])
            self.assertTrue(metadata["speech_reference_active"])


def sysmodule(function):
    import sys
    return sys.modules[function.__module__]


if __name__ == "__main__":
    unittest.main()
