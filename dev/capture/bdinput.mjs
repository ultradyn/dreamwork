/* bdinput — #523 + #524: burndown limit input keeps focus across ticks;
   [-]/[+] steppers with hold-to-repeat, including across a data tick.

   #523: under the old innerHTML swap a focused .bdlimit-in was destroyed;
   snapshotViewInputs / restoreViewInputs carried id + value + selection.
   #505 p2 retired that pair: the node is now KEPT by id via morphdom, and
   reconcileGuard's focus-gated value-stamp keeps mid-edit text from being
   clobbered to the server value (caret/focus/scroll ride the kept node).
   Typed text still wins over fresh markup.

   #524: − / + buttons flank the input; click steps; hold auto-repeats
   (module-level interval so a re-render mid-hold does not kill it).

   OWN TARGET + OWN EPHEMERAL PORT — same reason as burndown.mjs: the limit
   control only appears when totalN > 28, so the ledger history is planted
   long enough that hourly yields more than 28 buckets. Every number the
   assertions compare is read from the page / data.json at runtime.

   Preconditions derived at runtime (born-hollow rule):
     - limit input exists (totalN > 28, hourly)
     - each forced tick really ran (__dwViewRenderGen advanced; under #505
       the input node is KEPT, so "replaced" is no longer required)
     - hold produces ≥2 value changes; hold-across-tick keeps changing after
       the swap

   production lines each green depends on (for red-proof injection):
     (a)(b) kept-node reconciliation by id + reconcileGuard value-stamp
            (document.activeElement === fromEl → toEl.value = fromEl.value)
     (a)    the value-stamp in reconcileGuard (typed wins; caret is not an
            attribute and rides the kept node)
     (c)    bdStepNudge / .bdlimit-step markup
     (d)    bdStepHoldStart interval arm
     (e)    pointercancel keep-hold when target.isConnected === false
            (or kept node mid-hold under #505)

   usage: node bdinput.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { createServer } from 'node:http';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeReporter } from './report.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const { ok, declare, finish, checks, notes, errs } = makeReporter();
const nameThrow = (kind, e) => {
  const msg = e && e.stack ? e.stack : String(e);
  errs.push(`${kind}: ${msg}`);
  checks.push(`FAIL the guard threw before finishing its checks: ${String(e)}`);
};
process.on('uncaughtException', e => nameThrow('uncaughtException', e));
process.on('unhandledRejection', e => nameThrow('unhandledRejection', e));

/* ── #548: bind the cap to the production constant, not the page's own max ──
   The OLD guard derived CAP from `pre.max` (the rendered input's own max),
   so it was self-consistent at ANY value of BURN_LIMIT_CAP — the
   coordinator's red-run reverted 256→168 and the guard PASSED (a green
   red-run is a finding). The rendered `max` is templated on the constant
   (`max="${BURN_LIMIT_CAP}"`), so it tracks whatever the working tree says —
   proven directly: max=256 normally, 168 under 256→168.
   Binding pre.max to a value read from the SAME working-tree file is
   therefore circular (both sides move together); the binding instead anchors
   on the COMMITTED production constant (HEAD:client/views.js), the source of
   truth a working-tree drift diverges from. The working-tree read stays the
   rename-detection precondition: a renamed constant → zero matches → a named
   extraction FAIL, not an obscure crash.

   #397: the constant used to live in watch.py's VIEWS_JS literal; the client
   is files now, so both reads follow it to `client/views.js`. Reading
   watch.py here would find zero matches and fail the extraction check for a
   reason that has nothing to do with the cap.

   production lines each green depends on (for red-proof injection):
     (#548 bind)   client/views.js `const BURN_LIMIT_CAP = 256;` (the constant)
                   client/views.js `max="${BURN_LIMIT_CAP}"`     (the render)
     (#548 rename) the const-declaration line itself (renamed → 0 matches) */
