const REGISTRATION_MARKER = Symbol.for("t8.prompt-enhancer.combo-preview");
const registrationsByNode = new WeakMap();
let activePanel = null;


function widgetValues(registration) {
    const values = registration.widget?.options?.values;
    return typeof values === "function"
        ? values(registration.widget, registration.node)
        : values;
}


function sameValues(left, right) {
    return Array.isArray(left)
        && Array.isArray(right)
        && left.length === right.length
        && left.every((value, index) => value === right[index]);
}


function activeCanvasNode() {
    return globalThis.LiteGraph?.LGraphCanvas?.active_canvas?.current_node
        || globalThis.LGraphCanvas?.active_canvas?.current_node
        || null;
}


function registrationFor(values) {
    if (values?.[REGISTRATION_MARKER]) return values[REGISTRATION_MARKER];
    const registrations = registrationsByNode.get(activeCanvasNode()) || [];
    return registrations.find((registration) => sameValues(values, widgetValues(registration))) || null;
}


function textBlock(className, value, style = "") {
    const block = document.createElement("div");
    block.className = className;
    block.textContent = value || "";
    if (style) block.style.cssText = style;
    return block;
}


function renderPreview(panel, model, reposition) {
    panel.replaceChildren();
    panel.append(textBlock(
        "t8-template-preview-authority",
        model?.authority || "提示词模板预览",
        "font-size:11px;opacity:.7",
    ));
    panel.append(textBlock(
        "t8-template-preview-title",
        model?.title || "悬停模板名称查看 GIF",
        "font-size:15px;font-weight:700;line-height:1.35",
    ));
    if (model?.summary) {
        panel.append(textBlock(
            "t8-template-preview-summary",
            model.summary,
            "font-size:12px;line-height:1.5;opacity:.9",
        ));
    }

    const previews = Array.isArray(model?.previews) ? model.previews : [];
    if (!previews.length) {
        panel.append(textBlock(
            "t8-template-preview-empty",
            model?.empty_message || "悬停一个具体模板即可查看对应 GIF。",
            "padding:22px 12px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.72",
        ));
    }

    for (const preview of previews) {
        const figure = document.createElement("div");
        figure.style.cssText = "display:flex;flex-direction:column;gap:6px;min-width:0";
        if (preview.label) {
            figure.append(textBlock("t8-template-preview-label", preview.label, "font-size:12px;font-weight:600"));
        }
        if (preview.available !== false && preview.url) {
            const image = document.createElement("img");
            image.src = preview.url;
            image.alt = `${preview.label || model?.title || "模板"} GIF 预览`;
            image.loading = "eager";
            image.decoding = "async";
            image.referrerPolicy = "no-referrer";
            image.style.cssText = [
                "display:block", "width:100%", "max-height:230px", "object-fit:contain",
                "border-radius:7px", "background:#111", "border:1px solid rgba(255,255,255,.08)",
            ].join(";");
            image.onload = reposition;
            image.onerror = () => {
                image.replaceWith(textBlock(
                    "t8-template-preview-error",
                    "GIF 预览加载失败",
                    "padding:22px 12px;border:1px dashed #8a5555;border-radius:7px;text-align:center",
                ));
                reposition();
            };
            figure.append(image);
        } else {
            figure.append(textBlock(
                "t8-template-preview-unavailable",
                preview.unavailable_message || "本机未配置此 GIF；不影响提示词增强。",
                "padding:22px 12px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.72",
            ));
        }
        if (preview.source_url) {
            const source = document.createElement("a");
            source.href = preview.source_url;
            source.target = "_blank";
            source.rel = "noopener noreferrer";
            source.referrerPolicy = "no-referrer";
            source.textContent = preview.source_label || "查看模板来源";
            source.style.cssText = "font-size:12px;color:var(--link-color,#7ab7ff);width:max-content";
            figure.append(source);
        }
        panel.append(figure);
    }

    panel.append(textBlock(
        "t8-template-preview-policy",
        model?.policy || "GIF 仅供选择时预览，不会发送给 LLM",
        "font-size:10px;opacity:.6;border-top:1px solid rgba(255,255,255,.08);padding-top:7px",
    ));
    reposition();
}


