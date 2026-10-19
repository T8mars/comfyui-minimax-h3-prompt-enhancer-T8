import { app } from "../../scripts/app.js";


const SHOW_NODE_ID = "T8ShowText";
const COPY_LABEL = "复制显示内容";


function graphNodes(graph) {
    return graph?.nodes || graph?._nodes || [];
}


function allGraphs(root) {
    const pending = [root], seen = new Set();
    while (pending.length) {
        const graph = pending.pop();
        if (!graph || seen.has(graph)) continue;
        seen.add(graph);
        for (const node of graphNodes(graph)) if (node.subgraph) pending.push(node.subgraph);
        if (graph.subgraphs?.values) pending.push(...graph.subgraphs.values());
    }
    return seen;
}


// New hosts restore locator IDs (subgraph UUID + local ID); older hosts may
// restore execution paths (container node IDs). Bare IDs belong ONLY to root.
// Never search the active canvas or fall back to the last segment of an ID.
function outputNode(root, key, graphs) {
    if (!root || typeof key !== "string" || !key) return null;
    const get = (graph, id) => graph?.getNodeById?.(id) || null;
    const decode = value => {
        try { const id = decodeURIComponent(value); return encodeURIComponent(id) === value ? id : null; }
        catch { return null; }
    };
    if (key.startsWith("~root:")) {
        const id = decode(key.slice(6));
        return id === null ? null : get(root, id);
    }
    const encoded = key.startsWith("~subgraph:");
    const parts = (encoded ? key.slice(10) : key).split(":");
    if (parts.length === 1) return encoded ? null : get(root, key);
    if (parts.length === 2) {
        const graph = [...graphs].find(value => value !== root && value.id === parts[0]);
        if (graph) {
            const id = encoded ? decode(parts[1]) : parts[1];
            return id === null ? null : get(graph, id);
        }
    }
    if (encoded || parts.some(part => !part)) return null;
    let graph = root;
    for (const part of parts.slice(0, -1)) {
        graph = get(graph, part)?.subgraph;
        if (!graph) return null;
    }
    return get(graph, parts.at(-1));
}


function normalizeExecutedText(message) {
    const values = Array.isArray(message?.text) ? message.text : [message?.text];
    return values
        .filter((value) => value !== undefined && value !== null)
        .map((value) => typeof value === "string" ? value : JSON.stringify(value, null, 2))
        .join("\n");
}


function resetCopy(state) {
    window.clearTimeout(state.timer);
    state.timer = undefined;
    state.copy.textContent = COPY_LABEL;
}


function updateTextPreview(node, message) {
    installTextPreview(node);
    const state = node.__t8TextPreview;
    state.rawText = normalizeExecutedText(message);
    state.revision++;
    // textarea normalizes CRLF to LF; retain rawText separately for copying.
    state.textarea.value = state.rawText;
    resetCopy(state);
    node.setDirtyCanvas?.(true, true);
}


function fallbackCopy(text) {
    const active = document.activeElement;
    const selection = document.getSelection?.();
    const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange()) : [];
    const inputSelection = active && typeof active.selectionStart === "number"
        ? [active.selectionStart, active.selectionEnd, active.selectionDirection] : null;
    const input = document.createElement("textarea");
    input.value = text;
    input.readOnly = true;
    input.style.cssText = "position:fixed;left:-10000px;top:0;opacity:0;pointer-events:none";
    let copied = false;
    const onCopy = event => {
        if (!event.clipboardData) return;
        event.clipboardData.setData("text/plain", text);
        event.preventDefault();
        copied = true;
    };
    try {
        document.body.append(input);
        input.focus({ preventScroll: true });
        input.select();
        document.addEventListener("copy", onCopy, true);
        // A copy event must write the raw string, not the normalized textarea.
        return document.execCommand?.("copy") === true && copied;
    } finally {
        document.removeEventListener("copy", onCopy, true);
        input.remove();
        active?.focus?.({ preventScroll: true });
        if (inputSelection) active.setSelectionRange?.(...inputSelection);
        if (selection && ranges.length) {
            selection.removeAllRanges();
            for (const range of ranges) selection.addRange(range);
        }
    }
}


