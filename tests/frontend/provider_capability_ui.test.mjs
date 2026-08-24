import assert from "node:assert/strict";
import test from "node:test";

import { providerCapabilitySummary } from "../../web/js/provider_capability_ui.mjs";


test("unknown OpenAI provider never claims verified visual support", () => {
    const value = providerCapabilitySummary("OpenAI兼容接口（备用）", "https://example.test/v1");
    assert.equal(value.profile, "openai-compatible-unknown");
    assert.match(value.image, /未知/);
    assert.match(value.video_data_url, /未知/);
});


test("Kimi coding profile explains automatic temperature omission", () => {
    const value = providerCapabilitySummary("OpenAI兼容接口（备用）", "https://api.kimi.com/coding/v1");
    assert.equal(value.profile, "kimi-coding-known-parameter-profile");
    assert.match(value.optional_parameters, /省略 temperature/);
});


test("Music preflight is explicit about its text-only node contract", () => {
    const value = providerCapabilitySummary("贞贞平价小屋（推荐）", "", { textOnly: true });
    assert.equal(value.image, "此节点无媒体输入");
    assert.equal(value.video_data_url, "此节点无媒体输入");
});
