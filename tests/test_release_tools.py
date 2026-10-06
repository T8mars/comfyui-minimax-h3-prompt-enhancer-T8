import importlib.util
import subprocess
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
    def test_hashed_evidence_keeps_original_bytes_in_git_on_both_autocrlf_settings(self):
        names = (
            "tudou_emotion_api_2026-10-04.json",
            "tudou_emotion_review_2026-10-04.json",
            "h3_vocal_protocol_api_2026-10-04.json",
            "h3_vocal_protocol_final_api_2026-10-04.json",
            "h3_hybrid_api_2026-10-06.json",
        )
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for name in names:
            self.assertIn("tests/fixtures/" + name + " -text", attributes)
        # Use a private disposable repository, not the user's checkout/index.
        with tempfile.TemporaryDirectory(prefix="t8-evidence-git-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / ".gitattributes").write_text(attributes, encoding="utf-8")
            (root / "tests/fixtures").mkdir(parents=True)
            payloads = {}
            for name in names:
                relative = "tests/fixtures/" + name
                payloads[relative] = (ROOT / relative).read_bytes()
                (root / relative).write_bytes(payloads[relative])
            for autocrlf in ("false", "true"):
                with self.subTest(autocrlf=autocrlf):
                    command = ["git", "-C", str(root), "-c", "core.autocrlf=" + autocrlf]
                    subprocess.run(command + ["add", "--renormalize", "--", ".gitattributes", *payloads],
                                   check=True, capture_output=True)
                    # --renormalize updates tracked files only; initialize the index too.
                    subprocess.run(command + ["add", "--", ".gitattributes", *payloads],
                                   check=True, capture_output=True)
                    for relative, original in payloads.items():
                        stored = subprocess.check_output(command + ["show", ":" + relative])
                        self.assertEqual(stored, original, relative)
                    subprocess.run(command + ["checkout-index", "-f", "--", *payloads],
                                   check=True, capture_output=True)
                    for relative, original in payloads.items():
                        self.assertEqual((root / relative).read_bytes(), original, relative)

    def test_repository_gate_scans_untracked_release_candidates(self):
        source = (ROOT / "tools" / "verify_repository.py").read_text(encoding="utf-8")
        self.assertIn('"-c", "-o", "--exclude-standard"', source)
        self.assertEqual(verify.MAX_BUNDLED_PREVIEW_BYTES, 90 * 1024 * 1024)
        self.assertIn(ROOT / "COMPATIBILITY.md", verify.tracked_files())

    def test_registry_archive_excludes_scanner_hostile_github_helpers(self):
        result = verify.verify_registry_package_hygiene(verify.tracked_files())
        self.assertGreater(result["registry_files"], 1000)
        self.assertGreater(result["registry_python_files"], 10)
        self.assertLess(result["registry_uncompressed_bytes"], 40 * 1024 * 1024)
        self.assertTrue((ROOT / "preview_assets" / "channel.json").is_file())
        runtime_shim = (ROOT / "local_qwen_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("importlib.import_module(", runtime_shim)

    def test_repository_secret_gate_includes_mjs_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "probe.mjs"
            module.write_text('const fixture = "' + 'sk-' + 'x' * 32 + '";', encoding="utf-8")
            with patch.object(verify, "ROOT", root), self.assertRaisesRegex(verify.VerificationError, 'probe.mjs'):
                verify.verify_secrets([module])

    def test_registry_gate_rejects_observed_semicolon_density_in_python_prose(self):
        files = verify.tracked_files()
        read_bytes = Path.read_bytes
        target = ROOT / "combat_camera.py"
        for count, rejected in ((4, False), (5, True), (9, True)):
            payload = ('instruction = "' + ' step;' * count + ' done"\n').encode()
            def read(path):
                return payload if path == target else read_bytes(path)
            with self.subTest(count=count), patch.object(Path, "read_bytes", read):
                if rejected:
                    with self.assertRaisesRegex(
                        verify.VerificationError, r"combat_camera\.py:dense_semicolon_line:1"
                    ):
                        verify.verify_registry_package_hygiene(files)
                else:
                    verify.verify_registry_package_hygiene(files)

    def test_registry_gate_allows_same_prose_split_across_python_literals(self):
        files = verify.tracked_files()
        read_bytes = Path.read_bytes
        target = ROOT / "combat_camera.py"
        payload = b'instruction = (\n' + b'    "step; "\n' * 9 + b'    "done"\n)\n'
        def read(path):
            return payload if path == target else read_bytes(path)
        with patch.object(Path, "read_bytes", read):
            verify.verify_registry_package_hygiene(files)

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

    def test_registry_gate_checks_observed_patterns_in_markdown(self):
        files = verify.tracked_files()
        read_bytes = Path.read_bytes
        for payload, label in (
            (b'```python\nmodel = os.environ["MODEL_DIR"]\n```', "environment_read"),
            (b'```python\nlyrics = Path("lyrics.txt").read_bytes()\n```', "direct_path_read_bytes"),
        ):
            def read(path):
                return payload if path == ROOT / "README.md" else read_bytes(path)
            with self.subTest(label=label), patch.object(Path, "read_bytes", read):
                with self.assertRaisesRegex(verify.VerificationError, "README.md:" + label):
                    verify.verify_registry_package_hygiene(files)

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
