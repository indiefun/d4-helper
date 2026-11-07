const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
async function editor(transform){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'frontend/index.html'),'utf8'),{runScripts:'outside-only',url:'http://localhost',pretendToBeVisual:true});
 dom.window.structuredClone=structuredClone;
 for(const file of ['model.js','graph-model.js'])dom.window.eval(fs.readFileSync(path.join(root,'frontend',file),'utf8'));
 const G=dom.window.GraphModel,M=dom.window.TimelineModel;let saved;const doc=G.demo();if(transform)transform(doc,G,M);
 dom.window.go={main:{App:{LoadConfiguration:async()=>({content:JSON.stringify(doc)}),StopAll:async()=>{},SaveAndApply:async raw=>{saved=JSON.parse(raw);return {content:raw};}}}};
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/app.js'),'utf8'));
 await new Promise(resolve=>setImmediate(resolve));
 return {dom,d:dom.window.document,G,M,saved:()=>saved};
}
function change(el,value){el.value=value;el.dispatchEvent(new el.ownerDocument.defaultView.Event('change',{bubbles:true}));}
test('node parameters retime successors, save and undo keep graph authoring',async()=>{
 const a=await editor(),d=a.d;try{
  assert.equal(d.querySelectorAll('.flow-node').length,4);assert.equal(d.querySelectorAll('.track-lane').length,0);
  const wait=d.querySelector('[data-key="wait_ms"]');change(wait,'900');
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  const m=a.saved().macros[0],hold=m.graph.nodes.find(n=>n.type==='hold');assert.equal(m.duration_ms,1760);assert.equal(m.tracks.flatMap(t=>t.blocks).find(b=>b.id===hold.id).at_ms,960);
  d.getElementById('undo').click();assert.equal(d.querySelector('[data-key="wait_ms"]').value,'300');
  d.getElementById('redo').click();assert.equal(d.querySelector('[data-key="wait_ms"]').value,'900');
 }finally{a.dom.window.close();}
});
test('palette insertion wires the new node between selection and successor',async()=>{
 const a=await editor(),d=a.d;try{
  d.querySelector('[data-node-type="wait"]').click();assert.equal(d.querySelectorAll('.flow-node').length,5);
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  const m=a.saved().macros[0],s=a.G.schedule(m.graph);assert.equal(s.duration,1660);assert.equal(s.outgoing.get(m.graph.nodes[0].id).length,1);assert.equal(new Set(m.graph.nodes.map(n=>`${n.x},${n.y}`)).size,5);
  d.getElementById('remove-node').click();assert.equal(d.querySelectorAll('.flow-node').length,4);
  d.getElementById('undo').click();assert.equal(d.querySelectorAll('.flow-node').length,5);
 }finally{a.dom.window.close();}
});
test('invalid edits and cycles reject atomically with actionable feedback',async()=>{
 const a=await editor(),d=a.d;try{
  change(d.querySelector('[data-key="wait_ms"]'),'-1');assert.equal(d.querySelector('[data-key="wait_ms"]').value,'300');assert.match(d.getElementById('notice').textContent,/等待时间/);
  const g=a.G.demo().macros[0].graph,from=g.nodes.at(-1).id,to=g.nodes[1].id,before=JSON.stringify(g);
  assert.throws(()=>a.G.connect(g,from,to));assert.equal(JSON.stringify(g),before);
  const cyc={version:1,nodes:[a.G.node('start'),a.G.node('wait'),a.G.node('wait')],edges:[]};cyc.edges=[{from:cyc.nodes[1].id,to:cyc.nodes[2].id},{from:cyc.nodes[2].id,to:cyc.nodes[1].id}];assert.throws(()=>a.G.schedule(cyc),/成环/);
 }finally{a.dom.window.close();}
});
test('timeline conversion preserves parallel actions, waits, paths, muted state and looping',async()=>{
 const a=await editor(),{G,M}=a;try{
  const m=M.demo().macros[0];m.loop=true;m.loop_wait_ms=700;M.syncTiming(m);const expected=M.flatten(m).map(e=>[e.at_ms,e.type,e.key]);const duration=m.duration_ms;
  G.fromTimeline(m);assert.deepEqual(M.flatten(m).map(e=>[e.at_ms,e.type,e.key]),expected);assert.equal(m.duration_ms,duration);
  const t=M.track('录制');t.muted=true;t.blocks=[{...M.block('move',200),path:[{at_ms:0,x:0,y:0},{at_ms:300,x:10,y:20}]}];const rec=M.macro();rec.tracks=[t];const original=JSON.stringify(rec);G.fromTimeline(rec);assert.equal(rec.graph.nodes.find(n=>n.type==='move').muted,true);assert.equal(rec.graph.nodes.find(n=>n.type==='move').action.path.length,2);assert.equal(rec.duration_ms,500);assert.equal(JSON.parse(original).tracks[0].blocks[0].at_ms,200);
 }finally{a.dom.window.close();}
});
test('parallel waits for longest branch at join and includes trailing wait',async()=>{
 const a=await editor(),{G}=a;try{
  const m=G.macro(),g=m.graph,s=g.nodes[0];const fork=G.add(g,'parallel',s.id),hold=G.add(g,'hold',fork.id);hold.action.duration_ms=100;
  const wait=G.add(g,'wait',fork.id);wait.wait_ms=300;const tap=G.add(g,'tap',wait.id),join=G.add(g,'join',hold.id);G.connect(g,tap.id,join.id);const last=G.add(g,'tap',join.id);last.action.duration_ms=50;const tail=G.add(g,'wait',last.id);tail.wait_ms=200;
  const result=G.materialize(m);assert.equal(result.times.get(join.id).at,360);assert.equal(m.duration_ms,610);
  const idle=G.add(g,'hold');idle.action.duration_ms=999;G.materialize(m);assert.equal(m.duration_ms,610);assert.equal(m.tracks.flatMap(t=>t.blocks).length,3);
 }finally{a.dom.window.close();}
});
test('duplicate nodes stay disconnected and macro duplicate remaps connections',async()=>{
 const a=await editor(),d=a.d;try{
  const hold=d.querySelector('.flow-node:has([data-key="key"])');hold.focus();
  d.getElementById('duplicate-node').click();assert.equal(d.querySelectorAll('.flow-node.disconnected').length,1);
  d.querySelector('.flow-node.mint').focus();d.getElementById('duplicate-macro').click();
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));
  const [first,second]=a.saved().macros;assert.equal(second.trigger,'none');assert.notEqual(first.id,second.id);assert.equal(second.graph.nodes.some(n=>first.graph.nodes.some(o=>o.id===n.id)),false);a.G.schedule(second.graph);
 }finally{a.dom.window.close();}
});
test('legacy workspace loads as nodes without saving until requested',async()=>{
 const a=await editor((doc,G,M)=>{doc.macros=M.demo().macros;});try{
  assert.ok(a.d.querySelectorAll('.flow-node').length>4);assert.equal(a.saved(),undefined);assert.equal(a.d.getElementById('save-state').textContent,'已保存');
 }finally{a.dom.window.close();}
});

test('undoing new or duplicated macros restores the original workspace',async()=>{
 const a=await editor(),d=a.d;try{
  d.getElementById('new-macro').click();assert.equal(d.querySelectorAll('[data-macro]').length,2);
  d.getElementById('undo').click();assert.equal(d.querySelectorAll('[data-macro]').length,1);assert.equal(d.getElementById('macro-name').textContent,'技能连招');
  d.getElementById('redo').click();assert.equal(d.querySelectorAll('[data-macro]').length,2);assert.equal(d.getElementById('macro-name').textContent,'技能连招');
  d.getElementById('save-button').click();await new Promise(resolve=>setImmediate(resolve));assert.equal(a.saved().macros.length,2);
 }finally{a.dom.window.close();}
});