const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = resolve(HERE, '..', '..');
const CAP_SRC = join(SKILL_ROOT, 'client', 'views.js');
const CAP_SRC_REL = 'client/views.js';
const CAP_RE = /const BURN_LIMIT_CAP = (\d+);/g;

/* EXPECTED_CAP — the recorded value of the production constant, pinned as a
   literal so a deliberate change to the cap must update it IN THE SAME COMMIT
   (the #549 golden-vector discipline: a constant whose value matters gets a
   recorded literal with provenance, and an accidental or unaccompanied drift
   fails here). Provenance:
     · recorded 2026-07-30, value 256
     · `const BURN_LIMIT_CAP = 256;` — in watch.py's VIEWS_JS when recorded,
       in `client/views.js` since #397 extracted the client
     · the same file renders it into the input's `max`
   This is the anchor for a COMMITTED drift: if someone changes the constant
   and commits it, HEAD and the working tree would agree and the working-tree/
   committed binding could not fail — so the committed constant is also pinned
   to this literal. An intentional cap change edits EXPECTED_CAP here AND the
   production constant in the same commit; anything else is a red. */
const EXPECTED_CAP = 256;
const extractCap = (src, where) => {
  const ms = [...src.matchAll(CAP_RE)];
  // Precondition assertion: the whole binding depends on exactly one
  // assignment. Zero (renamed/removed) or two (a second appeared) are both
  // guard failures, loudly.
  ok(`extraction (#548): BURN_LIMIT_CAP defined exactly once in ${where} ` +
     `(saw ${ms.length})`, ms.length === 1);
  return ms.length === 1 ? Number(ms[0][1]) : null;
};
const CAP_WT = extractCap(readFileSync(CAP_SRC, 'utf8'),
                          `working-tree ${CAP_SRC_REL}`);
const CAP_COMMITTED = extractCap(
  execFileSync('git', ['show', `HEAD:${CAP_SRC_REL}`],
               { cwd: SKILL_ROOT, encoding: 'utf8' }),
  `committed (HEAD) ${CAP_SRC_REL}`);
if (CAP_WT == null || CAP_COMMITTED == null) {
  finish();
  process.exit(1);
}

/* #548 / #549 — pin the committed constant to the recorded literal. The
   working-tree↔committed binding catches an uncommitted drift (red #1: a
   working-tree revert renders a different max than HEAD). But a COMMITTED
   drift (constant changed AND committed) would leave HEAD and the working
   tree agreeing, so neither side of that binding could fail. The recorded
   literal EXPECTED_CAP is the third leg: the committed constant must equal
   it, so a committed drift fails here unless EXPECTED_CAP was updated in the
   same commit (the golden-vector discipline). Derives the committed value at
   runtime (CAP_COMMITTED, from HEAD:watch.py) so this is not a literal
   compared to itself. */
ok(`recorded (#548): committed BURN_LIMIT_CAP equals the recorded literal ` +
   `(committed ${CAP_COMMITTED}, recorded ${EXPECTED_CAP})`,
   CAP_COMMITTED === EXPECTED_CAP);
if (CAP_COMMITTED !== EXPECTED_CAP) {
  finish();
  process.exit(1);
}

declare({
  drives: 'own-server planted ledger (hourly, >28 buckets); focus+type and ' +
          'select-range on #bdlimit-in across forced tick(); click −/+; ' +
          'hold + (pointerdown) for repeats; hold + across a mid-hold tick',
  traceWindow: 'tick survival samples after setLiveContent (node identity); ' +
               'hold driven deterministically via page.clock (400ms delay + ' +
               '80ms repeats, runFor); hold-across-tick forces one /command + tick mid-hold'
});

// ── planted ledger long enough for the #499 control ───────────────────────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const T0 = Math.floor(Date.now() / 1000) - 6 * 3600;
const git = (args, at) => execFileSync('git', ['-C', DIR, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x',
         GIT_AUTHOR_DATE: `@${at} +0000`, GIT_COMMITTER_DATE: `@${at} +0000` },
}).toString().trim();
const entry = i => `- **#${i}** — task ${i} · P2 · task\n`;
const ledger = (open, done) =>
  `# Task ledger\n\nNext id: **99**\n\n## Open\n\n${open.map(entry).join('')}` +
  `\n## Recently landed\n\n${done.map(i => `**#${i}** landed (aaa111${i}).`).join(' ')}\n`;
