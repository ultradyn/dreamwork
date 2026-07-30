/* #128 — a follow-up thread must not read as the human replying to himself.

   His words, with a screenshot of an awaiting-fold entry: "the first thing
   that showed up was like me replying to me? ... if we have a thread of notes
   like that, they should be collapsed but also expandable."

   It looked like a rendering bug and it was a PARSER bug. The answer is lifted
   out of the sub-bullets so the card can show it as the resolution, and the
   lift discarded both the timestamps and WHERE the answer sat among the notes
   — so the render hoisted it above every note regardless of when it was
   written, and a note from two hours earlier appeared underneath it. Parsing
   the same entry with its sub-bullets in either source order produced
   byte-identical structures, which is the proof that no rendering fix could
   have worked.

   Three properties, all measured on what he sees rather than on how it is
   built:

     - CHRONOLOGY: a note written before the answer sits ABOVE it; one written
       after sits BELOW it; each says when it was written.
     - AUTHORSHIP SYMMETRY: of two things he wrote, both say so. The answer
       carries the same author label vocabulary his notes do (#109).
     - THE SETTLED PART COLLAPSES — and only it. Discussion a resolution has
       already answered is detail; a note written after it is a live amendment
       and an unanswered question's notes are his own steers, so neither is
       ever hidden. Expanding moves the list the way every other in-card expand
       does (the styleguide's fold-motion contract): the cards below travel
       continuously rather than jumping, and the revealed notes ease in.
       Reduced motion does it in one step with no ghost.

   The fixture entry is built for this: two notes before the answer (a segment
   long enough to be a thread) and one after (which must stay inline).
   usage: node thread.mjs <outdir> <port> */
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
  drives: '/questions in two contexts (normal + reduced-motion), probing an ' +
          'awaiting-fold thread (chronology, authorship symmetry, collapsed-by-default), ' +
          'expanding it through the shared fold-motion gesture, and collapsing again',
  traceWindow: 'two 1800ms rAF traces per context across the expand and the ' +
               'collapse, sampling every card top + height + ghost/reveal counts',
});

const uniq = a => [...new Set(a)];

/* the awaiting card, described by what is on screen. A note is addressed by a
   phrase from its own text, never by position — position is the thing under
   test. */
const PROBE = `(() => {
  const card = [...document.querySelectorAll('.qa')]
                 .find(c => c.querySelector('.anstext'));
  if (!card) return null;
  /* A closed <details> does NOT give its children display:none in current
     Chromium — it skips them with content-visibility, so their rects survive
     from the last layout and read as if they were on screen. A geometry test
     for "is it hidden" therefore passes on collapsed content; ask the browser
     whether he can see it instead. */
  const box = el => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top), h: Math.round(r.height),
             shown: el.checkVisibility ? el.checkVisibility() : r.height > 0 };
  };
  const note = frag => [...card.querySelectorAll('.follow')]
                         .find(f => f.textContent.includes(frag)) || null;
  const who = el => {
    const w = el && el.querySelector('.who');
    return w ? w.textContent.trim() : null;
  };
  const ans = card.querySelector('.anstext');
  const rows = ['written BEFORE', "loop's reply", 'legacy loop tag']
    .map(frag => { const n = note(frag);
      return { frag, box: box(n), who: who(n),
               text: n ? n.textContent.replace(/\\s+/g, ' ').trim() : null }; });
  return {
    qid: card.dataset.qid,
    answer: box(ans), answerWho: who(ans),
    answerText: ans ? ans.textContent.replace(/\\s+/g, ' ').trim() : null,
    rows,
    summaries: [...card.querySelectorAll('details > summary')]
                 .map(s => s.textContent.replace(/\\s+/g, ' ').trim()),
    // an OPEN question (no resolution) — its notes are live steers, so they
    // are never folded away no matter how many there are
    unanswered: [...document.querySelectorAll('.qa.open .follow')].map(box),
  };
})()`;

/* per-frame geometry of every card while `act` runs — the outcome check for
   "it travelled", copied in spirit from states.mjs: count intermediate
   positions, never demand a particular transform. */
const TRACE = (act, ms) => `((act, ms) => new Promise(res => {
  const frames = []; const t0 = performance.now();
  (function step() {
    const at = {};
    for (const c of document.querySelectorAll('.qa[data-qid]')) {
      const r = c.getBoundingClientRect();
      at[c.dataset.qid] = { top: Math.round(r.top), h: Math.round(r.height) };
    }
    frames.push({ at, ghosts: document.querySelectorAll('.qaghost').length,
                  revealing: document.querySelectorAll('.qreveal').length });
    if (performance.now() - t0 < ms) requestAnimationFrame(step); else res(frames);
  })();
  (async () => { await act(); })();
}))(${act}, ${ms})`;

