export const NORMAL_ACTION = "normal";
export const RESTORE_ACTION = "restore_last";
export const RECOVERY_SLOT_PROPERTY = "t8_completion_recovery_slot";


export function newRecoverySlot() {
    const uuid = globalThis.crypto?.randomUUID?.();
    if (uuid) return `t8-${uuid}`;
    return `t8-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}


export function ensureUniqueSlot(node, slotWidget) {
    if (!slotWidget) return "";
    let slot = String(
        node.properties?.[RECOVERY_SLOT_PROPERTY]
        || slotWidget.value
        || "",
    ).trim();
    const duplicates = (node.graph?._nodes || []).some((other) => {
        if (other === node) return false;
        const otherSlot = other.widgets?.find((widget) => widget.name === "recovery_slot");
        const otherValue = other.properties?.[RECOVERY_SLOT_PROPERTY] || otherSlot?.value || "";
        return slot && String(otherValue).trim() === slot;
    });
    if (!slot || duplicates) {
        slot = newRecoverySlot();
        node.graph?.change?.();
    }
    slotWidget.value = slot;
    if (!node.properties || typeof node.properties !== "object" || Array.isArray(node.properties)) {
        node.properties = {};
    }
    node.properties[RECOVERY_SLOT_PROPERTY] = slot;
    return slot;
}


export function recoveryMessage(status) {
    if (status.recoverable) {
        const meta = status.creation_metadata;
        const provenance = meta?.director_skill
            ? `\n原结果来源 / Original result: ${meta.director_skill} v${meta.director_revision || "?"}${meta.authoring_revision ? ` · Authoring v${meta.authoring_revision}` : ""} · ${meta.output_language || "?"} · ${meta.output_mode || "?"}。恢复的是原稿，不是按当前 Skill 重新创作。`
            : "";
        return "已找到完整的本地结果检查点。恢复只读取内存，不会调用云端或再次扣费。" + provenance + cameraSelectionMessage(meta) + emotionSelectionMessage(meta) + hybridSelectionMessage(meta) + speechSelectionMessage(meta) + storyboardSelectionMessage(meta) + visualMarkerSelectionMessage(meta) + visualStyleSelectionMessage(meta);
    }
    if (status.state === "ambiguous_partial") {
        return `上次请求返回途中断开，只收到 ${status.partial_chars || 0} 个字符；为防止把截断提示词当成完整结果，节点不会自动输出这段内容，也不会重新扣费。`;
    }
    if (status.state === "ambiguous_no_checkpoint") {
        return "上游可能已经完成，但没有任何响应字节到达 ComfyUI。当前服务没有按 Chat Completion ID 查询结果的接口，因此无法安全取回，也不会偷偷重新提交付费请求。";
    }
    if (status.state === "failed") {
        return "上次执行失败，且没有完整结果检查点可恢复。";
    }
    if (status.state === "unavailable_oversize") {
        return "上次执行已成功，但完整输出超过内存恢复安全上限；原节点输出不受影响，本次不提供恢复缓存。";
    }
    if (status.state === "streaming" || status.state === "stream_complete" || status.state === "started") {
        return "上次请求仍处于本地记录的处理中状态，请稍后再点。";
    }
    return "当前 ComfyUI 进程中还没有这个节点的完整结果。先正常运行一次；重启 ComfyUI 会清空恢复缓存。";
}


export async function restoreCompletionResult({
    node,
    component,
    slotWidget,
    actionWidget,
    beforeQueue = null,
    fetchFn,
    alertFn,
    queuePrompt,
}) {
    const slot = ensureUniqueSlot(node, slotWidget);
    try {
        if (typeof fetchFn !== "function" || typeof queuePrompt !== "function") {
            throw new Error("恢复运行环境不可用");
        }
        const response = await fetchFn(
            `/t8-prompt-enhancer/completion-recovery/${encodeURIComponent(component)}/${encodeURIComponent(slot)}`,
            { cache: "no-store", headers: { Accept: "application/json" } },
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const status = await response.json();
        if (!status.recoverable) {
            alertFn?.(recoveryMessage(status));
            return { queued: false, status };
        }
        if (status.creation_metadata?.director_skill || cameraSelectionMessage(status.creation_metadata) || emotionSelectionMessage(status.creation_metadata) || hybridSelectionMessage(status.creation_metadata) || speechSelectionMessage(status.creation_metadata) || storyboardSelectionMessage(status.creation_metadata) || visualMarkerSelectionMessage(status.creation_metadata) || visualStyleSelectionMessage(status.creation_metadata)) alertFn?.(recoveryMessage(status));
        beforeQueue?.();
        actionWidget.value = RESTORE_ACTION;
        await queuePrompt(0, 1, [String(node.id)]);
        return { queued: true, status };
    } catch (error) {
        alertFn?.(`恢复检查失败：${error?.message || error}`);
        return { queued: false, error };
    } finally {
        actionWidget.value = NORMAL_ACTION;
        node.setDirtyCanvas?.(true, true);
    }
}

export function visualStyleSelectionMessage(meta) {
    let text = "";
    for (const kind of ["color", "creator"]) {
        const block = meta?.[kind + "_style"];
        const keys = ["style_id", "resource_revision", "resource_sha256", "adapter_revision", ...(kind === "color" ? ["scope"] : [])];
        if (!block || typeof block !== "object" || Array.isArray(block) || Object.keys(block).length !== keys.length
            || !keys.every(k => typeof block[k] === "string")
            || !/^(?:00[1-9]|0[1-9][0-9]|1[0-9]{2}|200)$/.test(block.style_id)
            || block.resource_revision !== "1.0.0" || block.adapter_revision !== "1.0.0"
            || !/^[0-9a-f]{64}$/.test(block.resource_sha256)
            || (kind === "color" && !["color_only", "color_and_light"].includes(block.scope))) continue;
        text += "\n上次风格选择 / Previous " + kind + " selection: #" + block.style_id + " v" + block.resource_revision
            + (kind === "color" ? " · " + block.scope : "") + "。恢复原稿，不应用当前选择；记录不代表语义或成片效果验收。";
    }
    return text;
}

function visualMarkerSelectionMessage(meta) {
    const m = meta?.h3_visual_marker;
    if (m?.revision !== "1.0.0" || m.status !== "enhancer_reference_matched"
        || !Number.isInteger(m.picture) || m.picture < 1 || m.picture > 11
        || !Number.isInteger(m.marker_count) || m.marker_count < 2 || m.marker_count > 64
        || !Number.isInteger(m.relation_count) || m.relation_count < 1 || m.relation_count > 128
        || m.downstream_verified !== false || m.semantic_verified !== false) return "";
    return `\n上次 H3 空间标记 / Previous visual marker: v1.0.0 · Picture ${m.picture} · ${m.marker_count} markers · ${m.relation_count} relations。仅验证增强器附件，未认证下游绑定、角色语义或成片；恢复原稿，不套用今天的标记配置。`;
}

function cameraSelectionMessage(meta) {
    if (!["auto", "strong"].includes(meta?.combat_camera_mode)
        || !["follow", "prefer_continuous"].includes(meta?.combat_camera_continuity)
        || !["natural", "stylized"].includes(meta?.combat_camera_impact)) return "";
    const mode = { auto: "AUTO", strong: "强化 / Strong" }[meta?.combat_camera_mode];
    const continuity = { follow: "沿用原设定 / Follow", prefer_continuous: "偏好连续 / Prefer continuous" }[meta?.combat_camera_continuity];
    const impact = { natural: "写实 / Natural", stylized: "风格化 / Stylized" }[meta?.combat_camera_impact];
    if (!mode || !continuity || !impact || meta?.combat_camera_revision !== "1.0.0") return "";
    return `\n上次战斗运镜选择 / Previous camera selection: ${mode} · ${continuity} · ${impact}。恢复原稿，不按当前配置重新生成；选择记录不代表效果验收。`;
}

function emotionSelectionMessage(meta) {
    if (meta?.emotion_strategy !== "tudou_emotion" || meta?.emotion_revision !== "1.0.0") return "";
    return "\n上次情绪策略 / Previous emotion strategy: 土豆-情绪演绎 v1.0.0。恢复原稿，不按当前模式重新生成；选择记录不代表成片效果验收。";
}

function storyboardSelectionMessage(meta) {
    if (meta?.storyboard_strategy !== "v20_storyboard" || meta?.storyboard_revision !== "1.0.0") return "";
    return "\n上次分镜策略 / Previous storyboard strategy: 分镜强化（实验） v1.0.0。恢复原稿，不套用当前开关；仅记录方法，不代表分镜或成片已通过验收。";
}

function hybridSelectionMessage(meta) {
    if (meta?.h3_task !== "Hybrid" || meta?.h3_family !== "reference_six" || meta?.hybrid_revision !== "1.0.0"
        || !Number.isInteger(meta?.hybrid_picture_count) || meta.hybrid_picture_count < 1 || meta.hybrid_picture_count > 11
        || !Number.isInteger(meta?.hybrid_video_count) || meta.hybrid_video_count < 0 || meta.hybrid_video_count > 3) return "";
    return `\n原结果模式 / Original task: Hybrid · 六段参考格式 / Six fields · ${meta.hybrid_picture_count} images / ${meta.hybrid_video_count} videos。恢复原稿，不按当前模式重新生成；非成片效果验收。`;
}

function speechSelectionMessage(meta) {
    const speech = meta?.speech_reference;
    if (speech?.schema_version !== "t8-speech-reference/v1" || !["reference", "keep_dialogue"].includes(speech.purpose)
        || !Number.isInteger(speech.cue_count) || speech.cue_count < 0 || speech.cue_count > 10000) return "";
    return `\n原语音参考 / Original speech: ${speech.purpose === "keep_dialogue" ? "用户指派保留对白" : "仅参考理解"} · ${speech.cue_count} 条段级语句。恢复原稿，不重新识别，也不套用当前字幕或角色映射。`;
}
