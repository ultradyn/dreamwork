/* dissolveperf — #449: the question→review dissolve is framey. A CAPTURE, not a
   guard (see footer): it measures and prints; it gates nothing.

   #483 (2026-07-29): #453 landed the successor this file named — the feImage
   liquify IS the default now (MIST_ON=true, MIST_IMPL='feimage'), so the
   baseline arm measures the CURRENT mechanism, and a `turbulence` arm
   re-selects the shelved #449 field so the two mechanisms stay comparable in
   one run. What that comparison SHOWS is in the foot's reading comment — and
   it is not the naive expectation: #453 changed BOTH impls to filter the
   ghost only (the arriving view rides compositor CSS blur either way), so
   the old two-filter route no longer exists to A/B, and the arms differ in
   FIELD mechanism at ONE rasterisation each. The reading comment at the foot
   is the current truth; the #449 record below is kept as history.

   The human (2026-07-29) reported framiness on ONE route change — question→
   review — and suspected the SVG liquify ("the SVG liquify stuff, maybe? … a
   lot of elements … recent addition … collapsible sections … liquify effect").
   This capture reproduces that exact transition and A/Bs the cost levers against
   a baseline, on the same host in one process, because this host is never idle
   (ambient load 25–55 on 16 cores) and an absolute frame-time threshold is
   untestable here (#444 refused a threshold on the same ground).

   THE LOAD-BEARING SIGNAL is rAF throughput inside the dissolve window.
   `crossfade`'s `stepFx` IS main-thread rAF (it rewrites six filter attributes
   per frame), so a starved rAF loop is precisely the jank he sees — the OPPOSITE
   of #442, where compositor-driven opacity/transform animated fine while zero
   rAF fired. Here, rAF starvation IS the symptom. The metric is therefore
   DISTINCT frames in [tNav, tNav+1300] (rAF callbacks clustered <8ms apart count
   as one frame, because stepFx and the #dreambg shader both run rAF and fire
   back-to-back within a single frame — a raw inter-callback gap reads ~0.2ms
   and is an instrument artefact, not the frame rate).

   WHAT THIS CAPTURE PROVED (2026-07-29, load 35–50 on 16 cores, SwiftShader,
   8–12 reps per condition interleaved). Geometry on this route: the ghost is
   pinned to the OUTGOING /questions box (553×1557px, narrow+tall) while the
   incoming review view is 1360×740px (wide+short) — review is the widest route,
   which is why he named it.

     baseline (both filters, animated)          frames mean 12.1  fmax 262ms
     freeze baseFrequency (I1)                  frames 13.9       fmax 254ms   ← refuted
     freeze ALL six stepFx writes (I3)          frames 14.8       fmax 272ms   ← refuted
     V1 viewport-clamp ghost 553×1557→553×900   frames 13.7       fmax 187ms   ← refuted (geom confirmed)
     drop ghost filter early at u≈0.5 (I4)      frames 11         fmax 290ms   ← refuted
     remove BOTH dissolve filters (I5)          frames 27.6       fmax 129ms   ← ONLY win; +128% frames

   The decisive reading is I3 next to I5. I3 APPLIES the filter but with
   scale=0 / stdDeviation=0 — visually inert — and it costs the SAME as the
   fully animated baseline. So the cost is NOT the displacement/blur math and
   NOT the per-frame attribute rewrites: it is the mere presence of an active
   feTurbulence primitive in the pipeline, which Chrome rasterizes afresh every
   frame (it does not cache feTurbulence output across frames, even when no
   attribute on any primitive in the filter graph changed — I3 changed none).
   That is also why I1 (freeze baseFrequency) and I2 (shrink the area 42%) and
   I4 (shorten the two-filter window) all do nothing: none of them stop
   feTurbulence regenerating per frame. Only I5 — removing the filter entirely —
   recovers frames, and I5 is forbidden by transitions.md ("a route change that
   stops liquifying to gain frames has traded away the thing the page exists to
   be"). So no CHEAP, in-constraint fix exists in this increment.

   The successor this capture named — the human's texture idea done as the one
   thing that escapes per-frame feTurbulence — was answered by #453 (1e0bd0e):
   pre-rendered noise consumed via feImage, the field moved by feOffset/feTile,
   ONE rasterisation on the departing ghost (the arriving haze is compositor
   CSS blur). Chrome does cache the feImage source across frames, and #453
   measured ~+40% frames over the two-filter turbulence route in this harness.
   MIST_IMPL='feimage' is now the DEFAULT, so `baseline` below IS the feImage
   mechanism; the `turbulence` arm re-selects the shelved #449 field. Both
   impls now filter the ghost ONLY, so the arms are an equal-rasterisation
   A/B of field mechanism — and #453's +40% was the 2→1 rasterisation cut,
   which no MIST_IMPL value can re-select (the second filter is deleted, not
   gated). See the foot's reading comment for what the arms show.

   WHY THIS IS A CAPTURE, NOT A GUARD. A perf threshold on this host is a load
   meter, not a check: baseline frames ranged 4–20 and fmax 110–540ms across
   reps at load 35–50. transitions.md (#311/#444) and inbox precedent (#444
   refused a duration floor for exactly this) forbid encoding a property of the
   machine as a feature check. This script prints the A/B distribution for a
   human/lanes to read; it does not exit non-zero on a frame count.

   usage: node dissolveperf.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { readFileSync } from 'node:fs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const loadavg = () => { try { return readFileSync('/proc/loadavg', 'utf8').split(' ')[0]; } catch { return '?'; } };
const cores = (() => { try { return readFileSync('/proc/cpuinfo', 'utf8').split('\n').filter(l => l.startsWith('processor')).length; } catch { return '?'; } })();
if (OUT) { import('node:fs').then(({mkdirSync}) => mkdirSync(OUT, {recursive:true})); }

const data = await (await fetch(`${BASE}/data.json`)).json();
const review = (data.reviews || [])[0];
// the LONGEST-bodied open question: the tallest review dock, so the cost on this
// route is a fact about the fixture, not a hope. (Same choice as reviewsplit.)
const question = (data.questions_open || []).slice().sort((a, b) =>
  (b.body || '').length - (a.body || '').length)[0];
if (!review || !question)
  throw new Error('fixture needs a review artifact and an open question');
const RP = review.name, RQ = question.title;

// rAF hook installed BEFORE the page script so every main-thread rAF (stepFx +
// #dreambg shader) is timestamped. One fn call + array push per rAF, present in
// ALL conditions equally, so it is controlled across the A/B.
const HOOK = `(() => {
  window.__raf = [];
  const orig = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function(cb) {
    return orig(function(ts){ window.__raf.push(performance.now()); return cb(ts); });
  };
  // #483: record every dissolve filter the page APPLIES (distinct values, in
  // order). This is the precondition evidence for the mechanism A/B — the
  // baseline must show url(#dissolveOut) and the turbulence arm
  // url(#dissolveOutT), or an arm that "measures turbulence" while running
  // feImage reads the same number twice and calls it a comparison.
  window.__mists = [];
  const obs = new MutationObserver(mrs => { for (const m of mrs) {
    const f = (m.target.style && m.target.style.filter) || '';
    if (f.includes('dissolve') && window.__mists[window.__mists.length - 1] !== f) window.__mists.push(f);
  }});
  const go = () => obs.observe(document.body, {attributes:true, attributeFilter:['style'], subtree:true});
  if (document.body) go(); else document.addEventListener('DOMContentLoaded', go);
})();`;
// I1: freeze baseFrequency writes only (refutes the baseFrequency-invalidation
// hypothesis). Faithful to deleting the two `tOut/tIn.setAttribute('baseFrequency'…)`
// lines in stepFx.
const C_FREEZEBF = HOOK + `(() => {
  const p = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function(n, v) { if (n === 'baseFrequency') return; return p.call(this, n, v); };
})();`;
// V1 (authorized, refuted): clamp every .ghost to the viewport height so its
// filter region shrinks to what is on screen. Re-applied on every style/class
// mutation because crossfade writes the ghost's box mid-dissolve.
const C_CLAMP = HOOK + `(() => {
  const clamp = () => document.querySelectorAll('.ghost').forEach(g => {
    g.style.height = window.innerHeight + 'px'; g.style.overflow = 'hidden';
  });
  const obs = new MutationObserver(clamp);
  const go = () => { obs.observe(document.body, {childList:true, subtree:true, attributes:true, attributeFilter:['style','class']}); clamp(); };
  if (document.body) go(); else document.addEventListener('DOMContentLoaded', go);
})();`;
// I5 (forbidden, the reference win): strip both dissolve filters the instant
// crossfade sets them. Pure reflow + shader cost; no mist. Proves the filter is
// the cost and that removing it is the only thing that recovers frames.
const C_NOFILTER = HOOK + `(() => {
  const obs = new MutationObserver(mrs => mrs.forEach(m => { if ((m.target.style.filter||'').includes('dissolve')) m.target.style.filter=''; }));
  const go = () => obs.observe(document.body, {attributes:true, attributeFilter:['style'], subtree:true});
  if (document.body) go(); else document.addEventListener('DOMContentLoaded', go);
})();`;
const COND = { baseline: HOOK, turbulence: HOOK, freezeBf: C_FREEZEBF, clamp: C_CLAMP, noFilter: C_NOFILTER };
// The turbulence arm carries the SAME init script as baseline; the difference
// is the served document. MIST_IMPL is a `const` baked into the page by
// watch.py, so no init script can re-select it — the honest lever is the one
// a human would use, editing that one line, done here by rewriting the served
// HTML in flight. The rewrite targets the exact source line; if watch.py ever
// rewords it, rewrites comes back 0 and the arm reports itself unconfirmed
// instead of silently measuring feImage twice.
const MIST_LINE = "const MIST_IMPL = 'feimage';";

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

async function runOnce(condInit, turb) {
  const ctx = await br.newContext({ viewport: { width: 1440, height: 900 } });
  let rewrites = 0, rewriteMiss = false;
  if (turb) await ctx.route('**/*', async route => {
    const req = route.request();
    // only the TOP-LEVEL shell carries MIST_IMPL — the review route's artifact
    // iframe (#reviewframe) is a document request too, and it must neither be
    // rewritten nor counted as a miss.
    if (req.resourceType() !== 'document' || req.frame().parentFrame()) return route.continue();
    const resp = await route.fetch();
    const body = await resp.text();
    if (!body.includes(MIST_LINE)) { rewriteMiss = true; return route.fulfill({ response: resp, body }); }
    rewrites++;
    return route.fulfill({ response: resp, body: body.replace(MIST_LINE, "const MIST_IMPL = 'turbulence';") });
  });
  await ctx.addInitScript(condInit);
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the #view the guard traces first, not a fixed sleep (#428 class)
  await waitFor(p, '#view');
  // the REAL crossfade (pushState, no reload → the rAF hook persists). Drive the
  // exact route he named, with the docked question seeded for the longest body.
  const tNav = await p.evaluate(([rp, rq]) => {
    const t = performance.now(); navigate('review', rp, { push: true, q: rq }); return t;
  }, [RP, RQ]);
  await sleep(1500);   // dissolve (DREAM_MS 1150) + settle
  const r = await p.evaluate(() => {
    const v = document.getElementById('view');
    return { raf: window.__raf.slice(), mists: window.__mists.slice(),
      review: document.body.classList.contains('review'),
      reviewH: document.documentElement.scrollHeight, vN: document.querySelectorAll('#view *').length,
      vW: v ? v.offsetWidth : 0, vH: v ? v.offsetHeight : 0 };
  });
  await ctx.close();
  // which mechanism the ghost ACTUALLY wore, from the filters the page applied:
  // 'T' = shelved two-filter feTurbulence, 'fe' = cached feImage texture,
  // '?' = no dissolve filter seen (arm measured nothing — say so, loudly).
  const mist = r.mists.some(f => f.includes('#dissolveOutT') || f.includes('#dissolveInT')) ? 'T'
    : r.mists.some(f => f.includes('#dissolveOut') || f.includes('#dissolveIn')) ? 'fe' : '?';
  // distinct-frame clustering: callbacks <8ms apart are one frame (stepFx +
  // shader share the frame). The count and the inter-FRAME gap distribution are
  // the load-bearing signal; a raw inter-callback gap is an instrument artefact.
  const win = r.raf.filter(t => t >= tNav && t <= tNav + 1300).sort((a, b) => a - b);
  const frames = [];
  for (const t of win) if (!frames.length || t - frames[frames.length - 1] > 8) frames.push(t);
  const gaps = [];
  for (let i = 1; i < frames.length; i++) gaps.push(frames[i] - frames[i - 1]);
  gaps.sort((a, b) => a - b);
  return { errs, mist, rewrites, rewriteMiss, review: r.review, reviewH: r.reviewH, vN: r.vN, vW: r.vW, vH: r.vH,
    frames: frames.length,
    fmax: gaps.length ? +gaps.at(-1).toFixed(1) : null,
    stall50: gaps.filter(g => g > 50).length };
}

