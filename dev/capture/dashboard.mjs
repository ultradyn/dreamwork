/* The dashboard's own sections — the ones whose behaviour is not visible in
   generated source and not reachable from the shared fixture.

     #132  a commit row's age is at SECONDS resolution, so it has to change
           every second. The interesting claim is not the format, it is WHERE
           the change happens: a targeted text write into a node that already
           exists, never a re-render. Routing it through the tick's innerHTML
           swap would re-run the regroup (#113) and re-carry his half-typed
           text (#118) sixty times a minute, forever, to move one digit.
     #151  five rows, fixed height, and a NEW COMMIT arrives as one gesture:
           the bottom row dreams away, the new top row eases in, the four
           between travel down one. On a new SHA — never on a tick.

   THIS GUARD BUILDS ITS OWN TARGET, health.mjs-style, and for a reason worth
   knowing: `dev/capture/fixture` is not a git repository, so `git_tail`
   returns [] there and the commits panel is EMPTY on the shared server every
   other guard uses. Every check below would have passed vacuously on it.
   So this one inits a repo and plants commits at known ages — which is also
   the only way to reach the 100-day boundary at all.

   It picks its own EPHEMERAL port and ignores the one it is handed — see
   below. usage: node dashboard.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, rmSync, cpSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { createServer } from 'node:http';
import { join } from 'node:path';
const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
/* An ephemeral port, not the one passed in. This guard runs its own server,
   so a fixed port would be shared mutable state with no owner — and where
   that can be REMOVED rather than owned, remove it (dreamhub, 2026-07-25,
   after its guard attached to a neighbouring dreamer's watch instance and
   asserted 23 checks against a stranger's page). The argument is accepted
   and ignored so the runner's call shape stays uniform. */
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
/* Report from an exit handler, not from the tail. A guard that throws part
   way through prints NOTHING, and a reader counting FAIL lines then sees a
   crash as a clean run — which is how three injections here read as "the
   check proves nothing" when the check had never been reached. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

// ── a target with a real history, at ages chosen to hit every format ───────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const NOW = Math.floor(Date.now() / 1000);
const git = (args, at) => execFileSync('git', ['-C', DIR, ...args], {
  stdio: 'ignore',
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x',
         GIT_AUTHOR_DATE: `@${at || NOW} +0000`,
         GIT_COMMITTER_DATE: `@${at || NOW} +0000` },
});
const commit = (msg, agoSec) =>
  git(['commit', '-q', '--allow-empty', '-m', msg], NOW - agoSec);
git(['init', '-q']);
// oldest first. The top five are what the panel shows; `off-panel` proves the
// cut, and each of the five names the format it is here to exercise.
const D = 86400;
commit('off-panel: this one must not be shown', 400 * D);
// #385: 100 days is no longer a three-digit day count — the week rung takes
// it (`14w 02d`). The subject still names the boundary so the assertion below
// can find the row.
commit('chore: the hundred-day boundary, which is now weeks not three-digit days', 100 * D + 7 * 3600);
commit('feat: the days-and-hours row', 3 * D + 7 * 3600);
commit('dreamwork(maintain:docs): the hours-and-minutes row, and a maintenance marker', 2 * 3600 + 14 * 60);
commit('fix: the minutes-and-seconds row, with a deliberately very long subject that must ellipsise rather than wrap, because a wrapped row would change the panel height and #151 rests on it not doing that', 323);
commit('feat: the newest row, seconds old', 12);

/* #428/#461: serveVerified polls /data.json and proves the responder is ours
   — replacing spawn + sleep(2500) + a hand-rolled identity check, which under
   load let python outlast the sleep and threw ECONNREFUSED over a correct
   server. */
const BASE = `http://127.0.0.1:${PORT}`;
const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 1100 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await waitFor(p, '.git .commit[data-sha]');   // #428 render readiness (the commits panel)

