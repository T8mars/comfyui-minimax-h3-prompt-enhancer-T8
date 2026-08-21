from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "example_workflows"
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
)
CARDS = {
    "basic_workflow_multi_task_connections": (
        "三节点连接示例", "H3 · Seedance 2.0 · Music 3", (42, 102, 135),
    ),
    "minimax_h3_prompt_enhancer_example": (
        "MiniMax H3 提示词增强", "官方 Skill · 云端 / 本地 Qwen", (76, 61, 145),
    ),
    "seedance20_prompt_enhancer_example": (
        "Seedance 2.0 提示词增强", "图像 / 视频分析 · 多渠道 LLM", (22, 118, 105),
    ),
    "music3_prompt_lyrics_enhancer_example": (
        "MiniMax Music 3", "歌词 + 官方结构化 Music Caption", (145, 73, 88),
    ),
}


def font(size: int):
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def make_card(title: str, subtitle: str, accent: tuple[int, int, int]) -> Image.Image:
    width, height = 640, 360
    image = Image.new("RGB", (width, height), (20, 21, 26))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        blend = x / width
        color = tuple(round(20 * (1 - blend) + channel * 0.42 * blend) for channel in accent)
        draw.line((x, 0, x, height), fill=color)
    draw.rounded_rectangle((44, 48, 596, 312), radius=22, fill=(23, 25, 31), outline=(115, 125, 155), width=2)
    draw.rounded_rectangle((66, 74, 205, 105), radius=15, fill=accent)
    draw.text((85, 79), "T8 · ComfyUI", font=font(16), fill=(255, 255, 255))
    draw.text((66, 139), title, font=font(30), fill=(246, 247, 252))
    draw.text((68, 197), subtitle, font=font(19), fill=(190, 198, 218))
    draw.line((68, 246, 526, 246), fill=accent, width=4)
    draw.text((68, 267), "Prompt Enhancer Workflow", font=font(15), fill=(145, 153, 177))
    return image


def main() -> int:
    for stem, (title, subtitle, accent) in CARDS.items():
        workflow = WORKFLOWS / f"{stem}.json"
        if not workflow.is_file():
            raise FileNotFoundError(workflow)
        target = WORKFLOWS / f"{stem}.jpg"
        make_card(title, subtitle, accent).save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
