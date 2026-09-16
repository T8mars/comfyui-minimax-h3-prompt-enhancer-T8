export const QUALITY_HELP_HEIGHT = 112;
const MODES = { off: "保持原样 / Off", none: "保持原样 / Off", check: "质量检查 / Check", repair: "质量纠正（最多追加1次） / Repair" };
const CREATION = { off: "原有编排 / Original", none: "原有编排 / Original", causal: "因果动作优化 / Causal" };
export const qualityLabel = (value) => MODES[value] ?? value ?? MODES.off;
export const creationLabel = (value) => CREATION[value] ?? value ?? CREATION.off;
const RESULTS = {
    checked: "检查完成 / Checked", corrected: "纠正已接受 / Corrected",
    candidate_rejected: "候选未通过，保留完整稿 / Candidate rejected",
    correction_failed_draft_kept: "纠正请求失败，保留完整稿 / Draft kept",
    check_failed_draft_kept: "检查失败，保留完整稿 / Check failed",
    protocol_repair_failed_draft_kept: "协议修复未完成，保留完整稿 / Draft kept",
    budget_exhausted_draft_kept: "纠正预算已用完，保留完整稿 / Budget exhausted",
};
export function qualityStatusText(value) {
    const result = RESULTS[value?.result] || "等待运行 / Awaiting run";
    const count = Array.isArray(value?.issue_codes) ? value.issue_codes.filter((s) => typeof s === "string" && /^[a-z_]{1,60}$/.test(s)).length : 0;
    const calls = value?.correction_calls === 1 ? 1 : 0;
    return `${result}；失败项 ${count}；追加纠正 ${calls} 次。${value?.cleanup_failed === true ? " 本地清理失败，请检查运行时。" : ""}\n文本检查 ≠ 成片验收；待确认项见脱敏诊断 / Text only.`;
}
export function addQualityUI(node) {
    if (node.t8QualityUI) return node.t8QualityUI;
    const quality = node.widgets?.find((w) => w.name === "quality_mode");
    const creation = node.widgets?.find((w) => w.name === "creation_mode");
    if (!quality || !creation) return null;
    const root = document.createElement("div");
    root.style.cssText = "box-sizing:border-box;height:112px;min-height:112px;max-height:112px;overflow:auto;padding:8px 10px;white-space:pre-wrap;font:12px/17px sans-serif;color:#eee;background:#202832;border:1px solid #496784;border-radius:6px";
    root.setAttribute("role", "status");
    const update = () => {
        quality.value = qualityLabel(quality.value);
        creation.value = creationLabel(creation.value);
        root.textContent = "质量 / Quality：Off 原流程；Check 只检查；Repair 最多1次计费纠正。\n因果 / Causal（实验）：同次优化衔接，不加请求；事实与尾态须复核。\n" + qualityStatusText(node.t8QualityStatus);
        node.setDirtyCanvas?.(true, true);
    };
    const widget = node.addDOMWidget("t8_quality_help", "custom", root, {
        getValue: () => "", setValue() {}, margin: 0, hideOnZoom: false, serialize: false,
        getHeight: () => QUALITY_HELP_HEIGHT, getMinHeight: () => QUALITY_HELP_HEIGHT, getMaxHeight: () => QUALITY_HELP_HEIGHT,
    });
    widget.computeSize = () => [0, QUALITY_HELP_HEIGHT];
    widget.serializeValue = () => undefined;
    for (const item of [quality, creation]) {
        const old = item.callback;
        item.callback = function () { old?.apply(this, arguments); node.t8QualityStatus = null; update(); node.graph?.change?.(); };
    }
    const executed = node.onExecuted;
    node.onExecuted = function (message) {
        executed?.apply(this, arguments);
        try { node.t8QualityStatus = JSON.parse(message?.t8_quality_status?.[0] || "null"); }
        catch (_) { node.t8QualityStatus = null; }
        update();
    };
    node.t8UpdateQuality = update;
    node.t8QualityUI = widget;
    update();
    return widget;
}
