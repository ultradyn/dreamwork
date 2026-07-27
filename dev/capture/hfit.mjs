// #312 — no route scrolls the page sideways at phone width.
//
// The command menu (`.cmdmenu`) lives in the PERSISTENT chrome, so it is on
// every route. It is `position:absolute` anchored to the ⋯ button at the
// right end of the command-kinds row, and it used to declare
// `width:max(32ch,100%)` with `left:0` — so it grew rightward from the ⋯
// and poked ~122px past a 390px viewport. A `visibility:hidden` box is still
// LAID OUT (it is not `display:none`), so it counts toward
// `documentElement.scrollWidth` whether the palette is open or shut, and a
// phone could thumb the whole dashboard sideways. watch-design.md forbids
// that; this guard is the red light for it.
//
// Ordinary guard shape: takes (OUT, PORT) — an output dir and a running
// watch server on the fixture. See dev/capture/README.md.
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39890';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

const PHONE = { width: 390, height: 844 };        // iPhone 12/13/14 class
// Every route reachable by plain navigation (the param-less ones). The
// chrome carries the menu onto each, so each is checked in its own right.
const ROUTES = [
  ['dashboard', '/'],
  ['questions', '/questions'],
  ['answers',   '/answers'],
];
const log = [];
const checks = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);

// Measure the document's horizontal overflow AND name the element whose right
// edge is furthest past the viewport, so a red names the offender rather than
// only the number. `visibility:hidden` keeps layout, so a hidden box that
// pokes out is still found here; `display:none` reads zeros and is skipped.
async function measure(page) {
  return page.evaluate(() => {
    const de = document.documentElement;
    let culprit = null, maxRight = de.clientWidth;
    for (const el of document.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;   // display:none / never laid out
      if (r.right > maxRight + 0.5) { maxRight = r.right; culprit = el; }
    }
    const id = culprit && culprit.id ? '#' + culprit.id
      : culprit && culprit.className ? '.' + String(culprit.className).split(/\s+/)[0]
      : culprit ? culprit.tagName.toLowerCase() : null;
    return {
      scrollWidth: de.scrollWidth,
      clientWidth: de.clientWidth,
      overflow: de.scrollWidth - de.clientWidth,
      culprit: id,
      culpritRight: culprit ? +culprit.getBoundingClientRect().right.toFixed(1) : null,
    };
  });
}

// ── 0. Precondition: the subject this guard exists for must actually be in
//    the DOM, or "no overflow" is satisfied by an absent subject. The palette
//    carries the menu; the menu must carry at least one item rendered from
//    COMMANDS, or it has no width to overflow with. (README: "Run it against
//    nothing" / "Absence costs one line, not a timeout.")
{
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(700);
  const subj = await page.evaluate(() => {
    const pal = document.getElementById('cmdpalette');
    const menu = document.getElementById('cmdmenu');
    return {
      palette: !!pal,
      menu: !!menu,
      items: menu ? menu.querySelectorAll('.cmdmenuitem').length : 0,
    };
  });
  log.push('subject: ' + JSON.stringify(subj));
  ok('command palette present in chrome', subj.palette);
  ok('cmd menu present and populated (guard is non-vacuous)',
     subj.menu && subj.items > 0);
  await ctx.close();
}

// ── 1. The contract, per route, palette CLOSED: the document never scrolls
//    sideways at phone width. The shipped bug is here — the hidden menu is
//    laid out off-screen and still pushes scrollWidth out.
for (const [name, path] of ROUTES) {
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + path, { waitUntil: 'networkidle' });
  await sleep(500);
  const m = await measure(page);
  await page.screenshot({ path: `${OUT}/${name}-closed.png` });
  log.push(`${name} closed: scrollWidth=${m.scrollWidth} clientWidth=${m.clientWidth} `
         + `overflow=${m.overflow}px culprit=${m.culprit} right=${m.culpritRight}`);
  ok(`${name}: no horizontal scroll at 390px closed `
   + `(overflow ${m.overflow}px${m.culprit ? ', ' + m.culprit : ''})`,
     m.overflow <= 0);
  await ctx.close();
}

// ── 2. The contract with the menu actually OPEN, on the dashboard: a fix
//    that only suppresses the closed-state overflow (e.g. display:none until
//    hovered) would re-introduce it the moment he opens the palette and
//    hovers the ⋯. The real-world failure is a phone scrolling sideways while
//    he uses the composer, so the open state is checked too.
{
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(500);
  await page.click('#cmdplus');
  await sleep(600);                                 // palette reveal (.5s)
  await page.hover('.cmdmorebtn');
  await sleep(500);                                 // menu reveal (.34s)
  const m = await measure(page);
  await page.screenshot({ path: `${OUT}/dashboard-menu-open.png` });
  log.push(`dashboard menu-open: scrollWidth=${m.scrollWidth} clientWidth=${m.clientWidth} `
         + `overflow=${m.overflow}px culprit=${m.culprit} right=${m.culpritRight}`);
  ok(`dashboard: no horizontal scroll at 390px with menu open `
   + `(overflow ${m.overflow}px${m.culprit ? ', ' + m.culprit : ''})`,
     m.overflow <= 0);
  await ctx.close();
}

console.log(log.join('\n'));
console.log('----');
console.log(checks.join('\n'));
await browser.close();
if (checks.some(c => c.startsWith('FAIL'))) process.exit(1);
