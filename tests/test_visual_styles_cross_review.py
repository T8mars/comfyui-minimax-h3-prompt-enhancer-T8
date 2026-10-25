"""Independent offline cross-review regressions; no model or video-quality claim.

The counted matrices preserve the actual review cases: 156 malformed identity
configs, 48 combined language-repair contracts and 8 UI-only color-label cases.
Consumer corruption cases recompute the manifest digest, so a hash mismatch
cannot accidentally substitute for the runtime schema validation being tested.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import hashlib
import importlib
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_directional_skills import h3, sd, h3_args, sd_args, primary_text


styles = importlib.import_module(h3.__package__ + ".visual_styles")
routes = importlib.import_module(h3.__package__ + ".visual_style_routes")
storyboard = importlib.import_module(h3.__package__ + ".storyboard_director")
performance = importlib.import_module(h3.__package__ + ".performance_director")
combat = importlib.import_module(h3.__package__ + ".combat_camera")


def active(kind, ident="001", scope=None):
    return styles.build_style_config(kind, styles.ON, ident, scope or styles.COLOR_ONLY)


def json_bytes(value):
    # allow_nan=True is intentional here: malformed NaN/Infinity tokens must
    # reach the actual consumer parser, not get rejected by this fixture writer.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=True) + "\n").encode("utf-8")


class VisualStylesCrossReviewTests(unittest.TestCase):
    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("Cross review forbids network")))
        guards.enter_context(patch("socket.create_connection", side_effect=AssertionError("Cross review forbids sockets")))
        for module in (h3, sd):
            guards.enter_context(patch.object(module, "LocalQwenProvider", side_effect=AssertionError("Cross review forbids real models")))

    def test_156_malformed_identity_field_values_are_rejected_without_echo(self):
        invalid_values = [None, False, True, 0, 1, [], {}, ["on"], {"on": 1}, "", "PRIVATE", float("nan")]
        checked = 0
        for kind in ("color", "creator"):
            good = active(kind)
            snapshot = dict(good)
            self.assertEqual(styles.resolve_style_config(good, kind), good)
            for field, invalid in itertools.product(good, invalid_values):
                with self.subTest(kind=kind, field=field, invalid=repr(invalid)):
                    value = copy.deepcopy(good)
                    value[field] = invalid
                    with self.assertRaises(ValueError) as caught:
                        styles.resolve_style_config(value, kind)
                    self.assertNotIn("PRIVATE", str(caught.exception))
                    self.assertEqual(good, snapshot)
                    checked += 1
        self.assertEqual(checked, 156)

    def test_48_combined_repairs_retain_single_style_block_and_original_request(self):
        color, creator = active("color"), active("creator", "181")
        source = "EXACT_AUDIT_SENTINEL keep the red sleeve and the same ending; exact text: 等我。"
        checked = 0
        for module, args in ((h3, h3_args), (sd, sd_args)):
            for director in ("none", "ning_wenwu", "continuous_combat"):
                for story_on, emotion_on, combat_on in itertools.product((False, True), repeat=3):
                    with self.subTest(target=module.__name__, director=director, storyboard=story_on,
                                      emotion=emotion_on, combat=combat_on):
                        configs = {
                            "director_skill": director,
                            "storyboard_director_config": storyboard.build_storyboard_director_config(storyboard.STORYBOARD_ON) if story_on else None,
                            "performance_director_config": performance.build_performance_director_config(performance.PERFORMANCE_TUDOU) if emotion_on else None,
                            "combat_camera_config": combat.build_combat_camera_config(
                                combat.CAMERA_STRONG, combat.CONTINUITY_CONTINUOUS, combat.IMPACT_STYLIZED) if combat_on else None,
                        }
                        messages = module._build_messages(
                            **args(prompt=source, shot_count=1, **configs), color_style_config=color, creator_style_config=creator)
                        snapshot = copy.deepcopy(messages)
                        if module is h3:
                            repaired = module._h3_language_repair_messages(
                                "draft", "English", None, messages, **configs,
                                color_style_config=color, creator_style_config=creator)
                        else:
                            # Exercise the same bounded repair composition used by
                            # Seedance; no provider completion is needed to inspect it.
                            repaired = module.local_language_repair_messages("draft", "English")
                            repaired = module.preserve_director_on_repair(
                                repaired, messages, director,
                                combat_camera_config=configs["combat_camera_config"],
                                performance_director_config=configs["performance_director_config"])
                            repaired = module.preserve_storyboard_on_repair(repaired, messages, configs["storyboard_director_config"])
                            repaired = module.preserve_speech_on_repair(repaired, messages)
                            repaired = styles.preserve_visual_styles_on_repair(repaired, messages, color, creator)
                        all_text = "\n".join(primary_text(message["content"]) for message in repaired)
                        self.assertEqual(all_text.count(styles.MARKER), 1)
                        self.assertIn("EXACT_AUDIT_SENTINEL", all_text)
                        self.assertIn(primary_text(messages[1]["content"]), all_text)
                        self.assertTrue(repaired[0]["content"].startswith(messages[0]["content"]))
                        self.assertEqual(messages, snapshot)
                        self.assertEqual(repaired, styles.preserve_visual_styles_on_repair(repaired, messages, color, creator))
                        checked += 1
        self.assertEqual(checked, 48)

    def test_8_color_label_cases_keep_thematic_names_in_ui_not_model_rules(self):
        detail = routes.detail_payload("color", "001")
        swatch = next(c for c in detail["resource"]["primary"] if c["code"] == "C04")
        self.assertEqual((swatch["name_en"], swatch["name_zh"]), ("Terror Scarlet", "恐惧猩红"))
        self.assertEqual(detail["model_calls"], 0)
        checked = 0
        for target, scope, with_creator in itertools.product(
                ("h3", "seedance20"), (styles.COLOR_ONLY, styles.COLOR_LIGHT), (False, True)):
            with self.subTest(target=target, scope=scope, creator=with_creator):
                rule = styles.visual_style_instruction(
                    active("color", scope=scope), active("creator", "181") if with_creator else None,
                    target, fixed_shot_count=1)
                self.assertIn("C04 #C41E3A 8%", rule)
                for group in ("primary", "accents"):
                    for color in detail["resource"][group]:
                        self.assertNotIn(color["name_en"], rule)
                        self.assertNotIn(color["name_zh"], rule)
                self.assertNotIn("Terror Scarlet", rule)
                checked += 1
        self.assertEqual(checked, 8)

    def test_21_consumer_schema_negatives_reject_after_recomputed_manifest_hash(self):
        catalog = json.loads((styles.ROOT / "catalog.json").read_bytes())
        originals = {kind: json.loads((styles.ROOT / (kind + "s") / "001.json").read_bytes())
                     for kind in ("color", "creator")}
        resource_cases = [
            ("creator", "dimension-list", lambda v: v["methods"][0].update(dimension=[])),
            ("creator", "unknown-review-code", lambda v: v["review_notes"].append("PRIVATE_UNKNOWN_CODE")),
            ("creator", "nonboolean-cuts", lambda v: v["methods"][0].update(requires_cuts=1)),
            ("creator", "empty-methods", lambda v: v.update(methods=[])),
            ("creator", "all-cut-dependent", lambda v: [m.update(requires_cuts=True) for m in v["methods"]]),
            ("creator", "external-rule-field", lambda v: v.update(instruction="PRIVATE")),
            ("color", "boolean-share", lambda v: v["primary"][0].update(share=True)),
            ("color", "nan-share", lambda v: v["primary"][0].update(share=float("nan"))),
            ("color", "infinite-share", lambda v: v["primary"][0].update(share=float("inf"))),
            ("color", "huge-integer-share", lambda v: v["primary"][0].update(share=10 ** 1000)),
            ("color", "zero-share", lambda v: v["primary"][0].update(share=0)),
            ("color", "accent-area-field", lambda v: v["accents"][0].update(share=0.2)),
            ("color", "nonstring-notes", lambda v: v["color_notes"].update(en=[])),
            ("color", "wrong-color-code", lambda v: v["primary"][0].update(code="C06")),
            ("color", "bad-hex", lambda v: v["primary"][0].update(hex="PRIVATE")),
            ("color", "unbounded-notes", lambda v: v["color_notes"].update(en="x" * 701)),
        ]
        catalog_cases = [
            ("role-list", lambda v: v["entries"][0].update(creator_role=[])),
            ("numeric-id", lambda v: v["entries"][0].update(id=1)),
            ("digest-list", lambda v: v["entries"][0].update(color_sha256=[])),
            ("label-list", lambda v: v["entries"][0].update(label_en=[])),
            ("extra-field", lambda v: v["entries"][0].update(extra="PRIVATE")),
        ]
        checked = 0
        with tempfile.TemporaryDirectory(prefix="t8-cross-review-consumer-") as folder:
            root = Path(folder)
            for kind in originals:
                (root / (kind + "s")).mkdir()

            def reset():
                (root / "catalog.json").write_bytes(json_bytes(catalog))
                for kind, value in originals.items():
                    (root / (kind + "s") / "001.json").write_bytes(json_bytes(value))

            reset()
            with patch.object(styles, "ROOT", root):
                for kind in originals:
                    self.assertEqual(styles.load_resource(kind, "001")[0], originals[kind])
                for kind, label, mutate in resource_cases:
                    with self.subTest(resource=kind, corruption=label):
                        reset()
                        data = copy.deepcopy(originals[kind])
                        mutate(data)
                        raw = json_bytes(data)
                        (root / (kind + "s") / "001.json").write_bytes(raw)
                        matching_catalog = copy.deepcopy(catalog)
                        matching_catalog["entries"][0][kind + "_sha256"] = hashlib.sha256(raw).hexdigest()
                        (root / "catalog.json").write_bytes(json_bytes(matching_catalog))
                        self.assertEqual(styles.load_catalog()[0]["entries"][0][kind + "_sha256"], hashlib.sha256(raw).hexdigest())
                        with self.assertRaises(ValueError) as caught:
                            styles.load_resource(kind, "001")
                        self.assertNotIn("PRIVATE", str(caught.exception))
                        checked += 1
                for label, mutate in catalog_cases:
                    with self.subTest(resource="catalog", corruption=label):
                        reset()
                        data = copy.deepcopy(catalog)
                        mutate(data)
                        (root / "catalog.json").write_bytes(json_bytes(data))
                        with self.assertRaises(ValueError) as caught:
                            styles.load_resource("color", "001")
                        self.assertNotIn("PRIVATE", str(caught.exception))
                        checked += 1
        self.assertEqual(checked, 21)

    def test_invalid_kind_uses_finite_config_error(self):
        for kind in ([], {}, None, 1, True, 'PRIVATE'):
            for fn, args in ((styles.load_resource, (kind, '001')),
                             (styles.build_style_config, (kind,)),
                             (styles.resolve_style_config, (None, kind)),
                             (styles.resolve_style_config, ({}, kind))):
                with self.subTest(kind=repr(kind), function=fn.__name__), self.assertRaises(ValueError) as caught:
                    fn(*args)
                self.assertNotIn('PRIVATE', str(caught.exception))


if __name__ == "__main__":
    unittest.main()
