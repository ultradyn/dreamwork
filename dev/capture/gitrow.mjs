/* gitrow — #166: a commit row EXPANDS, and it expands the way everything
   else on this page does.

   The body of a commit is where this repo's reasoning lives and it is the
   most useful text in the log; the row shows a 60-character ellipsised
   subject. So the row becomes a disclosure — and the moment it does, it
   inherits every contract the page already has for one.

   THREE OF THOSE ARE WHY THIS GUARD EXISTS, and none of them can fail an
   end-state check:

     - **The FLIP window.** Commit rows are `travelCard`'d through
       `GIT_LIST`, and `regroupCards` measures the new rect in the SAME TICK
       as the toggle. Anything the open row adds to its box must be in layout
       by then. `details[open]` carries #169's `.5rem` of air; put a
       transition on that (or get the box model wrong) and the travel plays to
       a height the row never reaches and SNAPS when the inline height
       clears. `prominence.mjs` asserts exactly this for the question list and
       has never covered this one (dreamer-gesture, #166).
     - **The panel's constant height.** #151 rests on five fixed-height rows,
       so `details { margin:.25rem 0 }` — which every other disclosure on the
       page wants — would push the rows apart and move the page every time a
       commit lands.
     - **What he opened survives the tick.** The dashboard rebuilds through
       `innerHTML` every two seconds and an expanded row exists nowhere on
       disk (#118, #141).

   THIS GUARD BUILDS ITS OWN TARGET and takes an ephemeral port, dashboard
   .mjs-style: `dev/capture/fixture` is not a git repository, so `git_tail`
   returns [] there and every check below would pass against an empty panel.
   The commits are planted with bodies and file lists this guard can name.

   usage: node gitrow.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored. #461 made this adopt argv[3] so a squatter red-proof could aim, and
// because the recipe always passes {{port}} that silently forced this guard onto
// the shared server's port, where serveVerified rightly refused -- so the guard
// stopped running at all (#471). Registration is not execution.
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = []; const errs = [];
/* FLOOR — below this many distinct sampled positions, between()==0 is
   structurally guaranteed and carries no travel-vs-teleport signal: you
   need at least 3 (start, a part-way, end) for between >= 1 to even be
   POSSIBLE. Below it the guard SKIPs with a stated reason instead of
   redding on code that is correct (#345). A skip is not a pass: it is
   visible as SKIP in the output and counted in the summary line, and it
   names the remedy — "sampled N, floor M" — never the bare "did not
   move" that was true about the sampler and false about the code (#940). */
const FLOOR = 3;
const skip = (n, why) => checks.push(`SKIP ${n} — could not measure: ${why}`);
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  const np = checks.filter(c => c.startsWith('PASS')).length;
  const nf = checks.filter(c => c.startsWith('FAIL')).length;
  const ns = checks.filter(c => c.startsWith('SKIP')).length;
  console.log(`summary: ${np} pass, ${nf} fail, ${ns} skip`);
  if (errs.length) console.log(errs.join('\n'));
});

// ── a target with commits whose bodies and files this guard can name ──────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const NOW = Math.floor(Date.now() / 1000);
const git = (args, at) => execFileSync('git', ['-C', DIR, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'the guard author', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'the guard author', GIT_COMMITTER_EMAIL: 'g@x',
         GIT_AUTHOR_DATE: `@${at || NOW} +0000`,
         GIT_COMMITTER_DATE: `@${at || NOW} +0000` },
}).toString().trim();
git(['init', '-q']);
// A body that is HARD-WRAPPED, because the reflow is half of what the fold is
// for: a commit message wrapped at 72 columns rendered verbatim in a 100ch
// column reads as a poem.
const BODY = [
  'The body is the reasoning, and the subject line is a label for it. This',
  'paragraph is hard-wrapped at seventy-two columns exactly as git asks for,',
  'so a renderer that does not reflow it leaves a ragged right edge.',
  '',
  'Trailer-Like: a second paragraph, so the reflow has a boundary to keep.',
].join('\n');
const touch = (name, body, msg, agoSec) => {
  writeFileSync(join(DIR, name), `${name}\n${agoSec}\n`);
  git(['add', name]);
  git(['commit', '-q', '-m', msg, ...(body ? ['-m', body] : [])], NOW - agoSec);
};
touch('older.txt', null, 'chore: a commit that is off the panel', 400 * 86400);
touch('a.txt', BODY, 'feat: the row this guard expands', 5 * 3600);
touch('b.txt', null, 'fix: a commit with no message body at all', 2 * 3600);
/* #486: a LONG subject and no body. The header's .gsub ellipsises, so until
   #486 the full subject was shown NOWHERE on the expanded row. Planted here,
   between b and c in CREATION order — the panel walks the parent chain, so
   creation order is display order and a commit appended at the end shifts
   every index the checks above select (measured, not theorised). */
