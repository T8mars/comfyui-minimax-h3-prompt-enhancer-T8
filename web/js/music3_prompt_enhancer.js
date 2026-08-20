import { app } from "../../scripts/app.js";
import { showLocalQwenStatus } from "./local_qwen_status.js";


const NODE_ID = "MiniMaxMusic3PromptEnhancerT8";
const SIGN_UP_URL = "https://api.seedance.nz/sign-up?aff=5f4w";
const AI_WORKSHOP_SIGN_UP_URL = "https://ai.t8star.org/register?aff=dP7j";
const LOCAL_SKILL_BUNDLE_URL = "https://github.com/T8mars/minimax-h3-prompt-skill-T8";
const SEEDANCE_API_MODE = "贞贞平价小屋（推荐）";
const AI_WORKSHOP_API_MODE = "贞贞的AI工坊（文本 LLM）";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const LOCAL_QWEN_API_MODE = "本地 Qwen3.8-27B（GGUF，离线）";
const AI_WORKSHOP_DEFAULT_MODEL = "gemini-3.5-flash";
const CUSTOM_MODEL_OPTION = "Custom（自定义）";
const CUSTOM_LANGUAGE = "Custom（自定义）";
const CUSTOM_STRUCTURE = "Custom（自定义）";
const CUSTOM_METER = "Custom（自定义）";
const EDIT_LYRICS_MODE = "按要求润色（T8非官方）";
const GENERATE_LYRICS_MODE = "生成新歌词（T8非官方）";
const PRESERVE_LYRICS_MODE = "严格保留歌词";
const INSTRUMENTAL_MODE = "纯器乐";
const AUTO_LYRICS_MODE = "AUTO（有词保留，无词按意图）";
const FULL_QUALITY_MODE = "官方完整（2–4次请求，推荐）";
const EDIT_SCOPE_AUTO = "AUTO（从润色要求识别）";
const EDIT_SCOPE_SECTION = "指定段落（全部同名段）";
const EDIT_SCOPE_OCCURRENCE = "指定段落（第N次）";
const SEMANTIC_MANUAL_MODE = "手动宽泛画像（不增加请求）";
const SEMANTIC_LLM_MODE = "LLM宽泛分析（会发送歌词并可能增加请求）";
const STATUS_CARD_HEIGHT = 176;
const MUSIC_API_MODES = [SEEDANCE_API_MODE, AI_WORKSHOP_API_MODE, OPENAI_API_MODE, LOCAL_QWEN_API_MODE];
const PUBLISHED_V1_WIDGET_NAMES = [
    "music_idea",
    "lyrics_mode",
    "lyrics",
    "lyrics_language",
    "target_duration_seconds",
    "rewrite_mode",
    "quality_mode",
    "structure_preset",
    "custom_structure",
    "lyrics_edit_request",
    "constraints_and_exclusions",
    "custom_lyrics_language",
    "fixed_bpm",
    "key_scale",
    "meter",
    "custom_meter",
    "caption_language",
    "caption_target_words",
    "api_key",
    "api_mode",
    "ai_workshop_model",
    "custom_model",
    "openai_base_url",
    "seed",
    "control_after_generate",
    "lyrics_edit_scope",
    "lyrics_edit_section",
    "lyrics_edit_occurrence",
    "semantic_profile_mode",
    "manual_lyrics_profile",
    "stage_cache",
];
// ComfyUI groups required inputs before optional inputs, independently of the
// declaration order. This was the real runtime order in the first release.
const RUNTIME_V1_WIDGET_NAMES = [
    "music_idea",
    "lyrics_mode",
    "lyrics_language",
    "target_duration_seconds",
    "rewrite_mode",
    "quality_mode",
    "structure_preset",
    "fixed_bpm",
    "meter",
    "caption_language",
    "caption_target_words",
    "api_mode",
    "ai_workshop_model",
    "seed",
    "control_after_generate",
    "lyrics_edit_scope",
    "lyrics_edit_section",
    "lyrics_edit_occurrence",
    "semantic_profile_mode",
    "stage_cache",
    "lyrics",
    "custom_structure",
    "lyrics_edit_request",
    "constraints_and_exclusions",
    "custom_lyrics_language",
    "key_scale",
    "custom_meter",
    "api_key",
    "custom_model",
    "openai_base_url",
    "manual_lyrics_profile",
];
// Lyrics is now a normal empty-by-default widget so it stays beside lyrics_mode.
// Optional/conditional text fields remain later and are hidden until required.
const SERIALIZED_WIDGET_NAMES = [
    "music_idea",
    "lyrics_mode",
    "lyrics",
    "lyrics_language",
    "target_duration_seconds",
    "rewrite_mode",
    "quality_mode",
    "structure_preset",
    "fixed_bpm",
    "meter",
    "caption_language",
    "caption_target_words",
    "api_mode",
    "ai_workshop_model",
    "seed",
    "control_after_generate",
    "lyrics_edit_scope",
    "lyrics_edit_section",
    "lyrics_edit_occurrence",
    "semantic_profile_mode",
    "stage_cache",
    "custom_structure",
    "lyrics_edit_request",
    "constraints_and_exclusions",
    "custom_lyrics_language",
    "key_scale",
    "custom_meter",
    "api_key",
    "custom_model",
    "openai_base_url",
    "manual_lyrics_profile",
    "local_model",
    "local_context_size",
    "local_max_tokens",
    "local_think_mode",
    "local_reasoning_effort",
    "local_unload_policy",
    "local_comfy_memory_policy",
];


