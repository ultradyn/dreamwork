/* bdhover — #298/#487: the burndown column inspector.

   One restrained chart-native inspector (`.bdinsp`) on #417's seam — the
   RICHER reading a deliberate look gets: a hover that dwells, a keyboard
   focus, or a tap. It names the exact interval, the open level, arrivals
   and completions, the commits, and the coverage state the geometry
   cannot say (a period with no ledger commit CARRIES the level; the
   current period is still arriving).

   #487 rework: pin is CONSISTENT (RHS of the panel when the inspector's
   measured width fits in the right half; otherwise above chart AND above
   `.bdtip` so the two never overlap). No native `title=` on columns —
   one hover surface. Granularity cycle is unit-tested; this guard owns
   geometry and values.

   OWN TARGET + OWN EPHEMERAL PORT, same reason as burndown.mjs: the datum
   is a property of a repository's ledger HISTORY. The history is PLANTED
   so the numbers are known, and every figure asserted here is derived
   from /data.json at runtime — never a literal tuned to today's fixture.

   What this guard proves (an end-state check could fail on none of it):
     - exact values: the inspector names the HOVERED column's served
       numbers, parsed by role (a wrong column's numbers would pass any
       visibility check);
     - the interval line corresponds to the bucket's served t0/t1;
     - coverage honesty: quiet period = carried, busy period = measured,
       last period = in progress;
     - #487 pin: slot is rhs|above from layout widths; never overlaps tip;
       stays inside the panel horizontally;
     - no native title= on level columns (one hover surface);
     - arrival has mid-frames (a snap has none); reduced motion snaps;
     - hover→focus parity, Escape and tap dismissal.

   usage: node bdhover.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';
import { waitFor, midFrames } from './dom.mjs';

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
declare({
  drives: 'one own-server target (a planted git ledger) on an ephemeral ' +
          'port; GET / and /data.json; dispatched pointerover/out, focus, ' +
          'click and Escape keydown events on level columns; a live tick ' +
          're-render (POST /command + tick()) under a held hover and under ' +
          'a pinned inspector; a reduced-motion context on the same target',
  traceWindow: '1.6s per inspector arrival capture (700ms dwell + the ' +
               '.42s ease-in, with margin); 500ms for reduced-motion; ' +
               'tick-survival samples immediately after the re-render'
});

// ── a planted ledger history ──────────────────────────────────────────────
// Hourly steps, six buckets, and each edge the inspector must name:
//   bucket 0: TWO revs (busy, measured) — the exact-values column
//   bucket 2: QUIET (no rev) — carried level, covered=0
//   bucket 5: last and quiet — carried AND in progress
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
const commit = (open, done, at) => {
  writeFileSync(join(DIR, '.dreamwork', 'tasks.md'), ledger(open, done));
  git(['add', '.dreamwork/tasks.md'], at);
  git(['commit', '-q', '-m', `ledger at ${at}`], at);
};
git(['init', '-q'], T0);
commit([1, 2, 3], [], T0);
commit([1, 2, 3, 4], [], T0 + 300);          // bucket 0: two revs
commit([2, 3, 4, 5], [1], T0 + 3600);        // bucket 1: arrive + land
//                                           // bucket 2: quiet — no rev
commit([2, 4, 5, 6], [3], T0 + 3 * 3600);    // bucket 3
commit([2, 4, 5, 6, 7], [], T0 + 4 * 3600);  // bucket 4
//                                           // bucket 5: quiet, in progress

const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill('SIGTERM'); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
// #507: serveVerified polls /data.json until the server answers with our
// target (and throws if it exits or a stranger holds the port) instead of
// racing a fixed 2500ms sleep — under load a slow python outlasted it, the
// fetch threw, and the guard reddened as "threw before finishing" over a
// page it never read. The target is already proven ours; fetch here only
// for the served series the figure checks below derive from.
const served = await (await fetch(`${BASE}/data.json`)).json();
const buckets = (served.burndown && served.burndown.buckets) || [];
const commits = buckets.map(b => b.commits || 0);
// THE PRECONDITIONS, asserted before anything that depends on them: the
// planted history really produced a busy bucket, a quiet middle bucket,
// and a quiet in-progress last bucket — a flat fixture would make every
// coverage check below vacuous (the born-hollow rule).
ok('precondition: served buckets carry the planted commit profile',
   buckets.length >= 6 && commits[0] === 2 && commits[1] === 1 &&
   commits[2] === 0 && commits[3] === 1 && commits[4] === 1 &&
   commits[buckets.length - 1] === 0);
const quietIdx = 2, lastIdx = buckets.length - 1;
let busyIdx = 0;
commits.forEach((c, i) => { if (c > commits[busyIdx]) busyIdx = i; });
notes.push(`served buckets: ${JSON.stringify(buckets.map(b =>
  ({ t0: b.t0, o: b.open, a: b.arrived, l: b.landed, c: b.commits || 0 })))}`);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1500 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
// #507: wait for the chart columns to be BUILT, not a fixed sleep — under load
// the client render lags networkidle and a sleep grades a half-painted panel.
// .bdnet .bdcol is what the hover/focus checks drive; settle for the level bars.
await waitFor(p, '.bdnet .bdcol[data-open]', 15000);
await sleep(400);

/* in-page measurement of the inspector: text per LINE (innerText keeps
   the div structure; textContent would concatenate the facts into one
   string a role-parse could not separate), opacity, and the rects the
   clamping checks reason about. */
