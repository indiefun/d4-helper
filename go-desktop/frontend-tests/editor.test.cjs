const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function editor({legacy=false,transform,backend={}}={}){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'frontend/index.html'),'utf8'),{runScripts:'outside-only',url:'http://localhost',pretendToBeVisual:true});
 dom.window.structuredClone=structuredClone;dom.window.confirm=()=>true;
 for(const file of ['model.js','graph-model.js','flow-model.js'])dom.window.eval(fs.readFileSync(path.join(root,'frontend',file),'utf8'));
 const {FlowModel:F,TimelineModel:M,GraphModel:G}=dom.window;
 const doc=M.demo();if(!legacy){doc.macros=G.demo().macros.map(m=>F.toMacro(F.fromMacro(m)));}
 if(transform)transform(doc,{F,M,G});
 let saved,stops=0,runs=0,armed=0;
 dom.window.go={main:{App:{LoadConfiguration:async()=>({content:JSON.stringify(doc)}),StopAll:async()=>{stops++;},SaveAndApply:async raw=>{saved=JSON.parse(raw);return{content:raw};},SetArmed:async()=>{armed++;},TryMacro:async()=>{runs++;},...backend}}};
 dom.window.eval(fs.readFileSync(path.join(root,'frontend/app.js'),'utf8'));await tick();
 return{dom,d:dom.window.document,F,M,G,doc,saved:()=>saved,stops:()=>stops,runs:()=>runs,armed:()=>armed};
}
function change(el,value){el.value=value;el.dispatchEvent(new el.ownerDocument.defaultView.Event('change',{bubbles:true}));}
function select(a,index){a.d.querySelectorAll('[data-node]')[index].querySelector('.node-heading').click();}
test('separate drawers, five actions, all edits stay on nodes',async()=>{const a=await editor();try{
 const d=a.d;assert.equal(d.querySelectorAll('[data-type]').length,5);assert.equal(d.querySelector('.inspector'),null);assert.equal(d.querySelectorAll('[data-node]').length,3);assert.equal(a.stops(),0);
 d.querySelector('[data-drawer="macros"]').click();assert.equal(d.getElementById('nodes-drawer').hidden,true);assert.equal(d.getElementById('macros-drawer').hidden,false);
 d.querySelector('[data-drawer="macros"]').click();assert.equal(d.getElementById('drawer').hidden,true);
 }finally{a.dom.window.close();}});
test('saving retains undo and graph v2 round-trip retimes successors',async()=>{const a=await editor();try{
 const d=a.d;change(d.querySelector('.wait [data-field="duration"]'),'900');assert.equal(a.stops(),1);
 d.getElementById('save-button').click();await tick();const m=a.saved().macros[0];assert.equal(m.graph.version,2);assert.equal(m.duration_ms,1760);assert.equal(a.F.expand(a.F.fromMacro(m).body).events.find(e=>e.type==='hold').at,960);
 d.getElementById('undo').click();assert.equal(d.querySelector('.wait [data-field="duration"]').value,'300');d.getElementById('redo').click();assert.equal(d.querySelector('.wait [data-field="duration"]').value,'900');
 }finally{a.dom.window.close();}});
test('local repeats become real runtime data and stop invalid edits atomically',async()=>{const a=await editor();try{
 const d=a.d;select(a,0);d.getElementById('make-repeat').click();change(d.querySelector('[data-group-count]'),'4');change(d.querySelector('[data-group-gap]'),'50');
 assert.equal(d.getElementById('preview-duration').textContent,'1.49 s');change(d.querySelector('[data-group-count]'),'1000');assert.equal(d.querySelector('[data-group-count]').value,'4');
 d.getElementById('save-button').click();await tick();const first=a.saved().macros[0].graph.root.items[0];assert.equal(first.type,'repeat');assert.equal(first.count,4);assert.equal(first.gap_ms,50);
 }finally{a.dom.window.close();}});
test('legacy timeline migration preserves timestamps, muted actions and path data',async()=>{const a=await editor({legacy:true,transform:(doc,{M})=>{
 doc.macros[0].loop=true;doc.macros[0].loop_wait_ms=700;const t=M.track('轨迹');t.muted=true;t.blocks=[{...M.block('move',500),path:[{at_ms:0,x:400,y:500},{at_ms:300,x:800,y:500}]}];doc.macros[0].tracks.push(t);M.syncTiming(doc.macros[0]);
 }});try{
 assert.equal(a.saved(),undefined);a.d.getElementById('save-button').click();await tick();const m=a.saved().macros[0],ui=a.F.fromMacro(m),plan=a.F.expand(ui.body);assert.equal(m.duration_ms,2100);assert.equal(plan.duration,1400);
 assert.deepEqual(Array.from(plan.events.filter(e=>e.type!=='wait').map(e=>e.at)).sort((a,b)=>a-b),[200,200,500,800]);let recorded;for(const b of ui.body.items[0].branches)for(const n of b.items)if(n.type==='move')recorded=n;assert.equal(recorded.path.length,2);assert.equal(recorded.disabled,true);
 }finally{a.dom.window.close();}});