const READ = `[...document.querySelectorAll('.git .commit[data-sha]')].map(r => ({
  sha: r.dataset.sha,
  sub: r.querySelector('.gsub').textContent,
  age: r.querySelector('.age[data-ct]').textContent,
  h: Math.round(r.getBoundingClientRect().height * 10) / 10,
  top: Math.round(r.getBoundingClientRect().top),
  maint: r.classList.contains('maint'),
}))`;
const rows = await p.evaluate(READ);
notes.push('rows:\n' + rows.map(r => `  ${r.age}  ${r.sub.slice(0, 44)}`).join('\n'));

// ── #151, the static half: five rows, one height, no jumping ──────────────
ok('the panel shows five commits', rows.length === 5);
ok('...the sixth is cut, not shown', !rows.some(r => /off-panel/.test(r.sub)));
ok('...every row is the same height', rows.length > 0 &&
   new Set(rows.map(r => r.h)).size === 1);
/* The line above is weak on its own and is kept only as a floor: deleting the
   explicit `height` leaves every row the same height anyway, because
   `nowrap` is what actually stops a subject wrapping. The ellipsis check
   below is the one that bites, and the panel-height check further down is
   the one that states the requirement ("layout cannot jump"). Said out loud
   because a reader would otherwise take the trio for one idea checked
   three times. */
const long = await p.evaluate(`(() => {
  const el = [...document.querySelectorAll('.git .gsub')]
    .find(e => /ellipsise rather than wrap/.test(e.textContent));
  const cs = el && getComputedStyle(el);
  return el ? { over: el.scrollWidth > el.clientWidth,
                ws: cs.whiteSpace, ov: cs.textOverflow } : null;
})()`);
notes.push(`long subject: ${JSON.stringify(long)}`);
ok('a long subject ellipsises instead of wrapping',
   !!long && long.ws === 'nowrap' && long.ov === 'ellipsis' && long.over);
ok('the panel is near the top — above dreams', await p.evaluate(`(() => {
  const labels = [...document.querySelectorAll('#sections > .label')]
    .map(l => l.textContent);
  const c = labels.findIndex(t => /^commits$/.test(t));
  const d = labels.findIndex(t => /^dreams/.test(t));
  return c >= 0 && d >= 0 && c < d;
})()`));
ok('a maintenance commit still wears the accent', rows.some(r => r.maint));

/* the enter-snap rule, asserted as an invariant rather than trusted. It has
   to beat whatever the arriving element's own component declares, and it did
   not: `.qa` states the same transitions later in the sheet at the same
   specificity, so a card carrying `.dreamin` kept its 0.85s transition and
   never left opacity 1. Every arrival on this page has been a pop-in since
   #104, and no guard noticed because none of them traced an ARRIVAL. Checked
   here for both lists, so the next component to declare a transition cannot
   quietly take it back. */
{
  const snapped = await p.evaluate(`(() => {
    const out = {};
    for (const [k, sel] of [['card', '.qa[data-qid]'],
                            ['commit', '.git .commit[data-sha]'],
                            ['crumb', '.crumb']]) {
      const el = document.querySelector(sel);
      if (!el) { out[k] = null; continue; }
      el.classList.add('dreamin');
      const cs = getComputedStyle(el);
      out[k] = { dur: cs.transitionDuration, op: cs.opacity };
      el.classList.remove('dreamin');
    }
    return out;
  })()`);
  notes.push(`dreamin: ${JSON.stringify(snapped)}`);
  const snaps = v => v && /^0s(, 0s)*$/.test(v.dur) && v.op === '0';
  ok('`.dreamin` snaps a commit row to nothing before it eases in',
     snaps(snapped.commit));
  ok('...and a question card, which it never did before (#151 found this)',
     snaps(snapped.card));
  ok('...and a crumb, which it always did', snaps(snapped.crumb));
}

// ── #132 / #385: the format, at every boundary it has ─────────────────────
// Exactly two digits per unit — his invariant. The old form allowed `\d{2,}`
// on the big unit so a three-digit day count at 100 days still "passed" as
// two units; #385 forbids that by climbing to weeks/years instead.
const AGE = /^(\d{2})([ywdhm]) (\d{2})([wdhms]) ago$/;
ok('every age is two units, two digits each',
   rows.length === 5 && rows.every(r => AGE.test(r.age)));
