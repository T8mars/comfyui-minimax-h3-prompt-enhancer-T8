import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFile } from "node:fs/promises";
import * as speech from "../../web/js/speech_reference_ui.mjs";
import { recoveryMessage } from "../../web/js/completion_recovery_core.mjs";

function node(order = speech.SPEECH_NAMES) {
    const defaults = { mode: "Enabled", source_mode: "Provided text", purpose: "reference",
        provided_text: "字幕原词 <script>not HTML</script>", provided_format: "auto", speaker_map_json: "{}",
        partial_policy: "reject", failure_policy: "stop", start_s: 0, duration_s: 0,
        language: "Auto", context: "", audio_track: 0, channel: "mean", offset_ms: 0, timeout_s: 1800 };
    return { widgets: order.map(name => ({ name, value: defaults[name] ?? "test", type: "text" })),
        size: [440, 300], properties: {}, inputs: [], setDirtyCanvas() {},
        setSize(size) { this.size = size; }, computeSize() { return [440, this.widgets.filter(w => !w.hidden).length * 24]; },
        addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options }; this.widgets.push(w); return w; } };
}

test("new helper serializes stable named schema only, restores reordered runtime synchronously", () => {
    const n = node(); n.addWidget("button", "nonserialized", "host-action", () => {}, { serialize: false });
    const data = {}; speech.serializeSpeech(n, data);
    assert.equal(data.widgets_values.length, speech.SPEECH_NAMES.length);
    assert.equal(data.widgets_values.includes("host-action"), false);
    const next = node([...speech.SPEECH_NAMES].reverse());
    speech.configureSpeech(next, data, function(d) { d.widgets_values.forEach((v, i) => { this.widgets[i].value = v; }); }, [data]);
    for (const name of speech.SPEECH_NAMES) assert.equal(next.widgets.find(w => w.name === name).value, n.widgets.find(w => w.name === name).value);
});

test("both independent speech workflows reload the actual 16 named fields without action tails", async () => {
    for (const target of ["h3", "seedance20"]) {
        const graph = JSON.parse(await readFile(new URL(`../../example_workflows/speech_reference_${target}.json`, import.meta.url), "utf8"));
        const helper = graph.nodes.find(n => n.type === "T8SpeechReference");
        const n = node([...speech.SPEECH_NAMES].reverse());
        speech.configureSpeech(n, helper, function(d) { d.widgets_values.forEach((v, i) => { this.widgets[i].value = v; }); }, [helper]);
        const saved = {}; speech.serializeSpeech(n, saved);
        assert.deepEqual(saved.widgets_values, helper.widgets_values);
        assert.equal(saved.widgets_values_named.provided_text.includes("等我回来。"), true);
        assert.equal(saved.widgets_values_named.purpose, "keep_dialogue");
        assert.equal(saved.widgets_values_named.speaker_map_json, target === "h3" ? '{"default":"<Subject 1> / S1"}' : '{"default":"讲解者"}');
    }
});

test("empty or corrupted named metadata cannot erase a valid saved positional layout", async () => {
    const graph = JSON.parse(await readFile(new URL("../../example_workflows/speech_reference_h3.json", import.meta.url), "utf8"));
    const original = graph.nodes.find(n => n.type === "T8SpeechReference");
    for (const metadata of [
        { widgets_values_named: {} },
        { properties: { t8_speech_widgets_v1: {} }, widgets_values_named: original.widgets_values_named },
        { properties: { t8_speech_widgets_v1: { mode: "bogus", provided_text: { not: "text" } } }, widgets_values_named: {} },
    ]) {
        const n = node([...speech.SPEECH_NAMES].reverse());
        const data = { widgets_values: original.widgets_values, ...metadata };
        speech.configureSpeech(n, data, function(d) { d.widgets_values.forEach((v, i) => { this.widgets[i].value = v; }); }, [data]);
        for (const [i, name] of speech.SPEECH_NAMES.entries()) assert.equal(n.widgets.find(w => w.name === name).value, original.widgets_values[i], name);
    }
});

