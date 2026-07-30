/* #177 — the text boxes grow with what he types, then scroll.

   His numbers are the contract: the composer starts at 2-3 rows and grows to
   15; an answer/note box starts at 2 and grows to 6. The asymmetry is the
   point (a 15-line box inside a question card shoves the list), so the two
   ceilings are checked separately and never unified.

   Every motion check drives the REAL gesture on the REAL route and traces it
   per-rAF. The frame-rate-free form is the house idiom: a frame strictly
   BETWEEN the two ends (`midFrames`, the shared helper in dom.mjs) is the
   whole distinction between a snap and a travel — a snap visits none at any
   frame rate. A vacuity precondition (the span, derived at runtime from the
   box's own line-height) sits beside it so a check over a box that never
   moved fails as "vacuous" rather than as "it snapped", and a sample-count
   precondition sits first so a starved rAF window fails as "sampled too
   sparsely" rather than as a motion bug. Three distinct FAIL lines for three
   distinct causes (#442's ambiguity, not re-added here).

   The MOTION is driven by ONE input event that grows the box by several
   lines: that is one travel (normal: part-way frames; reduced: an instant
   step, none), where a many-newline sweep would visit a plateau per newline
   and read as "travelled" under reduced motion too. The ceiling +
   scroll-past check is the one that types many, slowly.

   The production line whose change reds the growth-travel check is the CSS
   `transition:height .85s cubic-bezier(.32,.1,.2,1)` on the textarea (in
   STYLE): remove it and the box still resizes (fitText still sets the height)
   but it SNAPS, so midFrames collapses to 0 and the card below teleports
   with it. The reduced-motion `transition:none` override in the same media
   block is the line whose change reds the reduced "no travel" half. The
   `data-max-rows` attribute (in APP_BODY / qaCompose) is the line whose
   removal reds the ceiling check — fitText then leaves the box alone.

   Writes to the target it is pointed at (one /command to force a real tick),
   so point it at a scratch copy.
   usage: node autogrow.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { midFrames } from './dom.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions (an open card answer box) and the composer, in normal ' +
          'and reduced-motion contexts: one-input growth + the ceiling + ' +
          'scroll-past-ceiling + shrink + a real tick that recreates the box',
  traceWindow: '1400ms rAF traces around one input (the .85s height travel + ' +
               'a settle beat), plus a ~6s window for the tick-survival step',
});

const NL = '\n';
/* Minimum samples for a part-way frame to be DECIDABLE: start, at least one
   intermediate draw, end. This is a decidability floor, not a frame-rate bet
   — #414's whole point (and the constant prominence.mjs / confirmation.mjs /
   states.mjs carry). rAF density IS the frame rate, so under host load the
   window thins and "did it travel" becomes undecidable rather than wrong;
   naming the count makes a starved run print "sampled enough… (N frames)"
   instead of masquerading as a motion bug. A floor above 3 re-couples the
   check to how many frames THIS BOX drew, which is exactly the failure #414
   chased out — a genuine .85s travel at ~40 load still draws a dozen frames
   with >=1 part-way, and `mid >= 1` is the rank-1 assertion that holds there. */
const MIN_SAMPLES = 3;
const uniq = a => [...new Set(a)];
const span = vals => Math.abs((vals.at(-1) ?? 0) - (vals[0] ?? 0));
const nums = (frames, k) => frames.map(f => f[k]).filter(v => v !== null && v !== undefined);

/* one textarea's line height, measured the way `fitText` measures it: a
   resolved pixel line-height when there is one, otherwise a two-line probe in
   the box's own font. Derived, never a pixel literal tuned to the layout. */
