import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import requests


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))

SPEC = importlib.util.spec_from_file_location(
    "t8_music3_live_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
music3 = sys.modules[f"{SPEC.name}.music3"]


PRESERVED_LYRICS = """[Verse]
凌晨四点，旧车站把雨声折成蓝线
我把未寄出的车票压在掌心

[Chorus]
沿着北纬三十一度的风
我们把沉默唱成回程的灯

[Outro]
最后一班车没有带走姓名"""

EDIT_ORIGINAL = """[Verse]
霓虹落在空杯里
我还没想好怎么告别

[Chorus]
把风留在旧天台
把约定留到云散开

[Verse]
末班车穿过长街
我仍然听见你的节拍

[Chorus]
把风留在旧天台
把约定留到云散开"""


CASES = [
    {
        "id": "generate_chinese_pop",
        "kwargs": {
            "music_idea": "原声华语流行歌曲，克制女声从雨夜独行逐步走向明亮坚定的最终副歌。",
            "lyrics_mode": music3.GENERATE_LYRICS_MODE,
            "lyrics": "",
            "lyrics_language": "中文",
            "target_duration_seconds": 150,
            "rewrite_mode": "balanced",
            "quality_mode": music3.FULL_QUALITY_MODE,
            "structure_preset": music3.POP_STRUCTURE,
            "constraints_and_exclusions": "Exactly 96 BPM in G major, 4/4 meter, female lead vocal, piano and acoustic guitar, no rap.",
            "fixed_bpm": 96,
            "key_scale": "G major",
            "meter": "4/4",
            "semantic_profile_mode": music3.SEMANTIC_LLM_MODE,
            "seed": 2026081401,
        },
        "required_groups": [["96 bpm"], ["g major"], ["female"], ["piano"], ["acoustic guitar"], ["no rap", "without rap"]],
        "sections": ["Verse", "Pre-Chorus", "Chorus", "Bridge", "Outro"],
        "mode": "generate",
    },
    {
        "id": "strict_preserve_synthpop",
        "kwargs": {
            "music_idea": "Retrowave synth-pop with a restrained opening, pulsing analog bass, and a wide but clean final chorus.",
            "lyrics_mode": music3.PRESERVE_LYRICS_MODE,
            "lyrics": PRESERVED_LYRICS,
            "lyrics_language": "中文",
            "target_duration_seconds": 135,
            "rewrite_mode": "strict",
            "quality_mode": music3.FULL_QUALITY_MODE,
            "constraints_and_exclusions": "Female alto lead, analog synth bass, gated drums, no choir, no key change.",
            "seed": 2026081402,
        },
        "required_groups": [["female alto"], ["analog synth", "synth bass"], ["gated drum"], ["no choir", "without choir"], ["no key change", "without key change"]],
        "sections": ["Verse", "Chorus", "Outro"],
        "mode": "preserve",
    },
    {
        "id": "instrumental_fusion",
        "kwargs": {
            "music_idea": "Instrumental cinematic folk fused with Chinese traditional colors, moving from a sparse dawn texture to a forceful final release.",
            "lyrics_mode": music3.INSTRUMENTAL_MODE,
            "lyrics": "",
            "target_duration_seconds": 180,
            "rewrite_mode": "balanced",
            "quality_mode": music3.FULL_QUALITY_MODE,
            "structure_preset": music3.CUSTOM_STRUCTURE,
            "custom_structure": "[Intro] [Verse: sparse erhu] [Instrumental: frame drum build] [Outro: instruments decay]",
            "constraints_and_exclusions": "Strictly instrumental. Erhu carries the lead melody; frame drum enters only after the midpoint; no singer and no choir.",
            "semantic_profile_mode": music3.SEMANTIC_PRIVACY_MODE,
            "seed": 2026081403,
        },
        "required_groups": [["instrumental"], ["erhu"], ["frame drum"], ["no singer", "without singer", "no vocal"], ["no choir", "without choir"]],
        "sections": ["Intro", "Verse", "Instrumental", "Outro"],
        "mode": "instrumental",
    },
    {
        "id": "targeted_second_verse_edit",
        "kwargs": {
            "music_idea": "Mid-tempo Mandarin indie pop with intimate verses and an open, memorable chorus.",
            "lyrics_mode": music3.EDIT_LYRICS_MODE,
            "lyrics": EDIT_ORIGINAL,
            "lyrics_language": "中文",
            "target_duration_seconds": 120,
            "rewrite_mode": "balanced",
            "quality_mode": music3.FAST_QUALITY_MODE,
            "lyrics_edit_request": "只改第二段主歌，使画面更具体并与副歌押韵；其他内容逐字不改。",
            "lyrics_edit_scope": music3.EDIT_SCOPE_AUTO,
            "constraints_and_exclusions": "Keep the existing chorus exactly unchanged. Warm male tenor, clean electric guitar, no rap.",
            "seed": 2026081404,
        },
        "required_groups": [["male tenor"], ["electric guitar"], ["no rap", "without rap"]],
        "sections": ["Verse", "Chorus"],
        "mode": "edit",
    },
]


def _sections(text: str) -> dict[str, str]:
    matches = list(music3.HEADING_PATTERN.finditer(text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1)] = text[match.end() : end].strip()
    return result


def _normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip().casefold() for line in text.splitlines() if line.strip()]


