"""Build/check two new examples, never rewrite the older 21 workflows."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from build_example_workflows import (_h3_node, _seedance_node, _prompt_text_node, _show_text_node,
                                     _workflow, _write_thumbnail, _socket, SEEDANCE_API_MODE)
from build_directional_skill_workflows import widget_names
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "example_workflows"
STEMS = ("h3_seedance_quality_check_example", "h3_seedance_causal_creation_example")

def generate():
    result = {}
    for stem in STEMS:
        causal = "causal" in stem
        prompt = "8秒，一台无脸四足小机器人从石台走过两级台阶到木桥入口，前足踏上木桥时后足仍在移动。一个连续镜头，不瞬移、不变形、不增加人物、对白或武器，无字幕与配乐，只有机械和落足声。"
        key = _prompt_text_node(1, [1, 2], [0, 40], text="", title="LLM API Key（运行前填写，分享前清空）")
        h3 = _h3_node(2, None, [420, 40], prompt=prompt, api_mode=SEEDANCE_API_MODE, api_key_link=1, output_links=[3])
        sd = _seedance_node(3, None, [1150, 40], prompt=prompt, api_mode=SEEDANCE_API_MODE, api_key_link=2, output_links=[4])
        h3["widgets_values"].extend(["普通增强 / Normal", 0, 0, "", "none"])
        sd["widgets_values"].append("none")
        for node, filename in ((h3, "minimax_h3_prompt_enhancer.js"), (sd, "seedance20_prompt_enhancer.js")):
            names = [*widget_names(filename), "quality_mode", "creation_mode"]
            values = dict(zip(names[:36], node["widgets_values"]))
            values.update(duration_seconds=8 if node is h3 else "8", shot_count="1", quality_mode="repair" if causal else "check",
                          creation_mode="causal" if causal else "off", local_max_tokens=16384)
            node["widgets_values"] = [values[n] for n in names]
            node["size"] = [650, 1160]
            node["inputs"].insert(5, _socket("performance_director_config", "T8_PERFORMANCE_DIRECTOR_CONFIG", None))
            node["inputs"].append(_socket("character_performance_bible", "T8_CHARACTER_PERFORMANCE_BIBLE", None))
        h3["outputs"] += [{"name":n,"type":t,"links":None} for n,t in (
            ("global_prompt","STRING"),("local_prompts","STRING"),("time_ranges","STRING"),("relay_length","INT"),("relay_report","STRING"))]
        a = _show_text_node(4, 3, [420, 1240]); a["title"]="H3 原生输出 / H3 native"
        b = _show_text_node(5, 4, [1150, 1240]); b["title"]="Seedance 原生输出 / Seedance native"
        result[stem] = _workflow(stem, [key,h3,sd,a,b], [
            [1,1,0,2,4,"STRING"],[2,1,0,3,4,"STRING"],[3,2,0,4,0,"STRING"],[4,3,0,5,0,"STRING"]])
    return result

def check():
    for stem, expected in generate().items():
        path = EXAMPLES / f"{stem}.json"
        assert json.loads(path.read_text(encoding="utf-8")) == expected, stem
        assert path.with_suffix(".jpg").is_file(), stem
        nodes={n["id"]:n for n in expected["nodes"]}
        for n in (nodes[2], nodes[3]):
            assert len(n["widgets_values"])==38
        assert nodes[1]["widgets_values"]==[""]
        for link,s,o,d,i,t in expected["links"]:
            assert nodes[s]["outputs"][o]["type"]==nodes[d]["inputs"][i]["type"]==t
            assert nodes[d]["inputs"][i]["link"]==link and link in nodes[s]["outputs"][o]["links"]
    print("Quality examples: 2 JSONs, 38 widgets, blank keys, stable native outputs and links.")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--check",action="store_true"); args=parser.parse_args()
    if not args.check:
        for stem, data in generate().items():
            path=EXAMPLES/f"{stem}.json"
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            _write_thumbnail(path.with_suffix(".jpg"),"Causal creation" if "causal" in stem else "Contract check", "H3 native", "Seedance native", "Optional / draft retained / text contracts only")
    check()
