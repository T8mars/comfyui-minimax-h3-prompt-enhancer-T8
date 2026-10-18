"""Owned CPU Comfy queue + optional real frontend; loopback responses, zero inference.

Never attaches to or alters an existing server. Isolated user/output directories.
Fixture responses prove wiring and recovery, not model compliance or video quality.
"""
from __future__ import annotations
import argparse
import copy
import http.server
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
ON = "开启（实验） / On (experimental)"
OFF = "关闭 / Off"
MARKER = "T8 EXPERIMENTAL STORYBOARD METHOD v1.0.0"
H3_DRAFT = "integrated_multimodal_description: [Shot 1] A woman holds a ticket beside the station door.\n\noverall_soundscape: Room tone.\n\nnon_diegetic_music: N/A"
SD_DRAFT = "Shot 1: A woman holds a ticket beside the station door. Room tone continues."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--browser", type=Path, help="Optional explicit Chrome executable for native UI contracts.")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error("Use a new external evidence directory.")
    out.mkdir(parents=True, exist_ok=False)
    for name in ("user", "input", "output", "temp"):
        (out / name).mkdir()
    config = out / "test-paths.yaml"
    config.write_text("storyboard_test:\n  custom_nodes: " + json.dumps(str(ROOT / "tests/fixtures")) + "\n", encoding="utf-8")
    calls, results = [], []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == "/v1/models": self.reply({"data": [{"id": "storyboard-fixture"}]})
            else: self.reply({"service": "strata", "protocol_version": 1, "model": "storyboard-fixture", "loaded": True,
                              "auto_load": True, "started": 100, "instance_id": None, "context": {"native": 32768},
                              "concurrency": {"serving": 1}, "vision": {"enabled": False, "available": False}})
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(value)
            draft = H3_DRAFT if "QUEUE_H3" in json.dumps(value["messages"]) else SD_DRAFT
            self.reply({"model": "storyboard-fixture", "choices": [{"finish_reason": "stop", "message": {"content": draft}}]})
    fixture = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fixture.daemon_threads = True
    thread = threading.Thread(target=fixture.serve_forever, daemon=True); thread.start()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    command = [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(port),
               "--disable-auto-launch", "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name, "storyboard_runtime",
               "--extra-model-paths-config", str(config)]
    for name in ("user", "input", "output", "temp"):
        command.extend(["--" + name + "-directory", str(out / name)])
    import requests
    session = requests.Session(); session.trust_env = False
    process = None
    def save():
        (out / "evidence.json").write_text(json.dumps({"real_comfy_queue": True, "real_inference": False,
            "port": port, "pid": process.pid if process else None, "provider_calls": len(calls), "tests": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with (out / "server.log").open("w", encoding="utf-8") as log:
            import os
            process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env={**os.environ, "STRATA_API_KEY": ""})
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError("Owned server exited; inspect server.log")
                try:
                    response = session.get(base + "/object_info", timeout=2)
                    if response.ok: info = response.json(); break
                except requests.RequestException: pass
                time.sleep(.25)
            else: raise TimeoutError("Owned server not ready")
            assert "T8StoryboardRuntimeFixture" in info
            assert list(info["T8StoryboardDirectorConfig"]["input"]["required"]) == ["mode"]
            assert info["T8StoryboardDirectorConfig"]["input"]["required"]["mode"][1]["default"] == OFF
            assert "storyboard_director_config" not in info["MOSSImagePromptEnhancerT8"]["input"].get("optional", {})
            (out / "object-info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            def defaults(name):
                values = {}
                for key, field in info[name]["input"]["required"].items():
                    options = field[1] if len(field) > 1 and isinstance(field[1], dict) else {}
                    values[key] = options.get("default", field[0][0] if isinstance(field[0], list) else None)
                return values
            def queue(label, graph, error=None):
                response = session.post(base + "/prompt", json={"prompt": graph}, timeout=10)
                if not response.ok: raise RuntimeError(label + " graph rejected: " + response.text[:1500])
                pid = response.json()["prompt_id"]; deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    history = session.get(base + "/history/" + pid, timeout=3).json().get(pid)
                    if history: break
                    time.sleep(.1)
                else: raise TimeoutError("Queue outcome unknown; never resubmit automatically")
                (out / (label + ".json")).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
                if error:
                    assert history["status"]["status_str"] == "error"
                    assert error in json.dumps(history["status"], ensure_ascii=False), history["status"]
                else: assert history["status"]["status_str"] == "success", history["status"]
                results.append({"id": label, "passed": True, "expected_error": bool(error)})
                save(); print(json.dumps(results[-1]), flush=True)
                return history
            shared = {"1": {"class_type": "T8StoryboardDirectorConfig", "inputs": {"mode": ON}}}
            consumers = []
            for index, (node, tag) in enumerate((("MiniMaxH3PromptEnhancerT8", "H3"), ("Seedance20PromptEnhancerT8", "SD"))):
                main_id, show_id, text_id = str(2 + index * 3), str(3 + index * 3), str(4 + index * 3)
                values = defaults(node)
                values.update(prompt=[text_id, 0], output_language="English", duration_seconds=3600 if tag == "H3" else "3600",
                              shot_count="1", api_mode="Strata 本地服务（桥接）", recovery_slot=str(uuid.uuid4()),
                              provider_config=["9", 0], storyboard_director_config=["1", 0])
                shared[main_id] = {"class_type": node, "inputs": values}
                shared[show_id] = {"class_type": "T8ShowText", "inputs": {"text": [main_id, 0]}}
                shared[text_id] = {"class_type": "T8PromptText", "inputs": {"text": f"QUEUE_{tag}: A woman holds a ticket. One continuous shot for 3600 seconds."}}
                consumers.append((main_id, show_id, text_id))
            provider = defaults("T8LLMProviderConfig")
            provider.update(provider="Strata", strata_url=f"http://127.0.0.1:{fixture.server_port}")
            shared["9"] = {"class_type": "T8LLMProviderConfig", "inputs": provider}
            initial = queue("on-shared-config-linked-text-long-duration", shared)
            assert len(calls) == 2
            for call in calls: assert call["messages"][0]["content"].count(MARKER) == 1 and "3600" in str(call)
            for main_id, show_id, text_id in consumers:
                graph = {k: copy.deepcopy(shared[k]) for k in ("1", "9", main_id, show_id, text_id)}
                # The same statically valid producer fails if executed; recovery must skip it.
                graph["1"] = {"class_type": "T8StoryboardRuntimeFixture", "inputs": {"poison": True}}
                graph[main_id]["inputs"]["recovery_action"] = "restore_last"
                restored = queue("restore-skips-poison-" + main_id, graph)
                assert restored["outputs"][show_id]["text"] == initial["outputs"][show_id]["text"]
                assert len(calls) == 2
                graph[main_id]["inputs"]["recovery_action"] = "normal"
                queue("normal-executes-poison-" + main_id, graph, "STORYBOARD_POISON_EXECUTED")
                graph["1"]["inputs"]["poison"] = False
                queue("resolved-invalid-config-preflight-" + main_id, graph, "Unsupported storyboard_director_config")
                assert len(calls) == 2
                graph[main_id]["inputs"]["recovery_action"] = "restore_last"
                preserved = queue("last-good-survives-preflight-" + main_id, graph)
                assert preserved["outputs"][show_id]["text"] == initial["outputs"][show_id]["text"]
            for mode in (OFF, None):
                graph = copy.deepcopy(shared)
                graph["1"]["inputs"]["mode"] = OFF
                for main_id, _, _ in consumers:
                    graph[main_id]["inputs"]["recovery_slot"] = str(uuid.uuid4())
                    if mode is None: graph[main_id]["inputs"].pop("storyboard_director_config")
                before = len(calls)
                queue("off-fanout" if mode else "unconnected-fanout", graph)
                assert len(calls) == before + 2
                assert all(MARKER not in str(call) for call in calls[before:])
            if args.browser:
                completed = subprocess.run(["node", str(ROOT / "tools/frontend_browser_cdp.mjs"), str(args.browser), base,
                    str(out / "native-ui.png"), "comfy-storyboard"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=100)
                (out / "native-ui.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
                assert completed.returncode == 0, completed.stderr
                results.append({"id": "native-browser-save-reload-reconnect", "passed": True}); save()
            (out / "loopback-requests.json").write_text(json.dumps(calls, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        fixture.shutdown(); fixture.server_close(); thread.join(2); session.close()
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
