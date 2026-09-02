from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, Mapping

from comfy_api.latest import io


FILM_PROJECT_SCHEMA = "t8-film-project-state/v1"
CHARACTER_PERFORMANCE_SCHEMA = "t8-character-performance-bible/v1"
CHARACTER_PERFORMANCE_SET_SCHEMA = "t8-character-performance-bible-set/v1"

T8FilmProjectStateIO = io.Custom("T8_FILM_PROJECT_STATE")
T8CharacterPerformanceBibleIO = io.Custom("T8_CHARACTER_PERFORMANCE_BIBLE")

PROJECT_MODES = [
    "全流程（从当前阶段继续）",
    "指定阶段（只做本阶段）",
    "接力（使用已有权威资料）",
    "修订（保留版本并标记影响）",
]

STAGES = [
    ("01-synopsis", "01 概念锚定"),
    ("02-characters", "02 角色圣经"),
    ("03-worldbuilding", "03 世界规则（可选）"),
    ("04-treatment", "04 分场大纲"),
    ("05-screenplay", "05 剧本"),
    ("06-assets", "06 图像资产"),
    ("07-acting", "07 表演设计"),
    ("08-prompt", "08 H3 / Seedance 提示词"),
]
STAGE_OPTIONS = [f"{stage_id} | {label}" for stage_id, label in STAGES]
STAGE_IDS = [stage_id for stage_id, _label in STAGES]
STAGE_LABELS = dict(STAGES)
NO_CHANGED_STAGE = "无（不触发失效传播）"
CHANGED_STAGE_OPTIONS = [NO_CHANGED_STAGE, *STAGE_OPTIONS]

STAGE_DEPENDENCIES = {
    "01-synopsis": [],
    "02-characters": ["01-synopsis"],
    "03-worldbuilding": ["01-synopsis", "02-characters"],
    "04-treatment": ["01-synopsis", "02-characters", "03-worldbuilding"],
    "05-screenplay": ["01-synopsis", "02-characters", "03-worldbuilding", "04-treatment"],
    "06-assets": ["02-characters", "03-worldbuilding", "05-screenplay"],
    "07-acting": ["02-characters", "05-screenplay", "06-assets"],
    "08-prompt": ["03-worldbuilding", "05-screenplay", "06-assets", "07-acting"],
}

SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
CLEAR_INHERITED_MARKERS = frozenset({"[清空继承]", "[CLEAR_INHERITED]"})


class FilmWorkflowError(ValueError):
    pass


def _clean_text(value: Any, *, limit: int = 20_000) -> str:
    text = str(value or "").strip()
    if SECRET_RE.search(text):
        raise FilmWorkflowError("Remove the API-key-like secret from film-project text.")
    return text[:limit]


def _requests_clear(value: Any) -> bool:
    """Return True only for an explicit whole-field inheritance-clear marker."""
    return str(value or "").strip().upper() in {
        marker.upper() for marker in CLEAR_INHERITED_MARKERS
    }


def _stage_id(value: Any, *, allow_none: bool = False) -> str:
    text = str(value or "").strip()
    if allow_none and (not text or text == NO_CHANGED_STAGE):
        return ""
    candidate = text.split(" | ", 1)[0].strip()
    if candidate not in STAGE_IDS:
        raise FilmWorkflowError(f"Unsupported film stage: {text}")
    return candidate


def _line_items(value: Any, *, limit: int = 24) -> list[str]:
    text = _clean_text(value)
    items = []
    for line in re.split(r"[\r\n]+", text):
        # A decimal/timing fact such as ``1.5秒后`` is authoritative content,
        # not an ordered-list prefix.  Only a dot followed by whitespace, or
        # an unambiguous closing punctuation, may introduce a numbered item.
        item = re.sub(r"^\s*(?:[-*•]\s+|\d+\.\s+|\d+[)、]\s*)", "", line).strip()
        if item and item not in items:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def _confirmed_stage_ids(value: Any) -> list[str]:
    text = _clean_text(value, limit=2_000)
    found = []
    for stage_id in STAGE_IDS:
        if re.search(rf"(?<![A-Za-z0-9-]){re.escape(stage_id)}(?![A-Za-z0-9-])", text):
            found.append(stage_id)
            continue
        number = stage_id.split("-", 1)[0]
        if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", text):
            found.append(stage_id)
    return found


