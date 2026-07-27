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
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions navigated onto and off /review in two contexts (normal + ' +
          'reduced-motion), tracing the heading survivors, column width, + opener ' +
          'and ghost per rAF; plus the + opener at rest across 4 widths x 4 routes',
  traceWindow: 'two 1500ms rAF traces per navigation direction per context, plus ' +
               'static reads after ~0.5s settle per width x route; motion sampled per frame',
});

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
/* Frames strictly BETWEEN the two ends, with a 3% deadband so a frame that is
   really an end does not read as travel. Same helper `reviewsplit.mjs` uses
   and the same shape as `qsec.mjs`'s fade count — deliberately not a second
   idiom (#311, transitions.md).

   It replaces `uniq(widths).length >= 8`, which reads like the same rule and
   is not: that threshold asserts THIS MACHINE drew eight frames inside a .85s
   transition, which is a fact about the box. It reddened this guard on a
   healthy commit twice on 2026-07-27 — once under a concurrent guard suite,
   once under the machine's own load — and base `f72f730` failed it in 3 of 5
   runs unaided. A snap has NO part-way frames at any frame rate, so that is
   the property worth asserting, and a slow box cannot manufacture one.

   The floor is ONE, deliberately rather than lazily. Measured on this trace:
   idle, 31 frames with 5 part-way; under six added CPU burners, 14 frames with
   2 part-way — so any floor above 1 is still a bet on the frame rate, only a
   smaller one, and 2 was already sitting exactly on the line. One is the only
   threshold the machine cannot move, because zero-versus-some IS the
   distinction between a snap and a travel. Whether a travel is too FAST is a
   different question with its own rules in transitions.md (no frame past the
   final position, and the pacing checks); this assertion is not the place to
   smuggle it in. */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const span = vals => Math.abs(vals.at(-1) - vals[0]);
const n = runs.normal, r = runs.reduced;
const moving = f => f.filter(x => x.ghostW !== null);

ok('no page errors', n.errs.length === 0 && r.errs.length === 0);
ok('both navigations actually fired',
   [n.onto, n.off, r.onto, r.off].every(t => t && !t.nolink));
for (const [dir, tr] of [['onto', n.onto], ['off', n.off]]) {
  const f = tr.frames;
  ok(`${dir}: the heading SURVIVES (same nodes, none rebuilt)`,
     tr.tagged > 0 && f[f.length - 1].survivors >= 2);
  const ws = f.map(x => x.wrap);
  const pls = f.map(x => x.plusLeft).filter(v => v !== null);
  /* The precondition `between` rests on, and which the old count assertion
     carried only implicitly: with no range there are no part-way values to
     find, so a column that never moved would read as "no travel to check"
     rather than failing. Derived at runtime, never a literal — the review
     column's width is a styleguide value and this must not need editing when
     it changes. */
  ok(`${dir}: the column really changes width (else the travel checks are vacuous) `
   + `(${ws[0]} -> ${ws.at(-1)}, ${span(ws).toFixed(0)}px)`,
     span(ws) >= 40);
  ok(`${dir}: the column TRAVELS (frames strictly part-way, at any frame rate) `
   + `(${between(ws, ws[0], ws.at(-1))} of ${ws.length} part-way)`,
     between(ws, ws[0], ws.at(-1)) >= 1);
  ok(`${dir}: the departing ghost never re-wraps (one width throughout)`,
     uniq(moving(f).map(x => x.ghostW)).length === 1);
  ok(`${dir}: the + is never clipped, on any frame`,
     f.every(x => x.plusLeft !== null && x.plusLeft >= 4));
  /* Not rounded, unlike the version this replaces: rounding a per-frame trace
     to whole pixels reports a clean sub-pixel ease as a snap, and the gutter's
     travel is the SMALL gesture here — exactly the one the rounding trap bites
     (transitions.md, #308). The deadband does the job rounding was doing. */
  ok(`${dir}: the + moves at all (else its travel check is vacuous) `
   + `(${span(pls).toFixed(1)}px)`,
     span(pls) >= 8);
  ok(`${dir}: the + travels with the column, it does not jump `
   + `(${between(pls, pls[0], pls.at(-1))} of ${pls.length} part-way)`,
     between(pls, pls[0], pls.at(-1)) >= 1);
}
for (const [dir, tr] of [['onto', r.onto], ['off', r.off]]) {
  /* The same trap inverted, and the more dangerous direction. `uniq(...) <= 2`
     is satisfied by a box that sampled a REAL ramp only twice, so under load
     this went hollow rather than red — it would have passed a reduced-motion
     build that animated. Part-way frames are the frame-rate-free form here
     too: instant means NONE of them, however few frames were drawn. The pair
     with the travel check above is exact — same measure, opposite expectation.
     (#311.) */
  const rws = tr.frames.map(x => x.wrap);
  ok(`reduced-motion ${dir}: the column still ends somewhere else (else vacuous) `
   + `(${rws[0]} -> ${rws.at(-1)})`,
     span(rws) >= 40);
  ok(`reduced-motion ${dir}: instant — it LANDS, with no frame part-way `
   + `(${between(rws, rws[0], rws.at(-1))} part-way of ${rws.length})`,
     between(rws, rws[0], rws.at(-1)) === 0);
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

notes.push('onto : ' + JSON.stringify(n.onto.frames.filter((_, i) => i % 8 === 0)));
notes.push('off  : ' + JSON.stringify(n.off.frames.filter((_, i) => i % 8 === 0)));
notes.push('reduced onto widths: ' + JSON.stringify(uniq(r.onto.frames.map(x => x.wrap))));
notes.push('min + left, onto/off: ' +
  Math.min(...n.onto.frames.map(x => x.plusLeft)) + ' / ' +
  Math.min(...n.off.frames.map(x => x.plusLeft)));
notes.push('opener at rest: ' + JSON.stringify(edges));
if (n.errs.length || r.errs.length)
  notes.push('errors: ' + n.errs.concat(r.errs).join(' | '));
finish();
