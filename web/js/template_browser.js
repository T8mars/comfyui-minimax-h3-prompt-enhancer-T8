import { api } from "../../scripts/api.js";
import { rankTemplates } from "./template_recommendation.mjs";
import { ensurePreview } from "./preview_asset_ui.js";


const FAVORITES_KEY = "t8.prompt-enhancer.template-favorites.v1";
const RECENTS_KEY = "t8.prompt-enhancer.template-recents.v1";
const MAX_RECENTS = 12;
let activeBrowser = null;


function readIds(key) {
    try {
        const value = JSON.parse(localStorage.getItem(key) || "[]");
        return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
    } catch (_error) {
        return [];
    }
}


function writeIds(key, ids) {
    try {
        localStorage.setItem(key, JSON.stringify(ids));
    } catch (_error) {
        // Browsing remains functional when storage is disabled.
    }
}


function categoryFor(template) {
    if (String(template.authority || "").includes("社区")) return "社区 Skill";
    const value = `${template.label || ""} ${template.summary || ""}`;
    const rules = [
        ["品牌与广告", /品牌|广告|产品|宣传|标志|logo|包装/i],
        ["角色与叙事", /角色|人物|真人|英雄|怪物|宠物|叙事|剧情|反派/i],
        ["音乐与节奏", /音乐|MV|舞蹈|节拍|歌词|演出|舞台/i],
        ["工艺与变形", /工艺|材质|机械|拼装|改造|变形|微缩|雕刻|制作/i],
        ["空间与世界", /空间|世界|场景|建筑|路线|环境|城市|地形/i],
        ["视觉与镜头", /镜头|视觉|动画|画中画|构图|转场|证据|风格/i],
    ];
    return rules.find(([, expression]) => expression.test(value))?.[0] || "综合创意";
}


function button(label, title = "") {
    const element = document.createElement("button");
    element.type = "button";
    element.textContent = label;
    element.title = title;
    element.style.cssText = [
        "height:30px", "padding:0 10px", "border:1px solid var(--border-color,#555)",
        "border-radius:6px", "background:var(--comfy-input-bg,#292929)",
        "color:var(--input-text,#eee)", "cursor:pointer",
    ].join(";");
    return element;
}


function templateSearchText(template) {
    return [
        template.label, template.summary, template.input_format, template.recommended_input,
        ...(template.required_anchors || []),
    ].join(" ").toLocaleLowerCase();
}


function releaseImages(root) {
    for (const image of root?.querySelectorAll?.("img") || []) {
        image.onload = null;
        image.onerror = null;
        image.removeAttribute("src");
    }
}


