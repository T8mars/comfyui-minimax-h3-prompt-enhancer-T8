"""Two independent, blank-key examples; never rewrite published workflows."""
import argparse
import json
from pathlib import Path

from build_example_workflows import _workflow, _socket
from build_directional_skill_workflows import generate as directional_examples

ROOT = Path(__file__).resolve().parents[1]
STEMS = ("combat_camera_h3", "combat_camera_seedance20")
PROMPT = ("8秒。两名成年练习者在空旷练功场进行木剑演练，红袖者向前一步挥剑，蓝袖者格挡后退半步，"
          "双方仍各持原来的木剑。保持侧面视角，让移动方向与接触清楚，不新增招式、敌人或胜负，"
          "无慢动作、定格、对白、字幕或配乐。")
CONFIG_VALUES = ["强化（明确轨迹与落点）", "沿用原设定 / Follow", "写实 / Natural"]


def generate():
    originals = directional_examples()
    result = {}
    for target in ("h3", "seedance20"):
        source = originals[f"directional_zhenzhen_pov_{target}"]
        nodes, links = source["nodes"], source["links"]
        enhancer = next(n for n in nodes if n["type"].endswith("PromptEnhancerT8"))
        enhancer["title"] = f"{target} · 战斗运镜示例 / Combat camera"
        values = enhancer["widgets_values"]
        values[0] = PROMPT
        values[2 if target == "h3" else 3] = 8 if target == "h3" else "8"
        values[35:] = ["none", "off", "off"]
        slot = len(enhancer["inputs"])
        enhancer["inputs"].append(_socket("combat_camera_config", "T8_COMBAT_CAMERA_CONFIG", 5))
        camera = {
            "id": 6, "type": "T8CombatCameraConfig", "pos": [0, 230], "size": [450, 160],
            "flags": {}, "order": 0, "mode": 0, "inputs": [],
            "outputs": [{"name": "战斗运镜配置 / Combat camera config", "type": "T8_COMBAT_CAMERA_CONFIG", "links": [5]}],
            "properties": {"Node name for S&R": "T8CombatCameraConfig"}, "widgets_values": list(CONFIG_VALUES),
        }
        nodes.append(camera)
        links.append([5, 6, 0, enhancer["id"], slot, "T8_COMBAT_CAMERA_CONFIG"])
        stem = f"combat_camera_{target}"
        result[stem] = _workflow(stem, nodes, links)
    return result


def check():
    for stem, expected in generate().items():
        actual = json.loads((ROOT / "example_workflows" / f"{stem}.json").read_text(encoding="utf-8"))
        assert actual == expected, stem
        nodes = {n["id"]: n for n in actual["nodes"]}
        assert nodes[1]["widgets_values"] == [""]
        assert len(nodes[6]["widgets_values"]) == 3
        enhancers = [n for n in nodes.values() if n["type"].endswith("PromptEnhancerT8")]
        assert len(enhancers) == 1 and len(enhancers[0]["widgets_values"]) == 38
        for lid, src, out, dst, inp, kind in actual["links"]:
            assert nodes[src]["outputs"][out]["type"] == nodes[dst]["inputs"][inp]["type"] == kind
            assert lid in nodes[src]["outputs"][out]["links"] and nodes[dst]["inputs"][inp]["link"] == lid
    print("Combat camera: two independent examples, blank keys, 38+3 native widgets and links verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        for stem, data in generate().items():
            (ROOT / "example_workflows" / f"{stem}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
