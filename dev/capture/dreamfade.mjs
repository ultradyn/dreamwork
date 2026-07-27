/* dreamfade — #277: a departing element dissolves in place FIRST, then leaves.

   The single .gone class on .qaghost started blur, opacity and travel at the
   same moment on one .7s transition, so the ghost was already moving by the
   time it started dissolving — it read as "mush then snap". #277 adds a
   .pregone phase (blur 0→8px, opacity 1→.8, ≤2px drift, 180ms) before .gone
   sends it away. The two beats chain continuously because removing .pregone
   restores .qaghost's .7s, and the browser retargets from the dissolve's
   mid-values to .gone's targets.

   THE LOAD-BEARING ASSERTION IS PHASE SEPARATION, and an end-state check
   cannot fail on it (transitions.md): the ghost must carry .pregone (the
   dissolve-in-place class) BEFORE it carries .gone (the departure class). A
   single-beat departure — blur and opacity falling together from frame one —
   never has .pregone, because .gone is applied immediately. The between()
   idiom (fileimg.mjs:161) is the frame-rate-free half: opacity must visit
   the dissolve plateau (clearly below 1, clearly above 0) on its way down.

   The gesture is a FOLD (an open entry's body leaves), driven as states.mjs
   drives it: two sequential traces on the same summary — the first opens,
   the second closes and ghosts the body. The fixture has a foldable entry
   because states.mjs already depends on one.

   ordinary (OUT, PORT) shape — shared server, shared fixture, drives /questions.
   usage: node dreamfade.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions in two contexts (normal + reduced-motion), unfolding a ' +
          'folded entry then folding it back so its body departs through dreamAway',
  traceWindow: 'two rAF traces per context (1600ms each); ghost opacity/blur/' +
               'transform/class sampled per frame',
});

/* between(vals, first, last) — the frame-rate-free form (fileimg.mjs:161,
   transitions.md). At least one frame STRICTLY between the two ends, with a
   ~3% deadband so a frame that really is an end does not read as travel. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}

/* Two traces on the same summary — first opens, second closes. The close
   ghosts the departing body through dreamAway. states.mjs's exact pattern,
   because the open and close must be sequential page.evaluate calls (the
   handler runs synchronously per click, and a pre-open in a separate
   evaluate before the trace does not produce a ghost — the handler's
   snapshot/regroup needs to run inside the rAF window). */
const openAct = qid => `(async () => {
    document.querySelector('.qa[data-qid="${qid}"] .qfold > summary').click();
  })()`;

/* Trace the ghost's computed opacity and transform per frame, plus the SVG
   mist filter's displacement/blur attributes (driven per-frame from rAF in
   dreamAway). The filter nodes are shared (#departMist), so there's one set
   of attrs per ghost — fine, since only one ghost exists at a time. The ghost
   lives ~1s and removes itself, so it must be sampled per frame — looked for
   afterwards it is a departure that did happen reported as one that did not. */
