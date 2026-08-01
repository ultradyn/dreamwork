/* posture — #445 three-axis posture controls on the dashboard.

   Contract under test:
   - section exists with pace (3), asking (4), delegation stepper
   - asking is NOT compressed to three — near-auto and auto both present
   - 10s shared arm: click a stop → countdown text + bar drain (sampled
     mid-arm); reduced motion hides the bar, keeps the text + same apply
   - only final POST writes `.dreamwork/posture` + one events line;
     identical final is silent
   - re-selecting the committed triple cancels the arm (no POST)
   - hard refresh follows the authoritative file when no pending
   - hover description never POSTs / arms
   - #488: source chip sits beside the Posture heading (same row geometry)
   - #488: hover desc reserves layout — #parm top unchanged open vs closed

   usage: node posture.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, readFileSync, existsSync, writeFileSync, rmSync, cpSync } from 'node:fs';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
/* #475/#461: posture starts its OWN watch.py for a scratch target, so it
   must take a free port and IGNORE argv[3]. The `guards` recipe always passes
   {{port}} (its own shared server's port) to every guard, and this guard
   `spawn`s watch.py on that same port — which dies "address in use" silently,
   leaving the guard grading the recipe's server (a DIFFERENT target). The
   arm bar's drain then samples the OTHER target's page (its posture section is
   inert) and the POST writes the OTHER target's posture file, so the file the
   guard opens here is empty. The five cascading failures (mid-frames=0, file
   not written, three axis checks) are all this one port collision — verified
   by a controlled collision (file="") and by a clean solo run (32/32 PASS,
   mid-frames=77). The `await freePort()` idiom is the #461 fix staleremedy,
   reviewdraft, identity and friends already use. */
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'scratch target on / — posture chips, arm drain sample, POST once, ' +
          'idempotent re-post, reduced-motion text path, hover no side effect, ' +
          'source-chip beside heading, desc open/closed layout parity',
  traceWindow: 'arm drain sampled ~2.5s of the 10s (between() on bar width); ' +
               'full arm wait once for commit; reduced-motion branch separate; ' +
               'reflow is two bounding-box snapshots (idle vs open), not motion',
});

