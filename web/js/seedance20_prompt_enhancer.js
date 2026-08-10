import { app } from "../../scripts/app.js";
import { addCaseTemplateUI, serializedCaseTemplateValue } from "./case_template_ui.js";


const NODE_ID = "Seedance20PromptEnhancerT8";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const AI_WORKSHOP_SIGN_UP_URL = "https://ai.t8star.org/register?aff=dP7j";
const SEEDANCE_API_MODE = "贞贞平价小屋（推荐）";
const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（图片/视频）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const AI_WORKSHOP_DEFAULT_MODEL = "gemini-3.5-flash";
const CUSTOM_MODEL_OPTION = "Custom（自定义）";
const AUTO_DURATION = "AUTO（模型智能选择）";
const AUTO_SHOT_COUNT = "AUTO（系统自动判断）";
const NO_CASE_TEMPLATE = "无（不使用 T8 案例）";
const TASK_LABELS = {
    AUTO: "AUTO（根据意图与素材判断）",
    T2V: "T2V（文生视频）",
    I2V: "I2V（首帧图生视频）",
    "FL-I2V": "FL-I2V（首尾帧图生视频）",
    MultiRef: "多模态参考生成（图片/视频）",
    VideoEdit: "视频编辑（增删改）",
    VideoExtend: "视频延长（向前/向后）",
    TrackFill: "轨道补齐（多视频衔接）",
    Combined: "组合任务（参考+编辑）",
};
const SERIALIZED_WIDGET_NAMES = [
    "prompt",
    "task_intent",
    "complexity_mode",
    "duration_seconds",
    "shot_count",
    "rewrite_mode",
    "output_detail",
    "output_language",
    "prompt_mode",
    "case_template",
    "reference_syntax",
    "subtitle_policy",
    "stability_constraints",
    "custom_length_target",
    "reference_roles",
    "reference_context",
    "constraints",
    "api_key",
    "reference_template",
    "api_mode",
    "ai_workshop_model",
    "custom_model",
    "openai_base_url",
    "openai_video_urls",
    "seed",
    "control_after_generate",
];


