/* qsec — #196: the dashboard's questions fold ARRIVES and DEPARTS.

   His report: clicking "questions · 8 to answer" makes the questions "just
   appear and disappear". It did: the section was the one disclosure on the
   page routed through nothing — a bare `<details>` toggling natively, with
   1250px of content blinking in and every panel below it teleporting.

   THIS GUARD IS ABOUT THE MIDDLE OF THE GESTURE, NOT ITS ENDS. Three
   consecutive batches on 2026-07-25 shipped a motion bug past a green check
   because every existing assertion was on the end state, and a snap ends in
   exactly the right place. So:

     - the trace is BOUNDED to the interaction (1500ms — `CARD_MS` is 850, the
       inline height clears at 1000, and the live tick is 2000). A guard that
       watches long enough sees some later tick supply the movement it was
       asserting, which is how #191 stayed green over a real teleport.
     - the assertion is the COUNT OF DISTINCT POSITIONS the panel below
       visits. A teleport visits two; a travel visits dozens. "It moved" and
       "it ended in the right place" are both true of the bug.
     - the click is a REAL pointer click on the REAL route (the dashboard,
       which is the only place this section exists), because a synthetic
       `element.click()` sails through `pointer-events:none` and would pass on
       a summary the human cannot press — #141's lesson.
     - it also asserts the panel below has ARRIVED when the travel ends. The
       height travel is set from `getBoundingClientRect()`, which is a BORDER
       box, while `height` is a content box unless something says otherwise —
       and `details[open]` carries `.5rem` of #169's air. Getting that wrong
       overshoots by the padding and snaps back when the inline height is
       cleared, which no end-state check can see.
     - and it checks the GHOST HOLDS NO ADDRESS. The departure clones the
       whole open section, so unlike a card ghost this corpse arrives carrying
       `data-keep="qsec"` and every `.qa[data-qid]` inside it. `snapshotFolds`
       walks `details[data-keep]` and takes the LAST match, so a ghost left
       holding the attribute would report the section as still open and the
       next tick would re-open it under him.

   Shown red three ways, one per thing it claims to check:

     - THE BUG ITSELF, before the fix: 2 distinct positions each way, no
       ghost, and not one frame with the reveal part-way faded in.
     - `box-sizing` deleted from `travelCard`: "16.0px to go at the end of the
       travel, 16.0px overshot" — `details[open]`'s 2 x .5rem, exactly.
     - the subtree strip in `dreamAway` reverted to the node-only form it had
       before #196: the ghost comes back holding `data-keep:"qsec"` and 3
       cards, and the driven tick re-opens the section he just shut.

   usage: node qsec.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
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

/* One frame-by-frame trace of the whole gesture, bounded to `ms`.

   The panel below is measured in DOCUMENT space (`top + scrollY`), not
   viewport space: a click that scrolls the page would otherwise register as
   movement the section did not cause, and as stillness where it did.

   The ghost is sampled per frame rather than looked for afterwards — it lives
   for ~1s and then removes itself, so an after-the-fact query finds nothing
   and reports a departure that did happen as one that did not. */
