import { app } from "../../scripts/app.js";
import { addCompletionRecoveryButton } from "./completion_recovery_ui.mjs";
import { showLocalQwenStatus } from "./local_qwen_status.js";
import { bindOpenAIProviderPersistence } from "./widget_state.mjs";
import { ID, NAMES, configure, serialize, linkedProvider, providerLabel, refresh, drawLinked, ensureAcrossGraphs, ensureWorkflowOwner } from "./h3_image_ui.mjs";

const HELP = `MiniMax H3 Image 提示词扩写
1. 文生图：写需求，不连接参考图。图像编辑：每槽接一张图，最多16张；槽位顺序对应 <Picture 1>…，批次请先拆开。
2. expanded_prompt 接 H3 图像生成/编辑的正向提示词，并接 T8 Show Text 预览。编辑用的同一组原图还要按同样顺序接下游；本节点只输出文字。
3. aspect_ratio 是输出画幅比例，不会自动改变下游尺寸。official_json 是官方两字段结构；report_json 是诊断，二者不要接正向。
4. 官方要求英文描述，但画面中文等原文保持原样。目标英文词数 0=官方自动；正数是软目标，没有1000上限，不截断结果。
5. 接入width和height自动计算比例，例如1920×1080为16:9；接入后宽高优先，手动比例框隐藏。文生图映射到最近的官方比例，编辑保留精确约分。未接宽高仍用auto或原手动比例。
6. 高级“逐字锁定文案”：每行一个文本，非空行保留全部字符和顺序。它检查提示词文字，不保证生成图中文字正确。
7. 支持原有云API、OpenAI兼容、本地GGUF、Strata。provider_config优先；切换本地后主界面直接选择GGUF模型和视觉投影器，无需打开高级或连接提示词。编辑需要匹配的视觉投影器/VLM。
8. 云端/本地/Strata分别使用自己的生成Token预算。词数不等于Token；官方H3下游4096Token限制没有在此精确测量。
9. 默认最多追加1次格式/文案纠正，可设0；网络错误不自动重发。硬失败不输出坏结果；目标词数偏差只记录。
10. 恢复按钮读取当前进程上次成功结果，跳过当前模型和输入，通常最多1小时；全局缓存有容量限制。不会应用修改后的设置。
官方资料：https://huggingface.co/MiniMaxAI/MiniMax-H3-Image-PE
示例：example_workflows/h3_image_t2i_example.json / h3_image_edit_example.json`;
const OBSERVED = Symbol("t8H3ImageConfigObserved");

function install(node) {
    if (node.t8H3ImageInstalled) return;
    node.t8H3ImageInstalled = true;
    const action = (name, callback) => {
        const w = node.addWidget("button", name, "", callback, { serialize: false });
        w.serialize = false; w.serializeValue = () => undefined; return w;
    };
    node.t8H3ImageRefreshSoon = () => {
        if (node.t8H3ImageRefreshPending) return;
        node.t8H3ImageRefreshPending = true;
        requestAnimationFrame(() => {
            node.t8H3ImageRefreshPending = false;
            if (!node.t8H3ImageRemoved) node.t8H3ImageRefresh?.();
        });
    };
    node.t8H3ImageRefresh = () => {
        const source = linkedProvider(node);
        for (const w of source?.widgets || []) {
            if (w[OBSERVED]) continue;
            w[OBSERVED] = true;
            const prior = w.callback;
            w.callback = function () {
                const result = prior?.apply(this, arguments);
                for (const n of source.graph?._nodes || []) if (linkedProvider(n) === source && !n.t8H3ImageRemoved) {
                    n.t8H3ImageRefresh?.(); n.t8H3ImageRefreshSoon?.();
                }
                return result;
            };
        }
        refresh(node);
    };
    action("⚙ 高级设置 / Advanced", () => { node.t8H3ImageAdvanced = !node.t8H3ImageAdvanced; refresh(node); });
    node.t8H3ImageProvider = action("实际渠道 / Effective provider", () => window.alert(providerLabel(node)));
    const recovery = addCompletionRecoveryButton(node, ID);
    if (recovery) { recovery.label = recovery.name = "🔄 恢复上次成功结果 / Restore"; recovery.serialize = false; recovery.options.serialize = false; }
    const ensure = node.t8EnsureRecoverySlot;
    node.t8EnsureRecoverySlot = () => {
        ensure?.();
        const root = app.rootGraph || app.graph;
        ensureWorkflowOwner(node, root);
        ensureAcrossGraphs(node, root);
    };
    action("🧩 本地 GGUF 安装与状态 / Local setup", () => showLocalQwenStatus(node));
    action("📖 使用说明与示例 / Help", () => window.alert(HELP));
    bindOpenAIProviderPersistence(node);
    for (const w of node.widgets || []) if (NAMES.includes(w.name)) {
        const prior = w.callback;
        w.callback = function () {
            const result = prior?.apply(this, arguments);
            node.t8H3ImageRefresh();
            // Native combos can invoke the callback before committing .value.
            // Reconcile once after that commit, without requiring a connection.
            node.t8H3ImageRefreshSoon();
            return result;
        };
    }
    node.t8RefreshStrata = node.t8H3ImageRefresh;
    node.t8H3ImageRefresh();
}

app.registerExtension({
    name: "T8.H3ImagePromptEnhancer",
    async beforeRegisterNodeDef(Type, data) {
        if (data.name !== ID) return;
        const created = Type.prototype.onNodeCreated, configured = Type.prototype.onConfigure,
            serialized = Type.prototype.onSerialize, connections = Type.prototype.onConnectionsChange,
            added = Type.prototype.onAdded, removed = Type.prototype.onRemoved, draw = Type.prototype.onDrawForeground;
        Type.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); install(this);
            requestAnimationFrame(() => { if (!this.t8H3ImageRemoved) refresh(this, true); }); return result;
        };
        Type.prototype.onConfigure = function (value) {
            const result = configure(this, value, configured, arguments);
            this.t8H3ImageRefresh?.();
            requestAnimationFrame(() => { if (!this.t8H3ImageRemoved) refresh(this, true); }); return result;
        };
        Type.prototype.onSerialize = function (value) { const result = serialized?.apply(this, arguments); serialize(this, value); return result; };
        Type.prototype.onConnectionsChange = function () {
            const result = connections?.apply(this, arguments);
            requestAnimationFrame(() => { if (!this.t8H3ImageRemoved) this.t8H3ImageRefresh?.(); }); return result;
        };
        Type.prototype.onAdded = function () { this.t8H3ImageRemoved = false; const result = added?.apply(this, arguments); this.t8EnsureRecoverySlot?.(); this.t8H3ImageRefresh?.(); return result; };
        Type.prototype.onRemoved = function () { this.t8H3ImageRemoved = true; return removed?.apply(this, arguments); };
        Type.prototype.onDrawForeground = function (ctx) { const result = draw?.apply(this, arguments); drawLinked(this, ctx); return result; };
    },
});
