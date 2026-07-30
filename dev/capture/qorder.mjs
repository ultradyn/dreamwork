/* qorder — #197: questions ordered by priority, then oldest, on BOTH surfaces.

   THE ORDER IS A PROPERTY OF THE PARSE, and this guard exists mostly to hold
   that. The dashboard's questions section and `/questions` render the same
   entries through the same `qaCard`; if each sorted for itself there would be
   two chances to disagree about which question is most urgent, on the one
   channel whose whole job is telling him what to look at first. So the
   load-bearing assertion is not "this page is in the right order" — it is
   that BOTH pages are in the SAME order, compared against each other rather
   than against a list written twice in this file.

   WHAT IT ASSERTS THAT A SCREENSHOT WOULD NOT:

     - the order is a permutation of the file's. The fixture's `P1` entry is
       deliberately SECOND in the file, so a renderer that ignores priority
       entirely cannot be accidentally right.
     - `P3` sorts BELOW an unmarked entry. Unmarked means P2 — the middle
       band — and that is the whole reason the default is not P1 or P3. The
       fixture's `P3` entry is FIRST in the file for this: with it already
       last, a build reading `P3` as unmarked renders the identical order and
       this check cannot fail for its own stated reason. It could not, until
       the fixture was rearranged to let it.
     - a live reorder TRAVELS. A question arriving at the top pushes every
       card below it down, and that is a move like any other on this page: it
       goes through the tick's regroup, so the survivors visit many
       intermediate positions rather than two.
     - ...and none of them goes PAST where it ends up — the timing-free form,
       which cannot be defeated by how far the cards happen to move.
     - reduced motion places them without the travel.

   THE FIXTURE IS HALF OF THIS CHECK. Before #197 it held zero prioritised
   entries, so every ordering assertion here would have passed over a sort
   that did nothing — there was no pair whose order priority and file order
   disagree about. Seeding it is part of the feature, not test scaffolding.

   SHOWN RED THREE WAYS:

     - `items.sort` dropped from `parse_open_questions` — the order checks,
       and the motion ones with them, because an unsorted list appends the
       new question at the BOTTOM and nothing below it has to move.
     - the default priority changed from 2 to 3 — the P3-below-unmarked check
       and the ordering it implies. This one did NOT discriminate at first,
       which is why the fixture reads the way it does: see above.
     - a sort added inside `buildQuestions` and taken out of the parse — the
       cross-surface check, and only it. That is the failure this guard is
       mostly for, and it is invisible to every other check here.

   usage: node qorder.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

const target = await (await fetch(`${BASE}/data.json`)).json()
  .then(d => d.target).catch(() => null);
if (!target) { ok('the server answered /data.json (nothing below can run)', false);
               process.exit(1); }
const QFILE = join(target, '.dreamwork', 'questions.md');

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1400 } });
p.on('pageerror', e => errs.push(String(e)));

/* the OPEN cards in DOM order. Awaiting-fold and folded cards are excluded:
   they are a different group with a different heading, and mixing them in
   would make this measure the grouping rather than the sort. */
const openOrder = pg => pg.evaluate(
  `[...document.querySelectorAll('.qa.open .qt')].map(n => n.textContent.trim())`);
