import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import av
from PIL import Image, ImageDraw


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_DIR))

from comfy_api.latest import VideoFromFile
from live_smoke import IMAGE_CODE, _font, make_image_fixture


SPEC = importlib.util.spec_from_file_location(
    "t8_workshop_live_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
h3 = sys.modules[f"{SPEC.name}.nodes"]
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]

EARLY_VIDEO_CODE = "BLUE-LINE-24"
LATE_VIDEO_CODE = "GREEN-DROP-91"
FPS = 12
VIDEO_SECONDS = 4
LATE_PHASE_SECOND = 2


def make_complete_video_fixture(path: Path):
    width, height = 640, 360
    with av.open(str(path), "w") as container:
        stream = container.add_stream("h264", rate=FPS)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        for frame_index in range(FPS * VIDEO_SECONDS):
            second = frame_index / FPS
            if second < LATE_PHASE_SECOND:
                image = Image.new("RGB", (width, height), (238, 242, 247))
                draw = ImageDraw.Draw(image)
                progress = frame_index / max(FPS * LATE_PHASE_SECOND - 1, 1)
                x = round(45 + progress * 470)
                draw.rectangle((x, 135, x + 82, 217), fill=(25, 95, 235), outline=(5, 30, 80), width=5)
                draw.rectangle((92, 18, 548, 90), fill=(10, 25, 65))
                draw.text((120, 28), EARLY_VIDEO_CODE, fill=(255, 255, 255), font=_font(46))
                draw.text((24, 310), "BLUE SQUARE MOVES LEFT TO RIGHT", fill=(15, 45, 100), font=_font(24))
            else:
                image = Image.new("RGB", (width, height), (30, 36, 42))
                draw = ImageDraw.Draw(image)
                late_frame = frame_index - FPS * LATE_PHASE_SECOND
                progress = late_frame / max(FPS * (VIDEO_SECONDS - LATE_PHASE_SECOND) - 1, 1)
                y = round(45 + progress * 220)
                draw.ellipse((279, y, 361, y + 82), fill=(40, 215, 85), outline=(5, 75, 25), width=5)
                draw.rectangle((72, 18, 568, 90), fill=(235, 240, 245))
                draw.text((94, 28), LATE_VIDEO_CODE, fill=(5, 70, 25), font=_font(46))
                draw.text((24, 310), "GREEN CIRCLE MOVES TOP TO BOTTOM", fill=(165, 255, 185), font=_font(24))

            frame = av.VideoFrame.from_image(image)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def evaluate_result(prompt: str) -> list[str]:
    lowered = prompt.lower()
    failures = []
    checks = {
        IMAGE_CODE.lower(): f"missing image code {IMAGE_CODE}",
        EARLY_VIDEO_CODE.lower(): f"missing early video code {EARLY_VIDEO_CODE}",
        LATE_VIDEO_CODE.lower(): f"missing late video code {LATE_VIDEO_CODE}",
        "blue square": "missing early blue square",
        "green circle": "missing late green circle",
    }
    for needle, message in checks.items():
        if needle not in lowered:
            failures.append(message)
    if not any(term in lowered for term in ("magenta triangle", "pink triangle", "purple triangle")):
        failures.append("missing image magenta triangle")
    if not any(term in lowered for term in ("yellow circle", "gold circle", "golden circle")):
        failures.append("missing image yellow circle")
    if not any(term in lowered for term in ("left to right", "left-to-right", "from left to right")):
        failures.append("missing early left-to-right motion")
    if not any(term in lowered for term in ("top to bottom", "top-to-bottom", "downward", "descends")):
        failures.append("missing late downward motion")
    early_position = lowered.find(EARLY_VIDEO_CODE.lower())
    late_position = lowered.find(LATE_VIDEO_CODE.lower())
    if early_position < 0 or late_position < 0 or early_position >= late_position:
        failures.append("complete video phases are not described in temporal order")
    return failures


def run_paid_smoke(confirm_paid: bool = False) -> dict[str, str]:
    if not confirm_paid:
        raise RuntimeError("Refusing to call paid AI Workshop endpoints without explicit confirmation.")
    if not os.environ.get("T8STAR_API_KEY", "").strip():
        raise RuntimeError("T8STAR_API_KEY is not set in this process.")

    with tempfile.TemporaryDirectory(prefix="t8_workshop_smoke_") as directory:
        video_path = Path(directory) / "complete_four_second_fixture.mp4"
        make_complete_video_fixture(video_path)

        common_prompt = (
            "Inspect the attached image and the complete four-second video, including the distinct second phase that "
            "begins halfway through. Transcribe every visible alphanumeric code exactly. Describe both image shapes and "
            "colors, then preserve the video's early and late shapes, colors, movement directions, and temporal order."
        )
        h3_result = h3.enhance_prompt(
            prompt=common_prompt,
            task_type="Ref2VA",
            duration_seconds=10,
            rewrite_mode="strict",
            output_language="English",
            official_skill_profile=h3.STRICT_SKILL_PROFILE,
            reference_images={"reference_image_0": make_image_fixture()},
            reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
            constraints="Do not omit, alter, translate, or reverse any visible fixture code or temporal phase.",
            api_mode=h3.AI_WORKSHOP_API_MODE,
            ai_workshop_model=h3.AI_WORKSHOP_DEFAULT_MODEL,
        )

        seedance20_result = seedance20.enhance_seedance20_prompt(
            prompt=common_prompt,
            task_intent="MultiRef",
            complexity_mode="复杂分镜式",
            duration_seconds="10",
            shot_count="3",
            rewrite_mode="strict",
            output_detail="详细",
            output_language="English",
            reference_images={"reference_image_0": make_image_fixture()},
            reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
            reference_roles="@Image 1 supplies appearance; @Video 1 supplies the complete temporal action and cut order.",
            constraints="Do not omit, alter, translate, or reverse any visible fixture code or temporal phase.",
            api_mode=seedance20.AI_WORKSHOP_API_MODE,
            ai_workshop_model=seedance20.CUSTOM_MODEL_OPTION,
            custom_model=seedance20.AI_WORKSHOP_DEFAULT_MODEL,
        )

    failures = []
    for node_name, output in (("MiniMax-H3", h3_result), ("Seedance 2.0", seedance20_result)):
        failures.extend(f"{node_name}: {message}" for message in evaluate_result(output))
    if failures:
        raise RuntimeError(
            "AI Workshop multimodal smoke test failed: "
            + "; ".join(failures)
            + "\n\nMiniMax-H3 output:\n"
            + h3_result
            + "\n\nSeedance 2.0 output:\n"
            + seedance20_result
        )
    return {"MiniMax-H3": h3_result, "Seedance 2.0": seedance20_result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Paid AI Workshop text+image+complete-video capability test for both prompt enhancer nodes."
    )
    parser.add_argument(
        "--confirm-paid",
        action="store_true",
        help="Acknowledge two potentially billable multimodal Chat Completions requests.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_paid:
        parser.error("Refusing to call paid endpoints without --confirm-paid.")
    results = run_paid_smoke(confirm_paid=True)
    print("AI_WORKSHOP_LIVE_SMOKE=PASS")
    for node_name, output in results.items():
        print(f"\n[{node_name}]\n{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
