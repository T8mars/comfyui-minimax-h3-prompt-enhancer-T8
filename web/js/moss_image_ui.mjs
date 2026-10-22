import { restoreNamedWidgetValues, serializeNamedWidgetValues, syncNamedWidgetSerialization } from "./widget_state.mjs";

export const MOSS_ID = "MOSSImagePromptEnhancerT8";
export const MOSS_STATE = "t8_moss_widgets_v1";
export const MOSS_PROFILE_SCHEMA = "t8_moss_widgets_schema";
export const CLASSIC = "Classic / 原版";
export const COMIC = "Comic / 漫画卡通";
export const FISHER = "Fisher / 通用长版";
export const MOSS_PROFILES = [CLASSIC, COMIC, FISHER];
export const GENERATE = "生成 / Generate";
export const COMPILE = "仅校验编译 / Compile only";
export const LEGACY_MOSS_NAMES = [
    "prompt", "operation", "output_format", "width", "height", "output_language", "api_mode",
    "locked_text", "max_output_chars", "max_corrections", "llm_max_tokens", "draft_json",
    "ai_workshop_model", "custom_model", "openai_base_url", "seed", "control_after_generate",
    "local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
    "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy", "recovery_slot", "recovery_action",
];
export const MOSS_NAMES = [...LEGACY_MOSS_NAMES, "authoring_profile"];
export const API_MODES = ["贞贞平价小屋（推荐）", "贞贞的AI工坊（图片/视频）", "OpenAI兼容接口（备用）",
    "本地 GGUF（llama.cpp / Qwen，离线）", "Strata 本地服务（桥接）"];
const FORMATS = ["AUTO / 自动", "Caption / 自然描述", "Layout / 空间排版"];
const LANGUAGES = ["按需求（默认英文）/ Auto", "English", "中文"];
const SEED_CONTROLS = ["fixed", "increment", "decrement", "randomize"];
const LINKED_TEXT_NAMES = new Set(["prompt", "draft_json", "locked_text", "custom_model", "openai_base_url"]);
const WORKSHOP_MODELS = ["gemini-3.5-flash", "Custom（自定义）"];
const ENUMS = { operation: [GENERATE, COMPILE], output_format: FORMATS, output_language: LANGUAGES,
    api_mode: API_MODES, control_after_generate: SEED_CONTROLS, recovery_action: ["normal", "restore_last"],
    authoring_profile: MOSS_PROFILES };
const INTS = new Set(["width", "height", "max_output_chars", "max_corrections", "llm_max_tokens", "seed", "local_context_size", "local_max_tokens"]);
const LINKED_NUMBER_DEFAULTS = { width: 1024, height: 1024, max_output_chars: 0, max_corrections: 1,
    llm_max_tokens: 16384, seed: 0, local_context_size: 32768, local_max_tokens: 16384 };
const ADVANCED = new Set(MOSS_NAMES.slice(7));
export const CANVAS_PRESETS = {
    "1:1": [1024, 1024], "3:4": [960, 1280], "4:3": [1280, 960],
    "16:9": [1536, 864], "9:16": [864, 1536], "2:1": [1536, 768], "1:2": [768, 1536],
};

function valueValid(name, value) {
    if (LINKED_TEXT_NAMES.has(name) && value == null) return true;
    if (ENUMS[name]) return ENUMS[name].includes(value);
    if (INTS.has(name)) {
        if (!Number.isInteger(value) || value < 0) return false;
        if (["width", "height"].includes(name)) return value >= 16 && value <= 16384 && value % 8 === 0;
        if (name === "max_corrections") return value <= 1;
        if (name === "max_output_chars") return value <= 20000;
        return Number.isFinite(value);
    }
    return typeof value === "string";
}

function hasSavedLink(data, name) {
    return Array.isArray(data?.inputs) && data.inputs.some(input => input?.link != null
        && (input.name === name || input.widget?.name === name));
}