function setWidgetVisible(widget, visible) {
    if (!widget) return;

    if (!("music3OriginalType" in widget)) {
        widget.music3OriginalType = widget.type;
        widget.music3OriginalComputeSize = widget.computeSize;
        widget.music3OriginalDisplay = widget.element?.style.display || "";
        widget.music3OriginalHidden = Boolean(widget.hidden);
    }

    widget.type = visible ? widget.music3OriginalType : "converted-widget";
    widget.computeSize = visible ? widget.music3OriginalComputeSize : () => [0, -4];
    widget.hidden = visible ? widget.music3OriginalHidden : true;
    widget.disabled = !visible;
    if (widget.element) {
        widget.element.dataset.shouldHide = visible ? "false" : "true";
        widget.element.style.display = visible ? widget.music3OriginalDisplay : "none";
        widget.element.hidden = !visible;
    }
}


function resizeNode(node) {
    if (!node || node.music3ResizeScheduled) return;
    node.music3ResizeScheduled = true;
    requestAnimationFrame(() => {
        try {
            for (const widget of node.widgets || []) {
                if (widget.element) delete widget.computedHeight;
            }
            const computed = node.computeSize?.() || [520, node.size?.[1] || 420];
            const nextWidth = Math.max(Number(node.size?.[0]) || 0, 560);
            const nextHeight = Math.max(Number(computed[1]) || 0, 320);
            const widthChanged = Math.abs((Number(node.size?.[0]) || 0) - nextWidth) > 0.5;
            const heightChanged = Math.abs((Number(node.size?.[1]) || 0) - nextHeight) > 0.5;
            if (widthChanged || heightChanged) node.setSize?.([nextWidth, nextHeight]);
            node.setDirtyCanvas?.(true, true);
            app.canvas?.setDirty?.(true, true);
        } finally {
            node.music3ResizeScheduled = false;
        }
    });
}


