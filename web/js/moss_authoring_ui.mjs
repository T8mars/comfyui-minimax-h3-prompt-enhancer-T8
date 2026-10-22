import { restoreNamedWidgetValues, serializeNamedWidgetValues, syncNamedWidgetSerialization } from "./widget_state.mjs";
import { ensureUniqueSlot, RECOVERY_SLOT_PROPERTY } from "./completion_recovery_core.mjs";

export const DIRECTOR_ID = "MOSSAuthoringDirectorT8";
export const DIRECTOR_STATE = "t8_moss_authoring_widgets_v1";
export const COMIC = "Comic / 漫画卡通";
export const FISHER = "Fisher / 通用长版";
export const AUTO_LANGUAGE = "Auto / 自动（Fisher默认中文）";
export const DIRECTOR_NAMES = ["brief", "profile", "width", "height", "max_output_chars", "max_corrections", "page_count",
    "reference_mode", "descriptive_language", "locked_text", "continuity_context", "layout_context_json", "preserve_layout",
    "llm_max_tokens", "seed", "recovery_slot", "recovery_action"];
export const DIRECTOR_DEFAULTS = { brief: "", profile: COMIC, width: 1024, height: 1024, max_output_chars: 0,
    max_corrections: 1, page_count: 0, reference_mode: "independent", descriptive_language: AUTO_LANGUAGE,
    locked_text: "", continuity_context: "", layout_context_json: "", preserve_layout: true,
    llm_max_tokens: 16384, seed: 0, recovery_slot: "", recovery_action: "normal" };
const INTERNAL = new Set(["recovery_slot", "recovery_action"]);
const ROW_LABELS = { brief: "创作/修订需求 / Brief", locked_text: "锁定文案 / Exact text",
    continuity_context: "连续性事实 / Human continuity", layout_context_json: "整册修订上下文 / Revision context",
    bundle_json: "完整集合 / Bundle JSON" };
const TEXT_BUDGETS = { brief: 64000, locked_text: 32000, continuity_context: 64000,
    layout_context_json: 2 * 1024 * 1024, recovery_slot: 160 };
const ENUMS = { profile: [COMIC, FISHER], reference_mode: ["independent", "fusion"],
    descriptive_language: [AUTO_LANGUAGE, "English", "中文"], recovery_action: ["normal", "restore_last"] };

function savedLink(data, name) {
    return Array.isArray(data?.inputs) && data.inputs.some(input => input?.link != null
        && (input.name === name || input.widget?.name === name));
}

function unicodeText(value) {
    for (let index = 0; index < value.length; index++) {
        const current = value.charCodeAt(index);
        if (current >= 0xd800 && current <= 0xdbff) {
            const next = value.charCodeAt(++index);
            if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
        } else if (current >= 0xdc00 && current <= 0xdfff) return false;
    }
    return true;
}

function validValue(name, value) {
    if (ENUMS[name]) return ENUMS[name].includes(value);
    if (name === "preserve_layout") return typeof value === "boolean";
    if (Object.hasOwn(TEXT_BUDGETS, name)) return typeof value === "string" && unicodeText(value)
        && new TextEncoder().encode(value).length <= TEXT_BUDGETS[name];
    if (!Number.isInteger(value) || value < 0) return false;
    if (["width", "height"].includes(name)) return value >= 16 && value <= 16384 && value % 8 === 0;
    if (name === "max_output_chars") return value <= 20000;
    if (name === "max_corrections") return value <= 1;
    if (name === "page_count") return value <= 16;
    if (name === "llm_max_tokens") return value >= 256 && value <= 65536;
    return name === "seed" && value <= 0xffffffffffffffff;
}

function namedMap(source, data) {
    if (!source || typeof source !== "object" || Array.isArray(source)) return null;
    const result = new Map();
    for (const name of DIRECTOR_NAMES) {
        if (!Object.hasOwn(source, name)) return null;
        let value = source[name];
        if (value === null && !INTERNAL.has(name) && savedLink(data, name)) value = DIRECTOR_DEFAULTS[name];
        if (!validValue(name, value)) return null;
        result.set(name, name === "recovery_action" ? "normal" : value);
    }
    return result;
}

export function savedDirectorValues(data) {
    for (const source of [data?.properties?.[DIRECTOR_STATE], data?.widgets_values_named]) {
        const values = namedMap(source, data);
        if (values) return values;
    }
    if (!Array.isArray(data?.widgets_values) || data.widgets_values.length < DIRECTOR_NAMES.length) return null;
    return namedMap(Object.fromEntries(DIRECTOR_NAMES.map((name, index) => [name, data.widgets_values[index]])), data);
}