/* between(vals, first, last) — transitions.md: at least one frame STRICTLY
   between the two ends, ~3% deadband. End-state alone cannot fail on a snap. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}

function fileText(path) {
  if (!existsSync(path)) return null;
  return readFileSync(path, 'utf8');
}
function postureLines(logPath) {
  if (!existsSync(logPath)) return [];
  return readFileSync(logPath, 'utf8').split('\n').filter(l => l.includes('posture'));
}

// Own target — shared fixture must not carry a leftover posture file.
const dir = join(OUT, 'target');
rmSync(dir, { recursive: true, force: true });
cpSync('dev/capture/fixture', dir, { recursive: true });
const server = await serveVerified(dir, PORT);   // #428/#461: poll+identity, no fixed sleep
const stop = () => { try { server.kill(); } catch (e) {} };
process.on('exit', stop);

const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await waitFor(p, '#posture');   // #428 render readiness (the section present() checks next)

if (!(await present(p, '#posture', 'posture section'))) {
  await br.close();
  finish();
  process.exit(1);
}

// ── structure: axes and stop counts derived at runtime ──────────────────
const struct = await p.evaluate(() => {
  const pace = [...document.querySelectorAll(
    '.paxis-chips[data-axis="pace"] .pchip')].map(b => b.dataset.stop);
  const asking = [...document.querySelectorAll(
    '.paxis-chips[data-axis="asking"] .pchip')].map(b => b.dataset.stop);
  const step = {
    dec: !!document.getElementById('pstepdec'),
    inc: !!document.getElementById('pstepinc'),
    val: document.getElementById('pstepval')?.textContent,
    label: document.getElementById('psteplabel')?.textContent,
  };
  const src = document.getElementById('posture-src')?.textContent || '';
  return { pace, asking, step, src };
});
notes.push('struct: ' + JSON.stringify(struct));
// Precondition counts on the OK row — a silent zero would look like coverage.
ok(`pace chips present: ${struct.pace.length} (want 3)`,
   struct.pace.length === 3);
ok(`asking chips present: ${struct.asking.length} (want 4 — asymmetry)`,
   struct.asking.length === 4);
ok('asking includes near-auto and auto (not compressed to three)',
   struct.asking.includes('near-auto') && struct.asking.includes('auto'));
ok('pace includes idle, steady, hot',
   ['idle', 'steady', 'hot'].every(s => struct.pace.includes(s)));
ok('delegation stepper present with value + label',
   struct.step.dec && struct.step.inc
   && struct.step.val != null && !!struct.step.label);
ok('ambient slot (no override file) shows the remind button (#551)',
   /remind/i.test(struct.src));

// ── #646 + #580 subagent policy: explicit write/reset + quiet cycling ───
const policyPath = join(dir, '.dreamwork', 'subagent-policy');
const policyInitial = await p.evaluate(() => {
  const sec = document.getElementById('spolicy');
  const field = document.getElementById('spolicy-field');
  const save = document.getElementById('spolicy-save');
  const reset = document.getElementById('spolicy-reset');
  const r = sec && sec.getBoundingClientRect();
  return {
    visible: !!(r && r.width > 20 && r.height > 20),
    placeholder: field?.placeholder || '',
    labelledBy: field?.getAttribute('aria-labelledby') || '',
    label: document.getElementById('spolicy-lab')?.textContent || '',
    save: !!save, reset: !!reset, resetDisabled: !!reset?.disabled,
  };
});
notes.push('subagent policy initial: ' + JSON.stringify(policyInitial));
ok('subagent policy control is visible', policyInitial.visible);
ok('policy field has a visible accessible label',
   policyInitial.labelledBy === 'spolicy-lab'
   && /subagent policy/i.test(policyInitial.label));
ok('explicit save + reset exist; reset starts disabled without an override',
   policyInitial.save && policyInitial.reset && policyInitial.resetDisabled);
let placeholderCycled = false;
try {
  await p.waitForFunction(before => {
    const f = document.getElementById('spolicy-field');
    return !!f && !f.value && f.placeholder !== before;
  }, policyInitial.placeholder, { timeout: 12_000 });
  placeholderCycled = true;
} catch (e) {}
const placeholderAfter = await p.$eval('#spolicy-field', f => f.placeholder);
notes.push(`policy placeholder: ${policyInitial.placeholder} -> ${placeholderAfter}`);
ok('placeholder cycles on a quiet page with no data render',
   placeholderCycled && placeholderAfter !== policyInitial.placeholder);

const policyText = '  leading α\ntrailing space \n';
await p.fill('#spolicy-field', policyText);
await p.locator('#spolicy-field').blur();
await p.evaluate(() => {
  lastViewHtml = null;
  setContent(buildDashboard(data));
});
const draftAfterMorph = await p.$eval('#spolicy-field', f => f.value);
ok('blur + morph preserves the unsaved policy draft',
   draftAfterMorph === policyText);
ok('typing and blur do not write the policy file', !existsSync(policyPath));
await p.click('#spolicy-save');
await p.waitForFunction(() =>
  document.getElementById('spolicy-msg')?.textContent === 'policy saved');
const saveState = await p.evaluate(() => ({
  value: document.getElementById('spolicy-field')?.value,
  source: document.getElementById('spolicy-src')?.textContent,
  resetDisabled: document.getElementById('spolicy-reset')?.disabled,
}));
ok('save persists and reads back exact whitespace + non-ASCII bytes',
   fileText(policyPath) === policyText && saveState.value === policyText);
ok('save paints override and enables reset',
   saveState.source === 'override' && saveState.resetDisabled === false);
await p.click('#spolicy-reset');
await p.waitForFunction(() =>
  document.getElementById('spolicy-msg')?.textContent ===
    'policy reset to default');
const resetState = await p.evaluate(() => ({
  value: document.getElementById('spolicy-field')?.value,
  source: document.getElementById('spolicy-src')?.textContent,
  resetDisabled: document.getElementById('spolicy-reset')?.disabled,
}));
ok('reset deletes the file and returns the field to standing default',
   !existsSync(policyPath) && resetState.value === ''
   && resetState.source === 'standing default'
   && resetState.resetDisabled === true);

// ── #488 source chip beside the Posture heading ─────────────────────────
// Geometry, not DOM ancestry alone: same-row means |label.top − src.top|
// is well under one line. Precondition: both boxes have positive size.
const headGeo = await p.evaluate(() => {
  const head = document.querySelector('.posture-head');
  const lab = head && head.querySelector('.label');
  const src = document.getElementById('posture-src');
  const axes = document.querySelector('.posture-axes');
  if (!head || !lab || !src || !axes) return null;
  const lr = lab.getBoundingClientRect();
  const sr = src.getBoundingClientRect();
  const ar = axes.getBoundingClientRect();
  return {
    inHead: head.contains(src),
    labTop: lr.top, srcTop: sr.top,
    labH: lr.height, srcH: sr.height,
    srcBottom: sr.bottom, axesTop: ar.top,
    topDelta: Math.abs(lr.top - sr.top),
  };
});
notes.push('head geo: ' + JSON.stringify(headGeo));
ok('source note lives inside .posture-head',
   !!headGeo && headGeo.inHead);
ok(`source note shares the heading row (Δtop=${headGeo ? headGeo.topDelta.toFixed(1) : '?'}px, floor < line height)`,
   !!headGeo && headGeo.labH > 4 && headGeo.srcH > 4
   && headGeo.topDelta < headGeo.labH * 0.75);
ok('source note sits above the axes block',
   !!headGeo && headGeo.srcBottom <= headGeo.axesTop + 1);

// ── hover description: zero side effects + no reflow (#488) ─────────────
const posts = [];
ctx.on('request', req => {
  if (req.method() === 'POST' && req.url().includes('/posture')) {
    let body = null;
    try { body = req.postDataJSON(); } catch (e) { body = req.postData(); }
    posts.push({ t: Date.now(), body });
  }
});
const logPath = join(dir, '.dreamwork', 'watch-events.log');
const filePath = join(dir, '.dreamwork', 'posture');
const linesBeforeHover = postureLines(logPath).length;
const fileBeforeHover = fileText(filePath);

// Idle layout snapshot BEFORE hover — production line for reflow is the
// shell's permanent min-height (and the absence of display:none collapse).
// Measure RELATIVE to #posture: Playwright's hover scrolls the chip into
// view, so absolute page tops jump even when the card's internal layout
// is rock-steady (observed: 349px scroll, 0px section Δh).
const snapLayout = () => p.evaluate(() => {
  const shell = document.getElementById('pdesc');
  const parm = document.getElementById('parm');
  const sec = document.getElementById('posture');
  if (!shell || !parm || !sec) return null;
  const sr = shell.getBoundingClientRect();
  const pr = parm.getBoundingClientRect();
  const cr = sec.getBoundingClientRect();
  const cs = getComputedStyle(shell);
  return {
    shellH: sr.height,
    // offsets inside the section — scroll-invariant
    shellOff: sr.top - cr.top,
    parmOff: pr.top - cr.top,
    secH: cr.height,
    open: shell.classList.contains('open'),
    display: cs.display, opacity: cs.opacity,
    minH: cs.minHeight,
  };
});
const layoutIdle = await snapLayout();
notes.push('layout idle: ' + JSON.stringify(layoutIdle));
ok('pdesc reserves height when idle (shell > 0, display not none)',
   !!layoutIdle && layoutIdle.shellH > 8
   && layoutIdle.display !== 'none' && !layoutIdle.open);

await p.mouse.move(1, 1);
await p.hover('.paxis-chips[data-axis="asking"] .pchip[data-stop="near-auto"]');
try {
  await p.waitForFunction(() => {
    const shell = document.getElementById('pdesc');
    const text = document.getElementById('pdesc-text');
    return !!(shell && shell.classList.contains('open')
              && text && text.textContent.length > 8);
  }, null, { timeout: 2_000 });
} catch (e) {}
const desc = await p.evaluate(() => {
  const t = document.getElementById('pdesc-text');
  const shell = document.getElementById('pdesc');
  return {
    text: t ? t.textContent : '',
    open: shell && shell.classList.contains('open'),
  };
});
notes.push('hover desc: ' + JSON.stringify(desc));
ok('hover shows a non-empty description for near-auto',
   desc.open && desc.text.length > 8);
ok('hover did not POST /posture', posts.length === 0);
ok('hover left posture file bytes unchanged',
   fileText(filePath) === fileBeforeHover);
ok('hover left events log posture lines unchanged',
   postureLines(logPath).length === linesBeforeHover);

// Open layout — relative offsets must match idle.
const layoutOpen = await snapLayout();
notes.push('layout open: ' + JSON.stringify(layoutOpen));
// Precondition: open actually painted different text/state than idle.
ok('open layout precondition: shell is open and taller-or-equal idle reserve',
   !!layoutOpen && layoutOpen.open
   && layoutIdle && layoutOpen.shellH + 0.5 >= layoutIdle.shellH);
const parmDelta = Math.abs(
  (layoutOpen && layoutOpen.parmOff) - (layoutIdle && layoutIdle.parmOff));
const shellDelta = Math.abs(
  (layoutOpen && layoutOpen.shellH) - (layoutIdle && layoutIdle.shellH));
const secDelta = Math.abs(
  (layoutOpen && layoutOpen.secH) - (layoutIdle && layoutIdle.secH));
notes.push(`reflow deltas: parmOff=${parmDelta.toFixed(2)} shellH=${shellDelta.toFixed(2)} secH=${secDelta.toFixed(2)}`);
// Production line: `.pdesc { min-height:2.6em }` + no display:none. If the
// shell collapsed when idle, parmOff would jump by ~shellH when open.
ok(`hover does not reflow #parm inside card (Δoff=${parmDelta.toFixed(2)}px, want ≤1)`,
   parmDelta <= 1);
ok(`hover does not grow/shrink #pdesc (Δh=${shellDelta.toFixed(2)}px, want ≤1)`,
   shellDelta <= 1);
ok(`hover does not grow/shrink #posture (Δh=${secDelta.toFixed(2)}px, want ≤1)`,
   secDelta <= 1);

// ── arm + intermediate progress (normal motion) ─────────────────────────
// Click a different pace stop so we arm away from the derived default.
await p.click('.paxis-chips[data-axis="pace"] .pchip[data-stop="steady"]');
await sleep(200);

/* The drain is a 10s `width` CSS transition on #pbarfill (watch.py
   `.pbarfill { transition:width 10s linear }`). width transitions repaint on
   the MAIN thread, so under concurrent-guard load the main thread stalls, the
   transition stops repainting, and the rAF sampler reads the SAME width frame
   after frame — mid-frames reads 0 over a perfect drain. That is the #442
   compositor/main-thread-starvation gap, and the load-independent snap
   detector is `transitionstart`: it fires iff the browser registered and began
   a width transition for the bar, however few frames the sampler caught. The
   assertion is the #442 shape — `ran || mid >= 1` — so a real drain passes
   either way (the event fired, or the trace caught it part-way), and a snap
   (transition removed from CSS) fails both. (#475.) */
