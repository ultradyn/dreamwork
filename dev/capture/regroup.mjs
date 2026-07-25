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
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

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
const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
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
    console.log('FAIL fixture has no open question — reset the scratch ' +
                'target from the live questions.md and re-run');
    process.exit(1);
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
ok('#77 the answered card TRAVELS (many intermediate positions)',
   uniq(tops(n.frames)).length >= 6);
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
ok('#104 a question below it also moves',
   n.neighbour && uniq(nTops(n.frames)).length > 1);
ok('#104 that neighbour SLIDES rather than jumping',
   n.neighbour && uniq(nTops(n.frames)).length >= 4);
ok('liveness is not held: the DOM regroups before the motion settles',
   landedAt(n.frames) >= 0 && landedAt(n.frames) < settledAt(n.frames));
// reduced motion changes timing, never function: the same regrouping
// happens, in discrete steps, with no FLIP transform ever applied
ok('reduced motion: no card is ever FLIPped',
   r.frames.every(x => x.flipping === 0));
ok('reduced motion: positions step rather than ramp',
   uniq(tops(r.frames)).length * 4 <= uniq(tops(n.frames)).length &&
   uniq(nTops(r.frames)).length * 4 <= uniq(nTops(n.frames)).length);

console.log('target positions  : ' + JSON.stringify(uniq(tops(n.frames))));
console.log('neighbour positions: ' + JSON.stringify(uniq(nTops(n.frames))));
console.log('regroup landed at frame ' + landedAt(n.frames) +
            ', motion settled at frame ' + settledAt(n.frames));
console.log('reduced target/neighbour: ' + JSON.stringify(uniq(tops(r.frames))) +
            ' / ' + JSON.stringify(uniq(nTops(r.frames))));
if (n.errs.length || r.errs.length) console.log('errors: ' + n.errs.concat(r.errs).join(' | '));
console.log('----'); console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
