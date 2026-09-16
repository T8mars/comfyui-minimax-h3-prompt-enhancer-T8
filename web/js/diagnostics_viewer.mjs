const SAFE_STAGE_KEYS = new Set(["stage", "duration_ms", "attempts", "asset_count", "cache_hit"]);
const QUALITY_CODES = new Set("empty_prompt h3_missing_core_fields h3_field_order h3_missing_first_shot shot_sequence shot_count_mismatch h3_shot_timecode non_monotonic_timecodes duration_budget h3_alignment h3_unexpected_prefix h3_unavailable_asset h3_undefined_reference h3_retention_marker h3_duplicate_definition h3_retention_missing h3_vocal_language h3_missing_speaker h3_speaker_identity semantic_exact_text_missing h3_extra_dialogue h3_visible_text_changed h3_dialogue_source_changed h3_vocal_wrong_layer h3_diegetic_music_layer h3_descriptive_language relay_invalid_authoring seedance_h3_protocol_leak".split(" "));
export function sanitizeQualityMetadata(value) {
    if (!value || typeof value !== "object") return undefined;
    const result = {};
    if (["checked", "corrected", "candidate_rejected", "correction_failed_draft_kept", "budget_exhausted_draft_kept", "protocol_repair_failed_draft_kept", "check_failed_draft_kept", "cleanup_failed_draft_kept"].includes(value.result)) result.result = value.result;
    if (["保持原样 / Off", "质量检查 / Check", "质量纠正（最多追加1次） / Repair"].includes(value.quality_mode)) result.quality_mode = value.quality_mode;
    if ([0, 1].includes(value.correction_calls)) result.correction_calls = value.correction_calls;
    if (Number.isInteger(value.protocol_edits) && value.protocol_edits >= 0 && value.protocol_edits <= 3) result.protocol_edits = value.protocol_edits;
    if (Array.isArray(value.issue_codes)) result.issue_codes = [...new Set(value.issue_codes.filter((s) => QUALITY_CODES.has(s)))];
    if (Array.isArray(value.unchecked)) result.unchecked = value.unchecked.filter((s) => ["physical_plausibility", "rendered_video_quality", "semantic_ownership_wait_and_ending", "descriptive_language", "alignment_duration", "shot_count", "relay_compilation", "relay_semantic_equivalence", "contract_check", "vocal_language"].includes(s));
    return result.result || result.quality_mode ? result : undefined;
}


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
            const quality = sanitizeQualityMetadata(stage.quality_metadata);
            if (quality) safe.quality_metadata = quality;
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
    notice.textContent = "仅包含节点、渠道、阶段、耗时、尝试次数、素材数量、缓存状态、安全错误类别及质量检查代码。unchecked为未验证项，不等于通过。";
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
