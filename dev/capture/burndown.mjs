/* burndown — #142: the ledger's own history, drawn.

   No new instrumentation: `.dreamwork/tasks.md` is versioned and its ids are
   permanent, so `git log` over that one path IS the time series. Arrivals
   AND completions, because the open count alone cannot tell "he steers fast"
   from "the work is slow" — those are the same curve.

   THIS GUARD BUILDS ITS OWN TARGET and takes an ephemeral port. The shared
   fixture is not a git repository, so the panel there can only ever be in
   its "no ledger" state and every check about a bar would pass against
   nothing at all — the same trap `dashboard.mjs` names for the commits
   panel. The history here is PLANTED, at times this guard chose, so the
   numbers are known rather than read off the page and compared to itself.

   THE MOTION HALF IS THE PART THAT NEEDS A GUARD, and it has three claims
   that no end-state check can fail on:

     - a bar whose value changed TRAVELS to its new height rather than
       snapping (distinct intermediate heights, not "did it end right");
     - a re-render that changes no number disturbs no bar. This is NOT a
       test of #151's gate — deleting that gate reddens nothing, because a
       bar's height is a pure function of the series and `regroupBars`
       early-returns on an equal height. It is stated as an optimisation in
       `watch.py` and deliberately has no check;
     - the panel's own HEIGHT NEVER CHANGES, which is the premise the whole
       design rests on: it is why bar motion needs no FLIP over the panels
       below. #204 is what a reasoned exemption costs when nobody checks its
       premise, so this one is measured.

   usage: node burndown.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';

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
/* Say WHAT threw — the shared sentinel only says "threw before finishing",
   which hid a TypeError under load (after.head undefined when .bd was
   briefly absent). Capture into errs (always printed) and rename the FAIL. */
const nameThrow = (kind, e) => {
  const msg = e && e.stack ? e.stack : String(e);
  errs.push(`${kind}: ${msg}`);
  checks.push(`FAIL the guard threw before finishing its checks: ${String(e)}`);
};
process.on('uncaughtException', e => nameThrow('uncaughtException', e));
process.on('unhandledRejection', e => nameThrow('unhandledRejection', e));
/* #334: this guard used to hand-roll its checks/ok/exit handler — the very
   reporter #324's sweep made structural. #281's plan cites burndown as the
   guard-writing precedent, so leaving the old idiom here pointed new work at
   the outdated shape. Adopting report.mjs inherits the crash sentinel and
   the coverage declaration by construction, the same inheritance every
   converted guard gets. */
declare({
  drives: 'two own-server targets (a planted git ledger and a bare non-git ' +
          'copy) on ephemeral ports; GET / and /data.json on each; a real ' +
          'git commit to the planted ledger while the first page is open ' +
          '(the /mtime poll path); POST /command {add-idea} then ' +
          '`tick()` (a re-render that changes no number); a reduced-motion ' +
          'context on the first target; pointer hover on a level column ' +
          'and a reduced-motion hover of the same column',
  traceWindow: '4.2s per motion capture — one /mtime poll (2s) plus the bar ' +
               'travel — deliberately stopping before the next tick could ' +
               'supply the motion being asserted (the regroup.mjs trap); ' +
               '1.2s for the quiet-tick capture; panel-height and ' +
               'panel-below premises measured across the same 4.2s window; ' +
               '0.7s for the hover tip arrival'
});

// ── a planted ledger history ──────────────────────────────────────────────
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
// six hourly steps, with an arrival profile this guard can name. #1 is
// GROOMED OUT of the landed section at the end — a completion read from the
// current contents would lose it, and that is the load-bearing property.
// #417: the first hour gets TWO ledger commits so peak>1 (weight maps to
// 6px) and a later quiet gap (no rev in that hour) can sit at 0 commits
// (1px) — the edges the weight mapping must distinguish.
commit([1, 2, 3], [], T0);
commit([1, 2, 3, 4], [], T0 + 300);            // still hour 0 — peak ≥ 2
commit([2, 3, 4, 5], [1], T0 + 3600);
commit([3, 4, 5, 6, 7, 8], [1, 2], T0 + 2 * 3600);
commit([4, 5, 6, 7, 8], [2, 3], T0 + 3 * 3600);
commit([5, 6, 7, 8, 9], [3, 4], T0 + 4 * 3600);
commit([6, 7, 8, 9], [4, 5], T0 + 5 * 3600);   // #1..#3 groomed away