const aged = s => (rows.find(r => new RegExp(s).test(r.sub)) || {}).age;
notes.push(`ages: ${rows.map(r => r.age).join(' | ')}`);
// under a minute still reads as two units, so the column never changes width
ok('seconds old reads `00m NNs ago`', /^00m \d{2}s ago$/.test(aged('newest row')));
ok('minutes reads `05m NNs ago`', /^05m \d{2}s ago$/.test(aged('minutes-and-seconds')));
ok('hours reads `02h 14m ago`', aged('hours-and-minutes') === '02h 14m ago');
ok('days reads `03d 07h ago`', aged('days-and-hours') === '03d 07h ago');
// #385: 100 days + 7h is 14w 02d, not 100d 07h. The live defect was the
// three-digit day count; the discriminating check is that the day unit is
// GONE from this row, not merely that some age string is present.
ok('past 100 days uses weeks (two digits), not a three-digit day count (#385)',
   aged('hundred-day') === '14w 02d ago');

/* ── #132, the load-bearing half ──────────────────────────────────────────
   The age changes every second, and it does it WITHOUT the node being
   replaced. Both halves are needed and neither is enough:
     - text alone would pass on an implementation that re-rendered the panel
       once a second, which is precisely the thing #132's ledger line forbids;
     - identity alone would pass on an age that never moved.
   Node identity is carried by an expando, which no re-render can preserve. */
{
  const seen = await p.evaluate(async () => {
    const row = () => document.querySelector('.git .commit[data-sha]');
    const el0 = row(); el0.__guardMark = 'kept';
    const t0 = el0.querySelector('.age').textContent;
    await new Promise(r => setTimeout(r, 2400));
    const el1 = row();
    return { same: el1.__guardMark === 'kept' && el1 === el0,
             t0, t1: el1.querySelector('.age').textContent };
  });
  notes.push(`ticking age: ${seen.t0} -> ${seen.t1} (same node: ${seen.same})`);
  ok('the age advances every second', seen.t0 !== seen.t1);
  ok('...by writing text into the node that was already there',
     seen.same === true);
}

/* ...and it survives a re-render. Under #505 the row is KEPT by data-sha
   (not replaced); ages() still owns the text and must not blank it. The
   vacuity proof is __dwViewRenderGen advancing, not node identity change. */
{
  const after = await p.evaluate(async () => {
    const row = () => document.querySelector('.git .commit[data-sha]');
    const el0 = row(); el0.__guardMark = 'kept';
    const gen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'dashboard guard tick' }) });
    // watch the age never go blank while the tick mutates the DOM under it
    let blank = 0;
    const t0 = performance.now();
    await new Promise(res => (function step() {
      const a = document.querySelector('.git .commit .age');
      if (a && !a.textContent.trim()) blank++;
      if (performance.now() - t0 < 4200) requestAnimationFrame(step); else res();
    })());
    const el1 = row();
    const t1 = el1.querySelector('.age').textContent;
    await new Promise(r => setTimeout(r, 1600));
    const advanced = (window.__dwViewRenderGen || 0) > gen0;
    return { replaced: el1 !== el0, advanced,
             tickWorked: advanced || el1 !== el0,
             kept: el1 === el0 && el1.__guardMark === 'kept',
             blank, t1,
             t2: row().querySelector('.age').textContent };
  });
  notes.push(`after a real tick: worked=${after.tickWorked} replaced=${after.replaced} ` +
             `kept=${after.kept} blank frames=${after.blank} ${after.t1} -> ${after.t2}`);
  // without this the three checks below pass on a tick that never happened
  ok('the tick genuinely ran (render gen advanced or row replaced)',
     after.tickWorked === true);
  ok('...the age row is filled (never blank mid-tick)', after.blank === 0);
  ok('...and it keeps ticking afterwards', after.t1 !== after.t2);
}

/* ── #151, the motion ─────────────────────────────────────────────────────
   Traced per frame, and asserted on OUTCOME rather than mechanism (the lesson
   states.mjs learned): the question is whether each row GOT there
   continuously, not which property carried it. */
