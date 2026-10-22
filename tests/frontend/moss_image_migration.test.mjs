import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import * as core from "../../web/js/moss_image_ui.mjs";

const legacyValues = ["A quiet cup.", core.GENERATE, "AUTO / 自动", 1256, 1672, "按需求（默认英文）/ Auto", core.API_MODES[0],
    "Original copy", 700, 1, 16384, "", "gemini-3.5-flash", "qwen/qwen3.8-flash-next", "", 42, "fixed",
    "test-model.gguf", "AUTO（自动匹配）", 32768, 16384, "关闭（推荐，速度优先）", "medium",
    "执行后卸载（推荐）", "AUTO（显存不足时释放）", "t8-moss-migration-slot", "normal"];
const legacyMap = () => Object.fromEntries(core.LEGACY_MOSS_NAMES.map((name, index) => [name, legacyValues[index]]));
const marker = () => ({ [core.MOSS_PROFILE_SCHEMA]: 2 });
const field = (node, name) => node.widgets.find(widget => widget.name === name);

class Node {
    constructor() {
        this.widgets = core.MOSS_NAMES.map((name, index) => ({ name,
            value: name === "authoring_profile" ? core.CLASSIC : legacyValues[index], type: "text",
            inputEl: ["prompt", "draft_json", "locked_text"].includes(name) ? { value: "" } : undefined,
            computeSize: () => [540, 28] }));
        this.widgets.push({ name: "api_key", value: "PRIVATE-KEY", type: "text", computeSize: () => [540, 28] });
        this.inputs = []; this.properties = {}; this.size = [540, 0]; this.id = 1;
        this.graph = { _nodes: [this], change() {} };
    }
    addWidget(type, name, value, callback, options) {
        const widget = { type, name, value, callback, options, computeSize: () => [540, 28] };
        this.widgets.push(widget); return widget;
    }
    computeSize() { return [540, 100 + this.widgets.reduce((sum, widget) => sum + (widget.computeSize?.()[1] ?? 28), 0)]; }
    setSize(size) { this.size = size; }
    setDirtyCanvas() {}
    onConfigure(data) {
        data.widgets_values?.forEach((value, index) => { if (this.widgets[index]) this.widgets[index].value = value; });
        for (const widget of this.widgets) if (Object.hasOwn(data.widgets_values_named || {}, widget.name)) widget.value = data.widgets_values_named[widget.name];
        this.inputs = data.inputs ? structuredClone(data.inputs) : this.inputs;
        this.properties = { ...this.properties, ...(data.properties || {}) };
        return 31;
    }
    onSerialize() { return 37; }
}

const workflowFingerprint = text => createHash("sha256").update(text.replaceAll("\r\n", "\n")).digest("hex");

test("Workflow fingerprints ignore only Git CRLF checkout policy, not content or other formatting", () => {
    const lf = '{\n  "value": "literal\\r\\n"\n}\n';
    assert.equal(workflowFingerprint(lf), workflowFingerprint(lf.replaceAll("\n", "\r\n")));
    assert.notEqual(workflowFingerprint(lf), workflowFingerprint(lf.replace("  ", " ")));
    assert.notEqual(workflowFingerprint(lf), workflowFingerprint(lf.replace("literal", "changed")));
});

