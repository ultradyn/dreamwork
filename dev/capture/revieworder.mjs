/* revieworder — #221: a live filesystem-mtime reorder travels by keyed FLIP.
   Own target/server because this guard must drive real artifact mtimes.
   usage: node revieworder.mjs <outdir> <ignored-port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { cpSync, mkdirSync, readdirSync, statSync, writeFileSync, utimesSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
const OUT = process.argv[2];
mkdirSync(OUT, { recursive: true });
const target = join(OUT, 'target');
cpSync(new URL('./fixture', import.meta.url), target, { recursive: true });
const rd = join(target, '.dreamwork', 'review');
writeFileSync(join(rd, 'a.html'), '<!doctype html><p>a');
writeFileSync(join(rd, 'z.html'), '<!doctype html><p>z');
const stamp = (name, seconds) => utimesSync(join(rd, name), seconds, seconds);
// Preserve nanoseconds in Node: JSON numbers cannot carry this 64-bit oracle.
// The browser proves that the server payload and settled DOM keep this sequence.
const orderedReviewNames = reviews => reviews.sort((a,b) => a.mtimeNs===b.mtimeNs
  ? a.name.localeCompare(b.name) : a.mtimeNs>b.mtimeNs ? -1 : 1).map(review => review.name);
const expectedReviewNames = () => orderedReviewNames(readdirSync(rd).filter(name=>name.endsWith('.html')).map(name => ({
  name, mtimeNs: statSync(join(rd, name), { bigint:true }).mtimeNs
})));
stamp('a.html', 1_700_000_000); stamp('z.html', 1_700_000_100);
const srv = spawn('python3', ['-u', 'watch.py', '--target', target, '--port', '0'], { stdio: ['ignore', 'pipe', 'inherit'] });
const line = await new Promise((resolve, reject) => { let s=''; srv.stdout.on('data', b => { s += b; const m=s.match(/http:\/\/[^:]+:(\d+)/); if(m) resolve(m[1]); }); srv.on('exit', reject); });
const base = `http://127.0.0.1:${line}`;
const checks=[]; const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
const EPS = .75;
/* between() — the frame-rate-free form (transitions.md, dreamfade.mjs).
   A count of distinct Y positions is a fact about how many frames this
   machine drew under load, not about whether the row passed through the
   middle. Zero-versus-some is the snap/travel distinction. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}
async function run(reduced, sabotage='none') {
  const br = await chromium.launch({args:['--use-gl=swiftshader']});
  try {
    const p = await br.newPage({viewport:{width:1000,height:1100}, reducedMotion: reduced?'reduce':'no-preference'});
    await p.goto(base, {waitUntil:'networkidle'});
    if (sabotage==='regroup') await p.evaluate(() => { regroupCards = () => {}; });
    if (sabotage==='wrong-order') await p.evaluate(() => {
      const originalSetLiveContent = setLiveContent;
      setLiveContent = (...args) => {
        const value = originalSetLiveContent(...args);
        if (window.__corruptNextReviewOrder) {
          window.__corruptNextReviewOrder = false;
          const rows = [...document.querySelectorAll('[data-review]')];
          if (rows.length >= 3) rows[0].before(rows[2]);
        }
        return value;
      };
    });
    await p.waitForFunction(() => {
      const rows=[...document.querySelectorAll('[data-review]')];
      if (rows.length<2) return false;
      const ys=rows.map(n=>n.getBoundingClientRect().top);
      return rows.every(n=>n.dataset.review) && ys.every((y,i)=>i===0 || y>ys[i-1]);
    });
    const nextStamp = reduced ? 1_700_000_500 : 1_700_000_300;
    const capture = p.evaluate(({epsilon}) => new Promise((resolve, reject) => {
      const frames=[]; let oldOrder=null, oldGeometry=null, natural=null, stableBefore=0, stableAfter=0, changedFrame=-1;
      let previous=null, causal=null, firstChanged=null, done=false;
      const originalSetData=setData; const started=performance.now(); let expected=null, armed=false;
      window.__reviewGuardReady = false;
      window.__armExpectedReviews = value => { expected=value; armed=true; };
      const sample = () => [...document.querySelectorAll('[data-review]')].map(n => ({
        key:n.dataset.review, top:n.getBoundingClientRect().top,
        transform:getComputedStyle(n).transform,
        animating:n.getAnimations().some(a=>a.playState!=='finished')
      }));
      const orderOf = rows => rows.map(x=>x.key).join('|');
      const sameGeometry = (a,b) => a && b && a.length===b.length && a.every((x,i)=>x.key===b[i].key && Math.abs(x.top-b[i].top)<=epsilon);
      const exactExpected = next => expected && Array.isArray(next?.reviews)
        && next.reviews.length===expected.length
        && next.reviews.every((review,i) => review.name===expected[i]);
      const finish=(fn,value) => { if(done) return; done=true; observer.disconnect(); setData=originalSetData; delete window.__armExpectedReviews; delete window.__reviewGuardReady; fn(value); };
      const fail=message => finish(reject,new Error(message));
      setData=function(next) {
        if (exactExpected(next)) {
          if (causal) return fail('expected review payload reached setData more than once');
          const fresh=sample();
          if (!oldOrder || stableBefore<3) return fail('expected review payload reached setData before stable preframes');
          if (orderOf(fresh)!==oldOrder || !sameGeometry(previous,fresh)) return fail('review order or geometry moved before causal expected setData');
          oldGeometry=fresh.map(x=>({key:x.key,top:x.top}));
          causal={token:Symbol('expected-review-setData'),timestamp:performance.now()};
        }
        return originalSetData(next);
      };
      const noteChange=source => {
        const now=sample(), order=orderOf(now);
        if (!oldOrder || order===oldOrder) return;
        if (!causal) return armed ? fail(`review DOM order changed before causal expected setData (${source})`) : undefined;
        if (!firstChanged) firstChanged={source,timestamp:performance.now(),token:causal.token};
      };
      const observer=new MutationObserver(() => noteChange('mutation'));
      observer.observe(document.querySelector('#review-list') || document.body,{childList:true,subtree:true});
      function frame() {
        if(done) return;
        const now=sample(), order=orderOf(now);
        if (!oldOrder) oldOrder=order;
        if (!causal) {
          if (armed && order!==oldOrder) return fail('review DOM order changed before causal expected setData (frame)');
          if (armed && previous && !sameGeometry(previous,now)) return fail('review geometry moved before causal expected setData (frame)');
          stableBefore=sameGeometry(previous,now) ? stableBefore+1 : 0;
          if (stableBefore>=3) window.__reviewGuardReady=true;
        } else if (!natural && order!==oldOrder) {
          noteChange('frame');
          changedFrame=frames.length;
          if (!firstChanged || firstChanged.token!==causal.token || firstChanged.timestamp<causal.timestamp)
            return fail('first changed mutation/frame was not tied to causal expected setData');
          natural=now.map(x => {
            const matrix=x.transform==='none' ? null : new DOMMatrixReadOnly(x.transform);
            return {key:x.key,top:x.top-(matrix ? matrix.m42 : 0)};
          });
          if (orderOf(natural)!==expected.join('|'))
            return fail('settled natural review order differs from exact filesystem order');
        }
        if (causal) frames.push(now);
        previous=now;
        if (natural) {
          const intended=order===orderOf(natural);
          const atNatural=intended && now.every(x=>Math.abs(x.top-natural.find(y=>y.key===x.key).top)<=epsilon);
          const finished=now.every(x=>x.transform==='none' && !x.animating);
          stableAfter = atNatural && finished && sameGeometry(frames.at(-2),now) ? stableAfter+1 : 0;
          if (stableAfter>=4) {
            if (order!==expected.join('|')) return fail('settled review DOM order differs from exact filesystem order');
            return finish(resolve,{oldGeometry,natural,frames:frames.slice(Math.max(0,changedFrame-1)),causalTimestamp:causal.timestamp,firstChanged:{source:firstChanged.source,timestamp:firstChanged.timestamp},expectedOrder:expected});
          }
        }
        if (performance.now()-started>6500) return fail('review reorder did not explicitly settle before timeout');
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }), {epsilon:EPS}).then(value=>({value}),error=>({error}));
    await p.waitForFunction(() => window.__reviewGuardReady===true);
    stamp('a.html', nextStamp);
    const expected=expectedReviewNames();
    await p.evaluate(expected => window.__armExpectedReviews(expected), expected);
    if (sabotage==='wrong-order') await p.evaluate(() => { window.__corruptNextReviewOrder = true; });
    if (sabotage==='early-reorder') await p.evaluate(() => {
      const rows=[...document.querySelectorAll('[data-review]')];
      rows[0].parentElement.insertBefore(rows.at(-1),rows[0]);
    });
    await p.evaluate(() => fetch('/command', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:'review reorder guard', kind:'steer'})}));
    const outcome=await capture;
    if (outcome.error) throw outcome.error;
    const result=outcome.value;
    const {oldGeometry,natural,frames,expectedOrder}=result;
    const expectedSequence=expectedOrder.join('|');
    const intended=natural.map(x=>x.key).join('|')===expectedSequence && expectedSequence!==oldGeometry.map(x=>x.key).join('|');
    const keyed=oldGeometry.length>=2 && natural.length===oldGeometry.length && oldGeometry.every(x=>x.key && natural.some(y=>y.key===x.key));
    const causal=result.firstChanged.timestamp>=result.causalTimestamp;
    const rows=oldGeometry.filter(x=>Math.abs(x.top-natural.find(y=>y.key===x.key).top)>2);
    const motions=rows.map(old=>{
      const last=natural.find(x=>x.key===old.key);
      const observed=frames.map(f=>f.find(x=>x.key===old.key)?.top).filter(Number.isFinite);
      const tops=[old.top,...observed];
      const partway=between(tops, old.top, last.top);
      const lo=Math.min(old.top,last.top)-EPS, hi=Math.max(old.top,last.top)+EPS;
      return {key:old.key, partway, span:Math.abs(last.top-old.top),
              bounded:tops.every(y=>y>=lo&&y<=hi),
              endpoints:Math.abs(tops[0]-old.top)<=EPS && Math.abs(tops.at(-1)-last.top)<=EPS};
    });
    // Vacuity: span floor is a pixel distance of the fixture layout (literal
    // well below the measured reorder). Part-way is zero-vs-some, not a count.
    const pass=keyed&&intended&&causal&&rows.length===2&&motions.every(m=>
      reduced ? m.partway===0&&m.endpoints
              : m.span>2&&m.partway>=1&&m.bounded&&m.endpoints);
    if (sabotage!=='none') return pass;
    ok(`${reduced?'reduced':'normal'}: expected setData causally precedes first changed ${result.firstChanged.source}`, causal);
    ok(`${reduced?'reduced':'normal'}: stable keyed review rows exist`, keyed);
    ok(`${reduced?'reduced':'normal'}: settled DOM equals exact filesystem order`, intended);
    for (const m of motions) ok(`${reduced?'reduced':'normal'}: ${m.key} ${reduced?'reorders instantly without transition':'travels through intermediate Y positions without overshoot'}`,
      reduced ? m.partway===0&&m.endpoints
              : m.span>2&&m.partway>=1&&m.bounded&&m.endpoints);
    return pass;
  } finally { await br.close(); }
}
try {
  await run(false);
  stamp('z.html',1_700_000_400); await run(true);
  stamp('a.html',1_700_000_000); stamp('z.html',1_700_000_100);
  if (await run(false, 'regroup')) throw new Error('self-test: disabled review regroup incorrectly passed normal motion guard');
  stamp('a.html',1_700_000_000); stamp('z.html',1_700_000_100);
  try {
    await run(false, 'wrong-order');
    throw new Error('self-test: smoothly wrong review order incorrectly passed expected-order guard');
  } catch (error) {
    if (!String(error).includes('differs from exact filesystem order')) throw error;
  }
  const adjacentNs = 1_700_000_000_000_000_000n;
  if (Number(adjacentNs)!==Number(adjacentNs+1n)) throw new Error('self-test: adjacent-nanosecond fixture does not expose Number collision');
  const adjacentOrder=orderedReviewNames([
    {name:'a.html',mtimeNs:adjacentNs},
    {name:'z.html',mtimeNs:adjacentNs+1n}
  ]).join('|');
  if (adjacentOrder!=='z.html|a.html') throw new Error('self-test: exact mtime oracle collapsed adjacent nanoseconds');
  stamp('a.html',1_700_000_000); stamp('z.html',1_700_000_100);
  try {
    await run(false, 'early-reorder');
    throw new Error('self-test: unrelated early DOM reorder incorrectly passed causal guard');
  } catch (error) {
    if (!String(error).includes('before causal expected setData')) throw error;
  }
} finally { srv.kill(); }
console.log(checks.join('\n')); process.exitCode=checks.some(x=>x.startsWith('FAIL'))?1:0;
