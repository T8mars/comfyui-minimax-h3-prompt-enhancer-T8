from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "t8-performance-benchmark/v1"
SOURCE_COMMIT = "ab65851f599435a1ff94ea4931949bd7bcaf069b"
DEFAULT_SEEDS = [2026083001, 2026083002, 2026083003, 2026083004, 2026083005]
SUBJECTS = {
    "live_actor": "One live-action adult character with stable identity and wardrobe.",
    "stylized_character": "One stylized non-photoreal character with stable silhouette and costume.",
}
ASPECT_RATIOS = ("9:16", "16:9")
ARMS = ("control", "treatment")
ALLOWED_RESULT_STATUS = {"pending", "rendered", "failed", "excluded"}
ALLOWED_METRICS = {
    "face_roi_registered_similarity",
    "landmark_stability",
    "optical_flow_consistency",
    "beat_realization_rate",
    "gaze_target_accuracy",
    "contract_preservation_rate",
}

HYPOTHESES: dict[str, dict[str, str]] = {
    "beat_density": {
        "brief": "A character receives upsetting news, contains the first reaction, then settles into a clear final decision.",
        "control": "Keep every emotional change inside one uninterrupted shot.",
        "treatment": "Give each shot one primary state change; split competing changes only when the requested shot count permits.",
    },
    "camera_eyeline_order": {
        "brief": "A character notices someone off camera and silently recognizes them.",
        "control": "Describe the facial expression before identifying the camera side or gaze target.",
        "treatment": "Establish camera side and a concrete gaze target before facial direction and micro-expression.",
    },
    "relational_composition": {
        "brief": "A restrained close performance must preserve eye and mouth readability.",
        "control": "Specify crop only with raw numeric face and frame percentages.",
        "treatment": "Specify a relational crop using visible facial landmarks and headroom; use a reference when exact geometry matters.",
    },
    "concealed_state_change": {
        "brief": "A character changes from composed to visibly non-human while identity and costume remain recognizable.",
        "control": "Show the entire strong state change continuously in a fully exposed face close-up.",
        "treatment": "Place the strongest change behind one motivated eye closure, head movement, foreground occlusion, action occlusion, or cut.",
    },
    "contact_causality": {
        "brief": "A character interacts with a fragile liquid-filled object and the result must remain causally legible.",
        "control": "Describe simultaneous direct contact, splash, breakage, recoil, and aftermath in one dense instant.",
        "treatment": "Separate approach, contact cue, reaction, and aftermath so the causal chain remains visible; do not ban contact or liquid.",
    },
}


class BenchmarkError(ValueError):
    pass


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pair_id(hypothesis: str, subject: str, aspect_ratio: str, seed: int) -> str:
    aspect = aspect_ratio.replace(":", "x")
    return f"{hypothesis}__{subject}__{aspect}__s{seed}"


def _blind_labels(pair_id: str) -> dict[str, str]:
    # Stable ordering prevents the treatment from always being B while keeping
    # generation seed and evaluation order independently reproducible.
    control_first = int(_hash_text(pair_id)[:2], 16) % 2 == 0
    return {"control": "A", "treatment": "B"} if control_first else {"control": "B", "treatment": "A"}


def build_manifest() -> dict[str, Any]:
    seeds = DEFAULT_SEEDS
    subjects = SUBJECTS
    aspect_ratios = ASPECT_RATIOS
    rows: list[dict[str, Any]] = []
    for hypothesis, definition in HYPOTHESES.items():
        for subject, subject_contract in subjects.items():
            for aspect_ratio in aspect_ratios:
                for raw_seed in seeds:
                    seed = int(raw_seed)
                    pair_id = _pair_id(hypothesis, subject, str(aspect_ratio), seed)
                    labels = _blind_labels(pair_id)
                    for arm in ARMS:
                        instruction = definition[arm]
                        prompt_contract = "\n".join((
                            definition["brief"],
                            subject_contract,
                            f"Aspect ratio: {aspect_ratio}.",
                            instruction,
                        ))
                        rows.append({
                            "case_id": f"{pair_id}__{arm}",
                            "pair_id": pair_id,
                            "hypothesis": hypothesis,
                            "subject": subject,
                            "aspect_ratio": str(aspect_ratio),
                            "seed": seed,
                            "arm": arm,
                            "blind_label": labels[arm],
                            "brief": definition["brief"],
                            "subject_contract": subject_contract,
                            "arm_instruction": instruction,
                            "prompt_contract_sha256": _hash_text(prompt_contract),
                            "result": {
                                "status": "pending",
                                "artifact_sha256": "",
                                "metrics": {},
                                "notes": "",
                            },
                        })
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "https://github.com/phileiny/h3-storyboard-skill",
            "commit": SOURCE_COMMIT,
            "evidence_level": "community observations pending independent paired validation",
        },
        "pre_registration": {
            "hypotheses": list(HYPOTHESES),
            "subjects": list(subjects),
            "aspect_ratios": list(aspect_ratios),
            "seeds": [int(seed) for seed in seeds],
            "arms": list(ARMS),
            "primary_metrics": sorted(ALLOWED_METRICS),
            "prohibited_proxy": "full-frame PSNR alone must not be reported as facial acting quality",
        },
        "model_metadata": {
            "model": "FILL_BEFORE_RENDER",
            "model_version": "FILL_BEFORE_RENDER",
            "provider_or_runtime": "FILL_BEFORE_RENDER",
            "node_version": "FILL_BEFORE_RENDER",
        },
        "cases": rows,
        "pair_reviews": [],
    }


