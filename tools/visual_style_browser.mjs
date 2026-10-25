// Native Comfy schemas/widgets, real extension dialogs and API-exported queues.
import {readFile, writeFile} from 'node:fs/promises';

export async function runVisualStyleBrowser({send, providerBase, screenshotPath}) {
    if (new URL(providerBase).hostname !== '127.0.0.1') throw Error('Owned loopback provider only');
    const wait = ms => new Promise(done => setTimeout(done, ms));
    await send('Emulation.setDeviceMetricsOverride', {width: 1800, height: 1350, deviceScaleFactor: 1, mobile: false});
    let ready = false;
    for (let i = 0; i < 300; i++) {
        const state = await send('Runtime.evaluate', {expression: "!!globalThis.LiteGraph?.registered_node_types?.T8CreatorStyleConfig && !document.getElementById('splash-loader')", returnByValue: true});
        if (state.result?.value) {ready = true; break;} await wait(200);
    }
    if (!ready) throw Error('Native style nodes unavailable');
    const names = ['visual_style_color_h3', 'visual_style_creator_seedance20', 'visual_style_combined_h3'];
    const workflows = await Promise.all(names.map(async name => ({name, workflow: JSON.parse(await readFile(new URL('../example_workflows/' + name + '.json', import.meta.url), 'utf8'))})));
    const result = await send('Runtime.evaluate', {awaitPromise: true, returnByValue: true, timeout: 90000, expression: `(async()=>{
        const {app}=await import('/scripts/app.js'),{api}=await import('/scripts/api.js');
        const ui=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/visual_style_config.js');
        const core=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/visual_style_ui.mjs');
        const assert=(ok,label)=>{if(!ok)throw Error(label)},wait=ms=>new Promise(done=>setTimeout(done,ms));
        const set=(n,key,v)=>{const w=n.widgets.find(w=>w.name===key);assert(w,'missing '+key);w.value=v;if(w.inputEl)w.inputEl.value=v;w.callback?.(v)};
        const until=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await wait(30)}throw Error('UI condition timeout '+JSON.stringify({nodes:app.graph._nodes.filter(n=>core.KINDS[n.comfyClass]).map(n=>({id:n.id,graphMatch:n.graph===app.graph,lookup:n.graph?.getNodeById(n.id)===n})),dialog:document.querySelector('dialog[open]')?.textContent?.slice(0,1400)}))};
        const output=[],examples=${JSON.stringify(workflows)};
        async function queue(label){
            const exported=await app.graphToPrompt();
            const response=await api.fetchApi('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:exported.output})});
            assert(response.ok,label+' graph rejected: '+await response.clone().text());
            const id=(await response.json()).prompt_id;let history;
            for(let i=0;i<300;i++){history=(await(await api.fetchApi('/history/'+id)).json())[id];if(history)break;await wait(50)}
            assert(history?.status?.status_str==='success',label+' failed '+JSON.stringify(history?.status));
            output.push({label,workflow:exported.workflow,prompt:exported.output,history});
        }
        for(const {name,workflow} of examples){
            await app.loadGraphData(workflow,false,true);await wait(80);
            for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
            let main=app.graph._nodes.find(n=>n.comfyClass?.endsWith('PromptEnhancerT8'));
            const mainSaved=main.serialize();assert(mainSaved.widgets_values.length===38,name+' main count');
            const helpers=()=>app.graph._nodes.filter(n=>core.KINDS[n.comfyClass]);
            for(const n of helpers()){
                const kind=core.KINDS[n.comfyClass],fields=core.fields(kind);
                assert(n.widgets.length===fields.length+1,name+' complete runtime widget count');
                assert(JSON.stringify(n.widgets.filter(w=>w.type!=='button').map(w=>w.name))===JSON.stringify(fields),name+' actual widget order');
                assert(n.widgets.at(-1).serialize===false&&n.widgets.at(-1).options.serialize===false,name+' action serialization');
                assert(n.serialize().widgets_values.length===fields.length,name+' saved helper count');
                assert(core.valueOf(n,'mode')===core.OFF,name+' default off');
            }
            const before=app.graph.serialize();await app.loadGraphData(before,false,true);await wait(60);
            main=app.graph._nodes.find(n=>n.comfyClass?.endsWith('PromptEnhancerT8'));
            assert(JSON.stringify(main.serialize().widgets_values)===JSON.stringify(mainSaved.widgets_values),name+' main reload drift');
            for(const n of helpers()){
                const kind=core.KINDS[n.comfyClass],key=kind==='color'?'palette':'creator';
                const old=before.nodes.find(v=>v.type===n.comfyClass);assert(old,'saved helper missing');assert(JSON.stringify(n.serialize().widgets_values)===JSON.stringify(old.widgets_values),name+' helper reload');
                const count=n.size[1];for(let i=0;i<15;i++){set(n,'mode',core.ON);set(n,'mode',core.OFF)}assert(n.size[1]===count,'size grows');
                n.widgets.at(-1).callback();await wait(100);
                const localCatalog=await(await api.fetchApi('/t8-prompt-enhancer/visual-styles/catalog')).json();assert(localCatalog.entries.length===200,'read-only catalog');
                await until(()=>document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]')?.options.length===200);
                const dialog=document.querySelector('dialog[open]'),search=dialog.querySelector('input'),list=dialog.querySelector('select[aria-label="风格列表 / Styles"]');
                search.value=kind==='color'?'001':'155';search.dispatchEvent(new Event('input',{bubbles:true}));assert(list.options.length===1,'ID search');
                list.value=kind==='color'?'001':'155';list.dispatchEvent(new Event('change',{bubbles:true}));
                const apply=[...dialog.querySelectorAll('button')].find(b=>b.textContent.includes('Apply selection'));
                await until(()=>!apply.disabled);
                assert(dialog.textContent.includes(kind==='color'?'#1A2332':'Limited source specificity'),'actual preview contents');
                const illustrated=dialog.querySelector('.t8-style-illustration');
                assert(illustrated?.querySelectorAll('svg').length===2,'two actual vector scenes');
                assert(illustrated.textContent.includes('NOT A MODEL OUTPUT')&&illustrated.textContent.includes('not tested'),'illustration provenance labels');
                const configBefore=JSON.stringify(n.serialize().widgets_values);
                if(kind==='color'){
                    const light=illustrated.querySelector('button');light.click();
                    assert(light.getAttribute('aria-pressed')==='true','local light demonstration');
                    const scene=illustrated.querySelector('select');scene.value='street';scene.dispatchEvent(new Event('change',{bubbles:true}));
                    assert(illustrated.querySelectorAll('svg').length===2,'street scene');
                }else{
                    const slider=illustrated.querySelector('input[type=range]');slider.value='80';slider.dispatchEvent(new Event('input',{bubbles:true}));
                    assert(illustrated.querySelector('[data-diagram]').dataset.progress==='80','relative slider');
                    const play=[...illustrated.querySelectorAll('button')].find(b=>b.textContent.includes('Play'));play.click();
                    await wait(180);assert(illustrated.querySelector('[data-diagram]').dataset.progress!=='80','real animation advances');play.click();
                    const stopped=illustrated.querySelector('[data-diagram]').dataset.progress;await wait(100);
                    assert(illustrated.querySelector('[data-diagram]').dataset.progress===stopped,'pause holds');
                    illustrated.querySelectorAll('button')[1].click();
                    assert(illustrated.querySelector('[data-diagram]').dataset.diagram==='handheld','second reviewed method');
                }
                assert(JSON.stringify(n.serialize().widgets_values)===configBefore,'preview controls cannot serialize');
                apply.click();assert(!document.querySelector('dialog[open]'),'apply closes');
                assert(core.valueOf(n,key).startsWith(kind==='color'?'001 ':'155 '),'selection applies');
                assert(core.valueOf(n,'mode')===core.OFF,'apply does not silently enable');
                const socket=main.inputs.findIndex(v=>v.name===kind+'_style_config');assert(socket>=0,'typed socket missing');
                main.disconnectInput(socket);n.connect(0,main,socket);assert(main.inputs[socket].link!=null,'reconnect');
            }
            // Use only our synthetic provider, never a configured user key or server.
            const provider=LiteGraph.createNode('T8LLMProviderConfig');app.graph.add(provider);set(provider,'provider','Strata');set(provider,'strata_url',${JSON.stringify(providerBase)});
            provider.connect(0,main,main.inputs.findIndex(v=>v.name==='provider_config'));
            set(main,'prompt',(name.includes('seedance20')?'QUEUE_SD':'QUEUE_H3')+': keep red sleeve and ticket; continue walking.');
            set(main,'output_language','English');set(main,'seed',20);
            await queue(name+'-off');for(const n of helpers())set(n,'mode',core.ON);await queue(name+'-on');
            const saved=app.graph.serialize();await app.loadGraphData(saved,false,true);await wait(50);
            for(const n of helpers()){assert(core.valueOf(n,'mode')===core.ON,'on selection reload');assert(n.widgets.length===core.fields(core.KINDS[n.comfyClass]).length+1,'no duplicate actions')}
        }
        // Dialog callbacks cannot apply to a replacement workflow/node with the same local ID.
        const owner=app.graph._nodes.find(n=>core.KINDS[n.comfyClass]),kind=core.KINDS[owner.comfyClass];
        ui.openStyleBrowser(owner,kind);await wait(60);await app.loadGraphData(examples[0].workflow,false,true);await wait(50);
        assert(!document.querySelector('dialog[open]'),'workflow switch leaves stale dialog');
        const n=app.graph._nodes.find(n=>core.KINDS[n.comfyClass]);
        ui.openStyleBrowser(n,'color');await until(()=>document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]')?.options.length===200);
        const select=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');
        const nativeFetch=api.fetchApi,arrivals=[];
        api.fetchApi=async function(path,...args){const response=await nativeFetch.call(this,path,...args);if(path.endsWith('/color/002'))await wait(450);if(path.includes('/color/'))arrivals.push(path);return response;};
        try{
            select.value='002';select.dispatchEvent(new Event('change',{bubbles:true}));select.value='001';select.dispatchEvent(new Event('change',{bubbles:true}));
            await until(()=>document.querySelector('dialog[open] h4')?.textContent.startsWith('001 '));
            await wait(600);assert(arrivals[0]?.endsWith('/001')&&arrivals[1]?.endsWith('/002'),'forced reverse completion');
            assert(document.querySelector('dialog[open] h4').textContent.startsWith('001 '),'stale response won');
        }finally{api.fetchApi=nativeFetch;}
        [...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent==='关闭 / Close').click();
        // Native subgraph edits its own helper only. Same-ID legacy graphs are
        // separately covered in the pure ownership contract; this host may remap IDs.
        const child=LiteGraph.createNode('T8ColorStyleConfig');app.graph.add(child);app.graph.convertToSubgraph(new Set([child]));
        const container=app.graph._nodes.find(v=>v.subgraph),sub=container.subgraph,subNode=sub._nodes.find(v=>v.comfyClass==='T8ColorStyleConfig');
        assert(subNode,'native subgraph helper');app.canvas.setGraph(sub);
        const rootValue=core.valueOf(n,'palette');
        ui.openStyleBrowser(subNode,'color');await until(()=>document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]')?.options.length===200);
        const subList=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');subList.value='002';subList.dispatchEvent(new Event('change',{bubbles:true}));
        const subApply=[...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent.includes('Apply selection'));await until(()=>!subApply.disabled);subApply.click();
        assert(core.valueOf(subNode,'palette').startsWith('002 ')&&core.valueOf(n,'palette')===rootValue,'subgraph selection isolation');
        app.canvas.setGraph(app.rootGraph);
        // Deleting a pending owner, then creating a replacement, cannot mutate it.
        const doomed=LiteGraph.createNode('T8ColorStyleConfig');app.graph.add(doomed);
        ui.openStyleBrowser(doomed,'color');app.graph.remove(doomed);
        const replacement=LiteGraph.createNode('T8ColorStyleConfig');replacement.id=doomed.id;app.graph.add(replacement);await wait(100);
        assert(!document.querySelector('dialog[open]')&&core.valueOf(replacement,'palette')===core.NONE,'removed node stale response');
        for(const close of document.querySelectorAll('.p-dialog-close-button,.p-dialog-header-close,[data-pc-section="closebutton"]'))close.click();
        ui.openStyleBrowser(n,'color');await until(()=>document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]')?.options.length===200);
        const lastList=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');lastList.value='001';lastList.dispatchEvent(new Event('change',{bubbles:true}));
        await until(()=>document.querySelector('dialog[open] h4')?.textContent.startsWith('001 '));
        globalThis.__visualStyleEvidence=output;
        const p=document.createElement('pre');p.id='result';p.dataset.status='pass';p.textContent='PASS: native 4/3 widgets, 38-field reload, local preview/search, reconnect, stale-dialog isolation and 6 native-exported queues';document.body.append(p);
        return {examples:examples.length,queues:output.length,evidence:output};
    })()`});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    const evaluate = async expression => {
        const checked = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
        if (checked.exceptionDetails) throw Error(JSON.stringify(checked.exceptionDetails));
        return checked.result.value;
    };
    const pointerClick = async selector => {
        const point = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('pointer target missing');
            el.scrollIntoView({block:'nearest'});const r=el.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2;
            if(document.elementFromPoint(x,y)!==el)throw Error('pointer target obscured');return {x,y};})()`);
        await send('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
        await send('Input.dispatchMouseEvent', {type: 'mousePressed', ...point, button: 'left', clickCount: 1});
        await send('Input.dispatchMouseEvent', {type: 'mouseReleased', ...point, button: 'left', clickCount: 1});
    };
    const capture = async suffix => {
        if (!screenshotPath) return;
        const shot = await send('Page.captureScreenshot', {format: 'png'});
        await writeFile(screenshotPath.replace(/\.png$/, '-' + suffix + '.png'), Buffer.from(shot.data, 'base64'));
    };
    await pointerClick('dialog[open] .t8-style-preview-controls button');
    if (!await evaluate(`document.querySelector('dialog[open] .t8-style-preview-controls button').getAttribute('aria-pressed')==='true'`)) throw Error('native pointer light click failed');
    await pointerClick('dialog[open] .t8-style-preview-controls button');
    await capture('color');
    await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js'),{openStyleBrowser}=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/visual_style_config.js');
        [...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent==='关闭 / Close').click();
        const n=LiteGraph.createNode('T8CreatorStyleConfig');app.graph.add(n);openStyleBrowser(n,'creator');
        const wait=ms=>new Promise(done=>setTimeout(done,ms));
        for(let i=0;i<100;i++){const list=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');
            if(list?.options.length===200){list.value='155';list.dispatchEvent(new Event('change',{bubbles:true}));break;}await wait(30);}
        for(let i=0;i<100;i++){if(document.querySelector('[data-diagram="push"]'))return true;await wait(30);}throw Error('creator illustration timeout');
    })()`);
    await pointerClick('dialog[open] .t8-style-preview-controls button:nth-child(3)');
    await wait(220);
    if (!await evaluate(`document.querySelector('[data-diagram]').dataset.progress!=='50' && document.querySelector('.t8-style-preview-controls button:nth-child(3)').textContent.includes('Pause')`)) throw Error('native pointer play failed');
    await pointerClick('dialog[open] .t8-style-preview-controls button:nth-child(3)');
    await capture('creator-motion');
    await evaluate(`(async()=>{const list=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');
        list.value='181';list.dispatchEvent(new Event('change',{bubbles:true}));
        for(let i=0;i<100;i++){if(document.querySelector('[data-diagram="low"]'))return;await new Promise(done=>setTimeout(done,30));}throw Error('low viewpoint timeout');})()`);
    if (!await evaluate(`document.querySelector('.t8-style-preview-controls button:nth-child(3)').disabled&&document.querySelector('.t8-style-preview-controls input').disabled`)) throw Error('static composition exposes meaningless playback');
    await capture('creator-low');
    await pointerClick('dialog[open] .t8-style-preview-controls button:nth-child(2)');
    if (!await evaluate(`document.querySelector('[data-diagram]').dataset.diagram==='negative'`)) throw Error('native pointer method failed');
    await capture('creator-negative');
    const layouts = [];
    for (const width of [600, 360]) {
        await send('Emulation.setDeviceMetricsOverride', {width, height: 1000, deviceScaleFactor: 1, mobile: false});
        await wait(80);
        layouts.push(await evaluate(`(()=>{const d=document.querySelector('dialog[open]'),r=d.getBoundingClientRect();
            if(d.scrollWidth>d.clientWidth+1||r.left<0||r.right>innerWidth+1)throw Error('horizontal overflow at '+innerWidth+': '+JSON.stringify({scroll:d.scrollWidth,client:d.clientWidth,left:r.left,right:r.right}));
            d.querySelector('.t8-style-illustration').scrollIntoView({block:'start'});return {width:innerWidth,dialogWidth:r.width,noOverflow:true};})()`));
        await capture('narrow-' + width);
    }
    await send('Emulation.setDeviceMetricsOverride', {width: 1800, height: 1350, deviceScaleFactor: 1, mobile: false});
    await evaluate(`document.querySelector('dialog[open]').scrollTop=0`);
    await evaluate(`(async()=>{const list=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');
        list.value='155';list.dispatchEvent(new Event('change',{bubbles:true}));
        for(let i=0;i<100;i++){if(document.querySelector('[data-diagram="push"]'))return;await new Promise(done=>setTimeout(done,30));}throw Error('motion switch timeout');})()`);
    await pointerClick('dialog[open] .t8-style-preview-controls button:nth-child(3)');
    await wait(100);
    await evaluate(`(()=>{globalThis.__closedStylePreview=document.querySelector('.t8-style-illustration');
        [...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent==='关闭 / Close').click();
        globalThis.__closedStyleProgress=__closedStylePreview.querySelector('[data-diagram]').dataset.progress;})()`);
    await wait(180);
    if (!await evaluate(`!document.querySelector('dialog[open]')&&__closedStylePreview.querySelector('[data-diagram]').dataset.progress===__closedStyleProgress`)) throw Error('closed preview animation continued');
    // Leave a fresh paused creator example for the harness's final screenshot.
    await evaluate(`(async()=>{const {app}=await import('/scripts/app.js'),{openStyleBrowser}=await import('/extensions/comfyui-minimax-h3-prompt-enhancer-T8/visual_style_config.js');
        const n=app.graph._nodes.find(n=>n.comfyClass==='T8CreatorStyleConfig');openStyleBrowser(n,'creator');
        const wait=ms=>new Promise(done=>setTimeout(done,ms));for(let i=0;i<100;i++){
            const list=document.querySelector('dialog[open] select[aria-label="风格列表 / Styles"]');if(list?.options.length===200){list.value='022';list.dispatchEvent(new Event('change',{bubbles:true}));break;}await wait(30);}
        for(let i=0;i<100;i++){if(document.querySelector('[data-diagram="reflection"]'))return;await wait(30);}throw Error('final preview timeout');})()`);
    result.result.value.visualPreview = {nativePointer: true, closeStopsPlayback: true, layouts};
    if (screenshotPath) await writeFile(screenshotPath.replace(/\.png$/, '-native-exports.json'), JSON.stringify(result.result.value, null, 2));
    process.stdout.write(JSON.stringify({examples: result.result.value.examples, queues: result.result.value.queues}) + '\n');
}
