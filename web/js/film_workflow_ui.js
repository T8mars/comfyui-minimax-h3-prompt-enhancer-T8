import { app } from "../../scripts/app.js";
import {
    contractStatusView,
    estimateStatusCardHeight,
    parseStatusMessage,
    routerStatusView,
} from "./film_workflow_status.mjs";


const ROUTER_NODE_ID = "T8FilmProjectRouter";
const BIBLE_NODE_ID = "T8CharacterPerformanceBible";
const CONTRACT_NODE_IDS = new Set(["T8LongFormPlanner", "T8StoryboardPack"]);
const BIBLE_ADVANCED_WIDGET_NAMES = [
    "tactics",
    "physical_task_and_inertia",
    "voice_lock",
    "mask_break_trigger",
    "gaze_and_listening",
];
const BIBLE_HELP_TEXTS = {
    zh: [
        "使用说明 / How to use",
        "必填 / Required：角色标识、场景目标、阻力与失败代价。",
        "高级选填 / Optional：需要精细表演时再展开；不要复制完整提示词。",
        "连接 / Connect：只把绿色“角色表演圣经”输出接到 H3 / Seedance 同名输入。",
        "分工 / Scope：主提示词写剧情、动作、镜头；本节点写人物动机与表演，设定须一致。",
    ].join("\n"),
    en: [
        "How to use / 使用说明",
        "Required / 必填: Character ID, scene objective, and obstacle & stakes.",
        "Optional / 选填: Expand only for precise acting; do not copy the complete main prompt.",
        "Connect / 连接: Connect only the green Bible output to the matching H3 / Seedance input.",
        "Scope / 分工: The main prompt owns plot/action/camera; this node adds motive/acting. Keep them consistent.",
    ].join("\n"),
};


function setBibleWidgetVisible(widget, visible) {
    if (!widget) return;
    if (!("t8BibleOriginalType" in widget)) {
        widget.t8BibleOriginalType = widget.type;
        widget.t8BibleOriginalComputeSize = widget.computeSize;
        widget.t8BibleOriginalDisplay = widget.element?.style.display || "";
        widget.t8BibleOriginalHidden = Boolean(widget.hidden);
    }
    widget.type = visible ? widget.t8BibleOriginalType : "converted-widget";
    widget.computeSize = visible ? widget.t8BibleOriginalComputeSize : () => [0, -4];
    widget.hidden = visible ? widget.t8BibleOriginalHidden : true;
    if (widget.element) {
        widget.element.dataset.shouldHide = visible ? "false" : "true";
        widget.element.style.display = visible ? widget.t8BibleOriginalDisplay : "none";
        widget.element.hidden = !visible;
    }
}


function resizeBibleNode(node) {
    for (const widget of node.widgets || []) {
        if (widget.element) delete widget.computedHeight;
    }
    const width = Math.max(520, Number(node.size?.[0] || 0));
    const height = Number(node.computeSize?.()?.[1] || node.size?.[1] || 0);
    node.setSize?.([width, height]);
    node.setDirtyCanvas?.(true, true);
    app.canvas?.setDirty?.(true, true);
}


function installBibleAdvancedToggle(node) {
    if (node.__t8CharacterBibleAdvancedToggle) return;
    const widgets = BIBLE_ADVANCED_WIDGET_NAMES
        .map((name) => node.widgets?.find((widget) => widget.name === name))
        .filter(Boolean);
    if (!widgets.length) return;
    let expanded = false;
    for (const widget of widgets) setBibleWidgetVisible(widget, expanded);
    const toggle = node.addWidget(
        "button",
        "⚙️ 高级表演选项（5 项选填）/ Advanced optional fields",
        "展开 / Expand",
        () => {
            expanded = !expanded;
            for (const widget of widgets) setBibleWidgetVisible(widget, expanded);
            toggle.value = expanded ? "收起 / Collapse" : "展开 / Expand";
            resizeBibleNode(node);
        },
        { serialize: false },
    );
    toggle.serializeValue = () => undefined;
    node.__t8CharacterBibleAdvancedToggle = { toggle, widgets };
    resizeBibleNode(node);
}


function parseStatus(message) {
    return parseStatusMessage(message, "film_project_status");
}


function parseContractStatus(message) {
    return parseStatusMessage(message, "creative_contract_status");
}


function currentLanguage() {
    const configured = app.ui?.settings?.getSettingValue?.("Comfy.Locale")
        ?? app.ui?.settings?.settingsValues?.["Comfy.Locale"]
        ?? document.documentElement?.lang
        ?? navigator.language
        ?? "zh";
    return String(configured).toLowerCase().startsWith("zh") ? "zh" : "en";
}


function bibleHelpText() {
    return BIBLE_HELP_TEXTS[currentLanguage()] || BIBLE_HELP_TEXTS.zh;
}


function applyAdaptiveHeight(node, holder, text) {
    const nextHeight = estimateStatusCardHeight(text, holder.minimum, holder.maximum);
    const previousHeight = holder.height;
    holder.height = nextHeight;
    holder.card.style.minHeight = `${Math.max(0, nextHeight - 8)}px`;
    if (nextHeight > previousHeight) {
        const width = Math.max(460, Number(node.size?.[0] || 0));
        const currentHeight = Number(node.size?.[1] || 0);
        node.setSize?.([width, currentHeight + (nextHeight - previousHeight)]);
    }
}


