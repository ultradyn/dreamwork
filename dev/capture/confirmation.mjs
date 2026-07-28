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
import { midFrames, midStates, transitionWindow, framesInWindow } from './dom.mjs';
const OUT=process.argv[2], PORT=process.argv[3]||'39887';
const BASE=`http://127.0.0.1:${PORT}`; mkdirSync(OUT,{recursive:true});
const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions composer confirmation lifecycle across main (typing during ' +
          'a delayed POST), close-during-POST, fallback listener cleanup, the ' +
          'popout form, and reduced-motion — five phases in fresh contexts',
  traceWindow: '8500ms rAF traces of cmdmsg opacity+transform+text through ' +
               'the ~5s hold and atmospheric departure (early-resolve 400ms after ' +
               'the departure transitionend, so the trace captures the departure ' +
               'however late load pushed it); 5600ms + 5800ms settle waits',
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const br=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl']});
async function page(reduced=false){const c=await br.newContext({viewport:{width:1200,height:900},reducedMotion:reduced?'reduce':'no-preference'});const p=await c.newPage();p.on('pageerror',e=>errs.push(String(e)));await p.goto(`${BASE}/questions`,{waitUntil:'networkidle'});await p.click('#cmdplus');await p.waitForFunction(()=>cmdpalette.classList.contains('open'));await sleep(250);return {c,p};}
// #442: the trace now captures per-property transition events alongside the
// rAF value trace. opacity/transform are COMPOSITOR-driven: the browser
// animates them in real time while rAF callbacks run on the (starvable)
// main thread, so a smooth transition can produce zero mid-frames if the
// sampler missed the window. transitionstart fires iff the browser
// registered the transition — the load-independent snap detector.
const trace=ms=>`((ms)=>new Promise(res=>{const m=cmdmsg,p=cmdpalette,seen=[],t0=performance.now();const events=[];let done=false;const finish=()=>{if(!done){done=true;res({frames:seen,events})}};const onT=type=>e=>{if(e.propertyName==='opacity'||e.propertyName==='transform')events.push({type,prop:e.propertyName,t:Math.round((performance.now()-t0)*10)/10});if(type==='end'&&e.propertyName==='opacity'&&(performance.now()-t0)>4000)setTimeout(finish,400)};m.addEventListener('transitionrun',onT('run'));m.addEventListener('transitionstart',onT('start'));m.addEventListener('transitionend',onT('end'));(function f(){const cs=getComputedStyle(m),t=performance.now()-t0;seen.push({t:Math.round(t),text:m.textContent,open:p.classList.contains('open'),op:Math.round(parseFloat(cs.opacity)*100),tf:cs.transform});t<ms?requestAnimationFrame(f):finish()})()}))(${ms})`;

// Main: type DURING a delayed real POST. The success still holds for ~5s,
// departs atmospherically and clears; typing only cancels panel courtesy-close.
{
 const {c,p}=await page();
 await p.evaluate(()=>{const f=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/command'))await new Promise(r=>setTimeout(r,500));return f(...a)}});
 await p.fill('#cmdtext','first thought'); await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await sleep(120); await p.fill('#cmdtext','next unsent thought');
 const seen=await p.evaluate(trace(8500));
 const frames=seen.frames, events=seen.events;
 const success=frames.filter(s=>s.text==='sent to the dream');
 const first=success[0]?.t??null,last=success.at(-1)?.t??null;
 const departing=success.filter(s=>first!==null&&s.t-first>4500);
 // #442: the departure transition's window, isolated from the arrival by
 // time (arrival fires near `first`; departure near `first+5000`).
 const win=transitionWindow(events,'opacity',first!==null?first+4000:-Infinity);
 const inside=framesInWindow(departing,win), sampled=inside>=2;
 notes.push(`main race first=${first} last=${last} final="${frames.at(-1).text}" open=${frames.at(-1).open}`);
 // #444: `dur` is DIAGNOSTIC only — logged so a future reader can re-measure.
 // Do NOT assert it against the declared .35s on .cmdmsg. Measured 2026-07-28
 // at load 36–42 on 16 cores (6 confirmation runs, main departure):
 //   durs ms = [239.4, 371.4, 354.0, 328.8, 307.4, 348.2]  (declared 350)
 // #442 under 8 burners: 289–665ms for the same gesture. A ±20% band around
 // 350 (280–420) fails the green set on 239.4; a band wide enough for 665
 // only excludes pathologies the STYLE constant already forbids. Existence
 // (win.ran) + the styleguide's single-source rule is the contract.
 notes.push(`main departure: transition ran=${win.ran} dur=${win.dur}ms; ${inside}/${departing.length} frames inside window`);
 ok('main success appears after typing during POST',first!==null);
 ok('main success remains readable for about 5s',first!==null&&last-first>=4500);
 // #442 MOTION: when the trace sampled inside the window, midFrames/midStates
 // are direct evidence. When it did not (rAF starved by the page's #dreambg
 // shader + host load — measured at 0 frames inside the window in 6/6 runs
 // under contention, and intermittently at baseline), transition registration
 // is the fallback: the browser animated it, so intermediate values existed
 // whether or not the sampler caught them.
 ok('main success departs through intermediate opacity and drift',
    win.ran&&(sampled
      ?midFrames(departing.map(s=>s.op))>=1&&midStates(departing.map(s=>s.tf))>=1
      :true));
 // #442 SNAP DETECTOR: a CSS transition registered for the opacity change.
 // A snap (transition removed from CSS, or the .depart class never applied)
 // never fires transitionstart. This line cannot be defeated by frame rate
 // because it asks the browser whether it animated, not how many frames the
 // sampler caught — the load-independent half of #414's snap detection.
 // #444: deliberately NO duration floor beside this. See notes above.
 ok('main departure runs a CSS transition rather than snapping',win.ran);
 ok('main success clears instead of remaining forever',frames.at(-1).text==='');
 ok('typing keeps the panel open independently',frames.at(-1).open);
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
  // #442: same transition-event capture as the main trace, on pmsg.
  const seen=await pp.evaluate(`new Promise(res=>{const m=pmsg,seen=[],t0=performance.now();const events=[];let done=false;const finish=()=>{if(!done){done=true;res({frames:seen,events})}};const onT=type=>e=>{if(e.propertyName==='opacity'||e.propertyName==='transform')events.push({type,prop:e.propertyName,t:Math.round((performance.now()-t0)*10)/10});if(type==='end'&&e.propertyName==='opacity'&&(performance.now()-t0)>4000)setTimeout(finish,400)};m.addEventListener('transitionrun',onT('run'));m.addEventListener('transitionstart',onT('start'));m.addEventListener('transitionend',onT('end'));pform.requestSubmit();(function f(){const cs=getComputedStyle(m),t=performance.now()-t0;seen.push({t:Math.round(t),text:m.textContent,op:Math.round(parseFloat(cs.opacity)*100),tf:cs.transform});t<8500?requestAnimationFrame(f):finish()})()})`);
  const pframes=seen.frames, pevents=seen.events;
  const success=pframes.filter(s=>s.text==='sent to the dream'),first=success[0]?.t??null;
  const arrival=success.filter(s=>first!==null&&s.t-first<500),departure=success.filter(s=>first!==null&&s.t-first>4500);
  // #442: arrival = first opacity transition; departure = last after the hold.
  const awin=transitionWindow(pevents,'opacity',0,'first');
  const dwin=transitionWindow(pevents,'opacity',first!==null?first+4000:-Infinity);
  const aIn=framesInWindow(arrival,awin), dIn=framesInWindow(departure,dwin);
  // #444: dur diagnostic-only here too (same refusal as main). Pre-pair-fix
  // popout departure reported negative durs (−68, −70, −178) when an orphan
  // end from a pre-afterT transition was paired with a later start.
  notes.push(`popout arrival: transition ran=${awin.ran} dur=${awin.dur}ms; ${aIn}/${arrival.length} frames inside window`);
  notes.push(`popout departure: transition ran=${dwin.ran} dur=${dwin.dur}ms; ${dIn}/${departure.length} frames inside window`);
  // #442: same snap-detector + sampled/unsampled motion structure as main.
  ok('popout success arrives through intermediate opacity and drift',
     awin.ran&&(aIn>=2
       ?midFrames(arrival.map(s=>s.op))>=1&&midStates(arrival.map(s=>s.tf))>=1
       :true));
  ok('popout arrival runs a CSS transition rather than snapping',awin.ran);
  ok('#291 popout is intentionally persistent beyond main courtesy close',
     !pp.isClosed() && pframes.some(s=>s.t>=2200&&s.text==='sent to the dream'));
  ok('popout success remains readable for about 5s',success.length&&success.at(-1).t-success[0].t>=4500);
  ok('popout success departs through intermediate opacity and drift',
     dwin.ran&&(dIn>=2
       ?midFrames(departure.map(s=>s.op))>=1&&midStates(departure.map(s=>s.tf))>=1
       :true));
  // #444: no duration floor — existence only, as on main.
  ok('popout departure runs a CSS transition rather than snapping',dwin.ran);
  ok('popout success self-dismisses',pframes.at(-1).text==='');
 }
 await c.close();
}

// Reduced motion preserves the lifecycle and legibility but has no visual ramp.
{
 const {c,p}=await page(true);
 await p.evaluate(()=>{const f=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/command'))await new Promise(r=>setTimeout(r,400));return f(...a)}});
 await p.fill('#cmdtext','reduced lifecycle');await p.locator('#cmdform').evaluate(f=>f.requestSubmit());
 await sleep(100);await p.fill('#cmdtext','next reduced thought');
 const seen=await p.evaluate(trace(8500));const success=seen.frames.filter(s=>s.text==='sent to the dream');
 ok('reduced success remains readable through the hold',success.length&&success.at(-1).t-success[0].t>=4500);
 ok('reduced success never ramps opacity or transform',success.every(s=>s.op>=95&&s.tf==='none'));
 ok('reduced success clears on schedule',seen.frames.at(-1).text==='');await c.close();
}
ok('no page errors',errs.length===0);await br.close();
finish();
