from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TRACKED = (
    re.compile(r"(^|/)roadmap\.md$", re.IGNORECASE),
    re.compile(r"(^|/)runtime(?:/|$)", re.IGNORECASE),
    re.compile(r"\.gguf(?:\.part)?$", re.IGNORECASE),
    re.compile(r"(^|/)runtime_config\.json$", re.IGNORECASE),
    re.compile(r"(^|/)\.user(?:/|$)", re.IGNORECASE),
    re.compile(r"(^|/)credentials\.json$", re.IGNORECASE),
)
SECRET_RE = re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}")
TEXT_SUFFIXES = {
    ".css", ".html", ".ini", ".js", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml",
}
PREVIEW_WARNING_BYTES = 80 * 1024 * 1024
PREVIEW_CONFIRM_BYTES = 85 * 1024 * 1024
# Comfy Registry flags node ZIPs above 100 MB.  The raw preview ceiling leaves
# room for Python, documentation, catalogs, manifests, and ZIP metadata.
MAX_BUNDLED_PREVIEW_BYTES = 90 * 1024 * 1024
MAX_BUNDLED_PREVIEW_FILE_BYTES = 2 * 1024 * 1024
T8_PREVIEW_SCHEMA = "t8-bundled-case-previews/v1"
REGISTRY_SCANNER_TRIPWIRES = {
    "environment_read": b"os.environ",
    "dynamic_import": b"importlib.import_module(",
    "direct_requests_post": b"requests.post(",
    "direct_urllib": b"urllib.request",
    "direct_socket": b"socket.socket(",
    "direct_subprocess_run": b"subprocess.run(",
    "direct_subprocess_popen": b"subprocess.Popen(",
}


class VerificationError(RuntimeError):
    pass


