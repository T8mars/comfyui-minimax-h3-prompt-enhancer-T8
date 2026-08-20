import { app } from "../../scripts/app.js";
import { addCaseTemplateUI, serializedCaseTemplateValue } from "./case_template_ui.js";
import { addOfficialPresetUI } from "./official_preset_previews.js";
import { showLocalQwenStatus } from "./local_qwen_status.js";


const NODE_ID = "MiniMaxH3PromptEnhancerT8";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const AI_WORKSHOP_SIGN_UP_URL = "https://ai.t8star.org/register?aff=dP7j";
const LOCAL_SKILL_BUNDLE_URL = "https://github.com/T8mars/minimax-h3-prompt-skill-T8";
const SEEDANCE_API_MODE = "贞贞平价小屋（推荐）";
const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（图片/视频）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const LOCAL_QWEN_API_MODE = "本地 Qwen3.8-27B（GGUF，离线）";
const AI_WORKSHOP_DEFAULT_MODEL = "gemini-3.5-flash";
const CUSTOM_MODEL_OPTION = "Custom（自定义）";
const AUTO_SHOT_COUNT = "AUTO（系统自动判断）";
const SHOT_COUNT_OPTIONS = [AUTO_SHOT_COUNT, ...Array.from({ length: 20 }, (_, index) => String(index + 1))];
const COMPAT_SKILL_PROFILE = "现有兼容（保留中英文）";
const STRICT_SKILL_PROFILE = "官方 Skill 严格（全英文协议）";
const OFFICIAL_SKILL_PROFILES = [COMPAT_SKILL_PROFILE, STRICT_SKILL_PROFILE];
const NO_CREATIVE_PRESET = "无（仅核心规则）";
const NO_CASE_TEMPLATE = "无（不使用 T8 案例）";
const MV_CREATIVE_PRESET = "音乐 MV 动态字幕（官方）";
const LEGACY_MV_CREATIVE_PRESET = "MV / 歌词贴字";
const CREATIVE_PRESET_OPTIONS = [
    NO_CREATIVE_PRESET,
    "AUTO（根据意图判断）",
    "极简产品广告",
    "3D 动画短片",
    "品牌宣传短片",
    MV_CREATIVE_PRESET,
    "双人合作游戏开场",
    "纸拼贴讲解",
    "立体纸艺停格讲解",
    "手绘实拍融合",
];
const MV_PROMPT_PLACEHOLDER = [
    "MV类型/音乐类型/视觉风格：",
    "歌词原文（逐字锁定，可空）：",
    "无歌词时：器乐 / 允许生成原创歌词",
    "演唱者或离屏人声：",
    "已知 BPM、歌词时间点或节拍事件（可空，节点不分析音频）：",
    "目标平台/画幅（可空）：",
    "字体包装与禁止项：",
].join("\n");
const MV_PROMPT_TOOLTIP = "官方 music-video-subtitle-generator v0.6.6：基础提示词可按占位模板填写。用户歌词会逐字锁定；只有明确写出“允许生成原创歌词”时才会补写短篇原创歌词。器乐、纯文字或离屏人声 MV 可以不填写演唱者。";
const MV_REFERENCE_CONTEXT_TOOLTIP = "MV 参考角色映射示例：<Picture 1>=人物外观；<Picture 2>=场景与灯光；<Picture 3>=字体包装，只参考字体、版式和动效，不参考人物与场景。";
const MV_CONSTRAINTS_TOOLTIP = "MV 硬性要求示例：不增加歌词；不遮挡眼睛与关键口型；不用淡入淡出；固定保留指定服装或场景。";
const MV_TEMPLATE_TOOLTIP = "仅迁移模板的镜头组织、节奏、运镜、转场和视觉语法；模板人物、歌词、BPM、标题、剧情和镜头数不会覆盖用户内容。";

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
    "official_skill_profile",
    "creative_preset",
    "case_template",
    "api_mode",
    "ai_workshop_model",
    "custom_model",
    "reference_context",
    "constraints",
    "api_key",
    "reference_template",
    "openai_base_url",
    "openai_video_urls",
    "seed",
    "control_after_generate",
    "local_model",
    "local_mmproj",
    "local_context_size",
    "local_max_tokens",
    "local_think_mode",
    "local_reasoning_effort",
    "local_video_sample_fps",
    "local_unload_policy",
    "local_comfy_memory_policy",
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


function getWidgetInput(widget) {
    return widget?.inputEl
        || (widget?.element?.matches?.("textarea, input") ? widget.element : null)
        || widget?.element?.querySelector?.("textarea, input")
        || null;
}


