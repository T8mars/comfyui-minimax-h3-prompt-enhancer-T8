import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";
import { showRedactedDiagnostics } from "./diagnostics_viewer.mjs";
import { showProviderCapability } from "./provider_capability_ui.mjs";
import { showLocalQwenStatus } from "./local_qwen_status.js";
import { MOSS_ID, MOSS_NAMES, COMPILE, API_MODES, CANVAS_PRESETS, configureMoss, serializeMoss,
    effectiveMossMode, linkedMossProvider, refreshMoss, drawMossLinkedLabels, mossStatus, layoutPreview } from "./moss_image_ui.mjs";

const CONFIG_CALLBACK = Symbol("t8MossConfigCallback");
function observeSharedConfig(node) {
    const source = linkedMossProvider(node);
    if (!source) return;
    for (const widget of source.widgets || []) {
        if (widget[CONFIG_CALLBACK]) continue;
        widget[CONFIG_CALLBACK] = true;
        const previous = widget.callback;
        widget.callback = function () {
            const result = previous?.apply(this, arguments);
            for (const item of source.graph?._nodes || []) {
                if (!item.t8MossRemoved && linkedMossProvider(item) === source) item.t8MossInvalidate?.();
            }
            return result;
        };
    }
}

const HELP = "MOSS Image Prompt Enhancer T8\n"
    + "1. 写需求即可。AUTO选自然描述或布局；只有需要文字/空间定位才用Layout。\n"
    + "2. positive_prompt接MOSS正向文本编码；width/height接最终latent。draft_json是可编辑草稿，report_json是诊断，不能接正向。\n"
    + "3. 默认1024×1024，支持8的倍数（至少16），不擅自取整。生成Layout按节点尺寸；仅编译Layout按草稿尺寸。下游latent可能自行对齐，请核对实际出图尺寸。\n"
    + "4. 高级锁文案：一个完整块，或JSON字符串数组；换行/重复次数须保持，多个块分别对应text项。描述语言不改变文案语言。\n"
    + "5. 仅编译用abs/xyxy原始JSON，不需要Key或模型。不能误贴abs_centralized成品再居中。\n"
    + "6. 参考图仅供增强LLM理解，不是MOSS原生编辑；云端时图像会发送所选增强服务，不承诺身份保真。\n"
    + "7. 默认最多1次额外纠正，可关为0。硬失败不输出坏JSON或空提示词；可查看失败草稿。软字数超限保留完整结果。\n"
    + "8. MOSS官方编码器含包装后截断至4096 tokens。本节点未运行匹配分词器，不把字符数或LLM预算当防截断证明。\n"
    + "9. 恢复读取当前进程中上次成功完整结果，不重新增强；通常保存1小时，超限/过期不可恢复。\n"
    + "10. 最大描述字数现位于主界面：0=自动。按Unicode码点统计，含空格标点；Layout只计summary与各项caption，不计可见text、坐标和JSON包装。它是软上限，保留完整稿，不是Token或防截断保证。\n"
    + "11. Classic保持原版；Comic用于单张/单页漫画；Fisher用于单张通用强化。完整漫画双语/多页和多参考独立稿属于独立编排入口，本节点不会暗中规划整本、翻译或合并多张参考。\n"
    + "12. Fisher自动语言默认中文；显式语言、短版和字数要求优先。自动中文且未指定长度时，以1500–2500汉字为软创作目标；素材不足不编造凑字，有字数上限时不强加最低长度。\n"
    + "English: Caption is prose; Layout is locally compiled JSON. Only positive_prompt goes to MOSS. Compile-only needs no Key/model. References are LLM context, not native editing. Geometry checks are not rendered-quality or token-budget verification.";

function dialog(content, title = "MOSS / 只读查看") {
    const element = document.createElement("dialog");
    Object.assign(element.style, { maxWidth: "90vw", maxHeight: "85vh", overflow: "auto", background: "#202228", color: "#eee", border: "1px solid #6aa9ed", borderRadius: "10px", padding: "16px" });
    const heading = document.createElement("h3"); heading.textContent = title; element.append(heading);
    if (typeof content === "string") {
        const pre = document.createElement("pre"); pre.textContent = content; pre.style.whiteSpace = "pre-wrap"; element.append(pre);
        const copy = document.createElement("button"); copy.textContent = "复制文本 / Copy";
        copy.onclick = async () => { try { await navigator.clipboard.writeText(content); } catch { window.alert("请手动复制 / Copy manually"); } }; element.append(copy);
    } else element.append(content);
    const close = document.createElement("button"); close.textContent = "关闭 / Close";
    close.onclick = () => element.close(); element.append(close);
    element.addEventListener("close", () => element.remove(), { once: true });
    document.body.append(element); element.showModal(); return element;
}