const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill('SIGTERM'); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
{
  // #507: serveVerified polls /data.json until the server answers with our
  // target (and throws if it exits or a stranger holds the port) rather than
  // racing a fixed 2500ms sleep — a slow python under load took longer than
  // that, the fetch threw ECONNREFUSED, and the guard reddened as "threw
  // before finishing its checks" over a page it never read. The served
  // target is already proven ours; fetch here only for the shape note.
  const d = await (await fetch(`${BASE}/data.json`)).json();
  notes.push(`served burndown: ${JSON.stringify(
    { ...d.burndown, buckets: (d.burndown.buckets || []).length })}`);
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1500 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
// #507: wait for the chart's bars (or the no-ledger state) to be BUILT, not a
// fixed sleep — under load the client render lags networkidle and a sleep
// grades a half-painted panel. .bdbar proves the chart attached; .bdnone the
// bare case. Settle briefly so columns/levels/caps paint in the same pass.
await waitFor(p, '.bd .bdbar[data-bk], .bdnone', 15000);
await sleep(400);

const READ = `(() => {
  const bd = document.querySelector('.bd');
  if (!bd) return { present: false };
  const bars = [...bd.querySelectorAll('.bdbar[data-bk]')];
  const cols = [...bd.querySelectorAll('.bdnet .bdcol')];
  const levels = [...bd.querySelectorAll('.bdlevel[data-bk]')];
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent)';
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  const paint = bars.map(b => {
    const cs = getComputedStyle(b);
    return cs.backgroundColor + '|' + cs.borderTopColor;
  });
  const copy = bd.querySelector('.bdcommit-copy');
  const copyCs = copy ? getComputedStyle(copy) : null;
  const lim = bd.querySelector('.bdlimit');
  const limIn = lim && lim.querySelector('.bdlimit-in');
  const limReset = lim && lim.querySelector('.bdlimit-reset');
  const head = bd.querySelector('.bdhead');
  const headCs = head ? getComputedStyle(head) : null;
  return {
    present: true,
    head: (bd.querySelector('.bdhead') || {}).textContent || '',
    note: (bd.querySelector('.bdnote') || {}).textContent || '',
    provline: (bd.querySelector('.provline') || {}).textContent || '',
    provsrc: [...bd.querySelectorAll('.provsrc')].map(s => s.textContent.trim()),
    provsegs: bd.querySelectorAll('.provseg').length,
    none: !!bd.querySelector('.bdnone'),
    bars: bars.length, cols: cols.length,
    series: [...new Set(bars.map(b => b.dataset.series))].sort(),
    buckets: [...new Set(bars.map(b => b.dataset.bk))].length,
    h: Math.round(bd.getBoundingClientRect().height),
    // the accent's one job on this page is marking what needs him, and
    // nothing in this panel does
    accentUsed: paint.some(c => c.includes(accent)),
    // #487: no native title= — aria-label is the column's named facts
    titles: cols.map(c => c.getAttribute('aria-label') || c.getAttribute('title')),
    // #417 c4
    commitCopy: copy ? copy.textContent.trim() : '',
    copyEllipsis: !!(copyCs && copyCs.textOverflow === 'ellipsis'),
    copyOverflow: !!(copy && copy.scrollWidth > copy.clientWidth + 1),
    // #417 c3 — per-column cap weights (border-top-width) and data-commits
    caps: levels.map(b => ({
      bk: b.dataset.bk,
      commits: +(b.dataset.commits || 0),
      px: parseFloat(getComputedStyle(b).borderTopWidth) || 0,
    })),
    colData: cols.map(c => ({
      open: c.dataset.open, arrived: c.dataset.arrived,
      landed: c.dataset.landed, commits: c.dataset.commits,
      stamp: c.dataset.stamp || '',
      t0: c.dataset.t0, t1: c.dataset.t1,
    })),
    // #499 limit control
    limitPresent: !!lim,
    limitTotal: lim ? +(lim.dataset.total || 0) : 0,
    limitActive: lim ? +(lim.dataset.limit || 0) : 0,
    limitValue: limIn ? limIn.value : null,
    limitReset: !!(limReset),
    headWhiteSpace: headCs ? headCs.whiteSpace : '',
    headDisplay: headCs ? headCs.display : '',
  };
})()`;

const r0 = await p.evaluate(READ);
notes.push(`panel: ${JSON.stringify({ ...r0, titles: r0.titles && r0.titles.length })}`);
const panelOk = !!(r0.present && !r0.none);
ok('the dashboard has a burndown panel (else everything here is vacuous)',
   panelOk);
// Absence-first: when the panel is missing, field reads (provline.trim) threw
// TypeError and the crash sentinel hid it under "threw before finishing".
// Soften every field access; skip motion when the subject never arrived.
if (panelOk) {
// the column count follows the clock (the chart runs to NOW, not to the
// last commit), so it is asserted as a relationship rather than a literal —
// a literal tuned to today is a check with an expiry date nobody can see
ok('...with one column per bucket and three series in each',
   r0.buckets >= 6 && r0.cols === r0.buckets &&
   r0.series.join(',') === 'arrived,landed,open' &&
   r0.bars === r0.cols * 3);
// the numbers, against the PLANTED history rather than against the page.
// `open` is the last snapshot's open set (4), not the arrival count (9) —
// telling those two apart is the entire point of drawing both.
ok('the head states the three totals it is a picture of',
   /\b4 open · 9 arrived · 5 landed · hourly\b/.test(r0.head || ''));
ok('...and a completion GROOMED out of the landed section still counts ' +
   '(#1, #2 and #3 were pruned)', /\b5 landed\b/.test(r0.head || ''));
ok('a column names its bucket and all four numbers (open · flow · commits)',
   !!r0.titles && r0.titles.length === r0.cols &&
   r0.titles.every(t =>
     /\d+ open · \d+ arrived · \d+ landed · \d+ commits?$/.test(t || '')));
ok('the panel spends no accent — nothing in it is waiting on him',
   r0.accentUsed === false);

/* ── #417 c3 + c4, derived from the served series ───────────────────────
   Never compare against a literal pixel height or a hard-coded copy string
   tuned to today's fixture — both expire. Figures come from /data.json;
   the weight mapping is re-derived here the way the renderer does it. */
{
  const served = await (await fetch(`${BASE}/data.json`)).json();
  const bd = served.burndown || {};
  const buckets = bd.buckets || [];
  // precondition: the planted history really produced commit counts, or
  // every c3/c4 check below is vacuous
  const commits = buckets.map(b => b.commits || 0);
  const hasShape = commits.some(c => c > 0) && new Set(commits).size >= 1;
  notes.push(`#417 served commits: total=${bd.commit_total} max=${bd.commit_max} ` +
             `median=${bd.commit_median} quiet=${bd.commit_quiet} ` +
             `series=${JSON.stringify(commits)}`);
  ok('#417 precondition: ledger_series exposed per-bucket commits',
     hasShape && typeof bd.commit_median === 'number' &&
     typeof bd.commit_max === 'number');

  // c4 copy — shortened, no ellipsis, figures match the served summary.
  // Parse the numbers by POSITION in the known template, never substring:
  // "1 empty" must not satisfy a median of 1 when the median was swapped
  // to 999 (a green red-run found that hollow form).
  const copy = r0.commitCopy || '';
  const copyParts = copy.match(
    /^(\d+) median commits\/period · peak (\d+)(?: · (\d+) empty)?$/);
  ok('#417 c4: the figure line carries the served median and peak',
     !!copyParts &&
     +copyParts[1] === bd.commit_median &&
     +copyParts[2] === bd.commit_max &&
     (bd.commit_quiet
       ? +copyParts[3] === bd.commit_quiet
       : !copyParts[3]));
  ok('#417 c4: the figure line does not ellipsise (his condition)',
     r0.copyEllipsis === false && r0.copyOverflow === false);
  // also at mobile width — the long form is what clipped there
  await p.setViewportSize({ width: 390, height: 844 });
  await sleep(400);
  const rMobile = await p.evaluate(READ);
  const mCopy = (rMobile.commitCopy || '').trim();
  const mParts = mCopy.match(
    /^(\d+) median commits\/period · peak (\d+)(?: · (\d+) empty)?$/);
  notes.push(`#417 c4 mobile copy: "${mCopy}" ` +
             `overflow=${rMobile.copyOverflow} ellipsis=${rMobile.copyEllipsis}`);
  ok('#417 c4: …and still does not ellipsise at 390px',
     rMobile.copyOverflow === false &&
     !!mParts &&
     +mParts[1] === bd.commit_median &&
     +mParts[2] === bd.commit_max);
  await p.setViewportSize({ width: 1100, height: 1500 });
  await sleep(400);

  // c3 weight mapping — 0 → 1px, 1..peak → 2..6px linear
  const peak = bd.commit_max || 0;
  const capOf = n => {
    if (n <= 0) return 1;
    if (peak <= 1) return 2;
    return Math.round(2 + 4 * (n - 1) / (peak - 1));
  };
  const caps = r0.caps || [];
  const byBk = Object.fromEntries(buckets.map(b => [String(b.t0), b]));
  const mapped = caps.map(c => {
    const b = byBk[String(c.bk)];
    const expect = b ? capOf(b.commits || 0) : null;
    return { ...c, expect, ok: expect !== null && Math.abs(c.px - expect) < 0.6 };
  });
  notes.push(`#417 c3 caps: ${JSON.stringify(mapped.map(m =>
    ({ c: m.commits, px: m.px, expect: m.expect })))}`);
  ok('#417 c3: every level bar\'s cap weight matches the served commits',
     mapped.length === buckets.length && mapped.every(m => m.ok));
  // edge honesty: zero is distinguishable from one when both exist
  const zeroCap = mapped.find(m => m.commits === 0);
  const oneCap = mapped.find(m => m.commits === 1);
  if (zeroCap && oneCap) {
    ok('#417 c3: zero commits is thinner than one (honest floor)',
       zeroCap.px < oneCap.px);
  } else {
    notes.push('#417 c3: fixture has no zero+one pair — edge check skipped ' +
               '(peak/max still asserted via mapping)');
  }
  const peakCap = mapped.find(m => m.commits === peak && peak > 0);
  if (peakCap) {
    // peak ≤ 1 collapses the range to the floor; only peak ≥ 2 reaches 6px
    const expectPeak = peak <= 1 ? 2 : 6;
    ok('#417 c3: the peak period renders at the top of the weight range',
       Math.abs(peakCap.px - expectPeak) < 0.6);
  }
}

/* the provenance coverage is #217's datum and provenance.mjs owns its
   deep checks; what belongs HERE is the property this fixture exists in:
   every planted entry is unmarked, so the honest split is ALL historical
   unknown and none of it loop's — the exact lie #217 was filed against
   would read `loop 9`. Nine ids were planted as entries. */
ok('...and its provenance is honest about the unknown remainder: every ' +
   'planted entry is unmarked, so none of the nine is the loop\'s',
   /human 0 · loop 0 · historical unknown 9/.test((r0.provline || '').trim()) &&
   r0.provsegs === 3 &&
   (r0.provsrc || []).some(s => /9 first sightings in recorded git history/.test(s)));

/* ── #417 per-column hover: numbers match the served bucket ─────────────
   Assert the FIGURES, not "a tooltip appeared". A tip showing the wrong
   column's numbers would pass any visibility check. The tip is an
   arrival (rundesc idiom): sample mid-frames of opacity. */
{
  const served = await (await fetch(`${BASE}/data.json`)).json();
  const buckets = (served.burndown && served.burndown.buckets) || [];
  // pick the busiest column by commits so the readout is non-trivial
  let pick = 0, bestC = -1;
  buckets.forEach((b, i) => {
    if ((b.commits || 0) > bestC) { bestC = b.commits || 0; pick = i; }
  });
  const want = buckets[pick];
  ok('#417 hover precondition: a level column exists to hover',
     !!want && (r0.colData || []).length === buckets.length);

  // trace tip opacity across the arrival
  const tipTrace = p.evaluate(`new Promise(res => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${pick}];
    if (!col) return res({ err: 'no col' });
    const seen = [];
    const t0 = performance.now();
    let started = false;
    const tip = () => document.querySelector('.bd .bdtip');
    tip() && tip().addEventListener('transitionstart', () => { started = true; },
                                    { once: true });
    // fire hover after the sampler is armed
    requestAnimationFrame(() => {
      col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
    });
    (function step() {
      const t = performance.now() - t0;
      const el = tip();
      const op = el && !el.hidden
        ? parseFloat(getComputedStyle(el).opacity) : 0;
      const text = el && !el.hidden ? (el.textContent || '').trim() : '';
      seen.push({ t, op, text, hidden: !el || el.hidden });
      if (t < 700) requestAnimationFrame(step);
      else res({ seen, started, text: (tip() && !tip().hidden)
        ? (tip().textContent || '').trim() : '' });
    })();
  })`);
  const tr = await tipTrace;
  const finalText = tr.text || '';
  notes.push(`#417 hover col[${pick}] want open=${want.open} arrived=${want.arrived} ` +
             `landed=${want.landed} commits=${want.commits}; tip="${finalText}"; ` +
             `transitionstart=${tr.started}; ops=` +
             `${[...new Set((tr.seen || []).map(s => Math.round(s.op * 100)))].join(',')}`);
  // THE numbers — parse by role, never bare substring. A tip that shows
  // "99 open · 4↑ …" would pass includes("4") against open=4 (green red-run).
  const tipParts = finalText.match(
    /^(\d+) open · (\d+)↑ (\d+)↓ · (\d+) commits?(?: · .+)?$/);
  ok('#417 hover: tip names this column\'s open count',
     !!tipParts && +tipParts[1] === want.open);
  ok('#417 hover: tip names this column\'s commits',
     !!tipParts && +tipParts[4] === (want.commits || 0));
  ok('#417 hover: tip names arrived and landed (the flow)',
     !!tipParts && +tipParts[2] === want.arrived &&
     +tipParts[3] === want.landed);
  // mid-frames: a snap has no opacity strictly between 0 and the end
  const ops = (tr.seen || []).map(s => s.op);
  const endOp = ops.length ? ops[ops.length - 1] : 0;
  const mid = ops.filter(o => o > 0.03 && o < Math.max(0.97, endOp) - 0.03);
  ok('#417 hover: tip arrives (mid-frame opacity, not a snap)',
     endOp >= 0.9 && (mid.length >= 1 || tr.started === true));
  // height still constant across the hover (tip floats)
  const hHover = await p.evaluate(
    `Math.round(document.querySelector('.bd').getBoundingClientRect().height)`);
  ok('#417 hover: panel height unchanged by the tip (floats, no growth)',
     hHover === r0.h);

  // leave so reduced-motion phase starts clean
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')
    .forEach(c => c.dispatchEvent(new PointerEvent('pointerout',
      { bubbles: true, relatedTarget: document.body })))`);
  await sleep(500);
}

/* ── #498: in-progress period names N% elapsed from real bounds ────────
   The inspector (deliberate hover / dwell) is where "period in progress"
   lives. Derive the expected percent from the last bucket's served
   t0/step and wall clock — never a literal tuned to today's fixture.
   Assert the gap: last period must still be open (t1 > now). */
{
  const served = await (await fetch(`${BASE}/data.json`)).json();
  const buckets = (served.burndown && served.burndown.buckets) || [];
  const step = (served.burndown && served.burndown.step) || 0;
  const last = buckets[buckets.length - 1];
  const nowSec = Date.now() / 1000;
  const t0 = last ? last.t0 : 0;
  const t1 = t0 + step;
  ok('#498 precondition: last period is still open (t1 > now)',
     !!last && step > 0 && t1 > nowSec);
  const expectPct = Math.max(0, Math.min(100,
    Math.round(100 * (nowSec - t0) / step)));
  notes.push(`#498 expect: t0=${t0} t1=${t1} now≈${nowSec.toFixed(1)} ` +
             `→ ${expectPct}% elapsed; buckets=${buckets.length}`);
  const lastIdx = buckets.length - 1;
  // dwell until the inspector arrives
  const insp = await p.evaluate(`new Promise(res => {
    const col = document.querySelectorAll('.bdnet .bdcol[data-open]')[${lastIdx}];
    if (!col) return res({ err: 'no col' });
    col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
    const t0 = performance.now();
    (function step() {
      const el = document.querySelector('.bd .bdinsp');
      if (el && !el.hidden && parseFloat(getComputedStyle(el).opacity) >= 0.9) {
        return res({
          text: (el.innerText || '').trim(),
          lines: (el.innerText || '').trim().split('\\n').map(s => s.trim()),
          t0: col.dataset.t0, t1: col.dataset.t1,
          now: Date.now() / 1000,
        });
      }
      if (performance.now() - t0 > 2000) return res({
        text: el && !el.hidden ? (el.innerText || '').trim() : '',
        lines: el && !el.hidden
          ? (el.innerText || '').trim().split('\\n').map(s => s.trim()) : [],
        t0: col.dataset.t0, t1: col.dataset.t1,
        now: Date.now() / 1000, timedOut: true,
      });
      requestAnimationFrame(step);
    })();
  })`);
  const covLine = (insp.lines && insp.lines[2]) || '';
  // re-derive at the moment the inspector was read (clock advanced during dwell)
  const gotT0 = +(insp.t0 || t0), gotT1 = +(insp.t1 || t1);
  const gotNow = insp.now || nowSec;
  const gotSpan = gotT1 - gotT0;
  const gotExpect = gotSpan > 0
    ? Math.max(0, Math.min(100, Math.round(100 * (gotNow - gotT0) / gotSpan)))
    : -1;
  const m = covLine.match(/(\d+)%\s*elapsed/);
  notes.push(`#498 insp cov="${covLine}" expect=${gotExpect}% got=` +
             `${m ? m[1] : 'none'} timedOut=${!!insp.timedOut}`);
  ok('#498: coverage line says period in progress',
     /period in progress/.test(covLine));
  ok('#498: coverage line carries N% elapsed from real period bounds',
     !!m && Math.abs(+m[1] - gotExpect) <= 1);
  // leave
  await p.evaluate(`document.querySelectorAll('.bdnet .bdcol[data-open]')
    .forEach(c => c.dispatchEvent(new PointerEvent('pointerout',
      { bubbles: true, relatedTarget: document.body })))`);
  await sleep(500);
}

/* ── #499: limit control — presence vs DEFAULT 28, not active limit ─────
   Presence is totalN > 28 (his "when we have more than 28 elements"),
   regardless of the active limit. That keeps the control up under
   limit=0 (all) so there is an in-UI recovery path. Slice still follows
   the active limit. Short fixture first (absent); then extend history
   past 28 hourly buckets for the present / all-mode / slice cases. */
{
  const served0 = await (await fetch(`${BASE}/data.json`)).json();
  const shortN = ((served0.burndown && served0.burndown.buckets) || []).length;
  const target = served0.target;
  ok('#499 precondition: short fixture has buckets, fewer than default 28',
     shortN >= 2 && shortN <= 28);
  ok('#499: limit control is absent when totalN ≤ 28 (any active limit)',
     r0.limitPresent === false);
  notes.push(`#499 short: totalN=${shortN} limitPresent=${r0.limitPresent} h=${r0.h}`);
  const hAbsent = r0.h;

  // Extend the planted history ~40h before T0 so hourly yields >28 buckets.
  // Presence precondition is derived from the PAGE after forcing hourly —
  // never a literal bucket count tuned to today's plant. Content must
  // change each commit (git refuses identical trees); a trailing note is
  // enough — the series span is the commit timestamps on the ledger path.
  for (let h = 40; h >= 1; h--) {
    const at = T0 - h * 3600;
    writeFileSync(join(DIR, '.dreamwork', 'tasks.md'),
      ledger([6, 7, 8, 9], [4, 5]) + `\n<!-- span ${h} -->\n`);
    git(['add', '.dreamwork/tasks.md'], at);
    git(['commit', '-q', '-m', `span ${at}`], at);
  }
  await p.evaluate(t => {
    localStorage.removeItem('dw:burn-limit:' + t);   // default 28
  }, target);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1400);
  // Force hourly via the real cycle control (localStorage burn-step is not
  // read on first paint — loadBurnStepPref runs before data.target is set).
  await p.evaluate(async () => {
    for (let i = 0; i < 8; i++) {
      if ((data && data.burndown && data.burndown.step) === 3600) return;
      const b = document.querySelector('.bdstep');
      if (!b) return;
      b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 450));
    }
  });
  await sleep(600);
  const pageMeta = await p.evaluate(() => ({
    step: data && data.burndown && data.burndown.step,
    totalN: ((data && data.burndown && data.burndown.buckets) || []).length,
  }));
  const totalN = pageMeta.totalN;
  ok('#499 precondition: extended series has more than 28 buckets (hourly)',
     pageMeta.step === 3600 && totalN > 28);
  notes.push(`#499 extended: totalN=${totalN} step=${pageMeta.step}`);

  const rDef = await p.evaluate(READ);
  notes.push(`#499 default-28 over long series: present=${rDef.limitPresent} ` +
             `cols=${rDef.cols} value=${rDef.limitValue} total=${rDef.limitTotal} ` +
             `h=${rDef.h} (absent-state h was ${hAbsent})`);
  ok('#499: control is present when totalN > 28 (default rule)',
     rDef.limitPresent === true && rDef.limitReset === true);
  ok('#499: control reports the full series length (not the sliced count)',
     rDef.limitTotal === totalN);
  ok('#499: default slices to 28 columns',
     rDef.cols === 28 && rDef.limitValue === '28');
  // fixed-height premise: panel height with control == without
  ok('#499: panel height is unchanged with the control visible (#417)',
     rDef.h === hAbsent);
  ok('#499: head stays one nowrap flex line (no wrap, no second row)',
     rDef.headDisplay === 'flex');

  // force a lower limit → still present (totalN > 28), fewer columns
  const forceLim = 12;
  ok('#499 precondition: forced limit is below totalN and below default',
     forceLim < totalN && forceLim < 28);
  await p.evaluate(({ t, lim }) => {
    localStorage.setItem('dw:burn-limit:' + t, String(lim));
  }, { t: target, lim: forceLim });
  // no reload needed — apply via the live control if present, else set pref
  // and rebuild through a step-noop isn't free; reload + re-force hourly
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1200);
  await p.evaluate(async () => {
    for (let i = 0; i < 8; i++) {
      if ((data && data.burndown && data.burndown.step) === 3600) return;
      const b = document.querySelector('.bdstep');
      if (!b) return;
      b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 450));
    }
  });
  await sleep(500);
  const rLim = await p.evaluate(READ);
  notes.push(`#499 forced lim=${forceLim}: present=${rLim.limitPresent} ` +
             `cols=${rLim.cols} value=${rLim.limitValue}`);
  ok('#499: control stays present under a non-default limit (totalN > 28)',
     rLim.limitPresent === true);
  ok('#499: chart shows exactly the active limit columns',
     rLim.cols === forceLim);
  ok('#499: input value is the active limit',
     rLim.limitValue === String(forceLim));

  // limit=0 (all/max) — THE recovery case: every column shown AND control
  // still present so he can dial back. Presence is vs 28, not vs active.
  await p.evaluate(() => {
    const inp = document.querySelector('.bdlimit-in');
    if (!inp) return;
    inp.value = '0';
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(800);
  const rAll = await p.evaluate(READ);
  notes.push(`#499 all/max (0): present=${rAll.limitPresent} cols=${rAll.cols} ` +
             `value=${rAll.limitValue}`);
  ok('#499: <=0 means all/max — every column shown',
     rAll.cols === totalN);
  ok('#499: limit=0 recovery — control STILL present when totalN > 28',
     rAll.limitPresent === true && rAll.limitValue === '0');

  // ⟳ reset → default 28; control still present (totalN > 28)
  await p.evaluate(() => {
    const b = document.querySelector('.bdlimit-reset');
    if (b) b.click();
  });
  await sleep(800);
  const rReset = await p.evaluate(READ);
  notes.push(`#499 after reset: present=${rReset.limitPresent} cols=${rReset.cols} ` +
             `value=${rReset.limitValue}`);
  ok('#499: ⟳ reset restores default 28 columns; control still present',
     rReset.limitPresent === true &&
     rReset.cols === 28 &&
     rReset.limitValue === '28');

  // invalid input refused quietly
  await p.evaluate(({ t, lim }) => {
    localStorage.setItem('dw:burn-limit:' + t, String(lim));
  }, { t: target, lim: forceLim });
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1200);
  await p.evaluate(async () => {
    for (let i = 0; i < 8; i++) {
      if ((data && data.burndown && data.burndown.step) === 3600) return;
      const b = document.querySelector('.bdstep');
      if (!b) return;
      b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 450));
    }
  });
  await sleep(500);
  await p.evaluate(() => {
    const inp = document.querySelector('.bdlimit-in');
    if (!inp) return;
    inp.value = 'abc';
    inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(600);
  const rBad = await p.evaluate(READ);
  notes.push(`#499 invalid: present=${rBad.limitPresent} value=${rBad.limitValue} ` +
             `cols=${rBad.cols}`);
  ok('#499: invalid input is refused quietly (prior limit kept)',
     rBad.limitPresent === true &&
     rBad.limitValue === String(forceLim) &&
     rBad.cols === forceLim);

  // clear prefs for the rest of the guard (auto step, default limit)
  await p.evaluate(t => {
    localStorage.removeItem('dw:burn-limit:' + t);
    localStorage.removeItem('dw:burn-step:' + t);
  }, target);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1200);
  const rClean = await p.evaluate(READ);
  if (rClean.present) {
    r0.h = rClean.h;
    r0.head = rClean.head;
    r0.cols = rClean.cols;
    r0.bars = rClean.bars;
    r0.buckets = rClean.buckets;
    r0.colData = rClean.colData;
    r0.caps = rClean.caps;
    r0.limitPresent = rClean.limitPresent;
  }
  notes.push(`#499 cleaned: h=${r0.h} cols=${r0.cols} limitPresent=${r0.limitPresent}`);
}
} else {
  notes.push('panel absent after load — static field checks and motion skipped');
}

