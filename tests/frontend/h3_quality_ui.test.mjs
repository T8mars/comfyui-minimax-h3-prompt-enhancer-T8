import test from "node:test";
import assert from "node:assert/strict";
import { addQualityUI, QUALITY_HELP_HEIGHT, qualityStatusText } from "../../web/js/h3_quality_ui.mjs";
import { sanitizeQualityMetadata } from "../../web/js/diagnostics_viewer.mjs";
test("quality UI remains fixed through 40 selection cycles and repeated execution", () => {
    const old = globalThis.document;
    globalThis.document = { createElement: () => ({ style: {}, setAttribute() {} }) };
    try {
        const node = { widgets: [{name:"quality_mode", value:"off"}, {name:"creation_mode", value:"off"}],
            addDOMWidget(name, type, element, options) { const w={name,type,element,options}; this.widgets.push(w); return w; },
            graph:{ change() {} }, setDirtyCanvas() {} };
        const widget = addQualityUI(node);
        assert.match(widget.element.textContent, /H3 说话人格式自动免费修复/);
        for (let n=0; n<40; n++) {
            node.widgets[0].value=n%2 ? "check" : "repair"; node.widgets[0].callback();
            node.onExecuted({ t8_quality_status:[JSON.stringify({result:"candidate_rejected", issue_codes:["h3_alignment"], correction_calls:1})] });
            assert.match(widget.element.textContent, /保留完整稿/);
            assert.equal(widget.options.getMinHeight(), QUALITY_HELP_HEIGHT);
            assert.equal(widget.options.getMaxHeight(), QUALITY_HELP_HEIGHT);
            assert.equal(widget.options.margin, 0);
            assert.equal(node.widgets.length, 3);
        }
        assert.equal(addQualityUI(node), widget);
        assert.equal(widget.serializeValue(), undefined);
        node.onExecuted({ t8_quality_status:[JSON.stringify({result:"corrected", quality_mode:"保持原样 / Off", issue_codes:[], correction_calls:0, protocol_edits:1, unchecked:["contract_check"]})] });
        assert.match(widget.element.textContent, /追加纠正 0 次/);
        assert.match(widget.element.textContent, /未进行完整质量检查/);
    } finally { globalThis.document=old; }
});
test("quality diagnostics never accept arbitrary strings or private errors", () => {
    const metadata=sanitizeQualityMetadata({result:"corrected", quality_mode:"secret", issue_codes:["h3_alignment","secret"], unchecked:["physical_plausibility","secret"], correction_calls:18, prompt:"secret"});
    assert.deepEqual(metadata,{ result:"corrected", issue_codes:["h3_alignment"], unchecked:["physical_plausibility"] });
    assert.doesNotMatch(qualityStatusText({result:"secret"}), /secret/);
    assert.doesNotThrow(() => qualityStatusText({result:"corrected", unchecked:{private:"secret"}}));
});
