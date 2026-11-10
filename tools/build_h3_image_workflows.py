"""Build two H3 Image prompt-only examples and original geometric references."""
import argparse
import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw
from build_example_workflows import _workflow, _write_thumbnail

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["prompt", "task_type", "aspect_ratio", "target_words", "api_mode", "locked_text",
         "max_corrections", "llm_max_tokens", "ai_workshop_model", "custom_model", "openai_base_url", "seed",
         "local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
         "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy", "recovery_slot", "recovery_action"]
DEFAULTS = ["", "文生图 / Text to image", "auto", 0, "贞贞平价小屋（推荐）", "", 1, 16384,
            "gemini-3.5-flash", "qwen/qwen3.8-flash-next", "", 0, "Qwen3.8-27B-Q4_K_M.gguf", "AUTO（自动匹配）",
            32768, 16384, "关闭（推荐，速度优先）", "medium", "执行后卸载（推荐）", "AUTO（显存不足时释放）", "", "normal"]


def node(number, kind, position, size, **kwargs):
    return dict(id=number, type=kind, pos=position, size=size, flags={}, order=number - 1, mode=0,
                properties={"Node name for S&R": kind}, inputs=[], outputs=[], widgets_values=[], **kwargs)


def generate():
    result = {}
    for mode in ("t2i", "edit"):
        values = dict(zip(NAMES, copy.deepcopy(DEFAULTS)))
        values.update(prompt="做一张克制的中文咖啡海报：左侧一只白陶杯，右侧标题为‘慢一点，刚刚好’，米白背景，不添加其他文字。",
                      locked_text="慢一点，刚刚好", aspect_ratio="4:3")
        if mode == "edit":
            values.update(task_type="图像编辑 / Image edit", aspect_ratio="auto", locked_text="",
                          prompt="保持图1的构图与右侧对象，把左侧对象改用图2面积最大的色块颜色，不增加其他对象或文字。")
        main = node(1, "MiniMaxH3ImagePromptEnhancerT8", [500, 60], [570, 570])
        main["properties"]["t8_h3_image_widgets_v1"] = copy.deepcopy(values)
        main["widgets_values"] = list(values.values()); main["widgets_values_named"] = copy.deepcopy(values)
        main["inputs"] = [{"name": "api_key", "type": "STRING", "link": 2, "shape": 7},
                          {"name": "provider_config", "type": "T8_LLM_PROVIDER_CONFIG", "link": None, "shape": 7}]
        main["outputs"] = [{"name": name, "type": "STRING", "links": [1] if i == 0 else None} for i, name in
                           enumerate(("expanded_prompt", "aspect_ratio", "official_json", "report_json"))]
        preview = node(2, "T8ShowText", [1140, 60], [570, 570])
        preview["inputs"] = [{"name": "text", "type": "STRING", "link": 1}]
        preview["outputs"] = [{"name": "text", "type": "STRING", "links": None}]
        key = node(3, "T8PromptText", [20, 60], [400, 170], title="API Key（本地无需；勿分享填写后的工作流）")
        key["widgets_values"] = [""]; key["outputs"] = [{"name": "text", "type": "STRING", "links": [2]}]
        nodes = [main, preview, key]
        links = [[1, 1, 0, 2, 0, "STRING"], [2, 3, 0, 1, 0, "STRING"]]
        if mode == "edit":
            for i, filename in enumerate(("h3_image_reference_canvas.png", "h3_image_reference_palette.png")):
                picture = node(i + 4, "LoadImage", [20, 300 + i * 360], [400, 310], title=f"Picture {i + 1} · 上传随附示例图或自己的图")
                picture["widgets_values"] = [filename, "image"]
                picture["outputs"] = [{"name": "IMAGE", "type": "IMAGE", "links": [i + 3]}, {"name": "MASK", "type": "MASK", "links": None}]
                main["inputs"].append({"name": f"reference_images.reference_image_{i}", "type": "IMAGE", "link": i + 3, "shape": 7})
                links.append([i + 3, i + 4, 0, 1, i + 2, "IMAGE"]); nodes.append(picture)
        note = node(6, "Note", [500, 700], [570, 235])
        note["widgets_values"] = ["仅扩写提示词，不生成图片。expanded_prompt接下游H3正向；原图仍须按Picture编号接下游编辑。\n目标英文词数0=官方自动，字数不是Token；官方英文描述保留中文画面文案。\n图像编辑示例图在example_workflows/h3_image_reference_*.png，请先上传到LoadImage。\n本地选择已安装的GGUF与匹配mmproj；共享provider_config优先。详细说明见docs/h3-image.md。"]
        nodes.append(note)
        stem = f"h3_image_{mode}_example"
        result[stem] = _workflow(stem, nodes, links)
    return result


def references(directory):
    canvas = Image.new("RGB", (640, 480), "#f4eedf"); draw = ImageDraw.Draw(canvas)
    draw.ellipse((70, 140, 270, 340), fill="#ce343a")
    draw.rectangle((370, 140, 570, 340), fill="#2867c9")
    canvas.save(directory / "h3_image_reference_canvas.png")
    palette = Image.new("RGB", (480, 640), "#8b3db8"); draw = ImageDraw.Draw(palette)
    draw.rectangle((340, 490, 430, 590), fill="#ddb447")
    palette.save(directory / "h3_image_reference_palette.png")


STEMS = ("h3_image_t2i_example", "h3_image_edit_example")


def check():
    directory = ROOT / "example_workflows"
    for stem, expected in generate().items():
        assert json.loads((directory / (stem + ".json")).read_text(encoding="utf-8")) == expected, stem
        assert (directory / (stem + ".jpg")).is_file(), stem
    for name in ("canvas", "palette"):
        with Image.open(directory / f"h3_image_reference_{name}.png") as img:
            assert img.size == ((640, 480) if name == "canvas" else (480, 640))
    print("H3 Image: two workflows, 22 canonical fields, original geometry references, blank credentials.")


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true")
    args = parser.parse_args(); directory = ROOT / "example_workflows"
    for stem, workflow in generate().items():
        path = directory / (stem + ".json")
        if args.check:
            assert json.loads(path.read_text(encoding="utf-8")) == workflow, stem
            assert path.with_suffix(".jpg").is_file(), stem
        else:
            path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _write_thumbnail(path.with_suffix(".jpg"), "H3 IMAGE PROMPT EXPANSION", stem, "Official T2I / Edit prompt contracts", "Workflow only | English prose, original visible text | No image generation")
    if not args.check: references(directory)
    check()


if __name__ == "__main__": main()
