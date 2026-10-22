"""Collection building blocks: structure and shared geometry, not image quality."""
import copy
import json
import unittest

import test_moss_image as base

from importlib import import_module

bc = import_module(base.moss.__package__ + ".moss_authoring_contract")
c, a = bc.c, bc.a


def comic():
    source = {"width": 1256, "height": 1672, "bbox_coord_space": "abs", "bbox_format": "xyxy",
              "summary": {"canvas": "multi_panel", "caption": "A calm page."}, "items": [
                  {"label": "comic_panel", "caption": "A border with a hand crossing its right edge.", "bbox": [0, 0, 600, 1600]},
                  {"label": "character", "caption": "One hand reaches beyond the panel.", "bbox": [500, 100, 700, 900]},
                  {"label": "text", "caption": "Small speech bubble.", "text": "你好！\n不必等待。", "bbox": [32, 32, 400, 160]}]}
    sidecar = {"item_ids": ["frame", "actor", "words"], "panel_order": ["frame"],
               "membership": {key: {"panel_ids": ["frame"], "global_overlay": False} for key in ("actor", "words")},
               "devices": [{"id": 31, "reason": "The hand extends its gesture across the border."}], "intensity": "quiet",
               "layout_signature": {**{key: "A deliberate simple composition." for key in bc._SIGNATURE}, "panel_count": 1},
               "state": {"identity_anchors": {}, "scene_anchors": {}, "current_state": {}}}
    return source, sidecar


