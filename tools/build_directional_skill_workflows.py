"""Build/check text-only directional examples; preserve existing example layouts."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

from build_example_workflows import (
    SEEDANCE_API_MODE, _h3_node, _prompt_text_node, _seedance_node,
    _show_text_node, _socket, _workflow,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "example_workflows"
SMALL_MODEL = "Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf"
CASES = {
    "continuous_combat": ("Fisher-连续战斗长镜头 / Continuous combat", 12,
        "12秒，一镜到底。两名成年剑客沿空走廊交锋，白衣者后退到柱旁，借柱侧身避开来剑，顺着对方未收住的冲势绕到侧面；黑衣者转身继续追击。保持双方衣服、剑和移动方向一致，不增加能力，不定格，不加对白、字幕或配乐。"),
    "high_density_combat": ("土豆-高密度连续攻防 / High-density combat", 8,
        "8秒。空旷练功场上两名成年练习者徒手连续攻防，红袖者出拳被蓝袖者格开，红袖者顺势转身避让，蓝袖者随其位移继续进攻。让攻防因果和重心移动清楚，全程保持空手，不停下来摆姿势，不强定胜负，不加对白、字幕或配乐。"),
    "cinematic_gunfight": ("兔子-电影枪战导演 / Cinematic gunfight", 12,
        "12秒虚构电影枪战。雨夜空车站，两名成年同伴带着同一个箱子向出口撤离，远处枪声响起，前方玻璃碎裂迫使他们改变路线；前者拉开侧门，后者带箱跟上。重点是撤离目标、人物回应、雨水和碎玻璃的连续状态；不要讲解枪械操作，不增加平民、字幕或配乐。"),
    "ning_wenwu": ("宁版-文武双全 / Ning · Drama & Action", 12,
        "12秒虚构电影片段，两名成年人物在走廊门口。黑衣侍卫站在左侧，红衣来客在右侧。侍卫先低声说原句“到此为止。”，来客听完才把已拿着的信放回自己的右侧口袋；随后侍卫拔出已有长剑挡住通道，但不出击。结尾双方仍在门口，门仍关闭，信归来客，剑归侍卫。一个连续镜头，让对白、手部动作与通道阻隔的变化清楚。不能新增人物、台词、武器、法术或胜负，无字幕，无配乐。"),
    "drama_scene": ("戏剧场面｜关系与潜台词 / Dramatic scene", 15,
        "15秒，固定双人中景，一个连续镜头。成年主管在左、成年员工在右，桌上已有一封辞职信。主管把信推回，员工用右手按住信；主管说原句“明天的会，你还来吗？”，员工听完回答原句“我把资料发给你。”。这是含蓄的挽留与回避，不争吵、不哭，不决定员工最后是否辞职。只有这两句，逐字保留，不新增人物、道具、秘密或对白；无字幕无配乐。"),
    "situational_drama": ("情境戏剧｜处境与铺垫回收 / Situational drama", 15,
        "请原创一个15秒、温暖轻松、无对白的小场面。只有两名成年搬家者和一张已有长桌，两人各握一端，目标是一起把桌子抬过已有门口。允许编排礼让导致一次配合错位，再通过手势默契调整；不要让任何人变蠢，不伤人，不撞坏物品，不添加人或道具。结尾两人协作把桌子完整抬过门，各自仍握原来一端。固定机位，一个连续镜头，只有动作声，无对白、字幕或配乐。"),
}
DRAMA_SKILLS = {"drama_scene", "situational_drama"}
STEMS = tuple(stem for skill in CASES for stem in (
    (f"directional_{skill}_h3", f"directional_{skill}_seedance20") if skill in DRAMA_SKILLS
    else (f"directional_{skill}_comparison",)))


def widget_names(filename: str) -> list[str]:
    source = (ROOT / "web/js" / filename).read_text(encoding="utf-8")
    match = re.search(r"const SERIALIZED_WIDGET_NAMES = \[([\s\S]*?)\];", source)
    if not match:
        raise RuntimeError("Serialized widget schema is missing")
    # The three published examples retain their original 36-value layout.
    return re.findall(r'"([a-z_]+)"', match.group(1))[:36]


def generate() -> dict[str, dict]:
    result = {}
    for skill, (label, duration, prompt) in CASES.items():
        stem = f"directional_{skill}_comparison"
        key = _prompt_text_node(1, [1, 2], [0, 40], text="",
            title="填写贞贞 API Key / Your API key (clear before sharing)")
        h3 = _h3_node(2, None, [480, 40], prompt=prompt,
            api_mode=SEEDANCE_API_MODE, api_key_link=1, output_links=[3])
        sd = _seedance_node(3, None, [1180, 40], prompt=prompt,
            api_mode=SEEDANCE_API_MODE, api_key_link=2, output_links=[4])
        h3["widgets_values"].extend(["普通增强 / Normal", 0, 0, "", skill])
        sd["widgets_values"].append(skill)
        for node, filename, kind in [(h3, "minimax_h3_prompt_enhancer.js", "H3"),
                                     (sd, "seedance20_prompt_enhancer.js", "Seedance 2.0")]:
            names = widget_names(filename)
            assert len(names) == len(node["widgets_values"]) == 36
            values = dict(zip(names, node["widgets_values"]))
            values.update(duration_seconds=duration if kind == "H3" else str(duration),
                          shot_count="AUTO（系统自动判断）", local_model=SMALL_MODEL,
                          local_max_tokens=16384)
            if skill == "ning_wenwu" or skill in DRAMA_SKILLS:
                # Explicit settings in this NEW example, not an implicit change
                # to the selector or any existing saved workflow.
                names = [*names, "quality_mode", "creation_mode"]
                values.update(quality_mode="repair", creation_mode="off")
            node["widgets_values"] = [values[name] for name in names]
            node["title"] = f"{kind} · {label}"
            node["size"] = [640, 1160]
            node["inputs"].insert(5, _socket("performance_director_config", "T8_PERFORMANCE_DIRECTOR_CONFIG", None))
            node["inputs"].append(_socket("character_performance_bible", "T8_CHARACTER_PERFORMANCE_BIBLE", None))
        h3["outputs"] += [{"name": name, "type": kind, "links": None} for name, kind in [
            ("global_prompt", "STRING"), ("local_prompts", "STRING"),
            ("time_ranges", "STRING"), ("relay_length", "INT"), ("relay_report", "STRING")]]
        show_h3 = _show_text_node(4, 3, [480, 1250])
        show_h3["title"] = "H3 原生提示词 / Native H3 prompt"
        show_sd = _show_text_node(5, 4, [1180, 1250])
        show_sd["title"] = "Seedance 原生提示词 / Native Seedance prompt"
        workflow = _workflow(stem, [key, h3, sd, show_h3, show_sd], [
            [1, 1, 0, 2, 4, "STRING"], [2, 1, 0, 3, 4, "STRING"],
            [3, 2, 0, 4, 0, "STRING"], [4, 3, 0, 5, 0, "STRING"],
        ])
        if skill in DRAMA_SKILLS:
            # Four self-contained new files: each Skill has both model targets.
            # Keep published comparison examples byte-for-byte unchanged.
            for target, ids in (("h3", {1, 2, 4}), ("seedance20", {1, 3, 5})):
                single = copy.deepcopy(workflow)
                single["nodes"] = [n for n in single["nodes"] if n["id"] in ids]
                single["links"] = [link for link in single["links"] if link[1] in ids and link[3] in ids]
                single["nodes"][0]["outputs"][0]["links"] = [single["links"][0][0]]
                result[f"directional_{skill}_{target}"] = single
        else:
            result[stem] = workflow
    return result


def check() -> None:
    for stem, expected in generate().items():
        path = EXAMPLES / f"{stem}.json"
        text = path.read_text(encoding="utf-8")
        actual = json.loads(text)
        if actual != expected:
            raise RuntimeError(f"{stem}: example differs from its checked generator")
        if "sk-" in text or "27B" in text or "Local Qwen" in text:
            raise RuntimeError(f"{stem}: unexpected credential or local default")
        nodes = {node["id"]: node for node in actual["nodes"]}
        assert nodes[1]["widgets_values"] == [""]
        for node_id, filename in [(2, "minimax_h3_prompt_enhancer.js"), (3, "seedance20_prompt_enhancer.js")]:
            if node_id not in nodes:
                continue
            node = nodes[node_id]
            names = widget_names(filename)
            if stem == "directional_ning_wenwu_comparison" or any(stem.startswith(f"directional_{skill}_") for skill in DRAMA_SKILLS):
                names = [*names, "quality_mode", "creation_mode"]
            values = dict(zip(names, node["widgets_values"]))
            assert len(node["widgets_values"]) == len(names)
            if values["director_skill"] == "ning_wenwu" or values["director_skill"] in DRAMA_SKILLS:
                assert len(names) == 38 and values["quality_mode"] == "repair" and values["creation_mode"] == "off"
            else:
                assert len(names) == 36 and names[-1] == "director_skill"
            assert values["director_skill"] in CASES
            assert values["api_mode"] == SEEDANCE_API_MODE and values["api_key"] == ""
            assert values["shot_count"] == "AUTO（系统自动判断）"
            assert values["output_language"] == "中文" and values["local_model"] == SMALL_MODEL
            assert values["case_template"] == "无（不使用 T8 案例）"
            assert isinstance(values["seed"], int) and values["control_after_generate"] == "fixed"
            if node_id == 2:
                assert values["relay_mode"] == "普通增强 / Normal" and len(node["outputs"]) == 6
                assert isinstance(values["duration_seconds"], int)
            else:
                assert len(node["outputs"]) == 1 and isinstance(values["custom_length_target"], int)
                assert isinstance(values["duration_seconds"], str)
        for link_id, source_id, out_slot, dest_id, in_slot, kind in actual["links"]:
            output = nodes[source_id]["outputs"][out_slot]
            input_ = nodes[dest_id]["inputs"][in_slot]
            assert output["type"] == input_["type"] == kind
            assert link_id in output["links"] and input_["link"] == link_id
    print(f"Directional examples: {len(STEMS)} JSONs, legacy 36/new 38 widgets, H3/Seedance outputs and links valid; no keys/models loaded.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        for stem, workflow in generate().items():
            (EXAMPLES / f"{stem}.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    check()


if __name__ == "__main__":
    main()
