import { app } from "../../scripts/app.js";


const NODE_ID = "T8LLMProviderConfig";


async function requestCredentials(method = "GET", body = null) {
    const response = await fetch("/t8-prompt-enhancer/credentials", {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers: body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}


function field(label, type = "text") {
    const wrapper = document.createElement("label");
    wrapper.style.cssText = "display:flex;flex-direction:column;gap:5px";
    const title = document.createElement("span");
    title.textContent = label;
    const input = document.createElement("input");
    input.type = type;
    input.autocomplete = type === "password" ? "new-password" : "off";
    input.style.cssText = "height:32px;padding:0 9px;border:1px solid #666;border-radius:6px;background:#171717;color:#eee";
    wrapper.append(title, input);
    return { wrapper, input };
}


async function openCredentialManager(node) {
    const aliasWidget = node.widgets?.find((widget) => widget.name === "credential_alias");
    const providerWidget = node.widgets?.find((widget) => widget.name === "provider");
    const baseUrlWidget = node.widgets?.find((widget) => widget.name === "openai_base_url");
    const customModelWidget = node.widgets?.find((widget) => widget.name === "custom_model");
    const workshopModelWidget = node.widgets?.find((widget) => widget.name === "ai_workshop_model");
    document.querySelector("[data-t8-credential-manager]")?.remove();
    const overlay = document.createElement("div");
    overlay.dataset.t8CredentialManager = "true";
    overlay.style.cssText = "position:fixed;inset:0;z-index:100003;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(0,0,0,.62)";
    const panel = document.createElement("section");
    panel.style.cssText = "width:min(560px,94vw);padding:16px;border:1px solid #666;border-radius:10px;background:#242424;color:#eee;font:14px/1.5 sans-serif";
    const title = document.createElement("h3");
    title.textContent = "本地凭据别名";
    title.style.margin = "0 0 8px";
    const notice = document.createElement("p");
    notice.textContent = "真实 Key 只写入 ComfyUI 用户目录；工作流只保存别名。现有 API Key STRING 接线仍具有最高优先级。";
    const alias = field("别名（字母、数字、点、下划线、短横线）");
    const secret = field("API Key / Token", "password");
    alias.input.value = String(aliasWidget?.value || "");
    const aliases = document.createElement("select");
    aliases.style.cssText = "width:100%;height:32px;margin:9px 0;padding:0 7px;background:#171717;color:#eee;border:1px solid #666;border-radius:6px";
    const buttons = document.createElement("div");
    buttons.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;margin-top:12px";
    const makeButton = (text) => {
        const item = document.createElement("button");
        item.type = "button";
        item.textContent = text;
        item.style.cssText = "padding:7px 11px;border:1px solid #666;border-radius:6px;background:#333;color:#eee;cursor:pointer";
        return item;
    };
    const save = makeButton("保存/更新");
    const use = makeButton("使用所选别名");
    const check = makeButton("检查别名已配置");
    const testConnection = makeButton("测试云端连接（1次请求）");
    const remove = makeButton("删除");
    const close = makeButton("关闭");
    const status = document.createElement("div");
    status.style.cssText = "min-height:22px;margin-top:9px;color:#bcd";

    const refresh = async () => {
        const result = await requestCredentials();
        aliases.replaceChildren();
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = result.aliases?.length ? "选择已保存别名" : "暂无已保存别名";
        aliases.append(empty);
        for (const value of result.aliases || []) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            aliases.append(option);
        }
    };
    aliases.addEventListener("change", () => { if (aliases.value) alias.input.value = aliases.value; });
    save.onclick = async () => {
        try {
            await requestCredentials("POST", { action: "save", alias: alias.input.value, secret: secret.input.value });
            secret.input.value = "";
            aliasWidget.value = alias.input.value.trim();
            status.textContent = "已保存；工作流只记录别名。";
            await refresh();
        } catch (_error) { status.textContent = "保存失败：请检查别名和 ComfyUI 用户目录权限。"; }
    };
    use.onclick = () => {
        const value = aliases.value || alias.input.value.trim();
        if (value && aliasWidget) aliasWidget.value = value;
        status.textContent = value ? `当前工作流别名：${value}` : "请先选择别名。";
    };
    check.onclick = async () => {
        try {
            await requestCredentials("POST", { action: "check", alias: aliases.value || alias.input.value });
            status.textContent = "别名已配置（未发起付费网络请求）。";
        } catch (_error) { status.textContent = "该别名未配置或凭据库不可用。"; }
    };
    testConnection.onclick = async () => {
        const selectedAlias = aliases.value || alias.input.value.trim();
        if (!selectedAlias) { status.textContent = "请先选择凭据别名。"; return; }
        if (providerWidget?.value === "Local Qwen") {
            status.textContent = "本地 Qwen 请使用节点内运行状态检查，不需要云端凭据。";
            return;
        }
        if (!window.confirm("将发送一次最小云端 LLM 请求，可能产生少量费用。是否继续？")) return;
        status.textContent = "正在测试连接……";
        try {
            const model = providerWidget?.value === "T8 AI Workshop"
                ? workshopModelWidget?.value
                : customModelWidget?.value;
            const result = await requestCredentials("POST", {
                action: "test_connection",
                alias: selectedAlias,
                provider: providerWidget?.value,
                base_url: baseUrlWidget?.value,
                model,
            });
            status.textContent = result.connected
                ? "连接成功。"
                : `连接未通过：${result.category || "unknown"}（未显示上游正文）`;
        } catch (_error) { status.textContent = "连接测试失败；Key、URL 和上游正文均未显示。"; }
    };
    remove.onclick = async () => {
        const value = aliases.value || alias.input.value.trim();
        if (!value || !window.confirm(`确定删除本地凭据“${value}”？工作流其他字段不会改变。`)) return;
        try {
            await requestCredentials("POST", { action: "delete", alias: value, confirmed: true });
            if (aliasWidget?.value === value) aliasWidget.value = "";
            alias.input.value = "";
            status.textContent = "已删除本地凭据。";
            await refresh();
        } catch (_error) { status.textContent = "删除失败。"; }
    };
    close.onclick = () => overlay.remove();
    overlay.addEventListener("pointerdown", (event) => { if (event.target === overlay) overlay.remove(); });
    buttons.append(save, use, check, testConnection, remove, close);
    panel.append(title, notice, aliases, alias.wrapper, secret.wrapper, buttons, status);
    overlay.append(panel);
    document.body.append(overlay);
    try { await refresh(); } catch (_error) { status.textContent = "无法读取凭据别名；请重启 ComfyUI 后重试。"; }
}


app.registerExtension({
    name: "T8.ProviderConfigUI",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            original?.apply(this, arguments);
            const manager = this.addWidget(
                "button",
                "🔐 管理本地凭据别名",
                "真实 Key 不进入工作流；外部 STRING/原节点保存值仍优先",
                () => openCredentialManager(this),
                { serialize: false },
            );
            manager.serializeValue = () => undefined;
        };
    },
});
