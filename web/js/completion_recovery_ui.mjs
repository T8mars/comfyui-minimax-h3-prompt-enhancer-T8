import { app } from "../../scripts/app.js";
import {
    NORMAL_ACTION,
    ensureUniqueSlot,
    restoreCompletionResult,
} from "./completion_recovery_core.mjs";



function hideInternalWidget(widget) {
    if (!widget) return;
    if (!("t8RecoveryOriginalType" in widget)) {
        widget.t8RecoveryOriginalType = widget.type;
        widget.t8RecoveryOriginalComputeSize = widget.computeSize;
        widget.t8RecoveryOriginalDisplay = widget.element?.style.display || "";
    }
    widget.type = "converted-widget";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
    if (widget.element) {
        widget.element.dataset.shouldHide = "true";
        widget.element.style.display = "none";
        widget.element.hidden = true;
    }
}


export function addCompletionRecoveryButton(node, component, { beforeQueue = null } = {}) {
    const slotWidget = node.widgets?.find((widget) => widget.name === "recovery_slot");
    const actionWidget = node.widgets?.find((widget) => widget.name === "recovery_action");
    if (!slotWidget || !actionWidget) return null;
    hideInternalWidget(slotWidget);
    hideInternalWidget(actionWidget);
    actionWidget.value = NORMAL_ACTION;
    ensureUniqueSlot(node, slotWidget);

    let recovering = false;
    const button = node.addWidget(
        "button",
        "🔄 恢复上次云端结果（不重新生成）",
        "只读取当前 ComfyUI 进程中的完整检查点；不会发送新的付费请求",
        async () => {
            if (recovering) return;
            recovering = true;
            try {
                await restoreCompletionResult({
                    node,
                    component,
                    slotWidget,
                    actionWidget,
                    beforeQueue,
                    fetchFn: (...args) => globalThis.fetch(...args),
                    alertFn: (message) => window.alert(message),
                    queuePrompt: (...args) => app.queuePrompt(...args),
                });
            } finally {
                recovering = false;
            }
        },
        { serialize: false },
    );
    button.serializeValue = () => undefined;
    node.t8EnsureRecoverySlot = () => ensureUniqueSlot(node, slotWidget);
    return button;
}
