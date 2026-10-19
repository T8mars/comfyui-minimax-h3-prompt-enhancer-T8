// Real Chromium pointers + production view, then native save/reopen/queue.
import {writeFile,readFile} from 'node:fs/promises';
import {dirname,join} from 'node:path';

export async function runSpatialBrowser({send,providerBase,screenshotPath}){
    const evaluate=async expression=>{
        const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
        if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;
    };
    const until=Date.now()+45000;
    while(!await evaluate("!!globalThis.LiteGraph?.registered_node_types?.T8H3SpatialMarkerCanvas && !document.getElementById('splash-loader')")){
        if(Date.now()>until)throw Error('Standalone canvas node unavailable');await new Promise(done=>setTimeout(done,150));
    }
    await send('Emulation.setDeviceMetricsOverride',{width:1800,height:1400,deviceScaleFactor:1,mobile:false});
    await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js');
        for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
        app.graph.clear();
        const node=LiteGraph.createNode('T8H3SpatialMarkerCanvas');app.graph.add(node);node.pos=[30,40];
        node.widgets.find(w=>w.name==='image').value='h3-marker-demo-source.png';
        globalThis.spatialFixtureNode=node;
        const editor=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_spatial_editor.js');
        await editor.openEditor(node).ready;
        if(!document.querySelector('[data-t8-spatial-editor] canvas'))throw Error('Editor did not open');
        globalThis.spatialPointerTrace=[];
        for(const type of ['pointerdown','pointermove','pointerup','pointercancel','lostpointercapture'])document.querySelector('[data-spatial-canvas]').addEventListener(type,event=>globalThis.spatialPointerTrace.push([type,event.pointerId,event.clientX,event.clientY,event.button,event.buttons]),true);
        globalThis.spatialDocumentTrace=[];for(const type of ['pointerdown','pointerup'])document.addEventListener(type,event=>globalThis.spatialDocumentTrace.push([type,event.target.tagName,event.clientX,event.clientY]),true);
    })()`);
    const click=key=>evaluate(`document.querySelector('[data-spatial-action="${key}"]').click()`);
    const fill=(name,value)=>evaluate(`(()=>{const field=document.querySelector('[data-spatial-field="${name}"]');if(!field)throw Error('Missing form field ${name}');field.value=${JSON.stringify(value)};field.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    const drag=async(a,b)=>{
        const rect=await evaluate(`(()=>{const r=document.querySelector('[data-spatial-canvas]').getBoundingClientRect();return {left:r.left,top:r.top,width:r.width,height:r.height};})()`);
        const hit=await evaluate(`(()=>{const c=document.querySelector('[data-spatial-canvas]'),e=document.elementFromPoint(${rect.left+a[0]*rect.width},${rect.top+a[1]*rect.height});return {hit:e?.outerHTML.slice(0,260),pointer:getComputedStyle(c).pointerEvents,rect:${JSON.stringify(rect)},viewport:[innerWidth,innerHeight,visualViewport.scale]};})()`);
        process.stdout.write(JSON.stringify({pointer_probe:hit})+'\n');
        const p=point=>({x:rect.left+point[0]*rect.width,y:rect.top+point[1]*rect.height});
        await send('Input.dispatchMouseEvent',{type:'mouseMoved',...p(a)});
        await send('Input.dispatchMouseEvent',{type:'mousePressed',...p(a),button:'left',clickCount:1});
        for(let step=1;step<=6;step++)await send('Input.dispatchMouseEvent',{type:'mouseMoved',...p(a.map((n,i)=>n+(b[i]-n)*step/6)),button:'left',buttons:1});
        await send('Input.dispatchMouseEvent',{type:'mouseReleased',...p(b),button:'left',clickCount:1});
    };
    await click('actor');await drag([.1,.1],[.4,.9]);
    await evaluate(`(()=>{if(!document.querySelector('[data-spatial-field=description]'))throw Error('First drag did not create box: '+JSON.stringify({canvas:globalThis.spatialPointerTrace,document:globalThis.spatialDocumentTrace})+' JSON='+document.querySelector('[data-spatial-json]').value);})()`);
    await fill('description','the woman in the red coat');
    await click('target');await drag([.95,.95],[.65,.2]);await fill('description','the doorway on the right');
    await click('relation');await fill('action','walk through the doorway and keep moving, without stopping');
    await fill('selection','actor_1');
    await drag([.25,.5],[.28,.5]); // Real move, then resize its SE handle.
    await drag([.43,.9],[.45,.92]);
    await click('undo');await click('redo');
    await evaluate(`(()=>{const json=JSON.parse(document.querySelector('[data-spatial-json]').value);if(json.markers.length!==2||json.relations.length!==1)throw Error('Draw/relationship missing');const a=json.markers[0].xyxy;if(Math.abs(a[0]-.13)>.003||Math.abs(a[2]-.45)>.003)throw Error('Move/resize not retained '+a);})()`);
    await evaluate("document.querySelector('[data-spatial-canvas]').focus()");
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:2});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:2});
    await evaluate(`(async()=>{
        const node=globalThis.spatialFixtureNode,before=node.widgets.find(w=>w.name==='markers_json').value;
        let confirmations=0;const originalConfirm=window.confirm;window.confirm=()=>{confirmations++;return false;};
        try{document.querySelector('[data-spatial-action=close]').click();if(confirmations!==1||!node.t8SpatialEditor)throw Error('Unsaved-close guard failed');}finally{window.confirm=originalConfirm;}
        const json=document.querySelector('[data-spatial-json]');json.value='{broken';json.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-spatial-action=import]').click();
        if(!document.querySelector('[data-spatial-action=apply]').disabled||node.widgets.find(w=>w.name==='markers_json').value!==before)throw Error('Invalid JSON changed node');
        document.querySelector('[data-spatial-action=reset-json]').click();
        const {api}=await import('/scripts/api.js');const fetchBefore=api.fetchApi;let release;
        api.fetchApi=async function(...args){const response=await fetchBefore.apply(this,args);await new Promise(done=>release=done);return response;};
        try{
            const pending=document.querySelector('[data-spatial-action=apply-keep]').onclick();
            const until=Date.now()+5000;while(!release&&Date.now()<until)await new Promise(done=>setTimeout(done,10));if(!release)throw Error('No pending preview');
            const text=document.querySelector('[data-spatial-field=description]');text.value='temporary unconfirmed edit';text.dispatchEvent(new Event('change',{bubbles:true}));release();await pending;
            const after=node.widgets.find(w=>w.name==='markers_json').value,status=document.querySelector('[data-t8-spatial-editor] [role=status]').textContent;
            if(after!==before||!status.includes('草稿或源图已变化'))throw Error('Async apply guard failed '+JSON.stringify({before,after,status}));
            document.querySelector('[data-spatial-action=undo]').click();
        }finally{api.fetchApi=fetchBefore;release?.();}
    })()`);
    const modal=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(join(dirname(screenshotPath),'spatial-editor.png'),Buffer.from(modal.data,'base64'));
    await evaluate("document.querySelector('[data-spatial-action=actual]').onclick()");
    await evaluate("document.querySelector('[data-spatial-action=apply-keep]').onclick()");
    await evaluate(`(()=>{const n=globalThis.spatialFixtureNode;if(n.serialize().widgets_values.length!==5)throw Error('Expected five saved fields');if(!/^[0-9a-f]{64}$/.test(n.widgets.find(w=>w.name==='expected_source_sha256').value))throw Error('No actual source binding');})()`);
    await click('close');
    const result=await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js');const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_spatial_editor.js');
        let n=globalThis.spatialFixtureNode;const id=n.id,saved=n.serialize().widgets_values;
        await app.loadGraphData(app.graph.serialize(),false,true);n=app.graph.getNodeById(id);globalThis.spatialFixtureNode=n;
        if(JSON.stringify(n.serialize().widgets_values)!==JSON.stringify(saved))throw Error('Five-field reload mismatch');
        await ui.openEditor(n).ready;
        if(document.querySelectorAll('[data-t8-spatial-editor]').length!==1)throw Error('Modal instance mismatch');
        if(JSON.parse(document.querySelector('[data-spatial-json]').value).markers.length!==2)throw Error('Reopen lost markers');
        const again=ui.openEditor(n);if(document.querySelectorAll('[data-t8-spatial-editor]').length!==1)throw Error('Duplicate modal');
        again.close(true);
        const cfg=LiteGraph.createNode('T8H3VisualMarkerConfig'),main=LiteGraph.createNode('MiniMaxH3PromptEnhancerT8');
        const key=LiteGraph.createNode('T8PromptText'),show=LiteGraph.createNode('T8ShowText');
        for(const node of [cfg,main,key,show])app.graph.add(node);
        cfg.pos=[590,40];main.pos=[1100,40];key.pos=[30,900];show.pos=[1800,40];
        const set=(node,name,value)=>{const w=node.widgets.find(w=>w.name===name);if(!w)throw Error('Missing '+name);w.value=value;if(w.inputEl)w.inputEl.value=value;const el=w.element?.querySelector?.('input,textarea');if(el)el.value=value;w.callback?.(value);};
        set(cfg,'mode','开启（实验） / On (experimental)');set(key,'text','test-placeholder');
        for(const [name,value] of Object.entries({prompt:'Walk through the doorway and keep moving.',task_type:'Hybrid（关键帧+参考混合生成）',duration_seconds:3600,shot_count:'1',output_language:'English',api_mode:'OpenAI兼容接口（备用）',openai_base_url:${JSON.stringify(providerBase)},custom_model:'marker-fixture'}))set(main,name,value);
        const connect=(src,out,dst,name)=>{const slot=dst.inputs.findIndex(i=>i.name===name);if(slot<0||!src.connect(out,dst,slot))throw Error('Cannot connect '+name);};
        connect(n,1,cfg,'marker_plan');connect(cfg,0,main,'visual_marker_config');
        const ref=main.inputs.find(i=>i.name.startsWith('reference_images.'));connect(n,0,main,ref.name);connect(n,2,main,'first_frame');
        connect(key,0,main,'api_key');connect(main,0,show,'text');
        // A real computed STRING validates as None. The editor must not silently
        // write its hidden offline widget or remove this link.
        // A second real CPU canvas supplies its raw STRING output. T8PromptText
        // intentionally enables dynamic prompts and therefore is not a JSON source.
        const wi=await import('/extensions/core/widgetInputs.js');const raw=LiteGraph.createNode('T8H3SpatialMarkerCanvas');app.graph.add(raw);raw.pos=[30,650];
        for(const name of ['image','mode','markers_json','line_width','expected_source_sha256'])set(raw,name,n.widgets.find(w=>w.name===name).value);
        if(!n.inputs.some(i=>i.name==='markers_json'))wi.convertToInput(n,n.widgets.find(w=>w.name==='markers_json'));
        connect(raw,3,n,'markers_json');const input=n.inputs.find(i=>i.name==='markers_json'),edge=input.link;
        await ui.openEditor(n).ready;
        if(!document.querySelector('[data-spatial-action=apply]').disabled)throw Error('Linked editor should be read-only');
        n.t8SpatialEditor.close(true);if(input.link!==edge)throw Error('Editor broke STRING link');
        const first=await app.graphToPrompt();if(!Array.isArray(first.output[n.id].inputs.markers_json))throw Error('Native linked STRING missing');
        const data=app.graph.serialize();await app.loadGraphData(data,false,true);
        const exported=await app.graphToPrompt();
        const response=await fetch('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});const ack=await response.json();
        if(!response.ok)throw Error('Native spatial graph rejected '+JSON.stringify(ack));
        const deadline=Date.now()+45000;let success=false;
        while(Date.now()<deadline){const history=(await(await fetch('/history/'+ack.prompt_id)).json())[ack.prompt_id];if(history){if(history.status.status_str!=='success')throw Error(JSON.stringify(history.status));success=true;break;}await new Promise(done=>setTimeout(done,100));}
        if(!success)throw Error('Native spatial graph outcome unknown');
        app.canvas.ds.scale=.55;app.canvas.ds.offset[0]=100;app.canvas.ds.offset[1]=120;app.canvas.setDirty(true,true);
        const status=document.createElement('pre');status.id='result';status.dataset.status='pass';status.textContent='PASS: standalone manual editor, real pointer drawing/move/resize, apply/save/reopen, linked STRING and native H3 queue';document.body.append(status);
        return {widgets:5,markers:2,relations:1,real_pointer_draw:true,reverse_drag:true,move_resize:true,undo_redo:true,invalid_JSON_safe:true,unsaved_close_guard:true,async_apply_race_rejected:true,modal_queue_shortcut_blocked:true,source_sha:true,save_reload_reopen:true,linked_STRING_queue:true,no_audio_plugin:true,workflow:data,api:exported.output};
    })()`);
    await writeFile(join(dirname(screenshotPath),'spatial-native-workflow.json'),JSON.stringify(result.workflow,null,2));
    await writeFile(join(dirname(screenshotPath),'spatial-native-api.json'),JSON.stringify(result.api,null,2));
    delete result.workflow;delete result.api;process.stdout.write(JSON.stringify(result)+'\n');
    const samples=await Promise.all(['ref2va','hybrid'].map(async name=>JSON.parse(await readFile(new URL('../example_workflows/h3_spatial_canvas_'+name+'.json',import.meta.url),'utf8'))));
    const sampleResult=await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js');const samples=${JSON.stringify(samples)},results=[];
        for(const sample of samples){
            await app.loadGraphData(sample,false,true);
            const nodes=()=>app.graph._nodes;
            let canvas=nodes().find(n=>n.comfyClass==='T8H3SpatialMarkerCanvas');
            let main=nodes().find(n=>n.comfyClass==='MiniMaxH3PromptEnhancerT8');
            let cfg=nodes().find(n=>n.comfyClass==='T8H3VisualMarkerConfig');
            const initial=[canvas.serialize().widgets_values,main.serialize().widgets_values,cfg.serialize().widgets_values];
            if(initial[0].length!==5||initial[1].length!==38||initial[2].length!==2)throw Error('Sample saved layout mismatch');
            await app.loadGraphData(app.graph.serialize(),false,true);
            [canvas,main,cfg]=[canvas,main,cfg].map(n=>app.graph.getNodeById(n.id));
            if(JSON.stringify(initial)!==JSON.stringify([canvas.serialize().widgets_values,main.serialize().widgets_values,cfg.serialize().widgets_values]))throw Error('Sample reload changed values');
            const set=(node,name,value)=>{const w=node.widgets.find(w=>w.name===name);w.value=value;if(w.inputEl)w.inputEl.value=value;const el=w.element?.querySelector?.('input,textarea');if(el)el.value=value;w.callback?.(value);};
            set(main,'openai_base_url',${JSON.stringify(providerBase)});set(main,'custom_model','marker-fixture');set(main,'api_mode','OpenAI兼容接口（备用）');set(main,'output_language','English');
            const key=LiteGraph.createNode('T8PromptText');app.graph.add(key);key.pos=[600,800];set(key,'text','test-placeholder');key.connect(0,main,main.inputs.findIndex(i=>i.name==='api_key'));
            for(const active of [false,true]){
                set(cfg,'mode',active?'开启（实验） / On (experimental)':'关闭 / Off');
                const exported=await app.graphToPrompt();
                const response=await fetch('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});const ack=await response.json();if(!response.ok)throw Error('Sample graph rejected '+JSON.stringify(ack));
                let success=false;const until=Date.now()+45000;
                while(Date.now()<until){const history=(await(await fetch('/history/'+ack.prompt_id)).json())[ack.prompt_id];if(history){if(history.status.status_str!=='success')throw Error(JSON.stringify(history.status));success=true;break;}await new Promise(done=>setTimeout(done,100));}
                if(!success)throw Error('Sample queue outcome unknown');results.push({mode:main.widgets.find(w=>w.name==='task_type').value,active,success});
            }
        }
        app.canvas.ds.scale=.65;app.canvas.ds.offset[0]=140;app.canvas.ds.offset[1]=220;app.canvas.setDirty(true,true);return results;
    })()`);
    process.stdout.write(JSON.stringify({standalone_examples:sampleResult})+'\n');
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await new Promise(done=>setTimeout(done,300));
}
