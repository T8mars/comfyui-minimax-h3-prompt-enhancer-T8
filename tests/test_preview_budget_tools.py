import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_preview_bundler_test", ROOT / "tools" / "bundle_t8_case_previews.py")
bundler = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bundler
SPEC.loader.exec_module(bundler)
GIF = b"GIF89a" + b"\x00" * 40


class FakeCompleted:
    returncode = 0
    stderr = ""


class PreviewBudgetToolTests(unittest.TestCase):
    def test_identical_encoded_previews_share_one_content_addressed_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dirs = [root / "case-a", root / "case-b"]
            for directory in source_dirs:
                directory.mkdir()
                (directory / "preview.gif").write_bytes(GIF)
            digest = hashlib.sha256(GIF).hexdigest()
            library = root / "library.json"
            community = root / "community.json"
            catalog = root / "catalog.json"
            output = root / "output"
            library.write_text(json.dumps({
                "schema_version": bundler.CASE_LIBRARY_SCHEMA,
                "records": [
                    {
                        "case_id": f"case-{name}",
                        "case_path": str(directory),
                        "preview": {"path": "preview.gif", "sha256": digest},
                    }
                    for name, directory in zip(("a", "b"), source_dirs)
                ],
            }), encoding="utf-8")
            community.write_text(json.dumps({
                "schema_version": bundler.COMMUNITY_LIBRARY_SCHEMA,
                "records": [],
            }), encoding="utf-8")
            catalog.write_text(json.dumps({
                "schema_version": bundler.CATALOG_SCHEMA,
                "templates": [
                    {"previews": [{"case_id": "case-a", "sha256": digest}]},
                    {"previews": [{"case_id": "case-b", "sha256": digest}]},
                ],
            }), encoding="utf-8")

            def fake_ffmpeg(command, **_kwargs):
                Path(command[-1]).write_bytes(GIF)
                return FakeCompleted()

            with patch.object(bundler, "_resolve_executable", return_value="ffmpeg"), patch.object(
                bundler.subprocess, "run", side_effect=fake_ffmpeg,
            ):
                manifest = bundler.bundle_previews(
                    library, community, catalog, output, "ffmpeg", fps=3, max_width=224, colors=40,
                )
            self.assertEqual(manifest["preview_count"], 2)
            self.assertEqual(manifest["asset_count"], 1)
            self.assertEqual(manifest["dedup_references"], 1)
            self.assertEqual(len(list(output.glob("*.gif"))), 1)
            self.assertEqual({item["file"] for item in manifest["previews"]}, {f"{digest}.gif"})
            self.assertIn("2 preview references", (output / "NOTICE.md").read_text(encoding="utf-8"))

    def test_preview_budget_thresholds_are_ordered_and_new_files_are_capped(self):
        self.assertLess(bundler.PREVIEW_WARNING_BYTES, bundler.PREVIEW_CONFIRM_BYTES)
        self.assertLess(bundler.PREVIEW_CONFIRM_BYTES, bundler.PREVIEW_HARD_LIMIT_BYTES)
        self.assertEqual(bundler.NEW_PREVIEW_FILE_LIMIT_BYTES, 2 * 1024 * 1024)

    def test_unchanged_source_reuses_the_verified_existing_bundle_without_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_root = root / "case"
            case_root.mkdir()
            source = case_root / "preview.gif"
            source.write_bytes(GIF)
            source_hash = hashlib.sha256(GIF).hexdigest()
            existing = root / "existing"
            existing.mkdir()
            bundled = GIF + b"encoded"
            bundled_hash = hashlib.sha256(bundled).hexdigest()
            filename = f"{bundled_hash}.gif"
            (existing / filename).write_bytes(bundled)
            (existing / "manifest.json").write_text(json.dumps({
                "schema_version": bundler.BUNDLE_SCHEMA,
                "previews": [{
                    "case_id": "case-a",
                    "file": filename,
                    "source_sha256": source_hash,
                    "sha256": bundled_hash,
                    "bytes": len(bundled),
                    "human_preview_only": True,
                }],
            }), encoding="utf-8")
            library = root / "library.json"
            community = root / "community.json"
            catalog = root / "catalog.json"
            output = root / "output"
            library.write_text(json.dumps({
                "schema_version": bundler.CASE_LIBRARY_SCHEMA,
                "records": [{
                    "case_id": "case-a",
                    "case_path": str(case_root),
                    "preview": {"path": "preview.gif", "sha256": source_hash},
                }],
            }), encoding="utf-8")
            community.write_text(json.dumps({
                "schema_version": bundler.COMMUNITY_LIBRARY_SCHEMA,
                "records": [],
            }), encoding="utf-8")
            catalog.write_text(json.dumps({
                "schema_version": bundler.CATALOG_SCHEMA,
                "templates": [{"previews": [{"case_id": "case-a", "sha256": source_hash}]}],
            }), encoding="utf-8")

            with patch.object(bundler, "_resolve_executable", return_value="ffmpeg"), patch.object(
                bundler.subprocess, "run",
            ) as ffmpeg:
                manifest = bundler.bundle_previews(
                    library,
                    community,
                    catalog,
                    output,
                    "ffmpeg",
                    fps=3,
                    max_width=224,
                    colors=40,
                    existing_bundle=existing,
                )
            ffmpeg.assert_not_called()
            self.assertEqual(manifest["preview_count"], 1)
            self.assertEqual(manifest["asset_count"], 1)
            self.assertEqual((output / filename).read_bytes(), bundled)
            self.assertTrue((output / "NOTICE.md").is_file())


if __name__ == "__main__":
    unittest.main()
