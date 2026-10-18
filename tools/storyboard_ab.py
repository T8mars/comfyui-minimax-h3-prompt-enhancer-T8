"""Offline experiment manifest and blinded review; never calls a model or scores quality."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "t8-storyboard-ab/v1"
CASES = (
    ("quiet", 60, 1, "固定单镜头，雨中空长椅，雨持续落下；没有人物、事件转折或新物件。", "静态价值与无人场景不得强加戏。"),
    ("handover", 60, 3, "三镜头：甲右手递信封给乙；乙右手接稳，甲松手；乙将信封放在桌上。只交接一次，无对白。", "同一交接可跨镜延续，但不能重复发生；接触和归属可读。"),
    ("reveal", 60, 3, "三镜头：观众看见甲藏起钥匙，乙背对甲不知情；乙转身后甲才展示钥匙；乙此时才看见并点头。", "观众知情不等于乙知情；开头和中间图不得提前泄露。"),
    ("dialogue", 60, 3, "甲说完整原句“等雨停了，我们再出发。”；镜头切到静听的乙，原句连续说完且只说一次；甲说完后两人静等十秒。", "跨镜不重复台词，不把听者变说者；保留十秒等待。"),
    ("product", 120, 3, "锁定三个镜头：瓶子正面静置；同一瓶子的侧面静置；同一瓶子背面静置。没有人和手，不加转动动作和冲突。", "完整产品分镜可保持原样，不为了强化增加镜头或人物。"),
    ("coordinates", 60, 2, "甲乙面对面坐着，各自握杯不换手。镜头一从桌南看，镜头二从桌北看，人物不移动，仍各持原杯。", "画面左右可反转，世界位置、身体手和持有者不能因此交换。"),
    ("long_take", 3600, 1, "目标3600秒，一镜到底，固定机位记录已有河流持续流动。无人物、无新事件、不变机位、不定格。", "不设上限、不截短、不自动拆段；镜数仍一。服务本身能力另评。"),
    ("moving_end", 60, 2, "两个镜头，成年骑行者沿直路持续向前；镜头二接续原速度，结尾仍在前进，不停下、不换人、不加入障碍。", "跨镜接续动量，结尾不擅自停顿；不得凭空生成参考素材。"),
)
HARD_GATES = ["原生格式与描述语言", "用户镜数/一镜到底/时长和首尾状态", "完整原话、说话者与等待",
              "源事件覆盖与无新增事件", "信息揭示顺序", "持有关系与跨镜连续性", "真实素材角色，不伪造观察"]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def plan(model, provider, repeats=1):
    if not model.strip() or not provider.strip() or not 1 <= repeats <= 20:
        raise ValueError("Specify a model/provider and 1..20 evaluation repeats (not a duration bound).")
    settings = {"model": model, "provider": provider, "seed": 0, "temperature": 0.7,
                "output_language": "中文", "director_skill": "none", "performance": "AUTO",
                "quality_mode": "off", "creation_mode": "off", "media_sha256": [], "method_revision": "1.0.0"}
    slots = []
    for target in ("h3", "seedance20"):
        for case_id, duration, shots, prompt, focus in CASES:
            for repeat in range(repeats):
                for on in (False, True):
                    slots.append({"id": f"{target}-{case_id}-{repeat}-{'on' if on else 'off'}",
                                  "target": target, "case_id": case_id, "repeat": repeat, "on": on,
                                  "input": {"prompt": prompt, "duration_seconds": duration, "shot_count": shots},
                                  "focus": focus})
    manifest = {"schema": SCHEMA, "settings": settings, "slots": slots,
                "limitations": "Text-only preregistration. No calls made. Counterbalance order externally; keep failures, retries, truncations and unknowns. No rendered-benefit claim."}
    observations = {"schema": SCHEMA, "manifest_sha256": digest(manifest), "records": [
        {"id": s["id"], "settings_sha256": digest(settings), "input_sha256": digest(s["input"]),
         "outcome": "pending", "output": "", "output_sha256": "", "logical_calls": 0, "http_attempts": 0,
         "elapsed_seconds": 0, "error_category": "", "usage": {"input_tokens": None, "output_tokens": None, "cost": None, "currency": ""}} for s in slots]}
    return manifest, observations


def blind(manifest, observations, *, rng=None):
    if manifest.get("schema") != SCHEMA or observations.get("schema") != SCHEMA or observations.get("manifest_sha256") != digest(manifest):
        raise ValueError("Manifest identity mismatch.")
    slots = manifest["slots"]
    if not slots:
        raise ValueError("Empty experiment: provide at least one complete Off/On pair.")
    expected = {s["id"]: s for s in slots}
    records = observations["records"]
    if len(expected) != len(slots) or len(records) != len(expected) or {r["id"] for r in records} != set(expected):
        raise ValueError("Missing/duplicate observations: failures must remain present.")
    pairs = {}
    for s in slots:
        if type(s["on"]) is not bool:
            raise ValueError("Invalid experimental arm.")
        pairs.setdefault((s["target"], s["case_id"], s["repeat"]), []).append(s)
    for pair in pairs.values():
        if len(pair) != 2 or sorted(s["on"] for s in pair) != [False, True] or pair[0]["input"] != pair[1]["input"]:
            raise ValueError("Unpaired or mismatched inputs.")
        if not isinstance(pair[0].get("focus"), str) or pair[0]["focus"] != pair[1].get("focus"):
            raise ValueError("Paired review focus must be identical text, without arm-specific guidance.")
    ordered = list(records)
    (rng or random.SystemRandom()).shuffle(ordered)
    candidates, mapping = [], []
    for index, record in enumerate(ordered):
        slot = expected[record["id"]]
        if record["settings_sha256"] != digest(manifest["settings"]) or record["input_sha256"] != digest(slot["input"]):
            raise ValueError("Input/settings changed; use a separately versioned experiment.")
        if record["outcome"] not in {"success", "failed", "interrupted", "truncated"}:
            raise ValueError("Unresolved pending slot; capture its outcome, do not silently drop it.")
        if not isinstance(record["output"], str) or digest(record["output"]) != record["output_sha256"]:
            raise ValueError("Output hash mismatch.")
        if record["outcome"] == "success" and not record["output"].strip():
            raise ValueError("Empty success is not a completed observation.")
        for key in ("logical_calls", "http_attempts", "elapsed_seconds"):
            value = record[key]
            allowed = (int, float) if key == "elapsed_seconds" else (int,)
            if type(value) not in allowed or not 0 <= value < float("inf"):
                raise ValueError("Invalid measurement.")
        usage = record.get("usage", {})
        if not isinstance(usage, dict):
            raise ValueError("Usage must be an object; unknown measurements are null fields.")
        finite_usage = {}
        for key in ("input_tokens", "output_tokens", "cost"):
            value = usage.get(key)
            allowed = (int, float) if key == "cost" else (int,)
            if value is not None and (type(value) not in allowed or not 0 <= value < float("inf")):
                raise ValueError("Invalid usage; missing measurements must remain null, not zero.")
            finite_usage[key] = value
        currency = usage.get("currency", "")
        if not isinstance(currency, str) or (currency and (len(currency) != 3 or not currency.isascii() or not currency.isalpha())):
            raise ValueError("Use an empty or three-letter currency code.")
        finite_usage["currency"] = currency
        candidate_id = f"C{index + 1:04}"
        candidates.append({"id": candidate_id, "target": slot["target"], "input": slot["input"],
                           "focus": slot["focus"], "outcome": record["outcome"], "output": record["output"]})
        mapping.append({"id": candidate_id, "slot_id": slot["id"], "on": slot["on"], "usage": finite_usage,
                        **{k: record[k] for k in ("output_sha256", "logical_calls", "http_attempts", "elapsed_seconds", "error_category")}})
    return {"schema": "t8-storyboard-blind/v1", "candidates": candidates,
            "rubric": {"hard_gates": HARD_GATES, "ratings": "pass / fail / unknown, with exact output evidence",
                       "dimensions": ["镜头信息效率", "动作与接触可读性", "连续性", "简洁可执行性"],
                       "rule": "Seal judgments before decoding. Hard violations cannot be offset by style points. Length, keywords and shot count are not quality. Failures count; unknown physical feasibility stays unknown."}}, {
                "schema": "t8-storyboard-mapping/v1", "manifest_sha256": digest(manifest),
                "observations_sha256": digest(observations), "mapping": mapping}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("plan")
    create.add_argument("--model", required=True); create.add_argument("--provider", required=True)
    create.add_argument("--repeats", type=int, default=1)
    review = sub.add_parser("blind")
    review.add_argument("--manifest", type=Path, required=True); review.add_argument("--observations", type=Path, required=True)
    for command in (create, review):
        command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents or destination.exists():
        parser.error("Use a new directory outside the repository; evidence is never overwritten.")
    if args.command == "plan":
        values = plan(args.model, args.provider, args.repeats)
        names = ("manifest.json", "observations.json")
    else:
        values = blind(json.loads(args.manifest.read_text(encoding="utf-8")), json.loads(args.observations.read_text(encoding="utf-8")))
        names = ("blind-candidates.json", "private-mapping.json")
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in zip(names, values):
        (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Offline files prepared. No network, model generation or quality scoring; keep mapping from reviewers.")


if __name__ == "__main__":
    main()
