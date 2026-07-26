/* #231 human-to-dreamer answers channel + #238 open survives tick.
   Usage: node answers.mjs <out> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
const OUT=process.argv[2], PORT=+(process.argv[3]||39890);
const checks=[]; const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
const target=join(dirname(OUT),'target');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ansPath=join(target,'.dreamwork','answers.md');
const seedTwoDup=(a,b)=>`# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): ${a}\n\n- **Duplicate?** → answered (2026-07-26): ${b}\n`;
const br=await chromium.launch({args:['--use-gl=swiftshader']});
const page=await br.newPage({viewport:{width:1100,height:800}}); const errs=[];
page.on('pageerror',e=>errs.push(String(e))); page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource')) errs.push(m.text())});
await page.goto(`http://127.0.0.1:${PORT}/answers`);
const exposed=await page.locator('#askbox').waitFor({state:'visible',timeout:5000}).then(()=>true).catch(()=>false);
ok('answers route exposes #askbox',exposed);
if(!exposed){console.log(checks.join('\n'));await br.close();process.exit(1)}
ok('route title',await page.locator('#chrome .htitle').textContent()==='answers');
ok('missing channel is calm',await page.locator('.aq').count()===0);
/* #247: live answerRecord render — missing aid omits BOTH attrs; present keeps both.
   Uses the page's own function (not fabricated HTML). No disk injection needed. */
const ar=await page.evaluate(()=>{
  if(typeof answerRecord!=='function') return {ok:false,why:'no answerRecord'};
  const missing=answerRecord({title:'T',body:'B'},true);
  const present=answerRecord({title:'T',body:'B',aid:'ans:test'},true);
  return {ok:true,missing,present};
});
ok('#247 answerRecord is page-global', ar.ok);
ok('#247 missing-aid render omits data-aid', ar.ok && !ar.missing.includes('data-aid'));
ok('#247 missing-aid render omits data-keep', ar.ok && !ar.missing.includes('data-keep'));
ok('#247 missing-aid is plain aq answered details',
  ar.ok && ar.missing.startsWith('<details class="aq answered"><summary>T</summary>'));
ok('#247 present-aid render has both attrs',
  ar.ok && ar.present.includes('data-aid="ans:test"') && ar.present.includes('data-keep="ans:test"'));
const asked='Does the live ask persist?\n## not a section\n- **not another entry**';
await page.locator('#askbox').fill(asked); await page.locator('#askbox').focus();
const tickResponse=await page.evaluate(()=>fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'do-next',text:'',from:'/answers'})}).then(r=>r.status));
ok('tick trigger accepted',tickResponse===200);
await page.waitForTimeout(2500);
ok('draft survives live tick',await page.locator('#askbox').inputValue()===asked);
ok('focus survives live tick',await page.evaluate(()=>document.activeElement?.id)==='askbox');
await page.locator('#askform button').click(); await page.waitForFunction(()=>document.querySelector('#askbox')?.value==='');
await page.waitForTimeout(400);
const pageText=await page.locator('#answersections').textContent();
ok('first ask creates exactly one open entry',await page.locator('.aq.open').count()===1);
ok('successful ask appears',pageText.includes('Does the live ask persist?'));
ok('multiline markdown meaning survives',pageText.includes('not a section')&&pageText.includes('not another entry'));
writeFileSync(ansPath, seedTwoDup('first loop answer.','second loop answer.'));
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===2,null,{timeout:5000});
const det=page.locator('.aq.answered').first(), neighbour=page.locator('.aq.answered').nth(1);
async function traceToggle(name){const p=[await neighbour.evaluate(e=>e.getBoundingClientRect().top)];await det.locator('summary').click();for(let i=0;i<30;i++){p.push(await neighbour.evaluate(e=>e.getBoundingClientRect().top));await page.waitForTimeout(30)}const end=p.at(-1),start=p[0],lo=Math.min(start,end)-1,hi=Math.max(start,end)+1;ok(name+' visits intermediate geometry',new Set(p.map(x=>Math.round(x))).size>3);ok(name+' has no overshoot',p.every(x=>x>=lo&&x<=hi));}
await traceToggle('answered disclosure open'); await traceToggle('answered disclosure close');

/* ── #238: open answered disclosure survives a real tick ───────────────────
   Load-bearing: prove the node was replaced (a no-op tick would pass every
   end-state check). Open is keyed to the logical record, not list position. */
