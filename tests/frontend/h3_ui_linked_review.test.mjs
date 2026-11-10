import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import * as core from "../../web/js/h3_image_ui.mjs";
import { RECOVERY_SLOT_PROPERTY } from "../../web/js/completion_recovery_core.mjs";

const example = JSON.parse(await readFile(new URL("../../example_workflows/h3_image_t2i_example.json", import.meta.url), "utf8"));
const saved = example.nodes.find(node => node.type === core.ID);
const field = (node, name) => node.widgets.find(widget => widget.name === name);
function node() {
    return { widgets: core.NAMES.map(name => ({ name, value: saved.widgets_values_named[name],
        type: typeof saved.widgets_values_named[name] === "number" ? "number" : "text", computeSize: () => [500, 28],
        ...(typeof saved.widgets_values_named[name] === "string" ? { inputEl: { value: saved.widgets_values_named[name] } } : {}) })),
        properties: {}, inputs: [], native(data) {
            data.widgets_values.forEach((value, index) => { this.widgets[index].value = value; });
            return "native-result";
        } };
}

test("linked-null aspect ratio keeps the schema's auto fallback after disconnect", () => {
    const target = node(), data = structuredClone(saved);
    data.properties[core.STATE].aspect_ratio = null;
    data.widgets_values_named.aspect_ratio = null;
    data.widgets_values[core.NAMES.indexOf("aspect_ratio")] = null;
    data.inputs.push({ name: "aspect_ratio", widget: { name: "aspect_ratio" }, link: 88 });
    core.configure(target, data, target.native, [data]);
    target.inputs = []; // user disconnected the restored source
    assert.equal(field(target, "aspect_ratio").value, "auto");
    const result = {}; core.serialize(target, result);
    assert.equal(result.widgets_values_named.aspect_ratio, "auto");
});

test("nullable linked copy/model/baseURL reset only their own required literal fallback and reconnect cleanly", () => {
    for (const name of ["locked_text", "custom_model", "openai_base_url"]) {
        const target = node(), data = structuredClone(saved);
        data.properties[core.STATE][name] = null;
        data.properties[core.STATE].target_words = 1750;
        data.inputs.push({ name, widget: { name }, link: 88 });
        core.configure(target, data, target.native, [data]);
        assert.equal(field(target, name).value, "", name);
        assert.equal(field(target, "target_words").value, 1750, name);
        target.updateComputedDisabled = () => {};
        target.t8H3ImageAdvanced = true;
        field(target, "api_mode").value = core.MODES[2];
        field(target, name).element = { style: {} };
        target.inputs = [{ name, widget: { name }, link: 88 }];
        core.refresh(target);
        assert.equal(field(target, name).hidden, false, name);
        assert.equal(field(target, name).element.hidden, true, name);
        assert.equal(field(target, name).computeSize()[1], 20, name);
        target.inputs[0].link = null;
        core.refresh(target);
        assert.equal(field(target, name).hidden, false, name);
        assert.equal(field(target, name).element.hidden, false, name);
        assert.equal(field(target, name).type, "text", name);
        assert.equal(field(target, name).computeSize()[1], 28, name);
        field(target, name).value = "new literal";
        target.inputs[0].link = 99;
        core.refresh(target);
        assert.equal(field(target, name).computeSize()[1], 20, name);
        assert.equal(target.widgets.length, 22, name);
    }
});

test("provider and Advanced cycling keeps connected DOM rows and stable VM layout", () => {
    const target = node();
    target.updateComputedDisabled = () => {};
    target.inputs = [{ name: "prompt", link: 44 }, { name: "locked_text", link: 55 }];
    for (const name of ["prompt", "locked_text"]) field(target, name).element = { style: {} };
    target.size = [550, 0];
    target.computeSize = () => [550, 100 + target.widgets.reduce((sum, widget) => sum + (widget.computeSize?.()[1] || 0), 0)];
    target.setSize = size => { target.size = size; };
    const snapshots = new Map();
    for (let cycle = 0; cycle < 10; cycle++) for (const mode of core.MODES) for (const advanced of [false, true]) {
        field(target, "api_mode").value = mode; target.t8H3ImageAdvanced = advanced;
        core.refresh(target);
        for (const name of ["prompt", "locked_text"]) {
            assert.equal(field(target, name).hidden, false);
            assert.equal(field(target, name).computeSize()[1], 20);
            assert.equal(field(target, name).element.hidden, true);
        }
        const key = mode + ":" + advanced;
        if (snapshots.has(key)) assert.deepEqual(target.size, snapshots.get(key), key);
        else snapshots.set(key, [...target.size]);
    }
    assert.equal(target.widgets.length, 22);
});

