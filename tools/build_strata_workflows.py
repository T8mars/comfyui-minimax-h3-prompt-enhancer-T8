"""Build only Strata examples, never rewrite the original workflows."""
import argparse
import copy
import json
from pathlib import Path
from build_example_workflows import _provider_node, _h3_node, _show_text_node, _workflow, _workflow_id, _write_thumbnail

ROOT=Path(__file__).resolve().parents[1]
STEMS=("strata_h3_text", "strata_qwen_image_edit", "strata_h3_hybrid_video")
MODE="Strata 本地服务（桥接）"
DEFAULTS=["http://127.0.0.1:8080","AUTO","","none",0,0,"frames",1.,8,1800.,False]
CONFIG_NAMES=["provider","temperature_policy","local_model","local_mmproj","local_context_size","local_max_tokens","local_think_mode","local_reasoning_effort","local_video_sample_fps","local_unload_policy","local_comfy_memory_policy","credential_alias","openai_base_url","custom_model","ai_workshop_model","extra_parameters_json","strata_url","strata_model","strata_credential_alias","strata_reasoning_effort","strata_max_tokens","strata_reasoning_budget_tokens","strata_video_mode","strata_video_sample_fps","strata_video_max_frames","strata_timeout_s","strata_allow_private_network"]

def workflows():
    config=_provider_node(1,[1],[0,0]);config["widgets_values"][0]="Strata"
    config["widgets_values"]+=DEFAULTS
    config["widgets_values_named"]=dict(zip(CONFIG_NAMES,config["widgets_values"],strict=True))
    config["properties"]["t8_provider_config_widgets_schema"]=1
    main=_h3_node(2,1,[550,0],prompt="黄色陶瓷杯静置木桌，镜头缓慢推进；无人物、无台词。",output_links=[2],api_mode=MODE)
    modern=json.loads((ROOT/"example_workflows/combat_camera_h3.json").read_text(encoding="utf-8"))
    values=copy.deepcopy(next(n for n in modern["nodes"] if n["type"]==main["type"])["widgets_values"])
    values[0]=main["widgets_values"][0];values[1]="T2VA（文生音视频）";values[11]=MODE
    main["widgets_values"]=values
    text=_workflow(STEMS[0],[config,main,_show_text_node(3,2,[1250,120])],[[1,1,0,2,5,"T8_LLM_PROVIDER_CONFIG"],[2,2,0,3,0,"STRING"]])
    edit=json.loads((ROOT/"example_workflows/qwen_image21_edit_example.json").read_text(encoding="utf-8"))
    qwen=next(n for n in edit["nodes"] if n["type"]=="QwenImage21PromptEnhancerT8")
    qwen["widgets_values"][5]=MODE
    edit["id"]=_workflow_id(STEMS[1])
    hybrid=json.loads((ROOT/"example_workflows/h3_hybrid_first_last_video.json").read_text(encoding="utf-8"))
    h3=next(n for n in hybrid["nodes"] if n["type"]=="MiniMaxH3PromptEnhancerT8")
    h3["widgets_values"][11]=MODE
    hybrid["id"]=_workflow_id(STEMS[2])
    return dict(zip(STEMS,(text,edit,hybrid),strict=True))

def check():
    for stem,expected in workflows().items():
        path=ROOT/"example_workflows"/(stem+".json")
        actual=json.loads(path.read_text(encoding="utf-8"))
        assert actual==expected,stem+": expected source changed"
        assert path.with_suffix(".jpg").is_file(),stem+": missing thumbnail"
        assert "sk-" not in path.read_text(encoding="utf-8")
        nodes={n["id"]:n for n in actual["nodes"]}
        for _,source,port,target,slot,kind in actual["links"]:
            assert source in nodes and target in nodes
            assert 0<=port<len(nodes[source]["outputs"]) and 0<=slot<len(nodes[target]["inputs"])
            assert nodes[target]["inputs"][slot]["type"]==kind
    print("Strata examples: 3 workflows, blank keys, frozen source derivations and valid links.")

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args()
    if not args.check:
        for stem,value in workflows().items():
            path=ROOT/"example_workflows"/(stem+".json")
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            _write_thumbnail(path.with_suffix(".jpg"),"STRATA SERVICE BRIDGE","Text / Images / VIDEO","Native prompts","Existing service | No audio | No cloud key")
    check()

if __name__=="__main__":main()