function actions(node) {
    if (node.t8MossInstalled || !node.addWidget) return;
    node.t8MossInstalled = true;
    const action = (name, callback) => {
        const widget = node.addWidget("button", name, "", callback, { serialize: false });
        widget.serialize = false;
        widget.serializeValue = () => undefined; return widget;
    };
    const changed = () => {
        observeSharedConfig(node);
        node.t8MossStale = true;
        if (node.t8MossStatusWidget) node.t8MossStatusWidget.label = mossStatus(node.t8MossLast, true).split("\n")[0];
        refreshMoss(node);
    };
    node.t8MossInvalidate = changed;
    action("⚙ 高级设置（选填）/ Advanced", () => { node.t8MossAdvanced = !node.t8MossAdvanced; refreshMoss(node); });
    node.t8MossProviderWidget = action("实际渠道 / Effective provider", () => window.alert(effectiveMossMode(node)));
    node.t8MossStatusWidget = action("等待执行 / Ready · Token未核验", () => window.alert(mossStatus(node.t8MossLast, node.t8MossStale)));
    const recovery = addCompletionRecoveryButton(node, MOSS_ID);
    if (recovery) {
        recovery.label = recovery.name = "🔄 恢复上次成功结果（不重新生成）/ Restore";
        recovery.serialize = false;
        recovery.options ||= {};
        recovery.options.serialize = false;
        recovery.serializeValue = () => undefined;
    }
    action("📝 查看失败草稿（未验证，不接下游）/ Failed draft", async () => {
        node.t8EnsureRecoverySlot?.();
        const slot = node.widgets?.find(w => w.name === "recovery_slot")?.value || "";
        try {
            const response = await api.fetchApi(`/t8-prompt-enhancer/moss-image/draft/${encodeURIComponent(slot)}`, { cache: "no-store" });
            if (!response.ok) throw new Error("No retained draft");
            const data = await response.json();
            dialog(`未验证，不可直接接正向 / Unverified${data.truncated ? " · 展示已截短 / Truncated" : ""}\n${String(data.draft || "")}`, "失败草稿 / Failed draft");
        } catch { window.alert("没有保留的失败草稿或已过期 / No retained draft or expired."); }
    });
    action("📐 查看上次布局示意（非成图）/ Layout", () => {
        if (!node.t8MossLast?.draft) return window.alert("请先执行节点 / Run first.");
        try { dialog(layoutPreview(node.t8MossLast.draft), node.t8MossStale ? "上次结果，已过期 / Stale layout" : "位置示意 / Layout"); }
        catch { window.alert("布局不可预览 / Layout is not previewable."); }
    });
    action("📐 填写画布尺寸预设 / Canvas presets", () => {
        const selection = window.prompt("选择比例：1:1, 3:4, 4:3, 16:9, 9:16, 2:1, 1:2。会替换节点宽高，不改草稿。/ Ratio preset", "1:1");
        if (!selection) return;
        const size = CANVAS_PRESETS[selection.trim()];
        if (!size) return window.alert("未知比例 / Unknown ratio.");
        if (node.widgets?.find(w => w.name === "operation")?.value === COMPILE) return window.alert("仅编译Layout以草稿宽高为准 / Compile Layout uses draft dimensions.");
        for (const [i, name] of ["width", "height"].entries()) {
            const widget = node.widgets?.find(w => w.name === name); if (widget) { widget.value = size[i]; widget.callback?.(size[i]); }
        }
        node.graph?.change?.(); changed();
    });
    action("💡 填入示例（仅空白未连线时）/ Example", () => {
        const input = node.inputs?.find(i => i.name === "prompt");
        const widget = node.widgets?.find(w => w.name === "prompt");
        if (!widget || input?.link != null || String(widget.value || "").trim()) return window.alert("已有输入或已连线，未覆盖 / Existing or linked input was not changed.");
        widget.value = "设计一张陶瓷杯海报：米白背景、柔和侧光，杯子放左侧；右侧标题写‘把日常，过成诗。’，下方写‘一杯温暖’，不添加其他文字或Logo。";
        if (widget.inputEl) widget.inputEl.value = widget.value;
        node.graph?.change?.(); changed();
    });
    action("🔑 获取渠道 API Key / Get Key", () => {
        const mode = effectiveMossMode(node);
        if ([API_MODES[3], API_MODES[4]].includes(mode) || node.widgets?.find(w => w.name === "operation")?.value === COMPILE) return window.alert("此路径不需要云端Key / No cloud Key needed.");
        if (mode === API_MODES[2]) return window.alert("使用你选择的OpenAI兼容服务的Key / Use your selected provider's Key.");
        window.open(mode === API_MODES[1] ? "https://ai.t8star.org/register?aff=dP7j" : "https://api.seedance.nz/sign-up?aff=5f4w", "_blank", "noopener,noreferrer");
    });
    action("🧩 本地 GGUF 安装与状态 / Local setup", () => showLocalQwenStatus(node));
    action("🧭 渠道能力边界 / Provider capability", () => showProviderCapability(effectiveMossMode(node), node.widgets?.find(w => w.name === "openai_base_url")?.value || ""));
    action("🔎 查看脱敏诊断 / Diagnostics", () => showRedactedDiagnostics(MOSS_ID));
    node.t8MossHelpWidget = action("📖 使用说明 / Help", () => dialog(HELP, "MOSS 使用说明 / How to use"));
    node.t8RefreshStrata = changed; // shared-config changes invalidate the previous result too
    for (const widget of node.widgets || []) if (MOSS_NAMES.includes(widget.name)) {
        const previous = widget.callback;
        widget.callback = function () { const result = previous?.apply(this, arguments); changed(); return result; };
    }
    refreshMoss(node);
}

