import {writeFile} from 'node:fs/promises';

export async function runH3LocalPicker({send,providerBase,screenshotPath}){
    const wait=ms=>new Promise(done=>setTimeout(done,ms));
    const evaluate=async expression=>{
        const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
        if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
        return result.result.value;
    };
    await send('Emulation.setDeviceMetricsOverride',{width:1800,height:1400,deviceScaleFactor:1,mobile:false});
    let ready=false;
    for(let i=0;i<300;i++){
        if(await evaluate("!!globalThis.LiteGraph?.registered_node_types?.MiniMaxH3ImagePromptEnhancerT8 && !document.getElementById('splash-loader')")){ready=true;break}
        await wait(200);
    }
    if(!ready)throw Error('Native node unavailable');
    await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js');const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_image_ui.mjs');
        await app.loadGraphData({nodes:[],links:[],groups:[],config:{},extra:{},version:.4},false,true);
        const n=LiteGraph.createNode(ui.ID);n.pos=[300,60];app.graph.add(n);n.setSize([650,n.size[1]]);
        app.canvas.ds.scale=1;app.canvas.ds.offset=[50,80];app.canvas.setDirty(true,true);
        globalThis.__localPicker={app,ui,n};return true;
    })()`);
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await wait(350);
    await evaluate("Array.from(document.querySelectorAll('button')).filter(b=>{const r=b.getBoundingClientRect();return r.x>1530&&r.x<1575&&r.y>145&&r.y<215}).forEach(b=>b.click())");
    const click=async point=>{
        await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:point.x,y:point.y});
        await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:point.x,y:point.y});
        await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:point.x,y:point.y});
    };
    async function openWidget(name){
        await wait(180);
        const point=await evaluate(`(()=>{const {app,n}=__localPicker,w=n.widgets.find(w=>w.name===${JSON.stringify(name)}),r=app.canvas.canvas.getBoundingClientRect();if(!w||w.hidden)throw Error('hidden '+${JSON.stringify(name)});const y=w.last_y??w.y;if(!Number.isFinite(y))throw Error('no widget Y '+${JSON.stringify(name)});return {x:r.x+(n.pos[0]+app.canvas.ds.offset[0]+n.size[0]*.65)*app.canvas.ds.scale,y:r.y+(n.pos[1]+app.canvas.ds.offset[1]+y+10)*app.canvas.ds.scale}})()`);
        await click(point);await wait(150);
    }
    async function selectOption(label){
        const entries=await evaluate("Array.from(document.querySelectorAll('.litemenu-entry,[role=option],[role=menuitem]')).filter(e=>e.getBoundingClientRect().width>0).map(e=>{const r=e.getBoundingClientRect();return {text:e.textContent.trim(),x:r.x+r.width/2,y:r.y+r.height/2}})");
        const item=entries.find(e=>e.text===label);
        if(!item)throw Error('Dropdown option not available: '+label+' '+JSON.stringify(entries));
        await click(item);await wait(180);
    }
    await openWidget('api_mode');await selectOption('本地 GGUF（llama.cpp / Qwen，离线）');
    const fresh=await evaluate("(()=>{const {n,ui}=__localPicker;return {mode:n.widgets.find(w=>w.name==='api_mode').value,effective:ui.effectiveMode(n),installed:!!n.t8H3ImageInstalled,advanced:!!n.t8H3ImageAdvanced,promptLinked:n.inputs.some(i=>i.name==='prompt'&&i.link!=null),models:n.widgets.find(w=>w.name==='local_model').options.values,modelVisible:!n.widgets.find(w=>w.name==='local_model').hidden,projectorVisible:!n.widgets.find(w=>w.name==='local_mmproj').hidden,layout:n.t8H3ImageLayout}})()");
    if(fresh.advanced||fresh.promptLinked||!fresh.modelVisible||!fresh.projectorVisible)throw Error('Fresh Local picker hidden '+JSON.stringify(fresh));
    const target=fresh.models.find(name=>name==='Qwen_Qwen3.5-9B-Q8_0.gguf')||fresh.models.find(name=>name.endsWith('.gguf'));
    if(!target)throw Error('No installed model in picker');
    await openWidget('local_model');await selectOption(target);
    const result=await evaluate(`(async()=>{
        const {app,ui}=__localPicker;let n=__localPicker.n;const assert=(v,m)=>{if(!v)throw Error(m)},wait=ms=>new Promise(r=>setTimeout(r,ms));
        const chosen=${JSON.stringify(target)};assert(n.widgets.find(w=>w.name==='local_model').value===chosen,'mouse selection failed');
        const saved=app.graph.serialize();assert(saved.nodes.find(v=>v.type===ui.ID).widgets_values.length===22,'saved values shifted');
        await app.loadGraphData(saved,false,true);await wait(150);n=app.graph._nodes.find(v=>v.comfyClass===ui.ID);__localPicker.n=n;
        assert(!n.t8H3ImageAdvanced&&!n.widgets.find(w=>w.name==='local_model').hidden,'reload hid local model');
        assert(n.widgets.find(w=>w.name==='local_model').value===chosen,'model selection lost on reload');
        const source=LiteGraph.createNode('T8PromptText');app.graph.add(source);source.widgets.find(w=>w.name==='text').value='Local picker connection lifecycle';
        const p=n.inputs.findIndex(i=>i.name==='prompt');source.connect(0,n,p);await wait(120);
        assert(!n.widgets.find(w=>w.name==='local_model').hidden,'prompt connection hides model');n.disconnectInput(p);await wait(120);
        assert(!n.widgets.find(w=>w.name==='local_model').hidden,'prompt disconnection hides model');
        const set=(name,value)=>{const w=n.widgets.find(w=>w.name===name);w.value=value;if(w.inputEl)w.inputEl.value=value;w.callback?.(value)};
        set('api_mode',ui.MODES[2]);set('custom_model','model-test');set('openai_base_url',${JSON.stringify(providerBase)}+'/v1');set('prompt','Dimension queue');
        const key=LiteGraph.createNode('T8PromptText');app.graph.add(key);key.widgets.find(w=>w.name==='text').value='test-placeholder';key.connect(0,n,n.inputs.findIndex(i=>i.name==='api_key'));
        for(const [name,value] of [['width',1920],['height',1080]]){const v=LiteGraph.createNode('PrimitiveInt');app.graph.add(v);v.widgets.find(w=>w.name==='value').value=value;assert(v.connect(0,n,n.inputs.findIndex(i=>i.name===name)),'dimension input missing '+name)}
        const show=LiteGraph.createNode('T8ShowText');app.graph.add(show);n.connect(1,show,0);
        await wait(120);assert(n.widgets.find(w=>w.name==='aspect_ratio').hidden,'manual ratio must yield to connected dimensions');
        await app.loadGraphData(app.graph.serialize(),false,true);await wait(150);n=app.graph._nodes.find(v=>v.comfyClass===ui.ID);__localPicker.n=n;
        assert(n.inputs.find(i=>i.name==='width').link!=null&&n.inputs.find(i=>i.name==='height').link!=null,'dimension links lost on reload');
        const exported=await app.graphToPrompt();assert(exported.output[n.id].inputs.local_model===chosen,'API export changed model');
        const response=await fetch('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});assert(response.ok,'size queue validation '+await response.clone().text());
        const id=(await response.json()).prompt_id;let history;for(let i=0;i<300;i++){history=(await(await fetch('/history/'+id)).json())[id];if(history)break;await wait(50)}
        assert(history?.status.status_str==='success','size queue '+JSON.stringify(history?.status));assert(history.outputs[show.id].text[0]==='16:9','width/height did not compute ratio');
        set('api_mode',ui.MODES[3]);await wait(120);assert(!n.widgets.find(w=>w.name==='local_model').hidden,'switch back hid model');
        for(const v of [...app.graph._nodes])if(v!==n)app.graph.remove(v);await wait(150);n.pos=[300,60];app.canvas.ds.scale=1;app.canvas.ds.offset=[50,80];app.canvas.setDirty(true,true);
        const result=document.createElement('pre');result.id='result';result.dataset.status='pass';result.style.display='none';result.textContent='PASS: mouse-selected local GGUF without prompt/Advanced, reload/reconnect, queued width/height ratio';document.body.append(result);
        return {selected:chosen,fresh:true,reload:true,promptConnectDisconnect:true,dimensionQueue:'1920x1080 -> 16:9',savedWidgets:n.serialize().widgets_values.length,providerRequests:1};
    })()`);
    if(screenshotPath)await writeFile(screenshotPath.replace(/\.png$/,'-picker.json'),JSON.stringify({fresh,result},null,2));
    console.log(JSON.stringify(result));
}
