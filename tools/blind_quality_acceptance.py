"""Prepare deidentified text-only creative assessments from saved API evidence.

No network, model, scoring LLM or re-generation. Reviewers receive only
blind-candidates.json; blind-mapping.json is for decoding AFTER scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def prepare(source: dict) -> tuple[dict, dict]:
    candidates, mapping = [], []
    for record in source["tests"]:
        if record.get("outcome") != "success":
            raise ValueError("A failed test cannot be silently excluded from blind review.")
        prompt = record["output"]
        output_sha = hashlib.sha256(json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if record["output_sha256"] != output_sha:
            raise ValueError("Saved output hash mismatch.")
        identity = json.dumps([record["case_id"], record["repeat"], record["on"], output_sha])
        candidate_id = hashlib.sha256(identity.encode()).hexdigest()[:16]
        case = record["input"]
        candidates.append({"candidate_id": candidate_id,
                           "request": {k: case[k] for k in ("task", "seconds", "shots", "prompt")},
                           "prompt": prompt})
        mapping.append({"candidate_id": candidate_id, "case_id": record["case_id"],
                        "repeat": record["repeat"], "on": record["on"], "output_sha256": output_sha})
    candidates.sort(key=lambda c: c["candidate_id"])
    if len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("Duplicate blinded identity.")
    rubric = {
        "scope": "Exploratory text-only review. No generated video or physical-quality claim.",
        "hard_gates": ["native task protocol and real shots/time", "effective descriptive language",
                       "exact speech/visible words and silent actors", "source ownership and no invented entities",
                       "explicit waits and requested moving end state"],
        "dimensions_out_of_20": ["causal action/reception/change", "continuity and inherited state",
                                 "readability and executability", "shot information effectiveness", "economy"],
        "requirement": "For every gate/dimension cite exact output fragments. Use pass/fail/unknown; hard failure cannot be offset by score. Unknown physical feasibility stays unknown. Do not infer group, model or mode. Seal scores before decoding. Small paired differences do not prove stable gains.",
    }
    return {"schema": "t8-blind-text-review/v1", "rubric": rubric, "candidates": candidates}, {
        "schema": "t8-blind-mapping/v1", "source_sha256": source["source_sha256"], "mapping": mapping}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=12)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = args.output_dir.resolve()
    if destination == root or root in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    source_bytes = args.source.read_bytes()
    blind, mapping = prepare(json.loads(source_bytes))
    if len(blind["candidates"]) != args.expected_count:
        raise SystemExit("Incomplete experiment; do not silently score a partial batch.")
    pairs = {}
    for record in mapping["mapping"]:
        pairs.setdefault((record["case_id"], record["repeat"]), []).append(record["on"])
    if any(sorted(arms) != [False, True] for arms in pairs.values()):
        raise SystemExit("Missing or duplicate experimental arm.")
    mapping["source_file_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    if any((destination / name).exists() for name in ("blind-candidates.json", "blind-mapping.json")):
        raise SystemExit("Do not overwrite a sealed blind assessment.")
    for name, value in (("blind-candidates.json", blind), ("blind-mapping.json", mapping)):
        target = destination / name
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(blind['candidates'])} blinded outputs; mapping separate. No model/network/scoring.")


if __name__ == "__main__":
    main()
