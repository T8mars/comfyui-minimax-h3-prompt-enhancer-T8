"""Build the reviewed visual-style resources from a read-only local source pack.

The TSV is an independently written, per-record adaptation, not executable source
instructions. This tool mechanically copies color numbers, records provenance,
and emits canonical JSON. It never calls a model, downloads assets or edits the
source. --check without --source-root verifies the shipped, self-contained data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "resources" / "visual_styles"
PROVENANCE_PATH = ROOT / "research_sources" / "visual-styles-200.json"
REVISION = "1.0.0"
CATALOG_SCHEMA = "t8-visual-style-catalog/v1"
COLOR_SCHEMA = "t8-color-style-resource/v1"
CREATOR_SCHEMA = "t8-creator-style-resource/v1"
IDS = tuple(f"{i:03d}" for i in range(1, 201))
DIMENSIONS = frozenset({"framing", "camera", "staging", "rhythm", "information", "editing"})
REVIEW_CODES = frozenset({
    "source_examples_excluded", "external_protocol_excluded", "color_kept_separate",
    "conflicting_avoid_excluded", "generic_avoid_excluded", "limited_method_specificity",
    "source_role_corrected",
})
# These entries contain usable techniques, but at least one method relies on a
# generic camera template or a broad source keyword rather than a detailed
# creator-specific directing procedure. The UI must disclose that distinction.
LIMITED_IDS = frozenset(f"{i:03d}" for i in (
    69, 70, 73, 79, 82, 84, 85, 88, 91, 92, 94, 96, 97, 104, 105, 106,
    109, 110, 111, 112, 114, 115, 116, 118, 119, 121, 123, 125, 126, 128,
    129, 132, 135, 136, 140, 144, 145, 146, 147, 151, 152, 153, 155,
    156, 157, 158, 160, 161, 162, 164, 166, 168, 170, 173, 174, 175,
    176, 179, 188, 191, 193, 195, 196, 197, 198, 199,
))
ROLES = {"058": "cinematographer", "059": "cinematographer", "074": "team",
         "097": "art_director", "156": "team"}
HEX = re.compile(r"#[0-9A-F]{6}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON property")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text(value, limit=500):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
            "Invalid bounded text")
    require(not any(ord(c) < 32 for c in value), "Control character in text")
    return value.strip()


def read_curation(path: Path | None = None):
    path = path or RESOURCE_ROOT / "curation.tsv"
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("|")
        require(len(fields) == 9, "Curation row must contain nine fields")
        ident, dim1, zh1, en1, dim2, zh2, en2, light_zh, light_en = fields
        require(ident in IDS and ident not in result, "Invalid or duplicate curated ID")
        methods = []
        for dimension, zh, en in ((dim1, zh1, en1), (dim2, zh2, en2)):
            require(dimension in DIMENSIONS, "Invalid method dimension")
            methods.append({"dimension": dimension, "text_zh": text(zh), "text_en": text(en),
                            "requires_cuts": dimension == "editing"})
        require(any(not m["requires_cuts"] for m in methods), "No single-shot method")
        result[ident] = {"methods": methods,
                         "lighting_notes": {"zh": text(light_zh, 700), "en": text(light_en, 700)}}
    require(tuple(result) == IDS, "Curation must cover ordered IDs 001..200 exactly")
    return result


def review_codes(ident: str):
    codes = {"source_examples_excluded", "external_protocol_excluded", "color_kept_separate"}
    if int(ident) >= 61:
        codes.add("generic_avoid_excluded")
    if ident in {"067", "077", "142"}:
        codes.add("conflicting_avoid_excluded")
    if ident in LIMITED_IDS:
        codes.add("limited_method_specificity")
    if ident in ROLES:
        codes.add("source_role_corrected")
    return sorted(codes)


def creator_resource(ident: str, curated: dict):
    return {"schema_version": CREATOR_SCHEMA, "id": ident, "revision": REVISION,
            "methods": curated["methods"], "review_notes": review_codes(ident)}


def _source_color(item: dict, index: int, *, accent: bool, primary: list):
    require(type(item) is dict, "Invalid source color")
    color_hex = text(item.get("hex"), 7).upper()
    require(bool(HEX.fullmatch(color_hex)), "Invalid source HEX")
    expected_rgb = [int(color_hex[i:i + 2], 16) for i in (1, 3, 5)]
    require(item.get("rgb") == expected_rgb, "Source RGB/HEX mismatch")
    code = ("E" if accent else "C") + f"{index:02d}"
    require(item.get("code") == code, "Source color code mismatch")
    matching = next((c for c in primary if c["hex"] == color_hex), {})
    # Some source accents have an emotion but no color name. Never turn that
    # emotional interpretation into a runtime instruction or invent a color fact.
    name_zh = item.get("name_zh") or matching.get("name_zh") or f"候选色 {index}"
    name_en = item.get("name_en") or matching.get("name_en") or f"Accent {index}"
    if accent and re.fullmatch(r"Emotional \d+", name_en):
        name_en = matching.get("name_en") or f"Accent {index}"
    result = {"code": code, "name_zh": text(name_zh, 100), "name_en": text(name_en, 100),
              "hex": color_hex}
    if not accent:
        share = item.get("ratio")
        require(type(share) in (float, int) and 0 < share <= 1 and math.isfinite(share),
                "Invalid source share")
        result["share"] = share  # Preserve the original numeric value; never normalize.
    return result


def color_resource(ident: str, source: dict, curated: dict):
    palette = source["palette"]
    require(type(palette.get("primary")) is list and len(palette["primary"]) == 6,
            "Expected six source primary colors")
    require(type(palette.get("emotional")) is list and len(palette["emotional"]) == 4,
            "Expected four source accent candidates")
    primary = [_source_color(c, i, accent=False, primary=[])
               for i, c in enumerate(palette["primary"], 1)]
    require(abs(sum(c["share"] for c in primary) - 1) <= 1e-6, "Source shares do not sum to one")
    accents = [_source_color(c, i, accent=True, primary=primary)
               for i, c in enumerate(palette["emotional"], 1)]
    # A precise numeric relationship rather than a claim of measured film color.
    order = sorted(primary, key=lambda c: -c["share"])
    top = ", ".join(c["hex"] for c in order[:3])
    return {"schema_version": COLOR_SCHEMA, "id": ident, "revision": REVISION,
            "primary": primary, "accents": accents,
            "color_notes": {
                "zh": f"来源权重前三色为 {top}；保留六色相对关系作为软参考，不要求全部出现。四候选色不叠加面积，不授权更改锁定主体颜色。",
                "en": f"The three highest source weights are {top}. Retain the six-color relationship as soft guidance; not every color must appear. Four accent candidates add no area quota or permission to recolor locked subjects."},
            "lighting_notes": curated["lighting_notes"]}


def build(source_root: Path):
    source_root = source_root.resolve(strict=True)
    require(source_root.is_dir() and source_root != RESOURCE_ROOT.resolve(), "Invalid source directory")
    curated = read_curation()
    folders = {}
    for category in sorted(source_root.iterdir()):
        if not category.is_dir() or not re.fullmatch(r"\d{2}_.+", category.name):
            continue
        for folder in sorted(category.iterdir()):
            if not folder.is_dir() or not re.fullmatch(r"\d{3}_.+", folder.name):
                continue
            ident = folder.name[:3]
            require(ident in IDS and ident not in folders, "Invalid or duplicate source ID")
            require(folder.resolve().is_relative_to(source_root), "Source folder escapes source root")
            require(int(category.name[:2]) == (int(ident) - 1) // 20 + 1, "Source category mismatch")
            folders[ident] = folder
    require(set(folders) == set(IDS), "Source must contain exactly 200 records")
    files, entries, provenance = {}, [], []
    for ident in IDS:
        folder = folders[ident]
        paths = {"palette": folder / "assets" / "color_palettes" / "palette.json",
                 "main": folder / "色卡主文档.md", "video": folder / "prompts" / "video_prompts.md"}
        require(all(path.resolve(strict=True).is_relative_to(source_root) for path in paths.values()),
                "Source file escapes source root")
        source = read_json(paths["palette"])
        require(str(source["director"]["id"]).zfill(3) == ident, "Palette/folder ID mismatch")
        color = color_resource(ident, source, curated[ident])
        creator = creator_resource(ident, curated[ident])
        color_bytes, creator_bytes = canonical_bytes(color), canonical_bytes(creator)
        files[f"colors/{ident}.json"] = color_bytes
        files[f"creators/{ident}.json"] = creator_bytes
        entries.append({"id": ident, "label_zh": text(source["director"]["name_zh"], 100),
                        "label_en": text(source["director"]["name_en"], 100),
                        "category": folder.parent.name, "creator_role": ROLES.get(ident, "director"),
                        "color_revision": REVISION, "color_sha256": digest(color_bytes),
                        "creator_revision": REVISION, "creator_sha256": digest(creator_bytes)})
        provenance.append({"id": ident, "files": [
            {"kind": kind, "relative_path": path.relative_to(source_root).as_posix(),
             "sha256": digest(path.read_bytes())} for kind, path in paths.items()],
            "method_basis": ["palette.composition_keywords", "main.camera_features"]
                            + (["video.camera_templates"] if ident in LIMITED_IDS else []),
            "review_notes": creator["review_notes"],
            "missing_accent_name_count": sum(not c.get("name_zh") for c in source["palette"]["emotional"]),
            "review_status": "adapted_from_supplied_material_not_model_or_video_validated"})
    files["catalog.json"] = canonical_bytes({"schema_version": CATALOG_SCHEMA, "revision": REVISION,
                                              "entries": entries})
    entrypoints = ("SKILL.md", "references/卷内速查表_001-200.md")
    require(all((source_root / rel).resolve(strict=True).is_relative_to(source_root) for rel in entrypoints),
            "Source entrypoint escapes source root")
    provenance_payload = {
        "schema_version": "t8-visual-style-provenance/v1", "revision": REVISION,
        "catalog_sha256": digest(files["catalog.json"]),
        "curation_sha256": digest((RESOURCE_ROOT / "curation.tsv").read_bytes()),
        "entry_count": 200, "color_count": 200, "creator_count": 200,
        "limited_method_specificity_count": len(LIMITED_IDS),
        "evidence": "All source camera tables and composition fields read; independent bounded bilingual adaptation. Specificity varies; no inference or video validation.",
        "source_entrypoints": [{"relative_path": rel, "sha256": digest((source_root / rel).read_bytes())}
                               for rel in entrypoints],
        "excluded": ["film_stills", "source_html_svg", "source_prompt_templates", "real_palettes",
                     "model_protocol_claims", "duration_caps", "fixed_end_freeze", "character_plot_invention"],
        "records": provenance,
    }
    return files, canonical_bytes(provenance_payload)


def verify_resources(resource_root: Path = RESOURCE_ROOT, provenance_path: Path = PROVENANCE_PATH):
    curated = read_curation(resource_root / "curation.tsv")
    catalog = read_json(resource_root / "catalog.json")
    require(set(catalog) == {"schema_version", "revision", "entries"}, "Catalog fields differ")
    require(catalog["schema_version"] == CATALOG_SCHEMA and catalog["revision"] == REVISION,
            "Catalog version differs")
    require((resource_root / "catalog.json").read_bytes() == canonical_bytes(catalog),
            "Catalog is not canonical UTF-8/LF JSON")
    require(type(catalog["entries"]) is list, "Catalog entries must be a list")
    require([e["id"] for e in catalog["entries"]] == list(IDS), "Catalog ID coverage differs")
    for kind in ("colors", "creators"):
        require(sorted(p.stem for p in (resource_root / kind).glob("*.json")) == list(IDS),
                "Resource file coverage differs")
    expected_files = {"catalog.json", "curation.tsv"} | {
        f"{kind}/{ident}.json" for kind in ("colors", "creators") for ident in IDS}
    require({p.relative_to(resource_root).as_posix() for p in resource_root.rglob("*") if p.is_file()}
            == expected_files, "Unexpected resource file; source assets must not be shipped")
    for entry in catalog["entries"]:
        require(set(entry) == {"id", "label_zh", "label_en", "category", "creator_role",
                               "color_revision", "color_sha256", "creator_revision", "creator_sha256"},
                "Catalog entry fields differ")
        ident = entry["id"]
        for field in ("label_zh", "label_en", "category"):
            require(entry[field] == text(entry[field], 100), "Catalog text is not normalized")
        require(re.fullmatch(r"\d{2}_.+", entry["category"]) is not None
                and int(entry["category"][:2]) == (int(ident) - 1) // 20 + 1,
                "Catalog category differs")
        require(entry["creator_role"] == ROLES.get(ident, "director"), "Creator role differs")
        require(all(entry[k] == REVISION for k in ("color_revision", "creator_revision")),
                "Catalog resource revision differs")
        require(all(type(entry[k]) is str and SHA.fullmatch(entry[k])
                    for k in ("color_sha256", "creator_sha256")), "Invalid catalog digest")
        for kind, singular, schema in (("colors", "color", COLOR_SCHEMA), ("creators", "creator", CREATOR_SCHEMA)):
            raw = (resource_root / kind / f"{ident}.json").read_bytes()
            item = read_json(resource_root / kind / f"{ident}.json")
            require(raw == canonical_bytes(item), "Resource is not canonical UTF-8/LF JSON")
            require(digest(raw) == entry[f"{singular}_sha256"], "Catalog/resource digest mismatch")
            require(item["id"] == ident and item["revision"] == REVISION and item["schema_version"] == schema,
                    "Resource identity mismatch")
            if singular == "creator":
                require(item == creator_resource(ident, curated[ident]), "Creator differs from reviewed adaptation")
            else:
                require(set(item) == {"schema_version", "id", "revision", "primary", "accents",
                                      "color_notes", "lighting_notes"}, "Color resource fields differ")
                require(type(item["primary"]) is list and len(item["primary"]) == 6
                        and type(item["accents"]) is list and len(item["accents"]) == 4,
                        "Color coverage differs")
                require(item["lighting_notes"] == curated[ident]["lighting_notes"], "Lighting differs from adaptation")
                shares = [c["share"] for c in item["primary"]]
                require(all(type(v) in (int, float) and 0 < v <= 1 and math.isfinite(v) for v in shares)
                        and abs(sum(shares) - 1) <= 1e-6, "Invalid primary shares")
                for group, prefix in (("primary", "C"), ("accents", "E")):
                    for n, color in enumerate(item[group], 1):
                        require(set(color) == {"code", "hex", "name_zh", "name_en"}
                                | ({"share"} if group == "primary" else set()), "Color fields differ")
                        require(color["code"] == f"{prefix}{n:02d}", "Color code differs")
                        require(type(color["hex"]) is str and HEX.fullmatch(color["hex"]), "Invalid resource HEX")
                        for language in ("zh", "en"):
                            require(color["name_" + language] == text(color["name_" + language], 100),
                                    "Color name is not normalized")
                for field in ("color_notes", "lighting_notes"):
                    require(type(item[field]) is dict and set(item[field]) == {"zh", "en"},
                            "Invalid bilingual notes")
                    require(all(v == text(v, 700) for v in item[field].values()), "Notes are not normalized")
    provenance = read_json(provenance_path)
    require(set(provenance) == {"schema_version", "revision", "catalog_sha256", "curation_sha256",
                               "entry_count", "color_count", "creator_count", "limited_method_specificity_count",
                               "evidence", "source_entrypoints", "excluded", "records"},
            "Provenance fields differ")
    require(provenance["catalog_sha256"] == digest((resource_root / "catalog.json").read_bytes()),
            "Provenance catalog digest mismatch")
    require(provenance["curation_sha256"] == digest((resource_root / "curation.tsv").read_bytes()),
            "Provenance curation digest mismatch")
    require([r["id"] for r in provenance["records"]] == list(IDS), "Provenance coverage differs")
    require(provenance_path.read_bytes() == canonical_bytes(provenance), "Provenance is not canonical")
    require(provenance["schema_version"] == "t8-visual-style-provenance/v1"
            and provenance["revision"] == REVISION
            and all(provenance[k] == 200 for k in ("entry_count", "color_count", "creator_count"))
            and provenance["limited_method_specificity_count"] == len(LIMITED_IDS),
            "Provenance contract differs")
    for record in provenance["records"]:
        require(set(record) == {"id", "files", "method_basis", "review_notes", "missing_accent_name_count",
                                "review_status"}, "Provenance record fields differ")
        require(record["review_status"] == "adapted_from_supplied_material_not_model_or_video_validated",
                "Invalid review status")
        require(record["review_notes"] == review_codes(record["id"]), "Provenance review differs")
        require(type(record["missing_accent_name_count"]) is int
                and 0 <= record["missing_accent_name_count"] <= 4, "Invalid source anomaly count")
        require(record["method_basis"] == ["palette.composition_keywords", "main.camera_features"]
                + (["video.camera_templates"] if record["id"] in LIMITED_IDS else []),
                "Method provenance differs")
        require([f["kind"] for f in record["files"]] == ["palette", "main", "video"],
                "Source file coverage differs")
        for file in record["files"]:
            require(set(file) == {"kind", "relative_path", "sha256"}
                    and type(file["sha256"]) is str and SHA.fullmatch(file["sha256"]),
                    "Invalid source hash record")
            path = Path(file["relative_path"])
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in file["relative_path"]
                    and len(path.parts) >= 3 and path.parts[1].startswith(record["id"] + "_"),
                    "Invalid relative source path")
            expected_tail = {"palette": "assets/color_palettes/palette.json", "main": "色卡主文档.md",
                             "video": "prompts/video_prompts.md"}[file["kind"]]
            require("/".join(path.parts[2:]) == expected_tail, "Source file kind/path mismatch")
    require([f["relative_path"] for f in provenance["source_entrypoints"]]
            == ["SKILL.md", "references/卷内速查表_001-200.md"], "Source entrypoint coverage differs")
    for file in provenance["source_entrypoints"]:
        require(set(file) == {"relative_path", "sha256"} and type(file["sha256"]) is str
                and SHA.fullmatch(file["sha256"]), "Invalid source entrypoint hash")
    return {"colors": 200, "creators": 200, "methods": sum(len(x["methods"]) for x in curated.values()),
            "limited_method_specificity": len(LIMITED_IDS)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="Read-only source pack; required to rebuild")
    parser.add_argument("--check", action="store_true", help="Verify without writing any files")
    args = parser.parse_args(argv)
    if args.source_root is None:
        if not args.check:
            parser.error("--source-root is required for rebuilding")
        print(json.dumps(verify_resources(), ensure_ascii=False))
        return 0
    files, provenance = build(args.source_root)
    expected = {RESOURCE_ROOT / rel: data for rel, data in files.items()}
    expected[PROVENANCE_PATH] = provenance
    if args.check:
        for path, data in expected.items():
            require(path.is_file() and path.read_bytes() == data, "Built output differs: " + path.name)
    else:
        for path, data in expected.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(json.dumps(verify_resources(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
