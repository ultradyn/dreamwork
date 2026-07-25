/* motion — the commits panel's animation, and what it must not disturb.
   Two reports, guarded together because he found them in one moment and they
   turned out to run through the same re-render:

     #179  a re-render must not take the focus out of the box he is typing in
     #184  something with no reason to move must not animate

   It builds its own git target, for the reason dashboard.mjs states: the
   shared `dev/capture/fixture` is not a repository, so `git_tail` returns []
   there and every commits-panel check would pass vacuously. It takes an
   EPHEMERAL port and ignores the one it is handed, so it cannot fight the
   shared server for one.

   usage: node motion.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
/* Report from an exit handler, not from the tail — a guard that throws part
   way through prints nothing, and a reader counting FAIL lines reads a crash
   as a clean run. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

// ── a target with a real history ──────────────────────────────────────────
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
const D = 86400;
// six, so the panel is full at five and a new one always displaces one
commit('off-panel: this one must not be shown', 400 * D);
commit('chore: the fifth row', 5 * D);
commit('feat: the fourth row', 4 * D);
commit('fix: the third row', 3 * D);
commit('chore: the second row', 2 * D);
commit('feat: the newest row', 60);

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
}
const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1300);

/* a plain tick: rewrite status.json, which is what the loop does every few
   seconds. It re-renders the whole dashboard and changes no commit. */
const plainTick = (n) => {
  const sp = join(DIR, '.dreamwork', 'status.json');
  const s = JSON.parse(readFileSync(sp, 'utf8'));
  s.queue_depth = (s.queue_depth || 0) + n;
  writeFileSync(sp, JSON.stringify(s, null, 2));
};

/* ── #179: a re-render must not take the focus ────────────────────────────
   The environment fact the whole bug rests on, asserted rather than
   remembered: focus() on an element inside a CLOSED <details> does nothing
   at all, and reports nothing. The dashboard renders every question card
   inside `.qsec`, which is closed on a fresh render until `restoreFolds`
   re-opens it — so restoring his focus BEFORE that ran was a silent no-op
   on this route and a success on /questions, which is the only route the
   typing guard ever visited. */
{
  const probe = await p.evaluate(`(() => {
    const d = document.createElement('details');
    d.innerHTML = '<summary>s</summary><textarea></textarea>';
    document.body.appendChild(d);
    const ta = d.querySelector('textarea');
    ta.focus();
    const closed = document.activeElement === ta;
    d.open = true; ta.focus();
    const open = document.activeElement === ta;
    d.remove();
    return { closed, open };
  })()`);
  notes.push(`closed-details focus: ${JSON.stringify(probe)}`);
  ok('focus() inside a closed <details> is a silent no-op (the premise)',
     probe.closed === false && probe.open === true);
}

/* Both triggers, because he reported the second and only the first was ever
   guarded. The assertion is on the CARET and the ELEMENT, never on "the rows
   animated" — a check that watches the rows passes on exactly this bug. */
const FOCUS_STATE = `(() => {
  const ta = document.querySelector('.qsec .qa[data-qid] .qcompose textarea');
  return { present: !!ta,
           value: ta ? ta.value : null,
           focused: !!ta && document.activeElement === ta,
           active: document.activeElement ? document.activeElement.tagName : null,
           start: ta ? ta.selectionStart : null,
           end: ta ? ta.selectionEnd : null };
})()`;
const startTyping = (text, caret) => p.evaluate(`(() => {
  const ta = document.querySelector('.qsec .qa[data-qid] .qcompose textarea');
  if (!ta) return false;
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(${caret}, ${caret});
  return document.activeElement === ta;
})()`);

await p.evaluate(`document.querySelector('.qsec > summary').click()`);
await sleep(500);

