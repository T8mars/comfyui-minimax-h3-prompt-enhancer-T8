import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import * as core from "../../web/js/moss_authoring_ui.mjs";
import { RECOVERY_SLOT_PROPERTY } from "../../web/js/completion_recovery_core.mjs";

const widget = (node, name) => node.widgets.find(item => item.name === name);
function fixture() {
    return { ...core.DIRECTOR_DEFAULTS, brief: "A short quiet comic.", width: 1256, height: 1672,
        max_output_chars: 800, page_count: 2, locked_text: "原文\r\n不改", continuity_context: "Human-supplied red hat.",
        layout_context_json: '{"kind":"user task data"}', seed: 42, recovery_slot: "t8-director-test-slot" };
}

class Node {
    constructor() {
        this.widgets = core.DIRECTOR_NAMES.map(name => ({ name, value: core.DIRECTOR_DEFAULTS[name], type: "text",
            inputEl: ["brief", "locked_text", "layout_context_json", "continuity_context"].includes(name) ? { value: "" } : undefined,
            computeSize: () => [540, 28] }));
        this.properties = {}; this.inputs = []; this.id = 42; this.size = [540, 600];
        this.graph = { _nodes: [this], changes: 0, change() { this.changes++; } };
    }
    addWidget(type, name, value, callback, options) {
        const valueObject = { type, name, value, callback, options, computeSize: () => [540, 28] };
        this.widgets.push(valueObject); return valueObject;
    }
    setDirtyCanvas() {}
    onNodeCreated() { return 11; }
    onConfigure(data) {
        data.widgets_values?.forEach((value, index) => { if (this.widgets[index]) this.widgets[index].value = value; });
        for (const item of this.widgets) if (Object.hasOwn(data.widgets_values_named || {}, item.name)) item.value = data.widgets_values_named[item.name];
        this.properties = { ...(data.properties || {}) };
        if (data.inputs) this.inputs = structuredClone(data.inputs);
        return 7;
    }
    onSerialize(data) { data.widgets_values_named = Object.fromEntries(this.widgets.map(item => [item.name, item.value])); return 13; }
    onAdded() { return 17; }
    onRemoved() { return 19; }
}

const saved = () => ({ widgets_values: core.DIRECTOR_NAMES.map(name => fixture()[name]),
    widgets_values_named: fixture(), properties: { [core.DIRECTOR_STATE]: fixture() } });

function deferred() {
    let resolve; const promise = new Promise(result => { resolve = result; }); return { promise, resolve };
}

function documentFixture() {
    const elements = [];
    const make = tag => {
        const element = { tag, style: {}, children: [], events: {}, textContent: "", removed: false,
            append(...children) { this.children.push(...children); },
            addEventListener(name, callback) { this.events[name] = callback; },
            close() { this.closed = true; this.events.close?.(); }, remove() { this.removed = true; },
            showModal() { this.shown = true; } };
        Object.defineProperty(element, "innerHTML", { set() { throw new Error("Untrusted HTML must never be used"); } });
        elements.push(element); return element;
    };
    return { elements, body: make("body"), createElement: make };
}

async function extensionHarness({ fetchFn, queuePrompt } = {}) {
    let extension; const alerts = [], requests = [], queues = [], document = documentFixture();
    const context = vm.createContext({ ...core, document, console,
        app: { registerExtension(value) { extension = value; }, queuePrompt: async (...args) => {
            queues.push(args); return queuePrompt?.(...args);
        } }, api: { fetchApi: async (...args) => { requests.push(args); return fetchFn?.(...args) || { ok: true, json: async () => ({ recoverable: false }) }; } },
        window: { alert(text) { alerts.push(text); } } });
    const code = (await readFile(new URL("../../web/js/moss_authoring_director.js", import.meta.url), "utf8"))
        .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "");
    vm.runInContext(code, context);
    class Director extends Node {}
    await extension.beforeRegisterNodeDef(Director, { name: core.DIRECTOR_ID });
    const node = new Director(); node.onNodeCreated();
    return { node, Director, extension, alerts, requests, queues, document };
}