app.registerExtension({
    name: "T8.MOSSImagePromptEnhancer",
    async beforeRegisterNodeDef(Type, data) {
        if (data.name !== MOSS_ID) return;
        const created = Type.prototype.onNodeCreated, configured = Type.prototype.onConfigure,
            serialized = Type.prototype.onSerialize, executed = Type.prototype.onExecuted,
            connections = Type.prototype.onConnectionsChange, removed = Type.prototype.onRemoved, added = Type.prototype.onAdded,
            draw = Type.prototype.onDrawForeground;
        Type.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); actions(this);
            requestAnimationFrame(() => { if (!this.t8MossRemoved) refreshMoss(this, true); });
            return result;
        };
        Type.prototype.onConfigure = function (value) {
            const result = configureMoss(this, value, configured, arguments);
            this.t8MossInvalidate?.();
            requestAnimationFrame(() => { if (!this.t8MossRemoved) refreshMoss(this, true); }); return result;
        };
        Type.prototype.onSerialize = function (value) { const result = serialized?.apply(this, arguments); serializeMoss(this, value); return result; };
        Type.prototype.onExecuted = function (value) {
            const result = executed?.apply(this, arguments);
            try {
                const status = JSON.parse(value?.t8_moss_image_result?.[0]);
                if (!["caption", "layout"].includes(status.format) || ![status.width, status.height].every(Number.isInteger)) throw new Error("Invalid status");
                this.t8MossLast = status; this.t8MossStale = false;
                if (this.t8MossStatusWidget) this.t8MossStatusWidget.label = mossStatus(status).split("\n")[0];
            } catch { this.t8MossStale = true; }
            refreshMoss(this); return result;
        };
        Type.prototype.onConnectionsChange = function () {
            const result = connections?.apply(this, arguments); this.t8MossInvalidate?.(); refreshMoss(this);
            requestAnimationFrame(() => { if (!this.t8MossRemoved) refreshMoss(this, true); });
            return result;
        };
        Type.prototype.onAdded = function () {
            const result = added?.apply(this, arguments); observeSharedConfig(this); return result;
        };
        Type.prototype.onDrawForeground = function (context) {
            const result = draw?.apply(this, arguments); drawMossLinkedLabels(this, context); return result;
        };
        Type.prototype.onRemoved = function () { this.t8MossRemoved = true; return removed?.apply(this, arguments); };
    },
});
