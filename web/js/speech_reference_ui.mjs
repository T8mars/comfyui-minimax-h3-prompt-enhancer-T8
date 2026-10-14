// Only this new helper owns these fields; existing enhancer arrays never change.
export const SPEECH_NAMES = ["mode", "source_mode", "purpose", "provided_text", "provided_format",
    "speaker_map_json", "partial_policy", "failure_policy", "start_s", "duration_s", "language", "context",
    "audio_track", "channel", "offset_ms", "timeout_s"];
const ADVANCED = new Set(["provided_format", "speaker_map_json", "partial_policy", "failure_policy",
    "context", "audio_track", "channel", "offset_ms", "timeout_s", "start_s", "duration_s"]);
const PROPERTY = "t8_speech_widgets_v1";
const DEFAULTS = ["Off", "Provided text", "reference", "", "auto", "{}", "reject", "stop", 0, 0, "Auto", "", 0, "mean", 0, 1800];
const linkedText = node => node.inputs?.some(i => i.name === "provided_text" && i.link != null);

function validSpeechValues(array) {
    return array.length === 16
        && ["Off", "Enabled"].includes(array[0]) && ["Provided text", "AUDIO", "VIDEO"].includes(array[1])
        && ["reference", "keep_dialogue"].includes(array[2]) && (typeof array[3] === "string" || array[3] === null)
        && ["auto", "plain", "srt", "vtt", "json"].includes(array[4]) && typeof array[5] === "string"
        && ["reject", "accept_review"].includes(array[6]) && ["stop", "continue_empty"].includes(array[7])
        && [8, 9, 12, 14, 15].every(i => typeof array[i] === "number" && Number.isFinite(array[i]))
        && typeof array[10] === "string" && typeof array[11] === "string" && ["mean", "left", "right"].includes(array[13]);
}

function namedState(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const array = SPEECH_NAMES.map(name => Object.hasOwn(value, name) ? value[name] : undefined);
    return validSpeechValues(array) ? Object.fromEntries(SPEECH_NAMES.map((name, i) => [name, array[i]])) : null;
}

function positionalState(node, values) {
    if (!Array.isArray(values)) return {};
    let canonical = values.slice(0, 16);
    if (!validSpeechValues(canonical) && linkedText(node)) {
        const omitted = [...values.slice(0, 3), null, ...values.slice(3, 15)];
        if (validSpeechValues(omitted)) canonical = omitted;
    }
    return validSpeechValues(canonical) ? Object.fromEntries(SPEECH_NAMES.map((name, i) => [name, canonical[i]])) : {};
}

export function restoreSpeechVisibility(node) {
    for (const w of node.widgets || []) {
        const saved = w.t8SpeechVisibility;
        if (!saved) continue;
        w.type = saved.type; w.computeSize = saved.computeSize; w.hidden = saved.hidden;
        if (w.element) { w.element.style.display = saved.display; w.element.hidden = saved.elementHidden; }
        delete w.t8SpeechVisibility;
    }
}

export function refreshSpeech(node) {
    restoreSpeechVisibility(node);
    const value = name => node.widgets?.find(w => w.name === name)?.value;
    const source = value("source_mode"), off = value("mode") === "Off";
    for (const w of node.widgets || []) {
        const irrelevant = (["provided_text", "provided_format"].includes(w.name) && source !== "Provided text")
            || (["language", "context", "channel", "offset_ms", "timeout_s", "failure_policy"].includes(w.name) && source === "Provided text")
            || (w.name === "audio_track" && source !== "VIDEO")
            || (w.name === "speaker_map_json" && value("purpose") !== "keep_dialogue");
        if ((ADVANCED.has(w.name) && !node.t8SpeechAdvanced) || irrelevant || (off && SPEECH_NAMES.includes(w.name) && w.name !== "mode")) {
            w.t8SpeechVisibility = { type: w.type, computeSize: w.computeSize, hidden: w.hidden,
                display: w.element?.style.display || "", elementHidden: w.element?.hidden || false };
            w.type = "converted-widget"; w.computeSize = () => [0, -4]; w.hidden = true;
            if (w.element) { w.element.style.display = "none"; w.element.hidden = true; }
        }
    }
    if (node.t8SpeechAdvancedButton) node.t8SpeechAdvancedButton.label = node.t8SpeechAdvanced
        ? "▾ 收起高级语音设置 / Less" : "⚙ 高级语音设置（选填） / Advanced";
    node.setSize?.([node.size?.[0] || 430, node.computeSize?.()?.[1] || 260]);
    node.setDirtyCanvas?.(true, true);
}

