/* #231 human-to-dreamer answers channel + #238 open survives tick.
   Usage: node answers.mjs <out> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT=outdir(process.argv), PORT=+(process.argv[3]||39890);
const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/answers end to end: #askbox expose + ask submit + live tick survival, ' +
          '#247 answerRecord attrs, #250 missing-aid disclosure travel, #238 open ' +
          'survives quiet/reorder/delete ticks, #292 Ctrl+Enter + inflight lifecycle, ' +
          '#293 arrival + reduced motion',
  traceWindow: '1000ms rAF traces of disclosure height/marker-top for #250 travel; ' +
               '2200ms arrival opacity trace; 5200ms polls for tick-driven reorders; ' +
               'settle waits keyed on real premises not fixed delays',
});
const target=join(dirname(OUT),'target');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ansPath=join(target,'.dreamwork','answers.md');
const seedTwoDup=(a,b)=>`# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): ${a}\n\n- **Duplicate?** → answered (2026-07-26): ${b}\n`;
const br=await chromium.launch({args:['--use-gl=swiftshader']});
const page=await br.newPage({viewport:{width:1100,height:800}});
page.on('pageerror',e=>errs.push(String(e))); page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource')) errs.push(m.text())});
await page.goto(`http://127.0.0.1:${PORT}/answers`);
const exposed=await page.locator('#askbox').waitFor({state:'visible',timeout:5000}).then(()=>true).catch(()=>false);
ok('answers route exposes #askbox',exposed);
if(!exposed){await br.close();finish();process.exit(1)}
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
/* #250: missing-aid disclosure must still toggle under EXPAND_SURFACES.
   preventDefault runs on .aq.answered > summary; without listlessFallback the
   host[data-aid] miss leaves open stuck. Real answerRecord HTML + a following
   marker; per-frame tops/heights (not end-state alone). */
await page.evaluate(()=>{
  const host=document.querySelector('#answersections')||document.body;
  host.insertAdjacentHTML('beforeend',
    answerRecord({title:'Missing aid toggle?', body:'orphan body text long enough to change height when opened.\n\nsecond para.'}, true)+
    '<div id="miss-aid-marker" class="dim" style="min-height:2rem">following marker</div>');
});
const miss=page.locator('.aq.answered').filter({hasText:'Missing aid toggle?'}).first();
ok('#250 missing-aid node has no data-aid', await miss.getAttribute('data-aid')===null);
ok('#250 missing-aid node has no data-keep', await miss.getAttribute('data-keep')===null);
// Normal motion: open with intermediate heights + marker travel
const openTrace=await page.evaluate(()=>new Promise(res=>{
  const det=[...document.querySelectorAll('.aq.answered')].find(e=>
    (e.querySelector('summary')?.textContent||'').includes('Missing aid toggle'));
  const mark=document.getElementById('miss-aid-marker');
  if(!det||!mark){res({err:'no fixture'});return;}
  det.open=false;
  const frames=[];
  const t0=performance.now();
  det.querySelector('summary').click();
  // #296: the travel must ARM a height transition. travelCard arms it
  // synchronously inside the click handler, so this is observable at once;
  // without it the node snaps and the >2-distinct evidence goes vacuous.
  const armed=det.style.height!==''&&/height/.test(det.style.transition);
  (function step(){
    const r=det.getBoundingClientRect(), m=mark.getBoundingClientRect();
    frames.push({t:Math.round(performance.now()-t0), h:Math.round(r.height),
      top:Math.round(m.top), open:!!det.open});
    if(performance.now()-t0<1000) requestAnimationFrame(step);
    else res({frames, open:!!det.open, h0:frames[0]?.h, hEnd:frames.at(-1)?.h, armed});
  })();
}));
const oH=new Set((openTrace.frames||[]).map(f=>f.h));
const oTops=new Set((openTrace.frames||[]).map(f=>f.top));
ok('#250 missing-aid opens (normal)', !!openTrace.open);
ok('#250 open travel arms a height transition', !!openTrace.armed);
ok('#250 open visits >2 distinct details heights', oH.size>2);
ok('#250 open visits >2 distinct marker tops', oTops.size>2);
/* #296: the close click must not race the OPEN travel's cleanup. travelCard
   holds inline height/overflow/transition on the node until CARD_MS+150
   (1000ms) after the open click — the same moment this trace would start.
   Under event-loop load the cleanup fires LATE: foldDetailsLocal then
   measures `now` against the stale inline height, was.height===now.height,
   no transition is armed, and the node SNAPS when the delayed cleanup clears
   the inline height — exactly 2 distinct heights and marker tops, the load
   flake this guard showed. Wait for the real premise (prior travel fully
   settled), never a fixed delay. */
