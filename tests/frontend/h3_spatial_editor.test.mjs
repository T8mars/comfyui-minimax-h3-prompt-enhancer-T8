import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import * as core from '../../web/js/h3_spatial_editor_core.mjs';

const empty=()=>({markers:[],relations:[]});
function pair(){
    let {spec}=core.appendBox(empty(),'actor',[.1,.1,.4,.9]);
    ({spec}=core.appendBox(spec,'target',[.65,.2,.95,.95]));
    spec.markers[0].description='the red coat person';spec.markers[1].description='the doorway';
    spec.relations.push({actor_marker_id:'actor_1',target_marker_id:'target_1',action:'walk through, then keep moving'});return spec;
}
const values=()=>({image:'source.png',mode:'render_rectangles',markers_json:JSON.stringify(pair()),line_width:3,expected_source_sha256:''});
function node(order=core.FIELDS){const v=values();return {widgets:order.map(name=>({name,value:v[name]})),inputs:[],properties:{},graph:{change(){}},setDirtyCanvas(){},addWidget(type,name,value,callback,options){const w={type,name,value,callback,options};this.widgets.push(w);return w;}};}

test('manual forms create unique boxes, preserve independent fields, and never invent actions',()=>{
    const original=empty();const a=core.appendBox(original,'actor',[0,0,.5,1]),b=core.appendBox(a.spec,'actor',[.1,.2,.2,.5]);
    assert.equal(original.markers.length,0);assert.notEqual(a.id,b.id);assert.notEqual(a.spec.markers[0].color,b.spec.markers[1].color);
    assert.equal(b.spec.relations.length,0);assert.equal(b.spec.markers[1].description,'');
    assert.ok(core.problems(b.spec,'render_rectangles').length);
    assert.deepEqual(core.problems(pair(),'render_rectangles'),[]);
    assert.throws(()=>core.appendBox(pair(),'actor',[0,0,0,1]));
});

test('rename follows every relation, delete removes dependent edges, shared colors remain legal',()=>{
    const a=pair(),b=core.changeBox(a,'actor_1',{marker_id:'walker',color:'yellow'});
    assert.equal(a.markers[0].marker_id,'actor_1');assert.equal(b.relations[0].actor_marker_id,'walker');
    assert.deepEqual(core.problems(b,'render_rectangles'),[]);
    assert.equal(core.deleteBox(b,'target_1').relations.length,0);
    assert.throws(()=>core.changeBox(a,'actor_1',{marker_id:'target_1'}));
});

test('geometry follows visible canvas scale, reverse drags, edge clamp and eight handles',()=>{
    assert.deepEqual(core.pointerPoint(225,325,{left:100,top:200,width:250,height:250}),[.5,.5]);
    assert.deepEqual(core.dragBox([.8,.9],[.2,.1]),[.2,.1,.8,.9]);
    assert.deepEqual(core.dragBox([-1,.4],[2,.8]),[0,.4,1,.8]);
    const box=[.1,.1,.4,.8];assert.equal(core.handles(box).length,8);
    assert.deepEqual(core.moveBox(box,-1,[.2,.2],[2,2]),[.7,.29999999999999993,1,1]);
    for(let handle=0;handle<8;handle++)assert.ok(core.validBox(core.moveBox(box,handle,[.2,.2],[.24,.24])));
    assert.equal(core.hitBox(pair(),[.25,.5],null,[.01,.01]).id,'actor_1');
    assert.equal(core.hitBox(pair(),[.1,.1],'actor_1',[.01,.01]).handle,0);
});

test('history undo/redo covers geometry, descriptions, relations and explicit mode',()=>{
    const first={spec:pair(),mode:'render_rectangles'},h=new core.History(first);
    h.push({...first,mode:'provided_marked'});assert.equal(h.dirty,true);
    h.undo();assert.deepEqual(h.value,first);assert.equal(h.dirty,false);
    h.redo();h.accept();assert.equal(h.dirty,false);
    const changed=h.value;changed.spec.relations[0].action='stop';h.push(changed);
    assert.equal(h.undo().spec.relations[0].action,'walk through, then keep moving');
    h.push({...h.value,mode:'render_rectangles'});assert.equal(h.values.length,3);
});

test('bounded history keeps no image payload and oversized raw JSON is rejected before parsing',()=>{
    const h=new core.History({n:0});for(let n=1;n<=1000;n++)h.push({n});
    assert.equal(h.values.length,256);assert.equal(h.value.n,1000);assert.equal(h.undo().n,999);
    assert.throws(()=>core.readSpec(' '.repeat(65537)),/64KiB/);
});

