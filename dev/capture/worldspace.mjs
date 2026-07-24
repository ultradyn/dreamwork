// #74/#91 — prove the shader field is WORLD-space, not window-space.
// Technique: freeze Date.now() via addInitScript so the wall-clock phase is
// identical across captures (the field is otherwise time-varying and two
// screenshots can never be simultaneous), hide #view for a clean plate, and
// switch to layer 1 (raw fractal) so the per-window lens (tilt-shift focus)
// is out of the comparison. Then the SAME screen position in windows of
// DIFFERENT heights must show the SAME pixels.
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const BASE = process.argv[2] || 'http://127.0.0.1:39885';
const OUT = process.argv[3] || '/tmp/shots-world';
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

// A 300x300 plate anchored to the window's TOP-LEFT. Both windows sit at
// screen (0,0) in headless, so that plate covers the same screen rectangle
// whatever the window height -> world-space means identical pixels.
async function plate(height) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height } });
  await ctx.addInitScript(() => { const T = 1771000000000; Date.now = () => T; });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(900);
  await page.evaluate(() => { document.getElementById('view').style.display = 'none'; });
  await page.keyboard.press('l');                    // layer 1: raw fractal
  await sleep(500);
  const buf = await page.screenshot({ clip: { x: 0, y: 0, width: 300, height: 300 } });
  await page.screenshot({ path: `${OUT}/plate-${height}.png`, clip: { x: 0, y: 0, width: 300, height: 300 } });
  await ctx.close();
  return buf;
}
const a = await plate(820);
const b = await plate(500);
// compare decoded pixels
const cmp = await (async () => {
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  const r = await p.evaluate(async ([da, db]) => {
    const load = u => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.src = u; });
    const [ia, ib] = await Promise.all([load(da), load(db)]);
    const cv = document.createElement('canvas'); cv.width = 300; cv.height = 300;
    const g = cv.getContext('2d');
    g.drawImage(ia, 0, 0); const A = g.getImageData(0, 0, 300, 300).data;
    g.clearRect(0, 0, 300, 300);
    g.drawImage(ib, 0, 0); const B = g.getImageData(0, 0, 300, 300).data;
    let maxd = 0, sum = 0, n = 0, spread = [255, 0];
    for (let i = 0; i < A.length; i += 4) {
      for (let c = 0; c < 3; c++) {
        const d = Math.abs(A[i+c] - B[i+c]); maxd = Math.max(maxd, d); sum += d; n++;
      }
      spread[0] = Math.min(spread[0], A[i]); spread[1] = Math.max(spread[1], A[i]);
    }
    return { maxDiff: maxd, meanDiff: +(sum/n).toFixed(3), plateSpread: spread };
  }, ['data:image/png;base64,' + a.toString('base64'),
      'data:image/png;base64,' + b.toString('base64')]);
  await ctx.close(); return r;
})();
console.log('820px vs 500px window, same screen rect:', JSON.stringify(cmp));
console.log(cmp.maxDiff <= 2 && cmp.plateSpread[1] - cmp.plateSpread[0] > 30
  ? 'PASS — world-space (identical field, and the plate is real detail not flat)'
  : 'FAIL — field differs with window height (or the plate is flat)');
await browser.close();