const TRACE = ms => `new Promise(res => {
  const frames = []; const t0 = performance.now();
  (function step() {
    const at = {};
    for (const r of document.querySelectorAll('.git .commit[data-sha]')) {
      const b = r.getBoundingClientRect();
      at[r.dataset.sha] = { top: Math.round(b.top),
                            op: Math.round(getComputedStyle(r).opacity * 100),
                            tf: r.style.transform || '' };
    }
    const panel = document.querySelector('.git');
    // qaghost.commit, not qaghost: a departure ghost keeps its component's
    // classes (its IDENTITY is what gets stripped), and the layout-shift
    // check below also removes the questions from the page, so a page-wide
    // count reads three question-card corpses as commit motion.
    // (No backticks in here: this string IS a template literal.)
    frames.push({ at, ghosts: document.querySelectorAll('.qaghost.commit').length,
                  panel: panel ? Math.round(panel.getBoundingClientRect().height) : -1 });
    if (performance.now() - t0 < ${ms}) requestAnimationFrame(step); else res(frames);
  })();
})`;
const shasOf = f => Object.keys(f.at);
const series = (frames, sha, k) =>
  frames.map(f => f.at[sha] && f.at[sha][k]).filter(v => v !== undefined);

/* FIRST: a tick with no new commit must not animate the rows.

   The obvious version of this check — post a /command and assert nothing
   moved — proves nothing, and was caught doing so: with the new-sha gate
   deleted the regroup still runs, but `regroupCards` returns early for a row
   that did not move, so the outcome is identical and the check passes on its
   own bug. The gate is only observable when the rows DO move for some other
   reason, which is exactly the case it exists for: motion with nothing behind
   it. So make them move — write an unreadable questions.md, which puts #136's
   warning line above the panel and pushes every row down — and require them
   to arrive there with the layout rather than travelling. */
{
  const qpath = join(DIR, '.dreamwork', 'questions.md');
  const kept = await p.evaluate(`(async () => (await (await fetch('/data.json')).json()).files['questions.md'])()`);
  const trace = p.evaluate(TRACE(4000));
  await sleep(60);
  writeFileSync(qpath, '# Q\n\n## Not a section the reader knows\n\nprose.\n');
  const frames = await trace;
  writeFileSync(qpath, kept);
  const shifted = shasOf(frames[frames.length - 1]).filter(s => {
    const t = series(frames, s, 'top');
    return t.length > 1 && t[t.length - 1] !== t[0];
  });
  const steps = Math.max(...shasOf(frames[frames.length - 1])
    .map(s => new Set(series(frames, s, 'top')).size));
  const transformed = frames.some(f => Object.values(f.at).some(v => v.tf));
  notes.push(`layout-shift tick: shifted=${shifted.length} maxsteps=${steps} ` +
             `transforms=${transformed} ghosts=${Math.max(...frames.map(f => f.ghosts))}`);
  // if this is 0 the check below is vacuous — the rows never moved, so
  // "they did not travel" is satisfied by nothing having happened
  ok('a tick that changes the page above the panel really does move the rows',
     shifted.length === 5);
  ok('...and they arrive with the layout rather than travelling to it',
     steps <= 2 && !transformed && frames.every(f => f.ghosts === 0));
  await sleep(2600);          // let the restored file tick back through
}