const TRACE = ms => `new Promise(res => {
  const seen = []; let ghost = null;
  const t0 = performance.now();
  (function step() {
    const t = performance.now() - t0;
    // Re-acquire the section, its sibling and its body EVERY frame. The live
    // tick re-renders the dashboard through snapshotFolds/restoreFolds, which
    // REPLACES the .qsec node mid-gesture; a reference cached here at trace
    // start detaches, and a detached element's getBoundingClientRect() is all
    // zeros — so the trace reads a section that collapsed to 0 height and a
    // panel that teleported (the deterministic 17->0, 0-part-way failure).
    // The page is right: the replacement node is at the section's real height.
    // The 1500ms bound was meant to sit inside the 2000ms tick, but the bound
    // is timed from the trace arm and the tick from page load, so the two
    // clocks drift and the bound does not in fact dodge the tick. Re-querying
    // per frame survives a tick mid-trace instead of measuring it as a snap —
    // the same do-not-cache-across-a-re-render lesson as oneinput's indicator.
    // (#475.)
    const sec = document.querySelector('.qsec');
    const below = sec && sec.nextElementSibling;
    const body = sec && [...sec.children].find(c => c.tagName !== 'SUMMARY');
    const g = document.querySelector('.qaghost');
    if (g && !ghost) ghost = {
      keep: g.getAttribute('data-keep'),
      qid: g.getAttribute('data-qid'),
      inner: g.querySelectorAll('[data-qid],[data-qkey],[data-sha],[data-keep]').length,
      h: g.getBoundingClientRect().height,
    };
    seen.push({ t,
      below: below ? below.getBoundingClientRect().top + window.scrollY : null,
      h: sec ? sec.getBoundingClientRect().height : null,
      op: body ? +getComputedStyle(body).opacity : 1,
      ghosts: document.querySelectorAll('.qaghost').length });
    if (t < ${ms}) requestAnimationFrame(step); else res({ seen, ghost });
  })();
})`;

/* One click, traced. The trace is armed 60ms before the click so frame 0 is
   the pre-gesture state, and it closes 1400ms later — inside the gesture,
   which is the whole point. */
async function gesture(p, ms = 1500) {
  const t = p.evaluate(TRACE(ms));
  await sleep(60);
  await p.click('.qsec > summary');
  return await t;
}

const distinct = xs => new Set(xs.map(v => Math.round(v))).size;
/* Frames strictly BETWEEN the two ends, 3% deadband — the frame-rate-free
   form of "it travelled". A snap has none of these at any frame rate, so the
   floor is ONE and the assertion is not a bet on how many frames this box
   drew. Same helper `reviewsplit.mjs`/`headertravel.mjs`/`regroup.mjs`/
   `morph.mjs` use; deliberately not a second idiom (#311, transitions.md
   "Checking a transition"). `distinct()` (above) rounds to whole px and is
   retained only for the diagnostic notes and the fade `mid` count, which is
   already the part-way idiom and which this commit does not touch. */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const span = vals => Math.abs(vals.at(-1) - vals[0]);
const at = (seen, ms) => seen.reduce((a, b) =>
  Math.abs(b.t - ms) < Math.abs(a.t - ms) ? b : a);

/* The travel, described in the two ways a snap-at-the-end shows up.

   `late` is anchored to the frame the panel FIRST MOVES, not to the frame the
   trace armed. Driving a real pointer click costs an unknown ~100-200ms, and
   at 1246px of travel a fixed offset measures a perfectly clean ease as 32px
   short — the guard would be reporting its own latency.

   `over` is the timing-free half and the one that actually catches #196's
   trap: an inline height set in the wrong box model plays the travel PAST the
   place the panel ends at, holds there, and snaps back when the height is
   cleared. Any frame beyond the final position, in the direction of travel, is
   that and nothing else. */