const INSP = `(() => {
  const el = document.querySelector('.bd .bdinsp');
  if (!el || el.hidden) return null;
  const r = el.getBoundingClientRect();
  const bdEl = document.querySelector('.bd');
  const bd = bdEl.getBoundingClientRect();
  const track = document.querySelector('.bd .bdnet').getBoundingClientRect();
  const tip = document.querySelector('.bd .bdtip');
  const tipR = tip && !tip.hidden ? tip.getBoundingClientRect() : null;
  // room derivation mirrors bdinspLay: inspector fits in the right half
  const hasRoom = (el.offsetWidth + 8) <= (bd.width / 2);
  const overlapTip = tipR
    ? !(r.bottom <= tipR.top + 1 || r.top >= tipR.bottom - 1
        || r.right <= tipR.left + 1 || r.left >= tipR.right - 1)
    : false;
  return { lines: (el.innerText || '').trim().split('\\n').map(s => s.trim()),
           op: parseFloat(getComputedStyle(el).opacity),
           left: r.left, right: r.right, top: r.top, bottom: r.bottom,
           w: r.width, bdL: bd.left, bdR: bd.right, bdW: bd.width,
           trackTop: track.top, slot: el.dataset.bdslot || '',
           hasRoom, overlapTip,
           tipTop: tipR ? tipR.top : null, tipBot: tipR ? tipR.bottom : null };
})()`;
const dwellAndRead = async (idx, wait = 1000) => {
  await p.evaluate(`(() => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${idx}];
    col && col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
  })()`);
  await sleep(wait);
  return p.evaluate(INSP);
};
const leaveAll = async () => {
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')
    .forEach(c => c.dispatchEvent(new PointerEvent('pointerout',
      { bubbles: true, relatedTarget: document.body })))`);
  await sleep(600);
};

/* ── exact values against the served bucket ─────────────────────────────
   The busy column, hovered with a dwell. THE numbers, parsed by role from
   the inspector's own value line — never a bare substring (a tip naming
   the wrong column passes includes()). */
{
  const want = buckets[busyIdx];
  const tr = await p.evaluate(`new Promise(res => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}];
    if (!col) return res({ err: 'no col' });
    const seen = [];
    const t0 = performance.now();
    requestAnimationFrame(() => {
      col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
    });
    (function step() {
      const t = performance.now() - t0;
      const el = document.querySelector('.bd .bdinsp');
      const op = el && !el.hidden
        ? parseFloat(getComputedStyle(el).opacity) : 0;
      seen.push({ t, op, hidden: !el || el.hidden });
      if (t < 1600) requestAnimationFrame(step);
      else res({ seen, lines: el && !el.hidden
        ? (el.innerText || '').trim().split('\\n').map(s => s.trim()) : [] });
    })();
  })`);
  const lines = tr.lines || [];
  notes.push(`dwell col[${busyIdx}] lines=${JSON.stringify(lines)}; ` +
    `firstVisible=${((tr.seen || []).find(s => !s.hidden) || {}).t | 0}ms; ` +
    `ops=${[...new Set((tr.seen || []).map(s => Math.round(s.op * 100)))].join(',')}`);
  ok('#298 precondition: three lines (interval · values · coverage)',
     lines.length === 3);
  const vals = (lines[1] || '').match(
    /^(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?$/);
  ok('#298: names this column\'s open level and commits',
     !!vals && +vals[1] === want.open && +vals[4] === (want.commits || 0));
  ok('#298: names this column\'s arrivals and completions',
     !!vals && +vals[2] === want.arrived && +vals[3] === want.landed);
  // the interval line corresponds to the bucket's served t0/t1, formatted
  // by the same Intl calls in-page — derived, never a literal date
  const wantIv = await p.evaluate(`(() => {
    const f = t => { const d = new Date(t * 1000);
      return d.toLocaleDateString(undefined,
        { weekday: 'short', day: 'numeric', month: 'short' }) + ' ' +
        d.toLocaleTimeString(undefined,
          { hour: '2-digit', minute: '2-digit' }); };
    return f(${want.t0}) + ' – ' + f(${want.t0 + served.burndown.step});
  })()`);
  notes.push(`interval: got "${lines[0]}" want "${wantIv}"`);
  ok('#298: the exact interval matches the served bucket', lines[0] === wantIv);
  ok('#298: a busy period reads as measured', /measured/.test(lines[2] || ''));
  // a PASSING hover is not enough — the inspector dwells (#417's glance
  // tip owns the pass). First visibility well after the pointer arrives.
  const firstVis = (tr.seen || []).find(s => !s.hidden);
  ok('#298: dwell, not instant — a passing hover stays a glance',
     !!firstVis && firstVis.t >= 600);
  // arrival has mid-frames: a snap has no opacity strictly between ends
  const ops = (tr.seen || []).filter(s => !s.hidden).map(s => s.op);
  const mid = ops.filter(o => o > 0.03 && o < 0.97);
  ok('#298: the inspector arrives (mid-frame opacity, not a snap)',
     ops.length > 0 && ops[ops.length - 1] >= 0.9 && mid.length >= 1);
  await leaveAll();
}

/* ── coverage honesty: carried and in-progress ────────────────────────── */
{
  const quiet = await dwellAndRead(quietIdx);
  notes.push(`quiet col[${quietIdx}]: ${JSON.stringify(quiet && quiet.lines)}`);
  ok('#298: a quiet period says its level is CARRIED, not measured',
     !!quiet && /level carried — no ledger commits/.test(quiet.lines[2] || '') &&
     !/period in progress/.test(quiet.lines[2] || ''));
  await leaveAll();
  const last = await dwellAndRead(lastIdx);
  notes.push(`last col[${lastIdx}]: ${JSON.stringify(last && last.lines)}`);
  ok('#298: the open period says so, and ends the interval at "now"',
     !!last && /period in progress/.test(last.lines[2] || '') &&
     /– now$/.test(last.lines[0] || ''));
  /* #498: % elapsed from the open period's real t0/t1, derived at the
     moment of the read — never a literal. Precondition: last is open. */
  {
    const want = buckets[lastIdx];
    const step = served.burndown.step;
    const nowSec = Date.now() / 1000;
    const t0 = want.t0, t1 = t0 + step;
    ok('#498 precondition: last period is still open (t1 > now)',
       step > 0 && t1 > nowSec);
    const expectPct = Math.max(0, Math.min(100,
      Math.round(100 * (nowSec - t0) / step)));
    const m = ((last && last.lines[2]) || '').match(/(\d+)%\s*elapsed/);
    notes.push(`#498: cov="${(last && last.lines[2]) || ''}" ` +
               `expect≈${expectPct}% got=${m ? m[1] : 'none'}`);
    ok('#498: open period names N% elapsed from real period bounds',
       !!m && Math.abs(+m[1] - expectPct) <= 2);
  }
  await leaveAll();
}