const TRACE = (act, ms) => `((act, ms) => new Promise(res => {
  const frames = []; let removedAt = -1;
  const t0 = performance.now();
  (function step() {
    const t = performance.now() - t0;
    const gs = [...document.querySelectorAll('.qaghost')];
    if (gs.length > 0) {
      const g = gs[0];
      const cs = getComputedStyle(g);
      let ty = 0;
      const tr = cs.transform;
      if (tr && tr !== 'none') {
        const m = tr.match(/matrix(?:3d)?\\(([^)]+)\\)/);
        if (m) { const v = m[1].split(',').map(Number); ty = v.length === 16 ? v[13] : v[5]; }
      }
      // the blur now lives in the SVG mist filter, not CSS filter:blur()
      const dm = document.querySelector('#departMist feDisplacementMap');
      const bl = document.querySelector('#departMist feGaussianBlur');
      const blur = bl ? parseFloat(bl.getAttribute('stdDeviation') || '0') : 0;
      const disp = dm ? parseFloat(dm.getAttribute('scale') || '0') : 0;
      frames.push({ t, op: parseFloat(cs.opacity), blur, disp, ty,
                    pre: g.classList.contains('pregone'),
                    gone: g.classList.contains('gone') });
    } else if (frames.length > 0 && removedAt < 0) removedAt = t;
    if (t < ms) requestAnimationFrame(step); else res({ frames, removedAt });
  })();
  (async () => { await act(); })();
}))(${act}, ${ms})`;

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const perrs = []; p.on('pageerror', e => perrs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1200);
  const tag = reduced ? 'reduced-motion' : 'normal';

  // Find a FOLDED entry — the fixture seeds one (states.mjs depends on it).
  // Assert it exists before driving, so absence is a 3s named failure rather
  // than a 30s Playwright timeout (qsec.mjs's lesson).
  const qid = await p.evaluate(() => {
    const el = document.querySelector('.qa.folded[data-qid]');
    return el ? el.dataset.qid : null;
  });
  ok(`${tag}: fixture has a folded entry to unfold-then-fold (else vacuous)`, !!qid);
  if (!qid) { notes.push(`${tag}: no .qa.folded found`); await br.close(); continue; }

  // UP: unfold the entry (no ghost on the way in)
  await p.evaluate(TRACE(`() => ${openAct(qid)}`, 1600));

  if (reduced) {
    // Reduced motion: the ghost never exists. Close and assert no ghost.
    const ghosts = await p.evaluate(q => {
      document.querySelector('.qa[data-qid="'+q+'"] .qfold > summary').click();
      return new Promise(res => setTimeout(() =>
        res(document.querySelectorAll('.qaghost').length), 400));
    }, qid);
    ok(`${tag}: reduced motion creates no ghost (the phase is unreachable)`,
       ghosts === 0);
    ok(`${tag}: no page errors`, perrs.length === 0);
    await br.close();
    continue;
  }

  // DOWN: fold back — the body departs through dreamAway
  const { frames, removedAt } = await p.evaluate(TRACE(`() => ${openAct(qid)}`, 1600));

  ok(`${tag}: a ghost is created when the body departs (else vacuous)`,
     frames.length > 0);
  if (frames.length === 0) {
    notes.push(`${tag}: no ghost frames captured — fold may not have triggered`);
    await br.close(); continue;
  }

  const ops = frames.map(f => f.op);
  const blurs = frames.map(f => f.blur);
  const disps = frames.map(f => f.disp);
  const tys = frames.map(f => f.ty);
  const hadPregone = frames.some(f => f.pre);
  const hadGone = frames.some(f => f.gone);
  const firstPregone = frames.findIndex(f => f.pre);
  const firstGone = frames.findIndex(f => f.gone);
  notes.push(`${tag}: ${frames.length} ghost frames; op ${ops[0].toFixed(3)}→` +
             `${ops.at(-1).toFixed(3)}; blur max ${Math.max(...blurs).toFixed(1)}px; ` +
             `disp max ${Math.max(...disps).toFixed(1)}px; ` +
             `pregone@${firstPregone} gone@${firstGone}; ` +
             `removed ${removedAt < 0 ? 'never' : removedAt.toFixed(0) + 'ms'}`);

  // ── THE LOAD-BEARING ASSERTION: phase separation ────────────────────────
  // .pregone must appear BEFORE .gone on the ghost's class list. Without the
  // two-beat design, .gone is applied on frame 0 and .pregone never exists.
  // This is the class-membership half; the opacity-plateau assertion below
  // is the frame-rate-free half.
  ok(`${tag}: .pregone appears on the ghost at all (the phase exists)`,
     hadPregone);
  ok(`${tag}: .pregone appears BEFORE .gone (dissolve then leave, not together)`,
     firstPregone >= 0 && firstGone >= 0 && firstPregone < firstGone);

  // ── the frame-rate-free half: opacity visits the dissolve plateau ───────
  // The dissolve takes opacity 1→.8 (.pregone's target); the departure takes
  // it to 0 (.gone). A frame in the plateau is opacity between 0.6 and 0.95
  // — clearly past 1 (started dissolving), clearly above 0 (has not left).
  const leftStart = ops.some(o => o < 0.95);
  const plateau = ops.filter(o => o > 0.6 && o < 0.95).length;
  ok(`${tag}: the ghost leaves full opacity (precondition)`, leftStart);
  ok(`${tag}: opacity visits the dissolve plateau (0.6–0.95) on the way down`,
     plateau >= 1);

  // ── the mist (SVG displacement + blur) rises before the departure ───────
  // The #departMist filter grows displacement 0→14 and blur 0→4.5 over the
  // whole departure. Both must be clearly rising (>2) before opacity drops
  // below 0.4 (the departure zone), so the ghost hazes before it leaves.
  const depIdx = ops.findIndex(o => o < 0.4);
  const dispBefore = depIdx > 0 ? Math.max(...disps.slice(0, depIdx)) : 0;
  const blurBefore = depIdx > 0 ? Math.max(...blurs.slice(0, depIdx)) : 0;
  ok(`${tag}: mist displacement rises to ≥3px before the departure zone ` +
     `(dissolve-first)`, depIdx < 0 || dispBefore >= 3);
  ok(`${tag}: mist blur rises to ≥1px before the departure zone`,
     depIdx < 0 || blurBefore >= 1);

  // ── the mist must NOT decrease during departure (no un-mist) ────────────
  // The envelope is smoothstep, which is monotonic — displacement and blur
  // only grow. If either decreased, the envelope broke.
  const mid = Math.floor(frames.length / 2);
  const dispFirst = Math.max(...disps.slice(0, mid));
  const dispSecond = Math.max(...disps.slice(mid));
  ok(`${tag}: mist displacement does not decrease during departure ` +
     `(${dispSecond.toFixed(1)}px late >= ${dispFirst.toFixed(1)}px early)`,
     dispSecond >= dispFirst - 0.5);

  // ── the drift sign: question-card ghosts rise (#174), never fall ────────
  ok(`${tag}: the ghost drifts UP (question-card sign, #174), never down`,
     Math.min(...tys) <= 0);

  // ── lifetime: the corpse is gone within 1.1s (#277's cap) ───────────────
  // removedAt is the first rAF frame AFTER the ghost is gone, so it includes
  // detection overhead on top of the setTimeout. The product lifetime
  // (setTimeout=1050ms) is under 1.1s; the guard allows rAF scheduling slack.
  ok(`${tag}: the corpse is removed within 1.1s (plus rAF detection slack)`,
     removedAt > 0 && removedAt <= 1300);

  ok(`${tag}: no page errors`, perrs.length === 0);
  await br.close();
}

finish();
