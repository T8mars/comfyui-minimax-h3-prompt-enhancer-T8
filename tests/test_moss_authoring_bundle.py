"""Pure-CPU collection contracts; no model, provider, ComfyUI or render proof."""
from __future__ import annotations

import copy
import json
import unittest

import moss_authoring as a
import moss_authoring_bundle as bundle
import moss_authoring_contract as contract
import moss_image_contract as native


def reference_map(count):
    return [{"index": index, "source_slot": f"reference_image_{index - 1}", "batch_index": 0,
             "sha256": f"{index:064x}", "role": ""} for index in range(1, count + 1)]


def comic_unit(index=1, *, languages=("en", "zh"), refs=()):
    source = {"width": 1256, "height": 1672, "bbox_coord_space": "abs", "bbox_format": "xyxy",
        "summary": {"canvas": "multi_panel", "caption": "A quiet page with one visibly framed scene."},
        "items": [
            {"label": "comic_panel", "caption": "A black bordered view of a window and a character.", "bbox": [20, 20, 1200, 1600]},
            {"label": "character", "caption": "One character in a red hat, reaching beyond the frame.", "bbox": [0, 450, 1256, 1650]},
            {"label": "object", "caption": "An ivory cup supported on the table.", "bbox": [800, 800, 1000, 1100]},
            {"label": "text", "caption": 'A crisp sign reading "STOP\n原文".', "text": "STOP\n原文", "bbox": [40, 50, 400, 200]},
        ]}
    ids = ["frame", "actor", "cup", "words"]
    sidecar = {"item_ids": ids, "panel_order": ["frame"],
        "membership": {key: {"panel_ids": ["frame"], "global_overlay": False} for key in ids[1:]},
        "devices": [{"id": 31, "reason": "The hand reaches beyond the frame without leaving the canvas."}],
        "intensity": "quiet", "layout_signature": {**{key: "One framed scene." for key in contract._SIGNATURE}, "panel_count": 1},
        "state": {"identity_anchors": {"actor": "red hat"}, "scene_anchors": {}, "current_state": {"cup": "held"}}}
    zh = contract.translate(source, ids, {"summary_caption": "一页安静漫画，清楚的独立画框。", "item_captions": {
        "frame": "黑色画框内是窗户与一位人物。", "actor": "一位戴红帽的人物，手臂越过画框。",
        "cup": "桌面上有一只奶白陶瓷杯。", "words": '清晰标牌写着“STOP\n原文”。'}})
    sources = {language: copy.deepcopy(source if language == "en" else zh) for language in languages}
    return {"unit_id": f"page-{index}", "index": index, "width": 1256, "height": 1672,
            "reference_indices": list(refs), "available_languages": [key for key in ("en", "zh") if key in sources],
            "sources": sources, "sidecar": sidecar}


def fisher_unit(index=1, *, refs=(), language="zh"):
    return {"unit_id": f"image-{index}", "index": index, "width": 1024, "height": 1024,
        "reference_indices": list(refs), "available_languages": [language],
        "sources": {language: {"caption": "一只白瓷杯，只有原始可见正面。" if language == "zh" else "One ivory cup, only the visible front."}},
        "sidecar": None}


def stages(units, profile=a.COMIC, *, correction=False):
    records = [{"stage_id": "plan", "kind": "plan", "unit_id": "", "calls": 1, "corrections": 0}] if profile == a.COMIC and units else []
    for unit in units:
        key = unit["unit_id"]
        records.append({"stage_id": key + ":source", "kind": "source", "unit_id": key,
                        "calls": 2 if correction else 1, "corrections": 1 if correction else 0})
        if profile == a.COMIC:
            records.append({"stage_id": key + ":translation", "kind": "translation", "unit_id": key, "calls": 1, "corrections": 0})
    return records


def comic_bundle(*, count=2, correction=False):
    units = [comic_unit(index) for index in range(1, count + 1)]
    records = stages(units, correction=correction)
    return bundle.build_bundle(a.COMIC, "context", units, [], [unit["unit_id"] for unit in units],
                               "The red hat stays on the same character.", records, sum(record["calls"] for record in records))


