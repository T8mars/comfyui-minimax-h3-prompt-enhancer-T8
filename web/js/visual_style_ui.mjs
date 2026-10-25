// Only canonical controls persist; previews and actions never enter workflows.
export const OFF = '关闭 / Off';
export const ON = '开启 / On';
export const NONE = '未选择 / None';
export const SCOPES = ['仅色彩 / Color only', '色彩 + 光影 / Color + lighting'];
export const KINDS = {T8ColorStyleConfig: 'color', T8CreatorStyleConfig: 'creator'};
export const fields = kind => kind === 'color' ? ['mode', 'palette', 'scope'] : ['mode', 'creator'];
export const valueOf = (node, name) => node.widgets?.find(w => w.name === name)?.value;
const property = kind => `t8_${kind}_style_widgets_v1`;
const defaults = kind => kind === 'color' ? {mode: OFF, palette: NONE, scope: SCOPES[0]} : {mode: OFF, creator: NONE};
export function validValues(kind, values) {
    return values && !Array.isArray(values) && fields(kind).every(name => Object.hasOwn(values, name)
        && typeof values[name] === 'string' && values[name].length > 0 && values[name].length <= 400)
        && [OFF, ON].includes(values.mode) && (kind !== 'color' || SCOPES.includes(values.scope));
}
export function serializeStyle(node, data, kind) {
    const values = Object.fromEntries(fields(kind).map(name => [name, valueOf(node, name)]));
    data.widgets_values = fields(kind).map(name => values[name]);
    data.widgets_values_named = {...values};
    data.properties = {...data.properties, [property(kind)]: values};
    node.properties = {...node.properties, [property(kind)]: values};
}
export function configureStyle(node, data, kind, original, args) {
    const names = fields(kind);
    const positional = Array.isArray(data?.widgets_values) && data.widgets_values.length === names.length
        ? Object.fromEntries(names.map((name, i) => [name, data.widgets_values[i]])) : null;
    const values = [data?.properties?.[property(kind)], data?.widgets_values_named, positional]
        .find(v => validValues(kind, v)) || defaults(kind);
    const projected = {...data, widgets_values: (node.widgets || []).map(w => Object.hasOwn(values, w.name) ? values[w.name] : w.value)};
    const result = original?.apply(node, [projected, ...Array.from(args || []).slice(1)]);
    for (const name of names) {
        const widget = node.widgets?.find(w => w.name === name);
        if (widget) widget.value = values[name]; // Retain unknown historical labels; never silently choose another style.
    }
    return result;
}
export function filterEntries(entries, category = '', query = '') {
    const normalize = value => value.normalize('NFKD').toLocaleLowerCase().replace(/[\u0300-\u036f\s·.-]/g, '');
    const needle = normalize(query);
    return entries.filter(row => (!category || row.category === category)
        && normalize([row.id, row.label_zh, row.label_en, row.category].join(' ')).includes(needle));
}
export function ownerIsCurrent(node, graph, root, currentRoot) {
    if (!graph || !root || node.graph !== graph || root !== currentRoot || graph.getNodeById?.(node.id) !== node) return false;
    const pending = [root], seen = new Set();
    while (pending.length) {
        const current = pending.pop();
        if (!current || seen.has(current)) continue;
        if (current === graph) return true;
        seen.add(current);
        for (const child of current.nodes || current._nodes || []) if (child.subgraph) pending.push(child.subgraph);
        if (typeof current.subgraphs?.values === 'function') pending.push(...current.subgraphs.values());
    }
    return false;
}
export const REVIEW_LABELS = {
    source_examples_excluded: '已剔除示例人物和剧情 / Example facts excluded',
    external_protocol_excluded: '未采用外部模型时长等协议 / External protocol excluded',
    color_kept_separate: '色彩独立选择 / Color kept separate',
    conflicting_avoid_excluded: '已剔除相互矛盾的禁用项 / Conflicting avoid-list excluded',
    generic_avoid_excluded: '已剔除通用禁用模板 / Generic avoid-list excluded',
    limited_method_specificity: '来源仅支持通用镜头模板，非独有导演理论 / Limited source specificity; not a unique directing theory',
    source_role_corrected: '已校正创作者职责 / Creator role corrected',
};
