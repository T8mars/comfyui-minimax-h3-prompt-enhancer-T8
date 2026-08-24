const SEEDANCE_API_MODE = "贞贞平价小屋（推荐）";
const AI_WORKSHOP_API_MODE_PREFIX = "贞贞的AI工坊";
const OPENAI_API_MODE = "OpenAI兼容接口（备用）";
const LOCAL_QWEN_API_MODE = "本地 Qwen3.8-27B（GGUF，离线）";


export function providerCapabilitySummary(apiMode, baseUrl = "", { textOnly = false } = {}) {
    const mode = String(apiMode || "");
    if (mode === LOCAL_QWEN_API_MODE) {
        return {
            profile: "local-qwen-verified",
            image: textOnly ? "此节点无媒体输入" : "支持：视觉投影器读取图片",
            video_data_url: textOnly ? "此节点无媒体输入" : "不适用：按真实时间戳采样画面，不发送完整视频",
            video_url: "不支持",
            audio: "不读取或分析音轨",
            optional_parameters: "由本地 llama.cpp 合同管理",
        };
    }
    if (mode === SEEDANCE_API_MODE) {
        return {
            profile: "seedance-nz-verified",
            image: textOnly ? "此节点无媒体输入" : "支持：上传图片素材",
            video_data_url: textOnly ? "此节点无媒体输入" : "支持：上传完整视频素材",
            video_url: "由渠道素材上传接口管理",
            audio: textOnly ? "此节点只处理文字" : "不把视觉分析表述为可靠音轨分析",
            optional_parameters: "使用节点已验证的固定请求合同",
        };
    }
    if (mode.startsWith(AI_WORKSHOP_API_MODE_PREFIX)) {
        return {
            profile: "t8-ai-workshop-verified",
            image: textOnly ? "此节点无媒体输入" : "支持：图片 Data URL",
            video_data_url: textOnly ? "此节点无媒体输入" : "支持：视频 Data URL（取决于所选视觉模型）",
            video_url: "未作为通用合同声明",
            audio: textOnly ? "此节点只处理文字" : "未声明独立音轨分析",
            optional_parameters: "使用节点已验证的固定请求合同",
        };
    }
    if (mode === OPENAI_API_MODE) {
        let host = "";
        let path = "";
        try {
            const parsed = new URL(String(baseUrl || ""));
            host = parsed.hostname.toLowerCase();
            path = parsed.pathname.toLowerCase();
        } catch (_error) {
            // Empty or partial Base URLs remain an unknown profile.
        }
        const kimiCoding = host === "api.kimi.com" && (path === "/coding" || path.startsWith("/coding/"));
        return {
            profile: kimiCoding ? "kimi-coding-known-parameter-profile" : "openai-compatible-unknown",
            image: textOnly ? "此节点无媒体输入" : "未知：节点使用图片 Data URL，模型/供应商必须自行支持",
            video_data_url: textOnly ? "此节点无媒体输入" : "未知：节点可发送视频 Data URL，模型/供应商必须自行支持",
            video_url: textOnly ? "此节点无媒体输入" : "未知：可为视频提供 URL，但是否支持由供应商决定",
            audio: "未声明",
            optional_parameters: kimiCoding
                ? "AUTO 会省略 temperature；其余未知字段不自动猜测"
                : "AUTO 保持 1.2.0 行为并发送 temperature；未知供应商不冒充已验证视觉模型",
        };
    }
    return {
        profile: "unknown",
        image: "未知",
        video_data_url: "未知",
        video_url: "未知",
        audio: "未知",
        optional_parameters: "未知",
    };
}


export function showProviderCapability(apiMode, baseUrl = "", options = {}) {
    const summary = providerCapabilitySummary(apiMode, baseUrl, options);
    const lines = [
        `能力配置：${summary.profile}`,
        `图片：${summary.image}`,
        `视频 Data URL/上传：${summary.video_data_url}`,
        `视频 URL：${summary.video_url}`,
        `音轨：${summary.audio}`,
        `可选参数：${summary.optional_parameters}`,
        "\n这是节点侧合同预检，不等同于未知第三方模型的在线能力证明。",
    ];
    window.alert(lines.join("\n"));
}