const LONG_SUBJ =
  'fold #445 + #443: attention axes ratified, controls landed and in use today';
touch('g.txt', null, LONG_SUBJ, 100 * 60);
touch('c.txt', BODY, 'docs: a third row, so there is one below the one we open', 900);
writeFileSync(join(DIR, 'd.txt'), 'd\n');
writeFileSync(join(DIR, 'e.txt'), 'e\n');
git(['add', 'd.txt', 'e.txt']);
git(['commit', '-q', '-m', 'feat: a commit touching two files', '-m', BODY], NOW - 300);
touch('f.txt', BODY, 'feat: the newest row', 20);

/* #461: prove the responder is ours before expanding rows against it. */
const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;

/* the trace, qsec.mjs's, aimed at this list. Document space, not viewport:
   a click that scrolls would otherwise read as movement the row did not
   cause. The ghost is sampled per FRAME because it lives ~1s and removes
   itself — looked for afterwards it is a departure that did happen reported
   as one that did not. */
const TRACE = ms => `new Promise(res => {
  /* RE-QUERY PER FRAME. A live tick replaces the dashboard through
     innerHTML; a reference held from the first frame is DETACHED after it
     and getBoundingClientRect throws / returns zeros — the throw is what
     burndown's notes already name, and under load this guard hit it too. */
  const seen = []; let ghost = null; let click = null;
  const t0 = performance.now();
  let clicked = false;
  (function step() {
    const t = performance.now() - t0;
    const row = document.querySelectorAll('.git .commit[data-sha]')[1];
    const panel = document.querySelector('.git');
    const below = panel && panel.nextElementSibling;
    const body = row && row.querySelector('.gdetail');
    const g = document.querySelector('.qaghost');
    if (g && !ghost) ghost = {
      sha: g.getAttribute('data-sha'), keep: g.getAttribute('data-keep'),
      inner: g.querySelectorAll('[data-qid],[data-qkey],[data-sha],[data-keep]').length,
      h: g.getBoundingClientRect().height };
    seen.push({ t,
      below: below ? below.getBoundingClientRect().top + window.scrollY : -1,
      h: row ? row.getBoundingClientRect().height : -1,
      op: body ? +getComputedStyle(body).opacity : 1,
      ghosts: document.querySelectorAll('.qaghost').length });
    /* THE CLICK IS DISPATCHED INSIDE THE TRACE, not as a separate Playwright
       roundtrip. #386: gesture() used to fire p.click() after a sleep(60),
       and under load that roundtrip's latency landed the click AFTER the
       1500ms trace window closed — the trace captured 0px and the open read
       as a vacuous failure. Anchoring the click to the trace's own first
       frame removes the race for the same reason dreamfade.mjs runs its
       action inside its evaluate.
       The #141 contract is preserved by HIT-TESTING: a bare summary.click()
       sails through pointer-events:none, so elementFromPoint models the real
       pointer the original p.click() used — it skips pointer-events:none and
       returns an overlay instead, so a summary he cannot press never toggles
       and the open reads 0px by name rather than by luck. */
    if (!clicked) {
      clicked = true;
      const summary = row && row.querySelector(':scope > summary');
      if (!summary) {
        click = { landed: false, why: 'no summary' };
      } else {
        const r = summary.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        if (hit && (summary === hit || summary.contains(hit))) {
          summary.click();
          click = { landed: true };
        } else {
          click = { landed: false, why: 'intercepted',
                    hit: hit ? (hit.tagName + '.' + (hit.className || '')).slice(0, 60) : 'null' };
        }
      }
    }
    if (t < ${ms}) requestAnimationFrame(step); else res({ seen, ghost, click });
  })();
})`;
async function gesture(p, ms = 1500) {
  return await p.evaluate(TRACE(ms));
}
const distinct = xs => new Set(xs.map(v => Math.round(v))).size;
/* between() — frame-rate-free travel (transitions.md, dreamfade.mjs).
   `positions >= 8` was a load meter: under 8 CPU burners this guard went
   0/5 while isolation was 4/5. Zero-versus-some part-way frames is the
   snap/travel distinction; the vacuity half is the moved-span floor. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}
const at = (seen, ms) => seen.reduce((a, b) =>
  Math.abs(b.t - ms) < Math.abs(a.t - ms) ? b : a);
function travel(seen) {
  const tops = seen.map(s => s.below);
  const from = tops[0], final = tops.at(-1);
  const i0 = tops.findIndex(v => Math.abs(v - from) > 1);
  const t0 = i0 < 0 ? 0 : seen[i0].t;
  const dir = Math.sign(final - from);
  return { moved: Math.abs(final - from), positions: distinct(tops),
           partway: between(tops, from, final),
           late: Math.abs(at(seen, t0 + 950).below - final),
           over: Math.max(0, ...tops.map(v => dir * (v - final))) };
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1400 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);

// ── the shape, and the preconditions every check below rests on ───────────
const shape = await p.evaluate(`(() => {
  const rows = [...document.querySelectorAll('.git .commit[data-sha]')];
  const panel = document.querySelector('.git');
  return {
    n: rows.length,
    details: rows.filter(r => r.tagName === 'DETAILS').length,
    summaries: rows.filter(r => r.querySelector(':scope > summary')).length,
    open: rows.filter(r => r.open).length,
    tops: rows.map(r => Math.round(r.getBoundingClientRect().top)),
    hs: rows.map(r => Math.round(r.getBoundingClientRect().height * 10) / 10),
    panelH: Math.round(panel.getBoundingClientRect().height),
    below: !!panel.nextElementSibling,
    // a closed <details> keeps its children's RECTS from the last layout in
    // current Chromium, so height cannot answer "is it hidden" (#128)
    bodyVisible: rows.map(r => {
      const b = r.querySelector('.gdetail');
      return b ? b.checkVisibility() : null; }),
  };
})()`);
notes.push(`shape: ${JSON.stringify(shape)}`);
ok('the panel holds five commit rows (else everything below is vacuous)',
   shape.n === 5);
ok('...each row is a disclosure with its own summary',
   shape.details === 5 && shape.summaries === 5);
ok('...all closed on arrival, and each has a body to reveal',
   shape.open === 0 && shape.bodyVisible.every(v => v === false));
ok('...with a panel below them to be displaced', shape.below);
/* #151's floor, restated because #166 is the change most likely to break it:
   `details { margin:.25rem 0 }` is what every other disclosure on this page
   wants, and it would push these rows apart. Rows are contiguous or they are
   not — the gap is the assertion, not the height. */
{
  const gaps = shape.tops.slice(1).map((t, i) => t - shape.tops[i]);
  notes.push(`row pitch: ${gaps.join(', ')} (heights ${shape.hs.join(', ')})`);
  // pitch EQUALS height, within a pixel of sub-pixel rounding — a row is
  // 22.4px tall and its neighbours land on 22 or 23. The failure this names
  // adds 8px to every gap (`.25rem` above and below), so there is nothing to
  // tune between 1 and 8.
  ok('...and closed they are contiguous, so the panel height is still a ' +
     'constant', gaps.every(g => Math.abs(g - shape.hs[0]) <= 1));
}

