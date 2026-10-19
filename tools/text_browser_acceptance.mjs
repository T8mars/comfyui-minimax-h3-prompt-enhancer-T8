// Native workflow/change-tracker/output hooks, not a second preview implementation.
export async function runTextBrowser({send}) {
    const pause = ms => new Promise(done => setTimeout(done, ms));
    let ready = false;
    for (let n = 0; n < 250 && !ready; n++) {
        const r = await send('Runtime.evaluate', {expression:"!!globalThis.LiteGraph?.registered_node_types?.T8ShowText && !document.getElementById('splash-loader')",returnByValue:true});
        ready = r.result?.value === true; if (!ready) await pause(200);
    }
    if (!ready) throw new Error('Native T8ShowText unavailable');
    await send('Emulation.setDeviceMetricsOverride', {width:1500,height:1000,deviceScaleFactor:1,mobile:false});
    // Dismiss the host's first-run template dialog in this disposable profile.
    await send('Input.dispatchKeyEvent', {type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent', {type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await pause(200);
    const r = await send('Runtime.evaluate', {awaitPromise:true,returnByValue:true,expression:`(async()=>{
        const {app}=await import('/scripts/app.js');
        const assert=(ok,why)=>{if(!ok)throw new Error(why)};
        const wait=ms=>new Promise(done=>setTimeout(done,ms));
        const ext=app.extensions.find(e=>e.name==='T8.TextUtilities');
        assert(ext?.onNodeOutputsUpdated,'Actual production restoration hook');
        // Discover the installed host's internal service only in this test.
        // The production extension imports no hashed/private host modules.
        let store,service;
        for(const url of performance.getEntriesByType('resource').map(e=>e.name).filter(s=>new URL(s).pathname.startsWith('/assets/settingStore-')&&s.endsWith('.js'))){
            const mod=await import(url);
            const useStore=Object.values(mod).find(v=>typeof v==='function'&&v.$id==='workflow');
            const useService=Object.values(mod).find(v=>typeof v==='function'&&v.name==='useWorkflowService');
            if(useStore&&useService){store=useStore();service=useService();break;}
        }
        assert(store&&service,'Native workflow store/service discovery');
        await app.loadGraphData({nodes:[],links:[],groups:[],config:{},extra:{},version:.4},false,true);
        const input=LiteGraph.createNode('T8PromptText'),show=LiteGraph.createNode('T8ShowText');
        app.graph.add(input);app.graph.add(show);input.pos=[30,70];show.pos=[650,70];show.setSize([650,600]);
        input.widgets.find(w=>w.name==='text').value='A actual queue\\n中文 result';
        assert(input.connect(0,show,0),'Native STRING link');
        const workflow=app.graph.serialize(),showId=show.id;
        const a=store.createTemporary('T8 preview A.json',workflow),b=store.createTemporary('T8 preview B.json',{...structuredClone(workflow),id:crypto.randomUUID()});
        await service.openWorkflow(a);
        const get=()=>app.rootGraph.getNodeById(showId);
        const graph=await app.graphToPrompt();
        assert(!graph.output[showId].inputs.t8_show_text_preview,'Preview absent from native API');
        await app.queuePrompt(0,1); // actual WebSocket onExecuted, tracked native job
        const until=Date.now()+15000;
        while(get().__t8TextPreview.rawText!=='A actual queue\\n中文 result'&&Date.now()<until)await wait(100);
        assert(get().__t8TextPreview.rawText==='A actual queue\\n中文 result','Real execution preview');
        const restore=ext.onNodeOutputsUpdated;
        try{
            ext.onNodeOutputsUpdated=undefined;
            await service.openWorkflow(b);await service.openWorkflow(a);
            assert(get().__t8TextPreview.rawText==='','Missing restore hook reproduces reported blank');
            assert(app.nodeOutputs[showId]?.text?.[0]==='A actual queue\\n中文 result','Host still retains the original output');
        }finally{ext.onNodeOutputsUpdated=restore;}
        restore(app.nodeOutputs);
        await service.openWorkflow(b);
        assert(get().__t8TextPreview.rawText==='','New workflow same node ID has no A output');
        get().onExecuted({text:['B only']});
        app.nodeOutputs={[showId]:{text:['B only']}};
        await service.openWorkflow(a);
        assert(get().__t8TextPreview.rawText==='A actual queue\\n中文 result','A restored through native workflow switch');
        await service.openWorkflow(b);assert(get().__t8TextPreview.rawText==='B only','B restores its own output');
        await service.openWorkflow(a);assert(get().__t8TextPreview.rawText==='A actual queue\\n中文 result','Repeated switch');
        const saved=app.graph.serialize(),serialized=saved.nodes.find(n=>String(n.id)===String(showId));
        assert(serialized,'Serialized Show Text node');
        assert((serialized.widgets_values||[]).every(v=>v==null),'No preview saved in widgets_values');
        assert(!JSON.stringify(serialized).includes('A actual queue'),'No result stashed in properties or widget metadata');
        assert(get().widgets.filter(w=>w.name==='t8_show_text_preview').length===1,'One preview after reload');
        const full=JSON.parse(JSON.stringify(app.nodeOutputs));await app.loadGraphData(saved,false,true);app.nodeOutputs=full;
        assert(get().__t8TextPreview.rawText==='A actual queue\\n中文 result','History-style graph plus host output restore');
        // Use the actual native subgraph class/registry and switch the active canvas.
        const child=LiteGraph.createNode('T8ShowText');app.graph.add(child);
        app.graph.convertToSubgraph(new Set([child]));
        const container=app.graph._nodes.find(n=>n.subgraph);
        const sub=container.subgraph,subShow=sub._nodes.find(n=>n.type==='T8ShowText');
        assert(subShow,'Native subgraph preview node');
        app.canvas.setGraph(sub);
        app.nodeOutputs={[showId]:{text:['root only']},[sub.id+':'+subShow.id]:{text:['sub only']}};
        assert(get().__t8TextPreview.rawText==='root only','Root restored while subgraph is open');
        assert(subShow.__t8TextPreview.rawText==='sub only','UUID scoped subgraph restored');
        app.nodeOutputs={};assert(get().__t8TextPreview.rawText===''&&subShow.__t8TextPreview.rawText==='','Empty snapshot clears old previews');
        app.canvas.setGraph(app.rootGraph);
        const state=get().__t8TextPreview,raw='line 1\\r\\n中文 line 2\\r\\n<script>literal</script>';
        get().onExecuted({text:[raw]});assert(state.textarea.value===raw.replaceAll('\\r\\n','\\n'),'Browser textarea normalization reproduced');
        globalThis.__t8TextCopyFixture={state,raw,get};
        return {missing_hook_reproduced:true,native_queue:true,native_workflow_switch:true,history_restore:true,subgraph_scope:true,preview_serialized:false,paid_calls:0};
    })()`});
    if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));
    process.stdout.write(JSON.stringify(r.result.value)+'\n');
    // A fresh browser user gesture is essential for legacy execCommand. Do not
    // confuse a gesture-less test script with failure of a real copy click.
    const copyResult = await send('Runtime.evaluate', {userGesture:true,awaitPromise:true,returnByValue:true,expression:`(async()=>{
        const {app}=await import('/scripts/app.js');
        const {state,raw,get}=globalThis.__t8TextCopyFixture;
        const assert=(ok,why)=>{if(!ok)throw new Error(why)};
        const wait=ms=>new Promise(done=>setTimeout(done,ms));
        const clipboard=Object.getOwnPropertyDescriptor(navigator,'clipboard');
        let copied,copyEvents=0;
        const observe=event=>{copied=event.clipboardData.getData('text/plain');copyEvents++;};
        document.addEventListener('copy',observe);
        try{
            // Real DOM + native execCommand, with the modern API missing/denied.
            for(const value of [undefined,{writeText:async()=>{throw new DOMException('Denied','NotAllowedError')}}]){
                Object.defineProperty(navigator,'clipboard',{configurable:true,value});
                state.copy.click();for(let n=0;n<50&&state.copy.disabled;n++)await wait(20);
                assert(copied===raw&&state.copy.textContent==='已复制','Fallback copies exact raw CRLF: '+JSON.stringify({copied,raw,label:state.copy.textContent,copyEvents,active:navigator.userActivation.isActive}));
            }
            let count=0;
            Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{copied=text;count++;await wait(60)}}});
            state.copy.click();state.copy.click();state.copy.click();await wait(90);
            assert(count===1&&copied===raw,'Pending clicks coalesced, modern API receives raw result');
            state.copy.click();await wait(90);assert(count===2,'Second completed copy allowed');
            await wait(1600);assert(state.copy.textContent==='复制显示内容','Rapid-copy feedback resets to fixed label');
            // Failure is visible and does not leave success or a disabled button.
            const exec=document.execCommand;document.execCommand=()=>false;
            Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined});
            try{state.copy.click();await wait(30);assert(state.copy.textContent.includes('复制失败')&&!state.copy.disabled,'Both paths failed safely');}
            finally{document.execCommand=exec;}
            get().onExecuted({text:[raw]});
        }finally{
            document.removeEventListener('copy',observe);
            if(clipboard)Object.defineProperty(navigator,'clipboard',clipboard);else delete navigator.clipboard;
        }
        assert(copyEvents===2,'Exactly two actual fallback copy events');
        app.canvas.ds.scale=.85;app.canvas.ds.offset=[10,10];app.graph.setDirtyCanvas(true,true);
        const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: real queue, native A/B workflow switching, history restoration, subgraph scope, raw CRLF fallback and rapid copy';document.body.append(p);
        delete globalThis.__t8TextCopyFixture;
        return {raw_CRLF:true,actual_fallback_copy_events:copyEvents,rapid_copy:true,paid_calls:0};
    })()`});
    if(copyResult.exceptionDetails)throw new Error(JSON.stringify(copyResult.exceptionDetails));
    process.stdout.write(JSON.stringify(copyResult.result.value)+'\n');
}
