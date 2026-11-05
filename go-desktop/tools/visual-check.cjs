// Test our local editor in an isolated headless browser. No user browser profile
// or real input injection is involved. The test owns its temporary HTTP server.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const http=require('node:http');
const fs=require('node:fs');
(async()=>{
 const frontend=path.resolve(__dirname,'../frontend');
 const server=http.createServer((request,response)=>{const pathname=new URL(request.url,'http://localhost').pathname;const file=path.resolve(frontend,'.'+(pathname==='/'?'/index.html':pathname));if(!file.startsWith(frontend+path.sep)){response.writeHead(403).end();return;}fs.readFile(file,(error,data)=>{if(error){response.writeHead(404).end();return;}const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.jpg':'image/jpeg'};response.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});response.end(data);});});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);await page.locator('.clip').first().waitFor();
  await page.screenshot({path:path.join(__dirname,'../build/studio-overview.png')});
  const palette=page.locator('[data-action="tap"]'),lane=page.locator('.track-lane').nth(2);
  const bounds=await lane.boundingBox();
  await palette.dragTo(lane,{targetPosition:{x:220,y:45}});
  assert.equal(await page.locator('.clip').count(),4);
  await page.locator('.clip.selected').click();
  await page.locator('#block-key').selectOption('3');
  await page.locator('#block-duration').fill('100');await page.locator('#block-duration').press('Tab');
  const clip=page.locator('.clip.selected');const before=await clip.boundingBox();
  const grip=Math.min(12,before.width/3);
  await page.mouse.move(before.x+grip,before.y+15);await page.mouse.down();await page.mouse.move(before.x+grip+100,before.y-80,{steps:10});await page.mouse.up();
  const after=await page.locator('.clip.selected').boundingBox();assert.ok(after.x>before.x+50,'drag did not move block in time');
  const resize=page.locator('.clip.selected .resize-handle');const handle=await resize.boundingBox();
  await page.mouse.move(handle.x+3,handle.y+12);await page.mouse.down();await page.mouse.move(handle.x+70,handle.y+12,{steps:8});await page.mouse.up();
  assert.ok(Number(await page.locator('#block-duration').inputValue())>100,'resize did not extend block');
  await page.screenshot({path:path.join(__dirname,'../build/studio-editing.png')});
  await page.locator('#save-button').click();
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-studio-draft')));
  assert.equal(saved.schema_version,3);assert.equal(saved.macros[0].tracks[1].blocks.length,2,'cross-track drag did not change target track');
  await page.locator('#settings-button').click();
  await page.locator('#settings-dialog').waitFor({state:'visible'});
  await page.locator('[data-setting="process_name"]').fill('Game.exe');
  await page.locator('[data-setting="process_name"]').press('Tab');
  await page.locator('#settings-done').click();
  await page.locator('#save-button').click();
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('d4-studio-draft')).process_name),'Game.exe');
  assert.deepEqual(errors,[]);
  await page.setViewportSize({width:1200,height:800});await page.screenshot({path:path.join(__dirname,'../build/studio-1200.png')});
  console.log('Headless browser: palette drag, cross-track move, resize, settings, save and JS errors passed. Screenshots in build/.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
