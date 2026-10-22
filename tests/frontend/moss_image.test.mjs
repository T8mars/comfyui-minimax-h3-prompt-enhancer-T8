import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import * as core from "../../web/js/moss_image_ui.mjs";

const values = ["A quiet cup.", core.GENERATE, "AUTO / 自动", 1024, 1024, "按需求（默认英文）/ Auto", core.API_MODES[0],
    "", 0, 1, 16384, "", "gemini-3.5-flash", "qwen/qwen3.8-flash-next", "", 0, "randomize",
    "test-model.gguf", "AUTO（自动匹配）", 32768, 16384, "关闭（推荐，速度优先）", "medium",
    "执行后卸载（推荐）", "AUTO（显存不足时释放）", "t8-moss-test-slot", "normal", core.CLASSIC];

test("MOSS five legacy workflows keep their exact 27 values and migrate to an appended Classic profile", async () => {
    for (const stem of ["caption", "layout", "spatial", "compile_only", "compile_error"]) {
        const workflow = JSON.parse(await readFile(new URL(`../../example_workflows/moss_${stem}_example.json`, import.meta.url), "utf8"));
        const saved = workflow.nodes.find(n => n.type === core.MOSS_ID);
        const node = new Node(); node.widgets.reverse();
        core.configureMoss(node, saved, Node.prototype.onConfigure, [saved]);
        for (const name of core.LEGACY_MOSS_NAMES) assert.equal(node.widgets.find(w => w.name === name).value, saved.widgets_values_named[name], `${stem}: ${name}`);
        assert.equal(node.widgets.find(w => w.name === "authoring_profile").value, core.CLASSIC);
        const again = {}; core.serializeMoss(node, again);
        assert.deepEqual(again.widgets_values.slice(0, 27), saved.widgets_values, stem);
        assert.equal(again.widgets_values.length, 28);
        assert.equal(again.widgets_values.at(-1), core.CLASSIC);
        assert.equal(again.properties[core.MOSS_PROFILE_SCHEMA], 2);
    }
});

class Node {
    constructor() {
        this.widgets = core.MOSS_NAMES.map((name, i) => ({ name, value: values[i], type: "text", computeSize: () => [500, 28] }));
        this.widgets.push({ name: "api_key", value: "PRIVATE-CREDENTIAL", type: "text", computeSize: () => [500, 28] });
        this.properties = {}; this.size = [540, 0]; this.inputs = []; this.id = 1;
        this.graph = { _nodes: [this], change() {} };
    }
    addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options, computeSize: () => [500, 28] }; this.widgets.push(w); return w; }
    computeSize() { return [540, 100 + this.widgets.reduce((sum, w) => sum + (w.computeSize?.()[1] ?? 28), 0)]; }
    setSize(size) { this.size = size; }
    setDirtyCanvas() {}
    onConfigure(data) {
        data.widgets_values?.forEach((value, i) => { if (this.widgets[i]) this.widgets[i].value = value; });
        for (const w of this.widgets) if (Object.hasOwn(data.widgets_values_named || {}, w.name)) w.value = data.widgets_values_named[w.name];
        return 17;
    }
    onSerialize(data) { data.widgets_values_named = Object.fromEntries(this.widgets.map(w => [w.name, w.value])); return 23; }
}

test("MOSS stable named and native order excludes Key/actions and restores INT fields synchronously", () => {
    const node = new Node(), saved = {};
    node.widgets.push({ name: "tooltip", value: "not a field" });
    core.serializeMoss(node, saved);
    assert.equal(saved.widgets_values.length, core.MOSS_NAMES.length);
    assert.equal(JSON.stringify(saved).includes("PRIVATE-CREDENTIAL"), false);
    assert.deepEqual(Object.keys(saved.widgets_values_named), core.MOSS_NAMES);
    const reload = new Node(); reload.widgets.reverse();
    const result = core.configureMoss(reload, saved, Node.prototype.onConfigure, [saved]);
    assert.equal(result, 17);
    for (const [i, name] of core.MOSS_NAMES.entries()) assert.equal(reload.widgets.find(w => w.name === name).value, values[i], name);
    assert.equal(reload.widgets.find(w => w.name === "api_key").value, "");
});

test("MOSS handles linked-null/omitted brief, absent seed control, optional Key and action tails", () => {
    for (const variation of ["null", "omit", "noControl", "keyBeforeApi", "keyOptional"]) {
        const array = [...values];
        if (variation === "null") array[0] = null;
        if (variation === "omit") array.shift();
        if (variation === "noControl") array.splice(16, 1);
        if (variation === "keyBeforeApi") array.splice(6, 0, "");
        if (variation === "keyOptional") array.splice(7, 0, "");
        array.push("UI tail", "private tooltip");
        const mapped = core.savedMossValues({ widgets_values: array });
        assert.ok(mapped, variation);
        assert.equal(mapped.get("seed"), 0, variation);
        assert.equal(mapped.get("local_model"), "test-model.gguf", variation);
        assert.equal(mapped.get("api_mode"), core.API_MODES[0], variation);
    }
});

