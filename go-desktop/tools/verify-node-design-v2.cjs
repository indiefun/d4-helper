// Review the standalone design in an isolated browser, using the same file URL
// a reviewer opens. No production workspace or input service is involved.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const build=path.resolve(__dirname,'../build');fs.mkdirSync(build,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(__dirname,'../design/node-editor-v2.html')).href);
  await page.locator('#drawer').waitFor({state:'visible'});
  assert.equal(await page.locator('#node-library [data-type]').count(),5);
  assert.equal(await page.locator('#nodes-drawer').isVisible(),true);
  assert.equal(await page.locator('#macros-drawer').isVisible(),false);
  assert.equal(await page.locator('.inspector').count(),0);
  assert.equal(await page.locator('#preview-duration').textContent(),'0.98 s');
  assert.equal(await page.evaluate(()=>DesignStudy.timing().events.find(e=>e.text==='等待 120 ms').at),800);
  await page.screenshot({path:path.join(build,'node-v2-drawers.png')});
  // Drawers are mutually exclusive; closing one leaves only the 64px rail.
  await page.locator('[data-drawer="macros"]').click();assert.equal(await page.locator('#nodes-drawer').isVisible(),false);assert.equal(await page.locator('#macros-drawer').isVisible(),true);
  await page.locator('[data-drawer="macros"]').click();assert.equal(await page.locator('#drawer').isVisible(),false);
  // Local repeat interval occurs only between rounds: 4*200+3*100=1100.
  await page.locator('[data-group-gap]').fill('100');await page.locator('[data-group-gap]').press('Tab');
  assert.equal(await page.locator('#preview-duration').textContent(),'1.28 s');
  await page.locator('#undo').click();assert.equal(await page.locator('#preview-duration').textContent(),'0.98 s');
  await page.locator('#run-mode').selectOption('continuous');assert.equal(await page.locator('.macro-loop').count(),1);assert.equal(await page.locator('#cycle-gap-field').isVisible(),true);
  assert.match(await page.locator('.macro-loop').textContent(),/整个宏.*持续循环/);
  await page.screenshot({path:path.join(build,'node-v2-scopes.png')});
  // Select the entire parallel scope and repeat it: local repeats may wrap
  // simultaneous branches without leaking outside their boundary.
  await page.locator('.parallel > .structure-header').click({position:{x:75,y:24}});
  await page.locator('#make-repeat').click();assert.equal(await page.locator('.repeat').count(),2);
  assert.equal(await page.locator('#preview-duration').textContent(),'2.58 s');
  await page.locator('#undo').click();assert.equal(await page.locator('#preview-duration').textContent(),'0.98 s');
  // Collapse affects display only.
  await page.locator('.repeat [data-collapse]').click();assert.equal(await page.locator('.scope-collapsed').count(),1);assert.equal(await page.locator('#preview-duration').textContent(),'0.98 s');await page.locator('.repeat [data-collapse]').click();
  // Build a new macro using the five-action drawer and convert two sequential
  // actions into concurrent branches with the selection toolbar.
  await page.locator('[data-drawer="macros"]').click();await page.locator('#new-macro').click();
  await page.locator('[data-type="tap"]').click();await page.locator('[data-type="hold"]').click();
  let cards=page.locator('[data-node]');await cards.nth(0).locator('.node-heading').click();await cards.nth(1).locator('.node-heading').click({modifiers:['Shift']});
  assert.equal(await page.locator('.node-card.selected').count(),2);await page.locator('#make-parallel').click();assert.equal(await page.locator('.parallel').count(),1);assert.equal(await page.locator('.lane').count(),2);assert.equal(await page.locator('#preview-duration').textContent(),'0.80 s');
  // Add a branch; its empty target sends subsequent palette actions there.
  await page.locator('[data-add-branch]').click();assert.equal(await page.locator('.lane').count(),3);await page.locator('[data-type="wait"]').click();assert.equal(await page.locator('.lane').last().locator('[data-node]').count(),1);
  // Cross-branch selection is rejected rather than changing semantics.
  await page.locator('.lane').nth(0).locator('.node-heading').click();await page.locator('.lane').nth(1).locator('.node-heading').click({modifiers:['Shift']});assert.equal(await page.locator('.node-card.selected').count(),1);assert.match(await page.locator('#toast').textContent(),/同一顺序/);
  // Inline validation rolls back; finite repetition includes its explicit gap.
  const duration=page.locator('.lane').nth(1).locator('[data-field="duration"]');await duration.fill('-1');await duration.press('Tab');assert.equal(await page.locator('.lane').nth(1).locator('[data-field="duration"]').inputValue(),'800');
  await page.locator('.lane').nth(0).locator('.node-heading').click();await page.locator('#make-repeat').click();
  assert.equal(await page.locator('.repeat').count(),1);await page.locator('[data-group-count]').fill('10');await page.locator('[data-group-count]').press('Tab');await page.locator('[data-group-gap]').fill('50');await page.locator('[data-group-gap]').press('Tab');assert.equal(await page.locator('#preview-duration').textContent(),'1.05 s');
  // Real HTML drag: move the wait from branch C into branch B.
  await page.locator('#close-drawer').click();await page.locator('#fit').click();
  const dragged=page.locator('.lane').nth(2).locator('[data-drag-node]'),target=page.locator('.lane').nth(1).locator('[data-node]');await dragged.dragTo(target);
  assert.equal(await page.locator('.lane').nth(2).locator('[data-node]').count(),0);assert.equal(await page.locator('.lane').nth(1).locator('[data-node]').count(),2);assert.equal(await page.locator('#preview-duration').textContent(),'1.10 s');
  // Independent local draft round trip retains nested structure and timing.
  await page.locator('#save-button').click();await page.reload();await page.locator('.parallel').waitFor();assert.equal(await page.locator('.repeat').count(),1);assert.equal(await page.locator('#preview-duration').textContent(),'1.10 s');
  assert.equal(await page.evaluate(()=>localStorage.getItem('d4-flow-draft')),null);
  assert.equal(await page.evaluate(()=>localStorage.getItem('d4-studio-draft')),null);
  // Preview highlights the running step. Whole-loop interval is reflected in
  // its own control; it is never appended to a local repeat's last round.
  await page.locator('#preview-toggle').click();await page.locator('.playing').first().waitFor();await page.locator('#preview-toggle').click();
  await page.locator('#expand-preview').click();assert.equal(await page.locator('#preview-events').isVisible(),true);
  // Box-select an actual contiguous range, then use the connection's insert
  // menu inside that repeat. The new action must stay inside its scope.
  await page.locator('[data-drawer="macros"]').click();await page.locator('[data-macro]').nth(1).click();await page.locator('#close-drawer').click();
  const a=await page.locator('[data-node]').nth(0).boundingBox(),b=await page.locator('[data-node]').nth(1).boundingBox();
  await page.keyboard.down('Shift');await page.mouse.move(a.x-9,a.y-9);await page.mouse.down();await page.mouse.move(b.x+b.width+9,b.y+b.height+9,{steps:10});await page.mouse.up();await page.keyboard.up('Shift');
  assert.equal(await page.locator('.node-card.selected').count(),2);await page.locator('#make-repeat').click();assert.equal(await page.locator('#preview-duration').textContent(),'1.88 s');
  await page.locator('.repeat [data-insert-seq]').last().click();assert.equal(await page.locator('[data-quick]').count(),5);await page.locator('[data-quick="wait"]').click();assert.equal(await page.locator('.repeat [data-node]').count(),3);assert.equal(await page.locator('#preview-duration').textContent(),'2.78 s');
  await page.evaluate(()=>localStorage.removeItem('d4-node-v2-design'));await page.reload();await page.locator('#nodes-drawer').waitFor({state:'visible'});await page.locator('#close-drawer').click();
  await page.setViewportSize({width:1200,height:800});await page.screenshot({path:path.join(build,'node-v2-1200.png')});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);
  const report={passed:true,checks:['exclusive drawers','five action types','no inspector','parallel max time','repeat interval boundaries','whole-macro scope','nested scopes','selection boundaries','box selection','in-scope insertion','validation rollback','drag between branches','independent save/reload','preview','1200px layout'],pageErrors:errors};
  fs.writeFileSync(path.join(build,'node-v2-design-verification.json'),JSON.stringify(report,null,2));
  console.log('V2 design: drawers, scopes, nesting, timing, selection, drag, validation, save/reload and preview passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