for (const [label, fire] of [
  ['a plain tick', () => plainTick(3)],
  ['a new commit', () => commit('feat: a commit that lands while he is typing', 0)],
]) {
  const typed = `he is part-way through a sentence (${label})`;
  const armed = await startTyping(typed, 7);
  const before = await p.evaluate(FOCUS_STATE);
  fire();
  await sleep(3000);
  const after = await p.evaluate(FOCUS_STATE);
  notes.push(`${label}: armed=${armed} after=${JSON.stringify(after)}`);
  ok(`${label} really does re-render the card (or the check below is vacuous)`,
     armed && before.focused);
  ok(`...${label} leaves the focus in the box he is typing in`, after.focused);
  ok(`...and does not move his caret`, after.start === 7 && after.end === 7);
  ok(`...and keeps what he had typed`, after.value === typed);
}

/* ── #184: what had no reason to move must not move ───────────────────────
   Asserted as ZERO transform and ZERO travel across the WHOLE animation, not
   as "it settled where it started" — the complaint is about the frames in
   between, and a settle check passes on every one of them. */
const TRACE = ms => `new Promise(res => {
  const frames = []; const t0 = performance.now();
  const key = el => (el.dataset.sha ? 's:' + el.dataset.sha : 'q:' + el.dataset.qid);
  (function step() {
    const at = {};
    for (const el of document.querySelectorAll('.git .commit[data-sha], .qa[data-qid]')) {
      const b = el.getBoundingClientRect();
      at[key(el)] = { top: Math.round(b.top), h: Math.round(b.height),
                      tf: el.style.transform || '',
                      op: Math.round(getComputedStyle(el).opacity * 100) };
    }
    const panel = document.querySelector('.git');
    frames.push({ at,
      panel: panel ? Math.round(panel.getBoundingClientRect().height) : -1,
      ghosts: [...document.querySelectorAll('.qaghost.commit')].map(n => {
        const b = n.getBoundingClientRect();
        return { top: Math.round(b.top),
                 op: Math.round(getComputedStyle(n).opacity * 100),
                 tf: getComputedStyle(n).transform };
      }) });
    if (performance.now() - t0 < ${ms}) requestAnimationFrame(step); else res(frames);
  })();
})`;
const seriesOf = (frames, k, f) =>
  frames.map(x => x.at[k] && x.at[k][f]).filter(v => v !== undefined);

let cycle = null;                      // reused by #174 below
{
  const trace = p.evaluate(TRACE(4000));
  await sleep(80);
  commit('feat: the commit whose cycle is traced', 0);
  cycle = await trace;
  const keys = [...new Set(cycle.flatMap(f => Object.keys(f.at)))];
  const qKeys = keys.filter(k => k.startsWith('q:'));
  // the LAST frame, not the union: across the gesture six shas exist — the
  // five that end up in the panel plus the one on its way out — so a union
  // counts the panel as six rows and the "five rows" check reads as broken
  const sKeys = Object.keys(cycle[cycle.length - 1].at).filter(k => k.startsWith('s:'));
  const moved = k => {
    const t = seriesOf(cycle, k, 'top');
    return t.length > 1 && Math.max(...t) - Math.min(...t) > 1;
  };
  const transformed = k => seriesOf(cycle, k, 'tf').some(v => v !== '');
  const restless = qKeys.filter(k => moved(k) || transformed(k));
  notes.push(`cycle: ${sKeys.length} rows, ${qKeys.length} cards, ` +
             `restless cards=${JSON.stringify(restless)}`);
  notes.push('panel heights: ' + [...new Set(cycle.map(f => f.panel))].join(','));
  ok('the commits panel is on screen with question cards below it (else vacuous)',
     sKeys.length === 5 && qKeys.length >= 2);
  ok('a commit cycle never changes the panel height',
     new Set(cycle.map(f => f.panel)).size === 1);
  ok('...so no question card below it moves, on any frame',
     restless.length === 0);
}

ok('no page errors', errs.length === 0);
await p.screenshot({ path: `${OUT}/motion.png`, fullPage: true });
await br.close();
try { srv.kill(); } catch (e) {}

finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