test("omitted linked text always saves a null placeholder and legacy 15 fields migrate only by validated layout", async () => {
    const graph = JSON.parse(await readFile(new URL("../../example_workflows/speech_reference_h3.json", import.meta.url), "utf8"));
    const original = graph.nodes.find(n => n.type === "T8SpeechReference");
    const n = node(); n.inputs = [{ name: "provided_text", link: 99 }];
    speech.configureSpeech(n, original, null, [original]);
    n.widgets = n.widgets.filter(w => w.name !== "provided_text");
    const saved = {}; speech.serializeSpeech(n, saved);
    assert.equal(saved.widgets_values.length, 16); assert.equal(saved.widgets_values[3], null);
    for (const raw of [saved.widgets_values, [...saved.widgets_values.slice(0, 3), ...saved.widgets_values.slice(4)],
        [...saved.widgets_values.slice(0, 3), ...saved.widgets_values.slice(4), "host-button-tail"]]) {
        const host = node([...speech.SPEECH_NAMES].reverse()); host.inputs = n.inputs;
        const markerStripped = { widgets_values: raw };
        speech.configureSpeech(host, markerStripped, function(d) { d.widgets_values.forEach((v, i) => { this.widgets[i].value = v; }); }, [markerStripped]);
        for (const [i, name] of speech.SPEECH_NAMES.entries()) assert.equal(host.widgets.find(w => w.name === name).value, saved.widgets_values[i], name);
    }
    const unlinked = node(); const before = unlinked.widgets.map(w => w.value);
    speech.configureSpeech(unlinked, { widgets_values: ["Enabled", "AUDIO", "broken-short"] }, null, [{}]);
    assert.deepEqual(unlinked.widgets.map(w => w.value), before);
});

test("advanced and source switches retain values without accumulated height", () => {
    const n = node(); speech.refreshSpeech(n); const collapsed = n.size[1];
    for (let i = 0; i < 10; i++) { n.t8SpeechAdvanced = true; speech.refreshSpeech(n); n.t8SpeechAdvanced = false; speech.refreshSpeech(n); }
    assert.equal(n.size[1], collapsed);
    const before = n.widgets.find(w => w.name === "provided_text").value;
    n.widgets.find(w => w.name === "source_mode").value = "AUDIO"; speech.refreshSpeech(n);
    assert.equal(n.widgets.find(w => w.name === "provided_text").hidden, true);
    n.widgets.find(w => w.name === "source_mode").value = "Provided text"; speech.refreshSpeech(n);
    assert.equal(n.widgets.find(w => w.name === "provided_text").value, before);
});

test("inactive ASR controls are hidden, retained and reappear only for an automatic source", () => {
    const n = node(); n.t8SpeechAdvanced = true;
    const savedOffset = n.widgets.find(w => w.name === "offset_ms").value;
    speech.refreshSpeech(n);
    for (const name of ["offset_ms", "context", "channel", "timeout_s", "failure_policy"])
        assert.equal(n.widgets.find(w => w.name === name).hidden, true, name);
    n.widgets.find(w => w.name === "source_mode").value = "AUDIO"; speech.refreshSpeech(n);
    assert.equal(n.widgets.find(w => w.name === "offset_ms").hidden, undefined);
    assert.equal(n.widgets.find(w => w.name === "offset_ms").value, savedOffset);
    assert.equal(n.widgets.find(w => w.name === "provided_format").hidden, true);
});

test("read-only connection follows reroute and never forwards cloud credentials or prompts", () => {
    const cfg = { widgets: [{ name: "provider", value: "Strata" }, { name: "strata_url", value: "http://127.0.0.1:9999" },
        { name: "api_key", value: "PRIVATE" }, { name: "custom_model", value: "PRIVATE" }] };
    const reroute = { type: "Reroute", inputs: [{ link: 1 }] };
    const n = node(); n.inputs = [{ name: "provider_config", link: 2 }];
    n.graph = { links: new Map([[1, { origin_id: 1 }], [2, { origin_id: 2 }]]), getNodeById: id => id === 1 ? cfg : reroute };
    assert.deepEqual(speech.speechConnectionValues(n), { strata_url: "http://127.0.0.1:9999" });
    cfg.widgets[0].value = "Local Qwen";
    assert.throws(() => speech.speechConnectionValues(n), /Strata/);
    assert.match(speech.speechStatusText({ connected: true, supported: true, device: "cpu", cpu_guard: false }), /缺失/);
});

