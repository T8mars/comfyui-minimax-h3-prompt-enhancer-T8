import ast
import copy
import inspect
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

# Standalone discovery must not initialize CUDA while importing real Comfy IO.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
import comfy.cli_args

comfy.cli_args.args.cpu = True
import numpy as np
import test_seedance20

sd = test_seedance20.seedance20
h3 = test_seedance20.nodes
from directional_skills import (
    DIRECTOR_OFF, DIRECTOR_OPTIONS, DIRECTOR_LABELS, DirectionalSkillError, _load_resource,
    normalize_director_skill, prepare_director_skill, director_instruction,
    template_fact_lookup, preserve_director_on_repair,
)
from completion_recovery import safe_director_metadata

BASELINE_COMMIT = "bfaae3ce13a8bdf3d4907146c13cfc280a2b2c36"


def original_function(filename, name, module, commit=BASELINE_COMMIT):
    source = subprocess.check_output(["git", "show", f"{commit}:{filename}"], cwd=ROOT).decode("utf-8")
    definition = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = dict(vars(module))
    exec(compile(ast.Module(body=[definition], type_ignores=[]), filename, "exec"), namespace)
    return namespace[name]


def original_execute(filename, class_name, module):
    source = subprocess.check_output(["git", "show", f"{BASELINE_COMMIT}:{filename}"], cwd=ROOT).decode("utf-8")
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == class_name)
    definition = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    definition.decorator_list = []
    namespace = dict(vars(module))
    exec(compile(ast.Module(body=[definition], type_ignores=[]), filename, "exec"), namespace)
    return namespace["execute"]


def primary_text(content):
    # Later text parts label media; they are not the request's main text and
    # intentionally do not exist in the initial empty-media budget build.
    return content if isinstance(content, str) else next(
        (part["text"] for part in content if part.get("type") == "text"), ""
    )


def native_draft(chinese=False):
    body = "女人保持红色袖口，向前滑步并拿稳车票，动作和持有状态持续继承。" if chinese else (
        "The woman keeps her red sleeve, steps forward and continues holding the ticket."
    )
    sound = "脚步摩擦和安静车站环境声持续可闻。" if chinese else "Quiet station ambience and footsteps."
    return f"integrated_multimodal_description: [Shot 1] {body}\n\noverall_soundscape: {sound}\n\nnon_diegetic_music: N/A"


def relay_draft(chinese=False):
    data = {
        "global_prompt": "保持人物红色袖口、身份和车站环境连续，镜头始终连续观察动作。" if chinese else (
            "Keep the woman's red sleeve, identity and station environment continuous in one observation."
        ),
        "events": [
            {"prompt": "女人向前滑步，同时拿稳手中的车票并保持朝向。" if chinese else (
                "The woman steps forward while securely holding the ticket and keeping her facing."
            ), "end_state": "女人仍然向前移动，车票保持在她的右手中。" if chinese else (
                "The woman continues moving forward with the ticket still in her right hand."
            ), "weight": 1},
            {"prompt": "女人延续前一步的速度，侧移避开地上的障碍物。" if chinese else (
                "The woman carries her prior speed into a sidestep around the existing obstruction."
            ), "end_state": "女人保持侧移余速和右手持票，地面障碍物仍然存在。" if chinese else (
                "She retains lateral momentum and the ticket; the ground obstruction remains present."
            ), "weight": 1},
        ],
        "native_prompt": native_draft(chinese),
    }
    return json.dumps(data, ensure_ascii=False)


class RecordingLocalProvider:
    """Only a transport double: never construct a GGUF provider or runtime."""

    def __init__(self, settings, *, vision, responses):
        self.settings = settings
        self.vision = vision
        self.responses = iter(responses)
        self.calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": copy.deepcopy(messages), "kwargs": dict(kwargs)})
        return next(self.responses)


def local_parameters(module):
    return {
        "local_model": "test-only-9b.gguf", "local_mmproj": "test-only-mmproj.gguf",
        "local_context_size": 49152, "local_max_tokens": 6144,
        "local_think_mode": module.LOCAL_THINK_OPTIONS[-1], "local_reasoning_effort": "xhigh",
        "local_video_sample_fps": 3.25, "local_unload_policy": module.LOCAL_UNLOAD_AFTER_RUN,
        "local_comfy_memory_policy": module.LOCAL_COMFY_MEMORY_POLICIES[-1],
    }


