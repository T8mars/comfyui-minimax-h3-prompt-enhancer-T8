import { readFile, writeFile } from 'node:fs/promises';

export async function runH3UILinkedReview({send, providerBase, screenshotPath}) {
    if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(providerBase)) throw Error('Owned loopback only');
    const wait=ms=>new Promise(done=>setTimeout(done,ms));
    await send('Emulation.setDeviceMetricsOverride',{width:1800,height:1350,deviceScaleFactor:1,mobile:false});
    let ready=false;
    for(let i=0;i<300;i++){
        const result=await send('Runtime.evaluate',{expression:"!!globalThis.LiteGraph?.registered_node_types?.MiniMaxH3ImagePromptEnhancerT8 && !document.getElementById('splash-loader')",returnByValue:true});
        if(result.result?.value){ready=true;break}await wait(200);
    }
    if(!ready)throw Error('H3 UI unavailable');
    const workflow=JSON.parse(await readFile(new URL('../example_workflows/h3_image_t2i_example.json',import.meta.url),'utf8'));
    const result=await send('Runtime.evaluate',{awaitPromise:true,returnByValue:true,timeout:150000,expression:`(async()=>{
        const {app}=await import('/scripts/app.js'),{api}=await import('/scripts/api.js');
        const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_image_ui.mjs');
        const assert=(ok,msg)=>{if(!ok)throw Error(msg)},wait=ms=>new Promise(done=>setTimeout(done,ms));
        const records=[],base=${JSON.stringify(providerBase)};
        const literal=String.fromCharCode(13,10)+'中文🙂 '+JSON.stringify({note:'literal {red|blue} // keep',url:'https://example.invalid/a?q=1'});
        const widget=(n,name)=>n.widgets.find(w=>w.name===name),set=(n,name,value)=>{const w=widget(n,name);assert(w,'missing '+name);w.value=value;if(w.inputEl)w.inputEl.value=value;w.callback?.(value)};
        const port=(n,name)=>n.inputs.findIndex(i=>i.name===name||i.widget?.name===name);
        const calls=async()=>await(await fetch(base+'/calls')).json();
        await app.loadGraphData(${JSON.stringify(workflow)},false,true);await wait(150);
        let main=app.graph._nodes.find(n=>n.comfyClass===ui.ID),show=app.graph._nodes.find(n=>n.comfyClass==='T8ShowText');
        set(main,'api_mode',ui.MODES[2]);set(main,'custom_model','fallback-model');set(main,'openai_base_url',base+'/v1');
        set(main,'prompt','UNCONNECTED_FALLBACK');set(main,'aspect_ratio','4:3');set(main,'target_words',77);set(main,'locked_text','');
        set(app.graph._nodes.find(n=>n.comfyClass==='T8PromptText'),'text','test-placeholder');
        const sources={};
        async function connectText(name,value){
            const source=LiteGraph.createNode('T8PromptText');app.graph.add(source);set(source,'text',value);
            if(port(main,name)<0){const wi=await import('/extensions/core/widgetInputs.js');wi.convertToInput(main,widget(main,name))}
            assert(source.connect(0,main,port(main,name)),'cannot connect '+name);sources[name]=source.id;
        }
        for(const [name,value] of Object.entries({prompt:'UI_LINKED_INPUT_AUDIT first'+literal,aspect_ratio:'16:9',locked_text:'外接标题'+String.fromCharCode(13,10)+'SECOND',custom_model:'linked-model-review',openai_base_url:base+'/v1'}))await connectText(name,value);
        for(const [name,value] of Object.entries({target_words:1750,llm_max_tokens:2048})){
            const source=LiteGraph.createNode('PrimitiveInt');app.graph.add(source);set(source,'value',value);
            if(port(main,name)<0){const wi=await import('/extensions/core/widgetInputs.js');wi.convertToInput(main,widget(main,name))}
            assert(source.connect(0,main,port(main,name)),'cannot connect '+name);sources[name]=source.id;
        }
        await wait(150);
        async function queue(label,expected){
            const before=(await calls()).length,exported=await app.graphToPrompt();
            const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});
            assert(response.ok,label+' validation '+await response.clone().text());const id=(await response.json()).prompt_id;let history;
            for(let i=0;i<300;i++){history=(await(await api.fetchApi('/history/'+id)).json())[id];if(history)break;await wait(50)}
            assert(history?.status?.status_str==='success',label+' runtime '+JSON.stringify(history?.status));
            const after=await calls();assert(after.length===before+1,label+' expected one new provider call');
            const payload=after.at(-1),text=payload.messages.map(m=>typeof m.content==='string'?m.content:JSON.stringify(m.content)).join(String.fromCharCode(10));
            assert(payload.model===expected.model,label+' wrong resolved model');
            assert(payload.max_tokens===expected.tokens,label+' wrong resolved tokens '+JSON.stringify({expected:expected.tokens,actual:payload.max_tokens}));
            assert(text.includes(expected.prompt),label+' linked prompt was not delivered');
            assert(text.includes('approximately '+expected.words+' English words'),label+' wrong resolved word target');
            const output=history.outputs[String(show.id)].text.join('');
            if(expected.lock)assert(output.includes(expected.lock),label+' lost locked text');
            records.push({label,passed:true,payload,output,workflow:exported.workflow});return history;
        }
        const expected={model:'linked-model-review',tokens:2048,prompt:'UI_LINKED_INPUT_AUDIT first'+literal,words:1750,lock:'外接标题'};
        await queue('external-STRING-INT-different-sentinels',expected);
        const saved=app.graph.serialize(),mainId=main.id,showId=show.id;
        assert(saved.nodes.find(n=>String(n.id)===String(mainId)).widgets_values.length===22,'linked save count');
        await app.loadGraphData(saved,false,true);await wait(150);main=app.graph.getNodeById(mainId);show=app.graph.getNodeById(showId);
        set(app.graph.getNodeById(sources.prompt),'text','UI_LINKED_INPUT_AUDIT reloaded');expected.prompt='UI_LINKED_INPUT_AUDIT reloaded';
        await queue('external-values-after-save-reload',expected);
        const metric=()=>({height:main.size[1],inputs:main.inputs.map((input,i)=>({name:input.name,link:input.link,y:main.getConnectionPos(true,i)[1]}))});
        main.t8H3ImageAdvanced=false;ui.refresh(main);await wait(120);const initial=metric();
        for(let i=0;i<10;i++){
            main.t8H3ImageAdvanced=true;ui.refresh(main);await wait(20);main.t8H3ImageAdvanced=false;ui.refresh(main);await wait(20);
        }
        await wait(120);const cycled=metric();
        assert(Math.abs(cycled.height-initial.height)<=1,'advanced cycle height drift '+JSON.stringify([initial,cycled]));
        assert(JSON.stringify(cycled.inputs)===JSON.stringify(initial.inputs),'advanced cycle socket position drift');
        records.push({label:'advanced-and-linked-socket-metrics',passed:true,initial,cycled});
        for(const name of Object.keys(sources)){main.disconnectInput(port(main,name))}await wait(150);
        for(const [name,value] of Object.entries({prompt:'UI_DISCONNECT_NORMAL_RUN',aspect_ratio:'4:3',target_words:123,locked_text:'断线后文案',custom_model:'disconnected-model',openai_base_url:base+'/v1',llm_max_tokens:3328}))set(main,name,value);
        await queue('disconnect-normal-generation',{model:'disconnected-model',tokens:3328,prompt:'UI_DISCONNECT_NORMAL_RUN',words:123,lock:'断线后文案'});
        for(const [name,id] of Object.entries(sources))assert(app.graph.getNodeById(id).connect(0,main,port(main,name)),'reconnect '+name);
        set(app.graph.getNodeById(sources.prompt),'text','UI_LINKED_INPUT_AUDIT reconnected');expected.prompt='UI_LINKED_INPUT_AUDIT reconnected';
        await wait(150);await queue('reconnected-normal-generation',expected);
        const nullRatio=app.graph.serialize(),nullMain=nullRatio.nodes.find(n=>String(n.id)===String(mainId));
        nullMain.widgets_values[ui.NAMES.indexOf('aspect_ratio')]=null;nullMain.widgets_values_named.aspect_ratio=null;nullMain.properties[ui.STATE].aspect_ratio=null;
        await app.loadGraphData(nullRatio,false,true);await wait(150);main=app.graph.getNodeById(mainId);show=app.graph.getNodeById(showId);
        main.disconnectInput(port(main,'aspect_ratio'));await wait(100);assert(widget(main,'aspect_ratio').value==='auto','linked-null ratio disconnect must restore auto');
        set(app.graph.getNodeById(sources.prompt),'text','UI_LINKED_INPUT_AUDIT ratio-default');expected.prompt='UI_LINKED_INPUT_AUDIT ratio-default';
        await queue('linked-null-ratio-disconnect-ordinary-run',expected);
        let store,service;
        for(const url of [...new Set(performance.getEntriesByType('resource').map(e=>e.name).filter(s=>new URL(s).pathname.startsWith('/assets/')&&s.endsWith('.js'))) ]){
            const module=await import(url),useStore=Object.values(module).find(v=>typeof v==='function'&&v.$id==='workflow'),useService=Object.values(module).find(v=>typeof v==='function'&&v.name==='useWorkflowService');
            if(useStore&&!store)store=useStore();if(useService&&!service)service=useService();if(store&&service)break;
        }
        assert(store&&service,'workflow Duplicate services unavailable');
        const stateA=app.graph.serialize();stateA.id=crypto.randomUUID();
        const workflowA=store.createTemporary('H3 recovery owner A.json',stateA);await service.openWorkflow(workflowA);await wait(120);
        main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);show=app.graph._nodes.find(n=>n.comfyClass==='T8ShowText');
        set(app.graph.getNodeById(sources.prompt),'text','UI_LINKED_INPUT_AUDIT OWNER_A');set(app.graph.getNodeById(sources.locked_text),'text','OWNER_A');
        await queue('workflow-A-generate',{...expected,prompt:'UI_LINKED_INPUT_AUDIT OWNER_A',lock:'OWNER_A'});
        const slotA=widget(main,'recovery_slot').value,rootA=app.rootGraph.id;
        await service.duplicateWorkflow(workflowA);await wait(120);const workflowB=store.activeWorkflow;
        main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);show=app.graph._nodes.find(n=>n.comfyClass==='T8ShowText');
        const slotB=widget(main,'recovery_slot').value,rootB=app.rootGraph.id;
        set(app.graph.getNodeById(sources.prompt),'text','UI_LINKED_INPUT_AUDIT OWNER_B');set(app.graph.getNodeById(sources.locked_text),'text','OWNER_B');
        await queue('workflow-B-generate',{...expected,prompt:'UI_LINKED_INPUT_AUDIT OWNER_B',lock:'OWNER_B'});
        await service.openWorkflow(workflowA);await wait(120);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);show=app.graph._nodes.find(n=>n.comfyClass==='T8ShowText');
        set(main,'recovery_action','restore_last');const prior=(await calls()).length,exported=await app.graphToPrompt();
        const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});
        assert(response.ok,'A restore validation');const promptId=(await response.json()).prompt_id;let history;
        for(let i=0;i<300;i++){history=(await(await api.fetchApi('/history/'+promptId)).json())[promptId];if(history)break;await wait(50)}
        assert(history?.status?.status_str==='success','A restore execution '+JSON.stringify(history?.status));
        const restored=history.outputs[String(show.id)].text.join('');
        const ownership={label:'actual-Duplicate-workflow-cache-isolation',rootA,rootB,slotA,slotB,restored,workflowA:workflowA.activeState.id,workflowB:workflowB.activeState.id};records.push(ownership);
        console.log('WORKFLOW_OWNER_EVIDENCE '+JSON.stringify(ownership));
        assert((await calls()).length===prior,'restore called provider');
        assert(restored.includes('OWNER_A')&&!restored.includes('OWNER_B'),'A restore returned another workflow result '+JSON.stringify(ownership));
        assert(slotA!==slotB,'Different workflow UUIDs share a recovery slot');set(main,'recovery_action','normal');
        app.canvas.ds.scale=.85;app.canvas.ds.offset=[20,20];app.canvas.setDirty(true,true);
        const result=document.createElement('pre');result.id='result';result.dataset.status='pass';result.textContent='PASS: H3 external inputs, disconnect/reconnect, widget/socket metrics and null-ratio ordinary Run';result.style.display='none';document.body.append(result);
        return records;
    })()`});
    if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
    if(screenshotPath)await writeFile(screenshotPath.replace(/\.png$/,'-browser.json'),JSON.stringify(result.result.value,null,2));
    console.log('H3 native UI linked-input lifecycle matrix passed.');
}
