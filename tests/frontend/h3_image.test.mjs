import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import * as ui from "../../web/js/h3_image_ui.mjs";

const workflow = JSON.parse(await readFile(new URL("../../example_workflows/h3_image_t2i_example.json", import.meta.url), "utf8"));
const saved = workflow.nodes.find(n => n.type === ui.ID);
const defaults = saved.widgets_values_named;
class Node {
    constructor() {
        this.widgets = ui.NAMES.map(name => ({ name, value: defaults[name], type: "text", computeSize: () => [550, 28],
            ...(typeof defaults[name] === "string" ? { inputEl: { value: defaults[name] } } : {}) }));
        this.widgets.push({ name: "api_key", value: "PRIVATE-KEY", type: "text" }, { name: "Help", value: "button tail", type: "button" });
        this.inputs = []; this.size = [550, 500]; this.properties = {};
    }
    onConfigure(data) {
        data.widgets_values.forEach((value, index) => { if (this.widgets[index]) this.widgets[index].value = value; }); return 17;
    }
    computeSize() { return [550, 200 + this.widgets.reduce((s, w) => s + (w.computeSize?.()[1] ?? 28), 0)]; }
    setSize(size) { this.size = size; }
    setDirtyCanvas() {}
}
const get = (node, name) => node.widgets.find(w => w.name === name);

test("H3 Image canonical state restores reordered runtime before native positional application", () => {
    const node = new Node(); node.widgets.reverse();
    assert.equal(ui.configure(node, saved, node.onConfigure, [saved]), 17);
    for (const name of ui.NAMES) assert.equal(get(node, name).value, defaults[name], name);
    assert.equal(get(node, "api_key").value, "");
    const result = {}; ui.serialize(node, result);
    assert.equal(result.widgets_values.length, 22);
    assert.deepEqual(result.widgets_values_named, defaults);
    assert(!JSON.stringify(result).includes("PRIVATE-KEY")); assert(!JSON.stringify(result).includes("button tail"));
});

test("H3 Image native named/positional states and unblurred provider input survive", () => {
    for (const data of [{ widgets_values: saved.widgets_values }, { widgets_values_named: defaults }]) {
        const node = new Node(); ui.configure(node, data, node.onConfigure, [data]);
        get(node, "target_words").value = 20000;
        get(node, "openai_base_url").inputEl.value = "http://127.0.0.1:12345/v1";
        get(node, "custom_model").inputEl.value = "unblurred-model";
        const result = {}; ui.serialize(node, result);
        assert.equal(result.widgets_values_named.target_words, 20000);
        assert.equal(result.widgets_values_named.openai_base_url, "http://127.0.0.1:12345/v1");
        assert.equal(result.widgets_values_named.custom_model, "unblurred-model");
    }
});

test("H3 Image linked nulls require link evidence and bad positional arrays cannot shift controls", () => {
    const node = new Node(), data = structuredClone(saved);
    for (const name of ["prompt", "aspect_ratio", "target_words"]) {
        data.properties[ui.STATE][name] = null;
        data.inputs.push({ name, type: name === "target_words" ? "INT" : "STRING", link: 11 });
    }
    ui.configure(node, data, node.onConfigure, [data]);
    assert.equal(get(node, "prompt").value, ""); assert.equal(get(node, "target_words").value, 0);
    const bad = { widgets_values: ["wrong", ...saved.widgets_values] };
    get(node, "task_type").value = ui.EDIT;
    ui.configure(node, bad, node.onConfigure, [bad]);
    assert.equal(get(node, "task_type").value, ui.EDIT);
});

test("H3 Image effective provider follows reroute without loops and budgets are mutually visible", () => {
    const node = new Node(), config = { widgets: [{ name: "provider", value: "Local Qwen" }] };
    const reroute = { type: "Reroute", inputs: [{ link: 2 }] };
    node.inputs = [{ name: "provider_config", link: 1 }];
    node.graph = { links: { 1: { origin_id: 2 }, 2: { origin_id: 3 } }, getNodeById: id => id === 2 ? reroute : config };
    node.t8H3ImageAdvanced = true; ui.refresh(node);
    assert.equal(ui.effectiveMode(node), ui.MODES[3]); assert.equal(get(node, "local_max_tokens").hidden, false);
    assert.equal(get(node, "llm_max_tokens").hidden, true);
    config.widgets[0].value = "OpenAI Compatible"; ui.refresh(node);
    assert.equal(get(node, "local_max_tokens").hidden, true); assert.equal(get(node, "llm_max_tokens").hidden, false);
    const height = node.size[1]; for (let i = 0; i < 10; i++) ui.refresh(node);
    assert.equal(node.size[1], height);
    node.graph.links[2].origin_id = 2; assert.equal(ui.linkedProvider(node), null);
});

test("H3 Image coexisting connected DOM rows keep socket geometry, legacy conversion stays host-owned", () => {
    const node = new Node(), prompt = get(node, "prompt");
    node.updateComputedDisabled = () => {}; node.inputs = [{ name: "prompt", link: 7 }]; prompt.element = { style: {} };
    ui.refresh(node);
    assert.equal(prompt.hidden, false); assert.equal(prompt.computeSize()[1], 20); assert.equal(prompt.element.hidden, true);
    const other = new Node(), old = get(other, "prompt");
    other.inputs = [{ name: "prompt", link: 7 }]; old.origType = "text"; old.type = "converted-widget";
    const native = () => "host-value"; old.serializeValue = native;
    ui.refresh(other); assert.equal(old.type, "converted-widget"); assert.equal(old.serializeValue, native);
});

test("Both published H3 Image examples wire the caption preview and keep 22 widgets", async () => {
    for (const mode of ["t2i", "edit"]) {
        const data = JSON.parse(await readFile(new URL(`../../example_workflows/h3_image_${mode}_example.json`, import.meta.url), "utf8"));
        const main = data.nodes.find(n => n.type === ui.ID);
        assert.equal(main.widgets_values.length, ui.NAMES.length);
        assert.deepEqual(Object.keys(main.widgets_values_named), ui.NAMES);
        assert(data.links.some(l => l[1] === main.id && l[2] === 0 && data.nodes.find(n => n.id === l[3])?.type === "T8ShowText"));
        assert.equal(data.nodes.filter(n => n.type === "LoadImage").length, mode === "edit" ? 2 : 0);
        assert.equal(data.nodes.find(n => n.type === "T8PromptText").widgets_values[0], "");
    }
});