def downstream_stages(changed_stage: str) -> list[str]:
    changed = _stage_id(changed_stage, allow_none=True)
    if not changed:
        return []
    affected = []
    frontier = [changed]
    while frontier:
        source = frontier.pop(0)
        for stage_id in STAGE_IDS:
            if source in STAGE_DEPENDENCIES[stage_id] and stage_id not in affected:
                affected.append(stage_id)
                frontier.append(stage_id)
    return [stage_id for stage_id in STAGE_IDS if stage_id in affected]


def coerce_project_state(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or value.get("schema_version") != FILM_PROJECT_SCHEMA:
        raise FilmWorkflowError("Connected film_project_state has an unsupported schema.")
    return dict(value)


def project_state_prompt_context(value: Any, *, target_stage: str | None = None) -> str:
    state = coerce_project_state(value)
    if not state:
        return ""
    stage_id = _stage_id(target_stage or state.get("target_stage"))
    compact = {
        "contract": "USER-AUTHORITATIVE FILM PROJECT STATE; never invent missing upstream facts",
        "project_title": state.get("project_title", ""),
        "revision": state.get("revision"),
        "mode": state.get("mode", ""),
        "target_stage": stage_id,
        "stage_label": STAGE_LABELS[stage_id],
        "project_brief": state.get("project_brief", ""),
        "authoritative_inputs": state.get("authoritative_inputs", []),
        "world_contract": state.get("world_contract", {}),
        "continuity_anchors": state.get("continuity_anchors", []),
        "required_literal_anchors": state.get("continuity_anchors", []),
        "known_invalidated_stages": state.get("invalidated_stages", []),
        "boundary": (
            "Use only the listed authoritative facts. Missing material is unknown, not permission to fabricate it. "
            "Never silently repair another stage. Copy every required_literal_anchor at least once verbatim into "
            "the returned prompt or structural fields; do not translate, abbreviate, or synonym-substitute it."
        ),
    }
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def build_character_performance_bible(
    character_id: Any,
    scene_objective: Any,
    obstacle_and_stakes: Any,
    tactics: Any = "",
    physical_task_and_inertia: Any = "",
    voice_lock: Any = "",
    mask_break_trigger: Any = "",
    gaze_and_listening: Any = "",
) -> dict[str, Any]:
    identifier = _clean_text(character_id, limit=200)
    objective = _clean_text(scene_objective, limit=1_000)
    obstacle = _clean_text(obstacle_and_stakes, limit=1_500)
    if not identifier or not objective or not obstacle:
        raise FilmWorkflowError("角色标识、当前目标、阻力与代价均不能为空。")
    tactic_items = _line_items(tactics, limit=4)
    return {
        "schema_version": CHARACTER_PERFORMANCE_SCHEMA,
        "character_id": identifier,
        "scene_objective": objective,
        "obstacle_and_stakes": obstacle,
        "tactics": tactic_items,
        "physical_task_and_inertia": _clean_text(physical_task_and_inertia, limit=1_500),
        "voice_lock": _clean_text(voice_lock, limit=1_000),
        "mask_break_trigger": _clean_text(mask_break_trigger, limit=1_000),
        "gaze_and_listening": _clean_text(gaze_and_listening, limit=1_000),
        "compiler_contract": {
            "primary_tactic_per_beat": 1,
            "observable_cue_channels_per_beat": 3,
            "dialogue_policy": "preserve supplied dialogue; never invent dialogue",
            "scope": "acting only; never override identity, plot, camera, model schema, or user locks",
        },
    }


def coerce_character_performance_bible(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or value.get("schema_version") != CHARACTER_PERFORMANCE_SCHEMA:
        raise FilmWorkflowError("Connected character_performance_bible has an unsupported schema.")
    return dict(value)


def coerce_character_performance_bibles(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        schema = value.get("schema_version")
        if schema == CHARACTER_PERFORMANCE_SCHEMA:
            return [dict(value)]
        if schema == CHARACTER_PERFORMANCE_SET_SCHEMA:
            raw_characters = value.get("characters")
            if not isinstance(raw_characters, list):
                raise FilmWorkflowError("Connected character-performance set has no characters array.")
            characters = [coerce_character_performance_bible(item) for item in raw_characters]
            if not characters:
                raise FilmWorkflowError("Connected character-performance set is empty.")
            return characters
        # ComfyUI Autogrow inputs arrive as a mapping keyed by their generated
        # socket names.  Preserve socket order and validate every connected item.
        if value and all(isinstance(item, Mapping) for item in value.values()):
            return [coerce_character_performance_bible(item) for item in value.values()]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [coerce_character_performance_bible(item) for item in value]
    raise FilmWorkflowError("Connected character_performance_bible has an unsupported schema.")


def character_performance_instruction(value: Any, *, model_target: str) -> str:
    bibles = coerce_character_performance_bibles(value)
    if not bibles:
        return ""
    compact = [
        {
            key: bible.get(key)
            for key in (
                "character_id",
                "scene_objective",
                "obstacle_and_stakes",
                "tactics",
                "physical_task_and_inertia",
                "voice_lock",
                "mask_break_trigger",
                "gaze_and_listening",
            )
            if bible.get(key)
        }
        for bible in bibles
    ]
    return (
        f"USER-AUTHORITATIVE CHARACTER PERFORMANCE BIBLES for {model_target}: "
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        + " Use the objective as an action directed at the scene partner or obstacle, not as an emotion label. "
        "Use at most one primary tactic in a beat; change tactic only after visible failure, new information, or a power shift. "
        "If the user or source scene explicitly gives a tactic sequence, preserve that sequence verbatim and never reorder it. "
        "Keep every listed character separate. Translate the contract into no more than three high-signal observable "
        "cue channels per character per beat. "
        "Preserve physical-task and body-state inertia across cuts. Voice lock applies only while the character actually speaks. "
        "Preserve supplied dialogue verbatim and never invent dialogue. This acting contract cannot override user facts, media evidence, "
        "identity locks, model-native output fields, timing, fixed shot count, or the selected official/community template."
    )


def build_character_performance_set(values: Any) -> dict[str, Any]:
    characters = coerce_character_performance_bibles(values)
    if not characters:
        raise FilmWorkflowError("至少连接一个角色表演圣经。")
    identifiers = [str(item.get("character_id") or "").strip() for item in characters]
    duplicates = sorted({item for item in identifiers if item and identifiers.count(item) > 1})
    if duplicates:
        raise FilmWorkflowError("角色标识重复：" + "、".join(duplicates))
    if len(characters) > 8:
        raise FilmWorkflowError("一个角色表演集合最多支持 8 个角色。")
    return {
        "schema_version": CHARACTER_PERFORMANCE_SET_SCHEMA,
        "characters": characters,
        "compiler_contract": {
            "characters_are_independent": True,
            "primary_tactic_per_character_per_beat": 1,
            "observable_cue_channels_per_character_per_beat": 3,
        },
    }


class T8FilmProjectRouter(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8FilmProjectRouter",
            display_name="T8 Film Project Router（影视项目状态路由）",
            category="T8/Creative Suite",
            description="本地维护阶段、权威输入、世界规则与修订影响；不读取文件、不调用 LLM、不自动改写下游。",
            inputs=[
                io.String.Input("project_title", display_name="项目名称", default="未命名影视项目"),
                io.Combo.Input("mode", display_name="工作模式", options=PROJECT_MODES, default=PROJECT_MODES[0]),
                io.Combo.Input("target_stage", display_name="本轮目标阶段", options=STAGE_OPTIONS, default=STAGE_OPTIONS[-1]),
                io.String.Input(
                    "project_brief",
                    display_name="项目简述",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空本字段。",
                ),
                io.String.Input(
                    "authoritative_inputs",
                    display_name="本轮权威输入（每行一项）",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空全部权威输入。",
                ),
                io.String.Input(
                    "confirmed_stages",
                    display_name="已确认阶段编号",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可清空已确认阶段。",
                ),
                io.Combo.Input(
                    "changed_stage",
                    display_name="本轮修改的上游阶段",
                    options=CHANGED_STAGE_OPTIONS,
                    default=NO_CHANGED_STAGE,
                ),
                io.String.Input("revision_note", display_name="修订说明", multiline=True, default=""),
                io.String.Input(
                    "world_rules",
                    display_name="世界硬规则",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空本字段。",
                ),
                io.String.Input(
                    "ability_costs_and_limits",
                    display_name="能力代价与不可做事项",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空本字段。",
                ),
                io.String.Input(
                    "knowledge_gaps",
                    display_name="人物知情差",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空本字段。",
                ),
                io.String.Input(
                    "continuity_anchors",
                    display_name="连续性锚点",
                    multiline=True,
                    default="",
                    tooltip="连接上一版时留空表示继承；输入 [清空继承] 可显式清空全部连续性锚点。",
                ),
                io.String.Input(
                    "previous_state_json",
                    display_name="上一版状态 JSON（可选）",
                    multiline=True,
                    optional=True,
                    default="",
                    advanced=True,
                ),
                T8FilmProjectStateIO.Input(
                    "previous_state",
                    display_name="上一版项目状态（可选，推荐直连）",
                    optional=True,
                    tooltip=(
                        "直接连接上一版 Router 的 film_project_state；与 JSON 同时提供时必须内容一致。"
                        "空白字段自动继承；在需要清空的对应字段输入 [清空继承]。"
                    ),
                ),
            ],
            outputs=[
                T8FilmProjectStateIO.Output(display_name="film_project_state"),
                io.String.Output(display_name="active_stage_context"),
                io.String.Output(display_name="project_state_json"),
                io.String.Output(display_name="invalidation_report_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        project_title,
        mode,
        target_stage,
        project_brief="",
        authoritative_inputs="",
        confirmed_stages="",
        changed_stage=NO_CHANGED_STAGE,
        revision_note="",
        world_rules="",
        ability_costs_and_limits="",
        knowledge_gaps="",
        continuity_anchors="",
        previous_state_json="",
        previous_state=None,
    ) -> io.NodeOutput:
        if mode not in PROJECT_MODES:
            raise FilmWorkflowError(f"Unsupported project mode: {mode}")
        target = _stage_id(target_stage)
        changed = _stage_id(changed_stage, allow_none=True)
        previous = coerce_project_state(previous_state)
        previous_text = _clean_text(previous_state_json, limit=100_000)
        if previous_text:
            try:
                candidate = json.loads(previous_text)
            except json.JSONDecodeError as error:
                raise FilmWorkflowError("上一版状态 JSON 无法解析。") from error
            json_previous = coerce_project_state(candidate)
            if previous and previous != json_previous:
                raise FilmWorkflowError("直连上一版状态与上一版状态 JSON 内容不一致，请只保留一个来源。")
            previous = json_previous
        try:
            previous_revision = int(previous.get("revision", 0) or 0)
        except (TypeError, ValueError) as error:
            raise FilmWorkflowError("上一版项目状态中的 revision 必须是非负整数。") from error
        if previous_revision < 0:
            raise FilmWorkflowError("上一版项目状态中的 revision 必须是非负整数。")
        revision = previous_revision + 1
        inherit = bool(previous)
        cleared_fields: list[str] = []

        def inherited_text(current: Any, key: str, *, fallback: str = "") -> str:
            if _requests_clear(current):
                cleared_fields.append(key)
                return ""
            cleaned = _clean_text(current)
            if cleaned or not inherit:
                return cleaned
            return _clean_text(previous.get(key, fallback))

        def inherited_lines(current: Any, key: str, *, nested: str | None = None) -> list[str]:
            if _requests_clear(current):
                cleared_fields.append(key)
                return []
            cleaned = _line_items(current)
            if cleaned or not inherit:
                return cleaned
            source: Any = previous
            if nested:
                source = previous.get(nested, {}) if isinstance(previous.get(nested), Mapping) else {}
            value = source.get(key, []) if isinstance(source, Mapping) else []
            return _line_items("\n".join(str(item) for item in value)) if isinstance(value, list) else _line_items(value)

        clear_confirmed = _requests_clear(confirmed_stages)
        confirmed = [] if clear_confirmed else _confirmed_stage_ids(confirmed_stages)
        if clear_confirmed:
            cleared_fields.append("confirmed_stages")
        elif not confirmed and inherit:
            confirmed = [stage for stage in previous.get("confirmed_stages", []) if stage in STAGE_IDS]
        affected = downstream_stages(changed)
        confirmed_affected = [stage for stage in affected if stage in confirmed]
        state = {
            "schema_version": FILM_PROJECT_SCHEMA,
            "revision": revision,
            "project_title": (
                _clean_text(previous.get("project_title"), limit=300)
                if inherit and _clean_text(project_title, limit=300) in {"", "未命名影视项目"}
                else _clean_text(project_title, limit=300)
            ) or "未命名影视项目",
            "mode": mode,
            "target_stage": target,
            "target_stage_label": STAGE_LABELS[target],
            "project_brief": inherited_text(project_brief, "project_brief"),
            "authoritative_inputs": inherited_lines(authoritative_inputs, "authoritative_inputs"),
            "confirmed_stages": confirmed,
            "changed_stage": changed,
            "revision_note": _clean_text(revision_note, limit=2_000),
            "world_contract": {
                "rules": inherited_lines(world_rules, "rules", nested="world_contract"),
                "costs_and_limits": inherited_lines(ability_costs_and_limits, "costs_and_limits", nested="world_contract"),
                "knowledge_gaps": inherited_lines(knowledge_gaps, "knowledge_gaps", nested="world_contract"),
            },
            "continuity_anchors": inherited_lines(continuity_anchors, "continuity_anchors"),
            "required_upstream": list(STAGE_DEPENDENCIES[target]),
            "invalidated_stages": affected,
            "confirmed_invalidated_stages": confirmed_affected,
            "cleared_inherited_fields": cleared_fields,
            "status": "awaiting_human_confirmation",
            "policy": {
                "authority_isolation": True,
                "silent_upstream_rewrite": False,
                "automatic_downstream_regeneration": False,
            },
        }
        context = project_state_prompt_context(state, target_stage=target)
        invalidation = {
            "schema_version": FILM_PROJECT_SCHEMA,
            "changed_stage": changed,
            "all_affected_downstream": affected,
            "confirmed_outputs_now_stale": confirmed_affected,
            "action": (
                "review_and_regenerate_only_after_user_confirmation"
                if affected
                else "no_invalidation"
            ),
        }
        status_summary = {
            "revision": revision,
            "target_stage": target,
            "changed_stage": changed,
            "invalidated_stages": affected,
            "confirmed_invalidated_stages": confirmed_affected,
            "cleared_inherited_fields": cleared_fields,
            "source": "direct_state" if previous_state is not None else ("state_json" if previous_text else "new"),
        }
        return io.NodeOutput(
            state,
            context,
            json.dumps(state, ensure_ascii=False, indent=2),
            json.dumps(invalidation, ensure_ascii=False, indent=2),
            ui={"film_project_status": [json.dumps(status_summary, ensure_ascii=False)]},
        )


class T8CharacterPerformanceBible(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CharacterPerformanceBible",
            display_name="T8 Character Performance Bible（角色表演圣经）",
            category="T8/Creative Suite",
            description="把角色目标、阻力、策略、声音与身体惯性编译为轻量表演合同；不调用 LLM。",
            inputs=[
                io.String.Input("character_id", display_name="角色标识 / 素材标签", default="角色A"),
                io.String.Input(
                    "scene_objective",
                    display_name="场景目标 / Scene objective",
                    multiline=True,
                    default="",
                    placeholder=(
                        "场景目标 / Scene objective：想让谁做什么 / Who should do what?\n"
                        "示例 / Example：让妹妹交钥匙 / Get sister to hand over the keys."
                    ),
                ),
                io.String.Input(
                    "obstacle_and_stakes",
                    display_name="阻力与失败代价 / Obstacle & stakes",
                    multiline=True,
                    default="",
                    placeholder=(
                        "阻力与代价 / Obstacle & stakes：阻力 + 失败后果 / Obstacle + cost of failure.\n"
                        "示例 / Example：妹妹拒绝；失败将错过末班车 / She refuses; miss the last train."
                    ),
                ),
                io.String.Input(
                    "tactics",
                    display_name="策略阶梯 / Tactics（每行一个 / one per line）",
                    multiline=True,
                    default="",
                    placeholder=(
                        "策略阶梯 / Tactics：每行一个 / One tactic per line.\n"
                        "示例 / Example：试探询问 / Probe；提出交换 / Trade；直接阻拦 / Block"
                    ),
                ),
                io.String.Input(
                    "physical_task_and_inertia",
                    display_name="手头动作与身体惯性 / Physical task & inertia",
                    multiline=True,
                    default="",
                    placeholder=(
                        "动作与惯性 / Task & inertia：手头动作 + 延续状态 / Task + carried body state.\n"
                        "示例 / Example：收拾行李，同时压住发抖的手 / Pack while steadying trembling hands."
                    ),
                ),
                io.String.Input(
                    "voice_lock",
                    display_name="声音锁定 / Voice lock（仅说话时 / only when speaking）",
                    multiline=True,
                    default="",
                    placeholder=(
                        "声音锁定 / Voice lock：音量、语速、口音或禁区 / Volume, pace, accent, limits.\n"
                        "示例 / Example：低声短句，越紧张越慢 / Low, short, slower under stress."
                    ),
                ),
                io.String.Input(
                    "mask_break_trigger",
                    display_name="面具破裂触发 / Mask-break trigger",
                    multiline=True,
                    default="",
                    placeholder=(
                        "面具破裂 / Mask break：何时失去伪装 / What breaks the mask?\n"
                        "示例 / Example：听见父亲名字时笑容停住 / Smile drops at father's name."
                    ),
                ),
                io.String.Input(
                    "gaze_and_listening",
                    display_name="视线与倾听反应 / Gaze & listening",
                    multiline=True,
                    default="",
                    placeholder=(
                        "视线与倾听 / Gaze & listening：看哪里 + 听后反应 / Gaze + listening response.\n"
                        "示例 / Example：避开姐姐目光；钥匙一响便抬眼 / Avoid her gaze; look up at key sound."
                    ),
                ),
            ],
            outputs=[
                T8CharacterPerformanceBibleIO.Output(display_name="character_performance_bible"),
                io.String.Output(display_name="performance_contract_text"),
                io.String.Output(display_name="performance_bible_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        character_id,
        scene_objective,
        obstacle_and_stakes,
        tactics="",
        physical_task_and_inertia="",
        voice_lock="",
        mask_break_trigger="",
        gaze_and_listening="",
    ) -> io.NodeOutput:
        bible = build_character_performance_bible(
            character_id,
            scene_objective,
            obstacle_and_stakes,
            tactics,
            physical_task_and_inertia,
            voice_lock,
            mask_break_trigger,
            gaze_and_listening,
        )
        contract = character_performance_instruction(bible, model_target="connected downstream model")
        return io.NodeOutput(bible, contract, json.dumps(bible, ensure_ascii=False, indent=2))


class T8CharacterPerformanceBibleStack(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CharacterPerformanceBibleStack",
            display_name="T8 Character Performance Bible Stack（多角色表演集合）",
            category="T8/Creative Suite",
            description="把 1–8 个角色表演圣经合并为同一场景的多角色合同；不调用 LLM。",
            inputs=[
                io.Autogrow.Input(
                    "character_performance_bibles",
                    template=io.Autogrow.TemplatePrefix(
                        input=T8CharacterPerformanceBibleIO.Input("character_performance_bible"),
                        prefix="character_performance_bible_",
                        min=1,
                        max=8,
                    ),
                ),
            ],
            outputs=[
                T8CharacterPerformanceBibleIO.Output(display_name="character_performance_bible_set"),
                io.String.Output(display_name="performance_contract_text"),
                io.String.Output(display_name="performance_bible_set_json"),
            ],
        )

    @classmethod
    def execute(cls, character_performance_bibles=None) -> io.NodeOutput:
        bible_set = build_character_performance_set(character_performance_bibles)
        contract = character_performance_instruction(bible_set, model_target="connected downstream model")
        return io.NodeOutput(bible_set, contract, json.dumps(bible_set, ensure_ascii=False, indent=2))


__all__ = [
    "CHARACTER_PERFORMANCE_SCHEMA",
    "CHARACTER_PERFORMANCE_SET_SCHEMA",
    "CHANGED_STAGE_OPTIONS",
    "CLEAR_INHERITED_MARKERS",
    "FILM_PROJECT_SCHEMA",
    "FilmWorkflowError",
    "NO_CHANGED_STAGE",
    "PROJECT_MODES",
    "STAGE_DEPENDENCIES",
    "STAGE_IDS",
    "STAGE_OPTIONS",
    "T8CharacterPerformanceBible",
    "T8CharacterPerformanceBibleStack",
    "T8CharacterPerformanceBibleIO",
    "T8FilmProjectRouter",
    "T8FilmProjectStateIO",
    "build_character_performance_bible",
    "build_character_performance_set",
    "character_performance_instruction",
    "coerce_character_performance_bible",
    "coerce_character_performance_bibles",
    "coerce_project_state",
    "downstream_stages",
    "project_state_prompt_context",
]
