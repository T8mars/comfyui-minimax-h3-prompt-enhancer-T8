from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

try:
    from .environment_defaults import optional_environment_value
except ImportError:
    try:
        from environment_defaults import optional_environment_value
    except ImportError:
        def optional_environment_value(_name: str) -> str:
            return ""


ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_SECRET_LENGTH = 4096
STORE_SCHEMA = "t8-local-credential-store/v1"
_LOCK = threading.RLock()


class CredentialStoreError(RuntimeError):
    pass


def _user_root() -> Path:
    override = optional_environment_value("T8_PROMPT_ENHANCER_USER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    try:
        import folder_paths

        return Path(folder_paths.get_user_directory()).resolve()
    except (ImportError, AttributeError):
        return (Path(__file__).resolve().parent / ".user").resolve()


def credential_store_path() -> Path:
    root = _user_root()
    candidate = root / "t8-prompt-enhancer"
    if candidate.exists() and candidate.is_symlink():
        raise CredentialStoreError("Credential directory cannot be a symbolic link.")
    store_dir = candidate.resolve()
    try:
        store_dir.relative_to(root)
    except ValueError as exc:
        raise CredentialStoreError("Credential directory must remain inside the ComfyUI user directory.") from exc
    return store_dir / "credentials.json"


def _validate_alias(alias: Any) -> str:
    value = str(alias or "").strip()
    if not ALIAS_RE.fullmatch(value):
        raise CredentialStoreError("Credential alias must be 1-64 letters, digits, dots, underscores, or hyphens.")
    return value


def _validate_secret(secret: Any) -> str:
    value = str(secret or "").strip()
    if not value or len(value) > MAX_SECRET_LENGTH or "\n" in value or "\r" in value:
        raise CredentialStoreError("Credential value must be one non-empty line of at most 4096 characters.")
    return value


def _safe_store_file() -> Path:
    path = credential_store_path()
    directory = path.parent
    if directory.exists() and directory.is_symlink():
        raise CredentialStoreError("Credential directory cannot be a symbolic link.")
    directory.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise CredentialStoreError("Credential file cannot be a symbolic link.")
    return path


def _read_store() -> dict[str, str]:
    path = _safe_store_file()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CredentialStoreError("Local credential store is unreadable or invalid.") from exc
    if payload.get("schema_version") != STORE_SCHEMA or not isinstance(payload.get("credentials"), dict):
        raise CredentialStoreError("Local credential store schema is unsupported.")
    result: dict[str, str] = {}
    for alias, secret in payload["credentials"].items():
        result[_validate_alias(alias)] = _validate_secret(secret)
    return result


def _write_store(values: dict[str, str]) -> None:
    path = _safe_store_file()
    payload = {
        "schema_version": STORE_SCHEMA,
        "credentials": {key: values[key] for key in sorted(values, key=str.casefold)},
    }
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".credentials-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows ACLs are inherited from the ComfyUI user directory.
            pass
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def list_credential_aliases() -> list[str]:
    with _LOCK:
        return sorted(_read_store(), key=str.casefold)


def get_credential(alias: Any) -> str:
    value = _validate_alias(alias)
    with _LOCK:
        secret = _read_store().get(value, "")
    if not secret:
        raise CredentialStoreError(f"Credential alias is not configured: {value}")
    return secret


def save_credential(alias: Any, secret: Any) -> None:
    name = _validate_alias(alias)
    value = _validate_secret(secret)
    with _LOCK:
        store = _read_store()
        store[name] = value
        _write_store(store)


def delete_credential(alias: Any) -> bool:
    name = _validate_alias(alias)
    with _LOCK:
        store = _read_store()
        existed = name in store
        if existed:
            del store[name]
            _write_store(store)
    return existed


__all__ = [
    "CredentialStoreError",
    "credential_store_path",
    "delete_credential",
    "get_credential",
    "list_credential_aliases",
    "save_credential",
]