function validatedMap(object, data) {
    if (!object || typeof object !== "object" || Array.isArray(object)) return null;
    const values = { ...object };
    // A connected number may have no saved native widget value. Normalize only
    // an explicit null with saved link evidence; never silently repair a bad
    // offline value or infer a link from a socket's mere existence.
    for (const name of INTS) if (Object.hasOwn(values, name) && values[name] === null && hasSavedLink(data, name)) {
        values[name] = LINKED_NUMBER_DEFAULTS[name];
    }
    if (!LEGACY_MOSS_NAMES.every(name => Object.hasOwn(values, name) && valueValid(name, values[name]))) return null;
    if (Object.hasOwn(values, "authoring_profile") && !valueValid("authoring_profile", values.authoring_profile)) return null;
    const mapped = new Map(LEGACY_MOSS_NAMES.map(name => [name, values[name]]));
    mapped.set("authoring_profile", values.authoring_profile ?? CLASSIC);
    for (const name of LINKED_TEXT_NAMES) if (mapped.get(name) == null) mapped.set(name, "");
    mapped.set("recovery_action", "normal");
    return mapped;
}

export function savedMossValues(data) {
    for (const source of [data?.properties?.[MOSS_STATE], data?.widgets_values_named]) {
        const mapped = validatedMap(source, data);
        if (mapped) return mapped;
    }
    if (!Array.isArray(data?.widgets_values)) return null;
    let values = [...data.widgets_values];
    if ([GENERATE, COMPILE].includes(values[0])) values.unshift(""); // omitted linked brief
    // Optional force-input key widget retained by a host is NOT a schema value.
    if (!API_MODES.includes(values[6]) && API_MODES.includes(values[7])) values.splice(6, 1);
    if (typeof values[7] === "string" && typeof values[8] === "string"
        && (Number.isInteger(values[9]) || values[9] === null && hasSavedLink(data, "max_output_chars"))) values.splice(7, 1);
    // A host may remove the linked draft widget as well as the linked brief.
    // Require the Workshop/model/URL/seed discriminators, never a length guess.
    if (WORKSHOP_MODELS.includes(values[11]) && typeof values[12] === "string" && typeof values[13] === "string"
        && (Number.isInteger(values[14]) || values[14] === null && hasSavedLink(data, "seed"))
        && (SEED_CONTROLS.includes(values[15]) || typeof values[15] === "string")) {
        values.splice(11, 0, "");
    }
    const names = [...LEGACY_MOSS_NAMES];
    if (!SEED_CONTROLS.includes(values[names.indexOf("control_after_generate")])) names.splice(names.indexOf("control_after_generate"), 1);
    if (values.length < names.length) return null;
    const object = Object.fromEntries(names.map((name, i) => [name, values[i]]));
    object.control_after_generate ??= "randomize";
    // Historical button tails can equal a new profile label. Only an explicit
    // version marker authorizes the positional 28th value. Complete named maps
    // above remain sufficient when a host drops that marker.
    object.authoring_profile = data?.properties?.[MOSS_PROFILE_SCHEMA] === 2
        && MOSS_PROFILES.includes(values[names.length]) ? values[names.length] : CLASSIC;
    return validatedMap(object, data); // all other action tails stay unmapped
}

export function configureMoss(node, data, original, args) {
    const mapped = savedMossValues(data);
    const input = { ...(data || {}) };
    if (mapped) {
        input.widgets_values = (node.widgets || []).map(w => mapped.has(w.name) ? mapped.get(w.name) : w.name === "api_key" ? "" : w.value);
        input.widgets_values_named = Object.fromEntries(mapped);
        if (node.widgets?.some(w => w.name === "api_key")) input.widgets_values_named.api_key = "";
    } else if (data?.widgets_values || data?.widgets_values_named || data?.properties?.[MOSS_STATE]) {
        // A malformed/unrecognized array must not reach native positional
        // loading and trigger a model scan with a value from another field.
        input.widgets_values = (node.widgets || []).map(w => w.name === "api_key" ? "" : w.name === "authoring_profile" ? CLASSIC : w.value);
        input.widgets_values_named = Object.fromEntries((node.widgets || [])
            .filter(w => MOSS_NAMES.includes(w.name)).map(w => [w.name, w.name === "authoring_profile" ? CLASSIC : w.value]));
    }
    const result = original?.apply(node, [input, ...Array.from(args || []).slice(1)]);
    if (mapped) {
        restoreNamedWidgetValues(node, mapped);
        for (const widget of node.widgets || []) if (mapped.has(widget.name) && widget.inputEl) widget.inputEl.value = String(mapped.get(widget.name) ?? "");
        if (mapped.get("recovery_slot")) {
            node.properties ||= {};
            node.properties.t8_completion_recovery_slot = mapped.get("recovery_slot");
        }
    } else {
        const profile = node.widgets?.find(w => w.name === "authoring_profile");
        if (profile) profile.value = CLASSIC;
    }
    const action = node.widgets?.find(w => w.name === "recovery_action");
    if (action) action.value = "normal";
    node.t8EnsureRecoverySlot?.();
    return result;
}

