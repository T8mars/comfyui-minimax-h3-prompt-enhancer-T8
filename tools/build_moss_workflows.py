"""Generate only MOSS examples; no model calls and no earlier workflow rewrites."""
import argparse
import copy
import json
from pathlib import Path

from build_example_workflows import _workflow, _write_thumbnail

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "prompt", "operation", "output_format", "width", "height", "output_language", "api_mode",
    "locked_text", "max_output_chars", "max_corrections", "llm_max_tokens", "draft_json",
    "ai_workshop_model", "custom_model", "openai_base_url", "seed", "control_after_generate",
    "local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
    "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy", "recovery_slot", "recovery_action",
)
VALUES = ["", "生成 / Generate", "AUTO / 自动", 1024, 1024, "按需求（默认英文）/ Auto", "贞贞平价小屋（推荐）",
          "", 0, 1, 16384, "", "gemini-3.5-flash", "qwen/qwen3.8-flash-next", "", 0, "randomize",
          "Qwen3.8-27B-Q4_K_M.gguf", "AUTO（自动匹配）", 32768, 16384, "关闭（推荐，速度优先）", "medium",
          "执行后卸载（推荐）", "AUTO（显存不足时释放）", "", "normal"]
DRAFT = {"width": 1536, "height": 1024, "bbox_coord_space": "abs", "bbox_format": "xyxy",
         "summary": {"caption": "A calm ivory cup campaign, with green Chinese copy."}, "items": [
             {"label": "object", "caption": "A single ivory ceramic cup.", "bbox": [176, 224, 800, 864]},
             {"label": "text", "caption": "Dark green large headline.", "text": "春日来信", "bbox": [928, 272, 1408, 448]}]}
STEMS = ("moss_caption_example", "moss_layout_example", "moss_spatial_example", "moss_compile_only_example", "moss_compile_error_example")


def generate():
    result = {}
    cases = {
        "moss_caption_example": {"prompt": "One ivory cup on a plain warm-gray table. Soft window light, natural photograph, no other objects and no visible text.", "output_format": "Caption / 自然描述"},
        "moss_layout_example": {"prompt": "极简陶瓷海报：左侧只有一只奶白色陶瓷杯，右侧深绿大标题春日来信，不出现其他文案。", "output_format": "Layout / 空间排版", "width": 1536, "height": 1024, "locked_text": "春日来信"},
        "moss_spatial_example": {"prompt": "Exactly two toy robots: red on the left foreground, blue on the right background. One low fence partly occludes both robots' feet. No text, no extra robots.", "output_format": "Layout / 空间排版", "width": 1536, "height": 1024},
        "moss_compile_only_example": {"operation": "仅校验编译 / Compile only", "draft_json": json.dumps(DRAFT, ensure_ascii=False, indent=2)},
        "moss_compile_error_example": {"operation": "仅校验编译 / Compile only", "draft_json": ""},
    }
    broken = copy.deepcopy(DRAFT)
    broken["items"][0]["bbox"][2] = 1600
    cases["moss_compile_error_example"]["draft_json"] = json.dumps(broken, ensure_ascii=False, indent=2)
    for stem, overrides in cases.items():
        values = dict(zip(NAMES, copy.deepcopy(VALUES)))
        values.update(overrides)
        main = dict(id=1, type="MOSSImagePromptEnhancerT8", pos=[0, 0], size=[540, 760], flags={}, order=0, mode=0,
                    title="MOSS · " + ("预期失败 / Expected failure" if "error" in stem else stem.removeprefix("moss_")),
                    inputs=[{"name": name, "type": kind, "link": None, "shape": 7} for name, kind in
                            (("api_key", "STRING"), ("provider_config", "T8_LLM_PROVIDER_CONFIG"))],
                    outputs=[{"name": name, "type": kind, "links": links} for name, kind, links in
                             (("positive_prompt", "STRING", [1]), ("width", "INT", None), ("height", "INT", None),
                              ("resolved_format", "STRING", None), ("draft_json", "STRING", None), ("report_json", "STRING", None))],
                    properties={"Node name for S&R": "MOSSImagePromptEnhancerT8", "t8_moss_widgets_v1": copy.deepcopy(values)},
                    widgets_values=list(values.values()), widgets_values_named=copy.deepcopy(values))
        show = dict(id=2, type="T8ShowText", pos=[620, 0], size=[520, 500], flags={}, order=1, mode=0,
                    inputs=[{"name": "text", "type": "STRING", "link": 1}],
                    outputs=[{"name": "text", "type": "STRING", "links": None}],
                    properties={"Node name for S&R": "T8ShowText"}, widgets_values=[])
        key = dict(id=3, type="T8PromptText", pos=[-420, 0], size=[380, 200], flags={}, order=0, mode=0,
                   title="API Key（本地无需；推荐环境变量；勿分享密钥）", inputs=[],
                   outputs=[{"name": "text", "type": "STRING", "links": [2]}],
                   properties={"Node name for S&R": "T8PromptText"}, widgets_values=[""])
        main["inputs"][0]["link"] = 2
        result[stem] = _workflow(stem, [main, show, key], [[1, 1, 0, 2, 0, "STRING"], [2, 3, 0, 1, 0, "STRING"]])
    return result


def check():
    for stem, expected in generate().items():
        path = ROOT / "example_workflows" / (stem + ".json")
        assert json.loads(path.read_text(encoding="utf-8")) == expected, stem
        assert path.with_suffix(".jpg").is_file(), stem
        main = expected["nodes"][0]
        assert len(main["widgets_values"]) == len(NAMES) == 27
        assert "api_key" not in main["widgets_values_named"]
        assert expected["nodes"][2]["widgets_values"] == [""]
        assert "sk-" not in path.read_text(encoding="utf-8")
    print("MOSS examples: five workflows, 27 named values, blank credentials, own thumbnails; old examples untouched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        for stem, workflow in generate().items():
            path = ROOT / "example_workflows" / (stem + ".json")
            path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _write_thumbnail(path.with_suffix(".jpg"), "MOSS PROMPT AUTHORING", stem, "Caption / Layout native compilation", "Workflow diagram only | No rendered image | Blank API key")
    check()