const armSample = await p.evaluate(() => {
  const fill = document.getElementById('pbarfill');
  const count = document.getElementById('pcount');
  const bar = document.getElementById('pbar');
  const widths = [];
  const events = [];
  let ranWidth = false;
  const onT = e => {
    if (e.propertyName !== 'width') return;
    const t = e.target;
    if (t && t.id === 'pbarfill') {
      events.push({ type: e.type, t: Math.round(performance.now() * 1000) / 1000 });
      if (e.type === 'transitionstart') ranWidth = true;
    }
  };
  document.addEventListener('transitionrun', onT, true);
  document.addEventListener('transitionstart', onT, true);
  document.addEventListener('transitionend', onT, true);
  return new Promise(resolve => {
    const t0 = performance.now();
    const tick = () => {
      if (fill) widths.push(parseFloat(getComputedStyle(fill).width) || 0);
      if (performance.now() - t0 < 2500) requestAnimationFrame(tick);
      else resolve({
        widths,
        ranWidth,
        events,
        count: count ? count.textContent : '',
        barHidden: bar ? bar.hidden : true,
        first: widths[0],
        last: widths[widths.length - 1],
      });
    };
    requestAnimationFrame(tick);
  });
});
notes.push('arm sample: first=' + armSample.first + ' last=' + armSample.last
  + ' n=' + armSample.widths.length + ' ranWidth=' + armSample.ranWidth
  + ' widthEvents=' + JSON.stringify(armSample.events) + ' count=' + armSample.count);