test('provided marks are declarations; invalid geometry, roles, dangling relations and oversize data cannot apply',()=>{
    const spec=pair();spec.markers.forEach(m=>delete m.xyxy);
    assert.deepEqual(core.problems(spec,'provided_marked'),[]);assert.ok(core.problems(spec,'render_rectangles').length);
    for(const mutate of [s=>s.markers[0].role_id='',s=>s.markers[0].xyxy=[NaN,0,1,1],s=>s.relations[0].target_marker_id='missing',s=>s.relations[0].action='',s=>s.markers[0].description='x'.repeat(4097)]){
        const s=pair();mutate(s);assert.ok(core.problems(s,'render_rectangles').length);
    }
    assert.throws(()=>core.readSpec('{"markers":null,"relations":[]}'));
});

test('five stable fields serialize by name, not upload/action positions, including unblurred DOM text',()=>{
    const n=node([...core.FIELDS].reverse());n.addWidget('button','upload','do not save',()=>{},{serialize:false});
    n.widgets.find(w=>w.name==='markers_json').inputEl={value:JSON.stringify(pair())};
    const data={};core.serializeCanvas(n,data);assert.equal(data.widgets_values.length,5);
    assert.deepEqual(data.widgets_values,core.FIELDS.map(name=>values()[name]));
    const copy=node();core.configureCanvas(copy,data,function(info){info.widgets_values.forEach((v,i)=>this.widgets[i].value=v);},[data]);
    for(const name of core.FIELDS)assert.equal(core.fieldValue(copy,name),values()[name]);
});

test('corrupt named metadata falls back to positional; linked missing widget keeps a null slot',()=>{
    const saved={widgets_values:core.FIELDS.map(n=>values()[n]),widgets_values_named:{},properties:{t8_spatial_canvas_widgets_v1:Object.fromEntries(core.FIELDS.map(n=>[n,null]))}};
    const n=node([...core.FIELDS].reverse());core.configureCanvas(n,saved,null,[saved]);
    for(const name of core.FIELDS)assert.equal(core.fieldValue(n,name),values()[name]);
    n.inputs=[{name:'markers_json',link:13}];n.widgets=n.widgets.filter(w=>w.name!=='markers_json');
    const data={};core.serializeCanvas(n,data);assert.equal(data.widgets_values.length,5);assert.equal(data.widgets_values[2],null);
});

test('apply checks source and connected ownership before any mutation, then updates actual saved DOM widgets',()=>{
    const n=node(),state={spec:pair(),mode:'render_rectangles'},source={name:'source.png',sha:'a'.repeat(64)};
    const initial=JSON.stringify(n.widgets);n.inputs=[{name:'markers_json',link:7}];
    assert.throws(()=>core.applyDraft(n,state,source),/外部连线/);assert.equal(JSON.stringify(n.widgets),initial);
    n.inputs=[];assert.throws(()=>core.applyDraft(n,state,{...source,name:'other.png'}),/换图/);
    assert.throws(()=>core.applyDraft(n,state,{...source,sha:''}),/校验/);
    n.widgets.find(w=>w.name==='markers_json').inputEl={value:'stale'};core.applyDraft(n,state,source);
    assert.equal(core.fieldValue(n,'expected_source_sha256'),source.sha);assert.deepEqual(JSON.parse(core.fieldValue(n,'markers_json')),pair());
});

test('production hook only targets the new node, action is idempotent and cannot be a saved sixth value',async()=>{
    const code=await readFile(new URL('../../web/js/h3_spatial_editor.js',import.meta.url),'utf8');
    const source=code.replace(/^import .*;\r?\n/gm,'').replace(/export /g,'');let extension,opened=0;
    vm.runInNewContext(source,{app:{registerExtension:e=>extension=e},api:{},configureCanvas:core.configureCanvas,
        serializeCanvas:core.serializeCanvas,openSpatialEditor:()=>{opened++;},Object,JSON});
    function Type(){Object.assign(this,node());}
    let created=0;Type.prototype.onNodeCreated=()=>++created;
    await extension.beforeRegisterNodeDef(Type,{name:'MiniMaxH3PromptEnhancerT8'});assert.equal(Type.prototype.onSerialize,undefined);
    await extension.beforeRegisterNodeDef(Type,{name:'T8H3SpatialMarkerCanvas'});const n=new Type();n.onNodeCreated();n.onNodeCreated();
    assert.equal(created,2);assert.equal(n.widgets.filter(w=>w.type==='button').length,1);
    const button=n.widgets.at(-1);assert.equal(button.serialize,false);assert.equal(button.options.serialize,false);button.callback();assert.equal(opened,1);
    const data={};n.onSerialize(data);assert.equal(data.widgets_values.length,5);
});
