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
utimesSync(join(rd, 'a.html'), 1_700_000_000, 1_700_000_000);
utimesSync(join(rd, 'z.html'), 1_700_000_100, 1_700_000_100);
const srv = spawn('python3', ['-u', 'watch.py', '--target', target, '--port', '0'], { stdio: ['ignore', 'pipe', 'inherit'] });
const line = await new Promise((resolve, reject) => { let s=''; srv.stdout.on('data', b => { s += b; const m=s.match(/http:\/\/[^:]+:(\d+)/); if(m) resolve(m[1]); }); srv.on('exit', reject); });
const base = `http://127.0.0.1:${line}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const checks=[]; const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
async function run(reduced) {
  const br = await chromium.launch({args:['--use-gl=swiftshader']});
  const p = await br.newPage({viewport:{width:1000,height:1100}, reducedMotion: reduced?'reduce':'no-preference'});
  await p.goto(base, {waitUntil:'networkidle'}); await sleep(300);
  const premise = await p.evaluate(() => [...document.querySelectorAll('[data-review]')].map(n=>({key:n.dataset.review,node:n,top:n.getBoundingClientRect().top})).map(x=>({key:x.key,top:x.top})));
  const trace = p.evaluate(() => new Promise(res => { const out=[], t0=performance.now(); (function f(){out.push([...document.querySelectorAll('[data-review]')].map(n=>({key:n.dataset.review,top:n.getBoundingClientRect().top,node:n})).map(x=>({key:x.key,top:x.top}))); performance.now()-t0<3500?requestAnimationFrame(f):res(out)})() }));
  await sleep(100); const next = reduced ? 1_700_000_500 : 1_700_000_300;
  utimesSync(join(rd,'a.html'), next, next);
  await p.evaluate(() => fetch('/command', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:'review reorder guard', kind:'steer'})}));
  const seen=await trace; const final=seen.at(-1); const changed=seen.findIndex(f=>f.map(x=>x.key).join('|')!==premise.map(x=>x.key).join('|'));
  ok(`${reduced?'reduced':'normal'}: stable keyed review rows exist`, premise.length>=2 && premise.every(x=>x.key));
  ok(`${reduced?'reduced':'normal'}: old and new orders differ`, changed>=0 && final.map(x=>x.key).join('|')!==premise.map(x=>x.key).join('|'));
  for (const old of premise) { const last=final.find(x=>x.key===old.key); if(!last||Math.abs(last.top-old.top)<2) continue; const tops=seen.slice(Math.max(0,changed-1)).map(f=>(f.find(x=>x.key===old.key)||{}).top).filter(Number.isFinite); const distinct=new Set(tops.map(Math.round)).size; const lo=Math.min(old.top,last.top)-1.5, hi=Math.max(old.top,last.top)+1.5; ok(`${reduced?'reduced':'normal'}: ${old.key} ${reduced?'reorders instantly without transition':'travels through intermediate Y positions without overshoot'}`, reduced ? distinct<=3 : distinct>=6 && tops.every(y=>y>=lo&&y<=hi)); }
  await br.close();
}
try { await run(false); utimesSync(join(rd,'z.html'),1_700_000_400,1_700_000_400); await run(true); } finally { srv.kill(); }
console.log(checks.join('\n')); process.exitCode=checks.some(x=>x.startsWith('FAIL'))?1:0;