def _constraint_group_matches(lowered_caption: str, alternatives: list[str]) -> bool:
    for term in alternatives:
        lowered_term = term.casefold()
        if lowered_term in lowered_caption:
            return True
        negated = re.fullmatch(r"(?:no|without)\s+(.+)", lowered_term)
        if negated:
            target = re.escape(negated.group(1).strip())
            if re.search(rf"\b(?:no|without)\b[^.!?\n]{{0,80}}\b{target}\b", lowered_caption):
                return True
    return False


def score_case(case: dict, result: dict) -> dict:
    lyrics = result["lyrics"]
    caption = result["music_caption"]
    payload = json.loads(result["music3_payload_json"])
    report = json.loads(result["enhancement_report_json"])
    lowered = caption.casefold()
    sections = _sections(caption)
    checks = {}
    hard_failures = []

    checks["official_heading_contract"] = 15 if list(sections) == ["Global Metadata", "Vocal Details", "Arrangement"] else 0
    if not checks["official_heading_contract"]:
        hard_failures.append("official_heading_contract")

    payload_exact = payload == {"input": lyrics, "instructions": caption}
    checks["payload_consistency"] = 10 if payload_exact else 0
    if not payload_exact:
        hard_failures.append("payload_consistency")

    matched = 0
    missing_constraints = []
    for alternatives in case["required_groups"]:
        if _constraint_group_matches(lowered, alternatives):
            matched += 1
        else:
            missing_constraints.append(alternatives)
    checks["explicit_constraint_preservation"] = round(20 * matched / max(1, len(case["required_groups"])), 2)

    arrangement = sections.get("Arrangement", "")
    covered = sum(1 for section in case["sections"] if section.casefold() in arrangement.casefold())
    checks["section_timeline_coverage"] = round(10 * covered / max(1, len(case["sections"])), 2)

    lyric_leak = music3._has_lyric_leakage(caption, lyrics)
    checks["lyrics_caption_separation"] = 10 if not lyric_leak else 0
    if lyric_leak:
        hard_failures.append("lyrics_caption_separation")

    body_depth = all(len(value) >= 60 for value in sections.values()) and len(arrangement) >= 140
    # The deterministic rubric is intentionally capped at exactly 100 points.
    checks["caption_specificity"] = 5 if body_depth else 2.5 if sections else 0

    mode_score = 0
    if case["mode"] == "preserve":
        mode_score = 20 if lyrics == case["kwargs"]["lyrics"] else 0
        if not mode_score:
            hard_failures.append("strict_lyrics_preservation")
    elif case["mode"] == "instrumental":
        safe_caption = not music3._caption_has_positive_vocal(caption)
        mode_score = 20 if lyrics == "[Instrumental]" and safe_caption else 0
        if not mode_score:
            hard_failures.append("instrumental_invariant")
    elif case["mode"] == "edit":
        original_sections = music3._split_lyric_sections(case["kwargs"]["lyrics"])
        output_sections = music3._split_lyric_sections(lyrics)
        first_verse_same = original_sections[0][1] == output_sections[0][1]
        first_chorus_same = original_sections[1][1] == output_sections[1][1]
        second_verse_changed = original_sections[2][1] != output_sections[2][1]
        last_chorus_same = original_sections[3][1] == output_sections[3][1]
        mode_score = 20 if all((first_verse_same, first_chorus_same, second_verse_changed, last_chorus_same)) else 0
        if not mode_score:
            hard_failures.append("targeted_edit_boundary")
    else:
        tags = music3._extract_section_tags(lyrics)
        chinese_characters = len(re.findall(r"[\u3400-\u9fff]", lyrics))
        mode_score = 20 if len(tags) >= 4 and chinese_characters >= 80 else 10 if tags and chinese_characters >= 40 else 0
        if not lyrics.strip():
            hard_failures.append("generated_lyrics_empty")
    checks["lyrics_mode_invariant"] = mode_score

    unsafe_report = any(
        value in result["enhancement_report_json"]
        for value in (case["kwargs"]["music_idea"], "chat/completions", "templates/")
    )
    severe_warnings = {
        "possible_lyric_line_leakage",
        "possible_selected_reference_phrase_overlap",
        "instrumental_caption_may_add_vocals",
        "music3_5000_token_budget_exceeded",
        "caption_timeline_inconsistent_with_target_duration",
    }.intersection(report.get("warnings", []))
    checks["safe_diagnostics"] = 5 if not unsafe_report and not severe_warnings else 0
    checks["nonempty_outputs"] = 5 if lyrics.strip() and caption.strip() else 0
    if not checks["nonempty_outputs"]:
        hard_failures.append("nonempty_outputs")

    score = round(sum(checks.values()), 2)
    if not 0 <= score <= 100:
        raise AssertionError(f"Deterministic Music 3 quality score escaped its 0-100 contract: {score}")
    return {
        "score": score,
        "checks": checks,
        "hard_failures": hard_failures,
        "missing_constraint_groups": missing_constraints,
        "report": report,
    }


