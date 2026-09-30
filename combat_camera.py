"""Optional camera modifier, independently adapted from a user-supplied handbook.

Not a scene generator, output-format authority, or evidence of rendered quality.
"""
from __future__ import annotations

from typing import Any, Mapping

from comfy_api.latest import io

CONFIG_SCHEMA = "t8-combat-camera-config/v1"
REVISION = "1.0.0"
CAMERA_AUTO = "AUTO（按已有战斗动作）"
CAMERA_STRONG = "强化（明确轨迹与落点）"
CAMERA_OFF = "关闭 / Off"
CAMERA_OPTIONS = [CAMERA_AUTO, CAMERA_STRONG, CAMERA_OFF]
CONTINUITY_FOLLOW = "沿用原设定 / Follow"
CONTINUITY_CONTINUOUS = "偏好连续镜头 / Prefer continuous"
CONTINUITY_OPTIONS = [CONTINUITY_FOLLOW, CONTINUITY_CONTINUOUS]
IMPACT_NATURAL = "写实 / Natural"
IMPACT_STYLIZED = "风格化 / Stylized"
IMPACT_OPTIONS = [IMPACT_NATURAL, IMPACT_STYLIZED]
T8CombatCameraConfigIO = io.Custom("T8_COMBAT_CAMERA_CONFIG")


def build_combat_camera_config(mode=CAMERA_AUTO, continuity=CONTINUITY_FOLLOW, impact=IMPACT_NATURAL):
    config = dict(schema_version=CONFIG_SCHEMA, mode=mode, continuity=continuity, impact=impact)
    resolve_combat_camera_config(config)
    return config


def resolve_combat_camera_config(config: Any = None) -> dict[str, str] | None:
    if config is None:
        return None
    if not isinstance(config, Mapping) or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("战斗运镜配置格式不支持 / Unsupported combat_camera_config schema.")
    for field, options in (("mode", CAMERA_OPTIONS), ("continuity", CONTINUITY_OPTIONS), ("impact", IMPACT_OPTIONS)):
        value = config.get(field)
        if not isinstance(value, str) or value not in options:
            # Never echo arbitrary connected data, prompts, paths or credentials.
            raise ValueError(f"战斗运镜配置选项无效 / Invalid combat camera option: {field}.")
    if config["mode"] == CAMERA_OFF:
        return None
    return {key: config[key] for key in ("schema_version", "mode", "continuity", "impact")}


def camera_metadata(config: Any = None) -> dict[str, str]:
    selected = resolve_combat_camera_config(config)
    if selected is None:
        return {}
    return {
        "combat_camera_mode": "strong" if selected["mode"] == CAMERA_STRONG else "auto",
        "combat_camera_continuity": "prefer_continuous" if selected["continuity"] == CONTINUITY_CONTINUOUS else "follow",
        "combat_camera_impact": "stylized" if selected["impact"] == IMPACT_STYLIZED else "natural",
        "combat_camera_revision": REVISION,
    }


