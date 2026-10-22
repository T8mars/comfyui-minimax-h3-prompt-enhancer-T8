"""Owned CPU Comfy + Chromium acceptance, with a loopback-only synthetic LLM.

Never loads a model, reads a credential, or addresses a user's running service.
Fixtures verify software boundaries, not translation accuracy or rendered art.
"""
from __future__ import annotations

import argparse
import copy
import http.server
import json
import os
import shutil
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents: parser.error("Evidence must be outside the repository")
    out.mkdir(parents=True, exist_ok=False)
    for name in ("input", "output", "temp", "user"): (out / name).mkdir()
    sys.path.insert(0, str(ROOT / "tests"))
    from test_strata_provider import status
    from test_moss_authoring_runtime import source_reply, translation_reply, plan
    from PIL import Image
    import requests
    for name, color in (("red.png", "red"), ("blue.png", "blue")):
        Image.new("RGB", (80, 64), color).save(out / "input" / name)
    for name in ("moss_authoring_fisher_independent.jpg", "moss_authoring_fisher_fusion.jpg"):
        shutil.copyfile(ROOT / "example_workflows" / name, out / "input" / name)
    calls, flags = [], {"bad_translation": False}

    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def answer(self, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            self.answer({"data": [{"id": "model-test"}]} if self.path == "/v1/models" else status())
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(payload)
            content = payload["messages"][1]["content"]
            request = json.loads(content[0]["text"] if isinstance(content, list) else content)
            stage = request.get("stage")
            if stage == "plan":
                flags["bad_translation"] = "FAIL_TRANSLATION" in request["brief"]
                context = request.get("existing_context")
                ids = context["edit_unit_ids"] if context else None
                reply = plan(request["page_count"] or 2, ids=ids, refs=range(1, len(request["references"]) + 1))
                if context:
                    old = {unit["unit_id"]: unit for unit in context["bundle"]["units"]}
                    for unit in reply["units"]:
                        source = next(iter(old[unit["unit_id"]]["sources"].values()))
                        unit["locked_visible_blocks"] = [item["text"] for item in source.get("items", []) if item["label"] == "text"]
            elif stage == "translation":
                reply = {"item_captions": {}} if flags["bad_translation"] else {
                    "summary_caption": "安静的一页。", "item_captions": {key: "保持原有元素和画面关系。" for key in request["item_ids"]}}
            elif stage == "source" and "COLLECTION SOURCE PROTOCOL" in payload["messages"][0]["content"]:
                previous = request.get("existing_unit")
                reply = {"source": copy.deepcopy(previous["sources"]["en"]), "sidecar": copy.deepcopy(previous["sidecar"])} if previous else source_reply()
            elif request.get("requested_format") == "layout":
                reply = source_reply()["source"]
                reply["items"][0]["label"] = "object"
                reply["items"] = [item for item in reply["items"] if item["label"] != "text"]
            else:
                reply = {"caption": "一只安静的红色小杯子，柔和的窗光落在杯沿。"}
            self.answer({"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply, ensure_ascii=False)}}]})

    provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    provider.daemon_threads = True
    thread = threading.Thread(target=provider.serve_forever, daemon=True); thread.start()
    with socket.socket() as probe: probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    provider_base = f"http://127.0.0.1:{provider.server_port}"
    cmd = [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(port), "--disable-auto-launch",
           "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name]
    for name in ("input", "output", "temp", "user"): cmd.extend(["--" + name + "-directory", str(out / name)])
    session = requests.Session(); session.trust_env = False
    process = None
    records = []
    try:
        with (out / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(cmd, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "STRATA_API_KEY": ""})
            until = time.monotonic() + 120
            while time.monotonic() < until:
                if process.poll() is not None: raise RuntimeError("Owned host exited; inspect server.log")
                try:
                    response = session.get(base + "/object_info", timeout=2)
                    if response.ok: info = response.json(); break
                except requests.RequestException: pass
                time.sleep(.25)
            else: raise TimeoutError("Owned host not ready")
            assert "MOSSAuthoringDirectorT8" in info and "MOSSAuthoringPageT8" in info
            (out / "object-info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")

            def defaults(name):
                values = {}
                for key, field in info[name]["input"]["required"].items():
                    settings = field[1] if len(field) > 1 and isinstance(field[1], dict) else {}
                    value = settings.get("default", field[0][0] if isinstance(field[0], list) else None)
                    if value is not None: values[key] = value
                return values
            def queue(label, graph, *, success=True, posts=None):
                before = len(calls)
                response = session.post(base + "/prompt", json={"prompt": graph}, timeout=20)
                if not response.ok: raise RuntimeError(label + " static rejection: " + response.text[:3000])
                pid = response.json()["prompt_id"]
                until = time.monotonic() + 75
                while time.monotonic() < until:
                    result = session.get(base + "/history/" + pid, timeout=5).json().get(pid)
                    if result: break
                    time.sleep(.15)
                else: raise TimeoutError(label + " unconfirmed; never resubmit")
                count = len(calls) - before
                (out / (label + ".json")).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                record = {"case": label, "status": result["status"]["status_str"], "posts": count}
                records.append(record); print(json.dumps(record), flush=True)
                assert (record["status"] == "success") == success, label
                if posts is not None: assert count == posts, (label, count, posts)
                return result
            def node(kind, **values): return {"class_type": kind, "inputs": {**defaults(kind), **values}}
            director = "MOSSAuthoringDirectorT8"
            config = node("T8LLMProviderConfig", provider="Strata", strata_url=provider_base)
            reference_nodes = {"8": node("LoadImage", image="red.png"), "9": node("LoadImage", image="blue.png"),
                               "11": node("ImageBatch", image1=["8", 0], image2=["9", 0])}
            values = dict(brief=["3", 0], profile="Comic / 漫画卡通", width=1256, height=1672, page_count=2,
                max_corrections=0, provider_config=["5", 0], recovery_slot="t8-authoring-acceptance-comic",
                **{"reference_images.reference_image_0": ["11", 0]})
            graph = {"1": node(director, **values), "2": node("T8ShowText", text=["1", 0]),
                "3": node("T8PromptText", text="简短版：两页中同一个红帽人物在窗前安静地伸手。"), "5": config, **reference_nodes,
                "6": node("MOSSAuthoringPageT8", bundle_json=["1", 0], page_index=1, language="en"),
                "7": node("T8ShowText", text=["6", 0]),
                "12": node("MOSSAuthoringPageT8", bundle_json=["1", 0], page_index=2, language="zh"),
                "13": node("T8ShowText", text=["12", 0])}
            first = queue("comic-two-pages-batch-en-zh", graph, posts=5)
            original = json.loads(first["outputs"]["2"]["text"][0])
            assert original["report"]["bilingual_complete"] and len(original["reference_map"]) == 2
            assert [row["batch_index"] for row in original["reference_map"]] == [0, 1]
            assert json.loads(first["outputs"]["7"]["text"][0])["items"][0]["label"] == "object"
            assert "安静" in first["outputs"]["13"]["text"][0]
            for position in (2, 4):
                assert not any(isinstance(message["content"], list) for message in calls[position]["messages"]), "Translation resends images"
            graph["1"]["inputs"].update(profile="Fisher / 通用长版", page_count=0, recovery_slot="t8-authoring-acceptance-fisher")
            graph["12"]["inputs"].update(language="zh")
            graph["6"]["inputs"].update(language="zh")
            before = len(calls)
            independent = queue("fisher-batch-independent", graph, posts=2)
            independent_bundle = json.loads(independent["outputs"]["2"]["text"][0])
            assert [u["reference_indices"] for u in independent_bundle["units"]] == [[1], [2]]
            for call in calls[before:]:
                parts = call["messages"][1]["content"]
                assert sum(p.get("type") == "image_url" for p in parts) == 1
                request = json.loads(parts[0]["text"])
                assert request["prior_validated_pages"] == []
            graph["1"]["inputs"].update(reference_mode="fusion", seed=1)
            graph["12"]["inputs"]["page_index"] = 1
            queue("fisher-explicit-fusion", graph, posts=1)

            context = {"schema_version": "t8-moss-authoring-context/v1", "mode": "full_layout", "bundle": original, "edit_unit_ids": ["page-2"]}
            graph["1"] = node(director, **{**values, "layout_context_json": json.dumps(context, ensure_ascii=False), "seed": 2})
            graph["6"]["inputs"].update(language="en")
            graph["12"]["inputs"].update(page_index=2, language="zh")
            revised = queue("comic-fixed-layout-edit-page-two-only", graph, posts=3)
            revised_bundle = json.loads(revised["outputs"]["2"]["text"][0])
            assert revised_bundle["units"][0] == original["units"][0]
            assert revised_bundle["edited_unit_ids"] == ["page-2"]

            graph["3"]["inputs"]["text"] = "FAIL_TRANSLATION 简短版。"
            queue("translation-failure-blocks-all-downstream", graph, success=False, posts=3)
            draft = session.get(base + "/t8-prompt-enhancer/moss-authoring/draft/" + values["recovery_slot"], timeout=5).json()
            assert draft["inspection_only"] is True and draft["complete"] is False
            assert any(u["available_languages"] == ["en"] for u in draft["units"])
            graph["1"]["inputs"]["recovery_action"] = "restore_last"
            graph["5"]["inputs"]["strata_url"] = "not-a-url"
            graph["3"] = node("T8SpeechReference", mode="Enabled", source_mode="AUDIO")
            graph["1"]["inputs"]["brief"] = ["3", 1]
            recovered = queue("restore-ignores-poisoned-provider-and-brief", graph, posts=0)
            assert json.loads(recovered["outputs"]["2"]["text"][0]) == revised_bundle
            context["edit_unit_ids"] = []
            graph["1"]["inputs"].update(recovery_action="normal", layout_context_json=json.dumps(context, ensure_ascii=False), seed=3)
            copied = queue("zero-edit-context-skips-lazy-provider-and-brief", graph, posts=0)
            assert json.loads(copied["outputs"]["2"]["text"][0])["units"] == original["units"]

            main_node = "MOSSImagePromptEnhancerT8"
            small = {"1": node(main_node, prompt=["3", 0], width=["12", 0], height=["12", 1], max_output_chars=["11", 0],
                authoring_profile="Fisher / 通用长版", output_format="Caption / 自然描述", output_language="中文", max_corrections=0, provider_config=["5", 0]),
                "2": node("T8ShowText", text=["1", 5]), "3": node("T8PromptText", text="简短版，一个杯子。"), "5": config,
                "8": reference_nodes["8"], "11": node("GetImageSize", image=["8", 0]),
                "12": node("ResolutionSelector", aspect_ratio="3:4 (Portrait Standard)", megapixels=2.0, multiple=8)}
            # The poisoned config above was a graph-local object; create a fresh
            # healthy config, never weaken the recovery test's invalid value.
            small["5"] = node("T8LLMProviderConfig", provider="Strata", strata_url=provider_base)
            main_result = queue("main-computed-int-80-and-1256x1672", small, posts=1)
            report = json.loads(main_result["outputs"]["2"]["text"][0])
            assert report["canvas"] == {"width": 1256, "height": 1672}
            assert report["authoring_length"]["max_output_chars"] == 80

            before_browser = len(calls)
            browser = subprocess.run(["node", str(ROOT / "tools/frontend_browser_cdp.mjs"), str(args.browser), base,
                str(out / "native-ui.png"), "comfy-moss-authoring", provider_base], cwd=ROOT, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=150)
            (out / "native-ui.log").write_text(browser.stdout + browser.stderr, encoding="utf-8")
            assert browser.returncode == 0, browser.stderr
            assert len(calls) - before_browser == 23, "Eight sample queues=15; native success=5, cached restore=0, failed translation=3"
            print(browser.stdout, flush=True)
            (out / "loopback-requests.json").write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")
            evidence = {"passed": True, "cases": records, "real_cpu_comfy": True, "real_chromium": True,
                        "model_inference": False, "translation_quality_verified": False, "rendered_image_verified": False}
            (out / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        provider.shutdown(); provider.server_close(); thread.join(2); session.close()
        (out / "owned-server-released.json").write_text(json.dumps({"pid": process.pid if process else None, "exited": process is None or process.poll() is not None}), encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
