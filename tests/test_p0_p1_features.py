import importlib.util
import inspect
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_p0_p1_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
credentials = sys.modules[f"{SPEC.name}.credential_store"]
provider_config = sys.modules[f"{SPEC.name}.provider_config"]
inspector = sys.modules[f"{SPEC.name}.prompt_inspector"]
credential_routes = sys.modules[f"{SPEC.name}.credential_routes"]
core_nodes = sys.modules[f"{SPEC.name}.nodes"]
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]


class FakeConnectionResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class P0P1FeatureTests(unittest.TestCase):
    def test_utility_example_widget_order_matches_comfy_runtime_order(self):
        workflow = json.loads((ROOT / "example_workflows" / "prompt_inspector_local_qwen_example.json").read_text(encoding="utf-8"))
        by_type = {node["type"]: node for node in workflow["nodes"]}

        config_schema = provider_config.T8LLMProviderConfig.define_schema()
        config_info = config_schema.get_v1_info(provider_config.T8LLMProviderConfig)
        config_names = config_info.input_order["required"] + config_info.input_order["optional"]
        self.assertEqual(
            config_names,
            [
                "provider", "temperature_policy", "local_model", "local_mmproj", "local_context_size",
                "local_max_tokens", "local_think_mode", "local_reasoning_effort", "local_video_sample_fps",
                "local_unload_policy", "local_comfy_memory_policy", "credential_alias", "openai_base_url",
                "custom_model", "ai_workshop_model", "extra_parameters_json",
            ],
        )
        config_values = dict(zip(config_names, by_type["T8LLMProviderConfig"]["widgets_values"], strict=True))
        self.assertEqual(config_values["provider"], provider_config.PROVIDER_LOCAL)
        self.assertEqual(config_values["local_model"], core_nodes.DEFAULT_MODEL_FILENAME)
        self.assertEqual(config_values["local_mmproj"], core_nodes.AUTO_MMPROJ)

        inspector_schema = inspector.T8PromptInspector.define_schema()
        inspector_info = inspector_schema.get_v1_info(inspector.T8PromptInspector)
        inspector_names = [
            name for name in inspector_info.input_order["required"] + inspector_info.input_order["optional"]
            if name != "prompt"
        ]
        inspector_values = dict(zip(inspector_names, by_type["T8PromptInspector"]["widgets_values"], strict=True))
        self.assertEqual(inspector_values["duration_seconds"], 15)
        self.assertEqual(inspector_values["task_intent"], "")

    def test_original_node_ids_and_outputs_remain_first_and_unchanged(self):
        import asyncio

        extension = asyncio.run(package.comfy_entrypoint())
        nodes = asyncio.run(extension.get_node_list())
        schemas = [node.define_schema() for node in nodes]
        self.assertEqual(
            [schema.node_id for schema in schemas[:3]],
            ["MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8", "MiniMaxMusic3PromptEnhancerT8"],
        )
        self.assertEqual([item.display_name for item in schemas[0].outputs], ["enhanced_prompt"])
        self.assertEqual([item.display_name for item in schemas[1].outputs], ["enhanced_prompt"])
        self.assertEqual(
            [item.display_name for item in schemas[2].outputs],
            ["lyrics", "music_caption", "music3_payload_json", "enhancement_report_json"],
        )
        self.assertEqual(
            [schema.node_id for schema in schemas[3:7]],
            ["T8LLMProviderConfig", "T8PromptInspector", "T8PromptText", "T8ShowText"],
        )
        self.assertEqual(
            [schema.node_id for schema in schemas[7:]],
            [
                "T8CreativeDirector",
                "T8CreativeContextAssembler",
                "T8DirectedRevision",
                "T8LongFormPlanner",
                "T8ReferenceRoleMapper",
                "T8CreativeCandidateLab",
                "T8CreativeCandidateSelector",
                "T8StoryboardPack",
                "T8CreativeDNAMixer",
                "T8PersonalCreativePreset",
                "T8MusicCreativeLab",
                "T8CreativeVersionStack",
                "T8MusicVideoBeatSheet",
            ],
        )
        for schema in schemas[:3]:
            self.assertEqual(schema.inputs[-1].id, "provider_config")

    def test_original_serialized_widget_contracts_remain_31_35_38(self):
        expected = {
            "minimax_h3_prompt_enhancer.js": 31,
            "seedance20_prompt_enhancer.js": 35,
            "music3_prompt_enhancer.js": 38,
        }
        for filename, count in expected.items():
            source = (ROOT / "web" / "js" / filename).read_text(encoding="utf-8")
            block = source.split("const SERIALIZED_WIDGET_NAMES = [", 1)[1].split("];", 1)[0]
            names = re.findall(r'^\s*"([A-Za-z0-9_]+)",?\s*$', block, re.MULTILINE)
            self.assertEqual(len(names), count, filename)
            self.assertEqual(len(names), len(set(names)), filename)

    def test_new_request_options_are_appended_after_existing_function_parameters(self):
        h3_names = list(inspect.signature(core_nodes.enhance_prompt).parameters)
        seedance_names = list(inspect.signature(seedance20.enhance_seedance20_prompt).parameters)
        self.assertEqual(h3_names[-2:], ["progress_callback", "provider_request_options"])
        self.assertEqual(seedance_names[-2:], ["progress_callback", "provider_request_options"])

    def test_disconnected_provider_config_is_an_exact_behavioral_noop(self):
        original = {
            "api_key": "saved-or-linked-key",
            "api_mode": "legacy-mode",
            "openai_base_url": "https://legacy.example/v1",
            "custom_model": "legacy/model",
        }
        merged = provider_config.merge_provider_config(original, None, api_mode_map={})
        self.assertEqual({key: merged[key] for key in original}, original)
        self.assertIsNone(merged["provider_request_options"])

    def test_credential_alias_store_is_local_and_never_exposes_secret_in_listing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"T8_PROMPT_ENHANCER_USER_DIR": temporary}):
                credentials.save_credential("seedance-main", "test-token-value")
                self.assertEqual(credentials.list_credential_aliases(), ["seedance-main"])
                self.assertEqual(credentials.get_credential("seedance-main"), "test-token-value")
                self.assertNotIn("test-token-value", json.dumps(credentials.list_credential_aliases()))
                store = credentials.credential_store_path()
                self.assertTrue(store.is_file())
                self.assertTrue(credentials.delete_credential("seedance-main"))
                self.assertEqual(credentials.list_credential_aliases(), [])
                with self.assertRaises(credentials.CredentialStoreError):
                    credentials.save_credential("../escape", "not-allowed")

    def test_credential_directory_symlink_is_rejected_when_platform_supports_it(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as external:
            link = Path(temporary) / "t8-prompt-enhancer"
            try:
                link.symlink_to(Path(external), target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks are unavailable on this Windows configuration")
            with patch.dict(os.environ, {"T8_PROMPT_ENHANCER_USER_DIR": temporary}):
                with self.assertRaises(credentials.CredentialStoreError):
                    credentials.credential_store_path()

    def test_existing_api_key_wins_and_alias_only_fills_an_empty_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"T8_PROMPT_ENHANCER_USER_DIR": temporary}):
                credentials.save_credential("shared", "alias-secret")
                config = provider_config.build_provider_config(
                    provider=provider_config.PROVIDER_OPENAI,
                    credential_alias="shared",
                    openai_base_url="https://provider.example/v1",
                    custom_model="vision/model",
                    temperature_policy="省略 temperature",
                    extra_parameters_json='{"top_p":0.8}',
                )
                mapping = {provider_config.PROVIDER_OPENAI: "openai-mode"}
                preserved = provider_config.merge_provider_config(
                    {"api_key": "linked-key", "api_mode": "old"}, config, api_mode_map=mapping,
                )
                resolved = provider_config.merge_provider_config(
                    {"api_key": "", "api_mode": "old"}, config, api_mode_map=mapping,
                )
                self.assertEqual(preserved["api_key"], "linked-key")
                self.assertEqual(resolved["api_key"], "alias-secret")
                self.assertEqual(resolved["api_mode"], "openai-mode")
                self.assertEqual(resolved["provider_request_options"]["temperature_policy"], "omit")
                self.assertEqual(resolved["provider_request_options"]["extra_parameters"], {"top_p": 0.8})

    def test_connection_probe_uses_stored_alias_and_returns_only_safe_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"T8_PROMPT_ENHANCER_USER_DIR": temporary}):
                credentials.save_credential("probe", "private-test-token")
                with patch.object(
                    credential_routes.requests,
                    "post",
                    return_value=FakeConnectionResponse(401),
                ) as post:
                    result = credential_routes._test_cloud_connection(
                        "probe", provider_config.PROVIDER_OPENAI, "https://provider.example/v1", "model-id",
                    )
                self.assertEqual(result, {"connected": False, "category": "authentication"})
                request = post.call_args
                self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer private-test-token")
                self.assertNotIn("private-test-token", json.dumps(result))
                self.assertNotIn("provider.example", json.dumps(result))

    def test_prompt_inspector_is_nonblocking_and_never_rewrites_input(self):
        original = "镜头2：人物出现。"
        passthrough, warnings_json, summary = inspector.inspect_prompt(
            original,
            inspector.FAMILY_SEEDANCE,
            "2",
            "中文",
            "AUTO",
        )
        report = json.loads(warnings_json)
        self.assertEqual(passthrough, original)
        self.assertEqual(report["schema_version"], "t8-prompt-inspector/v1")
        self.assertTrue(any(item["code"] == "shot_sequence" for item in report["warnings"]))
        self.assertIn("仅本地结构检查", summary)


if __name__ == "__main__":
    unittest.main()
