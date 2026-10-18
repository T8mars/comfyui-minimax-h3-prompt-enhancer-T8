"""Independent paired examples. No modification to published workflows."""
import argparse
import copy
import json
from pathlib import Path

from build_directional_skill_workflows import generate as originals
from build_example_workflows import _workflow, _socket, _show_text_node

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ("60秒，固定三个镜头，两位成年人坐在桌子两侧，桌上只有一个信封。"
          "镜头1：甲把信封递给乙，乙右手接稳后甲松手，交接只发生一次。"
          "镜头2：乙保持信封未打开，安静等待；甲说完整原句“等雨停了，我们再出发。”，不改字、不加对白。"
          "镜头3：乙把信封收进自己的口袋，甲乙继续坐着，雨仍未停。"
          "开头不得提前展示收信结局，不新增物品、人物、冲突、字幕或配乐。")
MODES = ("关闭 / Off", "开启（实验） / On (experimental)")
STEMS = ("storyboard_director_h3_comparison", "storyboard_director_seedance20_comparison")


def generate():
    sources, result = originals(), {}
    for target in ("h3", "seedance20"):
        source = sources[f"directional_zhenzhen_pov_{target}"]
        original = next(n for n in source["nodes"] if n["type"].endswith("PromptEnhancerT8"))
        key = copy.deepcopy(source["nodes"][0])
        key["outputs"][0]["links"] = [1, 2]
        nodes, links = [key], []
        for index, mode in enumerate(MODES):
            enhancer = copy.deepcopy(original)
            nid, sid, cid = 2 + index, 4 + index, 6 + index
            enhancer.update(id=nid, pos=[480 + index * 720, 40],
                            title=f"{target} · {'On 实验' if index else 'Off 基线'}")
            values = enhancer["widgets_values"]
            values[0] = PROMPT
            values[2 if target == "h3" else 3] = 60 if target == "h3" else "60"
            values[3 if target == "h3" else 4] = "3"
            values[35:] = ["none", "off", "off"]
            for inp in enhancer["inputs"]:
                inp["link"] = index + 1 if inp["name"] == "api_key" else None
            enhancer["inputs"].extend([
                _socket("combat_camera_config", "T8_COMBAT_CAMERA_CONFIG", None),
                _socket("speech_reference", "T8_SPEECH_REFERENCE", None),
                _socket("storyboard_director_config", "T8_STORYBOARD_DIRECTOR_CONFIG", 5 + index),
            ])
            for output in enhancer["outputs"]:
                output["links"] = None
            enhancer["outputs"][0]["links"] = [3 + index]
            show = _show_text_node(sid, 3 + index, [480 + index * 720, 1550])
            show["title"] = f"{'On 实验' if index else 'Off 基线'} 原生结果 / Native output"
            config = {"id": cid, "type": "T8StoryboardDirectorConfig", "pos": [0, 520 + index * 240],
                      "size": [470, 140], "flags": {}, "order": 0, "mode": 0, "inputs": [],
                      "outputs": [{"name": "storyboard_director_config", "type": "T8_STORYBOARD_DIRECTOR_CONFIG", "links": [5 + index]}],
                      "properties": {"Node name for S&R": "T8StoryboardDirectorConfig"}, "widgets_values": [mode]}
            nodes.extend([enhancer, show, config])
            links.extend([[1 + index, 1, 0, nid, 4, "STRING"],
                          [3 + index, nid, 0, sid, 0, "STRING"],
                          [5 + index, cid, 0, nid, len(enhancer["inputs"]) - 1, "T8_STORYBOARD_DIRECTOR_CONFIG"]])
        stem = f"storyboard_director_{target}_comparison"
        result[stem] = _workflow(stem, nodes, links)
    return result


def check():
    for stem, expected in generate().items():
        actual = json.loads((ROOT / "example_workflows" / f"{stem}.json").read_text(encoding="utf-8"))
        assert actual == expected, stem
        nodes = {n["id"]: n for n in actual["nodes"]}
        assert nodes[1]["widgets_values"] == [""]
        assert nodes[2]["widgets_values"] == nodes[3]["widgets_values"]
        assert len(nodes[2]["widgets_values"]) == 38
        assert nodes[6]["widgets_values"] == [MODES[0]] and nodes[7]["widgets_values"] == [MODES[1]]
        for lid, src, out, dst, inp, kind in actual["links"]:
            assert nodes[src]["outputs"][out]["type"] == nodes[dst]["inputs"][inp]["type"] == kind
            assert lid in nodes[src]["outputs"][out]["links"] and nodes[dst]["inputs"][inp]["link"] == lid
    print("Storyboard examples: two same-input Off/On pairs, blank keys, 38+1 widgets, native outputs/links.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        from generate_workflow_thumbnails import make_card
        for stem, data in generate().items():
            (ROOT / "example_workflows" / f"{stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            make_card("分镜强化 · Off / On", "H3" if "_h3_" in stem else "Seedance 2.0", (57, 111, 135)).save(
                ROOT / "example_workflows" / f"{stem}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
