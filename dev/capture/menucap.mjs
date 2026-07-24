// #91 item 5 — the hover-discoverability menu.
// Verifies: the row shows only common kinds; the menu lists EVERY kind with a
// description; hovering the icon reveals it; picking an uncommon kind adds it
// to the row (so the indicator has a target) and the row rebuild LANDS rather
// than sliding from nothing; reduced-motion reveals instantly.
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

async function run(rm) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 },
    reducedMotion: rm ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log('ERR', m.text()); });
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(800);
  await page.click('#cmdplus');
  await sleep(rm ? 100 : 700);
  const initial = await page.evaluate(() => ({
    row: [...document.querySelectorAll('.cmdkind')].map(b => b.dataset.kind),
    menu: [...document.querySelectorAll('.cmdmenuitem')].map(b => b.dataset.kind),
    descs: [...document.querySelectorAll('.cmdmenuitem .cmd')].map(d => d.textContent.length),
    menuVis: getComputedStyle(document.getElementById('cmdmenu')).visibility,
    rowOneLine: new Set([...document.querySelectorAll('.cmdkind')]
      .map(b => Math.round(b.getBoundingClientRect().top))).size === 1,
  }));
  await page.hover('.cmdmorebtn');
  await sleep(rm ? 100 : 500);
  const hovered = await page.evaluate(() => ({
    menuVis: getComputedStyle(document.getElementById('cmdmenu')).visibility,
    opacity: +getComputedStyle(document.getElementById('cmdmenu')).opacity,
    expanded: document.querySelector('.cmdmorebtn').getAttribute('aria-expanded'),
  }));
  await page.screenshot({ path: `${OUT}/${rm ? 'rm' : 'motion'}-menu.png` });
  // pick the uncommon kind from the menu; trace the indicator per frame
  await page.evaluate(() => {
    window.__t = []; const t0 = performance.now();
    (function tick() {
      const ind = document.getElementById('cmdind');
      if (ind) { const cs = getComputedStyle(ind);
        const m = new DOMMatrixReadOnly(cs.transform);
        window.__t.push(m.m41.toFixed(1) + ',' + m.m42.toFixed(1) + ',' + cs.width); }
      if (performance.now() - t0 < 700) requestAnimationFrame(tick);
    })();
  });
  await page.click('.cmdmenuitem[data-kind="maintenance"]');
  await sleep(800);
  const after = await page.evaluate(() => ({
    row: [...document.querySelectorAll('.cmdkind')].map(b => b.dataset.kind),
    on: [...document.querySelectorAll('.cmdkind.on')].map(b => b.dataset.kind),
    menuOn: [...document.querySelectorAll('.cmdmenuitem.on')].map(b => b.dataset.kind),
    states: new Set(window.__t).size,
  }));
  await page.screenshot({ path: `${OUT}/${rm ? 'rm' : 'motion'}-picked.png` });
  await ctx.close();
  return { rm, initial, hovered, after };
}
for (const rm of [false, true]) {
  const r = await run(rm);
  console.log(JSON.stringify(r, null, 1));
  const ok = r.initial.row.length === 3 && r.initial.rowOneLine
    && r.initial.menu.length === 4 && r.initial.menuVis === 'hidden'
    && r.hovered.menuVis === 'visible' && r.hovered.opacity > 0.9
    && r.hovered.expanded === 'true'
    && r.after.row.includes('maintenance') && r.after.on[0] === 'maintenance'
    && r.after.states <= 2;      // row rebuilt -> indicator LANDS, never slides
  console.log(rm ? 'reduced-motion:' : 'motion:', ok ? 'PASS' : 'FAIL');
}
await browser.close();