/* ── the motion ───────────────────────────────────────────────────────────
   Traced per frame and bounded to the interaction. `regroupBars` runs on a
   tick, so the window has to cover one tick and stop well before the next
   (2000ms) — a guard that watches longer sees the following tick supply the
   movement it was asserting, which is how #191 stayed green over a teleport
   for a day. */
const TRACE = ms => `new Promise(res => {
  /* EVERY ELEMENT IS RE-QUERIED PER FRAME. The tick replaces the dashboard
     through innerHTML, so a reference captured before it is DETACHED after
     it — and getBoundingClientRect on a detached node returns zeros, which
     reads as "the panel height changed" and "the panel below moved". The
     first version of this guard held those references and reported two
     failures that were entirely its own. */
  const watched = [...document.querySelectorAll('.bd .bdbar[data-bk]')]
    .map(b => b.dataset.bk + '/' + b.dataset.series);
  const seen = [];
  const t0 = performance.now();
  (function step() {
    const t = performance.now() - t0;
    const now = {};
    document.querySelectorAll('.bd .bdbar[data-bk]').forEach(b => {
      now[b.dataset.bk + '/' + b.dataset.series] =
        b.getBoundingClientRect().height;
    });
    const bd = document.querySelector('.bd');
    const below = document.querySelector('#status');
    seen.push({ t, now,
      panelH: bd ? bd.getBoundingClientRect().height : -1,
      below: below ? below.getBoundingClientRect().top + window.scrollY : -1 });
    if (t < ${ms}) requestAnimationFrame(step); else res({ seen, watched });
  })();
})`;
/* AT A TENTH OF A PIXEL, not at whole pixels. A height eased over 850ms
   inside a 34px track moves in fractions, and rounding to integers reports a
   perfectly clean travel of 2.1px as "two distinct positions" — i.e. as a
   snap. That is what the first version of this guard did, and the bug it
   found was its own. The travel is also made LARGE below, so the assertion
   does not depend on this resolution being generous. */
