import { restoreNamedWidgetValues, serializeNamedWidgetValues, syncNamedWidgetSerialization } from "./widget_state.mjs";

export const STRATA_API_MODE = "Strata 本地服务（桥接）";
export const STRATA_PROVIDER = "Strata";
// Frozen native widget order of the pre-Strata config: required, then optional.
export const CONFIG_OLD_NAMES = ["provider", "temperature_policy", "local_model", "local_mmproj",
    "local_context_size", "local_max_tokens", "local_think_mode", "local_reasoning_effort",
    "local_video_sample_fps", "local_unload_policy", "local_comfy_memory_policy",
    "credential_alias", "openai_base_url", "custom_model", "ai_workshop_model", "extra_parameters_json"];
export const STRATA_DEFAULTS = { strata_url: "http://127.0.0.1:8080", strata_model: "AUTO",
    strata_credential_alias: "", strata_reasoning_effort: "none", strata_max_tokens: 0,
    strata_reasoning_budget_tokens: 0, strata_video_mode: "frames", strata_video_sample_fps: 1,
    strata_video_max_frames: 8, strata_timeout_s: 1800, strata_allow_private_network: false };
export const CONFIG_NAMES = [...CONFIG_OLD_NAMES, ...Object.keys(STRATA_DEFAULTS)];
const SCHEMA = "t8_provider_config_widgets_schema";
const TEMPERATURES = new Set(["AUTO（兼容策略）", "发送 temperature", "省略 temperature"]);
const PROVIDERS = new Set(["Seedance NZ", "T8 AI Workshop", "OpenAI Compatible", "Local Qwen", STRATA_PROVIDER]);
const DECLARATION_OLD = ["provider", "credential_alias", "openai_base_url", "custom_model", "ai_workshop_model",
    "temperature_policy", "extra_parameters_json", "local_model", "local_mmproj", "local_context_size",
    "local_max_tokens", "local_think_mode", "local_reasoning_effort", "local_video_sample_fps", "local_unload_policy", "local_comfy_memory_policy"];

export function configSavedValues(saved) {
    const values = saved?.widgets_values;
    const named = saved?.widgets_values_named;
    const marked = saved?.properties?.[SCHEMA] === 1;
    let names;
    if (Array.isArray(values) && PROVIDERS.has(values[0])) {
        const newFields = values.slice(CONFIG_OLD_NAMES.length, CONFIG_NAMES.length);
        const typedNew = newFields.length === 11 && typeof newFields[0] === "string" && typeof newFields[1] === "string"
            && typeof newFields[2] === "string" && ["none", "low", "medium", "high"].includes(newFields[3])
            && Number.isInteger(newFields[4]) && Number.isInteger(newFields[5]) && ["frames", "native"].includes(newFields[6])
            && Number.isFinite(newFields[7]) && Number.isInteger(newFields[8]) && Number.isFinite(newFields[9]) && typeof newFields[10] === "boolean";
        if (TEMPERATURES.has(values[1]) && values.length >= CONFIG_NAMES.length && (marked || typedNew)) names = CONFIG_NAMES;
        else if (TEMPERATURES.has(values[1]) && values.length >= CONFIG_OLD_NAMES.length) names = CONFIG_OLD_NAMES;
        else if (TEMPERATURES.has(values[5]) && values.length >= DECLARATION_OLD.length) names = DECLARATION_OLD;
    }
    const result = names ? new Map(names.map((name, i) => [name, values[i]])) : new Map();
    // Native named metadata can restore a new workflow whose host strips our
    // marker. Reject conflicting positional/named maps instead of trusting one.
    if (named && typeof named === "object" && !Array.isArray(named)
        && PROVIDERS.has(named.provider) && TEMPERATURES.has(named.temperature_policy)
        && [...result].every(([name, value]) => !Object.hasOwn(named, name) || named[name] === value)) {
        for (const name of CONFIG_NAMES) if (Object.hasOwn(named, name)) result.set(name, named[name]);
    }
    for (const [name, value] of Object.entries(STRATA_DEFAULTS)) if (!result.has(name)) result.set(name, value);
    return result;
}

export function projectConfigValues(node, values) {
    return node.widgets?.map(widget => values.has(widget.name) ? values.get(widget.name) : widget.value) || [];
}

export function configureConfig(node, saved, original, args) {
    const values = configSavedValues(saved);
    const projected = { ...saved, widgets_values: projectConfigValues(node, values), widgets_values_named: Object.fromEntries(values) };
    const result = original?.apply(node, [projected, ...args.slice(1)]);
    restoreNamedWidgetValues(node, values);
    return result;
}

export function serializeConfig(node, saved) {
    saved.widgets_values = serializeNamedWidgetValues(node, CONFIG_NAMES);
    saved.properties = { ...(saved.properties || {}), [SCHEMA]: 1 };
    syncNamedWidgetSerialization(saved, CONFIG_NAMES);
}

