import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = PROJECT_ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))


def _isolated_module():
    """Load the contract module without importing the GPU-only Comfy runtime."""
    package_name = "t8_qwen_image_isolated"
    comfy_api = types.ModuleType("comfy_api")
    latest = types.ModuleType("comfy_api.latest")

    class Descriptor:
        def __init__(self, identifier=None, display_name=None, **kwargs):
            self.id = identifier
            self.display_name = display_name
            self.kwargs = kwargs

    class TypeFactory:
        @classmethod
        def Input(cls, identifier, display_name=None, **kwargs):
            return Descriptor(identifier, display_name, **kwargs)

        @classmethod
        def Output(cls, display_name=None, **kwargs):
            return Descriptor(None, display_name, **kwargs)

    class IO:
        ComfyNode = object
        String = type("String", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Combo = type("Combo", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Image = type("Image", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Boolean = type("Boolean", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Int = type("Int", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Float = type("Float", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
        Autogrow = type("Autogrow", (), {
            "Input": TypeFactory.Input,
            "TemplatePrefix": staticmethod(lambda **kwargs: kwargs),
        })
        Custom = staticmethod(lambda *_args, **_kwargs: type("CustomType", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output}))
        Schema = staticmethod(lambda **kwargs: types.SimpleNamespace(**kwargs))

        class NodeOutput(tuple):
            def __new__(cls, *values, **kwargs):
                return tuple.__new__(cls, values)

    latest.io = IO
    latest.ComfyExtension = object
    comfy_api.latest = latest
    sys.modules["comfy_api"] = comfy_api
    sys.modules["comfy_api.latest"] = latest

    nodes = types.ModuleType(f"{package_name}.nodes")
    nodes.AI_WORKSHOP_API_MODE = "workshop"
    nodes.AI_WORKSHOP_DEFAULT_MODEL = "gemini-3.5-flash"
    nodes.AI_WORKSHOP_MODEL_OPTIONS = [nodes.AI_WORKSHOP_DEFAULT_MODEL, "Custom（自定义）"]
    nodes.API_MODES = ["seedance", "workshop", "openai", "local"]
    nodes.LEGACY_UI_VALUES = set()
    nodes.OPENAI_API_MODE = "openai"
    nodes.PromptEnhancerError = RuntimeError
    nodes.SEEDANCE_API_MODE = "seedance"
    nodes._image_count = lambda image: 1 if len(image.shape) == 3 else int(image.shape[0])
    nodes._image_at = lambda image, index: image if len(image.shape) == 3 else image[index]
    nodes._ordered_values = lambda values: [values[key] for key in sorted(values or {})]
    nodes._inline_media_plan = lambda plan: []
    nodes._openai_media_plan = lambda plan, urls, video_sample_fps=2.0: []
    nodes._provider_config = lambda *args: ("", "", "", "")
    nodes._request_completion = lambda *args, **kwargs: ""
    nodes._upload_media_plan = lambda *args, **kwargs: []
    sys.modules[f"{package_name}.nodes"] = nodes

    local = types.ModuleType(f"{package_name}.local_qwen_provider")
    local.DEFAULT_CONTEXT_SIZE = 32768
    local.DEFAULT_MAX_TOKENS = 16384
    local.DEFAULT_VIDEO_SAMPLE_FPS = 2.0
    local.LOCAL_QWEN_API_MODE = "local"
    local.LOCAL_REASONING_OPTIONS = ["medium"]
    local.LOCAL_THINK_OFF = "off"
    local.LOCAL_THINK_ON = "on"
    local.LOCAL_UNLOAD_AFTER_RUN = "unload"
    local.LOCAL_UNLOAD_POLICIES = ["unload"]
    local.MAX_OUTPUT_TOKENS = 61440
    local.LocalQwenProvider = object
    local.LocalQwenProviderError = RuntimeError
    local.apply_local_language_lock = lambda messages, language: messages
    local.build_local_multimodal_parts = lambda *args, **kwargs: ([], {})
    local.is_local_qwen_api_mode = lambda value: value == "local"
    local.local_visual_part_budget = lambda *args, **kwargs: 16
    local.settings_from_values = lambda **kwargs: types.SimpleNamespace(**kwargs)
    sys.modules[f"{package_name}.local_qwen_provider"] = local

    runtime = types.ModuleType(f"{package_name}.local_qwen_runtime")
    runtime.AUTO_MMPROJ = "AUTO"
    runtime.DEFAULT_MMPROJ_FILENAME = "mmproj.gguf"
    runtime.DEFAULT_MODEL_FILENAME = "model.gguf"
    runtime.LOCAL_COMFY_MEMORY_POLICIES = ["auto"]
    runtime.list_gguf_models = lambda: [runtime.DEFAULT_MODEL_FILENAME]
    runtime.list_mmproj_models = lambda: [runtime.AUTO_MMPROJ]
    sys.modules[f"{package_name}.local_qwen_runtime"] = runtime

    capabilities = types.ModuleType(f"{package_name}.provider_capabilities")
    capabilities.apply_chat_request_options = lambda payload, **kwargs: dict(payload)
    sys.modules[f"{package_name}.provider_capabilities"] = capabilities

    config = types.ModuleType(f"{package_name}.provider_config")
    config.PROVIDER_LOCAL = "local"
    config.PROVIDER_OPENAI = "openai"
    config.PROVIDER_SEEDANCE = "seedance"
    config.PROVIDER_WORKSHOP = "workshop"
    config.T8ProviderConfigIO = type("T8ProviderConfigIO", (), {"Input": TypeFactory.Input, "Output": TypeFactory.Output})
    config.merge_provider_config = lambda current, provider_config, **kwargs: dict(current)
    sys.modules[f"{package_name}.provider_config"] = config

    package = types.ModuleType(package_name)
    package.__path__ = [str(PROJECT_ROOT)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(f"{package_name}.qwen_image21", PROJECT_ROOT / "qwen_image21.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    SPEC = importlib.util.spec_from_file_location(
        "t8_qwen_image_test_package",
        PROJECT_ROOT / "__init__.py",
        submodule_search_locations=[str(PROJECT_ROOT)],
    )
    PACKAGE = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = PACKAGE
    SPEC.loader.exec_module(PACKAGE)
    qwen = sys.modules[f"{SPEC.name}.qwen_image21"]
except ModuleNotFoundError:
    qwen = _isolated_module()


class QwenImage21ContractTests(unittest.TestCase):
    def test_extension_registration_is_present(self):
        source = (PROJECT_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("from .qwen_image21 import QwenImage21PromptEnhancer", source)
        self.assertIn("            QwenImage21PromptEnhancer,", source)

    def test_skill_snapshot_and_schema(self):
        self.assertTrue(qwen._load_skill().startswith("# Image Prompt Rewriting Expert"))
        schema = qwen.QwenImage21PromptEnhancer.define_schema()
        self.assertEqual(schema.node_id, qwen.NODE_ID)
        names = [item.id for item in schema.inputs]
        self.assertIn("reference_images", names)
        self.assertIn("max_output_chars", names)
        self.assertIn("transparent_alpha", names)
        self.assertIn("recovery_slot", names)
        self.assertIn("recovery_action", names)
        self.assertEqual([output.display_name for output in schema.outputs], [
            "rewritten_prompt", "wh_ratio", "qwen_image_request_json", "enhancement_report_json",
        ])

    def test_fenced_json_and_output_contract(self):
        payload = qwen._extract_json('```json\n{"rewritten_prompt":"A clean scene.","wh_ratio":"1:1"}\n```')
        self.assertEqual(payload["wh_ratio"], "1:1")
        prompt, ratio, details = qwen._validate_output(payload, requested_ratio="1:1", transparent=False, max_chars=0)
        self.assertEqual((prompt, ratio), ("A clean scene.", "1:1"))
        self.assertFalse(details["over_limit"])
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen._validate_output(
                {"rewritten_prompt": "A clean scene.", "wh_ratio": "1:1", "extra": "ignored?"},
                requested_ratio="1:1", transparent=False, max_chars=0,
            )
        quoted, _, _ = qwen._validate_output(
            {"rewritten_prompt": 'A label reads "1:1" exactly.', "wh_ratio": "1:1"},
            requested_ratio="1:1", transparent=False, max_chars=0,
        )
        self.assertIn('"1:1"', quoted)
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen._validate_output(
                {"rewritten_prompt": "A clean scene.", "wh_ratio": "auto"},
                requested_ratio="auto", transparent=False, max_chars=0,
            )

    def test_api_key_is_allowed_only_in_credential_field(self):
        self.assertEqual(qwen._clean_secret("sk-ABCDEFGHIJKLMNOPQRST", "api_key"), "sk-ABCDEFGHIJKLMNOPQRST")
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen._clean_secret("include sk-ABCDEFGHIJKLMNOPQRST here", "prompt")

    def test_input_modes_reject_wrong_media_count(self):
        image = np.zeros((1, 1, 3), dtype=np.float32)
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen.QwenImage21PromptEnhancer.validate_inputs(
                prompt="a cat", input_mode=qwen.INPUT_MODE_TEXT, reference_images={"reference_image_0": image},
            )
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen.QwenImage21PromptEnhancer.validate_inputs(
                prompt="edit this", input_mode=qwen.INPUT_MODE_EDIT, reference_images=None,
            )
        eleven = {f"reference_image_{index}": image for index in range(11)}
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen.QwenImage21PromptEnhancer.validate_inputs(
                prompt="edit these", input_mode=qwen.INPUT_MODE_EDIT, reference_images=eleven,
            )

    def test_flat_autogrow_reference_inputs_are_normalized(self):
        image = np.zeros((1, 1, 3), dtype=np.float32)
        qwen.QwenImage21PromptEnhancer.validate_inputs(
            prompt="edit these",
            input_mode=qwen.INPUT_MODE_EDIT,
            reference_image_0=image,
            **{"reference_images.reference_image_1": image},
        )
        normalized = qwen._coerce_reference_images(
            None,
            {"reference_image_0": image, "reference_images.reference_image_1": image},
        )
        self.assertEqual(list(normalized), ["reference_image_0", "reference_image_1"])
        self.assertEqual(len(qwen._image_plan(normalized)), 2)

    def test_linked_reference_slots_are_deferred_during_validation(self):
        # ComfyUI supplies None placeholders for linked upstream IMAGE values
        # while validating; the actual tensors arrive during execute().
        qwen.QwenImage21PromptEnhancer.validate_inputs(
            prompt="edit this bag",
            input_mode=qwen.INPUT_MODE_EDIT,
            reference_images={"reference_image_0": None, "reference_image_1": None},
        )
        qwen.QwenImage21PromptEnhancer.validate_inputs(
            prompt="edit this bag",
            input_mode=qwen.INPUT_MODE_EDIT,
            reference_images=[None],
        )
        with self.assertRaises(qwen.QwenImage21PromptEnhancerError):
            qwen.QwenImage21PromptEnhancer.validate_inputs(
                prompt="text only",
                input_mode=qwen.INPUT_MODE_TEXT,
                reference_images={"reference_image_0": None},
            )

    def test_linked_prompt_is_checked_after_upstream_execution(self):
        # ComfyUI passes a None placeholder for a linked STRING during graph
        # validation; the actual text arrives only at execute().
        image = np.zeros((1, 1, 3), dtype=np.float32)
        self.assertTrue(qwen.QwenImage21PromptEnhancer.validate_inputs(
            prompt=None, input_mode=qwen.INPUT_MODE_EDIT,
            reference_images={"reference_image_0": None},
        ))
        self.assertTrue(qwen.QwenImage21PromptEnhancer.validate_inputs(
            prompt=None, input_mode=qwen.INPUT_MODE_TEXT,
        ))
        with self.assertRaisesRegex(qwen.QwenImage21PromptEnhancerError, "prompt is required"):
            qwen.QwenImage21PromptEnhancer.validate_inputs(
                prompt="", input_mode=qwen.INPUT_MODE_TEXT,
            )
        with self.assertRaisesRegex(qwen.QwenImage21PromptEnhancerError, "prompt is required"):
            qwen.QwenImage21PromptEnhancer.execute(
                prompt="", input_mode=qwen.INPUT_MODE_EDIT,
                reference_images={"reference_image_0": image},
                api_mode=qwen.LOCAL_QWEN_API_MODE,
            )

    def test_provider_model_and_budget_routing(self):
        self.assertEqual(
            qwen._resolve_image_model(qwen.SEEDANCE_API_MODE, qwen.AI_WORKSHOP_DEFAULT_MODEL, ""),
            qwen.QWEN_IMAGE_MODEL_ID,
        )
        self.assertEqual(
            qwen._resolve_image_model(qwen.AI_WORKSHOP_API_MODE, qwen.AI_WORKSHOP_DEFAULT_MODEL, ""),
            qwen.AI_WORKSHOP_DEFAULT_MODEL,
        )
        self.assertEqual(qwen._resolve_image_model(qwen.OPENAI_API_MODE, "", "vendor/vision"), "vendor/vision")
        self.assertEqual(qwen._resolve_image_model(qwen.LOCAL_QWEN_API_MODE, "", ""), "local-gguf")
        options = qwen._cloud_request_options({"extra_parameters": {"max_completion_tokens": 12345}})
        self.assertEqual(options["extra_parameters"], {"max_completion_tokens": 12345})

    def test_local_mode_needs_no_api_key(self):
        class FakeLocalProvider:
            def __init__(self, settings, vision=False):
                self.vision = vision

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def complete(self, *_args, **_kwargs):
                return json.dumps({"rewritten_prompt": "A local image prompt.", "wh_ratio": "1:1"})

        with patch.object(qwen, "local_qwen_settings", return_value=object()), \
                patch.object(qwen, "LocalQwenProvider", FakeLocalProvider), \
                patch.object(qwen, "local_visual_part_budget", return_value=0), \
                patch.object(qwen, "build_local_multimodal_parts", return_value=([], {})), \
                patch.object(qwen, "_provider_config", side_effect=AssertionError("cloud path must not run")):
            output = qwen.QwenImage21PromptEnhancer.execute(
                prompt="a square product photo", wh_ratio="1:1",
                api_mode=qwen.LOCAL_QWEN_API_MODE, api_key="",
            )
        self.assertEqual(output[0], "A local image prompt.")

    def test_disconnected_stream_is_accepted_only_when_qwen_json_is_valid(self):
        complete = json.dumps({"rewritten_prompt": "A complete image description.", "wh_ratio": "1:1"})
        self.assertTrue(
            qwen._accept_complete_stream(
                complete, requested_ratio="1:1", transparent=False, max_chars=0,
            )
        )
        self.assertFalse(
            qwen._accept_complete_stream(
                complete[:-1], requested_ratio="1:1", transparent=False, max_chars=0,
            )
        )

    def test_all_requested_ratios_and_transparency_contract(self):
        for ratio in qwen.RATIO_OPTIONS:
            qwen._validate_mode("brief", qwen.INPUT_MODE_TEXT, [], ratio, 0, False)
        prompt, ratio, _ = qwen._validate_output(
            {"rewritten_prompt": "An RGBA icon with an alpha channel and a transparent background.", "wh_ratio": "2:3"},
            requested_ratio="auto", transparent=True, max_chars=0,
        )
        self.assertIn("RGBA", prompt)
        self.assertEqual(ratio, "2:3")

    def test_cloud_default_model_and_ten_image_count(self):
        image = np.zeros((1, 1, 3), dtype=np.float32)
        ten = {f"reference_image_{index}": image for index in range(10)}
        valid = json.dumps({"rewritten_prompt": "A complete English image description.", "wh_ratio": "2:3"})
        with patch.object(qwen, "_provider_config", return_value=(
            "test-key", "https://api.seedance.nz/v1/chat/completions", "https://api.seedance.nz/v1/files/upload", "Seedance",
        )), patch.object(qwen, "_upload_media_plan", return_value=[]), patch.object(qwen, "_request_completion", return_value=valid) as request:
            result = qwen.QwenImage21PromptEnhancer.execute(
                prompt="a vertical portrait", input_mode=qwen.INPUT_MODE_EDIT, reference_images=ten,
                wh_ratio="auto", api_key="test-credential",
            )
        self.assertEqual(json.loads(result[3])["image_count"], 10)
        self.assertEqual(request.call_args.args[-1], qwen.QWEN_IMAGE_MODEL_ID)
        self.assertEqual(request.call_args.kwargs["provider_request_options"]["extra_parameters"]["max_tokens"], 8192)

    def test_max_chars_uses_one_bounded_correction(self):
        first = json.dumps({"rewritten_prompt": "too-long-description", "wh_ratio": "1:1"})
        second = json.dumps({"rewritten_prompt": "short", "wh_ratio": "1:1"})
        with patch.object(qwen, "_provider_config", return_value=(
            "test-key", "https://api.seedance.nz/v1/chat/completions", "", "Seedance",
        )), patch.object(qwen, "_request_completion", side_effect=[first, second]) as request:
            result = qwen.QwenImage21PromptEnhancer.execute(
                prompt="a square icon", max_output_chars=5, wh_ratio="1:1", api_key="test-credential",
            )
        self.assertEqual(result[0], "short")
        self.assertEqual(json.loads(result[3])["correction_calls"], 1)
        self.assertEqual(request.call_count, 2)

    def test_cloud_result_can_be_recovered_without_a_second_request(self):
        valid = json.dumps({"rewritten_prompt": "A recoverable image description.", "wh_ratio": "1:1"})
        slot = "t8-qwen-recovery-0001"
        with patch.object(qwen, "_provider_config", return_value=(
            "test-key", "https://api.seedance.nz/v1/chat/completions", "", "Seedance",
        )), patch.object(qwen, "_request_completion", return_value=valid) as request:
            first = qwen.QwenImage21PromptEnhancer.execute(
                prompt="a square icon", wh_ratio="1:1", api_key="test-credential", recovery_slot=slot,
            )
            restored = qwen.QwenImage21PromptEnhancer.execute(
                prompt="this input is ignored during restore", wh_ratio="auto",
                api_key="test-credential", recovery_slot=slot, recovery_action=qwen.RECOVERY_ACTION_RESTORE,
            )
        self.assertEqual(tuple(restored), tuple(first))
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
