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
test("connected status distinguishes manual loading and unavailable enabled vision", () => {
    const text=ui.statusText({connected:true,model:"test",context:32768,loaded:false,auto_load:false,vision_enabled:true,vision_available:false});
    assert.match(text,/请先在 Strata 手动加载模型/);
    assert.match(text,/已启用但尚不可用/);
    assert.doesNotMatch(text,/连接未通过|按配置自动加载/);
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
test("shared provider follows bounded reroute chains, Map links, and upstream non-Strata overrides", () => {
    const config = node(); config.widgets[0].value = "Strata";
    const relay = { type: "Reroute", inputs: [{ link: 7 }] };
    const nodes = new Map([[1, config], [2, relay]]);
    const graph = { links: new Map([[7, { origin_id: 1 }], [8, { origin_id: 2 }]]), getNodeById: id => nodes.get(id) };
    const main = { widgets: [{ name: "api_mode", value: "cloud" }], inputs: [{ name: "provider_config", link: 8 }], graph };
    assert.equal(ui.effectiveStrata(main), true, "shared config still controls the backend through Reroute");
    config.widgets[0].value = "Local Qwen";
    main.widgets[0].value = ui.STRATA_API_MODE;
    assert.equal(ui.effectiveStrata(main), false, "shared local override wins over saved Strata mode");
    relay.inputs[0].link = 8;
    assert.equal(ui.effectiveStrata(main), true, "cycles cannot hang UI and use the node's saved mode");
    relay.inputs[0].link = null;
    assert.equal(ui.effectiveStrata(main), true, "disconnected relay falls back to the node mode");
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
test("real extension refreshes distant consumers after reroute input changes without replacing host callbacks", async () => {
    let extension; const frames=[];
    const context=vm.createContext({...ui,app:{registerExtension(e){extension=e;}},requestAnimationFrame(fn){frames.push(fn);},window:{alert(){}}});
    const source=(await readFile(new URL("../../web/js/strata_bridge_ui.js",import.meta.url),"utf8")).replace(/^import\s.*;\s*$/gm,"");
    vm.runInContext(source,context);
    class N { constructor() { Object.assign(this,node(["api_mode","api_key","local_model"])); this.comfyClass="QwenImage21PromptEnhancerT8"; } }
    await extension.beforeRegisterNodeDef(N,{name:"QwenImage21PromptEnhancerT8"});
    const config=node(); config.widgets[0].value="Strata";
    const relay={type:"Reroute",inputs:[{link:7}]};
    let hostCalls=0;
    const graph={_nodes:[],links:{7:{origin_id:1},8:{origin_id:2}},getNodeById:id=>id===1?config:relay,
        onNodeConnectionChange(){hostCalls++;return "host-return";}};
    const n=new N(); n.graph=graph; n.inputs=[{name:"provider_config",link:8}]; n.widgets[0].value="cloud";
    graph._nodes=[config,relay,n]; n.onNodeCreated(); n.onAdded(); while(frames.length)frames.shift()();
    assert.equal(n.widgets[1].hidden,true);
    relay.inputs[0].link=null;
    for(let i=0;i<5;i++)assert.equal(graph.onNodeConnectionChange(),"host-return");
    assert.equal(frames.length,1,"connection burst is coalesced");
    while(frames.length)frames.shift()();
    assert.equal(hostCalls,5); assert.equal(n.widgets[1].hidden,undefined);
    assert.equal(n.t8StrataNoticeWidget.hidden,true);
    relay.inputs[0].link=7; graph.onNodeConnectionChange(); while(frames.length)frames.shift()();
    assert.equal(n.widgets[1].hidden,true); assert.equal(n.t8StrataNoticeWidget.hidden,undefined);
});
