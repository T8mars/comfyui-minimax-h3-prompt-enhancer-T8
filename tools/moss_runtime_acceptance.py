"""Opt-in owned-process queue/GGUF/render acceptance. No cloud inference or Key."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def local(out, model):
    sys.path.insert(0, str(ROOT.parents[1]))
    sys.argv = ["moss-gguf-acceptance", "--cpu"]
    spec = importlib.util.spec_from_file_location("t8_moss_runtime", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    moss = sys.modules[spec.name + ".moss_image"]
    runtime = sys.modules[spec.name + ".local_qwen_runtime"]
    records = []
    try:
        for label, values in (
            ("caption-zh", {"prompt": "一张自然照片：只有一只白瓷杯在灰色桌面上，窗边柔光，不要文字。", "output_language": "中文", "output_format": moss.contract.CAPTION}),
            ("layout-copy", {"prompt": "A minimal poster: one ivory cup on the left, headline on the right. Only the locked visible text.", "output_format": moss.contract.LAYOUT, "locked_text": "春日来信"}),
        ):
            started = time.monotonic()
            try:
                result = moss.MOSSImagePromptEnhancer.execute(**values, api_mode=moss.LOCAL_QWEN_API_MODE,
                    local_model=model, local_context_size=16384, local_max_tokens=4096, max_corrections=1,
                    local_unload_policy=moss.LOCAL_UNLOAD_AFTER_RUN, recovery_slot="t8-moss-local-" + label).result
                records.append({"case": label, "passed": True, "outputs": list(result), "seconds": round(time.monotonic()-started, 3)})
            except Exception as error:
                records.append({"case": label, "passed": False, "error": str(error)[:1000], "seconds": round(time.monotonic()-started, 3)})
            print(json.dumps({k: v for k, v in records[-1].items() if k != "outputs"}, ensure_ascii=False), flush=True)
            (out / "local-results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        # Only this process owns this manager; do not address user's services.
        runtime.LOCAL_QWEN_MANAGER.finish(moss.LOCAL_UNLOAD_AFTER_RUN)
        status = runtime.runtime_status()
        manager = runtime.LOCAL_QWEN_MANAGER
        status["owned_manager_empty"] = getattr(manager, "_runtime", None) is None and getattr(manager, "_server", None) is None
        (out / "local-release.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"owned_manager_released": True}), flush=True)


def server_checks(args, out):
    import requests
    session = requests.Session()
    session.trust_env = False
    base = f"http://127.0.0.1:{args.port}"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    for name in ("user", "input", "output", "temp"):
        (out / name).mkdir()
    command = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(args.port), "--disable-auto-launch",
        "--disable-all-custom-nodes", "--whitelist-custom-nodes", ROOT.name,
        "--user-directory", str(out / "user"), "--input-directory", str(out / "input"),
        "--output-directory", str(out / "output"), "--temp-directory", str(out / "temp")]
    if args.mode in ("queue", "ui"):
        command.append("--cpu")
    records = []
    def save():
        (out / "queue-results.json").write_text(json.dumps({"mode": args.mode, "cases": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            started = time.monotonic()
            while time.monotonic()-started < 150:
                if process.poll() is not None:
                    raise RuntimeError("Owned Comfy exited; inspect server.log")
                try:
                    response = session.get(base + "/object_info", timeout=2)
                    if response.status_code == 200:
                        info = response.json()
                        break
                except requests.RequestException:
                    pass
                time.sleep(.3)
            else:
                raise TimeoutError("Owned server startup unconfirmed")
            moss = "MOSSImagePromptEnhancerT8"
            assert moss in info
            (out / "moss-object-info.json").write_text(json.dumps(info[moss], ensure_ascii=False, indent=2), encoding="utf-8")
            if args.mode == "ui":
                from run_frontend_browser_tests import browser_path
                result = subprocess.run(["node", str(ROOT / "tools/frontend_browser_cdp.mjs"), browser_path(), base,
                    str(out / "moss-native-ui.png"), "comfy-moss"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=100)
                (out / "browser-result.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
                if result.returncode:
                    raise RuntimeError("Real MOSS frontend checks failed: " + result.stderr[-2500:])
                print(result.stdout, flush=True)
                return
            def defaults(name):
                result = {}
                for key, field in info[name]["input"]["required"].items():
                    settings = field[1] if len(field) > 1 and isinstance(field[1], dict) else {}
                    value = settings.get("default", field[0][0] if isinstance(field[0], list) else None)
                    if value is not None:
                        result[key] = value
                return result
            def queue(label, graph, *, success=True):
                response = session.post(base + "/prompt", json={"prompt": graph}, timeout=20)
                if response.status_code != 200:
                    raise RuntimeError(label + " rejected: " + response.text[:3000])
                pid = response.json()["prompt_id"]
                started = time.monotonic()
                while time.monotonic()-started < 1500:
                    result = session.get(base + "/history/" + pid, timeout=10).json().get(pid)
                    if result:
                        break
                    time.sleep(.3)
                else:
                    raise TimeoutError("Result unconfirmed; never automatically resubmit")
                (out / (label + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                records.append({"id": label, "status": result["status"]["status_str"], "seconds": round(time.monotonic()-started, 3)})
                save()
                print(json.dumps(records[-1]), flush=True)
                assert (records[-1]["status"] == "success") == success, label
                return result
            if args.mode == "queue":
                # These dependencies statically validate, but fail if actually run.
                poisoned = {**defaults("T8SpeechReference"), "mode": "Enabled", "source_mode": "AUDIO"}
                cfg = {**defaults("T8LLMProviderConfig"), "provider": "Strata", "strata_url": "not-a-url"}
                values = {**defaults(moss), "operation": "仅校验编译 / Compile only", "draft_json": ["3", 0],
                    "prompt": ["4", 1], "api_key": ["4", 1], "provider_config": ["5", 0], "recovery_slot": "t8-moss-queue-last-good"}
                graph = {"1": {"class_type": moss, "inputs": values},
                    "2": {"class_type": "T8ShowText", "inputs": {"text": ["1", 0]}},
                    "3": {"class_type": "T8PromptText", "inputs": {"text": '{"caption":"A quiet cup."}'}},
                    "4": {"class_type": "T8SpeechReference", "inputs": poisoned},
                    "5": {"class_type": "T8LLMProviderConfig", "inputs": cfg}}
                first = queue("compile-linked-skips-poisoned-dependencies", graph)
                assert first["outputs"]["2"]["text"] == ["A quiet cup."]
                draft = {"width": 768, "height": 512, "bbox_coord_space": "abs", "bbox_format": "xyxy",
                    "summary": {"caption": "A cup."}, "items": [{"label": "object", "caption": "One cup.", "bbox": [48, 48, 300, 448]}]}
                graph["3"]["inputs"]["text"] = json.dumps(draft)
                graph["6"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["1", 1], "height": ["1", 2], "batch_size": 1}}
                graph["7"] = {"class_type": "SaveLatent", "inputs": {"samples": ["6", 0], "filename_prefix": "moss-typed-canvas"}}
                first_layout = queue("compile-layout-typed-canvas-to-native-latent", graph)
                expected = first_layout["outputs"]["2"]["text"]
                draft["items"][0]["bbox"][2] = 9999
                graph["3"]["inputs"]["text"] = json.dumps(draft)
                queue("invalid-layout-blocks-downstream", graph, success=False)
                status = session.get(base + "/t8-prompt-enhancer/moss-image/status/t8-moss-queue-last-good", timeout=5).json()
                retained = session.get(base + "/t8-prompt-enhancer/moss-image/draft/t8-moss-queue-last-good", timeout=5).json()
                assert status["recoverable"] and status["failed_draft_available"] and not retained["verified"]
                values["recovery_action"] = "restore_last"
                restored = queue("restore-last-good-with-bad-draft-and-poisoned-dependencies", graph)
                assert restored["outputs"]["2"]["text"] == expected
                values["recovery_slot"] = "t8-moss-no-such-cache"
                missing = queue("missing-cache-not-inference", graph, success=False)
                assert "Connect only" not in json.dumps(missing["status"])
                # Real host graph + real loopback HTTP, but no model inference:
                # prove linked STRING, both images and inactive cloud-Key laziness.
                sys.path.insert(0, str(ROOT / "tests"))
                from test_strata_provider import http_fixture
                from PIL import Image
                for index, color in enumerate(("red", "blue")):
                    Image.new("RGB", (32, 32), color).save(out / "input" / f"reference-{index}.png")
                with http_fixture(response={"model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": '{"caption":"A red shape beside a blue shape."}'}}]}) as (url, calls):
                    generate = {**defaults(moss), "prompt": ["3", 0], "provider_config": ["5", 0], "api_key": ["4", 1],
                        "draft_json": ["4", 1], "reference_images.reference_image_0": ["8", 0], "reference_images.reference_image_1": ["9", 0]}
                    active = {"1": {"class_type": moss, "inputs": generate}, "2": graph["2"],
                        "3": {"class_type": "T8PromptText", "inputs": {"text": "Use both reference colors for two shapes."}},
                        "4": graph["4"], "5": {"class_type": "T8LLMProviderConfig", "inputs": {**defaults("T8LLMProviderConfig"), "provider": "Strata", "strata_url": url}},
                        "8": {"class_type": "LoadImage", "inputs": {"image": "reference-0.png"}},
                        "9": {"class_type": "LoadImage", "inputs": {"image": "reference-1.png"}},
                        "10": {"class_type": "T8ShowText", "inputs": {"text": ["1", 5]}}}
                    result = queue("linked-generation-two-images-inactive-key-not-run", active)
                    report = json.loads(result["outputs"]["10"]["text"][0])
                    assert len(report["image_map"]) == 2
                    posts = [row for row in calls if row[0] == "POST"]
                    assert len(posts) == 1
                    content = posts[0][3]["messages"][1]["content"]
                    assert sum(p.get("type") == "image_url" for p in content) == 2
                    # Unlike frontend Primitive folding, these INT links are
                    # real upstream nodes and unresolved at graph validation.
                    active["11"] = {"class_type": "GetImageSize", "inputs": {"image": ["8", 0]}}
                    generate["width"], generate["height"] = ["11", 0], ["11", 1]
                    sized = queue("linked-native-int-canvas-generation", active)
                    sized_report = json.loads(sized["outputs"]["10"]["text"][0])
                    assert sized_report["canvas"] == {"width": 32, "height": 32}
                    records[-1].update(image_count=2, model_inference=False, loopback_chat_posts=1)
                    save()
                    active["12"] = {"class_type": "ResolutionSelector", "inputs": {
                        "aspect_ratio": "3:4 (Portrait Standard)", "megapixels": 2.0, "multiple": 8}}
                    generate["width"], generate["height"] = ["12", 0], ["12", 1]
                    eight = queue("resolution-selector-eight-caption-generation", active)
                    eight_report = json.loads(eight["outputs"]["10"]["text"][0])
                    assert eight_report["canvas"] == {"width": 1256, "height": 1672}
                    assert "eight_pixel_canvas_downstream_unverified" in eight_report["warnings"]
                    eight_draft = {"width": 1256, "height": 1672, "bbox_coord_space": "abs", "bbox_format": "xyxy",
                        "summary": {"caption": "A full-frame shape."}, "items": [
                            {"label": "object", "caption": "One shape.", "bbox": [0, 0, 1256, 1672]}]}
                    eight_values = {**defaults(moss), "operation": "仅校验编译 / Compile only",
                        "draft_json": json.dumps(eight_draft), "recovery_slot": "t8-moss-eight-queue-cache"}
                    eight_graph = {"1": {"class_type": moss, "inputs": eight_values}, "2": graph["2"],
                        "6": graph["6"], "7": graph["7"], "10": active["10"]}
                    compiled = queue("eight-layout-real-canvas-and-native-latent", eight_graph)
                    centered = json.loads(compiled["outputs"]["2"]["text"][0])
                    assert centered["items"][0]["bbox"] == [-836, -628, 836, 628]
                    assert json.loads(compiled["outputs"]["10"]["text"][0])["canvas"] == {"width": 1256, "height": 1672}
                    from safetensors import safe_open
                    saved_latent = compiled["outputs"]["7"]["latents"][0]
                    latent_path = out / "output" / saved_latent["subfolder"] / saved_latent["filename"]
                    with safe_open(latent_path, framework="pt", device="cpu") as tensors:
                        shape = tensors.get_slice("latent_tensor").get_shape()
                    assert shape[-2:] == [104, 78]  # native Flux2 latent floors /16, node does not change input
                    records[-1].update(requested_canvas=[1256, 1672], native_latent_shape=shape,
                        native_latent_pixel_equivalent=[1248, 1664], model_inference=False)
                    eight_values["recovery_action"] = "restore_last"
                    eight_values["draft_json"] = "deliberately invalid; cache must skip it"
                    restored_eight = queue("eight-pixel-typed-recovery-to-native-latent", eight_graph)
                    assert restored_eight["outputs"]["2"]["text"] == compiled["outputs"]["2"]["text"]
                    eight_values["recovery_action"] = "normal"
                    eight_draft["items"][0]["bbox"][2] = 1257  # inside validation envelope, OUTSIDE real canvas
                    eight_values["draft_json"] = json.dumps(eight_draft)
                    queue("eight-layout-padding-stripe-is-still-rejected", eight_graph, success=False)
                    save()
            else:
                if not args.live_results:
                    raise ValueError("Render needs already completed --live-results (no new API)")
                data = json.loads(args.live_results.read_text(encoding="utf-8"))
                for label in ("minimal_caption", "chinese_poster"):
                    row = next(r for r in data["records"] if r["case"] == label and r["model"] == "qwen/qwen3.8-flash-next")
                    values = {**defaults(moss), "operation": "仅校验编译 / Compile only", "draft_json": json.dumps(row["draft"], ensure_ascii=False), "width": row["width"], "height": row["height"]}
                    graph = {"1": {"class_type": moss, "inputs": values},
                        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "moss_image_sft_int8_convrot.safetensors", "weight_dtype": "default"}},
                        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_int8_convrot.safetensors", "type": "moss_image", "device": "default"}},
                        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ["1", 0]}},
                        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ""}},
                        "6": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["1", 1], "height": ["1", 2], "batch_size": 1}},
                        "7": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
                            "seed": 176017, "steps": 50, "cfg": 3., "sampler_name": "euler", "scheduler": "normal", "denoise": 1.}},
                        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
                        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["8", 0]}},
                        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "moss-" + label}}}
                    queue("render-" + label, graph)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            session.close()
            (out / "owned-server-released.json").write_text(json.dumps({"pid": process.pid, "exited": process.poll() is not None}), encoding="utf-8")
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real", action="store_true", required=True)
    parser.add_argument("--mode", choices=("queue", "gguf", "render", "ui"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8197)
    parser.add_argument("--model", default="Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf")
    parser.add_argument("--live-results", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error("Evidence must be outside the repository")
    out.mkdir(parents=True, exist_ok=False)
    if args.mode == "gguf":
        local(out, args.model)
    else:
        server_checks(args, out)
