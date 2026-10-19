import {app} from '../../scripts/app.js';
import {api} from '../../scripts/api.js';
import {configureCanvas,serializeCanvas} from './h3_spatial_editor_core.mjs';
import {openSpatialEditor} from './h3_spatial_editor_view.mjs';

export const EDIT_BUTTON='🖱 手动画框 / Edit spatial regions';
export function openEditor(node){return openSpatialEditor(node,{preview:async data=>{
    const response=await api.fetchApi('/t8-prompt-enhancer/h3-spatial-editor/preview',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),cache:'no-store'});
    const result=await response.json();if(!response.ok)throw Error(result.error||'无法读取空间预览');return result;
}});}

app.registerExtension({name:'T8.H3.SpatialMarkerCanvas',async beforeRegisterNodeDef(Type,data){
    if(data.name!=='T8H3SpatialMarkerCanvas')return;
    const created=Type.prototype.onNodeCreated,configured=Type.prototype.onConfigure;
    const serialized=Type.prototype.onSerialize,removed=Type.prototype.onRemoved;
    Type.prototype.onNodeCreated=function(...args){
        const result=created?.apply(this,args);
        if(!this.widgets?.some(w=>w.name===EDIT_BUTTON)){
            const button=this.addWidget('button',EDIT_BUTTON,null,()=>openEditor(this),{serialize:false});
            button.serialize=false;button.serializeValue=()=>undefined;
        }
        return result;
    };
    Type.prototype.onConfigure=function(data){return configureCanvas(this,data,configured,arguments);};
    Type.prototype.onSerialize=function(data){const result=serialized?.apply(this,arguments);serializeCanvas(this,data);return result;};
    Type.prototype.onRemoved=function(...args){this.t8SpatialEditor?.close(true);return removed?.apply(this,args);};
}});