def _judge_results(api_key: str, results: list[dict]) -> dict[str, dict]:
    api_key, chat_url, _upload_url, provider_name = music3._provider_config(
        music3.SEEDANCE_API_MODE,
        api_key,
        "",
    )
    system = """You are a strict release-quality judge for a MiniMax Music 3 text-preparation node. Score each case independently from 0-100 using only the supplied brief, final lyrics, and Structured Caption. Return JSON only as {"cases":[{"id":"...","score":0,"dimensions":{"brief_fidelity":0,"arrangement_coherence":0,"lyric_singability":0,"originality_and_hook":0,"official_separation":0},"evidence":["..."]}]}. Dimension maxima are 30, 25, 20, 15, and 10. Penalize generic equipment lists, incoherent instrument entrances, weak hooks, cliches, contradictions, copied lyric lines in Caption, invented constraints, and edits outside the requested scope. Evidence must be concise factual observations, not hidden reasoning, and must not quote more than six consecutive lyric words. Do not reward length by itself."""
    judge_input = []
    for item in results:
        case = item["case"]
        judge_input.append(
            {
                "id": case["id"],
                "brief": case["kwargs"],
                "lyrics": item["lyrics"],
                "structured_caption": item["music_caption"],
            }
        )
    with requests.Session() as session:
        response = music3._request_music_completion(
            session,
            api_key,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({"cases": judge_input}, ensure_ascii=False)},
            ],
            0.1,
            chat_url,
            provider_name,
            music3._resolve_llm_model(music3.SEEDANCE_API_MODE, music3.AI_WORKSHOP_DEFAULT_MODEL, ""),
            "release_quality_judge",
        )
    parsed = music3._extract_json(response) or {}
    judged = {}
    dimension_maxima = {
        "brief_fidelity": 30,
        "arrangement_coherence": 25,
        "lyric_singability": 20,
        "originality_and_hook": 15,
        "official_separation": 10,
    }
    for item in parsed.get("cases", []):
        if not isinstance(item, dict) or item.get("id") not in {case["id"] for case in CASES}:
            continue
        score = float(item.get("score", -1))
        dimensions = item.get("dimensions")
        evidence = item.get("evidence")
        if not 0 <= score <= 100 or not isinstance(dimensions, dict) or not isinstance(evidence, list):
            continue
        if set(dimensions) != set(dimension_maxima):
            continue
        try:
            normalized_dimensions = {key: float(dimensions[key]) for key in dimension_maxima}
        except (TypeError, ValueError):
            continue
        if any(
            value < 0 or value > dimension_maxima[key]
            for key, value in normalized_dimensions.items()
        ):
            continue
        dimension_total = round(sum(normalized_dimensions.values()), 2)
        if abs(dimension_total - score) > 0.01:
            continue
        judged[item["id"]] = {
            "score": score,
            "dimensions": normalized_dimensions,
            "evidence": [str(value)[:500] for value in evidence[:8]],
        }
    if len(judged) != len(CASES):
        raise RuntimeError("The paid quality judge did not return one valid score for every case.")
    return judged


def _sanitized_case(case: dict) -> dict:
    kwargs = dict(case["kwargs"])
    return {"id": case["id"], "kwargs": kwargs, "required_groups": case["required_groups"], "sections": case["sections"], "mode": case["mode"]}


