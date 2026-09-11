import { app } from "../../scripts/app.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";
import { bindOpenAIProviderPersistence } from "./widget_state.mjs";
import { showRedactedDiagnostics } from "./diagnostics_viewer.mjs";
import { showProviderCapability } from "./provider_capability_ui.mjs";
import { showLocalQwenStatus } from "./local_qwen_status.js";

export const YUE2_NODE_ID = "YuE2MusicPromptEnhancerT8";
const STATE = "t8_yue2_widgets_v1";
const BASIC = new Set(["music_idea", "lyrics_mode", "lyrics_language", "lyrics", "cot", "api_mode", "quality_mode", "seed"]);
const INTERNAL = new Set(["recovery_slot", "recovery_action"]);
export const EXAMPLES = [
    ["中文公路歌 / Road song", "写一首原创中文公路歌：清晨独自离开旧城，到副歌决定向前走。女声，钢琴和原声吉他，88 BPM；副歌有一句易记的短句，第二段主歌推进故事。"],
    ["原词换编曲 / Restyle lyrics", "保留已填写的全部歌词，为它配一版温暖摇滚：克制主歌、开阔副歌、干净电吉他和有弹性的鼓，结尾自然收束。请先在原有歌词框填写你的歌词。"],
    ["古风叙事 / Story song", "原创中文古风叙事歌：旅人在故乡渡口读到一封迟到的家书，从克制到释然。清澈人声，古筝与弦乐，副歌回到渡口意象；避免空泛堆砌古风词汇。"],
];

function setVisible(widget, visible) {
    if (!widget.t8YueOriginal) widget.t8YueOriginal = { type: widget.type, computeSize: widget.computeSize, display: widget.element?.style.display || "" };
    widget.type = visible ? widget.t8YueOriginal.type : "converted-widget";
    widget.computeSize = visible ? widget.t8YueOriginal.computeSize : () => [0, -4];
    widget.hidden = !visible;
    if (widget.element) {
        widget.element.hidden = !visible;
        widget.element.style.display = visible ? widget.t8YueOriginal.display : "none";
        widget.element.dataset.shouldHide = String(!visible);
        delete widget.computedHeight;
    }
}

function resize(node) {
    for (const widget of node.widgets || []) if (widget.element) delete widget.computedHeight;
    const width = Math.max(620, Number(node.size?.[0] || 620));
    const height = Number(node.computeSize?.([width, 0])?.[1] || node.size?.[1] || 620);
    node.setSize?.([width, height]);
    node.setDirtyCanvas?.(true, true);
}

export function installYuE2UI(node) {
    if (node.t8Yue2UI) return;
    const schemaWidgets = [...(node.widgets || [])];
    const field = (name) => schemaWidgets.find(w => w.name === name);
    const state = { expanded: false, widgets: schemaWidgets, field };
    node.t8Yue2UI = state;
    bindOpenAIProviderPersistence(node);
    const button = (name, callback) => {
        const widget = node.addWidget("button", name, "", callback, { serialize: false });
        widget.serializeValue = () => undefined;
        return widget;
    };
    state.refresh = () => {
        for (const widget of schemaWidgets) {
            let visible = BASIC.has(widget.name) || state.expanded;
            if (INTERNAL.has(widget.name)) visible = false;
            setVisible(widget, visible);
        }
        resize(node);
    };
    button("⚙️ 高级创作与渠道设置 / Advanced", () => { state.expanded = !state.expanded; state.refresh(); });
    button("▶ 创作 YuE2 提示词与歌词 / Create", async () => {
        node.t8CommitOpenAIProviderState?.();
        node.t8EnsureRecoverySlot?.();
        field("recovery_action").value = "normal";
        await app.queuePrompt(0, 1, [String(node.id)]);
    });
    addCompletionRecoveryButton(node, YUE2_NODE_ID, { beforeQueue: () => node.t8CommitOpenAIProviderState?.() });
    button("🧭 渠道能力说明 / Provider capability", () => showProviderCapability(field("api_mode").value, field("openai_base_url").value, { textOnly: true }));
    button("🔎 查看脱敏诊断 / Diagnostics", () => showRedactedDiagnostics(YUE2_NODE_ID));
    button("🧩 本地 GGUF 安装与路径 / Local setup", () => showLocalQwenStatus());

    const card = document.createElement("div");
    card.style.cssText = "box-sizing:border-box;width:100%;height:100%;padding:10px;background:#152238;color:#e5eefc;border:1px solid #3b82f6;border-radius:7px;font:12px/1.5 system-ui;overflow:auto";
    const info = document.createElement("div");
    info.style.whiteSpace = "pre-wrap";
    info.textContent = "使用说明 / How to use\n1. 写主题即可；有词时 AUTO 原样保留，无词时创作。\n2. 已有 ABC 可留空；full 生成旋律＋和弦，melody 无和弦，off 无谱。\n3. ABC 由当前 LLM 创作（T8 扩展），不是 YuE2 模型出谱；已有 ABC 优先保留。\n4. style 接风格，lyrics 接歌词，abc 从右侧输出乐谱；本节点不生成音频。\n费用：默认新歌约 3 次、保留歌词约 2 次；ABC 校验失败最多修正 1 次，审校另加 1–2 次。\nFull/melody compose ABC via your LLM; off leaves it empty. Advanced → Empty ABC input → Downstream 保留原来的下游规划方式（少 1 次作谱调用）。";
    card.append(info);
    for (const [label, brief] of EXAMPLES) {
        const sample = document.createElement("button");
        sample.textContent = label;
        sample.style.cssText = "margin:6px 5px 0 0;padding:5px;cursor:pointer";
        sample.onclick = () => {
            const target = field("music_idea");
            if (String(target.value || "").trim() && !window.confirm("替换当前创作要求？歌词不会被修改。 / Replace brief only?")) return;
            target.value = brief;
            const input = target.inputEl || target.element?.querySelector?.("textarea,input");
            if (input) input.value = brief;
            target.callback?.(brief);
            node.graph?.change?.();
        };
        card.append(sample);
    }
    const help = node.addDOMWidget("t8_yue2_help", "custom", card, { serialize: false, hideOnZoom: true, getMinHeight: () => 220, getMaxHeight: () => 220 });
    help.computeSize = width => [width, 220];
    help.serializeValue = () => undefined;
    state.refresh();
}

app.registerExtension({
    name: "T8.YuE2Music",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== YUE2_NODE_ID) return;
        const created = nodeType.prototype.onNodeCreated;
        const serialized = nodeType.prototype.onSerialize;
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            installYuE2UI(this);
            return result;
        };
        nodeType.prototype.onSerialize = function (data) {
            serialized?.apply(this, arguments);
            this.t8CommitOpenAIProviderState?.();
            data.properties ||= {};
            data.properties[STATE] = Object.fromEntries(this.t8Yue2UI.widgets.filter(w => w.name !== "api_key").map(w => [w.name, w.value]));
        };
        nodeType.prototype.onConfigure = function (data) {
            configured?.apply(this, arguments);
            installYuE2UI(this);
            const saved = data.properties?.[STATE];
            if (saved && typeof saved === "object" && !Array.isArray(saved)) {
                for (const widget of this.t8Yue2UI.widgets) if (widget.name !== "api_key" && Object.hasOwn(saved, widget.name)) widget.value = saved[widget.name];
            }
            this.t8EnsureRecoverySlot?.();
            this.t8Yue2UI.refresh();
        };
    },
});