export function ensureDirectorSlot(node) {
    const widget = node.widgets?.find(item => item.name === "recovery_slot");
    if (widget && (typeof widget.value !== "string" || widget.value && !/^[A-Za-z0-9._:-]{8,160}$/.test(widget.value))) widget.value = "";
    const property = node.properties?.[RECOVERY_SLOT_PROPERTY];
    if (property && (typeof property !== "string" || !/^[A-Za-z0-9._:-]{8,160}$/.test(property))) delete node.properties[RECOVERY_SLOT_PROPERTY];
    return ensureUniqueSlot(node, widget);
}

export function configureDirector(node, data, original, args) {
    const saved = savedDirectorValues(data);
    const values = saved || new Map(Object.entries(DIRECTOR_DEFAULTS));
    const slot = values.get("recovery_slot");
    const input = { ...(data || {}), properties: { ...(data?.properties || {}), [RECOVERY_SLOT_PROPERTY]: slot },
        widgets_values: (node.widgets || []).map(widget => values.has(widget.name) ? values.get(widget.name) : widget.value),
        widgets_values_named: Object.fromEntries(values) };
    const result = original?.apply(node, [input, ...Array.from(args || []).slice(1)]);
    restoreNamedWidgetValues(node, values);
    for (const widget of node.widgets || []) if (values.has(widget.name) && widget.inputEl) widget.inputEl.value = String(values.get(widget.name));
    node.properties ||= {};
    node.properties[RECOVERY_SLOT_PROPERTY] = slot;
    ensureDirectorSlot(node);
    hideDirectorInternals(node);
    return result;
}

export function serializeDirector(node, data) {
    ensureDirectorSlot(node);
    data.widgets_values = serializeNamedWidgetValues(node, DIRECTOR_NAMES, (name, value) => name === "recovery_action" ? "normal" : value);
    syncNamedWidgetSerialization(data, DIRECTOR_NAMES);
    data.properties = { ...(data.properties || {}), [DIRECTOR_STATE]: { ...data.widgets_values_named },
        [RECOVERY_SLOT_PROPERTY]: data.widgets_values_named.recovery_slot };
}

export function hideDirectorInternals(node) {
    for (const widget of node.widgets || []) if (INTERNAL.has(widget.name)) {
        widget.hidden = true;
        widget.type = "converted-widget";
        widget.computeSize = () => [0, -4];
        if (widget.element) {
            widget.element.hidden = true;
            if (widget.element.style) widget.element.style.display = "none";
        }
        if (widget.name === "recovery_action") widget.value = "normal";
    }
    node.setDirtyCanvas?.(true, true);
}

export function refreshAuthoringRows(node) {
    const inline = typeof node.updateComputedDisabled === "function";
    for (const widget of node.widgets || []) {
        if (!Object.hasOwn(ROW_LABELS, widget.name)) continue;
        const converted = Object.hasOwn(widget, "origType") && widget.type?.startsWith("converted-widget");
        const connected = node.inputs?.some(input => input.link != null && (input.name === widget.name || input.widget?.name === widget.name));
        widget.t8AuthoringRow ||= { type: converted ? widget.origType : widget.type,
            compute: converted ? widget.origComputeSize : widget.computeSize, display: widget.element?.style?.display || "" };
        const show = !converted && (!connected || inline);
        widget.hidden = !show;
        if (!converted) {
            widget.type = show ? widget.t8AuthoringRow.type : "converted-widget";
            widget.computeSize = show ? connected && inline ? () => [0, 20] : widget.t8AuthoringRow.compute : () => [0, -4];
        }
        if (widget.element) {
            widget.element.hidden = !show;
            if (widget.element.style) widget.element.style.display = show ? widget.t8AuthoringRow.display : "none";
        }
        if (widget.inputEl) widget.inputEl.placeholder = ROW_LABELS[widget.name];
    }
    if (node.computeSize && node.setSize) {
        const layout = Object.keys(ROW_LABELS).map(name => `${name}:${node.inputs?.some(i => i.name === name && i.link != null)}`).join("|");
        const width = Math.max(node.size?.[0] || 440, 420), height = node.computeSize([width, 0])[1];
        if (Number.isFinite(height) && (layout !== node.t8AuthoringRowsLayout || node.size?.[1] < height)) node.setSize([width, height]);
        node.t8AuthoringRowsLayout = layout;
    }
    node.setDirtyCanvas?.(true, true);
}

export function drawAuthoringLinkedLabels(node, context) {
    if (node.flags?.collapsed || typeof node.updateComputedDisabled !== "function" || !context?.fillText) return;
    context.save(); context.fillStyle = "#aaa"; context.font = "12px sans-serif"; context.textAlign = "left";
    for (const [name, label] of Object.entries(ROW_LABELS)) {
        const widget = node.widgets?.find(item => item.name === name);
        if (widget?.type === "customtext" && Number.isFinite(widget.y) && node.inputs?.some(i => i.name === name && i.link != null))
            context.fillText(`${label}（已连接）`, 24, widget.y + 15, Math.max(0, (node.size?.[0] || 420) - 48));
    }
    context.restore();
}

