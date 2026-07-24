import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs';
mkdirSync(OUT, { recursive: true });
const OFFSETS = [150, 450, 900, 1400];

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const log = [];

// ---------- 1. click a question's review link -> dock + FLIP ----------
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(BASE + '/questions', { waitUntil: 'networkidle' });
await sleep(1200);
await page.screenshot({ path: `${OUT}/00-questions.png` });
const linkInfo = await page.evaluate(() => {
  const a = document.querySelector('.qa a.rev');
  return a ? { href: a.getAttribute('href'), rect: a.closest('.qa').getBoundingClientRect() } : null;
});
log.push('review link found: ' + JSON.stringify(linkInfo && linkInfo.href));
const framesBefore = await page.evaluate(() => window.dreambg.frames);
const t0 = Date.now();
await page.click('.qa a.rev');
const samples = [];
for (const off of OFFSETS) {
  await sleep(Math.max(0, off - (Date.now() - t0)));
  await page.screenshot({ path: `${OUT}/01-dock-t${off}.png` });
  samples.push({ off, ...(await page.evaluate(() => ({
    url: location.pathname + location.search,
    review: document.body.classList.contains('review'),
    dock: !!document.getElementById('qdock'),
    iframe: !!document.getElementById('reviewframe'),
    iframeSrc: document.getElementById('reviewframe')?.getAttribute('src'),
    dockXform: document.getElementById('qdock')?.style.transform || '(none)',
    frames: window.dreambg.frames,
  }))) });
}
await sleep(Math.max(0, 2400 - (Date.now() - t0)));
const settled = await page.evaluate(() => ({
  url: location.pathname + location.search,
  review: document.body.classList.contains('review'),
  dockTitle: document.querySelector('#qdock .qt')?.textContent,
  dockHasAnswerBox: !!document.querySelector('#qdock textarea'),
  dockXform: document.getElementById('qdock')?.style.transform || '(cleared)',
  dockFilter: document.getElementById('qdock')?.style.filter || '(cleared)',
  iframeSrc: document.getElementById('reviewframe')?.getAttribute('src'),
  frames: window.dreambg.frames,
}));
await page.screenshot({ path: `${OUT}/02-docked-settled.png` });
log.push('samples: ' + JSON.stringify(samples, null, 1));
log.push('settled: ' + JSON.stringify(settled));

// verify the iframe actually rendered the artifact
const frameText = await (async () => {
  const fr = page.frames().find(f => f.url().includes('/reviewraw'));
  if (!fr) return '(no iframe frame)';
  try { return (await fr.locator('body').innerText()).slice(0, 60); } catch (e) { return '(err ' + e.message + ')'; }
})();
log.push('iframe body text: ' + JSON.stringify(frameText));

// ---------- 2. answer from the docked question ----------
await page.fill('#qdock textarea', 'Approved: 5-min cadence, draft-only, per-repo.');
const answerResp = await page.evaluate(async () => {
  const btn = document.querySelector('#qdock button');
  btn.click();
  await new Promise(r => setTimeout(r, 400));
  return 'clicked';
});
log.push('answer submit: ' + answerResp);

// ---------- 3. back button returns to questions ----------
await page.goBack();
await sleep(1600);
const afterBack = await page.evaluate(() => ({
  url: location.pathname, review: document.body.classList.contains('review'),
  view: document.querySelector('#qsections') ? 'questions' : 'other',
  frames: window.dreambg.frames }));
log.push('after back: ' + JSON.stringify(afterBack));

// ---------- 4. deep-load /review WITHOUT a question -> no dock ----------
const p2 = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await p2.goto(BASE + '/review?p=ud-dreamwork-github-review.html', { waitUntil: 'networkidle' });
await sleep(1600);
const deep = await p2.evaluate(() => ({
  review: document.body.classList.contains('review'),
  dock: !!document.getElementById('qdock'),
  iframe: !!document.getElementById('reviewframe'),
  hasCanvas: !!document.getElementById('dreambg') }));
await p2.screenshot({ path: `${OUT}/03-deeplink-nodock.png` });
log.push('deeplink (no q): ' + JSON.stringify(deep));

// ---------- 5. reduced-motion: instant dock, no FLIP ----------
const rmctx = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1280, height: 900 } });
const p3 = await rmctx.newPage();
await p3.goto(BASE + '/questions', { waitUntil: 'networkidle' });
await sleep(400);
await p3.click('.qa a.rev');
await sleep(60);
const rmMid = await p3.evaluate(() => ({
  review: document.body.classList.contains('review'),
  dock: !!document.getElementById('qdock'),
  dockXform: document.getElementById('qdock')?.style.transform || '(none)',
  ghost: document.querySelectorAll('.ghost').length }));
log.push('reduced-motion mid: ' + JSON.stringify(rmMid));

// checks
const checks = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
ok('nav reached /review with q param', settled.url.includes('/review?p=') && settled.url.includes('q='));
ok('body.review width class set', settled.review === true);
ok('iframe embeds /reviewraw artifact', settled.iframeSrc && settled.iframeSrc.includes('/reviewraw'));
ok('iframe rendered artifact body', /incubation|review|dreamwork/i.test(frameText));
ok('question docked with title', !!settled.dockTitle);
ok('docked question has answer box', settled.dockHasAnswerBox === true);
ok('dock FLIP cleared at rest (crisp)', settled.dockXform === '(cleared)' && settled.dockFilter === '(cleared)');
ok('FLIP transform active mid-morph', samples.some(s => s.dockXform && s.dockXform !== '(none)'));
ok('frames monotonic across dock+back', framesBefore < settled.frames && settled.frames < afterBack.frames);
ok('back returns to questions', afterBack.view === 'questions' && afterBack.review === false);
ok('deep-load review shows artifact, no dock', deep.review && deep.iframe && !deep.dock && deep.hasCanvas);
ok('reduced-motion: instant dock, no FLIP transform, no ghost',
   rmMid.dock && rmMid.dockXform === '(none)' && rmMid.ghost === 0 && rmMid.review);

console.log(log.join('\n'));
console.log('----');
console.log(checks.join('\n'));
await browser.close();