async function lineHeightOf(page, sel) {
  return page.evaluate(s => {
    const ta = document.querySelector(s);
    if (!ta) return 0;
    const cs = getComputedStyle(ta);
    const lh = parseFloat(cs.lineHeight);
    if (isFinite(lh) && lh > 0) return lh;
    const p = document.createElement('div');
    p.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;' +
      'border:0;padding:0;margin:0;width:0;font:' + cs.font +
      ';line-height:' + cs.lineHeight;
    p.textContent = 'M\nM';
    document.body.appendChild(p);
    const h = p.getBoundingClientRect().height / 2;
    p.remove();
    return h || parseFloat(cs.fontSize) * 1.2;
  }, sel);
}

/* Trace `sel`'s height and `belowSel`'s top per rAF while ONE input event
   runs. After `delay`, the box's value becomes `set` (replace) or gains
   `append`, and one 'input' event is dispatched — the same delegated listener
   fitText hangs off — then rAF runs on for `ms`.

   rAF OWNS the window: it is the only in-page work, as a pure
   promise + requestAnimationFrame loop (the shape prominence.mjs / regroup.mjs
   trace in). An earlier form ran a `while … await setTimeout(24)` task pump
   alongside the rAF sampler inside the SAME evaluate; under this host's
   ~30–50 load that pump churned the main thread and the window collapsed to
   5–6 frames — flaking the guard 2-in-3 while the feature was correct. The
   mutation is now ONE scheduled task, not a poll, so sampling and the .85s
   travel share the frame clock undisturbed. (#428: never a quiet-machine bet.) */
async function trace(page, sel, belowSel, { delay, set, append, ms }) {
  return page.evaluate(({ sel, belowSel, delay, setv, appendv, ms }) => {
    const ta = document.querySelector(sel);
    const frames = [];
    const t0 = performance.now();
    if (ta) ta.focus();
    // ONE scheduled mutation, not a poll — set or append, then one input event
    if (ta && (setv !== null || appendv !== null)) {
      setTimeout(() => {
        if (setv !== null && setv !== undefined) ta.value = setv;
        else if (appendv !== null && appendv !== undefined) ta.value = (ta.value || '') + appendv;
        ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
      }, delay);
    }
    return new Promise(res => {
      (function step() {
        const t = document.querySelector(sel),
              b = belowSel ? document.querySelector(belowSel) : null;
        frames.push({
          h: t ? +t.getBoundingClientRect().height.toFixed(2) : null,
          top: b ? +b.getBoundingClientRect().top.toFixed(2) : null,
        });
        if (performance.now() - t0 < ms) requestAnimationFrame(step);
        else res(frames);
      })();
    });
  }, { sel, belowSel, delay, setv: set ?? null, appendv: append ?? null, ms });
}

/* the growth + carries-below assertion set. `reduced` flips the travel
   expectation (an instant step has no part-way frame) but keeps the vacuity
   + sample-count preconditions, so a reduced run that did not grow fails as
   "vacuous" exactly as a normal one would. */
function checkTravel(label, frames, lineH, reduced) {
  const h = nums(frames, 'h'), top = nums(frames, 'top');
  const floor = lineH * 0.5;                  // a real growth is several lines; half one is margin
  ok(`${label}: window sampled enough to decide travel vs snap (${h.length} frames; ` +
     `under ${MIN_SAMPLES} reads "sampled too sparsely", a load red, NOT "snap")`,
     h.length >= MIN_SAMPLES);
  ok(`${label}: the box really changed height (else the travel check is vacuous) ` +
     `(${h[0]} -> ${h.at(-1)}, ${span(h).toFixed(1)}px; floor ${floor.toFixed(1)}px)`,
     span(h) >= floor);
  // THE motion line. A snap leaves NO frame strictly between the ends; the
  // transition is what produces them. Reduced runs the same trace and asserts
  // the opposite (an instant step), so the one check distinguishes them.
  ok(`${label}: growth TRAVELS (it does not snap) ` +
     `(${midFrames(h)} of ${h.length} part-way; reds when transition:height is removed)`,
     reduced ? midFrames(h) === 0 : midFrames(h) >= 1);
  if (top.length) {
    ok(`${label}: what sits below the box is CARRIED, not teleported ` +
       `(${midFrames(top)} of ${top.length} part-way tops; span ${span(top).toFixed(1)}px)`,
       reduced ? midFrames(top) === 0 : midFrames(top) >= 1);
  }
}

