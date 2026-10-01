"""Opt-in, serial live Qwen Classic/Edit-aware acceptance. Never stores keys.

Calls the production node, real image uploads and real chat transport. Observers
record only safe request metadata; they do not substitute any API response.
Evidence must be outside the repository. No local inference models are loaded.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1]))
import comfy.cli_args
comfy.cli_args.args.cpu = True
from tools.directional_skill_acceptance import load_package, digest
from tools.h3_quality_acceptance import response_metrics


CASES = [
    dict(id="wall_zh", images=["portrait"], prompt="仅将照片背景替换成安静的浅灰色摄影棚墙面。原图人物的身份、面部、发型、衣服、姿势、表情、饰品和构图完全不变，不添加物体。", expected_follow=1),
    dict(id="wall_en", images=["portrait"], prompt="Only replace the photo background with a quiet light-gray studio wall. Keep the original person's identity, face, hair, clothes, pose, expression, accessories and framing unchanged. Add nothing else.", expected_follow=1),
    dict(id="sign_open", images=["sign"], prompt='仅将照片招牌上的文字改为 "OPEN"，保持原有字体风格、招牌位置、底色及其他内容不变。', expected_follow=1, literal="OPEN"),
    dict(id="chinese_lettering", images=["sign"], prompt='Only change the sign lettering to "你好世界". Keep the sign position, original styling, background and all other contents unchanged. Do not add an English translation.', expected_follow=1, literal="你好世界"),
    dict(id="person_scene", images=["portrait", "scene"], prompt="把图1的人物放进图2的公园场景，使用图2作为原始画布并保持构图。保留图1人物身份、外貌和衣服，人物站在图2小路中部，调整接触阴影和光照以融合，不新增人物或物体。", expected_follow=2),
    dict(id="clothes_canvas", images=["clothes", "portrait"], prompt="图2是目标照片和画布，只把图2人物上衣替换成图1的红色外套款式。保持图2人物面部、发型、身体、姿势、背景、饰品和构图不变；图1不提供人物身份或背景。", expected_follow=2),
    dict(id="style_canvas", images=["style", "sign"], prompt="以图2为目标画布，只应用图1的蓝黄平面插画配色与质感。保持图2招牌内容、位置、文字、物体数量和构图，不添加图1的图形元素，不使用图1的画幅。", expected_follow=2),
    dict(id="ten_sources", images=["portrait", *[f"unused{i}" for i in range(2, 10)], "scene"], prompt="仅把图1的人物放入图10的公园小路中部，图10作为目标画布并保持构图。保留图1人物身份和衣服；图2至图9是无关测试图，不参与本次修改，不生成它们的物体或文字，不新增人物。", expected_follow=10),
    dict(id="fixed_ratio", images=["sign"], prompt="只把招牌底色换成浅蓝色，保留原文字和其他元素。目标比例：16:9。", wh_ratio="3:4", expected_ratio="3:4"),
    dict(id="dimensions_literal", images=["sign"], prompt='输出尺寸：1024x1536。将招牌文字改成 "1:1"，其余内容不变，扩展背景以适应新画布，不裁切招牌。', expected_ratio="2:3", literal="1:1"),
    dict(id="outpaint", images=["portrait"], prompt="以原照片为画布向左右扩展背景，使总宽度约增加一倍，高度不变。原图人物位置、大小、面部、发型、衣服与所有原始内容不变，只延展原有背景，不裁切、不拉伸，不生成新的人物或物体。", expected_changed_canvas=True),
    dict(id="alpha_short", images=["portrait"], prompt="提取原图人物，保留人物面部、发型、衣服、饰品与姿势，去掉背景，生成透明背景的RGBA图像，具有alpha通道，不添加新物体。", transparent_alpha=True, max_output_chars=60, expected_follow=1),
]


def fixtures(destination, portrait_path):
    from PIL import Image, ImageDraw
    import numpy as np
    import torch
    tensors, manifest = {}, {}

    def add(name, image, path, source):
        tensors[name] = torch.from_numpy(np.array(image.convert("RGB"), dtype=np.float32) / 255).unsqueeze(0)
        manifest[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "width": image.width, "height": image.height, "source": source}

    with Image.open(portrait_path) as image:
        add("portrait", image, portrait_path, "existing user reference; unchanged pixels")
    for name, dimensions in [("sign", (640, 400)), ("scene", (960, 540)),
                             ("clothes", (512, 768)), ("style", (640, 640)),
                             *[(f"unused{i}", (200 + i * 8, 160 + i * 4)) for i in range(2, 10)]]:
        image = Image.new("RGB", dimensions, (238, 236, 224))
        draw = ImageDraw.Draw(image)
        width, height = dimensions
        if name == "sign":
            draw.rectangle((80, 85, 560, 315), fill=(55, 83, 78), outline=(25, 30, 30), width=8)
            draw.text((175, 145), "CAFE", fill="white", font_size=100)
        elif name == "scene":
            draw.rectangle((0, 0, width, 290), fill=(163, 211, 235))
            draw.rectangle((0, 291, width, height), fill=(112, 159, 89))
            draw.polygon(((410, 290), (550, 290), (850, 540), (100, 540)), fill=(199, 183, 151))
            for x in (100, 850):
                draw.rectangle((x - 12, 175, x + 12, 340), fill=(108, 76, 51))
                draw.ellipse((x - 65, 95, x + 65, 235), fill=(65, 120, 77))
        elif name == "clothes":
            draw.polygon(((180, 130), (240, 155), (270, 130), (385, 230), (355, 355), (305, 300),
                          (320, 620), (145, 620), (155, 300), (105, 355), (75, 230)), fill=(177, 43, 40))
            draw.line((240, 155, 235, 615), fill=(36, 35, 35), width=7)
        elif name == "style":
            draw.rectangle((0, 0, width, height), fill=(19, 61, 120))
            draw.ellipse((90, 60, 455, 425), fill=(249, 205, 52))
            draw.polygon(((55, 560), (295, 230), (590, 560)), fill=(88, 170, 212))
        else:
            index = int(name.replace("unused", ""))
            draw.rectangle((20, 20, width - 20, height - 20), fill=(20 * index, 190 - 10 * index, 120))
            draw.text((40, 50), f"UNUSED {index}", fill="white", font_size=22)
        path = destination / f"reference-{name}.png"
        image.save(path)
        add(name, image, path, "synthetic test fixture, generated once and shared by both arms")
        image.close()
    return tensors, manifest


def safe_messages(messages):
    # Never persist signed upload URLs or private request headers.
    rows = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "system":
            content = {"sha256": digest(content), "characters": len(str(content))}
        elif isinstance(content, list):
            content = [{"type": p.get("type"), **({"text": p.get("text", "")} if p.get("type") == "text" else {})}
                       for p in content]
        rows.append({"role": message.get("role"), "content": content})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--portrait", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=[c["id"] for c in CASES])
    parser.add_argument("--tag", default="initial")
    parser.add_argument("--completed-from", action="append", default=[],
                        help="Reuse completed arms from a same-contract evidence tag; never retry a completed paid arm.")
    parser.add_argument("--reuse-uploads", action="store_true",
                        help="Test-process-only reuse of real upload URLs; one bounded retry of an upload connection failure.")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("tag must be a filename token")
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / f"{args.tag}.json"
    if output_path.exists():
        raise SystemExit("Prior observations are immutable; use another tag.")
    key = getpass.getpass("API key (hidden; memory only): ")
    if not key:
        raise SystemExit("Missing key.")
    h3, _, _ = load_package()
    qwen = sys.modules[h3.__package__ + ".qwen_image21"]
    provider = sys.modules[h3.__package__ + ".provider_config"]
    config = provider.build_provider_config(provider=provider.PROVIDER_SEEDANCE,
                                           extra_parameters_json='{"max_tokens":8192}')
    tensors, assets = fixtures(destination, args.portrait.resolve())
    cases = [c for c in CASES if not args.case or c["id"] in args.case]
    evidence = {"schema": "t8-qwen-edit-real-ab/v1", "date": "2026-10-01", "tag": args.tag,
                "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                                  ("qwen_image21.py", "qwen_image21_edit.py", "resources/qwen-image-edit-t8.md", "tools/qwen_edit_live_ab.py")},
                "provider": "贞贞平价小屋", "endpoint": h3.CHAT_COMPLETIONS_URL, "model": qwen.QWEN_IMAGE_MODEL_ID,
                "scope": "Real image uploads and prompt enhancement, no image generation; one exploratory sample per arm.",
                "request_options": config["provider_request_options"], "assets": assets,
                "planned_cases": cases, "tests": [], "prior_observations": [],
                "reuse_uploads": args.reuse_uploads}
    completed = {}
    for tag in args.completed_from:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", tag):
            raise SystemExit("Prior tag must be a filename token.")
        prior_path = destination / f"{tag}.json"
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        for field in ("provider", "endpoint", "model", "request_options", "assets"):
            if prior.get(field) != evidence[field]:
                raise SystemExit("Prior assets or request settings differ; cannot combine observations.")
        for name, fingerprint in evidence["source_sha256"].items():
            if not name.startswith("tools/") and prior.get("source_sha256", {}).get(name) != fingerprint:
                raise SystemExit("Prior runtime contract differs; cannot combine observations.")
        evidence["prior_observations"].append({"tag": tag, "sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                                               "failed_arms": sum(r.get("outcome") != "success" for r in prior["tests"])})
        prior_cases = {c["id"]: c for c in prior["planned_cases"]}
        for row in prior["tests"]:
            case = next((c for c in cases if c["id"] == row["case_id"]), None)
            if case and prior_cases.get(case["id"]) != case:
                raise SystemExit("Prior brief or input settings differ; cannot combine observations.")
            if case and row.get("outcome") == "success":
                completed[(row["case_id"], row["arm"])] = {**row, "reused_from": tag}
    calls, posts, upload_events = [], [], []
    upload_cache = {}
    original_request, original_post = qwen._request_completion, qwen.requests.Session.post
    original_upload = h3._upload_media

    def observed_upload(session, credential, data, filename, mime_type, *values, **kwargs):
        fingerprint = hashlib.sha256(data).hexdigest()
        cache_key = (fingerprint, mime_type)
        if args.reuse_uploads and cache_key in upload_cache:
            upload_events.append({"sha256": fingerprint, "bytes": len(data), "cache_hit": True})
            return upload_cache[cache_key]
        for attempt in range(1, 3 if args.reuse_uploads else 2):
            event = {"sha256": fingerprint, "bytes": len(data), "cache_hit": False, "attempt": attempt}
            upload_events.append(event)
            try:
                url = original_upload(session, credential, data, filename, mime_type, *values, **kwargs)
                if args.reuse_uploads:
                    upload_cache[cache_key] = url  # Memory only; never persisted.
                return url
            except h3.PromptEnhancerError as error:
                cause = error.__cause__
                event["error_type"] = type(cause or error).__name__
                if not (args.reuse_uploads and attempt == 1 and isinstance(cause, h3.requests.exceptions.ConnectionError)):
                    raise

    def observed_request(*values, **kwargs):
        row = {"messages": safe_messages(values[2]), "http_attempts": []}
        calls.append(row)
        started = time.monotonic()
        try:
            result = original_request(*values, **kwargs)
            row.update(output=result, output_sha256=digest(result))
            return result
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise
        finally:
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)

    def observed_post(session, *values, **kwargs):
        url = str(values[0] if values else kwargs.get("url", ""))
        payload = kwargs.get("json", {})
        row = {"kind": "chat" if url.endswith("/chat/completions") else "upload",
               "parameters": {k: payload[k] for k in ("model", "stream", "temperature", "seed", "max_tokens") if k in payload}}
        posts.append(row)
        if row["kind"] == "chat" and calls:
            calls[-1]["http_attempts"].append(row)
            row["image_parts"] = sum(p.get("type") == "image_url" for m in payload.get("messages", [])
                                     for p in m.get("content", []) if isinstance(m.get("content"), list))
        try:
            response = original_post(session, *values, **kwargs)
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise
        row["status"] = response.status_code
        if "json" in response.headers.get("Content-Type", "").lower():
            try:
                response_metrics(response.json(), row)
            except ValueError:
                pass
        if kwargs.get("stream"):
            original_lines = response.iter_lines
            def lines(*args, **options):
                for raw in original_lines(*args, **options):
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    if line.strip().startswith("data:"):
                        try:
                            response_metrics(json.loads(line.strip()[5:].strip()), row)
                        except ValueError:
                            pass
                    yield raw
            response.iter_lines = lines
        return response

    def save():
        serialized = json.dumps(evidence, ensure_ascii=False, indent=2)
        if key in serialized or re.search(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}", serialized):
            raise SystemExit("Secret scan rejected evidence.")
        output_path.write_text(serialized, encoding="utf-8")

    try:
        with patch.object(qwen, "_request_completion", observed_request), patch.object(qwen.requests.Session, "post", observed_post), \
                patch.object(h3, "_upload_media", observed_upload):
            for index, case in enumerate(cases):
                arms = ["classic", "edit"]
                random.Random(2026100101 + index).shuffle(arms)
                for arm in arms:
                    if (case["id"], arm) in completed:
                        evidence["tests"].append(completed[(case["id"], arm)])
                        save()
                        print(json.dumps({"case": case["id"], "arm": arm, "reused_from": completed[(case["id"], arm)]["reused_from"]}), flush=True)
                        continue
                    calls.clear(); posts.clear(); upload_events.clear()
                    slot = f"qwen-edit-live-{args.tag}-{case['id']}-{arm}"
                    profile = qwen.edit.LEGACY_PROFILE if arm == "classic" else qwen.edit.EDIT_PROFILE
                    row = {"case_id": case["id"], "arm": arm}
                    started = time.monotonic()
                    try:
                        result = qwen.QwenImage21PromptEnhancer.execute(
                            prompt=case["prompt"], input_mode=qwen.INPUT_MODE_EDIT, api_key=key,
                            reference_images={f"reference_image_{i}": tensors[name] for i, name in enumerate(case["images"])},
                            rewrite_profile=profile, provider_config=config, recovery_slot=slot,
                            wh_ratio=case.get("wh_ratio", "auto"), max_output_chars=case.get("max_output_chars", 0),
                            transparent_alpha=case.get("transparent_alpha", False),
                        )
                        values = tuple(result)
                        row.update(outcome="success", rewritten_prompt=values[0], wh_ratio=values[1],
                                   request=json.loads(values[2]), report=json.loads(values[3]))
                        post_count = len(posts)
                        recovered = qwen.QwenImage21PromptEnhancer.execute(
                            recovery_action=qwen.RECOVERY_ACTION_RESTORE, recovery_slot=slot)
                        row["recovery_exact_no_http"] = tuple(recovered) == values and len(posts) == post_count
                    except Exception as error:
                        row.update(outcome="failed", error_type=type(error).__name__)
                        chain = error
                        row["error_chain"] = []
                        for _ in range(6):
                            if chain is None:
                                break
                            row["error_chain"].append(type(chain).__name__)
                            chain = chain.__cause__ or chain.__context__
                        status = re.search(r"\bstatus=(\d+)\b", str(error))
                        if status:
                            row["error_status"] = int(status.group(1))
                    row.update(elapsed_seconds=round(time.monotonic() - started, 3), calls=list(calls), posts=list(posts),
                               upload_events=list(upload_events))
                    evidence["tests"].append(row)
                    save()
                    print(json.dumps({"case": case["id"], "arm": arm, "outcome": row["outcome"],
                                      "seconds": row["elapsed_seconds"], "calls": len(calls),
                                      "http": [p.get("status") for p in posts], "ratio": row.get("wh_ratio"),
                                      "structured": row.get("report", {}).get("structured_response"),
                                      "chars": len(row.get("rewritten_prompt", "")),
                                      "repair_failed": row.get("report", {}).get("repair_failed", False)}, ensure_ascii=False), flush=True)
                    if row["outcome"] != "success":
                        raise SystemExit("Stopped on real failure; observations preserved, no blind paid retry.")
    finally:
        key = ""
        tensors.clear()
        upload_cache.clear()


if __name__ == "__main__":
    main()
