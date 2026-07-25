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
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const uniq = a => [...new Set(a)];
const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];

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
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1200);
  const tag = reduced ? 'reduced-motion' : 'normal';

  const ids = await p.evaluate(() => ({
    folded: (document.querySelector('.qa.folded[data-qid]') || {dataset:{}}).dataset.qid,
    open: (document.querySelector('.qa.open[data-qid]') || {dataset:{}}).dataset.qid,
  }));
  if (!ids.folded || !ids.open) {
    console.log('FAIL fixture needs a folded and an open entry'); process.exit(1);
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
    ok(`${tag}: unfolding TRAVELS its height (it does not jump open)`,
       uniq(upH).length >= 6 && upH.at(-1) > upH[0]);
    ok(`${tag}: the revealed body eases in rather than being wiped up`,
       anyFrame(up, f => f.revealing > 0));
    ok(`${tag}: folding TRAVELS its height (it does not snap shut)`,
       uniq(dnH).length >= 6 && dnH.at(-1) < dnH[0]);
    ok(`${tag}: the departing body FADES rather than blanking`,
       anyFrame(down, f => f.clipped > 0));
    ok(`${tag}: a card the loop grows under him travels too`,
       uniq(tkH).length >= 6);

    // the mechanism's own property, which is what covers the whole matrix
    /* The property that covers the whole matrix is the one HE sees: anything
       that ended somewhere else got there continuously.

       Asserting the MECHANISM instead was the first version of this, and it
       was wrong in an instructive way. It demanded an inline transform on
       every card that moved — but a card sitting below one that is folding
       is carried by the layout as that height animates, continuously and
       welded to the card it is following, with no transform of its own. That
       is the better motion, and the mechanism check would have forbidden it.
       So: count intermediate positions, not implementation traces. */
    const MOVE = 2;      // regroupCards ignores sub-pixel drift; so do we
    const track = (frames, id, k) =>
      uniq(frames.map(f => f.at[id] && f.at[id][k]).filter(v => v !== undefined));
    const mech = [up, down, tick].map(frames => {
      const first = frames[0].at, last = frames.at(-1).at;
      const pick = k => Object.keys(last).filter(id => first[id] &&
        Math.abs(first[id][k] - last[id][k]) >= MOVE);
      const jumped = pick('top').filter(id => track(frames, id, 'top').length < 6);
      const snapped = pick('h').filter(id => track(frames, id, 'h').length < 6);
      return { n: pick('top').length + pick('h').length, jumped, snapped,
               scaled: frames.some(f =>
                 Object.values(f.at).some(c => /scale\(/.test(c.tf))),
               flipped: frames.some(f => Object.values(f.at).some(c => c.tf)) };
    });
    notes.push(`${tag}: changed per phase = ${mech.map(m => m.n)}` +
               ` | jumped = ${JSON.stringify(mech.map(m => m.jumped.length))}` +
               ` | snapped = ${JSON.stringify(mech.map(m => m.snapped.length))}` +
               ` | flip used = ${mech.map(m => m.flipped)}`);
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
    // timing changes, function does not: the same folding happens, at once
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

console.log(notes.join('\n'));
console.log('----');
console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
