import { app } from "../../scripts/app.js";


const NODE_ID = "MiniMaxH3PromptEnhancerT8";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const SEEDANCE_API_MODE = "贞贞平价小屋（推荐）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const AUTO_SHOT_COUNT = "AUTO（系统自动判断）";
const SHOT_COUNT_OPTIONS = [AUTO_SHOT_COUNT, ...Array.from({ length: 20 }, (_, index) => String(index + 1))];
const TASK_TYPE_LABELS = {
    T2VA: "T2VA（文生音视频）",
    I2VA: "I2VA（首帧图生音视频）",
    FL2VA: "FL2VA（首尾帧生音视频）",
    L2VA: "L2VA（尾帧图生音视频）",
    Ref2VA: "Ref2VA（参考图/视频生音视频）",
};
const LEGACY_UI_VALUES = new Set(["展开", "收起", "提交当前工作流", "打开 Seedance 注册页面"]);
const API_KEY_PATTERN = /^sk-[A-Za-z0-9_-]{16,}$/;
const SERIALIZED_WIDGET_NAMES = [
    "prompt",
    "task_type",
    "duration_seconds",
    "shot_count",
    "rewrite_mode",
    "description_word_target",
    "output_language",
    "prompt_mode",
    "api_mode",
    "reference_context",
    "constraints",
    "api_key",
    "reference_template",
    "openai_base_url",
    "openai_upload_url",
    "seed",
    "control_after_generate",
];


function setWidgetVisible(widget, visible) {
    if (!("t8OriginalType" in widget)) {
        widget.t8OriginalType = widget.type;
        widget.t8OriginalComputeSize = widget.computeSize;
        widget.t8OriginalDisplay = widget.element?.style.display || "";
        widget.t8OriginalHidden = Boolean(widget.hidden);
    }

    widget.type = visible ? widget.t8OriginalType : "converted-widget";
    widget.computeSize = visible ? widget.t8OriginalComputeSize : () => [0, -4];
    widget.hidden = visible ? widget.t8OriginalHidden : true;
    if (widget.element) {
        widget.element.dataset.shouldHide = visible ? "false" : "true";
        widget.element.style.display = visible ? widget.t8OriginalDisplay : "none";
        widget.element.hidden = !visible;
    }
}


function resizeNode(node) {
    const apply = () => {
        for (const widget of node.widgets || []) {
            if (widget.element) delete widget.computedHeight;
        }
        node.setSize([node.size[0], node.computeSize()[1]]);
        node.setDirtyCanvas(true, true);
        app.canvas?.setDirty?.(true, true);
    };
    requestAnimationFrame(() => {
        apply();
        requestAnimationFrame(apply);
    });
}


function normalizeChoice(widget, options, fallback) {
    if (widget && !options.includes(widget.value)) widget.value = fallback;
}


function setTextWidgetValue(widget, value) {
    if (!widget) return;
    widget.value = value;
    const input = widget.inputEl
        || (widget.element?.matches?.("textarea, input") ? widget.element : null)
        || widget.element?.querySelector?.("textarea, input");
    if (input) input.value = value;
}


function addAdvancedToggle(node, widgets) {
    let expanded = false;
    for (const widget of widgets) setWidgetVisible(widget, expanded);

    const toggle = node.addWidget(
        "button",
        "⚙️ 高级选项（可选）",
        "展开",
        () => {
            expanded = !expanded;
            for (const widget of widgets) setWidgetVisible(widget, expanded);
            toggle.value = expanded ? "收起" : "展开";
            resizeNode(node);
        },
        { serialize: false },
    );
    toggle.serializeValue = () => undefined;
}


function addReferenceTemplateBehavior(node, modeWidget, templateWidget) {
    const update = (mode = modeWidget.value) => {
        if (LEGACY_UI_VALUES.has(String(templateWidget.value || "").trim())) {
            setTextWidgetValue(templateWidget, "");
        }
        setWidgetVisible(templateWidget, mode === "参考模板融合");
        resizeNode(node);
    };
    const originalCallback = modeWidget.callback;
    modeWidget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.t8UpdateReferenceTemplate = update;
    update();
}


function addApiModeBehavior(node, modeWidget, baseUrlWidget, uploadUrlWidget) {
    const update = (mode = modeWidget.value) => {
        for (const widget of [baseUrlWidget, uploadUrlWidget]) {
            if (LEGACY_UI_VALUES.has(String(widget.value || "").trim())) setTextWidgetValue(widget, "");
        }
        const compatible = mode === OPENAI_API_MODE;
        setWidgetVisible(baseUrlWidget, compatible);
        setWidgetVisible(uploadUrlWidget, compatible);
        if (node.t8SignUpWidget) setWidgetVisible(node.t8SignUpWidget, !compatible);
        node.t8UpdateApiKeyPlaceholder?.();
        resizeNode(node);
    };
    const originalCallback = modeWidget.callback;
    modeWidget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.t8UpdateApiMode = update;
    update();
}


