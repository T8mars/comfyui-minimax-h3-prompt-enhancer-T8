from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "official_skills" / "h3-prompt-writing"
SOURCE_MANIFEST = ROOT / "official_skills" / "H3_SOURCE.json"
NODES_MODULE = ROOT / "nodes.py"
REQUIRED_FILES = (
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("references/base-en.txt"),
    Path("references/ref-en.txt"),
)


class H3SkillUpdateError(RuntimeError):
    pass


def _normalized_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_skill(root: Path) -> dict[str, object]:
    missing = [relative.as_posix() for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise H3SkillUpdateError(f"H3 official Skill is missing required files: {missing}")
    records = []
    file_hashes: dict[str, str] = {}
    for relative in REQUIRED_FILES:
        digest = _sha256(_normalized_bytes(root / relative))
        file_hashes[relative.as_posix()] = digest
        records.append(f"{relative.as_posix()}\0{digest}")
    return {
        "file_count": len(REQUIRED_FILES),
        "normalized_tree_sha256": _sha256("\n".join(records).encode("utf-8")),
        "files": file_hashes,
    }


def _replace_constant(text: str, name: str, value: str) -> str:
    pattern = re.compile(rf'(?m)^{re.escape(name)}\s*=\s*"[^"]*"\s*$')
    updated, count = pattern.subn(f'{name} = "{value}"', text, count=1)
    if count != 1:
        raise H3SkillUpdateError(f"Could not update {name} in nodes.py")
    return updated


def apply_snapshot(source: Path, commit: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise H3SkillUpdateError("--commit must be an exact 40-character Git commit SHA")
    facts = inspect_skill(source)
    temporary = DESTINATION.with_name(DESTINATION.name + ".new")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    for relative in REQUIRED_FILES:
        target = temporary / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    temporary.replace(DESTINATION)
    manifest = {
        "schema_version": "t8-official-h3-skill-source/v1",
        "authority": "MiniMax-AI",
        "repository": "https://github.com/MiniMax-AI/MiniMax-H3",
        "commit": commit,
        "skill": "h3-prompt-writing",
        **facts,
        "normalization": "Required files are hashed after CRLF-to-LF normalization; sorted path NUL hash records are joined with LF and hashed again.",
        "purpose": "Pinned official H3 prompt-writing source used by the node's task-specific prompt compiler.",
    }
    SOURCE_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    module_text = NODES_MODULE.read_text(encoding="utf-8")
    module_text = _replace_constant(module_text, "OFFICIAL_SKILL_SOURCE_SHA", commit)
    module_text = _replace_constant(
        module_text,
        "OFFICIAL_SKILL_TREE_SHA256",
        str(facts["normalized_tree_sha256"]),
    )
    NODES_MODULE.write_text(module_text, encoding="utf-8", newline="\n")
    return manifest


def check_current() -> dict[str, object]:
    if not SOURCE_MANIFEST.is_file():
        raise H3SkillUpdateError("official_skills/H3_SOURCE.json is missing")
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    facts = inspect_skill(DESTINATION)
    for key in ("file_count", "normalized_tree_sha256", "files"):
        if manifest.get(key) != facts.get(key):
            raise H3SkillUpdateError(f"Bundled H3 Skill differs from H3_SOURCE.json: {key}")
    module_text = NODES_MODULE.read_text(encoding="utf-8")
    for name, value in (
        ("OFFICIAL_SKILL_SOURCE_SHA", manifest.get("commit")),
        ("OFFICIAL_SKILL_TREE_SHA256", manifest.get("normalized_tree_sha256")),
    ):
        if f'{name} = "{value}"' not in module_text:
            raise H3SkillUpdateError(f"nodes.py {name} does not match H3_SOURCE.json")
    return {**facts, "commit": manifest.get("commit")}


def resolve_source(path: Path) -> Path:
    candidate = path.resolve()
    nested = candidate / "skills" / "h3-prompt-writing"
    if nested.is_dir():
        return nested
    if candidate.name == "h3-prompt-writing" and candidate.is_dir():
        return candidate
    raise H3SkillUpdateError("--source-dir must be MiniMax-H3 or skills/h3-prompt-writing")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or explicitly replace the pinned MiniMax H3 official prompt-writing Skill."
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check-current", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if args.source_dir is None or not args.commit:
            parser.error("--apply requires --source-dir and --commit")
        result = apply_snapshot(resolve_source(args.source_dir), args.commit)
    elif args.check_current:
        result = check_current()
    elif args.source_dir is not None:
        result = inspect_skill(resolve_source(args.source_dir))
    else:
        parser.error("choose --check-current, or provide --source-dir, optionally with --apply")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
