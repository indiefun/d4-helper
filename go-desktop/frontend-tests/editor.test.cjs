const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
async function editor(transform){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'frontend/index.html'),'utf8'),{runScripts:'outside-only',url:'http://localhost',pretendToBeVisual:true});
 dom.window.structuredClone=structuredClone;
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/model.js'),'utf8'));
 let saved;const document=dom.window.TimelineModel.demo();if(transform)transform(document);
 dom.window.go={main:{App:{LoadConfiguration:async()=>({path:'workspace.timeline.json',content:JSON.stringify(document)}),StopAll:async()=>{},SaveAndApply:async raw=>{saved=JSON.parse(raw);return {path:'workspace.timeline.json',content:raw};}}}};
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/app.js'),'utf8'));
 await new Promise(resolve=>setImmediate(resolve));
 return {dom,d:dom.window.document,M:dom.window.TimelineModel,saved:()=>saved};
}
test('starter macro uses two parallel tracks and the palette exposes only paired key actions, movement and scroll',async()=>{const a=await editor();try{assert.equal(a.d.querySelectorAll('.track-lane').length,2);assert.equal(a.d.querySelectorAll('.clip').length,3);assert.deepEqual(Array.from(a.d.querySelectorAll('[data-action]'),e=>e.dataset.action),['tap','hold','move','scroll']);assert.equal(a.d.querySelector('#action'),null);assert.equal(a.d.querySelector('#profiles'),null);assert.equal(a.d.querySelector('#loop').checked,false);}finally{a.dom.window.close();}});

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
 d.getElementById('add-track').click();d.querySelector('[data-action="move"]').click();assert.equal(d.querySelectorAll('.clip').length,4);
 d.getElementById('block-at').value=600;d.getElementById('block-at').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('block-x').value=1200;d.getElementById('block-x').dispatchEvent(new a.dom.window.Event('change'));
 d.getElementById('add-track').click();assert.equal(d.querySelectorAll('.track-lane').length,4);
 d.getElementById('undo').click();assert.equal(d.querySelectorAll('.track-lane').length,3);
 d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(a.saved().schema_version,3);assert.equal(a.saved().macros[0].tracks[2].blocks.at(-1).at_ms,600);assert.equal(a.saved().macros[0].tracks[2].blocks.at(-1).x,1200);
 }finally{a.dom.window.close();}});
test('track geometry supports cross-track move, resize and absolute timing',async()=>{const a=await editor();try{const m=a.M.macro('test');m.tracks.push(a.M.track('轨道 2'));const b=a.M.place(m,'hold',m.tracks[0].id,103,10);assert.equal(b.at_ms,100);a.M.move(m,b.id,m.tracks[1].id,557,10);assert.equal(m.tracks[0].blocks.length,0);assert.equal(m.tracks[1].blocks[0].at_ms,560);a.M.resize(m,b.id,440,10);assert.equal(b.duration_ms,440);assert.equal(a.M.flatten(m)[1].at_ms,1000);}finally{a.dom.window.close();}});
test('palette drop inserts into an added track at the dropped absolute time',async()=>{const a=await editor();try{a.d.getElementById('add-track').click();const lane=a.d.querySelectorAll('.track-lane')[2];lane.getBoundingClientRect=()=>({left:150,top:0});const event=new a.dom.window.Event('drop',{bubbles:true,cancelable:true});Object.defineProperties(event,{clientX:{value:260},dataTransfer:{value:{getData:()=> 'tap'}}});lane.dispatchEvent(event);a.d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));const b=a.saved().macros[0].tracks[2].blocks.at(-1);assert.equal(b.type,'tap');assert.equal(b.at_ms,500);}finally{a.dom.window.close();}});
test('removed key actions cannot be created or previewed, including on muted tracks',async()=>{const a=await editor();try{for(const type of ['down','up']){assert.throws(()=>a.M.block(type),/未知动作/);for(const muted of [false,true]){const m=a.M.macro('test');m.tracks[0].muted=muted;m.tracks[0].blocks=[{id:'unsupported',type,key:'f',at_ms:100,duration_ms:0}];assert.ok(a.M.errors(m).some(x=>x.includes('未知动作')));assert.throws(()=>a.M.flatten(m),/未知动作/);}}}finally{a.dom.window.close();}});

