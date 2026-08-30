from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping, Sequence


SCHEMA = "t8-film-render-acceptance/v1"
MODEL_FAMILIES = {"MiniMax H3", "Seedance 2.0"}
RUBRIC_FIELDS = (
    "identity_continuity",
    "causality_visibility",
    "performance_readability",
    "world_rule_compliance",
    "overall_watchability",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False, "reason": "ffprobe_not_installed"}
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height,avg_frame_rate",
        "-of", "json", str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return {"available": True, "valid": False, "error_type": type(error).__name__}
    if not isinstance(payload, Mapping):
        return {"available": True, "valid": False, "error_type": "InvalidProbePayload"}
    duration = 0.0
    try:
        duration = float(payload.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        pass
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    return {
        "available": True,
        "valid": duration > 0 and any(item.get("codec_type") == "video" for item in streams if isinstance(item, Mapping)),
        "duration_seconds": round(duration, 3),
        "streams": streams,
    }


def _human_review_errors(review: Any) -> list[str]:
    if not isinstance(review, Mapping):
        return ["human_review_missing"]
    errors = []
    for field in RUBRIC_FIELDS:
        value = review.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            errors.append(f"invalid_score:{field}")
    if not str(review.get("reviewer") or "").strip():
        errors.append("reviewer_missing")
    if not str(review.get("evidence_notes") or "").strip():
        errors.append("evidence_notes_missing")
    return errors


def evaluate_manifest(manifest_path: Path, *, require_ffprobe: bool = False) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA:
        raise ValueError(f"Unsupported render-acceptance schema: {payload.get('schema_version')}")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Render-acceptance manifest must contain at least one case.")
    results = []
    for position, item in enumerate(raw_cases, 1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Case {position} is not an object.")
        family = str(item.get("model_family") or "").strip()
        errors = []
        if family not in MODEL_FAMILIES:
            errors.append("unsupported_model_family")
        raw_path = Path(str(item.get("video_path") or ""))
        video_path = raw_path if raw_path.is_absolute() else manifest_path.parent / raw_path
        if not video_path.is_file() or video_path.stat().st_size < 1:
            errors.append("video_missing_or_empty")
            probe = {"available": bool(shutil.which("ffprobe")), "valid": False}
            sha256 = ""
            byte_count = 0
        else:
            probe = _probe_video(video_path)
            sha256 = _sha256(video_path)
            byte_count = video_path.stat().st_size
            if require_ffprobe and not probe.get("available"):
                errors.append("ffprobe_required")
            if probe.get("available") and not probe.get("valid"):
                errors.append("video_probe_failed")
            expected_duration = item.get("expected_duration_seconds")
            if probe.get("valid") and expected_duration is not None:
                try:
                    delta = abs(float(probe["duration_seconds"]) - float(expected_duration))
                    tolerance = max(0.5, float(expected_duration) * 0.05)
                    if delta > tolerance:
                        errors.append("duration_out_of_tolerance")
                except (TypeError, ValueError):
                    errors.append("expected_duration_invalid")
        errors.extend(_human_review_errors(item.get("human_review")))
        review = item.get("human_review") if isinstance(item.get("human_review"), Mapping) else {}
        scores = [
            review.get(field)
            for field in RUBRIC_FIELDS
            if isinstance(review.get(field), int) and not isinstance(review.get(field), bool)
        ]
        results.append({
            "case_id": str(item.get("case_id") or f"case-{position}"),
            "model_family": family,
            "variant": str(item.get("variant") or "enhanced"),
            "video_sha256": sha256,
            "video_bytes": byte_count,
            "probe": probe,
            "human_score_average": round(sum(scores) / len(scores), 2) if len(scores) == len(RUBRIC_FIELDS) else None,
            "errors": errors,
            "passed": not errors,
        })
    return {
        "schema_version": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": manifest_path.name,
        "video_content_stored": False,
        "credentials_stored": False,
        "case_count": len(results),
        "passed": all(item["passed"] for item in results),
        "results": results,
        "scope_note": "File/probe evidence plus named human rubric; this tool does not claim to generate or artistically judge video by itself.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate actual MiniMax H3 / Seedance 2.0 render evidence.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ffprobe", action="store_true")
    args = parser.parse_args(argv)
    report = evaluate_manifest(args.manifest, require_ffprobe=args.require_ffprobe)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")  # noqa: T201
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
