import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import * as core from "../../web/js/moss_image_ui.mjs";

async function compileExample() {
    const graph = JSON.parse(await readFile(new URL("../../example_workflows/moss_compile_only_example.json", import.meta.url), "utf8"));
    return graph.nodes.find(node => node.type === core.MOSS_ID);
}

test("MOSS linked draft null metadata preserves compile mode and all unrelated values", async () => {
    const saved = await compileExample();
    saved.widgets_values[core.MOSS_NAMES.indexOf("draft_json")] = null;
    saved.widgets_values_named.draft_json = null;
    saved.properties[core.MOSS_STATE].draft_json = null;
    const mapped = core.savedMossValues(saved);
    assert.ok(mapped, "A connected lazy STRING is not a corrupt workflow");
    assert.equal(mapped.get("operation"), core.COMPILE);
    assert.equal(mapped.get("draft_json"), "");
    assert.equal(mapped.get("local_context_size"), saved.widgets_values_named.local_context_size);
});

test("MOSS eight-pixel canvas survives named and positional host restoration without rounding", async () => {
    const saved = await compileExample();
    saved.widgets_values[3] = saved.widgets_values_named.width = saved.properties[core.MOSS_STATE].width = 1256;
    saved.widgets_values[4] = saved.widgets_values_named.height = saved.properties[core.MOSS_STATE].height = 1672;
    for (const named of [true, false]) {
        if (!named) { delete saved.widgets_values_named; delete saved.properties[core.MOSS_STATE]; }
        const values = core.savedMossValues(saved);
        assert.ok(values);
        assert.equal(values.get("width"), 1256);
        assert.equal(values.get("height"), 1672);
    }
});

test("MOSS positional host omission of linked draft does not shift models or seed", async () => {
    const saved = await compileExample();
    delete saved.widgets_values_named;
    delete saved.properties[core.MOSS_STATE];
    saved.widgets_values.splice(core.MOSS_NAMES.indexOf("draft_json"), 1);
    const mapped = core.savedMossValues(saved);
    assert.ok(mapped, "Recognize omitted linked draft using later model/seed discriminators");
    assert.equal(mapped.get("operation"), core.COMPILE);
    assert.equal(mapped.get("draft_json"), "");
    assert.equal(mapped.get("custom_model"), "qwen/qwen3.8-flash-next");
    assert.equal(mapped.get("seed"), 0);
});

async function extensionNode() {
    let extension;
    const source = await compileExample();
    class Node {
        constructor() {
            this.widgets = core.MOSS_NAMES.map(name => ({ name, value: source.widgets_values_named[name], type: "text", computeSize: () => [500, 28] }));
            this.properties = {}; this.size = [540, 0]; this.inputs = []; this.id = 1;
            this.graph = { _nodes: [this], change() {} };
        }
        addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options, computeSize: () => [500, 28] }; this.widgets.push(w); return w; }
        computeSize() { return [540, 100 + this.widgets.reduce((n, w) => n + (w.computeSize?.()[1] ?? 28), 0)]; }
        setSize(size) { this.size = size; }
        setDirtyCanvas() {}
    }
    const context = vm.createContext({ ...core, app: { registerExtension(value) { extension = value; } }, api: {},
        addCompletionRecoveryButton(node) { return node.addWidget("button", "Recovery", "", () => {}, { serialize: false }); },
        requestAnimationFrame(callback) { callback(); }, window: {}, console });
    const code = (await readFile(new URL("../../web/js/moss_image_prompt_enhancer.js", import.meta.url), "utf8"))
        .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "");
    vm.runInContext(code, context);
    await extension.beforeRegisterNodeDef(Node, { name: core.MOSS_ID });
    const node = new Node(); node.onNodeCreated();
    return node;
}

const validResult = { t8_moss_image_result: [JSON.stringify({ format: "caption", width: 1024, height: 1024, calls: 1, warnings: [] })] };

test("MOSS connection and shared-provider changes mark the previous result stale", async () => {
    const node = await extensionNode();
    node.onExecuted(validResult);
    assert.equal(node.t8MossStale, false);
    node.onConnectionsChange(1, 0, true, {});
    assert.equal(node.t8MossStale, true);
    assert.match(node.t8MossStatusWidget.label, /上次结果/);
    node.onExecuted(validResult);
    node.t8RefreshStrata();
    assert.equal(node.t8MossStale, true);
});

test("MOSS malformed status warnings never break the UI status button", () => {
    for (const warnings of [null, {}, 3, true, "description_over_limit"]) {
        assert.doesNotThrow(() => core.mossStatus({ format: "caption", width: 1024, height: 1024, calls: 1, warnings }));
    }
});

test("MOSS respects native conversion and new-host linked controls without hiding unconnected sockets", async () => {
    const node = await extensionNode();
    node.widgets.find(w => w.name === "operation").value = core.GENERATE;
    const prompt = node.widgets.find(w => w.name === "prompt");
    node.inputs = [{ name: "prompt", widget: { name: "prompt" }, link: null }];
    core.refreshMoss(node);
    assert.equal(prompt.hidden, false, "New hosts expose unconnected widget sockets too");
    node.inputs[0].link = 42;
    core.refreshMoss(node);
    assert.equal(prompt.hidden, true);
    assert.deepEqual(prompt.computeSize(), [0, -4]);
    node.inputs[0].link = null;
    core.refreshMoss(node);
    assert.equal(prompt.hidden, false);
    const nativeSize = () => [0, -4], nativeSerialize = () => "linked-only";
    prompt.origType = prompt.type; prompt.origComputeSize = prompt.computeSize;
    prompt.type = "converted-widget"; prompt.computeSize = nativeSize; prompt.serializeValue = nativeSerialize;
    for (let i = 0; i < 20; i++) core.refreshMoss(node);
    assert.equal(prompt.type, "converted-widget");
    assert.equal(prompt.computeSize, nativeSize);
    assert.equal(prompt.serializeValue, nativeSerialize);
});

