function tokens(value) {
    const text = String(value || "").toLocaleLowerCase();
    const result = new Set(text.match(/[a-z0-9][a-z0-9._-]{1,}|[\u4e00-\u9fff]{2,}/g) || []);
    for (const segment of text.match(/[\u4e00-\u9fff]{3,}/g) || []) {
        for (let index = 0; index < segment.length - 1; index += 1) result.add(segment.slice(index, index + 2));
    }
    return result;
}


function searchText(template) {
    return [
        template.label, template.summary, template.input_format, template.recommended_input,
        ...(template.required_anchors || []), template.authority, template.template_kind,
    ].join(" ");
}


export function rankTemplates(templates, context = {}, limit = 3) {
    const query = [context.prompt, context.task, context.media].filter(Boolean).join(" ");
    const queryTokens = tokens(query);
    const prompt = String(context.prompt || "");
    return [...(templates || [])].map((template) => {
        const corpus = searchText(template).toLocaleLowerCase();
        const corpusTokens = tokens(corpus);
        const matches = [...queryTokens].filter((token) => corpusTokens.has(token) || corpus.includes(token));
        let score = matches.reduce((total, token) => total + Math.min(8, token.length), 0);
        const reasons = [];
        if (matches.length) reasons.push(`关键词匹配：${matches.slice(0, 4).join("、")}`);
        if (/图片|image|i2v|ref/i.test(String(context.media || "")) && /图片|人物|角色|主体|参考|image/i.test(corpus)) {
            score += 5;
            reasons.push("适合已连接图片/参考素材");
        }
        if (/视频|video|edit|extend/i.test(String(context.media || "")) && /视频|动作|时序|变化|衔接|video/i.test(corpus)) {
            score += 5;
            reasons.push("适合视频时序或编辑素材");
        }
        if (/mv|音乐|舞|节奏|music/i.test(prompt) && /mv|音乐|舞|节奏|music/i.test(corpus)) {
            score += 7;
            reasons.push("音乐/节奏意图一致");
        }
        if (/广告|产品|品牌|logo/i.test(prompt) && /广告|产品|品牌|logo/i.test(corpus)) {
            score += 7;
            reasons.push("品牌/产品意图一致");
        }
        if (!reasons.length) reasons.push("按任务类型与模板结构稳定排序");
        return { template, score, reasons };
    }).sort((left, right) => right.score - left.score || String(left.template.id).localeCompare(String(right.template.id)))
        .slice(0, Math.max(1, Number(limit) || 3));
}
