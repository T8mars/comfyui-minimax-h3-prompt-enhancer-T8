from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


BUNDLE_SCHEMA = "t8-bundled-case-previews/v1"
CASE_LIBRARY_SCHEMA = "t8-unofficial-case-library/v2"
COMMUNITY_LIBRARY_SCHEMA = "t8-standalone-community-skill-handoff/v1"
CATALOG_SCHEMA = "t8-case-template-catalog/v2"
PREVIEW_WARNING_BYTES = 80 * 1024 * 1024
PREVIEW_CONFIRM_BYTES = 85 * 1024 * 1024
# Comfy Registry flags node ZIPs above 100 MB.  Keep raw previews below
# 90 MiB so ZIP metadata and the rest of the node pack retain safe headroom.
PREVIEW_HARD_LIMIT_BYTES = 90 * 1024 * 1024
NEW_PREVIEW_FILE_LIMIT_BYTES = 2 * 1024 * 1024


class PreviewBundleError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreviewBundleError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreviewBundleError(f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_previews(case_library: Path, community_library: Path) -> dict[str, dict[str, str]]:
    cases = _read_json(case_library)
    if cases.get("schema_version") != CASE_LIBRARY_SCHEMA:
        raise PreviewBundleError("Unsupported T8 case-library schema")
    sources: dict[str, dict[str, str]] = {}
    for record in cases.get("records", []):
        if not isinstance(record, dict):
            continue
        preview = record.get("preview", {})
        case_id = str(record.get("case_id", ""))
        source = (Path(str(record.get("case_path", ""))).resolve() / str(preview.get("path", ""))).resolve()
        sources[case_id] = {"path": str(source), "sha256": str(preview.get("sha256", ""))}

    community = _read_json(community_library)
    if community.get("schema_version") != COMMUNITY_LIBRARY_SCHEMA:
        raise PreviewBundleError("Unsupported standalone community-Skill schema")
    for record in community.get("records", []):
        if not isinstance(record, dict):
            continue
        preview = record.get("preview", {})
        preview_id = f"community-skill--{record.get('skill_id', '')}"
        sources[preview_id] = {
            "path": str(Path(str(preview.get("path", ""))).resolve()),
            "sha256": str(preview.get("sha256", "")),
        }
    return sources


def _catalog_previews(catalog_path: Path) -> list[dict[str, Any]]:
    catalog = _read_json(catalog_path)
    if catalog.get("schema_version") != CATALOG_SCHEMA:
        raise PreviewBundleError("Unsupported installed T8 case-template catalog schema")
    previews = [
        preview
        for template in catalog.get("templates", [])
        if isinstance(template, dict)
        for preview in template.get("previews", [])
        if isinstance(preview, dict)
    ]
    if not previews or len({str(item.get("case_id", "")) for item in previews}) != len(previews):
        raise PreviewBundleError("Installed catalog has missing or duplicate preview identities")
    return previews


def _resolve_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(value)
    if resolved:
        return resolved
    raise PreviewBundleError(f"Executable not found: {value}")


def _existing_preview_index(
    bundle_dir: Path | None,
    *,
    fps: int,
    max_width: int,
    colors: int,
) -> dict[str, dict[str, Any]]:
    if bundle_dir is None:
        return {}
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return {}
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != BUNDLE_SCHEMA:
        raise PreviewBundleError(f"Unsupported reusable preview manifest: {manifest_path}")
    encoding = manifest.get("encoding") if isinstance(manifest.get("encoding"), dict) else {}
    expected_encoding = {
        "format": "gif",
        "fps": fps,
        "max_width": max_width,
        "max_colors": colors,
        "loop": True,
    }
    if any(encoding.get(key) != value for key, value in expected_encoding.items()):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in manifest.get("previews", []):
        if not isinstance(item, dict):
            raise PreviewBundleError(f"Reusable preview manifest contains an invalid entry: {manifest_path}")
        case_id = str(item.get("case_id", ""))
        filename = str(item.get("file", ""))
        bundled_hash = str(item.get("sha256", ""))
        if (
            not case_id
            or case_id in result
            or Path(filename).name != filename
            or not re.fullmatch(r"[0-9a-f]{64}\.gif", filename)
            or filename != f"{bundled_hash}.gif"
        ):
            raise PreviewBundleError(f"Reusable preview manifest identity is invalid: {case_id or '<unknown>'}")
        result[case_id] = item
    return result


def bundle_previews(
    case_library: Path,
    community_library: Path,
    catalog_path: Path,
    output_dir: Path,
    ffmpeg: str,
    *,
    fps: int,
    max_width: int,
    colors: int,
    existing_bundle: Path | None = None,
) -> dict[str, Any]:
    sources = _source_previews(case_library, community_library)
    previews = _catalog_previews(catalog_path)
    expected_ids = {str(item["case_id"]) for item in previews}
    if set(sources) != expected_ids:
        missing = sorted(expected_ids - set(sources))
        extra = sorted(set(sources) - expected_ids)
        raise PreviewBundleError(f"Source/catalog preview IDs differ; missing={missing}, extra={extra}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PreviewBundleError(f"Output directory must be absent or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = _resolve_executable(ffmpeg)
    reusable = _existing_preview_index(
        existing_bundle,
        fps=fps,
        max_width=max_width,
        colors=colors,
    )
    reusable_root = existing_bundle.resolve() if existing_bundle is not None else None
    filter_graph = (
        f"fps={fps},scale='min({max_width},iw)':-2:flags=lanczos,split[s0][s1];"
        f"[s0]palettegen=max_colors={colors}:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )

    entries: list[dict[str, Any]] = []
    bundled_by_hash: dict[str, Path] = {}
    for index, preview in enumerate(previews, 1):
        case_id = str(preview["case_id"])
        source = Path(sources[case_id]["path"])
        source_hash = sources[case_id]["sha256"]
        if source.suffix.lower() != ".gif" or not source.is_file():
            raise PreviewBundleError(f"Source GIF is missing: {case_id}: {source}")
        if _sha256(source) != source_hash or source_hash != str(preview.get("sha256", "")):
            raise PreviewBundleError(f"Source/catalog SHA-256 mismatch: {case_id}")
        reusable_entry = reusable.get(case_id)
        if reusable_entry is not None and reusable_entry.get("source_sha256") == source_hash:
            assert reusable_root is not None
            filename = str(reusable_entry["file"])
            bundled_hash = str(reusable_entry["sha256"])
            current = reusable_root / filename
            if not current.is_file() or _sha256(current) != bundled_hash:
                raise PreviewBundleError(f"Reusable bundled GIF hash mismatch: {case_id}: {filename}")
            with current.open("rb") as handle:
                if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
                    raise PreviewBundleError(f"Reusable bundled output is not a GIF: {case_id}")
            final_path = output_dir / filename
            if final_path.exists():
                if _sha256(final_path) != bundled_hash:
                    raise PreviewBundleError(f"Conflicting reusable bundled GIF: {case_id}: {filename}")
            else:
                shutil.copy2(current, final_path)
            entries.append({
                "case_id": case_id,
                "file": filename,
                "source_sha256": source_hash,
                "sha256": bundled_hash,
                "bytes": final_path.stat().st_size,
                "human_preview_only": True,
            })
            bundled_by_hash[bundled_hash] = final_path
            print(
                f"[{index:02d}/{len(previews)}] {case_id} -> {filename} "
                f"({final_path.stat().st_size} bytes, reused)"
            )
            continue
        temporary = output_dir / f".{index:03d}.gif"
        completed = subprocess.run(
            [
                ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y",
                "-threads", "1", "-filter_threads", "1", "-filter_complex_threads", "1",
                "-i", str(source),
                "-filter_complex", filter_graph, "-loop", "0", str(temporary),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise PreviewBundleError(f"ffmpeg failed for {case_id}: {completed.stderr.strip()}")
        with temporary.open("rb") as handle:
            if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
                raise PreviewBundleError(f"Bundled output is not a GIF: {case_id}")
        bundled_hash = _sha256(temporary)
        filename = f"{bundled_hash}.gif"
        final_path = output_dir / filename
        if final_path.exists():
            # Distinct evidence variants may intentionally encode to identical
            # preview bytes.  Reuse the content-addressed asset while retaining
            # one manifest entry per selector identity.
            if bundled_hash not in bundled_by_hash or _sha256(final_path) != bundled_hash:
                raise PreviewBundleError(f"Conflicting duplicate bundled GIF: {case_id}: {filename}")
            temporary.unlink()
        else:
            if temporary.stat().st_size > NEW_PREVIEW_FILE_LIMIT_BYTES:
                raise PreviewBundleError(
                    f"Bundled preview exceeds {NEW_PREVIEW_FILE_LIMIT_BYTES} bytes: "
                    f"{case_id}: {temporary.stat().st_size}"
                )
            temporary.replace(final_path)
            bundled_by_hash[bundled_hash] = final_path
        entries.append({
            "case_id": case_id,
            "file": filename,
            "source_sha256": source_hash,
            "sha256": bundled_hash,
            "bytes": final_path.stat().st_size,
            "human_preview_only": True,
        })
        print(f"[{index:02d}/{len(previews)}] {case_id} -> {filename} ({final_path.stat().st_size} bytes)")

    assets = list(output_dir.glob("*.gif"))
    dedup_references = len(entries) - len(assets)
    total_bytes = sum(path.stat().st_size for path in assets)
    largest_bytes = max((path.stat().st_size for path in assets), default=0)
    manifest = {
        "schema_version": BUNDLE_SCHEMA,
        "catalog_id": "t8-unofficial-case-library-v2",
        "preview_count": len(entries),
        "asset_count": len(assets),
        "dedup_references": dedup_references,
        "total_bytes": total_bytes,
        "largest_bytes": largest_bytes,
        "encoding": {
            "format": "gif",
            "fps": fps,
            "max_width": max_width,
            "max_colors": colors,
            "loop": True,
        },
        "policy": "Bundled human UI preview only; never connect or send as model/LLM reference material.",
        "previews": entries,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    community_count = sum(item["case_id"].startswith("community-skill--") for item in entries)
    case_count = len(entries) - community_count
    (output_dir / "NOTICE.md").write_text(
        "# T8 case preview GIFs\n\n"
        "This directory contains lightweight GIF previews bundled for the non-official T8 template library.\n\n"
        f"- {len(entries)} preview references are included: {case_count} released case previews and "
        f"{community_count} standalone community-Skill previews.\n"
        "- They are human UI previews only. The node never connects or sends them as image, video, model, or "
        "LLM reference material.\n"
        "- Files are indexed by `manifest.json`; both source and bundled SHA-256 values are pinned.\n"
        f"- The distributable encoding profile is {fps} fps, maximum width {max_width} px, and a "
        f"{colors}-color palette.\n"
        "- Source videos are not included.\n\n"
        "Regenerate the directory with `tools/bundle_t8_case_previews.py` whenever the selector catalog changes. "
        "Generate into an empty directory, validate the manifest and tests, then replace this directory as one "
        "reviewed change.\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build distributable lightweight GIFs for every T8 selector preview.")
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--community-skills", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--fps", type=int, default=2)
    parser.add_argument("--max-width", type=int, default=180)
    parser.add_argument("--colors", type=int, default=32)
    parser.add_argument(
        "--existing-bundle",
        type=Path,
        help="Reuse hash-verified encoded GIFs when their source SHA-256 has not changed.",
    )
    args = parser.parse_args()
    if not 1 <= args.fps <= 15 or not 160 <= args.max_width <= 640 or not 32 <= args.colors <= 128:
        raise PreviewBundleError("Encoding limits: fps 1-15, max-width 160-640, colors 32-128")
    manifest = bundle_previews(
        args.library.resolve(),
        args.community_skills.resolve(),
        args.catalog.resolve(),
        args.output_dir.resolve(),
        args.ffmpeg,
        fps=args.fps,
        max_width=args.max_width,
        colors=args.colors,
        existing_bundle=args.existing_bundle.resolve() if args.existing_bundle else None,
    )
    total_bytes = int(manifest["total_bytes"])
    if total_bytes > PREVIEW_HARD_LIMIT_BYTES:
        raise PreviewBundleError(
            f"Bundled previews use {total_bytes} bytes, above hard limit {PREVIEW_HARD_LIMIT_BYTES}"
        )
    if total_bytes >= PREVIEW_CONFIRM_BYTES:
        status = "confirm"
    elif total_bytes >= PREVIEW_WARNING_BYTES:
        status = "warning"
    else:
        status = "ok"
    report = {
        "new_references": manifest["preview_count"],
        "unique_assets": manifest["asset_count"],
        "dedup_hits": manifest["dedup_references"],
        "largest_bytes": manifest["largest_bytes"],
        "total_bytes": total_bytes,
        "budget_status": status,
        "thresholds": {
            "warning": PREVIEW_WARNING_BYTES,
            "confirm": PREVIEW_CONFIRM_BYTES,
            "hard": PREVIEW_HARD_LIMIT_BYTES,
            "single_file": NEW_PREVIEW_FILE_LIMIT_BYTES,
        },
        "output_dir": str(args.output_dir.resolve()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