const commit = (open, done, at, note) => {
  writeFileSync(join(DIR, '.dreamwork', 'tasks.md'),
    ledger(open, done) + (note ? `\n<!-- ${note} -->\n` : ''));
  git(['add', '.dreamwork/tasks.md'], at);
  git(['commit', '-q', '-m', `ledger at ${at}`], at);
};
git(['init', '-q'], T0);
commit([1, 2, 3], [], T0, 'seed');
// ~40h of hourly commits before T0 → totalN > 28 under hourly step
for (let h = 40; h >= 1; h--) {
  commit([6, 7, 8, 9], [4, 5], T0 - h * 3600, `span ${h}`);
}

const BASE = `http://127.0.0.1:${PORT}`;
const srv = await serveVerified(DIR, PORT);   // #428/#461: poll+identity, no fixed sleep
process.on('exit', () => { try { srv.kill(); } catch (e) {} });

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1280, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(BASE + '/', { waitUntil: 'networkidle' });
await waitFor(p, '.bd');   // #428 render readiness (the burndown panel)

// Force hourly so the extended history yields >28 buckets (control present).
await p.evaluate(async () => {
  for (let i = 0; i < 8; i++) {
    if ((data && data.burndown && data.burndown.step) === 3600) return;
    const b = document.querySelector('.bdstep');
    if (!b) return;
    b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 450));
  }
});
await sleep(700);

const pre = await p.evaluate(() => {
  const inp = document.getElementById('bdlimit-in');
  const minus = document.querySelector('.bdlimit-step[data-dir="-1"]');
  const plus = document.querySelector('.bdlimit-step[data-dir="1"]');
  const totalN = ((data && data.burndown && data.burndown.buckets) || []).length;
  const step = data && data.burndown && data.burndown.step;
  return {
    hasInp: !!inp,
    hasMinus: !!minus,
    hasPlus: !!plus,
    id: inp ? inp.id : null,
    value: inp ? inp.value : null,
    min: inp ? inp.min : null,
    max: inp ? inp.max : null,
    totalN, step,
  };
});
notes.push(`pre: ${JSON.stringify(pre)}`);
ok('precondition: hourly step with more than 28 buckets (control present)',
   pre.step === 3600 && pre.totalN > 28);
ok('precondition: #bdlimit-in exists with a stable id',
   pre.hasInp && pre.id === 'bdlimit-in');
ok('precondition: − and + steppers flank the input',
   pre.hasMinus && pre.hasPlus);
ok('precondition: input min/max match the panel contract (0..cap)',
   pre.min === '0' && Number(pre.max) >= 28);

if (!pre.hasInp || !pre.hasMinus || !pre.hasPlus || pre.totalN <= 28) {
  await p.screenshot({ path: join(OUT, 'fail-pre.png'), fullPage: true });
  await br.close();
  try { srv.kill(); } catch (e) {}
  finish();
  process.exit(1);
}

const CAP = CAP_WT;   // #548: the page's actual cap (== committed under a clean tree)

/* #548 — the binding the guard lacked. The rendered max must equal the
   COMMITTED production constant, not the page's own max (circular: both
   derive from the same working-tree file) nor the working-tree value (a
   working-tree drift IS what the page renders, so it could never catch
   itself). A constant reverted in the working tree (256→168) makes the live
   page disagree with the committed source of truth — exactly the finding the
   old guard read as green. Derives both comparands at runtime (pre.max from
   the page, CAP_COMMITTED from HEAD:watch.py) so the assertion is not a
   literal tuned to today's fixture. */
ok(`binding (#548): rendered input max equals the production BURN_LIMIT_CAP ` +
   `constant (rendered ${pre.max}, committed ${CAP_COMMITTED})`,
   Number(pre.max) === CAP_COMMITTED);
