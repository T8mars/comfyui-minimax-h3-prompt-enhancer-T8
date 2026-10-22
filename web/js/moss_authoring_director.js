import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { DIRECTOR_ID, DIRECTOR_HELP, configureDirector, serializeDirector, ensureDirectorSlot,
    hideDirectorInternals, restoreDirector, inspectDirector, refreshAuthoringRows, drawAuthoringLinkedLabels } from "./moss_authoring_ui.mjs";

const INSTALLED = Symbol("t8AuthoringDirectorHooks");
const ROWS_INSTALLED = Symbol("t8AuthoringRowsHooks");

function rowHooks(Type) {
    if (Object.hasOwn(Type.prototype, ROWS_INSTALLED)) return;
    Object.defineProperty(Type.prototype, ROWS_INSTALLED, { value: true });
    for (const name of ["onNodeCreated", "onConfigure", "onConnectionsChange"]) {
        const original = Type.prototype[name];
        Type.prototype[name] = function () {
            const result = original?.apply(this, arguments); refreshAuthoringRows(this);
            if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => {
                if (!this.t8AuthoringRemoved) refreshAuthoringRows(this);
            });
            return result;
        };
    }
    const draw = Type.prototype.onDrawForeground;
    Type.prototype.onDrawForeground = function (context) {
        const result = draw?.apply(this, arguments); drawAuthoringLinkedLabels(this, context); return result;
    };
}

function dialog(node, text, title) {
    if (node.t8AuthoringRemoved) return;
    const element = document.createElement("dialog");
    Object.assign(element.style, { maxWidth: "90vw", maxHeight: "85vh", overflow: "auto", background: "#202228",
        color: "#eee", padding: "16px", border: "1px solid #6aa9ed", borderRadius: "10px", pointerEvents: "auto" });
    const heading = document.createElement("h3"); heading.textContent = title; element.append(heading);
    const pre = document.createElement("pre"); pre.textContent = text; pre.style.whiteSpace = "pre-wrap"; element.append(pre);
    const close = document.createElement("button"); close.textContent = "关闭 / Close";
    close.onclick = () => element.close(); element.append(close);
    element.addEventListener("keydown", event => event.stopPropagation());
    element.addEventListener("keyup", event => event.stopPropagation());
    element.addEventListener("close", () => { node.t8AuthoringDialogs?.delete(element); element.remove(); }, { once: true });
    node.t8AuthoringDialogs ||= new Set(); node.t8AuthoringDialogs.add(element);
    document.body.append(element); element.showModal();
}

function install(node) {
    if (node.t8AuthoringInstalled || !node.addWidget) return;
    node.t8AuthoringInstalled = true;
    node.t8AuthoringRemoved = false;
    node.t8AuthoringEpoch ||= 0;
    const action = (name, callback) => {
        const widget = node.addWidget("button", name, "", callback, { serialize: false });
        widget.serialize = false; widget.serializeValue = () => undefined;
        return widget;
    };
    const fetchFn = (...args) => api.fetchApi(...args);
    const alertFn = text => window.alert(text);
    action("🔄 恢复完整集合（不重新生成）/ Restore", () => restoreDirector({ node, fetchFn, alertFn,
        queuePrompt: (...args) => app.queuePrompt(...args) }));
    action("📝 只读查看失败稿 / Inspect failed draft", () => inspectDirector({ node, fetchFn, alertFn,
        showText: (text, title) => dialog(node, text, title) }));
    action("📖 整册/逐图使用说明 / Help", () => dialog(node, DIRECTOR_HELP, "MOSS Authoring 使用说明 / Help"));
    ensureDirectorSlot(node); hideDirectorInternals(node);
}

app.registerExtension({
    name: "T8.MOSSAuthoringDirector",
    async beforeRegisterNodeDef(Type, data) {
        if (data.name === "MOSSAuthoringPageT8") { rowHooks(Type); return; }
        if (data.name !== DIRECTOR_ID || Object.hasOwn(Type.prototype, INSTALLED)) return;
        Object.defineProperty(Type.prototype, INSTALLED, { value: true });
        const created = Type.prototype.onNodeCreated, configured = Type.prototype.onConfigure,
            serialized = Type.prototype.onSerialize, removed = Type.prototype.onRemoved, added = Type.prototype.onAdded;
        Type.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); install(this); return result;
        };
        Type.prototype.onConfigure = function (value) {
            this.t8AuthoringEpoch = (this.t8AuthoringEpoch || 0) + 1;
            const result = configureDirector(this, value, configured, arguments);
            hideDirectorInternals(this); return result;
        };
        Type.prototype.onSerialize = function (value) {
            const result = serialized?.apply(this, arguments); serializeDirector(this, value); return result;
        };
        Type.prototype.onAdded = function () {
            const result = added?.apply(this, arguments); this.t8AuthoringRemoved = false;
            ensureDirectorSlot(this); hideDirectorInternals(this); return result;
        };
        Type.prototype.onRemoved = function () {
            this.t8AuthoringRemoved = true; this.t8AuthoringEpoch = (this.t8AuthoringEpoch || 0) + 1;
            for (const element of this.t8AuthoringDialogs || []) { element.close?.(); element.remove?.(); }
            this.t8AuthoringDialogs?.clear();
            return removed?.apply(this, arguments);
        };
        rowHooks(Type);
    },
});
