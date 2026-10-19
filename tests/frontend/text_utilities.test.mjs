import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFile } from "node:fs/promises";

const source = (await readFile(new URL("../../web/js/text_utilities.js", import.meta.url), "utf8"))
    .replace(/^import .*;$/gm, "");

async function fixture() {
    let extension, copied, failCopy = false, execSuccess = true, commands = 0;
    const timers = new Map(), events = new Map();
    let timerId = 0;
    const document = {
        activeElement: null,
        createElement(tag) {
            let value = "";
            return { tag, style: {}, children: [], listeners: {}, readOnly: false,
                get value() { return value; }, set value(next) { value = String(next).replace(/\r\n?/g, "\n"); },
                setAttribute() {}, append(...nodes) { this.children.push(...nodes); },
                addEventListener(name, fn) { this.listeners[name] = fn; },
                focus() { document.activeElement = this; }, select() {}, remove() {},
            };
        },
        body: { append() {} },
        addEventListener(name, fn) { events.set(name, fn); },
        removeEventListener(name, fn) { if (events.get(name) === fn) events.delete(name); },
        execCommand(name) {
            commands++; assert.equal(name, "copy");
            if (execSuccess) events.get("copy")?.({ clipboardData: { setData(type, value) { assert.equal(type, "text/plain"); copied = value; } }, preventDefault() {} });
            return execSuccess;
        },
    };
    const navigator = { clipboard: { async writeText(value) { if (failCopy) throw new Error("denied"); copied = value; } } };
    const app = { registerExtension(value) { extension = value; } };
    const context = vm.createContext({ app, document, navigator, console,
        window: { setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); } },
    });
    vm.runInContext(source, context);
    class Node {
        constructor(id = 1) { this.id = id; this.type = "T8ShowText"; this.widgets = []; this.size = [400, 300]; this.properties = {}; }
        onNodeCreated() { this.created = (this.created || 0) + 1; return "created"; }
        onExecuted() { this.executed = (this.executed || 0) + 1; return "executed"; }
        onRemoved() { this.removed = (this.removed || 0) + 1; return "removed"; }
        addDOMWidget(name, type, root, options) { const widget = { name, type, root, options }; this.widgets.push(widget); return widget; }
        setDirtyCanvas() {}
    }
    await extension.beforeRegisterNodeDef(Node, { name: "T8ShowText" });
    const node = new Node(); node.onNodeCreated();
    const graph = (nodes, id) => ({ nodes, id, getNodeById(key) { return nodes.find(node => String(node.id) === String(key)); } });
    app.rootGraph = graph([node], "root"); app.graph = app.rootGraph;
    return { app, extension, Node, node, graph, navigator, document, timers, events,
        copy: () => node.__t8TextPreview.copy.listeners.click(),
        copied: () => copied, commands: () => commands,
        deny: () => { failCopy = true; }, execFail: () => { execSuccess = false; },
        flush: () => { for (const [id, fn] of [...timers]) { timers.delete(id); fn(); } },
    };
}

test("execution and restored snapshots share read-only nonserialized preview; old callbacks and size preserved", async () => {
    const f = await fixture(), state = f.node.__t8TextPreview;
    assert.equal(f.node.onExecuted({ text: ["first", "second"] }), "executed");
    assert.equal(state.textarea.value, "first\nsecond");
    f.extension.onNodeOutputsUpdated({ 1: { text: ["restored"] } });
    assert.equal(state.textarea.value, "restored");
    assert.equal(state.textarea.readOnly, true); assert.equal(state.widget.options.serialize, false);
    assert.equal(state.widget.serialize, false); assert.equal(state.widget.serializeValue(), undefined);
    assert.deepEqual(f.node.size, [400, 300]); assert.deepEqual(f.node.properties, {});
    assert.equal(f.node.executed, 1, "Restoration is not another execution callback");
    assert.equal(f.node.widgets.length, 1);
});

test("bare root ID never targets the active subgraph or sibling with the same local ID", async () => {
    const f = await fixture(), sub = new f.Node(1), other = new f.Node(1);
    const g = f.graph([sub], "sub-a"), h = f.graph([other], "sub-b");
    f.app.rootGraph.subgraphs = new Map([[g.id, g], [h.id, h]]);
    f.app.canvas = { graph: g }; f.app.graph = g;
    f.extension.onNodeOutputsUpdated({ 1: { text: ["root"] }, "sub-a:1": { text: ["A"] }, "sub-b:1": { text: ["B"] } });
    assert.equal(f.node.__t8TextPreview.rawText, "root");
    assert.equal(sub.__t8TextPreview.rawText, "A"); assert.equal(other.__t8TextPreview.rawText, "B");
    f.extension.onNodeOutputsUpdated({ "missing:1": { text: ["leak"] } });
    assert.equal(sub.__t8TextPreview.rawText, ""); assert.equal(f.node.__t8TextPreview.rawText, "");
});

test("legacy nested execution paths and encoded locator IDs resolve exact graph ownership", async () => {
    const f = await fixture(), nested = new f.Node("special:id"), sub = new f.Node(1);
    const g = f.graph([sub, nested], "12345678-1234-1234-1234-123456789abc");
    f.app.rootGraph.nodes.push({ id: 10, subgraph: g });
    f.extension.onNodeOutputsUpdated({ "10:1": { text: ["legacy"] }, [`~subgraph:${g.id}:special%3Aid`]: { text: ["encoded"] } });
    assert.equal(sub.__t8TextPreview.rawText, "legacy"); assert.equal(nested.__t8TextPreview.rawText, "encoded");
    f.node.id = "root:id";
    f.extension.onNodeOutputsUpdated({ "~root:root%3Aid": { text: ["root encoded"] }, "~root:%ZZ": { text: ["bad"] } });
    assert.equal(f.node.__t8TextPreview.rawText, "root encoded");
});

