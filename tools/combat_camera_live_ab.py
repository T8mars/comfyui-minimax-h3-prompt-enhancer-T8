"""Opt-in serial real API A/B. No keys in files, headers or evidence.

Calls the production enhancers and observes real requests without substituting
transport responses. Synthetic PNG anchors are actual uploaded media.
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
from h3_quality import check_h3, check_seedance

CASES = [
    dict(id="h3_dynamic", target="h3", task="T2VA", seconds=8, shots="1", performance="extreme",
         prompt="8秒，一个连续镜头。两名成年练习者在空旷练功场做友好木剑演练，红袖甲在左，蓝袖乙在右，各持自己的木剑。甲向前一步横挥，乙用原有木剑格挡并向右退半步，甲顺势跟进半步但不再出剑；结尾双方仍站立，各自持原剑。镜头可以跟随已有动作，让移动方向、木剑接触与两人距离清楚。不加第三人、招式、能力、伤害或胜负，不加慢动作、定格、尘土、台词、字幕或配乐；只有脚步与一次木剑接触声。"),
    dict(id="h3_solo", target="h3", task="T2VA", seconds=6, shots="1", performance="auto",
         prompt="6秒，一个连续镜头。只有一名成年红袖练习者在干净练习室独自做低扫腿演练，先左脚支撑，右腿向画面右侧低扫，再顺势收腿站稳。地面干净，无道具。允许镜头跟随腿部轨迹，结尾双脚落地站稳。全片没有对手或接触目标，不增加攻击对象、器械、尘土、伤害、能力、下一招、冻结、慢动作或旁白；只有衣料与足底摩擦声，无台词字幕配乐。"),
    dict(id="h3_noncombat", target="h3", task="T2VA", seconds=6, shots="1", performance="auto",
         prompt="6秒固定机位，一个连续镜头。成年蓝袖女子坐在安静练习室的长椅上，右手把一条白毛巾折好放回自己腿上；左手不动。背景架上已有两把木剑，全片木剑静止且不被触碰。仅她一人，没有战斗、威胁、敌人或新动作。结尾毛巾在腿上，女子仍坐着。不得移动、推拉、环绕或变焦相机；全片静音，无台词、字幕、配乐、粒子、慢动作或定格。"),
    dict(id="h3_fixed_two", target="h3", task="T2VA", seconds=8, shots="2", performance="extreme",
         prompt="8秒，严格2个镜头，每个镜头都是固定机位、固定焦距，不推拉平移摇镜环绕，不手持震动。两名成年空手练习者红袖甲在左、蓝袖乙在右，在干净地板练习室做闪避练习。镜头1侧面中景：甲的试探拳从乙肩外空处划过，乙向右后撤；镜头2原轴同侧固定全景：乙继续后撤一步，甲收拳停在左侧。全片身体从不接触，结尾甲左乙右均站立，无胜负。只有两人，不增道具、声音、尘土、伤害、下一招、冻结或慢动作；全片静音，无台词字幕配乐。"),
    dict(id="h3_pov", target="h3", task="T2VA", seconds=8, shots="1", performance="strong", skill="zhenzhen_pov",
         prompt="8秒，一个连续镜头，观看者本人眼睛的第一人称，不是第三人称、自拍或旁边摄影师。我的左手已持一个红色软垫，垫在画面左下；正前方只有一位成年蓝袖朋友，在练习室做友好试拳。朋友右拳轻碰原软垫后收回，我的左手连垫向后让出少许并停稳。始终从我的眼睛看朋友，保持朋友完整脸和接触区可读，镜头随我自然身体回应但不得脱离我的视点或环绕拍我的身体。结尾朋友仍在前方站立，垫始终在我左手，不加第二垫、新拳、新人、对白、字幕、配乐、伤害、冻结或慢动作；声音仅一次软垫接触声。"),
    dict(id="h3_frames_relay", target="h3", task="FL2VA", seconds=8, shots="1", performance="auto", images="pair", relay=True,
         prompt="8秒平面示意动画，一个连续镜头。实际首帧和尾帧已经提供：红衣成年练习者甲始终在左，蓝衣成年练习者乙始终在右，各自持自己的棕色木剑。甲由首帧位置向右一步挥剑，乙用已有木剑格挡，同时向右后撤半步；随后双方收住木剑，抵达实际尾帧的位置和姿态。以两张图为首尾锚点，人物色块、木剑数、背景和脚下地面不变。镜头观察这条连续动作，不切镜、不越轴、不换人、不换剑、不添加下一招、敌人、受伤、尘土、能力或胜负，无对白字幕配乐；只有一次木剑接触声。"),
    dict(id="sd_dynamic", target="seedance20", task="T2V", seconds=8, shots="1", performance="extreme",
         prompt="8秒，一个连续镜头，两名成年练习者在空练功场进行友好木剑演练，甲红袖在左，乙蓝袖在右，各持自己的木剑。甲向前一步横挥，乙用原剑格挡并向右后退半步，甲跟进但不再挥剑；结尾两人仍站立、各持原剑，无胜负。允许一个主运镜跟随动作，看清方向、接触和距离。没有第三人、额外招式、伤害、能力、尘土、定格、慢动作、台词、字幕或配乐，只有脚步与一次木剑接触声。"),
    dict(id="sd_fixed_two", target="seedance20", task="T2V", seconds=8, shots="2", performance="auto",
         prompt="8秒严格2个镜头，每个镜头固定机位与焦距，不允许推拉平移摇镜环绕或震动。只有成年红袖甲和蓝袖乙，均空手，甲左乙右。镜头1侧面中景，甲试探拳从乙肩外空处划过，乙后撤避让；镜头2原轴同侧固定全景，乙继续后撤一步，甲收拳停在左侧。身体全片不接触，没有受伤或胜负；结尾两人保持甲左乙右站立。干净练习室不增加人、道具、尘土、声音、下一招、慢动作、冻结、对白、字幕或配乐，全片静音。"),
]


def anchors(destination):
    from PIL import Image, ImageDraw
    import numpy as np
    import torch
    tensors = []
    for name, left, right in (("first", 125, 335), ("last", 180, 380)):
        image = Image.new("RGB", (512, 320), (238, 238, 232))
        draw = ImageDraw.Draw(image)
        draw.line((25, 265, 487, 265), fill=(115, 115, 110), width=3)
        for x, color, direction in ((left, (200, 45, 45), 1), (right, (40, 90, 195), -1)):
            draw.ellipse((x-15, 75, x+15, 105), fill=(208, 172, 130))
            draw.rectangle((x-18, 108, x+18, 183), fill=color)
            draw.line((x-10, 184, x-24, 263), fill=color, width=12)
            draw.line((x+10, 184, x+25, 263), fill=color, width=12)
            draw.line((x+direction*13, 121, x+direction*48, 145), fill=color, width=12)
            draw.line((x+direction*48, 145, x+direction*75, 102), fill=(128, 80, 35), width=7)
        path = destination / f"anchor-{name}.png"
        image.save(path)
        tensors.append(torch.from_numpy(np.asarray(image).astype(np.float32) / 255).unsqueeze(0))
        image.close()
    return tensors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--key-stdin", action="store_true")
    parser.add_argument("--case", action="append", choices=[case["id"] for case in CASES])
    parser.add_argument("--tag", default="initial")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("--tag must be a plain filename token, not a path.")
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    output = destination / f"{args.tag}.json"
    if output.exists():
        raise SystemExit("Use a new evidence filename; prior observations are immutable.")
    if args.key_stdin:
        print("Awaiting API key on stdin; it will not be echoed or persisted.", flush=True)
        key = sys.stdin.readline().strip()
    else:
        key = getpass.getpass("API key (hidden; not saved): ")
    if not key:
        raise SystemExit("Missing key.")
    destination.mkdir(parents=True, exist_ok=True)
    h3, sd, _ = load_package()
    camera = sys.modules[h3.__package__ + ".combat_camera"]
    performance = sys.modules[h3.__package__ + ".performance_director"]
    cases = [case for case in CASES if not args.case or case["id"] in args.case]
    media = anchors(destination) if any(c.get("images") for c in cases) else []
    revision = digest({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                       for name in ("nodes.py", "seedance20.py", "combat_camera.py", "directional_skills.py", "h3_quality.py")})
    evidence = {"schema": "t8-combat-camera-real-ab/v1", "source_sha256": revision,
                "provider": "贞贞平价小屋", "endpoint": h3.CHAT_COMPLETIONS_URL, "model": h3.MODEL_ID,
                "rubric": {"facts_and_ownership": 25, "hard_constraints": 25, "camera_readability_or_restraint": 25,
                           "action_causality_and_ending": 15, "native_protocol": 10},
                "scope": "Real text enhancement and actual PNG uploads; no video generation. Subjective text scores are not rendered quality.",
                "request_options": {"temperature_policy": "send", "extra_parameters": {"seed": 2026093001, "max_tokens": 16384}},
                "tests": []}
    calls, posts = [], []
    original_request = h3._request_completion
    original_post = h3.requests.Session.post

    def observed_request(*values, **kwargs):
        row = {"messages": values[2], "message_sha256": digest(values[2]), "http_attempts": []}
        calls.append(row)
        started = time.monotonic()
        try:
            result = original_request(*values, **kwargs)
            row.update(output=result, output_sha256=digest(result))
            return result
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise
        finally:
            row["elapsed_seconds"] = round(time.monotonic()-started, 3)

    def observed_post(session, *values, **kwargs):
        url = str(values[0] if values else kwargs.get("url", ""))
        payload = kwargs.get("json", {})
        row = {"kind": "chat" if url.endswith("/chat/completions") else "upload",
               "parameters": {k: payload[k] for k in ("model", "stream", "temperature", "seed", "max_tokens") if k in payload}}
        posts.append(row)
        if row["kind"] == "chat" and calls:
            calls[-1]["http_attempts"].append(row)
        response = original_post(session, *values, **kwargs)
        row["status"] = response.status_code
        if "json" in response.headers.get("Content-Type", "").lower():
            try:
                response_metrics(response.json(), row)
            except ValueError:
                pass
        if kwargs.get("stream"):
            original_lines = response.iter_lines
            def lines(*args, **options):
                for raw in original_lines(*args, **options):
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try:
                            response_metrics(json.loads(line.strip()[5:].strip()), row)
                        except ValueError:
                            pass
                    yield raw
            response.iter_lines = lines
        return response

    def save():
        serialized = json.dumps(evidence, ensure_ascii=False, indent=2)
        if key in serialized or re.search(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}", serialized):
            raise SystemExit("Secret scan rejected evidence.")
        output.write_text(serialized, encoding="utf-8")

    try:
        with patch.object(h3, "_request_completion", observed_request), patch.object(sd, "_request_completion", observed_request), \
                patch.object(h3.requests.Session, "post", observed_post), h3.requests.Session() as session:
            for index, case in enumerate(cases):
                arms = ["off", "strong"]
                random.Random(2026093001 + index).shuffle(arms)
                for arm in arms:
                    calls.clear(); posts.clear()
                    mode = camera.CAMERA_OFF if arm == "off" else camera.CAMERA_STRONG
                    config = camera.build_combat_camera_config(mode, camera.CONTINUITY_CONTINUOUS, camera.IMPACT_NATURAL)
                    p_mode = {"auto": performance.PERFORMANCE_AUTO, "strong": performance.PERFORMANCE_STRONG, "extreme": performance.PERFORMANCE_EXTREME}[case["performance"]]
                    common = dict(prompt=case["prompt"], duration_seconds=case["seconds"], shot_count=case["shots"],
                                  output_language="中文", api_key=key, session=session, rewrite_mode="balanced", seed=2026093001,
                                  combat_camera_config=config, performance_director_config=performance.build_performance_director_config(p_mode),
                                  director_skill=case.get("skill", "none"), quality_mode="off", creation_mode="off",
                                  provider_request_options=evidence["request_options"])
                    if case.get("images"):
                        common.update(first_frame=media[0], last_frame=media[1])
                    if case.get("relay"):
                        common["relay_config"] = {"event_count": 2, "time_ranges": "0-4\n4-8"}
                    row = {"case": case, "arm": arm, "camera_config": config}
                    started = time.monotonic()
                    try:
                        if case["target"] == "h3":
                            result = h3.enhance_prompt(task_type=case["task"], **common)
                            native = result
                            if case.get("relay"):
                                compiled = h3.compile_relay_response(result, case["seconds"], 2, "0-4\n4-8", case["task"], "中文")
                                native = json.loads(result)["native_prompt"]
                                row["relay"] = compiled
                            check = check_h3(native, task_type=case["task"], duration=case["seconds"], shot_count=int(case["shots"]),
                                             language="中文", source=case["prompt"], media_labels=["<Picture 1>", "<Picture 2>"] if media and case.get("images") else [])
                        else:
                            result = sd.enhance_seedance20_prompt(task_intent=case["task"], **common)
                            check = check_seedance(result, language="中文", source=case["prompt"], shot_count=int(case["shots"]))
                        row.update(outcome="success", output=result, output_sha256=digest(result), contract_check=check)
                    except Exception as error:
                        row.update(outcome="failed", error_type=type(error).__name__)
                        status = re.search(r"\bstatus=(\d+)\b", str(error))
                        if status:
                            row["error_status"] = int(status.group(1))
                    row.update(elapsed_seconds=round(time.monotonic()-started,3), calls=list(calls), posts=list(posts))
                    evidence["tests"].append(row)
                    save()
                    print(json.dumps({"case":case["id"], "arm":arm, "outcome":row["outcome"],
                                      "seconds":row["elapsed_seconds"], "logical_calls":len(calls),
                                      "statuses":[p.get("status") for p in posts],
                                      "issues":row.get("contract_check", {}).get("issues", [])}, ensure_ascii=False), flush=True)
                    if row["outcome"] != "success":
                        raise SystemExit("Stopped on actual failure; evidence preserved for diagnosis.")
    finally:
        key = ""
        media.clear()


if __name__ == "__main__":
    main()
