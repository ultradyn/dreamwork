/* #113 part 2 — every transition between the three question states is
   covered, and covered by ONE mechanism.

   The three states are one axis (who is the entry waiting on: the human, the
   loop, nobody), so their transitions are one matrix. Every cell of it funnels
   through regroupCards → travelCard, which is what makes the matrix
   assertable without driving all six cells: the property to check is the
   MECHANISM's, not each cell's.

     - a card that ends somewhere else, or at another size, TRAVELLED there:
       it carried an inline transform, and an inline height if it resized.
       If any cell were missed, some card would change place or size with
       neither.
     - it travels by height, never by SCALE. Since folding collapses the card
       (#111) a card can be fifteen times taller before a move than after, and
       flipDock's scale morph would squash the text by that ratio at frame 0.
     - a body that LEAVES fades rather than blanking (human, 2026-07-25: "when
       it folds in, the body shouldn't disappear all at once"). The new node is
       already the folded one, so the proof is that a ghost exists carrying the
       old body while the box shrinks.
     - a body that ARRIVES eases in rather than being wiped up by the box.
     - reduced motion does all of it in one step, with no transform ever.

   Two cells are driven for real: the human folding and unfolding an entry
   (which is a cell — he is the one who acts), and a live tick that changes a
   card's height under him. The cross-heading cell is regroup.mjs's.
   Writes to the target it is pointed at, so point it at a scratch copy.
   usage: node states.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions in two contexts (normal + reduced-motion), driving three ' +
          'state-matrix cells: unfold a folded entry, fold it back, and a live ' +
          '/comment tick that grows an open card under the cursor',
  traceWindow: 'three rAF traces per context (1600ms for each fold, 5200ms for the ' +
               'tick-grow); every card geometry + FLIP signature sampled per frame',
});

const uniq = a => [...new Set(a)];
/* Frames strictly BETWEEN the two ends, 3% deadband — the frame-rate-free
   form of "it travelled". A snap has none of these at any frame rate, so the
   floor is ONE and the assertion is not a bet on how many frames this box
   drew. Same helper `reviewsplit.mjs`/`headertravel.mjs`/`qsec.mjs`/
   `morph.mjs` use; deliberately not a second idiom (#311, transitions.md
   "Checking a transition").

   It replaces `uniq(h).length >= 6` (three live counts on the unfold / fold /
   tick-grow heights below), which asserted THIS MACHINE drew six distinct
   heights inside the trace window — a fact about the box, not the motion.
   #333; confirmation.mjs #414 for the sample-count precondition that must
   sit first so a starved window and a real snap print different lines. */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const span = vals => Math.abs((vals.at(-1) ?? 0) - (vals[0] ?? 0));
/* Minimum samples for a part-way frame to be decidable: start, at least one
   intermediate draw, end. Named in the precondition so a starved rAF window
   fails with "sampled enough… (N frames)" rather than masquerading as a
   motion bug (#413 / #414). */
const MIN_SAMPLES = 3;
/* Per-motion vacuity floors — one literal per motion, each with its
   measurement recorded beside it. #441: a single shared MIN_HEIGHT_SPAN=20
   covered two motions with ~10x different travel (fold ~193px, tick-grow
   ~23px), and the margin was invisible in the guard output. Splitting is the
   fix; the *shape* is still a deliberate constant per transitions.md ("a
   part-way count needs a vacuity precondition… and that one IS a literal"),
   NOT a fraction of the observed span.

   Why not a fraction of the span it validates: a floor computed as
   `k * span(measured)` can never fail — any observed span satisfies its own
   fraction — so the vacuity check becomes decoration. That is the #444 trap
   ("a check that restates the value it reads") one level down. The span we
   PRINT is derived at runtime; the floor we COMPARE against is a fixed
   literal, and the two come from different sources by construction.

   Span is deterministic on the frozen fixture (a property of its CSS +
   content); only the per-frame SAMPLE COUNT varies with load. So a literal
   pegged below the minimum real signal holds across every load. Measured
   2026-07-29 at load 40-47 on 16 cores, six runs each: fold/unfold 17↔210
   every time; tick-grow 248→271 every time. */