function attachPreview(contextMenu, registration) {
    const root = contextMenu?.root;
    if (!root?.isConnected) return;
    activePanel?.remove();

    const panel = document.createElement("aside");
    panel.className = "t8-template-menu-preview";
    panel.style.cssText = [
        "position:fixed", "z-index:100000", "display:flex", "flex-direction:column", "gap:8px",
        "box-sizing:border-box", "width:min(360px,calc(100vw - 16px))", "padding:12px",
        "overflow:auto", "border:1px solid var(--border-color,#555)", "border-radius:8px",
        "background:var(--comfy-menu-bg,#202020)", "color:var(--input-text,#eee)",
        "box-shadow:0 12px 36px rgba(0,0,0,.5)", "pointer-events:auto",
    ].join(";");
    document.body.append(panel);
    activePanel = panel;

    const reposition = () => {
        if (!panel.isConnected || !root.isConnected) return;
        const gap = 8;
        const viewportWidth = document.documentElement.clientWidth || window.innerWidth;
        const viewportHeight = document.documentElement.clientHeight || window.innerHeight;
        const rootRect = root.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        let left = rootRect.right + gap;
        if (left + panelRect.width > viewportWidth - gap) left = rootRect.left - panelRect.width - gap;
        if (left < gap) left = Math.max(gap, viewportWidth - panelRect.width - gap);
        const top = Math.max(gap, Math.min(rootRect.top, viewportHeight - Math.min(panelRect.height, viewportHeight - gap * 2) - gap));
        panel.style.left = `${Math.round(left)}px`;
        panel.style.top = `${Math.round(top)}px`;
        panel.style.maxHeight = `${Math.max(120, viewportHeight - top - gap)}px`;
    };

    let renderedValue = null;
    const showValue = (value) => {
        if (value === renderedValue) return;
        renderedValue = value;
        const model = registration.resolve(String(value ?? ""));
        renderPreview(panel, model, reposition);
    };
    const entries = Array.from(root.querySelectorAll(".litemenu-entry:not(.separator)"));
    for (const entry of entries) {
        const value = entry.dataset.value || entry.textContent || "";
        entry.addEventListener("pointerenter", () => showValue(value));
        entry.addEventListener("focus", () => showValue(value));
    }
    let movedEntry = null;
    root.addEventListener("mousemove", (event) => {
        const entry = event.target?.closest?.(".litemenu-entry:not(.separator)");
        if (!entry || entry === movedEntry) return;
        movedEntry = entry;
        showValue(entry.dataset.value || entry.textContent || "");
    });

    const showKeyboardSelection = () => setTimeout(() => {
        const selected = entries.find((entry) => entry.style.display !== "none" && entry.style.backgroundColor)
            || entries.find((entry) => entry.style.display !== "none");
        if (selected) showValue(selected.dataset.value || selected.textContent || "");
    }, 0);
    const filter = root.querySelector(".comfy-context-menu-filter");
    filter?.addEventListener("keydown", (event) => {
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) showKeyboardSelection();
    });
    filter?.addEventListener("input", showKeyboardSelection);

    const cleanup = () => {
        window.removeEventListener("resize", reposition);
        panel.remove();
        if (activePanel === panel) activePanel = null;
    };
    const originalClose = contextMenu.close;
    contextMenu.close = function () {
        cleanup();
        return originalClose.apply(this, arguments);
    };
    window.addEventListener("resize", reposition);
    showValue(registration.widget?.value);
    requestAnimationFrame(reposition);
}


function installContextMenuPreview() {
    const liteGraph = globalThis.LiteGraph;
    const OriginalContextMenu = liteGraph?.ContextMenu;
    if (!OriginalContextMenu || OriginalContextMenu.__t8TemplatePreviewWrapper) return Boolean(OriginalContextMenu);

    function T8TemplatePreviewContextMenu(values, options, ...rest) {
        const contextMenu = new OriginalContextMenu(values, options, ...rest);
        const registration = registrationFor(values);
        if (registration && options?.className === "dark") {
            requestAnimationFrame(() => attachPreview(contextMenu, registration));
        }
        return contextMenu;
    }
    Object.setPrototypeOf(T8TemplatePreviewContextMenu, OriginalContextMenu);
    T8TemplatePreviewContextMenu.prototype = OriginalContextMenu.prototype;
    T8TemplatePreviewContextMenu.__t8TemplatePreviewWrapper = true;
    liteGraph.ContextMenu = T8TemplatePreviewContextMenu;
    return true;
}


export function registerTemplateMenuPreview(node, widget, resolve) {
    if (!node || !widget || typeof resolve !== "function") return;
    const registration = { node, widget, resolve };
    const registrations = registrationsByNode.get(node) || [];
    const existing = registrations.findIndex((item) => item.widget === widget);
    if (existing >= 0) registrations.splice(existing, 1, registration);
    else registrations.push(registration);
    registrationsByNode.set(node, registrations);

    const values = widgetValues(registration);
    if (Array.isArray(values)) {
        try {
            Object.defineProperty(values, REGISTRATION_MARKER, {
                value: registration,
                configurable: true,
                enumerable: false,
            });
        } catch (_error) {
            // The active-node fallback still handles a frozen options array.
        }
    }
    installContextMenuPreview();
}