// a block of text that grows a box from its floor by several lines in one go
const BLOCK = (n) => Array.from({ length: n }, (_, i) => 'line ' + i).join('\n') + '\n';

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1100 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1100);
  const tag = reduced ? 'reduced-motion' : 'normal';

  // ── the answer/note box, inside the question list ───────────────────────
  const ids = await p.evaluate(() => {
    const cards = [...document.querySelectorAll('.qa.open[data-qid]')];
    const first = cards[0], second = cards[1];
    return {
      ta: first ? first.querySelector('textarea[id^="qi"]')?.id : null,
      below: second?.dataset.qid || null,
      rows: first ? first.querySelector('textarea')?.dataset.maxRows : null,
    };
  });
  if (!(await present(p, '.qa.open textarea[id^="qi"]',
                      'an open question with an answer box'))) {
    await br.close(); finish(); process.exit(1);
  }
  const taSel = `#${ids.ta}`;
  const belowSel = ids.below ? `.qa[data-qid="${ids.below}"]` : null;
  const lineH = await lineHeightOf(p, taSel);
  notes.push(`${tag}: answer box line-height ${lineH.toFixed(2)}px, max-rows ${ids.rows}`);
  // start at the floor
  await p.evaluate(s => { const t = document.querySelector(s); if (t) { t.value = ''; t.dispatchEvent(new InputEvent('input', { bubbles: true })); } }, taSel);
  await sleep(reduced ? 250 : 1000);

  // (1) growth — one input, several lines — travels (normal) or steps (reduced)
  const grow = await trace(p, taSel, belowSel, { delay: 120, append: BLOCK(5), ms: 1400 });
  checkTravel(`${tag} answer box: growth`, grow, lineH, reduced);

  // (2) shrink — clear it — is the same gesture reversed, not a snap
  const shrink = await trace(p, taSel, belowSel, { delay: 120, set: '', ms: 1400 });
  const sh = nums(shrink, 'h');
  ok(`${tag} answer box: shrink window sampled enough to decide (${sh.length} frames; ` +
     `under ${MIN_SAMPLES} is "sampled too sparsely", not "snap")`,
     sh.length >= MIN_SAMPLES);
  ok(`${tag} answer box: shrink really changes height (${sh[0]} -> ${sh.at(-1)}, ${span(sh).toFixed(1)}px)`,
     span(sh) >= lineH * 0.5);
  ok(`${tag} answer box: shrink TRAVELS (the reverse gesture, not a snap) ` +
     `(${midFrames(sh)} of ${sh.length} part-way)`,
     reduced ? midFrames(sh) === 0 : midFrames(sh) >= 1);

  // (3) the ceiling + scroll-past, measured EMPIRICALLY against the box's own
  //     settled heights rather than computed from a line-height (which cannot
  //     disagree with fitText's own measurement of the ceiling). Type to the
  //     ceiling, settle, type past it, settle again, and prove the box stopped
  //     growing and the content overflows. SETTLING matters: a height
  //     transition means the box is still chasing its cap right after a burst
  //     of inputs, so a fixed wait catches it mid-travel and reads "still
  //     growing". Poll until the height is stable instead.
  const CEIL_ROWS = parseInt(ids.rows, 10);
  const ceilPx = await p.evaluate(async ({ s, rows }) => {
    const t = document.querySelector(s); if (!t) return null;
    const settle = async () => {
      let prev = -1, stable = 0;
      for (let i = 0; i < 40; i++) {
        const h = +t.getBoundingClientRect().height.toFixed(2);
        if (Math.abs(h - prev) < 0.5) { if (++stable >= 2) return h; }
        else stable = 0;
        prev = h;
        await new Promise(r => setTimeout(r, 100));
      }
      return +t.getBoundingClientRect().height.toFixed(2);
    };
    const type = async n => { for (let i = 0; i < n; i++) {
      t.value += 'line ' + Math.random() + '\n';
      t.dispatchEvent(new InputEvent('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 40));
    } };
    t.value = ''; t.dispatchEvent(new InputEvent('input', { bubbles: true }));
    const hMin = await settle();                  // the empty floor
    await type(rows + 4);                         // to the ceiling
    const h1 = await settle();
    await type(6);                                // well past it
    const h2 = await settle();
    return { hMin, h1, h2, sh: t.scrollHeight, ch: t.clientHeight };
  }, { s: taSel, rows: CEIL_ROWS });
  // PRECONDITION (self-defending): the box grew past its empty floor by at
  // least a line, else the cap below passes vacuously on a box that never
  // grew (data-max-rows removed -> fitText leaves it at its CSS min-height).
  ok(`${tag} answer box: the box grew past its floor (${ceilPx?.hMin} -> ${ceilPx?.h1}px)`,
     ceilPx && ceilPx.h1 > ceilPx.hMin + lineH);
  ok(`${tag} answer box: growth stops at its ceiling (typing past it does not grow it: ${ceilPx?.h1} -> ${ceilPx?.h2}px)`,
     ceilPx && Math.abs(ceilPx.h2 - ceilPx.h1) < 2);
  // scroll-past: the box is capped AND the content beyond it overflows, so it
  // scrolls rather than growing forever. scrollHeight>clientHeight is the
  // honest signal — a programmatic value set does not move the caret, so
  // scrollTop itself stays 0 and would test the typing, not the box.
  ok(`${tag} answer box: past the ceiling it SCROLLS (scrollHeight ${ceilPx?.sh} > clientHeight ${ceilPx?.ch})`,
     ceilPx && ceilPx.sh > ceilPx.ch + 1);
  if (!reduced) await p.screenshot({ path: `${OUT}/answerbox-${tag}.png`, fullPage: false });

  // ── the composer ────────────────────────────────────────────────────────
  await p.click('#cmdplus'); await sleep(reduced ? 250 : 700);
  if (!(await present(p, '#cmdtext', 'the composer textarea'))) {
    await br.close(); finish(); process.exit(1);
  }
  const cLineH = await lineHeightOf(p, '#cmdtext');
  const cRows = await p.evaluate(() => document.querySelector('#cmdtext')?.dataset.maxRows || null);
  notes.push(`${tag}: composer line-height ${cLineH.toFixed(2)}px, max-rows ${cRows}`);
  await p.evaluate(() => { const t = document.getElementById('cmdtext'); if (t) { t.value = ''; t.dispatchEvent(new InputEvent('input', { bubbles: true })); } });
  await sleep(reduced ? 200 : 900);

  // the composer's send row sits directly below #cmdtext in the panel; a
  // growing thought carries it the way a growing answer box carries the card.
  const cgrow = await trace(p, '#cmdtext', '#cmdform .cmdrow',
    { delay: 120, append: BLOCK(5), ms: 1400 });
  checkTravel(`${tag} composer: growth`, cgrow, cLineH, reduced);

  const CROWS = parseInt(cRows, 10);
  const cCeil = await p.evaluate(async ({ s, rows }) => {
    const t = document.querySelector(s); if (!t) return null;
    const settle = async () => {
      let prev = -1, stable = 0;
      for (let i = 0; i < 40; i++) {
        const h = +t.getBoundingClientRect().height.toFixed(2);
        if (Math.abs(h - prev) < 0.5) { if (++stable >= 2) return h; }
        else stable = 0;
        prev = h;
        await new Promise(r => setTimeout(r, 100));
      }
      return +t.getBoundingClientRect().height.toFixed(2);
    };
    const type = async n => { for (let i = 0; i < n; i++) {
      t.value += 'line ' + Math.random() + '\n';
      t.dispatchEvent(new InputEvent('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 40));
    } };
    t.value = ''; t.dispatchEvent(new InputEvent('input', { bubbles: true }));
    const hMin = await settle();
    await type(rows + 4);
    const h1 = await settle();
    await type(6);
    const h2 = await settle();
    return { hMin, h1, h2, sh: t.scrollHeight, ch: t.clientHeight };
  }, { s: '#cmdtext', rows: CROWS });
  ok(`${tag} composer: the box grew past its floor (${cCeil?.hMin} -> ${cCeil?.h1}px)`,
     cCeil && cCeil.h1 > cCeil.hMin + cLineH);
  ok(`${tag} composer: growth stops at its ceiling (typing past it does not grow it: ${cCeil?.h1} -> ${cCeil?.h2}px)`,
     cCeil && Math.abs(cCeil.h2 - cCeil.h1) < 2);
  ok(`${tag} composer: past the ceiling it SCROLLS (scrollHeight ${cCeil?.sh} > clientHeight ${cCeil?.ch})`,
     cCeil && cCeil.sh > cCeil.ch + 1);

  ok(`${tag}: no page errors`, errs.length === 0);
  await br.close();
}

// ── #118 tick-survival: a status tick must not reset the height mid-typing.
//    The box's height is now state, so the snapshot must carry it across the
//    innerHTML swap and restore it SNAPPED (else the box re-grows every 2s).
{
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1100 } });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1100);
  const taId = await p.evaluate(() => {
    const c = document.querySelector('.qa.open[data-qid]');
    return c ? c.querySelector('textarea[id^="qi"]')?.id : null;
  });
  if (taId) {
    const sel = `#${taId}`;
    // grow the box to a few rows; vacuity is __dwViewRenderGen advancing
    // (#505 keeps the node — tag survival is no longer the re-render tell)
    const before = await p.evaluate(async (s) => {
      const t = document.querySelector(s); if (!t) return null;
      t.value = '';
      for (let i = 0; i < 4; i++) {
        t.value += 'kept thought ' + i + '\n';
        t.dispatchEvent(new InputEvent('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 60));
      }
      t.dataset.autogrowTag = '1';
      await new Promise(r => setTimeout(r, 900));   // let the growth settle
      return +t.getBoundingClientRect().height.toFixed(2);
    }, sel);
    // a quiet tick: the loop writing its own files, questions unchanged
    const gen0 = await p.evaluate(() => {
      if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
      return window.__dwViewRenderGen || 0;
    });
    await p.evaluate(() => fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'autogrow guard tick' }) }));
    // wait for setContent to run (gen advanced) or legacy node replace
    let tickWorked = false;
    for (let i = 0; i < 30; i++) {
      await sleep(200);
      tickWorked = await p.evaluate(g0 => {
        const advanced = (window.__dwViewRenderGen || 0) > g0;
        const t = document.querySelector('textarea[id^="qi"]');
        const replaced = t && !t.dataset.autogrowTag;
        return advanced || !!replaced;
      }, gen0);
      if (tickWorked) break;
    }
    const after = await p.evaluate(s => { const t = document.querySelector(s); return t ? +t.getBoundingClientRect().height.toFixed(2) : null; }, sel);
    ok('tick-survival: the tick really ran (render gen advanced or node replaced)',
       tickWorked);
    notes.push(`tick-survival: height ${before} -> ${after} across the tick`);
    // SNAPPED restore / kept height: within one line of before is the contract.
    const tol = Math.max(8, (before || 0) * 0.15);
    ok(`tick-survival: the grown height survives the tick (${before} -> ${after}, tol ${tol.toFixed(1)})`,
       tickWorked && before && after && Math.abs(after - before) < tol);
  } else {
    ok('tick-survival: an open answer box exists to grow across a tick', false);
  }
  ok('tick-survival: no page errors', errs.length === 0);
  await br.close();
}

finish();
