/* #104 + #77 — answering a question regroups the list, gracefully.

   One moment, two views of it: the questions below close the gap the
   answered one left (#104), and the answered one travels to its new heading
   instead of being re-set there (#77). Both must be TRACED, not
   screenshotted — a card that ends in the right place proves nothing about
   whether it got there or jumped.

   What this asserts, per frame, across a real POST /answer and the live tick
   that follows it:
     - the moved card visits many intermediate positions (it travelled)
     - a neighbour below it also moves, and also travels (the gap closed)
     - the card is the SAME element before and after (keyed by data-qid, not
       by its positional key, which answering changes)
     - the DOM lands the new grouping immediately — liveness is never held
       waiting on the animation
     - reduced motion does all of it instantly
   Writes to the target it is pointed at, so point it at a scratch copy.
   usage: node regroup.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions in two contexts (normal + reduced-motion), answering the ' +
          'first open question through the real UI (answer mode + qsend) and ' +
          'tracing every card across the tick that regroups them',
  traceWindow: 'a 5200ms rAF trace per context spanning the 2s tick poll; the card ' +
               'must change state and the trace must outlast the regroup',
});

/* Answer the FIRST open question, then trace every card's position per frame
   until well past the tick that regroups them. The tick polls /mtime every
   2s, so the window has to outlast that. */
const TRACE = `((ms) => new Promise(res => {
  const cards = () => [...document.querySelectorAll('.qa[data-qid]')];
  const first = cards().find(c => c.classList.contains('open'));
  if (!first) { res({ nofixture: true }); return; }
  const target = first.dataset.qid;
  const below = cards().filter(c => c.getBoundingClientRect().top >
                                    first.getBoundingClientRect().top)[0];
  const neighbour = below ? below.dataset.qid : null;
  first.dataset.trace = 'target';        // survives only if the node survives
  const frames = [];
  const t0 = performance.now();
  (function step() {
    const byId = {};
    for (const c of cards()) {
      const r = c.getBoundingClientRect();
      byId[c.dataset.qid] = { top: Math.round(r.top),
                              cls: c.className.replace(/ ?dreamin/, '') };
    }
    frames.push({ t: Math.round(performance.now() - t0),
      target: byId[target] || null,
      neighbour: neighbour ? (byId[neighbour] || null) : null,
      sameNode: !!document.querySelector('.qa[data-trace=target]'),
      // FLIP's signature: an inline transform on a card. reduced motion
      // must never produce one.
      flipping: [...cards()].filter(c => c.style.transform).length,
      // a card crossing headings must travel by POSITION and HEIGHT, never
      // by scale: since #111 a card can be fifteen times taller before the
      // move than after, and a scale morph would squash the text by that
      // ratio at frame 0 instead of folding it
      // NB the double backslash: this whole block is a template literal, so
      // a single one is eaten before the page ever sees the regex
      scaled: [...cards()].filter(c => /scale\\(/.test(c.style.transform)).length,
      ghosts: document.querySelectorAll('.qaghost').length });
    if (performance.now() - t0 < ms) requestAnimationFrame(step);
    else res({ target, neighbour, frames });
  })();
  // fill and submit through the real UI, in answer mode
  first.querySelector('.qmode[data-mode=answer]').click();
  first.querySelector('textarea').value = 'traced answer for the regroup';
  first.querySelector('.qsend').click();
}))(5200)`;

const uniq = a => [...new Set(a)];
/* Frames strictly BETWEEN the two ends, 3% deadband — the frame-rate-free
   form of "it travelled". A snap has none of these at any frame rate, so the
   floor is ONE and the assertion is not a bet on how many frames this box
   drew (idle ~31 frames / 5 part-way; six CPU burners ~14 / 2 — any floor
   above 1 sits on the frame rate). Same helper `reviewsplit.mjs` /
   `headertravel.mjs` use; deliberately not a second idiom (#311,
   transitions.md "Checking a transition"). */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const span = vals => Math.abs(vals.at(-1) - vals[0]);
const runs = {};

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 950 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1000);
  const openCount = await p.evaluate(() => document.querySelectorAll('.qa.open').length);
  if (!openCount) {
    ok('fixture has an open question to answer (else the travel checks are vacuous)',
       false);
    notes.push('fixture has no open question — reset the scratch target from the ' +
               'live questions.md and re-run');
    await br.close(); finish(); process.exit(1);
  }
  const r = await p.evaluate(TRACE);
  if (!reduced) await p.screenshot({ path: `${OUT}/after-regroup.png`, fullPage: true });
  runs[reduced ? 'reduced' : 'normal'] = { ...r, errs };
  await br.close();
}

const n = runs.normal, r = runs.reduced;
const tops = f => f.filter(x => x.target).map(x => x.target.top);
const nTops = f => f.filter(x => x.neighbour).map(x => x.neighbour.top);
// the frame the card's class changed is the frame the new grouping landed
const landedAt = f => f.findIndex(x => x.target && /awaiting/.test(x.target.cls));
const settledAt = f => {
  const last = tops(f).at(-1);
  return f.findIndex(x => x.target && x.target.top === last);
};

