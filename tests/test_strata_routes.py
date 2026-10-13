"""Read-only status over real isolated HTTP; never load or generate a model."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

from test_strata_provider import http_fixture, status, strata


class StrataProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.package_name = "_t8_strata_probe_tests"
        package = types.ModuleType(cls.package_name)
        package.__path__ = [str(root)]
        sys.modules[cls.package_name] = package
        sys.modules[cls.package_name + ".strata_provider"] = strata
        spec = importlib.util.spec_from_file_location(cls.package_name + ".strata_routes", root / "strata_routes.py")
        cls.routes = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.routes
        spec.loader.exec_module(cls.routes)

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules):
            if name == cls.package_name or name.startswith(cls.package_name + "."):
                del sys.modules[name]

    def test_unloaded_service_is_connected_but_requires_manual_loading(self):
        value = status(); value.update(loaded=False, auto_load=False)
        with http_fixture(status=value) as (url, seen):
            result = self.routes.probe_strata({"strata_url": url})
        self.assertTrue(result["connected"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["auto_load"])
        self.assertFalse(result["loaded"])
        self.assertEqual(result["generation_requests"], 0)
        self.assertEqual([item[:2] for item in seen], [("GET", "/v1/status")])

    def test_probe_preserves_autoload_and_vision_availability_without_loading(self):
        value = status(); value["loaded"] = False; value["vision"]["available"] = False
        with http_fixture(status=value) as (url, seen):
            result = self.routes.probe_strata({"strata_url": url})
        self.assertTrue(result["ready"])
        self.assertTrue(result["auto_load"])
        self.assertFalse(result["vision_available"])
        self.assertEqual([item[0] for item in seen], ["GET"])

    def test_probe_rejects_wrong_service_and_redacts_untrusted_model(self):
        with http_fixture(status={**status(), "service": "other"}) as (url, seen):
            with self.assertRaises(strata.StrataProviderError):
                self.routes.probe_strata({"strata_url": url})
            self.assertEqual(len(seen), 1)
        with http_fixture(status=status("private model name")) as (url, seen):
            result = self.routes.probe_strata({"strata_url": url})
            self.assertEqual(result["model"], "[redacted-model]")
            self.assertEqual(len(seen), 1)


if __name__ == "__main__":
    unittest.main()
