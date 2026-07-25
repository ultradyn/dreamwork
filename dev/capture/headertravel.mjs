/* #107 / #108 / #110 — one design, traced per frame.

   The review view is a wider column, so navigating onto or off it RESIZES
   the page. Three things must be true through every frame of that, and a
   before/after screenshot can show none of them:
     #107 the departing view must not RE-WRAP while it is still opaque, and
          the column must travel to its new width rather than snap
     #108 the + opener hangs in the gutter left of the column; the gutter
          shrinks as the column widens, so the clamp has to hold on every
          frame, not just at the two ends
     #110 the heading survives the navigation — the same DOM nodes, moving —
          rather than dissolving and being rebuilt
   So: sample per rAF across the change, in BOTH directions, and again under
   reduced motion (where all of it must be instant).
   usage: node headertravel.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

/* Tag the live heading nodes before navigating. If they are still tagged
   afterwards they are literally the same elements — which is what "the
   heading travels" means, and what a FLIP needs. */
const TRACE = href => `((href, ms) => new Promise(res => {
  const frames = [];
  document.querySelectorAll('#chrome .crumb, #chrome .htitle, #cmdplus')
    .forEach((el, i) => el.dataset.trace = 'n' + i);
  const tagged = document.querySelectorAll('[data-trace]').length;
  // offsetWidth, NOT getBoundingClientRect: the dissolve deliberately lifts
  // the ghost toward the viewer with scale(1.07), which inflates the rect.
  // The question here is whether the ghost RE-LAID-OUT, and layout width is
  // the only measure that answers it.
  const ghostW = () => {
    const g = document.querySelector('.ghost');
    return g ? g.offsetWidth : null;
  };
  const t0 = performance.now();
  (function step() {
    const plus = document.getElementById('cmdplus');
    const title = document.querySelector('#chrome .htitle');
    const wrap = document.querySelector('.wrap');
    frames.push({
      t: Math.round(performance.now() - t0),
      wrap: Math.round(wrap.getBoundingClientRect().width),
      wrapLeft: Math.round(wrap.getBoundingClientRect().left),
      plusLeft: plus ? +plus.getBoundingClientRect().left.toFixed(1) : null,
      titleLeft: title ? Math.round(title.getBoundingClientRect().left) : null,
      ghostW: ghostW(),
      survivors: document.querySelectorAll('#chrome [data-trace]').length,
      crumbs: document.querySelectorAll('#meta .crumb').length,
    });
    if (performance.now() - t0 < ms) requestAnimationFrame(step);
    else res({ tagged, frames });
  })();
  const link = document.querySelector('a[href^="' + href + '"]');
  if (!link) { res({ tagged, frames, nolink: true }); return; }
  link.click();
}))(${JSON.stringify(href)}, 1500)`;

