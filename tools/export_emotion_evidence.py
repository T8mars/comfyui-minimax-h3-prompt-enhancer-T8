"""Offline allowlisted export of synthetic API observations; no regeneration."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def sanitized(source, expected):
    records = source.get("tests", [])
    if len(records) != expected:
        raise ValueError("Incomplete observations; do not silently omit failed slots.")
    identities = [(t["case_id"], t["repeat"], t["arm"]) for t in records]
    if len(set(identities)) != expected:
        raise ValueError("Duplicate observation identity.")
    results = []
    for record in records:
        if record.get("output") and digest(record["output"]) != record.get("output_sha256"):
            raise ValueError("Output hash mismatch.")
        item = {k: record[k] for k in ("case_id", "repeat", "arm", "outcome", "output", "output_sha256", "logical_calls", "elapsed_seconds", "error_type", "error_status", "evaluator_note", "contract_check", "quality_events") if k in record}
        item["requests"] = []
        for call in record.get("calls", []):
            request = {k: call[k] for k in ("message_sha256", "model_id", "elapsed_seconds", "output", "output_sha256", "error_type") if k in call}
            request["http_attempts"] = [{k: attempt[k] for k in ("parameters", "request_parameters", "status", "usage", "response_model", "finish_reason", "error_type") if k in attempt} for attempt in call.get("http_attempts", [])]
            item["requests"].append(request)
        results.append(item)
    document = {"schema": "t8-emotion-synthetic-evidence/v1", "settings": source["settings"], "cases": source["cases"], "tests": results,
                "limitations": "Synthetic text-only prompts. Output completion is not a hard-contract pass. Unknown rendered quality, real-image behavior and local-9B compliance. Failures retained; no keys, headers, server IDs, reasoning or original message bundles exported."}
    if re.search(r"\bsk-[A-Za-z0-9_-]{16,}\b", json.dumps(document, ensure_ascii=False)):
        raise ValueError("Secret pattern in export; do not write.")
    return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path)
    parser.add_argument("--followup", type=Path)
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--single", type=Path, help="A separate bounded follow-up; never replace historical observations.")
    parser.add_argument("--expected-slots", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Do not overwrite evidence.")
    if args.single:
        if any((args.base, args.followup, args.quality)) or not args.expected_slots or args.expected_slots < 1:
            parser.error("Single export requires --expected-slots and no multiphase inputs.")
        raw = args.single.read_bytes()
        evidence = sanitized(json.loads(raw), args.expected_slots)
        evidence["source_sha256"] = hashlib.sha256(raw).hexdigest()
        root = Path(__file__).resolve().parents[1]
        evidence["post_run_output_code_sha256"] = {name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                                   for name in ("quality_pipeline.py", "h3_vocal_protocol.py")}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"slots": len(evidence["tests"]), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
        return
    if not all((args.base, args.followup, args.quality)) or args.expected_slots:
        parser.error("Multiphase export requires --base, --followup and --quality.")
    phases = {}
    source_hashes = {}
    for name, path, expected in (("frozen_ab", args.base, 48), ("native_followup", args.followup, 8), ("quality_followup", args.quality, 4)):
        raw = path.read_bytes()
        source_hashes[name] = hashlib.sha256(raw).hexdigest()
        phases[name] = sanitized(json.loads(raw), expected)
    evidence = {"schema": "t8-emotion-multiphase-evidence/v1", "source_sha256": source_hashes, "phases": phases,
                "runner_notes": ["The first three complete HTTP-200 responses were initially misclassified by an offline evaluator TypeError, then rechecked without generation. Original evaluator errors remain noted.", "One extra fourth-slot request was interrupted during runner diagnosis before a complete answer was captured; its outcome/tokens/cost are unknown and it is not an A/B sample. The separately recorded later fourth-slot answer is a new request.", "An UnboundLocalError after saving the fourth result stopped the runner without losing that result. Resume skipped all saved observations. Runner regressions now test all slots, resume and interrupted-slot retention."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"phases": {k: len(v["tests"]) for k, v in phases.items()}, "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
