import assert from "node:assert/strict";
import test from "node:test";

import {
    contractStatusView,
    estimateStatusCardHeight,
    parseStatusMessage,
    routerStatusView,
} from "../../web/js/film_workflow_status.mjs";


test("status parser accepts ComfyUI arrays and rejects malformed JSON", () => {
    assert.deepEqual(
        parseStatusMessage({ state: ["{\"contract_valid\":true}"] }, "state"),
        { contract_valid: true },
    );
    assert.equal(parseStatusMessage({ state: ["not-json"] }, "state"), null);
    assert.equal(parseStatusMessage({}, "state"), null);
});


test("adaptive status-card height expands for wrapped multi-line diagnostics", () => {
    assert.equal(estimateStatusCardHeight("short", 84, 180), 84);
    const expanded = estimateStatusCardHeight(
        "line one\n" + "很长的协议诊断字段".repeat(12) + "\nline three\nline four",
        84,
        180,
    );
    assert.ok(expanded > 84);
    assert.ok(expanded <= 180);
});


test("router view exposes selective clears without hiding invalidation", () => {
    const view = routerStatusView({
        revision: 2,
        source: "direct_state",
        target_stage: "08-prompt",
        invalidated_stages: ["08-prompt"],
        confirmed_invalidated_stages: ["08-prompt"],
        cleared_inherited_fields: ["rules"],
    });
    assert.match(view.text, /已失效下游：08-prompt/);
    assert.match(view.text, /已清空上一版字段：世界硬规则/);
    assert.equal(view.borderColor, "#ef4444");

    const english = routerStatusView({
        revision: 2,
        source: "direct_state",
        target_stage: "08-prompt",
        invalidated_stages: ["08-prompt"],
        cleared_inherited_fields: ["rules"],
    }, "en-US");
    assert.match(english.text, /Invalidated downstream: 08-prompt/);
    assert.match(english.text, /Cleared inherited fields: world rules/);
});


test("contract view distinguishes valid and invalid non-empty responses", () => {
    const valid = contractStatusView({
        operation: "long_form_planning",
        contract_valid: true,
        provider: "local-qwen",
        expected_item_count: 2,
        received_item_count: 2,
    });
    assert.match(valid.text, /校验通过/);
    assert.match(valid.text, /2\/2/);
    assert.equal(valid.borderColor, "#22c55e");

    const invalid = contractStatusView({
        operation: "storyboard_planning",
        contract_valid: false,
        provider: "openai-compatible",
        validation_error_count: 2,
        validation_error_codes: ["shot_count_mismatch", "timeline_duration_mismatch"],
        expected_item_count: 4,
        received_item_count: 1,
    });
    assert.match(invalid.text, /校验失败/);
    assert.match(invalid.text, /shot_count_mismatch/);
    assert.match(invalid.text, /validation_errors/);
    assert.equal(invalid.borderColor, "#ef4444");

    const blockedEnglish = contractStatusView({
        operation: "storyboard_planning",
        contract_valid: false,
        provider: "local-qwen",
        validation_error_count: 1,
        validation_error_codes: ["shot_count_mismatch"],
        downstream_blocked: true,
    }, "en");
    assert.match(blockedEnglish.text, /Storyboard delivery contract failed/);
    assert.match(blockedEnglish.text, /Downstream execution was blocked/);
});
