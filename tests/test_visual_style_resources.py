"""Offline resource contracts; no claim of model adherence or visual quality.

The local source pack is deliberately not required by these tests or the runtime.
Reproducibility against a pack is checked separately with the builder's explicit
--source-root <directory> --check command.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_visual_resource_builder", ROOT / "tools/build_visual_styles.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
RESOURCE_ROOT = ROOT / "resources/visual_styles"
PROVENANCE_PATH = ROOT / "research_sources/visual-styles-200.json"
EXPECTED_IDS = [f"{n:03d}" for n in range(1, 201)]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_palette():
    """A synthetic importer fixture using public resource numbers, not source files."""
    resource = read(RESOURCE_ROOT / "colors/001.json")
    groups = {}
    for group, output in (("primary", "primary"), ("accents", "emotional")):
        groups[output] = []
        for color in resource[group]:
            color = dict(color)
            color["rgb"] = [int(color["hex"][i:i + 2], 16) for i in (1, 3, 5)]
            if "share" in color:
                color["ratio"] = color.pop("share")
            groups[output].append(color)
    return {"palette": groups}


class VisualStyleResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read(RESOURCE_ROOT / "catalog.json")
        cls.curated = builder.read_curation()
        cls.temp = tempfile.TemporaryDirectory(prefix="t8-visual-style-resources-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.working = Path(cls.temp.name) / "resources"
        shutil.copytree(RESOURCE_ROOT, cls.working)
        cls.provenance = Path(cls.temp.name) / "provenance.json"
        shutil.copyfile(PROVENANCE_PATH, cls.provenance)

    @contextmanager
    def changed_files(self, replacements):
        originals = {path: path.read_bytes() if path.exists() else None for path in replacements}
        try:
            for path, content in replacements.items():
                if content is None:
                    path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
            yield
        finally:
            for path, content in originals.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)

    def replacements_for_resource(self, relative_path, value):
        """Update hashes too, so schema negatives cannot pass merely via hash failure."""
        catalog = read(self.working / "catalog.json")
        raw = builder.canonical_bytes(value)
        style_id = Path(relative_path).stem
        kind = "color" if relative_path.startswith("colors/") else "creator"
        next(e for e in catalog["entries"] if e["id"] == style_id)[kind + "_sha256"] = hashlib.sha256(raw).hexdigest()
        catalog_raw = builder.canonical_bytes(catalog)
        provenance = read(self.provenance)
        provenance["catalog_sha256"] = hashlib.sha256(catalog_raw).hexdigest()
        return {self.working / relative_path: raw, self.working / "catalog.json": catalog_raw,
                self.provenance: builder.canonical_bytes(provenance)}

    def test_all_resources_verify_without_source_pack(self):
        self.assertEqual(builder.verify_resources(), {
            "colors": 200, "creators": 200, "methods": 400, "limited_method_specificity": 66})

    def test_exact_catalog_shape_identity_roles_and_categories(self):
        self.assertEqual(set(self.catalog), {"schema_version", "revision", "entries"})
        self.assertEqual(self.catalog["schema_version"], "t8-visual-style-catalog/v1")
        self.assertEqual(self.catalog["revision"], "1.0.0")
        self.assertEqual([e["id"] for e in self.catalog["entries"]], EXPECTED_IDS)
        expected_roles = {"058": "cinematographer", "059": "cinematographer", "074": "team",
                          "097": "art_director", "156": "team"}
        for entry in self.catalog["entries"]:
            self.assertEqual(set(entry), {"id", "label_zh", "label_en", "category", "creator_role",
                                         "color_revision", "color_sha256", "creator_revision", "creator_sha256"})
            self.assertEqual(entry["creator_role"], expected_roles.get(entry["id"], "director"))
            self.assertEqual(int(entry["category"][:2]), (int(entry["id"]) - 1) // 20 + 1)
            self.assertEqual(entry["color_revision"], "1.0.0")
            self.assertEqual(entry["creator_revision"], "1.0.0")
            for field in ("label_zh", "label_en", "category"):
                self.assertTrue(entry[field].strip())
        self.assertNotEqual(self.catalog["entries"][155]["label_zh"], "等")

    def test_independent_numeric_palette_contract_and_byte_digests(self):
        vectors = set()
        for entry in self.catalog["entries"]:
            path = RESOURCE_ROOT / "colors" / (entry["id"] + ".json")
            raw = path.read_bytes()
            value = json.loads(raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["color_sha256"])
            self.assertEqual(set(value), {"schema_version", "id", "revision", "primary", "accents",
                                          "color_notes", "lighting_notes"})
            self.assertEqual((value["id"], value["revision"], value["schema_version"]),
                             (entry["id"], "1.0.0", "t8-color-style-resource/v1"))
            for group, length, prefix in (("primary", 6, "C"), ("accents", 4, "E")):
                self.assertEqual(len(value[group]), length)
                for n, swatch in enumerate(value[group], 1):
                    self.assertEqual(set(swatch), {"code", "name_zh", "name_en", "hex"}
                                     | ({"share"} if group == "primary" else set()))
                    self.assertEqual(swatch["code"], f"{prefix}{n:02d}")
                    self.assertRegex(swatch["hex"], r"^#[0-9A-F]{6}$")
                    if group == "primary":
                        self.assertIn(type(swatch["share"]), (float, int))
                        self.assertTrue(math.isfinite(swatch["share"]))
                        self.assertGreater(swatch["share"], 0)
                        self.assertLessEqual(swatch["share"], 1)
            self.assertAlmostEqual(sum(c["share"] for c in value["primary"]), 1, places=6)
            vectors.add(tuple(c["hex"] for c in value["primary"]))
        self.assertEqual(len(vectors), 200)

    def test_creator_methods_bounded_typed_and_not_accidentally_cloned(self):
        signatures = set()
        all_methods = []
        allowed_codes = {"source_examples_excluded", "external_protocol_excluded", "color_kept_separate",
                         "conflicting_avoid_excluded", "generic_avoid_excluded", "limited_method_specificity",
                         "source_role_corrected"}
        for entry in self.catalog["entries"]:
            raw = (RESOURCE_ROOT / "creators" / (entry["id"] + ".json")).read_bytes()
            value = json.loads(raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["creator_sha256"])
            self.assertEqual(set(value), {"schema_version", "id", "revision", "methods", "review_notes"})
            self.assertEqual(value["schema_version"], "t8-creator-style-resource/v1")
            self.assertEqual(value["id"], entry["id"])
            self.assertEqual(value["revision"], "1.0.0")
            self.assertEqual(len(value["methods"]), 2)
            self.assertTrue(any(not m["requires_cuts"] for m in value["methods"]))
            self.assertEqual(len(set(value["review_notes"])), len(value["review_notes"]))
            self.assertTrue(set(value["review_notes"]) <= allowed_codes)
            for method in value["methods"]:
                self.assertEqual(set(method), {"dimension", "text_zh", "text_en", "requires_cuts"})
                self.assertIn(method["dimension"], {"framing", "camera", "staging", "rhythm", "information", "editing"})
                self.assertIs(type(method["requires_cuts"]), bool)
                self.assertEqual(method["requires_cuts"], method["dimension"] == "editing")
                for language in ("zh", "en"):
                    text = method["text_" + language]
                    self.assertTrue(text and text == text.strip())
                    self.assertLessEqual(len(text), 500)
                    self.assertFalse(any(ord(c) < 32 for c in text))
                all_methods.append(method["text_en"])
            signatures.add(tuple(m["text_en"] for m in value["methods"]))
        # Distinct wording catches copy accidents; it is not evidence of 200 unique theories.
        self.assertEqual(len(signatures), 200)
        self.assertEqual(len(set(all_methods)), 400)

    def test_no_source_protocols_duration_caps_or_absolute_paths_in_runtime_data(self):
        forbidden = re.compile(r"Seedance|MiniMax|Runway|Pika|overall_soundscape|--ar|7000|30\s*秒|12\s*[s秒]|[A-Z]:[\\/]", re.I)
        for folder in ("colors", "creators"):
            for path in (RESOURCE_ROOT / folder).glob("*.json"):
                self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), str(path))
        for path in (RESOURCE_ROOT / "creators").glob("*.json"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"#[0-9a-fA-F]{6}")

    def test_weak_sources_and_conflicts_are_disclosed_not_hidden(self):
        limited = []
        for ident in EXPECTED_IDS:
            value = read(RESOURCE_ROOT / "creators" / (ident + ".json"))
            if "limited_method_specificity" in value["review_notes"]:
                limited.append(ident)
        self.assertEqual(len(limited), 66)
        self.assertIn("155", limited)
        self.assertIn("156", limited)
        self.assertIn("conflicting_avoid_excluded", read(RESOURCE_ROOT / "creators/142.json")["review_notes"])
        light = read(RESOURCE_ROOT / "colors/142.json")["lighting_notes"]
        self.assertIn("soft", light["en"].lower())
        self.assertNotIn("avoid flat", light["en"].lower())
        generic = read(RESOURCE_ROOT / "creators/155.json")["methods"]
        self.assertIn("template", generic[0]["text_en"])
        self.assertIn("without adding", generic[1]["text_en"])

    def test_bounded_note_lengths_and_runtime_file_sizes(self):
        self.assertLess((RESOURCE_ROOT / "catalog.json").stat().st_size, 192 * 1024)
        for kind in ("colors", "creators"):
            for path in (RESOURCE_ROOT / kind).glob("*.json"):
                self.assertLess(path.stat().st_size, 24 * 1024)
        for path in (RESOURCE_ROOT / "colors").glob("*.json"):
            value = read(path)
            for field in ("color_notes", "lighting_notes"):
                self.assertEqual(set(value[field]), {"zh", "en"})
                for text in value[field].values():
                    self.assertTrue(text.strip())
                    self.assertLessEqual(len(text), 700)

    def test_source_numeric_values_are_not_reweighted_or_accent_area_added(self):
        source = source_palette()
        expected = [0.13, 0.17, 0.19, 0.21, 0.23, 0.07]
        for item, share in zip(source["palette"]["primary"], expected):
            item["ratio"] = share
        source["real_palettes"] = [{"ratio": 75, "hex": "#FFFFFF"}]
        source["palette"]["emotional"][0]["ratio"] = 90
        source["palette"]["emotional"][0]["emotion"] = "invent a war and a new character"
        result = builder.color_resource("001", source, self.curated["001"])
        self.assertEqual([c["share"] for c in result["primary"]], expected)
        self.assertTrue(all("share" not in c and "ratio" not in c and "emotion" not in c for c in result["accents"]))
        self.assertNotIn("real_palettes", result)
        self.assertNotIn("invent a war", json.dumps(result))

    def test_missing_accent_names_use_matching_color_or_neutral_fallback(self):
        primary = read(RESOURCE_ROOT / "colors/001.json")["primary"]
        source = {"code": "E01", "hex": primary[0]["hex"], "rgb": [26, 35, 50], "name_en": "Emotional 1"}
        result = builder._source_color(source, 1, accent=True, primary=primary)
        self.assertEqual((result["name_zh"], result["name_en"]), (primary[0]["name_zh"], primary[0]["name_en"]))
        source.update(hex="#ABCDEF", rgb=[171, 205, 239])
        result = builder._source_color(source, 1, accent=True, primary=primary)
        self.assertEqual((result["name_zh"], result["name_en"]), ("候选色 1", "Accent 1"))

    def test_source_color_malformed_numeric_and_identity_rejected(self):
        cases = [dict(ratio=True), dict(ratio=0), dict(ratio=-0.1), dict(ratio=1.1),
                 dict(ratio=float("nan")), dict(ratio=float("inf")), dict(rgb=[0, 0, 0]),
                 dict(code="C02"), dict(hex="red"), dict(name_zh="x" * 101)]
        for change in cases:
            with self.subTest(change=change):
                source = source_palette()
                source["palette"]["primary"][0].update(change)
                with self.assertRaises(ValueError):
                    builder.color_resource("001", source, self.curated["001"])
        source = source_palette()
        source["palette"]["primary"][0]["ratio"] = 0.8
        with self.assertRaisesRegex(ValueError, "sum"):
            builder.color_resource("001", source, self.curated["001"])
        for group in ("primary", "emotional"):
            source = source_palette()
            source["palette"][group].pop()
            with self.assertRaises(ValueError):
                builder.color_resource("001", source, self.curated["001"])

    def test_provenance_is_finite_relative_hash_bound_and_honest(self):
        provenance = read(PROVENANCE_PATH)
        self.assertEqual([r["id"] for r in provenance["records"]], EXPECTED_IDS)
        self.assertEqual(sum(r["missing_accent_name_count"] for r in provenance["records"]), 160)
        self.assertEqual(provenance["limited_method_specificity_count"], 66)
        self.assertEqual(provenance["catalog_sha256"], hashlib.sha256((RESOURCE_ROOT / "catalog.json").read_bytes()).hexdigest())
        self.assertEqual(provenance["curation_sha256"], hashlib.sha256((RESOURCE_ROOT / "curation.tsv").read_bytes()).hexdigest())
        for record in provenance["records"]:
            self.assertEqual(record["review_status"], "adapted_from_supplied_material_not_model_or_video_validated")
            self.assertEqual([f["kind"] for f in record["files"]], ["palette", "main", "video"])
            self.assertEqual(len(set(record["method_basis"])), len(record["method_basis"]))
            for file in record["files"]:
                self.assertRegex(file["sha256"], r"^[0-9a-f]{64}$")
                self.assertFalse(Path(file["relative_path"]).is_absolute())
                self.assertNotIn("..", Path(file["relative_path"]).parts)
                self.assertTrue(Path(file["relative_path"]).parts[1].startswith(record["id"] + "_"))
        self.assertIn("no inference or video validation", provenance["evidence"])

    def test_every_json_has_canonical_lf_utf8_bytes_and_no_extra_assets(self):
        for path in list(RESOURCE_ROOT.rglob("*.json")) + [PROVENANCE_PATH]:
            raw = path.read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(raw, (json.dumps(json.loads(raw), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        self.assertEqual(len(list(RESOURCE_ROOT.rglob("*.json"))), 401)
        self.assertEqual({p.suffix for p in RESOURCE_ROOT.rglob("*") if p.is_file()}, {".json", ".tsv"})

    def test_duplicate_json_properties_and_nonfinite_values_rejected(self):
        path = Path(self.temp.name) / "invalid.json"
        for raw in (b'{"id":"001","id":"002"}', b'{"ratio":NaN}', b'{"ratio":Infinity}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                builder.read_json(path)

    def test_curation_rejects_missing_duplicate_reordered_unbounded_or_invalid_methods(self):
        lines = (RESOURCE_ROOT / "curation.tsv").read_text(encoding="utf-8").splitlines()
        body = [line for line in lines if line and not line.startswith("#")]
        self.assertEqual(len(body), 200)
        path = Path(self.temp.name) / "bad-curation.tsv"
        invalid = [body[1:], body + [body[-1]], [body[1], body[0]] + body[2:],
                   [body[0] + "|unexpected"] + body[1:]]
        for index, value in ((1, "invalid_dimension"), (2, "x" * 501), (3, "bad\tcontrol"), (8, "x" * 701)):
            changed = body[0].split("|")
            changed[index] = value
            invalid.append(["|".join(changed)] + body[1:])
        changed = body[0].split("|")
        changed[1] = changed[4] = "editing"
        invalid.append(["|".join(changed)] + body[1:])
        for n, content in enumerate(invalid):
            with self.subTest(case=n):
                path.write_text("\n".join(content), encoding="utf-8")
                with self.assertRaises(ValueError):
                    builder.read_curation(path)

    def test_corrupt_hash_and_noncanonical_bytes_rejected(self):
        path = self.working / "colors/001.json"
        value = read(path)
        value["primary"][0]["hex"] = "#FFFFFF"
        with self.changed_files({path: builder.canonical_bytes(value)}):
            with self.assertRaisesRegex(ValueError, "digest"):
                builder.verify_resources(self.working, self.provenance)
        with self.changed_files({path: path.read_bytes().replace(b"\n", b"\r\n")}):
            with self.assertRaisesRegex(ValueError, "canonical"):
                builder.verify_resources(self.working, self.provenance)

    def test_color_schema_rejects_bad_values_even_with_recomputed_hash(self):
        original = read(self.working / "colors/001.json")
        mutations = [lambda v: v.update(unexpected="payload"),
                     lambda v: v["primary"][0].update(share=True),
                     lambda v: v["primary"][0].update(share=10 ** 1000),
                     lambda v: v["primary"][0].update(share=0),
                     lambda v: v["primary"][0].update(code="C06"),
                     lambda v: v["accents"][0].update(share=0.3),
                     lambda v: v["color_notes"].update(en="x" * 701),
                     lambda v: v["color_notes"].update(ar="extra language"),
                     lambda v: v["lighting_notes"].update(en="unreviewed lighting")]
        for n, mutate in enumerate(mutations):
            with self.subTest(case=n):
                value = copy.deepcopy(original)
                mutate(value)
                with self.changed_files(self.replacements_for_resource("colors/001.json", value)):
                    with self.assertRaises(ValueError):
                        builder.verify_resources(self.working, self.provenance)

    def test_creator_unreviewed_mutation_rejected_even_with_recomputed_hash(self):
        value = read(self.working / "creators/001.json")
        value["methods"][0]["text_en"] = "Invent a different film plot."
        with self.changed_files(self.replacements_for_resource("creators/001.json", value)):
            with self.assertRaisesRegex(ValueError, "reviewed adaptation"):
                builder.verify_resources(self.working, self.provenance)

    def test_source_large_integer_share_has_bounded_validation_error(self):
        source = {"code": "C01", "hex": "#112233", "rgb": [17, 34, 51],
                  "name_zh": "蓝色", "name_en": "Blue", "ratio": 10 ** 1000}
        with self.assertRaisesRegex(ValueError, "Invalid source share"):
            builder._source_color(source, 1, accent=False, primary=[])

    def test_catalog_reorder_wrong_role_and_unexpected_asset_rejected(self):
        for change in (lambda v: v["entries"].reverse(),
                       lambda v: v["entries"][57].update(creator_role="director"),
                       lambda v: v["entries"][0].update(color_revision="0.1.0")):
            value = read(self.working / "catalog.json")
            change(value)
            with self.changed_files({self.working / "catalog.json": builder.canonical_bytes(value)}):
                with self.assertRaises(ValueError):
                    builder.verify_resources(self.working, self.provenance)
        with self.changed_files({self.working / "film_still.png": b"not shipped"}):
            with self.assertRaisesRegex(ValueError, "Unexpected resource"):
                builder.verify_resources(self.working, self.provenance)
        with self.changed_files({self.working / "colors/200.json": None}):
            with self.assertRaisesRegex(ValueError, "coverage"):
                builder.verify_resources(self.working, self.provenance)

    def test_provenance_bad_relative_paths_and_hash_binding_rejected(self):
        for change in (lambda v: v.update(catalog_sha256="0" * 64),
                       lambda v: v.update(curation_sha256="0" * 64),
                       lambda v: v["records"][0]["files"][0].update(relative_path="../outside.json"),
                       lambda v: v["records"][0]["files"][0].update(sha256="not a hash"),
                       lambda v: v["records"][0].update(review_notes=[])):
            value = read(self.provenance)
            change(value)
            with self.changed_files({self.provenance: builder.canonical_bytes(value)}):
                with self.assertRaises(ValueError):
                    builder.verify_resources(self.working, self.provenance)

    def test_cli_check_has_no_source_dependency_and_rebuild_requires_explicit_path(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/build_visual_styles.py"), "--check"],
                                capture_output=True, text=True, encoding="utf-8", cwd=self.temp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["creators"], 200)
        result = subprocess.run([sys.executable, str(ROOT / "tools/build_visual_styles.py")],
                                capture_output=True, text=True, encoding="utf-8", cwd=self.temp.name)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--source-root is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
