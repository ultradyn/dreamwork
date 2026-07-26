/* revieworder — #221: a live filesystem-mtime reorder travels by keyed FLIP.
   Own target/server because this guard must drive real artifact mtimes.
   usage: node revieworder.mjs <outdir> <ignored-port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { cpSync, mkdirSync, writeFileSync, utimesSync } from 'node:fs';
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
stamp('a.html', 1_700_000_000); stamp('z.html', 1_700_000_100);
const srv = spawn('python3', ['-u', 'watch.py', '--target', target, '--port', '0'], { stdio: ['ignore', 'pipe', 'inherit'] });
const line = await new Promise((resolve, reject) => { let s=''; srv.stdout.on('data', b => { s += b; const m=s.match(/http:\/\/[^:]+:(\d+)/); if(m) resolve(m[1]); }); srv.on('exit', reject); });
const base = `http://127.0.0.1:${line}`;
const checks=[]; const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
const EPS = .75;
async function run(reduced, sabotage=false) {
  const br = await chromium.launch({args:['--use-gl=swiftshader']});
  try {
    const p = await br.newPage({viewport:{width:1000,height:1100}, reducedMotion: reduced?'reduce':'no-preference'});
    await p.goto(base, {waitUntil:'networkidle'});
    if (sabotage) await p.evaluate(() => { regroupCards = () => {}; });
    const capture = p.evaluate(({epsilon}) => new Promise((resolve, reject) => {
      const frames=[]; let oldOrder=null, oldGeometry=null, changed=-1, natural=null, stableBefore=0, stableAfter=0;
      let previous=null; const started=performance.now();
      const sample = () => [...document.querySelectorAll('[data-review]')].map(n => ({
        key:n.dataset.review, top:n.getBoundingClientRect().top,
        transform:getComputedStyle(n).transform,
        animating:n.getAnimations().some(a=>a.playState!=='finished')
      }));
      const sameGeometry = (a,b) => a && b && a.length===b.length && a.every((x,i)=>x.key===b[i].key && Math.abs(x.top-b[i].top)<=epsilon);
      function frame() {
        const now=sample(), order=now.map(x=>x.key).join('|');
        if (!oldOrder) oldOrder=order;
        if (changed<0) {
          if (order===oldOrder && sameGeometry(previous,now)) stableBefore++; else if (order===oldOrder) stableBefore=0;
          if (order===oldOrder && stableBefore>=3) oldGeometry=now.map(x=>({key:x.key,top:x.top}));
          if (order!==oldOrder) {
            if (!oldGeometry) return reject(new Error('DOM reordered before stable old geometry'));
            changed=frames.length;
            natural=now.map(x => {
              const matrix=x.transform==='none' ? null : new DOMMatrixReadOnly(x.transform);
              return {key:x.key,top:x.top-(matrix ? matrix.m42 : 0)};
            });
          }
        }
        frames.push(now); previous=now;
        if (changed>=0) {
          const intended=order===natural.map(x=>x.key).join('|');
          const atNatural=intended && now.every(x=>Math.abs(x.top-natural.find(y=>y.key===x.key).top)<=epsilon);
          const finished=now.every(x=>x.transform==='none' && !x.animating);
          stableAfter = atNatural && finished && sameGeometry(frames.at(-2),now) ? stableAfter+1 : 0;
          if (stableAfter>=4) return resolve({oldGeometry,natural,frames:frames.slice(Math.max(0,changed-1)),changed:1});
        }
        if (performance.now()-started>6500) return reject(new Error('review reorder did not explicitly settle before timeout'));
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }), {epsilon:EPS});
    await p.waitForFunction(() => {
      const rows=[...document.querySelectorAll('[data-review]')];
      if (rows.length<2) return false;
      const ys=rows.map(n=>n.getBoundingClientRect().top);
      return rows.every(n=>n.dataset.review) && ys.every((y,i)=>i===0 || y>ys[i-1]);
    });
    stamp('a.html', reduced ? 1_700_000_500 : 1_700_000_300);
    await p.evaluate(() => fetch('/command', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:'review reorder guard', kind:'steer'})}));
    const result=await capture;
    const evaluate = () => {
      const {oldGeometry,natural,frames}=result;
      const intended=natural.map(x=>x.key).join('|')!==oldGeometry.map(x=>x.key).join('|');
      const keyed=oldGeometry.length>=2 && natural.length===oldGeometry.length && oldGeometry.every(x=>x.key && natural.some(y=>y.key===x.key));
      const rows=oldGeometry.filter(x=>Math.abs(x.top-natural.find(y=>y.key===x.key).top)>2);
      const motions=rows.map(old=>{
        const last=natural.find(x=>x.key===old.key);
        const tops=frames.map(f=>f.find(x=>x.key===old.key)?.top).filter(Number.isFinite);
        const distinct=new Set(tops.map(y=>Math.round(y*4)/4)).size;
        const lo=Math.min(old.top,last.top)-EPS, hi=Math.max(old.top,last.top)+EPS;
        const first=tops[0];
        return {key:old.key, distinct, bounded:tops.every(y=>y>=lo&&y<=hi), endpoints:Math.abs(first-old.top)<=EPS && Math.abs(tops.at(-1)-last.top)<=EPS};
      });
      return {keyed,intended,rows,motions,pass:keyed&&intended&&rows.length===2&&motions.every(m=>reduced ? m.distinct<=3&&m.endpoints : m.distinct>=8&&m.bounded&&m.endpoints)};
    };
    const verdict=evaluate();
    if (sabotage) return verdict.pass;
    ok(`${reduced?'reduced':'normal'}: stable keyed review rows exist`, verdict.keyed);
    ok(`${reduced?'reduced':'normal'}: old and new orders differ`, verdict.intended);
    for (const m of verdict.motions)
      ok(`${reduced?'reduced':'normal'}: ${m.key} ${reduced?'reorders instantly without transition':'travels through intermediate Y positions without overshoot'}`, reduced ? m.distinct<=3&&m.endpoints : m.distinct>=8&&m.bounded&&m.endpoints);
    return verdict.pass;
  } finally { await br.close(); }
}
try {
  await run(false);
  stamp('z.html',1_700_000_400); await run(true);
  stamp('a.html',1_700_000_000); stamp('z.html',1_700_000_100);
  if (await run(false, true)) throw new Error('self-test: disabled review regroup incorrectly passed normal motion guard');
} finally { srv.kill(); }
console.log(checks.join('\n')); process.exitCode=checks.some(x=>x.startsWith('FAIL'))?1:0;