test('track controls toggle execution, reorder both ways, confirm deletion and undo',async()=>{
 const a=await editor(),d=a.d;try{
  const original=d.querySelector('[data-track-row]').dataset.trackRow;
  assert.equal(d.querySelector('[data-track-toggle]').getAttribute('aria-checked'),'true');
  assert.equal(d.querySelector('[data-track-toggle]').textContent,'');
  d.querySelector('[data-track-toggle]').click();
  assert.equal(d.querySelector('[data-track-toggle]').getAttribute('aria-checked'),'false');
  assert.equal(d.querySelectorAll('.event-chip').length,2);
  d.querySelector('[data-track-toggle]').click();assert.equal(d.querySelectorAll('.event-chip').length,6);
  assert.ok(d.querySelector('[data-track-up]').disabled);assert.ok(d.querySelectorAll('[data-track-down]')[1].disabled);
  d.getElementById('add-track').click();
  d.querySelector('[data-track-down]').click();
  assert.equal(d.querySelectorAll('[data-track-row]')[1].dataset.trackRow,original);
  d.querySelectorAll('[data-track-up]')[1].click();
  assert.equal(d.querySelector('[data-track-row]').dataset.trackRow,original);
  let message='';a.dom.window.confirm=text=>{message=text;return false;};
  d.querySelector('[data-track-remove]').click();assert.equal(d.querySelectorAll('.track-lane').length,3);assert.match(message,/2 个动作/);
  a.dom.window.confirm=()=>true;d.querySelector('[data-track-remove]').click();
  assert.equal(d.querySelectorAll('.clip').length,1);
  d.getElementById('undo').click();assert.equal(d.querySelectorAll('.clip').length,3);
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(a.saved().macros[0].tracks[0].id,original);assert.equal(a.saved().macros[0].tracks[0].muted,false);
 }finally{a.dom.window.close();}
});

test('Ctrl wheel zooms around the pointer without changing macros or intercepting normal scrolling',async()=>{
 const a=await editor(),d=a.d;try{
  const scroll=d.getElementById('timeline-scroll');Object.defineProperty(scroll,'clientWidth',{value:700});
  scroll.getBoundingClientRect=()=>({left:100});scroll.scrollLeft=100;
  const wheel=options=>{const e=new a.dom.window.WheelEvent('wheel',{bubbles:true,cancelable:true,clientX:548,deltaY:-100,...options});scroll.dispatchEvent(e);return e;};
  assert.equal(wheel().defaultPrevented,false);assert.equal(wheel({shiftKey:true}).defaultPrevented,false);
  assert.equal(d.getElementById('zoom-label').textContent,'100%');
  assert.equal(wheel({ctrlKey:true}).defaultPrevented,true);assert.equal(d.getElementById('zoom-label').textContent,'130%');
  assert.ok(Math.abs(scroll.scrollLeft-220)<.001);
  wheel({ctrlKey:true,deltaY:100});assert.equal(d.getElementById('zoom-label').textContent,'100%');assert.ok(Math.abs(scroll.scrollLeft-100)<.001);
  assert.equal(d.getElementById('save-state').textContent,'已保存');
  for(let i=0;i<20;i++)wheel({ctrlKey:true});assert.equal(d.getElementById('zoom-label').textContent,'1364%');
  for(let i=0;i<40;i++)wheel({ctrlKey:true,deltaY:100});assert.equal(d.getElementById('zoom-label').textContent,'9%');
 }finally{a.dom.window.close();}
});

test('placement is atomic, same-track overlaps reject, boundaries and cross-track concurrency work',async()=>{
 const a=await editor();try{
  const m=a.M.macro('test'),t=m.tracks[0],b=a.M.place(m,'hold',t.id,100,1);
  const before=JSON.stringify(m);assert.throws(()=>a.M.place(m,'tap',t.id,200,1),/不能重叠/);assert.equal(JSON.stringify(m),before);
  const adjacent=a.M.place(m,'tap',t.id,700,1);assert.equal(adjacent.at_ms,700);
  assert.equal(a.M.resize(m,b.id,2000,1),600);assert.equal(adjacent.at_ms,700);
  m.tracks.push(a.M.track());const concurrent=a.M.place(m,'tap',m.tracks[1].id,200,1);
  const snapshot=JSON.stringify(m);assert.throws(()=>a.M.move(m,concurrent.id,t.id,200,1),/不能重叠/);assert.equal(JSON.stringify(m),snapshot);
  assert.equal(a.M.flatten(m).length,6);
  const instant=a.M.macro('points');a.M.place(instant,'scroll',instant.tracks[0].id,100,1);
  assert.throws(()=>a.M.place(instant,'scroll',instant.tracks[0].id,100,1),/不能重叠/);
  a.M.place(instant,'scroll',instant.tracks[0].id,101,1);
 }finally{a.dom.window.close();}
});

