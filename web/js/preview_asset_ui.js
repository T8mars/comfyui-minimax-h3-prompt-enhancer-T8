import { api } from "../../scripts/api.js";


const STATUS_ENDPOINT = "/t8-prompt-enhancer/preview-assets/status";
let activeManager = null;


async function requestJson(path, options = {}) {
    const response = await api.fetchApi(path, { cache: "no-store", ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
}


export async function ensurePreview(preview, { force = false } = {}) {
    if (preview?.available && preview.preview_url) return api.apiURL(preview.preview_url);
    if (!preview?.downloadable || !preview.ensure_url) return "";
    if (!force && preview.auto_download === false) return "";
    if (!preview.t8EnsurePromise) {
        preview.t8EnsurePromise = requestJson(preview.ensure_url, { method: "POST" })
            .then((result) => {
                preview.available = true;
                preview.cached = true;
                preview.preview_url = result.preview_url;
                return api.apiURL(result.preview_url);
            })
            .finally(() => { preview.t8EnsurePromise = null; });
    }
    return preview.t8EnsurePromise;
}


function modalButton(label) {
    const element = document.createElement("button");
    element.type = "button";
    element.textContent = label;
    element.style.cssText = [
        "height:32px", "padding:0 11px", "border:1px solid #5b5b5b", "border-radius:6px",
        "background:var(--comfy-input-bg,#292929)", "color:var(--input-text,#eee)", "cursor:pointer",
    ].join(";");
    return element;
}


export async function openPreviewAssetManager(catalog) {
    activeManager?.dismiss?.();
    const overlay = document.createElement("div");
    overlay.className = "t8-preview-asset-manager-overlay";
    overlay.style.cssText = [
        "position:fixed", "inset:0", "z-index:100004", "display:flex", "align-items:center",
        "justify-content:center", "padding:18px", "background:rgba(0,0,0,.65)", "box-sizing:border-box",
    ].join(";");
    const dialog = document.createElement("section");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.style.cssText = [
        "display:flex", "flex-direction:column", "gap:12px", "width:min(620px,96vw)", "max-height:90vh",
        "overflow:auto", "padding:16px", "border:1px solid #5b5b5b", "border-radius:10px",
        "background:var(--comfy-menu-bg,#202020)", "color:var(--input-text,#eee)",
        "box-shadow:0 18px 60px rgba(0,0,0,.65)",
    ].join(";");
    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px";
    const heading = document.createElement("strong");
    heading.textContent = "T8 动态预览资源管理";
    const close = modalButton("关闭");
    header.append(heading, close);
    const explanation = document.createElement("div");
    explanation.textContent = "默认按需下载：仅在查看某个案例时获取对应分片。预览始终只供人类界面查看，不会发送给 LLM，也不会影响提示词生成。";
    explanation.style.cssText = "font-size:12px;line-height:1.55;opacity:.82";
    const modeRow = document.createElement("label");
    modeRow.style.cssText = "display:flex;align-items:center;gap:9px;flex-wrap:wrap";
    modeRow.append(document.createTextNode("更新模式："));
    const mode = document.createElement("select");
    mode.style.cssText = "height:32px;min-width:230px;background:#181818;color:#eee;border:1px solid #555;border-radius:6px";
    for (const [value, label] of [
        ["on_demand", "智能按需（推荐）"],
        ["full_auto", "自动补齐全部"],
        ["manual", "仅手动下载"],
    ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        mode.append(option);
    }
    modeRow.append(mode);
    const status = document.createElement("pre");
    status.style.cssText = "white-space:pre-wrap;margin:0;padding:10px;border-radius:7px;background:#151515;font:12px/1.55 monospace";
    const progress = document.createElement("div");
    progress.style.cssText = "min-height:20px;font-size:12px;color:#b9d5ff";
    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    const check = modalButton("检查资源更新");
    const install = modalButton("下载缺失 / 全部");
    const repair = modalButton("校验并修复");
    const clear = modalButton("清空预览缓存");
    actions.append(check, install, repair, clear);
    dialog.append(header, explanation, modeRow, status, progress, actions);
    overlay.append(dialog);
    document.body.append(overlay);

    const dismiss = () => {
        overlay.remove();
        if (activeManager?.overlay === overlay) activeManager = null;
    };
    activeManager = { overlay, dismiss };
    close.onclick = dismiss;
    overlay.addEventListener("pointerdown", (event) => { if (event.target === overlay) dismiss(); });

    const renderStatus = (value) => {
        mode.value = value.mode || "on_demand";
        const megabytes = (Number(value.cached_bytes || 0) / 1024 / 1024).toFixed(1);
        status.textContent = [
            `资源通道：${value.channel_version || "不可用"}`,
            `已缓存：${value.cached_count || 0} / ${value.downloadable_count || 0}（${megabytes} MB）`,
            `缓存位置：${value.cache_root || ""}`,
        ].join("\n");
    };
    const run = async (label, operation) => {
        for (const item of [check, install, repair, clear, mode]) item.disabled = true;
        progress.textContent = label;
        try {
            const result = await operation();
            renderStatus(result);
            progress.textContent = "完成";
            return result;
        } catch (error) {
            progress.textContent = `失败：${error.message}（不影响提示词增强）`;
            return null;
        } finally {
            for (const item of [check, install, repair, clear, mode]) item.disabled = false;
        }
    };
    mode.onchange = () => run("正在保存更新模式…", () => requestJson(
        "/t8-prompt-enhancer/preview-assets/settings",
        { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: mode.value }) },
    ).then(() => requestJson(STATUS_ENDPOINT)).then((result) => {
        for (const template of catalog?.templates || []) {
            for (const preview of template.previews || []) {
                preview.auto_download = result.mode !== "manual";
            }
        }
        return result;
    }));
    check.onclick = () => run("正在检查远端资源清单…", () => requestJson(
        "/t8-prompt-enhancer/preview-assets/check", { method: "POST" },
    ));
    install.onclick = () => run("正在下载缺失分片，请保持 ComfyUI 运行…", () => requestJson(
        "/t8-prompt-enhancer/preview-assets/install-all", { method: "POST" },
    ).then((result) => {
        for (const template of catalog?.templates || []) {
            for (const preview of template.previews || []) {
                if (preview.downloadable) {
                    preview.available = true;
                    preview.cached = true;
                    preview.preview_url = `/t8-prompt-enhancer/case-preview/${preview.case_id}`;
                }
            }
        }
        return result;
    }));
    repair.onclick = () => run("正在逐项校验并修复缓存…", () => requestJson(
        "/t8-prompt-enhancer/preview-assets/repair", { method: "POST" },
    ));
    clear.onclick = () => run("正在清空可重新下载的预览缓存…", () => requestJson(
        "/t8-prompt-enhancer/preview-assets/cache", { method: "DELETE" },
    ).then((result) => {
        for (const template of catalog?.templates || []) {
            for (const preview of template.previews || []) {
                if (preview.cached) {
                    preview.cached = false;
                    preview.available = false;
                    preview.preview_url = "";
                }
            }
        }
        return result;
    }));

    try {
        renderStatus(await requestJson(STATUS_ENDPOINT));
    } catch (error) {
        progress.textContent = `状态读取失败：${error.message}`;
    }
}
