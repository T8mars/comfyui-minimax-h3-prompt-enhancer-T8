"""Opt-in producer tests; explicit checkout, CPU only, no cross-project writes."""
import json
import os
import unittest
from unittest.mock import patch

import torch
from test_h3_visual_marker import vm, config, media
from marker_producer_loader import load_producer


@unittest.skipUnless(os.environ.get("T8_MARKER_PRODUCER_ROOT"), "Explicit read-only producer checkout required")
class ActualMarkerProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer(os.environ["T8_MARKER_PRODUCER_ROOT"])

    def test_actual_rendered_handdrawn_and_manual_original_recipe(self):
        p = self.producer
        for mode in ("render_rectangles", "provided_marked"):
            spec = json.loads(p.DEFAULT_MARKERS)
            if mode == "provided_marked":
                for marker in spec["markers"]: marker.pop("xyxy")
            _, plan, record = p.prepare_markers(torch.zeros(1, 32, 48, 3), json.dumps(spec), mode=mode)
            with patch.object(p.MarkerPlan, "verify", side_effect=AssertionError("Adapter must not call foreign methods")):
                cfg = config(plan)
                pixels, evidence = vm.bind_visual_marker(cfg, media(plan), "Ref2VA")
            self.assertEqual(evidence.picture, 1)
            self.assertFalse(vm.visual_marker_metadata(evidence)["h3_visual_marker"]["downstream_verified"])
            self.assertEqual(vm._pixel_identity(pixels[0]["value"][None]), record["marked_rgb"])
            recipe = p.prepare_marker_prompt(plan, "Existing native enhanced text", mode="manual_original")
            # The producer owns this API; inspect its real return rather than duplicating it.
            self.assertIn("Existing native enhanced text", str(recipe))

    def test_derived_record_budget_with_actual_maximum_warning_fixture(self):
        p = self.producer
        ids = [("actor_" if i < 32 else "target_") + str(i).zfill(2) + "x"*(40 if i < 32 else 39) for i in range(64)]
        markers = [dict(marker_id=ident, kind="actor" if i < 32 else "target", color="cyan",
                        description="declared object", xyxy=[.1, .1, .9, .9],
                        **({"role_id": "shared"} if i < 32 else {})) for i, ident in enumerate(ids)]
        relations = [dict(actor_marker_id=ids[i % 32], target_marker_id=ids[32+i % 32], action="walk through") for i in range(128)]
        spec = dict(markers=markers, relations=relations)
        for relation in relations:
            room = p.MAX_JSON_BYTES - len(p.canonical(spec).encode()) - 1
            relation["action"] += "x"*max(0, min(room, 4096-len(relation["action"])))
        raw = p.canonical(spec)
        self.assertTrue(65530 <= len(raw.encode()) <= 65536)
        _, plan, record = p.prepare_markers(torch.zeros(1, 16, 16, 3), raw)
        self.assertEqual(sum(w.startswith("Overlapping") for w in record["warnings"]), 2016)
        self.assertTrue(65536 < len(plan.record_json.encode()) < vm.MAX_RECORD_BYTES)
        cfg = config(plan)
        _, evidence = vm.bind_visual_marker(cfg, media(plan), "Ref2VA")
        self.assertIn("overlap", evidence.warning_codes)
        self.assertEqual(len(json.loads(evidence.evidence_json)["relations"]), 128)
        print("Actual producer budget:", len(raw.encode()), len(plan.record_json.encode()), len(record["warnings"]))

    def test_standalone_canvas_pixels_can_rebuild_original_foreign_plan(self):
        import importlib
        from test_h3_spatial_editor import SPEC
        from test_h3_visual_marker import h3
        editor=importlib.import_module(h3.__package__+'.h3_spatial_editor')
        source=torch.linspace(0,1,48*32*3,dtype=torch.float32).reshape(1,32,48,3)
        for mode in ('render_rectangles','provided_marked'):
            for width in (1,3,32):
                raw=json.dumps(SPEC)
                marked,local,record,_=editor.prepare_spatial_image(source,raw,mode,width)
                foreign,plan,other=self.producer.prepare_markers(source,raw,mode=mode,line_width=width)
                self.assertTrue(torch.equal(marked,foreign))
                self.assertEqual(record['spec'],other['spec'])
                self.assertEqual(record['marked_rgb'],other['marked_rgb'])
                # Rebuild its real plan, rather than pretending our Python class
                # passes its strict class identity check.
                recipe=self.producer.prepare_marker_prompt(plan,'Native enhanced text',mode='manual_original')
                self.assertIn('Native enhanced text',str(recipe))
                vm.build_visual_marker_config(vm.ON,0,local)
