import { app } from "../../scripts/app.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";
import { RECOVERY_SLOT_PROPERTY } from "./completion_recovery_core.mjs";
import { showRedactedDiagnostics } from "./diagnostics_viewer.mjs";
import {
    copyLocalModelDirectory,
    openLlamaCppPythonWheels,
    showLocalQwenStatus,
} from "./local_qwen_status.js";
import { showProviderCapability } from "./provider_capability_ui.mjs";
import { restoreNamedWidgetValues, serializeNamedWidgetValues } from "./widget_state.mjs";


const NODE_ID = "QwenImage21PromptEnhancerT8";
const LEGACY_EXAMPLE_TITLE = "填写 API Key（建议使用环境变量，不要把密钥保存到工作流）";
const EXAMPLE_TITLE = "Qwen Image 2.1 提示词增强（本地 GGUF 无需 API Key）";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const AI_WORKSHOP_SIGN_UP_URL = "https://ai.t8star.org/register?aff=dP7j";
const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（图片/视频）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const LOCAL_QWEN_API_MODES = new Set([
    "本地 GGUF（llama.cpp / Qwen，离线）",
    "本地 Qwen3.8-27B（GGUF，离线）",
]);
const API_MODES = new Set([
    "贞贞平价小屋（推荐）", AI_WORKSHOP_API_MODE, OPENAI_API_MODE,
    ...LOCAL_QWEN_API_MODES,
]);
const SEED_CONTROLS = new Set(["fixed", "increment", "decrement", "randomize"]);
// Canonical workflow order has no api_key widget: the backend declares it as
// force_input. The seed's linked control is a widget on newer frontends.
const SERIALIZED_WIDGET_NAMES = [
    "prompt", "input_mode", "max_output_chars", "wh_ratio", "transparent_alpha",
    "api_mode", "ai_workshop_model", "custom_model", "openai_base_url", "seed",
    "control_after_generate", "local_model", "local_mmproj", "local_context_size",
    "local_max_tokens", "local_think_mode", "local_reasoning_effort",
    "local_video_sample_fps", "local_unload_policy", "local_comfy_memory_policy",
    "recovery_slot", "recovery_action",
];
const WIDGET_DEFAULTS = { prompt: "", api_key: "", control_after_generate: "randomize", recovery_action: "normal" };


function savedWidgetValueMap(values) {
    // Some hosts omit a converted, linked prompt widget entirely rather than
    // serializing its empty value. Normalize that historical shape first.
    if (Array.isArray(values) && ["文生图 / Text-to-image", "图像编辑 / Image edit"].includes(values[0])
        && Number.isInteger(values[1])) values = ["", ...values];
    if (!Array.isArray(values) || values.length < 19 || (typeof values[0] !== "string" && values[0] != null)
        || !["文生图 / Text-to-image", "图像编辑 / Image edit"].includes(values[1])
        || !Number.isInteger(values[2]) || values[2] < 0 || values[2] > 12000
        || !["auto", "1:1", "3:4", "4:3", "16:9", "9:16", "2:1", "1:2"].includes(values[3])
        || typeof values[4] !== "boolean") return null;
    const hasApiKey = API_MODES.has(values[6]) && !API_MODES.has(values[5]);
    const withoutApiKey = API_MODES.has(values[5]) && !API_MODES.has(values[6]);
    if (!hasApiKey && !withoutApiKey) return null;
    const seedIndex = hasApiKey ? 10 : 9;
    if (typeof values[seedIndex] !== "number" || !Number.isFinite(values[seedIndex])) return null;
    const hasSeedControl = SEED_CONTROLS.has(values[seedIndex + 1]);
    const names = SERIALIZED_WIDGET_NAMES.slice(0, -2);
    if (!hasSeedControl) names.splice(names.indexOf("control_after_generate"), 1);
    if (hasApiKey) names.splice(names.indexOf("api_mode"), 0, "api_key");
    if (values.length < names.length) return null;
    const mapped = new Map(names.map((name, index) => [name, values[index]]));
    if (mapped.get("prompt") == null) mapped.set("prompt", "");
    const recovery = values.slice(names.length);
    if (typeof recovery[0] === "string" && (recovery[0] === "" || recovery[0].startsWith("t8-"))) {
        mapped.set("recovery_slot", recovery[0]);
        if (["normal", "restore_last"].includes(recovery[1])) mapped.set("recovery_action", "normal");
    }
    return mapped;
}


