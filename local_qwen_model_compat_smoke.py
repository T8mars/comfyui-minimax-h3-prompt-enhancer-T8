from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_DIR))

from live_smoke import IMAGE_CODE, make_image_fixture
from comfy_api.latest import VideoFromFile
from workshop_live_smoke import (
    EARLY_VIDEO_CODE,
    LATE_VIDEO_CODE,
    make_complete_video_fixture,
)


SPEC = importlib.util.spec_from_file_location(
    "t8_local_qwen_compat_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
provider_module = sys.modules[f"{SPEC.name}.local_qwen_provider"]
runtime_module = sys.modules[f"{SPEC.name}.local_qwen_runtime"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(model_filename: str, *, include_diagnostic_outputs: bool = False) -> dict:
    model_path = runtime_module.resolve_model_path(model_filename, label="local Qwen model")
    mmproj_path = runtime_module.resolve_model_path(
        runtime_module.DEFAULT_MMPROJ_FILENAME,
        label="local Qwen vision projector",
    )
    expected_model = runtime_module.KNOWN_MODEL_FILES.get(model_filename)
    model_sha256 = sha256_file(model_path)
    mmproj_sha256 = sha256_file(mmproj_path)
    if expected_model is not None and (
        model_path.stat().st_size != expected_model[0] or model_sha256 != expected_model[1]
    ):
        raise RuntimeError("Selected model failed pinned size/SHA256 verification.")
    if (
        mmproj_path.stat().st_size != runtime_module.DEFAULT_MMPROJ_SIZE
        or mmproj_sha256 != runtime_module.DEFAULT_MMPROJ_SHA256
    ):
        raise RuntimeError("Vision projector failed pinned size/SHA256 verification.")

    settings = provider_module.settings_from_values(
        local_model=model_filename,
        local_mmproj=runtime_module.DEFAULT_MMPROJ_FILENAME,
        local_context_size=32768,
        local_max_tokens=1024,
        local_think_mode=runtime_module.LOCAL_THINK_OFF,
        local_unload_policy=runtime_module.LOCAL_UNLOAD_AFTER_RUN,
        local_comfy_memory_policy=runtime_module.LOCAL_RELEASE_COMFY_AUTO,
    )
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="t8_qwen_compat_") as directory:
        video_path = Path(directory) / "visual_timeline.mp4"
        make_complete_video_fixture(video_path)
        visual_parts, media_report = provider_module.build_local_multimodal_parts(
            [
                {"kind": "image", "label": "compatibility_test_image", "value": make_image_fixture()},
                {
                    "kind": "video",
                    "label": "compatibility_test_video",
                    "value": VideoFromFile(str(video_path)),
                },
            ],
            settings,
            max_visual_parts=2,
        )
        with provider_module.LocalQwenProvider(settings, vision=True) as local_provider:
            text_output = local_provider.complete(
                [
                    {"role": "system", "content": "Follow the requested output literally and concisely."},
                    {"role": "user", "content": "Reply with the exact token T8-TEXT-OK."},
                ],
                temperature=0.0,
                seed=2026082001,
                max_tokens=256,
            )
            vision_output = local_provider.complete(
                [
                    {
                        "role": "user",
                        "content": visual_parts
                        + [
                            {
                                "type": "text",
                                "text": (
                                    "Transcribe all three visible codes exactly. Describe the image's left and right "
                                    "shapes and colors. Then describe the video's early blue-square motion and late "
                                    "green-circle motion in temporal order. Answer concisely in English."
                                ),
                            }
                        ],
                    }
                ],
                temperature=0.0,
                seed=2026082002,
                max_tokens=512,
            )

    lowered = vision_output.casefold()
    checks = {
        "text_exact_token": "t8-text-ok" in text_output.casefold(),
        "vision_exact_ocr": IMAGE_CODE.casefold() in lowered,
        "vision_left_magenta_triangle": all(term in lowered for term in ("magenta", "triangle", "left")),
        "vision_right_yellow_circle": all(term in lowered for term in ("yellow", "circle", "right")),
        "video_early_exact_ocr": EARLY_VIDEO_CODE.casefold() in lowered,
        "video_late_exact_ocr": LATE_VIDEO_CODE.casefold() in lowered,
        "video_early_blue_square_left_to_right": (
            "blue" in lowered
            and "square" in lowered
            and (
                any(term in lowered for term in ("left to right", "left-to-right", "rightward"))
                or bool(re.search(r"from the left.{0,80}to the right", lowered))
            )
        ),
        "video_late_green_circle_downward": (
            "green" in lowered
            and "circle" in lowered
            and any(term in lowered for term in ("top to bottom", "top-to-bottom", "downward", "down"))
        ),
        "video_temporal_order": lowered.find(EARLY_VIDEO_CODE.casefold()) < lowered.find(LATE_VIDEO_CODE.casefold()),
        "single_image_sent": media_report.get("image_count") == 1,
        "single_video_sent": media_report.get("video_count") == 1,
        "audio_not_analyzed": media_report.get("audio_analyzed") is False,
    }
    report = {
        "schema_version": 1,
        "model": {
            "filename": model_filename,
            "size": model_path.stat().st_size,
            "sha256": model_sha256,
        },
        "mmproj": {
            "filename": mmproj_path.name,
            "size": mmproj_path.stat().st_size,
            "sha256": mmproj_sha256,
        },
        "runtime": "llama.cpp local provider",
        "checks": checks,
        "passed": all(checks.values()),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "text_output_sha256": sha256_text(text_output),
        "vision_output_sha256": sha256_text(vision_output),
        "privacy": "Outputs and Base64 image bytes are not stored in this report.",
    }
    if include_diagnostic_outputs:
        report["diagnostic_outputs"] = {
            "text": text_output,
            "vision": vision_output,
        }
        report["privacy"] = "Synthetic-fixture outputs included by explicit diagnostic flag."
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify one installed local Qwen GGUF with the pinned text and vision paths."
    )
    parser.add_argument("--model", required=True, help="Installed GGUF filename.")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--confirm-local-large-model",
        action="store_true",
        help="Acknowledge loading the local 27B model for real inference.",
    )
    parser.add_argument(
        "--diagnostic-output",
        action="store_true",
        help="Print synthetic-fixture model outputs for validator diagnosis; never use with private inputs.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_local_large_model:
        parser.error("Refusing the real inference run without --confirm-local-large-model.")
    report = run(
        str(args.model),
        include_diagnostic_outputs=bool(args.diagnostic_output),
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".part")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