test("read-only readiness cannot call CUDA or an unguarded service ready for CPU speech", () => {
    for (const value of [{ device: "cuda", cpu_guard: true }, { device: "cpu", cpu_guard: false }]) {
        const message = speech.speechStatusText({ connected: true, supported: true, ...value });
        assert.doesNotMatch(message, /就绪 \/ Ready/);
    }
    assert.match(speech.speechStatusText({ connected: true, supported: true, device: "cuda", cpu_guard: true }), /CPU/);
    assert.match(speech.speechStatusText({ connected: true, supported: true, device: "cpu", cpu_guard: true }), /就绪 \/ Ready/);
});

test("actual helper extension actions are nonserializable and initialization is idempotent", async () => {
    let extension; const frames = [], seen = [];
    const context = vm.createContext({ ...speech, app: { registerExtension(e) { extension = e; } },
        api: { fetchApi: async (url, options) => { seen.push({ url, options }); return { json: async () => ({ connected: true, supported: true, device: "cpu", cpu_guard: true }) }; } },
        window: { alert() {} }, requestAnimationFrame(fn) { frames.push(fn); } });
    const source = (await readFile(new URL("../../web/js/speech_reference.js", import.meta.url), "utf8"))
        .replace(/^import[\s\S]*?from\s+"[^"]+";\s*/gm, "");
    vm.runInContext(source, context);
    class N { constructor() { Object.assign(this, node()); } }
    await extension.beforeRegisterNodeDef(N, { name: "T8SpeechReference" });
    const n = new N(); n.onNodeCreated(); const count = n.widgets.length; n.onNodeCreated();
    assert.equal(n.widgets.length, count);
    const actions = n.widgets.filter(w => w.type === "button");
    assert.equal(actions.length, 4);
    for (const w of actions) { assert.equal(w.options.serialize, false); assert.equal(w.serializeValue(), undefined); }
    await actions[1].callback(); assert.equal(seen.length, 1);
    assert.equal(seen[0].url, "/t8-prompt-enhancer/speech/capabilities");
    const saved = {}; n.onSerialize(saved);
    assert.equal(saved.widgets_values.length, speech.SPEECH_NAMES.length);
    n.onConfigure(saved); while (frames.length) frames.shift()();
    assert.equal(n.widgets.find(w => w.name === "provided_text").value.includes("<script>"), true);
});

test("a delayed capability response cannot describe a changed source or removed helper", async () => {
    let extension, respond; const alerts = [];
    const context = vm.createContext({ ...speech, app: { registerExtension(e) { extension = e; } },
        api: { fetchApi: () => new Promise(resolve => { respond = resolve; }) },
        window: { alert(value) { alerts.push(value); } }, requestAnimationFrame() {} });
    const source = (await readFile(new URL("../../web/js/speech_reference.js", import.meta.url), "utf8"))
        .replace(/^import[\s\S]*?from\s+"[^"]+";\s*/gm, "");
    vm.runInContext(source, context);
    class N { constructor() { Object.assign(this, node()); } }
    await extension.beforeRegisterNodeDef(N, { name: "T8SpeechReference" });
    for (const change of [n => { n.widgets.find(w => w.name === "source_mode").value = "AUDIO"; }, n => n.onRemoved()]) {
        const n = new N(); n.onNodeCreated();
        const pending = n.widgets.filter(w => w.type === "button")[1].callback();
        change(n); respond({ json: async () => ({ connected: true, supported: true, device: "cpu", cpu_guard: true }) });
        await pending; assert.equal(alerts.length, 0);
    }
});

test("recovery names only the cached finite speech choice and never source text or model paths", () => {
    const value = { schema_version: "t8-speech-reference/v1", purpose: "keep_dialogue", cue_count: 3,
        text: "PRIVATE WORDS", path: "PRIVATE PATH", speaker_map: { default: "PRIVATE ROLE" } };
    const message = recoveryMessage({ recoverable: true, creation_metadata: { speech_reference: value } });
    assert.match(message, /不重新识别/); assert.match(message, /3 条/); assert.doesNotMatch(message, /PRIVATE/);
    const invalid = recoveryMessage({ recoverable: true, creation_metadata: { speech_reference: { ...value, cue_count: true } } });
    assert.doesNotMatch(invalid, /原语音参考/);
});