function setWidgetVisible(widget, visible) {
    if (!widget) return;
    if (!("s20OriginalType" in widget)) {
        widget.s20OriginalType = widget.type;
        widget.s20OriginalComputeSize = widget.computeSize;
        widget.s20OriginalDisplay = widget.element?.style.display || "";
        widget.s20OriginalHidden = Boolean(widget.hidden);
    }
    widget.type = visible ? widget.s20OriginalType : "converted-widget";
    widget.computeSize = visible ? widget.s20OriginalComputeSize : () => [0, -4];
    widget.hidden = visible ? widget.s20OriginalHidden : true;
    if (widget.element) {
        widget.element.dataset.shouldHide = visible ? "false" : "true";
        widget.element.style.display = visible ? widget.s20OriginalDisplay : "none";
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


function normalizeChoice(widget, choices, fallback) {
    if (widget && !choices.includes(widget.value)) widget.value = fallback;
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


function addConditionalWidget(node, controller, target, predicate) {
    const update = (value = controller.value) => {
        setWidgetVisible(target, predicate(value));
        resizeNode(node);
    };
    const originalCallback = controller.callback;
    controller.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    update();
    return update;
}


function addApiModeBehavior(node, modeWidget, baseUrlWidget, videoUrlsWidget, modelWidget, customModelWidget) {
    const updateModel = () => {
        const workshop = modeWidget.value === AI_WORKSHOP_API_MODE;
        const compatible = modeWidget.value === OPENAI_API_MODE;
        setWidgetVisible(modelWidget, workshop);
        setWidgetVisible(customModelWidget, compatible || (workshop && modelWidget.value === CUSTOM_MODEL_OPTION));
        customModelWidget.label = compatible ? "OpenAI 模型 ID（必填）" : "AI工坊自定义模型 ID";
    };
    const originalModelCallback = modelWidget.callback;
    modelWidget.callback = function (value) {
        originalModelCallback?.apply(this, arguments);
        updateModel();
        resizeNode(node);
    };
    const update = (mode = modeWidget.value) => {
        const compatible = mode === OPENAI_API_MODE;
        baseUrlWidget.label = "OpenAI Base URL";
        videoUrlsWidget.label = "视频素材 URL（可选，每行一个）";
        setWidgetVisible(baseUrlWidget, compatible);
        setWidgetVisible(videoUrlsWidget, compatible);
        updateModel();
        if (node.s20SignUpWidget) {
            setWidgetVisible(node.s20SignUpWidget, !compatible);
            const signupLabel = mode === AI_WORKSHOP_API_MODE
                ? "🔑 获取 AI 工坊 API Key"
                : "🔑 获取贞贞提示词增强 API Key";
            node.s20SignUpWidget.label = signupLabel;
            node.s20SignUpWidget.name = signupLabel;
        }
        node.s20UpdateApiKeyPlaceholder?.();
        resizeNode(node);
    };
    const originalCallback = modeWidget.callback;
    modeWidget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.s20UpdateApiMode = update;
    update();
}


function addApiKeyWidget(node, sourceWidget, apiModeWidget) {
    const container = document.createElement("div");
    container.style.cssText = "display:flex;flex-direction:column;gap:6px;width:100%;box-sizing:border-box";

    const inputRow = document.createElement("div");
    inputRow.style.cssText = "display:flex;align-items:center;gap:6px;width:100%;height:30px;box-sizing:border-box";
    const input = document.createElement("input");
    input.type = "password";
    input.autocomplete = "new-password";
    input.spellcheck = false;
    input.style.cssText = [
        "flex:1", "min-width:0", "width:0", "height:28px", "box-sizing:border-box",
        "border:1px solid var(--border-color, #555)", "border-radius:6px",
        "background:var(--comfy-input-bg, #1f1f1f)", "color:var(--input-text, #ddd)", "padding:0 9px",
    ].join(";");
    const updatePlaceholder = () => {
        if (apiModeWidget?.value === OPENAI_API_MODE) {
            input.placeholder = "提示词增强 LLM 的 OpenAI 兼容 API Key";
        } else if (apiModeWidget?.value === AI_WORKSHOP_API_MODE) {
            input.placeholder = "AI 工坊 API Key（可保存到工作流）";
        } else {
            input.placeholder = "贞贞提示词增强 LLM API Key（可保存到工作流）";
        }
    };
    node.s20UpdateApiKeyPlaceholder = updatePlaceholder;
    updatePlaceholder();

    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.textContent = "显示";
    reveal.title = "显示或隐藏 API Key";
    reveal.style.cssText = "flex:0 0 auto;height:28px;padding:0 9px;border:1px solid var(--border-color, #555);border-radius:6px;background:var(--comfy-input-bg, #2a2a2a);color:var(--input-text, #ddd);cursor:pointer";
    reveal.onclick = () => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        reveal.textContent = show ? "隐藏" : "显示";
    };
    inputRow.append(input, reveal);

    const actionRow = document.createElement("div");
    actionRow.style.cssText = "display:flex;gap:6px;width:100%;height:28px;box-sizing:border-box";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "💾 保存到工作流";
    save.title = "API Key 会写入工作流 JSON；分享工作流前请清空";
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "清空";
    clear.title = "从输入框和工作流中删除 API Key";
    for (const button of [save, clear]) {
        button.style.cssText = "flex:1;min-width:0;height:28px;border:1px solid var(--border-color, #555);border-radius:6px;background:var(--comfy-input-bg, #2a2a2a);color:var(--input-text, #ddd);cursor:pointer";
    }
    actionRow.append(save, clear);
    container.append(inputRow, actionRow);

    let value = String(sourceWidget.value || "");
    Object.defineProperty(sourceWidget, "value", {
        configurable: true,
        get() { return value; },
        set(nextValue) {
            value = String(nextValue || "");
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
        sourceWidget.callback?.("");
        node.graph?.change?.();
        node.setDirtyCanvas(true, true);
        save.textContent = "💾 保存到工作流";
    };
    node.s20CommitApiKey = commit;

    setWidgetVisible(sourceWidget, false);
    const secureWidget = node.addDOMWidget("seedance20_api_key_secure", "custom", container, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => 78,
        getMaxHeight: () => 78,
        hideOnZoom: false,
        serialize: false,
        beforeResize() { delete this.width; },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas(true, true);
        },
        onDraw(widget) {
            if ("width" in widget) delete widget.width;
        },
    });
    delete secureWidget.width;
    secureWidget.serializeValue = () => undefined;
}


app.registerExtension({
    name: "T8.Seedance20PromptEnhancer",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnConfigure = nodeType.prototype.onConfigure;
        const originalOnSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);

            const find = (name) => this.widgets?.find((widget) => widget.name === name);
            const promptWidget = find("prompt");
            const taskWidget = find("task_intent");
            const complexityWidget = find("complexity_mode");
            const durationWidget = find("duration_seconds");
            const shotCountWidget = find("shot_count");
            const outputLanguageWidget = find("output_language");
            const promptModeWidget = find("prompt_mode");
            const templateWidget = find("reference_template");
            const caseTemplateWidget = find("case_template");
            const apiModeWidget = find("api_mode");
            const aiWorkshopModelWidget = find("ai_workshop_model");
            const customModelWidget = find("custom_model");
            const baseUrlWidget = find("openai_base_url");
            const videoUrlsWidget = find("openai_video_urls");
            const apiKeyWidget = find("api_key");
            const seedWidget = find("seed");
            const seedControlWidget = seedWidget?.linkedWidgets?.[0] || find("control_after_generate");

            if (seedControlWidget) {
                seedControlWidget.label = "种子状态（运行后）";
                seedControlWidget.tooltip = "fixed 固定；randomize 随机；increment 递增；decrement 递减。";
            }

            this.s20UpdateTemplate = addConditionalWidget(
                this,
                promptModeWidget,
                templateWidget,
                (value) => value === "参考模板融合",
            );
            addApiModeBehavior(
                this, apiModeWidget, baseUrlWidget, videoUrlsWidget,
                aiWorkshopModelWidget, customModelWidget,
            );

            this.s20NormalizeOptions = () => {
                if (TASK_LABELS[taskWidget?.value]) taskWidget.value = TASK_LABELS[taskWidget.value];
                normalizeChoice(taskWidget, Object.values(TASK_LABELS), TASK_LABELS.AUTO);
                normalizeChoice(complexityWidget, ["AUTO（自动判断）", "简单一段式", "复杂分镜式"], "AUTO（自动判断）");
                normalizeChoice(durationWidget, [AUTO_DURATION, ...Array.from({ length: 12 }, (_, index) => String(index + 4))], AUTO_DURATION);
                normalizeChoice(shotCountWidget, [AUTO_SHOT_COUNT, ...Array.from({ length: 20 }, (_, index) => String(index + 1))], AUTO_SHOT_COUNT);
                normalizeChoice(outputLanguageWidget, ["中文", "English"], "中文");
                normalizeChoice(promptModeWidget, ["官方优化", "参考模板融合"], "官方优化");
                normalizeChoice(
                    apiModeWidget,
                    [SEEDANCE_API_MODE, AI_WORKSHOP_API_MODE, OPENAI_API_MODE],
                    SEEDANCE_API_MODE,
                );
                normalizeChoice(
                    aiWorkshopModelWidget,
                    [AI_WORKSHOP_DEFAULT_MODEL, CUSTOM_MODEL_OPTION],
                    AI_WORKSHOP_DEFAULT_MODEL,
                );
                this.s20UpdateTemplate?.();
                this.s20UpdateApiMode?.();
            };
            this.s20NormalizeOptions();

            addCaseTemplateUI(this, caseTemplateWidget, promptWidget, () => resizeNode(this));

            const advancedWidgets = [
                find("custom_length_target"), find("reference_roles"), find("reference_context"), find("constraints"),
            ].filter(Boolean);
            if (advancedWidgets.length) addAdvancedToggle(this, advancedWidgets);
            if (apiKeyWidget) addApiKeyWidget(this, apiKeyWidget, apiModeWidget);

            let queuing = false;
            const runWidget = this.addWidget(
                "button",
                "▶ 运行 Seedance 2.0 提示词优化",
                "提交当前节点",
                async () => {
                    if (queuing) return;
                    queuing = true;
                    try {
                        this.s20CommitApiKey?.();
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
                "🔑 获取贞贞提示词增强 API Key",
                "打开当前渠道注册页面",
                () => window.open(
                    apiModeWidget?.value === AI_WORKSHOP_API_MODE ? AI_WORKSHOP_SIGN_UP_URL : SIGN_UP_URL,
                    "_blank",
                    "noopener,noreferrer",
                ),
                { serialize: false },
            );
            signUpWidget.serializeValue = () => undefined;
            this.s20SignUpWidget = signUpWidget;
            this.s20UpdateApiMode?.();
            resizeNode(this);
        };

        nodeType.prototype.onConfigure = function () {
            const args = [...arguments];
            const hadLegacyUploadUrl = args[0]?.inputs?.some((input) => input.name === "openai_upload_url");
            if (Array.isArray(args[0]?.widgets_values) && [23, 25].includes(args[0].widgets_values.length)) {
                args[0] = { ...args[0], widgets_values: [...args[0].widgets_values] };
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 23) {
                args[0].widgets_values.splice(19, 0, AI_WORKSHOP_DEFAULT_MODEL, "");
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 25) {
                args[0].widgets_values.splice(9, 0, NO_CASE_TEMPLATE);
            }
            if (Array.isArray(args[0]?.widgets_values)) {
                this.t8PendingCaseTemplateValue = args[0].widgets_values[9];
            }
            originalOnConfigure?.apply(this, args);
            requestAnimationFrame(() => {
                if (hadLegacyUploadUrl) {
                    setTextWidgetValue(this.widgets?.find((widget) => widget.name === "openai_video_urls"), "");
                }
                this.t8RestoreCaseTemplate?.(this.t8PendingCaseTemplateValue);
                if (this.t8RestoreCaseTemplate) this.t8PendingCaseTemplateValue = "";
                this.s20NormalizeOptions?.();
            });
        };

        nodeType.prototype.onSerialize = function (serialized) {
            originalOnSerialize?.apply(this, arguments);
            serialized.widgets_values = SERIALIZED_WIDGET_NAMES.map((name) => {
                const widget = this.widgets?.find((item) => item.name === name);
                return name === "case_template"
                    ? serializedCaseTemplateValue(this, widget)
                    : (widget?.value ?? null);
            });
        };
    },
});