if (Number(pre.max) !== CAP_COMMITTED) {
  try { await p.screenshot({ path: join(OUT, 'fail-cap-binding.png'), fullPage: true }); } catch (e) {}
  await br.close();
  try { srv.kill(); } catch (e) {}
  finish();
  process.exit(1);
}

/* ── helpers ──────────────────────────────────────────────────────────── */
/* Drive the same snapshot → setLiveContent → restore path as tick(), but
   snapshot FIRST (before any await) so a concurrent poll cannot steal focus
   between "he is typing" and the capture. Production tick also snapshots
   after its data fetch — #523 no longer has its own snapshot/restore pair
   (#505 p2): the focused input is kept by id and value-stamped in the morph,
   so the load-bearing line is the kept node, not a restore call. */
const forceTick = async () => {
  const r = await p.evaluate(async () => {
    const before = document.getElementById('bdlimit-in');
    const beforeId = before ? before.id : null;
    const renderGen0 = window.__dwViewRenderGen || 0;
    // Force morph path even when dashboard markup is byte-identical.
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    // SNAPSHOT WHILE FOCUS STILL HOLDS — no await above this line.
    const kept = snapshotCardState();
    const askKept = snapshotAskState();
    const reviewFrame = snapshotReviewFrame();
    const beforeCards = snapshotCards();
    const bdHover = snapshotBdHover();
    const was = burnKey(data);
    const genBefore = document.getElementById('view')
      && document.getElementById('view').innerHTML.length;

    await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'bdinput tick ' + Date.now() }),
    });
    // Mark mtime current + hold the poller so a concurrent auto-tick cannot
    // re-swap after our restore and steal focus before the guard samples.
    try {
      const mt = parseMtime(await (await fetch('/mtime')).text());
      if (mt && mt.mtime != null) lastMtime = mt.mtime;
    } catch (e) {}
    holdRerenderUntil = Date.now() + 8000;

    // Use the production delta seam. Calling dataJsonUrl() directly can
    // return a {changed, removed} envelope, which is not a data document.
    const next = await fetchDataResponse();
    if (next) setData(next);
    const html = await buildCurrent();
    setLiveContent(html);
    restoreBdHover(bdHover);
    restoreReviewFrame(reviewFrame);
    restoreCardState(kept);
    // #523: no restoreViewInputs — kept by id + value-stamped in the morph.
    restoreAskState(askKept);
    bindAskDraft();
    regroupCards(beforeCards);

    const after = document.getElementById('bdlimit-in');
    const advanced = (window.__dwViewRenderGen || 0) > renderGen0;
    // Sample INSIDE this turn — a later evaluate can lose the race to
    // anything else that focuses (the failure mode that made (a) red
    // while (b) green: identical restore, different inter-evaluate delay).
    return {
      replaced: !!(before && after && before !== after),
      advanced,
      // #505: gen advanced is vacuity; replaced is legacy under innerHTML
      tickWorked: advanced || !!(before && after && before !== after),
      beforeId,
      afterId: after ? after.id : null,
      genBefore,
      genAfter: document.getElementById('view')
        && document.getElementById('view').innerHTML.length,
      burnChanged: burnKey(data) !== was,
      after: after ? {
        value: after.value,
        start: after.selectionStart,
        end: after.selectionEnd,
        focused: document.activeElement === after,
        id: after.id,
      } : null,
    };
  });
  return r;
};

