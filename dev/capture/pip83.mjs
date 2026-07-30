import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`; const sleep=ms=>new Promise(r=>setTimeout(r,ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT,{recursive:true});
const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl']});
const p=await b.newPage({viewport:{width:1000,height:820}});
await p.goto(BASE + '/',{waitUntil:'networkidle'});
// #536 render readiness — wait for the .pipbtn affordance the guard counts first, not a fixed sleep (#428 class)
await waitFor(p, '.pipbtn');
const dash = await p.evaluate(()=>({ pip: document.querySelectorAll('.pipbtn').length,
  reviewsHavePip: !!document.querySelector('#sections .pipbtn') }));
await p.screenshot({path:`${OUT}/dashboard-pip.png`});
// click the first review's pip button -> popout
const popupP = p.waitForEvent('popup',{timeout:2500}).catch(()=>null);
await p.click('#sections .pipbtn');
const popup = await popupP;
let popInfo='(none)';
if (popup) {
  await popup.waitForLoadState('domcontentloaded').catch(()=>{});
  await sleep(400);
  popInfo = await popup.evaluate(()=>({ title: document.title,
    ident: document.querySelector('.ptitle')?.textContent,
    path: document.querySelector('.ppath')?.textContent,
    hasIframe: !!document.querySelector('iframe'),
    iframeSrc: document.querySelector('iframe')?.getAttribute('src') }));
  await popup.screenshot({path:`${OUT}/popout-doc.png`});
}
// file view pip + review view pip present?
await p.goto(BASE + '/file?p=.dreamwork/lessons.md',{waitUntil:'networkidle'}); await sleep(600);
const filePip = await p.evaluate(()=>!!document.querySelector('#meta .pipbtn'));
await p.goto(BASE + '/review?p=ud-dreamwork-github-review.html',{waitUntil:'networkidle'}); await sleep(600);
const reviewPip = await p.evaluate(()=>!!document.querySelector('#meta .pipbtn'));
console.log('dashboard: '+JSON.stringify(dash));
console.log('popout: '+JSON.stringify(popInfo));
console.log('filePip: '+filePip+'  reviewPip: '+reviewPip);
const checks=[];
const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
ok('pip buttons on dashboard reviews', dash.reviewsHavePip);
ok('file view has pip button', filePip);
ok('review view has pip button', reviewPip);
if (popup) {
  ok('popout identifies project (name)', /dreamwork|vtarget/.test(popInfo.ident||''));
  ok('popout has path', !!popInfo.path);
  ok('popout embeds artifact iframe (/reviewraw)', (popInfo.iframeSrc||'').includes('/reviewraw'));
} else ok('popout opened', false);
console.log('----'); console.log(checks.join('\n'));
await b.close();