/* THEN: a real commit. One gesture — the bottom row leaves, the new top row
   arrives, and the four between travel down one. */
{
  const before = await p.evaluate(READ);
  const trace = p.evaluate(TRACE(5000));
  await sleep(80);
  commit('feat: a commit that lands while he is watching', 0);
  const frames = await trace;
  const after = await p.evaluate(READ);
  const wasShas = before.map(r => r.sha), nowShas = after.map(r => r.sha);
  const arrived = nowShas.filter(s => !wasShas.includes(s));
  const left = wasShas.filter(s => !nowShas.includes(s));
  const survivors = nowShas.filter(s => wasShas.includes(s));
  notes.push(`new commit: +${arrived.length} -${left.length} ` +
             `survivors=${survivors.length} ` +
             `maxghosts=${Math.max(...frames.map(f => f.ghosts))}`);

  ok('a new commit lands at the top', arrived.length === 1 &&
     nowShas[0] === arrived[0]);
  ok('...the oldest leaves, and the count stays five',
     left.length === 1 && left[0] === wasShas[4] && after.length === 5);
  ok('...the departing row dreams away rather than blinking out',
     frames.some(f => f.ghosts > 0));
  // it arrives from nothing: `.dreamin` snaps it to opacity 0, then it eases
  // up. A row that was simply painted in place is opaque on every frame.
  const arrOp = series(frames, arrived[0], 'op');
  notes.push(`arrival opacity: ${arrOp.slice(0, 8).join(',')} … n=${arrOp.length}`);
  ok('...the new row eases in rather than appearing',
     arrOp.length > 0 && Math.min(...arrOp) < 90);
  // the four between TRAVEL: they visit intermediate positions rather than
  // teleporting one row down. Two distinct values is a jump; a travel has many.
  const travel = survivors.map(s => ({
    s, n: new Set(series(frames, s, 'top')).size,
    d: series(frames, s, 'top').slice(-1)[0] - series(frames, s, 'top')[0] }));
  notes.push(`survivor travel: ${JSON.stringify(travel)}`);
  ok('...and the rows between it and the gap slide down one, continuously',
     travel.length === 4 && travel.every(t => t.n >= 4 && t.d > 8));
  // "fixed-height rows so layout cannot jump" is a claim about the PANEL, and
  // this is where it is actually tested: five rows in, five out, and the box
  // the same height on every frame in between — so nothing below it is pushed
  // around while the gesture plays.
  const heights = [...new Set(frames.map(f => f.panel))];
  notes.push(`panel height across the gesture: ${heights.join(',')}`);
  ok('...while the panel itself never changes height', heights.length === 1);
  await p.screenshot({ path: `${OUT}/dashboard.png`, fullPage: true });
}

/* ── #141: the questions section folds, counts, and greys at a real zero ───
   Three states, and the point of holding them in one place is that the third
   is the one an implementation swallows: "nothing to answer" and "this page
   cannot read your questions file" are the same count. */