const band = t => (t.match(/^P([123])\s+·/) || [null, '2'])[1];

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .qa cards the guard orders first, not a fixed sleep (#428 class)
await waitFor(p, '.qa');

/* the subject, before anything is measured against it — an empty list makes
   every `every` below vacuously true, which is the "run it against nothing"
   house rule aimed at this guard's own assertions */
const qOrder = await openOrder(p);
notes.push(`/questions open: ${JSON.stringify(qOrder.map(t => t.slice(0, 46)))}`);
const HAVE = qOrder.length >= 3;
ok('/questions shows at least three open questions (else every ordering ' +
   `check below is about an empty list; saw ${qOrder.length})`, HAVE);

if (HAVE) {
  const bands = qOrder.map(band);
  notes.push(`bands: ${JSON.stringify(bands)}`);
  ok('open questions are in priority order, most urgent first',
     bands.join('') === [...bands].sort().join(''));
  // THE FIXTURE'S P1 IS SECOND IN THE FILE. Without that, "in priority order"
  // is also satisfied by a build that never sorts at all.
  ok('...and that is a real permutation of the file, not the file order ' +
     'wearing a label', bands[0] === '1');
  // unmarked means P2, the MIDDLE band. If the default were P1 or P3 this is
  // the only check that would notice.
  ok('an explicit P3 sorts BELOW an unmarked entry, because unmarked is P2',
     bands.indexOf('3') === bands.length - 1 && bands.indexOf('2') >= 0);
}

/* ── the same order on the dashboard, compared against the OTHER SURFACE ─── */
let dOrder = [];
if (HAVE) {
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const sec = await p.evaluate(`!!document.querySelector('details.qsec')`);
  ok('the dashboard has a questions section (else the comparison is empty)',
     sec);
  if (sec) {
    await p.click('.qsec > summary');
    await sleep(1200);                 // the fold travels (#196)
    dOrder = await openOrder(p);
    notes.push(`dashboard open: ${JSON.stringify(dOrder.map(t => t.slice(0, 46)))}`);
    /* THE ASSERTION THIS GUARD EXISTS FOR. Compared surface-to-surface, not
       against an expectation written here: an expectation rebuilt inside the
       guard passes when both surfaces are wrong in the same way, and the
       failure being prevented is that they stop being wrong in the same way. */
    ok('the dashboard and /questions agree on the order, because they share ' +
       'the parse rather than each sorting for itself',
       dOrder.length === qOrder.length &&
       dOrder.every((t, i) => t === qOrder[i]));
  }
}

/* ── a live reorder TRAVELS ───────────────────────────────────────────────
   A new P1 sorts to the top and pushes every card below it down. That is a
   move, so it obeys transitions.md — and it rides the tick's existing regroup
   because `data-qid` is the question's own title, which the reorder does not
   change. The window is bounded to the arrival: 900ms from the frame the card
   count changes, so a later tick cannot supply the movement. */
const NEWQ = '- **P1 · 2026-07-25 — an urgent question that arrives after the ' +
  'others.**\n  It is appended at the END of `## Open`, so file order puts it ' +
  'last\n  and priority puts it first — which is the whole reorder, in one ' +
  'entry.\n\n';
function addUrgent() {
  const text = readFileSync(QFILE, 'utf8');
  const at = text.indexOf('## Answered');
  writeFileSync(QFILE, text.slice(0, at) + NEWQ + text.slice(at));
}
/* Frames strictly BETWEEN the two ends, 3% deadband — the frame-rate-free form
   of "it travelled", and the one idiom this repo uses for it (`reviewsplit.mjs`
   first, then `headertravel`, `regroup`, `morph`, `qsec`, `dismiss`). A snap has
   none of these at any frame rate, so the floor is ONE; see transitions.md
   "Checking a transition" for why a bigger count or a fraction is still a bet on
   the frame rate. (#317.) */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
/* Which survivors HAD to move, and how many distinct positions each visited.

   ONE HELPER FOR BOTH THE ANIMATED AND THE REDUCED RUN, because the two
   differ only in the count and a second implementation is a second thing that
   can be wrong. The window opens on the frame BEFORE the arrival: under
   reduced motion the card is at its final position from the first post-change
   frame, so a window starting at the change itself sees one position and
   cannot tell "placed" from "never moved" — that was this guard's own
   vacuous-check bug, found by reading its notes rather than its result. */
function movedIn(seen, grew) {
  const from = Math.max(0, grew - 1), t0 = seen[from].t;
  const win = seen.slice(from).filter(f => f.t - t0 <= 900);
  const out = [];
  for (const id of seen[from].cards.map(c => c.id)) {
    const tops = win.map(f => (f.cards.find(c => c.id === id) || {}).top)
      .filter(v => v != null);
    if (tops.length < 3) continue;
    const last = tops[tops.length - 1];
    if (Math.abs(last - tops[0]) < 4) continue;   // it did not have to move
    out.push({ id: id.slice(0, 24),
               steps: [...new Set(tops.map(v => Math.round(v)))].length,
               partway: between(tops, tops[0], last),
               frames: tops.length,
               from: Math.round(tops[0]), to: Math.round(last),
               // the timing-free form: nothing goes PAST the end
               past: tops.some(v => v > last + 1.5) });
  }
  return out;
}
async function reorderTrace(pg) {
  const trace = pg.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      seen.push({ t: performance.now() - t0,
        cards: [...document.querySelectorAll('.qa.open')].map(n => ({
          id: n.dataset.qid, top: n.getBoundingClientRect().top })) });
      if (performance.now() - t0 < 4500) requestAnimationFrame(step); else res(seen);
    })();
  })`);
  await sleep(100);
  addUrgent();
  return trace;
}

if (HAVE) {
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const seen = await reorderTrace(p);
  const before = seen[0].cards.length;
  const grew = seen.findIndex(f => f.cards.length > before);
  notes.push(`reorder: ${before} cards -> ${
    seen[seen.length - 1].cards.length}, changed at frame ${grew}`);
  ok('the urgent question reached the page (else the motion checks are ' +
     'about nothing)', grew >= 0);
  if (grew >= 0) {
    const moved = movedIn(seen, grew);
    notes.push(`survivors that moved: ${JSON.stringify(moved)}`);
    ok('the cards below the arrival actually had to move (else this measures ' +
       'a page where nothing happened)', moved.length > 0);
    // A TELEPORT VISITS TWO POSITIONS AND PASSES EVERY END-STATE CHECK.
    // `steps >= 6` said that and also said "this box drew six frames in the
    // 900ms window", which is why this guard passed in small runs and failed
    // in the full suite (#311's evidence, #317's fix). The part-way count is
    // the same distinction without the frame-rate claim; the vacuity this
    // needs is already upstream — movedIn drops any card that travelled less
    // than 4px, and `moved.length > 0` above asserts one survived that filter.
    ok('...and each of them TRAVELLED there rather than jumping ' +
       `(${moved.map(m => `${m.partway}/${m.frames}`).join(' ')} part-way)`,
       moved.length > 0 && moved.every(m => m.partway >= 1));
    // not anchored to a clock: "arrived by t=950" works at 20px and fails at
    // 1246px, where it reports the guard's own latency (transitions.md)
    ok('...and none of them went past where it ended up',
       moved.every(m => !m.past));
    const urgent = seen[seen.length - 1].cards[0];
    ok('the urgent question is FIRST once it lands, not merely present',
       !!urgent && /^P1/.test(decodeURIComponent(urgent.id)));
  }
  await p.screenshot({ path: `${OUT}/qorder.png`, fullPage: false });
}

/* ── reduced motion: the order without the travel ─────────────────────────
   Verified on its own server-visible state: the file already carries the
   urgent question from the phase above, so this page reloads into the sorted
   order and then gets a SECOND one, which is the same event again. */
if (HAVE) {
  const rp = await br.newPage({ viewport: { width: 1100, height: 1400 },
                                reducedMotion: 'reduce' });
  rp.on('pageerror', e => errs.push('reduced: ' + String(e)));
  await rp.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const seen = await reorderTrace(rp);
  const before = seen[0].cards.length;
  const grew = seen.findIndex(f => f.cards.length > before);
  ok('reduced motion still gets the question (timing, never function)',
     grew >= 0);
  if (grew >= 0) {
    const moved = movedIn(seen, grew);
    notes.push(`reduced: ${JSON.stringify(moved)}`);
    // THE SAME FILTER as the animated run, so this cannot pass on a page
    // where the cards never moved at all — which is what "one distinct
    // position" also describes.
    ok('...and cards below it still had to move', moved.length > 0);
    // `steps <= 3` was the HOLLOW direction of the same mistake: a box that
    // sampled a real ramp only three times satisfied it, so under load this
    // would have passed a reduced-motion build that animated. Instant means NO
    // frame part-way, however many were drawn — the same measure as the travel
    // check above with the opposite expectation. Measured before choosing zero
    // rather than after: 51 frames, 2 distinct positions, 0 part-way, so no
    // layout intermediate lands inside the window and a strict zero is the
    // contract and not a coincidence. (#317.)
    ok('...and each is PLACED rather than travelling ' +
       `(${moved.map(m => `${m.partway}/${m.frames}`).join(' ')} part-way)`,
       moved.length > 0 && moved.every(m => m.partway === 0));
  }
  await rp.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
