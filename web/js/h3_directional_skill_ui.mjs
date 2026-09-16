// Shared presentation only. Each enhancer retains its own output compiler.
export const DIRECTIONAL_SKILLS = Object.freeze([
    { id: "none", label: "关闭 / Off", summary: "按原来的场景与模板设置增强提示词。" },
    { id: "continuous_combat", label: "连续战斗长镜头 / Continuous combat", summary: "连续摄影路径、攻防起伏、空间与受击状态承接。", example: "例 / Example: 双剑客走廊交锋，一镜到底 / Corridor sword duel, one take." },
    { id: "high_density_combat", label: "高密度连续攻防 / High-density combat", summary: "按已有武器与能力编排攻防，让上一动作结果触发下一动作。", example: "例 / Example: 两人徒手连续攻防8秒 / Unarmed duel, 8s nonstop." },
    { id: "cinematic_gunfight", label: "电影枪战导演 / Cinematic gunfight", summary: "围绕人物目标组织枪战、空间、动作回应与声音。", example: "例 / Example: 雨夜枪战掩护同伴撤离 / Rainy gunfight, cover an escape." },
]);

export function directionalSkillId(value) {
    // Malformed saved/API values must reach validation, not turn []/false into
    // a silently disabled Skill. Only absent/string-empty selections are Off.
    if (value != null && typeof value !== "string") return value;
    const original = String(value ?? "");
    const text = original.trim();
    // Preserve unknown values for the backend's explicit, sanitized validation.
    // An unrecognized saved selection must never silently become Off.
    return DIRECTIONAL_SKILLS.find((item) => item.id === text || item.label === text)?.id || (text ? original : "none");
}

export function directionalSkillLabel(value) {
    const id = directionalSkillId(value);
    return DIRECTIONAL_SKILLS.find((item) => item.id === id)?.label ?? id;
}

export function isDirectionalSkillEnabled(value) {
    const id = directionalSkillId(value);
    return DIRECTIONAL_SKILLS.some((item) => item.id === id && id !== "none");
}

export const DIRECTIONAL_HELP_HEIGHT = 120;

export function directionalSkillDescription(value, target = "h3") {
    const skill = DIRECTIONAL_SKILLS.find((item) => item.id === directionalSkillId(value));
    const format = target === "seedance20" ? "Seedance 原有格式保留。" : "H3 官方核心与所选输出格式保留。";
    if (!skill) return `未知定向技能，请重新选择 / Unknown skill; please select again.\n${format}\n未自动改为关闭，也未启用其他技能；原选择保留用于校验。`;
    const priority = target === "seedance20"
        ? "T8 案例、手动模板本次暂停；关闭后恢复原选择。"
        : "官方场景、T8 案例、手动模板本次暂停；关闭后恢复原选择。";
    return [
        skill.id === "none" ? "定向创作：关闭 / Off" : `当前创作来源：${skill.label}（非官方）`,
        ...(skill.example ? [skill.example] : []),
        skill.summary,
        format,
        skill.id === "none" ? "选择一种定向技能即可，无需新增连线或填写表格。" : priority,
        "恢复上次结果不会按当前技能重新生成。",
    ].join("\n");
}

export function addDirectionalSkillUI(node, skillWidget, { target = "h3", onChange } = {}) {
    if (!skillWidget || node.t8DirectionalSkillUI) return node.t8DirectionalSkillUI || null;
    const root = document.createElement("div");
    root.style.cssText = "box-sizing:border-box;height:120px;min-height:120px;max-height:120px;padding:8px 10px;overflow:auto;white-space:pre-wrap;font:12px/17px sans-serif;color:#ddd;background:#202832;border:1px solid #496784;border-radius:6px;";
    root.setAttribute("role", "note");
    const detail = node.addDOMWidget("t8_directional_skill_help", "custom", root, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => DIRECTIONAL_HELP_HEIGHT,
        getMaxHeight: () => DIRECTIONAL_HELP_HEIGHT,
        getHeight: () => DIRECTIONAL_HELP_HEIGHT,
        // Modern DOM widgets subtract two margins from their host height.
        // The element already owns padding; reserve its full 120px footprint.
        margin: 0,
        hideOnZoom: false,
        serialize: false,
    });
    // Legacy LiteGraph reads computeSize rather than computeLayoutSize.
    detail.computeSize = () => [0, DIRECTIONAL_HELP_HEIGHT];
    detail.serializeValue = () => undefined;
    skillWidget.label = "定向创作 Skill（非官方）";
    skillWidget.tooltip = "仅选择一种创作方法；中文/English、原有模型格式、素材与用户明确要求仍保留。关闭后恢复原模板设置。";
    const originals = new Map();
    for (const name of ["case_template", "prompt_mode", "reference_template"]) {
        const widget = node.widgets?.find((item) => item.name === name);
        if (widget) originals.set(widget, { label: widget.label, tooltip: widget.tooltip });
    }
    const update = () => {
        skillWidget.value = directionalSkillLabel(skillWidget.value);
        const active = isDirectionalSkillEnabled(skillWidget.value);
        root.textContent = directionalSkillDescription(skillWidget.value, target);
        for (const [widget, original] of originals) {
            widget.label = active ? `${original.label || widget.name}（定向技能优先，当前暂停）` : original.label;
            widget.tooltip = active
                ? "当前定向创作 Skill 优先；原选择和内容已保留，关闭定向技能后恢复。"
                : original.tooltip;
        }
        node.setDirtyCanvas?.(true, true);
    };
    const originalCallback = skillWidget.callback;
    skillWidget.callback = function () {
        originalCallback?.apply(this, arguments);
        update();
        onChange?.(isDirectionalSkillEnabled(skillWidget.value));
        node.graph?.change?.();
    };
    // UI order can differ from serialization order: append-only named storage is
    // maintained by each enhancer, never derived from this visual position.
    const caseWidget = node.widgets?.find((item) => item.name === "case_template");
    if (caseWidget && Array.isArray(node.widgets)) {
        for (const widget of [skillWidget, detail]) {
            const index = node.widgets.indexOf(widget);
            if (index >= 0) node.widgets.splice(index, 1);
        }
        node.widgets.splice(node.widgets.indexOf(caseWidget) + 1, 0, skillWidget, detail);
    }
    node.t8UpdateDirectionalSkill = update;
    node.t8DirectionalSkillUI = detail;
    update();
    return detail;
}
