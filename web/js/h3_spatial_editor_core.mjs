// Independent authoring and widget contracts. No graph execution or inference.
export const FIELDS = ['image','mode','markers_json','line_width','expected_source_sha256'];
export const MODES = ['render_rectangles','provided_marked'];
export const COLORS = {cyan:'#00dfff',yellow:'#ffdf00',magenta:'#ef30ef',blue:'#3070ff',green:'#20df50',orange:'#ff9000',red:'#ff3030',white:'#ffffff',black:'#000000'};
const copy = value => structuredClone(value);
const ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/;
export const colorHex = color => COLORS[String(color).toLowerCase()] || String(color).toLowerCase();
export const validBox = box => Array.isArray(box) && box.length===4 && box.every(Number.isFinite)
    && 0<=box[0] && box[0]<box[2] && box[2]<=1 && 0<=box[1] && box[1]<box[3] && box[3]<=1;

export function readSpec(text) {
    if(typeof text!=='string'||new TextEncoder().encode(text).length>65536)throw Error('标记JSON超过v1的64KiB预算');
    const value=JSON.parse(text);
    if(!value || typeof value!=='object' || Array.isArray(value) || Object.keys(value).sort().join()!=='markers,relations'
        || !Array.isArray(value.markers) || !Array.isArray(value.relations)
        || value.markers.some(m=>!m||typeof m!=='object'||Array.isArray(m)||!ID.test(m.marker_id)||!['actor','target'].includes(m.kind))
        || value.relations.some(r=>!r||typeof r!=='object'||Array.isArray(r))) throw Error('标记数据格式不正确，可在高级JSON中修复。');
    return value;
}