test('conflicting inspector and palette edits leave timing and undo intact',async()=>{
 const a=await editor(),d=a.d;try{
  // Adding a 600ms hold at 0ms would cover the first skill click.
  d.querySelector('[data-action="hold"]').click();assert.equal(d.querySelectorAll('.clip').length,3);
  assert.equal(d.getElementById('save-state').textContent,'已保存');assert.ok(d.getElementById('undo').disabled);
  d.querySelector('.clip.tap').dispatchEvent(new a.dom.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  d.getElementById('block-at').value=800;d.getElementById('block-at').dispatchEvent(new a.dom.window.Event('change'));
  assert.equal(d.getElementById('block-at').value,'200');assert.ok(d.getElementById('undo').disabled);
  d.getElementById('block-duration').value=1000;d.getElementById('block-duration').dispatchEvent(new a.dom.window.Event('change'));
  assert.equal(d.getElementById('block-duration').value,'600');
  d.getElementById('undo').click();assert.equal(d.getElementById('save-state').textContent,'未保存');
 }finally{a.dom.window.close();}
});

test('old overlaps are offered an explicit reversible split with unchanged events',async()=>{
 const a=await editor(doc=>{const m=doc.macros[0];m.tracks[0].blocks.push(...m.tracks[1].blocks);m.tracks.splice(1);}),d=a.d;
 try{
  assert.equal(d.getElementById('overlap-notice').hidden,false);
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));assert.equal(a.saved(),undefined);
  d.getElementById('split-tracks').click();assert.equal(d.getElementById('overlap-notice').hidden,true);assert.equal(d.querySelectorAll('.track-lane').length,2);
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  const m=a.saved().macros[0];assert.equal(m.tracks.some(a.M.trackOverlaps),false);
  assert.deepEqual(Array.from(a.M.flatten(m),e=>e.at_ms),[200,200,260,800,860,1400]);
  // Save clears history; split itself is undoable before saving.
 }finally{a.dom.window.close();}
 const b=await editor(doc=>{doc.macros[0].tracks[0].blocks.push(...doc.macros[0].tracks[1].blocks);doc.macros[0].tracks.splice(1);});
 try{b.d.getElementById('split-tracks').click();b.d.getElementById('undo').click();assert.equal(b.d.getElementById('overlap-notice').hidden,false);}finally{b.dom.window.close();}
});

test('copy finds free space and resizing a recorded path stops at its neighbor',async()=>{
 const a=await editor();try{
  const m=a.M.macro('test'),t=m.tracks[0],b=a.M.place(m,'tap',t.id,0,1);
  a.M.place(m,'hold',t.id,100,1);const copy=a.M.cloneBlock(m,b.id);assert.equal(copy.at_ms,700);assert.equal(a.M.trackOverlaps(t),false);
  const path=a.M.macro('path'),p=a.M.place(path,'move',path.tracks[0].id,0,1);p.path=[{at_ms:0,x:0,y:0},{at_ms:300,x:10,y:10}];
  a.M.place(path,'tap',path.tracks[0].id,400,1);a.M.resize(path,p.id,1000,1);assert.equal(p.duration_ms,400);assert.equal(p.path[1].at_ms,400);
 }finally{a.dom.window.close();}
});

test('out-of-range timing edits reject atomically instead of rendering an unbounded ruler',async()=>{
 const a=await editor(),d=a.d;try{
  const m=a.M.macro(),t=m.tracks[0],b=a.M.place(m,'tap',t.id,100,1),before=JSON.stringify(m);
  for(const at of [3600000,Infinity,NaN])assert.throws(()=>a.M.move(m,b.id,t.id,at,1),/1 小时/);
  for(const duration of [3600000,Infinity,NaN])assert.throws(()=>a.M.resize(m,b.id,duration,1),/1 小时/);
  assert.throws(()=>a.M.setDuration(m,3600001),/1 小时/);assert.equal(JSON.stringify(m),before);
  d.getElementById('duration').value='3600001';d.getElementById('duration').dispatchEvent(new a.dom.window.Event('change'));
  assert.equal(d.getElementById('duration').value,'2000');assert.ok(d.getElementById('undo').disabled);
 }finally{a.dom.window.close();}
});