function serializedWidgetValueMap(values) {
    if (!Array.isArray(values)) return null;
    if (values.length === SERIALIZED_WIDGET_NAMES.length) {
        return new Map(SERIALIZED_WIDGET_NAMES.map((name, index) => [name, values[index]]));
    }
    if (values.length !== PUBLISHED_V1_WIDGET_NAMES.length) return null;
    let sourceNames;
    if (MUSIC_API_MODES.includes(String(values[19] || ""))) {
        sourceNames = PUBLISHED_V1_WIDGET_NAMES;
    } else if (MUSIC_API_MODES.includes(String(values[11] || ""))) {
        sourceNames = RUNTIME_V1_WIDGET_NAMES;
    } else {
        return null;
    }
    return new Map(sourceNames.map((name, index) => [name, values[index]]));
}


function remapSerializedWidgetValues(values) {
    const source = serializedWidgetValueMap(values);
    if (!source) return values;
    return SERIALIZED_WIDGET_NAMES.map((name) => source.get(name) ?? null);
}


function addAdvancedControls(node, widgets, updateConditional) {
    node.music3AdvancedExpanded = false;
    const toggle = node.addWidget(
        "button",
        "⚙️ 高级音乐选项（可选）",
        "展开",
        () => {
            node.music3AdvancedExpanded = !node.music3AdvancedExpanded;
            toggle.value = node.music3AdvancedExpanded ? "收起" : "展开";
            updateConditional();
            resizeNode(node);
        },
        { serialize: false },
    );
    toggle.serializeValue = () => undefined;
    for (const widget of widgets) setWidgetVisible(widget, false);
}


function addRequestEstimateWidget(node, widgets) {
    const container = document.createElement("div");
    container.style.cssText = [
        "display:flex", "flex-direction:column", "gap:5px", "width:100%", "box-sizing:border-box",
        "padding:8px 10px", "border:1px solid var(--border-color, #555)", "border-radius:7px",
        "background:var(--comfy-input-bg, #202020)", "color:var(--input-text, #ddd)", "font-size:12px",
        "line-height:1.45", "white-space:normal", "overflow-wrap:anywhere", `height:${STATUS_CARD_HEIGHT}px`, "overflow:auto",
    ].join(";");
    const officialTitle = document.createElement("div");
    officialTitle.textContent = "官方 Skill：Music Caption 结构化改写";
    officialTitle.style.cssText = "font-weight:700;color:var(--input-text, #eee)";
    const officialDescription = document.createElement("div");
    officialDescription.textContent = "输出 Global Metadata / Vocal Details / Arrangement；“官方完整”会再启用流派路由与最多 3 个官方模板。歌词生成与润色属于 T8 非官方扩展。";
    officialDescription.style.opacity = "0.9";
    const estimate = document.createElement("div");
    estimate.style.fontWeight = "600";
    const stages = document.createElement("div");
    stages.style.opacity = "0.82";
    const hiddenLyrics = document.createElement("div");
    hiddenLyrics.style.cssText = "display:none;align-items:center;flex-wrap:wrap;gap:8px;color:#f0c674";
    const hiddenText = document.createElement("span");
    hiddenText.textContent = "纯器乐模式下工作流仍保存着隐藏歌词。";
    const clearLyrics = document.createElement("button");
    clearLyrics.type = "button";
    clearLyrics.textContent = "清空隐藏歌词";
    clearLyrics.style.cssText = "height:24px;padding:0 8px;border:1px solid var(--border-color, #666);border-radius:5px;background:#2a2a2a;color:#ddd;cursor:pointer";
    clearLyrics.onclick = () => {
        if (widgets.lyrics) {
            widgets.lyrics.value = "";
            widgets.lyrics.callback?.("");
        }
        node.graph?.change?.();
        node.music3UpdateEstimate?.();
    };
    hiddenLyrics.append(hiddenText, clearLyrics);
    container.append(officialTitle, officialDescription, estimate, stages, hiddenLyrics);


    const update = () => {
        const mode = widgets.lyricsMode?.value;
        const hasLyrics = Boolean(String(widgets.lyrics?.value || "").trim());
        const effectiveMode = mode === AUTO_LYRICS_MODE
            ? (hasLyrics ? PRESERVE_LYRICS_MODE : GENERATE_LYRICS_MODE)
            : mode;
        let minimum = 1;
        let maximum = 1;
        const stageNames = [];
        if (effectiveMode === GENERATE_LYRICS_MODE || effectiveMode === EDIT_LYRICS_MODE) {
            minimum += 1;
            maximum += 1;
            stageNames.push(effectiveMode === EDIT_LYRICS_MODE ? "歌词润色" : "歌词生成");
            if (effectiveMode === GENERATE_LYRICS_MODE) {
                maximum += 1;
                stageNames.push("歌词语言纠正（仅检测不符时）");
            }
        }
        if (widgets.quality?.value === FULL_QUALITY_MODE) {
            minimum += 1;
            maximum += 2;
            stageNames.push("官方路由（按需）", "参考选择");
        }
        if (widgets.semantic?.value === SEMANTIC_LLM_MODE && effectiveMode === PRESERVE_LYRICS_MODE) {
            minimum += 1;
            maximum += 1;
            stageNames.push("宽泛歌词画像");
        }
        stageNames.push("Caption 编译");
        const local = widgets.apiMode?.value === LOCAL_QWEN_API_MODE;
        const requestKind = local ? "本地推理阶段" : "预计付费请求";
        estimate.textContent = minimum === maximum
            ? `${requestKind}：${minimum} 次（命中10分钟阶段缓存时可为0）`
            : `${requestKind}：${minimum}–${maximum} 次（命中10分钟阶段缓存时会减少）`;
        stages.textContent = `阶段：本地资源检查 → ${stageNames.join(" → ")}`;
        hiddenLyrics.style.display = mode === INSTRUMENTAL_MODE && hasLyrics ? "flex" : "none";
        node.setDirtyCanvas?.(true, true);
    };
    node.music3UpdateEstimate = update;
    const statusWidget = node.addDOMWidget("music3_request_estimate", "custom", container, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => STATUS_CARD_HEIGHT,
        getMaxHeight: () => STATUS_CARD_HEIGHT,
        hideOnZoom: false,
        serialize: false,
        beforeResize() { delete this.width; },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas?.(true, true);
        },
        onDraw(widget) { if ("width" in widget) delete widget.width; },
    });
    statusWidget.computeSize = () => [0, STATUS_CARD_HEIGHT];
    delete statusWidget.width;
    statusWidget.serializeValue = () => undefined;
    update();
}


