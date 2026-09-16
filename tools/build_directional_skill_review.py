"""Create blinded text-review evidence outside the repository; never call an LLM."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="Pair new on-only results with matching saved off results; no new calls.")
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise SystemExit("Review evidence must be outside the repository.")
    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in snapshot["cases"]}
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        prior_cases = {case["id"]: case for case in baseline["cases"]}
        for case_id, case in cases.items():
            if prior_cases.get(case_id) != case:
                raise SystemExit("Baseline facts differ; do not pair unrelated inputs.")
        wanted = {(record["target"], record["case_id"], record["repeat"]) for record in snapshot["tests"]}
        prior = [record for record in baseline["tests"] if record["director_skill"] == "none"
                 and (record["target"], record["case_id"], record["repeat"]) in wanted]
        snapshot["tests"] = prior + [record for record in snapshot["tests"] if record["director_skill"] != "none"]
    groups, mapping = {}, {}
    for record in snapshot["tests"]:
        if record["outcome"] != "success":
            continue
        group = f'{record["target"]}/{record["case_id"]}/{record["repeat"]}'
        identifier = hashlib.sha256((group + record["output"]).encode("utf-8")).hexdigest()[:16]
        item = groups.setdefault(group, {"target": record["target"], "case_id": record["case_id"],
            "repeat": record["repeat"], "input": cases[record["case_id"]]["prompt"], "candidates": []})
        item["candidates"].append({"candidate_id": identifier, "output": record["output"]})
        mapping[identifier] = {key: record[key] for key in ("target", "case_id", "repeat", "director_skill")}
    for group in groups.values():
        group["candidates"].sort(key=lambda item: item["candidate_id"])
    bundle = {"rubric": {"causal_action": 25, "state_continuity": 25,
        "readability": 20, "scene_direction": 20, "economy": 10},
        "gates": "Check native format, selected Chinese language, fixed count/duration, exact dialogue, actor/weapon/ability ownership and requested end state. A gate failure cannot be compensated by points.",
        "limitations": "Exploratory human/agent text review, not video quality or statistical significance. Candidates omit provider, condition, latency and request metadata.",
        "groups": [group for group in groups.values() if len(group["candidates"]) == 2]}
    directory.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    (directory / f"{stem}-blind.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / f"{stem}-mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Blinded complete pairs: {len(bundle['groups'])}; condition mapping kept in a separate file.")


if __name__ == "__main__":
    main()