const track = (frames, id, k) =>
  uniq(frames.map(f => f.at[id] && f.at[id][k]).filter(v => v !== undefined));

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1600 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the .qa cards the guard probes first, not a fixed sleep (#428 class)
  await waitFor(p, '.qa');
  const tag = reduced ? 'reduced-motion' : 'normal';

  const before = await p.evaluate(PROBE);
  if (!before) {
    ok(`${tag}: fixture has an awaiting-fold thread to probe`, false);
    notes.push('fixture needs an awaiting-fold entry');
    await br.close(); finish(); process.exit(1);
  }
  const [pre1, pre2, post] = before.rows;
  notes.push(`${tag}: answer top=${before.answer && before.answer.top}` +
             ` who=${before.answerWho} | ` +
             before.rows.map(r => `${r.frag}: top=${r.box && r.box.top}` +
               ` h=${r.box && r.box.h} who=${r.who}`).join(' | '));
  notes.push(`${tag}: summaries = ${JSON.stringify(before.summaries)}`);

  // ── collapsed by default: a segment of two notes is a thread ─────────────
  ok(`${tag}: a settled thread collapses by default`,
     !!pre1.box && !!pre2.box && !pre1.box.shown && !pre2.box.shown);
  ok(`${tag}: it is expandable, and says how much it is hiding`,
     before.summaries.some(s => /\b2\b/.test(s) && /note/.test(s)));
  // only the SETTLED part folds: a note written after the resolution is a live
  // amendment, and an unanswered question's notes are his own steers
  ok(`${tag}: a note written after the resolution stays inline`,
     !!post.box && post.box.shown);
  ok(`${tag}: an unanswered question never hides its notes`,
     before.unanswered.every(n => n.shown) && before.unanswered.length > 0);

  // ── authorship symmetry (#109, part b of #128) ──────────────────────────
  ok(`${tag}: the answer says whose words it is`, !!before.answerWho);
  ok(`${tag}: and it says it in the same vocabulary his notes do`,
     !!before.answerWho && before.answerWho === pre1.who);

  // ── chronology, once the thread is open ─────────────────────────────────
  const expandAct = `(async () => {
    const card = [...document.querySelectorAll('.qa')]
                   .find(c => c.querySelector('.anstext'));
    const s = card && card.querySelector('details > summary');
    if (s) s.click();
  })()`;
  const frames = await p.evaluate(TRACE(`() => ${expandAct}`, 1800));
  await sleep(200);
  const after = await p.evaluate(PROBE);
  const [apre1, apre2, apost] = after.rows;
  notes.push(`${tag}: expanded — answer top=${after.answer.top} ` +
             after.rows.map(r => `${r.frag}=${r.box && r.box.top}`).join(' '));

  ok(`${tag}: expanding reveals the hidden notes`,
     !!apre1.box && apre1.box.shown && !!apre2.box && apre2.box.shown);
  ok(`${tag}: a note written BEFORE the answer sits above it`,
     apre1.box.top < after.answer.top && apre2.box.top < after.answer.top);
  ok(`${tag}: the two earlier notes keep their own order`,
     apre1.box.top < apre2.box.top);
  ok(`${tag}: a note written AFTER the answer sits below it`,
     apost.box.top > after.answer.top);
  // position says which came first only if you trust it; the stamp says so
  ok(`${tag}: every contribution says when it was written`,
     /08:44/.test(apre1.text || '') && /08:59/.test(apre2.text || '') &&
     /09:02/.test(after.answerText || '') && /09:03/.test(apost.text || ''));

  // ── the fold-motion contract (styleguide) ───────────────────────────────
  const grew = Object.keys(frames.at(-1).at).filter(id =>
    frames[0].at[id] &&
    Math.abs(frames[0].at[id].top - frames.at(-1).at[id].top) >= 2);
  notes.push(`${tag}: cards displaced by the expand = ${grew.length}` +
             ` | own height steps = ${track(frames, before.qid, 'h').length}`);
  if (!reduced) {
    ok(`${tag}: the card travels its height rather than jumping open`,
       track(frames, before.qid, 'h').length >= 6);
    ok(`${tag}: the cards below it are carried continuously`,
       grew.length > 0 && grew.every(id => track(frames, id, 'top').length >= 6));
    ok(`${tag}: the revealed notes ease in rather than appearing`,
       frames.some(f => f.revealing > 0));
    await p.screenshot({ path: `${OUT}/thread-open.png`, fullPage: true });

    // ── and collapsing again is that moment run backwards ─────────────────
    const back = await p.evaluate(TRACE(`() => ${expandAct}`, 1800));
    ok(`${tag}: collapsing travels too`,
       track(back, before.qid, 'h').length >= 6);
    ok(`${tag}: the departing notes fade rather than blanking`,
       back.some(f => f.ghosts > 0));
  } else {
    // timing changes, function and legibility do not
    ok(`${tag}: expanding is one step`,
       track(frames, before.qid, 'h').length <= 3);
    ok(`${tag}: no ghosts and no reveals`,
       frames.every(f => f.ghosts === 0 && f.revealing === 0));
  }
  ok(`${tag}: no page errors`, errs.length === 0);
  await br.close();
}

finish();
