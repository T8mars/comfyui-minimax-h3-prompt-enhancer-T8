import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import * as ui from "../../web/js/strata_ui.mjs";

const old = ["Local Qwen", "AUTO（兼容策略）", "test.gguf", "AUTO（自动匹配）", 32768, 16384,
    "关闭（推荐，速度优先）", "medium", 2, "执行后卸载（推荐）", "AUTO（显存不足时释放）", "", "", "", "gemini-3.5-flash", ""];
const current = [...old]; current[0] = "Strata"; current.push(...Object.values(ui.STRATA_DEFAULTS));
current[16] = "http://127.0.0.1:9999"; current[17] = "chosen-model";
function node(order = ui.CONFIG_NAMES) {
    return { widgets: order.map(name => ({ name, value: null, type: "combo" })), size: [400, 250],
        comfyClass: "T8LLMProviderConfig", properties: {}, setDirtyCanvas() {},
        addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options }; this.widgets.push(w); return w; },
        setSize(value) { this.size = value; }, computeSize() { return [400, this.widgets.filter(w => !w.hidden).length * 24]; } };
}
test("native pre-Strata 16 order is frozen, new 27 values restore synchronously by name", () => {
    for (const values of [old, current]) for (const named of [false, true]) {
        const n = node([...ui.CONFIG_NAMES].reverse());
        const saved = { widgets_values: [...values, "ignored button tail"] };
        if (named) saved.widgets_values_named = Object.fromEntries(ui.CONFIG_NAMES.slice(0, values.length).map((s, i) => [s, values[i]]));
        ui.configureConfig(n, saved, function(data) { data.widgets_values.forEach((v, i) => this.widgets[i].value = v); }, [saved]);
        for (let i=0; i<values.length; i++) assert.equal(n.widgets.find(w=>w.name===ui.CONFIG_NAMES[i]).value, values[i]);
        const output = {}; ui.serializeConfig(n, output);
        assert.equal(output.widgets_values.length, 27);
        assert.equal(output.widgets_values_named.strata_url, values.length===27 ? current[16] : ui.STRATA_DEFAULTS.strata_url);
    }
});
test("legacy declaration order, corrupt native named metadata, and action tails cannot shift values", () => {
    const declaration = [old[0], ...old.slice(11,15), old[1],old[15], ...old.slice(2,11)];
    const got = ui.configSavedValues({ widgets_values: [...declaration, "button"], widgets_values_named: { provider: "Strata", temperature_policy: old[1], local_model: "wrong" } });
    assert.equal(got.get("provider"), "Local Qwen"); assert.equal(got.get("local_model"), "test.gguf");
    assert.equal(got.get("strata_url"), ui.STRATA_DEFAULTS.strata_url);
});
test("read-only probe never calls chat; changed mode and removed node discard stale response", async () => {
    const n=node(); n.widgets[0].value="Strata";
    let done, request;
    const waiting=ui.probeStrata(n,{},(url,options)=>{request={url,options}; return new Promise(r=>done=r);});
    n.widgets[0].value="Local Qwen";
    done({json:async()=>({connected:true,model:"test"})});
    assert.equal(await waiting,null); assert.equal(request.url,"/t8-prompt-enhancer/strata/status");
    assert.equal(request.options.method,"POST"); assert.equal(Object.keys(JSON.parse(request.options.body)).some(k=>k==="api_key"),false);
});
test("visibility switching and shared override retain old cloud/local values", () => {
    const n=node(); n.widgets[0].value="Strata"; n.widgets.find(w=>w.name==="custom_model").value="cloud-model";
    ui.updateStrataVisibility(n); assert.equal(n.widgets.find(w=>w.name==="custom_model").hidden,true);
    ui.restoreStrataVisibility(n); n.widgets[0].value="Local Qwen"; ui.updateStrataVisibility(n);
    assert.equal(n.widgets.find(w=>w.name==="custom_model").value,"cloud-model");
    assert.equal(n.widgets.find(w=>w.name==="strata_url").hidden,true);
    const main={widgets:[{name:"api_mode",value:"old cloud"}], inputs:[{name:"provider_config",link:1}],graph:{links:{1:{origin_id:2}},getNodeById:()=>n}};
    assert.equal(ui.effectiveStrata(main),false); n.widgets[0].value="Strata"; assert.equal(ui.effectiveStrata(main),true);
});
test("real generic extension hooks are idempotent, notices are never serialized", async () => {
    let extension; const frames=[];
    const context=vm.createContext({...ui,app:{registerExtension(e){extension=e;}},requestAnimationFrame(fn){frames.push(fn);},window:{alert(){}}});
    const source=(await readFile(new URL("../../web/js/strata_bridge_ui.js",import.meta.url),"utf8")).replace(/^import\s.*;\s*$/gm,"");
    vm.runInContext(source,context);
    class N {constructor(){Object.assign(this,node());} onConfigure(){} }
    await extension.beforeRegisterNodeDef(N,{name:"T8LLMProviderConfig"});
    const n=new N(); n.onNodeCreated(); n.widgets[0].value="Strata"; n.widgets[0].callback(); const size=[...n.size];
    for(let i=0;i<8;i++){n.onConfigure({}); while(frames.length)frames.shift()();}
    assert.deepEqual([...n.size],size); assert.equal(n.widgets.filter(w=>w===n.t8StrataNoticeWidget).length,1);
    assert.equal(n.t8StrataNoticeWidget.options.serialize,false); assert.equal(n.t8StrataNoticeWidget.serializeValue(),undefined);
    n.widgets[0].value="Local Qwen";n.widgets[0].callback();n.size=[600,777];
    n.onConfigure({});while(frames.length)frames.shift()();assert.deepEqual([...n.size],[600,777],"old saved/manual size is preserved");
});
