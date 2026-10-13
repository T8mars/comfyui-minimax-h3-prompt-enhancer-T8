import { app } from "../../scripts/app.js";
import { STRATA_API_MODE, effectiveStrata, restoreStrataVisibility, updateStrataVisibility } from "./strata_ui.mjs";

const IDS = new Set(["MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8", "MiniMaxMusic3PromptEnhancerT8",
    "YuE2MusicPromptEnhancerT8", "QwenImage21PromptEnhancerT8", "T8LyricWriter", "T8ArrangementPlanner", "T8LLMProviderConfig",
    "T8DirectedRevision", "T8LongFormPlanner", "T8ReferenceRoleMapper", "T8CreativeCandidateLab", "T8StoryboardPack",
    "T8MusicCreativeLab", "T8MusicVideoBeatSheet"]);

const GRAPH_OBSERVER = Symbol("t8StrataGraphObserver");
function observeConnections(graph) {
    if (!graph || graph[GRAPH_OBSERVER]) return;
    const state = { pending: false };
    graph[GRAPH_OBSERVER] = state;
    const original = graph.onNodeConnectionChange;
    graph.onNodeConnectionChange = function () {
        const result = original?.apply(this, arguments);
        // Changing a reroute's input does not notify the distant enhancer.
        // Refresh once after the host finishes updating the graph, preserving
        // its callback and avoiding a frame per affected link.
        if (!state.pending) {
            state.pending = true;
            requestAnimationFrame(() => {
                state.pending = false;
                for (const item of graph._nodes || []) if (!item.t8StrataRemoved) item.t8RefreshStrata?.();
            });
        }
        return result;
    };
}

function refresh(node) {
    restoreStrataVisibility(node);
    updateStrataVisibility(node);
    if (node.t8StrataNoticeWidget) {
        const report = node.t8StrataLastRun;
        node.t8StrataNoticeWidget.label = report
            ? `Strata：${report.model} · ${report.request_count} 次生成 · 不读取音频`
            : "Strata 桥接：使用已启动服务；高级连接参数在共享渠道配置";
    }
    if (effectiveStrata(node)) {
        if (!node.t8StrataWasActive) node.t8StrataPreviousSize = [...(node.size || [400, 200])];
        node.t8StrataWasActive = true;
        node.setSize?.([node.size?.[0] || 400, node.computeSize?.()?.[1] || node.size?.[1] || 200]);
    } else if (node.t8StrataWasActive) {
        node.t8StrataWasActive = false;
        node.setSize?.(node.t8StrataPreviousSize || node.size);
    }
}

function install(node) {
    observeConnections(node.graph);
    if (node.t8StrataUIInstalled) return;
    node.t8StrataUIInstalled = true;
    const notice = node.addWidget("button", "Strata 桥接：使用已启动服务", "",
        () => {
            const report = node.t8StrataLastRun;
            const samples = report?.videos?.map(v => `${v.label}: ${v.sample_count} 个样本，${v.first_sample_s.toFixed(3)}–${v.last_sample_s.toFixed(3)}秒，最大间隙${v.max_sample_gap_s.toFixed(3)}秒`).join("\n") || "尚未执行视频采样；不宣称逐帧覆盖。";
            window.alert(`Strata 设置由上游共享渠道配置优先决定；断开后使用原节点设置。\n默认连接 ComfyUI 后端本机 127.0.0.1:8080，AUTO 使用服务当前模型。\n无需云端 API Key；认证服务使用独立 Strata 凭据。\nGGUF 的模型路径/上下文/卸载参数不控制此服务。\n取消仅请求结束本次连接，不保证显存释放；桥接不负责起停或卸载。\n${samples}`);
        }, { serialize: false });
    notice.serializeValue = () => undefined;
    node.t8StrataNoticeWidget = notice;
    node.t8RefreshStrata = () => refresh(node);
    for (const widget of node.widgets || []) {
        if (!["api_mode", "provider"].includes(widget.name)) continue;
        const old = widget.callback;
        widget.callback = function () {
            restoreStrataVisibility(node);
            const result = old?.apply(this, arguments);
            refresh(node);
            if (widget.name === "provider") for (const item of node.graph?._nodes || []) item.t8RefreshStrata?.();
            return result;
        };
    }
    refresh(node);
}

app.registerExtension({
    name: "T8.StrataBridgeUI",
    async beforeRegisterNodeDef(nodeType, data) {
        if (!IDS.has(data.name)) return;
        const created = nodeType.prototype.onNodeCreated;
        const configured = nodeType.prototype.onConfigure;
        const executed = nodeType.prototype.onExecuted;
        const connected = nodeType.prototype.onConnectionsChange;
        const removed = nodeType.prototype.onRemoved;
        const added = nodeType.prototype.onAdded;
        nodeType.prototype.onNodeCreated = function () { created?.apply(this, arguments); install(this); };
        nodeType.prototype.onConfigure = function () {
            restoreStrataVisibility(this);
            const result = configured?.apply(this, arguments);
            updateStrataVisibility(this);
            requestAnimationFrame(() => refresh(this));
            return result;
        };
        nodeType.prototype.onExecuted = function (message) {
            executed?.apply(this, arguments);
            const value = message?.strata_bridge?.[0];
            if (value?.provider === "Strata") this.t8StrataLastRun = value;
            refresh(this);
        };
        nodeType.prototype.onConnectionsChange = function () {
            restoreStrataVisibility(this);
            const result = connected?.apply(this, arguments);
            requestAnimationFrame(() => refresh(this));
            return result;
        };
        nodeType.prototype.onRemoved = function () {
            this.t8StrataRemoved = true;
            this.t8StrataProbeGeneration = (this.t8StrataProbeGeneration || 0) + 1;
            return removed?.apply(this, arguments);
        };
        nodeType.prototype.onAdded = function () {
            const result = added?.apply(this, arguments);
            this.t8StrataRemoved = false;
            observeConnections(this.graph);
            requestAnimationFrame(() => { if (!this.t8StrataRemoved) refresh(this); });
            return result;
        };
    },
});