// Precondition: bar is visible and has a measurable span.
const span = Math.abs((armSample.first || 0) - (armSample.last || 0));
ok(`arm bar span measured ${span.toFixed(1)}px (floor 20)`,
   !armSample.barHidden && span >= 20);
const mid = between(armSample.widths, armSample.first, armSample.last);
ok(`arm bar drain visited mid frames: ${mid} (between())` +
   ` · transitionstart=${armSample.ranWidth}`,
   armSample.ranWidth || mid >= 1);
ok('arm countdown text names the pending pace',
   /arms in \d+s/.test(armSample.count) && /steady/.test(armSample.count));
ok('no POST yet during the arm', posts.length === 0);

// Also pick asking=inform so the final triple is distinct on all axes we care
// about — and so the commit is not "just pace".
await p.click('.paxis-chips[data-axis="asking"] .pchip[data-stop="inform"]');
await sleep(150);
// Bump delegation once so the integer is also intentional.
await p.click('#pstepinc');
await sleep(150);

// Wait out the remaining arm (reset on each pick → full ~10s from last click).
await sleep(10500);

// Poll for the POST / file.
let landed = false;
for (let i = 0; i < 40; i++) {
  if (posts.length >= 1 && existsSync(filePath)) { landed = true; break; }
  await sleep(250);
}
notes.push('posts after arm: ' + JSON.stringify(posts));
ok('exactly one POST /posture after the arm', posts.length === 1);
ok('posture file written', existsSync(filePath));
const written = fileText(filePath) || '';
notes.push('file: ' + JSON.stringify(written));
ok('file carries pace: steady', /pace:\s*steady/.test(written));
ok('file carries asking: inform', /asking:\s*inform/.test(written));
ok('file carries a non-negative delegation integer',
   /delegation:\s*\d+/.test(written));
