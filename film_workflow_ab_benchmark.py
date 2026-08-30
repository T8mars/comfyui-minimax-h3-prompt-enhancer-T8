from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__:
    from . import creative_suite as creative
    from . import film_workflow as film
    from . import performance_director as performance
    from . import provider_config as shared_provider
else:
    PROJECT_DIR = Path(__file__).resolve().parent
    COMFYUI_ROOT = PROJECT_DIR.parents[1]
    sys.path.insert(0, str(COMFYUI_ROOT))
    SPEC = importlib.util.spec_from_file_location(
        "t8_film_workflow_ab_live_package",
        PROJECT_DIR / "__init__.py",
        submodule_search_locations=[str(PROJECT_DIR)],
    )
    package = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = package
    SPEC.loader.exec_module(package)
    creative = sys.modules[f"{SPEC.name}.creative_suite"]
    film = sys.modules[f"{SPEC.name}.film_workflow"]
    performance = sys.modules[f"{SPEC.name}.performance_director"]
    shared_provider = sys.modules[f"{SPEC.name}.provider_config"]


SUITE_NAME = "T8 film workflow contract A/B"
BENCHMARK_SCHEMA = "t8-film-workflow-paid-ab/v1"
CONTRACT_REVISION = "2026-08-30.3"
BENCHMARK_MODEL = "qwen/qwen3.6-flash"
BENCHMARK_BASE_URL = "https://api.seedance.nz/v1"
STORYBOARD_MAX_TOKENS = 2600
LONGFORM_MAX_TOKENS = 3200
PROVIDER_NAME = f"Seedance NZ OpenAI-compatible endpoint / {BENCHMARK_MODEL}"
UNSCORED_TRANSPORT_OBSERVATIONS = [{
    "model": "bytedance/doubao-seed-evolving",
    "trial_count": 2,
    "outcome": "HTTP 524 upstream timeout",
    "response_text_hidden": True,
    "included_in_scores": False,
}]
DEFAULT_REPORT = Path(__file__).resolve().parent / "tests" / "fixtures" / "film_workflow_paid_ab_2026-08-30.json"
DEFAULT_CHECKPOINT = Path(__file__).resolve().parent / "runtime" / "film_workflow_paid_ab_checkpoint.json"


BASELINE_STORYBOARD_SYSTEM = """You are a storyboard delivery director. Build an executable creative pack, not a production claim. Respect the requested duration and supplied story facts.
Each shot must have index, start_seconds, end_seconds, purpose, composition, subject_action, camera, continuity, media_bindings, dialogue_or_text, sound, keyframe_prompt, transition_in, and transition_out. Keep fields compact. Return one JSON object with global_prompt and shots only. Do not use Markdown fences."""

BASELINE_LONGFORM_SYSTEM = """You are a long-form audiovisual continuity director. Plan multiple independently generatable video segments. Preserve identity, props, spatial direction, action state, dialogue, visible text, and sound handoffs. Return one JSON object with global_continuity_brief, segments, and handoffs. Each segment must contain segment_index, start_state, end_state, continuity_anchors, media_bindings, h3_prompt, and seedance20_prompt. Do not use Markdown fences."""


