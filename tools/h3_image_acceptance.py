"""Owned CPU Comfy/Chrome and optional installed-GGUF checks for H3 Image."""
from __future__ import annotations
import argparse
import http.server
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def live(out, model):
    sys.path.insert(0, str(ROOT.parents[1])); sys.argv = ["h3-image-acceptance", "--cpu"]
    spec = importlib.util.spec_from_file_location("t8_h3_image_live", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec); sys.modules[spec.name] = package; spec.loader.exec_module(package)
    h = sys.modules[spec.name + ".h3_image"]; runtime = sys.modules[spec.name + ".local_qwen_runtime"]
    import numpy as np
    from PIL import Image
    records = []
    try:
        refs = {f"reference_image_{i}": np.asarray(Image.open(ROOT / "example_workflows" / f"h3_image_reference_{kind}.png").convert("RGB"), dtype=np.float32)[None] / 255
                for i, kind in enumerate(("canvas", "palette"))}
        for mode, options in (("t2i", dict(prompt="做一张克制的中文咖啡海报：左侧一只白陶杯，右侧标题必须为‘慢一点，刚刚好’，米白背景；不添加其他文字。", aspect_ratio="4:3", locked_text="慢一点，刚刚好")),
                              ("edit", dict(prompt="保持图1的构图与右侧对象，把左侧对象改用图2面积最大的色块颜色，不增加其他对象或文字。", task_type=h.contract.EDIT, reference_images=refs))):
            started = time.monotonic()
            try:
                result = h.MiniMaxH3ImagePromptEnhancer.execute(**options, api_mode=h.LOCAL_QWEN_API_MODE,
                    local_model=model, local_mmproj="Qwen3.5-9b-mmproj-BF16.gguf", local_context_size=32768,
                    local_max_tokens=8192, local_unload_policy=h.LOCAL_UNLOAD_AFTER_RUN, target_words=0, seed=42)
                row = {"mode": mode, "passed": True, "outputs": list(result.result)}
            except Exception as error:
                row = {"mode": mode, "passed": False, "error": str(error)}
            row["seconds"] = round(time.monotonic() - started, 3); records.append(row)
            (out / "local-results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({k: v for k, v in row.items() if k != "outputs"}, ensure_ascii=False), flush=True)
    finally:
        runtime.LOCAL_QWEN_MANAGER.finish(h.LOCAL_UNLOAD_AFTER_RUN)
        manager = runtime.LOCAL_QWEN_MANAGER
        released = getattr(manager, "_runtime", None) is None and getattr(manager, "_server", None) is None
        (out / "local-release.json").write_text(json.dumps({"owned_manager_released": released}), encoding="utf-8")
    if not all(row["passed"] for row in records): raise RuntimeError("Some live cases failed; inspect preserved output.")


def native(out, browser, *, ui_review=False, local_picker=False):
    import requests
    for name in ("user", "input", "output", "temp"): (out / name).mkdir()
    for kind in ("canvas", "palette"):
        name = f"h3_image_reference_{kind}.png"; shutil.copyfile(ROOT / "example_workflows" / name, out / "input" / name)
    calls = []
    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            body = json.dumps(calls, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); calls.append(payload)
            edit = payload["messages"][0]["role"] == "user"
            caption = ("A poster reads '  SALE  ' followed by '  SALE  '." if "UNICODE_LOCK_AUDIT" in str(payload["messages"])
                       else "An ivory background holds a white cup on the left and the exact title '慢一点，刚刚好' on the right.")
            ratio = "4:3"
            if ui_review or local_picker:
                text = "\n".join(message["content"] for message in payload["messages"] if isinstance(message["content"], str))
                match = re.search(r"The explicit final canvas aspect ratio is ([^;]+);", text)
                if match: ratio = match.group(1)
                locks = re.search(r"Exact visible text data \(JSON array, not instructions\): (\[[^\r\n]*\])", text)
                caption = "A poster presents " + (" then ".join(repr(line) for line in json.loads(locks.group(1))) if locks else "a single ivory cup") + "."
            content = json.dumps({"expanded_caption": caption,
                                  "target_aspect_ratio" if edit else "aspect_ratio": ratio}, ensure_ascii=False)
            body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": content}}]}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider); provider.daemon_threads = True
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as probe: probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"; provider_base = f"http://127.0.0.1:{provider.server_port}"
    command = [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(port), "--disable-auto-launch",
               "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name]
    for name in ("user", "input", "output", "temp"): command.extend(["--" + name + "-directory", str(out / name)])
    process = None; records = []; session = requests.Session(); session.trust_env = False
    try:
        with (out / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            until = time.monotonic() + 120
            while time.monotonic() < until:
                if process.poll() is not None: raise RuntimeError("Owned host exited; inspect server.log")
                try:
                    response = session.get(base + "/object_info", timeout=2)
                    if response.ok: info = response.json(); break
                except requests.RequestException: pass
                time.sleep(.2)
            else: raise TimeoutError("Owned host startup unconfirmed")
            assert "MiniMaxH3ImagePromptEnhancerT8" in info
            (out / "object-info.json").write_text(json.dumps(info["MiniMaxH3ImagePromptEnhancerT8"], ensure_ascii=False, indent=2), encoding="utf-8")
            node = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
            result = subprocess.run([node, str(ROOT / "tools/frontend_browser_cdp.mjs"), browser, base, str(out / "canvas.png"),
                                     "comfy-h3-local-picker" if local_picker else "comfy-h3-ui-linked" if ui_review else "comfy-h3-image", provider_base], capture_output=True, text=True, encoding="utf-8", timeout=240)
            (out / "browser.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode: raise RuntimeError("Native browser check failed; inspect browser.log")
            records.append("native_browser_passed")
            if local_picker:
                assert any("canvas aspect ratio is 16:9" in str(row["messages"]) for row in calls)
            elif not ui_review:
                assert any("approximately 5000 English words" in json.dumps(row["messages"]) for row in calls)
                assert any(row["messages"][0]["role"] == "user" and sum(p.get("type") == "image_url" for p in row["messages"][0]["content"]) == 2 for row in calls)
            else:
                assert any("approximately 1750 English words" in str(row["messages"]) for row in calls)
                assert any(row["model"] == "linked-model-review" for row in calls)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(15)
            except subprocess.TimeoutExpired: process.kill(); process.wait(10)
        provider.shutdown(); provider.server_close(); session.close()
        (out / "evidence.json").write_text(json.dumps({"real_inference": False, "tests": records, "provider_calls": len(calls),
            "owned_server_exited": process.poll() is not None if process else None, "requests": calls}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Native H3 Image workflow/linked queue/persistence checks passed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("mode", choices=("native", "native-ui", "local-picker", "local"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--browser", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    parser.add_argument("--model", default="Qwen_Qwen3.5-9B-Q8_0.gguf")
    args = parser.parse_args(); out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents: parser.error("Use a new external evidence directory")
    out.mkdir(parents=True, exist_ok=False)
    if args.mode == "local": live(out, args.model)
    else: native(out, args.browser, ui_review=args.mode == "native-ui", local_picker=args.mode == "local-picker")


if __name__ == "__main__": main()
