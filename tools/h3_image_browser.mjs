import { readFile, writeFile } from "node:fs/promises";

export async function runH3ImageBrowser({ send, providerBase, screenshotPath }) {
    if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(providerBase)) throw Error("Owned loopback only");
    const wait = ms => new Promise(done => setTimeout(done, ms));
    await send("Emulation.setDeviceMetricsOverride", { width: 1800, height: 1350, deviceScaleFactor: 1, mobile: false });
    let ready = false;
    for (let i = 0; i < 300; i++) {
        const result = await send("Runtime.evaluate", { expression: "!!globalThis.LiteGraph?.registered_node_types?.MiniMaxH3ImagePromptEnhancerT8 && !document.getElementById('splash-loader')", returnByValue: true });
        if (result.result?.value) { ready = true; break; } await wait(200);
    }
    if (!ready) throw Error("Native H3 Image registration unavailable");
    const examples = await Promise.all(["t2i", "edit"].map(async name => ({ name, workflow: JSON.parse(await readFile(new URL(`../example_workflows/h3_image_${name}_example.json`, import.meta.url), "utf8")) })));
    const result = await send("Runtime.evaluate", { awaitPromise: true, returnByValue: true, timeout: 110000, expression: `(async()=>{
        const {app}=await import('/scripts/app.js'),{api}=await import('/scripts/api.js');
        const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/h3_image_ui.mjs');
        const assert=(v,label)=>{if(!v)throw Error(label)}, wait=ms=>new Promise(done=>setTimeout(done,ms));
        const set=(n,name,v)=>{const w=n.widgets.find(w=>w.name===name);assert(w,'missing '+name);w.value=v;if(w.inputEl)w.inputEl.value=v;w.callback?.(v)};
        const records=[];
        async function queue(label){
            const exported=await app.graphToPrompt();
            const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});
            assert(response.ok,label+' validation '+await response.clone().text());const id=(await response.json()).prompt_id;let history;
            for(let i=0;i<500;i++){history=(await(await api.fetchApi('/history/'+id)).json())[id];if(history)break;await wait(40)}
            assert(history?.status?.status_str==='success',label+' execution '+JSON.stringify(history?.status));
            records.push({label,prompt:exported.output,history});return history;
        }
        for(const item of ${JSON.stringify(examples)}){
            await app.loadGraphData(item.workflow,false,true);await wait(120);
            for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
            let main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);
            assert(main,'node missing');
            assert(JSON.stringify(main.widgets.filter(w=>ui.NAMES.includes(w.name)).map(w=>w.name))===JSON.stringify(ui.NAMES),'actual canonical runtime order');
            assert(!main.widgets.some(w=>w.name==='control_after_generate'),'unexpected seed control');
            assert(main.widgets.length===27,'full runtime widget count '+main.widgets.map(w=>w.name));
            for(const w of main.widgets.filter(w=>w.type==='button'))assert(w.serialize===false&&w.options.serialize===false,'button serialization');
            set(main,'api_mode',ui.MODES[2]);set(main,'openai_base_url',${JSON.stringify(providerBase)}+'/v1');set(main,'custom_model','model-test');
            const key=app.graph._nodes.find(n=>n.comfyClass==='T8PromptText');set(key,'text','test-not-real');
            const fallback=main.serialize();fallback.properties[ui.STATE]={broken:true};fallback.widgets_values_named.target_words=1500;
            main.configure(fallback);assert(main.widgets.find(w=>w.name==='target_words').value===1500,'corrupt private state blocked valid named fallback');
            if(item.name==='t2i'){
                const brief=main.widgets.find(w=>w.name==='prompt').value,lock=main.widgets.find(w=>w.name==='locked_text').value;
                set(main,'prompt','UNICODE_LOCK_AUDIT');set(main,'locked_text','  SALE  '+String.fromCharCode(0x2028)+'  SALE  ');
                const history=await queue('unicode-locked-lines');
                const shown=history.outputs['2']?.text?.join('')||JSON.stringify(history.outputs['2']);
                assert(shown.includes('  SALE  '),'unicode locked text lost spaces');
                set(main,'prompt',brief);set(main,'locked_text',lock);
            }
            for(const value of [0,1500,5000,20000]){
                set(main,'target_words',value);const saved=app.graph.serialize();const row=saved.nodes.find(n=>n.type===ui.ID);
                assert(row.widgets_values.length===22&&row.widgets_values_named.target_words===value,'saved target count');
                await app.loadGraphData(saved,false,true);await wait(60);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);
                assert(main.widgets.find(w=>w.name==='target_words').value===value,'target reload');
                assert((await app.graphToPrompt()).output[String(main.id)].inputs.target_words===value,'API target export');
            }
            main.t8H3ImageAdvanced=true;ui.refresh(main);await wait(100);ui.refresh(main);await wait(60);
            const height=main.size[1],heights=[height];for(let i=0;i<12;i++){ui.refresh(main);heights.push(main.size[1])}assert(height===main.size[1],'height drift '+JSON.stringify(heights));
            set(main,'target_words',5000);await queue(item.name+'-literal');
            if(item.name==='t2i'){
                const brief=LiteGraph.createNode('T8PromptText');app.graph.add(brief);set(brief,'text','Linked cup brief.');
                const number=LiteGraph.createNode('PrimitiveInt');assert(number,'PrimitiveInt missing');app.graph.add(number);set(number,'value',5000);
                const inputName=name=>main.inputs.findIndex(i=>i.name===name||i.widget?.name===name);
                brief.connect(0,main,inputName('prompt'));number.connect(0,main,inputName('target_words'));await wait(80);
                const linked=await app.graphToPrompt();assert(Array.isArray(linked.output[String(main.id)].inputs.target_words),'INT was not linked');
                await queue('linked-STRING-INT');const saved=app.graph.serialize();await app.loadGraphData(saved,false,true);await wait(80);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);await queue('linked-reloaded');
                main.disconnectInput(main.inputs.findIndex(i=>i.name==='prompt'));main.disconnectInput(main.inputs.findIndex(i=>i.name==='target_words'));await wait(70);
                set(main,'prompt','');set(main,'target_words',0);set(main,'custom_model','');set(main,'recovery_action','restore_last');
                await queue('restore-skips-current-invalid-inputs');set(main,'recovery_action','normal');
            }
            if(item.name==='edit'){
                const two=app.graph.serialize(),picture=app.graph._nodes.find(n=>n.comfyClass==='LoadImage');
                for(let i=2;i<16;i++){
                    const port=main.inputs.findIndex(input=>input.name==='reference_images.reference_image_'+i);
                    assert(port>=0,'autogrow missing '+i);picture.connect(0,main,port);await wait(25);
                }
                await queue('edit-sixteen-reference-sockets');
                await app.loadGraphData(app.graph.serialize(),false,true);await wait(80);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);
                assert(main.inputs.filter(i=>i.name.startsWith('reference_images.')&&i.link!=null).length===16,'16-image reload');
                await app.loadGraphData(two,false,true);await wait(80);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);
                const shared=LiteGraph.createNode('T8LLMProviderConfig');app.graph.add(shared);
                set(shared,'provider','OpenAI Compatible');set(shared,'openai_base_url',${JSON.stringify(providerBase)}+'/v1');set(shared,'custom_model','model-test');
                shared.connect(0,main,main.inputs.findIndex(i=>i.name==='provider_config'));set(main,'api_mode',ui.MODES[3]);await wait(80);
                assert(ui.effectiveMode(main)===ui.MODES[2],'shared provider not effective');await queue('edit-shared-provider');
                await app.loadGraphData(two,false,true);await wait(100);main=app.graph._nodes.find(n=>n.comfyClass===ui.ID);
                main.t8H3ImageAdvanced=false;ui.refresh(main);await wait(100);
                // Use the host queue so its workflow store owns websocket
                // outputs; a raw /prompt POST only proves backend execution.
                set(main,'seed',57);await app.queuePrompt(0,1);
                const preview=app.graph._nodes.find(n=>n.comfyClass==='T8ShowText');
                for(let i=0;i<200&&!preview.__t8TextPreview?.rawText;i++)await wait(50);
                assert(preview.__t8TextPreview?.rawText.includes('ivory'),'native Show Text preview empty');
                assert(!JSON.stringify(preview.serialize()).includes('An ivory background'),'preview was serialized');
                records.push({label:'host-queue-preview',passed:true});
            }
            records.push({label:item.name+'-canvas',serialized:main.serialize()});
        }
        app.canvas.ds.scale=0.78;app.canvas.ds.offset=[30,20];app.canvas.setDirty(true,true);
        const result=document.createElement('pre');result.id='result';result.dataset.status='pass';result.textContent='PASS: native H3 Image examples, widgets, linked inputs and recovery';result.style.display='none';document.body.append(result);
        return records;
    })()` });
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    // A clean-profile template welcome dialog can appear after node loading.
    // Click only its observed top-right close button in the fixed QA viewport.
    await send('Runtime.evaluate',{expression:"Array.from(document.querySelectorAll('button')).filter(b=>{const r=b.getBoundingClientRect();return r.x>1530&&r.x<1575&&r.y>145&&r.y<190}).forEach(b=>b.click())"});
    await wait(180);
    if (screenshotPath) {
        await writeFile(screenshotPath.replace(/\.png$/, "-browser.json"), JSON.stringify(result.result.value, null, 2));
        const shot = await send("Page.captureScreenshot", { format: "png" }); await writeFile(screenshotPath, Buffer.from(shot.data, "base64"));
    }
    console.log("H3 Image native Chrome: two examples, full runtime fields, saved/exported targets, linked STRING/INT, restore passed.");
}
