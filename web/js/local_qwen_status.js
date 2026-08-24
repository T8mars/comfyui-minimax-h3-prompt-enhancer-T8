const STATUS_URL = "/t8-prompt-enhancer/local-qwen/status";


async function fetchLocalStatus(refresh = false) {
    const response = await fetch(`${STATUS_URL}${refresh ? "?refresh=1" : ""}`, { cache: "no-store" });
    let payload = {};
    try {
        payload = await response.json();
    } catch (_error) {
        // The caller reports a stable error without exposing a server body.
    }
    if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
}


function updateCombo(widget, values) {
    if (!widget || !Array.isArray(values) || !values.length) return;
    const current = String(widget.value || "");
    const options = current && !values.includes(current) ? [current, ...values] : [...values];
    widget.options = { ...(widget.options || {}), values: options };
}


function refreshNodeModelWidgets(node, payload) {
    if (!node?.widgets) return;
    const find = (name) => node.widgets.find((widget) => widget.name === name);
    updateCombo(find("local_model"), payload.model_options);
    updateCombo(find("local_mmproj"), payload.projector_options);
    node.setDirtyCanvas?.(true, true);
}


function selectedModelSummary(node, payload) {
    const selected = String(node?.widgets?.find((widget) => widget.name === "local_model")?.value || "");
    if (!selected) return "";
    const model = payload.models?.find((item) => item.identifier === selected || item.filename === selected);
    if (!model) return `当前模型：${selected}（未在本次扫描中找到，保留旧工作流值）`;
    const metadata = model.metadata_readable
        ? `${model.architecture || "未知架构"}${model.context_length ? ` / 上下文 ${model.context_length}` : ""}`
        : "元数据不可读，将在加载时由 llama.cpp 最终判定";
    const vision = model.vision_capable
        ? `视觉：可用，匹配 ${model.recommended_projector}`
        : "视觉：未找到匹配 mmproj（文字仍可使用）";
    const verification = {
        project_tested_pinned_size_match: "项目实测型号（文件大小与固定版本一致）",
        runtime_supported_unverified: "运行时可识别，尚未做本项目质量验收",
        discovered_unverified: "仅发现文件，需运行兼容性检查",
    }[model.verification_tier] || "未分级";
    return `当前模型：${model.identifier}\n能力：${metadata}\n${vision}\n验证级别：${verification}`;
}


export async function showLocalQwenStatus(node = null) {
    let payload;
    try {
        payload = await fetchLocalStatus(true);
    } catch (error) {
        window.alert(`无法读取本地 GGUF 状态：${error?.message || error}`);
        return;
    }
    refreshNodeModelWidgets(node, payload);
    const textReady = Boolean(payload.text_ready);
    const visionReady = Boolean(payload.vision_ready);
    const backends = Array.isArray(payload.runtime_backends)
        ? payload.runtime_backends.map((item) => {
            const version = item.version ? ` ${item.version}` : "";
            return `${item.backend}${version}（${item.source || "来源未知"}）`;
        }).join("\n  - ")
        : "";
    const warnings = Array.isArray(payload.runtime_warnings)
        ? payload.runtime_warnings.join("\n")
        : "";
    window.alert([
        textReady ? "文字能力：已就绪。" : "文字能力：未就绪（需要运行时和至少一个主模型 GGUF）。",
        visionReady ? "视觉能力：至少一组模型/mmproj 已匹配。" : "视觉能力：未就绪；文字模型仍可用于 Music 3 或纯文字提示词。",
        `已发现：${payload.model_count || 0} 个主模型，${payload.projector_count || 0} 个视觉投影器。`,
        backends ? `可用运行时：\n  - ${backends}` : "可用运行时：无。",
        "AUTO 会优先使用固定 llama-server，也可自动复用当前 ComfyUI 的 llama-cpp-python。",
        selectedModelSummary(node, payload),
        `模型目录：${payload.model_directory || "未知"}`,
        "支持目录下任意层级子文件夹；点击本按钮会重新扫描并刷新节点下拉列表。",
        warnings ? `检测提示：\n${warnings}` : "",
        "兼容边界：GGUF 被发现不等于质量已验证；图像/视频分析必须有匹配 mmproj。",
        "视频边界：按真实时间戳采样可见画面，不读取视频音轨。",
        "Music 3 边界：仅处理文字，不加载视觉投影器。",
    ].filter(Boolean).join("\n"));
}


export async function copyLocalModelDirectory() {
    try {
        const payload = await fetchLocalStatus(false);
        const path = String(payload.model_directory || "");
        if (!path) throw new Error("模型目录未知");
        try {
            await navigator.clipboard.writeText(path);
        } catch (_error) {
            window.prompt("复制本地 GGUF 模型目录：", path);
            return;
        }
        window.alert(`模型目录已复制：\n${path}\n\n主模型与 mmproj 均可放在此目录或任意子目录。`);
    } catch (error) {
        window.alert(`无法读取模型目录：${error?.message || error}`);
    }
}