export function serializeMoss(node, data) {
    node.t8EnsureRecoverySlot?.();
    data.widgets_values = serializeNamedWidgetValues(node, MOSS_NAMES, (name, value) =>
        name === "recovery_action" ? "normal" : name === "control_after_generate" ? value ?? "randomize"
            : name === "authoring_profile" ? MOSS_PROFILES.includes(value) ? value : CLASSIC : value);
    syncNamedWidgetSerialization(data, MOSS_NAMES);
    data.properties = { ...(data.properties || {}), [MOSS_STATE]: { ...data.widgets_values_named }, [MOSS_PROFILE_SCHEMA]: 2 };
}

export function linkedMossProvider(node) {
    const port = node.inputs?.find(i => i.name === "provider_config");
    let linkId = port?.link;
    const visited = new Set();
    for (let i = 0; i < 128 && linkId != null && !visited.has(linkId); i++) {
        visited.add(linkId);
        const link = node.graph?.links?.get?.(linkId) || node.graph?.links?.[linkId];
        const source = node.graph?.getNodeById?.(link?.origin_id);
        if (!source) break;
        if ([source.type, source.comfyClass].includes("Reroute")) { linkId = source.inputs?.[0]?.link; continue; }
        return source;
    }
    return null;
}

export function effectiveMossMode(node) {
    const provider = linkedMossProvider(node)?.widgets?.find(w => w.name === "provider")?.value;
    const selected = { "Seedance NZ": API_MODES[0], "T8 AI Workshop": API_MODES[1], "OpenAI Compatible": API_MODES[2],
        "Local Qwen": API_MODES[3], Strata: API_MODES[4] }[provider];
    if (selected) return selected;
    return node.widgets?.find(w => w.name === "api_mode")?.value || API_MODES[0];
}

function visible(node, widget, show) {
    if (!widget) return;
    // Older hosts own converted widgets (including their serialization hook).
    // Never resurrect those as editable controls during a mode refresh. Newer
    // hosts expose widget sockets even when unconnected: existence is not enough.
    const nativeConverted = Object.hasOwn(widget, "origType") && widget.type?.startsWith("converted-widget");
    const connected = node.inputs?.some(input => input.link != null
        && (input.widget?.name === widget.name || input.name === widget.name));
    // The coexisting-socket host draws a compact linked-row label itself. It
    // must keep that row in its layout or the socket is anchored to a stale y.
    const inlineSockets = typeof node.updateComputedDisabled === "function";
    show = (show || (connected && inlineSockets)) && (!connected || inlineSockets) && !nativeConverted;
    widget.t8MossOriginal ||= { type: nativeConverted ? widget.origType : widget.type,
        compute: nativeConverted ? widget.origComputeSize : widget.computeSize,
        display: widget.element?.style?.display || "" };
    widget.hidden = !show;
    if (!nativeConverted) {
        widget.type = show ? widget.t8MossOriginal.type : "converted-widget";
        widget.computeSize = show ? connected && inlineSockets ? () => [0, 20] : widget.t8MossOriginal.compute : () => [0, -4];
    }
    if (widget.element) {
        widget.element.hidden = !show;
        if (widget.element.style) widget.element.style.display = show ? widget.t8MossOriginal.display : "none";
    }
}

