import assert from "node:assert/strict";
import test from "node:test";

import {
    OPENAI_PROVIDER_STATE_PROPERTY,
    bindOpenAIProviderPersistence,
    restoreOpenAIProviderState,
    serializeOpenAIProviderState,
    serializedOpenAIProviderState,
    expandNamedWidgetValues,
    namedWidgetValueMap,
    namedWidgetValueMapByDiscriminator,
    remapNamedWidgetValues,
    restoreNamedWidgetValues,
    serializeNamedWidgetValues,
} from "../../web/js/widget_state.mjs";


function fakeInput(value = "") {
    const listeners = new Map();
    return {
        value,
        addEventListener(name, callback) {
            listeners.set(name, callback);
        },
        emit(name) {
            listeners.get(name)?.();
        },
    };
}


test("hidden custom model and base URL survive configure/serialize cycles", () => {
    const names = ["api_mode", "custom_model", "openai_base_url", "seed"];
    const saved = ["OpenAI兼容接口（备用）", "k3", "https://api.kimi.com/coding/", 42];
    const restored = namedWidgetValueMap(names, saved);
    const node = {
        widgets: names.map((name) => ({ name, value: name === "custom_model" ? "" : null, hidden: true })),
    };
    restoreNamedWidgetValues(node, restored);
    assert.equal(node.widgets.find((widget) => widget.name === "custom_model").value, "k3");
    assert.deepEqual(serializeNamedWidgetValues(node, names), saved);
});


test("unblurred OpenAI fields are committed from the live DOM before run and reload", () => {
    const baseInput = fakeInput(" https://provider.test/v1 ");
    const modelInput = fakeInput(" vendor/vision-model ");
    const base = { name: "openai_base_url", value: "", inputEl: baseInput };
    const model = { name: "custom_model", value: "", inputEl: modelInput };
    const node = { widgets: [base, model], properties: {} };

    bindOpenAIProviderPersistence(node, base, model);
    node.t8CommitOpenAIProviderState();
    assert.equal(base.value, "https://provider.test/v1");
    assert.equal(model.value, "vendor/vision-model");

    const serialized = {};
    serializeOpenAIProviderState(node, serialized, base, model);
    assert.deepEqual(serialized.properties[OPENAI_PROVIDER_STATE_PROPERTY], {
        base_url: "https://provider.test/v1",
        model_id: "vendor/vision-model",
    });

    const restoredBase = { name: "openai_base_url", value: "", inputEl: fakeInput() };
    const restoredModel = { name: "custom_model", value: "", inputEl: fakeInput() };
    const restoredNode = { widgets: [restoredBase, restoredModel], properties: {} };
    restoreOpenAIProviderState(restoredNode, serializedOpenAIProviderState(serialized));
    assert.equal(restoredBase.value, "https://provider.test/v1");
    assert.equal(restoredBase.inputEl.value, "https://provider.test/v1");
    assert.equal(restoredModel.value, "vendor/vision-model");
    assert.equal(restoredModel.inputEl.value, "vendor/vision-model");
});


test("clearing a live OpenAI field replaces stale saved state", () => {
    const base = { name: "openai_base_url", value: "https://old.test/v1", inputEl: fakeInput("https://old.test/v1") };
    const model = { name: "custom_model", value: "old/model", inputEl: fakeInput("old/model") };
    const node = { widgets: [base, model], properties: {} };
    bindOpenAIProviderPersistence(node, base, model);
    model.inputEl.value = "";
    model.inputEl.emit("input");
    assert.equal(model.value, "");
    assert.equal(node.properties[OPENAI_PROVIDER_STATE_PROPERTY].model_id, "");
});


test("legacy prefix restores named values without shifting appended defaults", () => {
    const names = ["prompt", "api_mode", "custom_model", "local_model"];
    const restored = namedWidgetValueMap(names, ["idea", "OpenAI", "visual-model"], [3, 4]);
    const node = {
        widgets: names.map((name) => ({ name, value: name === "local_model" ? "default.gguf" : "" })),
    };
    restoreNamedWidgetValues(node, restored);
    assert.equal(node.widgets[2].value, "visual-model");
    assert.equal(node.widgets[3].value, "default.gguf");
});


test("legacy workflow is padded before ComfyUI validates appended local Qwen widgets", () => {
    const names = ["prompt", "seed", "control_after_generate", "local_model", "local_context_size"];
    const expanded = expandNamedWidgetValues(
        names,
        ["idea", 42, "randomize"],
        { local_model: "Qwen3.8-27B-Q4_K_M.gguf", local_context_size: 32768 },
        [3, 5],
    );
    assert.deepEqual(expanded, ["idea", 42, "randomize", "Qwen3.8-27B-Q4_K_M.gguf", 32768]);
});


test("excluded legacy field is not restored", () => {
    const names = ["openai_video_urls", "custom_model"];
    const node = { widgets: names.map((name) => ({ name, value: "safe" })) };
    restoreNamedWidgetValues(
        node,
        namedWidgetValueMap(names, ["legacy-upload-button", "model-id"]),
        new Set(["openai_video_urls"]),
    );
    assert.equal(node.widgets[0].value, "safe");
    assert.equal(node.widgets[1].value, "model-id");
});


test("Seedance published order remaps custom length before ComfyUI INT validation", () => {
    const published = ["prompt", "custom_length_target", "api_mode", "seed", "control_after_generate"];
    const runtime = ["prompt", "api_mode", "custom_length_target", "seed", "control_after_generate"];
    const saved = ["idea", 0, "本地 Qwen3.8-27B（GGUF，离线）", 42, "randomize"];
    const mapped = namedWidgetValueMapByDiscriminator(
        saved,
        [runtime, published],
        "api_mode",
        ["本地 Qwen3.8-27B（GGUF，离线）"],
    );
    const remapped = remapNamedWidgetValues(runtime, mapped, {}, saved);
    assert.equal(remapped[1], "本地 Qwen3.8-27B（GGUF，离线）");
    assert.equal(remapped[2], 0);
    assert.equal(remapped[4], "randomize");
});
