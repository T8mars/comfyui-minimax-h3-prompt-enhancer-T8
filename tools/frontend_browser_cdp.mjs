// Wait for the real asynchronous browser harness to finish instead of trusting
// Chromium's --dump-dom timing under a virtual-time budget.
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const [browser, url, screenshotPath = "", mode = "harness"] = process.argv.slice(2);
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