export function openTemplateBrowser({ catalog, selectedValue, onSelect, recommendationContext = {}, initialCategory = "全部" }) {
    activeBrowser?.dismiss?.();
    const overlay = document.createElement("div");
    overlay.className = "t8-template-browser-overlay";
    overlay.style.cssText = [
        "position:fixed", "inset:0", "z-index:100002", "display:flex", "align-items:center",
        "justify-content:center", "padding:20px", "background:rgba(0,0,0,.62)", "box-sizing:border-box",
    ].join(";");
    const dialog = document.createElement("section");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", "T8 非官方模板浏览器");
    dialog.style.cssText = [
        "display:grid", "grid-template-rows:auto 1fr", "width:min(1080px,96vw)", "height:min(760px,92vh)",
        "overflow:hidden", "border:1px solid var(--border-color,#555)", "border-radius:10px",
        "background:var(--comfy-menu-bg,#202020)", "color:var(--input-text,#eee)",
        "box-shadow:0 18px 60px rgba(0,0,0,.65)",
    ].join(";");
    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;gap:8px;padding:10px;border-bottom:1px solid #555";
    const title = document.createElement("strong");
    title.textContent = `T8 模板浏览器（${catalog.templates?.length || 0}）`;
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "搜索名称、用途、锚点或推荐输入";
    search.style.cssText = "flex:1;min-width:120px;height:32px;padding:0 9px;border:1px solid #555;border-radius:6px;background:#171717;color:#eee";
    const compare = button("对比（0/3）", "选择 2–3 个模板并排对比");
    const close = button("关闭", "Esc");
    header.append(title, search, compare, close);

    const body = document.createElement("div");
    body.style.cssText = "display:grid;min-height:0";
    const left = document.createElement("div");
    left.style.cssText = "display:grid;grid-template-rows:auto 1fr;min-height:0;border-right:1px solid #555";
    const filters = document.createElement("div");
    filters.style.cssText = [
        "display:grid", "grid-template-columns:repeat(auto-fit,minmax(70px,1fr))", "gap:6px",
        "overflow-x:hidden", "overflow-y:auto", "padding:8px", "min-width:0", "box-sizing:border-box",
    ].join(";");
    const list = document.createElement("div");
    list.style.cssText = "overflow:auto;padding:0 8px 8px";
    const detail = document.createElement("div");
    detail.style.cssText = "overflow:auto;padding:14px;display:flex;flex-direction:column;gap:9px";
    left.append(filters, list);
    body.append(left, detail);
    dialog.append(header, body);
    overlay.append(dialog);
    document.body.append(overlay);

    const applyResponsiveLayout = () => {
        const compact = window.innerWidth < 780;
        body.style.gridTemplateColumns = compact ? "1fr" : "minmax(280px,38%) minmax(0,1fr)";
        body.style.gridTemplateRows = compact ? "minmax(220px,42%) minmax(0,1fr)" : "1fr";
        left.style.borderRight = compact ? "0" : "1px solid #555";
        left.style.borderBottom = compact ? "1px solid #555" : "0";
    };
    applyResponsiveLayout();
    window.addEventListener("resize", applyResponsiveLayout);

    const templates = [...(catalog.templates || [])];
    const byId = new Map(templates.map((item) => [item.id, item]));
    const recommendations = rankTemplates(templates, recommendationContext, 3);
    const recommendationReasons = new Map(recommendations.map((item) => [item.template.id, item.reasons]));
    let favorites = readIds(FAVORITES_KEY).filter((id) => byId.has(id));
    let recents = readIds(RECENTS_KEY).filter((id) => byId.has(id));
    const categories = ["全部", "推荐 Top-3", "收藏", "最近", ...new Set(templates.map(categoryFor))];
    let category = categories.includes(initialCategory) ? initialCategory : "全部";
    let activeTemplate = templates.find((item) => item.label === selectedValue || item.id === selectedValue) || templates[0];
    const comparison = new Set();

    const dismiss = () => {
        releaseImages(dialog);
        overlay.remove();
        if (activeBrowser?.overlay === overlay) activeBrowser = null;
        document.removeEventListener("keydown", onKey);
        window.removeEventListener("resize", applyResponsiveLayout);
    };
    const onKey = (event) => {
        if (event.key === "Escape") dismiss();
    };
    close.onclick = dismiss;
    overlay.addEventListener("pointerdown", (event) => {
        if (event.target === overlay) dismiss();
    });
    document.addEventListener("keydown", onKey);
    activeBrowser = { overlay, dismiss };

    const updateCompareLabel = () => {
        compare.textContent = `对比（${comparison.size}/3）`;
        compare.disabled = comparison.size < 2;
        compare.style.opacity = comparison.size < 2 ? ".55" : "1";
    };

    function appendOnePreview(container, template, maxHeight = 250) {
        const preview = (template.previews || []).find((item) => (item.available && item.preview_url) || item.downloadable);
        if (!preview) return;
        const host = document.createElement("div");
        host.style.cssText = "display:flex;flex-direction:column;gap:7px";
        container.append(host);
        const renderImage = (url) => {
            host.replaceChildren();
            const image = document.createElement("img");
            image.loading = "lazy";
            image.decoding = "async";
            image.alt = `${preview.label || template.label} GIF 预览`;
            image.style.cssText = `display:block;width:100%;max-height:${maxHeight}px;object-fit:contain;border-radius:7px;background:#111`;
            image.src = url;
            host.append(image);
        };
        if (preview.available && preview.preview_url) {
            renderImage(api.apiURL(preview.preview_url));
            return;
        }
        const message = document.createElement("div");
        message.textContent = "正在准备 GIF 预览…";
        message.style.cssText = "padding:22px 12px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.72";
        const download = button("下载此预览");
        host.append(message, download);
        const load = async (force) => {
            try {
                const url = await ensurePreview(preview, { force });
                if (url && host.isConnected) renderImage(url);
                else message.textContent = "当前为仅手动下载模式；提示词增强可正常使用。";
            } catch (error) {
                message.textContent = `GIF 获取失败：${error.message}；不影响提示词增强。`;
            }
        };
        download.onclick = () => load(true);
        load(false);
    }

    function renderComparison() {
        releaseImages(detail);
        detail.replaceChildren();
        const selected = [...comparison].map((id) => byId.get(id)).filter(Boolean).slice(0, 3);
        const grid = document.createElement("div");
        grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px";
        for (const template of selected) {
            const card = document.createElement("section");
            card.style.cssText = "display:flex;flex-direction:column;gap:7px;padding:10px;border:1px solid #555;border-radius:8px;min-width:0";
            const heading = document.createElement("strong");
            heading.textContent = template.label;
            const summary = document.createElement("div");
            summary.textContent = template.summary || "";
            const recommended = document.createElement("div");
            recommended.textContent = `推荐输入：${template.recommended_input || ""}`;
            const anchors = document.createElement("ol");
            anchors.style.margin = "0 0 0 18px";
            for (const value of template.required_anchors || []) {
                const item = document.createElement("li");
                item.textContent = value;
                anchors.append(item);
            }
            const use = button("使用此模板");
            use.onclick = () => { onSelect(template); dismiss(); };
            card.append(heading, summary, recommended, anchors, use);
            appendOnePreview(card, template, 210);
            grid.append(card);
        }
        detail.append(grid);
    }
    compare.onclick = renderComparison;
    updateCompareLabel();

    function renderDetail(template) {
        activeTemplate = template;
        releaseImages(detail);
        detail.replaceChildren();
        if (!template) return;
        const heading = document.createElement("h3");
        heading.textContent = template.label;
        heading.style.margin = "0";
        const authority = document.createElement("small");
        authority.textContent = `${template.authority || "T8 非官方模板"} · ${categoryFor(template)}`;
        authority.style.opacity = ".7";
        const summary = document.createElement("div");
        summary.textContent = template.summary || "";
        const reasons = recommendationReasons.get(template.id);
        const why = document.createElement("div");
        why.textContent = reasons?.length ? `为什么推荐：${reasons.join("；")}` : "";
        why.style.cssText = "color:#b9d5ff;font-size:12px";
        const recommended = document.createElement("div");
        recommended.textContent = `简约推荐输入：${template.recommended_input || ""}`;
        recommended.style.cssText = "padding:9px;border-radius:6px;background:rgba(255,255,255,.05);line-height:1.5";
        const anchors = document.createElement("ol");
        anchors.style.margin = "0 0 0 20px";
        for (const value of template.required_anchors || []) {
            const item = document.createElement("li");
            item.textContent = value;
            anchors.append(item);
        }
        const actions = document.createElement("div");
        actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
        const use = button("使用此模板");
        const favorite = button(favorites.includes(template.id) ? "★ 已收藏" : "☆ 收藏");
        use.onclick = () => {
            recents = [template.id, ...recents.filter((id) => id !== template.id)].slice(0, MAX_RECENTS);
            writeIds(RECENTS_KEY, recents);
            onSelect(template);
            dismiss();
        };
        favorite.onclick = () => {
            favorites = favorites.includes(template.id)
                ? favorites.filter((id) => id !== template.id)
                : [template.id, ...favorites];
            writeIds(FAVORITES_KEY, favorites);
            renderFilters();
            renderList();
            renderDetail(template);
        };
        actions.append(use, favorite);
        detail.append(heading, authority, summary);
        if (reasons?.length) detail.append(why);
        detail.append(recommended, anchors, actions);
        appendOnePreview(detail, template, 330);
        if (!(template.previews || []).some((item) => (item.available && item.preview_url) || item.downloadable)) {
            const empty = document.createElement("div");
            empty.textContent = "本机未配置此模板 GIF；不影响提示词增强。";
            empty.style.cssText = "padding:28px;border:1px dashed #666;border-radius:7px;text-align:center;opacity:.7";
            detail.append(empty);
        }
        const policy = document.createElement("small");
        policy.textContent = "GIF 仅供人类选择时预览，不会发送给 LLM，也不会作为模型参考素材。";
        policy.style.opacity = ".6";
        detail.append(policy);
    }

    function visibleTemplates() {
        const query = search.value.trim().toLocaleLowerCase();
        let values = templates;
        if (category === "推荐 Top-3") values = recommendations.map((item) => item.template);
        else if (category === "收藏") values = favorites.map((id) => byId.get(id)).filter(Boolean);
        else if (category === "最近") values = recents.map((id) => byId.get(id)).filter(Boolean);
        else if (category !== "全部") values = values.filter((item) => categoryFor(item) === category);
        if (query) values = values.filter((item) => templateSearchText(item).includes(query));
        return values;
    }

    function renderList() {
        list.replaceChildren();
        const values = visibleTemplates();
        for (const template of values) {
            const wrapper = document.createElement("div");
            wrapper.style.cssText = "display:flex;align-items:center;border-bottom:1px solid rgba(255,255,255,.07)";
            const row = document.createElement("button");
            row.type = "button";
            row.setAttribute("aria-label", `查看模板：${template.label}`);
            row.style.cssText = [
                "display:flex", "width:100%", "align-items:center", "gap:7px", "padding:8px",
                "border:0", "text-align:left",
                "background:transparent", "color:inherit", "cursor:pointer",
            ].join(";");
            row.textContent = `${favorites.includes(template.id) ? "★ " : ""}${template.label}`;
            if (template === activeTemplate) {
                row.style.background = "rgba(90,150,255,.16)";
                row.setAttribute("aria-current", "true");
            }
            row.onclick = () => {
                renderDetail(template);
                renderList();
            };
            const pick = button(comparison.has(template.id) ? "✓" : "+", "加入/移出对比");
            pick.style.width = "32px";
            pick.onclick = () => {
                if (comparison.has(template.id)) comparison.delete(template.id);
                else if (comparison.size < 3) comparison.add(template.id);
                updateCompareLabel();
                renderList();
            };
            wrapper.append(row, pick);
            list.append(wrapper);
        }
        if (!values.length) {
            const empty = document.createElement("div");
            empty.textContent = "没有匹配模板";
            empty.style.cssText = "padding:24px;text-align:center;opacity:.65";
            list.append(empty);
        }
    }

    function renderFilters() {
        filters.replaceChildren();
        for (const value of categories) {
            const item = button(value);
            item.style.cssText += ";width:100%;min-width:0;height:auto;min-height:30px;padding:5px 7px;white-space:normal;overflow-wrap:anywhere;line-height:1.2;box-sizing:border-box";
            if (value === category) item.style.background = "rgba(90,150,255,.25)";
            item.onclick = () => {
                category = value;
                renderFilters();
                renderList();
            };
            filters.append(item);
        }
    }

    search.addEventListener("input", renderList);
    renderFilters();
    renderList();
    renderDetail(activeTemplate);
    search.focus();
}
