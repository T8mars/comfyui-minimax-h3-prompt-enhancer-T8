import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {DIAGRAM_LABELS, LIGHT_LABELS, validIllustration, renderVisualPreview} from '../../web/js/visual_style_preview.mjs';

const manifest = JSON.parse(await readFile(new URL('../../resources/visual_style_previews/catalog.json', import.meta.url), 'utf8'));
async function fixture(kind, id = '022') {
    const raw = await readFile(new URL(`../../resources/visual_styles/${kind === 'color' ? 'colors' : 'creators'}/${id}.json`, import.meta.url));
    const resource = JSON.parse(raw), digest = createHash('sha256').update(raw).digest('hex'), row = manifest.entries.find(v => v.id === id);
    return {kind, resource, digest, illustration: {available: true, schema_version: manifest.schema_version, revision: manifest.revision,
        kind, id, resource_sha256: digest, real_output: false, lighting: kind === 'color' ? row.lighting : null, methods: kind === 'creator' ? row.methods : []}};
}
class Element {
    constructor(tag) {this.tagName = tag; this.children = []; this.style = {}; this.dataset = {}; this.attributes = {}; this.textContent = ''; this.isConnected = true;}
    append(el) {this.children.push(el);}
    replaceChildren() {this.children = [];}
    setAttribute(key, value) {this.attributes[key] = String(value);}
}
const descendants = el => [el, ...el.children.flatMap(descendants)];
function dom() {
    const pending = new Map(), listeners = new Set(); let next = 0;
    const previous = {document: globalThis.document, requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame};
    globalThis.document = {createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), hidden: false,
        addEventListener: (_, fn) => listeners.add(fn), removeEventListener: (_, fn) => listeners.delete(fn)};
    globalThis.requestAnimationFrame = callback => {pending.set(++next, callback); return next;};
    globalThis.cancelAnimationFrame = id => pending.delete(id);
    return {root: new Element('main'), pending, listeners, hide() {document.hidden = true; listeners.forEach(fn => fn());},
        tick(now) {const callbacks = [...pending.values()]; pending.clear(); callbacks.forEach(fn => fn(now));}, restore() {Object.assign(globalThis, previous);}};
}

test('400 display identities validate; every curated diagram has a renderer label', async () => {
    const seen = new Set();
    for (const row of manifest.entries) for (const kind of ['color', 'creator']) {
        const f = await fixture(kind, row.id);
        assert.equal(validIllustration(f.illustration, kind, f.resource, f.digest), true);
        if (kind === 'creator') row.methods.forEach(code => seen.add(code));
        else assert.ok(Object.hasOwn(LIGHT_LABELS, row.lighting));
    }
    assert.deepEqual([...seen].sort(), Object.keys(DIAGRAM_LABELS).sort());
});
test('source mismatch / unknown diagram / falsely real output cannot render a misleading image', async () => {
    const f = await fixture('creator');
    for (const change of [{id: '001'}, {resource_sha256: 'b'.repeat(64)}, {methods: ['bad']}, {real_output: true}, {revision: '2.0.0'}, {available: false}]) {
        const h = dom();
        try {
            const dispose = renderVisualPreview(h.root, {...f, illustration: {...f.illustration, ...change}});
            assert.equal(descendants(h.root).filter(e => e.tagName === 'svg').length, 0);
            assert.ok(descendants(h.root).some(e => e.textContent.includes('仍可使用'))); dispose();
        } finally {h.restore();}
    }
});
test('all 200 colors and 400 methods render SVG locally without mutating resources', async () => {
    const h = dom();
    try {
        for (const row of manifest.entries) for (const kind of ['color', 'creator']) {
            const f = await fixture(kind, row.id), before = JSON.stringify(f); h.root.replaceChildren();
            const dispose = renderVisualPreview(h.root, f);
            const all = descendants(h.root); assert.equal(all.filter(e => e.tagName === 'svg').length, 2);
            assert.equal(all.some(e => ['img', 'video', 'iframe', 'script'].includes(e.tagName)), false);
            if (kind === 'creator') {
                const buttons = all.filter(e => e.tagName === 'button'); buttons[1].onclick();
                assert.equal(descendants(h.root).find(e => e.dataset.diagram)?.dataset.diagram, row.methods[1]);
            }
            assert.equal(JSON.stringify(f), before); assert.equal(h.pending.size, 0, 'no autoplay'); dispose();
        }
    } finally {h.restore();}
});
test('preview light / scene controls are local and leave the selected scope unchanged', async () => {
    const h = dom(), f = {...await fixture('color'), scope: '仅色彩 / Color only'};
    try {
        const before = JSON.stringify(f), dispose = renderVisualPreview(h.root, f);
        descendants(h.root).find(e => e.tagName === 'button').onclick();
        const select = descendants(h.root).find(e => e.tagName === 'select'); select.value = 'street'; select.onchange();
        assert.equal(JSON.stringify(f), before); assert.equal(descendants(h.root).filter(e => e.tagName === 'svg').length, 2); dispose();
    } finally {h.restore();}
});
test('animation stops on dispose, stale owner, hidden tab and detached preview', async () => {
    const f = await fixture('creator', '155');
    for (const reason of ['dispose', 'owner', 'hidden', 'detached']) {
        const h = dom(); let live = true;
        try {
            const dispose = renderVisualPreview(h.root, {...f, isLive: () => live});
            const play = descendants(h.root).find(e => e.tagName === 'button' && e.textContent.includes('Play'));
            play.onclick(); assert.equal(h.pending.size, 1); h.tick(0); h.tick(100); assert.equal(h.pending.size, 1);
            if (reason === 'dispose') dispose();
            if (reason === 'owner') live = false;
            if (reason === 'hidden') {h.hide(); assert.equal(h.pending.size, 0, 'hidden page cancels without waiting for another RAF');}
            if (reason === 'detached') h.root.children[0].isConnected = false;
            h.tick(200); assert.equal(h.pending.size, 0, reason); dispose(); assert.equal(h.listeners.size, 0, 'no retained visibility listeners');
        } finally {h.restore();}
    }
});

test('static composition disables playback; switching from motion stops the queued frame', async () => {
    const h = dom(), f = await fixture('creator', '022');
    try {
        const dispose = renderVisualPreview(h.root, f);
        const buttons = descendants(h.root).filter(e => e.tagName === 'button'), play = buttons[2];
        assert.equal(play.disabled, true); play.onclick(); assert.equal(h.pending.size, 0);
        buttons[1].onclick(); assert.equal(play.disabled, false); play.onclick(); assert.equal(h.pending.size, 1);
        buttons[0].onclick(); assert.equal(play.disabled, true); assert.equal(h.pending.size, 0); dispose();
    } finally {h.restore();}
});
