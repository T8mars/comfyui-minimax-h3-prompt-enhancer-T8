from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
REGISTRY_URL = "https://api.comfy.org/nodes/minimax-h3-seedance-music3-prompt-enhancer-t8"
VERSION_RE = re.compile(r'(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"\s*$')


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", str(value).strip())
        if not match:
            raise ReleaseError(f"Invalid semantic version: {value!r}")
        return cls(*(int(part) for part in match.groups()))

    def bump(self, kind: str) -> "Version":
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ReleaseError(f"Unsupported bump kind: {kind}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def version_from_text(text: str) -> Version:
    match = VERSION_RE.search(text)
    if not match:
        raise ReleaseError("[project].version was not found in pyproject.toml")
    return Version.parse(match.group(1))


def current_version() -> Version:
    return version_from_text(PYPROJECT.read_text(encoding="utf-8"))


def origin_version() -> Version | None:
    result = subprocess.run(
        ["git", "show", "origin/main:pyproject.toml"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return None
    return version_from_text(result.stdout)


def registry_version(*, allow_unavailable: bool = False) -> Version | None:
    request = urllib.request.Request(REGISTRY_URL, headers={"User-Agent": "t8-release-verifier/1"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        if allow_unavailable:
            return None
        raise ReleaseError(f"Cannot read current Comfy Registry version: {exc}") from exc
    value = payload.get("latest_version", {}).get("version") if isinstance(payload, dict) else None
    if not value:
        if allow_unavailable:
            return None
        raise ReleaseError("Registry response did not contain latest_version.version")
    return Version.parse(str(value))


def _replace_version(version: Version) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    updated, count = VERSION_RE.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise ReleaseError("Unable to update exactly one project version")
    PYPROJECT.write_text(updated, encoding="utf-8", newline="\n")


def bump(kind: str) -> Version:
    versions = [current_version()]
    remote = origin_version()
    if remote is not None:
        versions.append(remote)
    published = registry_version(allow_unavailable=True)
    if published is not None:
        versions.append(published)
    target = max(versions).bump(kind)
    _replace_version(target)
    print(f"Updated pyproject.toml to {target}")
    if not CHANGELOG.is_file() or f"## [{target}]" not in CHANGELOG.read_text(encoding="utf-8"):
        print(f"WARNING: add a '## [{target}]' entry to CHANGELOG.md before pushing", file=sys.stderr)
    return target


def check(mode: str) -> None:
    local = current_version()
    origin = origin_version()
    published = registry_version()
    if mode == "prepush":
        if origin is not None and local <= origin:
            raise ReleaseError(f"Local {local} must be newer than origin/main {origin} before push")
    elif mode == "publish":
        if origin is not None and local != origin:
            raise ReleaseError(f"Checked-out version {local} does not match origin/main {origin}")
    else:
        raise ReleaseError(f"Unknown check mode: {mode}")
    if local <= published:
        raise ReleaseError(f"Version {local} must be newer than Registry {published}")
    if not CHANGELOG.is_file() or f"## [{local}]" not in CHANGELOG.read_text(encoding="utf-8"):
        raise ReleaseError(f"CHANGELOG.md is missing version {local}")
    print(json.dumps({
        "mode": mode,
        "local": str(local),
        "origin": str(origin) if origin else None,
        "registry": str(published),
        "changelog": True,
    }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump or verify the Comfy Registry release version.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--bump", choices=("patch", "minor", "major"))
    actions.add_argument("--check-prepush", action="store_true")
    actions.add_argument("--check-publish", action="store_true")
    args = parser.parse_args()
    try:
        if args.bump:
            bump(args.bump)
        else:
            check("prepush" if args.check_prepush else "publish")
    except ReleaseError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