CASES: list[dict[str, Any]] = [
    {
        "id": "storyboard_causality_value_shift",
        "kind": "storyboard",
        "concept": "12秒四镜审讯戏。审计员周岚要逼顾衡承认假账；顾衡拒绝认罪并用银色钢笔敲桌拖延；周岚发现钢笔墨迹与账本批注一致，权力从顾衡掌控转为周岚掌控。不得让顾衡认罪。",
        "authoritative": "周岚要逼顾衡承认假账\n顾衡拒绝认罪\n银色钢笔墨迹与账本批注一致",
        "knowledge": "前两镜只有顾衡知道钢笔与假账有关\n第三镜周岚才确认关联",
        "anchors": ["银色钢笔", "拒绝认罪", "账本"],
        "character": {
            "character_id": "顾衡",
            "scene_objective": "拖延审讯并守住秘密",
            "obstacle_and_stakes": "周岚正在用物证逼近；失败将暴露假账",
            "tactics": "用钢笔敲桌打断节奏\n反问周岚\n沉默施压",
            "physical_task_and_inertia": "右手持续握住银色钢笔；被识破后握力加重但不突然换手",
            "gaze_and_listening": "先盯周岚，听到账本批注后视线短暂落向钢笔",
        },
        "checks": ["structured", "count", "base_fields", "anchors", "narrative_fields", "causal_chain", "value_shift", "scene_necessity"],
    },
    {
        "id": "storyboard_setup_payoff",
        "kind": "storyboard",
        "concept": "12秒四镜逃脱戏。第一镜明确把红色围巾系在女孩手腕；卷闸门开始下降；第三镜围巾被解下；第四镜女孩用同一条红色围巾卡住卷闸门齿轮，门停住，她滑出门外。围巾不能中途消失或变色。",
        "authoritative": "第一镜红色围巾系在女孩手腕\n第四镜同一条红色围巾卡住卷闸门齿轮\n结尾女孩滑出门外",
        "world_rules": "红色围巾是唯一能卡住卷闸门齿轮的现有物件",
        "continuity": "红色围巾始终为同一条且颜色不变",
        "anchors": ["红色围巾", "卷闸门", "齿轮"],
        "setup_payoff_anchor": "红色围巾",
        "character": {
            "character_id": "女孩",
            "scene_objective": "在卷闸门完全关闭前逃出去",
            "obstacle_and_stakes": "下降的卷闸门会把她困在室内",
            "tactics": "冲刺\n观察齿轮\n解下围巾卡住齿轮",
            "physical_task_and_inertia": "奔跑惯性延续到滑行动作；围巾从手腕解下后一直在右手",
        },
        "checks": ["structured", "count", "base_fields", "anchors", "narrative_fields", "causal_chain", "setup_payoff", "scene_necessity"],
    },
    {
        "id": "storyboard_tactic_shift",
        "kind": "storyboard",
        "concept": "12秒四镜谈判戏。经纪人沈乔要客户签字，客户连续三次拒绝；沈乔依次用示弱、交换条件、沉默施压三种策略，只有前一种失败后才换下一种。第三次拒绝后她的职业微笑消失。她始终端着同一个玻璃杯，杯中水面随手部紧张轻颤。不得让客户签字。",
        "authoritative": "客户连续三次拒绝且最终不签字\n沈乔依次示弱、交换条件、沉默施压\n第三次拒绝后职业微笑消失",
        "continuity": "沈乔始终端着同一个玻璃杯；水面可颤但杯子不能换手",
        "anchors": ["三次拒绝", "玻璃杯", "不签字"],
        "character": {
            "character_id": "沈乔",
            "scene_objective": "让客户签下合同",
            "obstacle_and_stakes": "客户连续拒绝；失败会失去本季度最大订单",
            "tactics": "示弱\n交换条件\n沉默施压",
            "physical_task_and_inertia": "右手一直端同一只玻璃杯；紧张时水面轻颤",
            "voice_lock": "语速稳定、音量偏低；只在她说话时适用",
            "mask_break_trigger": "客户第三次明确拒绝后，职业微笑消失",
            "gaze_and_listening": "客户说话时保持倾听；策略失败后才移开视线重整",
        },
        "checks": ["structured", "count", "base_fields", "anchors", "narrative_fields", "performance_beats", "cue_budget", "tactic_order"],
    },
    {
        "id": "storyboard_silent_mask_break",
        "kind": "storyboard",
        "concept": "12秒四镜无对白戏。母亲在厨房假装平静地切苹果，女儿把退学通知放在桌上；母亲读完后刀停在半空，先看女儿再把刀轻放下，最后把通知推回去。全片任何角色都不能说话，也不能出现字幕。",
        "authoritative": "全片无对白且无字幕\n母亲先切苹果\n读完退学通知后刀停在半空再轻放下",
        "knowledge": "第一镜母亲不知道退学\n第二镜读完通知后母亲知道\n女儿从开场就知道",
        "anchors": ["退学通知", "刀停在半空", "无对白"],
        "silent": True,
        "character": {
            "character_id": "母亲",
            "scene_objective": "维持表面平静并让女儿先解释",
            "obstacle_and_stakes": "退学通知打破日常秩序；立即爆发会终止沟通",
            "tactics": "继续切苹果维持常态\n用停刀等待解释\n把通知推回去要求回应",
            "physical_task_and_inertia": "切苹果的重复节奏先稳定；读完通知后刀停在半空，再轻放下",
            "voice_lock": "本场无对白，禁止生成台词",
            "mask_break_trigger": "读完退学通知",
            "gaze_and_listening": "先看通知，再看女儿；等待女儿反应",
        },
        "checks": ["structured", "count", "base_fields", "anchors", "narrative_fields", "performance_beats", "cue_budget", "silent_contract"],
    },
    {
        "id": "longform_world_cost",
        "kind": "longform",
        "concept": "24秒两段奇幻短片。治疗师阿洛只能在全片使用一次治愈；治愈会永久失去一段童年记忆。第一段他拒绝为轻伤者使用，第二段为濒危妹妹使用后忘记两人童年约定。能力不会恢复，也不能第二次治愈。",
        "authoritative": "阿洛全片只能治愈一次\n第一段拒绝为轻伤者使用\n第二段为濒危妹妹使用",
        "world_rules": "治愈能力每个故事只允许使用一次\n能力使用后不会恢复",
        "costs": "每次治愈永久失去一段童年记忆",
        "continuity": "阿洛左腕有蓝色绷带；第二段治愈后仍保留",
        "anchors": ["只能", "一次", "童年记忆", "不会恢复"],
        "checks": ["structured", "count", "base_fields", "anchors", "gapless_schedule", "world_rule_checks", "knowledge_state", "downstream_status"],
    },
    {
        "id": "longform_knowledge_and_invalidation",
        "kind": "longform",
        "concept": "24秒两段家庭悬疑。女儿林宁从开场知道遗嘱是伪造的，父亲林海在第二段末尾看到水印后才知道。第一段父亲必须按真遗嘱行动。角色圣经阶段刚被修订，因此分场大纲、剧本、资产、表演和提示词都应视为待复核，不能当成已确认事实。",
        "authoritative": "林宁从开场知道遗嘱伪造\n林海在第二段末尾看到水印后才知道\n第一段林海按真遗嘱行动",
        "knowledge": "林宁从开场知道遗嘱伪造\n林海第一段不知道，第二段末尾看到水印后才知道",
        "continuity": "伪造遗嘱右下角有淡蓝水印",
        "changed_stage": "02-characters | 02 角色圣经",
        "confirmed_stages": "01 02 04 05 06 07 08",
        "anchors": ["林宁", "林海", "水印", "第二段末尾"],
        "checks": ["structured", "count", "base_fields", "anchors", "gapless_schedule", "world_rule_checks", "knowledge_state", "downstream_status"],
    },
]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _extract_payload(text: Any) -> dict[str, Any]:
    parsed = creative._extract_json(str(text or ""))
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _hash_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _provider_name(model: str) -> str:
    return f"Seedance NZ OpenAI-compatible endpoint / {model}"


