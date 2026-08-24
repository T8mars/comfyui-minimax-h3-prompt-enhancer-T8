import { app } from "../../scripts/app.js";


const SHOW_NODE_ID = "T8ShowText";


function normalizeExecutedText(message) {
    const values = Array.isArray(message?.text) ? message.text : [message?.text];
    return values
        .filter((value) => value !== undefined && value !== null)
        .map((value) => typeof value === "string" ? value : JSON.stringify(value, null, 2))
        .join("\n");
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
    copy.textContent = "复制显示内容";
    copy.style.cssText = "height:28px;border:1px solid #666;border-radius:5px;background:#292929;color:#eee;cursor:pointer";
    copy.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(textarea.value);
            const previous = copy.textContent;
            copy.textContent = "已复制";
            window.setTimeout(() => { copy.textContent = previous; }, 1000);
        } catch (error) {
            window.alert(`复制失败：${error?.message || error}`);
        }
    });

    root.append(textarea, copy);
    const widget = node.addDOMWidget("t8_show_text_preview", "custom", root, {
        serialize: false,
        hideOnZoom: false,
        getMinHeight: () => 170,
        getMaxHeight: () => Math.max(170, Number(node.size?.[1] || 260) - 70),
    });
    widget.serializeValue = () => undefined;
    node.__t8TextPreview = { root, textarea, widget };
    if (node.size?.[0] < 360) node.setSize?.([360, Math.max(260, node.size?.[1] || 0)]);
}


app.registerExtension({
    name: "T8.TextUtilities",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== SHOW_NODE_ID) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnExecuted = nodeType.prototype.onExecuted;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            installTextPreview(this);
            return result;
        };

        nodeType.prototype.onExecuted = function (message) {
            originalOnExecuted?.apply(this, arguments);
            installTextPreview(this);
            this.__t8TextPreview.textarea.value = normalizeExecutedText(message);
            this.setDirtyCanvas?.(true, true);
        };
    },
});
