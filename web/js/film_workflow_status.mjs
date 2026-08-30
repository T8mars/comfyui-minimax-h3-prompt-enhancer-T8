export function parseStatusMessage(message, key) {
    const raw = Array.isArray(message?.[key]) ? message[key][0] : message?.[key];
    if (!raw) return null;
    try {
        return typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch (_error) {
        return null;
    }
}


function isEnglish(language) {
    return !String(language || "zh").toLowerCase().startsWith("zh");
}


export function estimateStatusCardHeight(text, minimum = 84, maximum = 180) {
    const lines = String(text || "").split("\n");
    const visualLines = lines.reduce((total, line) => {
        const units = Array.from(line).reduce(
            (sum, character) => sum + (character.codePointAt(0) > 255 ? 1.8 : 1),
            0,
        );
        return total + Math.max(1, Math.ceil(units / 54));
    }, 0);
    return Math.max(minimum, Math.min(maximum, 22 + (visualLines * 18)));
}


export function routerStatusView(status, language = "zh") {
    const english = isEnglish(language);
    if (!status) {
        return {
            text: english
                ? "Stage status: no parseable execution state received"
                : "阶段状态：未收到可解析的执行状态",
            borderColor: "#a16207",
            background: "#2a2114",
        };
    }
    const invalidated = Array.isArray(status.invalidated_stages) ? status.invalidated_stages : [];
    const confirmed = Array.isArray(status.confirmed_invalidated_stages)
        ? status.confirmed_invalidated_stages
        : [];
    const cleared = Array.isArray(status.cleared_inherited_fields)
        ? status.cleared_inherited_fields
        : [];
    const sourceLabels = english
        ? { direct_state: "connected revision", state_json: "prior JSON", new: "new project" }
        : { direct_state: "直连上一版", state_json: "上一版 JSON", new: "新项目" };
    const clearLabels = english ? {
        project_brief: "project brief",
        authoritative_inputs: "authoritative inputs",
        confirmed_stages: "confirmed stages",
        rules: "world rules",
        costs_and_limits: "costs and limits",
        knowledge_gaps: "knowledge gaps",
        continuity_anchors: "continuity anchors",
    } : {
        project_brief: "项目简述",
        authoritative_inputs: "本轮权威输入",
        confirmed_stages: "已确认阶段",
        rules: "世界硬规则",
        costs_and_limits: "能力代价与限制",
        knowledge_gaps: "人物知情差",
        continuity_anchors: "连续性锚点",
    };
    const lines = [
        english
            ? `Revision: r${status.revision ?? "?"}  Source: ${sourceLabels[status.source] || status.source || "unknown"}`
            : `修订版本：r${status.revision ?? "?"}　来源：${sourceLabels[status.source] || status.source || "未知"}`,
        english
            ? `Current stage: ${status.target_stage || "not set"}`
            : `本轮阶段：${status.target_stage || "未设置"}`,
        invalidated.length
            ? (english
                ? `⚠ Invalidated downstream: ${invalidated.join(", ")}`
                : `⚠ 已失效下游：${invalidated.join("、")}`)
            : (english ? "✓ No downstream stage was invalidated" : "✓ 本轮没有触发下游失效"),
    ];
    if (confirmed.length) {
        lines.push(english
            ? `Reconfirmation required: ${confirmed.join(", ")}`
            : `需重新确认：${confirmed.join("、")}`);
    }
    if (cleared.length) {
        const values = cleared.map((item) => clearLabels[item] || item);
        lines.push(english
            ? `Cleared inherited fields: ${values.join(", ")}`
            : `已清空上一版字段：${values.join("、")}`);
    }
    return {
        text: lines.join("\n"),
        borderColor: invalidated.length ? "#ef4444" : "#22c55e",
        background: invalidated.length ? "#2a1717" : "#14251b",
    };
}


export function contractStatusView(status, language = "zh") {
    const english = isEnglish(language);
    if (!status) {
        return {
            text: english
                ? "Contract status: no parseable result received; inspect the node JSON output"
                : "结构协议：未收到可解析的校验状态，请查看节点 JSON 输出",
            borderColor: "#a16207",
            background: "#2a2114",
        };
    }
    const valid = status.contract_valid === true;
    const labels = english ? {
        long_form_planning: "Long-form segment contract",
        storyboard_planning: "Storyboard delivery contract",
    } : {
        long_form_planning: "长片分段协议",
        storyboard_planning: "分镜交付协议",
    };
    const label = labels[status.operation] || (english ? "Creative structure contract" : "创作结构协议");
    const expected = Number.isInteger(status.expected_item_count)
        ? status.expected_item_count
        : null;
    const received = Number.isInteger(status.received_item_count)
        ? status.received_item_count
        : null;
    const countText = expected !== null
        ? (english ? `  Items: ${received ?? "?"}/${expected}` : `　条目：${received ?? "?"}/${expected}`)
        : (received !== null ? (english ? `  Items: ${received}` : `　条目：${received}`) : "");
    const lines = [
        valid
            ? (english ? `✓ ${label} passed${countText}` : `✓ ${label}校验通过${countText}`)
            : (english ? `✕ ${label} failed${countText}` : `✕ ${label}校验失败${countText}`),
        `Provider: ${status.provider || (english ? "unknown" : "未知")}`,
    ];
    if (!valid) {
        const codes = Array.isArray(status.validation_error_codes)
            ? status.validation_error_codes
            : [];
        const errorCount = Number(status.validation_error_count || codes.length || 0);
        lines.push(english
            ? `${errorCount} contract error(s): ${codes.slice(0, 3).join(", ") || "inspect JSON"}`
            : `发现 ${errorCount} 项协议错误：${codes.slice(0, 3).join("、") || "请查看 JSON"}`);
        if (status.downstream_blocked === true) {
            lines.push(english
                ? "Downstream execution was blocked by the strict policy; review validation_errors."
                : "严格策略已阻止下游执行；请查看 validation_errors 后修正或重跑。");
        } else {
            lines.push(english
                ? "Compatibility mode kept the outputs; do not use them downstream before reviewing validation_errors."
                : "兼容模式保留了输出；查看 validation_errors 前不要直接交给下游。");
        }
    }
    return {
        text: lines.join("\n"),
        borderColor: valid ? "#22c55e" : "#ef4444",
        background: valid ? "#14251b" : "#2a1717",
    };
}