const distinct = xs => new Set(xs.map(v => Math.round(v * 10))).size;
/* between() — frame-rate-free travel (transitions.md, dreamfade.mjs).
   `positions >= 8` reddened under load with 3–7 distinct heights that still
   travelled; zero-versus-some part-way is the snap/travel distinction. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}
/* the bar that moved MOST across the window, and how it got there. Named by
   key, never by index: three series share a bucket and two bars share a
   column, so a bucket alone is not an identity. */
function busiest({ seen, watched }) {
  let best = null;
  for (const k of watched) {
    const hs = seen.map(s => s.now[k]).filter(v => v !== undefined);
    if (hs.length < 5) continue;
    const moved = Math.abs(hs.at(-1) - hs[0]);
    if (!best || moved > best.moved)
      best = { k, moved, positions: distinct(hs),
               partway: between(hs, hs[0], hs.at(-1)), hs };
  }
  return best;
}

/* A ledger commit lands while the page is open, and the tick brings it. The
   real path: a real commit, the real /mtime poll, the real re-render. */
async function ledgerLands(page, ms = 1500) {
  const t = page.evaluate(TRACE(ms));
  await sleep(60);
  // TEN arrivals at once, deliberately: this bucket's arrival bar goes to
  // the top of its track and rescales every other one, so the travel under
  // test is tens of pixels rather than the two a one-task commit produces.
  // A guard whose subject moves 2px is measuring its own rounding.
  commit([6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
         [4, 5, 6], T0 + 6 * 3600);
  return await t;
}

if (panelOk) {
  // the panel BEFORE, so the change is real rather than assumed
  const before = await p.evaluate(READ);
  const tr = await ledgerLands(p, 4200);       // one poll (2s) plus the travel
  const b = busiest(tr);
  const after = await p.evaluate(READ);
  const panelHs = distinct(tr.seen.map(s => s.panelH));
  const belows = distinct(tr.seen.map(s => s.below));
  notes.push(`ledger lands: head "${(before.head || '').trim()}" -> ` +
             `"${(after.head || '').trim()}"; busiest bar ${b ? b.k : 'none'} moved ` +
             `${b ? b.moved.toFixed(1) : 0}px over ${b ? b.positions : 0} ` +
             `distinct heights (${b ? b.partway : 0} part-way); panel height values ` +
             `${JSON.stringify([...new Set(tr.seen.map(s => Math.round(s.panelH)))])}; ` +
             `panel-below values ` +
             `${JSON.stringify([...new Set(tr.seen.map(s => Math.round(s.below)))])}`);
  ok('a ledger commit really changed the panel (else the rest is vacuous)',
     before.head !== after.head && /\b19 arrived\b/.test(after.head || ''));
  ok('...and a bar whose value changed is displaced at all', !!b && b.moved >= 8);
  // THE ASSERTION. A snap has zero frames strictly between the ends.
  ok('...and it TRAVELS to its new height rather than snapping',
     !!b && b.partway >= 1);
  /* THE PREMISE, measured rather than asserted in prose. Bar motion needs no
     FLIP over the panels below only because the panel's own height is a
     constant — every track height is fixed in CSS. If that ever stops being
     true the bars start dragging four panels with them and nothing else
     would notice. */
  ok('...while the panel\'s own height never changes, which is why the bars ' +
     'may animate at all', panelHs === 1);
  ok('...so nothing below the panel moves', belows === 1);
  /* AND THE CHART IS STILL THERE WHEN THE ANIMATION ENDS. Every other travel
     on this page clears its inline height at the end, because those elements
     get their size from layout; a bar gets its size from an inline
     `height:N%` the renderer wrote, so clearing it leaves the bar at ZERO.
     The first version of this panel collapsed the whole chart to its 2px
     rules after every animation and stayed collapsed until the next
     re-render replaced the nodes — #198's shape, a permanent bug with a
     short unreliable lifetime, laundered by something unrelated. So the
     check is made AFTER the inline heights are restored (CARD_MS + 150) and
     BEFORE any tick can put fresh nodes in. */
  await sleep(1100);
  const settled = await p.evaluate(`(() => {
    const bars = [...document.querySelectorAll('.bd .bdbar[data-bk]')];
    return { n: bars.length,
             pct: bars.filter(b => /%$/.test(b.style.height)).length,
             tall: bars.filter(b => b.getBoundingClientRect().height > 3).length,
             px: bars.filter(b => /px$/.test(b.style.height)).length };
  })()`);
  notes.push(`settled after the travel: ${JSON.stringify(settled)}`);
  ok('...and when the travel ends the bars still have a height at all',
     settled.n > 0 && settled.pct === settled.n && settled.px === 0);
  ok('...so the chart did not collapse to its rules', settled.tall >= 4);
}

/* ── a tick that changes no numbers moves nothing ─────────────────────────
   NOT a test of #151's gate, and the distinction was learned by injecting.
   Deleting the gate reddens nothing here, because a bar's height is a pure
   function of the series: with the gate gone `regroupBars` still early-
   returns on every equal height. The gate is an optimisation on this panel
   rather than a behaviour, it is stated as one in `watch.py`, and it has no
   check — a check that cannot fail is worse than none.

   What this DOES prove is the user-visible property: a re-render that
   changes no number must not disturb the chart. It is the check that found
   the collapse bug above, by measuring the bars at 2px before the tick it
   was nominally about. The page is made to re-render by a /command, which
   appends to watch-events.log — watched, and rendering nothing. */
if (panelOk) {
  // CARD_MS + 150 is when regroupBars clears its inline heights; tracing
  // before that measures the previous phase's animation and blames the tick
  await sleep(1400);
  const t = p.evaluate(TRACE(1200));
  await sleep(60);
  await p.evaluate(`fetch('/command', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'add-idea', text: 'burndown guard tick' }) })`);
  await p.evaluate(`tick()`);
  const tr = await t;
  const b = busiest(tr);
  const moved = tr.watched.map(k => {
    const hs = tr.seen.map(s => s.now[k]).filter(v => v !== undefined);
    return distinct(hs);
  });
  const noisy = tr.watched.map(k => [k, tr.seen.map(s => s.now[k])
      .filter(v => v !== undefined)])
    .filter(([, hs]) => distinct(hs) > 1)
    .map(([k, hs]) => `${k}=${hs.map((v, i) =>
        `${Math.round(tr.seen[i].t)}:${Math.round(v * 10) / 10}`)
        .filter((_, i) => i === 0 || Math.round(hs[i - 1] * 10) !== Math.round(hs[i] * 10))
        .join(' ')}`);
  notes.push(`quiet tick: busiest ${b ? b.k : 'none'} moved ` +
             `${b ? b.moved.toFixed(1) : 0}px; heights per bar ` +
             `${[...new Set(moved)].sort().join(',')}; noisy: ` +
             `${noisy.slice(0, 4).join(' | ') || 'none'}`);
  ok('a tick that does not change the ledger really did re-render the page ' +
     '(else this proves nothing)',
     await p.evaluate(`document.querySelectorAll('.bd .bdbar').length > 0`));
  ok('...and disturbs no bar: they arrive with the layout, at their height',
     moved.every(m => m <= 1));
  await p.screenshot({ path: `${OUT}/burndown.png`, fullPage: false });
}

// ── reduced motion: timing changes, function does not ─────────────────────
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1500 },
                                    reducedMotion: 'reduce' });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(rp, '.bd .bdbar[data-bk], .bdnone', 15000);   // #507 render readiness
  await sleep(400);
  const before = await rp.evaluate(READ);
  const t = rp.evaluate(TRACE(4200));
  await sleep(60);
  commit([6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
         [4, 5, 6, 7], T0 + 7 * 3600);
  const tr = await t;
  const after = await rp.evaluate(READ);
  const served = await (await fetch(`${BASE}/data.json`)).json();
  notes.push(`reduced served: ${JSON.stringify(
    { ...served.burndown, buckets: (served.burndown.buckets || []).length })}`);
  const b = busiest(tr);
  notes.push(`reduced: head "${(before.head || '').trim()}" -> "${(after.head || '').trim()}"; ` +
             `busiest ${b ? b.k : 'none'} took ${b ? b.positions : 0} heights ` +
             `(${b ? b.partway : 0} part-way)`);
  ok('reduced motion: the numbers still arrive (function is intact)',
     before.head !== after.head && /\b21 arrived\b/.test(after.head || ''));
  ok('reduced motion: ...in one step, with no travel', !!b && b.partway === 0);
  // #417 hover under reduced motion: function intact, no travel
  {
    const tipTr = await rp.evaluate(`new Promise(res => {
      const col = document.querySelector('.bdnet .bdcol[data-open]');
      if (!col) return res({ err: 'no col' });
      const seen = [];
      const t0 = performance.now();
      requestAnimationFrame(() => {
        col.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
      });
      (function step() {
        const t = performance.now() - t0;
        const el = document.querySelector('.bd .bdtip');
        const op = el && !el.hidden
          ? parseFloat(getComputedStyle(el).opacity) : 0;
        seen.push(op);
        if (t < 500) requestAnimationFrame(step);
        else res({
          seen,
          text: el && !el.hidden ? (el.textContent || '').trim() : '',
          open: col.dataset.open,
          commits: col.dataset.commits,
        });
      })();
    })`);
    const mid = (tipTr.seen || []).filter(o => o > 0.03 && o < 0.97);
    notes.push(`#417 reduced hover: text="${tipTr.text}" mid=${mid.length} ` +
               `ops=${[...new Set((tipTr.seen || []).map(o =>
                 Math.round(o * 100)))].join(',')}`);
    const rmParts = (tipTr.text || '').match(
      /^(\d+) open · (\d+)↑ (\d+)↓ · (\d+) commits?(?: · .+)?$/);
    ok('#417 reduced motion: hover still names open and commits (function)',
       !!rmParts &&
       +rmParts[1] === +tipTr.open &&
       +rmParts[4] === +tipTr.commits);
    ok('#417 reduced motion: hover tip does not travel (timing only)',
       mid.length === 0);
  }
  await rp.screenshot({ path: `${OUT}/burndown-reduced.png`, fullPage: false });
  await ctx.close();
}