def _benchmark_provider_config(max_tokens: int, model: str = BENCHMARK_MODEL) -> dict[str, Any]:
    return shared_provider.build_provider_config(
        provider=shared_provider.PROVIDER_OPENAI,
        openai_base_url=BENCHMARK_BASE_URL,
        custom_model=model,
        temperature_policy="AUTO（兼容策略）",
        extra_parameters_json=json.dumps({"max_tokens": int(max_tokens)}),
    )


def _contains_all(text: str, anchors: Sequence[str]) -> bool:
    return all(str(anchor).casefold() in text.casefold() for anchor in anchors)


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return value is not None


def _base_shot_fields(shots: list[dict[str, Any]]) -> bool:
    required = ("index", "start_seconds", "end_seconds", "purpose", "subject_action", "camera")
    return bool(shots) and all(all(_nonempty(shot.get(field)) for field in required) for shot in shots)


def _narrative_fields(shots: list[dict[str, Any]]) -> bool:
    required = ("causal_link", "value_before", "value_after", "scene_necessity")
    return bool(shots) and all(
        all(_nonempty(shot.get(field)) for field in required)
        and isinstance(shot.get("setup_elements"), list)
        and isinstance(shot.get("payoff_elements"), list)
        for shot in shots
    )


def _matched_setup_payoff(shots: list[dict[str, Any]], anchor: str = "") -> bool:
    setup = {
        str(item).strip().casefold()
        for shot in shots
        for item in shot.get("setup_elements", [])
        if str(item).strip()
    }
    payoff = {
        str(item).strip().casefold()
        for shot in shots
        for item in shot.get("payoff_elements", [])
        if str(item).strip()
    }
    if not setup.intersection(payoff):
        return False
    if not anchor:
        return True
    needle = anchor.casefold()
    return any(needle in item or item in needle for item in setup.intersection(payoff))