def validate_manifest(manifest: Mapping[str, Any], *, require_results: bool = False) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        return [*errors, "cases must be a list"]
    expected_cases = {item["case_id"]: item for item in build_manifest()["cases"]}
    supplied_ids = {str(item.get("case_id", "")) for item in cases if isinstance(item, Mapping)}
    if supplied_ids != set(expected_cases):
        errors.append("cases do not match the pre-registered 200-row matrix")
    seen: set[str] = set()
    pairs: dict[str, set[str]] = defaultdict(set)
    metadata = manifest.get("model_metadata") if isinstance(manifest.get("model_metadata"), Mapping) else {}
    metadata_ready = bool(metadata) and all(
        str(metadata.get(key, "")).strip() not in {"", "FILL_BEFORE_RENDER"}
        for key in ("model", "model_version", "provider_or_runtime", "node_version")
    )
    for index, item in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(item.get("case_id", ""))
        if not case_id or case_id in seen:
            errors.append(f"{prefix} has missing or duplicate case_id")
        seen.add(case_id)
        expected = expected_cases.get(case_id)
        if expected is not None:
            protected_fields = (
                "pair_id", "hypothesis", "subject", "aspect_ratio", "seed", "arm",
                "blind_label", "brief", "subject_contract", "arm_instruction", "prompt_contract_sha256",
            )
            if any(item.get(field) != expected.get(field) for field in protected_fields):
                errors.append(f"{prefix} changes a pre-registered field")
        pair_id = str(item.get("pair_id", ""))
        arm = str(item.get("arm", ""))
        if arm not in ARMS:
            errors.append(f"{prefix}.arm is invalid")
        pairs[pair_id].add(arm)
        if item.get("hypothesis") not in HYPOTHESES:
            errors.append(f"{prefix}.hypothesis is invalid")
        digest = str(item.get("prompt_contract_sha256", ""))
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            errors.append(f"{prefix}.prompt_contract_sha256 is invalid")
        result = item.get("result")
        if not isinstance(result, Mapping):
            errors.append(f"{prefix}.result must be an object")
            continue
        status = str(result.get("status", ""))
        if status not in ALLOWED_RESULT_STATUS:
            errors.append(f"{prefix}.result.status is invalid")
        metrics = result.get("metrics", {})
        if not isinstance(metrics, Mapping):
            errors.append(f"{prefix}.result.metrics must be an object")
            metrics = {}
        unknown_metrics = sorted(set(metrics) - ALLOWED_METRICS)
        if unknown_metrics:
            errors.append(f"{prefix} has unregistered metrics: {', '.join(unknown_metrics)}")
        for name, value in metrics.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
                errors.append(f"{prefix}.result.metrics.{name} must be in [0, 1]")
        if status == "rendered":
            artifact_hash = str(result.get("artifact_sha256", ""))
            if len(artifact_hash) != 64 or any(char not in "0123456789abcdef" for char in artifact_hash):
                errors.append(f"{prefix} rendered result requires artifact_sha256")
            if not metadata_ready:
                errors.append(f"{prefix} rendered result requires complete model_metadata")
            if require_results and not metrics:
                errors.append(f"{prefix} rendered result requires at least one registered metric")
    for pair_id, arms in pairs.items():
        if not pair_id or arms != set(ARMS):
            errors.append(f"pair {pair_id or '<missing>'} must contain control and treatment")
    reviews = manifest.get("pair_reviews", [])
    if not isinstance(reviews, list):
        errors.append("pair_reviews must be a list")
    else:
        known_pairs = set(pairs)
        reviewed: set[str] = set()
        for index, review in enumerate(reviews):
            if not isinstance(review, Mapping):
                errors.append(f"pair_reviews[{index}] must be an object")
                continue
            pair_id = str(review.get("pair_id", ""))
            if pair_id not in known_pairs or pair_id in reviewed:
                errors.append(f"pair_reviews[{index}] has unknown or duplicate pair_id")
            reviewed.add(pair_id)
            if review.get("preference") not in {"A", "B", "tie", "unrateable"}:
                errors.append(f"pair_reviews[{index}].preference is invalid")
    return errors


