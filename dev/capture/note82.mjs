import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`; const sleep=ms=>new Promise(r=>setTimeout(r,ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT,{recursive:true});
const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl']});
const p=await b.newPage({viewport:{width:1000,height:900}});
const posts=[]; p.on('request',r=>{ if(r.url().endsWith('/comment')) posts.push(r.method()); });
await p.goto(BASE + '/questions',{waitUntil:'networkidle'});
// #536 render readiness — wait for the .notebox surface the guard reads first, not a fixed sleep (#428 class)
await waitFor(p, '.notebox');
const layout = await p.evaluate(()=>({
  noteBoxes: document.querySelectorAll('.notebox').length,
  threads: document.querySelectorAll('.thread').length,
  follows: [...document.querySelectorAll('.follow')].map(f=>f.textContent),
  answeredEntries: document.querySelectorAll('.aentry').length }));
await p.screenshot({path:`${OUT}/questions-threads.png`, fullPage:true});
// add a note to the OPEN question (first notebox, key o0) via Ctrl+Enter
await p.fill('#nbo0','a follow-up on the open one');
await p.focus('#nbo0'); await p.keyboard.press('Control+Enter');
await sleep(300);
const afterOpen = await p.evaluate(()=>({ firstThreadFollows:[...document.querySelectorAll('.qa .follow')].map(f=>f.textContent) }));
// add a note to the ANSWERED (folded) entry (key a0)
await p.fill('#nba0','a note on the folded one');
await p.click(`button[onclick="sendComment('a0')"]`);
await sleep(300);
const afterAns = await p.evaluate(()=>({ aentryFollows:[...document.querySelectorAll('.aentry .follow')].map(f=>f.textContent) }));
await p.screenshot({path:`${OUT}/after-notes.png`, fullPage:true});
console.log('layout: '+JSON.stringify(layout));
console.log('afterOpen: '+JSON.stringify(afterOpen));
console.log('afterAns: '+JSON.stringify(afterAns));
console.log('posts to /comment: '+JSON.stringify(posts));
const checks=[];
const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
ok('note box on every entry (>=3)', layout.noteBoxes>=3);
ok('existing follow-up thread rendered', layout.follows.some(f=>/reconsider/.test(f)));
ok('answered entries rendered structured', layout.answeredEntries===1);
ok('note added to OPEN entry via Ctrl+Enter', afterOpen.firstThreadFollows.some(f=>/follow-up on the open/.test(f)));
ok('note added to ANSWERED entry', afterAns.aentryFollows.some(f=>/note on the folded/.test(f)));
ok('both notes POSTed to /comment', posts.filter(m=>m==='POST').length>=2);
console.log('----'); console.log(checks.join('\n'));
await b.close();
