/* #255 — a successful composer confirmation owns one shared lifecycle.

   Real main and popout forms; fresh context per phase. The main race delays the
   real /command response and types during the POST, then proves success remains
   readable independently of the panel courtesy timer before departing through
   intermediate visual states. Close hard-cleans; popout consumes the same
   lifecycle; reduced motion keeps the hold but snaps visual changes.

   Writes to its target, so use a scratch fixture. usage:
   node confirmation.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
import { midFrames, midStates } from './dom.mjs';
const OUT=process.argv[2], PORT=process.argv[3]||'39887';
const BASE=`http://127.0.0.1:${PORT}`; mkdirSync(OUT,{recursive:true});
const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions composer confirmation lifecycle across main (typing during ' +
          'a delayed POST), close-during-POST, fallback listener cleanup, the ' +
          'popout form, and reduced-motion — five phases in fresh contexts',
  traceWindow: '6800ms / 5800ms rAF traces of cmdmsg opacity+transform+text through ' +
               'the ~5s hold and atmospheric departure; 5600ms + 5800ms settle waits',
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const br=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl']});
async function page(reduced=false){const c=await br.newContext({viewport:{width:1200,height:900},reducedMotion:reduced?'reduce':'no-preference'});const p=await c.newPage();p.on('pageerror',e=>errs.push(String(e)));await p.goto(`${BASE}/questions`,{waitUntil:'networkidle'});await p.click('#cmdplus');await p.waitForFunction(()=>cmdpalette.classList.contains('open'));await sleep(250);return {c,p};}
const trace=ms=>`((ms)=>new Promise(res=>{const m=cmdmsg,p=cmdpalette,seen=[],t0=performance.now();(function f(){const cs=getComputedStyle(m),t=performance.now()-t0;seen.push({t:Math.round(t),text:m.textContent,open:p.classList.contains('open'),op:Math.round(parseFloat(cs.opacity)*100),tf:cs.transform});t<ms?requestAnimationFrame(f):res(seen)})()}))(${ms})`;

// Main: type DURING a delayed real POST. The success still holds for ~5s,
// departs atmospherically and clears; typing only cancels panel courtesy-close.
{
 const {c,p}=await page();
 await p.evaluate(()=>{const f=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/command'))await new Promise(r=>setTimeout(r,500));return f(...a)}});
 await p.fill('#cmdtext','first thought'); await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await sleep(120); await p.fill('#cmdtext','next unsent thought');
 const seen=await p.evaluate(trace(6800));
 const success=seen.filter(s=>s.text==='sent to the dream');
 const first=success[0]?.t??null,last=success.at(-1)?.t??null;
 const departing=success.filter(s=>first!==null&&s.t-first>4500);
 notes.push(`main race first=${first} last=${last} final="${seen.at(-1).text}" open=${seen.at(-1).open}`);
 ok('main success appears after typing during POST',first!==null);
 ok('main success remains readable for about 5s',first!==null&&last-first>=4500);
 // PRECONDITION. These assertions need >=4 DISTINCT opacity values, which is
 // arithmetically impossible with fewer than 4 SAMPLES. The sampler is a
 // requestAnimationFrame loop, so its density is the browser's frame rate --
 // under system load rAF throttles and the window starves. Without this line a
 // starved run reports 'the motion is wrong' when what happened is 'we did not
 // look often enough', and those two need opposite responses: one is a bug, the
 // other is a busy machine. Naming the count makes the difference readable.
 ok(`main departure window sampled enough to see motion (${departing.length} frames)`,
    departing.length>=3);
 // #414: MID-FRAME form, not distinct-value counting. A snap has zero frames
 // strictly between its two ends at ANY frame rate; the old `>=4 distinct`
 // could not hold below 4 samples however correct the animation was.
 ok('main success departs through intermediate opacity and drift',
    midFrames(departing.map(s=>s.op))>=1&&midStates(departing.map(s=>s.tf))>=1);
 ok('main success clears instead of remaining forever',seen.at(-1).text==='');
 ok('typing keeps the panel open independently',seen.at(-1).open);
 await c.close();
}

// Closing is destruction, not a slow departure: clear now and cancel old work.
{
 const {c,p}=await page(); await p.fill('#cmdtext','close lifecycle');
 await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await p.waitForFunction(()=>cmdmsg.textContent==='sent to the dream');
 await p.keyboard.press('Escape'); await sleep(100);
 ok('close hard-cleans confirmation',await p.locator('#cmdmsg').textContent()===''&&!await p.locator('#cmdpalette').evaluate(n=>n.classList.contains('open')));
 await p.click('#cmdplus');await p.waitForFunction(()=>cmdpalette.classList.contains('open'));
 await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await p.waitForFunction(()=>cmdmsg.textContent==='a thought is needed');
 await sleep(5600);
 ok('close cancels old lifecycle so it cannot erase a later claim',await p.locator('#cmdmsg').textContent()==='a thought is needed');
 await c.close();
}

// Close DURING an in-flight POST invalidates that attempt. Its later response
// must not recreate success in the closed or subsequently reopened surface.
{
 const {c,p}=await page();
 await p.evaluate(()=>{const f=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/command'))await new Promise(r=>setTimeout(r,500));return f(...a)}});
 await p.fill('#cmdtext','close during request');await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await sleep(100);await p.keyboard.press('Escape');await sleep(700);
 ok('close during POST prevents its later response recreating success',await p.locator('#cmdmsg').textContent()==='');
 await p.click('#cmdplus');await p.waitForFunction(()=>cmdpalette.classList.contains('open'));
 ok('reopen stays clean after the invalidated POST returns',await p.locator('#cmdmsg').textContent()==='');
 await c.close();
}

// The fallback path must remove the transition listener it installed. Force a
// no-transition departure and count the real node's listener operations.
{
 const {c,p}=await page();
 await p.evaluate(()=>{const m=cmdmsg,add=m.addEventListener.bind(m),remove=m.removeEventListener.bind(m);window.__listenerOps={add:0,remove:0};m.addEventListener=(type,...rest)=>{if(type==='transitionend')__listenerOps.add++;return add(type,...rest)};m.removeEventListener=(type,...rest)=>{if(type==='transitionend')__listenerOps.remove++;return remove(type,...rest)};m.style.transition='none';});
 await p.fill('#cmdtext','fallback cleanup');await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await p.waitForFunction(()=>cmdmsg.textContent==='sent to the dream');await p.fill('#cmdtext','keep panel open');await sleep(5800);
 const ops=await p.evaluate(()=>__listenerOps);
 ok('fallback removes its transition listener instead of accumulating closures',ops.add===1&&ops.remove===1);
 await c.close();
}

// Popout uses the same controller rather than a permanent direct assignment.
{
 const {c,p}=await page(); const before=c.pages().length; await p.click('#cmdpop');
 await p.waitForTimeout(500); const pp=c.pages().find(x=>x!==p&&x.url()==='about:blank');
 ok('popout opens for lifecycle coverage',!!pp&&c.pages().length>before);
 if(pp){
  await pp.fill('#ptext','popout lifecycle');
  const seen=await pp.evaluate(`new Promise(res=>{const m=pmsg,seen=[],t0=performance.now();pform.requestSubmit();(function f(){const cs=getComputedStyle(m),t=performance.now()-t0;seen.push({t:Math.round(t),text:m.textContent,op:Math.round(parseFloat(cs.opacity)*100),tf:cs.transform});t<5800?requestAnimationFrame(f):res(seen)})()})`);
  const success=seen.filter(s=>s.text==='sent to the dream'),first=success[0]?.t??null;
  const arrival=success.filter(s=>first!==null&&s.t-first<500),departure=success.filter(s=>first!==null&&s.t-first>4500);
  notes.push(`popout arrival opacity=${[...new Set(arrival.map(s=>s.op))].join(',')} transform=${[...new Set(arrival.map(s=>s.tf))].join(',')} first=${first}`);
  // Same precondition as the main window above, for both popout windows.
  ok(`popout arrival window sampled enough to see motion (${arrival.length} frames)`,
     arrival.length>=3);
  ok(`popout departure window sampled enough to see motion (${departure.length} frames)`,
     departure.length>=3);
  ok('popout success arrives through intermediate opacity and drift',
     midFrames(arrival.map(s=>s.op))>=1&&midStates(arrival.map(s=>s.tf))>=1);
  ok('#291 popout is intentionally persistent beyond main courtesy close',
     !pp.isClosed() && seen.some(s=>s.t>=2200&&s.text==='sent to the dream'));
  ok('popout success remains readable for about 5s',success.length&&success.at(-1).t-success[0].t>=4500);
  ok('popout success departs through intermediate opacity and drift',
     midFrames(departure.map(s=>s.op))>=1&&midStates(departure.map(s=>s.tf))>=1);
  ok('popout success self-dismisses',seen.at(-1).text==='');
 }
 await c.close();
}

// Reduced motion preserves the lifecycle and legibility but has no visual ramp.
{
 const {c,p}=await page(true);
 await p.evaluate(()=>{const f=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/command'))await new Promise(r=>setTimeout(r,400));return f(...a)}});
 await p.fill('#cmdtext','reduced lifecycle');await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await sleep(100);await p.fill('#cmdtext','next reduced thought');
 const seen=await p.evaluate(trace(5800));const success=seen.filter(s=>s.text==='sent to the dream');
 ok('reduced success remains readable through the hold',success.length&&success.at(-1).t-success[0].t>=4500);
 ok('reduced success never ramps opacity or transform',success.every(s=>s.op>=95&&s.tf==='none'));
 ok('reduced success clears on schedule',seen.at(-1).text==='');await c.close();
}
ok('no page errors',errs.length===0);await br.close();
finish();
