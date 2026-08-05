import argparse
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))

from comfy_api.latest import VideoFromFile

from live_smoke import IMAGE_CODE, VIDEO_CODE, make_image_fixture, make_video_fixture


SPEC = importlib.util.spec_from_file_location(
    "t8_seedance20_live_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]


def evaluate_result(prompt: str) -> list[str]:
    lowered = prompt.lower()
    failures = []
    checks = {
        IMAGE_CODE.lower(): f"missing exact image code {IMAGE_CODE}",
        VIDEO_CODE.lower(): f"missing exact video code {VIDEO_CODE}",
        "@image 1": "missing @Image 1 reference",
        "@video 1": "missing @Video 1 reference",
        "phase one": "missing the source video's Phase One",
        "phase two": "missing the source video's Phase Two",
        "hard-cut": "missing the source video's hard cut",
    }
    for needle, message in checks.items():
        if needle not in lowered:
            failures.append(message)
    if not any(term in lowered for term in ("magenta triangle", "pink triangle", "purple triangle")):
        failures.append("missing the image's magenta triangle")
    if not any(term in lowered for term in ("yellow circle", "gold circle", "golden circle")):
        failures.append("missing the image's yellow circle")

    phase_one_position = lowered.find("phase one")
    phase_two_position = lowered.find("phase two")
    if phase_one_position < 0 or phase_two_position < 0 or phase_one_position >= phase_two_position:
        failures.append("video phases are not preserved in temporal order")
    if not any(term in lowered for term in ("left to right", "left-to-right", "from left to right")):
        failures.append("missing the source video's first-phase horizontal direction")
    if not any(term in lowered for term in ("descend", "downward", "straight down", "top to bottom")):
        failures.append("missing the source video's second-phase downward direction")

    forbidden = (
        "integrated_multimodal_description",
        "overall_soundscape:",
        "non_diegetic_music:",
        "[shot 1]",
        "<picture 1>",
        "<video 1>",
    )
    for value in forbidden:
        if value in lowered:
            failures.append(f"contains MiniMax-H3 residue: {value}")
    if re.search(r"\b\d{2}:\d{2}\.\d{3}\b", prompt):
        failures.append("contains a MiniMax-H3 millisecond timestamp")
    return failures


def run_paid_smoke(confirm_paid: bool = False) -> str:
    if not confirm_paid:
        raise RuntimeError("Refusing to call the paid chat endpoint without explicit confirmation.")
    if not os.environ.get("SEEDANCE_API_KEY", "").strip():
        raise RuntimeError("SEEDANCE_API_KEY is not set in this process.")

    with tempfile.TemporaryDirectory(prefix="seedance20_smoke_") as directory:
        video_path = Path(directory) / "temporal_fixture.mp4"
        make_video_fixture(video_path)
        result = seedance20.enhance_seedance20_prompt(
            prompt=(
                "Create one coherent reference-guided video in exactly three event-ordered shots. Inspect both assets, "
                "transcribe each visible alphanumeric code exactly, preserve the image's two shapes and colors, and "
                "follow the complete video's two-phase action and hard-cut order. State each asset's role explicitly."
            ),
            task_intent="MultiRef",
            complexity_mode="复杂分镜式",
            duration_seconds="8",
            shot_count="3",
            rewrite_mode="strict",
            output_detail="详细",
            output_language="English",
            prompt_mode="官方优化",
            reference_syntax=seedance20.REFERENCE_SYNTAXES[1],
            reference_images={"reference_image_0": make_image_fixture()},
            reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
            reference_roles="@Image 1 supplies subject appearance; @Video 1 supplies motion, direction, cut order, and camera rhythm.",
            constraints=(
                "Do not omit, translate, or alter visible asset codes. Do not reverse the source video's temporal order. "
                "Do not use MiniMax-H3 fields, bracketed shot tags, or absolute shot timestamps."
            ),
            seed=20260805,
        )

    failures = evaluate_result(result)
    if failures:
        raise RuntimeError("Seedance 2.0 visual smoke test failed: " + "; ".join(failures) + "\n\nModel output:\n" + result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Paid Seedance 2.0 multimodal prompt-enhancer smoke test.")
    parser.add_argument("--confirm-paid", action="store_true", help="Confirm one paid image+video chat request.")
    args = parser.parse_args()
    result = run_paid_smoke(args.confirm_paid)
    print("Seedance 2.0 paid visual smoke test passed.\n")
    print(result)


if __name__ == "__main__":
    main()