function addApiKeyWidget(node, sourceWidget, apiModeWidget) {
    const container = document.createElement("div");
    container.style.cssText = [
        "display:flex",
        "flex-direction:column",
        "gap:6px",
        "width:100%",
    ].join(";");

    const inputRow = document.createElement("div");
    inputRow.style.cssText = [
        "display:flex",
        "align-items:center",
        "gap:6px",
        "width:100%",
        "height:30px",
    ].join(";");

    const input = document.createElement("input");
    input.type = "password";
    const updatePlaceholder = () => {
        input.placeholder = apiModeWidget?.value === OPENAI_API_MODE
            ? "OpenAI兼容 API Key（输入后保存到工作流）"
            : "贞贞 API Key（输入后保存到工作流）";
    };
    node.t8UpdateApiKeyPlaceholder = updatePlaceholder;
    updatePlaceholder();
    input.autocomplete = "new-password";
    input.spellcheck = false;
    input.style.cssText = [
        "flex:1",
        "min-width:0",
        "height:28px",
        "box-sizing:border-box",
        "border:1px solid var(--border-color, #555)",
        "border-radius:6px",
        "background:var(--comfy-input-bg, #1f1f1f)",
        "color:var(--input-text, #ddd)",
        "padding:0 9px",
    ].join(";");

    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.textContent = "显示";
    reveal.title = "显示或隐藏 API Key";
    reveal.style.cssText = [
        "height:28px",
        "padding:0 9px",
        "border:1px solid var(--border-color, #555)",
        "border-radius:6px",
        "background:var(--comfy-input-bg, #2a2a2a)",
        "color:var(--input-text, #ddd)",
        "cursor:pointer",
    ].join(";");
    reveal.onclick = () => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        reveal.textContent = show ? "隐藏" : "显示";
    };

    inputRow.append(input, reveal);

    const actionRow = document.createElement("div");
    actionRow.style.cssText = [
        "display:flex",
        "gap:6px",
        "width:100%",
        "height:28px",
    ].join(";");

    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "💾 保存到工作流";
    save.title = "API Key 将写入工作流 JSON，分享前请清空";

    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "清空";
    clear.title = "从输入框和工作流中删除 API Key";

    for (const button of [save, clear]) {
        button.style.cssText = [
            "flex:1",
            "height:28px",
            "border:1px solid var(--border-color, #555)",
            "border-radius:6px",
            "background:var(--comfy-input-bg, #2a2a2a)",
            "color:var(--input-text, #ddd)",
            "cursor:pointer",
        ].join(";");
    }
    actionRow.append(save, clear);
    container.append(inputRow, actionRow);

    let value = String(sourceWidget.value || "");
    if (LEGACY_UI_VALUES.has(value.trim())) value = "";
    Object.defineProperty(sourceWidget, "value", {
        configurable: true,
        get() {
            return value;
        },
        set(nextValue) {
            const next = String(nextValue || "");
            value = LEGACY_UI_VALUES.has(next.trim()) ? "" : next;
            input.value = value;
        },
    });
    input.value = value;
    input.addEventListener("input", () => {
        save.textContent = "💾 保存到工作流";
        node.setDirtyCanvas(true, true);
    });

    const commit = () => {
        sourceWidget.value = input.value.trim();
        sourceWidget.callback?.(sourceWidget.value);
        node.graph?.change?.();
        node.setDirtyCanvas(true, true);
        save.textContent = "✓ 已保存到工作流";
    };
    save.onclick = commit;
    clear.onclick = () => {
        input.value = "";
        sourceWidget.value = "";
        sourceWidget.callback?.(sourceWidget.value);
        node.graph?.change?.();
        node.setDirtyCanvas(true, true);
        save.textContent = "💾 保存到工作流";
    };
    node.t8CommitApiKey = commit;

    setWidgetVisible(sourceWidget, false);
    const secureWidget = node.addDOMWidget("seedance_api_key_secure", "custom", container, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => 78,
        getMaxHeight: () => 78,
        hideOnZoom: false,
        serialize: false,
        beforeResize() {
            delete this.width;
        },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas(true, true);
        },
        onDraw(widget) {
            if (!("width" in widget)) return;
            delete widget.width;
            node.setDirtyCanvas(true, true);
        },
    });
    delete secureWidget.width;
    secureWidget.serializeValue = () => undefined;
}


