import assert from "node:assert/strict";
import test from "node:test";

import {
    NORMAL_ACTION,
    RECOVERY_SLOT_PROPERTY,
    RESTORE_ACTION,
    ensureUniqueSlot,
    restoreCompletionResult,
} from "../../web/js/completion_recovery_core.mjs";


function fixture(slot = "t8-recovery-test-slot-0001") {
    const slotWidget = { name: "recovery_slot", value: slot };
    const actionWidget = { name: "recovery_action", value: NORMAL_ACTION };
    const node = {
        id: 42,
        widgets: [slotWidget, actionWidget],
        properties: { [RECOVERY_SLOT_PROPERTY]: slot },
        graph: { _nodes: [], changeCount: 0, change() { this.changeCount += 1; } },
        dirtyCalls: [],
        setDirtyCanvas(...args) { this.dirtyCalls.push(args); },
    };
    node.graph._nodes = [node];
    return { node, slotWidget, actionWidget };
}


test("complete recovery performs one GET status check and queues only this node", async () => {
    const { node, slotWidget, actionWidget } = fixture();
    const fetchCalls = [];
    const queueCalls = [];
    const actionSeenByQueue = [];
    let beforeQueueCalls = 0;
    const result = await restoreCompletionResult({
        node,
        component: "MiniMaxH3PromptEnhancerT8",
        slotWidget,
        actionWidget,
        beforeQueue: () => { beforeQueueCalls += 1; },
        fetchFn: async (...args) => {
            fetchCalls.push(args);
            return { ok: true, status: 200, async json() { return { state: "completed", recoverable: true }; } };
        },
        alertFn: () => assert.fail("recoverable result must not alert"),
        queuePrompt: async (...args) => {
            actionSeenByQueue.push(actionWidget.value);
            queueCalls.push(args);
        },
    });

    assert.equal(result.queued, true);
    assert.equal(fetchCalls.length, 1);
    assert.match(fetchCalls[0][0], /^\/t8-prompt-enhancer\/completion-recovery\/MiniMaxH3PromptEnhancerT8\//);
    assert.deepEqual(fetchCalls[0][1], { cache: "no-store", headers: { Accept: "application/json" } });
    assert.equal("method" in fetchCalls[0][1], false);
    assert.equal(beforeQueueCalls, 1);
    assert.deepEqual(queueCalls, [[0, 1, ["42"]]]);
    assert.deepEqual(actionSeenByQueue, [RESTORE_ACTION]);
    assert.equal(actionWidget.value, NORMAL_ACTION);
    assert.deepEqual(node.dirtyCalls, [[true, true]]);
});


test("partial recovery warns and never queues a provider run", async () => {
    const { node, slotWidget, actionWidget } = fixture();
    const alerts = [];
    let queueCalls = 0;
    const result = await restoreCompletionResult({
        node,
        component: "Seedance20PromptEnhancerT8",
        slotWidget,
        actionWidget,
        fetchFn: async () => ({
            ok: true,
            status: 200,
            async json() { return { state: "ambiguous_partial", recoverable: false, partial_chars: 137 }; },
        }),
        alertFn: (message) => alerts.push(message),
        queuePrompt: async () => { queueCalls += 1; },
    });

    assert.equal(result.queued, false);
    assert.equal(queueCalls, 0);
    assert.equal(actionWidget.value, NORMAL_ACTION);
    assert.equal(alerts.length, 1);
    assert.match(alerts[0], /137 个字符/);
    assert.match(alerts[0], /不会重新扣费/);
});


test("status failure resets the action and does not queue", async () => {
    const { node, slotWidget, actionWidget } = fixture();
    actionWidget.value = RESTORE_ACTION;
    const alerts = [];
    let queueCalls = 0;
    const result = await restoreCompletionResult({
        node,
        component: "MiniMaxMusic3PromptEnhancerT8",
        slotWidget,
        actionWidget,
        fetchFn: async () => { throw new Error("offline"); },
        alertFn: (message) => alerts.push(message),
        queuePrompt: async () => { queueCalls += 1; },
    });

    assert.equal(result.queued, false);
    assert.equal(queueCalls, 0);
    assert.equal(actionWidget.value, NORMAL_ACTION);
    assert.deepEqual(alerts, ["恢复检查失败：offline"]);
});


test("copied nodes with duplicate recovery slots receive an independent slot", () => {
    const first = fixture("t8-duplicate-slot-0001");
    const second = fixture("t8-duplicate-slot-0001");
    second.node.id = 43;
    second.node.graph = first.node.graph;
    first.node.graph._nodes = [first.node, second.node];

    const slot = ensureUniqueSlot(second.node, second.slotWidget);
    assert.notEqual(slot, "t8-duplicate-slot-0001");
    assert.equal(second.slotWidget.value, slot);
    assert.equal(second.node.properties[RECOVERY_SLOT_PROPERTY], slot);
    assert.equal(first.node.graph.changeCount, 1);
});
