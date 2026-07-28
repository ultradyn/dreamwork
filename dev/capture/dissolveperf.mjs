/* dissolveperf — #449: the question→review dissolve is framey. A CAPTURE, not a
   guard (see footer): it measures and prints; it gates nothing.

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

   The non-refuted successor is the human's texture idea done as the one thing
   that escapes per-frame feTurbulence: pre-render the noise ONCE to a canvas/
   image and consume it via feImage, animating the field by feOffset/feTile (or
   two interfering layers). Whether Chrome caches an feImage source across
   frames — and whether a translated static field reads as the gesture evolving —
   is unmeasured and is the successor task's first question.

   WHY THIS IS A CAPTURE, NOT A GUARD. A perf threshold on this host is a load
   meter, not a check: baseline frames ranged 4–20 and fmax 110–540ms across
   reps at load 35–50. transitions.md (#311/#444) and inbox precedent (#444
   refused a duration floor for exactly this) forbid encoding a property of the
   machine as a feature check. This script prints the A/B distribution for a
   human/lanes to read; it does not exit non-zero on a frame count.

   usage: node dissolveperf.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { readFileSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
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
const COND = { baseline: HOOK, freezeBf: C_FREEZEBF, clamp: C_CLAMP, noFilter: C_NOFILTER };

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

async function runOnce(condInit) {
  const ctx = await br.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(condInit);
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(250);
  // the REAL crossfade (pushState, no reload → the rAF hook persists). Drive the
  // exact route he named, with the docked question seeded for the longest body.
  const tNav = await p.evaluate(([rp, rq]) => {
    const t = performance.now(); navigate('review', rp, { push: true, q: rq }); return t;
  }, [RP, RQ]);
  await sleep(1500);   // dissolve (DREAM_MS 1150) + settle
  const r = await p.evaluate(() => {
    const v = document.getElementById('view');
    return { raf: window.__raf.slice(), review: document.body.classList.contains('review'),
      reviewH: document.documentElement.scrollHeight, vN: document.querySelectorAll('#view *').length,
      vW: v ? v.offsetWidth : 0, vH: v ? v.offsetHeight : 0 };
  });
  await ctx.close();
  // distinct-frame clustering: callbacks <8ms apart are one frame (stepFx +
  // shader share the frame). The count and the inter-FRAME gap distribution are
  // the load-bearing signal; a raw inter-callback gap is an instrument artefact.
  const win = r.raf.filter(t => t >= tNav && t <= tNav + 1300).sort((a, b) => a - b);
  const frames = [];
  for (const t of win) if (!frames.length || t - frames[frames.length - 1] > 8) frames.push(t);
  const gaps = [];
  for (let i = 1; i < frames.length; i++) gaps.push(frames[i] - frames[i - 1]);
  gaps.sort((a, b) => a - b);
  return { errs, review: r.review, reviewH: r.reviewH, vN: r.vN, vW: r.vW, vH: r.vH,
    frames: frames.length,
    fmax: gaps.length ? +gaps.at(-1).toFixed(1) : null,
    stall50: gaps.filter(g => g > 50).length };
}

const REPS = 10;
const labels = ['baseline', 'freezeBf', 'clamp', 'noFilter'];
const seq = []; for (let i = 0; i < REPS; i++) seq.push(...labels);
for (const l of labels) await runOnce(COND[l]);   // warmup (discarded)

console.log(`# dissolveperf #449 — load ${loadavg()} on ${cores} cores; ${REPS} reps each, interleaved`);
console.log(`# route: /questions -> /review (p=${RP}, q=longest body ${question.body.length} chars); 1440x900; DREAM_MS=1150`);
console.log(`# metric: distinct rAF frames in [tNav, tNav+1300] (cluster<8ms=1frame); fmax=largest inter-frame gap(ms)`);
const res = {};
for (const l of labels) res[l] = [];
for (const l of seq) {
  const r = await runOnce(COND[l]);
  res[l].push(r);
  console.log(`${l.padEnd(9)} frames=${String(r.frames).padStart(3)} fmax=${String(r.fmax).padStart(7)} stall50=${String(r.stall50).padStart(2)} errs=${r.errs.length} [load ${loadavg()}]`);
}
function summ(a, k) {
  const v = a.map(r => r[k]).filter(x => x != null).sort((x, y) => x - y);
  if (!v.length) return 'n/a';
  const m = +(v.reduce((s, x) => s + x, 0) / v.length).toFixed(1);
  return `mean=${m} min=${v[0]} max=${v.at(-1)}`;
}
const g = res.baseline[0];
console.log(`\n# review settled: body.review=${g.review} H=${g.reviewH}px (${g.vN} els) view ${g.vW}x${g.vH}`);
console.log('# summary (frames higher=better; fmax/stall lower=better)');
for (const l of labels) {
  console.log(`# ${l.padEnd(9)} frames ${summ(res[l], 'frames')} | fmax ${summ(res[l], 'fmax')} | stall50 ${summ(res[l], 'stall50')}`);
}
console.log('\n# reading: freezeBf≈baseline (baseFrequency NOT the cost); clamp≈baseline (area NOT the');
console.log('# cost); only noFilter recovers frames (+128%) — but noFilter is forbidden by transitions.md');
console.log('# (no mist = less gesture). Successor: feImage of a pre-rendered noise texture. See header.');
await br.close();
