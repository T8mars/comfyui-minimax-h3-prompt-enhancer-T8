from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
T8_ROOT = ROOT / "web" / "js" / "assets" / "t8-case-previews"
OFFICIAL_ROOT = ROOT / "web" / "js" / "assets" / "official-previews"
OFFICIAL_COMMIT = "743d51e83329cbae6c7694f1c7b89576e7c25e07"
DEFAULT_FPS = 4
DEFAULT_MAX_WIDTH = 256
DEFAULT_COLORS = 48


class GifOptimizationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encoder(ffmpeg: str) -> str:
    candidate = Path(ffmpeg).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(ffmpeg)
    if not resolved:
        raise GifOptimizationError(f"ffmpeg is unavailable: {ffmpeg}")
    return resolved


def encode(source: Path, target: Path, ffmpeg: str, *, fps: int, width: int, colors: int) -> None:
    graph = (
        f"fps={fps},scale='min({width},iw)':-2:flags=lanczos,split[s0][s1];"
        f"[s0]palettegen=max_colors={colors}:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    completed = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-threads", "1",
            "-filter_threads", "1", "-filter_complex_threads", "1", "-i", str(source),
            "-filter_complex", graph, "-loop", "0", str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise GifOptimizationError(f"ffmpeg failed for {source.name}: {completed.stderr.strip()}")
    with target.open("rb") as handle:
        if handle.read(6) not in {b"GIF87a", b"GIF89a"}:
            raise GifOptimizationError(f"Output is not GIF: {target}")


def optimize_t8(ffmpeg: str, *, fps: int, width: int, colors: int) -> dict[str, Any]:
    manifest_path = T8_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("previews", [])
    temporary = T8_ROOT.with_name(T8_ROOT.name + ".optimized")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    updated = []
    try:
        for index, entry in enumerate(entries, 1):
            source = T8_ROOT / str(entry["file"])
            if not source.is_file() or sha256(source) != entry.get("sha256"):
                raise GifOptimizationError(f"T8 source/manifest mismatch: {entry.get('case_id')}")
            encoded = temporary / f".{index:03d}.gif"
            encode(source, encoded, ffmpeg, fps=fps, width=width, colors=colors)
            digest = sha256(encoded)
            final = temporary / f"{digest}.gif"
            encoded.replace(final)
            updated.append({**entry, "file": final.name, "sha256": digest, "bytes": final.stat().st_size})
        manifest["encoding"] = {
            "format": "gif", "fps": fps, "max_width": width, "max_colors": colors, "loop": True,
        }
        manifest["previews"] = updated
        manifest["preview_count"] = len(updated)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        notice = T8_ROOT / "NOTICE.md"
        if notice.is_file():
            shutil.copy2(notice, temporary / notice.name)
        backup = T8_ROOT.with_name(T8_ROOT.name + ".before-optimization")
        if backup.exists():
            shutil.rmtree(backup)
        T8_ROOT.replace(backup)
        temporary.replace(T8_ROOT)
        shutil.rmtree(backup)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return manifest


def optimize_official(ffmpeg: str, *, fps: int, width: int, colors: int) -> dict[str, Any]:
    source_entries = []
    temporary = OFFICIAL_ROOT.with_name(OFFICIAL_ROOT.name + ".optimized")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        for source in sorted(OFFICIAL_ROOT.glob("*.gif")):
            target = temporary / source.name
            source_hash = sha256(source)
            encode(source, target, ffmpeg, fps=fps, width=width, colors=colors)
            source_entries.append({
                "file": source.name,
                "source_sha256": source_hash,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            })
        manifest = {
            "schema_version": "t8-bundled-official-h3-previews/v1",
            "authority": "MiniMax-AI",
            "source_commit": OFFICIAL_COMMIT,
            "preview_count": len(source_entries),
            "encoding": {
                "format": "gif", "fps": fps, "max_width": width, "max_colors": colors, "loop": True,
            },
            "policy": "Official GIFs are human UI previews only and are never sent to an LLM.",
            "previews": source_entries,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        notice = OFFICIAL_ROOT / "NOTICE.md"
        if notice.is_file():
            shutil.copy2(notice, temporary / notice.name)
        backup = OFFICIAL_ROOT.with_name(OFFICIAL_ROOT.name + ".before-optimization")
        if backup.exists():
            shutil.rmtree(backup)
        OFFICIAL_ROOT.replace(backup)
        temporary.replace(OFFICIAL_ROOT)
        shutil.rmtree(backup)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically optimize all bundled preview GIFs.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--max-width", type=int, default=DEFAULT_MAX_WIDTH)
    parser.add_argument("--colors", type=int, default=DEFAULT_COLORS)
    args = parser.parse_args()
    if not 2 <= args.fps <= 8 or not 200 <= args.max_width <= 400 or not 32 <= args.colors <= 96:
        parser.error("limits: fps 2-8, max-width 200-400, colors 32-96")
    ffmpeg = encoder(args.ffmpeg)
    t8 = optimize_t8(ffmpeg, fps=args.fps, width=args.max_width, colors=args.colors)
    official = optimize_official(ffmpeg, fps=args.fps, width=args.max_width, colors=args.colors)
    report = {
        "t8_count": t8["preview_count"],
        "t8_bytes": sum(int(item["bytes"]) for item in t8["previews"]),
        "official_count": official["preview_count"],
        "official_bytes": sum(int(item["bytes"]) for item in official["previews"]),
        "encoding": t8["encoding"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