class ComicSourceContracts(unittest.TestCase):
    def test_fisher_cannot_bypass_native_schema_using_unaccompanied_comic_panels(self):
        source, _sidecar = comic()
        unit = {"unit_id": "image-1", "index": 1, "width": 1256, "height": 1672,
            "reference_indices": [], "available_languages": ["en"], "sources": {"en": source}, "sidecar": None}
        with self.assertRaises(c.MossContractError): bc.validate_unit(unit, a.FISHER, 0)
        unit["sources"]["en"] = bc.native_projection(source)
        bc.validate_unit(unit, a.FISHER, 0)

    def test_source_panel_projection_compiles_copy_and_preserves_original(self):
        source, sidecar = comic()
        before = copy.deepcopy(source)
        result = bc.compile_source(source, width=1256, height=1672)
        bc.validate_sidecar(source, sidecar)
        self.assertEqual(source, before)
        self.assertEqual(source["items"][0]["label"], "comic_panel")
        native = json.loads(result[4])
        self.assertEqual(native["items"][0]["label"], "object")
        self.assertEqual(native["items"][0]["tags"], ["comic_panel"])
        self.assertEqual(result[1:3], (1256, 1672))
        # The limb crosses the frame; it is not erroneously clipped to it.
        self.assertGreater(native["items"][1]["bbox"][2], native["items"][0]["bbox"][2])
        with self.assertRaises(c.MossContractError): c.compile_draft(source, width=1256, height=1672)

    def test_bilingual_mapping_cannot_change_non_caption_fields_or_words(self):
        source, sidecar = comic()
        translated = bc.translate(source, sidecar["item_ids"], {"summary_caption": "平静的一页。",
            "item_captions": {"frame": "手越出右侧画框。", "actor": "一只伸出边框的手。", "words": "小对白框。"}})
        self.assertTrue(bc.same_json(bc.without_captions(source), bc.without_captions(translated)))
        self.assertEqual(translated["items"][2]["text"], "你好！\n不必等待。")
        self.assertEqual(source["summary"]["caption"], "A calm page.")
        for mapping in ({"summary_caption": "页", "item_captions": {"frame": "框"}},
                        {"summary_caption": "页", "item_captions": {"frame": "框", "actor": "手", "words": "字", "other": "多"}},
                        {"summary_caption": "页", "item_captions": {"frame": "框", "actor": None, "words": "字"}},
                        {"summary_caption": "页", "item_captions": {"frame": "框", "actor": "手", "words": "字"}, "bbox": [0, 0, 1, 1]}):
            with self.assertRaises(c.MossContractError): bc.translate(source, sidecar["item_ids"], mapping)
        self.assertEqual(bc.translate({"caption": "One cup."}, [], {"caption": "一个杯子。"}), {"caption": "一个杯子。"})
        with self.assertRaises(c.MossContractError): bc.translate({"caption": "A cup."}, [], {"caption": "杯", "width": 1024})
        for ids in (None, [{}], [True]):
            with self.assertRaises(c.MossContractError):
                bc.translate(source, ids, {"summary_caption": "页", "item_captions": {}})
        source["items"][2]["text"] = "STOP"
        source["items"][2]["caption"] = 'A sign reading "STOP".'
        mapping = {"summary_caption": "页", "item_captions": {"frame": "框", "actor": "手", "words": "写着“停”的标牌。"}}
        with self.assertRaises(c.MossContractError): bc.translate(source, sidecar["item_ids"], mapping)
        mapping["item_captions"]["words"] = "写着“STOP”的标牌。"
        bc.translate(source, sidecar["item_ids"], mapping)

    def test_panel_identity_coverage_membership_and_methods_are_strict(self):
        source, sidecar = comic()
        for mutate in (
            lambda s: s.update(item_ids=["frame", "actor", "actor"]),
            lambda s: s.update(panel_order=["frame", "frame"]),
            lambda s: s["membership"].pop("words"),
            lambda s: s["membership"]["actor"].update(panel_ids=["missing"]),
            lambda s: s["membership"]["actor"].update(panel_ids=[]),
            lambda s: s["devices"][0].update(id=True),
            lambda s: s["devices"].append(copy.deepcopy(s["devices"][0])),
            lambda s: s["layout_signature"].update(panel_count=True),
            lambda s: s.update(provider_config={"secret": "not part of sidecar"}),
        ):
            changed = copy.deepcopy(sidecar); mutate(changed)
            with self.assertRaises(c.MossContractError): bc.validate_sidecar(source, changed)
        sidecar["membership"]["words"] = {"panel_ids": [], "global_overlay": True}
        bc.validate_sidecar(source, sidecar)

    def test_fixed_revision_preserves_whole_copy_and_actual_non_caption_tree(self):
        source, sidecar = comic()
        revised = copy.deepcopy(source)
        revised["items"][1]["caption"] = "A more specifically described reaching hand."
        bc.validate_revision(revised, source, sidecar, sidecar, "full_layout")
        revised["items"][1]["bbox"][0] = 480
        with self.assertRaises(c.MossContractError): bc.validate_revision(revised, source, sidecar, sidecar, "full_layout")
        bc.validate_revision(revised, source, sidecar, sidecar, "panels_only")
        revised["items"][2]["text"] = "你好！ 不必等待。"
        with self.assertRaises(c.MossContractError): bc.validate_revision(revised, source, sidecar, sidecar, "panels_only")
        self.assertFalse(bc.same_json({"number": True}, {"number": 1}))
        self.assertFalse(bc.same_json({"number": 1}, {"number": 1.0}))

    def test_global_canvas_but_not_panel_containment_is_a_hard_boundary(self):
        source, _ = comic()
        bc.compile_source(source, width=1256, height=1672)
        source["items"][1]["bbox"][2] = 1257
        with self.assertRaises(c.MossContractError): bc.compile_source(source, width=1256, height=1672)
        for bad in (float("nan"), True, "700"):
            source["items"][1]["bbox"][2] = bad
            with self.assertRaises(c.MossContractError): bc.compile_source(source, width=1256, height=1672)

    def test_unit_languages_are_explicit_and_share_geometry(self):
        source, sidecar = comic()
        unit = {"unit_id": "page-1", "index": 1, "width": 1256, "height": 1672, "reference_indices": [1],
                "available_languages": ["en", "zh"], "sources": {"en": source, "zh": copy.deepcopy(source)}, "sidecar": sidecar}
        bc.validate_unit(unit, a.COMIC, 1)
        unit["sources"]["zh"]["items"][1]["bbox"][0] = 480
        with self.assertRaises(c.MossContractError): bc.validate_unit(unit, a.COMIC, 1)
        unit["sources"].pop("zh")
        with self.assertRaises(c.MossContractError): bc.validate_unit(unit, a.COMIC, 1)
        unit["available_languages"] = ["en"]
        bc.validate_unit(unit, a.COMIC, 1)  # truthful existing single-language revision context
        unit["reference_indices"] = [1, 1]
        with self.assertRaises(c.MossContractError): bc.validate_unit(unit, a.COMIC, 1)

    def test_json_rejects_duplicates_secrets_nonfinite_depth_and_total_budget(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '[' * 30 + '0' + ']' * 30, '{"x":"sk-' + 'x' * 24 + '"}'):
            with self.assertRaises(c.MossContractError): bc.parse(text)
        with self.assertRaises(c.MossContractError): bc.encode({"x": "x" * bc.MAX_BUNDLE_BYTES})
        with self.assertRaises(c.MossContractError): bc.parse('{"x":"\\ud800"}')


if __name__ == "__main__": unittest.main()