def _silent_contract(shots: list[dict[str, Any]]) -> bool:
    spoken = []
    for shot in shots:
        value = str(shot.get("dialogue_or_text") or "").strip()
        if value and value.casefold() not in {"none", "n/a", "无", "无对白", "无台词", "无对白与字幕"}:
            spoken.append(value)
    return not spoken


def _performance_beats(shots: list[dict[str, Any]]) -> bool:
    return sum(bool(str(shot.get("primary_performance_beat") or "").strip()) for shot in shots) >= 2


def _cue_budget(shots: list[dict[str, Any]]) -> bool:
    populated = 0
    for shot in shots:
        cues = shot.get("observable_cues")
        if not isinstance(cues, list):
            return False
        if cues:
            populated += 1
        if len(cues) > 3:
            return False
    return populated >= 2


def _tactic_order(text: str) -> bool:
    positions = [text.find(item) for item in ("示弱", "交换条件", "沉默施压")]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


def _score(case: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(case["kind"])
    rendered = _json(payload)
    checks: dict[str, bool] = {
        "structured": bool(payload.get("structured_response", bool(payload)))
    }
    if kind == "storyboard":
        shots = [dict(item) for item in payload.get("shots", []) if isinstance(item, Mapping)]
        checks.update({
            "count": len(shots) == 4,
            "base_fields": _base_shot_fields(shots),
            "anchors": _contains_all(rendered, case.get("anchors", [])),
            "narrative_fields": _narrative_fields(shots),
            "causal_chain": len(shots) == 4 and all(_nonempty(shot.get("causal_link")) for shot in shots[1:]),
            "value_shift": sum(
                str(shot.get("value_before") or "").strip() != str(shot.get("value_after") or "").strip()
                and _nonempty(shot.get("value_before")) and _nonempty(shot.get("value_after"))
                for shot in shots
            ) >= 2,
            "scene_necessity": len(shots) == 4 and all(_nonempty(shot.get("scene_necessity")) for shot in shots),
            "setup_payoff": _matched_setup_payoff(shots, str(case.get("setup_payoff_anchor") or "")),
            "performance_beats": _performance_beats(shots),
            "cue_budget": _cue_budget(shots),
            "tactic_order": _tactic_order(rendered),
            "silent_contract": _silent_contract(shots),
        })
    else:
        segments = [dict(item) for item in payload.get("segments", []) if isinstance(item, Mapping)]
        schedule_ok = len(segments) == 2
        if schedule_ok:
            try:
                schedule_ok = (
                    float(segments[0].get("start_seconds")) == 0
                    and float(segments[0].get("end_seconds")) == 12
                    and float(segments[1].get("start_seconds")) == 12
                    and float(segments[1].get("end_seconds")) == 24
                )
            except (TypeError, ValueError):
                schedule_ok = False
        checks.update({
            "count": len(segments) == 2,
            "base_fields": bool(segments) and all(
                _nonempty(item.get("start_state"))
                and _nonempty(item.get("end_state"))
                and _nonempty(item.get("h3_prompt"))
                and _nonempty(item.get("seedance20_prompt"))
                for item in segments
            ),
            "anchors": _contains_all(rendered, case.get("anchors", [])),
            "gapless_schedule": schedule_ok,
            "world_rule_checks": bool(segments) and all(isinstance(item.get("world_rule_checks"), list) and item["world_rule_checks"] for item in segments),
            "knowledge_state": bool(segments) and all(isinstance(item.get("knowledge_state"), Mapping) and item["knowledge_state"] for item in segments),
            "downstream_status": bool(segments) and all(isinstance(item.get("downstream_status"), list) for item in segments)
            and any(item.get("downstream_status") for item in segments),
        })
    selected = {name: bool(checks.get(name, False)) for name in case["checks"]}
    passed_count = sum(selected.values())
    return {
        "score": round(100 * passed_count / len(selected)),
        "passed_checks": [name for name, passed in selected.items() if passed],
        "failed_checks": [name for name, passed in selected.items() if not passed],
        "checks": selected,
    }


def _project_state(case: Mapping[str, Any]) -> dict[str, Any]:
    continuity = [str(case.get("continuity") or "").strip(), *[str(item) for item in case.get("anchors", [])]]
    result = film.T8FilmProjectRouter.execute(
        project_title=f"A/B {case['id']}",
        mode=film.PROJECT_MODES[3],
        target_stage=film.STAGE_OPTIONS[-1],
        project_brief=case["concept"],
        authoritative_inputs=case.get("authoritative", ""),
        confirmed_stages=case.get("confirmed_stages", "01 02 03 04 05 06 07 08"),
        changed_stage=case.get("changed_stage", film.NO_CHANGED_STAGE),
        revision_note="A/B contract verification",
        world_rules=case.get("world_rules", ""),
        ability_costs_and_limits=case.get("costs", ""),
        knowledge_gaps=case.get("knowledge", ""),
        continuity_anchors="\n".join(item for item in continuity if item),
    )
    return result[0]


def _character_bible(case: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(case.get("character") or {})
    if not values:
        return {}
    return film.build_character_performance_bible(**values)


def _baseline(
    case: Mapping[str, Any],
    api_key: str,
    seed: int,
    model: str = BENCHMARK_MODEL,
) -> tuple[dict[str, Any], str]:
    if case["kind"] == "storyboard":
        provider_config = _benchmark_provider_config(STORYBOARD_MAX_TOKENS, model)
        user = "\n".join([
            "Output language: 中文",
            "Target model: MiniMax H3 + Seedance 2.0",
            "Duration: 12 seconds",
            "Shot count: 4",
            "Selected creative direction:",
            str(case["concept"]),
        ])
        result = creative._run_completion(
            system=BASELINE_STORYBOARD_SYSTEM,
            user=user,
            api_key=api_key,
            provider_config=provider_config,
            rewrite_mode="balanced",
            seed=seed,
            max_output_tokens=STORYBOARD_MAX_TOKENS,
        )
        return _extract_payload(result.text), result.text
    schedule = creative._segment_schedule(24, 12)
    user = "\n".join([
        "Output language: 中文",
        "Target model: MiniMax H3 + Seedance 2.0",
        "Total duration: 24 seconds",
        "Authoritative deterministic segment schedule:",
        _json(schedule),
        "Whole-film concept/script:",
        str(case["concept"]),
    ])
    provider_config = _benchmark_provider_config(LONGFORM_MAX_TOKENS, model)
    result = creative._run_completion(
        system=BASELINE_LONGFORM_SYSTEM,
        user=user,
        api_key=api_key,
        provider_config=provider_config,
        rewrite_mode="balanced",
        seed=seed,
        max_output_tokens=LONGFORM_MAX_TOKENS,
    )
    return _extract_payload(result.text), result.text


def _enhanced(
    case: Mapping[str, Any],
    api_key: str,
    seed: int,
    model: str = BENCHMARK_MODEL,
) -> tuple[dict[str, Any], str]:
    state = _project_state(case)
    if case["kind"] == "storyboard":
        provider_config = _benchmark_provider_config(STORYBOARD_MAX_TOKENS, model)
        result = creative.T8StoryboardPack.execute(
            concept=case["concept"],
            film_project_state=state,
            character_performance_bible=_character_bible(case) or None,
            performance_director_config=performance.build_performance_director_config(performance.PERFORMANCE_STRONG),
            model_target=creative.MODEL_TARGETS[2],
            duration_seconds=12,
            shot_count="4",
            rewrite_mode="balanced",
            output_language="中文",
            api_key=api_key,
            provider_config=provider_config,
            seed=seed,
        )
        payload = json.loads(result[1])
        return payload, _json(payload)
    provider_config = _benchmark_provider_config(LONGFORM_MAX_TOKENS, model)
    result = creative.T8LongFormPlanner.execute(
        concept=case["concept"],
        film_project_state=state,
        model_target=creative.MODEL_TARGETS[2],
        total_duration_seconds=24,
        segment_duration_seconds=12,
        continuity_anchors=case.get("continuity", ""),
        rewrite_mode="balanced",
        output_language="中文",
        api_key=api_key,
        provider_config=provider_config,
        seed=seed,
    )
    h3_payload = json.loads(result[1])
    seedance_payload = json.loads(result[2])
    h3_by_index = {item["segment_index"]: item for item in h3_payload.get("segments", [])}
    segments = []
    for item in seedance_payload.get("segments", []):
        merged = dict(h3_by_index.get(item.get("segment_index"), {}))
        merged.update(item)
        segments.append(merged)
    payload = {**h3_payload, "segments": segments}
    return payload, _json(payload)


def _resolve_api_key(*, credential_alias: str = "", prompt_for_key: bool = True) -> str:
    value = os.environ.get("SEEDANCE_API_KEY", "").strip()
    if value:
        return value
    if credential_alias:
        from credential_store import get_credential

        return get_credential(credential_alias)
    if prompt_for_key:
        value = getpass.getpass("Seedance API key (hidden, memory only): ").strip()
        if value:
            return value
    raise RuntimeError("SEEDANCE_API_KEY is not set and no credential alias or hidden interactive key was provided.")


def _contract_hash(cases: Sequence[Mapping[str, Any]], model: str = BENCHMARK_MODEL) -> str:
    return _hash_text(
        BENCHMARK_SCHEMA
        + CONTRACT_REVISION
        + model
        + str(STORYBOARD_MAX_TOKENS)
        + str(LONGFORM_MAX_TOKENS)
        + _json(list(cases))
    )


def _baseline_contract_hash(case: Mapping[str, Any], model: str = BENCHMARK_MODEL) -> str:
    system = BASELINE_STORYBOARD_SYSTEM if case.get("kind") == "storyboard" else BASELINE_LONGFORM_SYSTEM
    token_limit = STORYBOARD_MAX_TOKENS if case.get("kind") == "storyboard" else LONGFORM_MAX_TOKENS
    return _hash_text(BENCHMARK_SCHEMA + model + system + str(token_limit) + _json(dict(case)))


def _repository_metadata() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    version = "unknown"
    try:
        source = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', source, re.MULTILINE)
        if match:
            version = match.group(1)
    except (OSError, UnicodeError):
        pass
    commit = "unknown"
    dirty: bool | None = None
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_version": version,
        "git_commit": commit,
        "git_dirty": dirty,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _load_checkpoint(path: Path, contract_hash: str) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": BENCHMARK_SCHEMA, "contract_sha256": contract_hash, "cases": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"schema_version": BENCHMARK_SCHEMA, "contract_sha256": contract_hash, "cases": {}}
    if payload.get("schema_version") != BENCHMARK_SCHEMA or payload.get("contract_sha256") != contract_hash:
        return {"schema_version": BENCHMARK_SCHEMA, "contract_sha256": contract_hash, "cases": {}}
    if not isinstance(payload.get("cases"), dict):
        payload["cases"] = {}
    return payload


def _load_reusable_baselines(
    path: Path | None,
    cases: Sequence[Mapping[str, Any]],
    *,
    model: str = BENCHMARK_MODEL,
) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if payload.get("provider") != _provider_name(model) or payload.get("response_text_stored") is not False:
        return {}
    expected = {str(case["id"]): 2026083000 + index for index, case in enumerate(cases, 1)}
    expected_contracts = {str(case["id"]): _baseline_contract_hash(case, model) for case in cases}
    reusable: dict[str, Any] = {}
    for item in payload.get("cases", []):
        if not isinstance(item, Mapping):
            continue
        case_id = str(item.get("case_id") or "")
        baseline = item.get("baseline")
        if (
            case_id in expected
            and item.get("seed") == expected[case_id]
            and item.get("baseline_contract_sha256") == expected_contracts[case_id]
            and isinstance(baseline, Mapping)
        ):
            reusable[case_id] = dict(baseline)
    return reusable


def _save_checkpoint(path: Path, payload: Mapping[str, Any]) -> None:
    safe = dict(payload)
    safe["response_text_stored"] = False
    safe["credentials_stored"] = False
    _validate_redacted(safe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _variant_record(case: Mapping[str, Any], payload: Mapping[str, Any], text: str) -> dict[str, Any]:
    return {
        **_score(case, payload),
        "sha256": _hash_text(text),
        "character_count": len(text),
    }


def run_paid_ab(
    *,
    confirm_paid: bool = False,
    credential_alias: str = "",
    prompt_for_key: bool = True,
    cases: Sequence[Mapping[str, Any]] = CASES,
    checkpoint_path: Path | None = DEFAULT_CHECKPOINT,
    baseline_report_path: Path | None = DEFAULT_REPORT,
    model: str = BENCHMARK_MODEL,
) -> dict[str, Any]:
    if not confirm_paid:
        raise RuntimeError("Refusing to call paid endpoints without explicit confirmation.")
    if not 5 <= len(cases) <= 10:
        raise RuntimeError("The paid A/B suite must contain 5-10 groups.")
    model = str(model or "").strip()
    if not model:
        raise RuntimeError("Benchmark model ID cannot be empty.")
    api_key = _resolve_api_key(credential_alias=credential_alias, prompt_for_key=prompt_for_key)
    contract_hash = _contract_hash(cases, model)
    checkpoint = _load_checkpoint(checkpoint_path, contract_hash) if checkpoint_path else {
        "schema_version": BENCHMARK_SCHEMA,
        "contract_sha256": contract_hash,
        "cases": {},
    }
    reusable_baselines = _load_reusable_baselines(baseline_report_path, cases, model=model)
    results = []
    live_requests_executed = 0
    for index, case in enumerate(cases, 1):
        seed = 2026083000 + index
        saved = dict(checkpoint["cases"].get(case["id"]) or {})
        if not isinstance(saved.get("baseline"), Mapping) and case["id"] in reusable_baselines:
            saved["baseline"] = reusable_baselines[case["id"]]
        baseline_score = saved.get("baseline")
        if not isinstance(baseline_score, Mapping):
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=baseline STATUS=start", flush=True)  # noqa: T201
            baseline_payload, baseline_text = _baseline(case, api_key, seed, model)
            live_requests_executed += 1
            baseline_score = _variant_record(case, baseline_payload, baseline_text)
            saved["baseline"] = baseline_score
            saved["kind"] = case["kind"]
            saved["seed"] = seed
            checkpoint["cases"][case["id"]] = saved
            if checkpoint_path:
                _save_checkpoint(checkpoint_path, checkpoint)
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=baseline STATUS=done SCORE={baseline_score['score']}", flush=True)  # noqa: T201
        else:
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=baseline STATUS=checkpoint SCORE={baseline_score['score']}", flush=True)  # noqa: T201
        enhanced_score = saved.get("enhanced")
        if not isinstance(enhanced_score, Mapping):
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=enhanced STATUS=start", flush=True)  # noqa: T201
            enhanced_payload, enhanced_text = _enhanced(case, api_key, seed, model)
            live_requests_executed += 1
            enhanced_score = _variant_record(case, enhanced_payload, enhanced_text)
            saved["enhanced"] = enhanced_score
            checkpoint["cases"][case["id"]] = saved
            if checkpoint_path:
                _save_checkpoint(checkpoint_path, checkpoint)
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=enhanced STATUS=done SCORE={enhanced_score['score']}", flush=True)  # noqa: T201
        else:
            print(f"AB_GROUP={index}/{len(cases)} CASE={case['id']} VARIANT=enhanced STATUS=checkpoint SCORE={enhanced_score['score']}", flush=True)  # noqa: T201
        results.append({
            "case_id": case["id"],
            "kind": case["kind"],
            "seed": seed,
            "baseline_contract_sha256": _baseline_contract_hash(case, model),
            "baseline": {
                **baseline_score,
            },
            "enhanced": {
                **enhanced_score,
            },
            "score_delta": enhanced_score["score"] - baseline_score["score"],
        })
    baseline_average = round(sum(item["baseline"]["score"] for item in results) / len(results))
    enhanced_average = round(sum(item["enhanced"]["score"] for item in results) / len(results))
    return {
        "suite": SUITE_NAME,
        "schema_version": BENCHMARK_SCHEMA,
        "contract_sha256": contract_hash,
        "provider": _provider_name(model),
        "run_metadata": {
            **_repository_metadata(),
            "contract_revision": CONTRACT_REVISION,
            "model": model,
            "base_url": BENCHMARK_BASE_URL,
            "temperature_policy": "AUTO（兼容策略）",
            "storyboard_max_tokens": STORYBOARD_MAX_TOKENS,
            "longform_max_tokens": LONGFORM_MAX_TOKENS,
            "seed_policy": "2026083000 + one-based case index",
            "test_scope": "prompt-structure contract only; no video render was requested",
        },
        "group_count": len(results),
        "paid_request_count": len(results) * 2,
        "paid_requests_executed_this_run": live_requests_executed,
        "paid_responses_reused_from_matching_report_or_checkpoint": len(results) * 2 - live_requests_executed,
        "unscored_transport_observations": UNSCORED_TRANSPORT_OBSERVATIONS,
        "baseline_average": baseline_average,
        "enhanced_average": enhanced_average,
        "average_delta": enhanced_average - baseline_average,
        "all_enhanced_scores_at_least_baseline": all(item["score_delta"] >= 0 for item in results),
        "response_text_stored": False,
        "credentials_stored": False,
        "scoring_note": "Deterministic contract checks only; not an objective score of artistic quality.",
        "cases": results,
    }


def _validate_redacted(report: Mapping[str, Any]) -> None:
    encoded = json.dumps(report, ensure_ascii=False)
    if re.search(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}", encoded):
        raise RuntimeError("Refusing to save a report containing an API-key-like value.")
    if report.get("response_text_stored") is not False or report.get("credentials_stored") is not False:
        raise RuntimeError("Refusing to save a non-redacted A/B report.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 5-10 paired paid film-workflow contract checks.")
    parser.add_argument("--confirm-paid", action="store_true", help="Confirm 12 potentially billable requests.")
    parser.add_argument("--credential-alias", default="", help="Optional local credential-store alias; the secret is never printed.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Write only the redacted score report.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Ignored, redacted progress file used to resume incomplete paid runs.")
    parser.add_argument("--reuse-baselines-from", type=Path, default=DEFAULT_REPORT, help="Reuse matching redacted baseline scores while retesting only a changed enhanced contract.")
    parser.add_argument("--model", default=BENCHMARK_MODEL, help="OpenAI-compatible model ID; run once per model for cross-model evidence.")
    args = parser.parse_args(argv)
    report = run_paid_ab(
        confirm_paid=args.confirm_paid,
        credential_alias=args.credential_alias,
        checkpoint_path=args.checkpoint,
        baseline_report_path=args.reuse_baselines_from,
        model=args.model,
    )
    _validate_redacted(report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.checkpoint.is_file():
        args.checkpoint.unlink()
    print("FILM_WORKFLOW_PAID_AB=PASS")  # noqa: T201
    print(json.dumps({key: report[key] for key in (  # noqa: T201
        "group_count", "paid_request_count", "baseline_average", "enhanced_average", "average_delta",
        "all_enhanced_scores_at_least_baseline", "paid_requests_executed_this_run",
        "paid_responses_reused_from_matching_report_or_checkpoint",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
