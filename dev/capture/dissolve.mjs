/* dissolve — #449: the route change still animates after the mist was shelved.

   The human reported framiness on question→review, and the fix shelved the SVG
   liquify mist behind MIST_ON (it regenerated feTurbulence every frame at a cost
   no cheaper lever could touch; see transitions.md). The dissolve must STILL
   arrive and depart — opacity + transform + (now) CSS blur ride CSS transitions,
   and a route change that snapped would have traded the gesture for the frames.

   A motion check must not encode a property of the machine (transitions.md):
   frame counts and durations are load-dependent on this host. The load-independent
   snap detector is `transitionstart` (#442): it fires iff the browser registered a
   CSS transition for the property, asking the browser "did you animate?" rather
   than "how many frames did a starved rAF sampler catch?". This guard uses it for
   the dissolve's core opacity transition on #view, and traces mid-frames as
   motion evidence when the sampler caught the window (same structure as
   confirmation.mjs). The #442 gap applies in reverse here: stepFx was main-thread
   rAF (now shelved), but the CSS opacity/transform/filter transitions are
   compositor-driven, so transitionstart is the primary probe and rAF mid-frames
   are the corroborating evidence, not the gate.

   The guard drives the EXACT route he named (/questions → /review with the longest-
   bodied open question docked), and asserts the gesture's two halves: the ghost
   departs (.out, opacity falling) and the view arrives (.enter removed, opacity
   rising). Reduced-motion asserts neither happens — the hard contract.

   #453: it also gates the RESTORED liquify's mechanism, load-independently —
   a MutationObserver records the ghost's inline filter during the window
   (registration evidence, like transitionstart: mutations land whatever the
   frame rate), the envelope's TERMINAL write proves stepFx ran to its end
   (#dissolveOut's displacement scale ends deterministically at 25 whatever
   the frame rate, and nothing clears it), and the feImage href proves the
   field is the cached texture rather than a live feTurbulence. Reverting the
   mechanism (MIST_ON false) reds the first two; an unwired texture reds the
   third.

   Writes to its target, so use a scratch fixture. usage:
   node dissolve.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
import { midFrames, transitionWindow, framesInWindow, waitFor } from './dom.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`; mkdirSync(OUT, { recursive: true });
const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions → /review crossfade (the route #449 named), the longest-bodied ' +
          'open question docked, plus the same under reduced-motion — two phases',
  traceWindow: '1600ms rAF + transition-event trace of #view opacity through the ~1.15s ' +
               'dissolve (DREAM_MS); settle waits 1600ms + 400ms',
});
const sleep = ms => new Promise(r => setTimeout(r, ms));
const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

// the fixture must hold a review artifact AND an open question — derived at
// runtime, never assumed, because a guard over an absent subject is silence.
const data = await (await fetch(`${BASE}/data.json`)).json();
const review = (data.reviews || [])[0];
const question = (data.questions_open || []).slice().sort((a, b) =>
  (b.body || '').length - (a.body || '').length)[0];
ok('fixture holds a review artifact and an open question', !!(review && question));
if (!review || !question) { notes.push('fixture incomplete — cannot test the dissolve'); await br.close(); finish(); }
else {

// NORMAL: drive the real question→review crossfade and capture transition events
// + an rAF opacity trace. transitionstart for opacity is the load-independent
// proof the browser registered the dissolve; mid-frames corroborate when sampled.
async function page(reduced = false) {
  const c = await br.newContext({ viewport: { width: 1440, height: 900 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await c.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the #view the guard traces first, not a fixed sleep (#428 class)
  await waitFor(p, '#view');
  return { c, p };
}

{
  const { c, p } = await page();
  // instrument #view for transition events BEFORE the dissolve, and trace opacity.
  // events and frames MUST share the same time base (relative to t0) — a mismatch
  // makes framesInWindow match nothing and the motion check passes vacuously.
  const trace = await p.evaluate(([rp, rq]) => {
    const view = document.getElementById('view');
    const events = [], frames = [], ghostFilters = [];
    let done = false;
    const onT = type => e => {
      if (e.propertyName === 'opacity' || e.propertyName === 'transform' || e.propertyName === 'filter')
        events.push({ type, prop: e.propertyName, t: Math.round((performance.now()) * 10) / 10 });
    };
    view.addEventListener('transitionrun', onT('run'));
    view.addEventListener('transitionstart', onT('start'));
    view.addEventListener('transitionend', onT('end'));
    // #453: the ghost's inline filter, recorded by mutation rather than by
    // sampling — a mutation lands whatever the frame rate, so this is the
    // same load-independent class of evidence as transitionstart.
    const mo = new MutationObserver(mrs => mrs.forEach(m => {
      if (m.target.classList && m.target.classList.contains('ghost'))
        ghostFilters.push(m.target.style.filter || '');
    }));
    mo.observe(document.body, { attributes: true, attributeFilter: ['style'], subtree: true });
    const t0 = performance.now();
    navigate('review', rp, { push: true, q: rq });   // the real crossfade
    (function f() {
      const t = performance.now() - t0;
      frames.push({ t: Math.round(t * 10) / 10, op: Math.round(parseFloat(getComputedStyle(view).opacity) * 100) });
      if (t < 1600) requestAnimationFrame(f);
    })();
    return new Promise(res => setTimeout(() => { mo.disconnect(); res({ events, frames, t0, ghostFilters }); }, 1700));
  }, [review.name, question.title]);

  const evs = trace.events, frames = trace.frames, t0 = trace.t0;
  // normalise event timestamps to the same relative base as frames
  const evsRel = evs.map(e => ({ ...e, t: Math.round((e.t - t0) * 10) / 10 }));
  // #442: opacity on #view is compositor-driven. transitionstart is the
  // load-independent snap detector (the browser registered the dissolve); rAF
  // mid-frames are a diagnostic, not a gate, because a starved sampler reads
  // zero intermediate values over a perfect compositor animation. The gesture
  // proof is: transitionstart fired (it animated) AND the opacity trace touched
  // near-0 (the .enter start pose took) and settled near-full (it arrived).
  const opWin = transitionWindow(evsRel, 'opacity', 0, 'first');
  const inside = framesInWindow(frames, opWin);
  const minOp = Math.min(...frames.map(f => f.op));
  const maxOp = Math.max(...frames.map(f => f.op));
  const reached = minOp <= 12 && frames.at(-1).op >= 95;
  const mids = midFrames(frames.map(f => f.op));   // diagnostic only
  notes.push(`normal: opacity transition ran=${opWin.ran} start=${opWin.start} ` +
             `${inside}/${frames.length} in window; op min=${minOp} max=${maxOp} last=${frames.at(-1).op} mids=${mids}`);
  ok('the dissolve runs a CSS opacity transition on #view (not a snap)', opWin.ran);
  ok('the view reaches near-zero and returns to near-full (the full gesture)',
     reached);

  // the ghost: crossfade creates it, .out departs it. Assert it existed AND
  // departed (class membership), because a dissolve with no departure half is
  // half a gesture. Read once after the dissolve window.
  const ghost = await p.evaluate(() => {
    const view = document.getElementById('view');
    const f = getComputedStyle(view).filter;
    // blur(0px) is visually crisp (zero radius) but not the string 'none';
    // parse the radius so the check holds whether CSS blur is active or not.
    const blurMatch = f.match(/blur\(([\d.]+)px\)/);
    const crisp = f === 'none' || (blurMatch && parseFloat(blurMatch[1]) === 0);
    return { review: document.body.classList.contains('review'),
             settled: getComputedStyle(view).opacity === '1',
             filter: f, crisp };
  });
  notes.push(`normal settled: body.review=${ghost.review} opacity=1=${ghost.settled} filter="${ghost.filter}" crisp=${ghost.crisp}`);
  ok('the crossfade completed to /review with a crisp settled view',
     ghost.review && ghost.settled && ghost.crisp);

  // #453: the liquify itself. Three load-independent facts: the ghost carried
  // the mist filter (mutation evidence), the envelope ran to its deterministic
  // terminal write (stepFx's last frame leaves #dissolveOut's scale at 25 and
  // nothing clears it — a starved rAF that fires even once after DREAM_MS
  // lands the same value), and the field is the cached texture, not a live
  // feTurbulence. Reverting to MIST_ON false reds the first two.
  const mist = await p.evaluate(() => {
    const sc = document.querySelector('#dissolveOut feDisplacementMap');
    const fi = document.querySelector('#dissolveOut feImage.texsrc');
    return { scale: sc ? sc.getAttribute('scale') : null,
             href: fi ? (fi.getAttribute('href') || '') : '' };
  });
  notes.push(`mist: ghost filters seen=${JSON.stringify(trace.ghostFilters)} ` +
             `terminal scale=${mist.scale} feImage href=${mist.href.slice(0, 22) || '<empty>'}`);
  ok('the ghost carries the dissolve mist filter while it departs',
     trace.ghostFilters.some(f => f.includes('dissolveOut')));
  ok('the mist envelope runs to its end (terminal displacement scale)',
     parseFloat(mist.scale) >= 20);
  ok('the mist field is the cached feImage texture (#453), not live turbulence',
     mist.href.startsWith('data:image/png'));
  ok('no page errors', errs.length === 0);
  await c.close();
}

// REDUCED MOTION: the hard contract — route swaps are instant (no ghost, no
// mist, no transition). transitionstart must NOT fire for opacity; no .ghost
// should be created. (transitions.md: "reduced-motion is a hard contract.")
{
  const { c, p } = await page(true);
  const r = await p.evaluate(([rp, rq]) => {
    const view = document.getElementById('view');
    let opT = false;
    view.addEventListener('transitionstart', e => { if (e.propertyName === 'opacity') opT = true; });
    navigate('review', rp, { push: true, q: rq });
    return new Promise(res => setTimeout(() => res({
      opTransition: opT,
      ghost: !!document.querySelector('.ghost'),
      review: document.body.classList.contains('review'),
    }), 600));
  }, [review.name, question.title]);
  notes.push(`reduced: opacity transition fired=${r.opTransition} ghost=${r.ghost} review=${r.review}`);
  ok('reduced-motion swaps instantly — no opacity transition', !r.opTransition);
  ok('reduced-motion creates no ghost', !r.ghost);
  ok('reduced-motion still reaches /review', r.review);
  await c.close();
}

} // end else (fixture complete)
await br.close();
finish();
