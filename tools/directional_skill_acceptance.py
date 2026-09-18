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

NING_CASES = [
    {"id": "ning_dialogue", "skill": "ning_wenwu", "duration": 10, "shots": "1",
     "prompt": "10秒一个连续镜头。两名成年姐妹在室内，姐姐在画面左侧，妹妹在右侧；只有两人。姐姐在画外低声说原句“钥匙给我。”，画面关注妹妹，不把妹妹变成说话者。妹妹听完才停下左手擦杯的动作，右手一直握着已有钥匙，不交出。结尾杯在妹妹左手，钥匙在妹妹右手。只有这一句对白，无字幕无配乐，不增加人物、台词或新道具。"},
    {"id": "ning_rehearsal", "skill": "ning_wenwu", "duration": 8, "shots": "1",
     "prompt": "8秒一个连续镜头。两名成年练习者在木地板练习室做友好对练，甲红袖，乙蓝袖，各持自己已有的软垫短棒。甲试探点向乙肩但未命中，乙后撤避开后格挡甲的下一次试探；双方继续移动，不分胜负，不受伤。棒始终归原持有者。不要加人、武器、法术、震飞、爆尘、冻结或慢动作。无对白字幕配乐，只有脚步与软垫接触声。"},
    {"id": "ning_mixed", "skill": "ning_wenwu", "duration": 12, "shots": "1",
     "prompt": "12秒一个连续镜头。成年黑衣侍卫在走廊门口左侧，成年红衣来客在右侧。侍卫先低声说原句“到此为止。”，来客听完等2秒，才把右手已有的信放进自己的右侧口袋；随后侍卫拔出自己已有的长剑挡住通道，但全片不出击，来客不反击。结尾两人仍在门口，门仍关闭，信在来客右侧口袋，剑归侍卫。仅这一句台词，不加人、道具、能力或胜负。无字幕，无配乐。"},
    {"id": "ning_spectacle", "skill": "ning_wenwu", "duration": 10, "shots": "1",
     "prompt": "10秒一个连续镜头，无人、静音、安静的奇观。已有巨大石像缓缓从云海后显露，始终不动，柔和暖色日光，云层持续移动；画面下方已有山脊提供尺度。结尾石像上半身可见，下半身仍被云遮挡。不要人物、动物、攻击、BOSS、眼睛发光、爆炸、裂缝、文字或配乐；完全无声音。"},
    {"id": "ning_group", "skill": "ning_wenwu", "duration": 12, "shots": "2",
     "prompt": "12秒，恰好2个镜头，三名成年人在桌边，A左、B中、C右。A看B说原句“别急，先听完。”；B听完才把自己右手已有的杯放在面前桌上。C装作没听见，全程完全无表情或动作反应，不偷加握拳。仅A说这句，B和C不发声。第二镜头看B放杯，但不改变三人的空间关系。结尾杯在B面前桌上，三人仍在原位。不得加人、秘密、台词或道具，无字幕无配乐。"},
    {"id": "ning_fantasy", "skill": "ning_wenwu", "duration": 12, "shots": "2",
     "prompt": "12秒，2个镜头。成年白衣剑客甲与成年黑衣剑客乙在石台交锋，各持自己的已有长剑，甲已有蓝色剑气，乙已有红色剑气。甲横斩被乙格开，双方绕开彼此原线路继续移动；第二镜头拍清乙利用甲余势侧移，双色剑气沿各自剑刃延伸但不盖住身体。结尾两人都站立且继续移动，各自长剑与气色不交换，无胜负。不得增加神兽、第三人、觉醒、新技能、伤亡、冻结或黑屏。无台词字幕配乐。"},
    {"id": "ning_dance", "skill": "ning_wenwu", "duration": 8, "shots": "1",
     "prompt": "8秒，固定机位，一个连续镜头。一位成年女子独自在空舞室转身跳舞，只有她一人。转身重心与脚步变化清楚，结尾仍在移动。不得增加搭档、观众、失恋剧情、旁白、台词或镜头运动；没有道具。只有真实脚步和衣料声，无字幕无配乐，不冻结。"},
    {"id": "ning_robot", "skill": "ning_wenwu", "duration": 8, "shots": "1",
     "prompt": "8秒一个连续镜头，固定机位。只有一台无脸、不发声的四足机器人，沿画面左侧已有栏杆走向右侧已有木桥入口，跨过两块已有台阶。前2秒在原地完全静止等待，然后才出发。结尾前足刚踏上桥入口，后足仍移动，尚未到桥中央。不能加人、敌人、面孔、眼睛、呼吸、情绪、武器、能力或新障碍，只有机械与摩擦声，无对白字幕配乐。"},
]

