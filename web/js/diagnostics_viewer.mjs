const SAFE_STAGE_KEYS = new Set(["stage", "duration_ms", "attempts", "asset_count", "cache_hit"]);


function safeInteger(value) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? Math.round(number) : undefined;
}


function safeLabel(value, limit) {
    return String(value || "unknown")
        .replace(/https?:\/\/\S+/gi, "[redacted-url]")
        .replace(/(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}/g, "[redacted-key]")
        .replace(/[A-Za-z]:\\[^\s]+/g, "[redacted-path]")
        .replace(/[^A-Za-z0-9 ._()/\-\u4e00-\u9fff\[\]]/g, "?")
        .slice(0, limit);
}


export function sanitizeDiagnosticRecord(record) {
    if (!record || typeof record !== "object") return null;
    const stages = Array.isArray(record.stages)
        ? record.stages.slice(0, 32).map((stage) => {
            const safe = {};
            if (!stage || typeof stage !== "object") return safe;
            for (const key of SAFE_STAGE_KEYS) {
                if (!(key in stage)) continue;
                if (key === "stage") safe.stage = safeLabel(stage.stage, 80);
                else if (key === "cache_hit") safe.cache_hit = Boolean(stage.cache_hit);
                else {
                    const value = safeInteger(stage[key]);
                    if (value !== undefined) safe[key] = value;
                }
            }
            return safe;
        })
        : [];
    const safe = {
        schema_version: "t8-redacted-execution-diagnostic-ui/v1",
        node: safeLabel(record.component, 80),
        provider: safeLabel(record.provider, 80),
        result: safeLabel(record.outcome, 32),
        duration_ms: safeInteger(record.duration_ms) ?? 0,
        stages,
    };
    if (record.error_category) safe.error_category = safeLabel(record.error_category, 64);
    return safe;
}


export function sanitizeDiagnosticSnapshot(snapshot, component = "") {
    const records = Array.isArray(snapshot?.recent) ? snapshot.recent : [];
    const requested = String(component || "");
    const record = records.find((item) => !requested || String(item?.component || "") === requested)
        || records[0];
    return sanitizeDiagnosticRecord(record);
}


function dismissExistingDialog() {
    document.querySelector("[data-t8-diagnostics-dialog]")?.remove();
}


function renderDialog(record) {
    dismissExistingDialog();
    const overlay = document.createElement("div");
    overlay.dataset.t8DiagnosticsDialog = "true";
    overlay.style.cssText = [
        "position:fixed", "inset:0", "z-index:100000", "display:flex", "align-items:center",
        "justify-content:center", "padding:20px", "background:rgba(0,0,0,.58)", "box-sizing:border-box",
    ].join(";");
    const panel = document.createElement("div");
    panel.style.cssText = [
        "width:min(720px,94vw)", "max-height:82vh", "overflow:auto", "border:1px solid #666",
        "border-radius:10px", "padding:16px", "background:#242424", "color:#eee",
        "box-shadow:0 18px 60px rgba(0,0,0,.5)", "font:14px/1.5 sans-serif",
    ].join(";");
    const title = document.createElement("div");
    title.textContent = "脱敏执行诊断";
    title.style.cssText = "font-size:18px;font-weight:700;margin-bottom:8px";
    const notice = document.createElement("div");
    notice.textContent = "仅包含节点、渠道、阶段、耗时、尝试次数、素材数量、缓存状态和安全错误类别。";
    notice.style.cssText = "color:#bbb;margin-bottom:10px";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(record, null, 2);
    pre.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere;background:#181818;padding:12px;border-radius:7px";
    const buttons = document.createElement("div");
    buttons.style.cssText = "display:flex;gap:8px;justify-content:flex-end;margin-top:12px";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "复制脱敏诊断";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "关闭";
    for (const button of [copy, close]) {
        button.style.cssText = "padding:7px 12px;border:1px solid #666;border-radius:6px;background:#333;color:#eee;cursor:pointer";
    }
    copy.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(pre.textContent || "");
            copy.textContent = "已复制";
        } catch (_error) {
            copy.textContent = "复制失败，请手动选择";
        }
    });
    close.addEventListener("click", () => overlay.remove());
    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) overlay.remove();
    });
    buttons.append(copy, close);
    panel.append(title, notice, pre, buttons);
    overlay.append(panel);
    document.body.append(overlay);
}


export async function showRedactedDiagnostics(component) {
    try {
        const response = await fetch("/t8-prompt-enhancer/diagnostics", {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
            headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const record = sanitizeDiagnosticSnapshot(await response.json(), component);
        if (!record) {
            window.alert("尚无可用的脱敏执行诊断。请先运行一次节点。");
            return;
        }
        renderDialog(record);
    } catch (_error) {
        window.alert("暂时无法读取脱敏诊断；这不会影响节点执行。请确认 ComfyUI 已完成重启。");
    }
}