async function copyPreview(state) {
    if (state.copying || state.disposed) return;
    const text = state.rawText, revision = state.revision;
    resetCopy(state);
    state.copying = true;
    state.copy.disabled = true;
    state.copy.textContent = "复制中…";
    let copied = false;
    try {
        try {
            if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
            await navigator.clipboard.writeText(text);
            copied = true;
        } catch {
            if (!state.disposed) copied = fallbackCopy(text);
        }
        if (!state.disposed && revision === state.revision) {
            state.copy.textContent = copied ? "已复制" : "复制失败，请手动选择文本复制";
            state.timer = window.setTimeout(() => resetCopy(state), 1500);
        }
    } catch {
        if (!state.disposed) {
            state.copy.textContent = "复制失败，请手动选择文本复制";
            state.timer = window.setTimeout(() => resetCopy(state), 1500);
        }
    } finally {
        state.copying = false;
        if (!state.disposed) {
            state.copy.disabled = false;
            if (revision !== state.revision) resetCopy(state);
        }
    }
}


function installTextPreview(node) {
    if (node.__t8TextPreview) return;

    const root = document.createElement("div");
    root.style.cssText = [
        "box-sizing:border-box",
        "display:flex",
        "flex-direction:column",
        "gap:6px",
        "width:100%",
        "height:100%",
        "padding:4px",
        "overflow:hidden",
    ].join(";");

    const textarea = document.createElement("textarea");
    textarea.readOnly = true;
    textarea.placeholder = "运行后在这里显示 STRING 内容";
    textarea.setAttribute("aria-label", "T8 Show Text output");
    textarea.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "height:100%",
        "min-height:120px",
        "resize:none",
        "overflow:auto",
        "padding:9px",
        "border:1px solid #555",
        "border-radius:6px",
        "background:#171717",
        "color:#eee",
        "font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace",
        "white-space:pre-wrap",
    ].join(";");

    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = COPY_LABEL;
    copy.style.cssText = "height:28px;border:1px solid #666;border-radius:5px;background:#292929;color:#eee;cursor:pointer";
    copy.addEventListener("click", () => copyPreview(node.__t8TextPreview));

    root.append(textarea, copy);
    const widget = node.addDOMWidget("t8_show_text_preview", "custom", root, {
        serialize: false,
        hideOnZoom: false,
        getMinHeight: () => 170,
        getMaxHeight: () => Math.max(170, Number(node.size?.[1] || 260) - 70),
    });
    widget.options = { ...widget.options, serialize: false };
    widget.serialize = false;
    widget.serializeValue = () => undefined;
    node.__t8TextPreview = { root, textarea, copy, widget, rawText: "", revision: 0, copying: false, disposed: false };
    if (node.size?.[0] < 360) node.setSize?.([360, Math.max(260, node.size?.[1] || 0)]);
}


app.registerExtension({
    name: "T8.TextUtilities",
    onNodeOutputsUpdated(outputs) {
        const root = app.rootGraph || app.graph;
        if (!root) return;
        const graphs = allGraphs(root), restored = new Map();
        for (const [key, message] of Object.entries(outputs || {})) {
            const node = outputNode(root, key, graphs);
            if ((node?.comfyClass || node?.type) === SHOW_NODE_ID) restored.set(node, message);
        }
        // This hook receives a snapshot, not a delta. Clear absent outputs so
        // reset/history loads cannot leave a previous result on reused nodes.
        for (const graph of graphs) for (const node of graphNodes(graph)) {
            if ((node.comfyClass || node.type) === SHOW_NODE_ID) updateTextPreview(node, restored.get(node));
        }
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== SHOW_NODE_ID) return;
        if (nodeType.prototype.__t8TextPreviewHooks) return;
        Object.defineProperty(nodeType.prototype, "__t8TextPreviewHooks", { value: true });

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnExecuted = nodeType.prototype.onExecuted;
        const originalOnRemoved = nodeType.prototype.onRemoved;
        const originalOnAdded = nodeType.prototype.onAdded;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            installTextPreview(this);
            return result;
        };

        nodeType.prototype.onExecuted = function (message) {
            const result = originalOnExecuted?.apply(this, arguments);
            updateTextPreview(this, message);
            return result;
        };

        nodeType.prototype.onRemoved = function () {
            const state = this.__t8TextPreview;
            if (state) { state.disposed = true; resetCopy(state); }
            return originalOnRemoved?.apply(this, arguments);
        };

        nodeType.prototype.onAdded = function () {
            const result = originalOnAdded?.apply(this, arguments);
            const state = this.__t8TextPreview;
            if (state?.disposed) { state.disposed = false; state.revision++; resetCopy(state); }
            return result;
        };
    },
});