function addMvPresetBehavior(node, presetWidget, promptWidget, referenceContextWidget, constraintsWidget, templateWidget) {
    const tracked = [
        [promptWidget, MV_PROMPT_TOOLTIP, MV_PROMPT_PLACEHOLDER],
        [referenceContextWidget, MV_REFERENCE_CONTEXT_TOOLTIP, ""],
        [constraintsWidget, MV_CONSTRAINTS_TOOLTIP, ""],
        [templateWidget, MV_TEMPLATE_TOOLTIP, ""],
    ].filter(([widget]) => Boolean(widget));

    for (const [widget] of tracked) {
        if (!("t8MvOriginalTooltip" in widget)) widget.t8MvOriginalTooltip = widget.tooltip || "";
    }

    const update = (preset = presetWidget.value) => {
        const isMv = preset === MV_CREATIVE_PRESET;
        for (const [widget, mvTooltip, mvPlaceholder] of tracked) {
            widget.tooltip = isMv ? mvTooltip : widget.t8MvOriginalTooltip;
            const input = getWidgetInput(widget);
            if (!input) continue;
            if (!("t8MvOriginalPlaceholder" in widget)) {
                widget.t8MvOriginalPlaceholder = input.placeholder || "";
            }
            input.placeholder = isMv && mvPlaceholder ? mvPlaceholder : widget.t8MvOriginalPlaceholder;
            input.title = widget.tooltip;
        }
        node.setDirtyCanvas(true, true);
    };

    const originalCallback = presetWidget.callback;
    presetWidget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.t8UpdateMvPreset = update;
    update();
    requestAnimationFrame(() => update());
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


function addApiModeBehavior(node, modeWidget, baseUrlWidget, videoUrlsWidget, modelWidget, customModelWidget, localWidgets) {
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
        for (const widget of [baseUrlWidget, videoUrlsWidget]) {
            if (LEGACY_UI_VALUES.has(String(widget.value || "").trim())) setTextWidgetValue(widget, "");
        }
        const compatible = mode === OPENAI_API_MODE;
        const local = mode === LOCAL_QWEN_API_MODE;
        baseUrlWidget.label = "OpenAI Base URL";
        videoUrlsWidget.label = "视频素材 URL（可选，每行一个）";
        setWidgetVisible(baseUrlWidget, compatible);
        setWidgetVisible(videoUrlsWidget, compatible);
        for (const widget of localWidgets || []) setWidgetVisible(widget, local);
        updateModel();
        if (node.t8SignUpWidget) {
            setWidgetVisible(node.t8SignUpWidget, !compatible && !local);
            const signupLabel = mode === AI_WORKSHOP_API_MODE
                ? "🔑 获取 AI 工坊 API Key"
                : "🔑 获取贞贞 API Key";
            node.t8SignUpWidget.label = signupLabel;
            node.t8SignUpWidget.name = signupLabel;
        }
        if (node.t8ApiKeySecureWidget) setWidgetVisible(node.t8ApiKeySecureWidget, !local);
        if (node.t8LocalQwenStatusWidget) setWidgetVisible(node.t8LocalQwenStatusWidget, local);
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
        if (apiModeWidget?.value === OPENAI_API_MODE) {
            input.placeholder = "OpenAI兼容 API Key（输入后保存到工作流）";
        } else if (apiModeWidget?.value === AI_WORKSHOP_API_MODE) {
            input.placeholder = "AI 工坊 API Key（输入后保存到工作流）";
        } else if (apiModeWidget?.value === LOCAL_QWEN_API_MODE) {
            input.placeholder = "本地模式不需要 API Key";
        } else {
            input.placeholder = "贞贞 API Key（输入后保存到工作流）";
        }
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
    node.t8ApiKeySecureWidget = secureWidget;
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

            const promptWidget = this.widgets?.find((widget) => widget.name === "prompt");
            const outputLanguageWidget = this.widgets?.find((widget) => widget.name === "output_language");
            const rewriteModeWidget = this.widgets?.find((widget) => widget.name === "rewrite_mode");
            const taskTypeWidget = this.widgets?.find((widget) => widget.name === "task_type");
            const shotCountWidget = this.widgets?.find((widget) => widget.name === "shot_count");
            const promptModeWidget = this.widgets?.find((widget) => widget.name === "prompt_mode");
            const officialSkillProfileWidget = this.widgets?.find((widget) => widget.name === "official_skill_profile");
            const creativePresetWidget = this.widgets?.find((widget) => widget.name === "creative_preset");
            const caseTemplateWidget = this.widgets?.find((widget) => widget.name === "case_template");
            const referenceTemplateWidget = this.widgets?.find((widget) => widget.name === "reference_template");
            const referenceContextWidget = this.widgets?.find((widget) => widget.name === "reference_context");
            const constraintsWidget = this.widgets?.find((widget) => widget.name === "constraints");
            const apiKeyWidget = this.widgets?.find((widget) => widget.name === "api_key");
            const apiModeWidget = this.widgets?.find((widget) => widget.name === "api_mode");
            const aiWorkshopModelWidget = this.widgets?.find((widget) => widget.name === "ai_workshop_model");
            const customModelWidget = this.widgets?.find((widget) => widget.name === "custom_model");
            const openaiBaseUrlWidget = this.widgets?.find((widget) => widget.name === "openai_base_url");
            const openaiVideoUrlsWidget = this.widgets?.find((widget) => widget.name === "openai_video_urls");
            const seedWidget = this.widgets?.find((widget) => widget.name === "seed");
            const localWidgets = [
                "local_model", "local_mmproj", "local_context_size", "local_max_tokens",
                "local_think_mode", "local_reasoning_effort", "local_video_sample_fps",
                "local_unload_policy", "local_comfy_memory_policy",
            ].map((name) => this.widgets?.find((widget) => widget.name === name)).filter(Boolean);
            const seedControlWidget = seedWidget?.linkedWidgets?.[0]
                || this.widgets?.find((widget) => widget.name === "control_after_generate");
            if (seedControlWidget) {
                seedControlWidget.label = "种子状态（运行后）";
                seedControlWidget.tooltip = "fixed 固定；randomize 随机；increment 递增；decrement 递减。";
            }
            if (rewriteModeWidget) {
                rewriteModeWidget.tooltip = "改写模式只控制扩写幅度：strict 最保守，balanced 平衡补全，creative 更具创造性；它不控制官方协议语言。";
            }
            if (officialSkillProfileWidget) {
                officialSkillProfileWidget.label = "H3 核心写作 Skill（始终启用）";
                officialSkillProfileWidget.tooltip = "官方 9 个 Skill = 1 个始终启用的 H3 核心写作 Skill + 8 个可选场景 Skill。这里控制核心规范的输出协议：兼容模式服从中文/English，严格模式强制英文说明；它不等同于改写模式 strict。";
            }
            if (creativePresetWidget) {
                creativePresetWidget.label = "MiniMax 官方场景 Skill（8 个可选）";
                creativePresetWidget.tooltip = "选择一个官方场景 Skill 后，节点下方会显示用途、推荐输入、结构锚点、官方 GIF 与来源；GIF 不会发送给 LLM。";
            }

            if (promptModeWidget && referenceTemplateWidget) {
                addReferenceTemplateBehavior(this, promptModeWidget, referenceTemplateWidget);
            }
            if (apiModeWidget && openaiBaseUrlWidget && openaiVideoUrlsWidget && aiWorkshopModelWidget && customModelWidget) {
                addApiModeBehavior(
                    this, apiModeWidget, openaiBaseUrlWidget, openaiVideoUrlsWidget,
                    aiWorkshopModelWidget, customModelWidget, localWidgets,
                );
            }
            if (creativePresetWidget && promptWidget) {
                addMvPresetBehavior(this, creativePresetWidget, promptWidget, referenceContextWidget, constraintsWidget, referenceTemplateWidget);
            }
            this.t8NormalizePromptOptions = () => {
                if (TASK_TYPE_LABELS[taskTypeWidget?.value]) taskTypeWidget.value = TASK_TYPE_LABELS[taskTypeWidget.value];
                normalizeChoice(taskTypeWidget, Object.values(TASK_TYPE_LABELS), TASK_TYPE_LABELS.T2VA);
                normalizeChoice(shotCountWidget, SHOT_COUNT_OPTIONS, AUTO_SHOT_COUNT);
                normalizeChoice(outputLanguageWidget, ["中文", "English"], "中文");
                normalizeChoice(promptModeWidget, ["官方增强", "参考模板融合"], "官方增强");
                normalizeChoice(officialSkillProfileWidget, OFFICIAL_SKILL_PROFILES, COMPAT_SKILL_PROFILE);
                if (creativePresetWidget?.value === LEGACY_MV_CREATIVE_PRESET) {
                    creativePresetWidget.value = MV_CREATIVE_PRESET;
                }
                normalizeChoice(creativePresetWidget, CREATIVE_PRESET_OPTIONS, NO_CREATIVE_PRESET);
                normalizeChoice(
                    apiModeWidget,
                    [SEEDANCE_API_MODE, AI_WORKSHOP_API_MODE, OPENAI_API_MODE, LOCAL_QWEN_API_MODE],
                    SEEDANCE_API_MODE,
                );
                normalizeChoice(
                    aiWorkshopModelWidget,
                    [AI_WORKSHOP_DEFAULT_MODEL, CUSTOM_MODEL_OPTION],
                    AI_WORKSHOP_DEFAULT_MODEL,
                );
                if (LEGACY_UI_VALUES.has(String(apiKeyWidget?.value || "").trim())) apiKeyWidget.value = "";
                for (const widget of [referenceContextWidget, constraintsWidget, referenceTemplateWidget, customModelWidget, openaiBaseUrlWidget, openaiVideoUrlsWidget]) {
                    const value = String(widget?.value || "").trim();
                    if (LEGACY_UI_VALUES.has(value)) setTextWidgetValue(widget, "");
                    if (API_KEY_PATTERN.test(value)) {
                        if (!String(apiKeyWidget?.value || "").trim()) apiKeyWidget.value = value;
                        setTextWidgetValue(widget, "");
                    }
                }
                this.t8UpdateReferenceTemplate?.();
                this.t8UpdateApiMode?.();
                this.t8UpdateMvPreset?.();
                this.t8UpdateOfficialPreset?.();
            };
            this.t8NormalizePromptOptions();

            addOfficialPresetUI(this, creativePresetWidget, promptWidget, () => resizeNode(this));
            addCaseTemplateUI(this, caseTemplateWidget, promptWidget, () => resizeNode(this));

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
                "打开当前渠道注册页面",
                () => window.open(
                    apiModeWidget?.value === AI_WORKSHOP_API_MODE ? AI_WORKSHOP_SIGN_UP_URL : SIGN_UP_URL,
                    "_blank",
                    "noopener,noreferrer",
                ),
                { serialize: false },
            );
            signUpWidget.serializeValue = () => undefined;
            this.t8SignUpWidget = signUpWidget;

            const localStatusWidget = this.addWidget(
                "button",
                "🧩 检查本地 Qwen 安装",
                "查看 GGUF、mmproj 与 llama.cpp 运行时状态",
                showLocalQwenStatus,
                { serialize: false },
            );
            localStatusWidget.serializeValue = () => undefined;
            this.t8LocalQwenStatusWidget = localStatusWidget;

            const localSkillBundleWidget = this.addWidget(
                "button",
                "MiniMax & Seedance本地Skill和整合包",
                "在新标签页打开本地 Skill 与整合包",
                () => window.open(LOCAL_SKILL_BUNDLE_URL, "_blank", "noopener,noreferrer"),
                { serialize: false },
            );
            localSkillBundleWidget.serializeValue = () => undefined;
            this.t8UpdateApiMode?.();
            resizeNode(this);
        };
        nodeType.prototype.onConfigure = function () {
            const args = [...arguments];
            const serialized = args[0];
            const hadLegacyUploadUrl = serialized?.inputs?.some((input) => input.name === "openai_upload_url");
            if (Array.isArray(serialized?.widgets_values)
                && [16, 17, 19, 21].includes(serialized.widgets_values.length)) {
                args[0] = { ...serialized, widgets_values: [...serialized.widgets_values] };
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 16) {
                args[0].widgets_values.splice(3, 0, AUTO_SHOT_COUNT);
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 17) {
                args[0].widgets_values.splice(8, 0, COMPAT_SKILL_PROFILE, NO_CREATIVE_PRESET);
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 19) {
                args[0].widgets_values.splice(11, 0, AI_WORKSHOP_DEFAULT_MODEL, "");
            }
            if (Array.isArray(args[0]?.widgets_values) && args[0].widgets_values.length === 21) {
                args[0].widgets_values.splice(10, 0, NO_CASE_TEMPLATE);
            }
            if (Array.isArray(args[0]?.widgets_values)) {
                this.t8PendingCaseTemplateValue = args[0].widgets_values[10];
            }
            originalOnConfigure?.apply(this, args);
            requestAnimationFrame(() => {
                if (hadLegacyUploadUrl) {
                    setTextWidgetValue(this.widgets?.find((widget) => widget.name === "openai_video_urls"), "");
                }
                this.t8RestoreCaseTemplate?.(this.t8PendingCaseTemplateValue);
                if (this.t8RestoreCaseTemplate) this.t8PendingCaseTemplateValue = "";
                this.t8NormalizePromptOptions?.();
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
