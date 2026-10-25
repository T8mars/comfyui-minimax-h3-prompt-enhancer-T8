import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import * as core from '../../web/js/visual_style_ui.mjs';
import {visualStyleSelectionMessage} from '../../web/js/completion_recovery_core.mjs';

const values = kind => kind === 'color' ? {mode: core.ON, palette: '181 历史名称 / Historical label', scope: core.SCOPES[1]} : {mode: core.ON, creator: '022 历史名称 / Historical label'};
function node(kind, reverse = false) {
    const names = core.fields(kind), v = values(kind);
    return {widgets: (reverse ? [...names].reverse() : names).map(name => ({name, value: v[name], type: 'combo'})), properties: {},
        addWidget(type, name, value, callback, options) {const w = {type, name, value, callback, options}; this.widgets.push(w); return w;}};
}
test('visual style exact saved order excludes action and preserves unknown historical selection', () => {
    for (const kind of ['color', 'creator']) {
        const n = node(kind, true); n.addWidget('button', 'browse', 'not data', null, {serialize: false});
        const data = {}; core.serializeStyle(n, data, kind);
        assert.deepEqual(data.widgets_values, core.fields(kind).map(name => values(kind)[name]));
        assert.deepEqual(data.widgets_values_named, values(kind));
        const restored = node(kind);
        core.configureStyle(restored, data, kind, function(info) {info.widgets_values.forEach((v, i) => this.widgets[i].value = v);}, [data]);
        assert.deepEqual(restored.widgets.map(w => w.value), data.widgets_values);
        for (const source of ['private', 'native', 'positional']) {
            const raw = structuredClone(data), reordered = node(kind, true);
            if (source !== 'private') raw.properties = {};
            if (source === 'positional') raw.widgets_values_named = {};
            core.configureStyle(reordered, raw, kind, function(info) {info.widgets_values.forEach((v, i) => this.widgets[i].value = v);}, [raw]);
            assert.deepEqual(Object.fromEntries(reordered.widgets.map(w => [w.name, w.value])), values(kind));
        }
    }
});
test('visual style corrupted maps fall back only to a valid layout; action tail cannot enable', () => {
    for (const kind of ['color', 'creator']) {
        const n = node(kind), data = {};
        core.serializeStyle(n, data, kind);
        data.properties[`t8_${kind}_style_widgets_v1`] = {mode: core.ON};
        data.widgets_values_named = Object.fromEntries(core.fields(kind).map(n => [n, null]));
        const restored = node(kind, true);
        core.configureStyle(restored, data, kind);
        assert.deepEqual(Object.fromEntries(restored.widgets.map(w => [w.name, w.value])), values(kind));
        data.widgets_values.push('browse');
        core.configureStyle(restored, data, kind);
        assert.equal(core.valueOf(restored, 'mode'), core.OFF);
        assert.equal(core.valueOf(restored, kind === 'color' ? 'palette' : 'creator'), core.NONE);
    }
});
test('browser ownership never resolves root/subgraph nodes by shared bare ID', () => {
    const a = {id: 7}, b = {id: 7}, graph = {getNodeById: () => a}, root = {_nodes: [{subgraph: graph}]}; a.graph = graph;
    assert.equal(core.ownerIsCurrent(a, graph, root, root), true);
    assert.equal(core.ownerIsCurrent(a, graph, root, {}), false);
    graph.getNodeById = () => b;
    assert.equal(core.ownerIsCurrent(a, graph, root, root), false);
    graph.getNodeById = () => a; a.graph = {};
    assert.equal(core.ownerIsCurrent(a, graph, root, root), false);
});