/* ── (a) focus + type across a data tick ──────────────────────────────── */
{
  const typed = '42';
  // Type via the real keyboard so the value is his, not applyBurnLimit's;
  // then re-assert focus+caret in one evaluate so the snapshot in forceTick
  // cannot race a blur between separate round-trips.
  await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    inp.focus();
    inp.value = '';
  });
  await p.keyboard.type(typed);
  await p.keyboard.press('ArrowLeft');
  const before = await p.evaluate(t => {
    const inp = document.getElementById('bdlimit-in');
    // re-seat caret explicitly (ArrowLeft is the gesture; this pins the
    // precondition so a green cannot be "typed but caret was already lost")
    if (inp && document.activeElement === inp) {
      try { inp.setSelectionRange(t.length - 1, t.length - 1); } catch (e) {}
    }
    return {
      value: inp ? inp.value : null,
      start: inp ? inp.selectionStart : -1,
      end: inp ? inp.selectionEnd : -1,
      focused: !!inp && document.activeElement === inp,
    };
  }, typed);
  ok('precondition (a): input is focused with typed value and mid-string caret',
     before.focused && before.value === typed &&
     before.start === typed.length - 1 && before.end === before.start);
  notes.push(`(a) before tick: ${JSON.stringify(before)}`);

  const tickA = await forceTick();
  // Copy primitives immediately — do not re-read the page.
  const aVal = tickA && tickA.after && tickA.after.value;
  const aStart = tickA && tickA.after && tickA.after.start;
  const aEnd = tickA && tickA.after && tickA.after.end;
  const aFocus = tickA && tickA.after && tickA.after.focused;
  notes.push(`(a) tick worked=${!!tickA.tickWorked} replaced=${!!tickA.replaced} ` +
             `advanced=${!!tickA.advanced} ` +
             `after={value:${aVal},start:${aStart},end:${aEnd},focused:${aFocus}}`);
  ok('(a) precondition: the tick really ran (render gen advanced or node replaced)',
     !!tickA.tickWorked);
  ok('(a) typed value survives the data tick (typed text wins over render)',
     aVal === typed);
  ok('(a) focus stays in the limit input across the tick',
     aFocus === true);
  ok('(a) caret position survives the tick',
     aStart === typed.length - 1 && aEnd === aStart);
}

/* ── (b) selection range across a data tick ───────────────────────────── */
{
  await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    // a known value with room for a range that is not the whole field
    inp.focus();
    inp.value = '128';
    inp.setSelectionRange(1, 3);   // "28"
  });
  const before = await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    return {
      value: inp.value, start: inp.selectionStart, end: inp.selectionEnd,
      focused: document.activeElement === inp,
    };
  });
  ok('precondition (b): a non-empty selection range is active',
     before.focused && before.start === 1 && before.end === 3 &&
     before.value === '128');
  const tickB = await forceTick();
  ok('(b) precondition: the tick really ran (render gen advanced or node replaced)',
     !!tickB.tickWorked);
  const after = tickB.after || {};
  notes.push(`(b) after: ${JSON.stringify(after)}`);
  ok('(b) selection range survives the data tick',
     after.value === '128' && after.start === 1 && after.end === 3);
  ok('(b) focus survives with the selection',
     after.focused === true);
}

