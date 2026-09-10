"""Build four schema-derived YuE2 examples without changing existing workflows."""
import importlib.util
import json
import sys
from pathlib import Path

from build_example_workflows import _provider_node, _show_text_node, _socket, _prompt_text_node, _workflow, _write_thumbnail

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
spec = importlib.util.spec_from_file_location("t8_yue2_workflows", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
yue = sys.modules[spec.name + ".yue2"]

ABC = 'X:1\nT:\nM:4/4\nL:1/32\nQ:1/4=88\nV: Vocal clef=treble name="Vocal Melody" snm="Vocal"\nV: Ins clef=treble name="Ins Melody" snm="Inst."\nK:C\n% verse\nV: Vocal\n"C"C8D8E8G8|\nV: Ins\nZ|\n'
LYRICS = "[Verse]\n风把旧地图轻轻翻开\n晨光落在陌生的站台\n\n[Chorus]\n让明天有名字\n让远方有回信\n"


def generate():
    cases = {
        "yue2_cloud_creation_example": {"music_idea": "原创中文公路歌：清晨带着旧地图出发，从犹豫到向前。女声、钢琴吉他，88 BPM，清晰的主歌发展与易记副歌。"},
        "yue2_preserve_lyrics_example": {"music_idea": "保持歌词原文，配温暖摇滚风格；电吉他、弹性鼓组，主歌克制，副歌开阔。", "lyrics": LYRICS, "lyrics_mode": yue.PRESERVE},
        "yue2_local_qwen_example": {"music_idea": "原创中文古风叙事歌：旅人在渡口读到一封迟到的家书，从克制到释然。清澈人声，古筝和弦乐。", "api_mode": yue.LOCAL_QWEN_API_MODE},
        "yue2_abc_melody_example": {"music_idea": "ABC 是一小节接口演示，不是完整歌曲。保持旋律，温暖中文人声，钢琴吉他。真实创作请替换完整乐谱与匹配歌词。", "lyrics": "[Verse]\n风吹过来\n", "lyrics_mode": yue.PRESERVE, "abc": ABC, "cot": list(yue.COT_MODES)[1], "abc_action": yue.ABC_STRIP},
    }
    result = {}
    for stem, changes in cases.items():
        local = "local_qwen" in stem
        values = {**yue.DEFAULTS, **changes}
        provider = _provider_node(1, [1], [0, 40]) if local else _prompt_text_node(1, [1], [0, 40], text="", title="填写你的 LLM API Key / Your key")
        node = {"id": 2, "type": yue.NODE_ID, "pos": [500, 40], "size": [680, 980], "flags": {}, "order": 1, "mode": 0,
                "inputs": [_socket("api_key", "STRING", None if local else 1), _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 1 if local else None)],
                "outputs": [{"name": name, "type": "STRING", "links": [index + 2]} for index, name in enumerate(("style", "lyrics", "abc", "yue2_request_json", "creation_report_json"))],
                "properties": {"Node name for S&R": yue.NODE_ID, "t8_yue2_widgets_v1": values}, "widgets_values": list(values.values())}
        nodes = [provider, node]
        links = [[1, 1, 0, 2, 1 if local else 0, "T8_LLM_PROVIDER_CONFIG" if local else "STRING"]]
        for index, name in enumerate(("style", "lyrics", "abc", "yue2_request_json", "creation_report_json")):
            show = _show_text_node(index + 3, index + 2, [1250 + (index // 3) * 500, 40 + (index % 3) * 390])
            show["title"] = name
            nodes.append(show)
            links.append([index + 2, 2, index, index + 3, 0, "STRING"])
        result[stem] = _workflow(stem, nodes, links)
    return result


def main():
    for stem, workflow in generate().items():
        path = ROOT / "example_workflows" / (stem + ".json")
        path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_thumbnail(path.with_suffix(".jpg"), "YuE2 - " + stem.split("_")[1], "LLM / local GGUF", "style + lyrics + ABC", "T8: text creation; no audio model required")
        print(path.name)


if __name__ == "__main__":
    main()