// ── it opens, and the panel below TRAVELS ─────────────────────────────────
{
  const { seen, ghost, click } = await gesture(p);
  const t = travel(seen);
  const hs = seen.map(s => s.h);
  const hPartway = between(hs, hs[0], hs.at(-1));
  const mid = seen.filter(s => s.op > 0.02 && s.op < 0.98).length;
  notes.push(`open: below travelled ${t.moved.toFixed(0)}px over ${t.positions} ` +
             `positions (${t.partway} part-way); row height ${seen[0].h.toFixed(0)} -> ` +
             `${seen.at(-1).h.toFixed(0)} (${hPartway} part-way of ` +
             `${distinct(hs)} rounded); ${mid} frames part-way faded in; ` +
             `${t.late.toFixed(1)}px to go at the end, ${t.over.toFixed(1)}px over; ` +
             `click ${click ? JSON.stringify(click) : 'n/a'}`);
  ok('opening: the click reached the summary (pointer-events / overlay gate, #141)',
     !!click && click.landed);
  ok('opening: the panel below is displaced at all (else vacuous)', t.moved >= 60);
  // THE ASSERTION. A snap has zero frames strictly between the ends.
  // #345: the shape needs at least FLOOR distinct positions to be
  // measurable — below it, between()==0 is structural, not a teleport
  // signal. The denominator (sampled N, floor M) prints on every run
  // so a 40-position pass and a 3-position skip never report alike (#868).
  const denom = `sampled ${t.positions} positions (floor ${FLOOR})`;
  if (t.positions < FLOOR) {
    skip('opening: ...and it travels there rather than teleporting', denom);
    skip('opening: the row itself grows continuously rather than in one step', denom);
    skip('opening: the revealed body eases in rather than blinking on', denom);
  } else {
    ok(`opening: ...and it travels there rather than teleporting (${denom})`, t.partway >= 1);
    ok('opening: the row itself grows continuously rather than in one step',
       hPartway >= 1);
    ok('opening: the revealed body eases in rather than blinking on', mid >= 1);
  }
  /* the FLIP-window contract, stated as the two things a mis-measured travel
     does. 4px each: a clean ease lands within ~1.5px, and the failure both
     describe is `details[open]`'s 2 x .5rem — 16px. Nothing to tune between. */
  ok('opening: ...and it has arrived when the travel ends, not after a snap',
     t.late <= 4);
  ok('opening: ...having never gone past where it ends up', t.over <= 4);
  ok('opening: nothing is ghosted on the way IN', !ghost);
}

