"""Serial, opt-in real API acceptance. Key read without echo, never persisted.

Synthetic reference PNGs are real uploaded inputs, not model mocks. Evidence
must be outside the repository. No GGUF/CUDA/video model is ever loaded here.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
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
from h3_quality import check_h3, check_seedance

QUALITY_CASES = [
    dict(id="two_real_frames", task="FL2VA", seconds=8, shots="1", images="pair",
         prompt="8秒平面几何动画。首帧红色圆片在左侧，尾帧它位于右侧蓝色框内。红圆沿灰色轨道连续平移，速度渐慢抵达蓝框；保留白底、蓝框位置与红圆大小，不瞬移、不变形、不新增物体。一个连续镜头，无文字、对白、音乐，仅轻微滑动摩擦声。"),
    dict(id="real_last_frame", task="L2VA", seconds=8, shots="1", images="last",
         prompt="8秒平面几何动画，以提供的图片为实际尾帧：红色圆片落在右侧蓝框内。合理构造红圆从画面左侧沿已有灰色轨道持续平移到蓝框的过程。保留白底、圆片大小和蓝框位置，不瞬移、不变形、不新增物体。一个连续镜头，无字幕、对白、音乐，仅轻微滑动摩擦声。"),
    dict(id="exact_foreign_speech", task="T2VA", seconds=8, shots="1", images="none",
         prompt="8秒写实车站片段。红衣女人右手拿车票，在窗边完整低声说原句“Please wait until I check the departure time before we board.”。逐字保留英文台词，不翻译，不增加或重复台词。说明必须中文。说完才向已有出口迈一步，车票始终在右手；一个镜头，结尾仍在缓慢移动。无字幕无配乐，只有轻声对白、脚步与车站环境声。"),
    dict(id="two_speakers", task="T2VA", seconds=8, shots="2", images="none",
         prompt="8秒写实室内，两个成年人物：红袖Alice右手拿钥匙，蓝袖Bob双手空置。Alice先低声说原句“等我。”，Bob再完整回答原句“我在这里。”。只有这两句，不新增重复或翻译。钥匙全程在Alice右手，不交给Bob。固定两个镜头，第二镜揭示Bob在已关闭的门旁等待；结尾门仍关闭。无字幕，无配乐，室内底噪与布料声。"),
    dict(id="audio_text_contract", task="T2VA", seconds=8, shots="1", images="none",
         prompt="8秒单镜头写实咖啡厅，成年女人站在窗边，画内已有收音机播放轻柔钢琴，角色能听到该音乐。她只说原句“等我回来。”一次，原样保留。配乐给观众独享另用低音弦乐，不让角色听到。环境声是雨声和瓷杯落桌声。无字幕，无歌词。只有文字创意，没有音频素材；不得声称听过或转写了素材。"),
    dict(id="wait_moving_end", task="T2VA", seconds=8, shots="1", images="none",
         prompt="8秒写实车厢，两位成年人物红衣Alice与蓝衣Bob都无武器。开头完整两秒静止等待，只有车厢外远处响声。两秒后Alice带Bob沿已有通道向关闭的车门移动；战争只在窗外背景，不增加车内枪手、武器或第三人。结尾两人仍向车门移动，门始终关闭，不冻结、不宣布胜负、不擅自开门。一个连续镜头，无对白、字幕和配乐。"),
]
CAUSAL_CASES = [
    dict(id="heldout_robot", task="T2VA", seconds=8, shots="1", images="none",
         prompt="8秒一镜到底，一台没有脸、不会呼吸的四足小机器人沿石台前进，踏过两级已有台阶后抵达木桥入口，借上一蹬踏的速度继续向前。末帧前足已上木桥、后足仍移动；不停止、不冻结、不瞬移。不增加人、敌人、对白、武器或能力。只有机械和落足声，无字幕、配乐。"),
    dict(id="heldout_prop_reply", task="T2VA", seconds=8, shots="2", images="none",
         prompt="8秒两镜，红衣Alice右手一直攥着黄票，蓝衣Bob双手空置，在已有售票窗前。Alice递近黄票但不松手，Bob指向已有售票口，于是Alice转身带着黄票向窗口迈步。只在第一镜Alice低声说原句“这里吗？”，Bob不说话。第二镜必须新增窗口与路线信息，结尾Alice仍移动、黄票仍在其右手。不新增人或道具，无字幕和配乐。"),
    dict(id="heldout_one_take_shift", task="T2VA", seconds=8, shots="1", images="none",
         prompt="8秒连续镜头，一只红色木制玩具车沿桌面轨道滚动，右轮碰到已有薄木块后轻微改向，沿着桌面继续滚向右侧纸盒入口。轮子与车身完整，无变形、悬空、瞬移；木块仍在桌上。镜头侧跟拍并逐渐贴近车轮，不切镜。末帧车仍移动但尚未进纸盒，不冻结、不突然宣布完成。无人脸对白字幕音乐，只木轮摩擦和轻碰声。"),
]


def response_metrics(payload, observation):
    if not isinstance(payload, dict):
        return
    if isinstance(payload.get("usage"), dict):
        observation["usage"] = {k: payload["usage"][k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance(payload["usage"].get(k), int)}
    if isinstance(payload.get("model"), str):
        observation["response_model"] = payload["model"]
    for c in payload.get("choices") or []:
        if isinstance(c, dict) and c.get("finish_reason"):
            observation["finish_reason"] = str(c["finish_reason"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=["quality", "causal", "seedance"], required=True)
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    key = getpass.getpass("API key (hidden; not saved): ")
    h3, sd, _runtime = load_package()
    from PIL import Image, ImageDraw
    import numpy as np
    import torch
    destination.mkdir(parents=True, exist_ok=True)
    media = []
    for label, x in (("first", 70), ("last", 390)):
        path = destination / f"reference-{label}.png"
        image = Image.new("RGB", (512, 256), "white")
        draw = ImageDraw.Draw(image)
        draw.line((40, 128, 470, 128), fill="gray", width=3)
        draw.rectangle((350, 85, 435, 170), outline="blue", width=4)
        draw.ellipse((x-24, 104, x+24, 152), fill="red")
        image.save(path)
        media.append(torch.from_numpy(np.array(image).astype(np.float32) / 255).unsqueeze(0))
        image.close()
    fingerprint = digest({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
        "nodes.py", "seedance20.py", "h3_quality.py", "quality_pipeline.py", "h3_prompt_relay.py")})
    snapshot = {"schema":"t8-quality-acceptance/v1", "phase":args.phase, "source_sha256":fingerprint,
                "media":"Real synthetic PNGs uploaded only for keyframe cases; audio case tests text only, no audio analysis.",
                "evaluation":"Exploratory text contracts, not rendered video quality.", "tests":[]}
    requests = []
    uploads = []
    original_request = h3._request_completion
    original_post = h3.requests.Session.post
    def observed_request(*values, **kwargs):
        observation = {"messages": values[2], "message_sha256":digest(values[2]), "model_id":values[6], "http_attempts":[]}
        requests.append(observation)
        started = time.monotonic()
        try:
            text = original_request(*values, **kwargs)
            observation["output"] = text
            observation["output_sha256"] = digest(text)
            return text
        except Exception as error:
            observation["error_type"] = type(error).__name__
            raise
        finally:
            observation["elapsed_seconds"] = round(time.monotonic()-started, 3)
    def observed_post(self, *values, **kwargs):
        payload = kwargs.get("json")
        observation = {"request_parameters": {k:payload[k] for k in ("model","stream","temperature","seed","max_tokens","max_completion_tokens","reasoning_effort") if k in payload}} if payload else {"upload":True}
        if requests:
            requests[-1]["http_attempts"].append(observation)
        elif not payload:
            uploads.append(observation)
        try:
            response = original_post(self, *values, **kwargs)
        except Exception as error:
            observation["error_type"] = type(error).__name__
            raise
        observation["status"] = response.status_code
        if "json" in response.headers.get("Content-Type", "").lower():
            try: response_metrics(response.json(), observation)
            except ValueError: pass
        elif kwargs.get("stream"):
            original_lines = response.iter_lines
            def lines(*args, **opts):
                for raw in original_lines(*args, **opts):
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try: response_metrics(json.loads(line.strip()[5:].strip()), observation)
                        except ValueError: pass
                    yield raw
            response.iter_lines = lines
        return response
    cases = QUALITY_CASES if args.phase == "quality" else CAUSAL_CASES
    if args.phase == "seedance":
        cases = CAUSAL_CASES[:2]
    cases = [c for c in cases if not args.case or c["id"] in args.case]
    output_path = destination / f"{args.phase}.json"
    if output_path.exists():
        snapshot = json.loads(output_path.read_text(encoding="utf-8"))
        if snapshot["source_sha256"] != fingerprint:
            raise SystemExit("Production source changed; use a new evidence directory.")
    try:
        with patch.object(h3, "_request_completion", observed_request), patch.object(sd, "_request_completion", observed_request), patch.object(h3.requests.Session, "post", observed_post):
            for case in cases:
                for repeat in range(2 if args.phase != "seedance" else 1):
                    for on in (False, True):
                        identity = (case["id"], repeat, on)
                        if any((t["case_id"],t["repeat"],t["on"]) == identity and t["outcome"] == "success" for t in snapshot["tests"]):
                            continue
                        requests.clear()
                        uploads.clear()
                        started=time.monotonic()
                        metrics=[]
                        common = dict(prompt=case["prompt"], duration_seconds=case["seconds"], shot_count=case["shots"],
                                      output_language="中文", api_key=key, rewrite_mode="balanced", seed=9170+repeat,
                                      quality_mode="repair" if args.phase != "quality" or on else "off",
                                      creation_mode="causal" if args.phase != "quality" and on else "off",
                                      progress_callback=lambda stage, **kw: metrics.append({"stage":stage, **kw}))
                        if case["images"]=="pair":
                            common.update(first_frame=media[0], last_frame=media[1])
                        elif case["images"]=="last":
                            common.update(last_frame=media[1])
                        record={"case_id":case["id"], "repeat":repeat, "on":on, "input":case,
                                "input_sha256":digest(case), "writing_seed":9170+repeat}
                        try:
                            if args.phase == "seedance":
                                text=sd.enhance_seedance20_prompt(task_intent="T2V", **common)
                                check=check_seedance(text, language="中文", source=case["prompt"], shot_count=int(case["shots"]))
                            else:
                                text=h3.enhance_prompt(task_type=case["task"], **common)
                                labels=["<Picture 1>","<Picture 2>"] if case["images"]=="pair" else ["<Picture 1>"] if case["images"]=="last" else []
                                check=check_h3(text, task_type=case["task"], duration=case["seconds"], language="中文", source=case["prompt"], shot_count=int(case["shots"]), media_labels=labels)
                            record.update(outcome="success", output=text, output_sha256=digest(text), contract_check=check)
                        except Exception as error:
                            record.update(outcome="failed", error_type=type(error).__name__)
                            status=re.search(r"\bstatus=(\d+)\b", str(error))
                            category=re.search(r"\bcategory=([a-z_]+)\b", str(error))
                            if status: record["error_status"]=int(status.group(1))
                            if category: record["error_category"]=category.group(1)
                        record.update(elapsed_seconds=round(time.monotonic()-started,3), requests=list(requests), uploads=list(uploads), logical_calls=len(requests), metrics=metrics)
                        # No raw exception, headers, keys, response IDs or reasoning.
                        if key in json.dumps(record, ensure_ascii=False):
                            raise SystemExit("Secret safety check failed; nothing saved.")
                        snapshot["tests"].append(record)
                        output_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
                        print(json.dumps({k:record[k] for k in ("case_id","repeat","on","outcome","elapsed_seconds","logical_calls")}),flush=True)
                        if record["outcome"] != "success" or any(r.get("error_type") for r in requests):
                            raise SystemExit("Stopped on actual transport failure; retained draft is saved for diagnosis.")
    finally:
        key=""
        media.clear()

if __name__ == "__main__":
    main()
