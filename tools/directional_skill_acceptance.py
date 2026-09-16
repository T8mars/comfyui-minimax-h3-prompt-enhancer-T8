"""Opt-in paid/local acceptance. Secrets come only from an environment variable.

Run serially; local mode explicitly selects 9B and unloads after every completion.
Evidence is written outside the repository, never to a committed fixture by default.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
sys.path.insert(0, str(ROOT))

CASES = [
    {"id": "take30", "skill": "continuous_combat", "duration": 30,
     "prompt": "30秒写实电影训练场，两名成年练习者使用各自已有的木杖连续攻防，主角红袖、对手灰袖。全程一个连续镜头，不硬切，不新增武器或超自然能力；木杖碰撞改变脚步路线，已有地面木屑持续移动，结尾两人仍在移动，没有指定胜负。无对白，无字幕，无配乐。"},
    {"id": "take8route", "skill": "continuous_combat", "duration": 8,
     "prompt": "8秒，一台无脸无声音的四足小机器人单独从画面左侧石台出发，沿已有栏杆下方跨过两块台阶，抵达右侧木桥入口。一个连续镜头，最后一帧前足刚踏上木桥，后足仍在移动；不能瞬移，不增加人或敌人、不增加武器或能力，不冻结，只有机械运动声，无字幕，无配乐。"},
    {"id": "exchange15", "skill": "high_density_combat", "duration": 15,
     "prompt": "15秒，成年红袖练习者双手空置，对手灰袖只持一根木杖，在雨后练习场做连续影视攻防。徒手方避开杖端并承接上一交换的滑步，对手回应真实线路；不裸手抓杖端，不增加武器、能力或第三人。中段红袖练习者低声说原句“让开。”，必须逐字保留，只有这一句对白。结尾对手的木杖仍由对手持有，没有指定胜负，两人仍在连续移动，无字幕，无配乐。"},
    {"id": "solo5", "skill": "high_density_combat", "duration": 5,
     "prompt": "5秒，一台已有四足和机械关节的无脸机器人独自做绕桩练习，连续侧移，支撑足蹬地，滑过松散木屑后改线。不能新增敌人、人脸、呼吸、对白、武器、能力、爆炸；无镜头切换，无停顿，最后仍在移动。只有电机和摩擦声，无字幕，无配乐。"},
    {"id": "escort10wait", "skill": "cinematic_gunfight", "duration": 10,
     "prompt": "10秒虚构写实电影车厢护送：两名成年人物，红外套护送者和蓝外套同行者都没有武器。开头两秒静静等待车厢外远处枪声，随后护送者把同行者带向已有车门。战争只在车窗外背景中，不增加车厢内枪手或武器，不把背景改成主戏。结尾两人到达车门旁，门仍关闭，不擅自开门或跳车；一个镜头，无对白，无字幕，无配乐。"},
    {"id": "foreground15", "skill": "cinematic_gunfight", "duration": 15,
     "prompt": "15秒虚构影视片段，三名成年人物：红外套主角持一把已有道具手枪，蓝外套同行者双手空置，灰外套阻挡者持一把已有道具手枪。旧仓库中主戏是把同行者带到右侧已有出口，远处战场只作背景。用短促交锋、人物回应与家具位移展现压力，不添加人物或新武器，不描述现实操作教学。主角全程保留自己的枪，同伴全程空手；结尾两人仍向出口移动，没有指定击杀或胜负。无对白、字幕、配乐，不新增match cut或枪械变形。"},
]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_package():
    spec = importlib.util.spec_from_file_location("t8_directional_acceptance", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    return sys.modules[spec.name + ".nodes"], sys.modules[spec.name + ".seedance20"], sys.modules[spec.name + ".local_qwen_runtime"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["cloud", "local"], required=True)
    parser.add_argument("--target", choices=["h3", "seedance20", "both"], default="both")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", choices=[case["id"] for case in CASES], action="append")
    parser.add_argument("--h3-repeats", type=int, choices=[1, 2], default=2)
    parser.add_argument("--selection", choices=["both", "on", "off"], default="both")
    args = parser.parse_args()
    if ROOT == args.output_dir.resolve() or ROOT in args.output_dir.resolve().parents:
        raise SystemExit("Acceptance evidence must be outside the repository.")
    key = os.environ.get("T8_DIRECTIONAL_TEST_KEY", "")
    if args.provider == "cloud" and not key:
        raise SystemExit("Set T8_DIRECTIONAL_TEST_KEY for this process; never put a key in the script.")
    h3, sd, runtime = load_package()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = ["h3", "seedance20"] if args.target == "both" else [args.target]
    cases = [case for case in CASES if not args.case or case["id"] in args.case]
    snapshot = {"schema": "t8-directional-acceptance/v1", "provider": args.provider,
                "tests": [], "cases": cases, "media": "Text-only factual scenes; multimodal parameter/format paths have separate offline regression tests.",
                "evaluation": "Paired exploratory text evidence, not video quality or statistical significance."}
    destination = args.output_dir / f"{args.provider}-{args.target}{'-' + '-'.join(args.case) if args.case else ''}{'-' + args.selection if args.selection != 'both' else ''}.json"
    original_request = h3._request_completion
    original_local = h3.LocalQwenProvider.complete
    original_manager = runtime.LOCAL_QWEN_MANAGER.complete
    original_post = h3.requests.Session.post
    active_requests = []

    def response_metrics(event, observation):
        if not isinstance(event, dict):
            return
        usage = event.get("usage")
        if isinstance(usage, dict):
            observation["usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance(usage.get(k), int)}
        if isinstance(event.get("model"), str):
            observation["response_model"] = event["model"]
        for choice in event.get("choices") or []:
            if isinstance(choice, dict) and choice.get("finish_reason") is not None:
                observation["finish_reason"] = str(choice["finish_reason"])

    def observed_post(self, *values, **kwargs):
        payload = kwargs.get("json") or {}
        observation = {"request_parameters": {k: payload[k] for k in ("model", "stream", "temperature", "seed", "max_tokens", "max_completion_tokens", "reasoning_effort") if k in payload}}
        if active_requests:
            active_requests[-1].setdefault("http_attempts", []).append(observation)
        try:
            response = original_post(self, *values, **kwargs)
        except h3.requests.RequestException as error:
            observation["error_type"] = type(error).__name__
            raise
        observation["status"] = response.status_code
        if "json" in str(response.headers.get("Content-Type", "")).lower():
            try:
                response_metrics(response.json(), observation)
            except ValueError:
                pass
        elif kwargs.get("stream"):
            original_lines = response.iter_lines

            def lines(*args, **line_kwargs):
                for raw in original_lines(*args, **line_kwargs):
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try:
                            response_metrics(json.loads(line.strip()[5:].strip()), observation)
                        except ValueError:
                            pass
                    yield raw
            response.iter_lines = lines
        return response

    def observed_request(*values, **kwargs):
        messages = values[2]
        active_requests.append({"message_sha256": digest(messages), "model_id": values[6],
                                "rewrite_mode": values[3], "provider_request_options": kwargs.get("provider_request_options"),
                                "temperature_override": kwargs.get("temperature_override")})
        return original_request(*values, **kwargs)

    def observed_local(self, messages, **kwargs):
        model_path = runtime.resolve_model_path(self.settings.model_filename, label="acceptance 9B model")
        active_requests.append({"message_sha256": digest(messages), "parameters": kwargs,
                                "model_file": model_path.name,
                                "model_bytes": model_path.stat().st_size,
                                "settings": {k: v for k, v in vars(self.settings).items() if isinstance(v, (str, int, float, bool, type(None)))}})
        return original_local(self, messages, **kwargs)

    def observed_manager(*values, **kwargs):
        output, usage = original_manager(*values, **kwargs)
        active_requests[-1]["usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens", "finish_reason") if k in usage}
        active_requests[-1]["runtime_parameters"] = {k: kwargs[k] for k in ("max_tokens", "temperature", "seed", "think_mode", "reasoning_effort") if k in kwargs}
        return output, usage

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(h3.requests.Session, "post", observed_post))
            stack.enter_context(patch.object(h3, "_request_completion", observed_request))
            stack.enter_context(patch.object(sd, "_request_completion", observed_request))
            stack.enter_context(patch.object(h3.LocalQwenProvider, "complete", observed_local))
            stack.enter_context(patch.object(runtime.LOCAL_QWEN_MANAGER, "complete", observed_manager))
            # Existing standalone binary, bounded threads for this test process
            # only. Never persist runtime settings or load 27B.
            server_cls = getattr(runtime, "LocalQwenServer", None)
            if server_cls is None:
                server_cls = next((c for c in vars(runtime).values() if isinstance(c, type) and hasattr(c, "_start_arguments")), None)
            if args.provider == "local" and server_cls:
                old_arguments = server_cls._start_arguments
                stack.enter_context(patch.object(server_cls, "_start_arguments", lambda self: [*old_arguments(self), "--threads", "2", "--threads-batch", "2"]))
            for target in targets:
                repeats = args.h3_repeats if args.provider == "cloud" and target == "h3" else 1
                for case in cases:
                    for repeat in range(repeats):
                        selections = ("none", case["skill"]) if args.selection == "both" else ((case["skill"],) if args.selection == "on" else ("none",))
                        for selection in selections:
                            active_requests.clear()
                            started = time.monotonic()
                            record = {"case_id": case["id"], "target": target, "director_skill": selection, "repeat": repeat,
                                      "input_sha256": digest(case), "writing_seed": 6180 + repeat,
                                      "duration": case["duration"], "selected_language": "中文"}
                            values = dict(prompt=case["prompt"], duration_seconds=case["duration"], shot_count="1" if case["skill"] == "continuous_combat" or case["id"] in {"solo5", "escort10wait"} else "AUTO（系统自动判断）",
                                          director_skill=selection, output_language="中文", rewrite_mode="balanced", seed=6180 + repeat,
                                          api_mode=h3.SEEDANCE_API_MODE if args.provider == "cloud" else h3.LOCAL_QWEN_API_MODE,
                                          api_key=key if args.provider == "cloud" else "", local_model="Qwen3.8/Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf",
                                          local_mmproj="AUTO（自动匹配）", local_context_size=16384, local_max_tokens=4096,
                                          local_think_mode=runtime.LOCAL_THINK_OFF, local_unload_policy=runtime.LOCAL_UNLOAD_AFTER_RUN)
                            # Each target receives its own task vocabulary/compiler.
                            try:
                                if target == "h3":
                                    output = h3.enhance_prompt(task_type="T2VA", **values)
                                else:
                                    values["shot_count"] = sd.AUTO_SHOT_COUNT if values["shot_count"].startswith("AUTO") else values["shot_count"]
                                    output = sd.enhance_seedance20_prompt(task_intent=sd.TASK_INTENT_LABELS["T2V"], **values)
                                record.update(outcome="success", output=output, output_sha256=digest(output))
                            except Exception as error:
                                # Only safe type/category; upstream text may contain private content.
                                record.update(outcome="failed", error_type=type(error).__name__)
                            record.update(elapsed_seconds=round(time.monotonic() - started, 3), requests=list(active_requests), call_count=len(active_requests))
                            snapshot["tests"].append(record)
                            destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                            print(json.dumps({k: record[k] for k in ("target", "case_id", "director_skill", "repeat", "outcome", "elapsed_seconds", "call_count")}), flush=True)
                            if record["outcome"] != "success":
                                raise SystemExit("Stopped on a real failure; inspect sanitized evidence before resubmission.")
    finally:
        if args.provider == "local":
            runtime.LOCAL_QWEN_MANAGER.release()
        key = ""


if __name__ == "__main__":
    main()