test("MOSS profile appends only field 28 and old workflows retain frozen Git bytes under checkout newline policy", async () => {
    assert.equal(core.LEGACY_MOSS_NAMES.length, 27);
    assert.equal(core.MOSS_NAMES.length, 28);
    assert.deepEqual(core.MOSS_NAMES.slice(0, 27), core.LEGACY_MOSS_NAMES);
    assert.equal(core.MOSS_NAMES[8], "max_output_chars");
    assert.equal(core.MOSS_NAMES.at(-1), "authoring_profile");
    const hashes = {
        caption: "644e339306d024d1ae49682a2adba19ca5662584e22fd4711da3d44cbce77471",
        layout: "85964dfc7c31a123889ee9dd2091e3a6c8c428ce8ad83616393033bb8abdf0dd",
        spatial: "4de8a524d8fbadf5a3f5d41ddb134b9c1844fabe0cbb31cf26aa292a1cfcec68",
        compile_only: "3fdb6f99755578e00317cffe37c74db1835c098f02817d6400480332ec3efb83",
        compile_error: "4dfb66db8b2f220a7a5d8bb20ff2e66cb408218030f6e77323e1556405a83a2c",
    };
    for (const [stem, expected] of Object.entries(hashes)) {
        const bytes = await readFile(new URL(`../../example_workflows/moss_${stem}_example.json`, import.meta.url));
        assert.equal(workflowFingerprint(bytes.toString("utf8")), expected, stem);
        assert.equal(JSON.parse(bytes).nodes.find(node => node.type === core.MOSS_ID).widgets_values.length, 27);
    }
});

test("MOSS historical named and positional layouts explicitly reset a previously active profile to Classic", () => {
    const variants = [
        { widgets_values: [...legacyValues, core.FISHER, core.COMIC] },
        { widgets_values_named: legacyMap() },
        { properties: { [core.MOSS_STATE]: legacyMap() } },
        { widgets_values: [...legacyValues, core.FISHER], widgets_values_named: legacyMap(), properties: marker() },
    ];
    for (const data of variants) {
        const node = new Node(); field(node, "authoring_profile").value = core.COMIC; node.widgets.reverse();
        assert.equal(core.configureMoss(node, data, Node.prototype.onConfigure, [data]), 31);
        assert.equal(field(node, "authoring_profile").value, core.CLASSIC);
        for (const [name, value] of Object.entries(legacyMap())) assert.equal(field(node, name).value, value, name);
    }
});

test("MOSS versioned profile and complete 28-name metadata reload without positional assumptions", () => {
    for (const profile of core.MOSS_PROFILES) for (const source of ["positional", "nativeNamed", "privateNamed"]) {
        const map = { ...legacyMap(), authoring_profile: profile };
        const data = source === "positional" ? { widgets_values: [...legacyValues, profile, "button tail"], properties: marker() }
            : source === "nativeNamed" ? { widgets_values_named: map }
                : { properties: { [core.MOSS_STATE]: map } };
        const node = new Node(); node.widgets.reverse();
        core.configureMoss(node, data, Node.prototype.onConfigure, [data]);
        assert.equal(field(node, "authoring_profile").value, profile, source);
        assert.equal(field(node, "width").value, 1256);
        assert.equal(field(node, "height").value, 1672);
        assert.equal(field(node, "max_output_chars").value, 700);
        assert.equal(field(node, "locked_text").inputEl.value, "Original copy");
        assert.equal(field(node, "api_key").value, "");
    }
});

test("MOSS profile migration preserves all recognized historical host variants", () => {
    for (const profile of [core.COMIC, core.FISHER]) for (const variation of ["nullBrief", "omitBrief", "omitDraft", "omitBoth", "noControl", "keyBeforeApi", "keyOptional", "bothKeys"]) {
        const values = [...legacyValues, profile];
        if (["omitDraft", "omitBoth"].includes(variation)) values.splice(11, 1);
        if (variation === "noControl") values.splice(16, 1);
        if (["keyBeforeApi", "bothKeys"].includes(variation)) values.splice(6, 0, "PRIVATE-KEY");
        if (variation === "keyOptional") values.splice(7, 0, "PRIVATE-KEY");
        if (variation === "bothKeys") values.splice(8, 0, "PRIVATE-KEY");
        if (variation === "nullBrief") values[0] = null;
        if (["omitBrief", "omitBoth"].includes(variation)) values.shift();
        const data = { widgets_values: [...values, "tooltip", core.FISHER], properties: marker() };
        const mapped = core.savedMossValues(data);
        assert.ok(mapped, variation);
        assert.equal(mapped.get("authoring_profile"), profile, variation);
        assert.equal(mapped.get("local_model"), "test-model.gguf", variation);
        assert.equal(mapped.get("seed"), 42, variation);
        assert.equal(mapped.get("max_output_chars"), 700, variation);
    }
});

