import argparse
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

import av
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))

from comfy_api.latest import VideoFromFile

SPEC = importlib.util.spec_from_file_location("minimax_h3_prompt_enhancer_nodes", PROJECT_DIR / "nodes.py")
enhancer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enhancer)

IMAGE_CODE = "MANGO-47"
VIDEO_CODE = "RIVER-83"
FPS = 24
VIDEO_SECONDS = 4


def _font(size: int):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_image_fixture() -> torch.Tensor:
    image = Image.new("RGB", (640, 360), (238, 242, 246))
    draw = ImageDraw.Draw(image)
    draw.polygon([(70, 270), (190, 55), (310, 270)], fill=(215, 30, 165), outline=(60, 10, 45), width=6)
    draw.ellipse((430, 110, 550, 230), fill=(250, 210, 20), outline=(70, 55, 5), width=6)
    draw.rectangle((185, 292, 455, 352), fill=(255, 255, 255), outline=(15, 15, 15), width=3)
    draw.text((205, 302), IMAGE_CODE, fill=(10, 10, 10), font=_font(36))
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


def make_video_fixture(path: Path):
    width, height = 640, 360
    with av.open(str(path), "w") as container:
        stream = container.add_stream("h264", rate=FPS)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        for frame_index in range(FPS * VIDEO_SECONDS):
            phase_frame = frame_index % (FPS * 2)
            image = Image.new("RGB", (width, height), (236, 240, 244) if frame_index < FPS * 2 else (32, 38, 44))
            draw = ImageDraw.Draw(image)
            draw.text((24, 20), VIDEO_CODE, fill=(20, 20, 20) if frame_index < FPS * 2 else (245, 245, 245), font=_font(32))

            progress = phase_frame / (FPS * 2 - 1)
            if frame_index < FPS * 2:
                x = round(45 + progress * 470)
                draw.rectangle((x, 135, x + 82, 217), fill=(20, 90, 235), outline=(5, 30, 80), width=5)
                draw.text((24, 310), "PHASE ONE", fill=(15, 45, 100), font=_font(28))
            else:
                y = round(55 + progress * 220)
                draw.ellipse((279, y, 361, y + 82), fill=(40, 210, 85), outline=(5, 75, 25), width=5)
                draw.text((24, 310), "PHASE TWO", fill=(160, 255, 180), font=_font(28))

            frame = av.VideoFrame.from_image(image)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def evaluate_result(prompt: str) -> list[str]:
    lowered = prompt.lower()
    detailed_match = re.search(
        r"(?ms)^detailed_description:\s*(.*?)(?=^overall_soundscape:)",
        lowered,
    )
    timeline = detailed_match.group(1) if detailed_match else ""
    failures = []
    if IMAGE_CODE.lower() not in lowered:
        failures.append(f"missing exact image code {IMAGE_CODE}")
    if VIDEO_CODE.lower() not in lowered:
        failures.append(f"missing exact video code {VIDEO_CODE}")
    if "<picture 1>" not in lowered:
        failures.append("missing <Picture 1> mapping")
    if "<video 1>" not in lowered:
        failures.append("missing <Video 1> mapping")

    if not any(term in lowered for term in ("magenta triangle", "pink triangle", "purple triangle")):
        failures.append("missing the picture's magenta triangle")
    if not any(term in lowered for term in ("yellow circle", "gold circle", "golden circle")):
        failures.append("missing the picture's yellow circle")
    if not timeline:
        failures.append("missing detailed_description timeline")

    if "blue square" not in lowered:
        failures.append("missing the source video's first-phase blue square")
    if "green circle" not in lowered:
        failures.append("missing the source video's second-phase green circle")
    if "hard cut" not in lowered:
        failures.append("missing the source video's hard cut")
    if "attribute_transfer" not in lowered:
        failures.append("missing cross-media attribute transfer analysis")

    phase_one = timeline.find("phase one")
    phase_two = timeline.find("phase two")
    if phase_one < 0 or phase_two < 0 or phase_one >= phase_two:
        failures.append("target phases are not described in temporal order")
    if not any(term in timeline for term in ("magenta triangle", "pink triangle", "purple triangle")):
        failures.append("target timeline does not transfer the picture's triangle into phase one")
    if not any(term in timeline for term in ("yellow circle", "gold circle", "golden circle")):
        failures.append("target timeline does not transfer the picture's circle into phase two")
    if not any(term in timeline for term in ("left to right", "left-to-right", "from left to right")):
        failures.append("missing the first phase's left-to-right motion")
    if not any(term in timeline for term in ("top to bottom", "top-to-bottom", "downward", "descends")):
        failures.append("missing the second phase's downward motion")
    return failures


def run_paid_smoke(confirm_paid: bool = False) -> str:
    if not confirm_paid:
        raise RuntimeError("Refusing to call the paid chat endpoint without explicit confirmation.")
    if not os.environ.get("SEEDANCE_API_KEY", "").strip():
        raise RuntimeError("SEEDANCE_API_KEY is not set in this process.")

    with tempfile.TemporaryDirectory(prefix="minimax_h3_smoke_") as directory:
        video_path = Path(directory) / "temporal_fixture.mp4"
        make_video_fixture(video_path)
        video = VideoFromFile(str(video_path))
        result = enhancer.enhance_prompt(
            prompt=(
                "Create a five-second reference-guided video. Inspect every attached asset, transcribe every visible "
                "alphanumeric code exactly, preserve the picture's observable subject layout, and follow the video "
                "reference's full two-phase motion and hard-cut order. Name each phase's shape, color, and direction."
            ),
            task_type="Ref2VA",
            duration_seconds=5,
            rewrite_mode="strict",
            description_word_target=0,
            output_language="English",
            reference_images={"reference_image_0": make_image_fixture()},
            reference_videos={"reference_video_0": video},
            constraints="Do not omit, translate, or alter visible asset codes. Do not reverse the reference video's temporal order.",
        )

    failures = evaluate_result(result)
    if failures:
        raise RuntimeError("Visual smoke test failed: " + "; ".join(failures) + "\n\nModel output:\n" + result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Paid live capability test for Seedance bytedance/doubao-seed-evolving image+video understanding."
    )
    parser.add_argument(
        "--confirm-paid",
        action="store_true",
        help="Acknowledge that this uploads generated fixtures and makes one potentially billable Chat Completions request.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_paid:
        parser.error("Refusing to call the paid chat endpoint without --confirm-paid.")

    result = run_paid_smoke(confirm_paid=True)
    print("LIVE_SMOKE_RESULT=PASS")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