test("Director canonical 17-field map restores before native configure, including reordered widgets and DOM text", () => {
    assert.equal(core.DIRECTOR_NAMES.length, 17);
    assert.deepEqual(core.DIRECTOR_NAMES.slice(-3), ["seed", "recovery_slot", "recovery_action"]);
    const node = new Node(); node.widgets.reverse(); const input = saved(), before = JSON.stringify(input);
    assert.equal(core.configureDirector(node, input, Node.prototype.onConfigure, [input]), 7);
    for (const [name, value] of Object.entries(fixture())) assert.equal(widget(node, name).value, value, name);
    assert.equal(widget(node, "locked_text").inputEl.value, "原文\r\n不改");
    assert.equal(JSON.stringify(input), before);
    const result = {}; core.serializeDirector(node, result);
    assert.deepEqual(result.widgets_values, input.widgets_values);
    assert.deepEqual(Object.keys(result.widgets_values_named), core.DIRECTOR_NAMES);
    assert.deepEqual(result.properties[core.DIRECTOR_STATE], fixture());
    assert.equal(widget(node, "recovery_slot").hidden, true);
    assert.equal(widget(node, "recovery_action").hidden, true);
    for (const item of node.widgets.filter(item => !["recovery_slot", "recovery_action"].includes(item.name))) assert.notEqual(item.hidden, true);
});

test("Director supports native/marker/positional metadata but malformed maps safely reset all fields", () => {
    for (const source of ["private", "native", "positional"]) {
        const data = saved();
        if (source !== "private") delete data.properties[core.DIRECTOR_STATE];
        if (source === "positional") delete data.widgets_values_named;
        data.widgets_values.push("button tail", "PRIVATE-KEY");
        const node = new Node(); core.configureDirector(node, data, Node.prototype.onConfigure, [data]);
        assert.equal(widget(node, "width").value, 1256);
        assert.equal(widget(node, "profile").value, core.COMIC);
    }
    const node = new Node(); widget(node, "profile").value = core.FISHER;
    widget(node, "width").value = 16384; widget(node, "brief").value = "Previous workflow content";
    const invalid = { widgets_values: ["bad"], widgets_values_named: { profile: core.FISHER },
        properties: { [core.DIRECTOR_STATE]: { profile: core.FISHER }, [RECOVERY_SLOT_PROPERTY]: "t8-old-other-workflow" } };
    core.configureDirector(node, invalid, Node.prototype.onConfigure, [invalid]);
    for (const name of core.DIRECTOR_NAMES.filter(name => name !== "recovery_slot")) assert.equal(widget(node, name).value, core.DIRECTOR_DEFAULTS[name]);
    assert.notEqual(widget(node, "recovery_slot").value, "t8-old-other-workflow");
    assert.match(widget(node, "recovery_slot").value, /^t8-/);
    for (const [name, value] of [["width", true], ["width", 17], ["max_output_chars", 20001], ["profile", []],
        ["preserve_layout", 1], ["llm_max_tokens", 12], ["seed", false], ["brief", "\ud800"],
        ["locked_text", "\udc00"], ["continuity_context", "文".repeat(22000)]]) {
        const data = { widgets_values_named: { ...fixture(), [name]: value } };
        assert.equal(core.savedDirectorValues(data), null, name);
    }
});

test("Director linked nulls require saved input links and leave those links intact", () => {
    const names = ["brief", "width", "height", "max_output_chars", "page_count", "locked_text", "continuity_context", "layout_context_json", "preserve_layout"];
    const map = fixture(); for (const name of names) map[name] = null;
    const inputs = names.map((name, index) => ({ name, widget: { name }, link: index }));
    const data = { widgets_values_named: map, inputs }, node = new Node(); node.widgets.reverse();
    core.configureDirector(node, data, Node.prototype.onConfigure, [data]);
    for (const name of names) assert.equal(widget(node, name).value, core.DIRECTOR_DEFAULTS[name]);
    assert.deepEqual(node.inputs, inputs);
    assert.equal(widget(node, "seed").value, 42);
    assert.equal(core.savedDirectorValues({ widgets_values_named: map }), null);
    assert.equal(core.savedDirectorValues({ widgets_values_named: map, inputs: inputs.map(input => ({ ...input, link: null })) }), null);
    for (const name of ["recovery_slot", "recovery_action"]) {
        assert.equal(core.savedDirectorValues({ widgets_values_named: { ...fixture(), [name]: null }, inputs: [{ name, link: 1 }] }), null);
    }
});

