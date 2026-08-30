import { app } from "../../scripts/app.js";
import {
    contractStatusView,
    estimateStatusCardHeight,
    parseStatusMessage,
    routerStatusView,
} from "./film_workflow_status.mjs";


const ROUTER_NODE_ID = "T8FilmProjectRouter";
const CONTRACT_NODE_IDS = new Set(["T8LongFormPlanner", "T8StoryboardPack"]);


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


app.registerExtension({
    name: "T8.FilmWorkflowStatus",
    async beforeRegisterNodeDef(nodeType, nodeData) {
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