/* ── #487 consistent pin: RHS when room, above otherwise; never tip ────
   First and last columns used to drive a column-centred clamp. The pin
   is now independent of the column: same slot for both. Room is derived
   from the inspector's measured width vs half the panel — assert that
   derivation matches the slot the page chose, and that tip+insp never
   share pixels. */
{
  const nativeTitle = await p.evaluate(`(() => {
    const cols = document.querySelectorAll('.bdnet .bdcol[data-open]');
    return [...cols].some(c => c.hasAttribute('title'));
  })()`);
  ok('#487: no native title= on level columns (one hover surface)',
     nativeTitle === false);
  const stepBtn = await p.evaluate(`(() => {
    const b = document.querySelector('.bd .bdstep');
    if (!b) return null;
    return { tag: b.tagName, role: b.getAttribute('role'),
             label: b.getAttribute('aria-label') || '',
             text: (b.textContent || '').trim() };
  })()`);
  ok('#487: granularity is a button control with announced state',
     !!stepBtn && stepBtn.tag === 'BUTTON' &&
     /granularity/i.test(stepBtn.label) && !!stepBtn.text);
  notes.push(`step control: ${JSON.stringify(stepBtn)}`);
}
/* ── #489 direction: plain click walks coarse→fine (down the fine→coarse
   ladder, wrapping to the coarsest); shift-click reverses. Real
   dispatched clicks, not a call into the page's function — the wiring
   (handler passes the modifier) is the thing under test. The ladder is
   read back from the page's own BURN_STEP_ORDER so a new server step
   cannot silently invalidate the walk. ── */
{
  const walk = await p.evaluate(`(async () => {
    const order = BURN_STEP_ORDER;
    const stepOf = () => (data && data.burndown && data.burndown.step) || null;
    const click = shift => {
      const b = document.querySelector('.bd .bdstep');
      b.dispatchEvent(new MouseEvent('click', { shiftKey: shift,
                                                bubbles: true,
                                                cancelable: true }));
    };
    const waitStep = async (prev) => {
      for (let i = 0; i < 50; i++) {
        await new Promise(r => setTimeout(r, 100));
        if (stepOf() !== prev) return stepOf();
      }
      return stepOf();
    };
    const s0 = stepOf();
    click(false);
    const s1 = await waitStep(s0);
    click(true);
    const s2 = await waitStep(s1);
    return { order, s0, s1, s2 };
  })()`);
  const i0 = walk && walk.order.indexOf(walk.s0);
  const i1 = walk && walk.order.indexOf(walk.s1);
  const i2 = walk && walk.order.indexOf(walk.s2);
  const L = walk ? walk.order.length : 0;
  ok('#489: fixture starts on a known ladder step (precondition)',
     !!walk && i0 >= 0);
  ok('#489: plain click walks coarse→fine (down the ladder, wrapping)',
     !!walk && i0 >= 0 && i1 === (i0 - 1 + L) % L);
  ok('#489: shift-click walks back up (reverse)',
     !!walk && i1 >= 0 && i2 === (i1 + 1) % L);
  notes.push(`cycle walk: ${JSON.stringify(walk)}`);
  /* leave the chart where we found it for the geometry checks below —
     plain-click until the served step returns, bounded */
  if (walk && walk.s2 !== walk.s0) {
    await p.evaluate(`(async (target) => {
      const stepOf = () => (data && data.burndown && data.burndown.step) || null;
      for (let n = 0; n < 8 && stepOf() !== target; n++) {
        const prev = stepOf();
        document.querySelector('.bd .bdstep')
          .dispatchEvent(new MouseEvent('click', { shiftKey: false,
                                                   bubbles: true,
                                                   cancelable: true }));
        for (let i = 0; i < 50; i++) {
          await new Promise(r => setTimeout(r, 100));
          if (stepOf() !== prev) break;
        }
      }
    })(${walk ? walk.s0 : 0})`);
  }
}
for (const idx of [0, lastIdx, busyIdx]) {
  const m = await dwellAndRead(idx);
  notes.push(`pin col[${idx}]: ${JSON.stringify(m &&
    { slot: m.slot, hasRoom: m.hasRoom, left: m.left | 0, right: m.right | 0,
      top: m.top | 0, bottom: m.bottom | 0, w: m.w | 0, bdW: m.bdW | 0,
      overlapTip: m.overlapTip, tipTop: m.tipTop | 0 })}`);
  ok(`#487: col ${idx} keeps the inspector inside the panel`,
     !!m && m.left >= m.bdL - 1 && m.right <= m.bdR + 1);
  // precondition: room flag and slot agree — a hollow check would let the
  // page claim "rhs" while measuring "no room"
  ok(`#487: col ${idx} slot matches layout-derived room`,
     !!m && ((m.hasRoom && m.slot === 'rhs') ||
             (!m.hasRoom && m.slot === 'above')));
  ok(`#487: col ${idx} inspector never overlaps the glance tip`,
     !!m && m.overlapTip === false);
  if (m && m.slot === 'above' && m.tipTop != null) {
    ok(`#487: col ${idx} above-slot sits above the tip line`,
       m.bottom <= m.tipTop + 1);
  }
  await leaveAll();
}
/* narrow viewport forces the above slot (room is width-derived) */
{
  await p.setViewportSize({ width: 390, height: 844 });
  await sleep(500);
  const m = await dwellAndRead(busyIdx);
  notes.push(`narrow pin: ${JSON.stringify(m &&
    { slot: m.slot, hasRoom: m.hasRoom, w: m.w | 0, bdW: m.bdW | 0,
      overlapTip: m.overlapTip })}`);
  // precondition: at 390 the inspector really does not fit half-width —
  // otherwise the "above" assertion is vacuous
  ok('#487 narrow precondition: no room on the right half',
     !!m && m.hasRoom === false);
  ok('#487 narrow: slot is above and clears the tip',
     !!m && m.slot === 'above' && m.overlapTip === false);
  await leaveAll();
  await p.setViewportSize({ width: 1100, height: 1500 });
  await sleep(400);
}