await page.waitForFunction(()=>{
  const det=[...document.querySelectorAll('.aq.answered')].find(e=>
    (e.querySelector('summary')?.textContent||'').includes('Missing aid toggle'));
  return det && det.style.height==='' && det.style.overflow==='' &&
    det.style.transition==='';
},null,{timeout:5000});
// Close path
const closeTrace=await page.evaluate(()=>new Promise(res=>{
  const det=[...document.querySelectorAll('.aq.answered')].find(e=>
    (e.querySelector('summary')?.textContent||'').includes('Missing aid toggle'));
  const mark=document.getElementById('miss-aid-marker');
  if(!det||!mark){res({err:'no fixture'});return;}
  const frames=[];
  const t0=performance.now();
  det.querySelector('summary').click();
  const armed=det.style.height!==''&&/height/.test(det.style.transition);
  (function step(){
    const r=det.getBoundingClientRect(), m=mark.getBoundingClientRect();
    frames.push({t:Math.round(performance.now()-t0), h:Math.round(r.height),
      top:Math.round(m.top), open:!!det.open});
    if(performance.now()-t0<1000) requestAnimationFrame(step);
    else res({frames, open:!!det.open, armed});
  })();
}));
const cH=new Set((closeTrace.frames||[]).map(f=>f.h));
const cTops=new Set((closeTrace.frames||[]).map(f=>f.top));
ok('#250 missing-aid closes (normal)', !closeTrace.open);
ok('#250 close travel arms a height transition', !!closeTrace.armed);
ok('#250 close visits >2 distinct details heights', cH.size>2);
ok('#250 close visits >2 distinct marker tops', cTops.size>2);
// Reduced motion: function only (immediate), no motion requirement
const rmPage=await br.newPage({reducedMotion:'reduce', viewport:{width:1100,height:800}});
await rmPage.goto(`http://127.0.0.1:${PORT}/answers`);
await rmPage.waitForSelector('#answersections');
await rmPage.evaluate(()=>{
  const host=document.querySelector('#answersections')||document.body;
  host.insertAdjacentHTML('beforeend',
    answerRecord({title:'Missing aid RM?', body:'rm body.'}, true));
});
const rmMiss=rmPage.locator('.aq.answered').filter({hasText:'Missing aid RM?'}).first();
await rmMiss.locator('summary').click();
ok('#250 reduced-motion missing-aid opens', await rmMiss.evaluate(e=>!!e.open));
await rmMiss.locator('summary').click();
ok('#250 reduced-motion missing-aid closes', await rmMiss.evaluate(e=>!e.open));
await rmPage.close();
// remove inject so later phases stay clean
await page.evaluate(()=>{
  for(const el of [...document.querySelectorAll('.aq.answered')]){
    if((el.querySelector('summary')?.textContent||'').includes('Missing aid toggle'))
      el.remove();
  }
  document.getElementById('miss-aid-marker')?.remove();
});
const asked='Does the live ask persist?\n## not a section\n- **not another entry**';
await page.locator('#askbox').fill(asked); await page.locator('#askbox').focus();
// E3 cutover: a successful write is 202 + receipt via _send_receipt, not 200.
// Asserting status===200 was the pre-receipt contract; it fails on a correct
// do-next that landed. "Accepted" means the write landed (ok, not rejected) —
// the same verdict identity/#263 E5 taught, not a frozen status code.
const tickVerdict=await page.evaluate(async()=>{
  const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind:'do-next',text:'',from:'/answers'})});
  let j=null; try{j=await r.json()}catch(e){j=null}
  return {status:r.status, ok:!!(j&&j.ok===true), rejected:!!(j&&j.rejected===true),
          hasReceipt:!!(j&&j.receipt)};
});
notes.push(`tick do-next verdict: ${JSON.stringify(tickVerdict)}`);
// Precondition: we got a response shape at all (else "accepted" is vacuous).
ok('precondition: tick /command returned a JSON body with ok',
   tickVerdict && typeof tickVerdict.status==='number' && tickVerdict.ok===true);