function travel(seen) {
  const tops = seen.map(s => s.below);
  const from = tops[0], final = tops.at(-1);
  const i0 = tops.findIndex(v => Math.abs(v - from) > 1);
  const t0 = i0 < 0 ? 0 : seen[i0].t;
  const dir = Math.sign(final - from);
  return { tops, moved: Math.abs(final - from),
           positions: distinct(tops),
           late: Math.abs(at(seen, t0 + 950).below - final),
           over: Math.max(0, ...tops.map(v => dir * (v - final))) };
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* ── the section arrives ──────────────────────────────────────────────── */
const p = await br.newPage({ viewport: { width: 1100, height: 1600 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);

const shut = await p.evaluate(`(() => {
  const d = document.querySelector('.qsec');
  return d ? { open: d.open, cards: d.querySelectorAll('.qa[data-qid]').length,
               below: !!d.nextElementSibling } : null; })()`);
ok('the dashboard has a questions fold, with cards in it and a panel below ' +
   '(else every check here is vacuous)',
   !!shut && shut.open === false && shut.cards >= 2 && shut.below);

{
  const { seen, ghost } = await gesture(p);
  const t = travel(seen);
  // an opacity strictly between the ends is the reveal actually fading; a
  // section that blinks in reports 1 on every frame
  const mid = seen.filter(s => s.op > 0.02 && s.op < 0.98).length;
  notes.push(`open: the panel below travelled ${t.moved.toFixed(0)}px over ` +
             `${t.positions} distinct positions; section height ` +
             `${seen[0].h.toFixed(0)} -> ${seen.at(-1).h.toFixed(0)} over ` +
             `${distinct(seen.map(s => s.h))} positions; ` +
             `${mid} frames with the body part-way faded in; ` +
             `${t.late.toFixed(1)}px to go at the end of the travel, ` +
             `${t.over.toFixed(1)}px overshot`);
  ok('opening: the panel below is displaced at all (else vacuous)', t.moved >= 200);
  // THE ASSERTION. `t.positions >= 8` (distinct rounded tops) was a claim about
  // how many frames THIS BOX drew across the .85s fold, not about the motion;
  // base `f72f730` failed it in 3 of 5 runs unaided. The frame-rate-free form
  // is the frames strictly part-way; a snap has none at any frame rate. (#311.)
  ok('opening: ...and it travels there, rather than teleporting '
   + `(${between(t.tops, t.tops[0], t.tops.at(-1))} of ${t.tops.length} part-way)`,
     between(t.tops, t.tops[0], t.tops.at(-1)) >= 1);
  // the section's own height is the same gesture in a different measure; the
  // vacuity it rested on implicitly is stated next, derived from the trace
  const ohs = seen.map(s => s.h);
  ok('opening: the section really grows (else its height check is vacuous) '
   + `(${ohs[0].toFixed(0)} -> ${ohs.at(-1).toFixed(0)}, ${span(ohs).toFixed(0)}px)`,
     span(ohs) >= 200);
  ok('opening: the section itself grows continuously rather than in one step '
   + `(${between(ohs, ohs[0], ohs.at(-1))} of ${ohs.length} part-way)`,
     between(ohs, ohs[0], ohs.at(-1)) >= 1);
  ok('opening: the revealed body eases in rather than blinking on', mid >= 3);
  // 4px each: a clean ease lands within ~1.5px of final (sub-pixel rounding),
  // and the failure both describe is `details[open]`'s 2 x .5rem of air — 16px.
  // There is no threshold in between to tune.
  ok('opening: ...and it has arrived when the travel ends, not after a snap',
     t.late <= 4);
  ok('opening: ...having never gone past where it ends up', t.over <= 4);
  ok('opening: nothing is ghosted on the way IN', !ghost);
}

/* ── ...and it departs ────────────────────────────────────────────────── */
{
  const { seen, ghost } = await gesture(p);
  const t = travel(seen);
  notes.push(`close: the panel below travelled ${t.moved.toFixed(0)}px over ` +
             `${t.positions} distinct positions; ` +
             `${t.late.toFixed(1)}px to go at the end of the travel, ` +
             `${t.over.toFixed(1)}px overshot; ` +
             `ghost ${ghost ? JSON.stringify(ghost) : 'none'}`);
  ok('closing: the panel below is displaced at all (else vacuous)', t.moved >= 200);
  ok('closing: ...and it travels there, rather than teleporting '
   + `(${between(t.tops, t.tops[0], t.tops.at(-1))} of ${t.tops.length} part-way)`,
     between(t.tops, t.tops[0], t.tops.at(-1)) >= 1);
  ok('closing: ...and it has arrived when the travel ends, not after a snap',
     t.late <= 4);
  ok('closing: ...having never gone past where it ends up', t.over <= 4);
  // the body LEAVES, and a departure on this page fades rather than vanishing
  ok('closing: the leaving body dreams away rather than being cut off',
     !!ghost && ghost.h > 100);
  /* A ghost is a corpse and holds no address — and this corpse is a whole
     SECTION, so the rule reaches its descendants too. Left holding
     `data-keep`, it is the last `details[data-keep]` in the document and
     `snapshotFolds` would read the section as open a frame after he shut it. */
  ok('closing: ...and the ghost carries no identity, its own or its cards\'',
     !!ghost && ghost.keep === null && ghost.qid === null && ghost.inner === 0);
  ok('closing: the section really is shut afterwards',
     await p.evaluate(`document.querySelector('.qsec').open === false`));
}

/* ── the address rule, as the damage it prevents ─────────────────────────
   The attribute check above is the mechanism; this is what it costs. A tick
   landing WHILE THE GHOST IS ON SCREEN reads the folds, and a corpse still
   holding `data-keep="qsec"` is the last `details[data-keep]` in the document
   — so `snapshotFolds` records the section as open and `restoreFolds` opens it
   again, a second after he shut it.

   The window is the ghost's ~1s life, which no ordinary wait can be aimed at:
   the tick polls on its own 2s phase, so simply sleeping catches this half the
   time, and a guard that is right half the time trains you to rerun it. So the
   tick is DRIVEN — the real `tick()`, over a real mtime change (`/command`
   appends to watch-events.log, which is watched and changes nothing rendered)
   — and the check reports whether the ghost was actually there, because the
   whole thing is vacuous if it was not. */
{
  await p.click('.qsec > summary');            // open
  await sleep(1400);
  await p.click('.qsec > summary');            // ...and shut, ghost now alive
  const r = await p.evaluate(`(async () => {
    const before = document.querySelectorAll('.qaghost').length;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'qsec guard tick' }) });
    await tick();
    return { before, after: document.querySelectorAll('.qaghost').length,
             open: document.querySelector('.qsec').open }; })()`);
  notes.push(`tick over the ghost: ${r.before} ghost(s) at the close, ` +
             `${r.after} when the re-render landed; section open=${r.open}`);
  ok('closing: the ghost really was on screen when the tick landed ' +
     '(else the check below is vacuous)', r.before >= 1 && r.after >= 1);
  ok('closing: ...and the section he shut stays shut across it', r.open === false);
}

await p.screenshot({ path: `${OUT}/qsec.png`, fullPage: false });

/* ── reduced motion: timing changes, function does not ────────────────── */
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1600 },
                                    reducedMotion: 'reduce' });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const open = await gesture(rp, 900);
  const otops = open.seen.map(s => s.below);
  const close = await gesture(rp, 900);
  const ctops = close.seen.map(s => s.below);
  notes.push(`reduced: open ${distinct(otops)} positions, ` +
             `close ${distinct(ctops)} positions, ` +
             `ghosts ${open.ghost || close.ghost ? 'yes' : 'none'}`);
  ok('reduced motion: the section still opens and shuts (function is intact)',
     Math.abs(otops.at(-1) - otops[0]) >= 200 &&
     Math.abs(ctops.at(-1) - ctops[0]) >= 200 &&
     await rp.evaluate(`document.querySelector('.qsec').open === false`));
  /* `distinct(...) <= 2` was the hollow direction: satisfied by a box that
     sampled a REAL ramp only twice, so under load it would pass a reduced-
     motion build that animated. The frame-rate-free form is the same measure
     as the travel check with the opposite expectation — instant means NO
     frame part-way, however few were drawn. The vacuity is the function-
     intact check above (each way still displaces >= 200px). (#311.) */
  ok('reduced motion: ...instantly — no frame part-way either way '
   + `(open ${between(otops, otops[0], otops.at(-1))} of ${otops.length}, `
   + `close ${between(ctops, ctops[0], ctops.at(-1))} of ${ctops.length})`,
     between(otops, otops[0], otops.at(-1)) === 0 &&
     between(ctops, ctops[0], ctops.at(-1)) === 0);
  ok('reduced motion: and nothing is ghosted', !open.ghost && !close.ghost);
  await rp.screenshot({ path: `${OUT}/qsec-reduced.png`, fullPage: false });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