export function serializeSpeech(node, data) {
    const state = {};
    for (const [index, name] of SPEECH_NAMES.entries()) {
        const w = node.widgets?.find(item => item.name === name);
        state[name] = w ? w.value : name === "provided_text" && linkedText(node) ? null : DEFAULTS[index];
    }
    data.properties = { ...(data.properties || {}), [PROPERTY]: state };
    data.widgets_values = SPEECH_NAMES.map(name => state[name]);
    data.widgets_values_named = { ...state };
}

export function configureSpeech(node, data, host, args) {
    const state = namedState(data?.properties?.[PROPERTY]) || namedState(data?.widgets_values_named)
        || positionalState(node, data?.widgets_values);
    const widgets = (node.widgets || []).filter(w => SPEECH_NAMES.includes(w.name));
    const prepared = { ...data, widgets_values: widgets.map(w => Object.hasOwn(state, w.name) ? state[w.name] : w.value) };
    const callArgs = [...args]; callArgs[0] = prepared;
    const result = host?.apply(node, callArgs);
    for (const w of widgets) if (Object.hasOwn(state, w.name) && state[w.name] !== undefined) {
        w.value = state[w.name];
        if (w.inputEl) w.inputEl.value = String(w.value ?? "");
    }
    return result;
}

export function speechConnectionValues(node) {
    let id = node.inputs?.find(i => i.name === "provider_config")?.link;
    const seen = new Set();
    for (let depth = 0; id != null && depth < 128 && !seen.has(id); depth++) {
        seen.add(id);
        const link = node.graph?.links?.get?.(id) || node.graph?.links?.[id];
        const source = node.graph?.getNodeById?.(link?.origin_id);
        if (!source) break;
        if (source.type === "Reroute" || source.comfyClass === "Reroute") { id = source.inputs?.[0]?.link; continue; }
        if (source.widgets?.find(w => w.name === "provider")?.value !== "Strata") throw new Error("请连接 Strata 渠道配置 / Connect a Strata provider config.");
        return Object.fromEntries((source.widgets || []).filter(w => ["strata_url", "strata_credential_alias", "strata_allow_private_network", "strata_timeout_s"].includes(w.name)).map(w => [w.name, w.value]));
    }
    if (id != null) throw new Error("无法解析共享配置 / Unresolved provider configuration.");
    return {};
}

export function speechStatusText(value) {
    if (!value?.connected) return `语音检查未通过 / Speech check failed (${value?.category || "connection"})。旧图文功能不受影响；仍可导入已有字幕。`;
    const ready = value.supported === true && value.device === "cpu" && value.cpu_guard === true;
    const reason = !value.supported ? "未配齐 / Not configured" : value.device !== "cpu"
        ? "当前设备不可用，请在 Strata 选择 CPU / CPU required"
        : "缺少 CPU 保护，请更新 Strata / Guard required";
    return `语音组件 ${ready ? "就绪 / Ready" : reason}；设备 ${value.device || "unknown"}；CPU 原子保护 ${value.cpu_guard ? "支持" : "缺失，请更新 Strata"}。\n只读检查，没有转写、加载或卸载模型。时标为段级近似；不识别说话人、BPM 或环境音。`;
}
