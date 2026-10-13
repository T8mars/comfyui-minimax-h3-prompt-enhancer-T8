"""Explicit real inference and Comfy queue acceptance, no service lifecycle calls.

Outputs live outside the repository. This measures transport/native text
contracts, not rendered video/music quality or model equivalence.
"""
from __future__ import annotations
import argparse
import base64
import copy
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")

def image_url(image):
    buffer=io.BytesIO(); image.save(buffer,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode("ascii")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--confirm-real",action="store_true",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--comfy",default="http://127.0.0.1:8193")
    parser.add_argument("--phase",choices=["pairs","queue","all"],default="all")
    parser.add_argument("--only",default="",help="Comma-separated group IDs for an explicit follow-up run")
    args=parser.parse_args()
    selected=set(args.only.split(",")) if args.only else None
    args.output.mkdir(parents=True,exist_ok=True)
    sys.argv=["strata-real-acceptance","--cpu"]
    sys.path.insert(0,str(ROOT.parents[1]))
    import comfy.cli_args
    comfy.cli_args.args.cpu=True
    import requests
    import av
    import numpy as np
    import torch
    from PIL import Image,ImageDraw
    from comfy_api.latest._input_impl.video_types import VideoFromFile,VideoFromList
    spec=importlib.util.spec_from_file_location("t8_strata_acceptance",ROOT/"__init__.py",submodule_search_locations=[str(ROOT)])
    package=importlib.util.module_from_spec(spec);sys.modules[spec.name]=package;spec.loader.exec_module(package)
    sp=sys.modules[spec.name+".strata_provider"]
    media=__import__(spec.name+".strata_media",fromlist=["*"])
    session=requests.Session();session.trust_env=False
    service="http://127.0.0.1:8080"
    before=session.get(service+"/v1/status",timeout=5).json()
    config={"model":before["model"],"started":before["started"],"protocol":before["protocol_version"],"package":before["package_version"]}
    source={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in ROOT.glob("*.py")}
    records=[]
    index=args.output/"results.json"
    def record(value):
        records.append(value);save(index,{"service":config,"source_sha256":source,"groups":records})
        print(json.dumps({k:value.get(k) for k in ("id","passed","seconds","requests","error")},ensure_ascii=False),flush=True)
    red=Image.new("RGB",(96,96),"white");ImageDraw.Draw(red).rectangle((20,20,75,75),fill="red")
    blue=Image.new("RGB",(96,96),"white");ImageDraw.Draw(blue).ellipse((20,20,75,75),fill="blue")
    tensors=[torch.from_numpy(np.asarray(im).copy()).float()[None]/255 for im in (red,blue)]
    binary=io.BytesIO()
    with av.open(binary,mode="w",format="mp4") as c:
        st=c.add_stream("libx264",rate=4);st.width=96;st.height=96;st.pix_fmt="yuv420p";st.options={"crf":"1","preset":"ultrafast"}
        for n in range(12):
            frame=av.VideoFrame.from_ndarray(np.full((96,96,3),(round(n*255/11),0,0),dtype=np.uint8),format="rgb24")
            for p in st.encode(frame):c.mux(p)
        for p in st.encode():c.mux(p)
    video_bytes=binary.getvalue()
    (args.output/"red-transition.mp4").write_bytes(video_bytes)
    red.save(args.output/"red-square.png");blue.save(args.output/"blue-circle.png")
    def file(**kwargs):return VideoFromFile(io.BytesIO(video_bytes),**kwargs)
    # Independent expected frames: decode all small fixture frames once; do not
    # call the bridge's selector, adapter or manifest builders here.
    with av.open(io.BytesIO(video_bytes)) as c:
        full=[(float(f.pts*f.time_base),f.to_image()) for f in c.decode(video=0)]
    def manual_video(indices,*,mode="frames",duration=3.,origin=0.,offset=0.):
        return {"type":"strata_video","contract_version":1,"mode":mode,
            "frames":[{"source":image_url(full[n][1]),"timestamp_s":full[n][0]-offset,
                       "source_timestamp_s":full[n][0],"index":i} for i,n in enumerate(indices)],
            "metadata":{"duration_s":duration,"time_origin_s":origin,"sampling_fps":1.}}
    boundary=media.EVIDENCE_BOUNDARY # Static evidence warning, not a selector or request builder.
    def expected_parts(images=(),videos=()):
        out=[]
        for label,im in images:out.extend([{"type":"text","text":f"The next attached image is {label}."},{"type":"image_url","image_url":{"url":image_url(im)}}])
        for label,part in videos:out.extend([{"type":"text","text":f"The following sampled visual clip is {label}. {boundary}"},part])
        return out
    cases=[
        ("text-cn",[],[],{},"用中文一句话描述黄色杯子，不要增加人物。",None),
        ("text-en",[],[],{},"Write one concise English image prompt for a yellow ceramic cup on a wood table.",None),
        ("structured-json",[],[],{},'Return JSON only with one key "prompt" containing a short yellow cup image prompt.',{"type":"json_object"}),
        ("thinking-low",[],[],{"reasoning_effort":"low","reasoning_budget_tokens":128},"用中文一句话描写木桌上的黄色杯子。",None),
        ("one-image",[{"kind":"image","label":"<Picture 1>","value":tensors[0]}],expected_parts([("<Picture 1>",red)]),{},"用中文一句话描述参考图的颜色和形状，别编人物。",None),
        ("two-images",[{"kind":"image","label":f"<Picture {i+1}>","value":t} for i,t in enumerate(tensors)],expected_parts([("<Picture 1>",red),("<Picture 2>",blue)]),{},"用中文分别描述两张参考图的颜色和形状。",None),
        ("video-frames",[{"kind":"video","label":"<Video 1>","value":file()}],expected_parts(videos=[("<Video 1>",manual_video([0,6,11]))]),{},"只用中文描述视频样本的可见颜色变化，不分析声音。",None),
        ("video-native",[{"kind":"video","label":"<Video 1>","value":file()}],expected_parts(videos=[("<Video 1>",manual_video([0,6,11],mode="native"))]),{"video_mode":"native"},"只用中文描述视频样本的可见颜色变化，不分析声音。",None),
        ("video-trim",[{"kind":"video","label":"<Video 1>","value":file(start_time=1,duration=1)}],expected_parts(videos=[("<Video 1>",manual_video([4,7],duration=1.,origin=1.,offset=1.))]),{},"只用中文描述裁剪后的样本可见变化，不分析声音。",None),
    ]
    list_part=manual_video([0,6,11]); list_part["metadata"]["duration_s"]=6.
    # Six samples over two 3s components: independent global targets 0,1.2,
    # 2.4,3.6,4.8,end; first PTS at/after each and actual last valid PTS.
    list_part["frames"]=[]
    for i,(n,offset) in enumerate([(0,0),(5,0),(10,0),(3,3),(8,3),(11,3)]):
        list_part["frames"].append({"source":image_url(full[n][1]),"timestamp_s":offset+full[n][0],"source_timestamp_s":offset+full[n][0],"index":i})
    cases.append(("video-list",[{"kind":"video","label":"<Video 1>","value":VideoFromList([file(),file()])}],expected_parts(videos=[("<Video 1>",list_part)]),{},"用中文描述样本可见变化，不分析声音，不宣称连续观察。",None))
    cases.append(("hybrid-media",[{"kind":"image","label":"<Picture 1>","role":"last_frame","value":tensors[1]},{"kind":"video","label":"<Video 1>","value":file()}],expected_parts([("<Picture 1>",blue)],[("<Video 1>",manual_video([0,6,11]))]),{},"参考视频颜色变化，在最后停留于参考图蓝色圆形。用中文一句话。",None))
    if args.phase in {"pairs","all"}:
        for case_id,plan,expected,settings,instruction,fmt in cases:
            if selected and case_id not in selected:continue
            start=time.monotonic(); row={"id":case_id,"passed":False,"requests":0}
            run=sp.StrataRun(settings,seed=731);token=sp._RUN.set(run)
            try:
                actual=media.build_strata_media_parts(plan) if plan else []
                if case_id=="video-list":
                    # File component source PTS and composite PTS are separate;
                    # the protocol source_timestamp follows the composite clock.
                    pass
                assert actual==expected,"Independent pixels/labels/timestamps/options differ"
                messages=[{"role":"system","content":"Answer only the requested final text. No reasoning in the final answer."},{"role":"user","content":[{"type":"text","text":instruction},*actual]}]
                if settings.get("video_mode")=="native" and run.identity().get("capabilities",{}).get("video",{}).get("native_verified") is not True:
                    try:run.complete(messages,temperature=.2,response_format=fmt)
                    except sp.StrataProviderError as error:
                        assert error.category=="capability" and run.requests==0
                        row.update(passed=True,acceptance="unsupported-native-rejected-before-post",summary=run.summary())
                        row["seconds"]=round(time.monotonic()-start,3);record(row)
                        continue
                    raise AssertionError("Unsupported native video was not rejected")
                payload={"model":config["model"],"messages":[messages[0],{"role":"user","content":[{"type":"text","text":instruction},*expected]}],"stream":False,"temperature":.2,"seed":731,"max_tokens":0,"reasoning_effort":settings.get("reasoning_effort","none"),"reasoning_budget_tokens":settings.get("reasoning_budget_tokens",0)}
                if fmt:payload["response_format"]=fmt
                # Direct baseline uses Requests, not StrataClient/complete.
                r=session.post(service+"/v1/chat/completions",json=payload,timeout=1800);row["requests"]+=1;r.raise_for_status();direct=r.json()
                emitted=[]; original_request=run.client.request
                def measured_request(path,body=None,**options):
                    if body is not None:emitted.append(copy.deepcopy(body))
                    return original_request(path,body,**options)
                run.client.request=measured_request
                bridge=run.complete(messages,temperature=.2,response_format=fmt);row["requests"]+=run.requests
                assert emitted==[payload],"Actual bridge HTTP payload differs from independent baseline"
                assert direct["model"]==config["model"] and direct["choices"][0]["finish_reason"]=="stop"
                direct_text=direct["choices"][0]["message"]["content"]
                assert isinstance(direct_text,str) and direct_text.strip() and bridge.strip()
                if fmt:json.loads(direct_text);json.loads(bridge)
                # Exact wire/options are required; prose is stochastic.
                row.update(passed=True,wire_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),direct=direct_text,bridge=bridge,summary=run.summary())
            except Exception as e:row["error"]=f"{type(e).__name__}: {e}"
            finally:run.close();sp._RUN.reset(token)
            row["seconds"]=round(time.monotonic()-start,3);record(row)
    if args.phase in {"queue","all"}:
        # Assets are copied only into our explicitly supplied isolated server's
        # input directory. No writes to the user's Strata service or workflow.
        input_dir=args.output/"input";input_dir.mkdir(exist_ok=True)
        red.save(input_dir/"red-square.png");blue.save(input_dir/"blue-circle.png")
        (input_dir/"red-transition.mp4").write_bytes(video_bytes)
        info=session.get(args.comfy+"/object_info",timeout=5).json()
        def defaults(node):
            result={}
            for k,c in info[node]["input"]["required"].items():
                opt=c[1] if len(c)>1 and isinstance(c[1],dict) else {}
                result[k]=opt.get("default",opt.get("options",c[0] if isinstance(c[0],list) else [None])[0])
            return result
        queue_cases=[("h3-linked","MiniMaxH3PromptEnhancerT8","prompt","黄色陶瓷杯静置木桌，镜头缓慢推进，无人物。",{"duration_seconds":5},{}),
            ("seedance-linked","Seedance20PromptEnhancerT8","prompt","黄色陶瓷杯静置木桌，镜头缓慢推进，无人物。",{},{}),
            ("qwen-linked","QwenImage21PromptEnhancerT8","prompt","黄色陶瓷杯静置木桌，静物摄影。",{},{}),
            ("music3-linked","MiniMaxMusic3PromptEnhancerT8","music_idea","轻柔中文流行歌曲，钢琴和弦乐，歌词只写四行，主题是雨后归家。",{},{}),
            ("yue2-linked","YuE2MusicPromptEnhancerT8","music_idea","轻柔中文流行，钢琴，雨后回家的四行歌词。",{"cot":"off（不使用谱面）"},{}),
            ("yue2-score","YuE2MusicPromptEnhancerT8","music_idea","Gentle piano pop, two short lines, four-bar melody for each voice. No extended sections.",{"cot":"melody（旋律谱面）","lyrics":"[Verse]\nHome in the rain\nLight at the door","lyrics_mode":"严格保留歌词 / Preserve","lyrics_language":"English","structure":"[Verse]"},{}),
            ("lyric-linked","T8LyricWriter","music_idea","中文流行歌词，雨后归家，只写短主歌与副歌。",{},{}),
            ("arrangement-linked","T8ArrangementPlanner","music_idea","雨后归家，轻柔流行，钢琴弦乐，三十秒编曲规划。",{},{}),
            ("creative-revision","T8DirectedRevision","original_prompt","A yellow cup rests on a wood table under warm light.",{"revision_request":"Change only the cup color to blue.","locked_anchors":"wood table; warm light"},{}),
            ("qwen-two-images","QwenImage21PromptEnhancerT8","prompt","把图1的红方块替换为图2的蓝圆形，保持白色背景。",{"input_mode":"图像编辑 / Image edit","reference_images.reference_image_0":["10",0],"reference_images.reference_image_1":["11",0]}, {"10":{"class_type":"LoadImage","inputs":{"image":"red-square.png"}},"11":{"class_type":"LoadImage","inputs":{"image":"blue-circle.png"}}}),
            ("h3-hybrid-video","MiniMaxH3PromptEnhancerT8","prompt","保持参考视频颜色变化，最后停留于蓝色圆形。无人物、无台词，不推断参考音轨。",{"task_type":"Hybrid（关键帧+参考混合生成）","duration_seconds":3,"last_frame":["10",0],"reference_videos.reference_video_0":["11",0]}, {"10":{"class_type":"LoadImage","inputs":{"image":"blue-circle.png"}},"11":{"class_type":"LoadVideo","inputs":{"file":"red-transition.mp4"}}}),
        ]
        for number,(case_id,node,field,brief,overrides,extras) in enumerate(queue_cases):
            if selected and case_id not in selected:continue
            start=time.monotonic();row={"id":case_id,"passed":False}
            try:
                values=defaults(node);values.update({field:["1",0],"api_mode":sp.STRATA_API_MODE,"seed":900+number,**overrides})
                if "api_mode" not in info[node]["input"]["required"] and "api_mode" not in info[node]["input"].get("optional",{}):values.pop("api_mode",None)
                graph={"1":{"class_type":"T8PromptText","inputs":{"text":brief}},"2":{"class_type":node,"inputs":values},**extras}
                string_ports=[i for i,t in enumerate(info[node]["output"]) if t=="STRING"]
                for port in string_ports:graph[str(20+port)]={"class_type":"T8ShowText","inputs":{"text":["2",port]}}
                # One queue uses an overriding shared Strata config and stale
                # cloud settings to prove they are not sent to the service.
                if case_id in {"qwen-linked","yue2-score","creative-revision"}:
                    cfg=defaults("T8LLMProviderConfig");cfg.update(provider="Strata",credential_alias="missing-old-cloud",custom_model="obsolete-cloud",openai_base_url="http://127.0.0.1:1/v1")
                    if case_id=="yue2-score":cfg.update(strata_max_tokens=4096)
                    graph["4"]={"class_type":"T8LLMProviderConfig","inputs":cfg};values.update(provider_config=["4",0])
                    if "api_mode" in info[node]["input"]["required"]:values["api_mode"]=info[node]["input"]["required"]["api_mode"][1]["default"]
                answer=session.post(args.comfy+"/prompt",json={"prompt":graph},timeout=10);answer.raise_for_status();pid=answer.json()["prompt_id"]
                while time.monotonic()-start<1800:
                    history=session.get(args.comfy+"/history/"+pid,timeout=10).json().get(pid)
                    if history:break
                    time.sleep(.5)
                else:raise RuntimeError("Queue exceeded acceptance deadline; no resubmission")
                save(args.output/(case_id+"-history.json"),history)
                if history["status"]["status_str"]!="success":raise RuntimeError(json.dumps(history["status"],ensure_ascii=False))
                outputs=[history["outputs"][str(20+i)]["text"][0] for i in string_ports]
                assert all(isinstance(x,str) for x in outputs) and outputs[0].strip()
                summary=history["outputs"].get("2",{}).get("strata_bridge",[None])[0]
                assert summary and summary["model"]==config["model"] and summary["request_count"]>=1
                row.update(passed=True,requests=summary["request_count"],outputs=outputs,summary=summary,prompt_id=pid)
            except Exception as e:row["error"]=f"{type(e).__name__}: {e}"
            row["seconds"]=round(time.monotonic()-start,3);record(row)
    after=session.get(service+"/v1/status",timeout=5).json()
    assert after["started"]==config["started"] and after["model"]==config["model"],"User service identity changed"
    print(json.dumps({"passed":sum(x["passed"] for x in records),"total":len(records),"generation_requests":sum(x.get("requests",0) for x in records),"service_lifecycle_calls":0}),flush=True)
    return 0 if all(x["passed"] for x in records) else 1

if __name__=="__main__":raise SystemExit(main())
