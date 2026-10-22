"""Build only additive MOSS authoring lessons; never call a model or alter old examples.

Run this script once to write its owned workflow/thumbnail artifacts; --check is
read-only and compares canonical JSON bytes plus pinned thumbnail SHA256 bytes.
The two reference lessons use our original CPU-drawn workflow diagrams, not user
photos. Upload those bundled JPGs with LoadImage before running either lesson.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

from build_example_workflows import _provider_node, _show_text_node, _workflow, _write_thumbnail
from build_moss_workflows import NAMES as OLD_NAMES, VALUES as OLD_VALUES
from build_strata_workflows import CONFIG_NAMES, DEFAULTS as STRATA_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import moss_authoring as authoring
import moss_authoring_bundle as bundle
import moss_authoring_contract as contract

EXAMPLES = ROOT / "example_workflows"
MAIN_NAMES = (*OLD_NAMES, "authoring_profile")
DIRECTOR_NAMES = ("brief", "profile", "width", "height", "max_output_chars", "max_corrections", "page_count",
                  "reference_mode", "descriptive_language", "locked_text", "continuity_context", "layout_context_json",
                  "preserve_layout", "llm_max_tokens", "seed", "recovery_slot", "recovery_action")
DIRECTOR_VALUES = ("", authoring.COMIC, 1256, 1672, 0, 1, 0, "independent", "Auto / 自动（Fisher默认中文）",
                   "", "", "", True, 16384, 0, "", "normal")
STEMS = ("moss_authoring_fisher_long", "moss_authoring_fisher_short", "moss_authoring_comic_single",
         "moss_authoring_comic_two_pages", "moss_authoring_fisher_independent", "moss_authoring_fisher_fusion",
         "moss_authoring_cpu_page", "moss_authoring_fixed_layout_revision")
# These verify the exact published original drawings without depending on the
# checking machine's Pillow font/JPEG encoder version. Generation is CPU-only.
THUMBNAIL_SHA256 = {
    "moss_authoring_fisher_long": "084628de8de122eb800c7db542f0ffd9e1782d426b788ec5f99fb73f4b4f2c4c",
    "moss_authoring_fisher_short": "25e863dc5c61825f22fc07f0cc82670aa2731208e8456ad8d2e1e8b6778eecd4",
    "moss_authoring_comic_single": "c8ebb7ce02d2ea8bf3ac1ce01490103239e63b5808de1c30ee8dc3d08eee420a",
    "moss_authoring_comic_two_pages": "d71d1b06393385f1c797b213ff79240cda352b1b658110cc4a9eef7ced597490",
    "moss_authoring_fisher_independent": "c5f3763e5aff5f26a99c8c6aec2175bb991fa10a4151886da211fe2ffd1d3940",
    "moss_authoring_fisher_fusion": "35b4d3f9e92ab0d5e6fa282fc3839123fbeea654ae77b30a7c96ce8d364a8484",
    "moss_authoring_cpu_page": "c30b915f7e3db37585b02f2171d15fc92f89b9893e9537c1d2af092b3cb00411",
    "moss_authoring_fixed_layout_revision": "719bc71659c84bc03817e82597093cf4cadc94b9022c7ad3d59313770367bb03",
}

CONFIGURATION_NOTE = (
    "【先配置，再运行 / Configure before running】\n"
    "共享配置默认 Local Qwen，不包含密钥。请按自己的安装选择云端/本地渠道、模型及预算；云端使用本地凭据别名或环境变量，勿把密钥粘进工作流。"
    "有图任务需要支持视觉输入的模型与相应投影器。示例生成器本身不调用模型。\n"
    "这里只生成提示词，不生成图片；描述字数是软上限，不是 Tokens，不裁切句子。模型纠正最多每阶段追加一次，并非无限重试。"
    "把主节点或 Page 的 positive_prompt 接给 MOSS 提示词输入，width/height 接下游画布；bundle/report/source JSON 不是正向提示词。"
    "最终 MOSS 分词长度仍需在实际模型侧检查；示例与结构测试不证明画质或双语语义。"
)


def _node(node_id, kind, pos, *, title=None, size=(540, 780)):
    result = dict(id=node_id, type=kind, pos=list(pos), size=list(size), flags={}, order=0, mode=0,
                  inputs=[], outputs=[], properties={"Node name for S&R": kind}, widgets_values=[])
    if title:
        result["title"] = title
    return result


def _note(node_id, text, pos=(-520, 620)):
    result = _node(node_id, "Note", pos, size=(460, 450), title="使用方法 / Read first")
    result["widgets_values"] = [text]
    return result


def _config(node_id=1):
    result = _provider_node(node_id, [1], [-520, 0])
    result["widgets_values"] += copy.deepcopy(STRATA_DEFAULTS)
    # Match the authoring stage default, rather than quietly limiting each page
    # to the old basic example's 4096-token generation budget.
    result["widgets_values"][5] = 16384
    result["widgets_values_named"] = dict(zip(CONFIG_NAMES, result["widgets_values"], strict=True))
    result["properties"]["t8_provider_config_widgets_schema"] = 1
    result["title"] = "先选择自己的渠道/模型 / Configure your own provider"
    return result


def _main(overrides):
    result = _node(2, "MOSSImagePromptEnhancerT8", [40, 0])
    values = dict(zip(MAIN_NAMES, [*copy.deepcopy(OLD_VALUES), authoring.CLASSIC], strict=True))
    values.update(api_mode="本地 GGUF（llama.cpp / Qwen，离线）", control_after_generate="fixed")
    values.update(overrides)
    result["inputs"] = [{"name": "api_key", "type": "STRING", "link": None, "shape": 7},
                        {"name": "provider_config", "type": "T8_LLM_PROVIDER_CONFIG", "link": 1, "shape": 7}]
    result["outputs"] = [{"name": name, "type": kind, "links": [2] if index == 0 else None}
                         for index, (name, kind) in enumerate((("positive_prompt", "STRING"), ("width", "INT"),
                             ("height", "INT"), ("resolved_format", "STRING"), ("draft_json", "STRING"), ("report_json", "STRING")))]
    result["widgets_values"] = list(values.values())
    result["widgets_values_named"] = copy.deepcopy(values)
    result["properties"].update(t8_moss_widgets_schema=2, t8_moss_widgets_v1=copy.deepcopy(values))
    return result


def _director(overrides, *, reference_links=()):
    result = _node(2, "MOSSAuthoringDirectorT8", [40, 0], size=(580, 1020))
    values = dict(zip(DIRECTOR_NAMES, copy.deepcopy(DIRECTOR_VALUES), strict=True))
    values.update(overrides)
    result["inputs"] = [{"name": "provider_config", "type": "T8_LLM_PROVIDER_CONFIG", "link": 1, "shape": 7}]
    result["inputs"] += [{"name": f"reference_images.reference_image_{index}", "type": "IMAGE", "link": link,
                           "shape": 7, "label": f"reference_image_{index}"} for index, link in enumerate(reference_links)]
    result["outputs"] = [{"name": name, "type": kind, "links": None} for name, kind in
                         (("bundle_json", "STRING"), ("unit_count", "INT"), ("report_json", "STRING"), ("paired_reading", "STRING"))]
    result["widgets_values"] = list(values.values())
    result["widgets_values_named"] = copy.deepcopy(values)
    result["properties"]["t8_moss_authoring_widgets_v1"] = copy.deepcopy(values)
    return result


def _page(node_id, page_index, language, *, bundle_text="", input_link=None, output_link=None, pos=(720, 0)):
    result = _node(node_id, "MOSSAuthoringPageT8", pos, size=(500, 560))
    result["title"] = f"Page {page_index} · {language} · positive_prompt → MOSS"
    result["inputs"] = [{"name": "bundle_json", "type": "STRING", "link": input_link,
                          "widget": {"name": "bundle_json"}}]
    result["widgets_values"] = [bundle_text, page_index, language]
    result["outputs"] = [{"name": name, "type": kind, "links": [output_link] if index == 0 and output_link else None}
                         for index, (name, kind) in enumerate((("positive_prompt", "STRING"), ("width", "INT"),
                             ("height", "INT"), ("resolved_format", "STRING"), ("native_draft_json", "STRING"),
                             ("report_json", "STRING"), ("source_json", "STRING"), ("paired_reading", "STRING"), ("unit_id", "STRING")))]
    return result


def _comic_unit(index):
    """Original hand-authored teaching page: not an LLM or rendered-image claim."""
    words = "先走一步。" if index == 1 else "我们出发！"
    source = {"width": 1256, "height": 1672, "bbox_coord_space": "abs", "bbox_format": "xyxy",
              "summary": {"canvas": "multi_panel", "caption": "An original teaching comic page about a small red robot starting a walk."},
              "items": [
                  {"label": "comic_panel", "caption": "A wide, black-bordered panel on warm ivory paper.", "bbox": [40, 40, 1216, 1632]},
                  {"label": "character", "caption": "One small red robot with a square head, two round eyes and short legs, taking a step to the right.", "bbox": [200, 500, 760, 1450]},
                  {"label": "text", "caption": "A clean speech balloon with the exact original Chinese words.", "text": words, "bbox": [200, 140, 1000, 360]},
              ]}
    ids = ["frame", "robot", "speech"]
    sidecar = {"item_ids": ids, "panel_order": ["frame"], "membership": {
        "robot": {"panel_ids": ["frame"], "global_overlay": False}, "speech": {"panel_ids": ["frame"], "global_overlay": False}},
        "devices": [], "intensity": "quiet" if index == 1 else "turning",
        "layout_signature": {"topology": "one tall panel", "emphasis": "the red robot", "framing_progression": "full-body view",
            "viewpoint": "eye level", "blocking": "robot moving right", "density": "sparse", "entry_exit": "rightward exit",
            "information_rhythm": "one action with one speech balloon", "panel_count": 1},
        "state": {"identity_anchors": {"robot": "small red robot; square head; two round eyes; short legs"},
                  "scene_anchors": {"path": "plain ivory ground"}, "current_state": {"robot": "starting to walk"}}}
    translated = contract.translate(source, ids, {"summary_caption": "原创教学漫画：一只小红机器人开始散步。",
        "item_captions": {"frame": "暖象牙纸面上的一个黑线宽画框。", "robot": "一只小红机器人，方脑袋、两只圆眼睛和短腿，向右迈步。",
                          "speech": "干净对白气泡，保留完整中文原文。"}})
    return {"unit_id": f"page-{index}", "index": index, "width": 1256, "height": 1672, "reference_indices": [],
            "available_languages": ["en", "zh"], "sources": {"en": source, "zh": translated}, "sidecar": sidecar}


def teaching_bundle():
    # This is supplied source data, not a claim that we made five LLM requests.
    # Zero edited units and empty stages correctly report zero historical calls.
    return bundle.build_bundle(authoring.COMIC, "context", [_comic_unit(1), _comic_unit(2)], [], [],
                               "The same small red robot has a square head, two round eyes and short legs on both pages.", [], 0)


def _load_image(node_id, filename, output_link, pos):
    result = _node(node_id, "LoadImage", pos, size=(430, 310), title="上传原创教学图或自己的图 / Upload reference")
    # The native upload button is not a persisted backend field.
    result["widgets_values"] = [filename]
    result["outputs"] = [{"name": "IMAGE", "type": "IMAGE", "links": [output_link]}, {"name": "MASK", "type": "MASK", "links": None}]
    return result


def generate():
    result = {}
    cases = {
        STEMS[0]: {"prompt": "为一只奶白色陶瓷杯写完整中文图像提示词：暖灰桌面，左侧窗光，真实釉面细节，安静但不空洞的产品照片，不加可见文字。", "authoring_profile": authoring.FISHER},
        STEMS[1]: {"prompt": "简短版：一只奶白陶瓷杯置于暖灰桌面，左侧窗光，写中文提示词，不加可见文字。", "authoring_profile": authoring.FISHER, "max_output_chars": 300},
        STEMS[2]: {"prompt": "单张漫画海报：只有一只小红机器人，方脑袋、两只圆眼和短腿，跨过一条小水沟；有节制的动势线，清楚的左右方向，无可见文字。只创作这一张图，不生成整册。", "authoring_profile": authoring.COMIC,
                   "output_format": "Layout / 空间排版", "width": 1256, "height": 1672},
    }
    for stem, overrides in cases.items():
        extra = ("\nFisher长版：字数=0、Auto 默认偏好约1500–2500汉字（软目标，非硬截断）。" if stem == STEMS[0] else
                 "\nFisher短版：显式简短需求+300字符软上限会覆盖自动长版目标。" if stem == STEMS[1] else
                 "\n单图 Comic 是原主节点的可选模式。需要多页+英中同布局时，请用 Director→Page 示例。")
        result[stem] = _workflow(stem, [_config(), _main(overrides), _show_text_node(3, 2, [700, 0]),
                                      _note(4, CONFIGURATION_NOTE + extra)],
                                 [[1, 1, 0, 2, 1, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"]])
    director = _director({"brief": "创作两页原创漫画：同一只小红机器人，方脑袋、两只圆眼、短腿；第一页犹豫地靠近小水沟，第二页迈过水沟继续向右走。每页布局有节奏变化，无可见文字。",
                          "page_count": 2, "continuity_context": "Both pages: exactly one small red robot with a square head, two round eyes and short legs."})
    director["outputs"][0]["links"] = [2, 3]
    result[STEMS[3]] = _workflow(STEMS[3], [_config(), director,
        _page(3, 1, "en", input_link=2, output_link=4, pos=(720, 0)),
        _page(4, 1, "zh", input_link=3, output_link=5, pos=(720, 650)),
        _show_text_node(5, 4, [1300, 0]), _show_text_node(6, 5, [1300, 650]),
        _note(7, CONFIGURATION_NOTE + "\n整册 Comic：一次规划+每页英语源稿/中文描述映射，2页通常5次逻辑调用，每阶段最多追加1次纠正。"
              "两个 Page 均选第1页，分别 en/zh；改页码为2查看第2页。中文只改变描述，同页几何与可见原文不变。", (-520, 620))],
        [[1, 1, 0, 2, 0, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"], [3, 2, 0, 4, 0, "STRING"],
         [4, 3, 0, 5, 0, "STRING"], [5, 4, 0, 6, 0, "STRING"]])
    for stem, mode in ((STEMS[4], "independent"), (STEMS[5], "fusion")):
        director = _director({"brief": "简短中文描述。根据参考图的几何配色和图形关系创作干净的扁平教学插画，不照搬图中文字。" +
            ("两张参考各自创作独立图，不能把两张图合到一起。" if mode == "independent" else "明确把图1的青绿线框与图2的紫色卡片融合到同一张新插画中，只输出一张图的描述。"),
            "profile": authoring.FISHER, "width": 1024, "height": 1024, "reference_mode": mode, "max_output_chars": 500}, reference_links=(2, 3))
        director["outputs"][0]["links"] = [4]
        nodes = [_config(), director,
            _load_image(3, STEMS[4] + ".jpg", 2, [-1000, 0]), _load_image(4, STEMS[5] + ".jpg", 3, [-1000, 380]),
            _page(5, 1, "zh", input_link=4, output_link=5), _show_text_node(6, 5, [1320, 0]),
            _note(7, CONFIGURATION_NOTE + "\n先把本目录 moss_authoring_fisher_independent.jpg 和 moss_authoring_fisher_fusion.jpg"
                  "分别拖到两个 LoadImage 节点上传，或选择你自己的两张图；示例不自动写入 ComfyUI/input。这两张图片是本项目原创CPU教学示意图，不是真实用户图。"
                  + ("\nindependent：两张图→两个独立单元，Page=1/2按上传顺序选择；单图批次会先展开。" if mode == "independent" else
                     "\nfusion：显式两图融合→一个单元，Page只能选1，不会自动生成两个独立结果。"), [-1000, 800])]
        result[stem] = _workflow(stem, nodes, [[1, 1, 0, 2, 0, "T8_LLM_PROVIDER_CONFIG"],
            [2, 3, 0, 2, 1, "IMAGE"], [3, 4, 0, 2, 2, "IMAGE"], [4, 2, 0, 5, 0, "STRING"], [5, 5, 0, 6, 0, "STRING"]])
    text = contract.encode(teaching_bundle())
    result[STEMS[6]] = _workflow(STEMS[6], [
        _page(1, 1, "en", bundle_text=text, output_link=1, pos=(0, 0)),
        _page(2, 1, "zh", bundle_text=text, output_link=2, pos=(0, 650)),
        _show_text_node(3, 1, [600, 0]), _show_text_node(4, 2, [600, 650]),
        _note(5, "【纯CPU，可直接运行】没有Provider/LoadImage/模型节点。两个Page各自内置相同的完整合法双语教学bundle；这是手工原稿数据，历史调用数为0。"
              "切换页码1/2、语言en/zh，查看positive_prompt、1256×1672、原始source及原生投影draft。漫画源保留comic_panel，原生编译副本转object+tag，不改源稿。"
              "\n粘贴新的完整bundle到Page的bundle_json即可；此字段关闭动态提示词。不要让会展开花括号的动态PromptText生成JSON。"
              "\n没有图片渲染或语义质量证明。要真正生成MOSS图片，请自行把positive_prompt和宽高接下游模型。", [-520, 0])],
        [[1, 1, 0, 3, 0, "STRING"], [2, 2, 0, 4, 0, "STRING"]])
    context = {"schema_version": "t8-moss-authoring-context/v1", "mode": "full_layout", "bundle": teaching_bundle(), "edit_unit_ids": ["page-2"]}
    director = _director({"brief": "只修订page-2的描述：机器人走得更坚定，釉红色外壳具有轻微柔和高光。保留完整既有画布、元素、框位置、读序及中文原文。不要改变page-1。",
                          "page_count": 2, "layout_context_json": contract.encode(context), "preserve_layout": True})
    director["outputs"][0]["links"] = [2]
    result[STEMS[7]] = _workflow(STEMS[7], [_config(), director, _page(3, 2, "zh", input_link=2, output_link=3),
        _show_text_node(4, 3, [1320, 0]), _note(5, CONFIGURATION_NOTE +
            "\n本例内置上一个纯CPU示例的整册 typed context：mode=full_layout，edit_unit_ids=[page-2]。page-1逐字段原样复制；page-2才调用规划/源稿/翻译（通常3次）。"
            "full_layout锁非caption字段与元素身份；panels_only只锁画框几何/读序，仍保留完整可见文案。不要仅粘原始source，必须使用带bundle的typed context。"
            "\n将edit_unit_ids改成[]可验证0调用复制，此时不执行新的lazy Provider/参考图分支；仍会遵守宿主全图静态验证与既有非lazy依赖。"
            "实际含参考图的旧bundle修订需重新连完全同顺序/内容参考图；此教学bundle没有参考图。")],
        [[1, 1, 0, 2, 0, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"], [3, 3, 0, 4, 0, "STRING"]])
    return result


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def thumbnail_arguments(stem):
    return ("MOSS AUTHORING - ORIGINAL CPU LESSON", stem.removeprefix("moss_authoring_")[:25],
            "Page -> MOSS", "Workflow diagram only | No model calls | " + str(STEMS.index(stem) + 1))


def check():
    for stem, expected in generate().items():
        path = EXAMPLES / (stem + ".json")
        raw = path.read_bytes()
        assert raw == _json_bytes(expected), stem + ": canonical workflow bytes differ"
        assert "sk-" not in raw.decode("utf-8"), stem + ": suspicious secret prefix"
        thumbnail = path.with_suffix(".jpg")
        assert thumbnail.is_file(), stem + ": missing same-name thumbnail"
        digest = hashlib.sha256(thumbnail.read_bytes()).hexdigest()
        assert digest == THUMBNAIL_SHA256.get(stem), stem + ": thumbnail bytes differ"
        nodes = {node["id"]: node for node in expected["nodes"]}
        assert len(nodes) == len(expected["nodes"])
        for link, origin, output, target, slot, kind in expected["links"]:
            assert nodes[target]["inputs"][slot]["link"] == link
            assert link in nodes[origin]["outputs"][output]["links"]
            assert nodes[target]["inputs"][slot]["type"] == nodes[origin]["outputs"][output]["type"] == kind
        for node in nodes.values():
            if node["type"] == "MOSSImagePromptEnhancerT8":
                assert len(node["widgets_values"]) == len(MAIN_NAMES) == 28
                assert node["widgets_values_named"] == dict(zip(MAIN_NAMES, node["widgets_values"], strict=True))
                assert node["properties"]["t8_moss_widgets_schema"] == 2
            if node["type"] == "MOSSAuthoringDirectorT8":
                assert len(node["widgets_values"]) == len(DIRECTOR_NAMES) == 17
                assert node["widgets_values_named"] == dict(zip(DIRECTOR_NAMES, node["widgets_values"], strict=True))
            if node["type"] == "T8LLMProviderConfig":
                values = node["widgets_values_named"]
                assert len(values) == len(node["widgets_values"]) == 27
                assert all(values[key] == "" for key in ("credential_alias", "openai_base_url", "custom_model", "strata_credential_alias"))
            if node["type"] == "MOSSAuthoringPageT8" and node["widgets_values"][0]:
                bundle.validate_bundle(node["widgets_values"][0])
    print("MOSS authoring examples: 8 additive workflows, exact JSON/JPG, named 28/17 controls, no credentials/model calls.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        for stem, value in generate().items():
            path = EXAMPLES / (stem + ".json")
            path.write_bytes(_json_bytes(value))
            _write_thumbnail(path.with_suffix(".jpg"), *thumbnail_arguments(stem))
    check()


if __name__ == "__main__":
    main()