function addApiModeBehavior(node, modeWidget, modelWidget, customModelWidget, baseUrlWidget) {
    const update = () => {
        const workshop = modeWidget?.value === AI_WORKSHOP_API_MODE;
        const compatible = modeWidget?.value === OPENAI_API_MODE;
        const local = modeWidget?.value === LOCAL_QWEN_API_MODE;
        setWidgetVisible(modelWidget, workshop);
        setWidgetVisible(customModelWidget, compatible || (workshop && modelWidget?.value === CUSTOM_MODEL_OPTION));
        setWidgetVisible(baseUrlWidget, compatible);
        if (customModelWidget) {
            customModelWidget.label = compatible ? "OpenAI 模型 ID（必填）" : "AI工坊自定义模型 ID";
        }
        if (node.music3SignUpWidget) {
            setWidgetVisible(node.music3SignUpWidget, !compatible && !local);
            const label = workshop ? "🔑 获取 AI 工坊 API Key" : "🔑 获取贞贞 API Key";
            node.music3SignUpWidget.label = label;
            node.music3SignUpWidget.name = label;
        }
        if (node.music3ApiKeySecureWidget) setWidgetVisible(node.music3ApiKeySecureWidget, !local);
        if (node.music3LocalQwenStatusWidget) setWidgetVisible(node.music3LocalQwenStatusWidget, local);
        node.music3UpdateConditional?.();
        node.music3UpdateApiKeyPlaceholder?.();
        resizeNode(node);
    };
    const originalModeCallback = modeWidget?.callback;
    if (modeWidget) {
        modeWidget.callback = function () {
            originalModeCallback?.apply(this, arguments);
            update();
        };
    }
    const originalModelCallback = modelWidget?.callback;
    if (modelWidget) {
        modelWidget.callback = function () {
            originalModelCallback?.apply(this, arguments);
            update();
        };
    }
    node.music3UpdateApiMode = update;
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
            input.placeholder = "Music 3 提示词 LLM 的 OpenAI 兼容 API Key";
        } else if (apiModeWidget?.value === AI_WORKSHOP_API_MODE) {
            input.placeholder = "AI 工坊 API Key（可保存到工作流）";
        } else if (apiModeWidget?.value === LOCAL_QWEN_API_MODE) {
            input.placeholder = "本地模式不需要 API Key";
        } else {
            input.placeholder = "贞贞 API Key（可保存到工作流）";
        }
    };
    node.music3UpdateApiKeyPlaceholder = updatePlaceholder;
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
        node.setDirtyCanvas?.(true, true);
    });

    const commit = () => {
        sourceWidget.value = input.value.trim();
        sourceWidget.callback?.(sourceWidget.value);
        node.graph?.change?.();
        node.setDirtyCanvas?.(true, true);
        save.textContent = "✓ 已保存到工作流";
    };
    save.onclick = commit;
    clear.onclick = () => {
        input.value = "";
        sourceWidget.value = "";
        sourceWidget.callback?.("");
        node.graph?.change?.();
        node.setDirtyCanvas?.(true, true);
        save.textContent = "💾 保存到工作流";
    };
    node.music3CommitApiKey = commit;

    setWidgetVisible(sourceWidget, false);
    const secureWidget = node.addDOMWidget("music3_api_key_secure", "custom", container, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => 78,
        getMaxHeight: () => 78,
        hideOnZoom: false,
        serialize: false,
        beforeResize() { delete this.width; },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas?.(true, true);
        },
        onDraw(widget) {
            if ("width" in widget) delete widget.width;
        },
    });
    delete secureWidget.width;
    secureWidget.serializeValue = () => undefined;
    node.music3ApiKeySecureWidget = secureWidget;
}