async function forceTick(markEl){
  // markEl is the pre-tick element handle; after tick it must not be in document
  const pre = await markEl.evaluate(e=>{e.__dwMark=1; return {aid:e.dataset.aid||'', keep:e.dataset.keep||'', body:(e.querySelector('.aqbody')||{}).textContent||''};});
  await page.evaluate(()=>fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'do-next',text:'',from:'/answers'})}).then(r=>r.status));
  const t0=Date.now();
  let replaced=false, open=false, peerOpen=false, body='';
  while(Date.now()-t0<5200){
    const st=await page.evaluate(({aid,bodyNeedle})=>{
      const all=[...document.querySelectorAll('.aq.answered')];
      const byBody=all.find(e=>(e.querySelector('.aqbody')?.textContent||'').includes(bodyNeedle));
      const el=aid?document.querySelector(`.aq.answered[data-aid="${CSS.escape(aid)}"]`):byBody;
      const peer=all.find(e=>e!==el);
      return {
        replaced: !!(el && !el.__dwMark),
        open: !!(el && el.open),
        peerOpen: !!(peer && peer.open),
        body: el?(el.querySelector('.aqbody')?.textContent||''):'',
        count: all.length,
        aids: all.map(e=>e.dataset.aid||''),
      };
    }, {aid:pre.aid, bodyNeedle:'first loop answer'});
    if(st.replaced){replaced=true; open=st.open; peerOpen=st.peerOpen; body=st.body; break;}
    await sleep(50);
  }
  return {replaced, open, peerOpen, body, pre};
}

// Quiet tick: open first of two duplicate-title / different-body records
writeFileSync(ansPath, seedTwoDup('first loop answer.','second loop answer.'));
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===2,null,{timeout:5000});
// ensure both closed, then open the first only (first contains "first loop answer")
await page.evaluate(()=>[...document.querySelectorAll('.aq.answered')].forEach(d=>{d.open=false;}));
const firstByBody=page.locator('.aq.answered').filter({hasText:'first loop answer'}).first();
await firstByBody.locator('summary').click();
await page.waitForFunction(()=>{
  const el=[...document.querySelectorAll('.aq.answered')].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('first loop answer'));
  return el && el.open;
},{timeout:3000});
const quiet=await forceTick(firstByBody);
ok('#238 quiet tick replaced the answered node', quiet.replaced);
ok('#238 open survives quiet tick on same body', quiet.open && quiet.body.includes('first loop answer'));
ok('#238 closed peer stays closed after quiet tick', !quiet.peerOpen);

// Reorder: swap bodies on disk; the open state must follow the body, not index 0
writeFileSync(ansPath, seedTwoDup('first loop answer.','second loop answer.'));
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===2,null,{timeout:5000});
await page.evaluate(()=>[...document.querySelectorAll('.aq.answered')].forEach(d=>{d.open=false;}));
const openFirst=page.locator('.aq.answered').filter({hasText:'first loop answer'}).first();
await openFirst.locator('summary').click();
await page.waitForFunction(()=>{
  const el=[...document.querySelectorAll('.aq.answered')].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('first loop answer'));
  return el && el.open;
},{timeout:3000});
// rewrite with swapped order (second body first in file)
writeFileSync(ansPath, seedTwoDup('second loop answer.','first loop answer.'));
const t0=Date.now();
let reorder={replaced:false, openOnFirstBody:false, openOnIndex0:false, closedPeer:false};
while(Date.now()-t0<5200){
  const st=await page.evaluate(()=>{
    const all=[...document.querySelectorAll('.aq.answered')];
    if(all.length!==2) return null;
    const bodies=all.map(e=>(e.querySelector('.aqbody')?.textContent||''));
    // order changed when first row is the second answer text
    const reordered=bodies[0].includes('second loop answer')&&bodies[1].includes('first loop answer');
    if(!reordered) return {ready:false};
    const byFirst=[...all].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('first loop answer'));
    const bySecond=[...all].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('second loop answer'));
    return {
      ready:true,
      openOnFirstBody: !!(byFirst&&byFirst.open),
      openOnIndex0: !!(all[0]&&all[0].open),
      closedPeer: !(bySecond&&bySecond.open),
    };
  });
  if(st&&st.ready){reorder={replaced:true,...st}; break;}
  await sleep(50);
}
ok('#238 reorder tick replaced / reordered the list', reorder.replaced);
ok('#238 open follows body across reorder', reorder.openOnFirstBody);
ok('#238 open is not stuck on index 0 after reorder', !reorder.openOnIndex0);
ok('#238 closed peer stays closed after reorder', reorder.closedPeer);

