"""Offline replay of captured MOSS drafts; never calls an LLM or claims semantic quality."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import moss_image_contract as c

LOCKS = {"chinese_poster": ["把日常，过成诗。", '一杯温暖\n"MOSS" 🪴'], "multi_panel_copy": ["播种", "发芽", "开花"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target == ROOT or ROOT in target.parents or target.exists():
        parser.error("Select a new evidence file outside the repository")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows, groups = [], {}
    for row in data["records"]:
        if row["hard_contract"] != "passed":
            rows.append({"case": row["case"], "model": row["model"], "replayed": False})
            continue
        compiled = c.compile_draft(c.strict_json(json.dumps(row["draft"], ensure_ascii=False)), output_format=row["format"],
            width=row["width"], height=row["height"], locked_text=json.dumps(LOCKS[row["case"]], ensure_ascii=False) if row["case"] in LOCKS else "")
        assert compiled[:4] == (row["prompt"], row["width"], row["height"], row["format"])
        assert c.strict_json(compiled[4]) == row["draft"]
        groups.setdefault(row["model"], []).append(row["seconds"])
        rows.append({"case": row["case"], "model": row["model"], "replayed": True,
                     "prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest()})
    result = {"source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(), "network_calls": 0,
        "semantic_or_render_quality_assessed": False, "rows": rows,
        "timing": {model: {"count": len(times), "mean_s": round(statistics.mean(times), 3), "median_s": round(statistics.median(times), 3)} for model, times in groups.items()},
        "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                        ("moss_image.py", "moss_image_contract.py", "moss_image_state.py", "moss_image_routes.py", "web/js/moss_image_ui.mjs", "web/js/moss_image_prompt_enhancer.js")}}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"replayed": sum(r["replayed"] for r in rows), "network_calls": 0, "source_sha256": result["source_sha256"], "timing": result["timing"]}))


if __name__ == "__main__":
    main()
