"""Generate only new H3 authoring examples; existing producer nodes stay unchanged."""
import argparse
import copy
import json
from pathlib import Path
from build_storyboard_workflows import generate as storyboard_examples
from build_example_workflows import _workflow, _socket, _show_text_node

ROOT = Path(__file__).resolve().parents[1]
STEMS = ("h3_visual_marker_ref2va", "h3_visual_marker_hybrid")
SPEC = {"markers":[
    {"marker_id":"walker","kind":"actor","role_id":"A","color":"cyan","description":"the woman in the red coat","xyxy":[.1,.1,.4,.9]},
    {"marker_id":"door","kind":"target","color":"yellow","description":"the doorway on the right","xyxy":[.65,.2,.95,.95]}],
    "relations":[{"actor_marker_id":"walker","target_marker_id":"door","action":"walk through the doorway and keep moving, without stopping"}]}


def node(nid, kind, pos, inputs, outputs, values, title):
    return dict(id=nid,type=kind,pos=pos,size=[430,280],flags={},order=0,mode=0,inputs=inputs,
        outputs=[dict(name=name,type=typ,links=[]) for name,typ in outputs],
        properties={"Node name for S&R":kind},widgets_values=values,title=title)


def generate():
    template=storyboard_examples()["storyboard_director_h3_comparison"]
    result={}
    for hybrid in (False, True):
        main=copy.deepcopy(next(n for n in template["nodes"] if n["id"]==2))
        main.update(id=4,pos=[1000,40],title="H3 · Hybrid" if hybrid else "H3 · Ref2VA")
        main["widgets_values"][0]="红衣人物从画面左侧走向右侧门口，穿过后继续前进，不停下。一个连续镜头，保留人物、场景，不新增对白、人物或音乐；青框标记人物，黄框标记门口，彩色框只是参考注释。"
        main["widgets_values"][1]="Hybrid（关键帧+参考混合生成）" if hybrid else "Ref2VA（参考图/视频生音视频）"
        main["widgets_values"][3]="1"
        for item in main["inputs"]: item["link"]=None
        for item in main["outputs"]: item["links"]=[]
        main["inputs"].append(_socket("visual_marker_config","T8_H3_VISUAL_MARKER_CONFIG",None))
        # Explicit Autogrow item uses the real API prefix, not an invented port.
        if not any(i["name"]=="reference_images.reference_image_0" for i in main["inputs"]):
            main["inputs"].append(_socket("reference_images.reference_image_0","IMAGE",None))
        image=node(1,"LoadImage",[0,40],[],[("IMAGE","IMAGE"),("MASK","MASK")],
            ["h3-marker-demo-source.png","image"],"① 上传教程配套 PNG / Upload demo PNG")
        prepare=node(2,"MiniMaxH3VisualMarkerPrepareEXPT8",[470,40],[_socket("image","IMAGE",None)],
            [("marked_image","IMAGE"),("marker_plan","T8_H3_VISUAL_MARKER_PLAN"),("report_json","STRING")],
            ["render_rectangles",json.dumps(SPEC,ensure_ascii=False),3,""],"现有 audio Prepare（需已安装）")
        helper=node(3,"T8H3VisualMarkerConfig",[470,500],[_socket("marker_plan","T8_H3_VISUAL_MARKER_PLAN",None)],
            [("visual_marker_config","T8_H3_VISUAL_MARKER_CONFIG")],["关闭 / Off",0],"本项目入口 · 默认 Off / Opt in explicitly")
        helper["size"]=[500,170]
        show=_show_text_node(5,None,[1740,40])
        notes=node(6,"Note",[0,550],[],[],["入门：点击空间配置节点的【示例与接线】按钮，下载配套 PNG，再上传到 Load Image。\n需先安装现有 audio 插件，才能找到 H3 Marker · Prepare。\n青框人物 walker → 黄框门口 door：走过去、穿过、继续前进。\nmarkers 定义人物/目标，xyxy 为源图0..1左上/右下坐标；relations 用ID配对动作。换图时修改标记。\nPrepare.marked_image → H3参考图；marker_plan → 空间配置 → H3.visual_marker_config。\n配置默认Off，手动切On启用。selector=0自动；Ref2VA标记Picture1，Hybrid首帧后标记Picture2。\nHybrid首帧用干净源图；配置自己的增强渠道，再运行获取提示词。\n接生成：enhanced_prompt → 现有 Prompt.base_prompt [manual_original] → recipe → Bind。\n保持上下游图序一致，marker只插一次；不保证硬轨迹或去框。"],"② 接线与运行步骤 / Quick start")
        notes["size"]=[450,440]
        nodes=[image,prepare,helper,main,show,notes];links=[]
        def link(src,out,dst,name,typ):
            index=next(i for i,v in enumerate(dst["inputs"]) if v["name"]==name)
            lid=len(links)+1
            src["outputs"][out]["links"].append(lid);dst["inputs"][index]["link"]=lid
            links.append([lid,src["id"],out,dst["id"],index,typ])
        link(image,0,prepare,"image","IMAGE")
        link(prepare,1,helper,"marker_plan","T8_H3_VISUAL_MARKER_PLAN")
        link(helper,0,main,"visual_marker_config","T8_H3_VISUAL_MARKER_CONFIG")
        link(prepare,0,main,"reference_images.reference_image_0","IMAGE")
        if hybrid: link(image,0,main,"first_frame","IMAGE")
        link(main,0,show,"text","STRING")
        stem="h3_visual_marker_"+("hybrid" if hybrid else "ref2va")
        result[stem]=_workflow(stem,nodes,links)
    return result


def check():
    for stem,data in generate().items():
        assert json.loads((ROOT/"example_workflows"/(stem+".json")).read_text(encoding="utf-8"))==data
        nodes={n["id"]:n for n in data["nodes"]}
        assert nodes[3]["widgets_values"]==["关闭 / Off",0]
        assert len(nodes[4]["widgets_values"])==38
        for n in nodes.values():
            assert len({i["name"] for i in n["inputs"]})==len(n["inputs"]), "Duplicate input name"
        for lid,src,out,dst,inp,kind in data["links"]:
            assert kind==nodes[src]["outputs"][out]["type"]==nodes[dst]["inputs"][inp]["type"]
            assert lid in nodes[src]["outputs"][out]["links"] and nodes[dst]["inputs"][inp]["link"]==lid
    print("H3 marker examples: two new Off-default workflows, native 38+2 fields, existing Prepare references only.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true");args=parser.parse_args()
    if args.check: check()
    else:
        from generate_workflow_thumbnails import make_card
        for stem,data in generate().items():
            (ROOT/"example_workflows"/(stem+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            make_card("H3 · 空间标记（实验）","Hybrid" if "hybrid" in stem else "Ref2VA",(40,120,130)).save(
                ROOT/"example_workflows"/(stem+".jpg"),"JPEG",quality=88,optimize=True,progressive=True)