test("Director saves exactly 17 fields, normal action, no button values/results and duplicate slots split", () => {
    const first = new Node(), second = new Node();
    first.graph._nodes.push(second); second.graph = first.graph;
    core.configureDirector(first, saved(), Node.prototype.onConfigure);
    core.configureDirector(second, saved(), Node.prototype.onConfigure);
    assert.notEqual(widget(first, "recovery_slot").value, widget(second, "recovery_slot").value);
    widget(first, "recovery_action").value = "restore_last";
    first.widgets.push({ name: "action", value: "PRIVATE-RESULT", serialize: false });
    first.t8AuthoringLast = { bundle: "PRIVATE-RESULT" };
    const serialized = {}; core.serializeDirector(first, serialized);
    assert.equal(serialized.widgets_values.length, 17);
    assert.equal(serialized.widgets_values.at(-1), "normal");
    assert.equal(serialized.widgets_values_named.recovery_action, "normal");
    assert.doesNotMatch(JSON.stringify(serialized), /PRIVATE-RESULT/);
    const data = saved(); data.widgets_values_named.recovery_action = "restore_last";
    data.properties[core.DIRECTOR_STATE].recovery_action = "restore_last";
    core.configureDirector(first, data, Node.prototype.onConfigure);
    assert.equal(widget(first, "recovery_action").value, "normal");
});

test("Director restoration performs only its own GET then queues only this node under restore_last", async () => {
    const node = new Node(), requests = [], queued = [], alerts = [];
    core.ensureDirectorSlot(node);
    assert.equal(await core.restoreDirector({ node, fetchFn: async (...args) => { requests.push(args); return { ok: true, json: async () => ({ recoverable: true, raw: "PRIVATE" }) }; },
        queuePrompt: async (...args) => { queued.push(args); assert.equal(widget(node, "recovery_action").value, "restore_last"); }, alertFn: text => alerts.push(text) }), true);
    assert.equal(requests.length, 1); assert.match(requests[0][0], /moss-authoring\/status\/t8-/);
    assert.equal(requests[0][1].cache, "no-store");
    assert.deepEqual(queued, [[0, 1, [42]]]);
    assert.equal(widget(node, "recovery_action").value, "normal");
    assert.deepEqual(alerts, []);
    for (const status of [{ recoverable: false }, { recoverable: "true" }, {}]) {
        assert.equal(await core.restoreDirector({ node, fetchFn: async () => ({ ok: true, json: async () => status }),
            queuePrompt: async () => { throw new Error("Must not queue"); } }), false);
    }
    assert.equal(await core.restoreDirector({ node, fetchFn: async () => { throw new Error("PRIVATE-UPSTREAM-URL"); },
        alertFn: text => alerts.push(text), queuePrompt: async () => {} }), false);
    assert.doesNotMatch(alerts.join("\n"), /PRIVATE/);
    assert.equal(widget(node, "recovery_action").value, "normal");
    await core.restoreDirector({ node, fetchFn: async () => ({ ok: true, json: async () => ({ recoverable: true }) }), queuePrompt: async () => { throw new Error("queue failed"); } });
    assert.equal(widget(node, "recovery_action").value, "normal");
});

test("Director pending restore coalesces clicks and removal/configure/slot replacement discard async responses", async () => {
    for (const change of ["remove", "configure", "slot", "graph"]) {
        const node = new Node(), pending = deferred(), queues = [], alerts = [];
        core.ensureDirectorSlot(node);
        const options = { node, fetchFn: () => pending.promise, queuePrompt: async (...args) => queues.push(args), alertFn: text => alerts.push(text) };
        const first = core.restoreDirector(options);
        assert.equal(await core.restoreDirector(options), false);
        if (change === "remove") node.t8AuthoringRemoved = true;
        if (change === "configure") node.t8AuthoringEpoch = 1;
        if (change === "slot") widget(node, "recovery_slot").value = "t8-another-new-slot";
        if (change === "graph") node.graph = { _nodes: [node] };
        pending.resolve({ ok: true, json: async () => ({ recoverable: true }) });
        assert.equal(await first, false, change);
        assert.deepEqual(queues, []); assert.deepEqual(alerts, []);
        assert.equal(widget(node, "recovery_action").value, "normal");
    }
});

