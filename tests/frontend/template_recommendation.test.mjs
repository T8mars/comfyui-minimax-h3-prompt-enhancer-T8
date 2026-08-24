import assert from "node:assert/strict";
import test from "node:test";

import { rankTemplates } from "../../web/js/template_recommendation.mjs";


const templates = [
    { id: "ad", label: "品牌产品广告", summary: "产品功能证明", input_format: "产品", recommended_input: "耳机广告", required_anchors: ["产品"] },
    { id: "mv", label: "音乐舞台 MV", summary: "节奏舞蹈", input_format: "歌曲", recommended_input: "舞台 MV", required_anchors: ["节拍"] },
    { id: "world", label: "世界探索", summary: "空间路线", input_format: "人物和世界", recommended_input: "穿越城市", required_anchors: ["路线"] },
];


test("Top-3 recommendation is deterministic and explains matching", () => {
    const first = rankTemplates(templates, { prompt: "耳机品牌产品广告", task: "I2VA", media: "reference_image_0" });
    const second = rankTemplates(templates, { prompt: "耳机品牌产品广告", task: "I2VA", media: "reference_image_0" });
    assert.equal(first[0].template.id, "ad");
    assert.deepEqual(first, second);
    assert.match(first[0].reasons.join(" "), /关键词|品牌/);
});


test("recommendation never mutates the catalog", () => {
    const before = JSON.stringify(templates);
    rankTemplates(templates, { prompt: "舞蹈音乐 MV" });
    assert.equal(JSON.stringify(templates), before);
});
