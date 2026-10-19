"""Owned CPU Comfy host + loopback provider; no inference or reference-repo writes."""
import argparse
import copy
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
OFF = "关闭 / Off"
ON = "开启（实验） / On (experimental)"
RULE = "T8 H3 VISUAL MARKER AUTHORING v1.0.0"
EVIDENCE = "T8_H3_MARKER_SOURCE_EVIDENCE_JSON"
DRAFT = """subject_definitions:
<Picture 1> supplies the character and source composition for <Subject 1>.

summary:
[reference generation] The character walks through the doorway and keeps moving.

retention_analysis:
<Picture 1> (identity and source composition): fully_preserved - retain the character and room, excluding annotation graphics.

detailed_description:
[Shot 1] <Subject 1> walks through the doorway and keeps moving. The camera remains still.

overall_soundscape:
Quiet room tone and footsteps.

non_diegetic_music:
N/A"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--producer-root", type=Path, required=True, help="Read-only existing audio checkout")
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents: parser.error("Use a new external evidence directory")
    out.mkdir(parents=True, exist_ok=False)
    for name in ("user", "input", "output", "temp"): (out/name).mkdir()
    from PIL import Image
    Image.new("RGB", (48,32), (90,90,90)).save(out/"input/h3-marker-demo-source.png")
    config = out / "test-paths.yaml"
    config.write_text("marker_test:\n  custom_nodes: " + json.dumps(str(ROOT / "tests/fixtures")) + "\n", encoding="utf-8")
    calls, results = [], []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"choices":[{"finish_reason":"stop","message":{"content":DRAFT}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    provider.daemon_threads = True
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    command = [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(port),
        "--disable-auto-launch", "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name, "marker_runtime",
        "--extra-model-paths-config", str(config)]
    for name in ("user", "input", "output", "temp"): command.extend(["--"+name+"-directory", str(out/name)])
    import requests
    session = requests.Session(); session.trust_env = False
    process = None
    def save():
        (out/"evidence.json").write_text(json.dumps(dict(real_comfy_queue=True, real_inference=False,
            real_readonly_producer=True, provider_calls=len(calls), tests=results), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with (out/"server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0), env={**os.environ, "PYTHONDONTWRITEBYTECODE":"1",
                    "T8_MARKER_PRODUCER_ROOT":str(args.producer_root.resolve()), "STRATA_API_KEY":""})
            deadline = time.monotonic()+120
            while time.monotonic()<deadline:
                if process.poll() is not None: raise RuntimeError("Owned host exited; inspect server.log")
                try:
                    response=session.get(base+"/object_info",timeout=2)
                    if response.ok: info=response.json(); break
                except requests.RequestException: pass
                time.sleep(.25)
            else: raise TimeoutError("Owned host not ready")
            (out/"object-info.json").write_text(json.dumps(info,ensure_ascii=False),encoding="utf-8")
            assert "MiniMaxH3AudioConditioningT8" not in info, "Full reference plugin must not be loaded"
            assert "MiniMaxH3VisualMarkerPrepareEXPT8" in info, "Read-only pure Prepare schema needed for example UI"
            assert list(info["T8H3VisualMarkerConfig"]["input"]["required"]) == ["mode","picture_selector"]
            def defaults(node):
                result={}
                for key, field in info[node]["input"]["required"].items():
                    options=field[1] if len(field)>1 and isinstance(field[1],dict) else {}
                    result[key]=options.get("default",field[0][0] if isinstance(field[0],list) else None)
                return result
            def queue(label,graph,error=None):
                response=session.post(base+"/prompt",json={"prompt":graph},timeout=10)
                if not response.ok: raise RuntimeError(label+" rejected: "+response.text[:1800])
                ident=response.json()["prompt_id"]; deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    history=session.get(base+"/history/"+ident,timeout=3).json().get(ident)
                    if history: break
                    time.sleep(.1)
                else: raise TimeoutError("Unknown outcome; never retry automatically")
                (out/(label+".json")).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
                assert history["status"]["status_str"] == ("error" if error else "success"), history["status"]
                if error: assert error in json.dumps(history["status"],ensure_ascii=False), history["status"]
                results.append(dict(id=label,passed=True,expected_error=bool(error))); save()
                print(json.dumps(results[-1]),flush=True)
                return history
            values=defaults("MiniMaxH3PromptEnhancerT8")
            values.update(prompt="A woman walks through the doorway and keeps moving. One shot, 3600 seconds.",task_type="Ref2VA",
                duration_seconds=3600, shot_count="1", output_language="English", api_mode="OpenAI兼容接口（备用）",
                openai_base_url=f"http://127.0.0.1:{provider.server_port}/v1", custom_model="marker-fixture", api_key="test-placeholder",
                recovery_slot=str(uuid.uuid4()), visual_marker_config=["2",0])
            values["reference_images.reference_image_0"]=["1",1]
            graph={"1":{"class_type":"T8MarkerRuntimeFixture","inputs":{"case":"valid","variant":0,"selector":1}},
                "2":{"class_type":"T8H3VisualMarkerConfig","inputs":{"mode":ON,"picture_selector":["1",2],"marker_plan":["1",0]}},
                "3":{"class_type":"MiniMaxH3PromptEnhancerT8","inputs":values},
                "4":{"class_type":"T8ShowText","inputs":{"text":["3",0]}}}
            initial=queue("on-real-producer-computed-selector",graph)
            assert len(calls)==1 and RULE in str(calls[-1]) and EVIDENCE in str(calls[-1]) and "3600" in str(calls[-1])
            assert len(info["MiniMaxH3PromptEnhancerT8"]["output"])==6
            queue("unchanged-cache-hit",graph); assert len(calls)==1
            graph["1"]["inputs"]["variant"]=1
            queue("changed-source-recomputes",graph); assert len(calls)==2
            for case, error in (("wrong_image","No matching"),("bad_record","Unsupported v1 fields")):
                bad=copy.deepcopy(graph); bad["1"]["inputs"]["case"]=case
                queue("preflight-"+case,bad,error); assert len(calls)==2
                bad["3"]["inputs"]["recovery_action"]="restore_last"
                recovered=queue("restore-after-"+case,bad)
                assert recovered["outputs"]["4"]["text"]==initial["outputs"]["4"]["text"] and len(calls)==2
            bad=copy.deepcopy(graph)
            bad["5"]={"class_type":"T8MarkerRuntimeFixture","inputs":{"case":"poison","variant":0,"selector":1}}
            bad["2"]["inputs"].update(marker_plan=["5",0],picture_selector=0)
            bad["3"]["inputs"]["recovery_action"]="restore_last"
            queue("restore-skips-new-plan-dependency",bad); assert len(calls)==2
            duplicate=copy.deepcopy(graph)
            duplicate["3"]["inputs"]["reference_images.reference_image_1"]=["1",1]
            duplicate["1"]["inputs"]["selector"]=0
            queue("duplicate-auto-rejected",duplicate,"Multiple matching"); assert len(calls)==2
            duplicate["1"]["inputs"]["selector"]=2
            queue("duplicate-explicit-selector",duplicate); assert len(calls)==3 and '\\"picture\\":\\"<Picture 2>\\"' in json.dumps(calls[-1])
            off=copy.deepcopy(graph)
            off["5"]={"class_type":"T8MarkerRuntimeFixture","inputs":{"case":"poison","variant":0,"selector":1}}
            off["2"]["inputs"].update(mode=OFF,marker_plan=["5",0],picture_selector=0)
            queue("off-skips-poison-plan-keeps-image",off); assert len(calls)==4 and RULE not in str(calls[-1])
            off["3"]["inputs"]["reference_images.reference_image_0"]=["5",1]
            queue("off-does-not-skip-image",off,"MARKER_POISON_EXECUTED"); assert len(calls)==4
            hybrid=copy.deepcopy(graph)
            hybrid["3"]["inputs"].update(task_type="Hybrid",first_frame=["1",1])
            hybrid["1"]["inputs"]["selector"]=2
            queue("hybrid-keyframe-plus-extra-warning",hybrid); assert len(calls)==5
            slot=values["recovery_slot"]
            status=session.get(base+"/t8-prompt-enhancer/completion-recovery/MiniMaxH3PromptEnhancerT8/"+slot,timeout=3).json()
            marker=status["creation_metadata"]["h3_visual_marker"]
            assert marker["picture"]==2 and "marker_also_keyframe" in marker["warning_codes"] and marker["downstream_verified"] is False
            if args.browser:
                result=subprocess.run(["node",str(ROOT/"tools/frontend_browser_cdp.mjs"),str(args.browser),base,str(out/"native-ui.png"),"comfy-marker",
                    f"http://127.0.0.1:{provider.server_port}/v1"],
                    cwd=ROOT,capture_output=True,text=True,encoding="utf-8",timeout=110)
                (out/"native-ui.log").write_text(result.stdout+result.stderr,encoding="utf-8")
                assert result.returncode==0,result.stderr
                assert len(calls)==10, "Five native-browser queues must each use the owned provider exactly once"
                for index, (active, picture, images) in enumerate([(True,1,1),(False,1,1),(True,1,1),(False,2,2),(True,2,2)], start=5):
                    message=calls[index]["messages"]
                    system=message[0]["content"]
                    user=message[1]["content"]
                    texts="\n".join(part["text"] for part in user if part.get("type")=="text")
                    assert (RULE in system)==active
                    assert texts.count(EVIDENCE)==int(active)
                    if active: assert f'"picture":"<Picture {picture}>"' in texts
                    assert sum(part.get("type")=="image_url" for part in user)==images
                results.append(dict(id="native-ui-save-reload-reconnect",passed=True)); save()
            # Requests include test images/text only; never actual keys or user media.
            (out/"loopback-requests.json").write_text(json.dumps(calls,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        provider.shutdown(); provider.server_close(); thread.join(2); session.close(); save()
    return 0


if __name__=="__main__": raise SystemExit(main())