test("Director inspection is explicit same-prefix GET, validates inspection flags and never queues", async () => {
    const node = new Node(), requests = [], shown = [], alerts = [];
    core.ensureDirectorSlot(node);
    const artifact = { schema_version: "t8-moss-authoring-inspection/v1", inspection_only: true, complete: false,
        raw: '<img src=x onerror="PRIVATE()">', units: [], stage_records: [], code: "invalid_source", truncated: false };
    const options = { node, fetchFn: async (...args) => { requests.push(args); return { ok: true, json: async () => artifact }; },
        showText: (...args) => shown.push(args), alertFn: text => alerts.push(text) };
    assert.equal(await core.inspectDirector(options), true);
    assert.match(requests[0][0], /moss-authoring\/draft\/t8-/);
    assert.equal(requests[0][1].cache, "no-store");
    assert.equal(JSON.parse(shown[0][0]).raw, artifact.raw);
    for (const update of [{ complete: true }, { inspection_only: false }, { inspection_only: "true" }, { schema_version: "bundle" }, { raw: "x".repeat(2 * 1024 * 1024) }]) {
        assert.equal(await core.inspectDirector({ ...options, fetchFn: async () => ({ ok: true, json: async () => ({ ...artifact, ...update }) }) }), false);
    }
    assert.equal(shown.length, 1);
    assert.doesNotMatch(alerts.join("\n"), /PRIVATE/);
    const pending = deferred();
    const result = core.inspectDirector({ ...options, fetchFn: () => pending.promise });
    node.t8AuthoringRemoved = true;
    pending.resolve({ ok: true, json: async () => artifact });
    assert.equal(await result, false); assert.equal(shown.length, 1);
});

test("Actual Director hooks are scoped/idempotent, preserve callback returns and render inspection via textContent", async () => {
    const artifact = { schema_version: "t8-moss-authoring-inspection/v1", inspection_only: true, complete: false,
        raw: '<script>globalThis.PRIVATE = true</script>', units: [], stage_records: [], code: "invalid", truncated: false };
    const h = await extensionHarness({ fetchFn: async () => ({ ok: true, json: async () => artifact }) });
    const count = h.node.widgets.length;
    assert.equal(h.node.onNodeCreated(), 11); assert.equal(h.node.widgets.length, count);
    const configured = h.Director.prototype.onConfigure;
    await h.extension.beforeRegisterNodeDef(h.Director, { name: core.DIRECTOR_ID });
    assert.equal(h.Director.prototype.onConfigure, configured);
    class Other extends Node {}
    const original = Other.prototype.onConfigure;
    await h.extension.beforeRegisterNodeDef(Other, { name: "MOSSImagePromptEnhancerT8" });
    assert.equal(Other.prototype.onConfigure, original);
    h.node.widgets.reverse(); assert.equal(h.node.onConfigure(saved()), 7);
    assert.equal(widget(h.node, "width").value, 1256);
    const serialized = {}; assert.equal(h.node.onSerialize(serialized), 13);
    assert.equal(serialized.widgets_values.length, 17);
    const buttons = h.node.widgets.filter(item => item.type === "button");
    assert.equal(buttons.length, 3);
    for (const button of buttons) {
        assert.equal(button.serialize, false); assert.equal(button.options.serialize, false); assert.equal(button.serializeValue(), undefined);
    }
    await buttons.find(button => /Inspect failed draft/.test(button.name)).callback();
    assert.deepEqual(h.queues, []);
    const pre = h.document.elements.find(element => element.tag === "pre");
    assert.match(pre.textContent, /<script>/);
    const dialog = h.document.elements.find(element => element.tag === "dialog");
    assert.equal(dialog.shown, true);
    assert.equal(h.node.onRemoved(), 19);
    assert.equal(dialog.removed, true);
    assert.equal(h.node.t8AuthoringRemoved, true);
    assert.equal(h.node.onAdded(), 17);
    assert.equal(h.node.t8AuthoringRemoved, false);
    assert.match(core.DIRECTOR_HELP, /1\+2N/);
    assert.match(core.DIRECTOR_HELP, /Token/);
    assert.match(core.DIRECTOR_HELP, /edit_unit_ids/);
});

