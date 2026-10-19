// Wait for the real asynchronous browser harness to finish instead of trusting
// Chromium's --dump-dom timing under a virtual-time budget.
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const [browser, url, screenshotPath = "", mode = "harness", markerProviderBase = ""] = process.argv.slice(2);
if (!browser || !url) throw new Error("Usage: node frontend_browser_cdp.mjs BROWSER URL [SCREENSHOT]");
const profile = await mkdtemp(join(tmpdir(), "t8-browser-cdp-"));
const chrome = spawn(browser, [
  "--headless=new", "--disable-gpu", "--disable-extensions",
  "--disable-background-networking", "--no-first-run",
  "--remote-debugging-port=0", "--remote-allow-origins=*",
  `--user-data-dir=${profile}`, url,
], { stdio: "ignore" });
const deadline = Date.now() + (mode.startsWith("comfy-") ? 75000 : 30000);
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket;

async function connect() {
  let port;
  while (!port && Date.now() < deadline) {
    if (chrome.exitCode !== null) throw new Error(`Chromium exited before DevTools opened (${chrome.exitCode})`);
    try { port = Number((await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]); }
    catch { await pause(100); }
  }
  if (!port) throw new Error("Timed out waiting for Chromium DevTools port");
  let target;
  while (!target && Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const pages = await response.json();
      target = pages.find(page => page.type === "page" && page.url === url) || pages.find(page => page.type === "page");
    } catch { /* The port file can precede the HTTP listener. */ }
    if (!target) await pause(100);
  }
  if (!target) throw new Error("Timed out waiting for browser page");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((done, fail) => {
    socket.addEventListener("open", done, { once: true });
    socket.addEventListener("error", fail, { once: true });
  });
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener("message", event => {
    const response = JSON.parse(event.data);
    if (!response.id || !pending.has(response.id)) return;
    const { done, fail } = pending.get(response.id);
    pending.delete(response.id);
    response.error ? fail(new Error(response.error.message)) : done(response.result);
  });
  return (method, params = {}) => new Promise((done, fail) => {
    const id = ++nextId;
    pending.set(id, { done, fail });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

try {
  const send = await connect();
  if (mode === "comfy-marker") {
    const markerWorkflows = await Promise.all(["ref2va","hybrid"].map(async target=>JSON.parse(await readFile(
      new URL(`../example_workflows/h3_visual_marker_${target}.json`,import.meta.url),"utf8"))));
    await send("Emulation.setDeviceMetricsOverride", {width:1800,height:1400,deviceScaleFactor:1,mobile:false});
    let ready=false;
    while(Date.now()<deadline&&!ready){
      const check=await send("Runtime.evaluate",{expression:"!!globalThis.LiteGraph?.registered_node_types?.T8H3VisualMarkerConfig && !document.getElementById('splash-loader')",returnByValue:true});
      ready=check.result?.value===true;
      if(!ready)await pause(200);
    }
    if(!ready)throw new Error("Native marker config unavailable");
    const check=await send("Runtime.evaluate",{awaitPromise:true,returnByValue:true,expression:`(async()=>{
      const {app}=await import('/scripts/app.js');
      const wi=await import('/extensions/core/widgetInputs.js');
      const assert=(ok,text)=>{if(!ok)throw new Error(text)};
      const providerBase=${JSON.stringify(markerProviderBase)};
      if(providerBase)assert(new URL(providerBase).hostname==='127.0.0.1','Owned loopback provider required');
      const queueResults=[];
      const setValue=(node,name,value)=>{
        const w=node.widgets.find(w=>w.name===name);assert(w,'Missing widget '+name);
        w.value=value;
        if(w.inputEl)w.inputEl.value=value;
        if(w.element?.matches?.('input,textarea'))w.element.value=value;
        const input=w.element?.querySelector?.('input,textarea');if(input)input.value=value;
        w.callback?.(value);
      };
      const nativeQueue=async(label,node)=>{
        if(!providerBase)return;
        setValue(node,'openai_base_url',providerBase);
        setValue(node,'custom_model','marker-fixture');
        setValue(node,'api_mode','OpenAI兼容接口（备用）');
        setValue(node,'output_language','English');
        if(node.widgets.some(w=>w.name==='api_key'))setValue(node,'api_key','test-placeholder');
        else {
          const slot=node.inputs.findIndex(i=>i.name==='api_key');
          if(node.inputs[slot].link==null){
            const key=LiteGraph.createNode('T8PromptText');app.graph.add(key);key.pos=[30,1100];setValue(key,'text','test-placeholder');
            assert(key.connect(0,node,slot),'Native linked credential fixture');
          }
        }
        const output=await app.graphToPrompt();
        assert(output.output[node.id].inputs.openai_base_url===providerBase,'Actual native provider URL');
        const response=await fetch('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:output.output})});
        const ack=await response.json();assert(response.ok,label+' native graph rejected: '+JSON.stringify(ack));
        const until=Date.now()+45000;
        while(Date.now()<until){
          const history=(await(await fetch('/history/'+ack.prompt_id)).json())[ack.prompt_id];
          if(history){assert(history.status.status_str==='success',label+' native queue failed: '+JSON.stringify(history.status));queueResults.push({label,success:true});return;}
          await new Promise(done=>setTimeout(done,100));
        }
        throw new Error(label+' native queue outcome unknown');
      };
      for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
      app.graph.clear();
      let helper=LiteGraph.createNode('T8H3VisualMarkerConfig');
      let main=LiteGraph.createNode('MiniMaxH3PromptEnhancerT8');
      let source=LiteGraph.createNode('T8MarkerRuntimeFixture');
      for(const n of [source,helper,main])app.graph.add(n);
      source.pos=[20,30];helper.pos=[400,40];main.pos=[900,40];
      const names=helper.widgets.filter(w=>w.options?.serialize!==false&&w.serialize!==false).map(w=>w.name);
      assert(JSON.stringify(names)==='["mode","picture_selector"]','Two native widgets only');
      assert(helper.widgets[0].value==='关闭 / Off'&&helper.widgets[1].value===0,'Native defaults');
      const guide=await import('/extensions/'+${JSON.stringify("comfyui-minimax-h3-prompt-enhancer-T8")}+'/h3_visual_marker.js');
      const guideButton=helper.widgets.find(w=>w.name===guide.MARKER_HELP_BUTTON);
      assert(guideButton&&guideButton.options.serialize===false,'Visible nonserializing example button');
      guide.attachMarkerGuide(helper);guide.attachMarkerGuide(helper);
      assert(helper.widgets.filter(w=>w.name===guide.MARKER_HELP_BUTTON).length===1,'Guide attachment is idempotent');
      // The existing asynchronous case-library UI adds buttons after its
      // catalog arrives. Wait for initialization, not merely quiet frames.
      const caseReadyUntil=Date.now()+30000;
      while(!main.widgets.some(w=>w.name==='管理 / 更新 T8 动态预览')&&Date.now()<caseReadyUntil)
        await new Promise(done=>setTimeout(done,100));
      assert(main.widgets.some(w=>w.name==='管理 / 更新 T8 动态预览'),'Existing H3 case-library initialization completed');
      const stableNodes=async()=>{
        let previous='',unchanged=0;
        for(let i=0;i<40;i++){
          await new Promise(done=>setTimeout(done,150));
          const current=JSON.stringify(app.graph.serialize().nodes);
          unchanged=current===previous?unchanged+1:0;
          if(unchanged>=8)return current;
          previous=current;
        }
        throw new Error('Native graph did not stabilize before guide comparison');
      };
      const graphBeforeGuide=await stableNodes();
      const sizeEvents=[];const originalSetSize=main.setSize;
      main.setSize=function(...args){sizeEvents.push({size:args[0],stack:new Error().stack});return originalSetSize.apply(this,args);};
      guideButton.callback();
      guideButton.callback();
      assert(document.querySelectorAll('[data-t8-marker-guide]').length===1,'Reopening keeps a single guide');
      const dialog=document.querySelector('[data-t8-marker-guide]');
      assert(dialog?.textContent.includes('marker_plan')&&dialog.textContent.includes('selector=0'),'Concrete wiring tutorial');
      assert(dialog.querySelectorAll('button[data-marker-action]').length===4,'PNG, two JSON downloads and close');
      const downloads=[];
      const originalApiFetch= (await import('/scripts/api.js')).api.fetchApi;
      const apiModule=(await import('/scripts/api.js')).api;
      let failTemplateOnce=true;
      apiModule.fetchApi=async function(route,...args){
        if(route==='/workflow_templates'&&failTemplateOnce){failTemplateOnce=false;return new Response('',{status:500});}
        const response=await originalApiFetch.call(this,route,...args);
        if(route==='/workflow_templates'&&response.ok){
          const catalog=await response.json();
          catalog['disabled-marker-backup']=['h3_visual_marker_ref2va','h3_visual_marker_hybrid'];
          return new Response(JSON.stringify(catalog),{status:200,headers:{'Content-Type':'application/json'}});
        }
        return response;
      };
      const originalClick=HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click=function(){if(this.download)downloads.push({name:this.download,url:this.href});else originalClick.call(this);};
      try {
        const retryButton=dialog.querySelector('[data-marker-action="h3_visual_marker_ref2va"]');
        await retryButton.onclick();
        assert(!retryButton.disabled&&downloads.length===0&&dialog.querySelector('[role="status"]').textContent.includes('Cannot read'),'Failed download restores action for retry');
        for(const action of ['image','h3_visual_marker_ref2va','h3_visual_marker_hybrid']){
          await dialog.querySelector('[data-marker-action="'+action+'"]').onclick();
          const item=downloads.at(-1);assert(item,'Download produced '+action);
          const blob=await(await fetch(item.url)).blob();
          if(action==='image'){
            const bitmap=await createImageBitmap(blob);assert(bitmap.width===1440&&bitmap.height===960,'Companion PNG dimensions');bitmap.close();
            const upload=new FormData();upload.append('image',blob,'h3-marker-demo-source.png');upload.append('overwrite','true');upload.append('type','input');
            assert((await fetch('/upload/image',{method:'POST',body:upload})).ok,'Companion PNG uploaded to owned test input');
          } else {
            const workflow=JSON.parse(await blob.text());
            const expected=${JSON.stringify(markerWorkflows)}[action.endsWith('hybrid')?1:0];
            assert(JSON.stringify(workflow)===JSON.stringify(expected),'Downloaded exact bundled workflow');
            const config=workflow.nodes.find(n=>n.type==='T8H3VisualMarkerConfig');
            const h3=workflow.nodes.find(n=>n.type==='MiniMaxH3PromptEnhancerT8');
            assert(JSON.stringify(config.widgets_values)==='["关闭 / Off",0]'&&h3.widgets_values.length===38,'Download preserves Off/two helper values and 38 H3 values');
            assert(!h3.properties?.widgets_values_named?.api_key,'Downloaded example has no embedded credential');
          }
        }
      } finally {HTMLAnchorElement.prototype.click=originalClick;apiModule.fetchApi=originalApiFetch;}
      assert(downloads.length===3,'All tutorial downloads succeeded');
      const graphAfterGuide=await stableNodes();
      if(graphAfterGuide!==graphBeforeGuide){
        const before=JSON.parse(graphBeforeGuide),after=JSON.parse(graphAfterGuide);
        const difference=before.flatMap((node,i)=>Object.keys({...node,...after[i]}).filter(key=>JSON.stringify(node[key])!==JSON.stringify(after[i]?.[key])).map(key=>({node:node.id,key,before:node[key],after:after[i]?.[key]})));
        throw new Error('Tutorial mutated saved canvas fields: '+JSON.stringify({difference,sizeEvents}));
      }
      main.setSize=originalSetSize;
      dialog.querySelector('[data-marker-action="close"]').click();
      assert(helper.serialize().widgets_values.length===2,'Help action is not a third saved value');
      helper.widgets[0].value='开启（实验） / On (experimental)';helper.widgets[1].value=2;
      for(const [name,value] of Object.entries({prompt:'Walk through the doorway, then keep moving.',task_type:'Ref2VA（参考图/视频生音视频）',duration_seconds:3600,shot_count:'1',output_language:'English'})){
        const w=main.widgets.find(w=>w.name===name);w.value=value;w.callback?.(value);
      }
      if(!helper.inputs.some(i=>i.name==='picture_selector'))wi.convertToInput(helper,helper.widgets.find(w=>w.name==='picture_selector'));
      source.connect(0,helper,helper.inputs.findIndex(i=>i.name==='marker_plan'));
      source.connect(2,helper,helper.inputs.findIndex(i=>i.name==='picture_selector'));
      helper.connect(0,main,main.inputs.findIndex(i=>i.name==='visual_marker_config'));
      const imageSlot=main.inputs.findIndex(i=>i.name.startsWith('reference_images.'));
      assert(imageSlot>=0&&source.connect(1,main,imageSlot),'Fresh native reference image connection');
      const show=LiteGraph.createNode('T8ShowText');app.graph.add(show);show.pos=[1600,40];main.connect(0,show,0);
      const before=await app.graphToPrompt();
      assert(Array.isArray(before.output[helper.id].inputs.picture_selector),'Real computed INT link retained');
      const savedMain=main.serialize().widgets_values;
      assert(savedMain.length===38,'H3 keeps 38 saved values');
      const ids=[source.id,helper.id,main.id];
      const saved=app.graph.serialize();await app.loadGraphData(saved,false,true);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      [source,helper,main]=ids.map(id=>app.graph.getNodeById(id));
      const after=await app.graphToPrompt();
      const reloadValues=main.serialize().widgets_values;
      assert(JSON.stringify(reloadValues)===JSON.stringify(savedMain),'H3 38 values survive reload: '+JSON.stringify(savedMain.map((v,i)=>[i,v,reloadValues[i]]).filter(([i,a,b])=>JSON.stringify(a)!==JSON.stringify(b))));
      assert(JSON.stringify(after.output[helper.id].inputs)===JSON.stringify(before.output[helper.id].inputs),'Helper mode/plan/computed selector reload');
      assert(JSON.stringify(after.output[main.id].inputs.visual_marker_config)===JSON.stringify(before.output[main.id].inputs.visual_marker_config),'H3 config link reload');
      const heights=[helper.size[1],main.size[1]];
      const edgeState=()=>JSON.stringify([helper.inputs.map(i=>[i.name,i.link]),main.inputs.filter(i=>['visual_marker_config'].includes(i.name)||i.name.startsWith('reference_images.')).map(i=>[i.name,i.link])]);
      const initialEdges=edgeState();
      for(let i=0;i<8;i++){helper.widgets[0].value=i%2?'关闭 / Off':'开启（实验） / On (experimental)';helper.widgets[0].callback?.(helper.widgets[0].value);assert(helper.widgets[1].value===2&&edgeState()===initialEdges,'Mode cycles preserve selector and links');}
      helper.widgets[0].value='开启（实验） / On (experimental)';
      for(const [node,name,from,output] of [[helper,'picture_selector',source,2],[helper,'marker_plan',source,0],[main,'visual_marker_config',helper,0]]){
        const slot=node.inputs.findIndex(i=>i.name===name);node.disconnectInput(slot);assert(node.inputs[slot].link==null,'Disconnect');
        if(name==='picture_selector'){
          assert(helper.widgets.find(w=>w.name==='picture_selector').value===2,'Disconnect retains offline selector');
          assert((await app.graphToPrompt()).output[helper.id].inputs.picture_selector===2,'Disconnected API selector value');
        }
        assert(from.connect(output,node,slot),'Reconnect');
      }
      assert(helper.size[1]===heights[0]&&main.size[1]===heights[1],'Repeated cycles do not grow nodes');
      await nativeQueue('fresh-computed-selector-after-reload-reconnect',main);
      const examples=[];
      for(const graph of ${JSON.stringify(markerWorkflows)}){
        await app.loadGraphData(graph,false,true);
        await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
        const original=await app.graphToPrompt();
        const consumer=app.graph._nodes.find(n=>n.comfyClass==='MiniMaxH3PromptEnhancerT8');
        const fields=consumer.serialize().widgets_values;
        assert(fields.length===38,'Example has 38 fields');
        assert(new Set(consumer.inputs.map(i=>i.name)).size===consumer.inputs.length,'No duplicate input names');
        const inputs=original.output[consumer.id].inputs;
        assert(Array.isArray(inputs.visual_marker_config)&&Array.isArray(inputs['reference_images.reference_image_0']),'Example typed and IMAGE edges');
        assert(original.output[inputs.visual_marker_config[0]].inputs.mode==='关闭 / Off','Example default Off');
        await app.loadGraphData(app.graph.serialize(),false,true);
        await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
        const again=await app.graphToPrompt();
        const restored=app.graph.getNodeById(consumer.id);
        assert(JSON.stringify(restored.serialize().widgets_values)===JSON.stringify(fields),'Example values reload');
        for(const key of ['visual_marker_config','reference_images.reference_image_0','first_frame']){
          assert(JSON.stringify(again.output[consumer.id].inputs[key])===JSON.stringify(inputs[key]),'Example links reload: '+key);
        }
        await nativeQueue('example-'+inputs.task_type+'-off',restored);
        const cfg=app.graph.getNodeById(inputs.visual_marker_config[0]);
        setValue(cfg,'mode','开启（实验） / On (experimental)');
        await nativeQueue('example-'+inputs.task_type+'-on',restored);
        examples.push(inputs.task_type);
      }
      await new Promise(done=>setTimeout(done,500));
      app.canvas.ds.scale=.65;app.canvas.ds.offset[0]=120;app.canvas.ds.offset[1]=180;app.canvas.setDirty(true,true);
      const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: real H3 marker native widgets, linked computed INT, 38 saved values, reload/reconnect';document.body.append(p);
      return {config_native_widgets:names,h3_saved_widgets:savedMain.length,computed_int_link:true,reload:true,reconnect:true,examples,native_queue:queueResults,tutorial_downloads:downloads.map(x=>x.name)};
    })()`});
    if(check.exceptionDetails)throw new Error(JSON.stringify(check.exceptionDetails));
    process.stdout.write(JSON.stringify(check.result.value)+"\n");
    await pause(300);
    await send("Input.dispatchKeyEvent", {type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
    await send("Input.dispatchKeyEvent", {type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
  }
  if (mode === "comfy-storyboard") {
    const workflows = await Promise.all(["h3", "seedance20"].map(async target => JSON.parse(await readFile(
      new URL(`../example_workflows/storyboard_director_${target}_comparison.json`, import.meta.url), "utf8"))));
    await send("Emulation.setDeviceMetricsOverride", { width: 1800, height: 1350, deviceScaleFactor: 1, mobile: false });
    let ready = false;
    while (Date.now() < deadline && !ready) {
      const check = await send("Runtime.evaluate", {expression:"!!globalThis.LiteGraph?.registered_node_types?.T8StoryboardDirectorConfig && !document.getElementById('splash-loader') && !!document.querySelector('canvas')",returnByValue:true});
      ready = check.result?.value === true;
      if (!ready) await pause(200);
    }
    if (!ready) throw new Error("Real Comfy frontend did not register storyboard config");
    const check = await send("Runtime.evaluate", {awaitPromise:true,returnByValue:true,expression:`(async()=>{
      const {app}=await import('/scripts/app.js');
      const assert=(condition,message)=>{if(!condition)throw new Error(message);};
      for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
      app.graph.clear();
      const helper=LiteGraph.createNode('T8StoryboardDirectorConfig');app.graph.add(helper);
      const nativeNames=helper.widgets.map(w=>w.name);
      assert(JSON.stringify(nativeNames)==='["mode"]','Only one native config widget');
      assert(helper.widgets[0].value==='关闭 / Off','Native default must be Off');
      const observations=[];
      for(const workflow of ${JSON.stringify(workflows)}){
        await app.loadGraphData(workflow,false,true);
        await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
        const mains=app.graph._nodes.filter(n=>['MiniMaxH3PromptEnhancerT8','Seedance20PromptEnhancerT8'].includes(n.comfyClass));
        const configs=app.graph._nodes.filter(n=>n.comfyClass==='T8StoryboardDirectorConfig');
        assert(mains.length===2&&configs.length===2,'Paired native workflow loaded');
        const before=await app.graphToPrompt();
        const beforeSaved=new Map(mains.map(n=>[n.id,structuredClone(n.serialize().widgets_values)]));
        for(const node of mains){
          assert(node.serialize().widgets_values.length===38,'No extra main serialized widget');
          const slot=node.inputs.findIndex(i=>i.name==='storyboard_director_config');
          assert(slot>=0&&node.inputs[slot].link!=null,'Typed socket linked');
          assert(Number(before.output[node.id].inputs.duration_seconds)===60,'Actual API graph duration retained');
          assert(Array.isArray(before.output[node.id].inputs.storyboard_director_config),'API graph keeps typed config edge');
          const cfg=configs.find(c=>c.id===before.output[node.id].inputs.storyboard_director_config[0]);
          const savedMode=cfg.widgets[0].value;
          node.disconnectInput(slot);
          assert(node.inputs[slot].link==null,'Disconnect applied');
          cfg.connect(0,node,slot);
          assert(cfg.widgets[0].value===savedMode&&node.inputs[slot].link!=null,'Reconnect keeps mode');
          const size=[...node.size];
          for(let i=0;i<8;i++){cfg.widgets[0].value=i%2?'关闭 / Off':'开启（实验） / On (experimental)';cfg.widgets[0].callback?.(cfg.widgets[0].value);}
          cfg.widgets[0].value=savedMode;
          assert(node.size[1]===size[1],'Config cycles cannot grow consumer');
        }
        const saved=app.graph.serialize();await app.loadGraphData(saved,false,true);
        await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
        const reloaded=mains.map(n=>app.graph.getNodeById(n.id));
        assert(reloaded.every(Boolean),'Reloaded main nodes exist in current graph');
        const after=await app.graphToPrompt();
        for(const node of reloaded){
          assert(JSON.stringify(node.serialize().widgets_values)===JSON.stringify(beforeSaved.get(node.id)),'All 38 saved values survive native reload');
          const values=after.output[node.id].inputs;
          for(const key of ['prompt','seed','api_mode','rewrite_mode','quality_mode','creation_mode','output_language']){
            assert(key in values&&JSON.stringify(values[key])===JSON.stringify(before.output[node.id].inputs[key]),'Native API reload retains '+key);
          }
          assert(Number(values.duration_seconds)===60&&String(values.shot_count)==='3','Native reload retains duration and shots');
          assert(JSON.stringify(values.storyboard_director_config)===JSON.stringify(before.output[node.id].inputs.storyboard_director_config),'Native reload keeps links');
          const cfg=values.storyboard_director_config[0];
          assert(after.output[cfg].inputs.mode===before.output[cfg].inputs.mode,'Native mode reload');
        }
        observations.push({target:reloaded[0].comfyClass,main_widgets:reloaded[0].serialize().widgets_values.length,all_saved_values_equal:true,config_widgets:nativeNames,links:true});
      }
      app.canvas.ds.scale=0.65;app.canvas.ds.offset=[80,80];app.canvas.setDirty(true,true);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: native storyboard combo, paired workflow API values, save/reload, reconnect and stable heights';document.body.append(p);
      return observations;
    })()`});
    if(check.exceptionDetails)throw new Error(JSON.stringify(check.exceptionDetails));
    process.stdout.write(JSON.stringify(check.result.value)+"\n");
    // First-run template discovery can open after the graph is ready. Dismiss
    // through the normal keyboard path before capturing the actual canvas.
    await pause(400);
    for (let i=0;i<2;i++) {
      await send("Input.dispatchKeyEvent", {type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
      await send("Input.dispatchKeyEvent", {type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
      await pause(200);
    }
  }
  if (mode === "comfy-moss") {
    await send("Emulation.setDeviceMetricsOverride", { width: 1700, height: 1400, deviceScaleFactor: 1, mobile: false });
    let ready = false;
    while (Date.now() < deadline && !ready) {
      const check = await send("Runtime.evaluate", { expression: "!!globalThis.LiteGraph?.registered_node_types?.MOSSImagePromptEnhancerT8", returnByValue: true });
      ready = check.result?.value === true;
      if (!ready) await pause(200);
    }
    if (!ready) throw new Error("Real Comfy frontend did not register MOSS");
    const check = await send("Runtime.evaluate", { awaitPromise: true, returnByValue: true, expression: `(async()=>{
      const {app}=await import('/scripts/app.js');
      const core=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/moss_image_ui.mjs');
      const wi=await import('/extensions/core/widgetInputs.js');
      for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
      app.graph.clear();
      let node=LiteGraph.createNode(core.MOSS_ID);node.pos=[600,50];app.graph.add(node);
      const widget=name=>node.widgets.find(w=>w.name===name);
      widget('width').value=1256;widget('height').value=1672;
      const snapshot=()=>({size:[...node.size],minimum:[...node.computeSize()],inputs:node.inputs.map(i=>({name:i.name,label:i.label,localized_name:i.localized_name,link:i.link,widget:i.widget?.name})),
        widgets:node.widgets.filter(w=>['prompt','width','height','operation','api_mode'].includes(w.name)).map(w=>({name:w.name,type:w.type,hidden:w.hidden,connectionSuppressed:w.connectionSuppressed,size:w.computeSize?.(540),computedHeight:w.computedHeight,y:w.y,domHidden:w.element?.hidden,domDisplay:w.element?.style.display}))});
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      const before=snapshot();
      for(const [index,name] of ['prompt','width','height'].entries()){
        if(!node.inputs.some(i=>i.name===name))wi.convertToInput(node,widget(name));
        const source=LiteGraph.createNode(name==='prompt'?'T8PromptText':'PrimitiveNode');
        source.pos=[50,50+index*250];app.graph.add(source);
        if(name==='prompt')source.widgets[0].value='One ivory cup, no visible copy.';
        const slot=node.inputs.findIndex(i=>i.name===name);
        if(slot<0||!source.connect(0,node,slot))throw new Error('Cannot connect '+name);
      }
      core.refreshMoss(node);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      const connected=snapshot();
      const saved=node.serialize();
      if(saved.widgets_values.length!==27)throw new Error('Native save includes action tails');
      const output=await app.graphToPrompt();
      const request=Object.values(output.output).find(n=>n.class_type===core.MOSS_ID);
      if(!Array.isArray(request?.inputs.prompt)||![request?.inputs.width,request?.inputs.height].every(Number.isInteger))throw new Error('External inputs were lost in API prompt: '+JSON.stringify(request?.inputs));
      if(request.inputs.width!==1256||request.inputs.height!==1672)throw new Error('Eight-pixel canvas was rounded during native serialization');
      for(let i=0;i<50;i++){widget('operation').value=core.COMPILE;core.refreshMoss(node);widget('operation').value=core.GENERATE;core.refreshMoss(node);}
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      core.refreshMoss(node,true);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      const final=snapshot();
      const workflow=app.graph.serialize();
      await app.loadGraphData(workflow,false,true);
      node=app.graph._nodes.find(n=>n.comfyClass===core.MOSS_ID);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      const reloaded=snapshot();
      if(reloaded.size[1]>final.size[1]+1)throw new Error('Linked reload increased height');
      const after=await app.graphToPrompt();
      const afterInputs=Object.values(after.output).find(n=>n.class_type===core.MOSS_ID)?.inputs;
      if(!Array.isArray(afterInputs?.prompt)||afterInputs.width!==request.inputs.width||afterInputs.height!==request.inputs.height)throw new Error('Reload lost actual external values');
      const slot=node.inputs.findIndex(i=>i.name==='prompt');
      const promptLink=app.graph.links.get?.(node.inputs[slot].link)||app.graph.links[node.inputs[slot].link];
      const source=app.graph.getNodeById(promptLink.origin_id);
      node.disconnectInput(slot);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      core.refreshMoss(node,true);
      if(widget('prompt').hidden)throw new Error('Disconnect did not restore prompt editor');
      source.connect(0,node,slot);
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      core.refreshMoss(node,true);
      const reconnected=snapshot();
      if(!(widget('prompt').hidden||widget('prompt').connectionSuppressed)||reconnected.size[1]>final.size[1]+1)throw new Error('Reconnect expanded hidden prompt');
      if(app.canvas?.ds){app.canvas.ds.scale=.85;app.canvas.ds.offset[0]=80;app.canvas.ds.offset[1]=30;app.canvas.setDirty?.(true,true);}
      const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: real MOSS frontend external STRING/INT wiring and named serialization measured';document.body.append(p);
      return {before,connected,final,reloaded,reconnected,api_inputs:request.inputs,frontend_version:app.frontendVersion||null};
    })()` });
    if (check.exceptionDetails) throw new Error(JSON.stringify(check.exceptionDetails));
    process.stdout.write(JSON.stringify(check.result.value) + "\n");
    await send("Input.dispatchKeyEvent", {type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
    await send("Input.dispatchKeyEvent", {type:"keyUp",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
    await pause(200);
    // The welcome template browser can appear asynchronously on a clean profile.
    // Close only its observed header action, never alter graph data for the shot.
    const dialogs=await send("Runtime.evaluate",{returnByValue:true,expression:"Array.from(document.querySelectorAll('button')).filter(b=>b.getBoundingClientRect().x>1450&&b.getBoundingClientRect().x<1540&&b.getBoundingClientRect().y>140&&b.getBoundingClientRect().y<200).map(b=>({text:b.textContent,aria:b.getAttribute('aria-label'),class:b.className,html:b.outerHTML.slice(0,500)}))"});
    process.stdout.write(JSON.stringify({welcome_close_actions:dialogs.result?.value})+"\n");
  }
  if (mode === "comfy-strata") {
    const workflows = await Promise.all(["strata_h3_text", "strata_qwen_image_edit", "strata_h3_hybrid_video"].map(async stem=>
      JSON.parse(await readFile(resolve(import.meta.dirname,"../example_workflows/"+stem+".json"),"utf8"))));
    let ready=false;
    while(Date.now()<deadline && !ready) {
      const check=await send("Runtime.evaluate",{expression:"!!globalThis.LiteGraph?.registered_node_types?.T8LLMProviderConfig",returnByValue:true});
      ready=check.result?.value===true;if(!ready)await pause(200);
    }
    if(!ready)throw new Error("Real Comfy frontend did not register shared config");
    const check=await send("Runtime.evaluate",{awaitPromise:true,returnByValue:true,expression:`(async()=>{
      const {app}=await import('/scripts/app.js');
      const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/strata_ui.mjs');
      const config=LiteGraph.createNode('T8LLMProviderConfig');app.graph.add(config);
      const names=config.widgets.filter(w=>ui.CONFIG_NAMES.includes(w.name)).map(w=>w.name);
      if(JSON.stringify(names)!==JSON.stringify(ui.CONFIG_NAMES))throw new Error('Measured native widget order differs: '+JSON.stringify(names));
      config.widgets.find(w=>w.name==='provider').value='Strata';config.widgets.find(w=>w.name==='provider').callback?.('Strata');
      config.widgets.find(w=>w.name==='strata_url').value='http://127.0.0.1:8080';
      const saved=config.serialize();if(saved.widgets_values.length!==27)throw new Error('Config saved UI/key tail');
      const copy=LiteGraph.createNode('T8LLMProviderConfig');app.graph.add(copy);copy.configure(saved);
      if(copy.widgets.find(w=>w.name==='provider').value!=='Strata'||copy.widgets.find(w=>w.name==='strata_max_tokens').value!==0)throw new Error('Native new reload failed');
      const legacy={...saved,widgets_values:saved.widgets_values.slice(0,16),properties:{},widgets_values_named:undefined};legacy.widgets_values[0]='Local Qwen';
      copy.configure(legacy);if(copy.widgets.find(w=>w.name==='provider').value!=='Local Qwen'||copy.widgets.find(w=>w.name==='strata_url').value!=='http://127.0.0.1:8080')throw new Error('Native old reload failed');
      const main=LiteGraph.createNode('QwenImage21PromptEnhancerT8');app.graph.add(main);
      main.widgets.find(w=>w.name==='api_mode').value=ui.STRATA_API_MODE;main.widgets.find(w=>w.name==='api_mode').callback?.(ui.STRATA_API_MODE);
      const imageSave=main.serialize();const imageCopy=LiteGraph.createNode('QwenImage21PromptEnhancerT8');app.graph.add(imageCopy);imageCopy.configure(imageSave);
      if(imageCopy.widgets.find(w=>w.name==='api_mode').value!==ui.STRATA_API_MODE)throw new Error('Strata reset to cloud during main reload');
      const before=await fetch('/t8-prompt-enhancer/strata/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(ui.strataValues(config))}).then(r=>r.json());
      if(!before.connected||before.generation_requests!==0||!before.read_only)throw new Error('Read-only real route failed');
      const workflows=${JSON.stringify(workflows)};
      for(const workflow of workflows){
        await app.loadGraphData(workflow,false,true);
        const main=app.graph._nodes.find(n=>['MiniMaxH3PromptEnhancerT8','QwenImage21PromptEnhancerT8'].includes(n.comfyClass));
        if(!main||main.widgets.find(w=>w.name==='api_mode')?.value!==ui.STRATA_API_MODE)throw new Error('Shipped Strata workflow did not retain its mode: '+workflow.id);
        if(!Number.isFinite(main.size[1]))throw new Error('Workflow node size is invalid');
      }
      const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: real Comfy widget order, old/new config reload, Strata main reload and metadata-only probe';document.body.append(p);
      return {names,saved_count:saved.widgets_values.length,main_saved_count:imageSave.widgets_values.length,provider:before.provider,real_workflows:workflows.length};
    })()`});
    if(check.exceptionDetails)throw new Error(JSON.stringify(check.exceptionDetails));
    process.stdout.write(JSON.stringify(check.result.value)+"\n");
  }
  let result;
  while (Date.now() < deadline) {
    const evaluation = await send("Runtime.evaluate", {
      expression: "JSON.stringify({status:document.querySelector('#result')?.dataset.status || '',text:document.querySelector('#result')?.textContent || ''})",
      returnByValue: true,
    });
    if (evaluation.exceptionDetails) throw new Error("Browser status evaluation failed");
    result = JSON.parse(evaluation.result.value);
    if (result.status === "pass" || result.status === "fail") break;
    await pause(100);
  }
  if (!result || !["pass", "fail"].includes(result.status)) throw new Error(`Browser harness did not finish: ${result?.text || "no result"}`);
  if (result.status === "fail") throw new Error(result.text);
  if (screenshotPath) {
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    await writeFile(resolve(screenshotPath), Buffer.from(shot.data, "base64"));
    if(mode==='comfy-marker'){
      await send('Runtime.evaluate',{awaitPromise:true,expression:`(async()=>{const guide=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_visual_marker.js');guide.showMarkerGuide();await new Promise(done=>setTimeout(done,300));})()`});
      const guideShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await writeFile(resolve(screenshotPath.replace(/\.png$/,'-guide.png')),Buffer.from(guideShot.data,'base64'));
    }
  }
  process.stdout.write(result.text + "\n");
} catch (error) {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
} finally {
  socket?.close();
  chrome.kill();
  if (resolve(profile).startsWith(resolve(tmpdir(), "t8-browser-cdp-"))) {
    await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
  }
}