test("MOSS metadata precedence and corrupt profile fallback cannot accidentally enable a contract", () => {
    const map = { ...legacyMap(), authoring_profile: core.FISHER };
    const oldPriority = core.savedMossValues({ properties: { [core.MOSS_STATE]: legacyMap() }, widgets_values_named: map });
    assert.equal(oldPriority.get("authoring_profile"), core.CLASSIC);
    const data = { properties: { [core.MOSS_STATE]: { ...map, authoring_profile: "Unknown" } },
        widgets_values_named: { ...map, width: false }, widgets_values: [...legacyValues, core.FISHER] };
    assert.equal(core.savedMossValues(data).get("authoring_profile"), core.CLASSIC);
    const node = new Node(); field(node, "authoring_profile").value = core.FISHER;
    core.configureMoss(node, { widgets_values: ["invalid"], widgets_values_named: { authoring_profile: core.FISHER } }, Node.prototype.onConfigure);
    assert.equal(field(node, "authoring_profile").value, core.CLASSIC);
    assert.equal(field(node, "local_model").value, "test-model.gguf");
    assert.equal(core.savedMossValues({ widgets_values: [...legacyValues], properties: marker() }).get("authoring_profile"), core.CLASSIC);
});

test("MOSS linked numeric nulls need actual saved-link evidence and never shift adjacent fields", () => {
    const defaults = { width: 1024, height: 1024, max_output_chars: 0, max_corrections: 1,
        llm_max_tokens: 16384, seed: 0, local_context_size: 32768, local_max_tokens: 16384 };
    for (const source of ["positional", "nativeNamed", "privateNamed"]) {
        const map = { ...legacyMap(), authoring_profile: core.FISHER };
        for (const name of Object.keys(defaults)) map[name] = null;
        const inputs = Object.keys(defaults).map((name, index) => ({ name, widget: { name }, link: index }));
        const data = { inputs, properties: marker() };
        if (source === "positional") data.widgets_values = core.MOSS_NAMES.map(name => map[name]);
        if (source === "nativeNamed") data.widgets_values_named = map;
        if (source === "privateNamed") data.properties[core.MOSS_STATE] = map;
        const before = JSON.stringify(data), node = new Node(); node.widgets.reverse();
        core.configureMoss(node, data, Node.prototype.onConfigure, [data]);
        for (const [name, value] of Object.entries(defaults)) assert.equal(field(node, name).value, value, `${source}:${name}`);
        assert.equal(field(node, "authoring_profile").value, core.FISHER);
        assert.equal(field(node, "local_model").value, "test-model.gguf");
        assert.deepEqual(node.inputs, inputs);
        assert.equal(JSON.stringify(data), before, "Migration does not mutate saved input data or links");
    }
    const values = [...legacyValues]; values[8] = null;
    for (const inputs of [undefined, [], [{ name: "max_output_chars", link: null }], [{ name: "width", link: 1 }]]) {
        assert.equal(core.savedMossValues({ widgets_values: values, inputs }), null);
    }
    assert.equal(core.savedMossValues({ widgets_values: [...legacyValues.slice(0, 8), false, ...legacyValues.slice(9)],
        inputs: [{ name: "max_output_chars", link: 1 }] }), null, "Links do not excuse invalid resolved literals");
});

