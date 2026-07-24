import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';

// beautycap.mjs BASE OUT
// Captures a navigation at several mid-transition timestamps so motion can be
// judged across frames, plus a settled shot. Two scenarios: dashboard->questions
// and questions->file. Records frames (continuity), warp pulse, ghost presence.
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const OFFSETS = [150, 400, 800, 1200];   // ms after nav to snapshot
const sleep = ms => new Promise(r => setTimeout(r, ms));

import { mkdirSync } from 'node:fs';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const page = await browser.newPage({ viewport: { width: 1000, height: 820 } });
const log = [];
const probe = () => page.evaluate(() => ({
  frames: window.dreambg ? window.dreambg.frames : null,
  warp: window.dreambg && 'warp' in window.dreambg ? +(+window.dreambg.warp).toFixed(3) : null,
  tint: window.dreambg ? +window.dreambg.tint.toFixed(3) : null,
  ghost: document.querySelectorAll('.ghost').length,
  viewFilter: document.getElementById('view')?.style.filter || '(none)',
}));

async function scenario(tag, navFn) {
  const before = await probe();
  const t0 = Date.now();
  await navFn();
  const samples = [];
  let prev = 0;
  for (const off of OFFSETS) {
    await sleep(Math.max(0, off - (Date.now() - t0)));
    const s = await probe();
    await page.screenshot({ path: `${OUT}/${tag}-t${off}.png` });
    samples.push({ off, ...s });
  }
  await sleep(2200 - (Date.now() - t0));
  const settled = await probe();
  await page.screenshot({ path: `${OUT}/${tag}-settled.png` });
  log.push(`== ${tag} ==`);
  log.push(`  before: ${JSON.stringify(before)}`);
  for (const s of samples) log.push(`  ${JSON.stringify(s)}`);
  log.push(`  settled: ${JSON.stringify(settled)}`);
  return { before, samples, settled };
}

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(1400);
await page.screenshot({ path: `${OUT}/00-dashboard-settled.png` });

const s1 = await scenario('dash-to-q', () => page.click('a.q'));
const s2 = await scenario('q-to-file', () =>
  page.evaluate(() => navigate('file', '.dreamwork/lessons.md', { push: true })));

// continuity + settle checks
const checks = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const framesMono = [s1.before, ...s1.samples, s1.settled, ...s2.samples, s2.settled]
  .map(x => x.frames);
ok('frames strictly monotonic across both navs',
   framesMono.every((v, i) => i === 0 || v > framesMono[i - 1]));
ok('ghost gone once settled (both)', s1.settled.ghost === 0 && s2.settled.ghost === 0);
ok('view filter cleared at rest (both)',
   s1.settled.viewFilter === '(none)' && s2.settled.viewFilter === '(none)');

console.log(log.join('\n'));
console.log('----');
console.log(checks.join('\n'));
await browser.close();