export function refreshMoss(node, compact = false) {
    const find = name => node.widgets?.find(w => w.name === name);
    const compile = find("operation")?.value === COMPILE;
    const mode = effectiveMossMode(node), local = mode === API_MODES[3], strata = mode === API_MODES[4];
    for (const widget of node.widgets || []) {
        if (!MOSS_NAMES.includes(widget.name) && widget.name !== "api_key") continue;
        let show = !ADVANCED.has(widget.name);
        if (ADVANCED.has(widget.name)) show = Boolean(node.t8MossAdvanced);
        if (["recovery_slot", "recovery_action", "control_after_generate"].includes(widget.name)) show = false;
        if (widget.name === "draft_json") show = compile;
        if (["prompt", "output_format", "output_language", "api_mode", "max_output_chars", "authoring_profile"].includes(widget.name)) show = !compile;
        if (widget.name === "api_key") show = !compile && !local && !strata;
        if (widget.name.startsWith("local_")) show = !compile && local && Boolean(node.t8MossAdvanced);
        if (["locked_text", "max_corrections", "llm_max_tokens", "seed"].includes(widget.name)) show = !compile && Boolean(node.t8MossAdvanced);
        if (widget.name === "llm_max_tokens" && (local || strata)) show = false;
        if (["ai_workshop_model", "custom_model", "openai_base_url"].includes(widget.name)) {
            show = !compile && !local && !strata && Boolean(node.t8MossAdvanced)
                && (widget.name !== "openai_base_url" || mode === API_MODES[2])
                && (widget.name !== "ai_workshop_model" || mode === API_MODES[1]);
        }
        visible(node, widget, show);
    }
    if (node.t8MossHelpWidget) node.t8MossHelpWidget.label = compile
        ? "📖 仅编译：0次LLM、无需Key；Layout尺寸取草稿 / Help"
        : local || strata ? "📖 本地增强无需云Key；参考图不是MOSS编辑 / Help" : "📖 使用说明 · 云端参考图将发送所选服务 / Help";
    if (node.t8MossProviderWidget) node.t8MossProviderWidget.label = compile ? "渠道不参与 / Provider inactive" : `实际渠道 / Effective: ${mode}`;
    if (node.computeSize && node.setSize) {
        const width = Math.max(node.size?.[0] || 540, 420);
        const minimum = node.computeSize([width, 0])[1];
        const current = node.size?.[1] || 0;
        const layout = (node.widgets || []).map(w => `${w.name}:${Boolean(w.hidden)}`).join("|");
        if (Number.isFinite(minimum) && (compact || layout !== node.t8MossLayout || current < minimum || current === node.t8MossAutoHeight)) {
            node.setSize([width, minimum]); node.t8MossAutoHeight = minimum;
        }
        node.t8MossLayout = layout;
    }
    node.setDirtyCanvas?.(true, true);
}

export function drawMossLinkedLabels(node, context) {
    // Native number/combo widgets draw their own suppressed-row labels. Some
    // native DOM multiline widgets have no concrete canvas renderer; add only
    // their label, never another widget or a second serialized value.
    if (node.flags?.collapsed || typeof node.updateComputedDisabled !== "function" || !context?.fillText) return;
    const labels = { prompt: "创作需求 / Brief（已连接）", draft_json: "原始草稿 / Draft JSON（已连接）",
        locked_text: "锁定文案 / Exact text（已连接）" };
    context.save();
    context.fillStyle = "#aaa"; context.font = "12px sans-serif"; context.textAlign = "left";
    for (const [name, label] of Object.entries(labels)) {
        const widget = node.widgets?.find(w => w.name === name);
        if (!widget || widget.type !== "customtext" || !Number.isFinite(widget.y)
            || !node.inputs?.some(i => i.name === name && i.link != null)) continue;
        context.fillText(label, 24, widget.y + 15, Math.max(0, (node.size?.[0] || 420) - 48));
    }
    context.restore();
}

function historicalAuthoringSummary(status) {
    if (!MOSS_PROFILES.includes(status?.authoring_profile)) return "";
    const profile = `历史强化 / Result profile: ${status.authoring_profile}\n`;
    const info = status.authoring_length;
    if (!info || typeof info !== "object" || Array.isArray(info)
        || info.metric !== "unicode_code_points" || info.hard_enforced !== false
        || !Number.isInteger(info.description_chars) || info.description_chars < 0 || info.description_chars > 262144
        || !Number.isInteger(info.han_chars) || info.han_chars < 0 || info.han_chars > info.description_chars
        || !Number.isInteger(info.max_output_chars) || info.max_output_chars < 0 || info.max_output_chars > 20000
        || typeof info.status !== "string") return profile;
    const target = info.target_han_range;
    if (target !== null && (!Array.isArray(target) || target.length !== 2
        || target[0] !== 1500 || target[1] !== 2500 || info.max_output_chars !== 0
        || status.authoring_profile !== FISHER)) return profile;
    const expected = info.max_output_chars ? info.description_chars > info.max_output_chars ? "over_limit" : "within_limit"
        : target ? info.han_chars < 1500 ? "below_target" : info.han_chars > 2500 ? "above_target" : "within_target" : "automatic";
    if (info.status !== expected) return profile;
    const maximum = info.max_output_chars ? ` · 软上限 / Soft cap ${info.max_output_chars}` : " · 自动 / Automatic";
    const preference = target ? " · 汉字软目标 / Han target 1500–2500" : "";
    const warning = info.status === "over_limit" ? " · ⚠ 超限，保留完整稿 / Complete draft kept"
        : ["below_target", "above_target"].includes(info.status) ? " · ⚠ 未达软目标 / Creative target unmet" : "";
    return profile + `实际描述 / Actual: ${info.description_chars} 码点 / code points · ${info.han_chars} 汉字 / Han${maximum}${preference}${warning}\n`;
}