test("Native connected text rows retain compact labels and repeated reconnects cannot grow height", () => {
    const node = new Node();
    node.updateComputedDisabled = () => {};
    node.computeSize = () => [540, 40 + node.widgets.reduce((total, item) => total + item.computeSize()[1], 0)];
    node.setSize = size => { node.size = size; };
    const brief = widget(node, "brief"); brief.type = "customtext"; brief.y = 80;
    core.refreshAuthoringRows(node);
    const originalHeight = node.size[1], originalValue = brief.value, originalCount = node.widgets.length;
    const labels = [];
    for (let index = 0; index < 40; index++) {
        node.inputs = [{ name: "brief", widget: { name: "brief" }, link: 8 }];
        core.refreshAuthoringRows(node);
        assert.equal(brief.type, "customtext"); assert.equal(brief.hidden, false); assert.equal(brief.computeSize()[1], 20);
        core.drawAuthoringLinkedLabels(node, { save() {}, restore() {}, fillText(text) { labels.push(text); } });
        node.inputs[0].link = null; core.refreshAuthoringRows(node);
        assert.equal(brief.computeSize()[1], 28); assert.equal(node.size[1], originalHeight);
    }
    assert.equal(brief.value, originalValue); assert.equal(node.widgets.length, originalCount);
    assert.ok(labels.every(label => label.includes("Brief") && label.includes("已连接")));
});

test("Legacy converted text keeps native serialization ownership and unrelated host controls are not saved", () => {
    const node = new Node(), brief = widget(node, "brief"), serialize = () => "native-owned";
    brief.origType = "customtext"; brief.origComputeSize = () => [540, 28]; brief.type = "converted-widget";
    brief.computeSize = () => [0, -4]; brief.serializeValue = serialize;
    node.inputs = [{ name: "brief", link: 2 }];
    node.widgets.splice(15, 0, { name: "control_after_generate", type: "combo", value: "randomize" });
    core.configureDirector(node, saved(), Node.prototype.onConfigure, [saved()]);
    core.refreshAuthoringRows(node);
    assert.equal(brief.type, "converted-widget"); assert.equal(brief.serializeValue, serialize); assert.equal(brief.hidden, true);
    assert.equal(widget(node, "control_after_generate").value, "randomize");
    const data = {}; core.serializeDirector(node, data);
    assert.equal(data.widgets_values.length, 17); assert.equal(Object.keys(data.widgets_values_named).length, 17);
    assert.ok(!Object.hasOwn(data.widgets_values_named, "control_after_generate"));
});

test("Page-only row hooks preserve native callbacks and three widgets without a custom serializer", async () => {
    const harness = await extensionHarness();
    class Page extends Node {
        onConnectionsChange() { return 23; }
    }
    await harness.extension.beforeRegisterNodeDef(Page, { name: "MOSSAuthoringPageT8" });
    const configured = Page.prototype.onConfigure;
    await harness.extension.beforeRegisterNodeDef(Page, { name: "MOSSAuthoringPageT8" });
    assert.equal(Page.prototype.onConfigure, configured);
    const page = new Page(); page.widgets = [{ name: "bundle_json", type: "customtext", value: "", computeSize: () => [500, 100] },
        { name: "page_index", value: 1, type: "number" }, { name: "language", value: "en", type: "combo" }];
    page.updateComputedDisabled = () => {};
    assert.equal(page.onNodeCreated(), 11);
    assert.equal(page.onConfigure({ widgets_values: ['{"literal":"{not expanded}"}', 2, "zh"] }), 7);
    page.inputs = [{ name: "bundle_json", link: 8 }];
    assert.equal(page.onConnectionsChange(), 23);
    assert.equal(page.widgets[0].computeSize()[1], 20); assert.equal(page.widgets.length, 3);
    assert.deepEqual(page.widgets.map(item => item.value), ['{"literal":"{not expanded}"}', 2, "zh"]);
    assert.equal(Page.prototype.onSerialize, Node.prototype.onSerialize);
});