const REPS = +(process.env.DP_REPS || 10);   // env knob for quick iterations; 10 for a real read
const labels = ['baseline', 'turbulence', 'freezeBf', 'clamp', 'noFilter'];
const seq = []; for (let i = 0; i < REPS; i++) seq.push(...labels);
for (const l of labels) await runOnce(COND[l], l === 'turbulence');   // warmup (discarded)

console.log(`# dissolveperf #449/#483 — load ${loadavg()} on ${cores} cores; ${REPS} reps each, interleaved`);
console.log(`# route: /questions -> /review (p=${RP}, q=longest body ${question.body.length} chars); 1440x900; DREAM_MS=1150`);
console.log(`# metric: distinct rAF frames in [tNav, tNav+1300] (cluster<8ms=1frame); fmax=largest inter-frame gap(ms)`);
console.log(`# baseline IS the current default (MIST_ON=true, MIST_IMPL='feimage', #453); turbulence re-serves the page with MIST_IMPL='turbulence' (#449's shelved field, same one-filter dissolve)`);
const res = {};
for (const l of labels) res[l] = [];
for (const l of seq) {
  const r = await runOnce(COND[l], l === 'turbulence');
  res[l].push(r);
  console.log(`${l.padEnd(10)} mist=${r.mist.padEnd(2)} rw=${r.rewrites}${r.rewriteMiss ? '!' : ''} frames=${String(r.frames).padStart(3)} fmax=${String(r.fmax).padStart(7)} stall50=${String(r.stall50).padStart(2)} errs=${r.errs.length} [load ${loadavg()}]`);
}
function summ(a, k) {
  const v = a.map(r => r[k]).filter(x => x != null).sort((x, y) => x - y);
  if (!v.length) return 'n/a';
  const m = +(v.reduce((s, x) => s + x, 0) / v.length).toFixed(1);
  return `mean=${m} min=${v[0]} max=${v.at(-1)}`;
}
const mean = (a, k) => { const v = a.map(r => r[k]).filter(x => x != null); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
const g = res.baseline[0];
console.log(`\n# review settled: body.review=${g.review} H=${g.reviewH}px (${g.vN} els) view ${g.vW}x${g.vH}`);
// PRECONDITIONS, asserted from the run's own evidence (a green A/B over two
// arms that ran the same mechanism is the #483 trap — see HOOK comment):
// every turbulence rep must have worn a dissolveOutT/InT filter and rewritten
// the MIST_IMPL line exactly once; no other arm may show a T filter.
const tOK = res.turbulence.every(r => r.mist === 'T' && r.rewrites === 1 && !r.rewriteMiss);
const bOK = ['baseline', 'freezeBf', 'clamp', 'noFilter'].every(l => res[l].every(r => r.mist !== 'T'));
console.log(`# precondition: turbulence arm engaged #dissolveOutT on all ${REPS} reps (rewrite=1 each): ${tOK ? 'CONFIRMED' : '!! NOT CONFIRMED — the arm may have measured feImage twice'}`);
console.log(`# precondition: no T filter in baseline/freezeBf/clamp/noFilter: ${bOK ? 'CONFIRMED' : '!! T filter seen outside the turbulence arm'}`);
console.log('# summary (frames higher=better; fmax/stall lower=better)');
for (const l of labels) {
  console.log(`# ${l.padEnd(10)} frames ${summ(res[l], 'frames')} | fmax ${summ(res[l], 'fmax')} | stall50 ${summ(res[l], 'stall50')}`);
}
const bM = mean(res.baseline, 'frames'), tM = mean(res.turbulence, 'frames');
const bS = mean(res.baseline, 'stall50'), tS = mean(res.turbulence, 'stall50');
if (bM && tM) console.log(`# feImage vs turbulence: ${bM.toFixed(1)} vs ${tM.toFixed(1)} frames (${(100 * (bM - tM) / tM).toFixed(0)}%) | stall50 ${bS.toFixed(1)} vs ${tS.toFixed(1)}`);
console.log('\n# reading: baseline is the feImage liquify (#453) — ONE rasterisation on the ghost.');
console.log('# turbulence runs the SAME one-filter dissolve with #449\'s live feTurbulence field');
console.log('# re-selected: #453 moved the arriving view to compositor CSS blur for BOTH impls,');
console.log('# so the arms differ in FIELD MECHANISM at an equal rasterisation count, and frame');
console.log('# PARITY between them is the expected result — it re-confirms #453\'s measured cost');
console.log('# model (watch.py: the per-frame price is the rasterisation COUNT, nothing else;');
console.log('# "feImage≈feTurbulence, static≈animated ... one ≈ 34"). Where the live field still');
console.log('# pays is the stall50 column. The +40% #453 win was the 2→1 rasterisation cut; the');
console.log('# old two-filter route is deleted code, not a gated one, and cannot be re-selected.');
console.log('# noFilter stays the CSS-only reference: the most frames, and forbidden by');
console.log('# transitions.md (no mist = less gesture). freezeBf/clamp keep their #449 meaning.');
console.log('# See header.');
await br.close();