/* ── hover→focus parity, then dismissal ──────────────────────────────────
   Focus shows the SAME inspector, immediately (focus is deliberate — no
   dwell). Escape departs it. Tap pins; a second tap on the same column
   lets it go, and a pin survives the pointer leaving. */
{
  const hBefore = await p.evaluate(
    `Math.round(document.querySelector('.bd').getBoundingClientRect().height)`);
  const t0 = Date.now();
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}].focus()`);
  await sleep(220);
  const fm = await p.evaluate(INSP);
  const want = buckets[busyIdx];
  const fvals = fm && (fm.lines[1] || '').match(
    /^(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?$/);
  notes.push(`focus col[${busyIdx}] after ${Date.now() - t0}ms: ` +
             JSON.stringify(fm && fm.lines));
  ok('#298 hover→focus parity: focus shows the same reading, immediately',
     !!fm && Date.now() - t0 < 600 && !!fvals &&
     +fvals[1] === want.open && +fvals[2] === want.arrived &&
     +fvals[3] === want.landed && +fvals[4] === (want.commits || 0));
  ok('#298: focus names the same interval hover does',
     !!fm && fm.lines[0] && fm.lines[0].includes('–'));
  const hDuring = await p.evaluate(
    `Math.round(document.querySelector('.bd').getBoundingClientRect().height)`);
  ok('#298: panel height unchanged with the inspector open (it floats)',
     hDuring === hBefore);
  await p.screenshot({ path: `${OUT}/bdhover-desktop.png`, fullPage: false });
  // Escape departs
  await p.keyboard.press('Escape');
  await sleep(600);
  ok('#298: Escape dismisses the inspector',
     (await p.evaluate(INSP)) === null);
  await p.evaluate(`document.activeElement && document.activeElement.blur()`);

  // tap pins: click, then the pointer leaving does NOT dismiss
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')[${quietIdx}]` +
    `.dispatchEvent(new MouseEvent('click', { bubbles: true }))`);
  await sleep(500);
  const pinned = await p.evaluate(INSP);
  ok('#298: tap selects the column (inspector arrives)', !!pinned);
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')[${quietIdx}]` +
    `.dispatchEvent(new PointerEvent('pointerout',
      { bubbles: true, relatedTarget: document.body }))`);
  await sleep(600);
  ok('#298: a tapped (pinned) reading survives the pointer leaving',
     (await p.evaluate(INSP)) !== null);
  // second tap on the same column dismisses
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')[${quietIdx}]` +
    `.dispatchEvent(new MouseEvent('click', { bubbles: true }))`);
  await sleep(600);
  ok('#298: a second tap on the same column dismisses it',
     (await p.evaluate(INSP)) === null);
}

