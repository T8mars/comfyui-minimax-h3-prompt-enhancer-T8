// Actual native Comfy widget persistence/exports and owned loopback queues.
import { readdir, readFile } from 'node:fs/promises';

export async function runAuthoringBrowser({send,providerBase}) {
  if(new URL(providerBase).hostname!=='127.0.0.1')throw new Error('Owned loopback only');
  const pause=ms=>new Promise(done=>setTimeout(done,ms));
  await send('Emulation.setDeviceMetricsOverride',{width:1900,height:1450,deviceScaleFactor:1,mobile:false});
  const until=Date.now()+60000;
  let ready=false;
  while(Date.now()<until&&!ready){
    const state=await send('Runtime.evaluate',{expression:"!!globalThis.LiteGraph?.registered_node_types?.MOSSAuthoringDirectorT8 && !document.getElementById('splash-loader')",returnByValue:true});
    ready=state.result?.value===true;if(!ready)await pause(200);
  }
  if(!ready)throw new Error('Native Director unavailable');
  const directory=new URL('../example_workflows/',import.meta.url);
  const names=(await readdir(directory)).filter(name=>/^moss_authoring_.*\.json$/.test(name)
    || /^moss_(caption|layout|spatial|compile_only|compile_error)_example\.json$/.test(name)).sort();
  const examples=await Promise.all(names.map(async name=>({name,workflow:JSON.parse(await readFile(new URL(name,directory),'utf8'))})));
  const result=await send('Runtime.evaluate',{awaitPromise:true,returnByValue:true,timeout:90000,expression:`(async()=>{
    const {app}=await import('/scripts/app.js');
    const {api}=await import('/scripts/api.js');
    const core=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/moss_authoring_ui.mjs');
    const main=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/moss_image_ui.mjs');
    const assert=(ok,label)=>{if(!ok)throw new Error(label)};
    window.alert=text=>{throw new Error('Unexpected native alert: '+text)};
    const wait=ms=>new Promise(done=>setTimeout(done,ms));
    const set=(node,name,value)=>{const w=node.widgets.find(w=>w.name===name);assert(w,'missing '+name);w.value=value;if(w.inputEl)w.inputEl.value=value;w.callback?.(value)};
    const observations=[];
    const queueCurrent=async label=>{
      const graph=await app.graphToPrompt();
      const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:graph.output})});
      assert(response.ok,label+' native export static rejection '+await response.clone().text());
      const id=(await response.json()).prompt_id;
      let history;
      for(let i=0;i<200;i++){history=(await(await api.fetchApi('/history/'+id)).json())[id];if(history)break;await wait(100)}
      assert(history?.status?.status_str==='success',label+' native queue failed '+JSON.stringify(history?.status));
      return history;
    };
    for(const {name,workflow} of ${JSON.stringify(examples)}){
      await app.loadGraphData(workflow,false,true);
      await wait(40);
      const before=app.graph.serialize();
      const stable=before.nodes.filter(n=>[core.DIRECTOR_ID,main.MOSS_ID,'MOSSAuthoringPageT8'].includes(n.type));
      assert(stable.length>0,'example has no own nodes '+name);
      for(const node of stable){
        const count=node.type===core.DIRECTOR_ID?17:node.type===main.MOSS_ID?28:3;
        assert(node.widgets_values?.length===count,name+' saved count '+node.type);
        if(node.type===main.MOSS_ID&&!name.startsWith('moss_authoring_'))assert(node.widgets_values[27]===main.CLASSIC,name+' old default not Classic');
      }
      await app.loadGraphData(before,false,true);
      const after=app.graph.serialize();
      for(const expected of stable){
        const actual=after.nodes.find(n=>String(n.id)===String(expected.id));
        assert(JSON.stringify(actual.widgets_values)===JSON.stringify(expected.widgets_values),name+' values shifted after reload');
      }
      const exported=await app.graphToPrompt();
      for(const node of Object.values(exported.output))if(node.class_type==='MOSSAuthoringPageT8')assert(node.inputs.language==='en'||node.inputs.language==='zh',name+' Page language shifted');
      if(name.startsWith('moss_authoring_')){
        for(const node of app.graph._nodes.filter(n=>n.comfyClass==='T8LLMProviderConfig')){
          set(node,'provider','Strata');set(node,'strata_url',${JSON.stringify(providerBase)});
        }
        await queueCurrent(name);
      }
      observations.push({name,native_reload:true,api_export:true,native_queue:name.startsWith('moss_authoring_')});
    }
    app.graph.clear();
    app.nodeOutputs={};
    let director=LiteGraph.createNode(core.DIRECTOR_ID);director.pos=[50,30];app.graph.add(director);
    const nativeNames=director.widgets.filter(w=>w.type!=='button').map(w=>w.name);
    assert(JSON.stringify(nativeNames)===JSON.stringify(core.DIRECTOR_NAMES),'actual Director widget order differs '+JSON.stringify(nativeNames));
    set(director,'brief','简短版，两页同一个人物在窗边伸手。');set(director,'width',1256);set(director,'height',1672);set(director,'page_count',2);set(director,'max_corrections',0);
    const config=LiteGraph.createNode('T8LLMProviderConfig');config.pos=[-600,30];app.graph.add(config);
    set(config,'provider','Strata');set(config,'strata_url',${JSON.stringify(providerBase)});
    const cfgSlot=director.inputs.findIndex(i=>i.name==='provider_config');assert(cfgSlot>=0&&config.connect(0,director,cfgSlot),'config wiring failed');
    const source=LiteGraph.createNode('T8PromptText');source.pos=[-600,450];app.graph.add(source);source.widgets[0].value='简短版，两页同一个人物在窗边伸手。';
    const briefSlot=director.inputs.findIndex(i=>i.name==='brief');assert(briefSlot>=0&&source.connect(0,director,briefSlot),'brief wiring failed');
    let page=LiteGraph.createNode('MOSSAuthoringPageT8');page.pos=[750,30];app.graph.add(page);set(page,'language','zh');set(page,'page_index',2);
    assert(director.connect(0,page,0),'bundle wiring failed');
    const show=LiteGraph.createNode('T8ShowText');show.pos=[1200,30];app.graph.add(show);assert(page.connect(0,show,0),'positive wiring failed');
    const showBundle=LiteGraph.createNode('T8ShowText');showBundle.pos=[1200,650];app.graph.add(showBundle);director.connect(0,showBundle,0);
    const before=app.graph.serialize();const nodeSave=before.nodes.find(n=>n.type===core.DIRECTOR_ID);
    assert(nodeSave.widgets_values.length===17,'actions leaked into 17 fields');
    assert(!Object.hasOwn(nodeSave.properties||{},'t8_moss_authoring_result'),'preview result serialized');
    await app.loadGraphData(before,false,true);await wait(100);
    director=app.graph._nodes.find(n=>n.comfyClass===core.DIRECTOR_ID);page=app.graph._nodes.find(n=>n.comfyClass==='MOSSAuthoringPageT8');
    assert(JSON.stringify(director.serialize().widgets_values)===JSON.stringify(nodeSave.widgets_values),'native 17-field reload shifted');
    const cfg=app.graph._nodes.find(n=>n.comfyClass==='T8LLMProviderConfig');
    director.disconnectInput(cfgSlot);assert(cfg.connect(0,director,cfgSlot),'config reconnect failed');
    const exported=await app.graphToPrompt();
    const req=Object.values(exported.output).find(n=>n.class_type===core.DIRECTOR_ID);
    assert(req.inputs.width===1256&&req.inputs.height===1672&&req.inputs.page_count===2,'native API widgets shifted');
    assert(Array.isArray(req.inputs.brief)&&Array.isArray(req.inputs.provider_config),'native lazy links lost');
    const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});
    assert(response.ok,'browser-exported graph rejected '+await response.clone().text());
    const id=(await response.json()).prompt_id;
    let history;
    for(let i=0;i<180;i++){history=(await (await api.fetchApi('/history/'+id)).json())[id];if(history)break;await wait(150)}
    assert(history?.status?.status_str==='success','browser-exported graph queue failed '+JSON.stringify(history?.status));
    const positive=history.outputs[String(show.id)]?.text?.[0];assert(positive?.includes('安静'),'selected Chinese page missing');
    const bundle=JSON.parse(history.outputs[String(showBundle.id)].text[0]);assert(bundle.units.length===2&&bundle.report.logical_generation_calls===5,'browser Comic count mismatch');
    assert(!JSON.stringify(director.serialize().widgets_values).includes('A calm page.'),'execution result inserted into saved widgets');
    // Real route + native restoration button, intercept only scheduling to
    // observe the generated request without sending any new model request.
    const originalQueue=app.queuePrompt;const queued=[];
    app.queuePrompt=async(...args)=>{queued.push({args,action:director.widgets.find(w=>w.name==='recovery_action').value,prompt:(await app.graphToPrompt()).output});};
    try{await director.widgets.find(w=>/Restore/.test(w.name)).callback()}finally{app.queuePrompt=originalQueue}
    assert(queued.length===1&&queued[0].action==='restore_last','restore did not request cached action');
    assert(director.widgets.find(w=>w.name==='recovery_action').value==='normal','restore action stuck');
    const restoreInputs=Object.values(queued[0].prompt).find(n=>n.class_type===core.DIRECTOR_ID).inputs;
    assert(restoreInputs.recovery_action==='restore_last','hidden cached action not exported');
    // Queue the actual cached native export too; post count is checked by the
    // Python owner. Provider need not remain valid for this read-only path.
    const cached=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:queued[0].prompt})});
    assert(cached.ok,'native recovery export rejected');
    const cacheId=(await cached.json()).prompt_id;
    let cachedHistory;
    for(let i=0;i<120;i++){cachedHistory=(await(await api.fetchApi('/history/'+cacheId)).json())[cacheId];if(cachedHistory)break;await wait(100)}
    assert(cachedHistory?.status?.status_str==='success','native recovery queue failed');
    assert(cachedHistory.outputs[String(show.id)].text[0]===positive,'recovered page changed');
    const failedPrompt=structuredClone(exported.output);
    const failedInputs=Object.values(failedPrompt).find(n=>n.class_type===core.DIRECTOR_ID).inputs;
    failedInputs.brief='FAIL_TRANSLATION 简短版，两页人物。';failedInputs.seed=99;
    const failed=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:failedPrompt})});
    assert(failed.ok,'native failed-draft graph rejected statically');
    const failedId=(await failed.json()).prompt_id;
    let failedHistory;
    for(let i=0;i<120;i++){failedHistory=(await(await api.fetchApi('/history/'+failedId)).json())[failedId];if(failedHistory)break;await wait(100)}
    assert(failedHistory?.status?.status_str==='error','malformed translation did not block native downstream');
    await director.widgets.find(w=>/Inspect failed draft/.test(w.name)).callback();
    const dialog=Array.from(document.querySelectorAll('dialog')).find(d=>d.textContent.includes('inspection_only'));
    assert(dialog&&dialog.querySelector('pre')?.textContent.includes('"complete": false'),'real failed inspection route did not render read-only');
    assert(!dialog.querySelector('script,img,iframe'),'inspection interprets HTML');dialog.close();
    const help=director.widgets.find(w=>/Help/.test(w.name));help.callback();
    const helpDialog=Array.from(document.querySelectorAll('dialog')).find(d=>d.textContent.includes('1+2N'));
    assert(helpDialog,'Director help missing');helpDialog.close();
    // Keep the generated native graph visible; no output persistence is added.
    app.canvas.ds.scale=.85;app.canvas.ds.offset=[100,100];app.canvas.setDirty(true,true);
    for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
    const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: 17/3 native fields, all MOSS examples reload, computed API links, Comic queue, cached restore and read-only inspection';document.body.append(p);
    return {examples:observations,native_widget_names:nativeNames,source_calls:5,recovery_calls:0,failed_stage_calls:3,real_comfy:true};
  })()`});
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
  process.stdout.write(JSON.stringify(result.result.value)+'\n');
  await pause(600);
  for(let i=0;i<2;i++){
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await pause(200);
  }
}
