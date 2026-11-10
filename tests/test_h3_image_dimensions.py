"""Pixel-size input contracts use real provider wiring with synthetic answers."""
import json
import unittest
from unittest.mock import patch

import numpy as np
from test_h3_image_node import h, Node, c, Response, Session, reply


class DimensionTests(unittest.TestCase):
    def test_dimensions_override_manual_ratio_and_preserve_legacy_defaults(self):
        self.assertEqual(h.resolve_canvas_ratio(c.T2I, "auto", 1920, 1080)[0], "16:9")
        self.assertEqual(h.resolve_canvas_ratio(c.T2I, "4:3", 1024, 1024)[0], "1:1")
        self.assertEqual(h.resolve_canvas_ratio(c.EDIT, "auto", 1001, 999)[0], "1001:999")
        ratio, report = h.resolve_canvas_ratio(c.T2I, "auto", 1001, 999)
        self.assertEqual(ratio, "1:1"); self.assertTrue(report["ratio_mapped_to_supported"])
        self.assertEqual(report["exact_canvas_aspect_ratio"], "1001:999")
        for ratio in ("auto", "16:9"):
            self.assertEqual(h.resolve_canvas_ratio(c.T2I, ratio)[0], ratio)

    def test_unresolved_dimensions_defer_validation_and_recovery_skips_them(self):
        self.assertTrue(Node.validate_inputs(prompt=None, width=None, height=None))
        self.assertTrue(Node.validate_inputs(prompt=None, width=1920, height=None))
        self.assertEqual(Node.check_lazy_status(prompt="brief", width=None, height=None), ["width", "height"])
        self.assertEqual(Node.check_lazy_status(width=None, height=None, recovery_action="restore_last"), [])
        self.assertTrue(Node.validate_inputs(recovery_action="restore_last", width=-1, height=-1))
        inputs = {i.id: i for i in Node.define_schema().inputs}
        for name in ("width", "height"):
            self.assertTrue(inputs[name].force_input); self.assertTrue(inputs[name].optional); self.assertTrue(inputs[name].lazy)

    def test_bad_dimensions_fail_before_provider(self):
        for width, height in ((1920, 0), (0, 1080), (-1, 1080), (True, 1080), (1920, 1.5), (None, 1080)):
            with self.subTest(width=width, height=height), patch.object(h, "_generate") as generate, self.assertRaises(h.H3ImageError):
                Node.execute(prompt="A cup.", width=width, height=height)
            generate.assert_not_called()

    def test_cloud_request_and_cache_use_derived_ratio(self):
        session = Session(Response(reply(ratio="16:9")))
        with patch.object(h.requests, "Session", return_value=session):
            output = Node.execute(prompt="A cup.", api_key="test-placeholder", width=1920, height=1080, recovery_slot="t8-size-cache-regression")
        self.assertEqual(output.result[1], "16:9")
        self.assertIn("canvas aspect ratio is 16:9", str(session.calls[0][1]["json"]["messages"]))
        report = json.loads(output.result[3]); self.assertEqual(report["canvas_dimensions"], {"width": 1920, "height": 1080})
        self.assertEqual(report["ratio_source"], "dimensions")
        self.assertEqual(Node.execute(recovery_slot="t8-size-cache-regression", recovery_action="restore_last", width=-1).result[:3], output.result[:3])

    def test_edit_uses_exact_target_size_instead_of_source_or_manual_ratio(self):
        session = Session(Response(reply(c.EDIT, ratio="1001:999")))
        with patch.object(h.requests, "Session", return_value=session):
            result = Node.execute(prompt="Reframe the image.", task_type=c.EDIT, aspect_ratio="16:9", width=1001, height=999,
                api_mode=h.AI_WORKSHOP_API_MODE, api_key="test-placeholder", reference_images={"reference_image_0": np.zeros((1, 7, 9, 3))})
        self.assertEqual(result.result[1], "1001:999")
        text = str(session.calls[0][1]["json"]["messages"])
        self.assertIn("aspect_ratio 9:7", text)
        self.assertIn("1001:999", text)
        self.assertFalse(json.loads(result.result[3])["ratio_mapped_to_supported"])


if __name__ == "__main__": unittest.main()
