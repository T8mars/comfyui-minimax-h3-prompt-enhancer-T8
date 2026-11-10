import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import * as ui from "../../web/js/h3_image_ui.mjs";

const workflow = JSON.parse(await readFile(new URL("../../example_workflows/h3_image_t2i_example.json", import.meta.url), "utf8"));
const saved = workflow.nodes.find(n => n.type === ui.ID);
function make() {
    const node = { widgets: ui.NAMES.map(name => ({ name, value: saved.widgets_values_named[name],
        ...(typeof saved.widgets_values_named[name] === "string" ? { inputEl: { value: saved.widgets_values_named[name] } } : {}) })), inputs: [], properties: {} };
    node.native = function (data) { data.widgets_values.forEach((value, i) => { this.widgets[i].value = value; }); };
    return node;
}
const get = (node, key) => node.widgets.find(w => w.name === key);

test("H3 Image malformed private state falls back to complete valid native named state", () => {
    const data = structuredClone(saved);
    data.properties[ui.STATE] = { broken: true };
    data.widgets_values_named.target_words = 1500;
    data.widgets_values_named.prompt = "Native named brief must survive.";
    const node = make();
    ui.configure(node, data, node.native, [data]);
    assert.equal(get(node, "target_words").value, 1500);
    assert.equal(get(node, "prompt").value, "Native named brief must survive.");
});

test("H3 Image valid reordered values synchronize native widgets and live text controls", () => {
    const node = make(); node.widgets.reverse();
    const data = structuredClone(saved);
    data.properties[ui.STATE].openai_base_url = "http://127.0.0.1:8899/v1";
    data.properties[ui.STATE].custom_model = "new-model";
    data.properties[ui.STATE].prompt = "Restored prompt.";
    ui.configure(node, data, node.native, [data]);
    for (const name of ["openai_base_url", "custom_model", "prompt"]) {
        assert.equal(get(node, name).value, data.properties[ui.STATE][name]);
        assert.equal(get(node, name).inputEl.value, data.properties[ui.STATE][name]);
    }
    const output = {}; ui.serialize(node, output);
    assert.equal(output.widgets_values_named.prompt, "Restored prompt.");
    assert.equal(output.widgets_values_named.custom_model, "new-model");
});

test("H3 Image all linked null placeholders preserve the other saved controls", () => {
    for (const field of ["prompt", "task_type", "aspect_ratio", "target_words", "api_mode", "locked_text", "max_corrections", "llm_max_tokens", "custom_model", "openai_base_url", "seed"]) {
        const data = structuredClone(saved), node = make();
        data.properties[ui.STATE].target_words = 1750;
        data.properties[ui.STATE][field] = null;
        data.inputs.push({ name: field, link: 9 });
        ui.configure(node, data, node.native, [data]);
        if (field !== "target_words") assert.equal(get(node, "target_words").value, 1750, field);
        assert.equal(get(node, "task_type").value, ui.T2I, field);
    }
});

test("H3 Image external typed provider is labeled unresolved through reroutes, then reverts on disconnect", () => {
    const node = make(), external = { type: "ExternalConfigProducer", widgets: [], outputs: [{ type: "T8_LLM_PROVIDER_CONFIG" }] };
    const reroute = { type: "Reroute", inputs: [{ link: 1 }] };
    node.inputs = [{ name: "provider_config", link: 2 }];
    node.graph = { links: new Map([[1, { origin_id: 10 }], [2, { origin_id: 20 }]]), getNodeById: id => id === 10 ? external : reroute };
    assert.match(ui.providerLabel(node), /执行时确定/);
    assert(!ui.providerLabel(node).includes(ui.MODES[0]));
    external.widgets.push({ name: "provider", value: "Strata" });
    assert(ui.providerLabel(node).includes(ui.MODES[4]));
    node.inputs[0].link = null;
    assert(ui.providerLabel(node).includes(ui.MODES[0]));
});
