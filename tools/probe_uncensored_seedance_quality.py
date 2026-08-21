from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = ROOT.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(ROOT))

import local_qwen_live_smoke as smoke
from comfy_api.latest import VideoFromFile


DEFAULT_MODEL = "qwen3.8-27b-uncensored-fp8-q4_k_m.gguf"
DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "local_qwen_uncensored_seedance_probe.json"


def run(model: str) -> dict:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="t8_seedance_diag_") as directory:
        video_path = Path(directory) / "visual.mp4"
        smoke.make_complete_video_fixture(video_path)
        prompt = (
            "Inspect the attached image and every ordered timestamped video sample. Transcribe every visible "
            "alphanumeric code exactly. Describe both image shapes and colors, then preserve the video's early "
            "and late shapes, colors, movement directions, hard transition, and temporal order."
        )
        result = smoke.seedance20.enhance_seedance20_prompt(
            prompt=prompt,
            task_intent="MultiRef",
            complexity_mode="复杂分镜式",
            duration_seconds="10",
            shot_count="3",
            rewrite_mode="strict",
            output_detail="详细",
            output_language="English",
            reference_images={"reference_image_0": smoke.make_image_fixture()},
            reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
            reference_roles="@Image 1 supplies appearance; @Video 1 supplies sampled temporal action and order.",
            constraints="Do not omit, alter, translate, or reverse any visible code or temporal phase.",
            seed=2026081905,
            api_mode=smoke.local_provider.LOCAL_QWEN_API_MODE,
            local_model=model,
            local_context_size=32768,
            local_max_tokens=4096,
            local_think_mode=smoke.local_runtime.LOCAL_THINK_OFF,
            local_reasoning_effort="medium",
            local_unload_policy=smoke.local_runtime.LOCAL_UNLOAD_AFTER_RUN,
            local_comfy_memory_policy=smoke.local_runtime.LOCAL_RELEASE_COMFY_AUTO,
            local_video_sample_fps=2.0,
        )
    early = result.casefold().find(smoke.EARLY_VIDEO_CODE.casefold())
    late = result.casefold().find(smoke.LATE_VIDEO_CODE.casefold())
    return {
        "schema_version": "t8-local-qwen-seedance-probe/v1",
        "model": model,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "output_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
        "output_characters": len(result),
        "early_code_first_position": early,
        "late_code_first_position": late,
        "evaluation_failures": smoke.evaluate_visual_result(result),
        "synthetic_output": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({key: value for key, value in report.items() if key != "synthetic_output"}, indent=2))
    return 0 if not report["evaluation_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