/* ── (c) click − / + and clamp at min/max ─────────────────────────────── */
{
  // Start from a mid value derived from the input's own max (not a literal
  // that expires when the cap changes).
  const mid = Math.min(20, Math.max(2, CAP - 10));
  await p.evaluate(v => {
    // clear any leaked hold / suppress from earlier probes
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    if (typeof _bdStepSuppressClick !== 'undefined') _bdStepSuppressClick = false;
    const inp = document.getElementById('bdlimit-in');
    inp.value = String(v);
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  }, mid);
  await sleep(600);
  const base = await p.evaluate(() => ({
    value: document.getElementById('bdlimit-in').value,
    display: displayBurnLimitValue(),
  }));
  ok('precondition (c): mid value committed before steppers',
     base.value === String(mid) && base.display === mid);

  // Blur + hold the poller so a stale view-input restore cannot overwrite
  // a stepped preference mid-assert.
  await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    if (inp) inp.blur();
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    _bdStepSuppressClick = false;
    holdRerenderUntil = Date.now() + 20000;
  });

  // One real pointer tap (down+up) on the stepper — same path as (d)/(e).
  const tap = async (dir) => {
    const sel = `.bdlimit-step[data-dir="${dir}"]`;
    const loc = p.locator(sel);
    await loc.scrollIntoViewIfNeeded();
    const box = await loc.boundingBox();
    if (!box) throw new Error('no hit target for ' + sel);
    await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await p.mouse.down();
    await p.mouse.up();
    // allow async rerenderBurnLimit to finish one paint
    await sleep(700);
  };

  await tap('1');
  const up = await p.evaluate(() => ({
    value: document.getElementById('bdlimit-in')?.value,
    display: displayBurnLimitValue(),
  }));
  notes.push(`(c) after +: ${JSON.stringify(up)}`);
  ok('(c) [+] increments the limit by one',
     up.display === mid + 1);

  await tap('-1');
  const down = await p.evaluate(() => ({
    value: document.getElementById('bdlimit-in')?.value,
    display: displayBurnLimitValue(),
  }));
  notes.push(`(c) after −: ${JSON.stringify(down)}`);
  ok('(c) [−] decrements the limit by one',
     down.display === mid);

  // clamp at max — step must not walk past the input's own max
  await p.evaluate(cap => {
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    burnLimitPref = cap;
    _burnLimitDidLoad = true;
    try { localStorage.setItem(burnLimitStorageKey(), String(cap)); } catch (e) {}
  }, CAP);
  await p.evaluate(async () => { await rerenderBurnLimit(); });
  await sleep(400);
  const beforeMax = await p.evaluate(() => displayBurnLimitValue());
  await tap('1');
  const atMax = await p.evaluate(() => displayBurnLimitValue());
  ok('precondition (c): max clamp starts at cap', beforeMax === CAP);
  ok('(c) [+] clamps at the input max (no walk past cap)',
     atMax === CAP);

  // clamp at min (0 = all)
  await p.evaluate(() => {
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    burnLimitPref = 0;
    _burnLimitDidLoad = true;
    try { localStorage.setItem(burnLimitStorageKey(), '0'); } catch (e) {}
  });
  await p.evaluate(async () => { await rerenderBurnLimit(); });
  await sleep(400);
  const beforeMin = await p.evaluate(() => displayBurnLimitValue());
  await tap('-1');
  const atMin = await p.evaluate(() => displayBurnLimitValue());
  ok('precondition (c): min clamp starts at 0', beforeMin === 0);
  ok('(c) [−] clamps at the input min (0)',
     atMin === 0);
  notes.push(`(c) mid=${mid} up=${JSON.stringify(up)} down=${JSON.stringify(down)} ` +
             `atMax=${atMax} atMin=${atMin} cap=${CAP}`);
}

/* ── (c2) TYPED values clamp at the same min/max (applyBurnLimit) ───────
   The merge gate's independent red found (c) binds only the STEPPER clamp:
   sabotaging applyBurnLimit's cap clamp produced no FAIL — the typed path
   the steppers were briefed to MATCH was unbound. A green red-run is a
   finding; this section is the fix. Same change-event idiom as (c)'s
   setup. */
{
  await p.evaluate(cap => {
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    const inp = document.getElementById('bdlimit-in');
    inp.value = String(cap + 50);
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  }, CAP);
  await sleep(600);
  const over = await p.evaluate(() => ({
    value: document.getElementById('bdlimit-in').value,
    display: displayBurnLimitValue(),
  }));
  notes.push(`(c2) typed ${CAP + 50} → ${JSON.stringify(over)}`);
  ok('(c2) a typed over-cap value clamps at the input max (applyBurnLimit)',
     over.display === CAP && over.value === String(CAP));

  await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    inp.value = '0';
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(600);
  const zero = await p.evaluate(() => displayBurnLimitValue());
  ok('(c2) a typed 0 keeps the all/max contract (stored 0)',
     zero === 0);
}

