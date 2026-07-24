import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:39890';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const b = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const ctx = await b.newContext({ reducedMotion: 'reduce', viewport: { width: 900, height: 700 } });
const p = await ctx.newPage();
await p.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(400);
const framesBefore = await p.evaluate(() => window.dreambg.frames);
await p.click('a.q');
await sleep(60);                                   // would be mid-dissolve normally
const mid = await p.evaluate(() => ({
  ghost: document.querySelectorAll('.ghost').length,
  tint: +window.dreambg.tint.toFixed(4),
  warp: +window.dreambg.warp.toFixed(4),
  view: document.querySelector('#qsections') ? 'questions' : 'other',
  viewFilter: document.getElementById('view')?.style.filter || '(none)',
}));
await sleep(300);
const framesAfter = await p.evaluate(() => window.dreambg.frames);
console.log(JSON.stringify(mid));
const pass = mid.ghost === 0 && Math.abs(mid.tint - 0.14) < 0.001 &&
  mid.warp === 0 && mid.view === 'questions' && mid.viewFilter === '(none)';
console.log(pass
  ? 'PASS reduced-motion: instant swap, no ghost, no warp, tint snapped, no mist filter'
  : 'FAIL reduced-motion');
// static-frame contract: reduced-motion renders on demand, not a rAF loop —
// frames should NOT be climbing on their own.
console.log(`frames idle delta over ~360ms: ${framesAfter - framesBefore} (expect small)`);
await b.close();