ok('no page errors', n.errs.length === 0 && r.errs.length === 0);
ok('the fixture regrouped at all (the card changed state)', landedAt(n.frames) > 0);
/* `uniq(tops).length >= 6` was a claim about how many frames THIS BOX drew
   inside the .85s FLIP, not about the motion — it reddened on a healthy
   commit twice on 2026-07-27 and passed when re-run with fewer guards in
   flight. The vacuity precondition the count carried only implicitly is
   stated next, derived from the trace: with no range there is nothing for
   `between` to find, so a card that never moved would read as "no travel to
   check" rather than failing. (#311.) */
const tps = tops(n.frames);
ok('#77 the answered card really moves (else the travel check is vacuous) '
 + `(${tps[0]} -> ${tps.at(-1)}, ${span(tps).toFixed(0)}px)`,
   span(tps) >= 30);
ok('#77 the answered card TRAVELS (frames strictly part-way, at any frame rate) '
 + `(${between(tps, tps[0], tps.at(-1))} of ${tps.length} part-way)`,
   between(tps, tps[0], tps.at(-1)) >= 1);
// The view re-renders through innerHTML, so the NODE is replaced; identity
// is carried by data-qid and the FLIP animates the new node from the old
// node's rect. That is what must hold: the question is continuously present
// and its motion is continuous. (Preserving the nodes themselves would need
// a keyed reconciler for the list — see the dream.)
ok('#77 the question is continuously present under one identity',
   n.frames.every(x => x.target));
ok('#77 the travel is a FLIP, not a re-layout',
   n.frames.some(x => x.flipping > 0));
// #113: a card crossing headings travels by position and HEIGHT. Since #111
// it can be fifteen times taller before the move than after (answering, then
// folding), and flipDock's scale morph would squash the text by that ratio
// at frame 0 instead of folding it.
ok('#113 the crossing card never morphs by scale',
   n.frames.every(x => x.scaled === 0));
/* Same conversion as the card above: `uniq(nTops).length > 1` / `>= 4` were
   frame counts. The neighbour's path is non-monotonic (it is pushed DOWN by
   the answered card's height change, then pulled UP into the gap the regroup
   opens) so `between(first, last)` reads only the part-way frames inside the
   net displacement — which is still many for a real slide and zero for a
   teleport, which is the distinction. */
const nps = nTops(n.frames);
ok('#104 a question below it also moves (else its travel check is vacuous) '
 + `(${nps[0]} -> ${nps.at(-1)}, ${span(nps).toFixed(0)}px)`,
   n.neighbour && span(nps) >= 8);
ok('#104 that neighbour SLIDES rather than jumping '
 + `(${between(nps, nps[0], nps.at(-1))} of ${nps.length} part-way)`,
   n.neighbour && between(nps, nps[0], nps.at(-1)) >= 1);
ok('liveness is not held: the DOM regroups before the motion settles',
   landedAt(n.frames) >= 0 && landedAt(n.frames) < settledAt(n.frames));
// reduced motion changes timing, never function: the same regrouping
// happens, in discrete steps, with no FLIP transform ever applied
ok('reduced motion: no card is ever FLIPped',
   r.frames.every(x => x.flipping === 0));
/* The same trap inverted, and the hollow direction: the old ratio
   `uniq(r).length * 4 <= uniq(n).length` tied the reduced contract to the
   normal frame count, so under load the NORMAL side dropped and the check
   tightened over a reduced build that was perfectly instant. The
   frame-rate-free form is the same measure as the travel check with the
   opposite expectation — instant means NO frame part-way, however few were
   drawn. The neighbour's reduced path steps through a layout excursion that
   lies OUTSIDE its [first, last] window (a height-change shove before the
   regroup pulls it back), so `between(first, last) === 0` still holds and
   a smooth ramp between the ends would not. (#311.) */
{
  const rTps = tops(r.frames);
  ok('reduced motion: the card still ends somewhere else (else vacuous) '
   + `(${rTps[0]} -> ${rTps.at(-1)})`,
     span(rTps) >= 30);
  ok('reduced motion: ...the card LANDS instantly, no frame part-way '
   + `(${between(rTps, rTps[0], rTps.at(-1))} part-way of ${rTps.length})`,
     between(rTps, rTps[0], rTps.at(-1)) === 0);
  const rNps = nTops(r.frames);
  ok('reduced motion: the neighbour still ends somewhere else (else vacuous) '
   + `(${rNps[0]} -> ${rNps.at(-1)})`,
     span(rNps) >= 8);
  ok('reduced motion: ...and the neighbour LANDS instantly too, no frame part-way '
   + `(${between(rNps, rNps[0], rNps.at(-1))} part-way of ${rNps.length})`,
     between(rNps, rNps[0], rNps.at(-1)) === 0);
}

notes.push('target positions  : ' + JSON.stringify(uniq(tops(n.frames))));
notes.push('neighbour positions: ' + JSON.stringify(uniq(nTops(n.frames))));
notes.push('regroup landed at frame ' + landedAt(n.frames) +
           ', motion settled at frame ' + settledAt(n.frames));
notes.push('reduced target/neighbour: ' + JSON.stringify(uniq(tops(r.frames))) +
           ' / ' + JSON.stringify(uniq(nTops(r.frames))));
if (n.errs.length || r.errs.length)
  notes.push('errors: ' + n.errs.concat(r.errs).join(' | '));
finish();