ok('tick trigger accepted',
   !!tickVerdict && tickVerdict.ok && !tickVerdict.rejected &&
   tickVerdict.status>=200 && tickVerdict.status<300);
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
async function traceToggle(name){
  /* #296: same settle premise as the missing-aid close — a click that lands
     while the PREVIOUS traceToggle's travel still holds inline styles
     measures a stale rect, arms nothing, and snaps, starving the
     intermediate-geometry evidence under load. */
  const detH=await det.elementHandle();
  await page.waitForFunction(e=>e&&e.style.height===''&&e.style.overflow===''&&e.style.transition==='',detH,{timeout:5000});
  await detH.dispose();
  const p=[await neighbour.evaluate(e=>e.getBoundingClientRect().top)];await det.locator('summary').click();for(let i=0;i<30;i++){p.push(await neighbour.evaluate(e=>e.getBoundingClientRect().top));await page.waitForTimeout(30)}const end=p.at(-1),start=p[0],lo=Math.min(start,end)-1,hi=Math.max(start,end)+1;ok(name+' visits intermediate geometry',new Set(p.map(x=>Math.round(x))).size>3);ok(name+' has no overshoot',p.every(x=>x>=lo&&x<=hi));}
await traceToggle('answered disclosure open'); await traceToggle('answered disclosure close');

/* ── #238: open answered disclosure survives a real tick ───────────────────
   Load-bearing: prove a setContent ran (no-op tick would pass every end-state
   check). Under #505 the node is KEPT by data-aid/data-keep; vacuity is
   __dwViewRenderGen advancing (or legacy: __dwMark gone). Open is keyed to
   the logical record, not list position. */
async function forceTick(markEl){
  const pre = await markEl.evaluate(e=>{e.__dwMark=1; return {aid:e.dataset.aid||'', keep:e.dataset.keep||'', body:(e.querySelector('.aqbody')||{}).textContent||''};});
  const gen0 = await page.evaluate(()=>{
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    return window.__dwViewRenderGen || 0;
  });
  await page.evaluate(()=>fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'do-next',text:'',from:'/answers'})}).then(r=>r.status));
  const t0=Date.now();
  let tickWorked=false, replaced=false, open=false, peerOpen=false, body='';
  while(Date.now()-t0<5200){
    const st=await page.evaluate(({aid,bodyNeedle,gen0})=>{
      const all=[...document.querySelectorAll('.aq.answered')];
      const byBody=all.find(e=>(e.querySelector('.aqbody')?.textContent||'').includes(bodyNeedle));
      const el=aid?document.querySelector(`.aq.answered[data-aid="${CSS.escape(aid)}"]`):byBody;
      const peer=all.find(e=>e!==el);
      const advanced = (window.__dwViewRenderGen || 0) > gen0;
      const replaced = !!(el && !el.__dwMark);
      return {
        replaced,
        advanced,
        tickWorked: advanced || replaced,
        open: !!(el && el.open),
        peerOpen: !!(peer && peer.open),
        body: el?(el.querySelector('.aqbody')?.textContent||''):'',
        count: all.length,
        aids: all.map(e=>e.dataset.aid||''),
      };
    }, {aid:pre.aid, bodyNeedle:'first loop answer', gen0});
    if(st.tickWorked){tickWorked=true; replaced=st.replaced; open=st.open; peerOpen=st.peerOpen; body=st.body; break;}
    await sleep(50);
  }
  return {tickWorked, replaced, open, peerOpen, body, pre};
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
ok('#238 quiet tick really ran (render gen advanced or node replaced)', quiet.tickWorked);
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
// #247/#251: under #505 the SURVIVOR node is KEPT by data-aid (same object
// across the tick) — vacuity is a setLiveContent that consumed the write
// (__dwRenders / gen), not detachment of the survivor. The deleted peer is
// gone; the open survivor keeps open + aid.
/* #296 handshake: wait for the render that consumed THIS write, not merely
   count===2 (which can already be true from the reorder phase). */