const runs = {};
for (const reduced of [false, true]) {
  const ctx = await (await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] }))
    .newContext({ viewport: { width: 1000, height: 900 },
                  reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(900);
  // onto the review view (column widens)
  const onto = await p.evaluate(TRACE('/review?p='));
  await sleep(400);
  if (!reduced) await p.screenshot({ path: `${OUT}/review-settled.png` });
  // ...and back off it (column narrows)
  const off = await p.evaluate(TRACE('/questions'));
  await sleep(400);
  runs[reduced ? 'reduced' : 'normal'] = { onto, off, errs };
  await ctx.browser().close();
}

// #108 at rest, on every route, in a window narrow enough to kill the gutter
const nb = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
// ask the target what artifact it has rather than naming one: the guard runs
// against a fixture, and hardcoding a filename ties it back to live content
const REVIEW = encodeURIComponent(
  (await (await fetch(`${BASE}/data.json`)).json()).reviews[0].name);
const edges = [];
for (const w of [1500, 1000, 720, 520]) {
  const p = await nb.newPage({ viewport: { width: w, height: 800 } });
  for (const [route, url] of [['dashboard', '/'], ['questions', '/questions'],
                              ['file', '/file?p=DREAMWORK.md'],
                              ['review', '/review?p=' + REVIEW]]) {
    await p.goto(BASE + url, { waitUntil: 'networkidle' }); await sleep(500);
    const r = await p.evaluate(() => {
      const b = document.getElementById('cmdplus').getBoundingClientRect();
      // #123: the opener and the heading text sit on ONE centreline. The
      // opener is the tallest item in the row, so it defines the line — under
      // baseline alignment the title hung near the top of that line and the
      // button sat 3.1px lower through the middle, on every route.
      const t = document.querySelector('#chrome .htitle').getBoundingClientRect();
      return { left: +b.left.toFixed(1), right: +b.right.toFixed(1),
               w: +b.width.toFixed(1),
               dc: +((b.top + b.bottom) / 2 - (t.top + t.bottom) / 2).toFixed(2) };
    });
    edges.push({ vw: w, route, ...r });
    if (w === 1000 && route === 'review')
      await p.screenshot({ path: `${OUT}/review-1000.png` });
    if (w === 720 && route === 'review')
      await p.screenshot({ path: `${OUT}/review-720.png` });
  }
  await p.close();
}
await nb.close();

const uniq = a => [...new Set(a)];
const n = runs.normal, r = runs.reduced;
const moving = f => f.filter(x => x.ghostW !== null);
const checks = []; const ok = (nm, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${nm}`);

ok('no page errors', n.errs.length === 0 && r.errs.length === 0);
ok('both navigations actually fired',
   [n.onto, n.off, r.onto, r.off].every(t => t && !t.nolink));
for (const [dir, tr] of [['onto', n.onto], ['off', n.off]]) {
  const f = tr.frames;
  ok(`${dir}: the heading SURVIVES (same nodes, none rebuilt)`,
     tr.tagged > 0 && f[f.length - 1].survivors >= 2);
  ok(`${dir}: the column TRAVELS (many intermediate widths)`,
     uniq(f.map(x => x.wrap)).length >= 8);
  ok(`${dir}: the departing ghost never re-wraps (one width throughout)`,
     uniq(moving(f).map(x => x.ghostW)).length === 1);
  ok(`${dir}: the + is never clipped, on any frame`,
     f.every(x => x.plusLeft !== null && x.plusLeft >= 4));
  ok(`${dir}: the + travels with the column, it does not jump`,
     uniq(f.map(x => Math.round(x.plusLeft))).length >= 4);
}
for (const [dir, tr] of [['onto', r.onto], ['off', r.off]]) {
  ok(`reduced-motion ${dir}: instant (at most 2 column widths)`,
     uniq(tr.frames.map(x => x.wrap)).length <= 2);
  ok(`reduced-motion ${dir}: no ghost at all`,
     tr.frames.every(x => x.ghostW === null));
}
ok('the + is fully visible with a gap, every route x every width',
   edges.every(e => e.left >= 4 && e.w > 10));
// #123. Half a pixel of tolerance, not zero: the two boxes are centred by the
// same flex rule, so any real drift is a whole pixel or more. The remaining
// ~1px between the button and the text's INK centre is the font's own
// ascender/descender asymmetry and is deliberately not chased — a magic nudge
// would be wrong the moment the mono stack falls back.
ok('the + shares the heading text\'s centreline, every route x every width',
   edges.every(e => Math.abs(e.dc) <= 0.5));

console.log('onto : ' + JSON.stringify(n.onto.frames.filter((_, i) => i % 8 === 0)));
console.log('off  : ' + JSON.stringify(n.off.frames.filter((_, i) => i % 8 === 0)));
console.log('reduced onto widths: ' + JSON.stringify(uniq(r.onto.frames.map(x => x.wrap))));
console.log('min + left, onto/off: ' +
  Math.min(...n.onto.frames.map(x => x.plusLeft)) + ' / ' +
  Math.min(...n.off.frames.map(x => x.plusLeft)));
console.log('opener at rest: ' + JSON.stringify(edges));
if (n.errs.length || r.errs.length) console.log('errors: ' + n.errs.concat(r.errs).join(' | '));
console.log('----'); console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