def combat_camera_instruction(config: Any = None, model_target: str = "h3") -> str:
    selected = resolve_combat_camera_config(config)
    if selected is None:
        return ""
    if model_target not in {"h3", "seedance20"}:
        raise ValueError("Combat camera supports H3 and Seedance 2.0 only.")
    strength = (
        "STRONG: materially clarify weak camera passages with a motivated viewing path, readable action direction and contact; synonym polishing is insufficient."
        if selected["mode"] == CAMERA_STRONG else
        "AUTO: add only the useful camera support missing from existing combat action; leave already clear passages alone."
    )
    continuity = (
        "Prefer a continuous observation ONLY where cuts and shot count are not already fixed. Within requested multiple shots preserve internal continuity; never change the count."
        if selected["continuity"] == CONTINUITY_CONTINUOUS else
        "Follow the existing camera continuity and shot policy; do not impose a single take."
    )
    impact = (
        "Stylized impact is permitted, not mandatory: a brief emphasis or restrained shake only if allowed by the user. No automatic freeze, repeated shake, mandatory slow motion or fixed-duration hold."
        if selected["impact"] == IMPACT_STYLIZED else
        "Natural impact: favor readable contact, framing and physically coherent follow-through, normally in real time. Do not add freeze, speed ramps, shockwaves or particles; preserve any explicitly requested stylization or slow motion."
    )
    native = (
        "H3: retain the selected native fields, shot/time syntax, reference roles and vocal grammar. For Prompt Relay, keep the existing JSON envelope, counts, weights and ranges; carry camera side, facing and velocity through global context and events. Events are not cuts."
        if model_target == "h3" else
        "Seedance 2.0: use native natural-language output and reference syntax only, never H3 fields or handbook abbreviations. Keep at most ONE primary camera movement per shot; focus/framing adjustments support it, not a stack of competing maneuvers. TrackFill bridges source videos: modify only the permitted transition and inherit both endpoints."
    )
    return "\n".join((
        f"T8 COMBAT CAMERA MODIFIER v{REVISION} (non-official, conditional camera guidance).",
        "Apply ONLY to combat or physical attack/defense already requested or evidenced in the actual scene. This is subordinate camera support, not another scene-directing Skill. Non-combat, a displayed weapon, or a character title alone does not authorize combat. A solo drill remains solo.",
        strength,
        "User hard constraints, media facts, native format, fixed duration/count, exact speech/text, identities, prop ownership, action order and ending outrank these suggestions. Never invent opponents, attacks, weapons, powers, injuries, sounds or outcomes to justify a camera move. Preserve the active directing Skill, performance/Bible contract and scene templates; do not replace them.",
        "Keep the user's clothing and equipment categories unchanged: a red/blue sleeve is clothing, not newly added arm guards, protective gear or gloves. Preserve a near-miss as a near-miss, not a contact. Retain the requested total duration and shot count in native descriptive text where the platform format permits.",
        continuity,
        "Keep spatial landmarks and the travel axis readable. Motivate each camera change by an existing action; no arbitrary roll/orbit or impossible jump through walls. An occlusion is not permission to teleport. Respect fixed-camera requests using framing/focus only. Keep a first-person viewpoint owned by the same observer; never orbit outside that observer's body. Continuous observation does not require actors to move constantly or cancel a requested wait.",
        "For an eye-owned POV, describe natural head/body response, not a handheld camera operator; explicitly requested hands or held objects may remain in view. Do not turn 'no exterior view of my body' into 'hide my visible hand or object'.",
        "Choose only applicable mechanisms, NOT a ten-step choreography: rush -> low wide tracking/push retaining distance; crossing/dodge -> reveal the crossing point and transfer attention without losing sides; low sweep -> low lateral tracking of its path; leap -> upward tracking from the established takeoff; contact -> briefly stabilize readable contact, not necessarily stop actors; recoil -> widen/retreat ONLY along existing displacement; combo -> matched lateral tracking preserving exchange rhythm; counterattack -> reorient toward the existing threat; downward action -> follow its descent while keeping geography; ending -> inherit the specified final state, never invent a next attack, defeat or charged pose.",
        impact,
        "Blur may support speed at the background/edges, not obscure limbs or decisive contact. Do not add environment debris absent from the scene. Choose one useful camera information task at a time rather than performing every mechanism. Fit motion within the existing duration and performance beats.",
        "Honor first/last-frame anchors; identity references are not automatically first frames. Edit only the authorized region/time/property, extend from the existing motion, and keep camera unchanged for an explicitly audio-only edit. Do not claim media was inspected if unavailable.",
        native,
        "Before returning, silently check axis, viewpoint, contact visibility, ownership, ending and forbidden additions. Output only the platform's existing final prompt/envelope, not a camera checklist or a new schema.",
    ))


class T8CombatCameraConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CombatCameraConfig",
            display_name="T8 战斗运镜配置 / Combat Camera Config",
            category="T8/Utilities",
            description=("连接 H3 / Seedance 2.0 左侧的战斗运镜配置输入，可叠加表演导演。未连接/关闭保持原行为。"
                         "例：两人木剑演练，格挡后退半步，让方向与接触清楚；不自动增加招式或敌人。"
                         "Optional camera support for existing action; no extra LLM call. Effects depend on model and scene."),
            inputs=[
                io.Combo.Input("mode", display_name="战斗运镜模式 / Mode", options=CAMERA_OPTIONS, default=CAMERA_AUTO,
                               tooltip="AUTO只补已有战斗的运镜；强化明确路线与落点；关闭不注入规则。No invented action."),
                io.Combo.Input("continuity", display_name="镜头连续性 / Continuity", options=CONTINUITY_OPTIONS, default=CONTINUITY_FOLLOW,
                               tooltip="连续仅是偏好，不覆盖指定镜头数、固定机位、POV或首尾帧。Explicit constraints win."),
                io.Combo.Input("impact", display_name="冲击表现 / Impact", options=IMPACT_OPTIONS, default=IMPACT_NATURAL,
                               tooltip="写实优先看清接触；风格化允许适度强调，不强加慢动作、定格、震动。Natural / optional stylization."),
            ],
            outputs=[T8CombatCameraConfigIO.Output(display_name="战斗运镜配置 / Combat camera config")],
        )

    @classmethod
    def execute(cls, mode=CAMERA_AUTO, continuity=CONTINUITY_FOLLOW, impact=IMPACT_NATURAL) -> io.NodeOutput:
        return io.NodeOutput(build_combat_camera_config(mode, continuity, impact))