app.registerExtension({
    name: "T8.MiniMaxMusic3PromptEnhancer",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnConfigure = nodeType.prototype.onConfigure;
        const originalOnSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onNodeCreated = function () {
            originalOnNodeCreated?.apply(this, arguments);
            const find = (name) => this.widgets?.find((widget) => widget.name === name);
            const lyricsModeWidget = find("lyrics_mode");
            const lyricsWidget = find("lyrics");
            const qualityWidget = find("quality_mode");
            const languageWidget = find("lyrics_language");
            const customLanguageWidget = find("custom_lyrics_language");
            const structureWidget = find("structure_preset");
            const customStructureWidget = find("custom_structure");
            const editRequestWidget = find("lyrics_edit_request");
            const constraintsWidget = find("constraints_and_exclusions");
            const fixedBpmWidget = find("fixed_bpm");
            const keyScaleWidget = find("key_scale");
            const meterWidget = find("meter");
            const customMeterWidget = find("custom_meter");
            const captionLanguageWidget = find("caption_language");
            const captionWordsWidget = find("caption_target_words");
            const apiKeyWidget = find("api_key");
            const apiModeWidget = find("api_mode");
            const aiWorkshopModelWidget = find("ai_workshop_model");
            const customModelWidget = find("custom_model");
            const baseUrlWidget = find("openai_base_url");
            const seedWidget = find("seed");
            const editScopeWidget = find("lyrics_edit_scope");
            const editSectionWidget = find("lyrics_edit_section");
            const editOccurrenceWidget = find("lyrics_edit_occurrence");
            const semanticModeWidget = find("semantic_profile_mode");
            const manualProfileWidget = find("manual_lyrics_profile");
            const stageCacheWidget = find("stage_cache");
            const localWidgets = [
                "local_model", "local_context_size", "local_max_tokens", "local_think_mode",
                "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy",
            ].map(find).filter(Boolean);
            const seedControlWidget = seedWidget?.linkedWidgets?.[0] || find("control_after_generate");
            if (lyricsModeWidget) {
                lyricsModeWidget.tooltip = "这里控制歌词工作流；生成/润色是 T8 非官方扩展，官方 Skill 的正式能力是下方 music_caption 结构化改写。";
            }
            if (lyricsWidget) {
                lyricsWidget.tooltip = "仅供 AUTO、严格保留和润色模式使用；生成新歌词模式会隐藏并忽略此框的正文。";
            }
            if (languageWidget) {
                languageWidget.label = "歌词语言（只控制歌词）";
                languageWidget.tooltip = "只控制 lyrics 输出，不改变官方 Music Caption 的描述语言。AUTO 会从音乐创意和已有歌词文字推断。";
            }
            if (qualityWidget) {
                qualityWidget.label = "官方 Skill 质量模式";
                qualityWidget.tooltip = "快速核心只执行官方三段 Caption 合同；官方完整再执行流派路由、索引筛选与最多三个官方模板参考。";
            }
            if (seedControlWidget) {
                seedControlWidget.label = "种子状态（运行后）";
                seedControlWidget.tooltip = "fixed 固定；randomize 随机；increment 递增；decrement 递减。供应商不保证绝对复现。";
            }

            const advancedWidgets = [
                structureWidget, customStructureWidget, editRequestWidget, constraintsWidget,
                customLanguageWidget, fixedBpmWidget, keyScaleWidget, meterWidget,
                customMeterWidget, captionLanguageWidget, captionWordsWidget, editScopeWidget,
                editSectionWidget, editOccurrenceWidget, semanticModeWidget, manualProfileWidget,
                stageCacheWidget,
                ...localWidgets,
            ].filter(Boolean);
            const updateConditional = () => {
                const expanded = Boolean(this.music3AdvancedExpanded);
                setWidgetVisible(lyricsWidget, ![INSTRUMENTAL_MODE, GENERATE_LYRICS_MODE].includes(lyricsModeWidget?.value));
                setWidgetVisible(structureWidget, expanded);
                setWidgetVisible(customStructureWidget, expanded && structureWidget?.value === CUSTOM_STRUCTURE);
                setWidgetVisible(editRequestWidget, expanded && lyricsModeWidget?.value === EDIT_LYRICS_MODE);
                setWidgetVisible(constraintsWidget, expanded);
                setWidgetVisible(customLanguageWidget, expanded && languageWidget?.value === CUSTOM_LANGUAGE);
                setWidgetVisible(fixedBpmWidget, expanded);
                setWidgetVisible(keyScaleWidget, expanded);
                setWidgetVisible(meterWidget, expanded);
                setWidgetVisible(customMeterWidget, expanded && meterWidget?.value === CUSTOM_METER);
                setWidgetVisible(captionLanguageWidget, expanded);
                setWidgetVisible(captionWordsWidget, expanded);
                const editing = lyricsModeWidget?.value === EDIT_LYRICS_MODE;
                setWidgetVisible(editScopeWidget, expanded && editing);
                const structuredScope = editScopeWidget?.value === EDIT_SCOPE_SECTION || editScopeWidget?.value === EDIT_SCOPE_OCCURRENCE;
                setWidgetVisible(editSectionWidget, expanded && editing && structuredScope);
                setWidgetVisible(editOccurrenceWidget, expanded && editing && editScopeWidget?.value === EDIT_SCOPE_OCCURRENCE);
                setWidgetVisible(semanticModeWidget, expanded);
                setWidgetVisible(manualProfileWidget, expanded && semanticModeWidget?.value === SEMANTIC_MANUAL_MODE);
                setWidgetVisible(stageCacheWidget, expanded);
                const local = apiModeWidget?.value === LOCAL_QWEN_API_MODE;
                for (const widget of localWidgets) setWidgetVisible(widget, expanded && local);
                this.music3UpdateEstimate?.();
                resizeNode(this);
            };
            this.music3UpdateConditional = updateConditional;
            addAdvancedControls(this, advancedWidgets, updateConditional);

            for (const controller of [
                lyricsModeWidget, lyricsWidget, languageWidget, structureWidget, meterWidget,
                editScopeWidget, semanticModeWidget, qualityWidget,
            ]) {
                if (!controller) continue;
                const callback = controller.callback;
                controller.callback = function () {
                    callback?.apply(this, arguments);
                    updateConditional();
                };
            }
            addApiModeBehavior(this, apiModeWidget, aiWorkshopModelWidget, customModelWidget, baseUrlWidget);
            if (apiKeyWidget) addApiKeyWidget(this, apiKeyWidget, apiModeWidget);

            let queuing = false;
            const runWidget = this.addWidget(
                "button",
                "▶ 运行 Music 3 提示词与歌词优化",
                "提交当前节点",
                async () => {
                    if (queuing) return;
                    queuing = true;
                    try {
                        this.music3CommitApiKey?.();
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
            this.music3SignUpWidget = signUpWidget;

            const localStatusWidget = this.addWidget(
                "button",
                "🧩 检查本地 Qwen 安装",
                "查看 GGUF 与 llama.cpp 运行时状态；Music 3 不加载 mmproj",
                showLocalQwenStatus,
                { serialize: false },
            );
            localStatusWidget.serializeValue = () => undefined;
            this.music3LocalQwenStatusWidget = localStatusWidget;

            const localSkillBundleWidget = this.addWidget(
                "button",
                "MiniMax & Seedance本地Skill和整合包",
                "在新标签页打开本地 Skill 与整合包",
                () => window.open(LOCAL_SKILL_BUNDLE_URL, "_blank", "noopener,noreferrer"),
                { serialize: false },
            );
            localSkillBundleWidget.serializeValue = () => undefined;
            // Keep all actionable controls above the variable-height status
            // card. Even on frontend builds that mis-cache DOM widget heights,
            // wrapped explanatory text can no longer cover Run or API Key.
            addRequestEstimateWidget(this, {
                lyricsMode: lyricsModeWidget,
                lyrics: lyricsWidget,
                quality: qualityWidget,
                semantic: semanticModeWidget,
                apiMode: apiModeWidget,
            });
            this.music3UpdateApiMode?.();
            updateConditional();
            resizeNode(this);
        };

        nodeType.prototype.onConfigure = function () {
            const args = [...arguments];
            const restoredValues = serializedWidgetValueMap(args[0]?.widgets_values);
            if (Array.isArray(args[0]?.widgets_values)) {
                args[0] = {
                    ...args[0],
                    widgets_values: remapSerializedWidgetValues([...args[0].widgets_values]),
                };
            }
            originalOnConfigure?.apply(this, args);
            requestAnimationFrame(() => {
                // Restore by stable field name as a second compatibility layer.
                // Several ComfyUI versions calculate hidden/optional DOM widget
                // positions differently, so positional remapping alone can still
                // shift API mode, seed and advanced fields in old workflows.
                if (restoredValues) {
                    for (const [name, value] of restoredValues) {
                        const widget = this.widgets?.find((item) => item.name === name);
                        if (widget) widget.value = value;
                    }
                }
                this.music3UpdateConditional?.();
                this.music3UpdateApiMode?.();
                this.music3UpdateEstimate?.();
                resizeNode(this);
            });
        };

        nodeType.prototype.onSerialize = function (serialized) {
            originalOnSerialize?.apply(this, arguments);
            serialized.widgets_values = SERIALIZED_WIDGET_NAMES.map((name) => {
                const widget = this.widgets?.find((item) => item.name === name);
                return widget?.value ?? null;
            });
        };
    },
});