export function strataValues(node, overrides = {}) {
    return Object.fromEntries(Object.entries(STRATA_DEFAULTS).map(([name, fallback]) =>
        [name, Object.hasOwn(overrides, name) ? overrides[name] : node.widgets?.find(widget => widget.name === name)?.value ?? fallback]));
}

export async function probeStrata(node, overrides = {}, fetchFn = (...args) => globalThis.fetch(...args)) {
    const values = strataValues(node, overrides);
    const snapshot = JSON.stringify([node.widgets?.find(widget => widget.name === "provider")?.value, values]);
    const generation = (node.t8StrataProbeGeneration || 0) + 1;
    node.t8StrataProbeGeneration = generation;
    const response = await fetchFn("/t8-prompt-enhancer/strata/status", { method: "POST", credentials: "same-origin",
        cache: "no-store", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(values) });
    const result = await response.json();
    const current = JSON.stringify([node.widgets?.find(widget => widget.name === "provider")?.value, strataValues(node, overrides)]);
    if (node.t8StrataRemoved || generation !== node.t8StrataProbeGeneration || current !== snapshot) return null;
    return result;
}

export function statusText(status) {
    if (!status?.connected) return `Strata 连接未通过：${status?.category || "connection"}（没有生成请求）`;
    const vision = !status.vision_enabled ? "未启用" : status.vision_available === false ? "已启用但尚不可用" : "已启用";
    const model = status.loaded ? "已加载" : status.auto_load === false ? "未加载；请先在 Strata 手动加载模型" : "由服务按配置自动加载";
    return `Strata 只读检查：${status.model} · 上下文 ${status.context}\n视觉：${vision} · native：${status.native_verified ? "已核验" : "尚未核验"}\n模型${model}；桥接不控制起停/卸载。`;
}

export function effectiveStrata(node) {
    if (node.comfyClass === "T8LLMProviderConfig" || node.type === "T8LLMProviderConfig") return node.widgets?.find(w => w.name === "provider")?.value === STRATA_PROVIDER;
    const input = node.inputs?.find(item => item.name === "provider_config");
    if (input?.link != null && node.graph) {
        let linkId = input.link;
        const visited = new Set();
        // Reroute is transparent to execution. Resolve it without assuming a
        // particular host's links container or looping on malformed graphs.
        for (let depth = 0; linkId != null && depth < 128 && !visited.has(linkId); depth++) {
            visited.add(linkId);
            const link = node.graph.links?.get?.(linkId) || node.graph.links?.[linkId];
            const source = node.graph.getNodeById?.(link?.origin_id);
            if (!source) break;
            if (source.type === "Reroute" || source.comfyClass === "Reroute") {
                linkId = source.inputs?.[0]?.link;
                continue;
            }
            const provider = source.widgets?.find(w => w.name === "provider");
            if (provider) return provider.value === STRATA_PROVIDER;
            break;
        }
    }
    return node.widgets?.find(w => w.name === "api_mode")?.value === STRATA_API_MODE;
}

export function restoreStrataVisibility(node) {
    for (const widget of node.widgets || []) {
        const state = widget.t8StrataHiddenState;
        if (!state) continue;
        widget.type = state.type; widget.computeSize = state.computeSize; widget.hidden = state.hidden;
        if (widget.element) { widget.element.style.display = state.display; widget.element.hidden = state.elementHidden; }
        delete widget.t8StrataHiddenState;
    }
}

function hide(widget) {
    if (!widget || widget.t8StrataHiddenState) return;
    widget.t8StrataHiddenState = { type: widget.type, computeSize: widget.computeSize, hidden: widget.hidden,
        display: widget.element?.style.display || "", elementHidden: widget.element?.hidden || false };
    widget.type = "converted-widget"; widget.computeSize = () => [0, -4]; widget.hidden = true;
    if (widget.element) { widget.element.style.display = "none"; widget.element.hidden = true; }
}

export function updateStrataVisibility(node) {
    const strata = effectiveStrata(node);
    const config = node.comfyClass === "T8LLMProviderConfig" || node.type === "T8LLMProviderConfig";
    for (const widget of node.widgets || []) {
        if (config && widget.name.startsWith("strata_") && !strata) hide(widget);
        if (strata && (widget.name.startsWith("local_") || ["api_key", "credential_alias", "ai_workshop_model", "custom_model", "openai_base_url", "openai_video_urls", "temperature_policy", "extra_parameters_json"].includes(widget.name)
            || /获取.*API Key|扫描本地 GGUF|检查本地 Qwen|本地 GGUF 安装|模型路径：|(?:安装|获取).*Wheel/.test(widget.name))) hide(widget);
        if (widget === node.t8StrataNoticeWidget && !strata) hide(widget);
    }
    node.setDirtyCanvas?.(true, true);
}
