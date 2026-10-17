"""Opt-in real MOSS *prompt* acceptance. No rendering, weights, keys or source uploads saved."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import importlib.util
import json
import re
from pathlib import Path
import sys
import time
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def load_node():
    sys.path.insert(0, str(ROOT.parents[1]))
    sys.argv = ["moss-live", "--cpu"]
    spec = importlib.util.spec_from_file_location("t8_moss_live", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    return sys.modules[spec.name + ".moss_image"]


def cases(module):
    import numpy as np
    from PIL import Image, ImageDraw
    one = Image.new("RGB", (384, 384), "white")
    ImageDraw.Draw(one).polygon([(192, 48), (55, 325), (329, 325)], fill=(210, 35, 35))
    two = Image.new("RGB", (384, 384), (248, 232, 174))
    draw = ImageDraw.Draw(two)
    for x in range(0, 384, 32): draw.line([(x, 0), (x, 384)], fill=(36, 95, 75), width=8)
    images = {"reference_image_0": np.asarray(one, dtype=np.float32)[None] / 255.,
              "reference_image_1": np.asarray(two, dtype=np.float32)[None] / 255.}
    c = module.contract
    return [
        {"id": "minimal_caption", "prompt": "A minimalist studio photograph of exactly one unbranded ivory ceramic cup on a pale grey table, soft side light, no typography, no decorative props. Keep it restrained.", "output_format": c.CAPTION},
        {"id": "complex_auto_not_poster", "prompt": "A natural documentary photograph of two adult botanists comparing leaves in a greenhouse after rain. One holds a notebook and the other a leaf, with coherent depth and soft overcast light. No titles or infographic panels.", "output_format": c.AUTO},
        {"id": "chinese_poster", "prompt": "设计一张陶瓷杯海报：杯子在左，右侧标题与副文案分开排版，米白与墨绿，留白清晰。严格使用锁定的两块文案，不添加其他文字。", "output_format": c.LAYOUT,
         "width": 1536, "height": 1024, "locked_text": json.dumps(["把日常，过成诗。", '一杯温暖\n"MOSS" 🪴'], ensure_ascii=False)},
        {"id": "two_subjects_spatial", "prompt": "Two different unbranded toy robots: one red robot on the left nearer the camera, one blue robot on the right farther away. A low wooden fence crosses the foreground, partially occluding their feet only. Exactly two robots, no visible writing.", "output_format": c.LAYOUT},
        {"id": "multi_panel_copy", "prompt": "A three-panel editorial illustration, left to right: one seed in soil, a seedling, then a small potted flowering plant. Each panel has its own locked Chinese heading, with no extra copy. Flat clean illustration, warm cream background.", "output_format": c.LAYOUT,
         "width": 1536, "height": 768, "locked_text": json.dumps(["播种", "发芽", "开花"], ensure_ascii=False)},
        {"id": "two_reference_roles", "prompt": "Describe an original poster whose central subject follows ONLY the shape and color observed in Reference 1. Use Reference 2 only for its background colors and stripe treatment, not as an extra object. Do not invent visible text. Describe both observed references accurately; do not turn this into a native image-edit request.",
         "output_format": c.LAYOUT, "reference_images": images},
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real", action="store_true")
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--control-model", default="")
    parser.add_argument("--candidate-model", default="qwen/qwen3.8-flash-next")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.confirm_real:
        parser.error("Use --confirm-real only with user authorization.")
    if not args.models_only and (not args.output or not args.control_model):
        parser.error("--control-model and external --output are required.")
    if args.output:
        output = args.output.resolve()
        if output == ROOT or ROOT in output.parents or output.exists():
            parser.error("Use a new evidence directory outside the repository.")
    key = getpass.getpass("Test Key (not saved): ")
    if not key:
        parser.error("No Key supplied.")
    module = load_node()
    if args.models_only:
        import requests
        _, chat, _, _ = module._provider_config(module.SEEDANCE_API_MODE, key, "")
        parts = urlsplit(chat)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path.rsplit("/", 2)[0] + "/models", "", ""))
        with requests.Session() as session:
            response = session.get(url, headers={"Authorization": "Bearer " + key, "Cache-Control": "no-cache"}, timeout=(20, 45))
            print(json.dumps({"status": response.status_code, "model_ids": [r.get("id") for r in response.json().get("data", [])
                if isinstance(r, dict) and any(term in str(r.get("id", "")).lower() for term in ("qwen", "gemini", "gpt-6"))][:80]}, ensure_ascii=False), flush=True)
        return
    output.mkdir(parents=True)
    counters = {"initial": 0, "repair": 0, "chat_attempts": 0}
    original = module._CloudCompletion.__call__
    def bounded(transport, messages, repair):
        key_name = "repair" if repair else "initial"
        if counters[key_name] >= (6 if repair else 12):
            raise module.MossImageError("Authorized acceptance-call budget exhausted.")
        counters[key_name] += 1
        counters["chat_attempts"] += 1
        return original(transport, messages, repair)
    records = []
    with patch.object(module._CloudCompletion, "__call__", bounded):
        for model in (args.candidate_model, args.control_model):
            for case in cases(module):
                values = dict(case)
                identity = values.pop("id")
                started = time.monotonic()
                try:
                    result = module.MOSSImagePromptEnhancer.execute(**values, custom_model=model, api_key=key,
                        max_corrections=1 if counters["repair"] < 6 else 0, recovery_slot="t8-moss-live-" + identity)
                    values_out = result.result
                    report = json.loads(values_out[5])
                    record = {"case": identity, "model": model, "hard_contract": "passed", "seconds": round(time.monotonic() - started, 3),
                              "prompt": values_out[0], "width": values_out[1], "height": values_out[2], "format": values_out[3],
                              "draft": json.loads(values_out[4]), "report": report, "human_semantics_review": "pending"}
                except Exception as error:
                    # Never persist HTTP bodies, Key, request headers or media.
                    cause = error.__cause__
                    http = re.search(r"\b(?:HTTP\s*)?(401|403|404|429|500|502|503)\b", str(error))
                    code = cause.code if isinstance(cause, module.contract.MossContractError) else "http_" + http.group(1) if http else type(error).__name__
                    record = {"case": identity, "model": model, "hard_contract": "failed", "error_type": type(error).__name__,
                              "error_code": code,
                              "seconds": round(time.monotonic() - started, 3)}
                records.append(record)
                (output / "results.json").write_text(json.dumps({"records": records, "call_budget": counters}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({k: record[k] for k in ("case", "model", "hard_contract", "seconds")}, ensure_ascii=False), flush=True)
                if record.get("error_code") in ("http_401", "http_403"):
                    raise SystemExit("Authentication failed. Stopped without retrying other cases.")
    print(json.dumps({"done": True, "case_results": len(records), "passed": sum(r["hard_contract"] == "passed" for r in records), "calls": counters}), flush=True)


if __name__ == "__main__":
    main()
