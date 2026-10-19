import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

export const MARKER_HELP_BUTTON = "📖 空间标记：示例与接线 / Examples";
const STEMS = ["h3_visual_marker_ref2va", "h3_visual_marker_hybrid"];
const DEMO_NAME = "h3-marker-demo-source.png";

function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    parent?.append(node);
    return node;
}

function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = element("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function workflow(stem, moduleHint = "") {
    if (!STEMS.includes(stem)) throw new Error("Unknown marker example");
    const response = await api.fetchApi("/workflow_templates");
    if (!response.ok) throw new Error("无法读取本地工作流模板 / Cannot read local templates");
    const catalog = await response.json();
    const modules = Object.keys(catalog).filter(key => Array.isArray(catalog[key])
        && STEMS.every(name => catalog[key].some(value => value === name || value === name + ".json")));
    const extension = decodeURIComponent(new URL(import.meta.url).pathname.split("/extensions/")[1]?.split("/")[0] || "");
    const source = String(moduleHint).replace(/^custom_nodes\./, "");
    const selected = [source, extension].find(key => modules.includes(key)) || (modules.length === 1 ? modules[0] : "");
    if (!selected) throw new Error("未找到当前插件的空间示例，请检查安装 / Marker examples unavailable");
    const result = await api.fetchApi(`/workflow_templates/${encodeURIComponent(selected)}/${stem}.json`);
    if (!result.ok) throw new Error("无法读取示例文件 / Cannot read example");
    return result.json();
}

async function demoImage() {
    const source = new URL("./assets/h3-marker-demo-source.svg", import.meta.url);
    const img = new Image();
    await new Promise((resolve, reject) => {img.onload = resolve; img.onerror = reject; img.src = source.href;});
    const canvas = document.createElement("canvas");
    canvas.width = 1440;
    canvas.height = 960;
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("参考图导出失败 / Reference export failed");
    saveBlob(blob, DEMO_NAME);
}

export function showMarkerGuide(moduleHint = "") {
    document.querySelector("[data-t8-marker-guide]")?.remove();
    const overlay = element("div", "", document.body);
    overlay.dataset.t8MarkerGuide = "true";
    overlay.style.cssText = "position:fixed;inset:0;z-index:100000;background:#0009;display:flex;align-items:center;justify-content:center;padding:20px";
    const panel = element("section", "", overlay);
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "空间标记接线教程与示例 / Spatial examples");
    panel.style.cssText = "background:#24282d;color:#eee;max-width:940px;width:95vw;max-height:90vh;overflow:auto;border:1px solid #678;border-radius:12px;padding:22px;font:14px/1.7 sans-serif";
    element("h2", "空间标记：从参考图到增强提示词 / Spatial marker quick start", panel);
    element("p", "示例：红衣人物从左侧走向右侧门口，穿过后继续前进。青框表示人物，黄框表示目标；这是教学示意图。", panel);
    const image = element("img", "", panel);
    image.src = new URL("./assets/h3-marker-quickstart.svg", import.meta.url).href;
    image.alt = "青框人物、黄框门口，以及 marker_plan 和 marked_image 的两条接线";
    image.style.cssText = "display:block;width:100%;max-height:430px;object-fit:contain;background:#f1f4f5;border-radius:8px";
    const steps = element("ol", "", panel);
    for (const text of [
        "先安装已有的 comfyui-minimax-h3-audio-T8；示例使用它的 H3 Marker · Prepare。",
        "下载配套 PNG 与一个工作流 JSON。先保存当前工作流，再把 JSON 拖入 ComfyUI；在 Load Image 中上传刚下载的 PNG。",
        "Prepare.marked_image → H3 的参考图；Prepare.marker_plan → 空间配置；空间配置输出 → H3.visual_marker_config。两条 Prepare 输出都要接。",
        "Prepare 的 markers_json 定义谁和目标：marker_id 是唯一名字；xyxy 是源图归一化左上、右下坐标；relations 写谁向哪个目标做什么。示例已填好，换图时按新图改框与角色。",
        "普通示例用 Ref2VA；Hybrid 示例另将干净源图接首帧。配置默认关闭，需要手动切 On 才使用空间信息。selector=0 自动唯一匹配；本例普通标记是 Picture 1，Hybrid 标记是 Picture 2。它不是 Bind.marker_position。",
        "在 H3 配置自己的文本增强渠道或共享配置，再运行。这里只生成增强提示词，不生成视频，也不增加独立规划请求。",
        "继续接视频工作流时：enhanced_prompt → 现有 Marker Prompt.base_prompt，选 manual_original，再将 recipe 接 Bind。上下游参考图顺序一致，marker 只插入一次。"
    ]) element("li", text, steps);
    element("p", "English: download the sample PNG and JSON, save your current graph, import JSON and upload PNG. Connect both Prepare outputs. Enable On, configure your enhancer provider, then queue. Hybrid anchors count before the marker Picture. Soft guidance; actual video results need review.", panel);
    const actions = element("div", "", panel);
    actions.style.cssText = "display:flex;flex-wrap:wrap;gap:10px;margin:16px 0";
    const status = element("p", "", panel);
    status.setAttribute("role", "status");
    const action = (label, key, callback) => {
        const button = element("button", label, actions);
        button.dataset.markerAction = key;
        button.style.cssText = "padding:9px 13px;background:#355c70;color:white;border:1px solid #82a7b8;border-radius:7px;cursor:pointer";
        button.onclick = async () => {
            button.disabled = true;
            try {await callback();status.textContent = "已下载；请保存当前工作流后导入 / Downloaded; save your current graph before importing.";}
            catch (error) {status.textContent = error?.message || "下载失败 / Download failed";}
            finally {button.disabled = false;}
        };
    };
    action("① 下载配套参考图 PNG", "image", demoImage);
    for (const [index, stem] of STEMS.entries()) {
        action(index ? "② 下载 Hybrid 空间示例 JSON" : "② 下载 Ref2VA 空间示例 JSON", stem, async () => {
            const data = await workflow(stem, moduleHint);
            saveBlob(new Blob([JSON.stringify(data, null, 2)], {type:"application/json"}), stem + ".json");
        });
    }
    const close = element("button", "关闭 / Close", panel);
    close.dataset.markerAction = "close";
    close.onclick = () => overlay.remove();
    overlay.onclick = event => {if (event.target === overlay) overlay.remove();};
    close.focus();
    return overlay;
}

export function attachMarkerGuide(node, moduleHint = "") {
    const existing = node.widgets?.find(w => w.name === MARKER_HELP_BUTTON);
    if (existing) return existing;
    const button = node.addWidget("button", MARKER_HELP_BUTTON, null, () => showMarkerGuide(moduleHint), {serialize:false});
    button.serialize = false;
    button.options = {...button.options, serialize:false};
    return button;
}

app.registerExtension({
    name:"T8.H3VisualMarkerGuide",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "T8H3VisualMarkerConfig") return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function(...args) {
            const result = original?.apply(this, args);
            attachMarkerGuide(this, nodeData.python_module);
            return result;
        };
    }
});