test("MOSS saves exactly 28 named fields, version 2 and no Key/action tails after reordered reload", () => {
    const node = new Node(); field(node, "authoring_profile").value = core.COMIC; node.widgets.reverse();
    node.widgets.push({ name: "button", value: core.FISHER, serialize: false });
    const saved = {}; core.serializeMoss(node, saved);
    assert.deepEqual(saved.widgets_values.slice(0, 27), legacyValues);
    assert.equal(saved.widgets_values[27], core.COMIC);
    assert.deepEqual(Object.keys(saved.widgets_values_named), core.MOSS_NAMES);
    assert.deepEqual(saved.properties[core.MOSS_STATE], saved.widgets_values_named);
    assert.equal(saved.properties[core.MOSS_PROFILE_SCHEMA], 2);
    assert.equal(JSON.stringify(saved).includes("PRIVATE-KEY"), false);
    const restored = new Node(); restored.widgets.reverse();
    core.configureMoss(restored, saved, Node.prototype.onConfigure, [saved]);
    const again = {}; core.serializeMoss(restored, again);
    assert.deepEqual(again.widgets_values, saved.widgets_values);
});

test("MOSS description cap and profile are main controls without changing widget order or repeated layout", () => {
    const node = new Node(); core.refreshMoss(node);
    const baseline = node.size[1], names = node.widgets.map(widget => widget.name);
    for (let count = 0; count < 100; count++) {
        for (const profile of core.MOSS_PROFILES) {
            field(node, "authoring_profile").value = profile;
            core.refreshMoss(node);
            assert.equal(field(node, "max_output_chars").hidden, false);
            assert.equal(field(node, "authoring_profile").hidden, false);
            assert.equal(node.size[1], baseline);
        }
        field(node, "operation").value = core.COMPILE; core.refreshMoss(node);
        assert.equal(field(node, "max_output_chars").hidden, true);
        assert.equal(field(node, "authoring_profile").hidden, true);
        field(node, "operation").value = core.GENERATE; core.refreshMoss(node);
        assert.equal(node.size[1], baseline);
    }
    assert.deepEqual(node.widgets.map(widget => widget.name), names);
    assert.equal(field(node, "max_output_chars").value, 700);
});

test("MOSS actual configure hook restores profile synchronously and RAF cannot overwrite a user's new selection", async () => {
    let extension; const frames = [];
    const context = vm.createContext({ ...core, app: { registerExtension(value) { extension = value; } }, api: {}, window: {}, console,
        addCompletionRecoveryButton(node) { return node.addWidget("button", "Recovery", "", () => {}, { serialize: false }); },
        requestAnimationFrame(callback) { frames.push(callback); } });
    const code = (await readFile(new URL("../../web/js/moss_image_prompt_enhancer.js", import.meta.url), "utf8"))
        .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "");
    vm.runInContext(code, context);
    class Moss extends Node {}
    await extension.beforeRegisterNodeDef(Moss, { name: core.MOSS_ID });
    const node = new Moss(); node.onNodeCreated(); const count = node.widgets.length;
    node.onNodeCreated(); assert.equal(node.widgets.length, count);
    const saved = { widgets_values: [...legacyValues, core.COMIC], properties: marker() };
    assert.equal(node.onConfigure(saved), 31);
    assert.equal(field(node, "authoring_profile").value, core.COMIC);
    field(node, "authoring_profile").value = core.FISHER;
    field(node, "max_output_chars").value = 80;
    frames.splice(0).forEach(callback => callback());
    assert.equal(field(node, "authoring_profile").value, core.FISHER);
    assert.equal(field(node, "max_output_chars").value, 80);
    const output = {}; assert.equal(node.onSerialize(output), 37);
    assert.equal(output.widgets_values.length, 28);
    assert.equal(output.widgets_values[8], 80);
    assert.equal(output.widgets_values.at(-1), core.FISHER);
    for (const widget of node.widgets.filter(widget => widget.type === "button" && widget.name !== "Recovery")) {
        assert.equal(widget.options.serialize, false);
        assert.equal(widget.serialize, false);
        assert.equal(widget.serializeValue(), undefined);
    }
});

