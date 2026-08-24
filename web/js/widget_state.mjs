export function namedWidgetValueMap(names, values, acceptedLengths = [names.length]) {
    if (!Array.isArray(names) || !Array.isArray(values)) return null;
    if (!acceptedLengths.includes(values.length) || values.length > names.length) return null;
    return new Map(names.slice(0, values.length).map((name, index) => [name, values[index]]));
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