/* ── (d) hold [+] — at least 2 repeats after the initial step ───────────
   #532: the hold was sampled over 1100ms of wall-clock and asserted
   delta≥3. Under CPU contention headless Chromium throttles the
   setTimeout(400)/setInterval(80) timers, so a correct feature read
   delta<3 in 1/3 gate runs. Fixed with page.clock: install fakes the
   page's timers so runFor fires the 400ms delay and each 80ms repeat
   exactly as the production constants say — no wall-clock race, no
   throttling, no assertion loosened. The only timers in the hold path
   are bdStepHoldStart's; displayBurnLimitValue reads burnLimitPref
   synchronously, so value reads are instant regardless of re-render. */
{
  const startVal = 10;
  await p.evaluate(v => {
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    const inp = document.getElementById('bdlimit-in');
    inp.value = String(v);
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  }, startVal);
  await sleep(600);
  // Playwright real mouse hold — not a synthetic PointerEvent (isTrusted
  // paths and button defaults differ; the production listener is on the
  // real pointer sequence).
  const plus = p.locator('.bdlimit-step[data-dir="1"]');
  await plus.scrollIntoViewIfNeeded();
  const box = await plus.boundingBox();
  ok('precondition (d): [+] button has a hit target', !!box && box.width > 0);
  // page.clock: the only timers in the hold path are the production
  // setTimeout(400) delay and setInterval(80) repeat (bdStepHoldStart).
  // install fakes them so runFor fires at least as often as the constants
  // say — virtual time also advances with real time between calls, so
  // repeats may fire extra, never fewer. delta is always ≥ the runFor
  // minimum (7), comfortably above the ≥3 assertion. No wall-clock race,
  // no throttling under load, no assertion loosened.
  await p.clock.install();
  const vals = [];
  vals.push(await p.evaluate(() => displayBurnLimitValue()));
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.mouse.down();            // pointerdown → bdStepNudge(1) + setTimeout(400)
  await p.clock.runFor(400);       // fire the 400ms first-delay → interval arms
  for (let i = 0; i < 6; i++) {    // 6 × 80ms repeats — comfortably above ≥3
    await p.clock.runFor(80);
    vals.push(await p.evaluate(() => displayBurnLimitValue()));
  }
  await p.mouse.up();
  await p.clock.resume();          // real-time flow for the remaining sections
  const maxV = Math.max(...vals.filter(n => Number.isFinite(n)));
  const deltas = maxV - startVal;
  notes.push(`(d) hold samples=${JSON.stringify(vals)} delta=${deltas}`);
  ok('precondition (d): hold started from a value with headroom under cap',
     startVal + 5 < CAP);
  ok('(d) hold [+] fires at least 2 repeats (value rises by ≥3)',
     deltas >= 3);
}