const QSEC = `(() => {
  const s = document.querySelector('.qsec > summary');
  if (!s) return null;
  const n = s.querySelector('.qsecn');
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent)';
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  return { text: s.textContent, open: s.parentElement.open,
           calm: s.classList.contains('none'),
           accented: !!n && getComputedStyle(n).color === accent,
           summaryColor: getComputedStyle(s).color,
           cards: [...document.querySelectorAll('.qsec .qa')]
                    .filter(c => c.checkVisibility()).length };
})()`;
// the page's `data` is a module-scope let, not window.data — ask the server
// for the number the summary is supposed to be showing
const servedCount = async () =>
  (await p.evaluate(`(async () => (await (await fetch('/data.json')).json()).open_questions)()`));
{
  const qpath = join(DIR, '.dreamwork', '.questions-backup.md');
  const live = join(DIR, '.dreamwork', 'questions.md');
  const original = await p.evaluate(`(async () => (await (await fetch('/data.json')).json()).files['questions.md'])()`);
  writeFileSync(qpath, original);

  const busy = await p.evaluate(QSEC);
  busy.served = await servedCount();
  notes.push(`qsec busy: ${JSON.stringify(busy)}`);
  ok('the questions section is collapsed by default', busy.open === false);
  // a closed <details> keeps its children's rects in current Chromium, so
  // "is it hidden" has to be asked with checkVisibility() — the fourth check
  // in this repo to be caught by that
  ok('...so no question card is visible until he opens it', busy.cards === 0);
  ok('...and the summary says how many are left to answer, the SERVERs number',
     busy.served > 0 && busy.text.includes(`${busy.served} to answer`));
  ok('...with the count on the accent, since it is live and actionable',
     busy.accented && !busy.calm);

  // what he opened is his, and the tick rebuilds the dashboard under him
  const survived = await p.evaluate(async () => {
    document.querySelector('.qsec > summary').click();
    const was = document.querySelector('.qsec').open;
    const el0 = document.querySelector('.qsec');
    const gen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'qsec guard tick' }) });
    await new Promise(r => setTimeout(r, 4200));
    const el1 = document.querySelector('.qsec');
    const advanced = (window.__dwViewRenderGen || 0) > gen0;
    return { was, replaced: el1 !== el0, advanced,
             tickWorked: advanced || el1 !== el0,
             still: el1.open,
             cards: [...document.querySelectorAll('.qsec .qa')]
                      .filter(c => c.checkVisibility()).length };
  });
  notes.push(`qsec across a tick: ${JSON.stringify(survived)}`);
  ok('it opens when he clicks it', survived.was === true);
  ok('...the tick genuinely ran (render gen advanced or section replaced)',
     survived.tickWorked === true);
  ok('...and it is still open afterwards, not shut under him',
     survived.still === true && survived.cards > 0);

  // a GENUINE zero: the seeded skeleton. Grey, no accent, and still openable
  writeFileSync(live, '# Questions for the human\n\n## Open\n\n## Answered\n');
  await sleep(3000);
  const calm = await p.evaluate(QSEC);
  notes.push(`qsec calm: ${JSON.stringify(calm)}`);
  ok('at a real zero it greys out', calm.calm === true &&
     /nothing to answer/.test(calm.text));
  ok('...and carries no accent', !calm.accented);
  /* Force it SHUT first: it is open at this point because he opened it above
     and restoreFolds correctly kept it that way across three ticks, so a bare
     click would close it and this would read as a refusal to open.

     And drive it with a REAL pointer, not `element.click()`. A synthetic
     click dispatches straight at the node and sails through
     `pointer-events:none`, so the obvious version of this check passes on a
     summary the human cannot click at all — which is exactly the bug it
     exists to catch. Shown by injecting that rule. */
  await p.evaluate(`document.querySelector('.qsec').open = false`);
  let opened = false;
  try {
    await p.click('.qsec > summary', { timeout: 4000 });
    opened = await p.evaluate(`document.querySelector('.qsec').open`);
  } catch (e) { notes.push(`calm summary was not clickable: ${e.message.split('\n')[0]}`); }
  ok('...but still opens — disabled means "nothing here needs you", not ' +
     '"you may not look"', opened === true);

  // the OTHER zero (#136): content the reader cannot see. Same number, and
  // it must not wear the calm treatment — the amber warning is right above it
  writeFileSync(live, '# Q\n\n## A question written as a heading?\n\nprose.\n');
  await sleep(3000);
  const broken = await p.evaluate(QSEC);
  const warned = await p.evaluate(
    `!!document.querySelector('.qhealth.unreadable')`);
  notes.push(`qsec unreadable: ${JSON.stringify(broken)} warned=${warned}`);
  ok('an unreadable questions.md still raises #136s warning', warned);
  ok('...and the section does NOT read as a calm zero underneath it',
     broken.calm === false &&
     broken.summaryColor !== calm.summaryColor);

  writeFileSync(live, original);
  await sleep(3000);
}

ok('no page errors', errs.length === 0);
await ctx.close();

/* reduced motion does all of it in one step — timing changes, function does
   not. A new commit still lands, it just does not travel. */
{
  const rctx = await br.newContext({ viewport: { width: 1100, height: 1100 },
                                     reducedMotion: 'reduce' });
  const rp = await rctx.newPage();
  rp.on('pageerror', e => errs.push('reduced: ' + String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const before = await rp.evaluate(READ);
  const trace = rp.evaluate(TRACE(4200));
  await sleep(80);
  commit('feat: one more, under reduced motion', 0);
  const frames = await trace;
  const after = await rp.evaluate(READ);
  const stepped = shasOf(frames[frames.length - 1]).every(s =>
    new Set(series(frames, s, 'top')).size <= 2);
  notes.push(`reduced: ${before[0].sha} -> ${after[0].sha} stepped=${stepped}`);
  ok('reduced motion still shows the new commit',
     after[0].sha !== before[0].sha && after.length === 5);
  ok('...in one step, with no ghost and no travel',
     stepped && frames.every(f => f.ghosts === 0));
  await rctx.close();
}

ok('no page errors under reduced motion either', errs.length === 0);
await br.close();
try { srv.kill(); } catch (e) {}

finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
