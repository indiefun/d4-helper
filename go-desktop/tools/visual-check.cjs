// Uses an isolated headless Edge instance and temporary server; no input injection.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const http=require('node:http');
const fs=require('node:fs');
(async()=>{
 const frontend=path.resolve(__dirname,'../frontend'),build=path.resolve(__dirname,'../build');fs.mkdirSync(build,{recursive:true});
 const server=http.createServer((request,response)=>{const pathname=new URL(request.url,'http://localhost').pathname;const file=path.resolve(frontend,'.'+(pathname==='/'?'/index.html':pathname));if(!file.startsWith(frontend+path.sep)){response.writeHead(403).end();return;}fs.readFile(file,(error,data)=>{if(error){response.writeHead(404).end();return;}const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};response.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});response.end(data);});});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);await page.locator('.flow-node').first().waitFor();assert.equal(await page.locator('.flow-node').count(),4);
  await page.screenshot({path:path.join(build,'node-editor-overview.png')});
  // Inline editing updates downstream timing, and undo remains usable after save.
  await page.locator('[data-key="wait_ms"]').fill('700');await page.locator('[data-key="wait_ms"]').press('Tab');
  await page.locator('#save-button').click();let saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-flow-draft')));assert.equal(saved.macros[0].duration_ms,1560);
  await page.locator('#undo').click();assert.equal(await page.locator('[data-key="wait_ms"]').inputValue(),'300');
  await page.locator('#redo').click();assert.equal(await page.locator('[data-key="wait_ms"]').inputValue(),'700');
  // Drag a node: moving its card changes only layout, never execution time.
  const hold=page.locator('.flow-node').filter({has:page.locator('strong',{hasText:'按住按键'})});const oldBox=await hold.boundingBox();
  await page.mouse.move(oldBox.x+50,oldBox.y+12);await page.mouse.down();await page.mouse.move(oldBox.x+90,oldBox.y+72,{steps:8});await page.mouse.up();
  await page.locator('#save-button').click();saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-flow-draft')));assert.equal(saved.macros[0].duration_ms,1560);assert.notEqual(saved.macros[0].graph.nodes.find(n=>n.type==='hold').y,180);
  // Zoom around cursor, then fit and pan the graph from empty canvas.
  const zoom=await page.locator('#zoom-label').textContent(),vp=await page.locator('#graph-viewport').boundingBox();await page.mouse.move(vp.x+vp.width/2,vp.y+vp.height/2);await page.mouse.wheel(0,-150);assert.notEqual(await page.locator('#zoom-label').textContent(),zoom);await page.locator('#fit').click();
  const transform=await page.locator('#graph-world').getAttribute('style');await page.mouse.move(vp.x+30,vp.y+vp.height-70);await page.mouse.down();await page.mouse.move(vp.x+70,vp.y+vp.height-45,{steps:5});await page.mouse.up();assert.notEqual(await page.locator('#graph-world').getAttribute('style'),transform);
  // Begin a fresh graph, add fork and two branches, then wire both into join.
  await page.locator('#new-macro').click();await page.locator('[data-node-type="parallel"]').click();await page.locator('[data-node-type="hold"]').click();
  await page.locator('.flow-node.mint').filter({has:page.locator('strong',{hasText:'并行',exact:true})}).locator('.node-header').click();
  await page.locator('[data-node-type="wait"]').click();await page.locator('[data-key="wait_ms"]').fill('900');await page.locator('[data-key="wait_ms"]').press('Tab');await page.locator('[data-node-type="tap"]').click();
  // Add an unconnected join via actual HTML drag and drop.
  await page.locator('#fit').click();const viewport=await page.locator('#graph-viewport').boundingBox();await page.locator('[data-node-type="join"]').dragTo(page.locator('#graph-viewport'),{targetPosition:{x:viewport.width-90,y:viewport.height-110}});assert.equal(await page.locator('.flow-node').count(),6);await page.locator('#fit').click();
  async function connect(fromType,toType){const source=page.locator('.flow-node').filter({has:page.locator('.node-header strong',{hasText:fromType,exact:true})}).locator('.port.out');const target=page.locator('.flow-node').filter({has:page.locator('.node-header strong',{hasText:toType,exact:true})}).locator('.port.in');const a=await source.boundingBox(),b=await target.boundingBox();await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:12});await page.mouse.up();}
  await connect('按住按键','汇合');await connect('点击按键','汇合');
  await page.locator('.flow-node').filter({has:page.locator('.node-header strong',{hasText:'汇合',exact:true})}).locator('.node-header').click();await page.locator('[data-node-type="wait"]').click();await page.locator('#fit').click();
  await page.locator('#save-button').click();saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-flow-draft')));const flow=saved.macros.at(-1);assert.equal(flow.duration_ms,1460);assert.equal(flow.graph.edges.length,7);assert.equal(flow.graph.nodes.length,7);
  await page.screenshot({path:path.join(build,'node-editor-parallel.png')});fs.writeFileSync(path.join(build,'browser-node-workspace.json'),JSON.stringify(saved,null,2));
  // Invalid multi-input connection must leave the last valid graph intact.
  await connect('点击按键','按住按键');assert.equal(await page.locator('[data-edge]').count(),7);assert.match(await page.locator('#notice').textContent(),/并行节点|汇合节点/);
  assert.equal(await page.locator('.flow-node .port.in').count(),6);
  // Delete an edge with keyboard, undo, and reopen persisted graph.
  await page.locator('[data-edge]').last().locator('.edge-hit').click({force:true});await page.keyboard.press('Delete');assert.equal(await page.locator('[data-edge]').count(),6);await page.locator('#undo').click();assert.equal(await page.locator('[data-edge]').count(),7);
  await page.locator('#save-button').click();await page.reload();await page.locator('.flow-node').first().waitFor();await page.locator('[data-macro]').last().click();assert.equal(await page.locator('.flow-node').count(),7);assert.equal(await page.locator('[data-edge]').count(),7);
  await page.locator('#preview-button').click();await page.locator('.playing').first().waitFor();await page.locator('#stop-button').click();assert.equal(await page.locator('.playing').count(),0);
  await page.setViewportSize({width:1200,height:780});await page.screenshot({path:path.join(build,'node-editor-1200.png')});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  // Legacy timeline import is in-memory only and preserves event timing.
  await page.evaluate(()=>{localStorage.removeItem('d4-flow-draft');localStorage.setItem('d4-studio-draft',JSON.stringify(TimelineModel.demo()));});await page.reload();await page.locator('.flow-node').first().waitFor();assert.ok(await page.locator('.flow-node').count()>4);await page.locator('#save-button').click();const migrated=await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-flow-draft')));assert.equal(migrated.macros[0].duration_ms,1400);assert.deepEqual(migrated.macros[0].tracks.flatMap(t=>t.blocks.map(b=>b.at_ms)).sort((a,b)=>a-b),[200,200,800]);
  assert.deepEqual(errors,[]);console.log('Node editor browser: inline timing, node drag, zoom/pan, palette drop, parallel/join wiring, undo, persistence, preview, responsive layout and legacy migration passed.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
