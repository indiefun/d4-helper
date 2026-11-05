const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
async function editor(){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'frontend/index.html'),'utf8'),{runScripts:'outside-only',url:'http://localhost',pretendToBeVisual:true});
 dom.window.structuredClone=structuredClone;
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/model.js'),'utf8'));
 let saved;const document=dom.window.TimelineModel.demo();
 dom.window.go={main:{App:{LoadConfiguration:async()=>({path:'workspace.timeline.json',content:JSON.stringify(document)}),StopAll:async()=>{},SaveAndApply:async raw=>{saved=JSON.parse(raw);return {path:'workspace.timeline.json',content:raw};}}}};
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/app.js'),'utf8'));
 await new Promise(resolve=>setImmediate(resolve));
 return {dom,d:dom.window.document,M:dom.window.TimelineModel,saved:()=>saved};
}
test('one macro contains concurrent editable tracks without legacy controls',async()=>{const a=await editor();try{assert.equal(a.d.querySelectorAll('.track-lane').length,3);assert.equal(a.d.querySelectorAll('.clip').length,3);assert.equal(a.d.querySelector('#action'),null);assert.equal(a.d.querySelector('#profiles'),null);assert.equal(a.d.querySelector('#loop').checked,false);}finally{a.dom.window.close();}});
test('palette click inserts at playhead, inspector edits timing, undo restores and save keeps tracks',async()=>{const a=await editor(),d=a.d;try{
 d.querySelector('[data-action="move"]').click();assert.equal(d.querySelectorAll('.clip').length,4);
 d.getElementById('block-at').value=600;d.getElementById('block-at').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('block-x').value=1200;d.getElementById('block-x').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('add-track').click();assert.equal(d.querySelectorAll('.track-lane').length,4);
 d.getElementById('undo').click();assert.equal(d.querySelectorAll('.track-lane').length,3);
 d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(a.saved().schema_version,3);assert.equal(a.saved().macros[0].tracks[0].blocks.at(-1).at_ms,600);assert.equal(a.saved().macros[0].tracks[0].blocks.at(-1).x,1200);
 }finally{a.dom.window.close();}});
test('track geometry supports cross-track move, resize and absolute timing',async()=>{const a=await editor();try{const m=a.M.macro('test');const b=a.M.place(m,'hold',m.tracks[0].id,103,10);assert.equal(b.at_ms,100);a.M.move(m,b.id,m.tracks[1].id,557,10);assert.equal(m.tracks[0].blocks.length,0);assert.equal(m.tracks[1].blocks[0].at_ms,560);a.M.resize(m,b.id,440,10);assert.equal(b.duration_ms,440);assert.equal(a.M.flatten(m)[1].at_ms,1000);}finally{a.dom.window.close();}});
test('palette drop inserts into chosen track at the dropped absolute time',async()=>{const a=await editor();try{const lane=a.d.querySelectorAll('.track-lane')[1];lane.getBoundingClientRect=()=>({left:150,top:0});const event=new a.dom.window.Event('drop',{bubbles:true,cancelable:true});Object.defineProperties(event,{clientX:{value:260},dataTransfer:{value:{getData:()=> 'tap'}}});lane.dispatchEvent(event);a.d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));const b=a.saved().macros[0].tracks[1].blocks.at(-1);assert.equal(b.type,'tap');assert.equal(b.at_ms,500);}finally{a.dom.window.close();}});
test('explicit key events validate across tracks and mute reveals missing release',async()=>{const a=await editor();try{const m=a.M.macro('test');m.tracks[0].blocks=[{...a.M.block('down',100),key:'f'}];m.tracks[1].blocks=[{...a.M.block('up',500),key:'f'}];assert.equal(a.M.errors(m).length,0);m.tracks[1].muted=true;assert.ok(a.M.errors(m).some(x=>x.includes('抬起')));}finally{a.dom.window.close();}});
