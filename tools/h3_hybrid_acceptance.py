"""Opt-in, serial real API Hybrid A/B. No secrets, GGUF or video model loading.

24 initial completions: first/last/both x image/video x 2 repeats x 2 groups.
Corrections share a global 12-request ceiling; HTTP retries share a 48-attempt
ceiling. Authentication failures stop the run instead of repeated billing.
Evidence files must be outside the repository. Inputs are actual synthetic
PNG/MP4 assets; this evaluates text contracts, not rendered H3 video quality.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import io
import json
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
from h3_hybrid import asset_roles
from h3_quality import check_h3


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--key-stdin",action="store_true",help="Read a single secret line over a private pipe; never log it.")
    args=parser.parse_args()
    dest=args.output_dir.resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise SystemExit("Evidence must be outside the repository.")
    print("Ready for test key",flush=True)
    key=sys.stdin.readline().strip() if args.key_stdin else getpass.getpass("API key (hidden): ")
    if not key:
        raise SystemExit("Missing API key")
    h3, _sd, _runtime=load_package()
    import av
    import numpy as np
    import torch
    from PIL import Image, ImageDraw
    dest.mkdir(parents=True,exist_ok=True)

    def picture(x):
        im=Image.new("RGB",(512,256),"white")
        draw=ImageDraw.Draw(im)
        draw.line((40,128,470,128),fill="gray",width=3)
        draw.rectangle((350,85,435,170),outline="blue",width=4)
        draw.ellipse((x-24,104,x+24,152),fill="red")
        return im

    images=[]
    for name,x in (("first",70),("last",390),("reference",230)):
        im=picture(x)
        im.save(dest/f"{name}.png")
        images.append(torch.from_numpy(np.array(im).astype(np.float32)/255).unsqueeze(0))
    data=io.BytesIO()
    with av.open(data,mode="w",format="mp4") as container:
        stream=container.add_stream("mpeg4",rate=2)
        stream.width,stream.height,stream.pix_fmt=512,256,"yuv420p"
        for index in range(16):
            frame=av.VideoFrame.from_image(picture(70+320*index/15))
            for packet in stream.encode(frame): container.mux(packet)
        for packet in stream.encode(): container.mux(packet)
    video_bytes=data.getvalue()
    (dest/"reference.mp4").write_bytes(video_bytes)
    class Video:
        def get_duration(self): return 8.0
        def get_stream_source(self): return io.BytesIO(video_bytes)
        def get_container_format(self): return "mp4"
    snapshot={"schema":"t8-hybrid-acceptance/v1","scope":"Real uploaded synthetic media, text contracts only; no rendered H3 video or real GGUF inference.",
              "source_sha256":digest({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ("nodes.py","h3_hybrid.py","h3_quality.py","quality_pipeline.py","h3_prompt_relay.py")}),
              "tests":[],"initial_calls":0,"correction_calls":0,"http_chat_attempts":0,"uploads":0}
    original_request=h3._request_completion
    original_post=h3.requests.Session.post
    current=None
    initial_in_case=False

    def request(*values,**kw):
        nonlocal initial_in_case
        correction=initial_in_case
        if correction and snapshot["correction_calls"] >= 12:
            raise RuntimeError("Acceptance correction budget exhausted")
        counter="correction_calls" if correction else "initial_calls"
        snapshot[counter]+=1
        initial_in_case=True
        observation={"kind":"correction" if correction else "initial","message_sha256":digest(values[2]),
                     "model":values[6],"attempts":[]}
        current["requests"].append(observation)
        started=time.monotonic()
        try:
            output=original_request(*values,**kw)
            observation["output"]=output
            return output
        finally:
            observation["elapsed_seconds"]=round(time.monotonic()-started,3)

    def post(self,*values,**kw):
        payload=kw.get("json")
        if payload:
            if snapshot["http_chat_attempts"] >= 48:
                raise RuntimeError("Acceptance HTTP attempt budget exhausted")
            snapshot["http_chat_attempts"]+=1
            observation={"parameters":{k:payload[k] for k in ("model","stream","temperature","seed","max_tokens","max_completion_tokens","reasoning_effort") if k in payload}}
            current["requests"][-1]["attempts"].append(observation)
        else:
            snapshot["uploads"]+=1
            observation={"upload":True}
        response=original_post(self,*values,**kw)
        observation["status"]=response.status_code
        if response.status_code in (401,403):
            snapshot["authentication_failed"]=response.status_code
        if "json" in response.headers.get("Content-Type","").lower():
            try: response_metrics(response.json(),observation)
            except ValueError: pass
        elif kw.get("stream"):
            lines=response.iter_lines
            def observed_lines(*a,**b):
                for raw in lines(*a,**b):
                    line=raw.decode("utf8",errors="replace") if isinstance(raw,bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try: response_metrics(json.loads(line.strip()[5:].strip()),observation)
                        except ValueError: pass
                    yield raw
            response.iter_lines=observed_lines
        return response

    path=dest/"acceptance.json"
    with patch.object(h3,"_request_completion",request),patch.object(h3.requests.Session,"post",post):
        for anchors in ("first","last","both"):
            for ref_kind in ("image","video"):
                for repeat in range(2):
                    for group in ("Ref2VA_control","Hybrid"):
                        first=images[0] if anchors in ("first","both") else None
                        last=images[1] if anchors in ("last","both") else None
                        extras={"reference_image_2":images[2]} if ref_kind=="image" else {}
                        videos={"reference_video_2":Video()} if ref_kind=="video" else {}
                        hybrid_plan=h3._hybrid_media_plan(first,last,extras,videos)
                        roles=asset_roles(hybrid_plan)
                        context="\n".join(f'{r["label"]}: {r["role"]}' for r in roles)
                        prompt="8秒平面几何动画。白底、灰色直轨、右侧固定蓝框和红色圆片。圆片沿灰轨连续平移并减速，保持大小、方向与蓝框位置；不瞬移、不变形、不增加物体。参考图只提供物体外观，参考视频只提供滑动节奏。实际首帧在0秒严格对齐，实际尾帧在8秒严格对齐；仅应用实际提供的首/尾角色。一个连续镜头，无对白、文字、音乐，只有轻微滑动摩擦声。说明中文。"
                        common=dict(prompt=prompt,duration_seconds=8,shot_count="1",output_language="中文",seed=10060+repeat,api_key=key,
                                    reference_context=context,quality_mode="repair",description_word_target=0,reference_videos=videos)
                        if group=="Hybrid":
                            common.update(task_type="Hybrid",first_frame=first,last_frame=last,reference_images=extras)
                        else:
                            common.update(task_type="Ref2VA",reference_images={f"reference_image_{i}":a["value"][None,...] for i,a in enumerate(hybrid_plan) if a["kind"]=="image"})
                        current={"case":f"{anchors}_{ref_kind}","repeat":repeat,"group":group,"requests":[],"progress":[]}
                        snapshot["tests"].append(current)
                        initial_in_case=False
                        try:
                            text=h3.enhance_prompt(**common,progress_callback=lambda stage,**kw:current["progress"].append({"stage":stage,**kw}))
                            current.update(outcome="success",output=text)
                            report=check_h3(text,task_type=common["task_type"],duration=8,shot_count=1,language="中文",media_labels=[a["label"] for a in hybrid_plan],
                                            **({"asset_roles":roles} if group=="Hybrid" else {}))
                            current["report"]={k:v for k,v in report.items() if not k.startswith("_")}
                            # Same role checker on the control measures anchor preservation,
                            # not compliance with new T8 role tokens (legacy format is natural).
                        except Exception as error:
                            current.update(outcome="failed",error_type=type(error).__name__)
                        path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf8")
                        print(json.dumps({k:current[k] for k in ("case","repeat","group","outcome")},ensure_ascii=True),flush=True)
                        if snapshot.get("authentication_failed"):
                            print("Authentication rejected; stopping without more requests",flush=True)
                            return 2
    print(json.dumps({k:snapshot[k] for k in ("initial_calls","correction_calls","http_chat_attempts","uploads")}),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