await page.evaluate(()=>{
  window.__dwRenders=[];
  const orig=setLiveContent;
  setLiveContent=function(html){
    const r=orig(html);
    window.__dwRenders.push({t:performance.now(), m:lastMtime});
    return r;
  };
});
writeFileSync(ansPath, seedTwoDup('first loop answer.','second loop answer.'));
const settled251=await page.evaluate(()=>new Promise(async res=>{
  const t0=Date.now();
  const m=parseMtime(await (await fetch('/mtime')).text()).mtime;
  const orderOk=()=>{
    const b=[...document.querySelectorAll('.aq.answered')]
      .map(e=>e.querySelector('.aqbody')?.textContent||'');
    return b.length===2 && b[0].includes('first loop answer') &&
      b[1].includes('second loop answer');
  };
  (function poll(){
    if(window.__dwRenders.some(r=>r.m===m) && orderOk()){res(true);return;}
    if(Date.now()-t0>9000){res(false);return;}   // fails closed, named below
    setTimeout(poll,50);
  })();
}));
ok('#251 refresh for the fixture write settled before handle', settled251);
await page.evaluate(()=>[...document.querySelectorAll('.aq.answered')].forEach(d=>{d.open=false;}));
const openSecond=page.locator('.aq.answered').filter({hasText:'second loop answer'}).first();
await openSecond.locator('summary').click();
await page.waitForFunction(()=>{
  const el=[...document.querySelectorAll('.aq.answered')].find(e=>(e.querySelector('.aqbody')?.textContent||'').includes('second loop answer'));
  return el && el.open;
},{timeout:3000});
// Playwright handle to the pre-deletion survivor — under #505 it stays
// connected (kept by data-aid); under legacy innerHTML it detaches.
const oldSecondHandle=await openSecond.elementHandle();
ok('#251 pre-deletion ElementHandle acquired', !!oldSecondHandle);
ok('#251 original node starts connected',
  !!oldSecondHandle && await oldSecondHandle.evaluate(n=>n.isConnected).catch(()=>false));
const preDel=await openSecond.evaluate(e=>{
  e.__dwMark=1;
  return {
    aid:e.dataset.aid||'',
    keep:e.dataset.keep||'',
    body:(e.querySelector('.aqbody')||{}).textContent||'',
  };
});
ok('#247 deletion preAid present on open survivor', !!preDel.aid && preDel.aid===preDel.keep);
const genDel0=await page.evaluate(()=>window.__dwViewRenderGen||0);
writeFileSync(ansPath, '# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): second loop answer.\n');
const t1=Date.now();
let del={ready:false, open:false, count:0, sameAid:false, replaced:false, connected:false, aid:'', advanced:false};
while(Date.now()-t1<5200){
  const st=await page.evaluate(({preAid, needle, gen0})=>{
    const all=[...document.querySelectorAll('.aq.answered')];
    if(all.length!==1) return {ready:false, count:all.length};
    const el=all[0];
    const body=el.querySelector('.aqbody')?.textContent||'';
    if(!body.includes(needle)) return {ready:false, count:1};
    const aid=el.dataset.aid||'';
    const advanced=(window.__dwViewRenderGen||0)>gen0;
    return {
      ready:true,
      open:!!el.open,
      count:1,
      sameAid:!!(preAid && aid===preAid),
      replaced:!(el.__dwMark),
      connected:!!el.isConnected,
      markSurvived:!!el.__dwMark,
      advanced,
      aid,
    };
  }, {preAid:preDel.aid, needle:'second loop answer', gen0:genDel0});
  if(st.ready){del=st; break;}
  await sleep(50);
}
// Vacuity: a render advanced OR the survivor was rebuilt. Under #505 the
// survivor is KEPT (markSurvived / same handle connected) — that is the win.
const oldStillConnected=oldSecondHandle
  ? await oldSecondHandle.evaluate(n=>n.isConnected).catch(()=>false)
  : false;
ok('#238 deletion leaves the survivor', del.ready && del.count===1);
ok('#247 deletion survivor keeps same aid', del.sameAid && del.aid===preDel.aid);
ok('#247 deletion tick ran (render gen advanced or survivor rebuilt)',
   !!(del.advanced || del.replaced));
