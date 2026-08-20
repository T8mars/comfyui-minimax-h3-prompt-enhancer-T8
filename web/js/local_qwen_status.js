const STATUS_URL = "/t8-prompt-enhancer/local-qwen/status";


export async function showLocalQwenStatus() {
    let payload;
    try {
        const response = await fetch(STATUS_URL, { cache: "no-store" });
        payload = await response.json();
        if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
    } catch (error) {
        window.alert(`无法读取本地 Qwen 状态：${error?.message || error}`);
        return;
    }
    const yesNo = (value) => value ? "已安装" : "缺失";
    const textReady = payload.text_ready ?? (payload.runtime_installed && payload.model_installed);
    const visionReady = payload.vision_ready ?? (textReady && payload.mmproj_installed);
    window.alert([
        textReady ? "文字能力：已就绪（可用于 Music 3 及纯文字提示词）。" : "文字能力：未就绪。",
        visionReady ? "视觉能力：已就绪（可用于图像与视频采样帧）。" : "视觉能力：未就绪（需要 mmproj）。",
        `llama.cpp 运行时：${yesNo(payload.runtime_installed)}`,
        `Qwen3.8-27B GGUF：${yesNo(payload.model_installed)}`,
        `视觉投影器 mmproj：${yesNo(payload.mmproj_installed)}`,
        payload.backend ? `运行后端：${payload.backend}` : "",
        `模型目录：${payload.model_directory || "未知"}`,
        "安装命令：python install_local_qwen.py",
        "视频边界：按真实时间戳采样可见画面；不读取视频音轨。",
        "Music 3 边界：仅处理文字，不加载视觉投影器。",
    ].filter(Boolean).join("\n"));
}
