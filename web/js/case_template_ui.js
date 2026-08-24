import { api } from "../../scripts/api.js";
import { registerTemplateMenuPreview } from "./template_menu_preview.js";
import { openTemplateBrowser } from "./template_browser.js";


const NO_CASE_TEMPLATE = "无（不使用 T8 案例）";
const CATALOG_ENDPOINT = "/t8-prompt-enhancer/case-library";
let catalogPromise = null;


function fetchCatalog() {
    if (!catalogPromise) {
        catalogPromise = api.fetchApi(CATALOG_ENDPOINT, { cache: "no-store" })
            .then(async (response) => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .catch((error) => {
                catalogPromise = null;
                throw error;
            });
    }
    return catalogPromise;
}


export function setTextWidgetValue(widget, value) {
    if (!widget) return;
    widget.value = value;
    const input = widget.inputEl
        || (widget.element?.matches?.("textarea, input") ? widget.element : null)
        || widget.element?.querySelector?.("textarea, input");
    if (input) input.value = value;
    widget.callback?.(value);
}


export function setDomWidgetVisible(widget, visible) {
    if (!("t8CaseOriginalType" in widget)) {
        widget.t8CaseOriginalType = widget.type;
        widget.t8CaseOriginalComputeSize = widget.computeSize;
    }
    widget.type = visible ? widget.t8CaseOriginalType : "converted-widget";
    widget.computeSize = visible ? widget.t8CaseOriginalComputeSize : () => [0, -4];
    widget.hidden = !visible;
    if (widget.element) {
        widget.element.style.display = visible ? "block" : "none";
        widget.element.hidden = !visible;
    }
}


export function textRow(label, value) {
    const row = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = `${label}：`;
    row.append(strong, document.createTextNode(value));
    return row;
}


export function createTemplateDetailCard() {
    const root = document.createElement("div");
    root.style.cssText = [
        "display:flex", "flex-direction:column", "gap:8px", "width:100%", "box-sizing:border-box",
        "padding:10px", "border:1px solid var(--border-color,#555)", "border-radius:7px",
        "background:var(--comfy-input-bg,#202020)", "color:var(--input-text,#ddd)",
        "font-size:12px", "line-height:1.45", "overflow:hidden",
    ].join(";");
    return root;
}


export function renderTemplateDetail(
    root,
    template,
    promptWidget,
    node,
    refreshSize,
    {
        resolvePreviewUrl = (preview) => api.apiURL(preview.preview_url),
        sourceLabel = "查看来源",
        policyText = "仅供人类本地预览，不会作为图像、视频或 LLM 参考素材",
    } = {},
) {
    for (const image of root.querySelectorAll("img")) {
        image.onload = null;
        image.onerror = null;
        image.removeAttribute("src");
    }
    root.replaceChildren();

    const title = document.createElement("div");
    title.textContent = template.label;
    title.style.cssText = "font-weight:700;font-size:14px;color:var(--input-text,#eee)";
    root.append(title);
    root.append(textRow("用途", template.summary));
    const mechanismName = template.label.includes("｜") ? template.label.split("｜").slice(1).join("｜") : template.label;
    root.append(textRow(
        "适用范围",
        template.applicability || `适合需要“${mechanismName}”结构的视频创意；主体、场景和表面风格均可替换。`,
    ));
    root.append(textRow("推荐输入格式", template.input_format));

    const anchors = document.createElement("div");
    const anchorTitle = document.createElement("strong");
    anchorTitle.textContent = "必须命中的结构锚点：";
    const list = document.createElement("ol");
    list.style.cssText = "margin:4px 0 0 20px;padding:0";
    for (const anchor of template.required_anchors) {
        const item = document.createElement("li");
        item.textContent = anchor;
        list.append(item);
    }
    anchors.append(anchorTitle, list);
    root.append(anchors);

    const sample = document.createElement("div");
    sample.style.cssText = "padding:7px;border-radius:5px;background:rgba(255,255,255,.045)";
    sample.append(textRow("推荐示例（可编辑输入，不是最终提示词）", template.recommended_input));
    root.append(sample);

    const buttonRow = document.createElement("div");
    buttonRow.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
    const fill = document.createElement("button");
    fill.type = "button";
    fill.textContent = "填入推荐示例";
    fill.title = "仅当主提示词为空时填入；不会覆盖已有输入";
    fill.style.cssText = [
        "height:28px", "padding:0 10px", "border:1px solid var(--border-color,#555)", "border-radius:5px",
        "background:var(--comfy-input-bg,#2a2a2a)", "color:var(--input-text,#ddd)", "cursor:pointer",
    ].join(";");
    const status = document.createElement("span");
    status.style.cssText = "opacity:.8";
    fill.onclick = () => {
        if (String(promptWidget?.value || "").trim()) {
            status.textContent = "已有输入，未覆盖";
            return;
        }
        setTextWidgetValue(promptWidget, template.recommended_input);
        node.graph?.change?.();
        node.setDirtyCanvas(true, true);
        status.textContent = "已填入，可继续修改";
    };
    buttonRow.append(fill, status);
    root.append(buttonRow);

    const previewWrap = document.createElement("div");
    previewWrap.style.cssText = "display:flex;flex-direction:column;gap:8px";
    const previewChoices = Array.isArray(template.previews) ? template.previews : [];
    const renderPreview = (preview) => {
        for (const image of previewWrap.querySelectorAll("img")) {
            image.onload = null;
            image.onerror = null;
            image.removeAttribute("src");
        }
        previewWrap.replaceChildren();
        if (!preview) return;
        const figure = document.createElement("div");
        figure.style.cssText = "display:flex;flex-direction:column;gap:5px;min-width:0";
        const caption = document.createElement("div");
        caption.textContent = preview.label;
        caption.style.fontWeight = "600";
        figure.append(caption);
        if (previewChoices.length > 1) {
            figure.append(textRow("此证据用途", preview.short_summary));
            figure.append(textRow("此 GIF 推荐示例", preview.recommended_input));
        }
        if (preview.available && preview.preview_url) {
            const img = document.createElement("img");
            img.src = resolvePreviewUrl(preview);
            img.alt = `${preview.label} GIF 预览`;
            img.loading = "lazy";
            img.style.cssText = "display:block;width:100%;max-height:220px;object-fit:contain;border-radius:5px;background:#111";
            img.onload = () => refreshSize?.();
            img.onerror = () => {
                img.replaceWith(document.createTextNode("GIF 预览加载失败"));
                refreshSize?.();
            };
            figure.append(img);
        } else {
            const unavailable = document.createElement("div");
            unavailable.textContent = "本机未配置此模板的 GIF 预览；不影响提示词增强。";
            unavailable.style.cssText = "padding:12px;border:1px dashed #666;border-radius:5px;opacity:.75";
            figure.append(unavailable);
        }
        if (preview.source_url) {
            const source = document.createElement("a");
            source.href = preview.source_url;
            source.target = "_blank";
            source.rel = "noopener noreferrer";
            source.textContent = preview.source_label || sourceLabel;
            source.style.color = "var(--link-color,#7ab7ff)";
            figure.append(source);
        }
        const policy = document.createElement("small");
        policy.textContent = policyText;
        policy.style.opacity = ".65";
        figure.append(policy);
        previewWrap.append(figure);
        refreshSize?.();
    };
    if (previewChoices.length > 1) {
        const selector = document.createElement("select");
        selector.style.cssText = "height:28px;max-width:100%;background:#1b1b1b;color:#ddd;border:1px solid #555;border-radius:5px";
        previewChoices.forEach((preview, index) => {
            const option = document.createElement("option");
            option.value = String(index);
            option.textContent = preview.label || `证据 ${index + 1}`;
            selector.append(option);
        });
        selector.addEventListener("change", () => renderPreview(previewChoices[Number(selector.value)]));
        root.append(selector);
    }
    renderPreview(previewChoices[0]);
    root.append(previewWrap);
    requestAnimationFrame(() => refreshSize?.());
}


export async function addCaseTemplateUI(node, caseWidget, promptWidget, refreshSize) {
    if (!caseWidget || !promptWidget) return null;
    const root = createTemplateDetailCard();
    root.textContent = "正在读取非官方模板说明…";
    const domWidget = node.addDOMWidget("t8_case_template_details", "custom", root, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => Math.max(150, root.scrollHeight + 8),
        getMaxHeight: () => Math.max(150, root.scrollHeight + 8),
        hideOnZoom: false,
        serialize: false,
        beforeResize() { delete this.width; },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas(true, true);
        },
    });
    delete domWidget.width;
    domWidget.serializeValue = () => undefined;

    let catalog;
    try {
        catalog = await fetchCatalog();
    } catch (error) {
        root.textContent = `模板说明加载失败：${error.message}`;
        setDomWidgetVisible(domWidget, caseWidget.value !== NO_CASE_TEMPLATE);
        refreshSize?.();
        return domWidget;
    }
    const byLabel = new Map();
    const byId = new Map();
    for (const template of catalog.templates || []) {
        byLabel.set(template.label, template);
        byId.set(template.id, template);
        for (const alias of [...(template.legacy_labels || []), ...(template.legacy_ids || [])]) {
            byId.set(alias, template);
        }
    }
    node.t8CaseCatalog = catalog;
    node.t8CaseTemplateId = () => byLabel.get(caseWidget.value)?.id || caseWidget.value || NO_CASE_TEMPLATE;
    node.t8RestoreCaseTemplate = (value) => {
        const template = byLabel.get(value) || byId.get(value);
        if (template) caseWidget.value = template.label;
    };
    if (node.t8PendingCaseTemplateValue) {
        node.t8RestoreCaseTemplate(node.t8PendingCaseTemplateValue);
        node.t8PendingCaseTemplateValue = "";
    }

    registerTemplateMenuPreview(node, caseWidget, (value) => {
        const template = byLabel.get(value) || byId.get(value);
        if (!template) {
            return {
                authority: "T8 非官方模板（案例 / 社区 Skill）",
                title: value || "T8 非官方模板（案例 / 社区 Skill）",
                summary: "悬停一个具体模板即可在右侧查看对应 GIF、用途与简约推荐输入。",
                empty_message: "当前未启用非官方模板。",
                previews: [],
            };
        }
        return {
            authority: template.authority || "T8 非官方模板（案例 / 社区 Skill）",
            title: template.label,
            summary: template.summary,
            input_format: template.input_format,
            recommended_input: template.recommended_input,
            previews: (template.previews || []).map((preview) => ({
                label: preview.label,
                summary: preview.short_summary,
                recommended_input: preview.recommended_input,
                url: preview.available && preview.preview_url ? api.apiURL(preview.preview_url) : "",
                available: Boolean(preview.available && preview.preview_url),
                unavailable_message: "本机未配置此模板 GIF；不影响提示词增强。",
                source_url: preview.source_url || "",
                source_label: "查看案例来源",
            })),
            policy: "GIF 仅供人类本地预览，不会作为图像、视频或 LLM 参考素材",
        };
    });

    const update = (value = caseWidget.value) => {
        const template = byLabel.get(value) || byId.get(value);
        if (!template) {
            root.replaceChildren();
            setDomWidgetVisible(domWidget, false);
        } else {
            if (caseWidget.value !== template.label) caseWidget.value = template.label;
            renderTemplateDetail(root, template, promptWidget, node, refreshSize);
            setDomWidgetVisible(domWidget, true);
        }
        refreshSize?.();
    };
    const originalCallback = caseWidget.callback;
    caseWidget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.t8UpdateCaseTemplate = update;
    const browserWidget = node.addWidget(
        "button",
        "浏览 T8 模板库（分类 / 搜索 / 收藏 / 最近）",
        null,
        () => openTemplateBrowser({
            catalog,
            selectedValue: caseWidget.value,
            onSelect: (template) => {
                caseWidget.value = template.label;
                caseWidget.callback?.(template.label);
                node.graph?.change?.();
                node.setDirtyCanvas(true, true);
            },
        }),
        { serialize: false },
    );
    browserWidget.serializeValue = () => undefined;
    const recommendWidget = node.addWidget(
        "button",
        "本地推荐 Top-3 / 对比",
        "只在本地根据关键词、任务类型、素材类型和结构锚点排序，不发送用户输入",
        () => {
            const linkedInputs = (node.inputs || []).filter((input) => input.link != null).map((input) => input.name).join(" ");
            const taskWidget = node.widgets?.find((widget) => ["task_type", "task_intent"].includes(widget.name));
            openTemplateBrowser({
                catalog,
                selectedValue: caseWidget.value,
                recommendationContext: {
                    prompt: String(promptWidget.value || ""),
                    task: String(taskWidget?.value || ""),
                    media: linkedInputs,
                },
                initialCategory: "推荐 Top-3",
                onSelect: (template) => {
                    caseWidget.value = template.label;
                    caseWidget.callback?.(template.label);
                    node.graph?.change?.();
                    node.setDirtyCanvas(true, true);
                },
            });
        },
        { serialize: false },
    );
    recommendWidget.serializeValue = () => undefined;
    const browserIndex = node.widgets?.indexOf(browserWidget) ?? -1;
    const detailIndex = node.widgets?.indexOf(domWidget) ?? -1;
    if (browserIndex > detailIndex && detailIndex >= 0) {
        node.widgets.splice(browserIndex, 1);
        node.widgets.splice(detailIndex, 0, browserWidget);
        const recommendIndex = node.widgets.indexOf(recommendWidget);
        if (recommendIndex >= 0) {
            node.widgets.splice(recommendIndex, 1);
            node.widgets.splice(detailIndex + 1, 0, recommendWidget);
        }
    }
    update();
    return domWidget;
}


export function serializedCaseTemplateValue(node, widget) {
    return node.t8CaseTemplateId?.() || widget?.value || NO_CASE_TEMPLATE;
}


export { NO_CASE_TEMPLATE };