function projectWidgetValues(node, mapped) {
    return (node.widgets || []).map((widget) => {
        if (mapped.has(widget.name)) return mapped.get(widget.name);
        if (Object.hasOwn(WIDGET_DEFAULTS, widget.name)) return WIDGET_DEFAULTS[widget.name];
        return widget.value;
    });
}


function restoreWidgetValues(node, mapped, restoreSavedSlot = false) {
    if (mapped) restoreNamedWidgetValues(node, mapped, new Set(["recovery_action"]));
    const apiKey = node.widgets?.find((widget) => widget.name === "api_key");
    if (mapped && apiKey && !mapped.has("api_key")) apiKey.value = "";
    const seedControl = node.widgets?.find((widget) => widget.name === "control_after_generate");
    if (mapped && seedControl && !mapped.has("control_after_generate")) seedControl.value = WIDGET_DEFAULTS.control_after_generate;
    const savedSlot = mapped?.get("recovery_slot");
    if (restoreSavedSlot && typeof savedSlot === "string" && savedSlot.startsWith("t8-")) {
        node.properties ||= {};
        node.properties[RECOVERY_SLOT_PROPERTY] = savedSlot;
    }
    for (const name of ["prompt", "custom_model", "openai_base_url", "api_key"]) {
        const widget = node.widgets?.find((item) => item.name === name);
        if (widget?.inputEl && mapped && (mapped.has(name) || name === "api_key")) {
            widget.inputEl.value = String(mapped.get(name) ?? "");
        }
    }
    const action = node.widgets?.find((widget) => widget.name === "recovery_action");
    if (action) action.value = "normal";
    node.t8EnsureRecoverySlot?.();
    node.t8QwenImage21UpdateApiMode?.();
}


export function qwenImage21SignUpUrl(apiMode) {
    return apiMode === AI_WORKSHOP_API_MODE ? AI_WORKSHOP_SIGN_UP_URL : SIGN_UP_URL;
}


function setActionVisible(widget, visible) {
    if (!widget) return;
    if (!("t8OriginalType" in widget)) {
        widget.t8OriginalType = widget.type;
        widget.t8OriginalComputeSize = widget.computeSize;
        widget.t8OriginalHidden = Boolean(widget.hidden);
    }
    widget.type = visible ? widget.t8OriginalType : "converted-widget";
    widget.computeSize = visible ? widget.t8OriginalComputeSize : () => [0, -4];
    widget.hidden = visible ? widget.t8OriginalHidden : true;
}


function resizeNode(node) {
    if (!node?.computeSize || !node?.setSize || !node?.size) return;
    requestAnimationFrame(() => {
        node.setSize([node.size[0], node.computeSize()[1]]);
        node.setDirtyCanvas?.(true, true);
    });
}


function addAction(node, label, tooltip, callback) {
    const widget = node.addWidget("button", label, tooltip, callback, { serialize: false });
    widget.serializeValue = () => undefined;
    return widget;
}