/* Fold + unfold share one constant because they are the SAME motion in
   opposite directions over the SAME content (the folded body), and the
   measurement is identical both ways: 17px ⇄ 210px = 193px, stable across
   six runs. The pre-split value of 20 (~9.6x under 193px) was never the
   defect — the fold's headroom was fine — so it is kept unchanged and merely
   given its own name and its measurement beside it. Literal by design. */
const MIN_FOLD_SPAN = 20;

/* Tick-grow is a different motion (a note lands, the open card grows) with a
   much smaller travel. Measured minimum real grow is ONE NOTE LINE = 20px —
   verified with notes "x", "ok", "a short note" and the fixture's own note,
   all of which grow exactly 20px; a two-line wrapping note grows 36px. So
   the old shared floor of 20 had ZERO headroom on tick-grow, not the "3px"
   the filing estimated from the fixture's single sample: it sat exactly ON
   the minimum real signal. 6px sits ~3.3x under that 20px signal and ~6x
   over the ≤1px rounded-rect noise of a frozen fixture, so a real note
   passes with room and a no-op (note failed to land) still fails. */
const MIN_GROW_SPAN = 6;

/* Trace every card's geometry and its FLIP signatures per frame, while `act`
   happens. `act` runs in the page and may be async. */
const TRACE = (act, ms) => `((act, ms) => new Promise(res => {
  const cards = () => [...document.querySelectorAll('.qa[data-qid]')];
  const frames = [];
  const t0 = performance.now();
  (function step() {
    const at = {};
    for (const c of cards()) {
      const r = c.getBoundingClientRect();
      at[c.dataset.qid] = { top: Math.round(r.top), h: Math.round(r.height),
                            tf: c.style.transform || '',
                            hh: !!c.style.height };
    }
    frames.push({ at,
      ghosts: document.querySelectorAll('.qaghost').length,
      // a ghost that is carrying a departing BODY is clipped; a whole-card
      // departure is not. They are the same idiom, told apart by that.
      clipped: [...document.querySelectorAll('.qaghost')]
                 .filter(g => /inset/.test(g.style.clipPath)).length,
      revealing: document.querySelectorAll('.qreveal').length });
    if (performance.now() - t0 < ms) requestAnimationFrame(step); else res(frames);
  })();
  (async () => { await act(); })();
}))(${act}, ${ms})`;

const series = (frames, qid, k) => frames.map(f => f.at[qid] && f.at[qid][k])
                                        .filter(v => v !== undefined);