def tracked_files() -> list[Path]:
    """Return every tracked or untracked, non-ignored release candidate.

    Using only ``git ls-files`` would miss a newly-created secret or malformed
    JSON before its first staging operation, exactly when this gate is most
    useful. Ignored local runtime/model files remain outside the candidate set;
    a force-added ignored file becomes tracked and is then rejected normally.
    """
    result = subprocess.run(
        ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    files = [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return [path for path in files if path.is_file()]


def verify_paths(files: list[Path]) -> None:
    relative = [path.relative_to(ROOT).as_posix() for path in files]
    bad = [value for value in relative if any(pattern.search(value) for pattern in FORBIDDEN_TRACKED)]
    if bad:
        raise VerificationError(f"Forbidden tracked release files: {bad}")


def verify_secrets(files: list[Path]) -> None:
    findings: list[str] = []
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        for match in SECRET_RE.finditer(path.read_bytes()):
            findings.append(f"{path.relative_to(ROOT).as_posix()}:{match.start()}")
    if findings:
        raise VerificationError(f"Potential API keys in tracked files: {findings}")


def verify_json(files: list[Path]) -> None:
    invalid: list[str] = []
    for path in files:
        if path.suffix.lower() != ".json" or not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(path.relative_to(ROOT).as_posix())
    if invalid:
        raise VerificationError(f"Invalid tracked JSON: {invalid}")


def verify_toml_and_yaml(files: list[Path]) -> None:
    invalid: list[str] = []
    for path in files:
        suffix = path.suffix.lower()
        try:
            if suffix == ".toml":
                tomllib.loads(path.read_text(encoding="utf-8"))
            elif suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError):
            invalid.append(path.relative_to(ROOT).as_posix())
    if invalid:
        raise VerificationError(f"Invalid TOML/YAML: {invalid}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_t8_preview_manifest() -> dict[str, int]:
    preview_root = ROOT / "web" / "js" / "assets" / "t8-case-previews"
    manifest_path = preview_root / "manifest.json"
    if not manifest_path.is_file():
        raise VerificationError("Missing T8 preview manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != T8_PREVIEW_SCHEMA:
        raise VerificationError("Unsupported T8 preview manifest schema")
    entries = manifest.get("previews")
    if not isinstance(entries, list) or int(manifest.get("preview_count", -1)) != len(entries):
        raise VerificationError("T8 preview manifest count mismatch")

    case_ids: set[str] = set()
    referenced_files: dict[str, int] = {}
    declared_hashes: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise VerificationError("T8 preview manifest contains a non-object entry")
        case_id = str(entry.get("case_id", "")).strip()
        filename = str(entry.get("file", "")).strip()
        declared_hash = str(entry.get("sha256", "")).strip().lower()
        if not case_id or case_id in case_ids:
            raise VerificationError(f"Missing or duplicate T8 preview case_id: {case_id!r}")
        if not re.fullmatch(r"[0-9a-f]{64}\.gif", filename):
            raise VerificationError(f"Unsafe T8 preview filename: {filename!r}")
        if declared_hash != filename[:-4]:
            raise VerificationError(f"T8 preview filename/hash mismatch: {case_id}")
        previous_hash = declared_hashes.setdefault(filename, declared_hash)
        if previous_hash != declared_hash:
            raise VerificationError(f"Conflicting hashes for shared preview: {filename}")
        case_ids.add(case_id)
        referenced_files[filename] = referenced_files.get(filename, 0) + 1

    gif_files = {path.name: path for path in preview_root.glob("*.gif")}
    missing = sorted(set(referenced_files) - set(gif_files))
    orphaned = sorted(set(gif_files) - set(referenced_files))
    if missing or orphaned:
        raise VerificationError(f"T8 preview manifest/files differ; missing={missing}, orphaned={orphaned}")

    for filename, path in gif_files.items():
        size = path.stat().st_size
        if size > MAX_BUNDLED_PREVIEW_FILE_BYTES:
            raise VerificationError(
                f"Bundled preview {filename} uses {size} bytes, above per-file limit "
                f"{MAX_BUNDLED_PREVIEW_FILE_BYTES}"
            )
        with path.open("rb") as handle:
            if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
                raise VerificationError(f"Bundled preview is not a GIF: {filename}")
        if _sha256(path) != declared_hashes[filename]:
            raise VerificationError(f"Bundled preview hash mismatch: {filename}")
        declared_sizes = {
            int(entry.get("bytes", -1))
            for entry in entries
            if isinstance(entry, dict) and entry.get("file") == filename
        }
        if declared_sizes != {size}:
            raise VerificationError(f"Bundled preview byte count mismatch: {filename}")

    return {
        "t8_preview_references": len(entries),
        "t8_preview_assets": len(gif_files),
        "t8_preview_dedup_references": len(entries) - len(gif_files),
    }


def verify_preview_budget() -> dict[str, int | str]:
    asset_root = ROOT / "web" / "js" / "assets"
    # Count only the two distributable preview roots. During an atomic case
    # update a hidden sibling temporarily holds the rollback bundle; including
    # it would double-count identical assets and reject an otherwise safe
    # release before the rollback directory can be removed.
    gifs = list((asset_root / "official-previews").glob("*.gif"))
    gifs.extend((asset_root / "t8-case-previews").glob("*.gif"))
    total = sum(path.stat().st_size for path in gifs)
    if total > MAX_BUNDLED_PREVIEW_BYTES:
        raise VerificationError(
            f"Bundled GIFs use {total} bytes, above budget {MAX_BUNDLED_PREVIEW_BYTES}"
        )
    if total >= PREVIEW_CONFIRM_BYTES and os.environ.get("T8_CONFIRM_PREVIEW_BUDGET") != "1":
        raise VerificationError(
            f"Bundled GIFs use {total} bytes (>= {PREVIEW_CONFIRM_BYTES}); reviewed releases must set "
            "T8_CONFIRM_PREVIEW_BUDGET=1"
        )
    if total >= PREVIEW_CONFIRM_BYTES:
        status = "confirm"
    elif total >= PREVIEW_WARNING_BYTES:
        status = "warning"
    else:
        status = "ok"
    largest = max((path.stat().st_size for path in gifs), default=0)
    return {
        "gif_count": len(gifs),
        "gif_bytes": total,
        "gif_largest_bytes": largest,
        "gif_budget_status": status,
        "gif_warning_bytes": PREVIEW_WARNING_BYTES,
        "gif_confirm_bytes": PREVIEW_CONFIRM_BYTES,
        "gif_budget": MAX_BUNDLED_PREVIEW_BYTES,
        **_verify_t8_preview_manifest(),
    }


def verify_required_release_files() -> None:
    required = (
        ROOT / "CHANGELOG.md",
        ROOT / "COMPATIBILITY.md",
        ROOT / "LICENSE.txt",
        ROOT / "pyproject.toml",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / ".comfyignore",
        ROOT / "assets" / "t8-prompt-enhancer-icon.svg",
        ROOT / "assets" / "t8-prompt-enhancer-banner.svg",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise VerificationError(f"Missing release files: {missing}")


def verify_registry_package_hygiene(files: list[Path]) -> dict[str, int]:
    relative = [path.relative_to(ROOT).as_posix() for path in files]
    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.excludesFile=.comfyignore",
            "check-ignore",
            "--no-index",
            "--stdin",
            "-z",
        ],
        cwd=ROOT,
        input=b"\0".join(value.encode("utf-8") for value in relative) + b"\0",
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise VerificationError("git could not evaluate .comfyignore")
    ignored = {
        item.decode("utf-8") for item in completed.stdout.split(b"\0") if item
    }
    shipped = [path for path in files if path.relative_to(ROOT).as_posix() not in ignored]
    shipped_relative = {path.relative_to(ROOT).as_posix() for path in shipped}
    required = {
        "__init__.py",
        "nodes.py",
        "seedance20.py",
        "music3.py",
        "creative_suite.py",
        "local_qwen_runtime.py",
        "local_qwen_python_runtime.py",
        "preview_asset_manager.py",
        "preview_assets/channel.json",
        "web/js/preview_asset_ui.js",
        "official_skills/h3-prompt-writing/SKILL.md",
        "official_skills/music-caption-rewriter/SKILL.md",
    }
    missing = sorted(required - shipped_relative)
    if missing:
        raise VerificationError(f"Registry archive is missing runtime files: {missing}")
    forbidden = {
        "install_local_qwen.py",
        "local_qwen_standalone_runtime.py",
        "environment_defaults.py",
        "credential_connection_probe.py",
        "creative_suite_live_smoke.py",
    }
    leaked = sorted(forbidden & shipped_relative)
    if leaked:
        raise VerificationError(f"Registry archive exposes GitHub-only helpers: {leaked}")
    leaked_t8_gifs = sorted(
        path for path in shipped_relative
        if path.startswith("web/js/assets/t8-case-previews/") and path.endswith(".gif")
    )
    if leaked_t8_gifs:
        raise VerificationError(
            f"Registry archive still contains externalized T8 GIF previews: {leaked_t8_gifs[:3]}"
        )
    if "web/js/assets/t8-case-previews/manifest.json" not in shipped_relative:
        raise VerificationError("Registry archive is missing the T8 preview identity manifest")

    findings: list[str] = []
    python_files = [path for path in shipped if path.suffix.casefold() == ".py"]
    for path in python_files:
        payload = path.read_bytes()
        for label, pattern in REGISTRY_SCANNER_TRIPWIRES.items():
            if pattern in payload:
                findings.append(f"{path.relative_to(ROOT).as_posix()}:{label}")
    if findings:
        raise VerificationError(f"Registry scanner tripwires remain in shipped Python: {findings}")
    return {
        "registry_files": len(shipped),
        "registry_python_files": len(python_files),
        "registry_uncompressed_bytes": sum(path.stat().st_size for path in shipped),
    }


def run_optional_checks() -> None:
    subprocess.run(
        [sys.executable, "tools/build_example_workflows.py", "--check"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/update_h3_official_skill.py", "--check-current"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/update_music3_official_skill.py", "--check-current"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([sys.executable, "-m", "compileall", "-q", "."], cwd=ROOT, check=True)
    node = subprocess.run(["node", "--version"], capture_output=True, check=False)
    if node.returncode == 0:
        scripts = sorted((ROOT / "web" / "js").glob("*.js")) + sorted((ROOT / "web" / "js").glob("*.mjs"))
        for path in scripts:
            subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=True)
        frontend_tests = sorted((ROOT / "tests" / "frontend").glob("*.test.mjs"))
        if frontend_tests:
            subprocess.run(["node", "--test", *map(str, frontend_tests)], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic release-safety checks.")
    parser.add_argument("--skip-tool-checks", action="store_true")
    args = parser.parse_args()
    try:
        files = tracked_files()
        verify_paths(files)
        verify_secrets(files)
        verify_json(files)
        verify_toml_and_yaml(files)
        verify_required_release_files()
        registry = verify_registry_package_hygiene(files)
        preview = verify_preview_budget()
        if not args.skip_tool_checks:
            run_optional_checks()
    except (VerificationError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {"tracked_files": len(files), **registry, **preview, "passed": True},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
