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
        return "已找到完整的本地结果检查点。恢复只读取内存，不会调用云端或再次扣费。";
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
