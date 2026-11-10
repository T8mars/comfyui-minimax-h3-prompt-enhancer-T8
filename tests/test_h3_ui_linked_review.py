"""Public STRING-source fidelity and linked-input validation regressions."""
import importlib
import unittest

from test_h3_image_node import h, Node

text = importlib.import_module(h.__package__ + ".text_utilities")


class LinkedStringReview(unittest.TestCase):
    def test_generic_string_source_does_not_enable_host_randomization_or_comment_stripping(self):
        schema = text.T8PromptText.define_schema()
        info = schema.get_v1_info(text.T8PromptText)
        config = info.input["required"]["text"][1]
        self.assertFalse(config.get("dynamicPrompts", True), "Generic STRING data must reach URL/JSON inputs unchanged")
        self.assertEqual(schema.node_id, "T8PromptText")
        self.assertEqual(info.input_order["required"], ["text"])
        for value in ("https://127.0.0.1:8000/v1", '{"title":"中文 😀", "choices":"{red|blue}"}',
                      "first line\r\n// literal copy\n/* visible phrase */\n花括号 {x|y} must stay"):
            with self.subTest(value=value):
                self.assertEqual(text.T8PromptText.execute(value).result, (value,))

    def test_all_unresolved_linked_text_and_numeric_controls_defer_then_validate_at_execution(self):
        self.assertIs(Node.validate_inputs(prompt=None, aspect_ratio=None, target_words=None, locked_text=None, max_corrections=None), True)
        self.assertNotEqual(Node.validate_inputs(prompt=""), True)
        # Explicit invalid literals remain invalid: only an unresolved None can
        # use the UI placeholder rather than becoming user data.
        self.assertNotEqual(Node.validate_inputs(prompt="brief", aspect_ratio=""), True)
        self.assertNotEqual(Node.validate_inputs(prompt="brief", target_words=-1), True)


if __name__ == "__main__": unittest.main()