/* ── the other kind of nothing ────────────────────────────────────────────
   A target with no versioned ledger is the ORDINARY case for a project that
   is not this one, and it must render a reading rather than an empty space —
   a panel that draws nothing is indistinguishable from a loop that has done
   nothing. Its own target and its own server, because the state is a
   property of the repository. */
{
  const port2 = await freePort();
  const DIR2 = join(OUT, 'bare');
  rmSync(DIR2, { recursive: true, force: true });
  cpSync('dev/capture/fixture', DIR2, { recursive: true });
  const srv2 = await serveVerified(DIR2, port2);
  try {
    const d = await (await fetch(`http://127.0.0.1:${port2}/data.json`)).json();
    const bp = await br.newPage({ viewport: { width: 1100, height: 1200 } });
    await bp.goto(`http://127.0.0.1:${port2}/`, { waitUntil: 'networkidle' });
    // #507: wait for the panel (no-ledger state) to render, not a fixed sleep.
    await waitFor(bp, '.bd', 15000);
    const r = await bp.evaluate(READ);
    notes.push(`no ledger: ${JSON.stringify({ none: r.none, head: r.head,
                                              bars: r.bars })}`);
    ok('a project with no versioned ledger still renders the panel',
       r.present && r.none);
    ok('...saying which kind of nothing, and drawing no bars',
       r.bars === 0 && /not a git checkout|nothing to chart/.test(
         await bp.evaluate(`(document.querySelector('.bdnone')||{}).textContent||''`)));
    await bp.close();
  } finally {
    try { srv2.kill(); } catch (e) {}
  }
}

ok('no page errors', errs.length === 0);
await br.close();
try { srv.kill(); } catch (e) {}
finish();
