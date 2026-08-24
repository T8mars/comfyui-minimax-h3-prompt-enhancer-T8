import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_provider_capabilities_test", ROOT / "provider_capabilities.py")
capabilities = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capabilities
SPEC.loader.exec_module(capabilities)


class ProviderCapabilityTests(unittest.TestCase):
    def test_auto_preserves_temperature_for_unknown_openai_provider(self):
        payload = capabilities.apply_chat_request_options(
            {"model": "visual-model", "messages": [], "stream": False},
            chat_url="https://provider.example/v1/chat/completions",
            temperature=0.7,
        )
        self.assertEqual(payload["temperature"], 0.7)

    def test_auto_omits_temperature_for_kimi_coding_plan(self):
        payload = capabilities.apply_chat_request_options(
            {"model": "k3", "messages": [], "stream": False},
            chat_url="https://api.kimi.com/coding/v1/chat/completions",
            temperature=0.7,
        )
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["model"], "k3")

    def test_explicit_send_and_omit_override_auto_profile(self):
        sent = capabilities.apply_chat_request_options(
            {"messages": []},
            chat_url="https://api.kimi.com/coding/v1/chat/completions",
            temperature=0.2,
            options={"temperature_policy": "send"},
        )
        omitted = capabilities.apply_chat_request_options(
            {"messages": []},
            chat_url="https://provider.example/v1/chat/completions",
            temperature=1.2,
            options={"temperature_policy": "omit"},
        )
        self.assertEqual(sent["temperature"], 0.2)
        self.assertNotIn("temperature", omitted)

    def test_additional_parameters_are_allowlisted_and_core_fields_are_protected(self):
        payload = capabilities.apply_chat_request_options(
            {"model": "m", "messages": [], "stream": False},
            chat_url="https://provider.example/v1/chat/completions",
            temperature=0.7,
            options={"extra_parameters": {"top_p": 0.9, "max_tokens": 2048}},
        )
        self.assertEqual(payload["top_p"], 0.9)
        self.assertEqual(payload["max_tokens"], 2048)
        with self.assertRaises(capabilities.ProviderCapabilityError):
            capabilities.apply_chat_request_options(
                {"model": "m", "messages": []},
                chat_url="https://provider.example/v1/chat/completions",
                temperature=0.7,
                options={"extra_parameters": {"messages": "override"}},
            )

    def test_capability_summary_does_not_claim_unknown_visual_support(self):
        summary = capabilities.provider_capability_summary("https://provider.example/v1/chat/completions")
        self.assertEqual(summary["image_data_url"], "unknown")
        self.assertEqual(summary["video_data_url"], "unknown")
        self.assertEqual(summary["video_url"], "unknown")


if __name__ == "__main__":
    unittest.main()