ok('#251 survivor node identity: kept under reconcile OR rebuilt under swap',
   (del.markSurvived && oldStillConnected) || (del.replaced && !oldStillConnected));
ok('#238 open survives deletion of the other record', del.open);
if(oldSecondHandle) await oldSecondHandle.dispose().catch(()=>{});

writeFileSync(ansPath,'# Questions for the dreamer\n\nprose no reader can see\n');
await page.waitForFunction(()=>document.body.textContent.includes('answers channel unreadable'),null,{timeout:5000});
ok('unreadable channel is loud and path-specific',await page.locator('.qhealth').evaluate(e=>e.textContent.includes('.dreamwork/answers.md')&&e.querySelector('a')?.getAttribute('href')?.includes('answers.md')));
writeFileSync(ansPath,'# Questions for the dreamer\n\n## Open\n\n## Answered\n\n- **Duplicate?** → answered (2026-07-26): first.\n');
await page.waitForFunction(()=>document.querySelectorAll('.aq.answered').length===1,null,{timeout:5000});
await page.route('**/ask',r=>r.fulfill({status:409,body:'refused'})); await page.locator('#askbox').fill('Keep these exact words'); await page.locator('#askform button').click(); await page.waitForFunction(()=>document.querySelector('#askmsg')?.textContent.includes('kept'));
ok('failed ask keeps words',await page.locator('#askbox').inputValue()==='Keep these exact words');
ok('failed ask explains outcome',(await page.locator('#askmsg').textContent()).includes('kept'));
ok('page-owned errors',errs.length===0);

/* #292 — Ctrl/Cmd+Enter must submit the /answers ask form (composer + card
   already do). Real keyboard, one durable submit, no duplicate. */
await page.unroute('**/ask').catch(()=>{});
writeFileSync(ansPath,'# Questions for the dreamer\n\n## Open\n\n## Answered\n');
await page.goto(`http://127.0.0.1:${PORT}/answers`,{waitUntil:'networkidle'});
await page.waitForSelector('#askbox');
const askText='Ctrl-enter submit from answers askbox';
await page.locator('#askbox').fill(askText);
await page.locator('#askbox').focus();
await page.keyboard.press('Control+Enter');
const submitted=await page.waitForFunction(()=>{
  const box=document.querySelector('#askbox');
  const n=document.querySelectorAll('.aq.open').length;
  return box&&box.value===''&&n>=1;
},null,{timeout:5000}).then(()=>true).catch(()=>false);
ok('#292 Ctrl+Enter clears the box and creates an open entry',submitted);
const nOpen=await page.locator('.aq.open').count();
ok('#292 exactly one open entry after one Ctrl+Enter',submitted&&nOpen===1);
const onDisk=(await import('node:fs')).readFileSync(ansPath,'utf8');
ok('#292 durable answers.md received the question',submitted&&onDisk.includes(askText));
// second Ctrl+Enter with empty box must not forge another entry
if(submitted){
  await page.locator('#askbox').focus();
  await page.keyboard.press('Control+Enter');
  await sleep(400);
}
ok('#292 empty Ctrl+Enter does not double-submit',
   submitted&&await page.locator('.aq.open').count()===1);

/* G1 HIGH: rapid double Ctrl+Enter while /ask is delayed — exactly one POST
   and one durable record (in-flight guard). */
