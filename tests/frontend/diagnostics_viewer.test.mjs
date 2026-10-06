import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeDiagnosticRecord, sanitizeDiagnosticSnapshot, sanitizeQualityMetadata } from "../../web/js/diagnostics_viewer.mjs";

test("Hybrid quality copies finite codes and makes pixel/role unknowns explicit", () => {
    const actual = sanitizeQualityMetadata({ result: "checked", issue_codes: ["h3_hybrid_anchor_roles", "h3_hybrid_anchor_tracking", "PRIVATE_SENTINEL"],
        unchecked: ["hybrid_pixel_and_transition_semantics", "hybrid_resolved_asset_roles", "PRIVATE_SENTINEL"], prompt: "PRIVATE_SENTINEL" });
    assert.deepEqual(actual.issue_codes, ["h3_hybrid_anchor_roles", "h3_hybrid_anchor_tracking"]);
    assert.deepEqual(actual.unchecked, ["hybrid_pixel_and_transition_semantics", "hybrid_resolved_asset_roles"]);
    assert.ok(!JSON.stringify(actual).includes("PRIVATE_SENTINEL"));
});


test("diagnostic UI copies only the explicit allowlist", () => {
    const record = sanitizeDiagnosticRecord({
        component: "MiniMax H3 Prompt Enhancer",
        provider: "OpenAI compatible https://private.example/v1 sk-" + "ABCDEFGHIJKLMNOPQRST",
        outcome: "success",
        duration_ms: 123.6,
        error_category: "network",
        api_key: "must-not-copy",
        prompt: "must-not-copy",
        response: "must-not-copy",
        stages: [{
            stage: "chat",
            duration_ms: 100,
            attempts: 2,
            asset_count: 3,
            cache_hit: true,
            media_url: "must-not-copy",
        }],
    });
    const copied = JSON.stringify(record);
    assert.equal(record.node, "MiniMax H3 Prompt Enhancer");
    assert.equal(record.stages[0].attempts, 2);
    assert.match(record.provider, /\[redacted-url\]/);
    assert.match(record.provider, /\[redacted-key\]/);
    for (const forbidden of ["must-not-copy", "api_key", "prompt", "response", "media_url"]) {
        assert.equal(copied.includes(forbidden), false);
    }
});


test("snapshot selects the latest matching node and falls back safely", () => {
    const snapshot = {
        recent: [
            { component: "Seedance", provider: "one", outcome: "success", stages: [] },
            { component: "Music", provider: "two", outcome: "failed", stages: [] },
        ],
    };
    assert.equal(sanitizeDiagnosticSnapshot(snapshot, "Music").node, "Music");
    assert.equal(sanitizeDiagnosticSnapshot(snapshot, "Missing").node, "Seedance");
    assert.equal(sanitizeDiagnosticSnapshot({ recent: [] }), null);
});