test("canonical 22-field linked prompt null retains target/model and resets required literal brief only", () => {
    const target = node(), data = structuredClone(saved);
    data.properties[core.STATE].prompt = null;
    data.properties[core.STATE].target_words = 1700;
    data.properties[core.STATE].custom_model = "linked-model";
    data.inputs.push({ name: "prompt", widget: { name: "prompt" }, link: 88 });
    assert.equal(core.configure(target, data, target.native, [data]), "native-result");
    assert.equal(field(target, "prompt").value, "");
    assert.equal(field(target, "target_words").value, 1700);
    assert.equal(field(target, "custom_model").value, "linked-model");
});

const ROOT_A = "11111111-1111-4111-8111-111111111111";
const ROOT_B = "22222222-2222-4222-8222-222222222222";
function ownedNode(owner, slot = "t8-review-legacy-original") {
    const result = node();
    field(result, "recovery_slot").value = slot;
    result.properties[RECOVERY_SLOT_PROPERTY] = slot;
    if (owner) result.properties[core.OWNER_PROPERTY] = owner;
    return result;
}

test("workflow recovery owner invalidates unauthenticated legacy slots once and preserves same-workflow reload", () => {
    const target = ownedNode(), root = { id: ROOT_A, _nodes: [target], change() {} };
    target.graph = root;
    core.ensureWorkflowOwner(target, root);
    const newSlot = field(target, "recovery_slot").value;
    assert.notEqual(newSlot, "t8-review-legacy-original");
    assert.equal(target.properties[core.OWNER_PROPERTY], ROOT_A);
    core.ensureWorkflowOwner(target, root);
    assert.equal(field(target, "recovery_slot").value, newSlot);
    const reloaded = ownedNode(ROOT_A, newSlot), newRoot = { id: ROOT_A, _nodes: [reloaded], change() {} };
    reloaded.graph = newRoot;
    core.ensureWorkflowOwner(reloaded, newRoot);
    assert.equal(field(reloaded, "recovery_slot").value, newSlot);
});

test("new root workflow UUID rotates recovery slot and serialization synchronizes owner and both slot copies", () => {
    const target = ownedNode(ROOT_A), root = { id: ROOT_B, _nodes: [target], change() {} };
    target.graph = root;
    target.t8EnsureRecoverySlot = () => core.ensureWorkflowOwner(target, root);
    const serialized = { properties: { ...target.properties } }; // native took this snapshot before onSerialize
    core.serialize(target, serialized);
    assert.notEqual(serialized.widgets_values_named.recovery_slot, "t8-review-legacy-original");
    assert.equal(serialized.properties[core.OWNER_PROPERTY], ROOT_B);
    assert.equal(serialized.properties[RECOVERY_SLOT_PROPERTY], serialized.widgets_values_named.recovery_slot);
    assert.equal(serialized.properties[core.STATE].recovery_slot, serialized.widgets_values_named.recovery_slot);
    assert.equal(serialized.widgets_values.length, 22);
});

test("native and legacy child graphs bind recovery to their root workflow, never active canvas/local graph ID", () => {
    for (const kind of ["map", "container"]) {
        const target = ownedNode(ROOT_A), child = { id: "33333333-3333-4333-8333-333333333333", _nodes: [target] };
        const root = { id: ROOT_A, _nodes: [], change() {} }; target.graph = child;
        if (kind === "map") root.subgraphs = new Map([[child.id, child]]);
        else root._nodes.push({ subgraph: child });
        core.ensureWorkflowOwner(target, root);
        assert.equal(target.properties[core.OWNER_PROPERTY], ROOT_A, kind);
        assert.equal(field(target, "recovery_slot").value, "t8-review-legacy-original", kind);
        core.ensureWorkflowOwner(target, root);
        assert.equal(field(target, "recovery_slot").value, "t8-review-legacy-original", kind);
    }
});

test("unattached recovery nodes defer owner binding until present under the intended root", () => {
    const target = ownedNode(ROOT_A), root = { id: ROOT_B, _nodes: [], change() {} };
    core.ensureWorkflowOwner(target, root);
    assert.equal(target.properties[core.OWNER_PROPERTY], ROOT_A);
    assert.equal(field(target, "recovery_slot").value, "t8-review-legacy-original");
    target.graph = { id: ROOT_A, _nodes: [target] };
    core.ensureWorkflowOwner(target, root);
    assert.equal(field(target, "recovery_slot").value, "t8-review-legacy-original");
    target.graph = root; root._nodes.push(target);
    core.ensureWorkflowOwner(target, root);
    assert.equal(target.properties[core.OWNER_PROPERTY], ROOT_B);
    assert.notEqual(field(target, "recovery_slot").value, "t8-review-legacy-original");
});