NING_STRESS_CASES = [
    {"id": "ning_no_contact", "skill": "ning_wenwu", "duration": 8, "shots": "1",
     "prompt": "8秒，固定机位，一个连续镜头。两名成年练习者在已有洁净木地板练习室做高强度徒手闪避训练，甲红袖、乙蓝袖，都空手，无道具。甲的试探拳始终从乙肩外空处划过，乙通过后撤和侧移避开；全片两人的身体从不接触，保持正常速度不断移动。结尾双方仍站立且在移动，不定胜负。地面没有尘土，不要新增人物、道具、声音、尘土、伤害、法术、冻结或慢动作。全片完全静音，无台词字幕配乐，固定机位不得移动。"},
    {"id": "ning_original_ending", "skill": "ning_wenwu", "duration": 12, "shots": "1",
     "prompt": "原创一个12秒、一个连续镜头、温暖欢乐的重逢小片段。只有两位成年旧友，甲左、乙右，已有空房间和一张纸条，纸条始终在甲右手。允许你创作彼此目标以及恰好两句简短中文对白，每人一句；不需要照抄任何示例。不要新人物、道具、秘密、武器、法术或伤害。明确结尾：甲主动在画面左侧跪坐，右手仍持纸条，乙仍在右侧站立；不是摔倒或战败。不得把用户要求的跪坐改成站立或持续奔跑。声音仅两句对白和两人现有动作声，无字幕无配乐。"},
    {"id": "ning_joyful_spectacle", "skill": "ning_wenwu", "duration": 10, "shots": "1",
     "prompt": "10秒，一个连续镜头，无人、欢乐明亮的奇观。已有空地上是一排彩色纸风车，暖阳照着已有花带，上方已有一串系在原处的彩色气球；仅这些现有景物。风车轻快转动，花带随微风轻摆，气球始终系在原处。镜头可平滑地揭示色彩与运动关系，结尾风车仍转、花带与气球同时可见，保持轻快欢乐而非危机感。没有人、动物、人脸或观众，不加新景物、文字、危险、攻击、爆炸、崩塌、超能力或胜负。全片完全静音，无对白、字幕或配乐。"},
]
CASE_SUITES = {"legacy": CASES, "ning": NING_CASES, "ning-stress": NING_STRESS_CASES}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def contains_text(value, needle):
    """Confirm source transmission without persisting an entire private payload."""
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(contains_text(item, needle) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_text(item, needle) for item in value)
    return False


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
    parser.add_argument("--suite", choices=list(CASE_SUITES), default="legacy")
    parser.add_argument("--case", choices=[case["id"] for suite in CASE_SUITES.values() for case in suite], action="append")
    parser.add_argument("--h3-repeats", type=int, choices=[1, 2], default=2)
    parser.add_argument("--repeats", type=int, choices=[1, 2], help="Override repetitions for both platforms.")
    parser.add_argument("--repeat-start", type=int, choices=[0, 1], default=0)
    parser.add_argument("--selection", choices=["both", "on", "off"], default="both")
    parser.add_argument("--performance", choices=["default", "off"], default="default",
                        help="Keep existing AUTO behavior or explicitly isolate directing from performance guidance.")
    parser.add_argument("--quality", choices=["off", "repair"], default="off")
    args = parser.parse_args()
    if ROOT == args.output_dir.resolve() or ROOT in args.output_dir.resolve().parents:
        raise SystemExit("Acceptance evidence must be outside the repository.")
    key = os.environ.get("T8_DIRECTIONAL_TEST_KEY", "")
    if args.provider == "cloud" and not key:
        raise SystemExit("Set T8_DIRECTIONAL_TEST_KEY for this process; never put a key in the script.")
    h3, sd, runtime = load_package()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = ["h3", "seedance20"] if args.target == "both" else [args.target]
    suite = CASE_SUITES[args.suite]
    cases = [case for case in suite if not args.case or case["id"] in args.case]
    if not cases or (args.case and set(args.case) - {case["id"] for case in suite}):
        raise SystemExit("Select cases from the chosen suite.")
    snapshot = {"schema": "t8-directional-acceptance/v1", "provider": args.provider,
                "performance": args.performance, "quality": args.quality, "creation": "off",
                "tests": [], "cases": cases, "media": "Text-only factual scenes; multimodal parameter/format paths have separate offline regression tests.",
                "evaluation": "Paired exploratory text evidence, not video quality or statistical significance."}
    resource = ROOT / "directional_skills" / "ning_wenwu" / "SKILL.md"
    if args.suite.startswith("ning"):
        snapshot["resource_sha256"] = hashlib.sha256(resource.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        snapshot["director_module_sha256"] = hashlib.sha256((ROOT / "directional_skills.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    destination = args.output_dir / f"{args.suite}-{args.provider}-{args.target}{'-' + '-'.join(args.case) if args.case else ''}{'-' + args.selection if args.selection != 'both' else ''}-r{args.repeat_start}.json"
    if destination.exists():
        raise SystemExit("Evidence already exists; choose a new directory instead of overwriting observations.")
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
        observation = {"request_parameters": {k: payload[k] for k in ("model", "stream", "temperature", "seed", "max_tokens", "max_completion_tokens", "reasoning_effort") if k in payload},
                       "source_prompt_present": contains_text(payload.get("messages"), case["prompt"]),
                       "director_instruction_present": selection == "none" or contains_text(payload.get("messages"), director_instruction(selection, target))}
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
                                "source_prompt_present": contains_text(messages, case["prompt"]),
                                "director_instruction_present": selection == "none" or contains_text(messages, director_instruction(selection, target)),
                                "rewrite_mode": values[3], "provider_request_options": kwargs.get("provider_request_options"),
                                "temperature_override": kwargs.get("temperature_override")})
        result = original_request(*values, **kwargs)
        active_requests[-1]["draft"] = result
        return result

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
                repeats = args.repeats or (args.h3_repeats if args.provider == "cloud" and target == "h3" else 1)
                for case_index, case in enumerate(cases):
                    for repeat in range(args.repeat_start, args.repeat_start + repeats):
                        selections = ("none", case["skill"]) if args.selection == "both" else ((case["skill"],) if args.selection == "on" else ("none",))
                        if args.suite.startswith("ning") and args.selection == "both" and (case_index + repeat + (target == "seedance20")) % 2:
                            selections = tuple(reversed(selections))
                        for selection in selections:
                            active_requests.clear()
                            started = time.monotonic()
                            record = {"case_id": case["id"], "target": target, "director_skill": selection, "repeat": repeat,
                                      "input_sha256": digest(case), "writing_seed": 6180 + repeat,
                                      "duration": case["duration"], "selected_language": "中文"}
                            from directional_skills import director_instruction
                            record["director_instruction_sha256"] = digest(director_instruction(selection, target))
                            def observed_progress(stage, **details):
                                metrics = details.get("quality_metadata")
                                if stage == "quality_checked" and isinstance(metrics, dict):
                                    record["quality_metrics"] = {k: metrics[k] for k in ("quality_mode", "correction_calls", "protocol_edits", "result", "issue_codes", "unchecked") if k in metrics}
                            values = dict(prompt=case["prompt"], duration_seconds=case["duration"], shot_count=case.get("shots", "1" if case["skill"] == "continuous_combat" or case["id"] in {"solo5", "escort10wait"} else "AUTO（系统自动判断）"),
                                          director_skill=selection, output_language="中文", rewrite_mode="balanced", seed=6180 + repeat,
                                          api_mode=h3.SEEDANCE_API_MODE if args.provider == "cloud" else h3.LOCAL_QWEN_API_MODE,
                                          api_key=key if args.provider == "cloud" else "", local_model="Qwen3.8/Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf",
                                          local_mmproj="AUTO（自动匹配）", local_context_size=16384, local_max_tokens=4096,
                                          local_think_mode=runtime.LOCAL_THINK_OFF, local_unload_policy=runtime.LOCAL_UNLOAD_AFTER_RUN)
                            if args.performance == "off":
                                from performance_director import build_performance_director_config, PERFORMANCE_OFF
                                values["performance_director_config"] = build_performance_director_config(PERFORMANCE_OFF)
                            if args.quality == "repair":
                                values["quality_mode"] = "repair"
                                values["progress_callback"] = observed_progress
                            # Each target receives its own task vocabulary/compiler.
                            try:
                                if target == "h3":
                                    output = h3.enhance_prompt(task_type="T2VA", **values)
                                else:
                                    values["shot_count"] = sd.AUTO_SHOT_COUNT if values["shot_count"].startswith("AUTO") else values["shot_count"]
                                    output = sd.enhance_seedance20_prompt(task_intent=sd.TASK_INTENT_LABELS["T2V"], **values)
                                record.update(outcome="success", output=output, output_sha256=digest(output))
                                from h3_quality import check_h3, check_seedance
                                record["contract_check"] = (check_h3(output, task_type="T2VA", duration=case["duration"],
                                    shot_count=int(case.get("shots", "0")), language="中文", source=case["prompt"], media_labels=[])
                                    if target == "h3" else check_seedance(output, language="中文", source=case["prompt"], shot_count=int(case.get("shots", "0"))))
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
