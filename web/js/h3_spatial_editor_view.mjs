import {History,readSpec,problems,appendBox,changeBox,deleteBox,colorHex,validBox,handles,
    pointerPoint,dragBox,hitBox,moveBox,fieldValue,linkedFields,applyDraft} from './h3_spatial_editor_core.mjs';

function el(tag,parent,text){const node=document.createElement(tag);if(text)node.textContent=text;parent?.append(node);return node;}
function action(parent,key,text,callback){const b=el('button',parent,text);b.type='button';b.dataset.spatialAction=key;b.onclick=callback;return b;}
function input(parent,label,value,onchange,tag='input'){
    const holder=el('label',parent,label),field=el(tag,holder);field.value=value??'';
    if(tag==='textarea')field.rows=3;
    field.onchange=()=>onchange(field.value);return field;
}
function select(parent,label,options,value,onchange){
    const holder=el('label',parent,label),field=el('select',holder);
    for(const [id,text] of options){const item=el('option',field,text);item.value=id;}
    field.value=value??'';field.onchange=()=>onchange(field.value);return field;
}
const bitmap=src=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('预览图加载失败'));image.src=src;});

export function openSpatialEditor(node,{preview,confirm=message=>window.confirm(message)}={}){
    if(node.t8SpatialEditor){node.t8SpatialEditor.root.focus();return node.t8SpatialEditor;}
    let initial,initialError='';
    const initialRaw=fieldValue(node,'markers_json')||'{"markers":[],"relations":[]}';
    try{initial=readSpec(initialRaw);}
    catch(error){initial={markers:[],relations:[]};initialError=error.message;}
    const history=new History({spec:initial,mode:fieldValue(node,'mode')||'render_rectangles'});
    let state=history.value,selected=state.spec.markers[0]?.marker_id,tool='select',gesture=null;
    let source=null,sourceImage=null,actualImage=null,loading=false,closed=false,revision=0,rawPending=!!initialError;
    const root=el('div',document.body);root.dataset.t8SpatialEditor='true';root.tabIndex=-1;
    const style=el('style',root);
    style.textContent=`[data-t8-spatial-editor]{position:fixed;inset:0;z-index:100001;pointer-events:auto;background:#000b;display:flex;align-items:center;justify-content:center;padding:14px;color:#eee;font:14px/1.5 sans-serif}
    [data-t8-spatial-editor] section{box-sizing:border-box;background:#252b33;border:1px solid #748797;border-radius:12px;padding:18px;width:96vw;max-width:1450px;max-height:94vh;overflow:auto}
    [data-t8-spatial-editor] h2{margin:0 0 8px;font-size:21px}[data-t8-spatial-editor] .layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px}
    [data-t8-spatial-editor] .stage{display:flex;align-items:center;justify-content:center;min-height:230px;background:#10151a;padding:8px}
    [data-t8-spatial-editor] canvas{max-width:100%;max-height:57vh;width:auto;height:auto;pointer-events:auto;touch-action:none;cursor:crosshair}
    [data-t8-spatial-editor] .side{max-height:65vh;overflow:auto;padding-right:8px}
    [data-t8-spatial-editor] label{display:block;margin:8px 0}[data-t8-spatial-editor] input,[data-t8-spatial-editor] textarea,[data-t8-spatial-editor] select{box-sizing:border-box;display:block;width:100%;padding:6px;background:#151c24;color:#eee;border:1px solid #667684;border-radius:4px}
    [data-t8-spatial-editor] button{padding:7px 10px;margin:3px;border:1px solid #6c8a9f;border-radius:5px;background:#365c71;color:white;cursor:pointer}
    [data-t8-spatial-editor] button:disabled{opacity:.45;cursor:not-allowed}[data-t8-spatial-editor] .row{display:flex;flex-wrap:wrap;align-items:center}
    [data-t8-spatial-editor] .status{padding:8px;background:#16242e;white-space:pre-wrap;min-height:21px}[data-t8-spatial-editor] .card{border-top:1px solid #52606b;padding:7px 0}
    @media(max-width:850px){[data-t8-spatial-editor] .layout{grid-template-columns:1fr}[data-t8-spatial-editor] .side{max-height:40vh}}`;
    const panel=el('section',root);panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','H3 手动空间画框');
    el('h2',panel,'H3 手动空间画框 / Spatial Marker Canvas');
    el('p',panel,'① 在节点上传图片　② 点「人物框 / 目标框」后拖动　③ 填写描述与动作关系　④ 应用后保存工作流。这里叠加标记，不裁掉原图，不运行模型。');
    const top=el('div',panel);top.className='row';
    const modeSelect=select(top,'输入图模式',[['render_rectangles','干净源图 → 绘制矩形'],['provided_marked','已有手绘标记图 → 原图不改']],state.mode,value=>commit({...state,mode:value}));
    const modeHelp=el('p',panel);
    const layout=el('div',panel);layout.className='layout';
    const left=el('div',layout),toolbar=el('div',left);toolbar.className='row';
    const setTool=value=>{tool=value;actualImage=null;status.textContent=value==='select'?'选择：拖框内部移动，拖八个控制点缩放。':'请在图片上拖出'+(value==='actor'?'人物框':value==='target'?'目标框':'当前框的新范围')+'。';draw();};
    action(toolbar,'select','选择 / 移动',()=>setTool('select'));
    action(toolbar,'actor','＋人物框',()=>setTool('actor'));
    action(toolbar,'target','＋目标框',()=>setTool('target'));
    action(toolbar,'redraw','重画选中框',()=>{if(selected)setTool('redraw');});
    const undo=action(toolbar,'undo','撤销',()=>restore(history.undo()));
    const redo=action(toolbar,'redo','重做',()=>restore(history.redo()));
    const stage=el('div',left);stage.className='stage';
    const canvas=el('canvas',stage);canvas.width=640;canvas.height=400;canvas.tabIndex=0;canvas.dataset.spatialCanvas='true';
    const under=el('div',left);under.className='row';
    action(under,'reload','重新读取节点图片',()=>load());
    action(under,'overlay','编辑叠层',()=>{actualImage=null;draw();});
    const actual=action(under,'actual','预览实际标记图（不运行模型）',async()=>{
        document.activeElement?.blur();const errors=problems(state.spec,state.mode);
        if(errors.length){status.textContent=errors.join('；');return;}
        const snapshot=JSON.stringify([state,fieldValue(node,'image'),fieldValue(node,'line_width')]),ticket=++revision;
        actual.disabled=true;
        try{
            const result=await preview({image:source?.name,mode:state.mode,markers_json:JSON.stringify(state.spec),line_width:fieldValue(node,'line_width')});
            const rendered=await bitmap(result.png);
            if(closed||ticket!==revision)return;
            if(snapshot!==JSON.stringify([state,fieldValue(node,'image'),fieldValue(node,'line_width')])||result.source_sha256!==source?.sha)throw Error('源图或草稿已变化，请重新加载/预览。');
            actualImage=rendered;draw();status.textContent='实际输出预览：不含ID、控制点和关系辅助线；最终视频效果仍需核对。';
        }catch(error){if(!closed)status.textContent=error.message;}finally{if(!closed)actual.disabled=false;}
    });
    const side=el('div',layout);side.className='side';
    const fields=el('div',side),relations=el('div',side);
    action(side,'relation','＋添加动作关系',()=>{
        const actors=state.spec.markers.filter(m=>m.kind==='actor'),targets=state.spec.markers.filter(m=>m.kind==='target');
        if(!actors.length||!targets.length){status.textContent='先画人物框和目标框。';return;}
        const spec=structuredClone(state.spec);spec.relations.push({actor_marker_id:actors.find(m=>m.marker_id===selected)?.marker_id||actors[0].marker_id,target_marker_id:targets[0].marker_id,action:''});commit({...state,spec});
    });
    const advanced=el('details',panel);el('summary',advanced,'高级JSON（自动填写，通常无需手写）');
    const json=el('textarea',advanced);json.rows=5;json.dataset.spatialJson='true';json.value=initialError?initialRaw:JSON.stringify(state.spec,null,2);
    json.oninput=()=>{rawPending=true;check();};
    action(advanced,'import','导入JSON草稿',()=>{try{const spec=readSpec(json.value);rawPending=false;commit({...state,spec});}catch(error){status.textContent=error.message;check();}});
    action(advanced,'reset-json','恢复为当前表单',()=>{rawPending=false;json.value=JSON.stringify(state.spec,null,2);check();});
    const status=el('p',panel);status.className='status';status.setAttribute('role','status');
    const bottom=el('div',panel);bottom.className='row';
    const save=action(bottom,'apply','应用并完成',()=>apply(true));
    const keep=action(bottom,'apply-keep','应用，继续编辑',()=>apply(false));
    action(bottom,'close','关闭',()=>close());

    function restore(value){state=value;selected=state.spec.markers.some(m=>m.marker_id===selected)?selected:state.spec.markers[0]?.marker_id;rawPending=false;actualImage=null;render();}
    function commit(value){if(rawPending){status.textContent='高级JSON尚未导入，请先导入或恢复表单。';return;}history.push(value);restore(history.value);}
    function check(){
        const errors=problems(state.spec,state.mode),driven=linkedFields(node);
        if(!source||loading)errors.unshift('请先在节点上传图片并读取成功');
        if(source&&fieldValue(node,'image')!==source.name)errors.unshift('节点已换图，请重新读取');
        if(driven.length)errors.unshift('外部连线驱动：'+driven.join(', ')+'；不会断线或覆盖');
        if(rawPending)errors.unshift('高级JSON尚未导入');
        save.disabled=keep.disabled=errors.length>0;
        actual.disabled=!source||loading||errors.length>0;
        undo.disabled=history.index===0;redo.disabled=history.index===history.values.length-1;
        status.textContent=errors.length?errors.join('；'):'已就绪。应用只写回节点，不排队；之后仍需保存工作流。';
    }
    function render(){
        fields.replaceChildren();relations.replaceChildren();modeSelect.value=state.mode;
        modeHelp.textContent=state.mode==='provided_marked'?'已有标记图模式：框与颜色仅作含义声明，移动/改色不改变原图像素。':'矩形绘制模式：输出保留原图大小，仅叠加彩色矩形；ID、关系线只在编辑器显示。';
        const selection=select(fields,'选择框',state.spec.markers.map(m=>[m.marker_id,(m.kind==='actor'?'人物 ':'目标 ')+m.marker_id+(m.description?' · '+m.description.slice(0,24):' · 待填写描述')]),selected,value=>{selected=value;render();});
        selection.dataset.spatialField='selection';
        const marker=state.spec.markers.find(m=>m.marker_id===selected);
        if(marker){
            const box=el('div',fields);box.className='card';
            const change=values=>{try{const id=values.marker_id??selected;const spec=changeBox(state.spec,selected,values);selected=id;commit({...state,spec});}catch(error){status.textContent=error.message;}};
            const description=input(box,'人物/目标描述',marker.description,value=>change({description:value}),'textarea');description.dataset.spatialField='description';
            const color=input(box,'颜色',colorHex(marker.color),value=>change({color:value}));color.type='color';color.dataset.spatialField='color';
            el('p',box,validBox(marker.xyxy)?'源图坐标：'+marker.xyxy.map(n=>n.toFixed(4)).join(', '):'未声明几何');
            const technical=el('details',box);el('summary',technical,'ID / 角色声明（高级）');
            input(technical,'框 ID',marker.marker_id,value=>change({marker_id:value.trim()}));
            if(marker.kind==='actor')input(technical,'角色 ID（不等于声音身份）',marker.role_id,value=>change({role_id:value.trim()}));
            action(box,'delete','删除此框和关联动作',()=>{const spec=deleteBox(state.spec,selected);selected=null;commit({...state,spec});});
        }
        const options=kind=>state.spec.markers.filter(m=>m.kind===kind).map(m=>[m.marker_id,m.description||m.marker_id]);
        state.spec.relations.forEach((relation,index)=>{
            const card=el('div',relations);card.className='card';el('strong',card,'动作关系 '+(index+1));
            const update=values=>{const spec=structuredClone(state.spec);Object.assign(spec.relations[index],values);commit({...state,spec});};
            select(card,'人物',options('actor'),relation.actor_marker_id,value=>update({actor_marker_id:value}));
            select(card,'目标',options('target'),relation.target_marker_id,value=>update({target_marker_id:value}));
            const actionField=input(card,'动作（走向哪里、做什么、最后状态）',relation.action,value=>update({action:value}),'textarea');actionField.dataset.spatialField='action';
            action(card,'delete-relation','删除动作',()=>{const spec=structuredClone(state.spec);spec.relations.splice(index,1);commit({...state,spec});});
        });
        if(!rawPending)json.value=JSON.stringify(state.spec,null,2);draw();check();
    }
    function draw(){
        const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
        if(!sourceImage)return;
        ctx.drawImage(actualImage||sourceImage,0,0,canvas.width,canvas.height);if(actualImage)return;
        const scale=canvas.width/(canvas.getBoundingClientRect().width||canvas.width),w=canvas.width,h=canvas.height;
        for(const m of state.spec.markers){
            const box=gesture?.id===m.marker_id?gesture.box:m.xyxy;if(!validBox(box))continue;
            const [l,t,r,b]=box;ctx.strokeStyle=colorHex(m.color);ctx.lineWidth=2*scale;ctx.strokeRect(l*w,t*h,(r-l)*w,(b-t)*h);
            ctx.fillStyle='#000a';ctx.fillRect(l*w,t*h,Math.min(w-l*w,(m.marker_id.length*8+8)*scale),22*scale);
            ctx.fillStyle='#fff';ctx.font=14*scale+'px sans-serif';ctx.fillText(m.marker_id,l*w+3*scale,t*h+16*scale);
            if(m.marker_id===selected)for(const [x,y] of handles(box)){ctx.fillStyle='#fff';ctx.fillRect(x*w-3*scale,y*h-3*scale,6*scale,6*scale);}
        }
        if(gesture&&!gesture.id&&validBox(gesture.box)){const [l,t,r,b]=gesture.box;ctx.strokeStyle=tool==='actor'?'#00dfff':'#ffdf00';ctx.lineWidth=2*scale;ctx.strokeRect(l*w,t*h,(r-l)*w,(b-t)*h);}
    }
    canvas.onpointerdown=event=>{
        if(!sourceImage||loading||rawPending||event.button!==0)return;
        const rect=canvas.getBoundingClientRect(),start=pointerPoint(event.clientX,event.clientY,rect);
        if(start.some(n=>n<0||n>1))return;
        actualImage=null;canvas.focus();
        if(tool==='select'){
            const hit=hitBox(state.spec,start,selected,[8/rect.width,8/rect.height]);
            if(!hit){selected=null;render();return;}selected=hit.id;
            const box=state.spec.markers.find(m=>m.marker_id===hit.id).xyxy;
            gesture={...hit,start,original:[...box],box:[...box],client:[event.clientX,event.clientY]};
        }else gesture={id:tool==='redraw'?selected:null,start,box:dragBox(start,start),client:[event.clientX,event.clientY]};
        gesture.pointer=event.pointerId;canvas.setPointerCapture?.(event.pointerId);draw();
    };
    canvas.onpointermove=event=>{
        if(!gesture||event.pointerId!==gesture.pointer)return;
        const end=pointerPoint(event.clientX,event.clientY,canvas.getBoundingClientRect());
        gesture.box=gesture.original?moveBox(gesture.original,gesture.handle,gesture.start,end):dragBox(gesture.start,end);draw();
    };
    const cancel=()=>{gesture=null;draw();};
    canvas.onpointerup=event=>{
        if(!gesture||event.pointerId!==gesture.pointer)return;
        canvas.onpointermove(event);const done=gesture;gesture=null;
        if(Math.hypot(event.clientX-done.client[0],event.clientY-done.client[1])<3||!validBox(done.box)){draw();return;}
        if(done.id)commit({...state,spec:changeBox(state.spec,done.id,{xyxy:done.box})});
        else{const result=appendBox(state.spec,tool,done.box);selected=result.id;commit({...state,spec:result.spec});}
        tool='select';
    };
    canvas.onpointercancel=cancel;canvas.onlostpointercapture=()=>{if(gesture)cancel();};
    async function load(){
        const ticket=++revision;loading=true;source=null;actualImage=null;check();
        const name=fieldValue(node,'image');
        try{
            if(linkedFields(node).includes('image'))throw Error('图片字段由外部连线驱动，不能用隐藏文件名冒充实际源图。');
            const result=await preview({image:name}),image=await bitmap(result.png);
            if(closed||ticket!==revision)return;
            if(fieldValue(node,'image')!==name)throw Error('读取期间节点已换图，请重试。');
            source={name,sha:result.source_sha256};sourceImage=image;canvas.width=result.width;canvas.height=result.height;
            const old=fieldValue(node,'expected_source_sha256');
            loading=false;draw();check();if(old&&old!==source.sha)status.textContent='源图已变化：请重新检查全部框的位置，再应用绑定新图。';
        }catch(error){if(!closed&&ticket===revision){loading=false;check();status.textContent=error.message+'；请先在节点选择/上传图片。';}}
    }
    async function apply(finish){
        document.activeElement?.blur();
        try{
            if(loading||!source||rawPending)throw Error('请先加载正确源图并完成草稿');
            // Re-read the source immediately before writing widgets. Never save a
            // binding for an older file while displaying a silently changed file.
            save.disabled=keep.disabled=true;
            const bound=source,snapshot=JSON.stringify(state),ticket=revision;
            const result=await preview({image:bound.name});
            if(closed)return;
            if(ticket!==revision||bound!==source||snapshot!==JSON.stringify(state)||rawPending)throw Error('读取期间草稿或源图已变化，请重新应用。');
            if(result.source_sha256!==bound.sha)throw Error('源图文件已变化，请重新读取并核对框选。');
            applyDraft(node,state,bound);history.accept();
            if(finish)close(true);else{check();status.textContent='已应用到节点，请保存工作流。';}
        }catch(error){if(!closed){check();status.textContent=error.message;}}
    }
    function close(force=false){
        document.activeElement?.blur();
        if(!force&&(history.dirty||rawPending)&&!confirm('有未应用的修改，确定关闭并放弃草稿？'))return false;
        closed=true;revision++;root.remove();delete node.t8SpatialEditor;return true;
    }
    root.onkeydown=event=>{
        // Editing shortcuts belong to this modal, not the graph underneath
        // (especially Ctrl+Enter queue and the graph's own Undo/Redo).
        event.stopPropagation();
        if(event.key==='Tab'){
            const targets=[...panel.querySelectorAll('button,input,textarea,select,summary,[tabindex="0"]')]
                .filter(n=>!n.disabled&&n.getClientRects().length);
            const index=targets.indexOf(document.activeElement);
            if(index<0||(!event.shiftKey&&index===targets.length-1)||(event.shiftKey&&index===0)){
                event.preventDefault();(event.shiftKey?targets.at(-1):targets[0])?.focus();
            }
        }
        if(event.key==='Escape'){event.preventDefault();event.stopPropagation();if(gesture)cancel();else close();return;}
        if(!['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName)&&(event.ctrlKey||event.metaKey)){
            if(event.key.toLowerCase()==='z'){event.preventDefault();restore(event.shiftKey?history.redo():history.undo());}
            if(event.key.toLowerCase()==='y'){event.preventDefault();restore(history.redo());}
        }
    };
    root.onkeyup=event=>event.stopPropagation();
    for(const type of ['pointerdown','pointermove','pointerup'])root.addEventListener(type,event=>event.stopPropagation());
    const instance={root,close};node.t8SpatialEditor=instance;render();root.focus();instance.ready=load();return instance;
}