test('browser ownership requires root reachability while retaining registered shared definitions', () => {
    const makeGraph = () => ({_nodes: [], subgraphs: new Map(), getNodeById(id) {return this._nodes.find(n => n.id === id);}});
    const root = makeGraph(), nested = makeGraph(), deep = makeGraph();
    const a = {id: 7, graph: root}, b = {id: 7, graph: deep};
    root._nodes.push(a, {id: 8, subgraph: nested}); nested._nodes.push({id: 9, subgraph: deep}); deep._nodes.push(b);
    assert.equal(core.ownerIsCurrent(a, root, root, root), true);
    assert.equal(core.ownerIsCurrent(b, deep, root, root), true);
    assert.equal(core.ownerIsCurrent(b, root, root, root), false);
    // A nested cycle must terminate and cannot make a detached graph current.
    deep._nodes.push({id: 10, subgraph: root});
    root._nodes.pop();
    assert.equal(core.ownerIsCurrent(b, deep, root, root), false);
    // Hosts can retain a shared subgraph definition after its last canvas instance.
    root.subgraphs.set('retained-definition', nested);
    assert.equal(core.ownerIsCurrent(b, deep, root, root), true);
    root.subgraphs.delete('retained-definition');
    root.subgraphs.set('self-cycle', root);
    assert.equal(core.ownerIsCurrent(b, deep, root, root), false);
    assert.equal(core.ownerIsCurrent(a, root, root, {}), false);
    assert.equal(core.ownerIsCurrent(a, root, root, root), true);
    root._nodes[0] = {id: 7, graph: root};
    assert.equal(core.ownerIsCurrent(a, root, root, root), false);
});
test('browser category, bilingual name and ID filters are local and nonmutating', () => {
    const entries = [{id: '001', label_zh: '甲', label_en: 'Alpha', category: 'A'}, {id: '002', label_zh: '乙', label_en: 'Beta', category: 'B'}];
    assert.deepEqual(core.filterEntries(entries, '', 'alpHA'), [entries[0]]);
    assert.deepEqual(core.filterEntries(entries, 'B', '乙'), [entries[1]]);
    assert.deepEqual(core.filterEntries(entries, '', '002'), [entries[1]]);
    assert.deepEqual(core.filterEntries(entries, 'A', 'Beta'), []);
    assert.equal(entries.length, 2);
    assert.deepEqual(core.filterEntries([{id: '181', label_zh: '小津', label_en: 'YasujiroOzu', category: 'A'}], '', 'Yasujiro Ozu').map(v => v.id), ['181']);
});
test('actual extension installs once and keeps complete runtime widget counts 4/3', async () => {
    let extension;
    const code = (await readFile(new URL('../../web/js/visual_style_config.js', import.meta.url), 'utf8'))
        .replace(/^import .*;\r?\n/gm, '').replace('export function openStyleBrowser', 'function openStyleBrowser');
    vm.runInNewContext(code, {...core, app: {registerExtension(e) {extension = e;}}, api: {}});
    for (const [name, kind] of Object.entries(core.KINDS)) {
        function Node() {Object.assign(this, node(kind, true));}
        Node.prototype.onNodeCreated = () => 'created';
        Node.prototype.onConfigure = () => 'configured';
        Node.prototype.onSerialize = () => 'serialized';
        Node.prototype.onRemoved = () => 'removed';
        await extension.beforeRegisterNodeDef(Node, {name}); await extension.beforeRegisterNodeDef(Node, {name});
        const n = new Node(); assert.equal(n.onNodeCreated(), 'created'); n.onNodeCreated();
        assert.equal(n.widgets.length, kind === 'color' ? 4 : 3);
        const button = n.widgets.at(-1); assert.equal(button.serialize, false); assert.equal(button.options.serialize, false);
        const data = {}; assert.equal(n.onSerialize(data), 'serialized');
        assert.equal(data.widgets_values.length, core.fields(kind).length);
        assert.equal(n.onConfigure(data), 'configured'); assert.equal(n.onRemoved(), 'removed');
    }
});
test('finite recovery metadata is independent and historical, never arbitrary text', () => {
    const base = {style_id: '001', resource_revision: '1.0.0', adapter_revision: '1.0.0', resource_sha256: 'a'.repeat(64)};
    const meta = {color_style: {...base, scope: 'color_only'}, creator_style: base};
    assert.match(visualStyleSelectionMessage(meta), /Previous color/);
    assert.match(visualStyleSelectionMessage(meta), /Previous creator/);
    for (const bad of [{...base, style_id: '201'}, {...base, resource_sha256: 'PRIVATE'}, {...base, extra: 'PRIVATE'}, {...base, adapter_revision: '2.0.0'}]) {
        assert.equal(visualStyleSelectionMessage({creator_style: bad}), '');
        assert.doesNotMatch(visualStyleSelectionMessage({color_style: meta.color_style, creator_style: bad}), /PRIVATE|Previous creator/);
    }
});

test('actual browser failure callbacks close stale owners but cannot close a reopened dialog', async () => {
    class Element {
        constructor(tag) {this.tag = tag; this.children = []; this.style = {}; this.textContent = ''; this.removed = false;}
        append(element) {this.children.push(element);}
        setAttribute() {}
        addEventListener() {}
        querySelectorAll() {return [];}
        replaceChildren() {this.children = [];}
        close() {this.closed = true;}
        remove() {this.removed = true;}
        showModal() {this.shown = true;}
    }
    const source = (await readFile(new URL('../../web/js/visual_style_config.js', import.meta.url), 'utf8'))
        .replace(/^import .*;\r?\n/gm, '').replace('export function openStyleBrowser', 'function openStyleBrowser');
    const catalog = {schema_version: 't8-visual-style-browser/v1', entries: Array.from({length: 200}, (_, i) => {
        const id = String(i + 1).padStart(3, '0');
        return {id, selection: `${id} 示例 / Example`, label_zh: '示例', label_en: 'Example', category: 'A', creator_role: 'director'};
    })};
    const flush = () => new Promise(resolve => setImmediate(resolve));
    function harness(initial = core.NONE) {
        const pending = [], document = {body: new Element('body'), createElement: tag => new Element(tag)};
        const app = {graph: {}, registerExtension() {}};
        const context = vm.createContext({...core, document, app, AbortController,
            api: {fetchApi(path) {return new Promise((resolve, reject) => pending.push({path, resolve, reject}));}}});
        vm.runInContext(source, context);
        const n = node('creator'); n.id = 1;
        n.widgets.find(widget => widget.name === 'creator').value = initial;
        n.graph = app.graph; n.graph._nodes = [n]; n.graph.getNodeById = () => n;
        return {app, pending, document, open: () => context.openStyleBrowser(n, 'creator')};
    }
    for (const phase of ['catalog', 'detail']) {
        const h = harness(phase === 'detail' ? catalog.entries[0].selection : core.NONE);
        h.open();
        if (phase === 'detail') {
            h.pending[0].resolve({ok: true, json: async () => catalog}); await flush();
            assert.match(h.pending[1].path, /creator\/001$/);
        }
        h.app.graph = {};
        h.pending.at(-1).reject(new Error('owned test transport failure')); await flush();
        assert.equal(h.document.body.children[0].removed, true, `${phase} failure must close a stale owner`);
    }
    const h = harness(); h.open(); h.open();
    const [oldDialog, newDialog] = h.document.body.children;
    assert.equal(oldDialog.removed, true);
    h.pending[0].reject(new Error('late old request failure')); await flush();
    assert.equal(newDialog.removed, false);
    assert.equal(newDialog.children.find(el => el.textContent.includes('Unable to read')), undefined);
    h.pending[1].resolve({ok: true, json: async () => catalog}); await flush();
    assert.equal(newDialog.removed, false);
    assert.ok(newDialog.children.some(el => el.textContent.includes('200 / 200')));
});