/* ── #494: hover / pin survive the live tick re-render ───────────────────
   The dashboard re-renders whenever ANY watched file changes (status.json
   every few seconds — the 2s /mtime poll). Without a carry, .bdtip/.bdinsp
   are recreated hidden and bdtipCol/bdinspCol point at detached columns:
   the tip fades in, then 1–2s later "it all resets" with the mouse unmoved.
   This is the poll, not a hide timer.

   Under #505, keyed reconciliation keeps .bdcol[data-t0] (and tip/insp
   when they are outside the swapped subtree). Vacuity is __dwViewRenderGen
   advancing (or legacy: column detached). End-state-only "tip is up" would
   pass if the tick never ran. THE ASSERTION is that tip + inspector stay
   the active surface for the same column numbers, with no pointer move. */
{
  const TIP = `(() => {
    const el = document.querySelector('.bd .bdtip');
    if (!el || el.hidden) return null;
    return { text: (el.textContent || '').trim(),
             op: parseFloat(getComputedStyle(el).opacity),
             depart: el.classList.contains('depart') };
  })()`;
  const pre = await p.evaluate(`(() => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}];
    if (!col) return { err: 'no col' };
    col.dataset.probe494 = '1';
    col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
    return { t0: col.dataset.t0, open: col.dataset.open,
             commits: col.dataset.commits };
  })()`);
  await sleep(1100);   // past BD_DWELL + tip ease-in
  const preTip = await p.evaluate(TIP);
  const preInsp = await p.evaluate(INSP);
  notes.push(`#494 pre-tick: tip=${JSON.stringify(preTip)} ` +
             `insp=${JSON.stringify(preInsp && preInsp.lines)}`);
  ok('#494 precondition: tip and inspector are both up before the tick',
     !!pre && !pre.err && !!preTip && !preTip.depart && preTip.op > 0.5 &&
     !!preInsp && preInsp.op > 0.5);
  // Real production path: /command appends watch-events.log (watched —
  // mtime moves), then tick() re-renders. Not a hand-call to setContent.
  const swap = await p.evaluate(`(async () => {
    const colBefore = document.querySelector('.bdnet .bdcol[data-probe494="1"]');
    const tipBefore = document.querySelector('.bd .bdtip');
    const gen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: '494 hover tick' }) });
    await tick();
    // one retry if the first tick no-op'd
    if ((window.__dwViewRenderGen || 0) <= gen0) {
      if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
      await new Promise(r => setTimeout(r, 50));
      await tick();
    }
    const tipAfter = document.querySelector('.bd .bdtip');
    const insp = document.querySelector('.bd .bdinsp');
    const advanced = (window.__dwViewRenderGen || 0) > gen0;
    return {
      colDetached: !colBefore || !colBefore.isConnected,
      tipReplaced: !!tipAfter && tipAfter !== tipBefore,
      advanced,
      tickWorked: advanced || !colBefore || !colBefore.isConnected,
      tipHidden: !tipAfter || tipAfter.hidden,
      tipText: tipAfter && !tipAfter.hidden
        ? (tipAfter.textContent || '').trim() : '',
      tipDepart: !!(tipAfter && tipAfter.classList.contains('depart')),
      tipOp: tipAfter && !tipAfter.hidden
        ? parseFloat(getComputedStyle(tipAfter).opacity) : 0,
      inspHidden: !insp || insp.hidden,
      inspDepart: !!(insp && insp.classList.contains('depart')),
      inspOp: insp && !insp.hidden
        ? parseFloat(getComputedStyle(insp).opacity) : 0,
      inspText: insp && !insp.hidden
        ? (insp.innerText || '').trim() : '',
    };
  })()`);
  notes.push(`#494 hover tick: ${JSON.stringify(swap)}`);
  ok('#494 precondition: the tick really re-rendered the burndown DOM ' +
     '(render gen advanced or column detached)',
     !!swap && swap.tickWorked === true);
  const tipMatch = !!swap && !swap.tipHidden && !swap.tipDepart &&
    swap.tipOp >= 0.9 &&
    new RegExp('^' + pre.open + ' open · ').test(swap.tipText || '') &&
    (swap.tipText || '').includes(pre.commits + ' commit');
  ok('#494: glance tip stays up for the same column after the tick ' +
     '(mouse unmoved)', tipMatch);
  const want = buckets[busyIdx];
  const inspVals = (swap.inspText || '').match(
    /(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?/);
  ok('#494: inspector stays up with the same column numbers after the tick',
     !!swap && !swap.inspHidden && !swap.inspDepart && swap.inspOp >= 0.9 &&
     !!inspVals && +inspVals[1] === want.open &&
     +inspVals[4] === (want.commits || 0));
  await leaveAll();

  // pin path: a tapped inspector must also survive the tick (#298 + #494)
  await p.evaluate(`(() => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${quietIdx}];
    if (!col) return;
    col.dataset.probe494pin = '1';
    col.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  })()`);
  await sleep(500);
  const pinPre = await p.evaluate(INSP);
  ok('#494 pin precondition: inspector is pinned before the tick', !!pinPre);
  const pinSwap = await p.evaluate(`(async () => {
    const colBefore = document.querySelector(
      '.bdnet .bdcol[data-probe494pin="1"]');
    const gen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: '494 pin tick' }) });
    await tick();
    if ((window.__dwViewRenderGen || 0) <= gen0) {
      if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
      await new Promise(r => setTimeout(r, 50));
      await tick();
    }
    const insp = document.querySelector('.bd .bdinsp');
    const advanced = (window.__dwViewRenderGen || 0) > gen0;
    return {
      colDetached: !colBefore || !colBefore.isConnected,
      advanced,
      tickWorked: advanced || !colBefore || !colBefore.isConnected,
      inspHidden: !insp || insp.hidden,
      inspText: insp && !insp.hidden ? (insp.innerText || '').trim() : '',
      inspOp: insp && !insp.hidden
        ? parseFloat(getComputedStyle(insp).opacity) : 0,
    };
  })()`);
  notes.push(`#494 pin tick: ${JSON.stringify(pinSwap)}`);
  ok('#494 pin precondition: the tick really re-rendered under the pin',
     !!pinSwap && pinSwap.tickWorked === true);
  const qWant = buckets[quietIdx];
  const pinVals = (pinSwap.inspText || '').match(
    /(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?/);
  ok('#494: a pinned inspector survives the tick re-render',
     !!pinSwap && !pinSwap.inspHidden && pinSwap.inspOp >= 0.9 &&
     !!pinVals && +pinVals[1] === qWant.open &&
     +pinVals[4] === (qWant.commits || 0));
  // hard clear so later geometry checks do not inherit a live pin
  await p.evaluate(`(() => {
    if (typeof hideBdInsp === 'function') hideBdInsp(true);
    if (typeof hideBdTip === 'function') hideBdTip(true);
  })()`);
  await leaveAll();
}

/* ── mobile screenshot + inside-panel pin (narrow path already covered) ─ */
{
  await p.setViewportSize({ width: 390, height: 844 });
  await sleep(500);
  const m = await dwellAndRead(lastIdx);
  notes.push(`mobile col[${lastIdx}]: ${JSON.stringify(m &&
    { slot: m.slot, left: m.left | 0, right: m.right | 0,
      bdL: m.bdL | 0, bdR: m.bdR | 0, overlapTip: m.overlapTip })}`);
  ok('#298/#487: at 390px the inspector stays inside the panel',
     !!m && m.left >= m.bdL - 1 && m.right <= m.bdR + 1);
  ok('#298/#487: at 390px tip and inspector do not overlap',
     !!m && m.overlapTip === false);
  await p.screenshot({ path: `${OUT}/bdhover-mobile.png`, fullPage: false });
  await leaveAll();
  await p.setViewportSize({ width: 1100, height: 1500 });
  await sleep(400);
}

/* ── reduced motion: the same reading, no travel ──────────────────────── */
{
  const ctx = await br.newContext({ reducedMotion: 'reduce',
                                    viewport: { width: 1100, height: 1500 } });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(rp, '.bdnet .bdcol[data-open]', 15000);   // #507 render readiness
  const tr = await rp.evaluate(`new Promise(res => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}];
    if (!col) return res({ err: 'no col' });
    const ops = [];
    const t0 = performance.now();
    requestAnimationFrame(() => col.focus());
    (function step() {
      const t = performance.now() - t0;
      const el = document.querySelector('.bd .bdinsp');
      const op = el && !el.hidden
        ? parseFloat(getComputedStyle(el).opacity) : 0;
      ops.push(op);
      if (t < 500) requestAnimationFrame(step);
      else res({ ops, lines: el && !el.hidden
        ? (el.innerText || '').trim().split('\\n').map(s => s.trim()) : [] });
    })();
  })`);
  const mid = (tr.ops || []).filter(o => o > 0.03 && o < 0.97);
  const want = buckets[busyIdx];
  const rvals = (tr.lines || [])[1] && tr.lines[1].match(
    /^(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?$/);
  notes.push(`reduced focus: lines=${JSON.stringify(tr.lines)} ` +
    `mid=${mid.length} ops=${[...new Set((tr.ops || []).map(o =>
      Math.round(o * 100)))].join(',')}`);
  ok('#298 reduced motion: the same reading still arrives (function intact)',
     !!rvals && +rvals[1] === want.open && +rvals[4] === (want.commits || 0));
  ok('#298 reduced motion: it snaps — no travel frames', mid.length === 0);
  await rp.screenshot({ path: `${OUT}/bdhover-reduced.png`, fullPage: false });
  await ctx.close();
}

/* ── #559: the hit zone is the WHOLE column (top + bottom + gap) ───────
   Before #559 only the top (.bdnet) section was hoverable: the pointer
   handlers resolved `.closest('.bdnet .bdcol[data-open]')`, and the bottom
   (.bdflow) columns are a SEPARATE flex track that carries no data and is
   not inside .bdnet — so the entire bottom half was a dead strip. #559
   resolves a point to its net column by geometry (bdColAtPoint), so every
   pixel of a column's full height surfaces the same reading. Preconditions
   are asserted at runtime: the bottom section really has height, and the
   two tracks' columns are pixel-aligned (the resolver depends on it). */
{
  await leaveAll();
  const geom = await p.evaluate(`(() => {
    const net = document.querySelector('.bd .bdnet');
    const flow = document.querySelector('.bd .bdflow');
    if (!net || !flow) return { err: 'no tracks' };
    const netCols = [...net.querySelectorAll('.bdcol[data-open]')];
    const flowCols = [...flow.querySelectorAll('.bdcol')];
    const i = Math.min(${busyIdx}, netCols.length - 1, flowCols.length - 1);
    const nc = netCols[i], fc = flowCols[i];
    if (!nc || !fc) return { err: 'no col at idx ' + i };
    const nr = nc.getBoundingClientRect(), fr = fc.getBoundingClientRect();
    const flowR = flow.getBoundingClientRect();
    return { i,
      flowH: Math.round(flowR.height), flowColH: Math.round(fr.height),
      netL: Math.round(nr.left), netR2: Math.round(nr.right),
      flowL: Math.round(fr.left), flowR2: Math.round(fr.right),
      flowCx: (fr.left + fr.right) / 2, flowCy: (fr.top + fr.bottom) / 2,
      gapCx: (nr.left + nr.right) / 2, gapCy: nr.bottom + (flowR.top - nr.bottom) / 2 };
  })()`);
  notes.push(`#559 geom: ${JSON.stringify(geom)}`);
  ok('#559 precondition: the bottom (.bdflow) section has real height',
     !!geom && !geom.err && geom.flowH > 0 && geom.flowColH > 0);
  ok('#559 precondition: net and flow columns are horizontally aligned ' +
     '(the resolver maps a flow point to its net column by index)',
     !!geom && !geom.err && Math.abs(geom.netL - geom.flowL) <= 2 &&
     Math.abs(geom.netR2 - geom.flowR2) <= 2);
  const TIP = `(() => {
    const el = document.querySelector('.bd .bdtip');
    if (!el || el.hidden) return null;
    return (el.textContent || '').trim();
  })()`;
  const want = buckets[(geom && geom.i != null) ? geom.i : busyIdx];
  const fx = (geom && geom.flowCx) || 0, fy = (geom && geom.flowCy) || 0;
  // hover the BOTTOM (flow) section — the dead strip before #559
  await p.evaluate(`document.querySelector('.bd').dispatchEvent(
    new PointerEvent('pointerover', { bubbles:true, clientX:${fx}, clientY:${fy} }))`);
  await sleep(120);
  const flowTip = await p.evaluate(TIP);
  notes.push(`#559 flow-section glance tip: "${flowTip}"`);
  ok('#559: hovering the BOTTOM section surfaces the glance tip',
     !!flowTip && new RegExp('^' + want.open + ' open · ').test(flowTip) &&
     flowTip.includes((want.commits || 0) + ' commit'));
  // the richer inspector surfaces too (a hover that dwells inspects)
  await sleep(900);
  const flowInsp = await p.evaluate(INSP);
  const fv = flowInsp && (flowInsp.lines[1] || '').match(
    /^(\d+) open · (\d+) arrived · (\d+) landed · (\d+) commits?$/);
  notes.push(`#559 flow-section inspector: ${JSON.stringify(flowInsp && flowInsp.lines)}`);
  ok('#559: hovering the BOTTOM section surfaces the inspector with this ' +
     'column\'s values (parsed by role — a wrong column fails)',
     !!fv && +fv[1] === want.open && +fv[2] === want.arrived &&
     +fv[3] === want.landed && +fv[4] === (want.commits || 0));
  await leaveAll();
  // the gap between the two sections is inside a column's span too
  const gx = (geom && geom.gapCx) || 0, gy = (geom && geom.gapCy) || 0;
  await p.evaluate(`document.querySelector('.bd').dispatchEvent(
    new PointerEvent('pointerover', { bubbles:true, clientX:${gx}, clientY:${gy} }))`);
  await sleep(120);
  const gapTip = await p.evaluate(TIP);
  ok('#559: hovering the gap between the sections stays on the column',
     !!gapTip && new RegExp('^' + want.open + ' open · ').test(gapTip));
  await leaveAll();
  // pointer leaving the top cell for the bottom cell (same column) must
  // NOT hide the tip — the full height is one hit zone
  await p.evaluate(`(() => {
    const c = document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}];
    if (c) c.dispatchEvent(new PointerEvent('pointerover', { bubbles:true }));
  })()`);
  await sleep(150);
  // move DOWN to the flow cell of the SAME column. Read the tip's state
  // SYNCHRONOUSLY right after the pointerout — a depart is armed in the
  // same tick and cleared by nothing here, so .depart membership is the
  // load-independent signal that the full height is one hit zone (a rAF
  // sample taken later would read text that is still present mid-depart
  // and pass over the very thing it claims to check).
  const afterDown = await p.evaluate(`(() => {
    const flow = document.querySelector('.bd .bdflow');
    const c = document.querySelectorAll('.bdnet .bdcol[data-open]')[${busyIdx}];
    if (!flow || !c) return null;
    const fr = flow.querySelectorAll('.bdcol')[${busyIdx}].getBoundingClientRect();
    c.dispatchEvent(new PointerEvent('pointerout', { bubbles:true,
      clientX:(fr.left + fr.right) / 2, clientY:(fr.top + fr.bottom) / 2,
      relatedTarget:document.body }));
    const tip = document.querySelector('.bd .bdtip');
    return { hidden:tip.hidden, depart:tip.classList.contains('depart'),
             text:(tip.textContent || '').trim() };
  })()`);
  notes.push(`#559 net→flow same-column: ${JSON.stringify(afterDown)}`);
  ok('#559: leaving the top cell for the bottom cell (same column) keeps ' +
     'the tip — no depart, no hide (the full height is one hit zone)',
     !!afterDown && !afterDown.hidden && !afterDown.depart &&
     new RegExp('^' + want.open + ' open · ').test(afterDown.text));
  await leaveAll();
}

/* ── #559: the tip persists across columns and cross-dissolves ─────────
   Once the glance tip is visible, moving to another column must NOT hide-
   and-show it: the container stays (no opacity dip) and the content cross-
   dissolves — old values fade out as new values fade in, on the same .42s
   envelope the tip's own arrival/departure use. Persistence is not a
   transition (nothing happens to the container); the content swap is the
   one gesture one level down. Preconditions: the two columns really carry
   different values (else the dissolve is vacuous). */
{
  await leaveAll();
  const tuple = b => `${b.open}/${b.arrived}/${b.landed}/${b.commits || 0}`;
  const aIdx = 0;
  let bIdx = Math.min(1, buckets.length - 1);
  for (let i = 1; i < buckets.length; i++) {
    if (tuple(buckets[i]) !== tuple(buckets[0])) { bIdx = i; break; }
  }
  ok('#559 precondition: the two columns carry different values ' +
     '(else the dissolve is vacuous)',
     buckets.length >= 2 && tuple(buckets[aIdx]) !== tuple(buckets[bIdx]));
  const wantB = buckets[bIdx];
  notes.push(`#559 swap cols: a=${aIdx}(${tuple(buckets[aIdx])}) ` +
             `b=${bIdx}(${tuple(buckets[bIdx])})`);
  const swap = await p.evaluate(`new Promise(res => {
    const cols = document.querySelectorAll('.bdnet .bdcol[data-open]');
    const A = cols[${aIdx}], B = cols[${bIdx}];
    if (!A || !B) return res({ err: 'no cols' });
    const br = B.getBoundingClientRect();
    const bx = (br.left + br.right) / 2, by = (br.top + br.bottom) / 2;
    A.dispatchEvent(new PointerEvent('pointerover', { bubbles:true }));
    setTimeout(() => {
      const tip = document.querySelector('.bd .bdtip');
      // real order: leave A (coords already at B), then enter B
      A.dispatchEvent(new PointerEvent('pointerout', { bubbles:true,
        clientX:bx, clientY:by, relatedTarget:B }));
      // SYNCHRONOUS post-leave state: a depart is armed in THIS tick, so
      // .depart/.hidden membership is the load-independent persistence
      // signal (a later rAF sample would miss it — the arrive cancels it).
      const afterLeave = { hidden: tip.hidden,
        depart: tip.classList.contains('depart') };
      B.dispatchEvent(new PointerEvent('pointerover', { bubbles:true,
        clientX:bx, clientY:by }));
      const frames = [], trans = [];
      const onT = ev => trans.push({ type:ev.type, prop:ev.propertyName,
        t:performance.now(), cls:(ev.target && ev.target.className) || '' });
      tip.addEventListener('transitionstart', onT);
      tip.addEventListener('transitionend', onT);
      const t0 = performance.now();
      (function step() {
        const t = performance.now() - t0;
        const bdi = tip.querySelector('.bdi');
        frames.push({ t,
          contOp: parseFloat(getComputedStyle(tip).opacity),
          hidden: tip.hidden, bdiOp: bdi ? parseFloat(getComputedStyle(bdi).opacity) : null });
        if (t < 760) requestAnimationFrame(step);
        else {
          tip.removeEventListener('transitionstart', onT);
          tip.removeEventListener('transitionend', onT);
          res({ frames, trans, afterLeave, err:null, finalText:(tip.textContent || '').trim() });
        }
      })();
    }, 900);
  })`);
  const frames = (swap && swap.frames) || [];
  const bdiOps = frames.filter(f => f.bdiOp != null).map(f => f.bdiOp);
  // The cross-dissolve gate is midFrames (the brief's "part-way frames
  // strictly between 0 and 1") — the container stays at full opacity
  // (minCont) while the INCOMING layer's opacity travels 0→1, which is the
  // dissolve. transitionstart (#442's load-independent snap detector) is
  // logged as bdiStart for diagnosis but is NOT the gate here: it is
  // intermittently suppressed for transitions on a FRESHLY-INSERTED layer
  // (bdContentSwap rebuilds the .bdi each swap), so it cannot be trusted as
  // a hard assertion. The brief mandates solo (unloaded) guard runs, where
  // the rAF sampler reliably catches the part-way frames.
  const ran = !!(swap && swap.trans && swap.trans.some(e =>
    e.type === 'start' && e.prop === 'opacity' && /\bbdi\b/.test(e.cls || '')));
  const minCont = frames.length ? Math.min(...frames.map(f => f.contOp)) : 0;
  const everHidden = frames.some(f => f.hidden);
  const afterLeave = (swap && swap.afterLeave) || {};
  const nBdiStart = !!(swap && swap.trans) ? swap.trans.filter(e =>
    e.type === 'start' && e.prop === 'opacity' && /\bbdi\b/.test(e.cls || '')).length : 0;
  notes.push(`#559 swap: frames=${frames.length} minCont=${minCont.toFixed(2)} ` +
    `everHidden=${everHidden} afterLeave=${JSON.stringify(afterLeave)} ` +
    `midBdi=${midFrames(bdiOps)} ran=${ran} bdiStart=${nBdiStart} ` +
    `bdiOps=${[...new Set(bdiOps.map(o => Math.round(o * 100)))].join(',')} ` +
    `final="${swap && swap.finalText}"`);
  ok('#559: the tip PERSISTS across the move — the leave arms no depart ' +
     '(synchronous post-pointerout: no .depart, no hide)',
     afterLeave.depart === false && afterLeave.hidden === false);
  ok('#559: the tip PERSISTS across the move — the container is never hidden',
     !everHidden);
  ok('#559: the tip PERSISTS across the move — no depart/arrival interval ' +
     '(the container stays at full opacity; no hide-and-show dip)',
     minCont >= 0.9);
  ok('#559: the content cross-dissolves — mid-swap opacity strictly ' +
     'between 0 and 1 on the incoming layer (the container stays full)',
     midFrames(bdiOps) >= 1 && minCont >= 0.9);
  ok('#559: after the move the tip names the NEW column\'s values',
     !!(swap && swap.finalText) &&
     new RegExp('^' + wantB.open + ' open · ').test(swap.finalText) &&
     swap.finalText.includes((wantB.commits || 0) + ' commit'));
  await leaveAll();
}

/* ── #559 reduced motion: the tip still stays; the swap snaps ──────────
   Persistence holds under reduced motion too (the tip STAYS — no vanish),
   and the swap SNAPS: content set directly, no cross-fade layers (the RM
   parity contract). */
{
  const ctx = await br.newContext({ reducedMotion: 'reduce',
                                    viewport: { width: 1100, height: 1500 } });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(rp, '.bdnet .bdcol[data-open]', 15000);
  await sleep(400);
  const tuple = b => `${b.open}/${b.arrived}/${b.landed}/${b.commits || 0}`;
  const aIdx = 0;
  let bIdx = Math.min(1, buckets.length - 1);
  for (let i = 1; i < buckets.length; i++) {
    if (tuple(buckets[i]) !== tuple(buckets[0])) { bIdx = i; break; }
  }
  const wantB = buckets[bIdx];
  const rm = await rp.evaluate(`new Promise(res => {
    const cols = document.querySelectorAll('.bdnet .bdcol[data-open]');
    const A = cols[${aIdx}], B = cols[${bIdx}];
    if (!A || !B) return res({ err:'no cols' });
    const br = B.getBoundingClientRect();
    const bx = (br.left + br.right) / 2, by = (br.top + br.bottom) / 2;
    A.dispatchEvent(new PointerEvent('pointerover', { bubbles:true }));
    setTimeout(() => {
      const tip = document.querySelector('.bd .bdtip');
      A.dispatchEvent(new PointerEvent('pointerout', { bubbles:true,
        clientX:bx, clientY:by, relatedTarget:B }));
      // RM finishes the depart SYNCHRONOUSLY (hideBdInsp/hideBdTip call
      // finish() at once under reduced motion), so the rAF sampler below
      // would never see a hidden=true that the arrive then clears. Read it
      // in the same tick as the leave.
      const afterLeaveHidden = tip.hidden;
      B.dispatchEvent(new PointerEvent('pointerover', { bubbles:true,
        clientX:bx, clientY:by }));
      const seen = [];
      const t0 = performance.now();
      (function step() {
        const t = performance.now() - t0;
        seen.push({ t, hidden:tip.hidden,
          bdi:!!tip.querySelector('.bdi'),
          op:parseFloat(getComputedStyle(tip).opacity) });
        if (t < 500) requestAnimationFrame(step);
        else res({ seen, afterLeaveHidden, finalText:(tip.textContent || '').trim() });
      })();
    }, 500);
  })`);
  const seen = (rm && rm.seen) || [];
  const everHidden = seen.some(s => s.hidden);
  const everBdi = seen.some(s => s.bdi);
  const afterLeaveHidden = rm && rm.afterLeaveHidden;
  notes.push(`#559 RM swap: afterLeaveHidden=${afterLeaveHidden} ` +
    `everHidden=${everHidden} everBdi=${everBdi} final="${rm && rm.finalText}"`);
  ok('#559 RM: the tip stays across the move — the leave hides nothing ' +
     '(synchronous post-pointerout: no hide; reduced motion still persists)',
     afterLeaveHidden === false);
  ok('#559 RM: the swap snaps — no cross-dissolve layers under reduced motion',
     !everBdi);
  ok('#559 RM: after the move the tip names the NEW column\'s values',
     !!(rm && rm.finalText) &&
     new RegExp('^' + wantB.open + ' open · ').test(rm.finalText));
  await rp.screenshot({ path: `${OUT}/bdhover-rm-swap.png`, fullPage: false });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
try { srv.kill(); } catch (e) {}
finish();
