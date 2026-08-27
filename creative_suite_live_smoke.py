from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))

SPEC = importlib.util.spec_from_file_location(
    "t8_creative_suite_live_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
creative = sys.modules[f"{SPEC.name}.creative_suite"]


def _json(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise RuntimeError("Expected a JSON object from the creative-suite node.")
    return parsed


def _check(name: str, checks: dict[str, bool], details: dict[str, Any]) -> dict[str, Any]:
    failed = [label for label, passed in checks.items() if not passed]
    return {
        "name": name,
        "passed": not failed,
        "score": round(100 * sum(checks.values()) / max(1, len(checks))),
        "checks": checks,
        "failed_checks": failed,
        "details": details,
    }


def _record(cases: list[dict[str, Any]], result: dict[str, Any]) -> None:
    cases.append(result)
    print(
        f"LIVE_CASE={result['name']} STATUS={'PASS' if result['passed'] else 'FAIL'} SCORE={result['score']}",
        flush=True,
    )


def _cjk_ratio(text: str) -> float:
    visible = re.sub(r"\s|\[[^\]\r\n]+\]|[\W\d_]", "", text)
    if not visible:
        return 0.0
    return len(re.findall(r"[\u4e00-\u9fff]", visible)) / len(visible)


def probe_endpoint(confirm_paid: bool = False) -> dict[str, Any]:
    """Issue one minimal real-model request without exposing response text or credentials."""
    if not confirm_paid:
        raise RuntimeError("Refusing to call the paid endpoint without explicit confirmation.")
    api_key = os.environ.get("SEEDANCE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY is not set in this process.")
    try:
        response = requests.post(
            creative.h3.CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": creative.h3.MODEL_ID,
                "messages": [{"role": "user", "content": "Return exactly this JSON object: {\"ok\":true}"}],
                "stream": False,
            },
            timeout=(20, 120),
        )
    except requests.RequestException as error:
        return {"passed": False, "network_error": type(error).__name__}
    content = ""
    if response.status_code == 200:
        try:
            content = str(response.json()["choices"][0]["message"]["content"]).strip()
        except (ValueError, KeyError, IndexError, TypeError):
            content = ""
    return {
        "passed": response.status_code == 200 and creative._extract_json(content) == {"ok": True},
        "status": int(response.status_code),
        "structured_json": creative._extract_json(content) == {"ok": True},
        "response_text_hidden": True,
    }


def run_paid_smoke(confirm_paid: bool = False) -> dict[str, Any]:
    if not confirm_paid:
        raise RuntimeError("Refusing to call paid endpoints without explicit confirmation.")
    api_key = os.environ.get("SEEDANCE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY is not set in this process.")

    brief = creative.T8CreativeDirector.execute(
        premise="12秒雨夜追逐：红色长风衣女性追赶即将离站的有轨电车。",
        character_identity="同一名成年女性，短黑发，红色长风衣",
        identity_policy=creative.LOCK_POLICY,
        world_space="雨夜霓虹街区，人物始终沿同一方向接近电车",
        world_policy=creative.LOCK_POLICY,
        action_editing="前段克制观察，后段连续加速，动作因果清晰",
        action_policy=creative.EVOLVE_POLICY,
        exclusions="不得改变人物身份、红色长风衣和追赶电车的结尾目标",
    )[0]

    cases: list[dict[str, Any]] = []

    candidates_result = creative.T8CreativeCandidateLab.execute(
        concept="为这段追逐设计两个机制真正不同、可在12秒执行的导演方案。",
        creative_brief=brief,
        candidate_count="2",
        divergence="高（明显不同导演路线）",
        must_keep="成年女性；短黑发；红色长风衣；雨夜；追赶电车",
        output_language="中文",
        api_key=api_key,
        seed=2026082701,
    )
    candidate_payload = _json(candidates_result[0])
    candidate_items = candidate_payload.get("candidates", [])
    axes = {str(item.get("creative_axis", "")).strip() for item in candidate_items if isinstance(item, dict)}
    _record(cases, _check("creative_candidates", {
        "structured_json": candidate_payload.get("structured_response") is True,
        "exact_candidate_count": len(candidate_items) == 2,
        "all_prompts_nonempty": all(str(item.get("prompt", "")).strip() for item in candidate_items),
        "distinct_axes": len(axes) >= 2,
        "soft_scores_present": all(isinstance(item.get("soft_scores"), dict) for item in candidate_items),
    }, {"candidate_count": len(candidate_items), "distinct_axis_count": len(axes)}))

    revision_result = creative.T8DirectedRevision.execute(
        original_prompt=str(candidates_result[2]),
        revision_request="只把最后4秒的追赶速度和镜头压迫感提高，其他设定不变。",
        locked_anchors="红色长风衣\n短黑发\n有轨电车\n雨夜",
        creative_brief=brief,
        output_language="中文",
        api_key=api_key,
        seed=2026082702,
    )
    revision_report = _json(revision_result[1])
    revised = revision_result[0]
    _record(cases, _check("directed_revision", {
        "structured_json": revision_report.get("structured_response") is True,
        "nonempty_revision": bool(revised.strip()),
        "identity_preserved": "红色长风衣" in revised and "短黑发" in revised,
        "goal_preserved": "电车" in revised,
        "local_diff_created": bool(revision_result[2].strip()),
    }, {"warning_count": len(revision_report.get("warnings", []))}))

    plan_result = creative.T8LongFormPlanner.execute(
        concept="24秒短片：女人从街角发现电车、穿过人群与积水，最终抓住车门上车。",
        creative_brief=brief,
        total_duration_seconds=24,
        segment_duration_seconds=12,
        continuity_anchors="红色长风衣；短黑发；始终朝同一电车前进；雨势逐段增强",
        output_language="中文",
        api_key=api_key,
        seed=2026082703,
    )
    h3_plan = _json(plan_result[1])
    seedance_plan = _json(plan_result[2])
    handoffs = _json(plan_result[3])
    h3_segments = h3_plan.get("segments", [])
    s2_segments = seedance_plan.get("segments", [])
    schedule = h3_plan.get("schedule", [])
    _record(cases, _check("long_form_planner", {
        "structured_json": h3_plan.get("structured_response") is True,
        "two_gapless_segments": len(schedule) == 2 and schedule[0]["start_seconds"] == 0 and schedule[-1]["end_seconds"] == 24,
        "h3_prompts_present": len(h3_segments) == 2 and all(str(item.get("h3_prompt", "")).strip() for item in h3_segments),
        "seedance_prompts_present": len(s2_segments) == 2 and all(str(item.get("seedance20_prompt", "")).strip() for item in s2_segments),
        "handoff_output_present": isinstance(handoffs.get("handoffs"), list),
    }, {"segment_count": len(schedule), "handoff_count": len(handoffs.get("handoffs", []))}))

    storyboard_result = creative.T8StoryboardPack.execute(
        concept=revised,
        creative_brief=brief,
        duration_seconds=12,
        shot_count="4",
        output_language="中文",
        api_key=api_key,
        seed=2026082704,
    )
    shots = _json(storyboard_result[1])
    keyframes = _json(storyboard_result[2])
    transitions = _json(storyboard_result[3])
    shot_items = shots.get("shots", [])
    _record(cases, _check("storyboard_pack", {
        "structured_json": shots.get("structured_response") is True,
        "global_prompt_nonempty": bool(storyboard_result[0].strip()),
        "exact_shot_count": len(shot_items) == 4,
        "shot_contract": all(all(key in item for key in ("index", "start_seconds", "end_seconds", "subject_action", "camera")) for item in shot_items),
        "keyframes_present": len(keyframes.get("keyframe_prompts", [])) >= 4,
        "transitions_present": len(transitions.get("transition_sound", [])) >= 1,
    }, {"shot_count": len(shot_items), "keyframe_count": len(keyframes.get("keyframe_prompts", []))}))

    from live_smoke import IMAGE_CODE, make_image_fixture

    reference_result = creative.T8ReferenceRoleMapper.execute(
        project_intent="制作产品身份稳定的12秒广告；精确读取图片中的可见编号并把它作为身份锚点。",
        asset_notes="<Picture 1> 只负责主体外观、构图、颜色和可见编号；不得虚构声音或图片外动作。",
        reference_images={"reference_image_0": make_image_fixture()},
        output_language="中文",
        api_key=api_key,
        seed=2026082705,
    )
    reference_payload = reference_result[0]
    reference_text = json.dumps(reference_payload, ensure_ascii=False) + reference_result[3]
    _record(cases, _check("reference_role_mapper", {
        "structured_json": reference_payload.get("structured_response") is True,
        "connected_label_exact": reference_payload.get("connected_labels") == ["<Picture 1>"],
        "asset_role_present": bool(reference_payload.get("assets")),
        "visible_code_read": IMAGE_CODE in reference_text,
        "no_preview_injection": "preview" not in reference_text.lower() and "gif" not in reference_text.lower(),
    }, {"asset_count": len(reference_payload.get("assets", []))}))

    music_result = creative.T8MusicCreativeLab.execute(
        operation=creative.MUSIC_LAB_MODES[0],
        music_idea="温暖的华语公路流行歌，女声从克制主歌走向明亮副歌，主题是雨停后重新出发。",
        lyrics_language="中文",
        candidate_count="2",
        locked_text="副歌核心意象必须包含：雨停以后",
        rewrite_mode="balanced",
        api_key=api_key,
        seed=2026082706,
    )
    music_payload = _json(music_result[1])
    music_candidates = music_payload.get("candidates", [])
    selected_lyrics = music_result[0]
    music_qa = _json(music_result[3])
    _record(cases, _check("music_creative_lab", {
        "structured_json": music_payload.get("structured_response") is True,
        "exact_candidate_count": len(music_candidates) == 2,
        "chinese_lyrics": _cjk_ratio(selected_lyrics) >= 0.65,
        "section_tags_present": "[Verse" in selected_lyrics and "[Chorus" in selected_lyrics,
        "locked_image_present": "雨停以后" in selected_lyrics,
        "local_language_qa_passed": not music_qa.get("local_text_qa", {}).get("script_warning"),
    }, {"candidate_count": len(music_candidates), "cjk_ratio": round(_cjk_ratio(selected_lyrics), 3)}))

    beat_result = creative.T8MusicVideoBeatSheet.execute(
        video_intent="15秒横版公路MV，从车窗雨痕过渡到雨后开阔公路，歌词字幕参与构图。",
        lyrics=selected_lyrics,
        music_caption="### Global Metadata\nMandopop road song, 96 BPM.\n### Vocal Details\nWarm female lead.\n### Arrangement\nSparse verse into bright chorus.",
        duration_seconds=15,
        known_bpm=96,
        known_time_cues="0–6秒主歌；6秒进入副歌；14–15秒定格收束",
        shot_count="5",
        output_language="中文",
        api_key=api_key,
        seed=2026082707,
    )
    beat_payload = beat_result[0]
    beat_text = json.dumps(beat_payload, ensure_ascii=False)
    _record(cases, _check("music_video_beat_sheet", {
        "structured_json": beat_payload.get("structured_response") is True,
        "five_or_more_events": len(beat_payload.get("beat_events", [])) >= 5,
        "text_evidence_boundary": bool(beat_payload.get("evidence_boundary")) and bool(
            re.search(r"text|文字|用户|provided|known", beat_payload.get("evidence_boundary", ""), re.I)
        ),
        "known_bpm_preserved": beat_payload.get("known_bpm") == 96,
        "h3_direction_present": bool(beat_result[2].strip()),
        "seedance_direction_present": bool(beat_result[3].strip()),
        "no_detected_audio_claim": not re.search(r"(detected|heard|listened).*?(audio|beat|bpm)", beat_text, re.I),
    }, {"beat_event_count": len(beat_payload.get("beat_events", []))}))

    failures = [case for case in cases if not case["passed"]]
    summary = {
        "suite": "T8 Creative Director Suite",
        "provider": "Seedance NZ / bytedance/doubao-seed-evolving",
        "paid_request_count": len(cases),
        "passed": not failures,
        "overall_score": round(sum(case["score"] for case in cases) / len(cases)),
        "cases": cases,
    }
    if failures:
        raise RuntimeError("Creative-suite paid smoke failed:\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Paid live quality smoke test for the T8 creative-director suite.")
    parser.add_argument(
        "--confirm-paid",
        action="store_true",
        help="Confirm seven potentially billable requests, including one synthetic image-analysis request.",
    )
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Make one minimal request and report only status/structure, never response text.",
    )
    args = parser.parse_args(argv)
    if args.probe_only:
        print(json.dumps(probe_endpoint(confirm_paid=args.confirm_paid), ensure_ascii=False, indent=2))
        return 0
    result = run_paid_smoke(confirm_paid=args.confirm_paid)
    print("CREATIVE_SUITE_LIVE_SMOKE=PASS")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
