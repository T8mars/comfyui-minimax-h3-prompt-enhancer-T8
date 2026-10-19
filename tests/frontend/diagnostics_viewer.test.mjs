import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeDiagnosticRecord, sanitizeDiagnosticSnapshot, sanitizeQualityMetadata } from "../../web/js/diagnostics_viewer.mjs";

test("marker diagnostics are H3-only, finite and never authenticate downstream or semantics", () => {
    assert.deepEqual(sanitizeQualityMetadata({result:"checked",issue_codes:["h3_marker_literal_missing","PRIVATE"]}).issue_codes,["h3_marker_literal_missing"]);
    const marker={revision:"1.0.0",status:"enhancer_reference_matched",picture:2,marker_count:3,relation_count:2,
        warning_codes:["overlap","PRIVATE_MARKER"],downstream_verified:false,semantic_verified:false,coordinates:"PRIVATE_MARKER"};
    const record={component:"MiniMaxH3PromptEnhancerT8",stages:[{stage:"input_validated",creation_metadata:{h3_visual_marker:marker}}]};
    const clean=sanitizeDiagnosticRecord(record);
    assert.deepEqual(clean.stages[0].h3_visual_marker.warning_codes,["overlap"]);
    assert.equal(clean.stages[0].h3_visual_marker.semantic_verified,false);
    assert.doesNotMatch(JSON.stringify(clean),/PRIVATE_MARKER/);
    for(const component of ["MOSSImagePromptEnhancerT8","Seedance20PromptEnhancerT8"]){
        assert.equal(sanitizeDiagnosticRecord({...record,component}).stages[0].h3_visual_marker,undefined);
    }
});

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
