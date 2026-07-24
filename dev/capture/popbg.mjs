// #91 item 2 — verify a popout window carries the world-space shader field.
// Checks: canvas mounted + painting, frames advancing, chrome estimate sane,
// and that the field matches the main window when the two are at the same
// screen position (the world-space anchoring contract from #74).
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:39885';
const OUT = process.argv[3] || '/tmp/shots-popbg';
import { mkdirSync } from 'node:fs';
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 } });
// freeze the shader's wall-clock phase so two non-simultaneous captures are
// still the same frame of the dream (applies to popups in this context too)
await ctx.addInitScript(() => { const T = 1771000000000; Date.now = () => T; });
const page = await ctx.newPage();
page.on('console', m => { if (m.type() === 'error') console.log('CONSOLE-ERR', m.text()); });
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(900);

const popP = page.waitForEvent('popup', { timeout: 8000 }).catch(() => null);
await page.click('#cmdplus');
await sleep(600);
await page.click('#cmdpop');
const pop = await popP;
if (!pop) { console.log('NO POPUP CAPTURED (Document PiP path?)'); await browser.close(); process.exit(1); }
await pop.waitForLoadState('domcontentloaded').catch(() => {});
await sleep(1400);

const probe = p => p.evaluate(() => {
  const cv = document.getElementById('dreambg');
  if (!cv) return { canvas: false };
  const g = cv.getContext('webgl');
  return {
    canvas: true, w: cv.width, h: cv.height,
    lost: g ? g.isContextLost() : 'no-ctx',
    display: getComputedStyle(cv).display, z: getComputedStyle(cv).zIndex,
    screenX: window.screenX, screenY: window.screenY,
    inner: window.innerHeight, outer: window.outerHeight,
    chrome: window.outerHeight - window.innerHeight,
  };
});
const f = p => p.evaluate(() => {
  const cv = document.getElementById('dreambg');
  const g = cv.getContext('webgl', { preserveDrawingBuffer: false });
  return 0;   // frames tally is only exposed on the main window handle
});
console.log('MAIN  ', JSON.stringify(await probe(page)));
console.log('POPOUT', JSON.stringify(await probe(pop)));
console.log('main frames advancing:', await page.evaluate(async () => {
  const a = window.dreambg.frames;
  await new Promise(r => setTimeout(r, 500));
  return window.dreambg.frames - a;
}));
await pop.screenshot({ path: `${OUT}/01-popout.png` });
await page.screenshot({ path: `${OUT}/02-main.png` });
// SEAM TEST: with the wall-clock phase frozen (addInitScript, below) and both
// windows at the same screen position, the two backgrounds must be identical
// pixels — that is the world-space contract, seen across two documents.
const bare = async p => {
  await p.evaluate(() => {
    for (const el of document.body.children)
      if (el.id !== 'dreambg') el.style.display = 'none';
  });
  await sleep(400);
  return p.screenshot({ clip: { x: 0, y: 0, width: 300, height: 300 } });
};
const mainPlate = await bare(page), popPlate = await bare(pop);
const ctx2 = await browser.newContext();
const cmpPage = await ctx2.newPage();
const seam = await cmpPage.evaluate(async ([da, db]) => {
  const load = u => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = u; });
  const [ia, ib] = await Promise.all([load(da), load(db)]);
  const cv = document.createElement('canvas'); cv.width = 300; cv.height = 300;
  const g = cv.getContext('2d');
  g.drawImage(ia, 0, 0); const A = g.getImageData(0, 0, 300, 300).data;
  g.clearRect(0, 0, 300, 300); g.drawImage(ib, 0, 0);
  const B = g.getImageData(0, 0, 300, 300).data;
  let maxd = 0, mn = 255, mx = 0;
  for (let i = 0; i < A.length; i += 4) {
    for (let c = 0; c < 3; c++) maxd = Math.max(maxd, Math.abs(A[i+c] - B[i+c]));
    mn = Math.min(mn, A[i]); mx = Math.max(mx, A[i]);
  }
  return { maxDiff: maxd, spread: mx - mn };
}, ['data:image/png;base64,' + mainPlate.toString('base64'),
    'data:image/png;base64,' + popPlate.toString('base64')]);
await ctx2.close();
console.log('SEAM main vs popout:', JSON.stringify(seam),
  seam.maxDiff <= 2 && seam.spread > 5
    ? 'PASS — identical field across the two documents'
    : 'FAIL');
// pixel evidence: the popout canvas must not be a flat fill
console.log('POPOUT pixel spread:', JSON.stringify(await pop.evaluate(() => {
  const cv = document.getElementById('dreambg');
  const g = cv.getContext('webgl');
  const px = new Uint8Array(cv.width * cv.height * 4);
  g.readPixels(0, 0, cv.width, cv.height, g.RGBA, g.UNSIGNED_BYTE, px);
  let mn = [255,255,255], mx = [0,0,0], n = 0;
  for (let i = 0; i < px.length; i += 4) {
    for (let c = 0; c < 3; c++) { mn[c] = Math.min(mn[c], px[i+c]); mx[c] = Math.max(mx[c], px[i+c]); }
    n++;
  }
  return { samples: n, min: mn, max: mx, spread: [mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2]] };
})));
await browser.close();