// ── what is inside it ─────────────────────────────────────────────────────
{
  const body = await p.evaluate(`(() => {
    const row = document.querySelectorAll('.git .commit[data-sha]')[1];
    const b = row.querySelector('.gdetail');
    if (!b) return null;
    return { visible: b.checkVisibility(), text: b.textContent,
             subject: row.querySelector('.gsub').textContent,
             meta: (b.querySelector('.gmeta') || {}).textContent || '',
             files: [...b.querySelectorAll('.gfile')].map(f => f.textContent),
             // the empty case, read across ALL rows: exactly one of these
             // commits was made without a body, and a page that renders
             // nothing there is indistinguishable from one that could not
             // read it (#136, one panel over)
             nobody: [...document.querySelectorAll('.git .gnone')]
               .map(n => n.textContent),
             // reflowed prose, not a <pre>: the message is wrapped at 72
             // columns and the column is wider than that
             pre: b.querySelectorAll('pre').length,
             md: b.querySelectorAll('.md').length,
             lines: b.querySelector('.md')
               ? [...b.querySelector('.md').querySelectorAll('p')].length : 0 };
  })()`);
  notes.push(`body: ${JSON.stringify(body).slice(0, 400)}`);
  ok('the open row shows its body (else the rest is vacuous)',
     !!body && body.visible);
  ok('...the full sha and the author, which the row cannot hold',
     !!body && /^[0-9a-f]{40}/.test(body.meta) && /the guard author/.test(body.meta));
  ok('...the message body, which is where the reasoning is',
     !!body && /seventy-two columns/.test(body.text));
  ok('...reflowed rather than left hard-wrapped',
     !!body && body.md === 1 && body.pre === 0 && body.lines >= 2);
  // named against the row actually opened, not against a filename this guard
  // remembers planting: the row is the second-newest, and asserting a file
  // from some OTHER commit is a check that passes only while the plant order
  // happens to line up
  ok('...and the files it touched, all of them',
     !!body && body.subject === 'feat: a commit touching two files' &&
     body.files.join(',') === 'd.txt,e.txt');
  ok('...and a commit with no body says so rather than rendering blank',
     !!body && body.nobody.filter(t => /no message body/.test(t)).length === 2);
}

// ── a long no-body subject is shown in FULL in the detail (#486) ──────────
{
  ok('precondition: the fixture subject is long enough to ellipsise in the header',
     LONG_SUBJ.length >= 60);
  const r = await p.evaluate(`(() => {
    const rows = [...document.querySelectorAll('.git .commit[data-sha]')];
    const row = rows.find(r => (r.querySelector('.gsub') || {}).textContent === ${JSON.stringify(LONG_SUBJ)});
    if (!row) return { found: false };
    /* NO CLICK: the detail is in the DOM whether the row is open or not, and
       leaving a second row open breaks the tick-survival block's exactly-one
       precondition below (measured). */
    const b = row.querySelector('.gdetail');
    return { found: true, detail: b ? b.textContent : '',
             fullsub: b && b.querySelector('.gfullsub')
               ? b.querySelector('.gfullsub').textContent : null };
  })()`);
  ok('a LONG subject with no body renders in FULL inside the detail (#486: the header may truncate)',
     r.found && r.fullsub === LONG_SUBJ);
  ok('...and the parenthetical still says why there is no body',
     r.found && /no message body/.test(r.detail));
}