def execute_inputs(module):
    if module is h3:
        return dict(prompt="Keep the red sleeve. LOCK: ticket stays in the right hand.", task_type="T2VA",
                    duration_seconds=8, rewrite_mode="balanced", description_word_target=0,
                    output_language="English", shot_count=h3.AUTO_SHOT_COUNT)
    return dict(prompt="Keep the red sleeve. LOCK: ticket stays in the right hand.", task_intent="T2V",
                complexity_mode=sd.COMPLEXITY_OPTIONS[0], duration_seconds=8,
                shot_count=sd.AUTO_SHOT_COUNT, rewrite_mode="balanced", output_detail=sd.OUTPUT_DETAILS[0],
                output_language="English")


def h3_args(**kwargs):
    args = dict(prompt="徒手练拳，保留红色袖口；不加对手。", task_type="T2VA", duration_seconds=15,
        rewrite_mode="balanced", description_word_target=0, output_language="中文", prompt_mode="官方增强",
        reference_template="", reference_context="", constraints="不新增装备", media_plan=[], media_parts=[],
        seed=12, shot_count=0, official_skill_profile=h3.COMPAT_SKILL_PROFILE,
        creative_preset=h3.NO_CREATIVE_PRESET, case_template=h3.NO_CASE_TEMPLATE)
    return {**args, **kwargs}


def sd_args(**kwargs):
    args = dict(prompt="两人在车厢内护送，先等待两秒，保留红色袖口。", task_intent="T2V",
        complexity_mode=sd.COMPLEXITY_OPTIONS[0], duration_seconds=15, shot_count=0,
        rewrite_mode="balanced", output_detail=sd.OUTPUT_DETAILS[0], custom_length_target=0,
        output_language="中文", prompt_mode="官方优化", reference_syntax=sd.REFERENCE_SYNTAXES[0],
        subtitle_policy=sd.SUBTITLE_POLICIES[0], stability_constraints=sd.STABILITY_POLICIES[0],
        reference_roles="", reference_context="", constraints="等待两秒，不增加人物", reference_template="",
        seed=12, media_plan=[], media_parts=[], case_template=sd.NO_CASE_TEMPLATE)
    return {**args, **kwargs}


