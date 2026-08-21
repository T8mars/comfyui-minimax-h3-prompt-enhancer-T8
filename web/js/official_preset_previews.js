import { registerTemplateMenuPreview } from "./template_menu_preview.js";
import {
    createTemplateDetailCard,
    renderTemplateDetail,
    setDomWidgetVisible,
} from "./case_template_ui.js";


const OFFICIAL_COMMIT = "743d51e83329cbae6c7694f1c7b89576e7c25e07";
const OFFICIAL_SKILL_ROOT = `https://github.com/MiniMax-AI/MiniMax-H3/tree/${OFFICIAL_COMMIT}/skills`;


const PRESETS = {
    "极简产品广告": {
        skill: "minimalist-product-ad-generator",
        file: "minimalist-product-ad-generator.gif",
        summary: "以产品实物、克制场景、材质细节和单一文案事件组成极简广告。",
        applicability: "适合电商展示、产品发布和单一核心卖点短片；不适合口播种草、复杂软件演示或未经核验的品牌宣传。",
        input_format: "产品名称或产品图 + 1–3 个真实卖点 + 材质/颜色 + 目标平台或画幅 + 可选精确文案。",
        recommended_input: "为一款磨砂银便携咖啡机制作极简产品短片，突出金属质感、旋钮操作和一键萃取，结尾保持产品完整可见，不添加未经提供的品牌文案。",
        required_anchors: ["产品身份、颜色与材质稳定", "干净负空间和单一视觉重点", "每个节拍只承担一个主要动作", "稳定产品收尾与可读的已提供文案"],
    },
    "3D 动画短片": {
        skill: "3d-animation-short-generator",
        file: "3d-animation-short-generator.gif",
        summary: "围绕角色、场景、表演、镜头连续性与动画运动规律组织 3D 短片。",
        applicability: "适合有明确角色、场景和短事件弧的风格化 3D 动画；不适合单张静态图、纯剪辑或写实实拍任务。",
        input_format: "故事目标 + 角色的 2–3 个固定特征 + 场景地标 + 核心动作/情绪 + 可选声音与结尾。",
        recommended_input: "戴黄色围巾的圆滚滚小机器人在雨后巷口追逐一只发光纸飞机，先笨拙起跑，再跃过水洼，最后接住纸飞机并开心定格。",
        required_anchors: ["角色可识别特征全程一致", "场景地标、尺度和光向连续", "动作具备预备、主动作与跟随", "单镜重要角色数量保持可读"],
    },
    "品牌宣传短片": {
        skill: "brand-promo-video-generator",
        file: "brand-promo-video-generator.gif",
        summary: "用可核验的品牌事实、产品功能证据与行动号召推进宣传短片。",
        applicability: "适合品牌、应用、网站、店铺或个人项目的发布与功能宣传；只使用用户提供或素材中可验证的事实。",
        input_format: "品牌/产品名称 + 已核验功能或卖点 + 使用场景 + 精确标题/口号/行动号召 + 目标平台。",
        recommended_input: "为 NoteFlow 笔记应用制作功能宣传短片，展示语音转文字、待办提取和跨设备同步三个已提供功能；结尾只显示“记录灵感，立即开始”。",
        required_anchors: ["品牌名称、标志和文案保持准确", "每段画面证明一个具体功能", "界面与主体留出清晰安全空间", "以用户提供的行动号召稳定收束"],
    },
    "音乐 MV 动态字幕（官方）": {
        skill: "music-video-subtitle-generator",
        file: "music-video-subtitle-generator.gif",
        summary: "把音乐、人声、表演、镜头和空间动态字幕组织成统一节奏系统。",
        applicability: "适合音乐 MV、情绪短片和歌词驱动的空间文字设计；不是普通字幕清理，也不会假装分析未连接的音频。",
        input_format: "音乐风格/节奏感 + 情绪与表演主体 + 已锁定歌词或明确授权原创歌词 + 字幕空间风格 + 人物/场景/文字参考分工。",
        recommended_input: "暗蓝霓虹雨夜的抒情电子 MV，女歌手边走边唱，锁定歌词“穿过雨幕，我仍看见你”；文字化作潮湿反光在街面和玻璃间随节拍移动。",
        required_anchors: ["歌词逐字锁定或获得明确原创授权", "口型、表演与人声条件一致", "空间文字避开脸部和关键动作", "音乐、人声、画面节拍与参考角色分离"],
    },
    "双人合作游戏开场": {
        skill: "co-op-game-intro-generator",
        file: "co-op-game-intro-generator.gif",
        summary: "锁定两位角色、左右位置、玩家信息与菜单布局，完成清晰的合作开场。",
        applicability: "适合双人合作游戏菜单、角色选择或开场动画；不用于虚构未提供的游戏机制、在线服务或分数。",
        input_format: "两位角色及左右位置 + 玩家名 + 游戏标题 + 按钮/UI 精确文案 + 配色 + 一次合作触发事件。",
        recommended_input: "双人合作游戏开场：左侧机械师 MIKA、右侧侦察员 RIN，标题“STAR RELAY”，按钮“开始协作”；两人同时确认后能量线路在中间连通。",
        required_anchors: ["恰好两位玩家且左右身份稳定", "玩家名、标题和按钮文案准确", "UI 层级清晰且主色数量克制", "合作动作产生一个可见反馈"],
    },
    "纸拼贴讲解": {
        skill: "paper-collage-explainer-generator",
        file: "paper-collage-explainer-generator.gif",
        summary: "用纸张物件关系、拼贴装配和触感声音解释抽象概念。",
        applicability: "适合知识点、观点、旁白或抽象概念的触感拼贴讲解；可输出单段短视频提示词，不扩展成完整制作流程。",
        input_format: "要解释的知识点/旁白 + 核心视觉隐喻 + 纸张配色与质感 + 是否需要字幕、配音或音乐。",
        recommended_input: "用暖白底的半调纸拼贴解释“复利像滚雪球”：一枚小纸币折成纸球，沿纸坡滚动并逐步粘上更多数字纸片，最后停在清晰增长曲线旁。",
        required_anchors: ["抽象概念对应一个清晰视觉隐喻", "纸张、半调纹理和投影保持一致", "滑入、弹入、压平等停格动作可读", "纸张摩擦和轻敲声对应可见动作"],
    },
    "立体纸艺停格讲解": {
        skill: "papercraft-stop-motion-explainer",
        file: "papercraft-stop-motion-explainer.gif",
        summary: "用分层纸雕、机械纸艺动作和停格节奏建立可读的知识路径。",
        applicability: "适合科学、教育和通识内容的分层纸景讲解；尤其适合翻页、弹起、拉条和纸偶机械动作。",
        input_format: "学习目标 + 纸艺视觉隐喻 + 分层场景/纸偶/道具 + 关键机械动作 + 可选标签、旁白和声音。",
        recommended_input: "用分层纸雕解释火山喷发：地壳剖面从书页中弹起，拉条推动岩浆纸带上升，山体翻折打开并喷出红橙纸屑，最后露出三层结构标签。",
        required_anchors: ["分层纸景的材质、比例与光照连续", "折叠、弹起、拉条或翻页驱动知识变化", "标签只出现在稳定可读的纸层", "纸张、卡扣和翻页声音与动作同步"],
    },
    "手绘实拍融合": {
        skill: "handdrawn-live-video-generator",
        file: "handdrawn-live-video-generator.gif",
        summary: "让手绘实体与真实空间发生可见接触、连续变形和延迟追拍。",
        applicability: "适合单一实拍空间中的手绘实体接触、变形、逃逸与追拍；不适合精致 CG、恐怖突吓或多场景快切。",
        input_format: "实拍空间 + 手绘实体外观 + 首次物理接触 + 连续变形/逃逸路线 + 摄影机反应 + 非恐怖基调。",
        recommended_input: "真实咖啡店桌面上，一条粗糙发光粉笔鱼从纸杯图案里探头，碰到勺子后沿桌面游动并变成纸鹤，手持镜头慢半拍追随它飞向窗边。",
        required_anchors: ["开场前段发生手绘与实拍物体接触", "同一实体在变形中保持连续身份", "沿真实空间留下可见手绘痕迹", "手持摄影机稍微延迟追随且保持轻松基调"],
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
        input_format: preset.input_format,
        recommended_input: preset.recommended_input,
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


function detailTemplate(value, preset) {
    return {
        label: value,
        summary: preset.summary,
        applicability: preset.applicability,
        input_format: preset.input_format,
        required_anchors: preset.required_anchors,
        recommended_input: preset.recommended_input,
        previews: [{
            label: "MiniMax 官方示例 GIF",
            preview_url: previewUrl(preset.file),
            available: true,
            source_url: `${OFFICIAL_SKILL_ROOT}/${preset.skill}`,
            source_label: "查看 MiniMax 官方 Skill",
        }],
    };
}


export function addOfficialPresetMenuPreview(node, widget) {
    registerTemplateMenuPreview(node, widget, previewModel);
}


export function addOfficialPresetUI(node, widget, promptWidget, refreshSize) {
    if (!widget || !promptWidget) return null;
    addOfficialPresetMenuPreview(node, widget);

    const root = createTemplateDetailCard();
    const domWidget = node.addDOMWidget("t8_official_preset_details", "custom", root, {
        getValue: () => "",
        setValue: () => {},
        getMinHeight: () => Math.max(150, root.scrollHeight + 8),
        getMaxHeight: () => Math.max(150, root.scrollHeight + 8),
        hideOnZoom: false,
        serialize: false,
        beforeResize() { delete this.width; },
        afterResize(resizedNode) {
            delete this.width;
            resizedNode.setDirtyCanvas(true, true);
        },
    });
    delete domWidget.width;
    domWidget.serializeValue = () => undefined;

    const update = (value = widget.value) => {
        const preset = PRESETS[value];
        if (!preset) {
            root.replaceChildren();
            setDomWidgetVisible(domWidget, false);
        } else {
            renderTemplateDetail(
                root,
                detailTemplate(value, preset),
                promptWidget,
                node,
                refreshSize,
                {
                    resolvePreviewUrl: (preview) => preview.preview_url,
                    sourceLabel: "查看 MiniMax 官方 Skill",
                    policyText: "MiniMax 官方 GIF 仅供人类本地预览，不会作为图像、视频或 LLM 参考素材",
                },
            );
            setDomWidgetVisible(domWidget, true);
        }
        refreshSize?.();
    };
    const originalCallback = widget.callback;
    widget.callback = function (value) {
        originalCallback?.apply(this, arguments);
        update(value);
    };
    node.t8UpdateOfficialPreset = update;
    update();
    return domWidget;
}


export { OFFICIAL_COMMIT, PRESETS as OFFICIAL_PRESET_PREVIEWS };
