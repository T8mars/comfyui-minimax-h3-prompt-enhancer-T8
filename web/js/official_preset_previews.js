import { registerTemplateMenuPreview } from "./template_menu_preview.js";


const OFFICIAL_COMMIT = "b7227fa6a6206e9fb30562383d39e53cf3866a48";
const OFFICIAL_SKILL_ROOT = `https://github.com/MiniMax-AI/MiniMax-H3/tree/${OFFICIAL_COMMIT}/skills`;


const PRESETS = {
    "极简产品广告": {
        skill: "minimalist-product-ad-generator",
        file: "minimalist-product-ad-generator.gif",
        summary: "以产品实物、克制场景、材质细节和单一文案事件组成极简广告。",
    },
    "3D 动画短片": {
        skill: "3d-animation-short-generator",
        file: "3d-animation-short-generator.gif",
        summary: "围绕角色、场景、表演、镜头连续性与动画运动规律组织 3D 短片。",
    },
    "品牌宣传短片": {
        skill: "brand-promo-video-generator",
        file: "brand-promo-video-generator.gif",
        summary: "用可核验的品牌事实、产品功能证据与行动号召推进宣传短片。",
    },
    "音乐 MV 动态字幕（官方）": {
        skill: "music-video-subtitle-generator",
        file: "music-video-subtitle-generator.gif",
        summary: "把音乐、人声、表演、镜头和空间动态字幕组织成统一节奏系统。",
    },
    "双人合作游戏开场": {
        skill: "co-op-game-intro-generator",
        file: "co-op-game-intro-generator.gif",
        summary: "锁定两位角色、左右位置、玩家信息与菜单布局，完成清晰的合作开场。",
    },
    "纸拼贴讲解": {
        skill: "paper-collage-explainer-generator",
        file: "paper-collage-explainer-generator.gif",
        summary: "用纸张物件关系、拼贴装配和触感声音解释抽象概念。",
    },
    "立体纸艺停格讲解": {
        skill: "papercraft-stop-motion-explainer",
        file: "papercraft-stop-motion-explainer.gif",
        summary: "用分层纸雕、机械纸艺动作和停格节奏建立可读的知识路径。",
    },
    "手绘实拍融合": {
        skill: "handdrawn-live-video-generator",
        file: "handdrawn-live-video-generator.gif",
        summary: "让手绘实体与真实空间发生可见接触、连续变形和延迟追拍。",
    },
};


function previewUrl(filename) {
    return new URL(`./assets/official-previews/${filename}`, import.meta.url).href;
}


function previewModel(value) {
    const preset = PRESETS[value];
    if (!preset) {
        const auto = value === "AUTO（根据意图判断）";
        return {
            authority: "MiniMax 官方创意预设",
            title: value || "MiniMax 官方创意预设",
            summary: auto
                ? "AUTO 会根据用户意图选择最多一个官方场景写作规则；悬停具体预设可查看它的官方 GIF。"
                : "悬停一个具体的官方场景预设即可查看对应官方 GIF。",
            empty_message: auto ? "AUTO 没有固定画面样例。" : "当前未启用具体官方预设。",
            previews: [],
            policy: "官方 GIF 仅供选择时预览，不会发送给 LLM",
        };
    }
    return {
        authority: "MiniMax 官方创意预设",
        title: value,
        summary: preset.summary,
        previews: [{
            label: "MiniMax 官方示例 GIF",
            url: previewUrl(preset.file),
            available: true,
            source_url: `${OFFICIAL_SKILL_ROOT}/${preset.skill}`,
            source_label: "查看 MiniMax 官方 Skill",
        }],
        policy: "官方 GIF 仅供选择时预览，不会发送给 LLM",
    };
}


export function addOfficialPresetMenuPreview(node, widget) {
    registerTemplateMenuPreview(node, widget, previewModel);
}


export { OFFICIAL_COMMIT, PRESETS as OFFICIAL_PRESET_PREVIEWS };
