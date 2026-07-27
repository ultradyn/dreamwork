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
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
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
          'context on the first target',
  traceWindow: '4.2s per motion capture — one /mtime poll (2s) plus the bar ' +
               'travel — deliberately stopping before the next tick could ' +
               'supply the motion being asserted (the regroup.mjs trap); ' +
               '1.2s for the quiet-tick capture; panel-height and ' +
               'panel-below premises measured across the same 4.2s window'
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
commit([1, 2, 3], [], T0);
commit([2, 3, 4, 5], [1], T0 + 3600);
commit([3, 4, 5, 6, 7, 8], [1, 2], T0 + 2 * 3600);
commit([4, 5, 6, 7, 8], [2, 3], T0 + 3 * 3600);
commit([5, 6, 7, 8, 9], [3, 4], T0 + 4 * 3600);
commit([6, 7, 8, 9], [4, 5], T0 + 5 * 3600);   // #1..#3 groomed away

const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);
const BASE = `http://127.0.0.1:${PORT}`;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
  notes.push(`served burndown: ${JSON.stringify(
    { ...d.burndown, buckets: (d.burndown.buckets || []).length })}`);
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1500 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);

const READ = `(() => {
  const bd = document.querySelector('.bd');
  if (!bd) return { present: false };
  const bars = [...bd.querySelectorAll('.bdbar[data-bk]')];
  const cols = [...bd.querySelectorAll('.bdnet .bdcol')];
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent)';
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  const paint = bars.map(b => {
    const cs = getComputedStyle(b);
    return cs.backgroundColor + '|' + cs.borderTopColor;
  });
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
    titles: cols.map(c => c.getAttribute('title')),
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
ok('a column names its bucket and all three numbers',
   !!r0.titles && r0.titles.length === r0.cols &&
   r0.titles.every(t => /arrived · \d+ landed · \d+ open$/.test(t || '')));
ok('the panel spends no accent — nothing in it is waiting on him',
   r0.accentUsed === false);
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
  await sleep(1200);
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
  const srv2 = spawn('python3', ['watch.py', '--target', DIR2,
                                 '--port', String(port2)], { stdio: 'ignore' });
  try {
    await sleep(2500);
    const d = await (await fetch(`http://127.0.0.1:${port2}/data.json`)).json();
    if (d.target !== DIR2) throw new Error(`:${port2} is serving ${d.target}`);
    const bp = await br.newPage({ viewport: { width: 1100, height: 1200 } });
    await bp.goto(`http://127.0.0.1:${port2}/`, { waitUntil: 'networkidle' });
    await sleep(1000);
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