test("MOSS linked layout compacts inherited native expansion, retains values and manual unchanged layout", async () => {
    const node = await extensionNode();
    node.widgets.find(w => w.name === "operation").value = core.GENERATE;
    core.refreshMoss(node);
    const prompt = node.widgets.find(w => w.name === "prompt"), value = prompt.value;
    node.size[1] += 600; // host allocates a stretchable multiline widget after onNodeCreated
    node.inputs = [{ name: "prompt", widget: { name: "prompt" }, link: 4 }];
    node.onConnectionsChange();
    assert.equal(node.size[1], node.computeSize()[1]);
    assert.equal(prompt.value, value);
    node.size[1] += 100;
    core.refreshMoss(node);
    assert.equal(node.size[1], node.computeSize()[1] + 100, "A status refresh does not erase a manual unchanged-layout resize");
});

test("MOSS first sees an already native-converted control and can later restore the editor", () => {
    const originalSize = () => [500, 100];
    const prompt = { name: "prompt", value: "Brief", type: "converted-widget", origType: "customtext",
        origComputeSize: originalSize, computeSize: () => [0, -4] };
    const node = { widgets: [prompt], inputs: [{ name: "prompt", widget: { name: "prompt" }, link: null }] };
    core.refreshMoss(node);
    assert.equal(prompt.type, "converted-widget");
    // Host's native showWidget and port removal, not the extension's own toggle.
    prompt.type = prompt.origType; prompt.computeSize = prompt.origComputeSize;
    delete prompt.origType; delete prompt.origComputeSize;
    node.inputs = [];
    core.refreshMoss(node);
    assert.equal(prompt.hidden, false);
    assert.equal(prompt.type, "customtext");
    assert.equal(prompt.computeSize, originalSize);
});

test("MOSS native inline socket rows retain a label, position and widget metadata when connected", async () => {
    const node = await extensionNode();
    node.updateComputedDisabled = () => {};
    const prompt = node.widgets.find(w => w.name === "prompt"), draft = node.widgets.find(w => w.name === "draft_json");
    node.widgets.find(w => w.name === "operation").value = core.GENERATE;
    node.inputs = [prompt, draft].map((w, i) => ({ name: w.name, widget: { name: w.name }, link: i + 4 }));
    core.refreshMoss(node);
    for (const w of [prompt, draft]) {
        assert.notEqual(w.type, "converted-widget");
        assert.equal(w.hidden, false, "Host keeps a native suppressed-row label even for connected advanced inputs");
        assert.deepEqual(w.computeSize(), [0, 20]);
    }
    assert.equal(node.inputs[0].widget.name, "prompt");
    node.inputs.forEach(i => { i.link = null; });
    core.refreshMoss(node);
    assert.deepEqual(prompt.computeSize(), [500, 28]);
    assert.equal(draft.hidden, true);
});

test("MOSS observes actual linked shared-config callbacks without affecting unrelated consumers", async () => {
    const node = await extensionNode(), other = await extensionNode();
    const calls = [];
    const source = { id: 10, widgets: [{ name: "provider", value: "OpenAI Compatible" },
        { name: "custom_model", value: "first", callback(v) { calls.push([this.name, v]); return 19; } }] };
    const graph = { _nodes: [source, node, other], links: new Map([[1, { origin_id: 10 }]]), getNodeById(id) { return id === 10 ? source : null; } };
    source.graph = node.graph = other.graph = graph;
    node.inputs = [{ name: "provider_config", link: 1 }];
    node.onConnectionsChange();
    node.onExecuted(validResult); other.onExecuted(validResult);
    const widget = source.widgets[1], callback = widget.callback;
    assert.equal(widget.callback("second"), 19);
    assert.equal(node.t8MossStale, true);
    assert.equal(other.t8MossStale, false);
    assert.deepEqual(calls, [["custom_model", "second"]]);
    node.onConnectionsChange();
    assert.equal(widget.callback, callback, "Observation does not stack wrappers");
    node.inputs[0].link = null;
    node.onExecuted(validResult);
    widget.callback("third");
    assert.equal(node.t8MossStale, false, "Disconnected config does not invalidate its former consumer");
});

test("MOSS draws only a finite linked DOM label, never user data or a second widget", () => {
    const drawn = [], calls = [];
    const context = { save() { calls.push("save"); }, restore() { calls.push("restore"); }, fillText(...args) { drawn.push(args); } };
    const node = { updateComputedDisabled() {}, size: [420, 600], widgets: [
        { name: "prompt", type: "customtext", y: 100, value: "PRIVATE BRIEF" },
        { name: "locked_text", type: "customtext", y: 160, value: "PRIVATE COPY" }],
        inputs: [{ name: "prompt", link: 3 }, { name: "locked_text", link: null }] };
    core.drawMossLinkedLabels(node, context);
    assert.deepEqual(drawn, [["创作需求 / Brief（已连接）", 24, 115, 372]]);
    assert.deepEqual(calls, ["save", "restore"]);
    assert.equal(JSON.stringify(drawn).includes("PRIVATE"), false);
    node.flags = { collapsed: true };
    core.drawMossLinkedLabels(node, context);
    assert.equal(drawn.length, 1);
});