export function installQwenImage21Actions(node) {
    if (node.t8QwenImage21ActionsInstalled) return;
    node.t8QwenImage21ActionsInstalled = true;
    const find = (name) => node.widgets?.find((widget) => widget.name === name);
    const apiModeWidget = find("api_mode");
    const baseUrlWidget = find("openai_base_url");

    addAction(node, "🧭 渠道能力预检", "查看当前渠道的已知与未知能力边界", () =>
        showProviderCapability(apiModeWidget?.value, baseUrlWidget?.value));
    addAction(node, "🩺 查看/复制脱敏诊断", "不包含 Key、提示词、图片或响应正文", () =>
        showRedactedDiagnostics(NODE_ID));
    addCompletionRecoveryButton(node, NODE_ID);

    let queuing = false;
    addAction(node, "▶ 运行 Qwen Image 提示词优化", "提交当前节点", async () => {
        if (queuing) return;
        queuing = true;
        try {
            await app.queuePrompt(0, 1, [String(node.id)]);
        } finally {
            queuing = false;
        }
    });

    const signUpWidget = addAction(node, "🔑 获取贞贞 API Key", "打开当前渠道注册页面", () =>
        window.open(qwenImage21SignUpUrl(apiModeWidget?.value), "_blank", "noopener,noreferrer"));
    const localStatusWidget = addAction(node, "🧩 检查本地 Qwen 安装 / 扫描 GGUF",
        "重新扫描 models/LLM 并检查本地运行时", () => showLocalQwenStatus(node));
    addAction(node, "🛞 获取 llama-cpp-python 预编译 Wheel", "打开预编译 Wheel 下载页面",
        openLlamaCppPythonWheels);
    addAction(node, "📁 模型路径：ComfyUI/models/LLM（点击复制）", "复制本地 GGUF 主模型与 mmproj 目录",
        copyLocalModelDirectory);
    addAction(node, "📖 Qwen Image 2.1 使用说明", "打开此节点的使用说明",
        () => window.open(new URL("./docs/qwen_image21.md", import.meta.url).href, "_blank", "noopener,noreferrer"));

    const updateApiMode = (mode = apiModeWidget?.value) => {
        const local = LOCAL_QWEN_API_MODES.has(mode);
        const compatible = mode === OPENAI_API_MODE;
        setActionVisible(signUpWidget, !local && !compatible);
        setActionVisible(localStatusWidget, local);
        const label = mode === AI_WORKSHOP_API_MODE ? "🔑 获取 AI 工坊 API Key" : "🔑 获取贞贞 API Key";
        signUpWidget.label = label;
        signUpWidget.name = label;
        resizeNode(node);
    };
    if (apiModeWidget) {
        const originalCallback = apiModeWidget.callback;
        apiModeWidget.callback = function (mode) {
            originalCallback?.apply(this, arguments);
            updateApiMode(mode);
        };
    }
    node.t8QwenImage21UpdateApiMode = updateApiMode;
    updateApiMode();
}


app.registerExtension({
    name: "T8.QwenImage21PromptEnhancer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnConfigure = nodeType.prototype.onConfigure;
        const originalOnSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);
            installQwenImage21Actions(this);
        };
        nodeType.prototype.onConfigure = function () {
            const args = [...arguments];
            const mapped = savedWidgetValueMap(args[0]?.widgets_values);
            if (mapped) args[0] = { ...args[0], widgets_values: projectWidgetValues(this, mapped) };
            const result = originalOnConfigure?.apply(this, args);
            if (this.title === LEGACY_EXAMPLE_TITLE || args[0]?.title === LEGACY_EXAMPLE_TITLE) {
                this.title = EXAMPLE_TITLE;
            }
            restoreWidgetValues(this, mapped, true);
            requestAnimationFrame(() => restoreWidgetValues(this, mapped));
            return result;
        };
        nodeType.prototype.onSerialize = function (serialized) {
            originalOnSerialize?.apply(this, arguments);
            this.t8EnsureRecoverySlot?.();
            serialized.widgets_values = serializeNamedWidgetValues(this, SERIALIZED_WIDGET_NAMES,
                (name, value) => name === "recovery_action" ? "normal"
                    : (value === null || value === undefined || value === "") && Object.hasOwn(WIDGET_DEFAULTS, name)
                        ? WIDGET_DEFAULTS[name] : value);
        };
    },
});