const linesAfter = postureLines(logPath);
ok(`events log has exactly one posture line (got ${linesAfter.length})`,
   linesAfter.length === 1);
ok('events line names the three axes',
   /pace=steady/.test(linesAfter[0] || '')
   && /asking=inform/.test(linesAfter[0] || ''));

// Idempotent re-arm of the same triple: cancel path, no second POST.
const nPosts = posts.length;
await p.click('.paxis-chips[data-axis="pace"] .pchip[data-stop="steady"]');
await sleep(300);
const cancelled = await p.evaluate(() => {
  const count = document.getElementById('pcount');
  const bar = document.getElementById('pbar');
  return {
    count: count ? count.textContent : '',
    barHidden: bar ? bar.hidden : true,
  };
});
notes.push('reselect cancel: ' + JSON.stringify(cancelled));
ok('re-selecting committed pace cancels arm (no countdown)',
   !/arms in/.test(cancelled.count));
ok('no additional POST on cancel', posts.length === nPosts);

// ── reduced motion: bar hidden, text still counts, same apply time ──────
const ctxRm = await br.newContext({
  viewport: { width: 1100, height: 900 },
  reducedMotion: 'reduce',
});
const pRm = await ctxRm.newPage();
pRm.on('pageerror', e => errs.push('rm: ' + e));
const postsRm = [];
ctxRm.on('request', req => {
  if (req.method() === 'POST' && req.url().includes('/posture'))
    postsRm.push(1);
});
await pRm.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(600);
await pRm.click('.paxis-chips[data-axis="pace"] .pchip[data-stop="hot"]');
await sleep(300);
const rmArm = await pRm.evaluate(() => {
  const bar = document.getElementById('pbar');
  const count = document.getElementById('pcount');
  const cs = bar ? getComputedStyle(bar) : null;
  return {
    display: cs ? cs.display : null,
    hidden: bar ? bar.hidden : true,
    count: count ? count.textContent : '',
  };
});
notes.push('rm arm: ' + JSON.stringify(rmArm));
ok('reduced motion hides the arm bar (display:none or hidden)',
   rmArm.hidden || rmArm.display === 'none');
ok('reduced motion keeps the countdown text',
   /arms in \d+s/.test(rmArm.count) && /hot/.test(rmArm.count));
ok('reduced motion did not POST immediately', postsRm.length === 0);

// Cancel the rm arm so we do not leave a pending write for other guards.
await pRm.click('.paxis-chips[data-axis="pace"] .pchip[data-stop="steady"]');
await sleep(200);
// steady is already committed — should cancel if we land on file state;
// if not, re-click the committed pace from the file.
const committedPace = (fileText(filePath) || '').match(/pace:\s*(\S+)/);
if (committedPace) {
  await pRm.click(
    `.paxis-chips[data-axis="pace"] .pchip[data-stop="${committedPace[1]}"]`);
  await sleep(200);
}
await ctxRm.close();

// ── hard refresh follows the file ───────────────────────────────────────
const p2 = await ctx.newPage();
await p2.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(600);
const afterReload = await p2.evaluate(() => {
  const on = [...document.querySelectorAll(
    '.paxis-chips[data-axis="pace"] .pchip.on')].map(b => b.dataset.stop);
  const ask = [...document.querySelectorAll(
    '.paxis-chips[data-axis="asking"] .pchip.on')].map(b => b.dataset.stop);
  const src = document.getElementById('posture-src')?.textContent || '';
  return { on, ask, src };
});
notes.push('reload: ' + JSON.stringify(afterReload));
ok('reload selects pace=steady from the file',
   afterReload.on.includes('steady'));
ok('reload selects asking=inform from the file',
   afterReload.ask.includes('inform'));
ok('reload slot (override file) shows the remind button (#551)',
   /remind/i.test(afterReload.src));

await br.close();
stop();
finish();
