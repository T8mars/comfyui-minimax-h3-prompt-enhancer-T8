import { app } from "../../scripts/app.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";
import { showRedactedDiagnostics } from "./diagnostics_viewer.mjs";
import {
    copyLocalModelDirectory,
    openLlamaCppPythonWheels,
    showLocalQwenStatus,
} from "./local_qwen_status.js";
import { showProviderCapability } from "./provider_capability_ui.mjs";


const NODE_ID = "QwenImage21PromptEnhancerT8";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const AI_WORKSHOP_SIGN_UP_URL = "https://ai.t8star.org/register?aff=dP7j";
const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（图片/视频）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const LOCAL_QWEN_API_MODES = new Set([
    "本地 GGUF（llama.cpp / Qwen，离线）",
    "本地 Qwen3.8-27B（GGUF，离线）",
]);


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
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);
            installQwenImage21Actions(this);
        };
        nodeType.prototype.onConfigure = function () {
            const result = originalOnConfigure?.apply(this, arguments);
            requestAnimationFrame(() => this.t8QwenImage21UpdateApiMode?.());
            return result;
        };
    },
});
