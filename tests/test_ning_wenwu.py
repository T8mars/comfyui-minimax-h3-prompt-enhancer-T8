"""Ning integration tests use CPU transport doubles and a frozen current baseline."""
import subprocess
import types
import unittest
from unittest.mock import patch

from test_directional_skills import h3, sd, h3_args, sd_args, original_function, ROOT, RecordingLocalProvider, test_seedance20
from directional_skills import prepare_director_skill, director_metadata, director_instruction, _load_resource, normalize_director_skill, DIRECTOR_LABELS, DIRECTOR_LEGACY_LABELS
from completion_recovery import safe_director_metadata
from performance_director import PERFORMANCE_OFF, PERFORMANCE_AUTO, PERFORMANCE_STRONG, PERFORMANCE_EXTREME, build_performance_director_config
from h3_quality import CREATION_OFF, CREATION_CAUSAL, correction_messages

PRE_NING_COMMIT = "d1a8cf5c8e5477847b51f1fc0757ea6b5a00b8c8"
LEGACY_SKILLS = ("none", "continuous_combat", "high_density_combat", "cinematic_gunfight")


class NingIntegrationTests(unittest.TestCase):
    def test_author_labels_keep_legacy_aliases_and_identical_native_requests(self):
        current_labels = {skill: label for label, skill in DIRECTOR_LABELS.items()}
        prefixes = ("Fisher-", "土豆-", "兔子-")
        for prefix, (legacy_label, skill) in zip(prefixes, DIRECTOR_LEGACY_LABELS.items()):
            self.assertEqual(current_labels[skill], prefix + legacy_label)
            for label in (legacy_label, current_labels[skill]):
                self.assertEqual(normalize_director_skill(label), skill)
                self.assertEqual(prepare_director_skill(label, 1), (skill, 1))
                for module, args, target in ((h3, h3_args, "h3"), (sd, sd_args, "seedance20")):
                    self.assertEqual(module._build_messages(**args(director_skill=label)),
                                     module._build_messages(**args(director_skill=skill)))
                    self.assertEqual(director_instruction(label, target), director_instruction(skill, target))

    def test_legacy_requests_and_resources_match_current_published_baseline(self):
        # All node/transport helpers are unchanged bytes, not merely equal
        # function signatures bound to the current implementation.
        for filename in ("nodes.py", "seedance20.py", "performance_director.py", "h3_quality.py"):
            old = subprocess.check_output(["git", "show", f"{PRE_NING_COMMIT}:{filename}"], cwd=ROOT)
            self.assertEqual((ROOT / filename).read_bytes().replace(b"\r\n", b"\n"), old.replace(b"\r\n", b"\n"))
        historical_director = types.ModuleType("historical_director")
        historical_director.__file__ = str(ROOT / "directional_skills.py")
        source = subprocess.check_output(["git", "show", f"{PRE_NING_COMMIT}:directional_skills.py"], cwd=ROOT).decode("utf-8")
        exec(compile(source, historical_director.__file__, "exec"), vars(historical_director))
        for module, filename, args in ((h3, "nodes.py", h3_args), (sd, "seedance20.py", sd_args)):
            baseline = original_function(filename, "_build_messages", module, PRE_NING_COMMIT)
            for skill in LEGACY_SKILLS:
                for language in ("中文", "English"):
                    values = args(director_skill=skill, output_language=language)
                    self.assertEqual(module._build_messages(**values), baseline(**values))
                    self.assertEqual(director_metadata(skill, language=language, mode="Normal", shot_count=2),
                        historical_director.director_metadata(skill, language=language, mode="Normal", shot_count=2))
                    if skill != "none":
                        target = "h3" if module is h3 else "seedance20"
                        self.assertEqual(director_instruction(skill, target), historical_director.director_instruction(skill, target))
        for skill in LEGACY_SKILLS[1:]:
            for name in ("SKILL.md", "meta.json"):
                path = f"directional_skills/{skill}/{name}"
                old = subprocess.check_output(["git", "show", f"{PRE_NING_COMMIT}:{path}"], cwd=ROOT)
                self.assertEqual((ROOT / path).read_bytes().replace(b"\r\n", b"\n"), old.replace(b"\r\n", b"\n"))

    def test_ning_does_not_impose_shot_or_duration_threshold(self):
        for count in (0, 1, 2, 20):
            self.assertEqual(prepare_director_skill("ning_wenwu", count), ("ning_wenwu", count))
        for task in ("T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA"):
            messages = h3._build_messages(**h3_args(director_skill="ning_wenwu", task_type=task, shot_count=1, duration_seconds=30))
            self.assertIn("ning_wenwu", messages[0]["content"])
            self.assertIn("30", str(messages[1]["content"]))

    def test_auxiliary_choices_survive_and_resource_is_injected_once(self):
        resource = _load_resource("ning_wenwu")[0]
        for module, args in ((h3, h3_args), (sd, sd_args)):
            for mode in (PERFORMANCE_OFF, PERFORMANCE_AUTO, PERFORMANCE_STRONG, PERFORMANCE_EXTREME):
                for creation in (CREATION_OFF, CREATION_CAUSAL):
                    messages = module._build_messages(**args(director_skill="ning_wenwu", creation_mode=creation,
                        performance_director_config=build_performance_director_config(mode)))
                    system = messages[0]["content"]
                    self.assertEqual(system.count(resource), 1)
                    self.assertEqual("COORDINATED PERFORMANCE DIRECTION" in system, mode != PERFORMANCE_OFF)
                    self.assertEqual("OPTIONAL CAUSAL CREATION METHOD" in system, creation == CREATION_CAUSAL)
                    fixed = correction_messages(messages, "draft", {"issues": [{"code": "shot_count_mismatch", "message": "count"}]})
                    self.assertEqual(fixed[:2], messages)

    def test_strict_language_and_finite_recovery_provenance(self):
        messages = h3._build_messages(**h3_args(director_skill="ning_wenwu", official_skill_profile=h3.STRICT_SKILL_PROFILE))
        self.assertIn(h3.LANGUAGE_RULES["English"], messages[0]["content"])
        metadata = director_metadata("ning_wenwu", language=h3._effective_output_language("中文", h3.STRICT_SKILL_PROFILE), mode="普通增强 / Normal", shot_count=1)
        self.assertEqual(safe_director_metadata(metadata), metadata)
        self.assertEqual(metadata["output_language"], "English")
        self.assertIn("H3 protocol delimiters are literal ASCII", director_instruction("ning_wenwu", "h3"))
        self.assertNotIn("H3 protocol delimiters are literal ASCII", director_instruction("ning_wenwu", "seedance20"))

    def test_explicit_quality_repair_preserves_ning_and_exact_words_without_an_extra_call(self):
        draft = ("integrated_multimodal_description: [Shot 1] One eight-second continuous shot. "
                 "Alice （S1） says: <d>[English] Keep （S1） unchanged.</d> She keeps the ticket in her right hand.\n\n"
                 "overall_soundscape: Quiet footsteps.\n\nnon_diegetic_music: N/A")
        expected = draft.replace("Alice （S1）", "Alice (S1)")
        for transport in ("cloud", "local"):
            for quality, result in (("off", draft), ("repair", expected)):
                with self.subTest(transport=transport, quality=quality):
                    inputs = dict(prompt='Alice says "Keep （S1） unchanged." Keep her ticket in her right hand.',
                                  duration_seconds=8, task_type="T2VA", shot_count="1", output_language="English",
                                  director_skill="ning_wenwu", quality_mode=quality,
                                  performance_director_config=build_performance_director_config(PERFORMANCE_OFF))
                    if transport == "cloud":
                        session = test_seedance20.SequencedChatSession([draft])
                        actual = h3.enhance_prompt(**inputs, session=session, api_key="test-placeholder")
                        calls = [{"messages": call["json"]["messages"]} for call in session.chat_requests]
                    else:
                        instances = []
                        def factory(settings, *, vision):
                            provider = RecordingLocalProvider(settings, vision=vision, responses=[draft])
                            instances.append(provider)
                            return provider
                        with patch.object(h3, "LocalQwenProvider", side_effect=factory):
                            actual = h3.enhance_prompt(**inputs, api_mode=h3.LOCAL_QWEN_API_MODE)
                        calls = instances[0].calls
                        self.assertTrue(instances[0].closed)
                    self.assertEqual(actual, result)
                    self.assertEqual(len(calls), 1)
                    self.assertIn("ning_wenwu", calls[0]["messages"][0]["content"])
                    self.assertIn("<d>[English] Keep （S1） unchanged.</d>", actual)


if __name__ == "__main__":
    unittest.main()