const anyFrame = (frames, f) => frames.some(f);

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the .qa cards the guard reads first, not a fixed sleep (#428 class)
  await waitFor(p, '.qa');
  const tag = reduced ? 'reduced-motion' : 'normal';

  const ids = await p.evaluate(() => ({
    folded: (document.querySelector('.qa.folded[data-qid]') || {dataset:{}}).dataset.qid,
    open: (document.querySelector('.qa.open[data-qid]') || {dataset:{}}).dataset.qid,
  }));
  if (!ids.folded || !ids.open) {
    ok(`${tag}: fixture has a folded and an open entry (else the matrix is vacuous)`,
       false);
    notes.push('fixture needs a folded and an open entry');
    await br.close(); finish(); process.exit(1);
  }

  // ── cell: nobody → the human is reading it (he unfolds it) ──────────────
  const openAct = `(async () => {
    document.querySelector('.qa[data-qid="${ids.folded}"] .qfold > summary').click();
  })()`;
  const up = await p.evaluate(TRACE(`() => ${openAct}`, 1600));
  const upH = series(up, ids.folded, 'h');
  notes.push(`${tag}: unfold h ${upH[0]}→${upH.at(-1)} steps=${uniq(upH).length}` +
             ` reveal=${anyFrame(up, f => f.revealing > 0)}`);

  // ── cell: the human is done reading it (he folds it back) ───────────────
  const down = await p.evaluate(TRACE(`() => ${openAct}`, 1600));
  const dnH = series(down, ids.folded, 'h');
  notes.push(`${tag}: fold h ${dnH[0]}→${dnH.at(-1)} steps=${uniq(dnH).length}` +
             ` clippedghost=${anyFrame(down, f => f.clipped > 0)}`);

  // ── cell: the loop changes a card under him (a note lands, it grows) ────
  // data-qid IS the title, URI-encoded, so this addresses the same entry the
  // trace is watching
  const tickAct = `() => fetch('/comment', { method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ question: decodeURIComponent(${JSON.stringify(ids.open)}),
        comment: 'a note that makes the card taller', section: 'Open' }) })`;
  const tick = await p.evaluate(TRACE(tickAct, 5200));
  const tkH = series(tick, ids.open, 'h');
  notes.push(`${tag}: tick-grow h ${tkH[0]}→${tkH.at(-1)} steps=${uniq(tkH).length}`);

  if (!reduced) {
    // ── unfold ────────────────────────────────────────────────────────────
    // #414 PRECONDITION first: rAF density IS the frame rate. Without this
    // line a starved window reports "the motion is wrong" when what happened
    // is "we did not look often enough" — opposite responses, one line (#413).
    ok(`${tag}: unfold window sampled enough to see motion (${upH.length} frames)`,
       upH.length >= MIN_SAMPLES);
    ok(`${tag}: unfolding really changes height (vacuity floor ${MIN_FOLD_SPAN}px) `
     + `(measured ${upH[0]} -> ${upH.at(-1)}, ${span(upH)}px)`,
       span(upH) >= MIN_FOLD_SPAN && upH.at(-1) > upH[0]);
    ok(`${tag}: unfolding TRAVELS its height (it does not jump open) `
     + `(${between(upH, upH[0], upH.at(-1))} of ${upH.length} part-way)`,
       between(upH, upH[0], upH.at(-1)) >= 1);
    ok(`${tag}: the revealed body eases in rather than being wiped up`,
       anyFrame(up, f => f.revealing > 0));

    // ── fold ──────────────────────────────────────────────────────────────
    ok(`${tag}: fold window sampled enough to see motion (${dnH.length} frames)`,
       dnH.length >= MIN_SAMPLES);
    ok(`${tag}: folding really changes height (vacuity floor ${MIN_FOLD_SPAN}px) `
     + `(measured ${dnH[0]} -> ${dnH.at(-1)}, ${span(dnH)}px)`,
       span(dnH) >= MIN_FOLD_SPAN && dnH.at(-1) < dnH[0]);
    ok(`${tag}: folding TRAVELS its height (it does not snap shut) `
     + `(${between(dnH, dnH[0], dnH.at(-1))} of ${dnH.length} part-way)`,
       between(dnH, dnH[0], dnH.at(-1)) >= 1);
    ok(`${tag}: the departing body FADES rather than blanking`,
       anyFrame(down, f => f.clipped > 0));

    // ── tick-grow ─────────────────────────────────────────────────────────
    ok(`${tag}: tick-grow window sampled enough to see motion (${tkH.length} frames)`,
       tkH.length >= MIN_SAMPLES);
    ok(`${tag}: a card the loop grows under him really changes height `
     + `(vacuity floor ${MIN_GROW_SPAN}px; measured ${tkH[0]} -> ${tkH.at(-1)}, `
     + `${span(tkH)}px)`,
       span(tkH) >= MIN_GROW_SPAN);
    ok(`${tag}: a card the loop grows under him travels too `
     + `(${between(tkH, tkH[0], tkH.at(-1))} of ${tkH.length} part-way)`,
       between(tkH, tkH[0], tkH.at(-1)) >= 1);

    // the outcome's own property, which is what covers the whole matrix
    /* The property that covers the whole matrix is the one HE sees: anything
       that ended somewhere else got there continuously.

       Asserting the MECHANISM instead was the first version of this, and it
       was wrong in an instructive way. It demanded an inline transform on
       every card that moved — but a card sitting below one that is folding
       is carried by the layout as that height animates, continuously and
       welded to the card it is following, with no transform of its own. That
       is the better motion, and the mechanism check would have forbidden it.
       So: frames strictly part-way between the ends, not implementation
       traces. (The old form counted distinct positions — the same frame-rate
       claim #333 retired on the three height assertions above.) */
    const MOVE = 2;      // regroupCards ignores sub-pixel drift; so do we
    const seriesOf = (frames, id, k) =>
      frames.map(f => f.at[id] && f.at[id][k]).filter(v => v !== undefined);
    const mech = [up, down, tick].map(frames => {
      const first = frames[0].at, last = frames.at(-1).at;
      const pick = k => Object.keys(last).filter(id => first[id] &&
        Math.abs(first[id][k] - last[id][k]) >= MOVE);
      // zero part-way frames = jump/snap, at any frame rate
      const jumped = pick('top').filter(id => {
        const vs = seriesOf(frames, id, 'top');
        return between(vs, vs[0], vs.at(-1)) < 1;
      });
      const snapped = pick('h').filter(id => {
        const vs = seriesOf(frames, id, 'h');
        return between(vs, vs[0], vs.at(-1)) < 1;
      });
      return { n: pick('top').length + pick('h').length, jumped, snapped,
               samples: frames.length,
               scaled: frames.some(f =>
                 Object.values(f.at).some(c => /scale\(/.test(c.tf))),
               flipped: frames.some(f => Object.values(f.at).some(c => c.tf)) };
    });
    notes.push(`${tag}: changed per phase = ${mech.map(m => m.n)}` +
               ` | jumped = ${JSON.stringify(mech.map(m => m.jumped.length))}` +
               ` | snapped = ${JSON.stringify(mech.map(m => m.snapped.length))}` +
               ` | samples = ${JSON.stringify(mech.map(m => m.samples))}` +
               ` | flip used = ${mech.map(m => m.flipped)}`);
    ok(`${tag}: matrix phases sampled enough to decide continuous travel `
     + `(${mech.map(m => m.samples).join('/')} frames)`,
       mech.every(m => m.samples >= MIN_SAMPLES));
    ok(`${tag}: EVERY card that ended elsewhere got there continuously`,
       mech.every(m => m.n > 0 && m.jumped.length === 0));
    ok(`${tag}: EVERY card that changed size changed it continuously`,
       mech.every(m => m.snapped.length === 0));
    ok(`${tag}: nothing in the list morphs by scale (that would squash it)`,
       mech.every(m => !m.scaled));
    ok(`${tag}: the FLIP is doing the work, not a CSS layout transition alone`,
       mech.some(m => m.flipped));
    await p.screenshot({ path: `${OUT}/states.png`, fullPage: true });
  } else {
    // timing changes, function does not: the same folding happens, at once.
    // These STAY as absolute counts (the OPPOSITE assertion of the travel
    // checks above): reduced motion must NOT animate, so few distinct heights
    // is the contract. Converting them to between()===0 would be correct too,
    // but the brief for #333 names this pair as the legitimate count that
    // must not be touched — a starved normal window and an instant reduced
    // step both produce few distinct values for different reasons, and this
    // half is "did it stay still enough", not "did it travel".
    ok(`${tag}: unfolding is one step`, uniq(upH).length <= 3 && upH.at(-1) > upH[0]);
    ok(`${tag}: folding is one step`, uniq(dnH).length <= 3 && dnH.at(-1) < dnH[0]);
    ok(`${tag}: no card is ever FLIPped`,
       [up, down, tick].every(fr => fr.every(f =>
         Object.values(f.at).every(c => !c.tf))));
    ok(`${tag}: no ghosts and no reveals`,
       [up, down, tick].every(fr => fr.every(f =>
         f.ghosts === 0 && f.revealing === 0)));
  }
  ok(`${tag}: no page errors`, errs.length === 0);
  await br.close();
}

finish();