function currentRequest(node, slot, graph, epoch) {
    return !node.t8AuthoringRemoved && node.graph === graph && graph != null
        && (!Array.isArray(graph._nodes) || graph._nodes.includes(node))
        && (node.t8AuthoringEpoch || 0) === epoch
        && node.widgets?.find(widget => widget.name === "recovery_slot")?.value === slot
        && node.properties?.[RECOVERY_SLOT_PROPERTY] === slot;
}

export async function restoreDirector({ node, fetchFn, queuePrompt, alertFn }) {
    if (node.t8AuthoringRestoring || node.t8AuthoringRemoved) return false;
    node.t8AuthoringRestoring = true;
    const slot = ensureDirectorSlot(node), graph = node.graph, epoch = node.t8AuthoringEpoch || 0;
    const active = () => currentRequest(node, slot, graph, epoch);
    const action = node.widgets?.find(widget => widget.name === "recovery_action");
    try {
        if (!action || !slot || !graph || typeof fetchFn !== "function" || typeof queuePrompt !== "function") throw new Error("unavailable");
        const response = await fetchFn(`/t8-prompt-enhancer/moss-authoring/status/${encodeURIComponent(slot)}`,
            { cache: "no-store", headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("status");
        const status = await response.json();
        if (!active()) return false;
        if (status?.recoverable !== true) {
            alertFn?.("没有可恢复的完整集合，或结果已过期。不会自动重新生成 / No complete cached collection; no generation was queued.");
            return false;
        }
        action.value = "restore_last";
        await queuePrompt(0, 1, [node.id]);
        return true;
    } catch {
        if (active()) alertFn?.("恢复检查失败，未重新生成 / Recovery check failed; no automatic generation.");
        return false;
    } finally {
        if (action) action.value = "normal";
        node.t8AuthoringRestoring = false;
        node.setDirtyCanvas?.(true, true);
    }
}

export async function inspectDirector({ node, fetchFn, showText, alertFn }) {
    if (node.t8AuthoringInspecting || node.t8AuthoringRemoved) return false;
    node.t8AuthoringInspecting = true;
    const slot = ensureDirectorSlot(node), graph = node.graph, epoch = node.t8AuthoringEpoch || 0;
    const active = () => currentRequest(node, slot, graph, epoch);
    try {
        if (!slot || !graph || typeof fetchFn !== "function") throw new Error("unavailable");
        const response = await fetchFn(`/t8-prompt-enhancer/moss-authoring/draft/${encodeURIComponent(slot)}`,
            { cache: "no-store", headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("missing");
        const artifact = await response.json();
        if (!active()) return false;
        if (artifact?.schema_version !== "t8-moss-authoring-inspection/v1" || artifact.inspection_only !== true || artifact.complete !== false) throw new Error("not inspection");
        const text = JSON.stringify(artifact, null, 2);
        if (new TextEncoder().encode(JSON.stringify(artifact)).length > 2 * 1024 * 1024) throw new Error("budget");
        showText?.(text, "失败检查稿（不可接正向）/ Inspection only");
        return true;
    } catch {
        if (active()) alertFn?.("没有可用检查稿、已过期或格式无效 / No valid retained inspection draft.");
        return false;
    } finally {
        node.t8AuthoringInspecting = false;
    }
}

export const DIRECTOR_HELP = "MOSS Authoring Director T8\n"
    + "生成的是完整集合bundle，不是正向提示词。连接MOSS Authoring Page，选择1起页码与en/zh，再把positive_prompt及宽高接下游。缺语言会报错，不自动翻译。\n"
    + "Comic正常调用1次规划+每编辑页英文/中文各1次，即1+2N；Fisher默认每张展开参考图独立1稿（N次），fusion明确融合为1稿（1次）。每个阶段最多额外1次纠正，可能增加调用；本节点不生图。\n"
    + "字数为描述Unicode码点（含空格标点，不含Layout.text/坐标/JSON），软上限且不截稿，不是Token。Fisher自动中文无显式长度时使用1500–2500汉字软目标；明确语言、短版、上限优先。\n"
    + "云端时参考图片发送给所选增强服务；Fisher独立稿只发送自己的图，Comic图作上下文，中文翻译不再发图。仅增强LLM理解，不是MOSS原生编辑。\n"
    + "修订上下文是schema_version=t8-moss-authoring-context/v1、mode=full_layout或panels_only、bundle=原完整集合、edit_unit_ids=明确页ID数组。未选页原样复制，零编辑不调用LLM；编辑有图集合须重接原顺序同内容图片。关闭布局保留也不解除可见原文锁。\n"
    + "完整结果只在当前进程内存中保留1小时（最多50槽）；恢复只读取原结果、不按当前设置重写。失败稿仅供同源检查，inspection_only=true且complete=false，绝不能当完整集合或正向提示词。\n"
    + "结构/共几何通过不是翻译、语义、字体、MOSS 4096 Token或成图效果验收。English: choose a single Page/language for one native positive prompt; bundle/report/source metadata are not positive prompts.";