function installStatusCard(node) {
    if (node.__t8FilmProjectStatus) return;
    const card = document.createElement("div");
    card.setAttribute("aria-label", "T8 film project invalidation status");
    card.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "height:100%",
        "min-height:76px",
        "padding:9px 11px",
        "border:1px solid #555",
        "border-radius:7px",
        "background:#202020",
        "color:#d4d4d4",
        "font:12px/1.45 system-ui,sans-serif",
        "white-space:pre-wrap",
        "overflow:hidden",
        "pointer-events:none",
    ].join(";");
    const initialView = routerStatusView(null, currentLanguage());
    card.textContent = initialView.text;
    const holder = { card, height: 84, minimum: 84, maximum: 180 };
    const widget = node.addDOMWidget("t8_film_project_status", "custom", card, {
        serialize: false,
        hideOnZoom: true,
        getMinHeight: () => holder.height,
        getMaxHeight: () => holder.height,
    });
    widget.serializeValue = () => undefined;
    holder.widget = widget;
    node.__t8FilmProjectStatus = holder;
    applyAdaptiveHeight(node, holder, initialView.text);
    if (Number(node.size?.[0] || 0) < 460) {
        node.setSize?.([460, Math.max(620, Number(node.size?.[1] || 0))]);
    }
}


function renderStatus(node, status) {
    installStatusCard(node);
    const holder = node.__t8FilmProjectStatus;
    const card = holder.card;
    const view = routerStatusView(status, currentLanguage());
    card.textContent = view.text;
    card.style.borderColor = view.borderColor;
    card.style.background = view.background;
    applyAdaptiveHeight(node, holder, view.text);
    node.setDirtyCanvas?.(true, true);
}


function installContractCard(node) {
    if (node.__t8CreativeContractStatus) return;
    const card = document.createElement("div");
    card.setAttribute("aria-label", "T8 creative contract validation status");
    card.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "height:100%",
        "min-height:82px",
        "padding:9px 11px",
        "border:1px solid #555",
        "border-radius:7px",
        "background:#202020",
        "color:#d4d4d4",
        "font:12px/1.45 system-ui,sans-serif",
        "white-space:pre-wrap",
        "overflow:hidden",
        "pointer-events:none",
    ].join(";");
    const initialView = contractStatusView(null, currentLanguage());
    card.textContent = initialView.text;
    const holder = { card, height: 90, minimum: 90, maximum: 180 };
    const widget = node.addDOMWidget("t8_creative_contract_status", "custom", card, {
        serialize: false,
        hideOnZoom: true,
        getMinHeight: () => holder.height,
        getMaxHeight: () => holder.height,
    });
    widget.serializeValue = () => undefined;
    holder.widget = widget;
    node.__t8CreativeContractStatus = holder;
    applyAdaptiveHeight(node, holder, initialView.text);
    const width = Math.max(460, Number(node.size?.[0] || 0));
    const computedHeight = Number(node.computeSize?.()?.[1] || 0);
    const height = Math.max(Number(node.size?.[1] || 0), computedHeight);
    node.setSize?.([width, height]);
}


function renderContractStatus(node, status) {
    installContractCard(node);
    const holder = node.__t8CreativeContractStatus;
    const card = holder.card;
    const view = contractStatusView(status, currentLanguage());
    card.textContent = view.text;
    card.style.borderColor = view.borderColor;
    card.style.background = view.background;
    applyAdaptiveHeight(node, holder, view.text);
    node.setDirtyCanvas?.(true, true);
}


function installBibleHelpCard(node) {
    if (node.__t8CharacterBibleHelp) return;
    const text = bibleHelpText();
    const card = document.createElement("div");
    card.setAttribute("aria-label", "T8 character performance bible usage guide");
    card.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "height:100%",
        "min-height:118px",
        "padding:10px 12px",
        "border:1px solid #3b82f6",
        "border-radius:7px",
        "background:#152238",
        "color:#e5eefc",
        "font:12px/1.5 system-ui,sans-serif",
        "white-space:pre-wrap",
        "overflow:hidden",
        "pointer-events:none",
    ].join(";");
    card.textContent = text;
    const holder = { card, height: 126, minimum: 126, maximum: 190 };
    const widget = node.addDOMWidget("t8_character_bible_help", "custom", card, {
        serialize: false,
        hideOnZoom: true,
        getMinHeight: () => holder.height,
        getMaxHeight: () => holder.height,
    });
    widget.serializeValue = () => undefined;
    holder.widget = widget;
    node.__t8CharacterBibleHelp = holder;
    applyAdaptiveHeight(node, holder, text);
    const width = Math.max(520, Number(node.size?.[0] || 0));
    const computedHeight = Number(node.computeSize?.()?.[1] || 0);
    const height = Math.max(Number(node.size?.[1] || 0), computedHeight);
    node.setSize?.([width, height]);
}


app.registerExtension({
    name: "T8.FilmWorkflowStatus",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === BIBLE_NODE_ID) {
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const result = originalOnNodeCreated?.apply(this, arguments);
                installBibleAdvancedToggle(this);
                installBibleHelpCard(this);
                return result;
            };
            return;
        }
        if (nodeData.name !== ROUTER_NODE_ID && !CONTRACT_NODE_IDS.has(nodeData.name)) return;
        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            if (nodeData.name === ROUTER_NODE_ID) installStatusCard(this);
            else installContractCard(this);
            return result;
        };
        nodeType.prototype.onExecuted = function (message) {
            originalOnExecuted?.apply(this, arguments);
            if (nodeData.name === ROUTER_NODE_ID) renderStatus(this, parseStatus(message));
            else renderContractStatus(this, parseContractStatus(message));
        };
    },
});
