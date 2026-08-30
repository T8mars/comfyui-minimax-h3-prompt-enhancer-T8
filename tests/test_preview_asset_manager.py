import asyncio
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "t8_preview_asset_manager_test", ROOT / "preview_asset_manager.py"
)
manager_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manager_module
SPEC.loader.exec_module(manager_module)


def installed_contract():
    channel = json.loads((ROOT / "preview_assets" / "channel.json").read_text(encoding="utf-8"))
    allowed = {
        item["case_id"]: {"sha256": item["source_sha256"]}
        for item in channel["previews"]
    }
    return channel, allowed


class PreviewAssetManagerTests(unittest.TestCase):
    def test_download_transport_is_bounded_and_hash_verified(self):
        payload = b"preview-payload"

        class FakeResponse:
            status_code = 200
            url = "https://release-assets.githubusercontent.com/preview.bin"
            headers = {"Content-Length": str(len(payload))}

            @staticmethod
            def iter_content(chunk_size):
                self.assertEqual(chunk_size, 1024 * 1024)
                return iter((payload[:4], payload[4:]))

            @staticmethod
            def close():
                return None

        class FakeSession:
            def request(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

            @staticmethod
            def close():
                return None

        fake_session = FakeSession()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(manager_module.requests, "Session", return_value=fake_session),
        ):
            manager = manager_module.PreviewAssetManager(Path(temporary))
            result = manager._download_once(
                "https://github.com/T8mars/assets/releases/download/v1/preview.bin",
                len(payload),
                manager_module._sha256_bytes(payload),
                max_bytes=len(payload),
            )
        self.assertEqual(result, payload)
        self.assertEqual(fake_session.kwargs["method"], "GET")
        self.assertTrue(fake_session.kwargs["stream"])
        self.assertTrue(fake_session.kwargs["allow_redirects"])
        self.assertEqual(fake_session.kwargs["headers"]["Cache-Control"], "no-cache, no-store, max-age=0")

    def test_download_transport_rejects_unapproved_hosts_before_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(Path(temporary))
            with (
                patch.object(manager_module.requests, "Session") as session,
                self.assertRaises(manager_module.PreviewAssetError),
            ):
                manager._download_once(
                    "https://example.invalid/preview.zip",
                    None,
                    None,
                    max_bytes=1024,
                )
            session.assert_not_called()

    def test_bootstrap_channel_exactly_matches_installed_catalog_contract(self):
        channel, allowed = installed_contract()
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(
                Path(temporary), ROOT / "preview_assets" / "channel.json"
            )
            loaded = manager.channel(allowed)
            self.assertEqual(loaded["channel_version"], "2026.08.30.1")
            self.assertEqual(set(loaded["_preview_index"]), set(allowed))
            self.assertEqual(len(loaded["_shard_index"]), 16)
            self.assertEqual(channel["catalog_digest"], loaded["catalog_digest"])

    def test_channel_with_changed_source_identity_is_rejected(self):
        channel, allowed = installed_contract()
        altered = json.loads(json.dumps(channel))
        altered["previews"][0]["source_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(Path(temporary))
            with self.assertRaises(manager_module.PreviewAssetError):
                manager.validate_channel(altered, allowed)

    def test_cached_preview_is_content_addressed_and_hash_verified(self):
        channel, allowed = installed_contract()
        preview = channel["previews"][0]
        source = ROOT / "web" / "js" / "assets" / "t8-case-previews" / preview["file"]
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(
                Path(temporary), ROOT / "preview_assets" / "channel.json"
            )
            manager.files_root.mkdir(parents=True)
            target = manager.files_root / preview["file"]
            target.write_bytes(source.read_bytes())
            self.assertIsNotNone(manager.cached_path(preview["case_id"], allowed, verify_hash=True))
            target.write_bytes(b"GIF89a" + b"broken")
            self.assertIsNone(manager.cached_path(preview["case_id"], allowed, verify_hash=True))

    def test_shard_rejects_path_traversal_before_writing_cache(self):
        channel, allowed = installed_contract()
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(
                Path(temporary), ROOT / "preview_assets" / "channel.json"
            )
            loaded = manager.channel(allowed)
            shard = loaded["shards"][0]
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("shard.json", json.dumps({
                    "schema_version": "t8-preview-shard/v1", "shard_id": shard["id"],
                }))
                archive.writestr("../escape.gif", b"GIF89a")
            with self.assertRaises(manager_module.PreviewAssetError):
                manager._verify_shard(payload.getvalue(), shard, loaded)

    def test_update_modes_are_explicit_and_workflow_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = manager_module.PreviewAssetManager(Path(temporary))
            self.assertEqual(manager.settings()["mode"], "on_demand")
            self.assertEqual(manager.set_mode("manual")["mode"], "manual")
            self.assertEqual(manager.settings()["mode"], "manual")
            with self.assertRaises(manager_module.PreviewAssetError):
                manager.set_mode("unknown")


if __name__ == "__main__":
    unittest.main()