def _suite_fingerprint() -> str:
    payload = {
        "cases": [_sanitized_case(case) for case in CASES],
        "model": "bytedance/doubao-seed-evolving",
        "official_skill_commit": music3.OFFICIAL_SOURCE_COMMIT,
        "official_skill_tree_sha256": music3.OFFICIAL_NORMALIZED_TREE_SHA256,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _load_checkpoint(path: Path, fingerprint: str) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if data.get("schema_version") != "t8-music3-paid-checkpoint/v1" or data.get("suite_fingerprint") != fingerprint:
        return {}
    items = data.get("completed_cases")
    return {item["id"]: item for item in items if isinstance(item, dict) and item.get("id")} if isinstance(items, list) else {}


def _write_checkpoint(path: Path, fingerprint: str, completed: dict[str, dict]) -> None:
    data = {
        "schema_version": "t8-music3-paid-checkpoint/v1",
        "suite_fingerprint": fingerprint,
        "completed_cases": list(completed.values()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _seed_checkpoint_from_report(
    report_path: Path,
    checkpoint_path: Path,
    fingerprint: str,
    rerun_case_ids: set[str],
) -> None:
    if not report_path.is_file():
        raise RuntimeError("--rerun-case requires an existing completed --output report.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    existing = {}
    for item in report.get("cases", []):
        case_id = item.get("case", {}).get("id")
        if not case_id or case_id in rerun_case_ids:
            continue
        existing[case_id] = {
            "id": case_id,
            "lyrics": item["lyrics"],
            "music_caption": item["music_caption"],
            "music3_payload_json": item["music3_payload_json"],
            "enhancement_report": item["enhancement_report"],
        }
    _write_checkpoint(checkpoint_path, fingerprint, existing)


def rescore_existing_report(report_path: Path, minimum_score: float = 85.0) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in CASES}
    if {item.get("case", {}).get("id") for item in report.get("cases", [])} != set(by_id):
        raise RuntimeError("The existing report does not contain exactly the current release-suite cases.")
    suite_passed = True
    for item in report["cases"]:
        case = by_id[item["case"]["id"]]
        result = {
            "lyrics": item["lyrics"],
            "music_caption": item["music_caption"],
            "music3_payload_json": json.dumps(item["music3_payload_json"], ensure_ascii=False),
            "enhancement_report_json": json.dumps(item["enhancement_report"], ensure_ascii=False),
        }
        deterministic = score_case(case, result)
        judge_score = float(item["judge"]["score"])
        final_score = round(deterministic["score"] * 0.7 + judge_score * 0.3, 2)
        passed = final_score >= minimum_score and judge_score >= 80 and not deterministic["hard_failures"]
        item["case"] = _sanitized_case(case)
        item["deterministic"] = deterministic
        item["final_score"] = final_score
        item["passed"] = passed
        item["output_sha256"] = hashlib.sha256(
            (item["lyrics"] + "\0" + item["music_caption"]).encode("utf-8")
        ).hexdigest()
        suite_passed = suite_passed and passed
    report["minimum_score"] = minimum_score
    report["minimum_judge_score"] = 80
    report["passed"] = suite_passed
    return report


def run_paid_quality_suite(
    confirm_paid: bool = False,
    minimum_score: float = 85.0,
    checkpoint_path: Path | None = None,
) -> dict:
    if not confirm_paid:
        raise RuntimeError("Refusing to call paid Music 3 prompt endpoints without explicit confirmation.")
    api_key = os.environ.get("SEEDANCE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY is not set in this process.")

    music3.clear_music3_stage_cache()
    fingerprint = _suite_fingerprint()
    completed = _load_checkpoint(checkpoint_path, fingerprint) if checkpoint_path else {}
    results = []
    for case in CASES:
        saved = completed.get(case["id"])
        if saved:
            print(f"CASE_RESUME={case['id']}", flush=True)
            lyrics = str(saved["lyrics"])
            caption = str(saved["music_caption"])
            payload = json.dumps(saved["music3_payload_json"], ensure_ascii=False)
            report = json.dumps(saved["enhancement_report"], ensure_ascii=False)
        else:
            print(f"CASE_START={case['id']}", flush=True)
            lyrics, caption, payload, report = music3.enhance_music3_prompt(
                **case["kwargs"],
                api_key=api_key,
                api_mode=music3.SEEDANCE_API_MODE,
                # Keep successful earlier stages in this process if a later gateway
                # stage needs a bounded release-suite resume.
                stage_cache=music3.STAGE_CACHE_ON,
            )
        result = {
            "case": case,
            "lyrics": lyrics,
            "music_caption": caption,
            "music3_payload_json": payload,
            "enhancement_report_json": report,
        }
        result["deterministic"] = score_case(case, result)
        results.append(result)
        if not saved and checkpoint_path:
            completed[case["id"]] = {
                "id": case["id"],
                "lyrics": lyrics,
                "music_caption": caption,
                "music3_payload_json": json.loads(payload),
                "enhancement_report": json.loads(report),
            }
            _write_checkpoint(checkpoint_path, fingerprint, completed)
            print(f"CASE_COMPLETE={case['id']} deterministic={result['deterministic']['score']:.2f}", flush=True)

    print("QUALITY_JUDGE_START=1", flush=True)
    judged = _judge_results(api_key, results)
    delivered = []
    suite_passed = True
    for result in results:
        case_id = result["case"]["id"]
        deterministic = result["deterministic"]
        judge = judged[case_id]
        final_score = round(deterministic["score"] * 0.7 + judge["score"] * 0.3, 2)
        passed = final_score >= minimum_score and judge["score"] >= 80 and not deterministic["hard_failures"]
        suite_passed = suite_passed and passed
        delivered.append(
            {
                "case": _sanitized_case(result["case"]),
                "lyrics": result["lyrics"],
                "music_caption": result["music_caption"],
                "music3_payload_json": json.loads(result["music3_payload_json"]),
                "enhancement_report": json.loads(result["enhancement_report_json"]),
                "deterministic": deterministic,
                "judge": judge,
                "final_score": final_score,
                "passed": passed,
                "output_sha256": hashlib.sha256(
                    (result["lyrics"] + "\0" + result["music_caption"]).encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "schema_version": "t8-music3-paid-quality/v1",
        "provider": "seedance-flat-price-house",
        "model": "bytedance/doubao-seed-evolving",
        "official_skill_commit": music3.OFFICIAL_SOURCE_COMMIT,
        "official_skill_tree_sha256": music3.OFFICIAL_NORMALIZED_TREE_SHA256,
        "minimum_score": minimum_score,
        "minimum_judge_score": 80,
        "score_formula": "70% deterministic contract score + 30% one batched structured LLM quality judge",
        "passed": suite_passed,
        "cases": delivered,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Paid MiniMax Music 3 prompt-and-lyrics release quality suite.")
    parser.add_argument("--confirm-paid", action="store_true", help="Confirm 4 generation workflows plus one batched quality-judge request.")
    parser.add_argument("--minimum-score", type=float, default=85.0)
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "tests" / "fixtures" / "music3_paid_quality_2026-08-14.json")
    parser.add_argument("--fresh", action="store_true", help="Ignore and remove a matching safe test checkpoint.")
    parser.add_argument("--rerun-case", action="append", choices=[case["id"] for case in CASES], help="Reuse the existing report except for this case; may be repeated.")
    parser.add_argument("--rescore-only", action="store_true", help="Recompute deterministic scores from the existing report without any API request.")
    args = parser.parse_args(argv)
    if args.rescore_only:
        if not args.output.is_file():
            parser.error("--rescore-only requires an existing --output report")
        report = rescore_existing_report(args.output, args.minimum_score)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"MUSIC3_RESCORE={'PASS' if report['passed'] else 'FAIL'}")
        for item in report["cases"]:
            print(f"{item['case']['id']}: deterministic={item['deterministic']['score']:.2f}, judge={item['judge']['score']:.2f}, final={item['final_score']:.2f}, passed={item['passed']}")
        return 0 if report["passed"] else 1
    if not args.confirm_paid:
        parser.error("Refusing paid requests without --confirm-paid.")
    checkpoint = args.output.with_suffix(".checkpoint.json")
    if args.fresh and checkpoint.exists():
        checkpoint.unlink()
    if args.rerun_case:
        _seed_checkpoint_from_report(args.output, checkpoint, _suite_fingerprint(), set(args.rerun_case))
    report = run_paid_quality_suite(True, args.minimum_score, checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MUSIC3_PAID_QUALITY={'PASS' if report['passed'] else 'FAIL'}")
    print(f"REPORT={args.output.resolve()}")
    for item in report["cases"]:
        print(f"{item['case']['id']}: deterministic={item['deterministic']['score']:.2f}, judge={item['judge']['score']:.2f}, final={item['final_score']:.2f}, passed={item['passed']}")
    if checkpoint.exists():
        checkpoint.unlink()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
