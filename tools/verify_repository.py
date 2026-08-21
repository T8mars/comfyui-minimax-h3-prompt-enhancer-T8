from __future__ import annotations

import argparse
import json
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
)
SECRET_RE = re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}")
TEXT_SUFFIXES = {
    ".css", ".html", ".ini", ".js", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml",
}
MAX_BUNDLED_PREVIEW_BYTES = 180 * 1024 * 1024


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


def verify_preview_budget() -> dict[str, int]:
    preview_root = ROOT / "web" / "js" / "assets"
    gifs = list(preview_root.rglob("*.gif"))
    total = sum(path.stat().st_size for path in gifs)
    if total > MAX_BUNDLED_PREVIEW_BYTES:
        raise VerificationError(
            f"Bundled GIFs use {total} bytes, above budget {MAX_BUNDLED_PREVIEW_BYTES}"
        )
    return {"gif_count": len(gifs), "gif_bytes": total, "gif_budget": MAX_BUNDLED_PREVIEW_BYTES}


def verify_required_release_files() -> None:
    required = (
        ROOT / "CHANGELOG.md",
        ROOT / "COMPATIBILITY.md",
        ROOT / "LICENSE.txt",
        ROOT / "pyproject.toml",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "assets" / "t8-prompt-enhancer-icon.svg",
        ROOT / "assets" / "t8-prompt-enhancer-banner.svg",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise VerificationError(f"Missing release files: {missing}")


def run_optional_checks() -> None:
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
        for path in sorted((ROOT / "web" / "js").glob("*.js")):
            subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=True)


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
        preview = verify_preview_budget()
        if not args.skip_tool_checks:
            run_optional_checks()
    except (VerificationError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps({"tracked_files": len(files), **preview, "passed": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
