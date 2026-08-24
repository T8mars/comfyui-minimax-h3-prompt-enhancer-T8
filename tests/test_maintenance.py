import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


drift = load_tool("t8_check_upstream_skills", "check_upstream_skills.py")


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, shas, compare_statuses=("behind",)):
        self.shas = iter(shas)
        self.compare_statuses = iter(compare_statuses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/compare/" in url:
            return FakeResponse({"status": next(self.compare_statuses)})
        return FakeResponse([{"sha": next(self.shas)}])


class MaintenanceTests(unittest.TestCase):
    def test_upstream_drift_uses_path_scoped_commits(self):
        with tempfile.TemporaryDirectory() as temporary:
            sources = drift.SOURCES[:2]
            manifests = []
            for index, source in enumerate(sources):
                path = Path(temporary) / f"source-{index}.json"
                path.write_text(json.dumps({source["commit_field"]: f"sha-{index}"}), encoding="utf-8")
                manifests.append({**source, "manifest": path})
            session = FakeSession(["sha-0", "new-sha"])
            with patch.object(drift, "SOURCES", tuple(manifests)):
                result = drift.check_sources(session)
        self.assertEqual([item["drift"] for item in result], [False, True])
        self.assertEqual(len(session.calls), 3)
        commit_calls = [call for call in session.calls if "/commits" in call[0]]
        self.assertTrue(all(call[1]["params"]["path"].startswith("skills/") for call in commit_calls))

    def test_reviewed_descendant_snapshot_does_not_report_false_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = drift.SOURCES[0]
            manifest = Path(temporary) / "source.json"
            manifest.write_text(json.dumps({source["commit_field"]: "reviewed-descendant"}), encoding="utf-8")
            session = FakeSession(["latest-path-change"], compare_statuses=("ahead",))
            with patch.object(drift, "SOURCES", ({**source, "manifest": manifest},)):
                result = drift.check_sources(session)
        self.assertFalse(result[0]["drift"])
        self.assertTrue(result[0]["pinned_contains_upstream"])

    def test_real_skill_manifests_expose_configured_commit_fields(self):
        self.assertEqual(len(drift.SOURCES), 10)
        self.assertEqual(
            {source["path"].removeprefix("skills/") for source in drift.SOURCES[2:]},
            set(drift.CREATIVE_H3_SKILLS),
        )
        for source in drift.SOURCES:
            with self.subTest(source=source["name"]):
                manifest = json.loads(source["manifest"].read_text(encoding="utf-8"))
                value = manifest[source["commit_field"]]
                self.assertRegex(value, r"^[0-9a-f]{40}$")

    def test_native_workflows_have_same_name_thumbnails(self):
        workflows = sorted((ROOT / "example_workflows").glob("*.json"))
        self.assertEqual(len(workflows), 4)
        for workflow in workflows:
            with self.subTest(workflow=workflow.name):
                self.assertTrue(workflow.with_suffix(".jpg").is_file())
                source = workflow.read_text(encoding="utf-8")
                self.assertNotRegex(source, r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")

    def test_locales_and_node_docs_cover_all_v3_nodes(self):
        node_ids = {
            "MiniMaxH3PromptEnhancerT8",
            "Seedance20PromptEnhancerT8",
            "MiniMaxMusic3PromptEnhancerT8",
        }
        for locale in ("en", "zh"):
            data = json.loads((ROOT / "locales" / locale / "nodeDefs.json").read_text(encoding="utf-8"))
            self.assertEqual(set(data), node_ids)
        for node_id in node_ids:
            for language in ("en", "zh"):
                self.assertTrue((ROOT / "web" / "js" / "docs" / node_id / f"{language}.md").is_file())


if __name__ == "__main__":
    unittest.main()
