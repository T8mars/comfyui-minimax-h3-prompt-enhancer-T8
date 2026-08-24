export const OPENAI_PROVIDER_STATE_PROPERTY = "t8_openai_provider_state";


function widgetTextInput(widget) {
    if (!widget) return null;
    if (widget.inputEl) return widget.inputEl;
    if (widget.element?.matches?.("textarea, input")) return widget.element;
    return widget.element?.querySelector?.("textarea, input") || null;
}


function liveWidgetText(widget) {
    const input = widgetTextInput(widget);
    return String(input?.value ?? widget?.value ?? "");
}


function assignWidgetText(widget, value) {
    if (!widget) return;
    const text = String(value ?? "");
    widget.value = text;
    const input = widgetTextInput(widget);
    if (input) input.value = text;
}


function normalizedOpenAIProviderState(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    return {
        base_url: String(value.base_url ?? "").slice(0, 4096),
        model_id: String(value.model_id ?? "").slice(0, 512),
    };
}


export function serializedOpenAIProviderState(serialized) {
    return normalizedOpenAIProviderState(serialized?.properties?.[OPENAI_PROVIDER_STATE_PROPERTY]);
}


export function commitOpenAIProviderState(node, baseUrlWidget = null, modelWidget = null) {
    const base = baseUrlWidget || node?.widgets?.find((widget) => widget.name === "openai_base_url");
    const model = modelWidget || node?.widgets?.find((widget) => widget.name === "custom_model");
    const state = {
        base_url: liveWidgetText(base).trim(),
        model_id: liveWidgetText(model).trim(),
    };
    assignWidgetText(base, state.base_url);
    assignWidgetText(model, state.model_id);
    if (node) {
        if (!node.properties || typeof node.properties !== "object" || Array.isArray(node.properties)) {
            node.properties = {};
        }
        node.properties[OPENAI_PROVIDER_STATE_PROPERTY] = state;
    }
    return state;
}


export function restoreOpenAIProviderState(node, state, baseUrlWidget = null, modelWidget = null) {
    const normalized = normalizedOpenAIProviderState(state);
    if (!normalized || !node) return null;
    const base = baseUrlWidget || node.widgets?.find((widget) => widget.name === "openai_base_url");
    const model = modelWidget || node.widgets?.find((widget) => widget.name === "custom_model");
    assignWidgetText(base, normalized.base_url);
    assignWidgetText(model, normalized.model_id);
    if (!node.properties || typeof node.properties !== "object" || Array.isArray(node.properties)) {
        node.properties = {};
    }
    node.properties[OPENAI_PROVIDER_STATE_PROPERTY] = normalized;
    return normalized;
}


export function serializeOpenAIProviderState(node, serialized, baseUrlWidget = null, modelWidget = null) {
    const state = commitOpenAIProviderState(node, baseUrlWidget, modelWidget);
    serialized.properties = {
        ...(serialized.properties && typeof serialized.properties === "object" ? serialized.properties : {}),
        [OPENAI_PROVIDER_STATE_PROPERTY]: state,
    };
    return state;
}


export function bindOpenAIProviderPersistence(node, baseUrlWidget = null, modelWidget = null) {
    const base = baseUrlWidget || node?.widgets?.find((widget) => widget.name === "openai_base_url");
    const model = modelWidget || node?.widgets?.find((widget) => widget.name === "custom_model");
    const commit = () => commitOpenAIProviderState(node, base, model);
    for (const widget of [base, model]) {
        if (!widget || widget.t8OpenAIProviderPersistenceBound) continue;
        widget.t8OpenAIProviderPersistenceBound = true;
        const originalCallback = widget.callback;
        widget.callback = function () {
            originalCallback?.apply(this, arguments);
            commit();
        };
        const input = widgetTextInput(widget);
        input?.addEventListener?.("input", () => {
            commit();
            node.graph?.change?.();
            node.setDirtyCanvas?.(true, true);
        });
        input?.addEventListener?.("change", commit);
    }
    node.t8CommitOpenAIProviderState = commit;
    return commit;
}


export function namedWidgetValueMap(names, values, acceptedLengths = [names.length]) {
    if (!Array.isArray(names) || !Array.isArray(values)) return null;
    if (!acceptedLengths.includes(values.length) || values.length > names.length) return null;
    return new Map(names.slice(0, values.length).map((name, index) => [name, values[index]]));
}


export function namedWidgetValueMapByDiscriminator(
    values,
    layouts,
    discriminatorName,
    acceptedValues,
) {
    if (!Array.isArray(values) || !Array.isArray(layouts)) return null;
    const accepted = acceptedValues instanceof Set ? acceptedValues : new Set(acceptedValues || []);
    for (const names of layouts) {
        if (!Array.isArray(names) || names.length !== values.length) continue;
        const index = names.indexOf(discriminatorName);
        if (index >= 0 && accepted.has(String(values[index] ?? ""))) {
            return new Map(names.map((name, valueIndex) => [name, values[valueIndex]]));
        }
    }
    return null;
}


export function remapNamedWidgetValues(names, values, defaults = {}, fallback = null) {
    if (!(values instanceof Map)) return fallback;
    return names.map((name) => {
        const value = values.get(name);
        if (value !== undefined && value !== null) return value;
        return Object.hasOwn(defaults, name) ? defaults[name] : null;
    });
}


export function expandNamedWidgetValues(
    names,
    values,
    defaults = {},
    acceptedLengths = [names.length],
) {
    const mapped = namedWidgetValueMap(names, values, acceptedLengths);
    if (!mapped) return values;
    return names.map((name) => {
        const value = mapped.get(name);
        if (value !== undefined && value !== null) return value;
        return Object.hasOwn(defaults, name) ? defaults[name] : null;
    });
}


export function restoreNamedWidgetValues(node, values, excludedNames = new Set()) {
    if (!values) return;
    for (const [name, value] of values) {
        if (excludedNames.has(name)) continue;
        const widget = node.widgets?.find((item) => item.name === name);
        if (widget) widget.value = value;
    }
}


export function serializeNamedWidgetValues(node, names, transform = null) {
    return names.map((name) => {
        const widget = node.widgets?.find((item) => item.name === name);
        const value = widget?.value ?? null;
        return transform ? transform(name, value, widget) : value;
    });
}
