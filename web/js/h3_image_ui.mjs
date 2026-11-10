import { syncNamedWidgetSerialization, bindOpenAIProviderPersistence, commitOpenAIProviderState } from "./widget_state.mjs";
import { newRecoverySlot, RECOVERY_SLOT_PROPERTY } from "./completion_recovery_core.mjs";

export const ID = "MiniMaxH3ImagePromptEnhancerT8";
export const STATE = "t8_h3_image_widgets_v1";
export const OWNER_PROPERTY = "t8_h3_image_workflow_owner_v1";
export const T2I = "文生图 / Text to image", EDIT = "图像编辑 / Image edit";
export const MODES = ["贞贞平价小屋（推荐）", "贞贞的AI工坊（图片/视频）", "OpenAI兼容接口（备用）",
    "本地 GGUF（llama.cpp / Qwen，离线）", "Strata 本地服务（桥接）"];
export const NAMES = ["prompt", "task_type", "aspect_ratio", "target_words", "api_mode", "locked_text",
    "max_corrections", "llm_max_tokens", "ai_workshop_model", "custom_model", "openai_base_url", "seed",
    "local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
    "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy", "recovery_slot", "recovery_action"];
const NUMBERS = { target_words: 0, max_corrections: 1, llm_max_tokens: 16384, seed: 0, local_context_size: 32768, local_max_tokens: 16384 };
const ENUMS = { task_type: [T2I, EDIT], api_mode: MODES, recovery_action: ["normal", "restore_last"] };
const PROVIDER_MODES = { "Seedance NZ": MODES[0], "T8 AI Workshop": MODES[1], "OpenAI Compatible": MODES[2],
    "Local Qwen": MODES[3], Strata: MODES[4] };
const widget = (node, name) => node.widgets?.find(w => w.name === name);
const linked = (node, name) => node.inputs?.some(i => (i.name === name || i.widget?.name === name) && i.link != null);

function graphTree(root) {
    const graphs = new Set(), pending = [root];
    while (pending.length) {
        const graph = pending.pop();
        if (!graph || graphs.has(graph)) continue;
        graphs.add(graph);
        if (graph.subgraphs?.values) pending.push(...graph.subgraphs.values());
        for (const item of graph._nodes || []) if (item.subgraph) pending.push(item.subgraph);
    }
    return graphs;
}

export function ensureWorkflowOwner(node, root) {
    if (typeof root?.id !== "string" || !root.id || !graphTree(root).has(node.graph)) return;
    const control = widget(node, "recovery_slot");
    if (!control) return;
    node.properties ||= {};
    if (node.properties[OWNER_PROPERTY] !== root.id) {
        // A copied workflow has a new root UUID. Legacy slots without an owner
        // cannot authenticate their old cached result either: start afresh.
        node.properties[OWNER_PROPERTY] = root.id;
        control.value = newRecoverySlot();
        node.properties[RECOVERY_SLOT_PROPERTY] = control.value;
        node.graph?.change?.();
    }
}

export function ensureAcrossGraphs(node, root) {
    const graphs = graphTree(root);
    if (!graphs.has(node.graph)) return;
    const control = widget(node, "recovery_slot"), slot = node.properties?.[RECOVERY_SLOT_PROPERTY] || control?.value;
    if (!control || !slot) return;
    const duplicate = [...graphs].some(graph => (graph._nodes || []).some(other => other !== node
        && (other.properties?.[RECOVERY_SLOT_PROPERTY] || widget(other, "recovery_slot")?.value) === slot));
    if (duplicate) {
        control.value = newRecoverySlot(); node.properties ||= {};
        node.properties[RECOVERY_SLOT_PROPERTY] = control.value; node.graph?.change?.();
    }
}

function checkedValues(raw, data) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    const map = new Map();
    for (const name of NAMES) {
        if (!Object.hasOwn(raw, name)) return null;
        let value = raw[name];
        if (value === null && linked(data, name)) value = Object.hasOwn(NUMBERS, name) ? NUMBERS[name]
            : name === "aspect_ratio" ? "auto" : ENUMS[name]?.[0] ?? "";
        if (Object.hasOwn(NUMBERS, name) ? !Number.isSafeInteger(value) || value < 0 : typeof value !== "string") return null;
        if (ENUMS[name] && !ENUMS[name].includes(value)) return null;
        map.set(name, value);
    }
    return map;
}

function valuesFrom(data) {
    const candidates = [data?.properties?.[STATE], data?.widgets_values_named,
        Array.isArray(data?.widgets_values) && data.widgets_values.length === NAMES.length
            ? Object.fromEntries(NAMES.map((name, i) => [name, data.widgets_values[i]])) : null];
    for (const raw of candidates) {
        const values = checkedValues(raw, data);
        if (values) return values;
    }
    return null;
}

export function configure(node, data, original, args) {
    const values = valuesFrom(data);
    const safe = { ...(data || {}), widgets_values_named: {} };
    // Never let an unknown positional layout shift credentials or actions.
    safe.widgets_values = (node.widgets || []).map(w => values?.has(w.name) ? values.get(w.name) : w.name === "api_key" ? "" : w.value);
    if (values) safe.widgets_values_named = Object.fromEntries(values);
    const result = original?.apply(node, [safe, ...Array.from(args || []).slice(1)]);
    for (const [name, value] of values || []) {
        const w = widget(node, name);
        if (!w) continue;
        w.value = value;
        if (w.inputEl) w.inputEl.value = String(value);
    }
    if (widget(node, "api_key")) widget(node, "api_key").value = "";
    if (widget(node, "recovery_action")) widget(node, "recovery_action").value = "normal";
    if (values?.get("recovery_slot")) {
        node.properties ||= {};
        node.properties.t8_completion_recovery_slot = values.get("recovery_slot");
    }
    if (typeof data?.properties?.[OWNER_PROPERTY] === "string") {
        node.properties ||= {};
        node.properties[OWNER_PROPERTY] = data.properties[OWNER_PROPERTY];
    }
    bindOpenAIProviderPersistence(node);
    commitOpenAIProviderState(node);
    node.t8EnsureRecoverySlot?.();
    return result;
}