class DirectionalSkillTests(unittest.TestCase):
    def test_non_string_falsey_skill_is_rejected_not_silently_disabled(self):
        for value in (0, False, [], {}, 1):
            with self.subTest(value=value), self.assertRaises(DirectionalSkillError):
                normalize_director_skill(value)
        for value in (None, '', '   ', DIRECTOR_OFF):
            self.assertEqual(normalize_director_skill(value), DIRECTOR_OFF)

    def test_protocol_hint_is_h3_only_and_never_a_postprocessing_rewrite(self):
        self.assertIn('ASCII (S1)', director_instruction('high_density_combat', 'h3'))
        self.assertIn('Explicitly state', director_instruction('continuous_combat', 'h3'))
        self.assertNotIn('ASCII (S1)', director_instruction('high_density_combat', 'seedance20'))
        self.assertEqual(director_instruction(DIRECTOR_OFF, 'h3'), '')

    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("No network in CPU regressions")))
        for module in (h3, sd):
            self.guards.enter_context(patch.object(module, "LocalQwenProvider", side_effect=AssertionError("No real GGUF provider in CPU regressions")))
        backends = {sys.modules[h3.prepare_director_skill.__module__], sys.modules[sd.prepare_director_skill.__module__]}
        for backend in backends:
            backend._load_resource.cache_clear()
            self.addCleanup(backend._load_resource.cache_clear)
        _load_resource.cache_clear()
        self.addCleanup(_load_resource.cache_clear)

    def test_explicit_opt_in_and_unknown(self):
        for value in (None, "", "  ", "none", DIRECTOR_OPTIONS[0]):
            self.assertEqual(normalize_director_skill(value), DIRECTOR_OFF)
        for label, stable in list(DIRECTOR_LABELS.items())[1:]:
            self.assertEqual(normalize_director_skill(label), stable)
            self.assertEqual(normalize_director_skill(stable), stable)
        with self.assertRaises(DirectionalSkillError):
            normalize_director_skill("sk-" + "x" * 30)

    def test_resources_are_independent_and_platform_neutral(self):
        for skill in list(DIRECTOR_LABELS.values())[1:]:
            text, meta = _load_resource(skill)
            self.assertEqual(meta["id"], skill)
            self.assertEqual(meta["version"], "1.0.0")
            self.assertEqual(len(meta["source_sha256"]), 64)
            for forbidden in ("BUNNY", "subject_definitions:", "<d>", "{{", "```", "$h3-prompt-writing"):
                self.assertNotIn(forbidden, text)
            sd_instruction = director_instruction(skill, "seedance20")
            self.assertIn("Never import H3", sd_instruction)
            self.assertNotIn("[Shot N]", sd_instruction)

    def test_off_never_reads_resources(self):
        backends = {sys.modules[_load_resource.__module__], sys.modules[h3.prepare_director_skill.__module__],
                    sys.modules[sd.prepare_director_skill.__module__]}
        with ExitStack() as stack:
            for backend in backends:
                stack.enter_context(patch.object(backend, "_load_resource", side_effect=AssertionError("off must not load")))
            self.assertEqual(prepare_director_skill("none", 4), ("none", 4))
            self.assertEqual(director_instruction("none", "h3"), "")
            h3._build_messages(**h3_args())
            sd._build_messages(**sd_args())

    def test_off_h3_requests_exactly_match_committed_baseline(self):
        old = original_function("nodes.py", "_build_messages", h3)
        for task in ("T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA"):
            for lang in ("中文", "English"):
                args = h3_args(task_type=task, output_language=lang, media_plan=[{"label": "<Picture 1>"}],
                               media_parts=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,TEST"}}])
                self.assertEqual(h3._build_messages(**args), old(**args), (task, lang))
                self.assertEqual(h3._build_messages(**args, director_skill="none"), old(**args))

    def test_off_seedance_requests_exactly_match_committed_baseline(self):
        old = original_function("seedance20.py", "_build_messages", sd)
        for task in sd.TASK_INTENT_LABELS:
            for lang in ("中文", "English"):
                args = sd_args(task_intent=task, output_language=lang)
                self.assertEqual(sd._build_messages(**args), old(**args), (task, lang))

    def test_on_pauses_optional_templates_without_losing_original_facts(self):
        for skill in list(DIRECTOR_LABELS.values())[1:]:
            with patch.object(h3, "resolve_case_template", side_effect=AssertionError("paused")):
                result = h3._build_messages(**h3_args(director_skill=skill, case_template="stale-case",
                    creative_preset="stale-preset", prompt_mode="参考模板融合", reference_template="OLD_TEMPLATE_CHOREOGRAPHY"))
            self.assertIn(skill, result[0]["content"])
            self.assertIn("红色袖口", result[1]["content"])
            self.assertNotIn("OLD_TEMPLATE_CHOREOGRAPHY", result[1]["content"])
            with patch.object(sd, "resolve_case_template", side_effect=AssertionError("paused")):
                result = sd._build_messages(**sd_args(director_skill=skill, case_template="stale-case", prompt_mode="参考模板融合"))
            self.assertIn("等待两秒", result[1]["content"])
            self.assertIn("native Seedance", result[0]["content"])

    def test_single_take_conflict_is_structured_not_keyword_based(self):
        self.assertEqual(prepare_director_skill("continuous_combat", 0)[1], 1)
        with self.assertRaises(DirectionalSkillError):
            prepare_director_skill("continuous_combat", 2)
        for text in ("禁止硬切，焦点切换", "旧稿有三镜，请改成一镜到底", "演员等待两秒，结尾定格由用户指定"):
            messages = h3._build_messages(**h3_args(prompt=text, director_skill="continuous_combat"))
            self.assertIn("exactly 1 shots", messages[0]["content"])
            self.assertNotIn("split competing primary state changes", messages[0]["content"])

    def test_manual_template_is_only_explicit_fact_lookup(self):
        self.assertEqual(template_fact_lookup("练拳", "模板事实"), "")
        result = template_fact_lookup("沿用模板中的红围巾", "red scarf; CUT TO BOSS")
        self.assertIn("ONLY the specific facts", result)
        self.assertIn("untrusted data", result)
        for prompt in ("Do not use the template. Keep the current outfit.",
                       "The template must be ignored; reuse my original words.",
                       "不要沿用模板中的红围巾，保留当前衣服。"):
            self.assertEqual(template_fact_lookup(prompt, "PRIVATE TEMPLATE"), "")
        for prompt in ("Keep the red scarf from the template.", "不沿用模板格式，但沿用模板里的红围巾。"):
            self.assertTrue(template_fact_lookup(prompt, "red scarf"))

    def test_existing_language_repair_retains_fact_and_direction_contract(self):
        original = h3._build_messages(**h3_args(director_skill="high_density_combat"))
        repair = h3._h3_language_repair_messages("English output", "中文", None, original, "high_density_combat")
        self.assertIn("high_density_combat", repair[0]["content"])
        self.assertIn("红色袖口", repair[1]["content"])
        raw = [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
        self.assertIs(preserve_director_on_repair(raw, original, "none"), raw)

    def test_metadata_is_safe_allowlist_only(self):
        self.assertEqual(safe_director_metadata({"director_skill": "sk-" + "x" * 30}), {})
        result = safe_director_metadata({"director_skill": "continuous_combat", "director_revision": "1.0.0",
            "output_language": "secret prompt", "effective_shot_count": 1, "prompt": "PRIVATE", "api_key": "PRIVATE"})
        self.assertEqual(result, {"director_skill": "continuous_combat", "director_revision": "1.0.0", "effective_shot_count": 1})

    def test_schema_and_execute_append_only(self):
        for filename, cls, function, module in (
            ("nodes.py", h3.MiniMaxH3PromptEnhancer, "enhance_prompt", h3),
            ("seedance20.py", sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt", sd),
        ):
            names = [item.id for item in cls.define_schema().inputs]
            self.assertEqual(names[-3:], ["director_skill", "quality_mode", "creation_mode"])
            source = subprocess.check_output(["git", "show", f"{BASELINE_COMMIT}:{filename}"], cwd=ROOT).decode("utf-8")
            definition = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
            old_names = [n.arg for n in definition.args.args]
            current = list(inspect.signature(getattr(module, function)).parameters)
            self.assertEqual(current[:len(old_names)], old_names)
            self.assertEqual(current[len(old_names):], ["director_skill", "quality_mode", "creation_mode"])
            self.assertEqual(len(cls.define_schema().outputs), 6 if filename == "nodes.py" else 1)

    def test_non_mapping_resource_metadata_is_wrapped_and_off_stays_independent(self):
        loaders = {_load_resource, sys.modules[h3.prepare_director_skill.__module__]._load_resource}
        for loader in loaders:
            backend = sys.modules[loader.__module__]
            for value in ("[]", "null", '"not a mapping"', "42"):
                with self.subTest(backend=backend.__name__, metadata=value):
                    loader.cache_clear()
                    with patch.object(backend.Path, "read_text", side_effect=[value, "Director rules."]):
                        with self.assertRaises(backend.DirectionalSkillError):
                            loader("continuous_combat")
                    with patch.object(backend, "_load_resource", side_effect=AssertionError("Off must not inspect damaged resources")):
                        self.assertEqual(backend.prepare_director_skill("none", 3), ("none", 3))
                        self.assertEqual(backend.director_instruction("none", "h3"), "")

    def test_all_local_parameters_and_budget_actual_media_share_director_contract(self):
        field_names = {
            "local_model": "model_filename", "local_mmproj": "mmproj_filename",
            "local_context_size": "context_size", "local_max_tokens": "max_tokens",
            "local_think_mode": "think_mode", "local_reasoning_effort": "reasoning_effort",
            "local_video_sample_fps": "video_sample_fps", "local_unload_policy": "unload_policy",
            "local_comfy_memory_policy": "comfy_memory_policy",
        }
        image = np.zeros((1, 16, 16, 3), dtype=np.float32)
        for module in (h3, sd):
            for skill in list(DIRECTOR_LABELS.values())[1:]:
                for attached in (False, True):
                    for language in ("中文", "English"):
                        with self.subTest(platform=module.__name__, skill=skill, image=attached, language=language):
                            instances = []
                            parameters = local_parameters(module)
                            response = native_draft(language == "中文") if module is h3 else (
                                "女人保持红色袖口，镜头连续跟随她向前滑步，车票始终在她的右手中。"
                                if language == "中文" else "The camera follows the woman in one shot; her red sleeve and right-hand ticket remain stable."
                            )

                            def factory(settings, *, vision):
                                instance = RecordingLocalProvider(settings, vision=vision, responses=[response])
                                instances.append(instance)
                                return instance

                            inputs = dict(prompt="Keep the red sleeve. LOCK: ticket stays in the right hand.",
                                          api_mode=module.LOCAL_QWEN_API_MODE, output_language=language,
                                          director_skill=skill, seed=98765, **parameters)
                            if module is h3:
                                inputs["task_type"] = "I2VA" if attached else "T2VA"
                                function = module.enhance_prompt
                            else:
                                inputs["task_intent"] = "I2V" if attached else "T2V"
                                function = module.enhance_seedance20_prompt
                            if attached:
                                inputs["first_frame"] = image
                            with patch.object(module, "LocalQwenProvider", side_effect=factory), \
                                 patch.object(module, "local_qwen_settings", wraps=module.local_qwen_settings) as settings_call, \
                                 patch.object(module, "_build_messages", wraps=module._build_messages) as builds, \
                                 patch.object(module, "local_visual_part_budget", wraps=module.local_visual_part_budget) as budget, \
                                 patch.object(module, "build_local_multimodal_parts", wraps=module.build_local_multimodal_parts) as media:
                                result = function(**inputs)
                            self.assertEqual(result, response)
                            self.assertEqual(len(instances), 1)
                            instance = instances[0]
                            self.assertTrue(instance.closed)
                            self.assertEqual(instance.vision, attached)
                            self.assertEqual(len(instance.calls), 1)
                            self.assertEqual(settings_call.call_args.kwargs, parameters)
                            for parameter, field in field_names.items():
                                self.assertEqual(getattr(instance.settings, field), parameters[parameter])
                            self.assertEqual(builds.call_count, 2)
                            signature = inspect.signature(builds._mock_wraps)
                            first, second = [signature.bind(*call.args, **call.kwargs).arguments for call in builds.call_args_list]
                            expected_shots = 1 if skill == "continuous_combat" else 0
                            self.assertEqual(first["director_skill"], skill)
                            self.assertEqual(second["director_skill"], skill)
                            self.assertEqual(first["shot_count"], expected_shots)
                            self.assertEqual(second["shot_count"], expected_shots)
                            self.assertIs(first["media_plan"], second["media_plan"])
                            self.assertEqual(first["media_parts"], [])
                            self.assertEqual(bool(second["media_parts"]), attached)
                            budget.assert_called_once()
                            media.assert_called_once()
                            self.assertIs(budget.call_args.args[1], instance.settings)
                            self.assertIs(media.call_args.args[1], instance.settings)
                            self.assertEqual(budget.call_args.kwargs["required_visual_parts"], int(attached))
                            self.assertEqual(set(media.call_args.kwargs), {"max_visual_parts"})
                            budget_messages = budget.call_args.args[0]
                            sent = instance.calls[0]["messages"]
                            self.assertEqual(budget_messages[0]["content"], sent[0]["content"])
                            self.assertEqual(primary_text(budget_messages[1]["content"]), primary_text(sent[1]["content"]))
                            self.assertIn(skill, sent[0]["content"])
                            self.assertTrue(sent[0]["content"].endswith(module.apply_local_language_lock(
                                [{"role": "system", "content": ""}], language)[0]["content"].strip()))
                            if attached:
                                image_parts = [part for part in sent[1]["content"] if part.get("type") == "image_url"]
                                self.assertEqual(len(image_parts), 1)
                                self.assertTrue(image_parts[0]["image_url"]["url"].startswith("data:image/"))
                                label_parts = [part["text"] for part in second["media_parts"] if part.get("type") == "text"]
                                self.assertTrue(any(first["media_plan"][0]["label"] in label for label in label_parts))
                            self.assertEqual(instance.calls[0]["kwargs"], {"temperature": 0.7, "seed": 98765})

    def test_relay_format_then_language_repairs_keep_facts_and_director_on_both_transports(self):
        malformed = json.loads(relay_draft())
        malformed["native_prompt"] = ""
        responses = [json.dumps(malformed), relay_draft(), relay_draft(True)]
        for skill, transport in ((skill, transport) for skill in list(DIRECTOR_LABELS.values())[1:] for transport in ("local", "cloud")):
            with self.subTest(skill=skill, transport=transport):
                inputs = dict(prompt="保留红色袖口。LOCK: ticket stays in the right hand.",
                              constraints="不添加武器，角色持续持有车票。", output_language="中文",
                              duration_seconds=8, director_skill=skill,
                              relay_config={"event_count": 2, "time_ranges": "0-4\n4-8"}, seed=12)
                if transport == "local":
                    instances = []

                    def factory(settings, *, vision):
                        instance = RecordingLocalProvider(settings, vision=vision, responses=responses)
                        instances.append(instance)
                        return instance

                    with patch.object(h3, "LocalQwenProvider", side_effect=factory):
                        result = h3.enhance_prompt(**inputs, api_mode=h3.LOCAL_QWEN_API_MODE)
                    calls = instances[0].calls
                    self.assertTrue(instances[0].closed)
                else:
                    session = test_seedance20.SequencedChatSession(responses)
                    result = h3.enhance_prompt(**inputs, session=session, api_key="test-placeholder")
                    calls = [{"messages": call["json"]["messages"]} for call in session.chat_requests]
                self.assertEqual(result, responses[-1])
                self.assertEqual(len(calls), 3)
                for call in calls:
                    self.assertIn(skill, call["messages"][0]["content"])
                    joined = "\n".join(primary_text(message["content"]) for message in call["messages"] if message["role"] == "user")
                    self.assertIn("红色袖口", joined)
                    self.assertIn("ticket stays in the right hand", joined)
                    self.assertIn("不添加武器", joined)
                self.assertIn("Repair the Relay JSON structure once", calls[1]["messages"][-1]["content"])
                self.assertIn("LANGUAGE REPAIR ONLY", calls[2]["messages"][0]["content"])
                self.assertIn("Return JSON", calls[2]["messages"][0]["content"])

    def test_relay_corrections_are_bounded_without_a_third_provider_call(self):
        malformed = json.loads(relay_draft())
        malformed["native_prompt"] = ""
        bad = json.dumps(malformed)
        for failure, responses in (("format", [bad, bad]), ("language", [relay_draft(), relay_draft()])):
            with self.subTest(failure=failure):
                instances = []

                def factory(settings, *, vision):
                    instance = RecordingLocalProvider(settings, vision=vision, responses=responses)
                    instances.append(instance)
                    return instance

                with patch.object(h3, "LocalQwenProvider", side_effect=factory):
                    with self.assertRaises(h3.PromptEnhancerError):
                        h3.enhance_prompt("保留红色袖口。", api_mode=h3.LOCAL_QWEN_API_MODE,
                                          output_language="中文", director_skill="continuous_combat",
                                          relay_config={"event_count": 2, "time_ranges": ""})
                self.assertEqual(len(instances[0].calls), 2)
                self.assertTrue(instances[0].closed)

    def test_directional_preflight_failures_preserve_previous_recoverable_result(self):
        for module, cls, function, component in (
            (h3, h3.MiniMaxH3PromptEnhancer, "enhance_prompt", "MiniMaxH3PromptEnhancerT8"),
            (sd, sd.Seedance20PromptEnhancer, "enhance_seedance20_prompt", "Seedance20PromptEnhancerT8"),
        ):
            recovery = sys.modules[module.begin_recovery_record.__module__]
            backend = sys.modules[module.prepare_director_skill.__module__]
            for failure in ("unknown", "multiple_shots", "missing_resource"):
                with self.subTest(platform=component, failure=failure):
                    slot = f"t8-dir-preserve-{component}-{failure}"
                    metadata = {"director_skill": "cinematic_gunfight", "director_revision": "1.0.0",
                                "output_language": "English", "output_mode": h3.NORMAL if module is h3 else "Seedance 2.0",
                                "effective_shot_count": 1}
                    module.begin_recovery_record(component, slot, "test-provider", metadata=metadata)
                    module.complete_recovery_record(component, slot, ("previous complete paid result",))
                    original = recovery.recovery_status(component, slot)
                    inputs = execute_inputs(module)
                    inputs.update(recovery_slot=slot, director_skill="bad-selection" if failure == "unknown" else "continuous_combat")
                    if failure == "multiple_shots":
                        inputs["shot_count"] = "2"
                    with ExitStack() as stack:
                        completion = stack.enter_context(patch.object(module, function, side_effect=AssertionError("No generation after invalid preflight")))
                        begin = stack.enter_context(patch.object(module, "begin_recovery_record", wraps=module.begin_recovery_record))
                        if failure == "missing_resource":
                            stack.enter_context(patch.object(backend, "_load_resource", side_effect=backend.DirectionalSkillError("selected resource missing")))
                        with self.assertRaises(module.PromptEnhancerError):
                            cls.execute(**inputs)
                    completion.assert_not_called()
                    begin.assert_not_called()
                    current = recovery.recovery_status(component, slot)
                    for key in ("state", "recoverable", "creation_metadata"):
                        self.assertEqual(current[key], original[key])
                    self.assertEqual(recovery.recover_outputs(component, slot, 1), ("previous complete paid result",))

    def test_off_execute_passes_exact_legacy_kwargs_without_director_parameter(self):
        for module, cls, filename, function in (
            (h3, h3.MiniMaxH3PromptEnhancer, "nodes.py", "enhance_prompt"),
            (sd, sd.Seedance20PromptEnhancer, "seedance20.py", "enhance_seedance20_prompt"),
        ):
            for shared in (False, True):
                with self.subTest(platform=filename, shared_provider=shared):
                    inputs = execute_inputs(module)
                    inputs.update(prompt_mode="参考模板融合", reference_template="Keep this saved template.",
                                  case_template=module.CASE_TEMPLATE_OPTIONS[1], **local_parameters(module))
                    if module is h3:
                        inputs["creative_preset"] = h3.CREATIVE_PRESET_OPTIONS[1]
                    if shared:
                        config_module = sys.modules[module.merge_provider_config.__module__]
                        config = config_module.build_provider_config(provider=config_module.PROVIDER_LOCAL, **local_parameters(module))
                        config["director_skill"] = "cinematic_gunfight"  # Not a provider field; must be ignored.
                        inputs["provider_config"] = config
                    with patch.object(module, function, return_value="unchanged original result") as completion:
                        old = original_execute(filename, cls.__name__, module)
                        baseline = old(cls, **inputs)
                        expected = dict(completion.call_args.kwargs)
                        completion.reset_mock()
                        current = cls.execute(**inputs, director_skill="none")
                        actual = dict(completion.call_args.kwargs)
                    self.assertEqual(tuple(current.result), tuple(baseline.result))
                    self.assertNotIn("director_skill", actual)
                    for values in (expected, actual):
                        callback = values.pop("progress_callback")
                        self.assertTrue(callable(callback))
                        self.assertEqual(callback.__self__.component, cls.define_schema().node_id)
                    self.assertEqual(actual, expected)

    def test_off_full_local_pipeline_matches_baseline_messages_settings_and_provider_kwargs(self):
        image = np.zeros((1, 16, 16, 3), dtype=np.float32)
        for module, filename, function_name in ((h3, "nodes.py", "enhance_prompt"), (sd, "seedance20.py", "enhance_seedance20_prompt")):
            for attached in (False, True):
                with self.subTest(platform=filename, image=attached):
                    inputs = dict(prompt="Keep the red sleeve and the right-hand ticket.", output_language="English",
                                  api_mode=module.LOCAL_QWEN_API_MODE, seed=54321, **local_parameters(module))
                    inputs["task_type" if module is h3 else "task_intent"] = (
                        ("I2VA" if attached else "T2VA") if module is h3 else ("I2V" if attached else "T2V")
                    )
                    if attached:
                        inputs["first_frame"] = image
                    response = native_draft() if module is h3 else "The camera tracks the woman; her red sleeve and right-hand ticket stay unchanged."
                    snapshots = []
                    for baseline in (True, False):
                        instances = []

                        def factory(settings, *, vision):
                            instance = RecordingLocalProvider(settings, vision=vision, responses=[response])
                            instances.append(instance)
                            return instance

                        with patch.object(module, "LocalQwenProvider", side_effect=factory), \
                             patch.object(module, "local_qwen_settings", wraps=module.local_qwen_settings) as settings, \
                             patch.object(module, "local_visual_part_budget", wraps=module.local_visual_part_budget) as budget, \
                             patch.object(module, "build_local_multimodal_parts", wraps=module.build_local_multimodal_parts) as media:
                            function = original_function(filename, function_name, module) if baseline else getattr(module, function_name)
                            result = function(**inputs)
                        instance = instances[0]
                        snapshots.append((result, instance.settings, instance.vision, instance.calls,
                                          settings.call_args.kwargs, budget.call_args.kwargs, media.call_args.kwargs))
                        self.assertTrue(instance.closed)
                        self.assertNotIn("director_skill", settings.call_args.kwargs)
                        self.assertNotIn("director_skill", instance.calls[0]["kwargs"])
                    self.assertEqual(snapshots[0], snapshots[1])

    def test_cpu_regressions_do_not_initialize_cuda(self):
        import torch
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
