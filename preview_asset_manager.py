from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests


CHANNEL_SCHEMA = "t8-remote-preview-channel/v1"
CATALOG_ID = "t8-unofficial-case-library-v2"
REMOTE_CHANNEL_URL = (
    "https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8-assets/"
    "releases/latest/download/channel.json"
)
BOOTSTRAP_CHANNEL = Path(__file__).resolve().parent / "preview_assets" / "channel.json"
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "raw.githubusercontent.com",
}
MAX_CHANNEL_BYTES = 2 * 1024 * 1024
MAX_SHARD_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 4 * 1024 * 1024
DOWNLOAD_ATTEMPTS = 4
VALID_MODES = {"on_demand", "full_auto", "manual"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
RELEASE_PATH_PREFIX = (
    "/T8mars/comfyui-minimax-h3-prompt-enhancer-T8-assets/releases/download/"
)


class PreviewAssetError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_catalog_digest(allowed: dict[str, dict[str, Any]]) -> str:
    rows = sorted(
        (
            {"case_id": case_id, "source_sha256": str(preview.get("sha256") or "")}
            for case_id, preview in allowed.items()
        ),
        key=lambda item: item["case_id"],
    )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _user_directory() -> Path:
    try:
        import folder_paths  # type: ignore

        getter = getattr(folder_paths, "get_user_directory", None)
        if callable(getter):
            value = getter()
            if value:
                return Path(value).resolve()
    except (ImportError, OSError, RuntimeError):
        pass
    return (Path(__file__).resolve().parent / ".user").resolve()


def default_cache_root() -> Path:
    return _user_directory() / "t8_prompt_enhancer" / "preview_assets"


def _safe_child(root: Path, child: Path) -> Path:
    resolved_root = root.resolve()
    resolved_child = child.resolve()
    try:
        resolved_child.relative_to(resolved_root)
    except ValueError as exc:
        raise PreviewAssetError("Preview cache path escapes its managed directory") from exc
    return resolved_child


def _bounded_positive_int(value: Any, maximum: int, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PreviewAssetError(f"{label} is not an integer") from exc
    if not 0 < parsed <= maximum:
        raise PreviewAssetError(f"{label} is outside its allowed range")
    return parsed


class PreviewAssetManager:
    def __init__(self, cache_root: Path | None = None, bootstrap_channel: Path | None = None) -> None:
        self.cache_root = (cache_root or default_cache_root()).resolve()
        self.bootstrap_channel = (bootstrap_channel or BOOTSTRAP_CHANNEL).resolve()
        self.settings_path = self.cache_root / "settings.json"
        self.channel_path = self.cache_root / "channel.json"
        self.files_root = self.cache_root / "files"
        self.download_root = self.cache_root / "downloads"
        self._shard_locks: dict[str, asyncio.Lock] = {}
        self._full_install_task: asyncio.Task[Any] | None = None
        self._channel_cache_key: tuple[Any, ...] | None = None
        self._channel_cache: dict[str, Any] | None = None

    def settings(self) -> dict[str, Any]:
        result: dict[str, Any] = {"mode": "on_demand"}
        if self.settings_path.is_file():
            try:
                payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("mode") in VALID_MODES:
                    result["mode"] = payload["mode"]
            except (OSError, json.JSONDecodeError):
                pass
        return result

    def set_mode(self, mode: str) -> dict[str, Any]:
        selected = str(mode or "").strip()
        if selected not in VALID_MODES:
            raise PreviewAssetError("Unsupported preview update mode")
        try:
            self.cache_root.mkdir(parents=True, exist_ok=True)
            temporary = self.settings_path.with_suffix(".json.part")
            temporary.write_text(json.dumps({"mode": selected}, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.settings_path)
        except OSError as exc:
            raise PreviewAssetError(f"Cannot save preview settings: {exc}") from exc
        return {"mode": selected}

    def _read_channel_file(self, path: Path, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise PreviewAssetError(f"Cannot read preview channel: {exc}") from exc
        if len(payload) > MAX_CHANNEL_BYTES:
            raise PreviewAssetError("Preview channel is too large")
        try:
            channel = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviewAssetError("Preview channel is not valid UTF-8 JSON") from exc
        return self.validate_channel(channel, allowed)

    def validate_channel(
        self,
        channel: Any,
        allowed: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        previews = channel.get("previews") if isinstance(channel, dict) else None
        shards = channel.get("shards") if isinstance(channel, dict) else None
        if (
            not isinstance(channel, dict)
            or channel.get("schema_version") != CHANNEL_SCHEMA
            or channel.get("catalog_id") != CATALOG_ID
            or channel.get("human_preview_only") is not True
            or not isinstance(previews, list)
            or not isinstance(shards, list)
            or channel.get("preview_count") != len(previews)
            or channel.get("catalog_digest") != _canonical_catalog_digest(allowed)
        ):
            raise PreviewAssetError("Preview channel is incompatible with the installed template catalog")

        shard_index: dict[str, dict[str, Any]] = {}
        for shard in shards:
            if not isinstance(shard, dict):
                raise PreviewAssetError("Preview shard metadata is invalid")
            shard_id = str(shard.get("id") or "")
            url = str(shard.get("url") or "")
            parsed_url = urlsplit(url)
            if (
                not shard_id.startswith("shard-")
                or shard_id in shard_index
                or parsed_url.scheme != "https"
                or parsed_url.hostname != "github.com"
                or not parsed_url.path.startswith(RELEASE_PATH_PREFIX)
                or SHA256_RE.fullmatch(str(shard.get("sha256") or "")) is None
            ):
                raise PreviewAssetError("Preview shard identity, URL, or integrity metadata is invalid")
            _bounded_positive_int(shard.get("bytes"), MAX_SHARD_BYTES, "Preview shard size")
            shard_index[shard_id] = shard

        preview_index: dict[str, dict[str, Any]] = {}
        for preview in previews:
            case_id = str(preview.get("case_id") or "") if isinstance(preview, dict) else ""
            expected = allowed.get(case_id)
            file_sha = str(preview.get("file_sha256") or "") if isinstance(preview, dict) else ""
            if (
                not case_id
                or case_id in preview_index
                or expected is None
                or preview.get("source_sha256") != expected.get("sha256")
                or preview.get("human_preview_only") is not True
                or preview.get("shard") not in shard_index
                or SHA256_RE.fullmatch(file_sha) is None
                or preview.get("file") != f"{file_sha}.gif"
            ):
                raise PreviewAssetError(f"Preview channel entry is incompatible: {case_id or '<missing>'}")
            _bounded_positive_int(preview.get("bytes"), MAX_GIF_BYTES, "Preview GIF size")
            preview_index[case_id] = preview
        if set(preview_index) != set(allowed):
            raise PreviewAssetError("Preview channel does not exactly cover the installed template catalog")
        return {**channel, "_preview_index": preview_index, "_shard_index": shard_index}

    def channel(self, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        allowed_digest = _canonical_catalog_digest(allowed)
        for path in (self.channel_path, self.bootstrap_channel):
            if path.is_file():
                stat = path.stat()
                cache_key = (str(path), stat.st_mtime_ns, stat.st_size, allowed_digest)
                if self._channel_cache_key == cache_key and self._channel_cache is not None:
                    return self._channel_cache
                try:
                    channel = self._read_channel_file(path, allowed)
                except PreviewAssetError:
                    continue
                self._channel_cache_key = cache_key
                self._channel_cache = channel
                return channel
        raise PreviewAssetError("No compatible preview asset channel is installed")

    def cached_path(
        self,
        case_id: str,
        allowed: dict[str, dict[str, Any]],
        *,
        verify_hash: bool,
    ) -> tuple[Path, dict[str, Any]] | None:
        try:
            preview = self.channel(allowed)["_preview_index"][case_id]
        except (PreviewAssetError, KeyError):
            return None
        path = _safe_child(self.files_root, self.files_root / str(preview["file"]))
        if not path.is_file() or path.stat().st_size != int(preview["bytes"]):
            return None
        try:
            with path.open("rb") as handle:
                if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
                    return None
        except OSError:
            return None
        if verify_hash and _sha256_path(path) != preview["file_sha256"]:
            return None
        return path, {**preview, "_template_kind": "cache", "_path": path}

    def availability(self, case_id: str, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        cached = self.cached_path(case_id, allowed, verify_hash=False)
        try:
            preview = self.channel(allowed)["_preview_index"].get(case_id)
        except PreviewAssetError:
            preview = None
        return {
            "cached": cached is not None,
            "downloadable": preview is not None,
            "ensure_url": f"/t8-prompt-enhancer/preview-assets/ensure/{case_id}" if preview else "",
        }

    def status(self, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        try:
            channel = self.channel(allowed)
            version = str(channel.get("channel_version") or "")
            downloadable = len(channel["_preview_index"])
        except PreviewAssetError:
            channel = None
            version = ""
            downloadable = 0
        cached_count = 0
        cached_bytes = 0
        if channel:
            for case_id in channel["_preview_index"]:
                resolved = self.cached_path(case_id, allowed, verify_hash=False)
                if resolved:
                    cached_count += 1
                    cached_bytes += resolved[0].stat().st_size
        return {
            "mode": self.settings()["mode"],
            "channel_version": version,
            "downloadable_count": downloadable,
            "cached_count": cached_count,
            "cached_bytes": cached_bytes,
            "cache_root": str(self.cache_root),
            "full_install_running": bool(self._full_install_task and not self._full_install_task.done()),
            "policy": "Human UI previews only; never sent to the LLM or used as model reference media.",
        }

    def _download_once(
        self,
        url: str,
        expected_bytes: int | None,
        expected_sha256: str | None,
        *,
        max_bytes: int,
    ) -> bytes:
        parsed_url = urlsplit(url)
        if (
            parsed_url.scheme != "https"
            or (parsed_url.hostname or "").casefold() not in ALLOWED_DOWNLOAD_HOSTS
        ):
            raise PreviewAssetError("Preview download URL is not an approved HTTPS host")
        session = requests.Session()
        response = None
        try:
            response = session.request(
                method="GET",
                url=url,
                allow_redirects=True,
                stream=True,
                timeout=(30, 60),
                headers={
                    "User-Agent": "T8-ComfyUI-Preview-Assets/1",
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                },
            )
            host = (urlsplit(str(response.url)).hostname or "").casefold()
            if response.status_code != 200:
                raise PreviewAssetError(f"Preview download returned HTTP {response.status_code}")
            if host not in ALLOWED_DOWNLOAD_HOSTS:
                raise PreviewAssetError("Preview download redirected to an unapproved host")
            declared_length = str(response.headers.get("Content-Length") or "").strip()
            if declared_length.isdigit() and int(declared_length) > max_bytes:
                raise PreviewAssetError("Preview download exceeds its maximum size")
            buffer = bytearray()
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    raise PreviewAssetError("Preview download exceeds its maximum size")
            payload = bytes(buffer)
        finally:
            if response is not None:
                response.close()
            session.close()
        if len(payload) > max_bytes or (expected_bytes is not None and len(payload) != expected_bytes):
            raise PreviewAssetError("Preview shard size does not match its channel metadata")
        if expected_sha256 is not None and _sha256_bytes(payload) != expected_sha256:
            raise PreviewAssetError("Preview shard SHA-256 verification failed")
        return payload

    async def _download(
        self,
        url: str,
        expected_bytes: int | None,
        expected_sha256: str | None,
        *,
        max_bytes: int,
    ) -> bytes:
        last_error: Exception | None = None
        for attempt in range(DOWNLOAD_ATTEMPTS):
            try:
                return await asyncio.to_thread(
                    self._download_once,
                    url,
                    expected_bytes,
                    expected_sha256,
                    max_bytes=max_bytes,
                )
            except (requests.RequestException, asyncio.TimeoutError, PreviewAssetError) as exc:
                last_error = exc
                if attempt + 1 < DOWNLOAD_ATTEMPTS:
                    await asyncio.sleep(min(1.5 * (2**attempt), 8.0))
        raise PreviewAssetError(f"Unable to download preview shard after {DOWNLOAD_ATTEMPTS} attempts: {last_error}")

    def _verify_shard(self, payload: bytes, shard: dict[str, Any], channel: dict[str, Any]) -> dict[str, bytes]:
        expected = {
            item["file"]: item
            for item in channel["_preview_index"].values()
            if item["shard"] == shard["id"]
        }
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                members = archive.infolist()
                names = {member.filename for member in members}
                if len(names) != len(members) or names != {"shard.json", *expected.keys()}:
                    raise PreviewAssetError("Preview shard contains unexpected or missing files")
                if sum(member.file_size for member in members) > MAX_SHARD_BYTES:
                    raise PreviewAssetError("Preview shard expands beyond its maximum size")
                extracted: dict[str, bytes] = {}
                for member in members:
                    if member.is_dir() or Path(member.filename).name != member.filename:
                        raise PreviewAssetError("Preview shard contains an unsafe path")
                    if (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise PreviewAssetError("Preview shard contains a symbolic link")
                    if member.file_size > (MAX_CHANNEL_BYTES if member.filename == "shard.json" else MAX_GIF_BYTES):
                        raise PreviewAssetError("Preview shard member is too large")
                    data = archive.read(member)
                    if member.filename == "shard.json":
                        metadata = json.loads(data.decode("utf-8"))
                        if metadata.get("schema_version") != "t8-preview-shard/v1" or metadata.get("shard_id") != shard["id"]:
                            raise PreviewAssetError("Preview shard manifest identity is invalid")
                        continue
                    record = expected[member.filename]
                    if (
                        len(data) != int(record["bytes"])
                        or data[:6] not in {b"GIF87a", b"GIF89a"}
                        or _sha256_bytes(data) != record["file_sha256"]
                    ):
                        raise PreviewAssetError("Preview GIF integrity verification failed")
                    extracted[member.filename] = data
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
            raise PreviewAssetError("Preview shard archive is invalid") from exc
        return extracted

    async def ensure(self, case_id: str, allowed: dict[str, dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
        existing = self.cached_path(case_id, allowed, verify_hash=True)
        if existing:
            return existing
        channel = self.channel(allowed)
        preview = channel["_preview_index"].get(case_id)
        if not preview:
            raise PreviewAssetError("This preview is not available in the compatible asset channel")
        shard = channel["_shard_index"][preview["shard"]]
        lock = self._shard_locks.setdefault(shard["id"], asyncio.Lock())
        async with lock:
            existing = self.cached_path(case_id, allowed, verify_hash=True)
            if existing:
                return existing
            payload = await self._download(
                shard["url"], int(shard["bytes"]), shard["sha256"], max_bytes=MAX_SHARD_BYTES
            )
            extracted = self._verify_shard(payload, shard, channel)
            try:
                self.files_root.mkdir(parents=True, exist_ok=True)
                for filename, data in extracted.items():
                    destination = _safe_child(self.files_root, self.files_root / filename)
                    with tempfile.NamedTemporaryFile(
                        mode="wb", dir=self.files_root, prefix=".preview-", suffix=".part", delete=False
                    ) as handle:
                        handle.write(data)
                        temporary = Path(handle.name)
                    os.replace(temporary, destination)
            except OSError as exc:
                raise PreviewAssetError(f"Cannot write the preview cache: {exc}") from exc
        resolved = self.cached_path(case_id, allowed, verify_hash=True)
        if not resolved:
            raise PreviewAssetError("Preview installation did not produce the requested GIF")
        return resolved

    async def check_remote(self, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        payload = await self._download(
            REMOTE_CHANNEL_URL, None, None, max_bytes=MAX_CHANNEL_BYTES
        )
        return self._install_channel_payload(payload, allowed)

    def _install_channel_payload(self, payload: bytes, allowed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if len(payload) > MAX_CHANNEL_BYTES:
            raise PreviewAssetError("Remote preview channel is too large")
        try:
            channel = self.validate_channel(json.loads(payload.decode("utf-8")), allowed)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviewAssetError("Remote preview channel is invalid") from exc
        try:
            self.cache_root.mkdir(parents=True, exist_ok=True)
            temporary = self.channel_path.with_suffix(".json.part")
            temporary.write_bytes(payload)
            os.replace(temporary, self.channel_path)
        except OSError as exc:
            raise PreviewAssetError(f"Cannot save the preview update channel: {exc}") from exc
        self._channel_cache_key = None
        self._channel_cache = None
        return channel

    async def install_all(self, allowed: dict[str, dict[str, Any]], *, verify_existing: bool = False) -> dict[str, Any]:
        channel = self.channel(allowed)
        installed = 0
        for case_id in channel["_preview_index"]:
            if verify_existing or not self.cached_path(case_id, allowed, verify_hash=False):
                await self.ensure(case_id, allowed)
                installed += 1
        return {**self.status(allowed), "installed_or_verified": installed}

    def schedule_full_install(self, allowed: dict[str, dict[str, Any]]) -> None:
        if self.settings()["mode"] != "full_auto":
            return
        if self._full_install_task and not self._full_install_task.done():
            return
        self._full_install_task = asyncio.create_task(self.install_all(allowed))
        self._full_install_task.add_done_callback(
            lambda task: task.exception() if not task.cancelled() else None
        )

    def clear(self) -> dict[str, Any]:
        try:
            if self.files_root.is_dir():
                _safe_child(self.cache_root, self.files_root)
                shutil.rmtree(self.files_root)
            if self.download_root.is_dir():
                _safe_child(self.cache_root, self.download_root)
                shutil.rmtree(self.download_root)
        except OSError as exc:
            raise PreviewAssetError(f"Cannot clear the preview cache: {exc}") from exc
        return {"cleared": True}


_MANAGER: PreviewAssetManager | None = None


def preview_asset_manager() -> PreviewAssetManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = PreviewAssetManager()
    return _MANAGER


__all__ = [
    "BOOTSTRAP_CHANNEL",
    "PreviewAssetError",
    "PreviewAssetManager",
    "default_cache_root",
    "preview_asset_manager",
]