class BundleTests(unittest.TestCase):
    def assert_bad(self, value, *, code=None):
        with self.assertRaises(native.MossContractError) as caught:
            bundle.validate_bundle(value)
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def test_comic_build_derives_real_counts_and_detaches_caller_data(self):
        units = [comic_unit(1), comic_unit(2)]
        records = stages(units, correction=True)
        original = copy.deepcopy(units)
        built = bundle.build_bundle(a.COMIC, "context", units, [], ["page-1", "page-2"], "Read-only prior facts.", records, 7)
        self.assertEqual(units, original)
        self.assertEqual(built["report"]["logical_generation_calls"], 7)
        self.assertEqual(built["report"]["correction_calls"], 2)
        self.assertTrue(built["report"]["bilingual_complete"])
        self.assertFalse(built["report"]["semantics_verified"])
        self.assertEqual(built["report"]["translation_quality"], "unverified")
        units[0]["sources"]["en"]["summary"]["caption"] = "Changed by caller."
        records[0]["calls"] = 99
        self.assertNotEqual(built["units"], units)
        self.assertEqual(built["report"]["stage_records"][0]["calls"], 1)
        self.assertEqual(bundle.validate(contract.encode(built)), built)

    def test_select_compiles_one_source_and_returns_nine_values_with_zero_calls(self):
        built = comic_bundle()
        original = copy.deepcopy(built)
        selected = bundle.select(contract.encode(built), 1, "zh")
        self.assertEqual(len(selected), 9)
        positive, width, height, resolved, draft, report, source, paired, unit_id = selected
        self.assertEqual((width, height, resolved, unit_id), (1256, 1672, "layout", "page-1"))
        self.assertIs(type(width), int); self.assertIs(type(height), int)
        self.assertEqual(json.loads(source)["items"][0]["label"], "comic_panel")
        self.assertEqual(json.loads(draft)["items"][0]["label"], "object")
        self.assertIn("comic_panel", json.loads(draft)["items"][0]["tags"])
        self.assertEqual(json.loads(positive)["bbox_coord_space"], "abs_centralized")
        self.assertEqual(native.compile_draft(json.loads(draft), width=width, height=height)[0], positive)
        details = json.loads(report)
        self.assertEqual((details["logical_generation_calls"], details["chat_post_attempts"], details["correction_calls"]), (0, 0, 0))
        self.assertEqual(details["source_bundle_generation_calls"], 5)
        self.assertEqual(details["moss_token_check"]["status"], "unverified")
        self.assertLess(paired.index("English / en"), paired.index("中文 / zh"))
        self.assertNotIn("Page 2", paired)
        self.assertEqual(built, original, "Projection/selection cannot mutate source comic_panel labels or geometry")

    def test_readable_pairs_each_page_english_then_chinese_not_languages_in_bulk(self):
        text = bundle.readable(comic_bundle())
        self.assertLess(text.index("Page 1"), text.index("English / en"))
        self.assertLess(text.index("English / en"), text.index("中文 / zh"))
        self.assertLess(text.index("中文 / zh"), text.index("Page 2"))
        self.assertLess(text.index("Page 2"), text.rindex("English / en"))
        self.assertLess(text.rindex("English / en"), text.rindex("中文 / zh"))
        self.assertIn('"label": "comic_panel"', text)

    def test_fisher_independent_batches_and_explicit_fusion_have_exact_reference_coverage(self):
        refs = reference_map(3)
        refs[1]["source_slot"], refs[1]["batch_index"] = "reference_image_0", 1
        refs[2]["source_slot"], refs[2]["batch_index"] = "reference_image_2", 0
        units = [fisher_unit(index, refs=[index]) for index in range(1, 4)]
        independent = bundle.build_bundle(a.FISHER, "independent", units, refs,
            [unit["unit_id"] for unit in units], "", stages(units, a.FISHER), 0)
        self.assertEqual(independent["report"]["logical_generation_calls"], 3)
        self.assertFalse(independent["report"]["bilingual_complete"])
        self.assertEqual(bundle.select(independent, 2, "zh")[8], "image-2")
        fusion_unit = fisher_unit(refs=[1, 2, 3], language="en")
        fusion = bundle.build_bundle(a.FISHER, "fusion", [fusion_unit], refs, ["image-1"], "",
                                     stages([fusion_unit], a.FISHER), 1)
        self.assertEqual(fusion["report"]["logical_generation_calls"], 1)
        self.assertEqual(bundle.select(fusion, 1, "en")[3], "caption")
        bad = copy.deepcopy(independent); bad["units"][1]["reference_indices"] = [1]
        self.assert_bad(bad, code="independent_reference_mismatch")
        bad = copy.deepcopy(fusion); bad["units"][0]["reference_indices"] = [1, 2]
        self.assert_bad(bad, code="fusion_reference_mismatch")

    def test_no_reference_fisher_is_one_deliverable_and_missing_language_never_falls_back(self):
        unit = fisher_unit()
        built = bundle.build_bundle(a.FISHER, "independent", [unit], [], [unit["unit_id"]], "", stages([unit], a.FISHER), 1)
        with self.assertRaises(native.MossContractError) as caught:
            bundle.select(built, 1, "en")
        self.assertEqual(caught.exception.code, "missing_selected_language")
        for index, language in [(0, "zh"), (True, "zh"), (2, "zh"), (1, "English"), (1, []), (1, True)]:
            with self.subTest(index=index, language=language), self.assertRaises(native.MossContractError):
                bundle.select(built, index, language)
        bad = copy.deepcopy(built); bad["units"].append(fisher_unit(2))
        self.assert_bad(bad, code="independent_reference_mismatch")

    def test_edited_comic_pages_require_complete_bilingual_sources_and_matching_stages(self):
        good = comic_bundle()
        for language in ("en", "zh"):
            bad = copy.deepcopy(good); del bad["units"][0]["sources"][language]
            bad["units"][0]["available_languages"].remove(language)
            self.assert_bad(bad, code="incomplete_bilingual_unit")
        for kind in ("plan", "source", "translation"):
            bad = copy.deepcopy(good)
            bad["report"]["stage_records"] = [record for record in bad["report"]["stage_records"]
                                                if not (record["kind"] == kind and record["unit_id"] in ("", "page-1"))]
            self.assert_bad(bad)

    def test_unedited_single_language_page_stays_untouched_and_truthfully_disables_bilingual_flag(self):
        old = comic_unit(1, languages=("en",))
        edited = comic_unit(2)
        built = bundle.build_bundle(a.COMIC, "context", [old, edited], [], ["page-2"], "Previous page unchanged.", stages([edited]), 3)
        self.assertEqual(built["units"][0], old)
        self.assertFalse(built["report"]["bilingual_complete"])
        self.assertEqual(built["report"]["logical_generation_calls"], 3)
        self.assertEqual(bundle.select(built, 1, "en")[8], "page-1")
        with self.assertRaises(native.MossContractError): bundle.select(built, 1, "zh")
        all_old = bundle.build_bundle(a.COMIC, "context", [old], [], [], "", [], 0)
        self.assertEqual(all_old["report"]["logical_generation_calls"], 0)
        self.assertEqual(all_old["units"], [old])

    def test_comic_reference_subset_requires_bounded_explicit_reason(self):
        units = [comic_unit(refs=[1])]
        refs = reference_map(2)
        with self.assertRaises(native.MossContractError) as caught:
            bundle.build_bundle(a.COMIC, "context", units, refs, ["page-1"], "", stages(units), 3)
        self.assertEqual(caught.exception.code, "unexplained_reference_subset")
        units[0]["reference_selection_reason"] = "Reference 2 is for a later page; this page shows only Reference 1."
        good = bundle.build_bundle(a.COMIC, "context", units, refs, ["page-1"], "", stages(units), 3)
        self.assertIn("reference_selection_reason", good["units"][0])
        bad = copy.deepcopy(good); bad["units"][0]["reference_selection_reason"] = "  "
        self.assert_bad(bad)
        bad = copy.deepcopy(good); bad["units"][0]["reference_selection_reason"] = ["not text"]
        self.assert_bad(bad)

    def test_full_bundle_is_validated_even_when_selecting_an_earlier_healthy_page(self):
        good = comic_bundle()
        for modification in ("canvas", "translation", "text", "unknown", "item_id"):
            bad = copy.deepcopy(good)
            if modification == "canvas": bad["units"][1]["width"] = 1000
            if modification == "translation": bad["units"][1]["sources"]["zh"]["items"][1]["bbox"][0] = 1
            if modification == "text": bad["units"][1]["sources"]["zh"]["items"][3]["text"] = "STOP 原文"
            if modification == "unknown": bad["units"][1]["sources"]["zh"]["items"][0]["provider_key"] = "not allowed"
            if modification == "item_id": bad["units"][1]["sidecar"]["item_ids"][1] = "frame"
            with self.subTest(modification=modification), self.assertRaises(native.MossContractError):
                bundle.select(bad, 1, "en")

    def test_top_level_flags_ids_edits_and_report_fields_are_exact_and_type_strict(self):
        good = comic_bundle()
        for key, value in (("complete", False), ("complete", 1), ("adapter_revision", "old"), ("schema_version", "other"),
                           ("profile", a.CLASSIC), ("profile", []), ("reference_mode", "independent"),
                           ("edited_unit_ids", ["page-1", "page-1"]), ("edited_unit_ids", ["missing"]),
                           ("edited_unit_ids", [{}]), ("continuity_context", True)):
            bad = copy.deepcopy(good); bad[key] = value
            with self.subTest(key=key, value=value): self.assert_bad(bad)
        for key, value in (("logical_generation_calls", True), ("chat_post_attempts", True), ("correction_calls", True),
                           ("logical_generation_calls", 4), ("chat_post_attempts", 6), ("semantics_verified", 0),
                           ("image_generation_performed", 0), ("translation_quality", "verified"), ("bilingual_complete", 1),
                           ("bilingual_complete", False)):
            bad = copy.deepcopy(good); bad["report"][key] = value
            with self.subTest(key=key, value=value): self.assert_bad(bad)
        for section in (None, "report", "unit"):
            bad = copy.deepcopy(good)
            (bad if section is None else bad["report"] if section == "report" else bad["units"][0])["unexpected"] = True
            self.assert_bad(bad)
        bad = copy.deepcopy(good); bad["units"][1]["unit_id"] = "page-1"
        self.assert_bad(bad, code="duplicate_unit_id")
        bad = copy.deepcopy(good); bad["units"][1]["index"] = 1
        self.assert_bad(bad, code="invalid_unit_index")

    def test_stage_id_order_scope_and_correction_counts_are_not_trusted(self):
        good = comic_bundle()
        for key, value in (("stage_id", ""), ("kind", []), ("unit_id", "page-2"), ("calls", True),
                           ("calls", 2), ("corrections", 1), ("corrections", False)):
            bad = copy.deepcopy(good); bad["report"]["stage_records"][0][key] = value
            with self.subTest(key=key, value=value): self.assert_bad(bad)
        bad = copy.deepcopy(good); bad["report"]["stage_records"][2]["stage_id"] = bad["report"]["stage_records"][1]["stage_id"]
        self.assert_bad(bad, code="duplicate_stage_id")
        bad = copy.deepcopy(good); bad["report"]["stage_records"][1:3] = reversed(bad["report"]["stage_records"][1:3])
        self.assert_bad(bad, code="invalid_stage_order")
        bad = copy.deepcopy(good); bad["report"]["stage_records"].append(copy.deepcopy(bad["report"]["stage_records"][1]))
        bad["report"]["stage_records"][-1]["stage_id"] = "another-source"
        self.assert_bad(bad, code="duplicate_stage")

    def test_reference_manifest_is_sequential_unique_bounded_and_does_not_carry_pixels(self):
        unit = fisher_unit(refs=[1])
        good = bundle.build_bundle(a.FISHER, "independent", [unit], reference_map(1), ["image-1"], "", stages([unit], a.FISHER), 1)
        for key, value in (("index", True), ("index", 2), ("batch_index", True), ("batch_index", 10),
                           ("source_slot", "reference_image_10"), ("source_slot", "C:/private.png"),
                           ("sha256", "not-a-hash"), ("role", {})):
            bad = copy.deepcopy(good); bad["reference_map"][0][key] = value
            with self.subTest(key=key, value=value): self.assert_bad(bad)
        bad = copy.deepcopy(good); bad["reference_map"][0]["pixels"] = "data:image/png;base64,AAAA"
        self.assert_bad(bad)
        units = [fisher_unit(index, refs=[index]) for index in (1, 2)]
        refs = reference_map(2); refs[1]["source_slot"] = "reference_image_0"
        with self.assertRaises(native.MossContractError):
            bundle.build_bundle(a.FISHER, "independent", units, refs, [unit["unit_id"] for unit in units], "", stages(units, a.FISHER), 2)

    def test_maximum_sixteen_pages_and_sixty_six_calls_are_explicit_safety_budget(self):
        units = [comic_unit(index) for index in range(1, 17)]
        records = stages(units)
        for record in records: record.update(calls=2, corrections=1)
        built = bundle.build_bundle(a.COMIC, "context", units, [], [unit["unit_id"] for unit in units], "", records, 66)
        self.assertEqual((len(records), built["report"]["logical_generation_calls"], built["report"]["correction_calls"]), (33, 66, 33))
        bad = copy.deepcopy(built); bad["units"].append(comic_unit(17))
        self.assert_bad(bad, code="invalid_unit_count")
        bad = copy.deepcopy(built); bad["report"]["stage_records"].append(copy.deepcopy(records[-1]))
        self.assert_bad(bad, code="invalid_stage_records")

    def test_json_unicode_byte_budget_duplicates_nonfinite_and_partial_bundle_are_rejected(self):
        good = comic_bundle(count=1)
        for text in ('{"complete":true,"complete":false}', '{"number":NaN}', '{"text":"\\ud800"}', "not JSON"):
            with self.subTest(text=text), self.assertRaises(native.MossContractError): bundle.validate(text)
        bad = copy.deepcopy(good); bad["continuity_context"] = "文" * 22000
        self.assert_bad(bad, code="input_budget")
        bad = copy.deepcopy(good); bad["complete"] = False
        with self.assertRaises(native.MossContractError): bundle.select(bad, 1, "en")
        units = [fisher_unit(index, refs=[index]) for index in range(1, 11)]
        for unit in units:
            unit["sources"] = {"en": {"caption": "x" * 120000}, "zh": {"caption": "文" * 40000}}
            unit["available_languages"] = ["en", "zh"]
        with self.assertRaises(native.MossContractError) as caught:
            bundle.build_bundle(a.FISHER, "independent", units, reference_map(10), [unit["unit_id"] for unit in units], "", stages(units, a.FISHER), 10)
        self.assertEqual(caught.exception.code, "input_budget")

    def test_build_rejects_malformed_ids_before_stage_set_operations(self):
        unit = fisher_unit()
        variants = [([unit], [{}]), ([unit], [True]), ([unit], ["missing"]),
                    ([{**unit, "unit_id": {}}], []), ([None], []), ([unit, copy.deepcopy(unit)], [])]
        for units, edits in variants:
            with self.subTest(units=units, edits=edits), self.assertRaises(native.MossContractError):
                bundle.build_bundle(a.FISHER, "independent", units, [], edits, "", [], 0)
        for profile in (a.CLASSIC, None, [], {}):
            with self.subTest(profile=profile), self.assertRaises(native.MossContractError):
                bundle.build_bundle(profile, "independent", [unit], [], [], "", [], 0)

    def test_historical_per_language_lengths_are_verified_and_selected_without_current_setting(self):
        unit = comic_unit()
        unit["lengths"] = {language: a.length_metadata(contract.compile_source(source, width=1256, height=1672),
            {"max_output_chars": 80 if language == "en" else 0, "target_han_range": None})
            for language, source in unit["sources"].items()}
        built = bundle.build_bundle(a.COMIC, "context", [unit], [], ["page-1"], "", stages([unit]), 3)
        report = json.loads(bundle.select(built, 1, "en")[5])
        self.assertEqual(report["authoring_length"], unit["lengths"]["en"])
        self.assertEqual(report["authoring_length"]["max_output_chars"], 80)
        self.assertEqual(report["authoring_profile"], a.COMIC)
        self.assertEqual(report["over_limit"], report["authoring_length"]["status"] == "over_limit")
        legacy = comic_bundle(count=1)
        self.assertNotIn("authoring_length", json.loads(bundle.select(legacy, 1, "en")[5]), "Do not invent an old cap")
        for bad_lengths in ({"en": unit["lengths"]["en"]}, {**unit["lengths"], "other": {}}, []):
            bad = copy.deepcopy(built); bad["units"][0]["lengths"] = bad_lengths
            self.assert_bad(bad)
        for key, value in (("description_chars", True), ("han_chars", 100000), ("status", []), ("max_output_chars", True)):
            bad = copy.deepcopy(built); bad["units"][0]["lengths"]["en"][key] = value
            with self.subTest(key=key): self.assert_bad(bad)
        english = fisher_unit(language="en")
        english["lengths"] = {"en": a.length_metadata(contract.compile_source(english["sources"]["en"], width=1024, height=1024),
            {"max_output_chars": 0, "target_han_range": [1500, 2500]})}
        with self.assertRaises(native.MossContractError) as caught:
            bundle.build_bundle(a.FISHER, "independent", [english], [], ["image-1"], "", stages([english], a.FISHER), 1)
        self.assertEqual(caught.exception.code, "invalid_language_length_target")


if __name__ == "__main__":
    unittest.main()