test("MOSS rejects corrupted named/positional maps before native model widgets see them", () => {
    const node = new Node();
    const originalModel = node.widgets.find(w => w.name === "local_model").value;
    const invalid = [...values]; invalid[6] = ""; invalid[17] = 0;
    core.configureMoss(node, { widgets_values: invalid, widgets_values_named: { api_mode: "" } }, Node.prototype.onConfigure);
    assert.equal(node.widgets.find(w => w.name === "api_mode").value, core.API_MODES[0]);
    assert.equal(node.widgets.find(w => w.name === "local_model").value, originalModel);
    const mapped = core.savedMossValues({ widgets_values: values, properties: { [core.MOSS_STATE]: { broken: true } } });
    assert.equal(mapped.get("width"), 1024);
});

test("MOSS compile/local/Strata visibility keeps saved values and stable node height", () => {
    const node = new Node();
    core.refreshMoss(node); const baseline = node.size[1];
    for (let i = 0; i < 100; i++) {
        node.widgets.find(w => w.name === "operation").value = core.COMPILE;
        core.refreshMoss(node);
        assert.ok(node.widgets.find(w => w.name === "api_key").hidden);
        assert.equal(node.widgets.find(w => w.name === "draft_json").hidden, false);
        node.widgets.find(w => w.name === "operation").value = core.GENERATE;
        core.refreshMoss(node);
        assert.equal(node.size[1], baseline);
    }
    node.widgets.find(w => w.name === "api_mode").value = core.API_MODES[3];
    core.refreshMoss(node);
    assert.ok(node.widgets.find(w => w.name === "api_key").hidden);
    assert.equal(node.widgets.find(w => w.name === "api_key").value, "PRIVATE-CREDENTIAL");
});

test("MOSS shared provider resolution traverses object/Map reroutes and terminates cycles", () => {
    const node = new Node(), source = { widgets: [{ name: "provider", value: "Local Qwen" }] };
    const reroute = { type: "Reroute", inputs: [{ link: 1 }] };
    node.inputs = [{ name: "provider_config", link: 2 }];
    const map = [[1, { origin_id: 10 }], [2, { origin_id: 20 }]];
    node.graph = { links: new Map(map), getNodeById: id => id === 10 ? source : reroute };
    assert.equal(core.effectiveMossMode(node), core.API_MODES[3]);
    source.widgets[0].value = "Strata";
    node.graph.links = Object.fromEntries(map);
    assert.equal(core.effectiveMossMode(node), core.API_MODES[4]);
    reroute.inputs[0].link = 2;
    assert.equal(core.effectiveMossMode(node), core.API_MODES[0]);
});

test("MOSS status does not promote structure into rendered or token quality", () => {
    const text = core.mossStatus({ format: "layout", width: 1536, height: 1024, calls: 2, origin: "cache" }, true);
    assert.match(text, /上次结果/); assert.match(text, /未核验/); assert.match(text, /1536×1024/);
    assert.equal(core.mossStatus({ format: "<script>", width: 1, height: 1, calls: 1 }).includes("<script>"), false);
    assert.match(core.mossStatus({ warnings: ["correction_failed_draft_kept"] }), /纠正失败/);
    assert.match(core.mossStatus({ warnings: ["description_over_limit"] }), /超字数/);
});

test("MOSS actual extension hooks are scoped, preserve callbacks and do not replay after RAF", async () => {
    let extension; const frames = [];
    const context = vm.createContext({ ...core, app: { registerExtension(value) { extension = value; } },
        requestAnimationFrame(fn) { frames.push(fn); },
        addCompletionRecoveryButton(node) { return node.addWidget("button", "Recovery", "", () => {}, { serialize: false }); },
        api: {}, window: {}, console,
    });
    const code = (await readFile(new URL("../../web/js/moss_image_prompt_enhancer.js", import.meta.url), "utf8"))
        .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "");
    vm.runInContext(code, context);
    class Other extends Node {}
    const original = Other.prototype.onConfigure;
    await extension.beforeRegisterNodeDef(Other, { name: "QwenImage21PromptEnhancerT8" });
    assert.equal(Other.prototype.onConfigure, original);
    class Moss extends Node {}
    await extension.beforeRegisterNodeDef(Moss, { name: core.MOSS_ID });
    const node = new Moss(); node.onNodeCreated();
    const count = node.widgets.length; node.onNodeCreated(); assert.equal(node.widgets.length, count);
    const saved = {}; assert.equal(node.onSerialize(saved), 23);
    node.widgets.reverse(); node.onConfigure(saved);
    assert.equal(node.widgets.find(w => w.name === "width").value, 1024);
    node.widgets.find(w => w.name === "width").value = 1536;
    frames.splice(0).forEach(fn => fn());
    assert.equal(node.widgets.find(w => w.name === "width").value, 1536);
    assert.equal(JSON.stringify(saved).includes("tooltip"), false);
});