export function serialize(node, data) {
    node.t8EnsureRecoverySlot?.();
    commitOpenAIProviderState(node);
    data.widgets_values = NAMES.map(name => name === "recovery_action" ? "normal" : widget(node, name)?.value ?? null);
    syncNamedWidgetSerialization(data, NAMES);
    data.properties = { ...(data.properties || {}), [STATE]: { ...data.widgets_values_named },
        [RECOVERY_SLOT_PROPERTY]: node.properties?.[RECOVERY_SLOT_PROPERTY] || widget(node, "recovery_slot")?.value || "",
        ...(node.properties?.[OWNER_PROPERTY] ? { [OWNER_PROPERTY]: node.properties[OWNER_PROPERTY] } : {}) };
}

export function linkedProvider(node) {
    let id = node.inputs?.find(i => i.name === "provider_config")?.link;
    const seen = new Set();
    while (id != null && !seen.has(id) && seen.size < 128) {
        seen.add(id);
        const link = node.graph?.links?.get?.(id) || node.graph?.links?.[id];
        const source = node.graph?.getNodeById?.(link?.origin_id);
        if (!source) break;
        if ([source.type, source.comfyClass].includes("Reroute")) { id = source.inputs?.[0]?.link; continue; }
        return source;
    }
    return null;
}

export function effectiveMode(node) {
    const choice = widget(linkedProvider(node) || {}, "provider")?.value;
    return PROVIDER_MODES[choice] || widget(node, "api_mode")?.value || MODES[0];
}

export function providerLabel(node) {
    const connected = node.inputs?.some(input => input.name === "provider_config" && input.link != null);
    const choice = widget(linkedProvider(node) || {}, "provider")?.value;
    return connected && !PROVIDER_MODES[choice] ? "共享配置（执行时确定）/ Shared config at execution" : effectiveMode(node);
}

function visible(node, w, show) {
    const converted = Object.hasOwn(w, "origType") && w.type?.startsWith("converted-widget");
    const connected = linked(node, w.name), coexisting = typeof node.updateComputedDisabled === "function";
    show = (show || (connected && coexisting)) && (!connected || coexisting) && !converted;
    w.t8H3ImageOriginal ||= { type: converted ? w.origType : w.type, compute: converted ? w.origComputeSize : w.computeSize,
        display: w.element?.style?.display || "" };
    w.hidden = !show;
    if (!converted) {
        w.type = show ? w.t8H3ImageOriginal.type : "converted-widget";
        w.computeSize = show ? connected && coexisting ? () => [0, 20] : w.t8H3ImageOriginal.compute : () => [0, -4];
    }
    if (w.element) {
        w.element.hidden = !show || Boolean(connected);
        if (w.element.style) w.element.style.display = show && !connected ? w.t8H3ImageOriginal.display : "none";
    }
}

export function refresh(node, compact = false) {
    const mode = effectiveMode(node), local = mode === MODES[3], strata = mode === MODES[4], advanced = Boolean(node.t8H3ImageAdvanced);
    const dimensions = linked(node, "width") || linked(node, "height");
    for (const w of node.widgets || []) {
        if (!NAMES.includes(w.name) && w.name !== "api_key") continue;
        let show = NAMES.indexOf(w.name) < 5 || advanced;
        if (w.name === "aspect_ratio" && dimensions) show = false;
        if (w.name.startsWith("local_") || w.name === "seed") show = local && advanced;
        if (["local_model", "local_mmproj"].includes(w.name)) show = local;
        if (w.name === "llm_max_tokens") show = !local && !strata && advanced;
        if (["ai_workshop_model", "custom_model", "openai_base_url"].includes(w.name)) {
            show = !local && !strata && advanced
                && (w.name !== "ai_workshop_model" || mode === MODES[1])
                && (w.name !== "openai_base_url" || mode === MODES[2]);
        }
        if (w.name.startsWith("recovery_")) show = false;
        if (w.name === "api_key") show = !local && !strata;
        visible(node, w, show);
    }
    if (node.t8H3ImageProvider) node.t8H3ImageProvider.label = `实际渠道 / Effective: ${providerLabel(node)}`;
    if (node.computeSize && node.setSize) {
        const layout = (node.widgets || []).map(w => `${w.name}:${w.hidden}:${Boolean(linked(node, w.name))}`).join("|");
        // DOM widgets can report their allocated height back as a new minimum.
        // Reapplying that on an unchanged layout creates an ever-growing node.
        if (compact || node.t8H3ImageLayout !== layout) {
            const width = Math.max(node.size?.[0] || 550, 480), height = node.computeSize([width, 0])[1];
            if (Number.isFinite(height)) node.setSize([width, height]);
        }
        node.t8H3ImageLayout = layout;
    }
    node.setDirtyCanvas?.(true, true);
}

export function drawLinked(node, ctx) {
    if (node.flags?.collapsed || typeof node.updateComputedDisabled !== "function" || !ctx?.fillText) return;
    ctx.save(); ctx.fillStyle = "#aaa"; ctx.font = "12px sans-serif";
    for (const name of ["prompt", "locked_text"]) {
        const w = widget(node, name);
        if (w && linked(node, name) && Number.isFinite(w.last_y)) ctx.fillText(`${name}（已连接）`, 14, w.last_y + 14);
    }
    ctx.restore();
}
