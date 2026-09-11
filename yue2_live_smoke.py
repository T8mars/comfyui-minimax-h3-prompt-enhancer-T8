"""Opt-in paid YuE2 text acceptance. Reads a key without echo; never saves it."""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
SPEC = importlib.util.spec_from_file_location("t8_yue2_live", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
yue = sys.modules[SPEC.name + ".yue2"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="runtime/yue2-acceptance")
    parser.add_argument("--local-model", default="")
    parser.add_argument("--local-reviewed", action="store_true")
    parser.add_argument("--abc-regression", action="store_true", help="Paid full/melody score regression with unchanged English lyrics and Chinese language control")
    parser.add_argument("--abc-case", choices=("full", "melody"), help="Limit --abc-regression to one mode")
    args = parser.parse_args()
    key = "" if args.local_model else getpass.getpass("API key (not saved): ")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.local_model:
        provider_module = sys.modules[yue.LocalQwenProvider.__module__]
        original_complete = provider_module.LOCAL_QWEN_MANAGER.complete
        def capture_complete(server, **options):
            result = original_complete(server, **options)
            (output / "local_runtime_evidence.json").write_text(json.dumps({
                "runtime_class": type(server).__name__, "max_tokens": options.get("max_tokens"),
                "response_format": options.get("response_format"), "usage": result[1],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        provider_module.LOCAL_QWEN_MANAGER.complete = capture_complete
        class RecordingLocalProvider(yue.LocalQwenProvider):
            count = 0
            def complete(self, messages, **options):
                text = super().complete(messages, **options)
                self.count += 1
                (output / f"local_reply_{self.count}.txt").write_text(text, encoding="utf-8")
                return text
        yue.LocalQwenProvider = RecordingLocalProvider
    original = "[Verse]\n车窗留着雨的形状\n旧地图折进了衣裳\n\n[Chorus]\n把明天唱给远方\n让灯火接住目光\n\n[Verse]\n绕过没说完的惆怅\n路牌已换新的方向\n\n[Chorus]\n把明天唱给远方\n让灯火接住目光\n"
    cases = [
        ("zh_new_reviewed", dict(music_idea="原创中文公路歌。离乡青年清晨带着旧地图出发，从犹豫到决定向前；不要空泛口号。女声、钢琴与吉他，88 BPM，短而易记的副歌，完整主副歌结构。", quality_mode=yue.REVIEW)),
        ("en_new", dict(music_idea="An original English folk song: a night-shift baker sees sunrise after sharing the last loaf with a stranger. Concrete images, warm male voice, acoustic guitar, memorable chorus. Two short verses and repeated chorus.", lyrics_language="English")),
        ("zh_preserve", dict(music_idea="原词严格保留，温暖摇滚版，主歌克制、副歌开阔，干净电吉他与弹性鼓组。", lyrics=original)),
        ("zh_edit_second_chorus", dict(music_idea="中文公路歌，温暖女声钢琴吉他，歌词其余部分不要改。", lyrics=original, lyrics_mode=yue.EDIT, edit_section="Chorus", edit_occurrence=2, edit_request="只改第二次副歌，以具体的黎明意象表现终于出发，保持两行。")),
    ]
    if args.abc_regression:
        original = "[Verse]\r\nI kept a light beside the door\r\nFor every dream we had before\r\n\r\n[Chorus]\r\nCarry the dawn into the rain\r\nWe learn to start again\r\n"
        cases = [("abc_" + cot, dict(music_idea="流行pop, r&b", lyrics=original,
                  lyrics_mode=yue.PRESERVE, lyrics_language="中文", cot=cot)) for cot in ("full", "melody")]
        if args.abc_case:
            cases = [case for case in cases if case[1]["cot"] == args.abc_case]
    if args.local_model:
        cases = cases if args.abc_regression else cases[:1]
        cases[0][1]["quality_mode"] = yue.REVIEW if args.local_reviewed else yue.STANDARD
    original_stage = yue.YuE2Runner.complete
    stage_outputs = []
    def traced_stage(runner, stage, *positional, **options):
        print(json.dumps({"stage": stage, "event": "started", "model": runner.model}), flush=True)
        result = original_stage(runner, stage, *positional, **options)
        if args.abc_regression:
            stage_outputs.append({**runner.stages[-1], "result": result})
            serialized = json.dumps(stage_outputs, ensure_ascii=False, indent=2)
            (output / "abc_stage_outputs.json").write_text(serialized.replace(key, "[redacted]") if key else serialized, encoding="utf-8")
        print(json.dumps({"stage": stage, "event": "completed"}), flush=True)
        return result
    yue.YuE2Runner.complete = traced_stage
    rows = []
    for name, values in cases:
        if args.local_model:
            values.update(api_mode=yue.LOCAL_QWEN_API_MODE, local_model=args.local_model, local_context_size=16384, local_max_tokens=8192)
        started = time.monotonic()
        try:
            result = yue.enhance_yue2_prompt(api_key=key, seed=314159, **values)
            request, report = json.loads(result[3]), json.loads(result[4])
            yue.validate_request(request)
            if not args.abc_regression:
                assert report["checks"]["lyrics_language"]
            else:
                assert result[1] == original
                assert result[2] and result[2] == request["abc"]
                score = yue.yue2_abc.parse_abc(result[2])
                assert bool(score.voices["Vocal"].chords) == (values["cot"] == "full")
                assert score.voices["Vocal"].bars == score.voices["Ins"].bars
            if name == "zh_preserve":
                assert result[1] == original
            if name == "zh_edit_second_chorus":
                start, end = yue.edit_span(original, "Chorus", 2)
                assert result[1].startswith(original[:start]) and result[1].endswith(original[end:])
            artifact = {"case": name, "input": values, "request": request, "report": report}
            (output / (name + ".json")).write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rows.append({"case": name, "passed": True, "requests": report["requests"], "seconds": round(time.monotonic() - started, 2), "text_review": report["review"]})
        except Exception as exc:
            rows.append({"case": name, "passed": False, "error_type": type(exc).__name__, "error": str(exc).replace(key, "[redacted]") if key else str(exc)})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    (output / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