// Deletion: open the second body; delete the first body from disk.
// #247: non-vacuous — capture preAid + marker; require a *new* node with the
// same aid still open. End-state "one open details" alone can pass without
// the tick replacing the survivor (no-op / wrong-record restore).
writeFileSync(ansPath, seedTwoDup('first loop answer.','second loop answer.'));
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===2,null,{timeout:5000});
await page.evaluate(()=>[...document.querySelectorAll('.aq.answered')].forEach(d=>{d.open=false;}));
const openSecond=page.locator('.aq.answered').filter({hasText:'second loop answer'}).first();
await openSecond.locator('summary').click();
await page.waitForFunction(()=>{
  const el=[...document.querySelectorAll('.aq.answered')].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('second loop answer'));
  return el && el.open;
},{timeout:3000});
const preDel=await openSecond.evaluate(e=>{
  e.__dwMark=1;
  return {
    aid:e.dataset.aid||'',
    keep:e.dataset.keep||'',
    body:(e.querySelector('.aqbody')||{}).textContent||'',
  };
});
ok('#247 deletion preAid present on open survivor', !!preDel.aid && preDel.aid===preDel.keep);
writeFileSync(ansPath, '# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): second loop answer.\n');
const t1=Date.now();
let del={ready:false, open:false, count:0, sameAid:false, replaced:false, connected:false, aid:''};
while(Date.now()-t1<5200){
  const st=await page.evaluate(({preAid, needle})=>{
    const all=[...document.querySelectorAll('.aq.answered')];
    if(all.length!==1) return {ready:false, count:all.length};
    const el=all[0];
    const body=el.querySelector('.aqbody')?.textContent||'';
    if(!body.includes(needle)) return {ready:false, count:1};
    const aid=el.dataset.aid||'';
    return {
      ready:true,
      open:!!el.open,
      count:1,
      sameAid:!!(preAid && aid===preAid),
      replaced:!(el.__dwMark),
      connected:!!el.isConnected,
      aid,
    };
  }, {preAid:preDel.aid, needle:'second loop answer'});
  if(st.ready){del=st; break;}
  await sleep(50);
}
ok('#238 deletion leaves the survivor', del.ready && del.count===1);
ok('#247 deletion survivor keeps same aid', del.sameAid && del.aid===preDel.aid);
ok('#247 deletion replaced connected survivor node', del.replaced && del.connected);
ok('#238 open survives deletion of the other record', del.open);

writeFileSync(ansPath,'# Questions for the dreamer\n\nprose no reader can see\n');
await page.waitForFunction(()=>document.body.textContent.includes('answers channel unreadable'),null,{timeout:5000});
ok('unreadable channel is loud and path-specific',await page.locator('.qhealth').evaluate(e=>e.textContent.includes('.dreamwork/answers.md')&&e.querySelector('a')?.getAttribute('href')?.includes('answers.md')));
writeFileSync(ansPath,'# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): first.\n');
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===1,null,{timeout:5000});
await page.route('**/ask',r=>r.fulfill({status:409,body:'refused'})); await page.locator('#askbox').fill('Keep these exact words'); await page.locator('#askform button').click(); await page.waitForFunction(()=>document.querySelector('#askmsg')?.textContent.includes('kept'));
ok('failed ask keeps words',await page.locator('#askbox').inputValue()==='Keep these exact words');
ok('failed ask explains outcome',(await page.locator('#askmsg').textContent()).includes('kept'));
ok('page-owned errors',errs.length===0); if(errs.length) console.error(errs.join('\n'));
const reduced=await br.newPage({reducedMotion:'reduce'}); await reduced.goto(`http://127.0.0.1:${PORT}/answers`); await reduced.waitForSelector('#answersections');
ok('reduced motion preserves function',await reduced.locator('#askbox').isVisible());
const rd=reduced.locator('.aq.answered').first(); await rd.locator('summary').click();
ok('reduced motion answered disclosure opens',await rd.getAttribute('open')!==null);
await rd.locator('summary').click(); ok('reduced motion answered disclosure closes',await rd.getAttribute('open')===null);
await br.close(); console.log(checks.join('\n')); if(checks.some(x=>x.startsWith('FAIL'))) process.exit(1);
