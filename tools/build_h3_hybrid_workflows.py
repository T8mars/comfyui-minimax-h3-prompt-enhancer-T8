"""Generate only the three new Hybrid examples; never rewrite legacy files."""
from __future__ import annotations
import copy
import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
STEMS=("h3_hybrid_first_image", "h3_hybrid_last_image", "h3_hybrid_first_last_video")


def workflows():
    # Reuse the current complete 38-field node, not outdated positional defaults.
    source=json.loads((ROOT/"example_workflows/combat_camera_h3.json").read_text(encoding="utf8"))
    enhancer=next(n for n in source["nodes"] if n["type"]=="MiniMaxH3PromptEnhancerT8")
    for mode in ("first_image","last_image","first_last_video"):
        node=copy.deepcopy(enhancer)
        node.update(id=10,order=3,pos=[460,0],size=[640,1160],title="H3 Hybrid · "+mode)
        for port in node["inputs"]: port["link"]=None
        for port in node["outputs"]: port["links"]=None
        node["widgets_values"][0]="8秒一个连续镜头，结合实际首/尾帧与额外视觉参考；保留素材中的身份、外观与布局，运动路径清晰可达。仅使用已连接素材，不捏造音频分析。无新增台词、文字或配乐。"
        node["widgets_values"][1]="Hybrid（关键帧+参考混合生成）"
        node["widgets_values"][3]="1"
        node["widgets_values"][36]="check"
        # The new examples keep the existing socket order, including the final
        # optional combat socket (unconnected); it is never a widget field.
        nodes=[node]
        links=[]

        def connect_media(node_id,kind,port_name,y):
            link_id=len(links)+1
            inputs=[]
            outputs=[{"name":"VIDEO" if kind=="LoadVideo" else "IMAGE","type":"VIDEO" if kind=="LoadVideo" else "IMAGE","links":[link_id]}]
            if kind=="LoadImage": outputs.append({"name":"MASK","type":"MASK","links":None})
            nodes.append({"id":node_id,"type":kind,"pos":[0,y],"size":[400,300],"flags":{},"order":0,"mode":0,
                          "inputs":inputs,"outputs":outputs,"properties":{"Node name for S&R":kind},
                          "widgets_values":[""],"title":"上传素材 / Upload · "+port_name})
            index=next(i for i,p in enumerate(node["inputs"]) if p["name"]==port_name)
            node["inputs"][index]["link"]=link_id
            links.append([link_id,node_id,0,10,index,outputs[0]["type"]])

        if mode.startswith("first"):
            connect_media(1,"LoadImage","first_frame",0)
        if mode in ("last_image","first_last_video"):
            connect_media(2,"LoadImage","last_frame",340)
        connect_media(3,"LoadVideo" if mode.endswith("video") else "LoadImage",
                      "reference_videos.reference_video_0" if mode.endswith("video") else "reference_images.reference_image_0",680)
        key_link=len(links)+1
        key_port=next(i for i,p in enumerate(node["inputs"]) if p["name"]=="api_key")
        node["inputs"][key_port]["link"]=key_link
        nodes.append({"id":4,"type":"T8PromptText","pos":[0,1040],"size":[400,180],"flags":{},"order":0,"mode":0,
                      "inputs":[],"outputs":[{"name":"text","type":"STRING","links":[key_link]}],
                      "properties":{"Node name for S&R":"T8PromptText"},"widgets_values":[""],"title":"填写 API Key / Clear before sharing"})
        links.append([key_link,4,0,10,key_port,"STRING"])
        text_link=len(links)+1
        node["outputs"][0]["links"]=[text_link]
        nodes.append({"id":11,"type":"T8ShowText","pos":[1160,0],"size":[600,660],"flags":{},"order":4,"mode":0,
                      "inputs":[{"name":"text","type":"STRING","link":text_link}],"outputs":[{"name":"text","type":"STRING","links":None}],
                      "properties":{"Node name for S&R":"T8ShowText"},"widgets_values":[]})
        links.append([text_link,10,0,11,0,"STRING"])
        note="Hybrid 使用说明 / How to use\n1. 上传首帧和/或尾帧，另上传至少一个参考图/视频。每槽单图，批次请拆开。\n2. 素材编号依次为首帧、尾帧、额外参考图；视频独立从 Video 1 开始。\n3. 默认中文、质量只检查。四种渠道可切换；本地需视觉 GGUF/mmproj，不需要 API Key。\n4. 无音频分析、无视频时长上限（渠道/模型资源限制仍适用）；只写提示词，不生成视频。\n5. 支持 Relay；native 六段描述只覆盖交付时长，补齐区保持已完成末态。\n6. 新 Hybrid 工作流需要支持 Hybrid 的插件版本；勿降级运行。分享前清空密钥。"
        nodes.append({"id":12,"type":"Note","pos":[1160,720],"size":[600,380],"flags":{},"order":5,"mode":0,"inputs":[],"outputs":[],"properties":{},"widgets_values":[note]})
        name=f"h3_hybrid_{mode}.json"
        yield name,{"id":str(uuid.uuid5(uuid.NAMESPACE_URL,name)),"revision":0,"last_node_id":12,"last_link_id":len(links),"nodes":nodes,"links":links,"groups":[],"config":{},"extra":{"ds":{"scale":0.65,"offset":[30,40]}},"version":0.4}


def check():
    expected=dict(workflows())
    for name,graph in expected.items():
        path=ROOT/"example_workflows"/name
        if json.loads(path.read_text(encoding="utf8")) != graph:
            raise RuntimeError(f"{name}: Hybrid example differs from its reviewed generator")
        if not path.with_suffix(".jpg").is_file():
            raise RuntimeError(f"{name}: missing thumbnail")
    return len(expected)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--thumbnails-only",action="store_true")
    args=parser.parse_args()
    if args.check:
        print(json.dumps({"hybrid_workflows":check(),"passed":True}))
    elif args.thumbnails_only:
        from tools.build_example_workflows import _write_thumbnail
        for stem in STEMS:
            path=ROOT/"example_workflows"/(stem+".jpg")
            _write_thumbnail(path,"H3 Hybrid - "+stem.removeprefix("h3_hybrid_"),
                             "Keyframes + refs","Six-field prompt","Upload your media; no key or sample media is bundled")
    else:
        # Emit proposed artifacts for review/apply_patch; never rewrite old files.
        print(json.dumps(dict(workflows()),ensure_ascii=True))
