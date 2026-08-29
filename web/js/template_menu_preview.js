const REGISTRATION_MARKER = Symbol.for("t8.prompt-enhancer.combo-preview");
const registrationsByNode = new WeakMap();
let activePanel = null;
let activeCleanup = null;
let activeRenderTimer = null;
let activeRenderEpoch = 0;


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


export function renderPreview(panel, model, reposition) {
    for (const image of panel.querySelectorAll("img")) {
        image.onload = null;
        image.onerror = null;
        image.removeAttribute("src");
    }
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
    if (model?.input_format) {
        panel.append(textBlock(
            "t8-template-preview-input-format",
            `推荐输入格式：${model.input_format}`,
            "font-size:11px;line-height:1.45;opacity:.78",
        ));
    }
    if (model?.recommended_input) {
        panel.append(textBlock(
            "t8-template-preview-recommended-input",
            `简约推荐输入：${model.recommended_input}`,
            "font-size:11px;line-height:1.45;padding:7px;border-radius:5px;background:rgba(255,255,255,.045)",
        ));
    }
    if (model?.preview_manager && typeof model.preview_manager.onClick === "function") {
        const callout = document.createElement("div");
        callout.className = "t8-preview-manager-callout";
        callout.style.cssText = [
            "display:flex", "flex-direction:column", "gap:7px", "padding:9px",
            "border:1px solid rgba(255,190,74,.82)", "border-radius:7px",
            "background:rgba(255,166,35,.13)", "box-shadow:inset 0 0 0 1px rgba(255,220,150,.05)",
        ].join(";");
        callout.append(textBlock(
            "t8-preview-manager-reminder",
            model.preview_manager.hint || "首次使用或 GIF 未显示时，请先检查并更新动态预览。",
            "font-size:11px;line-height:1.45;color:#ffd99a;font-weight:600",
        ));
        const manage = document.createElement("button");
        manage.type = "button";
        manage.dataset.t8PreviewManagerAction = "true";
        manage.textContent = model.preview_manager.label || "管理 / 更新动态预览";
        manage.title = model.preview_manager.title || "检查、下载或修复 T8 模板 GIF 预览资源";
        manage.style.cssText = [
            "min-height:34px", "padding:5px 11px", "border:1px solid #ffbe4a", "border-radius:6px",
            "background:#8a5312", "color:#fff4dc", "font-weight:700", "cursor:pointer",
        ].join(";");
        manage.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();
        });
        manage.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            model.preview_manager.onClick();
        });
        callout.append(manage);
        panel.append(callout);
    }

    const previews = Array.isArray(model?.previews) ? model.previews : [];
    if (!previews.length) {
        panel.append(textBlock(
            "t8-template-preview-empty",
            model?.empty_message || "悬停一个具体模板即可查看对应 GIF。",
            "padding:22px 12px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.72",
        ));
    }

    const previewHost = document.createElement("div");
    previewHost.style.cssText = "display:flex;flex-direction:column;gap:6px;min-width:0";
    let renderedPreview = null;
    const renderOne = (preview) => {
        renderedPreview = preview;
        for (const image of previewHost.querySelectorAll("img")) {
            image.onload = null;
            image.onerror = null;
            image.removeAttribute("src");
        }
        previewHost.replaceChildren();
        if (!preview) return;
        const figure = document.createElement("div");
        figure.style.cssText = "display:flex;flex-direction:column;gap:6px;min-width:0";
        if (preview.label) {
            figure.append(textBlock("t8-template-preview-label", preview.label, "font-size:12px;font-weight:600"));
        }
        if (preview.summary && preview.summary !== model?.summary) {
            figure.append(textBlock("t8-template-preview-evidence-summary", preview.summary, "font-size:11px;opacity:.8"));
        }
        if (preview.recommended_input && preview.recommended_input !== model?.recommended_input) {
            figure.append(textBlock(
                "t8-template-preview-evidence-input",
                `此证据推荐输入：${preview.recommended_input}`,
                "font-size:11px;line-height:1.4;opacity:.78",
            ));
        }
        if (preview.available !== false && preview.url) {
            const image = document.createElement("img");
            image.alt = `${preview.label || model?.title || "模板"} GIF 预览`;
            image.loading = "lazy";
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
            image.src = preview.url;
            figure.append(image);
        } else {
            const unavailable = textBlock(
                "t8-template-preview-unavailable",
                preview.downloadable ? "正在准备 GIF 预览…" : (preview.unavailable_message || "本机未配置此 GIF；不影响提示词增强。"),
                "padding:22px 12px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.72",
            );
            figure.append(unavailable);
            if (preview.downloadable && typeof preview.ensure === "function") {
                const download = document.createElement("button");
                download.type = "button";
                download.textContent = "下载此预览";
                download.style.cssText = "height:28px;border:1px solid #555;border-radius:5px;background:#292929;color:#eee;cursor:pointer";
                const load = async (force) => {
                    try {
                        const url = await preview.ensure(force);
                        if (url && renderedPreview === preview && previewHost.isConnected) {
                            preview.url = url;
                            preview.available = true;
                            renderOne(preview);
                        } else if (!url) {
                            unavailable.textContent = "当前为仅手动下载模式；提示词增强可正常使用。";
                        }
                    } catch (error) {
                        unavailable.textContent = `GIF 获取失败：${error.message}；不影响提示词增强。`;
                        reposition();
                    }
                };
                download.onclick = () => load(true);
                figure.append(download);
                load(false);
            }
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
        previewHost.append(figure);
        reposition();
    };
    if (previews.length > 1) {
        const selector = document.createElement("select");
        selector.style.cssText = "height:28px;background:#171717;color:#eee;border:1px solid #555;border-radius:5px";
        previews.forEach((preview, index) => {
            const option = document.createElement("option");
            option.value = String(index);
            option.textContent = preview.label || `证据 ${index + 1}`;
            selector.append(option);
        });
        selector.addEventListener("change", () => renderOne(previews[Number(selector.value)]));
        panel.append(selector);
    }
    renderOne(previews[0]);
    panel.append(previewHost);

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
    activeCleanup?.();
    activeCleanup = null;
    if (activeRenderTimer) clearTimeout(activeRenderTimer);
    activeRenderTimer = null;
    activeRenderEpoch += 1;
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
    const showValue = (value, immediate = false) => {
        if (value === renderedValue) return;
        if (activeRenderTimer) clearTimeout(activeRenderTimer);
        const epoch = ++activeRenderEpoch;
        const render = () => {
            activeRenderTimer = null;
            if (epoch !== activeRenderEpoch || !panel.isConnected) return;
            renderedValue = value;
            const model = registration.resolve(String(value ?? ""));
            renderPreview(panel, model, reposition);
        };
        if (immediate) render();
        else activeRenderTimer = setTimeout(render, 120);
    };
    const entries = Array.from(root.querySelectorAll(".litemenu-entry:not(.separator)"));
    for (const entry of entries) {
        const value = entry.dataset.value || entry.textContent || "";
        entry.addEventListener("pointerenter", () => showValue(value));
        entry.addEventListener("focus", () => showValue(value));
    }
    let movedEntry = null;
    let keyboardTimer = null;
    root.addEventListener("mousemove", (event) => {
        const entry = event.target?.closest?.(".litemenu-entry:not(.separator)");
        if (!entry || entry === movedEntry) return;
        movedEntry = entry;
        showValue(entry.dataset.value || entry.textContent || "");
    });

    const showKeyboardSelection = () => {
        if (keyboardTimer) clearTimeout(keyboardTimer);
        keyboardTimer = setTimeout(() => {
        keyboardTimer = null;
        const selected = entries.find((entry) => entry.style.display !== "none" && entry.style.backgroundColor)
            || entries.find((entry) => entry.style.display !== "none");
        if (selected) showValue(selected.dataset.value || selected.textContent || "");
        }, 0);
    };
    const filter = root.querySelector(".comfy-context-menu-filter");
    filter?.addEventListener("keydown", (event) => {
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) showKeyboardSelection();
    });
    filter?.addEventListener("input", showKeyboardSelection);

    let cleaned = false;
    const cleanup = () => {
        if (cleaned) return;
        cleaned = true;
        if (activeRenderTimer) clearTimeout(activeRenderTimer);
        activeRenderTimer = null;
        if (keyboardTimer) clearTimeout(keyboardTimer);
        keyboardTimer = null;
        activeRenderEpoch += 1;
        window.removeEventListener("resize", reposition);
        for (const image of panel.querySelectorAll("img")) {
            image.onload = null;
            image.onerror = null;
            image.removeAttribute("src");
        }
        panel.remove();
        if (activePanel === panel) activePanel = null;
        if (activeCleanup === cleanup) activeCleanup = null;
    };
    const originalClose = contextMenu.close;
    contextMenu.close = function () {
        cleanup();
        return originalClose.apply(this, arguments);
    };
    window.addEventListener("resize", reposition);
    activeCleanup = cleanup;
    showValue(registration.widget?.value, true);
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