// ── what he opened survives the tick (#118 one level down) ────────────────
{
  const r = await p.evaluate(`(async () => {
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'gitrow guard tick' }) });
    const before = document.querySelectorAll('.git .commit[open]').length;
    await tick();
    return { before, after: document.querySelectorAll('.git .commit[open]').length };
  })()`);
  notes.push(`across a driven tick: ${r.before} open before, ${r.after} after`);
  ok('a row he opened was open before the tick (else this is vacuous)',
     r.before === 1);
  ok('...and the tick does not shut it under him', r.after === 1);
}

// ── ...and it closes, on the page's one departure idiom ───────────────────
{
  const { seen, ghost, click } = await gesture(p);
  const t = travel(seen);
  notes.push(`close: below travelled ${t.moved.toFixed(0)}px over ${t.positions} ` +
             `positions (${t.partway} part-way); ${t.late.toFixed(1)}px to go, ` +
             `${t.over.toFixed(1)}px over; ` +
             `ghost ${ghost ? JSON.stringify(ghost) : 'none'}; ` +
             `click ${click ? JSON.stringify(click) : 'n/a'}`);
  ok('closing: the click reached the summary (pointer-events / overlay gate, #141)',
     !!click && click.landed);
  ok('closing: the panel below is displaced at all (else vacuous)', t.moved >= 60);
  const cdenom = `sampled ${t.positions} positions (floor ${FLOOR})`;
  if (t.positions < FLOOR) {
    skip('closing: ...and it travels there rather than teleporting', cdenom);
  } else {
    ok(`closing: ...and it travels there rather than teleporting (${cdenom})`, t.partway >= 1);
  }
  ok('closing: ...and it has arrived when the travel ends', t.late <= 4);
  ok('closing: ...having never gone past where it ends up', t.over <= 4);
  ok('closing: the leaving body dreams away rather than being cut off',
     !!ghost && ghost.h > 20);
  // a ghost is a corpse and holds no address: it is a clone of the row, so it
  // arrives carrying data-sha AND data-keep, and every keyed walk on the page
  // would find it — including snapshotFolds, which takes the LAST match and
  // would re-open the row he just shut
  ok('closing: ...and the ghost carries no identity',
     !!ghost && ghost.sha === null && ghost.keep === null && ghost.inner === 0);
  ok('closing: the row really is shut afterwards',
     await p.evaluate(`document.querySelectorAll('.git .commit[open]').length === 0`));
}
await p.screenshot({ path: `${OUT}/gitrow.png`, fullPage: false });

// ── reduced motion: timing changes, function does not ─────────────────────
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 },
                                    reducedMotion: 'reduce' });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const open = await gesture(rp, 800);
  const close = await gesture(rp, 800);
  const o = open.seen.map(s => s.below), c = close.seen.map(s => s.below);
  const oMid = between(o, o[0], o.at(-1)), cMid = between(c, c[0], c.at(-1));
  notes.push(`reduced: open ${distinct(o)} positions (${oMid} part-way), ` +
             `close ${distinct(c)} (${cMid} part-way), ` +
             `ghosts ${open.ghost || close.ghost ? 'yes' : 'none'}`);
  ok('reduced motion: the row still opens and shuts (function is intact)',
     Math.abs(o.at(-1) - o[0]) >= 60 && Math.abs(c.at(-1) - c[0]) >= 60 &&
     await rp.evaluate(`document.querySelectorAll('.git .commit[open]').length === 0`));
  ok('reduced motion: ...instantly, in one step each way',
     oMid === 0 && cMid === 0);
  ok('reduced motion: and nothing is ghosted', !open.ghost && !close.ghost);
  await rp.screenshot({ path: `${OUT}/gitrow-reduced.png`, fullPage: false });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
try { srv.kill(); } catch (e) {}
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
