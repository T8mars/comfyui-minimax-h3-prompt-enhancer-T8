import {app} from '../../../scripts/app.js';
import {api} from '../../../scripts/api.js';
import {KINDS, REVIEW_LABELS, configureStyle, serializeStyle, filterEntries, ownerIsCurrent, valueOf} from './visual_style_ui.mjs';

const dialogs = new WeakMap();
const roles = {director: '导演 / Director', cinematographer: '摄影 / Cinematographer', art_director: '美术 / Art director', team: '团队 / Team'};
const make = (tag, text, parent) => {const el = document.createElement(tag); if (text) el.textContent = text; parent?.append(el); return el;};

export function openStyleBrowser(node, kind) {
    dialogs.get(node)?.();
    const graph = node.graph, root = app.graph, name = kind === 'color' ? 'palette' : 'creator';
    const initialValue = valueOf(node, name), abort = new AbortController();
    const dialog = make('dialog');
    dialog.setAttribute('aria-label', 'T8 视觉风格浏览 / Visual styles');
    dialog.style.cssText = 'width:min(900px,94vw);max-height:88vh;overflow:auto;background:#202126;color:#eee;padding:20px;border:1px solid #777;border-radius:10px;pointer-events:auto;';
    let closed = false, epoch = 0, selected = null, entries = [];
    const live = () => !closed && ownerIsCurrent(node, graph, root, app.graph);
    const close = () => {if (closed) return; closed = true; epoch++; abort.abort(); dialog.close(); dialog.remove(); if (dialogs.get(node) === close) dialogs.delete(node);};
    dialogs.set(node, close);
    dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
    make('h3', kind === 'color' ? '200 色彩风格 / Color references' : '200 导演与创作者 / Creator references', dialog);
    make('p', '1. 搜索并预览 → 2. 应用选择 → 3. 节点切为开启 / On → 4. 接 H3 或 Seedance 对应配置口。两个入口可独立组合，默认关闭。 / Preview → Apply → switch On → connect the matching input.', dialog);
    make('p', kind === 'color' ? '这是提示词配色参考，不是 LUT，不修改原图。六色比例是原资料的相对参考；不要求全用，也不保证像素面积。光影仅在选择“色彩 + 光影”时加入。 / Prompt references only; lighting is opt-in.' : '仅提供已有场面的构图、拍法与节奏建议，不是完整编剧器，不新增剧情。不会自动采用同名色卡。 / Presentation methods, not screenplay generation or automatic color transfer.', dialog);
    const toolbar = make('div', '', dialog);
    toolbar.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;pointer-events:auto';
    const search = make('input', '', toolbar); search.placeholder = '编号 / 中文 / English'; search.setAttribute('aria-label', '搜索风格 / Search');
    const category = make('select', '', toolbar); category.setAttribute('aria-label', '分类 / Category'); make('option', '全部分类 / All categories', category).value = '';
    const status = make('p', '正在读取本地资源 / Loading local resources…', dialog);
    const body = make('div', '', dialog); body.style.cssText = 'display:grid;grid-template-columns:minmax(180px,1fr) 2fr;gap:16px';
    const list = make('select', '', body); list.size = 12; list.setAttribute('aria-label', '风格列表 / Styles'); list.style.cssText = 'width:100%;pointer-events:auto';
    const detail = make('div', '', body); detail.style.cssText = 'min-width:0;overflow-wrap:anywhere';
    const apply = make('button', '应用到当前节点 / Apply selection', dialog); apply.disabled = true;
    const cancel = make('button', '关闭 / Close', dialog); cancel.onclick = close;
    make('p', '纯本地浏览，无模型调用。适配方法为实验性建议；内容整理不等于模型遵从或成片效果已验证。 / Local-only preview; model and rendered outcomes are unverified.', dialog);
    for (const element of dialog.querySelectorAll('input,select,button')) element.style.pointerEvents = 'auto';
    const fail = () => {
        if (!live()) {close(); return;}
        status.textContent = '无法读取受校验的本地资源。请检查安装后重新打开。 / Unable to read validated resources; reopen after checking installation.';
        apply.disabled = true;
    };
    const fetchJSON = async path => {const response = await api.fetchApi(`/t8-prompt-enhancer/visual-styles/${path}`, {cache: 'no-store', signal: abort.signal}); if (!response.ok) throw Error('resource'); return response.json();};
    async function preview(id) {
        const ticket = ++epoch; selected = null; apply.disabled = true; detail.replaceChildren();
        if (!/^\d{3}$/.test(id)) return;
        try {
            const response = await fetchJSON(`${kind}/${id}`);
            if (!live()) {close(); return;}
            if (ticket !== epoch) return;
            const row = entries.find(row => row.id === id), resource = response.resource;
            if (!row || !resource || resource.id !== id || response.selection !== row.selection) throw Error('identity');
            make('h4', row.selection, detail); make('p', `${row.category} · ${roles[row.creator_role] || row.creator_role} · v${resource.revision}`, detail);
            if (kind === 'color') {
                const swatches = (colors, title) => {
                    make('p', title, detail);
                    const grid = make('div', '', detail); grid.style.cssText = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px';
                    for (const color of colors) {
                        const card = make('div', '', grid), swatch = make('div', '', card);
                        if (!/^#[0-9a-f]{6}$/i.test(color.hex)) throw Error('color');
                        swatch.style.cssText = `height:32px;background:${color.hex};border:1px solid #999`;
                        make('small', `${color.name_zh} / ${color.name_en} ${color.hex}${color.share == null ? '' : ` · ${(color.share * 100).toFixed(1)}%`}`, card);
                    }
                };
                swatches(resource.primary, '主色 / Primary (soft reference)');
                swatches(resource.accents, '候选点缀色（不自动注入） / Accent candidates (preview only)');
                for (const key of ['color_notes', 'lighting_notes']) make('p', `${resource[key].zh}\n${resource[key].en}`, detail);
            } else {
                for (const method of resource.methods) make('p', `${method.dimension}${method.requires_cuts ? ' · 需切镜，单镜时跳过 / skipped for one shot' : ''}\n${method.text_zh}\n${method.text_en}`, detail);
                for (const code of resource.review_notes) if (REVIEW_LABELS[code]) make('p', REVIEW_LABELS[code], detail);
            }
            selected = row; apply.disabled = false;
        } catch (error) {if (ticket === epoch && error.name !== 'AbortError') fail();}
    }
    function refresh() {
        epoch++; selected = null; apply.disabled = true; detail.replaceChildren(); list.replaceChildren();
        const filtered = filterEntries(entries, category.value, search.value);
        for (const row of filtered) make('option', row.selection, list).value = row.id;
        list.selectedIndex = -1; status.textContent = `${filtered.length} / ${entries.length} · 本地资源 / Local resources`;
    }
    search.oninput = refresh; category.onchange = refresh; list.onchange = () => preview(list.value);
    apply.onclick = () => {
        const widget = node.widgets?.find(w => w.name === name);
        if (!live() || !selected || !widget || widget.value !== initialValue || !widget.options?.values?.includes(selected.selection)) {
            status.textContent = '节点/工作流/选项已变化，请关闭后重新打开。 / Node or selection changed; reopen the browser.'; apply.disabled = true; return;
        }
        widget.value = selected.selection; widget.callback?.(widget.value); graph.change?.(); node.setDirtyCanvas?.(true, true); close();
    };
    document.body.append(dialog); dialog.showModal();
    fetchJSON('catalog').then(data => {
        if (!live()) {close(); return;}
        if (data.schema_version !== 't8-visual-style-browser/v1' || !Array.isArray(data.entries) || data.entries.length !== 200) throw Error('catalog');
        entries = data.entries;
        for (const label of new Set(entries.map(row => row.category))) make('option', label, category).value = label;
        refresh();
        const current = entries.find(row => row.selection === initialValue);
        if (current) {list.value = current.id; preview(current.id);}
    }).catch(error => {if (error.name !== 'AbortError') fail();});
    return close;
}

app.registerExtension({
    name: 'T8.VisualStyleConfigs',
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const kind = KINDS[nodeData.name];
        if (!kind || Object.hasOwn(nodeType.prototype, '__t8VisualStyles')) return;
        nodeType.prototype.__t8VisualStyles = true;
        const created = nodeType.prototype.onNodeCreated, configure = nodeType.prototype.onConfigure;
        const serialize = nodeType.prototype.onSerialize, removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onNodeCreated = function() {
            const result = created?.apply(this, arguments);
            if (!this.widgets?.some(w => w.name === '浏览风格与帮助 / Browse styles')) {
                const button = this.addWidget('button', '浏览风格与帮助 / Browse styles', null, () => openStyleBrowser(this, kind), {serialize: false});
                button.serialize = false;
            }
            return result;
        };
        nodeType.prototype.onConfigure = function(data) {dialogs.get(this)?.(); return configureStyle(this, data, kind, configure, arguments);};
        nodeType.prototype.onSerialize = function(data) {const result = serialize?.apply(this, arguments); serializeStyle(this, data, kind); return result;};
        nodeType.prototype.onRemoved = function() {dialogs.get(this)?.(); return removed?.apply(this, arguments);};
    },
});
