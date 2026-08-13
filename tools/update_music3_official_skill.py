"""Validate or explicitly replace the pinned MiniMax Music 3 official Skill snapshot.

This is a maintainer tool, never a runtime downloader. Point it at a trusted local
checkout of MiniMax-AI/MiniMax-Music3 and pass --apply only after reviewing the
reported commit and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = PROJECT_ROOT / "official_skills" / "music-caption-rewriter"
SOURCE_MANIFEST = PROJECT_ROOT / "official_skills" / "SOURCE.json"
MUSIC3_MODULE = PROJECT_ROOT / "music3.py"
EXPECTED_INDEX_COUNT = 18
EXPECTED_TEMPLATE_COUNT = 1000
EXPECTED_FILE_COUNT = 1022


def _skill_root(path: Path) -> Path:
    resolved = path.resolve()
    nested = resolved / "skills" / "music-caption-rewriter"
    if nested.is_dir():
        return nested
    if resolved.name == "music-caption-rewriter" and resolved.is_dir():
        return resolved
    raise ValueError("source-dir must be the MiniMax-Music3 checkout or its skills/music-caption-rewriter directory")


def _normalized_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def normalized_tree_sha256(root: Path) -> str:
    records = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"symlinks are not accepted in the official snapshot: {path}")
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(_normalized_bytes(path)).hexdigest()
        records.append(f"{relative}\0{digest}")
    return hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()


def inspect_snapshot(root: Path) -> dict:
    root = root.resolve()
    skill = root / "SKILL.md"
    router = root / "references" / "genre-router.md"
    indexes = sorted((root / "references").glob("index-*.md"))
    templates = sorted((root / "templates").glob("*.txt"))
    files = sorted(item for item in root.rglob("*") if item.is_file())
    if not skill.is_file() or not router.is_file():
        raise ValueError("snapshot is missing SKILL.md or references/genre-router.md")
    if len(indexes) != EXPECTED_INDEX_COUNT:
        raise ValueError(f"expected {EXPECTED_INDEX_COUNT} family indexes, found {len(indexes)}")
    if len(templates) != EXPECTED_TEMPLATE_COUNT:
        raise ValueError(f"expected {EXPECTED_TEMPLATE_COUNT} templates, found {len(templates)}")
    if len(files) != EXPECTED_FILE_COUNT:
        raise ValueError(f"expected {EXPECTED_FILE_COUNT} files, found {len(files)}")
    return {
        "file_count": len(files),
        "family_index_count": len(indexes),
        "template_count": len(templates),
        "normalized_tree_sha256": normalized_tree_sha256(root),
        "core_skill_sha256": hashlib.sha256(_normalized_bytes(skill)).hexdigest(),
    }


def _replace_constant(text: str, name: str, value: str) -> str:
    pattern = rf'(?m)^{re.escape(name)} = "[0-9a-f]+"$'
    replaced, count = re.subn(pattern, f'{name} = "{value}"', text)
    if count != 1:
        raise ValueError(f"could not uniquely update {name} in music3.py")
    return replaced


def apply_snapshot(source: Path, commit: str, facts: dict) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("--commit must be the exact 40-character lowercase Git commit SHA")
    source = source.resolve()
    target_parent = TARGET_ROOT.parent.resolve()
    if source == TARGET_ROOT.resolve() or target_parent not in TARGET_ROOT.resolve().parents:
        raise ValueError("unsafe source or target path")

    previous_module_text = MUSIC3_MODULE.read_text(encoding="utf-8")
    previous_manifest_text = SOURCE_MANIFEST.read_text(encoding="utf-8")
    module_text = _replace_constant(previous_module_text, "OFFICIAL_SOURCE_COMMIT", commit)
    module_text = _replace_constant(module_text, "OFFICIAL_NORMALIZED_TREE_SHA256", facts["normalized_tree_sha256"])
    module_text = _replace_constant(module_text, "OFFICIAL_CORE_SKILL_SHA256", facts["core_skill_sha256"])
    manifest = {
        "schema_version": "t8-official-skill-source/v1",
        "authority": "MiniMax-AI",
        "repository": "https://github.com/MiniMax-AI/MiniMax-Music3",
        "commit": commit,
        "skill": "music-caption-rewriter",
        **{key: facts[key] for key in ("file_count", "family_index_count", "template_count", "normalized_tree_sha256")},
        "core_skill_sha256": facts["core_skill_sha256"],
        "normalization": "Each file is hashed after CRLF-to-LF normalization; sorted relative-path NUL file-hash records are joined with LF and hashed again.",
        "purpose": "Official MiniMax Music 3 prompt-writing resources bundled for progressive-disclosure caption enhancement.",
    }

    with tempfile.TemporaryDirectory(prefix="t8-music3-snapshot-", dir=target_parent) as temp_dir:
        staged = Path(temp_dir) / "music-caption-rewriter"
        shutil.copytree(source, staged)
        if inspect_snapshot(staged) != facts:
            raise ValueError("staged official snapshot changed during copy")
        backup = Path(temp_dir) / "previous-snapshot"
        TARGET_ROOT.rename(backup)
        try:
            staged.rename(TARGET_ROOT)
            MUSIC3_MODULE.write_text(module_text, encoding="utf-8", newline="\n")
            SOURCE_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        except Exception:
            if TARGET_ROOT.exists():
                shutil.rmtree(TARGET_ROOT)
            backup.rename(TARGET_ROOT)
            MUSIC3_MODULE.write_text(previous_module_text, encoding="utf-8", newline="\n")
            SOURCE_MANIFEST.write_text(previous_manifest_text, encoding="utf-8", newline="\n")
            raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="Trusted local MiniMax-Music3 checkout or Skill directory.")
    parser.add_argument("--commit", help="Exact upstream commit represented by source-dir; required with --apply.")
    parser.add_argument("--apply", action="store_true", help="Replace the pinned snapshot and update manifest/constants.")
    parser.add_argument("--check-current", action="store_true", help="Validate the currently bundled snapshot without modifying it.")
    args = parser.parse_args(argv)
    if args.check_current:
        root = TARGET_ROOT
    elif args.source_dir:
        root = _skill_root(args.source_dir)
    else:
        parser.error("provide --check-current or --source-dir")
    facts = inspect_snapshot(root)
    print(json.dumps({"root": str(root.resolve()), **facts}, ensure_ascii=False, indent=2))
    if args.apply:
        if args.check_current:
            parser.error("--apply cannot be combined with --check-current")
        if not args.commit:
            parser.error("--commit is required with --apply")
        apply_snapshot(root, args.commit, facts)
        print("UPDATED_MUSIC3_OFFICIAL_SKILL=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