app.registerExtension({
    name: "T8.MiniMaxH3PromptEnhancer",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnConfigure = nodeType.prototype.onConfigure;
        const originalOnSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);

            const outputLanguageWidget = this.widgets?.find((widget) => widget.name === "output_language");
            const taskTypeWidget = this.widgets?.find((widget) => widget.name === "task_type");
            const shotCountWidget = this.widgets?.find((widget) => widget.name === "shot_count");
            const promptModeWidget = this.widgets?.find((widget) => widget.name === "prompt_mode");
            const referenceTemplateWidget = this.widgets?.find((widget) => widget.name === "reference_template");
            const referenceContextWidget = this.widgets?.find((widget) => widget.name === "reference_context");
            const constraintsWidget = this.widgets?.find((widget) => widget.name === "constraints");
            const apiKeyWidget = this.widgets?.find((widget) => widget.name === "api_key");
            const apiModeWidget = this.widgets?.find((widget) => widget.name === "api_mode");
            const openaiBaseUrlWidget = this.widgets?.find((widget) => widget.name === "openai_base_url");
            const openaiUploadUrlWidget = this.widgets?.find((widget) => widget.name === "openai_upload_url");
            const seedWidget = this.widgets?.find((widget) => widget.name === "seed");
            const seedControlWidget = seedWidget?.linkedWidgets?.[0]
                || this.widgets?.find((widget) => widget.name === "control_after_generate");
            if (seedControlWidget) {
                seedControlWidget.label = "种子状态（运行后）";
                seedControlWidget.tooltip = "fixed 固定；randomize 随机；increment 递增；decrement 递减。";
            }
            if (promptModeWidget && referenceTemplateWidget) {
                addReferenceTemplateBehavior(this, promptModeWidget, referenceTemplateWidget);
            }
            if (apiModeWidget && openaiBaseUrlWidget && openaiUploadUrlWidget) {
                addApiModeBehavior(this, apiModeWidget, openaiBaseUrlWidget, openaiUploadUrlWidget);
            }
            this.t8NormalizePromptOptions = () => {
                if (TASK_TYPE_LABELS[taskTypeWidget?.value]) taskTypeWidget.value = TASK_TYPE_LABELS[taskTypeWidget.value];
                normalizeChoice(taskTypeWidget, Object.values(TASK_TYPE_LABELS), TASK_TYPE_LABELS.T2VA);
                normalizeChoice(shotCountWidget, SHOT_COUNT_OPTIONS, AUTO_SHOT_COUNT);
                normalizeChoice(outputLanguageWidget, ["中文", "English"], "中文");
                normalizeChoice(promptModeWidget, ["官方增强", "参考模板融合"], "官方增强");
                normalizeChoice(apiModeWidget, [SEEDANCE_API_MODE, OPENAI_API_MODE], SEEDANCE_API_MODE);
                if (LEGACY_UI_VALUES.has(String(apiKeyWidget?.value || "").trim())) apiKeyWidget.value = "";
                for (const widget of [referenceContextWidget, constraintsWidget, referenceTemplateWidget, openaiBaseUrlWidget, openaiUploadUrlWidget]) {
                    const value = String(widget?.value || "").trim();
                    if (LEGACY_UI_VALUES.has(value)) setTextWidgetValue(widget, "");
                    if (API_KEY_PATTERN.test(value)) {
                        if (!String(apiKeyWidget?.value || "").trim()) apiKeyWidget.value = value;
                        setTextWidgetValue(widget, "");
                    }
                }
                this.t8UpdateReferenceTemplate?.();
                this.t8UpdateApiMode?.();
            };
            this.t8NormalizePromptOptions();

            const advancedWidgets = [referenceContextWidget, constraintsWidget].filter(Boolean);
            if (advancedWidgets.length) addAdvancedToggle(this, advancedWidgets);

            if (apiKeyWidget) addApiKeyWidget(this, apiKeyWidget, apiModeWidget);

            let queuing = false;
            const runWidget = this.addWidget(
                "button",
                "▶ 运行提示词优化",
                "提交当前工作流",
                async () => {
                    if (queuing) return;
                    queuing = true;
                    try {
                        this.t8CommitApiKey?.();
                        await app.queuePrompt(0, 1, [String(this.id)]);
                    } finally {
                        queuing = false;
                    }
                },
                { serialize: false },
            );
            runWidget.serializeValue = () => undefined;

            const signUpWidget = this.addWidget(
                "button",
                "🔑 获取贞贞 API Key",
                "打开 Seedance 注册页面",
                () => window.open(SIGN_UP_URL, "_blank", "noopener,noreferrer"),
                { serialize: false },
            );
            signUpWidget.serializeValue = () => undefined;
            this.t8SignUpWidget = signUpWidget;
            this.t8UpdateApiMode?.();
            resizeNode(this);
        };
        nodeType.prototype.onConfigure = function () {
            const args = [...arguments];
            const serialized = args[0];
            if (Array.isArray(serialized?.widgets_values) && serialized.widgets_values.length === 16) {
                args[0] = { ...serialized, widgets_values: [...serialized.widgets_values] };
                args[0].widgets_values.splice(3, 0, AUTO_SHOT_COUNT);
            }
            originalOnConfigure?.apply(this, args);
            requestAnimationFrame(() => this.t8NormalizePromptOptions?.());
        };
        nodeType.prototype.onSerialize = function (serialized) {
            originalOnSerialize?.apply(this, arguments);
            serialized.widgets_values = SERIALIZED_WIDGET_NAMES.map((name) => (
                this.widgets?.find((widget) => widget.name === name)?.value ?? null
            ));
        };
    },
});
