"""User-initiated Seedance-only Relay smoke; read the key from stdin, never save it."""
import importlib.util
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
spec = importlib.util.spec_from_file_location("h3_relay_live_nodes", ROOT / "nodes.py")
nodes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nodes)


def main():
    key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("Provide the API key on stdin.")
    cases = [
        ("explicit_8s", 8, 0, 3, "0-2.5\n2.5-5\n5-8", "女生在站台捡起车票，交给回头的乘客，说“你的车票。”，对方点头，她挥手告别。8秒，一镜到底，无配乐。"),
        ("weighted_25_29s", 25, 25.29, 0, "", "25.29秒，一个连续镜头。清晨的修表铺，老师傅戴着放大镜检查怀表，用镊子将松脱齿轮归位，轻转表冠，指针开始走动。他把修好的表交给等候的青年；青年看表后微笑。无对白，无字幕，无配乐，保留自然工具声。不改变道具持有关系。"),
        ("ref_two_images", 8, 0, 2, "0-4\n4-8", "两张输入是测试纯色色卡：图片1红色，图片2蓝色，仅参考颜色。白色桌面上红纸片从左侧滑入，蓝纸片从右侧滑入，两者靠拢后同时静止。8秒，一镜到底，无人物、对白、字幕或配乐，保留纸片滑动摩擦声。"),
    ]
    if len(sys.argv) > 1:
        cases = [case for case in cases if case[0] == sys.argv[1]]
        if not cases:
            raise SystemExit("Unknown smoke case")
    output_dir = ROOT / "runtime/h3-relay-live"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = []
    for label, seconds, exact, count, ranges, prompt in cases:
        started = time.monotonic()
        media = {}
        if label == "ref_two_images":
            red = torch.zeros((1, 256, 256, 3))
            blue = torch.zeros_like(red)
            red[..., 0] = 1
            blue[..., 2] = 1
            media = {"reference_images": {"reference_image_0": red, "reference_image_1": blue}}
        result = nodes.MiniMaxH3PromptEnhancer.execute(
            prompt=prompt, task_type="Ref2VA" if media else "T2VA", duration_seconds=seconds,
            rewrite_mode="balanced", description_word_target=0, output_language="中文",
            api_mode=nodes.SEEDANCE_API_MODE, api_key=key, shot_count="1",
            relay_mode=nodes.RELAY, relay_event_count=count,
            relay_duration_seconds=exact, relay_time_ranges=ranges,
            recovery_slot="t8-live-relay-" + label,
            **media,
        )
        report = json.loads(result[5])
        outputs = dict(zip(("enhanced_prompt", "global_prompt", "local_prompts", "time_ranges", "relay_length", "relay_report"), result.result))
        serialized = json.dumps(outputs, ensure_ascii=False, indent=2)
        if key in serialized:
            raise RuntimeError("Secret appeared in output; refusing to save.")
        (output_dir / (label + ".json")).write_text(serialized, encoding="utf-8")
        assert all(result[i] for i in (0, 1, 2, 3, 5))
        assert report["delivery_frames"] == round((exact or seconds) * 24)
        assert (result[4] - 5) % 17 == 0
        if label == "explicit_8s":
            assert "你的车票。" in result[2] and "你的车票。" not in result[1]
        restored = nodes.MiniMaxH3PromptEnhancer.execute(
            prompt="", task_type="T2VA", duration_seconds=seconds,
            rewrite_mode="balanced", description_word_target=0,
            relay_mode=nodes.RELAY, recovery_slot="t8-live-relay-" + label,
            recovery_action=nodes.RECOVERY_ACTION_RESTORE,
        )
        assert tuple(restored.result) == tuple(result.result)
        item = {"case": label, "seconds": round(time.monotonic() - started, 2),
                "provider": "Seedance", "model": nodes.MODEL_ID, "events": report["event_count"],
                "delivery_frames": report["delivery_frames"], "relay_length": result[4], "recovery_exact": True}
        evidence.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    summary = output_dir / "summary.json"
    previous = json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else []
    current = {item["case"]: item for item in previous}
    current.update({item["case"]: item for item in evidence})
    summary.write_text(json.dumps(list(current.values()), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