export function mossStatus(status, stale = false) {
    if (!status) return "等待执行 / Ready · MOSS 4096 Token预算未核验";
    const format = ["caption", "layout"].includes(status.format) ? status.format : "unknown";
    const dimensions = [status.width, status.height].every(Number.isInteger) ? `${status.width}×${status.height}` : "unknown";
    const calls = Number.isInteger(status.calls) && status.calls >= 0 && status.calls <= 2 ? status.calls : "?";
    const warnings = Array.isArray(status.warnings) ? status.warnings : [];
    const warning = warnings.includes("correction_failed_draft_kept") ? " · ⚠ 纠正失败，保留首稿 / Draft kept"
        : warnings.includes("description_over_limit") ? " · ⚠ 描述超字数，保留完整稿 / Over limit" : "";
    const alignment = warnings.includes("eight_pixel_canvas_downstream_unverified") ? " · 8像素兼容，核对下游画布 / Check downstream canvas" : "";
    return `${stale ? "⚠ 上次结果，配置已改 / Stale" : status.origin === "cache" ? "恢复原结果 / Restored" : "结构通过，非成图保证 / Structure only"}${warning}\n`
        + `${format} · ${dimensions} · ${calls} 次 LLM · MOSS 4096 Token未核验${alignment}\n`
        + historicalAuthoringSummary(status)
        + "positive_prompt接正向文本；宽高接最终latent。draft/report不是生成提示词。";
}

export function layoutPreview(draftText, documentObject = globalThis.document) {
    const root = documentObject.createElement("div");
    const title = documentObject.createElement("p");
    title.textContent = "位置示意，不是成图／字体或质量验收 / Geometry only, not a generated image";
    root.append(title);
    if (typeof draftText !== "string" || draftText.length > 262144) throw new Error("Draft preview budget exceeded");
    const draft = JSON.parse(draftText);
    if (![draft.width, draft.height].every(v => Number.isInteger(v) && v > 0 && v <= 16384)
        || draft.bbox_coord_space !== "abs" || draft.bbox_format !== "xyxy" || !Array.isArray(draft.items) || draft.items.length > 128) {
        const note = documentObject.createElement("p"); note.textContent = "Caption没有坐标布局 / Caption has no layout"; root.append(note); return root;
    }
    const board = documentObject.createElement("div");
    Object.assign(board.style, { position: "relative", width: "640px", maxWidth: "80vw", aspectRatio: `${draft.width}/${draft.height}`, background: "#20252c", overflow: "hidden" });
    const palette = ["#80c9ff", "#f5b85f", "#baee93", "#e7a3f7"];
    for (const [index, item] of draft.items.entries()) {
        const box = item.bbox;
        if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)
            || box[0] < 0 || box[1] < 0 || box[2] > draft.width || box[3] > draft.height || box[0] >= box[2] || box[1] >= box[3]) throw new Error("Invalid preview box");
        const region = documentObject.createElement("div");
        Object.assign(region.style, { position: "absolute", boxSizing: "border-box", overflow: "hidden", whiteSpace: "pre-wrap",
            border: `2px solid ${palette[index % palette.length]}`, color: palette[index % palette.length], font: "12px sans-serif",
            left: `${100 * box[0] / draft.width}%`, top: `${100 * box[1] / draft.height}%`,
            width: `${100 * (box[2] - box[0]) / draft.width}%`, height: `${100 * (box[3] - box[1]) / draft.height}%` });
        const label = ["object", "character", "text"].includes(item.label) ? item.label : "item";
        region.textContent = `${index + 1} ${label}\n${String(item.text || item.caption || "").slice(0, 160)}`;
        board.append(region);
    }
    root.append(board);
    const footer = documentObject.createElement("p"); footer.textContent = "示意文字仅显示前160字，不会修改完整输出 / Preview abbreviates only the display."; root.append(footer);
    return root;
}