writeFileSync(ansPath,'# Questions for the dreamer\n\n## Open\n\n## Answered\n');
await page.goto(`http://127.0.0.1:${PORT}/answers`,{waitUntil:'networkidle'});
await page.waitForSelector('#askbox');
let askPosts=0;
await page.route('**/ask',async route=>{
  askPosts++;
  await sleep(700);
  await route.continue();
});
// Title is first sentence only; unique marker lives only in the body so a
// single write is not double-counted when grepping the file.
const bodyMark='INFLIGHT_BODY_'+Date.now();
const duplex='Short duplex title?\n\n'+bodyMark+' trailing words for the body.';
await page.locator('#askbox').fill(duplex);
await page.locator('#askbox').focus();
await page.keyboard.press('Control+Enter');
await page.keyboard.press('Control+Enter'); // before first response
await page.waitForFunction(()=>document.querySelector('#askbox')?.value===''&&document.querySelectorAll('.aq.open').length>=1,null,{timeout:8000}).catch(()=>{});
await sleep(200);
const openAfterDup=await page.locator('.aq.open').count();
const diskDup=(await import('node:fs')).readFileSync(ansPath,'utf8');
const diskHits=(diskDup.match(new RegExp(bodyMark,'g'))||[]).length;
const openHeads=(diskDup.match(/^- \*\*/gm)||[]).length;
ok('#292 delayed double Ctrl+Enter issues exactly one /ask',askPosts===1);
ok('#292 delayed double Ctrl+Enter leaves exactly one open row',openAfterDup===1);
ok('#292 delayed double Ctrl+Enter writes the body marker once',diskHits===1);
ok('#292 delayed double Ctrl+Enter adds exactly one open entry head',openHeads===1);
await page.unroute('**/ask').catch(()=>{});

/* G1 lifecycle: delayed /ask then navigate away/back — new surface free;
   late old response must not clear/status/tick the new form. */
writeFileSync(ansPath,'# Questions for the dreamer\n\n## Open\n\n## Answered\n');
await page.goto(`http://127.0.0.1:${PORT}/answers`,{waitUntil:'networkidle'});
await page.waitForSelector('#askbox');
let latePosts=0, continueLate=null;
await page.route('**/ask',route=>{
  latePosts++;
  // hold the first request until after route-away/back
  return new Promise(resolve=>{
    continueLate=()=>route.continue().then(resolve);
  });
});
const staleText='Stale flight words must stay if still pending '+Date.now();
await page.locator('#askbox').fill(staleText);
await page.locator('#askbox').focus();
await page.keyboard.press('Control+Enter');
await sleep(150);
// SPA away while in flight
await page.evaluate(()=>typeof navigate==='function'&&navigate('questions',null,{push:true,transition:false}));
await page.waitForFunction(()=>!document.getElementById('askbox'),null,{timeout:3000}).catch(()=>{});
// return to answers — new surface
await page.evaluate(()=>typeof navigate==='function'&&navigate('answers',null,{push:true,transition:false}));
await page.waitForSelector('#askbox');
const fresh='Fresh ask after surface rebuild '+Date.now();
await page.locator('#askbox').fill(fresh);
// release stale response
if(typeof continueLate==='function') await continueLate();
await sleep(500);
const boxAfterLate=await page.locator('#askbox').inputValue();
const msgAfterLate=await page.locator('#askmsg').textContent();
ok('#292 late response after leave/return does not clear the new draft',
   boxAfterLate===fresh);
ok('#292 late response does not stamp success on the new form',
   !(msgAfterLate||'').includes('asked')||boxAfterLate===fresh);
// new submit must not be blocked by stuck in-flight
await page.unroute('**/ask').catch(()=>{});
await page.locator('#askbox').focus();
await page.keyboard.press('Control+Enter');
const freshOk=await page.waitForFunction((want)=>{
  const box=document.querySelector('#askbox');
  return box&&box.value===''&&document.body.innerText.includes(want.slice(0,20));
},fresh,{timeout:5000}).then(()=>true).catch(()=>false);
ok('#292 after leave/return a new Ctrl+Enter can submit independently',freshOk);
ok('#292 leave/return path still only one late POST for the stale flight',latePosts===1);

/* G2: exact-title distinct-body twins have distinct data-aqid; a new twin arrives. */
writeFileSync(ansPath,
  '# Questions for the dreamer\n\n## Open\n\n'+
  '- **2026-07-27 — Twin title**\n  first body only\n\n'+
  '- **2026-07-27 — Twin title**\n  second body different\n\n'+
  '## Answered\n');
await page.goto(`http://127.0.0.1:${PORT}/answers`,{waitUntil:'networkidle'});
await page.waitForFunction(()=>document.querySelectorAll('.aq.open').length===2,null,{timeout:5000});
const twinIds=await page.evaluate(()=>[...document.querySelectorAll('.aq.open')].map(e=>e.dataset.aqid||''));
ok('#293 twin open rows both carry data-aqid',twinIds.length===2&&twinIds.every(Boolean));
ok('#293 twin open rows have distinct data-aqid',twinIds[0]!==twinIds[1]);

