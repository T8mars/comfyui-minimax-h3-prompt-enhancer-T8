import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import * as widgetState from "../../web/js/widget_state.mjs";
import { RECOVERY_SLOT_PROPERTY } from "../../web/js/completion_recovery_core.mjs";

async function harness() {
    const frames = [];
    let extension;
    const context = vm.createContext({ ...widgetState, RECOVERY_SLOT_PROPERTY,
        app: { registerExtension(value) { extension = value; } },
        requestAnimationFrame(callback) { frames.push(callback); },
    });
    const source = (await readFile(new URL("../../web/js/qwen_image21_prompt_enhancer.js", import.meta.url), "utf8"))
        .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*$/gm, "")
        .replace(/^export\s+/gm, "").replaceAll("import.meta.url", '"https://example.test/extension.js"');
    vm.runInContext(`${source}\nglobalThis.names = SERIALIZED_WIDGET_NAMES;`, context);
    const names = [...context.names];
    class Node {
        constructor() { this.widgets = names.map(name => ({ name, value: null })); this.properties = {}; }
        onConfigure(data) {
            data.widgets_values?.forEach((value, index) => { if (this.widgets[index]) this.widgets[index].value = value; });
            for (const widget of this.widgets) {
                if (Object.hasOwn(data.widgets_values_named || {}, widget.name)) widget.value = data.widgets_values_named[widget.name];
            }
        }
        onSerialize(data) { data.widgets_values_named = Object.fromEntries(this.widgets.map(w => [w.name, w.value])); }
    }
    await extension.beforeRegisterNodeDef(Node, { name: "QwenImage21PromptEnhancerT8" });
    return { Node, names, frames };
}

// Sanitized structure from the reporter's attached JSON, not a guessed layout.
const current = ["teapot brief", "文生图 / Text-to-image", 0, "auto", false,
    "OpenAI兼容接口（备用）", "Custom（自定义）", "vendor/model", "https://example.test/v1",
    0, "randomize", "Qwen3.8-27B-Q4_K_M.gguf", "AUTO（自动匹配）", 32768, 16384,
    "关闭（推荐，速度优先）", "medium", 2, "执行后卸载（推荐）", "AUTO（显存不足时释放）", "t8-test-slot", "normal"];

test("#21 extra key slot after Base URL overrides corrupted native named map before RAF", async () => {
    const { Node, names } = await harness();
    const legacy = [...current];
    legacy.splice(9, 0, "");
    legacy.push("provider tooltip", "recovery tooltip");
    const data = { widgets_values: legacy, widgets_values_named: Object.fromEntries(names.map((name, i) => [name, legacy[i]])) };
    const node = new Node();
    node.onConfigure(data);
    for (const name of ["seed", "control_after_generate", "local_model", "local_mmproj", "local_context_size", "local_max_tokens"]) {
        assert.equal(node.widgets.find(w => w.name === name).value, current[names.indexOf(name)], name);
    }
    assert.equal(data.widgets_values_named.seed, "", "do not mutate the caller's workflow");
});

test("Qwen serializer keeps native named and stable positional maps consistent and omits UI/key", async () => {
    const { Node, names } = await harness();
    const node = new Node();
    current.forEach((value, i) => { node.widgets[i].value = value; });
    node.widgets.push({ name: "button tooltip", value: "not a schema field" });
    node.widgets.push({ name: "api_key", value: "private test value" });
    const saved = {};
    node.onSerialize(saved);
    assert.deepEqual(Object.keys(saved.widgets_values_named), names);
    names.forEach((name, i) => assert.equal(saved.widgets_values_named[name], saved.widgets_values[i], name));
    const reloaded = new Node();
    reloaded.onConfigure(saved);
    assert.equal(reloaded.widgets.find(w => w.name === "seed").value, 0);
    assert.equal(reloaded.widgets.find(w => w.name === "local_model").value, current[11]);
});

const classic = "经典兼容 / Classic";
const editAware = "编辑专用（T8）/ Edit-aware";
const schemaKey = "t8_qwen_image21_widgets_schema";

test("new profile appends to the frozen 22-field order and survives a versioned reload before RAF", async () => {
    const { Node, names } = await harness();
    assert.equal(names.length, 23);
    assert.equal(names.at(-1), "rewrite_profile");
    const node = new Node();
    [...current, editAware].forEach((value, i) => { node.widgets[i].value = value; });
    const saved = {};
    node.onSerialize(saved);
    assert.equal(saved.properties[schemaKey], 2);
    assert.deepEqual([...saved.widgets_values].slice(0, 22), current);
    const reload = new Node();
    reload.widgets.reverse(); // The native runtime order is not the saved order.
    reload.onConfigure({ ...saved, widgets_values: [...saved.widgets_values, "trailing button"] });
    assert.equal(reload.widgets.find(w => w.name === "rewrite_profile").value, editAware);
    assert.equal(reload.widgets.find(w => w.name === "api_mode").value, current[5]);
    assert.equal(reload.widgets.find(w => w.name === "seed").value, 0);
});

test("old workflows always default Classic even when a button tail resembles the new choice", async () => {
    const { Node } = await harness();
    for (const values of [current, [...current, editAware], current.slice(0, 20),
                          [...current.slice(0, 20), "tooltip", "normal", editAware]]) {
        const node = new Node();
        node.widgets.find(w => w.name === "rewrite_profile").value = editAware;
        node.onConfigure({ widgets_values: values });
        assert.equal(node.widgets.find(w => w.name === "rewrite_profile").value, classic);
        assert.equal(node.widgets.find(w => w.name === "seed").value, 0);
    }
});

test("consistent native named metadata retains new choice if host strips schema marker", async () => {
    const { Node, names } = await harness();
    const values = [...current, editAware];
    const node = new Node();
    node.onConfigure({ widgets_values: values, widgets_values_named: Object.fromEntries(names.map((name, i) => [name, values[i]])) });
    assert.equal(node.widgets.find(w => w.name === "rewrite_profile").value, editAware);
});

test("deferred layout work does not overwrite a selection made immediately after loading", async () => {
    const { Node, frames } = await harness();
    const node = new Node();
    node.onConfigure({ widgets_values: current });
    node.widgets.find(w => w.name === "rewrite_profile").value = editAware;
    node.widgets.find(w => w.name === "seed").value = 42;
    frames.splice(0).forEach(callback => callback());
    assert.equal(node.widgets.find(w => w.name === "rewrite_profile").value, editAware);
    assert.equal(node.widgets.find(w => w.name === "seed").value, 42);
});

test("versioned key/omitted linked prompt/seed control migrations preserve new choice", async () => {
    const { Node } = await harness();
    for (const location of ["beforeApi", "beforeSeed", "noPrompt", "noControl"]) {
        const values = [...current, editAware];
        if (location === "beforeApi") values.splice(5, 0, "");
        if (location === "beforeSeed") values.splice(9, 0, "");
        if (location === "noPrompt") values.shift();
        if (location === "noControl") values.splice(10, 1);
        const node = new Node();
        node.onConfigure({ widgets_values: values, properties: { [schemaKey]: 2 } });
        assert.equal(node.widgets.find(w => w.name === "rewrite_profile").value, editAware, location);
        assert.equal(node.widgets.find(w => w.name === "local_model").value, current[11], location);
        assert.equal(node.widgets.find(w => w.name === "seed").value, 0, location);
    }
});
