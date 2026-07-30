// #91 item 4 — per-frame trace of the composer's sliding selection indicator.
// Two things must both hold, and a single screenshot can prove neither:
//   * on OPEN it must SNAP under the active kind (an indicator that animates
//     up from its 0-width start reads as a glitch — the enter-snap rule);
//   * on SELECT it must SLIDE (intermediate positions), and under
//     reduced-motion it must jump with no intermediates.
//
// HARNESS-CONTRACT REPAIR (#538): this guard printed `open SNAP ok · select
// slide ok` — a human-readable line that is NOT the harness verdict contract
// (a non-sentinel ^(PASS|FAIL) line per check). The verdict-checker therefore
// read it as did-not-judge (rc=1) though the script exited 0, and worse: the
// script exited 0 UNCONDITIONALLY, so a real tween-on-open or a no-slide
// select printed "FAIL" in prose yet gated nothing. Reporting is now routed
// through makeReporter, so each property is a binding PASS/FAIL verdict and
// finish() sets the exit code from them.
//
// The PROPERTY asserted is UNCHANGED (no weakening): OPEN snaps ⇒ no
// intermediate position (a tween reads as a glitch); SELECT slides ⇒ ≥1
// intermediate position under motion, and 0 (a jump) under reduced-motion. The
// DETECTOR is upgraded to dom.mjs `midStates` — the rank-1 snap/slide idiom
// every registered motion guard shares — because the original ≥5-distinct bar
// was rank-N: under host load rAF is starved, a correct slide captures <5
// frames, and the guard reddened on a page that behaved (#414). midStates holds
// at any frame rate and tests the same property. Two preconditions are added so
// a green cannot be vacuous: the trace must have CAPTURED frames (an empty rAF
// trace reads as a snap that never happened), and the select click must have
// REGISTERED (the kind became checked, else the select trace measured a no-op).
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor, midStates } from './dom.mjs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/ — open the composer (#cmdplus) and select a kind (.cmdkind ' +
          'click); per-frame transform/width trace of #cmdind, in two contexts ' +
          '(motion + reduced-motion)',
  traceWindow: '~700ms rAF trace per gesture (the indicator\'s own duration); ' +
               'snap = 0 mid-positions, slide = ≥1 (rank-1, frame-rate-free)',
});

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

// absence-first, once: a page without the indicator/opener/kinds is a named
// FAIL in seconds, not a 30s click timeout reported as "the guard threw".
{
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 } });
  const pp = await ctx.newPage();
  pp.on('pageerror', e => errs.push(String(e)));
  await pp.goto(BASE + '/', { waitUntil: 'networkidle' });
  await waitFor(pp, '#cmdind');
  const hasInd = await present(pp, '#cmdind', 'the composer indicator (#cmdind)');
  const hasPlus = await present(pp, '#cmdplus', 'the composer opener (#cmdplus)');
  const hasKinds = await present(pp, '.cmdkind', 'the composer kind buttons (.cmdkind)');
  await ctx.close();
  if (!(hasInd && hasPlus && hasKinds)) { await browser.close(); finish(); process.exit(1); }
}

// arm a per-frame recorder BEFORE the click so frame 0 is the start state
const arm = page => page.evaluate(() => {
  window.__trace = [];
  const ind = document.getElementById('cmdind');
  const t0 = performance.now();
  (function tick() {
    const cs = getComputedStyle(ind);
    const m = new DOMMatrixReadOnly(cs.transform);
    window.__trace.push([+(performance.now() - t0).toFixed(0),
                         +m.m41.toFixed(1), +m.m42.toFixed(1),
                         +parseFloat(cs.width).toFixed(1)]);
    if (performance.now() - t0 < 700) requestAnimationFrame(tick);
  })();
});

async function run(rm) {
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 },
    reducedMotion: rm ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage();
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the #cmdind the guard traces first (#428 class)
  await waitFor(page, '#cmdind');
  await arm(page);
  await page.click('#cmdplus');
  await sleep(800);
  const openTrace = await page.evaluate(() => window.__trace);
  await arm(page);
  await page.click('.cmdkind[data-kind="do-now"]');
  await sleep(800);
  const selTrace = await page.evaluate(() => window.__trace);
  const state = await page.evaluate(() => ({
    checked: [...document.querySelectorAll('.cmdkind')]
      .filter(b => b.getAttribute('aria-checked') === 'true').map(b => b.dataset.kind),
    on: [...document.querySelectorAll('.cmdkind.on')].map(b => b.dataset.kind),
  }));
  await page.screenshot({ path: `${OUT}/indtrace-${rm ? 'reduced' : 'motion'}.png` });
  await ctx.close();
  return { rm, openTrace, selTrace, state };
}

// distinct (x,y,width) tuples — kept as a diagnostic (the original detector).
const xs = t => [...new Set(t.map(f => f[1] + ',' + f[2] + ',' + f[3]))];
// the composite position string per frame — the input to midStates.
const pos = t => t.map(f => f[1] + ',' + f[2] + ',' + f[3]);

for (const rm of [false, true]) {
  const mode = rm ? 'reduced-motion' : 'motion';
  const r = await run(rm);
  const openDistinct = xs(r.openTrace).length;
  const selDistinct = xs(r.selTrace).length;
  // midStates: frames whose composite position matches NEITHER end — the
  // rank-1 snap detector (dom.mjs). A snap/jump has 0 at ANY frame rate; a
  // slide has ≥1 as soon as one frame catches it part-way. The original
  // ≥5-distinct bar was rank-N: under host load rAF is starved and a correct
  // slide captures <5 frames and reddens on a page that behaved (#414) — so the
  // PROPERTY asserted (snap has no intermediates; slide has ≥1) is preserved
  // exactly, made load-robust the way every registered motion guard already is.
  const openMid = midStates(pos(r.openTrace));
  const selMid = midStates(pos(r.selTrace));
  notes.push(`${mode}: openDistinct=${openDistinct} selDistinct=${selDistinct} ` +
             `openMid=${openMid} selMid=${selMid} openFrames=${r.openTrace.length} selFrames=${r.selTrace.length} state=${JSON.stringify(r.state)}`);
  // preconditions: a green over an empty trace or a no-op click proves nothing
  ok(`OPEN trace captured frames [${mode}]`, r.openTrace.length >= 2);
  ok(`SELECT trace captured frames [${mode}]`, r.selTrace.length >= 2);
  ok(`the select kind became checked [${mode}] (else the select trace measured a no-op)`,
     (r.state.checked || []).includes('do-now'));
  // the verdicts — the snap/slide/jump property, rank-1 (frame-rate-free)
  ok(`OPEN snaps under the active kind (0 intermediate positions, no tween) [${mode}]`, openMid === 0);
  if (rm) {
    ok(`SELECT jumps with no intermediates under reduced-motion (0 mid-positions) [${mode}]`, selMid === 0);
  } else {
    ok(`SELECT slides through intermediates under motion (≥1 mid-position) [${mode}]`, selMid >= 1);
  }
}

ok('no page errors', errs.length === 0);
await browser.close();
finish();
