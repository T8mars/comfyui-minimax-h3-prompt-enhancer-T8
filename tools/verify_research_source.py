from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen


LOCK_SCHEMA = "t8-research-source-lock/v1"
DEFAULT_LOCK = Path(__file__).resolve().parents[1] / "research_sources" / "h3-storyboard-skill.lock.json"


class SourceVerificationError(ValueError):
    pass


def load_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SourceVerificationError("source lock root must be an object")
    return payload


def validate_lock(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != LOCK_SCHEMA:
        errors.append("unsupported schema_version")
    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
        source = {}
    repository = str(source.get("repository", ""))
    if repository != "https://github.com/phileiny/h3-storyboard-skill":
        errors.append("unexpected source repository")
    commit = str(source.get("commit", ""))
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        errors.append("source commit must be a full lowercase SHA-1")
    if source.get("license") != "MIT":
        errors.append("source license must be recorded as MIT")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, item in enumerate(files):
        prefix = f"files[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        path = str(item.get("path", ""))
        if not path or path.startswith(("/", "\\")) or ".." in Path(path).parts or path in seen:
            errors.append(f"{prefix}.path is unsafe or duplicated")
        seen.add(path)
        if not isinstance(item.get("bytes"), int) or int(item.get("bytes", -1)) < 0:
            errors.append(f"{prefix}.bytes is invalid")
        digest = str(item.get("sha256", ""))
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            errors.append(f"{prefix}.sha256 is invalid")
    if not isinstance(payload.get("limitations"), list) or not payload.get("limitations"):
        errors.append("limitations must be recorded")
    if not isinstance(payload.get("prohibited_overclaims"), list) or not payload.get("prohibited_overclaims"):
        errors.append("prohibited_overclaims must be recorded")
    return errors


def _raw_url(repository: str, commit: str, path: str) -> str:
    owner_repo = repository.removeprefix("https://github.com/").strip("/")
    encoded_path = "/".join(quote(part, safe="") for part in Path(path).as_posix().split("/"))
    return f"https://raw.githubusercontent.com/{owner_repo}/{commit}/{encoded_path}"


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "T8-research-source-verifier", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def verify_remote(
    payload: Mapping[str, Any],
    *,
    fetcher: Callable[[str], bytes] = fetch_bytes,
) -> list[dict[str, Any]]:
    errors = validate_lock(payload)
    if errors:
        raise SourceVerificationError("; ".join(errors))
    source = payload["source"]
    results: list[dict[str, Any]] = []
    for item in payload["files"]:
        url = _raw_url(str(source["repository"]), str(source["commit"]), str(item["path"]))
        content = fetcher(url)
        digest = hashlib.sha256(content).hexdigest()
        byte_count = len(content)
        if byte_count != int(item["bytes"]) or digest != str(item["sha256"]):
            raise SourceVerificationError(
                f"source mismatch for {item['path']}: bytes={byte_count}, sha256={digest}"
            )
        results.append({"path": item["path"], "bytes": byte_count, "sha256": digest, "verified": True})
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or re-fetch the pinned community research source.")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--offline", action="store_true", help="Validate lock structure without making network requests.")
    args = parser.parse_args(argv)
    payload = load_lock(args.lock)
    errors = validate_lock(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.offline:
        print(json.dumps({"valid": True, "remote_verified": False, "files": len(payload["files"])}, ensure_ascii=False))
        return 0
    results = verify_remote(payload)
    print(json.dumps({"valid": True, "remote_verified": True, "files": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
