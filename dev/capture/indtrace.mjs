// #91 item 4 — per-frame trace of the composer's sliding selection indicator.
// Two things must both hold, and a single screenshot can prove neither:
//   * on OPEN it must SNAP under the active kind (an indicator that animates
//     up from its 0-width start reads as a glitch — the enter-snap rule);
//   * on SELECT it must SLIDE (intermediate positions), and under
//     reduced-motion it must jump with no intermediates.
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:39885';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

async function run(rm) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 },
    reducedMotion: rm ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(800);
  // arm a per-frame recorder BEFORE the click so frame 0 is the start state
  const arm = () => page.evaluate(() => {
    window.__trace = [];
    const ind = document.getElementById('cmdind');
    const t0 = performance.now();
    (function tick() {
      const cs = getComputedStyle(ind);
      const m = new DOMMatrixReadOnly(cs.transform);
      window.__trace.push([+(performance.now() - t0).toFixed(0),
                           +m.m41.toFixed(1), +m.m42.toFixed(1),
                           +parseFloat(cs.width).toFixed(1)]);
      if (performance.now() - t0 < 700) requestAnimationFrame(tick);
    })();
  });
  await arm();
  await page.click('#cmdplus');
  await sleep(800);
  const openTrace = await page.evaluate(() => window.__trace);
  await arm();
  await page.click('.cmdkind[data-kind="maintenance"]');
  await sleep(800);
  const selTrace = await page.evaluate(() => window.__trace);
  const state = await page.evaluate(() => ({
    checked: [...document.querySelectorAll('.cmdkind')]
      .filter(b => b.getAttribute('aria-checked') === 'true').map(b => b.dataset.kind),
    on: [...document.querySelectorAll('.cmdkind.on')].map(b => b.dataset.kind),
  }));
  await page.screenshot({ path: `/tmp/shots-ind/${rm ? 'rm' : 'motion'}.png` });
  await ctx.close();
  // distinct x positions during the OPEN window, ignoring the pre-open frames
  const xs = t => [...new Set(t.map(f => f[1] + ',' + f[2] + ',' + f[3]))];
  const settled = t => t[t.length - 1];
  return { rm, openXs: xs(openTrace).length, openSettled: settled(openTrace),
           selXs: xs(selTrace).length, selSettled: settled(selTrace), state };
}
import { mkdirSync } from 'node:fs'; mkdirSync('/tmp/shots-ind', { recursive: true });
for (const rm of [false, true]) {
  const r = await run(rm);
  console.log(JSON.stringify(r));
  const openOK = r.openXs <= 2;                       // start + landed, no tween
  const selOK = r.rm ? r.selXs <= 2 : r.selXs >= 5;   // slide vs jump
  console.log(`  open ${openOK ? 'SNAP ok' : 'FAIL (tweened in)'} · ` +
              `select ${selOK ? (r.rm ? 'jump ok' : 'slide ok') : 'FAIL'}`);
}
await browser.close();