export function problems(spec,mode) {
    const errors=[];
    if(!MODES.includes(mode))errors.push('请选择绘框模式');
    if(spec.markers.length<2||spec.markers.length>64)errors.push('需要人物框和目标框，最多64框');
    if(spec.relations.length<1||spec.relations.length>128)errors.push('请添加动作关系，最多128条');
    const ids=new Set();
    for(const m of spec.markers){
        if(!ID.test(m.marker_id)||ids.has(m.marker_id))errors.push('框的ID重复或无效');
        ids.add(m.marker_id);
        if(!['actor','target'].includes(m.kind))errors.push('框类型无效');
        if(m.kind==='actor'&&!ID.test(m.role_id||''))errors.push(m.marker_id+'缺少角色ID');
        if(m.kind==='target'&&m.role_id!=null)errors.push('目标框不能有角色ID');
        if(!/^#[0-9a-f]{6}$/.test(colorHex(m.color)))errors.push(m.marker_id+'颜色无效');
        if(typeof m.description!=='string'||!m.description.trim()||new TextEncoder().encode(m.description).length>4096)errors.push(m.marker_id+'请填写描述（最多4096字节）');
        if(!(mode==='provided_marked'&&m.xyxy==null)&&!validBox(m.xyxy))errors.push(m.marker_id+'请画有效矩形');
        if(Object.keys(m).some(k=>!['marker_id','kind','role_id','color','description','xyxy'].includes(k)))errors.push('未知标记字段');
    }
    const used=new Set();
    for(const r of spec.relations){
        if(!spec.markers.some(m=>m.marker_id===r.actor_marker_id&&m.kind==='actor')||!spec.markers.some(m=>m.marker_id===r.target_marker_id&&m.kind==='target'))errors.push('动作关系需连接人物与目标');
        used.add(r.actor_marker_id);used.add(r.target_marker_id);
        if(typeof r.action!=='string'||!r.action.trim()||new TextEncoder().encode(r.action).length>4096)errors.push('请填写动作（最多4096字节）');
        if(Object.keys(r).sort().join()!=='action,actor_marker_id,target_marker_id')errors.push('未知动作字段');
    }
    if(spec.markers.some(m=>!used.has(m.marker_id)))errors.push('每个框都需要参与动作关系');
    if(new TextEncoder().encode(JSON.stringify(spec)).length>65536)errors.push('数据超过v1的64KiB预算');
    return [...new Set(errors)];
}

export function appendBox(spec,kind,xyxy) {
    if(!['actor','target'].includes(kind)||!validBox(xyxy)||spec.markers.length>=64)throw Error('框无效或已达64框');
    const next=copy(spec);let index=1;
    while(next.markers.some(m=>m.marker_id===kind+'_'+index))index++;
    const id=kind+'_'+index;
    const used=new Set(next.markers.map(m=>colorHex(m.color)));
    const palette=kind==='actor'?['cyan','magenta','blue','green','red','orange']:['yellow','orange','green','magenta'];
    const color=palette.find(c=>!used.has(COLORS[c]))||palette[(index-1)%palette.length];
    next.markers.push({marker_id:id,kind,...(kind==='actor'?{role_id:'role_'+index}:{}),color,description:'',xyxy:[...xyxy]});
    return {spec:next,id};
}

export function changeBox(spec,id,fields) {
    const next=copy(spec), marker=next.markers.find(m=>m.marker_id===id);
    if(!marker)throw Error('框已不存在');
    const newID=fields.marker_id??id;
    if(!ID.test(newID)||next.markers.some(m=>m!==marker&&m.marker_id===newID))throw Error('ID需唯一，使用1–48位英文字母、数字、下划线或短横线');
    Object.assign(marker,fields);
    for(const r of next.relations){if(r.actor_marker_id===id)r.actor_marker_id=newID;if(r.target_marker_id===id)r.target_marker_id=newID;}
    return next;
}

export function deleteBox(spec,id) {
    const next=copy(spec);
    next.markers=next.markers.filter(m=>m.marker_id!==id);
    next.relations=next.relations.filter(r=>r.actor_marker_id!==id&&r.target_marker_id!==id);
    return next;
}

export class History {
    constructor(value){this.values=[copy(value)];this.index=0;this.saved=JSON.stringify(value);}
    get value(){return copy(this.values[this.index]);}
    get dirty(){return JSON.stringify(this.value)!==this.saved;}
    push(value){if(JSON.stringify(value)===JSON.stringify(this.value))return;this.values.splice(++this.index);this.values.push(copy(value));if(this.values.length>256){this.values.shift();this.index--;}}
    undo(){this.index=Math.max(0,this.index-1);return this.value;}
    redo(){this.index=Math.min(this.values.length-1,this.index+1);return this.value;}
    accept(){this.saved=JSON.stringify(this.value);}
}

export function pointerPoint(x,y,rect) {
    if(!(rect.width>0&&rect.height>0))throw Error('图片尚未加载');
    return [(x-rect.left)/rect.width,(y-rect.top)/rect.height];
}
const clamp=n=>Math.min(1,Math.max(0,n));
export function dragBox(a,b){return [clamp(Math.min(a[0],b[0])),clamp(Math.min(a[1],b[1])),clamp(Math.max(a[0],b[0])),clamp(Math.max(a[1],b[1]))];}
export function handles(box){const [l,t,r,b]=box,x=(l+r)/2,y=(t+b)/2;return [[l,t],[x,t],[r,t],[r,y],[r,b],[x,b],[l,b],[l,y]];}
export function hitBox(spec,point,selected,tolerance){
    const active=spec.markers.find(m=>m.marker_id===selected);
    if(validBox(active?.xyxy)){
        const handle=handles(active.xyxy).findIndex(p=>Math.abs(p[0]-point[0])<=tolerance[0]&&Math.abs(p[1]-point[1])<=tolerance[1]);
        if(handle>=0)return {id:selected,handle};
    }
    const found=[...spec.markers].reverse().find(m=>validBox(m.xyxy)&&point[0]>=m.xyxy[0]&&point[0]<=m.xyxy[2]&&point[1]>=m.xyxy[1]&&point[1]<=m.xyxy[3]);
    return found?{id:found.marker_id,handle:-1}:null;
}
export function moveBox(box,handle,start,end){
    const dx=end[0]-start[0],dy=end[1]-start[1],p=[...box];
    if(handle===-1){const x=Math.max(-p[0],Math.min(1-p[2],dx)),y=Math.max(-p[1],Math.min(1-p[3],dy));return [p[0]+x,p[1]+y,p[2]+x,p[3]+y];}
    if([0,6,7].includes(handle))p[0]=clamp(p[0]+dx);
    if([0,1,2].includes(handle))p[1]=clamp(p[1]+dy);
    if([2,3,4].includes(handle))p[2]=clamp(p[2]+dx);
    if([4,5,6].includes(handle))p[3]=clamp(p[3]+dy);
    return dragBox([p[0],p[1]],[p[2],p[3]]);
}

function textInput(w){return w?.inputEl||(w?.element?.matches?.('input,textarea')?w.element:w?.element?.querySelector?.('input,textarea'));}
export function fieldValue(node,name){const w=node.widgets?.find(w=>w.name===name);return ['image','mode','line_width'].includes(name)?w?.value:(textInput(w)?.value??w?.value);}
export function setField(node,name,value){const w=node.widgets?.find(w=>w.name===name);if(!w)throw Error('找不到控件 '+name);w.value=value;const el=textInput(w);if(el)el.value=value??'';w.callback?.(value);}
export function linkedFields(node){return FIELDS.filter(name=>node.inputs?.some(i=>(i.name===name||i.widget?.name===name)&&i.link!=null));}
const typesOK=data=>data&&FIELDS.every(n=>Object.hasOwn(data,n)&&(
    data[n]===null||(n==='line_width'?Number.isInteger(data[n]):typeof data[n]==='string')))&&
    (data.mode===null||MODES.includes(data.mode));
export function serializeCanvas(node,data){
    const values=Object.fromEntries(FIELDS.map(n=>[n,fieldValue(node,n)??null]));
    data.widgets_values=FIELDS.map(n=>values[n]);data.widgets_values_named={...values};
    data.properties={...data.properties,t8_spatial_canvas_widgets_v1:values};
    node.properties={...node.properties,t8_spatial_canvas_widgets_v1:values};
}
export function configureCanvas(node,data,original,args){
    const positional=Array.isArray(data?.widgets_values)&&data.widgets_values.length===FIELDS.length?Object.fromEntries(FIELDS.map((n,i)=>[n,data.widgets_values[i]])):null;
    const values=[data?.properties?.t8_spatial_canvas_widgets_v1,data?.widgets_values_named,positional].find(value=>typesOK(value)
        && FIELDS.every(name=>value[name]!==null||node.inputs?.some(i=>(i.name===name||i.widget?.name===name)&&i.link!=null)));
    const projected=values?{...data,widgets_values:(node.widgets||[]).map(w=>Object.hasOwn(values,w.name)?values[w.name]:w.value)}:data;
    const result=original?.apply(node,[projected,...Array.from(args||[]).slice(1)]);
    if(values)for(const name of FIELDS){const w=node.widgets?.find(w=>w.name===name);if(w){w.value=values[name];const el=textInput(w);if(el)el.value=values[name]??'';}}
    return result;
}
export function applyDraft(node,state,source){
    const driven=linkedFields(node);
    if(driven.length)throw Error('这些字段由外部连线驱动，未覆盖或断线：'+driven.join(', '));
    if(fieldValue(node,'image')!==source.name)throw Error('节点已换图，请重新打开编辑器加载当前图。');
    const errors=problems(state.spec,state.mode);if(errors.length)throw Error(errors.join('；'));
    if(!/^[0-9a-f]{64}$/.test(source.sha))throw Error('源图校验尚未完成');
    for(const name of FIELDS)if(!node.widgets?.some(w=>w.name===name))throw Error('控件缺失 '+name);
    setField(node,'markers_json',JSON.stringify(state.spec));setField(node,'mode',state.mode);setField(node,'expected_source_sha256',source.sha);
    node.graph?.change?.();node.setDirtyCanvas?.(true,true);
}
