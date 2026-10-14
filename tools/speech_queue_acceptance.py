"""Explicit isolated real Comfy queue acceptance; never touch the user's queue.

The two generation cases call the selected existing LLM service. ASR native
inference is measured independently by speech_real_acceptance.py.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-real", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8193)
    parser.add_argument("--llm-url", default="http://127.0.0.1:8081")
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Acceptance artifacts must be outside the repository")
    out.mkdir(parents=True, exist_ok=False)
    for name in ("user", "input", "output", "temp"):
        (out / name).mkdir()
    import requests
    session = requests.Session(); session.trust_env = False
    base = f"http://127.0.0.1:{args.port}"
    # Refuse an occupied port; do not reuse a live user's Comfy process.
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    command = [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(args.port),
        "--disable-auto-launch", "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name,
        "--user-directory", str(out / "user"), "--input-directory", str(out / "input"),
        "--output-directory", str(out / "output"), "--temp-directory", str(out / "temp")]
    records = []
    def save():
        (out / "queue-results.json").write_text(json.dumps({"real_comfy_queue": True,
            "real_llm_cases": 2, "asr_inference_scope": "separate native acceptance", "cases": records},
            ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            started = time.monotonic()
            while time.monotonic() - started < 120:
                if process.poll() is not None: raise RuntimeError("Owned Comfy server exited; inspect server.log")
                try:
                    response = session.get(base + "/object_info", timeout=2)
                    if response.status_code == 200:
                        info = response.json(); break
                except requests.RequestException: pass
                time.sleep(.25)
            else: raise TimeoutError("Owned Comfy server startup timed out")
            assert "T8SpeechReference" in info
            def defaults(name):
                values = {}
                for key, field in info[name]["input"]["required"].items():
                    settings = field[1] if len(field) > 1 and isinstance(field[1], dict) else {}
                    values[key] = settings.get("default", field[0][0] if isinstance(field[0], list) else None)
                return values
            def queue(label, graph):
                response = session.post(base + "/prompt", json={"prompt": graph}, timeout=15)
                if response.status_code != 200: raise RuntimeError(label + " graph rejected: " + response.text[:3000])
                pid = response.json()["prompt_id"]; started = time.monotonic()
                while time.monotonic() - started < 1800:
                    result = session.get(base + "/history/" + pid, timeout=5).json().get(pid)
                    if result: break
                    time.sleep(.2)
                else: raise TimeoutError("Queue result unconfirmed; no automatic resubmission")
                (out / (label + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                passed = result["status"]["status_str"] == "success"
                records.append({"id": label, "passed": passed, "seconds": round(time.monotonic()-started, 3), "prompt_id": pid})
                save(); print(json.dumps(records[-1]), flush=True)
                if not passed: raise RuntimeError(label + " failed; inspect its saved history")
                return result
            helper = defaults("T8SpeechReference")
            helper.update(mode="Off", source_mode="AUDIO")
            bad_cfg = defaults("T8LLMProviderConfig"); bad_cfg.update(provider="Strata", strata_url="not-a-valid-url")
            graph = {"1": {"class_type": "T8SpeechReference", "inputs": {**helper, "provider_config": ["3", 0]}},
                "2": {"class_type": "T8ShowText", "inputs": {"text": ["1", 1]}},
                "3": {"class_type": "T8LLMProviderConfig", "inputs": bad_cfg}}
            assert queue("off-skips-runtime-invalid-provider", graph)["outputs"]["2"]["text"] == [""]
            helper.update(mode="Enabled", source_mode="Provided text", provided_text=["4", 0])
            graph["1"]["inputs"] = {**helper, "provider_config": ["3", 0]}
            graph["4"] = {"class_type": "T8PromptText", "inputs": {"text": "1\n00:00:00,100 --> 00:00:01,100\n等我回来。"}}
            assert queue("provided-linked-string-skips-provider", graph)["outputs"]["2"]["text"] == ["等我回来。"]
            cfg = defaults("T8LLMProviderConfig"); cfg.update(provider="Strata", strata_url=args.llm_url, strata_max_tokens=2048)
            active = {"1": {"class_type": "T8SpeechReference", "inputs": {**defaults("T8SpeechReference"),
                "mode": "Enabled", "source_mode": "Provided text", "provided_text": ["4", 0], "provider_config": ["3", 0]}},
                "3": graph["3"], "4": {"class_type": "T8PromptText", "inputs": {"text": graph["4"]["inputs"]["text"] + "\n\n"}},
                "6": {"class_type": "T8LLMProviderConfig", "inputs": cfg}}
            consumers = []
            for index, node in enumerate(("MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8")):
                slot = str(uuid.uuid4())
                values = defaults(node)
                values.update(prompt="A woman waits by a station door, pockets her ticket and looks at the clock. No additional people. Silent scene: no spoken dialogue or voice-over; environmental room tone only.",
                    output_language="English", api_mode="Strata 本地服务（桥接）", recovery_slot=slot,
                    provider_config=["6", 0], speech_reference=["1", 0])
                main_id, show_id = str(5 + index * 3), str(7 + index * 3)
                active[main_id] = {"class_type": node, "inputs": values}
                active[show_id] = {"class_type": "T8ShowText", "inputs": {"text": [main_id, 0]}}
                consumers.append((node, values, main_id, show_id))
            normal = queue("h3-seedance-shared-speech-fanout", active)["outputs"]
            assert len(normal["1"]["speech_reference"]) == 1, "One helper result fans out without mutation"
            for node, values, main_id, show_id in consumers:
                first = normal[show_id]["text"]; assert first[0].strip()
                # Cache fingerprint changes, and this helper would fail if executed.
                restore_graph = {"1": {"class_type": "T8SpeechReference", "inputs": {**defaults("T8SpeechReference"), "mode": "Enabled", "source_mode": "AUDIO"}},
                    "6": active["6"], main_id: active[main_id], show_id: active[show_id]}
                values["recovery_action"] = "restore_last"
                restored = queue(node + "-restore-poisoned-asr", restore_graph)["outputs"][show_id]["text"]
                assert restored == first
                values["recovery_slot"] = str(uuid.uuid4())
                response = session.post(base + "/prompt", json={"prompt": restore_graph}, timeout=15); response.raise_for_status()
                pid = response.json()["prompt_id"]
                for _ in range(100):
                    history = session.get(base + "/history/" + pid, timeout=5).json().get(pid)
                    if history: break
                    time.sleep(.1)
                assert history and history["status"]["status_str"] == "error"
                messages = json.dumps(history["status"], ensure_ascii=False)
                assert "No completed result" in messages or "recoverable" in messages or "complete" in messages or "No in-memory result" in messages
                assert "Connect only" not in messages, "Missing recovery must not execute poisoned ASR"
                records.append({"id": node + "-missing-cache-does-not-run-asr", "passed": True}); save()
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
    save()
    return 0 if records and all(row["passed"] for row in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
