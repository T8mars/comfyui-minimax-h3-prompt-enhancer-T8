import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "t8_text_utilities_test_package",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
text_utilities = sys.modules[f"{SPEC.name}.text_utilities"]


class TextUtilitiesTests(unittest.TestCase):
    def test_prompt_text_is_a_multiline_string_source(self):
        schema = text_utilities.T8PromptText.define_schema()
        info = schema.get_v1_info(text_utilities.T8PromptText)
        self.assertEqual(schema.node_id, "T8PromptText")
        self.assertEqual(schema.category, "T8/Utilities")
        self.assertEqual(info.input_order["required"], ["text"])
        result = text_utilities.T8PromptText.execute("第一行\nsecond line")
        self.assertEqual(result[0], "第一行\nsecond line")

    def test_show_text_is_an_output_node_and_passes_string_through(self):
        schema = text_utilities.T8ShowText.define_schema()
        info = schema.get_v1_info(text_utilities.T8ShowText)
        self.assertEqual(schema.node_id, "T8ShowText")
        self.assertTrue(info.output_node)
        result = text_utilities.T8ShowText.execute("完整结果")
        self.assertEqual(result[0], "完整结果")
        self.assertEqual(result.ui, {"text": ["完整结果"]})

    def test_frontend_preview_is_read_only_non_serialized_and_uses_text_content(self):
        source = (ROOT / "web" / "js" / "text_utilities.js").read_text(encoding="utf-8")
        self.assertIn("textarea.readOnly = true", source)
        self.assertIn("serialize: false", source)
        self.assertNotIn("innerHTML", source)


if __name__ == "__main__":
    unittest.main()
