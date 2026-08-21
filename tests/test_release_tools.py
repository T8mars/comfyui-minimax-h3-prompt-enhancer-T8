import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("t8_release_tool", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)
VERIFY_SPEC = importlib.util.spec_from_file_location("t8_verify_repository", ROOT / "tools" / "verify_repository.py")
verify = importlib.util.module_from_spec(VERIFY_SPEC)
sys.modules[VERIFY_SPEC.name] = verify
VERIFY_SPEC.loader.exec_module(verify)


class ReleaseToolTests(unittest.TestCase):
    def test_repository_gate_scans_untracked_release_candidates(self):
        source = (ROOT / "tools" / "verify_repository.py").read_text(encoding="utf-8")
        self.assertIn('"-c", "-o", "--exclude-standard"', source)
        self.assertEqual(verify.MAX_BUNDLED_PREVIEW_BYTES, 180 * 1024 * 1024)
        self.assertIn(ROOT / "COMPATIBILITY.md", verify.tracked_files())

    def test_repository_gate_parses_toml_and_yaml(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good_toml = root / "good.toml"
            good_yaml = root / "good.yml"
            bad_yaml = root / "bad.yml"
            good_toml.write_text('[project]\nversion = "1.1.0"\n', encoding="utf-8")
            good_yaml.write_text("jobs:\n  verify:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
            bad_yaml.write_text("jobs: [unterminated\n", encoding="utf-8")
            with patch.object(verify, "ROOT", root):
                verify.verify_toml_and_yaml([good_toml, good_yaml])
                with self.assertRaises(verify.VerificationError):
                    verify.verify_toml_and_yaml([bad_yaml])

    def test_semver_parse_order_and_bumps(self):
        value = release.Version.parse("1.2.3")
        self.assertEqual(str(value.bump("patch")), "1.2.4")
        self.assertEqual(str(value.bump("minor")), "1.3.0")
        self.assertEqual(str(value.bump("major")), "2.0.0")
        self.assertGreater(release.Version.parse("1.10.0"), release.Version.parse("1.9.9"))

    def test_invalid_semver_is_rejected(self):
        for value in ("1.0", "v1.0.0", "1.0.0.0", "01.0.0"):
            with self.subTest(value=value), self.assertRaises(release.ReleaseError):
                release.Version.parse(value)

    def test_bump_uses_newest_origin_or_registry_and_warns_for_changelog(self):
        with tempfile.TemporaryDirectory() as temporary:
            pyproject = Path(temporary) / "pyproject.toml"
            changelog = Path(temporary) / "CHANGELOG.md"
            pyproject.write_text('[project]\nversion = "1.0.2"\n', encoding="utf-8")
            changelog.write_text("# Changelog\n", encoding="utf-8")
            with (
                patch.object(release, "PYPROJECT", pyproject),
                patch.object(release, "CHANGELOG", changelog),
                patch.object(release, "origin_version", return_value=release.Version.parse("1.0.3")),
                patch.object(release, "registry_version", return_value=release.Version.parse("1.1.0")),
            ):
                target = release.bump("minor")
            self.assertEqual(str(target), "1.2.0")
            self.assertIn('version = "1.2.0"', pyproject.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