const lengthInfo = (extra = {}) => ({ metric: "unicode_code_points", description_chars: 1800, han_chars: 1600,
    max_output_chars: 0, target_han_range: [1500, 2500], status: "within_target", hard_enforced: false, ...extra });

test("MOSS status shows only historical finite profile and actual length, never a current widget setting", () => {
    const status = { origin: "cache", format: "caption", width: 1256, height: 1672, calls: 1,
        authoring_profile: core.FISHER, authoring_length: lengthInfo() };
    const text = core.mossStatus(status, true);
    assert.match(text, /上次结果/);
    assert.match(text, /Result profile: Fisher/);
    assert.match(text, /1800 码点/);
    assert.match(text, /1600 汉字/);
    assert.match(text, /Han target 1500–2500/);
    assert.match(text, /Token未核验/);
    assert.doesNotMatch(text, /Creative target unmet/);
    const cap = core.mossStatus({ ...status, authoring_profile: core.COMIC,
        authoring_length: lengthInfo({ description_chars: 90, han_chars: 70, max_output_chars: 80,
            target_han_range: null, status: "over_limit" }) });
    assert.match(cap, /Soft cap 80/);
    assert.match(cap, /Complete draft kept/);
    assert.doesNotMatch(cap, /1500–2500/);
    for (const [han, label] of [[500, "below_target"], [2600, "above_target"]]) {
        assert.match(core.mossStatus({ ...status, authoring_length: lengthInfo({ description_chars: 3000,
            han_chars: han, status: label }) }), /Creative target unmet/);
    }
    assert.doesNotMatch(core.mossStatus({ format: "caption", width: 1024, height: 1024, calls: 1 }), /Result profile|Actual:/,
        "Legacy results do not acquire a current profile or made-up count");
});

test("MOSS status ignores malformed authoring metadata, unknown keys and arbitrary profile/status text", () => {
    const base = { format: "caption", width: 1024, height: 1024, calls: 1,
        authoring_profile: core.FISHER, authoring_length: lengthInfo() };
    for (const profile of [null, [], {}, true, 3, "<script>PRIVATE</script>"]) {
        const text = core.mossStatus({ ...base, authoring_profile: profile });
        assert.doesNotMatch(text, /Result profile|Actual:|PRIVATE/);
    }
    const invalid = [null, [], "PRIVATE", true,
        lengthInfo({ metric: "tokens" }), lengthInfo({ description_chars: true }), lengthInfo({ description_chars: 262145 }),
        lengthInfo({ description_chars: 2.5 }), lengthInfo({ han_chars: false }), lengthInfo({ han_chars: 1801 }),
        lengthInfo({ max_output_chars: true }), lengthInfo({ max_output_chars: 20001 }), lengthInfo({ hard_enforced: true }),
        lengthInfo({ status: [] }), lengthInfo({ status: {} }), lengthInfo({ status: true }), lengthInfo({ status: "PRIVATE" }),
        lengthInfo({ status: "above_target" }), lengthInfo({ target_han_range: "PRIVATE" }),
        lengthInfo({ target_han_range: [true, 2500] }), lengthInfo({ target_han_range: [1500, 2500, 3000] }),
        lengthInfo({ target_han_range: undefined }), lengthInfo({ max_output_chars: 100 })];
    for (const info of invalid) {
        assert.doesNotThrow(() => core.mossStatus({ ...base, authoring_length: info }));
        const text = core.mossStatus({ ...base, authoring_length: info });
        assert.doesNotMatch(text, /Actual:|PRIVATE/);
    }
    const text = core.mossStatus({ ...base, private_context: "PRIVATE", authoring_length: lengthInfo({ secret: "PRIVATE" }) });
    assert.match(text, /Actual: 1800/);
    assert.doesNotMatch(text, /PRIVATE/);
    assert.doesNotMatch(core.mossStatus({ ...base, authoring_profile: core.COMIC }), /Actual:/,
        "A Comic result cannot claim the Fisher-only default Han target");
});