/* #293 — submitted open entry text must be visibly readable (opacity/color),
   live after submit and after hard refresh. Stuck .dreamin is opacity 0 with
   a still-hitbox I-beam — existence checks pass over that. */
const liveVis=submitted?await page.locator('.aq.open').first().evaluate(el=>{
  const qt=el.querySelector('.qt');
  const body=el.querySelector('.aqbody')||el;
  if(!qt) return {ok:false};
  const csq=getComputedStyle(qt), csb=getComputedStyle(body), cse=getComputedStyle(el);
  const parseRgb=s=>{const m=String(s).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);return m?[+m[1],+m[2],+m[3]]:null;};
  const lum=rgb=>rgb?0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]:0;
  return {
    ok:true,
    text:(qt.textContent||'').trim(),
    dreamin:el.classList.contains('dreamin'),
    opEl:parseFloat(cse.opacity),
    opQt:parseFloat(csq.opacity),
    opBody:parseFloat(csb.opacity),
    colorQt:csq.color,
    colorBody:csb.color,
    lumQt:lum(parseRgb(csq.color)),
    h:el.getBoundingClientRect().height,
    w:el.getBoundingClientRect().width,
  };
}):{ok:false};
ok('#293 live open entry exists with title text',
   liveVis.ok&&liveVis.text.length>0);
ok('#293 live open entry is not stuck in .dreamin',liveVis.ok&&!liveVis.dreamin);
ok('#293 live title opacity is fully visible',liveVis.ok&&liveVis.opQt>=0.95&&liveVis.opEl>=0.95);
ok('#293 live title has non-transparent readable color',
   liveVis.ok&&liveVis.lumQt>30&&!/rgba\(0,\s*0,\s*0,\s*0\)/.test(liveVis.colorQt||''));
ok('#293 live entry has real geometry (not zero box)',
   liveVis.ok&&liveVis.h>8&&liveVis.w>40);

let refreshVis={ok:false};
if(submitted){
  await page.reload({waitUntil:'networkidle'});
  const hasOpen=await page.waitForSelector('.aq.open',{timeout:5000}).then(()=>true).catch(()=>false);
  if(hasOpen){
    refreshVis=await page.locator('.aq.open').first().evaluate(el=>{
      const qt=el.querySelector('.qt');
      if(!qt) return {ok:false};
      const csq=getComputedStyle(qt), cse=getComputedStyle(el);
      const parseRgb=s=>{const m=String(s).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);return m?[+m[1],+m[2],+m[3]]:null;};
      const lum=rgb=>rgb?0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]:0;
      return {
        ok:true,
        text:(qt.textContent||'').trim(),
        dreamin:el.classList.contains('dreamin'),
        opQt:parseFloat(csq.opacity),
        opEl:parseFloat(cse.opacity),
        lumQt:lum(parseRgb(csq.color)),
        h:el.getBoundingClientRect().height,
      };
    });
  }
}
ok('#293 after hard refresh open text still present',
   refreshVis.ok&&refreshVis.text.length>0);
ok('#293 after hard refresh not stuck in .dreamin',refreshVis.ok&&!refreshVis.dreamin);
ok('#293 after hard refresh title opacity fully visible',
   refreshVis.ok&&refreshVis.opQt>=0.95&&refreshVis.opEl>=0.95);
ok('#293 after hard refresh title color still readable',
   refreshVis.ok&&refreshVis.lumQt>30);
ok('#293 after hard refresh geometry remains',refreshVis.ok&&refreshVis.h>8);

/* #293 arrival: live-added open row must traverse intermediate opacities
   (enter-snap). RED inject: __dwSkipOpenAskArrival skips the mechanism. */
