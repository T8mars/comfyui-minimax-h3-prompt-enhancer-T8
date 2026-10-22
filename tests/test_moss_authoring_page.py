"""Direct CPU selector wiring; native host registration is tested separately."""
import importlib
import json
import unittest

import test_moss_image as base

nodes = importlib.import_module(base.moss.__package__ + ".moss_authoring_nodes")
Node, b, c, a = nodes.MOSSAuthoringPage, nodes.bundle, nodes.contract.c, nodes.bundle.authoring


def sample():
    unit = {"unit_id": "image-1", "index": 1, "width": 1256, "height": 1672,
            "reference_indices": [], "available_languages": ["zh"], "sources": {"zh": {"caption": "一只白瓷杯。"}}, "sidecar": None}
    stages = [{"stage_id": "image-1-source", "kind": "source", "unit_id": "image-1", "calls": 1, "corrections": 0}]
    return b.build_bundle(a.FISHER, "independent", [unit], [], ["image-1"], "", stages, 0)


class PageNodeTests(unittest.TestCase):
    def test_native_schema_has_three_inputs_nine_outputs_and_typed_dimensions(self):
        schema = Node.define_schema()
        self.assertEqual([i.id for i in schema.inputs], ["bundle_json", "page_index", "language"])
        self.assertEqual(len(schema.outputs), 9)
        self.assertEqual([schema.outputs[i].get_io_type() for i in (1, 2)], ["INT", "INT"])

    def test_linked_none_defers_but_resolved_invalid_values_fail(self):
        self.assertIs(Node.validate_inputs(bundle_json=None, page_index=None, language=None), True)
        self.assertIsInstance(Node.validate_inputs(bundle_json=""), str)
        self.assertIsInstance(Node.validate_inputs(bundle_json=None, page_index=True), str)
        for value in (None, "", "{}"):
            with self.assertRaises(c.MossContractError): Node.execute(value, page_index=1, language="zh")

    def test_select_is_cpu_only_original_prose_and_int_canvas(self):
        result = Node.execute(json.dumps(sample()), page_index=1, language="zh").result
        self.assertEqual(result[:4], ("一只白瓷杯。", 1256, 1672, "caption"))
        self.assertEqual(result[8], "image-1")
        report = json.loads(result[5])
        self.assertEqual(report["logical_generation_calls"], 0)
        self.assertEqual(json.loads(result[6]), {"caption": "一只白瓷杯。"})
        with self.assertRaises(c.MossContractError): Node.execute(json.dumps(sample()), language="en")


if __name__ == "__main__": unittest.main()
