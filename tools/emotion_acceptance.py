"""Opt-in real production API paired observations, not video evaluation.

12 frozen cases x 2 modes x 2 repeats. Hidden credential stays in memory.
No GGUF/video load. Failed slots are preserved, never automatically resubmitted.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1]))
import comfy.cli_args
comfy.cli_args.args.cpu = True
from tools.directional_skill_acceptance import load_package, digest
from tools.h3_quality_acceptance import response_metrics

CASES = [
    dict(id="restrained_tears", target="h3", prompt="8秒一个固定胸部以上镜头，成年女人含泪却尽力保持平静，独自对画外右侧说原句“我知道了。”一次。声音低但清楚，不哭腔、不抽泣、不大声；说完仍有伤心余绪，继续望着画外右侧，不突然微笑。眼泪停在眼眶，不新增电话、信件或人物。没有配乐、字幕或环境声，只允许这句对白。"),
    dict(id="smiling_threat", target="h3", prompt="8秒固定近景，成年女人全程保留礼貌微笑，独自低声清楚说“你可以再试一次。”一次。语气有冷静威胁意味，不吼叫、不咬牙、不收起笑容、不加剧情或武器。说完仍微笑看向画外左侧，无字幕、音乐和其他声音，只这句对白。"),
    dict(id="numb_speech", target="h3", prompt="8秒固定中近景，疲惫的成年女人麻木而平稳地说原句“明天照常上班。”一次；发音清楚、正常口型，不哭不笑、不屏住呼吸。说完仍麻木站着，不新增道具、同伴、字幕或情节。只有这句对白，其他声音与配乐都没有。"),
    dict(id="carryover", target="h3", prompt="8秒连续中近景，成年女人独自在窗前，起初强忍失落；她主动决定继续等待，缓缓把视线从窗外转到已有关闭的门，尝试平静但眼眶的紧绷仍残留；末尾继续等待，门不开。没有新人物、画外消息、敲门声或对白，无字幕；全片完全静音。"),
    dict(id="heightened", target="h3", prompt="8秒一个固定中景，成年男人独自明显愤怒，大幅甩开双臂并用响亮但清楚的声音说原句“到此为止！”一次。是明确外放的爆发，不要缩成细微克制。他说完仍紧绷站着，不摔物品、不伤害人、不新增道具或反转。只有这句对白，没有配乐、字幕或其他声音。"),
    dict(id="crop_and_silence", target="h3", prompt="8秒固定极近特写，仅成年女人的眼睛和眉毛在画面内，不可重新构图、拉远或切镜。她由紧张逐渐恢复平稳注视，最后仍有轻微警觉，不新增触发情节，不描写可见手脚、肩膀或嘴。完全静音、无字幕无配乐无对白。"),
    dict(id="two_bibles", target="h3", bibles=True, prompt="8秒固定双人中景：红袖Alice右手持钥匙，蓝袖Bob双手空着，门始终关闭。Alice只低声说“等我。”一次，Bob只清楚说“我在这里。”一次，两句依次完整说完。Alice焦急但声音清楚，Bob平稳，不把Alice的情绪和声音复制给Bob。钥匙不交换、不新增人、道具、对白、字幕或开门；只有这两句声音，无配乐环境声。"),
    dict(id="non_character", target="h3", prompt="8秒固定镜头，没有脸的红色小玩具车沿已有灰轨向右连续滚动，结束仍滚动，不停车、不变形。纯机械展示，无人物、拟人、眼睛、呼吸、情绪或对白。只有滚轮摩擦声，无字幕无配乐。"),
    dict(id="relay_wait", target="relay", prompt="8秒一个连续固定中景，成年女人红色袖口，右手始终拿车票。前4秒安静站着等待、视线固定画外右侧；后4秒自行决定前往已有出口，沿走廊迈步，保留等待时的紧张余绪；最后仍在移动，不定格。没有消息、敲门、其他人物或对白，只有脚步声，无配乐无字幕。"),
    dict(id="relay_exact_line", target="relay", prompt="8秒一个固定中近景，成年女人。前4秒仅低声清楚说“等我回来。”一次，后4秒不再发声，凝视画外右侧并保持先前担忧余绪。无切镜，无新增人、道具、事件、回答或下一句。只有这句对白，无配乐、环境声和字幕，末尾仍凝视，不定格。"),
    dict(id="seedance_subtext", target="seedance20", skill="drama_scene", prompt="8秒一个固定双人中景，Alice右手拿黄票，Bob不接票。Alice平静低声说原句“你先走吧。”一次，情绪依恋但不哭不笑不拉人。Bob全程安静、没有反应，票始终在Alice右手；关系故意开放，不推断分手、不编背景。没有其他声音、配乐或字幕，最后仍面对面站着。"),
    dict(id="seedance_carryover", target="seedance20", skill="situational_drama", prompt="8秒一个固定中近景，成年女人独自深夜等车，双手不做动作。起初焦急；她主动让自己平静地等待，但眉间仍留轻微紧绷，末尾继续望向画外左侧，不突然笑、不走、不换姿势。不新增车、人、物品、手机、消息或触发声，没有对白、字幕或配乐；全片完全静音。"),
]


def assess_text(quality, h3, case, text):
    """Offline checks accept only their native signature; Relay is compiled first."""
    if case["target"] == "seedance20":
        return quality.check_seedance(text, language="中文", source=case["prompt"], shot_count=1)
    if case["target"] == "relay":
        from h3_prompt_relay import compile_relay_response
        compiled = compile_relay_response(text, 8, 2, "0-4\n4-8", "T2VA", "中文")
        text = compiled["enhanced_prompt"]
    return quality.check_h3(text, task_type="T2VA", duration=8, shot_count=1, language="中文", source=case["prompt"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Skip ALL observed slots, including failures; never retry implicitly.")
    parser.add_argument("--recheck-captured", action="store_true", help="Recheck captured returns offline after an evaluator error, no new request.")
    parser.add_argument("--case", choices=[c["id"] for c in CASES], action="append", help="Explicit bounded follow-up subset; never replace failed observations.")
    parser.add_argument("--arm", choices=["both", "tudou", "extreme"], default="both")
    parser.add_argument("--repeats", choices=[1, 2], type=int, default=2)
    parser.add_argument("--quality", choices=["off", "repair"], default="off", help="Explicit existing bounded quality path, not implicitly enabled by the strategy.")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    h3, sd, _runtime = load_package()
    perf = sys.modules[h3.__package__ + ".performance_director"]
    film = sys.modules[h3.__package__ + ".film_workflow"]
    quality = sys.modules[h3.__package__ + ".h3_quality"]
    fingerprints = {p: hashlib.sha256((ROOT / p).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in (
        "nodes.py", "seedance20.py", "performance_director.py", "emotion_performance.py", "directional_skills.py", "film_workflow.py", "h3_quality.py", "h3_prompt_relay.py", "quality_pipeline.py", "h3_vocal_protocol.py")}
    selected = [c for c in CASES if not args.case or c["id"] in args.case]
    settings = {"cases_sha256": digest(CASES), "code_sha256": fingerprints, "quality": args.quality, "creation": "off", "requested_model": h3.MODEL_ID, "provider": h3.SEEDANCE_API_MODE, "repeats": args.repeats, "duration": 8, "shots": 1, "language": "中文", "rewrite": "balanced", "selected_cases": [c["id"] for c in selected], "arms": args.arm}
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "observations.json"
    snapshot = {"schema": "t8-emotion-api-observations/v1", "settings": settings, "cases": CASES, "tests": [], "limitations": "Synthetic text scenes only; no real reference upload, local 9B or rendered video evidence. Checks are advisory until reviewed. No inference benefit or statistical significance claimed."}
    if path.exists():
        if not args.resume:
            raise SystemExit("Evidence exists; --resume skips observed slots without resubmission.")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot["settings"] != settings:
            raise SystemExit("Code or frozen settings changed; use a new evidence directory.")
    observed = {(t["case_id"], t["repeat"], t["arm"]) for t in snapshot["tests"]}
    if args.recheck_captured:
        for record in snapshot["tests"]:
            if record.get("error_type") != "TypeError" or record.get("outcome") != "failed":
                continue
            captured = record.get("calls", [])
            if not captured or not captured[-1].get("output"):
                continue
            case = next(c for c in CASES if c["id"] == record["case_id"])
            text = h3._reorder_complete_fields(captured[-1]["output"], "T2VA")
            record.update(outcome="success", output=text, output_sha256=digest(text), contract_check=assess_text(quality, h3, case, text), evaluator_note="Original TypeError was an unsupported offline check argument, not a generation failure. Captured production output rechecked without another API request.")
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    key = getpass.getpass("API key (hidden, memory only): ")
    if not key:
        raise SystemExit("Missing credential.")
    original_request = h3._request_completion
    original_post = h3.requests.Session.post
    calls = []

    def request(*values, **kwargs):
        item = {"message_sha256": digest(values[2]), "messages": values[2], "model_id": values[6], "http_attempts": []}
        calls.append(item)
        start = time.monotonic()
        try:
            text = original_request(*values, **kwargs)
            item.update(output=text, output_sha256=digest(text))
            return text
        except Exception as error:
            item["error_type"] = type(error).__name__
            raise
        finally:
            item["elapsed_seconds"] = round(time.monotonic() - start, 3)

    def post(self, *values, **kwargs):
        payload = kwargs.get("json") or {}
        item = {"parameters": {k: payload[k] for k in ("model", "stream", "temperature", "seed", "max_tokens", "max_completion_tokens", "reasoning_effort") if k in payload}}
        if calls:
            calls[-1]["http_attempts"].append(item)
        try:
            response = original_post(self, *values, **kwargs)
        except Exception as error:
            item["error_type"] = type(error).__name__
            raise
        item["status"] = response.status_code
        if "json" in response.headers.get("Content-Type", "").lower():
            try:
                response_metrics(response.json(), item)
            except ValueError:
                pass
        elif kwargs.get("stream"):
            original_lines = response.iter_lines
            def lines(*args, **opts):
                for raw in original_lines(*args, **opts):
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try:
                            response_metrics(json.loads(line.strip()[5:].strip()), item)
                        except ValueError:
                            pass
                    yield raw
            response.iter_lines = lines
        return response

    try:
        with patch.object(h3, "_request_completion", request), patch.object(sd, "_request_completion", request), patch.object(h3.requests.Session, "post", post):
            for case in selected:
                for repeat in range(args.repeats):
                    for arm in (("extreme", "tudou") if repeat == 0 else ("tudou", "extreme")):
                        if args.arm != "both" and arm != args.arm:
                            continue
                        if (case["id"], repeat, arm) in observed:
                            continue
                        calls.clear()
                        start = time.monotonic()
                        record = {"case_id": case["id"], "repeat": repeat, "arm": arm, "writing_seed": 10420 + repeat, "input_sha256": digest(case)}
                        quality_events = []
                        values = dict(prompt=case["prompt"], duration_seconds=8, shot_count="1", output_language="中文", rewrite_mode="balanced", api_key=key, seed=10420 + repeat, quality_mode=args.quality, creation_mode="off", director_skill=case.get("skill", "none"), performance_director_config=perf.build_performance_director_config(perf.PERFORMANCE_EXTREME if arm == "extreme" else perf.PERFORMANCE_TUDOU), progress_callback=lambda stage, **kw: quality_events.append(kw["quality_metadata"]) if isinstance(kw.get("quality_metadata"), dict) else None)
                        if case.get("bibles"):
                            values["character_performance_bible"] = film.build_character_performance_set([
                                film.build_character_performance_bible("Alice", "让Bob等她", "她焦急但门仍关闭", voice_lock="低声清楚，焦急不影响可懂度", physical_task_and_inertia="右手一直持钥匙"),
                                film.build_character_performance_bible("Bob", "原地等Alice", "不能替Alice开门", voice_lock="清楚平稳，不复制焦急", physical_task_and_inertia="双手空置"),
                            ])
                        if case["target"] == "relay":
                            values["relay_config"] = {"event_count": 2, "time_ranges": "0-4\n4-8"}
                        interrupted = False
                        try:
                            if case["target"] == "seedance20":
                                text = sd.enhance_seedance20_prompt(task_intent="T2V", **values)
                            else:
                                text = h3.enhance_prompt(task_type="T2VA", **values)
                            record["generated_text"] = text
                            check = assess_text(quality, h3, case, text)
                            record.update(outcome="success", output=text, output_sha256=digest(text), contract_check=check)
                        except KeyboardInterrupt:
                            record.update(outcome="interrupted", error_type="KeyboardInterrupt")
                            interrupted = True
                        except Exception as error:
                            record.update(outcome="failed", error_type=type(error).__name__)
                            match = re.search(r"\bstatus=(\d+)\b", str(error))
                            if match:
                                record["error_status"] = int(match.group(1))
                        record.update(logical_calls=len(calls), calls=copy_calls(calls), elapsed_seconds=round(time.monotonic() - start, 3), quality_events=quality_events)
                        if key in json.dumps(record, ensure_ascii=False):
                            raise SystemExit("Secret safety check failed; nothing saved.")
                        snapshot["tests"].append(record)
                        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                        print(json.dumps({k: record[k] for k in ("case_id", "repeat", "arm", "outcome", "logical_calls", "elapsed_seconds")}), flush=True)
                        if interrupted:
                            raise SystemExit("Interrupted slot retained; resume will not resubmit it.")
                        if record.get("error_status") in (401, 402, 403, 429) or any(a.get("status") in (401, 402, 403, 429) for c in calls for a in c["http_attempts"]):
                            raise SystemExit("Authentication, balance or rate limit requires attention; no repeated submission.")
    finally:
        key = ""
    items = []
    mapping = {}
    rng = random.Random(10448)
    tests = list(snapshot["tests"])
    rng.shuffle(tests)
    for n, record in enumerate(tests):
        label = f"E{n + 1:02d}"
        case = next(c for c in CASES if c["id"] == record["case_id"])
        items.append({"label": label, "case_id": case["id"], "input": case["prompt"], "output": record.get("output", ""), "outcome": record["outcome"]})
        mapping[label] = {k: record[k] for k in ("case_id", "repeat", "arm")}
    (destination / "blind-texts.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "blind-mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_calls(calls):
    return json.loads(json.dumps(calls, ensure_ascii=False))


if __name__ == "__main__":
    main()
