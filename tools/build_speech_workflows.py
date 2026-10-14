"""Build only the two new speech examples; never rewrite earlier workflows."""
import argparse
import copy
import json
from pathlib import Path

from build_example_workflows import _workflow, _write_thumbnail

ROOT = Path(__file__).resolve().parents[1]
STEMS = ("speech_reference_h3", "speech_reference_seedance20")
NAMES = ("mode", "source_mode", "purpose", "provided_text", "provided_format", "speaker_map_json",
         "partial_policy", "failure_policy", "start_s", "duration_s", "language", "context",
         "audio_track", "channel", "offset_ms", "timeout_s")
SUBTITLE = "1\n00:00:00,000 --> 00:00:02,000\n等我回来。"
VALUES = ["Enabled", "Provided text", "keep_dialogue", SUBTITLE, "srt", '{"default":"<Subject 1> / S1"}',
          "reject", "stop", 0., 0., "Auto", "", 0, "mean", 0, 1800.]


def generate():
    result = {}
    for target in ("h3", "seedance20"):
        source = json.loads((ROOT / "example_workflows" / f"combat_camera_{target}.json").read_text(encoding="utf-8"))
        main = next(n for n in source["nodes"] if n["type"].endswith("PromptEnhancerT8"))
        # Remove only the optional camera from this independent derivation.
        source["nodes"] = [n for n in source["nodes"] if n["type"] != "T8CombatCameraConfig"]
        source["links"] = [link for link in source["links"] if link[-1] != "T8_COMBAT_CAMERA_CONFIG"]
        next(item for item in main["inputs"] if item["name"] == "combat_camera_config")["link"] = None
        main["title"] = "已有字幕参考 / Provided subtitle · " + target
        main["widgets_values"][0] = "一名成年女子在车站门边停下，把车票收入口袋，说出已指定的原句，然后转身离开。只有她一个角色，不新增对白或字幕。"
        main["widgets_values"][2 if target == "h3" else 3] = 5 if target == "h3" else "5"
        main["widgets_values"][3 if target == "h3" else 4] = "1"
        slot = len(main["inputs"])
        main["inputs"].append({"name": "speech_reference", "type": "T8_SPEECH_REFERENCE", "shape": 7, "link": 5})
        helper = dict(id=6, type="T8SpeechReference", pos=[0, 280], size=[460, 480], flags={}, order=0, mode=0,
            title="离线字幕 · 已显式指派角色 / Offline subtitle + role map",
            inputs=[{"name": name, "type": kind, "shape": 7, "link": None} for name, kind in
                    (("audio", "AUDIO"), ("video", "VIDEO"), ("provider_config", "T8_LLM_PROVIDER_CONFIG"))],
            outputs=[{"name": name, "type": kind, "links": links} for name, kind, links in
                     (("speech_reference", "T8_SPEECH_REFERENCE", [5]), ("speech_text", "STRING", None),
                      ("timed_transcript_json", "STRING", None), ("subtitles_srt", "STRING", None))],
            properties={"Node name for S&R": "T8SpeechReference", "t8_speech_widgets_v1": dict(zip(NAMES, VALUES))},
            widgets_values=copy.deepcopy(VALUES), widgets_values_named=dict(zip(NAMES, VALUES)))
        if target == "seedance20":
            helper["widgets_values"][5] = '{"default":"讲解者"}'
            helper["widgets_values_named"]["speaker_map_json"] = helper["widgets_values"][5]
            helper["properties"]["t8_speech_widgets_v1"]["speaker_map_json"] = helper["widgets_values"][5]
        source["nodes"].append(helper)
        source["links"].append([5, 6, 0, main["id"], slot, "T8_SPEECH_REFERENCE"])
        stem = f"speech_reference_{target}"
        result[stem] = _workflow(stem, source["nodes"], source["links"])
    return result


def check():
    for stem, expected in generate().items():
        path = ROOT / "example_workflows" / (stem + ".json")
        assert json.loads(path.read_text(encoding="utf-8")) == expected, stem
        assert path.with_suffix(".jpg").is_file(), stem
        assert "sk-" not in path.read_text(encoding="utf-8")
        nodes = {n["id"]: n for n in expected["nodes"]}
        assert nodes[1]["widgets_values"] == [""]
        assert len(nodes[6]["widgets_values"]) == 16
        main = next(n for n in expected["nodes"] if n["type"].endswith("PromptEnhancerT8"))
        assert len(main["widgets_values"]) == 38
        for lid, src, port, dst, slot, kind in expected["links"]:
            assert nodes[src]["outputs"][port]["type"] == nodes[dst]["inputs"][slot]["type"] == kind
            assert lid in nodes[src]["outputs"][port]["links"] and nodes[dst]["inputs"][slot]["link"] == lid
    print("Speech examples: two independent workflows, blank keys, 16+38 widgets and native links verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        for stem, value in generate().items():
            path = ROOT / "example_workflows" / (stem + ".json")
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _write_thumbnail(path.with_suffix(".jpg"), "OPTIONAL SPEECH REFERENCE", "Provided subtitles / Explicit roles", "H3 / Seedance native prompts", "Offline subtitle | Blank API key | No audio generation")
    check()
