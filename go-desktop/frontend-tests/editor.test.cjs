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
test('starter macro uses one track and the palette exposes only paired key actions, movement and scroll',async()=>{const a=await editor();try{assert.equal(a.d.querySelectorAll('.track-lane').length,1);assert.equal(a.d.querySelectorAll('.clip').length,3);assert.deepEqual(Array.from(a.d.querySelectorAll('[data-action]'),e=>e.dataset.action),['tap','hold','move','scroll']);assert.equal(a.d.querySelector('#action'),null);assert.equal(a.d.querySelector('#profiles'),null);assert.equal(a.d.querySelector('#loop').checked,false);}finally{a.dom.window.close();}});

test('inspector switches between the selected macro and action without mixing their settings',async()=>{
 const a=await editor(),d=a.d;
 try{
  assert.equal(d.getElementById('inspector-title').textContent,'宏属性');
  assert.equal(d.getElementById('block-key'),null);
  d.getElementById('macro-name-input').value='测试宏';d.getElementById('macro-name-input').dispatchEvent(new a.dom.window.Event('change'));
  d.getElementById('macro-trigger').value='f3';d.getElementById('macro-trigger').dispatchEvent(new a.dom.window.Event('change'));
  d.getElementById('loop').checked=true;d.getElementById('loop').dispatchEvent(new a.dom.window.Event('change'));
  d.getElementById('duration').value=2500;d.getElementById('duration').dispatchEvent(new a.dom.window.Event('change'));
  assert.equal(d.getElementById('macro-name').textContent,'测试宏');
  assert.equal(d.getElementById('loop-status').textContent,'循环播放');
  assert.equal(d.getElementById('duration-readout').textContent,'2500');
  d.querySelector('.clip.tap').dispatchEvent(new a.dom.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  assert.equal(d.getElementById('inspector-title').textContent,'动作属性');
  assert.ok(d.getElementById('block-key'));
  for(const id of ['macro-name-input','macro-trigger','macro-enabled','loop','duration','duplicate-macro','remove-macro','block-repeat'])assert.equal(d.getElementById(id),null,id);
  d.getElementById('block-duration').value=80;d.getElementById('block-duration').dispatchEvent(new a.dom.window.Event('change'));
  d.querySelector('[data-macro]').click();
  assert.equal(d.getElementById('inspector-title').textContent,'宏属性');
  assert.equal(d.getElementById('macro-trigger').value,'f3');
  assert.equal(d.getElementById('loop').checked,true);
  assert.equal(d.getElementById('duration').value,'2500');
  assert.equal(d.getElementById('block-key'),null);
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(a.saved().macros[0].tracks[0].blocks[0].duration_ms,80);
  assert.equal(a.saved().macros[0].loop,true);
 }finally{a.dom.window.close();}
});

test('a click previews once even when an imported draft contains obsolete repeat metadata',async()=>{
 const a=await editor();
 try{const m=a.M.macro('test');m.loop=true;m.tracks[0].blocks=[{...a.M.block('tap',100),repeat_ms:100}];const events=a.M.flatten(m);assert.equal(events.length,2);assert.equal(events[0].at_ms,100);assert.equal(events[1].at_ms,160);}finally{a.dom.window.close();}
});

test('new macro starts with one empty track and saves paired arrow-key actions',async()=>{const a=await editor();try{a.d.getElementById('new-macro').click();assert.equal(a.d.querySelectorAll('.track-lane').length,1);assert.equal(a.d.querySelectorAll('.clip').length,0);a.d.querySelector('[data-action="tap"]').click();a.d.getElementById('block-key').value='up';a.d.getElementById('block-key').dispatchEvent(new a.dom.window.Event('change'));a.d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));const m=a.saved().macros[1];assert.equal(m.tracks.length,1);assert.equal(m.tracks[0].blocks[0].type,'tap');assert.equal(m.tracks[0].blocks[0].key,'up');assert.deepEqual(Array.from(a.M.flatten(m),e=>e.type),['key_down','key_up']);}finally{a.dom.window.close();}});
test('palette click inserts at playhead, inspector edits timing, undo restores and save keeps tracks',async()=>{const a=await editor(),d=a.d;try{
 d.querySelector('[data-action="move"]').click();assert.equal(d.querySelectorAll('.clip').length,4);
 d.getElementById('block-at').value=600;d.getElementById('block-at').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('block-x').value=1200;d.getElementById('block-x').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('add-track').click();assert.equal(d.querySelectorAll('.track-lane').length,2);
 d.getElementById('undo').click();assert.equal(d.querySelectorAll('.track-lane').length,1);
 d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(a.saved().schema_version,3);assert.equal(a.saved().macros[0].tracks[0].blocks.at(-1).at_ms,600);assert.equal(a.saved().macros[0].tracks[0].blocks.at(-1).x,1200);
 }finally{a.dom.window.close();}});
test('track geometry supports cross-track move, resize and absolute timing',async()=>{const a=await editor();try{const m=a.M.macro('test');m.tracks.push(a.M.track('轨道 2'));const b=a.M.place(m,'hold',m.tracks[0].id,103,10);assert.equal(b.at_ms,100);a.M.move(m,b.id,m.tracks[1].id,557,10);assert.equal(m.tracks[0].blocks.length,0);assert.equal(m.tracks[1].blocks[0].at_ms,560);a.M.resize(m,b.id,440,10);assert.equal(b.duration_ms,440);assert.equal(a.M.flatten(m)[1].at_ms,1000);}finally{a.dom.window.close();}});
test('palette drop inserts into an added track at the dropped absolute time',async()=>{const a=await editor();try{a.d.getElementById('add-track').click();const lane=a.d.querySelectorAll('.track-lane')[1];lane.getBoundingClientRect=()=>({left:150,top:0});const event=new a.dom.window.Event('drop',{bubbles:true,cancelable:true});Object.defineProperties(event,{clientX:{value:260},dataTransfer:{value:{getData:()=> 'tap'}}});lane.dispatchEvent(event);a.d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));const b=a.saved().macros[0].tracks[1].blocks.at(-1);assert.equal(b.type,'tap');assert.equal(b.at_ms,500);}finally{a.dom.window.close();}});
test('removed key actions cannot be created or previewed, including on muted tracks',async()=>{const a=await editor();try{for(const type of ['down','up']){assert.throws(()=>a.M.block(type),/未知动作/);for(const muted of [false,true]){const m=a.M.macro('test');m.tracks[0].muted=muted;m.tracks[0].blocks=[{id:'unsupported',type,key:'f',at_ms:100,duration_ms:0}];assert.ok(a.M.errors(m).some(x=>x.includes('未知动作')));assert.throws(()=>a.M.flatten(m),/未知动作/);}}}finally{a.dom.window.close();}});