/* ── (e) hold [+] ACROSS a forced data tick — repeat continues ──────────
   #532: same page.clock treatment as (d). The hold's timers are already
   faked from (d)'s install + resume; runFor drives them deterministically
   through the swap. The module-level interval survives the node swap
   (production claim) — value keeps rising after setLiveContent. */
{
  const startVal = 15;
  await p.evaluate(v => {
    if (typeof bdStepHoldStop === 'function') bdStepHoldStop();
    const inp = document.getElementById('bdlimit-in');
    inp.value = String(v);
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  }, startVal);
  await sleep(600);

  const plus = p.locator('.bdlimit-step[data-dir="1"]');
  await plus.scrollIntoViewIfNeeded();
  const box = await plus.boundingBox();
  ok('precondition (e): [+] hit target present for hold-across-tick',
     !!box && box.width > 0);

  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.mouse.down();            // pointerdown → first nudge (16), setTimeout(400)
  // Drive past the 400ms delay so the interval is armed, plus two repeats.
  await p.clock.runFor(400);        // fire the 400ms first-delay → interval arms
  await p.clock.runFor(80);         // one repeat → 17
  await p.clock.runFor(80);         // one repeat → 18
  const midHold = await p.evaluate(() => ({
    v: displayBurnLimitValue(),
    holding: !!_bdStepHold,
    node: !!document.getElementById('bdlimit-in'),
  }));
  // Force a node-replacing swap WHILE the mouse button is still down.
  // Snapshot does not need the limit input (focus is on the button); the
  // load-bearing claim is that the module-level interval keeps firing.
  const tickE = await p.evaluate(async () => {
    const nodeBefore = document.getElementById('bdlimit-in');
    const held = !!_bdStepHold;
    const renderGen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'bdinput hold-tick ' + Date.now() }),
    });
    const next = await fetchDataResponse();
    if (next) setData(next);
    const bdHover = snapshotBdHover();
    const html = await buildCurrent();
    setLiveContent(html);
    restoreBdHover(bdHover);
    // #523: no restoreViewInputs — kept by id + value-stamped (#505 p2).
    const nodeAfter = document.getElementById('bdlimit-in');
    const advanced = (window.__dwViewRenderGen || 0) > renderGen0;
    return {
      replaced: !!(nodeBefore && nodeAfter && nodeBefore !== nodeAfter),
      advanced,
      tickWorked: advanced || !!(nodeBefore && nodeAfter && nodeBefore !== nodeAfter),
      heldBefore: held,
      heldAfter: !!_bdStepHold,
      v: displayBurnLimitValue(),
    };
  });
  // Keep holding — drive more repeats after the swap (module-level interval
  // survives: value keeps rising despite the node replacement).
  const afterVals = [tickE.v];
  for (let i = 0; i < 3; i++) {
    await p.clock.runFor(80);
    afterVals.push(await p.evaluate(() => displayBurnLimitValue()));
  }
  await p.mouse.up();
  await p.clock.resume();
  const maxAfter = Math.max(...afterVals.filter(n => Number.isFinite(n)));
  notes.push(`(e) midHold=${JSON.stringify(midHold)} tickE=${JSON.stringify(tickE)} ` +
             `afterVals=${JSON.stringify(afterVals)} maxAfter=${maxAfter}`);
  ok('(e) precondition: tick mid-hold really ran (render gen advanced or node replaced)',
     !!tickE.tickWorked);
  ok('(e) precondition: hold had already stepped before the tick',
     midHold.v > startVal && midHold.holding);
  ok('(e) hold state survives the swap (module-level interval)',
     tickE.heldAfter === true);
  ok('(e) hold [+] continues after a data tick (value keeps rising)',
     maxAfter > tickE.v);
}

/* ── screenshots for the visual verdict (desktop + 390px) ─────────────── */
{
  // settle at a readable mid value with steppers at rest
  await p.evaluate(() => {
    const inp = document.getElementById('bdlimit-in');
    inp.value = '28';
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(600);
  // scroll the burndown into view for a tight crop feel (fullPage too)
  await p.evaluate(() => {
    const bd = document.querySelector('.bd');
    if (bd) bd.scrollIntoView({ block: 'center' });
  });
  await p.screenshot({ path: join(OUT, 'stepper-rest-desktop.png'), fullPage: false });

  // mid-hold: real mouse down while interval is running
  {
    const plus = p.locator('.bdlimit-step[data-dir="1"]');
    const box = await plus.boundingBox();
    if (box) {
      await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await p.mouse.down();
      await sleep(500);
    }
  }
  await p.screenshot({ path: join(OUT, 'stepper-hold-desktop.png'), fullPage: false });
  await p.mouse.up();
  await sleep(200);

  // mobile width
  await p.setViewportSize({ width: 390, height: 844 });
  await sleep(400);
  await p.evaluate(() => {
    const bd = document.querySelector('.bd');
    if (bd) bd.scrollIntoView({ block: 'center' });
  });
  await p.screenshot({ path: join(OUT, 'stepper-rest-390.png'), fullPage: false });
  {
    const plus = p.locator('.bdlimit-step[data-dir="1"]');
    const box = await plus.boundingBox();
    if (box) {
      await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await p.mouse.down();
      await sleep(500);
    }
  }
  await p.screenshot({ path: join(OUT, 'stepper-hold-390.png'), fullPage: false });
  await p.mouse.up();
}

await br.close();
try { srv.kill(); } catch (e) {}
finish();
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
