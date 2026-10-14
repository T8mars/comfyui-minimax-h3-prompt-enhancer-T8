import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { refreshSpeech, restoreSpeechVisibility, serializeSpeech, configureSpeech,
    speechConnectionValues, speechStatusText } from "./speech_reference_ui.mjs";

const HELP = "使用说明 / How to use\n1. 默认关闭；开启后明确选已有字幕/文字、AUDIO 或 VIDEO 音轨。\n2. 语音参考接 H3/Seedance 的可选入口；text 可接其他创作节点。Strata先转文字，增强仍用主节点所选渠道。\n3. 默认只理解内容；保留对白时用高级角色映射明确指派，不自动猜说话人。\n4. 已有字幕无需服务；自动转写要求已启动且支持 CPU 保护的 Strata。非默认地址接 Strata 共享渠道配置。\n5. 源范围与成片时长不同；duration=0选当前输入剩余范围，超预算请先裁剪。\n6. ASR仅语音文字，非口型/音色/音乐/BPM分析。转写可能保存在 Strata 缓存与 Comfy 历史；云增强会收到转写文字。\nExisting text/subtitles work offline. No downloads, service management or automatic POST retries.\n校对请复制 SRT 到已有字幕输入再执行；只读预览不作为隐藏的第二份输入。";

app.registerExtension({
    name: "T8.SpeechReference",
    async beforeRegisterNodeDef(Type, data) {
        if (data.name !== "T8SpeechReference") return;
        const created = Type.prototype.onNodeCreated, configured = Type.prototype.onConfigure;
        const serialized = Type.prototype.onSerialize, executed = Type.prototype.onExecuted;
        const removed = Type.prototype.onRemoved;
        Type.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            if (this.t8SpeechInstalled) return result;
            this.t8SpeechInstalled = true;
            const action = (label, callback) => {
                const w = this.addWidget("button", label, "", callback, { serialize: false });
                w.serializeValue = () => undefined; return w;
            };
            this.t8SpeechAdvancedButton = action("⚙ 高级语音设置（选填） / Advanced", () => {
                this.t8SpeechAdvanced = !this.t8SpeechAdvanced; refreshSpeech(this);
            });
            action("🔎 只读检查 Strata 语音组件 / Check", async () => {
                const revision = this.t8SpeechProbeRevision = (this.t8SpeechProbeRevision || 0) + 1;
                const snapshot = () => JSON.stringify({ connection: speechConnectionValues(this),
                    mode: this.widgets?.find(w => w.name === "mode")?.value,
                    source: this.widgets?.find(w => w.name === "source_mode")?.value });
                let selected;
                const current = () => !this.t8SpeechRemoved && revision === this.t8SpeechProbeRevision && snapshot() === selected;
                try {
                    selected = snapshot();
                    const response = await api.fetchApi("/t8-prompt-enhancer/speech/capabilities", {
                        method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(speechConnectionValues(this)), cache: "no-store",
                    });
                    const value = await response.json();
                    if (current()) window.alert(speechStatusText(value));
                } catch {
                    try { if (selected === undefined || current()) window.alert(speechStatusText(null)); } catch { /* changed/invalid connection: no stale status */ }
                }
            });
            action("📖 使用说明／隐私 / Help", () => window.alert(HELP));
            action("📝 查看上次转写状态 / Last status", () => window.alert(this.t8SpeechLastStatus || "尚未转写 / No transcription yet. 文字、JSON、SRT可接显示文本节点校对。"));
            for (const w of this.widgets || []) if (["mode", "source_mode", "purpose"].includes(w.name)) {
                const prior = w.callback;
                w.callback = function () { const result = prior?.apply(this, arguments); refreshSpeech(thisNode); return result; };
                const thisNode = this;
            }
            refreshSpeech(this); return result;
        };
        Type.prototype.onConfigure = function (value) {
            restoreSpeechVisibility(this);
            const result = configureSpeech(this, value, configured, arguments);
            requestAnimationFrame(() => { if (!this.t8SpeechRemoved) refreshSpeech(this); });
            return result;
        };
        Type.prototype.onSerialize = function (value) {
            const result = serialized?.apply(this, arguments); serializeSpeech(this, value); return result;
        };
        Type.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            const status = message?.speech_status?.[0] || message?.t8_speech_status?.[0] || message?.speech_reference?.[0];
            if (status) this.t8SpeechLastStatus = typeof status === "string" ? status.slice(0, 2000) : JSON.stringify(status).slice(0, 2000);
            return result;
        };
        Type.prototype.onRemoved = function () {
            this.t8SpeechRemoved = true; this.t8SpeechProbeRevision = (this.t8SpeechProbeRevision || 0) + 1;
            return removed?.apply(this, arguments);
        };
    },
});