test('v1 graph trailing waits and source authoring survive migration',async()=>{const a=await editor({transform:(doc,{G})=>{
 const m=G.demo().macros[0];G.add(m.graph,'wait',m.graph.nodes.at(-1).id).wait_ms=120;G.materialize(m);doc.macros=[m];
 }});try{
 a.d.getElementById('save-button').click();await tick();const m=a.saved().macros[0];assert.equal(m.duration_ms,1280);assert.equal(m.graph.source_v1.version,1);assert.equal(a.F.expand(a.F.fromMacro(m).body).duration,1280);
 }finally{a.dom.window.close();}});
test('recorded path speed changes retain relative points',async()=>{const a=await editor({legacy:true,transform:(doc,{M})=>{
 const m=M.macro('轨迹');m.tracks[0].blocks=[{...M.block('move',0),path:[{at_ms:0,x:400,y:500},{at_ms:150,x:600,y:500},{at_ms:300,x:800,y:500}]}];M.syncTiming(m);doc.macros=[m];
 }});try{
  assert.match(a.d.querySelector('.node-card.move').textContent,/3 个录制轨迹点/);change(a.d.querySelector('.node-card.move [data-field="duration"]'),'600');a.d.getElementById('save-button').click();await tick();const b=a.saved().macros[0].graph.root.items[0].action;assert.deepEqual(b.path.map(p=>p.at_ms),[0,300,600]);
 }finally{a.dom.window.close();}});
test('run saves first and never starts after backend validation failure',async()=>{let saved=false,started=false;const a=await editor({backend:{SaveAndApply:async()=>{saved=true;throw Error('鼠标移动动作重叠');},TryMacro:async()=>{started=true;}}});try{
 change(a.d.querySelector('.wait [data-field="duration"]'),'400');a.d.getElementById('run-button').click();await tick();assert.equal(saved,true);assert.equal(started,false);assert.equal(a.armed(),0);assert.match(a.d.getElementById('toast').textContent,/移动动作重叠/);
 }finally{a.dom.window.close();}});
test('successful run saves structured changes and calls Go execution',async()=>{const a=await editor();try{
 select(a,0);a.d.getElementById('make-repeat').click();a.d.getElementById('run-button').click();await tick();assert.equal(a.saved().macros[0].graph.root.items[0].type,'repeat');assert.equal(a.runs(),1);assert.equal(a.armed(),1);
 }finally{a.dom.window.close();}});
test('undo new macro restores original and duplicate clears trigger',async()=>{const a=await editor();try{
 const d=a.d;d.getElementById('new-macro').click();assert.equal(d.querySelectorAll('[data-macro]').length,2);d.getElementById('undo').click();assert.equal(d.querySelectorAll('[data-macro]').length,1);d.getElementById('macro-options').click();d.getElementById('duplicate-macro').click();d.getElementById('save-button').click();await tick();const [first,second]=a.saved().macros;assert.notEqual(first.id,second.id);assert.equal(second.trigger,'none');assert.notEqual(first.graph.root.id,second.graph.root.id);
 }finally{a.dom.window.close();}});
test('expansion rejects huge nested repetitions before generating preview',async()=>{const a=await editor();try{
 let n={id:'scroll',type:'scroll',duration:0,delta:120};for(let i=0;i<5;i++)n={id:'r'+i,type:'repeat',count:100,gap:0,body:{id:'b'+i,type:'sequence',items:[n]}};
 assert.throws(()=>a.F.expand({id:'root',type:'sequence',items:[n]}),/超过/);
 }finally{a.dom.window.close();}});
test('poll receives recordings and keeps original movement points',async()=>{let sent=false;const raw={id:'recorded',name:'新录制',enabled:true,trigger:'none',loop:false,loop_wait_ms:0,duration_ms:200,tracks:[{id:'t',name:'mouse',muted:false,blocks:[{id:'b',type:'move',at_ms:0,duration_ms:200,x:100,y:200,from_x:0,from_y:0,path:[{at_ms:0,x:0,y:0},{at_ms:200,x:100,y:200}]}]}]};const a=await editor({backend:{Poll:async()=>({new_recordings:sent?[]:(sent=true,[raw])})}});try{
 assert.match(a.d.getElementById('macro-title').textContent,/新录制/);a.d.getElementById('save-button').click();await tick();const recorded=a.saved().macros.find(m=>m.id==='recorded');assert.equal(recorded.graph.root.items[0].action.path.length,2);
 }finally{a.dom.window.close();}});