def summarize_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    if errors:
        raise BenchmarkError("; ".join(errors))
    cases = [item for item in manifest["cases"] if isinstance(item, Mapping)]
    statuses = Counter(str(item["result"]["status"]) for item in cases)
    metric_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    rendered_by_pair: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for item in cases:
        result = item["result"]
        if result["status"] != "rendered":
            continue
        rendered_by_pair[str(item["pair_id"])][str(item["arm"])] = item
        for name, value in result.get("metrics", {}).items():
            metric_values[name][str(item["arm"])].append(float(value))
    metric_summary: dict[str, Any] = {}
    for name, arms in sorted(metric_values.items()):
        control = arms.get("control", [])
        treatment = arms.get("treatment", [])
        metric_summary[name] = {
            "control_n": len(control),
            "treatment_n": len(treatment),
            "control_mean": sum(control) / len(control) if control else None,
            "treatment_mean": sum(treatment) / len(treatment) if treatment else None,
        }
        if control and treatment:
            metric_summary[name]["unpaired_mean_delta"] = metric_summary[name]["treatment_mean"] - metric_summary[name]["control_mean"]
        else:
            metric_summary[name]["unpaired_mean_delta"] = None
    blind_counts = Counter()
    cases_by_pair = {pair_id: arms for pair_id, arms in rendered_by_pair.items() if set(arms) == set(ARMS)}
    for review in manifest.get("pair_reviews", []):
        pair_id = str(review["pair_id"])
        preference = str(review["preference"])
        if pair_id not in cases_by_pair or preference in {"tie", "unrateable"}:
            blind_counts[preference] += 1
            continue
        label_to_arm = {str(item["blind_label"]): arm for arm, item in cases_by_pair[pair_id].items()}
        blind_counts[label_to_arm.get(preference, "unrateable")] += 1
    total = len(cases)
    rendered = statuses.get("rendered", 0)
    if rendered == 0:
        evidence_state = "no_observations"
    elif rendered < total:
        evidence_state = "partial_observations"
    else:
        evidence_state = "complete_observations"
    return {
        "schema_version": "t8-performance-benchmark-report/v1",
        "evidence_state": evidence_state,
        "experiment_executed": rendered > 0,
        "planned_renders": total,
        "status_counts": dict(sorted(statuses.items())),
        "complete_rendered_pairs": len(cases_by_pair),
        "structure_contract": {
            "valid": True,
            "source_commit": manifest["source"]["commit"],
        },
        "automatic_or_annotated_metrics": {
            "scope": "registered ROI, temporal, gaze, beat, and contract metrics supplied by the evaluator; not an objective creativity score",
            "metrics": metric_summary,
        },
        "blinded_human_review": {
            "scope": "paired preference only; model identity and arm should remain hidden from raters",
            "counts": dict(sorted(blind_counts.items())),
        },
        "claims": {
            "experiment_complete": bool(rendered == total and len(cases_by_pair) * 2 == total),
            "ready_for_preregistered_human_inference_review": bool(
                rendered == total and len(cases_by_pair) * 2 == total and blind_counts
            ),
            "external_findings_independently_validated": False,
            "validation_note": "Completion and aggregation never auto-promote a community observation into a validated model law; review effect direction, uncertainty, exclusions, and blind-rating quality hypothesis by hypothesis.",
            "full_frame_psnr_used_as_facial_quality": False,
        },
    }


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkError("manifest root must be an object")
    return data


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create and audit the offline T8 performance-directing A/B benchmark.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Create a deterministic pending benchmark manifest.")
    init_parser.add_argument("--output", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate", help="Validate a benchmark manifest without claiming success.")
    validate_parser.add_argument("manifest", type=Path)
    validate_parser.add_argument("--require-results", action="store_true")
    summary_parser = subparsers.add_parser("summarize", help="Summarize only actually supplied rendered results.")
    summary_parser.add_argument("manifest", type=Path)
    summary_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "init":
        _write(args.output, build_manifest())
        print(f"created {args.output} with {len(build_manifest()['cases'])} pending renders")
        return 0
    manifest = _load(args.manifest)
    if args.command == "validate":
        errors = validate_manifest(manifest, require_results=args.require_results)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("benchmark manifest is valid")
        return 0
    report = summarize_manifest(copy.deepcopy(manifest))
    if args.output:
        _write(args.output, report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
