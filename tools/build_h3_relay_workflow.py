"""Build a text-only Relay tutorial; no external nodes or model execution required."""
import json
from pathlib import Path

from build_example_workflows import _h3_node, _prompt_text_node, _show_text_node, _workflow, _write_thumbnail, SEEDANCE_API_MODE

ROOT = Path(__file__).resolve().parents[1]


def generate():
    key = _prompt_text_node(1, [1], [0, 40], text="", title="填写贞贞平价小屋 API Key（不要分享密钥）")
    h3 = _h3_node(2, None, [480, 40], prompt="女生在站台捡起车票，交给回头的乘客，说‘你的车票。’，对方点头，她挥手告别。8秒，一镜到底，无配乐。", api_mode=SEEDANCE_API_MODE, api_key_link=1)
    h3["widgets_values"][2:4] = [8, "1"]
    h3["widgets_values"].extend(["Prompt Relay 编排", 3, 0, "0-2.5\n2.5-5\n5-8"])
    names = ["enhanced_prompt", "global_prompt", "local_prompts", "time_ranges", "relay_length", "relay_report"]
    h3["outputs"] = [{"name": name, "type": "INT" if index == 4 else "STRING", "links": None if index == 4 else [index + 2]} for index, name in enumerate(names)]
    nodes = [key, h3]
    links = [[1, 1, 0, 2, 4, "STRING"]]
    for index, name in enumerate(names):
        if index == 4:
            continue
        show = _show_text_node(index + 3, index + 2, [1220 + (index // 3) * 600, 40 + (index % 3) * 430])
        show["title"] = name
        nodes.append(show)
        links.append([index + 2, 2, index, index + 3, 0, "STRING"])
    return _workflow("h3_prompt_relay_example", nodes, links)


def plan_example():
    workflow = generate()
    h3 = workflow["nodes"][1]
    sockets = []
    for link_id, output_index, name, type_name in [(20, 1, "global_prompt", "STRING"), (21, 2, "local_prompts", "STRING"), (22, 3, "time_ranges", "STRING"), (23, 4, "length", "INT")]:
        h3["outputs"][output_index]["links"] = (h3["outputs"][output_index]["links"] or []) + [link_id]
        sockets.append({"name": name, "type": type_name, "link": link_id, "widget": {"name": name}})
        workflow["links"].append([link_id, 2, output_index, 20, len(sockets) - 1, type_name])
    sockets.append({"name": "prompt_relay_events", "type": "H3_T8_PROMPT_RELAY_EVENTS", "link": None, "shape": 7})
    plan = {"id": 20, "type": "MiniMaxH3PromptRelayPlanT8Advanced", "pos": [2450, 40], "size": [660, 660], "flags": {}, "order": 3, "mode": 0,
            "inputs": sockets, "outputs": [
                {"name": name, "type": kind, "links": [24] if name == "timeline_json" else None}
                for name, kind in [("prompt_relay_plan", "H3_T8_PROMPT_RELAY_PLAN"), ("compiled_prompt", "STRING"), ("length", "INT"), ("timeline_json", "STRING"), ("report_json", "STRING")]],
            "properties": {"Node name for S&R": "MiniMaxH3PromptRelayPlanT8Advanced"},
            "widgets_values": ["", "", 192, "seconds", "", "paper_v1", 0.1, False, False]}
    show = _show_text_node(21, 24, [3200, 40])
    show["title"] = "下游 Plan 时间线（仅编译；不生成视频）"
    workflow["nodes"].extend([plan, show])
    workflow["links"].append([24, 20, 3, 21, 0, "STRING"])
    workflow["last_node_id"] = 21
    workflow["last_link_id"] = 24
    return workflow


def main():
    path = ROOT / "example_workflows/h3_prompt_relay_example.json"
    path.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_thumbnail(path.with_suffix(".jpg"), "H3 Prompt Relay", "Global + Local + Time", "Cloud / local GGUF", "T8 - 24 FPS timeline planning")
    adapter = ROOT / "docs/workflows/h3_prompt_relay_plan.json"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(json.dumps(plan_example(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
