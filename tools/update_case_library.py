from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "case_templates" / "catalog.json"
PREVIEW_ROOT = ROOT / "web" / "js" / "assets" / "t8-case-previews"
DELIVERY_SCHEMA = "comfyui-delivery-package/v1"
REPORT_SCHEMA = "t8-case-library-update-report/v1"


class CaseLibraryUpdateError(RuntimeError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaseLibraryUpdateError(f"Unreadable JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise CaseLibraryUpdateError(f"Expected JSON object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_delivery(directory: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    directory = directory.resolve()
    manifest_path = directory / "delivery-manifest.json"
    manifest = _json(manifest_path)
    if manifest.get("schema_version") != DELIVERY_SCHEMA or manifest.get("immutable") is not True:
        raise CaseLibraryUpdateError("Unsupported or mutable delivery manifest")
    if manifest.get("mixed_batches_allowed") is not False:
        raise CaseLibraryUpdateError("Mixed delivery packages are not accepted")
    files: dict[str, Path] = {}
    for record in manifest.get("files", []):
        if not isinstance(record, dict):
            raise CaseLibraryUpdateError("Delivery file record is invalid")
        name = str(record.get("name", ""))
        path = (directory / name).resolve()
        try:
            path.relative_to(directory)
        except ValueError as exc:
            raise CaseLibraryUpdateError("Delivery file escapes its package directory") from exc
        if not path.is_file() or path.stat().st_size != int(record.get("size_bytes", -1)):
            raise CaseLibraryUpdateError(f"Delivery file is missing or truncated: {name}")
        if _sha256(path) != record.get("sha256"):
            raise CaseLibraryUpdateError(f"Delivery file hash mismatch: {name}")
        files[name] = path
    for required in ("unofficial-case-library-v2.json", "standalone-community-skills-v1.json"):
        if required not in files:
            raise CaseLibraryUpdateError(f"Delivery lacks required file: {required}")
    return manifest, files


def _load_importer():
    path = ROOT / "tools" / "import_unofficial_case_library_v2.py"
    spec = importlib.util.spec_from_file_location("t8_case_importer", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_preview_bundler():
    path = ROOT / "tools" / "bundle_t8_case_previews.py"
    spec = importlib.util.spec_from_file_location("t8_case_preview_bundler", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fingerprint(template: dict[str, Any]) -> str:
    material = {
        key: template.get(key)
        for key in ("summary", "input_format", "recommended_input", "required_anchors", "creative_dna", "variants")
    }
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _catalog_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_by_id = {str(item["id"]): item for item in old.get("templates", [])}
    new_by_id = {str(item["id"]): item for item in new.get("templates", [])}
    shared = set(old_by_id).intersection(new_by_id)
    return {
        "added_ids": sorted(set(new_by_id) - set(old_by_id)),
        "removed_ids": sorted(set(old_by_id) - set(new_by_id)),
        "renamed_ids": sorted(item for item in shared if old_by_id[item].get("label") != new_by_id[item].get("label")),
        "semantic_change_ids": sorted(item for item in shared if _fingerprint(old_by_id[item]) != _fingerprint(new_by_id[item])),
    }


def _preview_index(catalog: dict[str, Any]) -> dict[str, str]:
    return {
        str(preview.get("case_id")): str(preview.get("sha256"))
        for template in catalog.get("templates", [])
        for preview in template.get("previews", [])
        if isinstance(preview, dict)
    }


def _current_preview_sources() -> dict[str, str]:
    manifest = _json(PREVIEW_ROOT / "manifest.json")
    return {
        str(item.get("case_id")): str(item.get("source_sha256"))
        for item in manifest.get("previews", [])
        if isinstance(item, dict)
    }


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def _compatibility_alias_summary(catalog: dict[str, Any]) -> dict[str, int]:
    templates = catalog.get("templates", [])
    return {
        "legacy_ids": sum(len(item.get("legacy_ids", [])) for item in templates if isinstance(item, dict)),
        "legacy_labels": sum(len(item.get("legacy_labels", [])) for item in templates if isinstance(item, dict)),
    }


def _readme_count_gate(catalog: dict[str, Any]) -> bool:
    source = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = [
        f'{catalog.get("source_case_count")} 条已发布案例事实',
        f'{catalog.get("case_selector_template_count")} 个稳定案例 selector',
        f'含 {catalog.get("evidence_variant_count")} 个同机制证据变体',
        f'{catalog.get("community_skill_count")} 个独立用户贡献社区 Skill',
        f'共 {catalog.get("selector_template_count")} 个非官方下拉项',
    ]
    return all(value in source for value in expected)


def _run_post_apply_gates() -> None:
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "tools/verify_repository.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            raise CaseLibraryUpdateError(f"Post-apply gate failed: {' '.join(command[1:])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally apply one immutable T8 case-library delivery.")
    parser.add_argument("--delivery-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Atomically replace catalog.json after all gates pass.")
    parser.add_argument("--confirm-breaking", action="store_true", help="Acknowledge selector removal/rename/semantic drift.")
    parser.add_argument("--rebuild-previews", action="store_true", help="Stage and atomically install changed preview assets.")
    parser.add_argument("--confirm-preview-budget", action="store_true", help="Acknowledge a staged preview package at or above 165 MiB.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--report", type=Path, help="Optional machine-readable report outside the repository.")
    args = parser.parse_args()
    manifest, files = _verify_delivery(args.delivery_dir)
    importer = _load_importer()
    new_catalog = importer.build_catalog(
        files["unofficial-case-library-v2.json"],
        files["standalone-community-skills-v1.json"],
        CATALOG,
    )
    old_catalog = _json(CATALOG)
    diff = _catalog_diff(old_catalog, new_catalog)
    expected_previews = _preview_index(new_catalog)
    installed_previews = _current_preview_sources()
    missing_or_changed_previews = sorted(
        case_id for case_id, digest in expected_previews.items() if installed_previews.get(case_id) != digest
    )
    orphaned_previews = sorted(set(installed_previews) - set(expected_previews))
    breaking = bool(diff["removed_ids"] or diff["renamed_ids"] or diff["semantic_change_ids"])
    if breaking and not args.confirm_breaking:
        raise CaseLibraryUpdateError("Selector removal, rename, or Creative DNA drift requires --confirm-breaking")
    preview_rebuild_required = bool(missing_or_changed_previews or orphaned_previews)
    if args.apply and preview_rebuild_required and not args.rebuild_previews:
        raise CaseLibraryUpdateError(
            "Preview package must be rebuilt with --rebuild-previews before --apply; "
            f"changed={len(missing_or_changed_previews)}, orphaned={len(orphaned_previews)}"
        )

    readme_counts_current = _readme_count_gate(new_catalog)
    if args.apply and not readme_counts_current:
        raise CaseLibraryUpdateError("README inventory counts must be updated and reviewed before --apply")

    staged_manifest = None
    staged_root = None
    staged_bundle = None
    if args.apply and preview_rebuild_required:
        bundler = _load_preview_bundler()
        staged_root = Path(tempfile.mkdtemp(prefix=".t8-case-update-", dir=PREVIEW_ROOT.parent)).resolve()
        try:
            staged_catalog = staged_root / "catalog.json"
            staged_bundle = staged_root / "bundle"
            _atomic_write_json(staged_catalog, new_catalog)
            current_encoding = _json(PREVIEW_ROOT / "manifest.json").get("encoding", {})
            staged_manifest = bundler.bundle_previews(
                files["unofficial-case-library-v2.json"],
                files["standalone-community-skills-v1.json"],
                staged_catalog,
                staged_bundle,
                args.ffmpeg,
                fps=int(current_encoding.get("fps", 3)),
                max_width=int(current_encoding.get("max_width", 224)),
                colors=int(current_encoding.get("max_colors", 40)),
                existing_bundle=PREVIEW_ROOT,
            )
            total = int(staged_manifest["total_bytes"])
            if total > bundler.PREVIEW_HARD_LIMIT_BYTES:
                raise CaseLibraryUpdateError("Staged preview package exceeds the 180 MiB hard limit")
            if total >= bundler.PREVIEW_CONFIRM_BYTES and not args.confirm_preview_budget:
                raise CaseLibraryUpdateError("Staged preview package at or above 165 MiB requires --confirm-preview-budget")
        except Exception:
            shutil.rmtree(staged_root)
            raise

    if args.apply:
        backup_bundle = PREVIEW_ROOT.with_name(f".{PREVIEW_ROOT.name}-rollback")
        installed_new_bundle = False
        try:
            if staged_bundle is not None:
                if backup_bundle.exists():
                    raise CaseLibraryUpdateError("A stale preview rollback directory already exists")
                os.replace(PREVIEW_ROOT, backup_bundle)
                os.replace(staged_bundle, PREVIEW_ROOT)
                installed_new_bundle = True
            _atomic_write_json(CATALOG, new_catalog)
            _run_post_apply_gates()
        except Exception:
            _atomic_write_json(CATALOG, old_catalog)
            if installed_new_bundle:
                failed_bundle = PREVIEW_ROOT.with_name(f".{PREVIEW_ROOT.name}-failed")
                if failed_bundle.exists():
                    shutil.rmtree(failed_bundle)
                os.replace(PREVIEW_ROOT, failed_bundle)
                os.replace(backup_bundle, PREVIEW_ROOT)
                shutil.rmtree(failed_bundle)
            raise
        else:
            if backup_bundle.exists():
                shutil.rmtree(backup_bundle)
        finally:
            if staged_root is not None and staged_root.exists():
                shutil.rmtree(staged_root)

    preview_files = list(PREVIEW_ROOT.glob("*.gif"))
    report = {
        "schema_version": REPORT_SCHEMA,
        "delivery_id": str(manifest.get("delivery_id", "")),
        "mode": "apply" if args.apply else "dry-run",
        "applied": bool(args.apply),
        "counts": {
            "source_cases": new_catalog.get("source_case_count"),
            "selectors": new_catalog.get("selector_template_count"),
            "evidence_variants": new_catalog.get("evidence_variant_count"),
            "community_skills": new_catalog.get("community_skill_count"),
            "preview_references": len(expected_previews),
            "preview_assets": len(preview_files),
            "compatibility_aliases": _compatibility_alias_summary(new_catalog),
        },
        "diff": diff,
        "preview_rebuild": {
            "required": preview_rebuild_required,
            "rebuilt": staged_manifest is not None,
            "missing_or_changed_count": len(missing_or_changed_previews),
            "orphaned_count": len(orphaned_previews),
            "total_bytes": sum(path.stat().st_size for path in preview_files),
            "largest_bytes": max((path.stat().st_size for path in preview_files), default=0),
        },
        "catalog_sha256": hashlib.sha256(
            json.dumps(new_catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "official_skills_modified": False,
        "readme_counts_current": readme_counts_current,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if re.search(r"https?://|[A-Za-z]:\\|(?:^|\W)sk-[A-Za-z0-9_-]{16,}", encoded):
        raise CaseLibraryUpdateError("Machine report unexpectedly contains a URL, local path, or secret")
    if args.report:
        report_path = args.report.expanduser().resolve()
        try:
            report_path.relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            raise CaseLibraryUpdateError("Machine reports must be written outside the repository")
        _atomic_write_json(report_path, report)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