const ARRIVE=(skip)=>`((skip)=>new Promise(async res=>{
  window.__dwSkipOpenAskArrival=!!skip;
  const box=document.getElementById('askbox');
  const form=document.getElementById('askform');
  if(!box||!form) return res({ok:false,why:'no form'});
  const before=new Set([...document.querySelectorAll('.aq.open[data-aqid]')].map(e=>e.dataset.aqid));
  box.value='Open-row arrival trace '+Math.random().toString(36).slice(2,7);
  box.dispatchEvent(new Event('input',{bubbles:true}));
  const seen=[];
  const t0=performance.now();
  form.requestSubmit();
  await new Promise(r=>{
    (function step(){
      const els=[...document.querySelectorAll('.aq.open[data-aqid]')];
      const neu=els.find(e=>!before.has(e.dataset.aqid))||els[els.length-1];
      if(neu){
        const cs=getComputedStyle(neu);
        seen.push({t:Math.round(performance.now()-t0),
                   op:Math.round(parseFloat(cs.opacity)*100),
                   tf:cs.transform,
                   dreamin:neu.classList.contains('dreamin')});
      }
      if(performance.now()-t0<2200) requestAnimationFrame(step); else r();
    })();
  });
  window.__dwSkipOpenAskArrival=false;
  const ops=[...new Set(seen.map(s=>s.op))];
  const tfs=[...new Set(seen.map(s=>s.tf))];
  res({ok:true,seen,ops,tfs,final:seen.at(-1)||null,n:seen.length});
}))(${skip?'true':'false'})`;

// RED: skip arrival → snap (few opacity positions, all high)
const redArr=await page.evaluate(ARRIVE(true));
ok('#293 RED disabled arrival still creates a row',
   redArr.ok&&redArr.final&&redArr.final.op>=95);
ok('#293 RED disabled arrival does NOT ease through many opacities',
   redArr.ok&&redArr.ops.filter(o=>o<95).length===0&&redArr.ops.length<=3);

// GREEN: real arrival after another submit
const greenArr=await page.evaluate(ARRIVE(false));
const greenOps=greenArr.ops||[];
ok('#293 GREEN live open arrival eases through many opacities',
   greenArr.ok&&new Set(greenOps).size>=4&&Math.min(...greenOps)<=10);
ok('#293 GREEN live open arrival ends fully visible',
   greenArr.ok&&greenArr.final&&greenArr.final.op>=95&&!greenArr.final.dreamin);
ok('#293 GREEN live open arrival drifts (not only fades)',
   greenArr.ok&&(greenArr.tfs||[]).length>=2);

const reduced=await br.newPage({reducedMotion:'reduce'});
// F1: seed a real answered disclosure — never pass on absence
writeFileSync(ansPath,
  '# Questions for the dreamer\n\n## Open\n\n## Answered\n\n'+
  '- **Seeded for RM** → answered (2026-07-27): loop body for reduced motion.\n');
await reduced.goto(`http://127.0.0.1:${PORT}/answers`,{waitUntil:'networkidle'});
await reduced.waitForSelector('#answersections');
ok('reduced motion preserves function',await reduced.locator('#askbox').isVisible());
const rd=reduced.locator('.aq.answered').filter({hasText:'Seeded for RM'}).first();
const hasRd=await rd.count()>0;
ok('#F1 reduced-motion answered disclosure is present (seeded)',hasRd);
if(hasRd){
  await rd.locator('summary').click();
  ok('reduced motion answered disclosure opens',await rd.getAttribute('open')!==null);
  await rd.locator('summary').click();
  ok('reduced motion answered disclosure closes',await rd.getAttribute('open')===null);
} else {
  ok('reduced motion answered disclosure opens',false);
  ok('reduced motion answered disclosure closes',false);
}
// #292 under reduced motion too
await reduced.locator('#askbox').fill('reduced ctrl enter ask');
await reduced.locator('#askbox').focus();
await reduced.keyboard.press('Control+Enter');
const rmSub=await reduced.waitForFunction(()=>document.querySelector('#askbox')?.value===''&&document.querySelectorAll('.aq.open').length>=1,null,{timeout:5000}).then(()=>true).catch(()=>false);
ok('#292 reduced motion Ctrl+Enter still submits',rmSub);
// RM arrival: ≤2 opacity positions (snap), ends visible
const rmArr=await reduced.evaluate(ARRIVE(false));
const rmOps=rmArr.ops||[];
ok('#293 reduced motion open arrival snaps (≤2 opacity positions)',
   rmArr.ok&&new Set(rmOps).size<=2);
ok('#293 reduced motion open arrival ends fully visible',
   rmArr.ok&&rmArr.final&&rmArr.final.op>=95&&!rmArr.final.dreamin);
await br.close(); finish();