test("workflow replacement, empty output/reset, missing graph and cyclic/shared definitions remain safe", async () => {
    const f = await fixture();
    f.node.onExecuted({ text: ["A"] });
    const b = new f.Node(); f.app.rootGraph = f.graph([b]);
    f.extension.onNodeOutputsUpdated({ 1: { text: ["B"] } });
    assert.equal(b.__t8TextPreview.rawText, "B"); assert.equal(f.node.__t8TextPreview.rawText, "A");
    f.app.rootGraph.nodes.push({ subgraph: f.app.rootGraph });
    f.extension.onNodeOutputsUpdated({}); assert.equal(b.__t8TextPreview.rawText, "");
    f.extension.onNodeOutputsUpdated({ 1: { images: [] } }); assert.equal(b.__t8TextPreview.rawText, "");
    f.app.rootGraph = f.app.graph = null; f.extension.onNodeOutputsUpdated({});
});

test("normalization preserves raw CRLF, empty/null arrays, JSON and literal HTML without executing markup", async () => {
    const f = await fixture();
    f.node.onExecuted({ text: ["a\r\nb\r\n<script>not executable</script>"] });
    assert.equal(f.node.__t8TextPreview.textarea.value, "a\nb\n<script>not executable</script>");
    await f.copy(); assert.equal(f.copied(), "a\r\nb\r\n<script>not executable</script>");
    f.node.onExecuted({ text: [null, 0, false, { a: 1 }] });
    assert.equal(f.node.__t8TextPreview.rawText, '0\nfalse\n{\n  "a": 1\n}');
    f.node.onExecuted({ text: [] }); assert.equal(f.node.__t8TextPreview.rawText, "");
});

test("denied or absent Clipboard API falls back to raw copy event, preserving focus and removing listeners", async () => {
    for (const absent of [false, true]) {
        const f = await fixture(); f.node.onExecuted({ text: ["a\r\nb"] });
        if (absent) delete f.navigator.clipboard; else f.deny();
        let focus = 0, selection;
        const active = { focus() { focus++; }, selectionStart: 2, selectionEnd: 4, selectionDirection: "backward", setSelectionRange(...args) { selection = args; } };
        f.document.activeElement = active;
        await f.copy(); assert.equal(f.copied(), "a\r\nb"); assert.equal(f.commands(), 1);
        assert.equal(f.node.__t8TextPreview.copy.textContent, "已复制"); assert.equal(focus, 1);
        assert.deepEqual(selection, [2, 4, "backward"]); assert.equal(f.events.size, 0);
    }
});

test("failed fallback gives actionable feedback, never falsely reports copied", async () => {
    const f = await fixture(); f.deny(); f.execFail(); await f.copy();
    assert.match(f.node.__t8TextPreview.copy.textContent, /复制失败/);
    assert.equal(f.node.__t8TextPreview.copy.disabled, false); assert.equal(f.events.size, 0);
    f.flush(); assert.equal(f.node.__t8TextPreview.copy.textContent, "复制显示内容");
});

test("rapid copies restart one fixed-label timer and overlapping pending requests are ignored", async () => {
    const f = await fixture(); let release, calls = 0;
    f.navigator.clipboard.writeText = () => { calls++; return new Promise(done => { release = done; }); };
    const first = f.copy(); await f.copy(); assert.equal(calls, 1);
    assert.equal(f.node.__t8TextPreview.copy.disabled, true); release(); await first;
    assert.equal(f.timers.size, 1);
    const second = f.copy(); assert.equal(f.timers.size, 0); release(); await second;
    assert.equal(f.timers.size, 1); f.flush();
    assert.equal(f.node.__t8TextPreview.copy.textContent, "复制显示内容");
});

test("changed output and removed node suppress stale asynchronous copy feedback and cleanup timers", async () => {
    const f = await fixture(); let release;
    f.navigator.clipboard.writeText = () => new Promise(done => { release = done; });
    const pending = f.copy(); f.node.onExecuted({ text: ["new"] }); release(); await pending;
    assert.equal(f.node.__t8TextPreview.copy.textContent, "复制显示内容");
    const removed = f.copy(); assert.equal(f.node.onRemoved(), "removed"); release(); await removed;
    assert.equal(f.timers.size, 0); assert.equal(f.node.removed, 1);
    f.node.onAdded();
    f.navigator.clipboard.writeText = async () => {};
    await f.copy(); assert.equal(f.node.__t8TextPreview.copy.textContent, "已复制", "Reattached node can copy again");
});

test("duplicate extension registration does not duplicate widgets or host callbacks and ignores unrelated types", async () => {
    const f = await fixture(); await f.extension.beforeRegisterNodeDef(f.Node, { name: "T8ShowText" });
    f.node.onNodeCreated(); f.node.onExecuted({ text: ["x"] });
    assert.equal(f.node.widgets.length, 1); assert.equal(f.node.created, 2); assert.equal(f.node.executed, 1);
    const foreign = { prototype: {} }; await f.extension.beforeRegisterNodeDef(foreign, { name: "Other" });
    assert.deepEqual(foreign.prototype, {});
});
