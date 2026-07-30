/* history — #165: what he has sent, read back where he sent it from.

   #175 records every submission with its outcome; this is the surface that
   makes it not-theatre. The two land together on purpose: a log nobody can
   reach is the silent shape this loop keeps closing.

   THE SOURCE IS THE CLIENT LOG, which is a decision this guard also checks the
   consequences of. `watch-events.log` covers every window but is a rendering
   and cannot say whether a submission landed; `.dreamwork/submissions.log`
   (#199) is verbatim but written before the work, so it is pre-outcome. Only
   #175's record knows the outcome, which is the field he cannot recover any
   other way — so the panel is narrow and SAYS SO, once, at the foot.

   WHAT IT ASSERTS THAT A SCREENSHOT WOULD NOT:

     - the FAILURES are in the list and marked as failures. A history that
       shows only what worked is a worse lie than no history, because it reads
       as complete. This is the whole recovery case.
     - newest FIRST, which is the order he needs and the opposite of the
       store's own.
     - it says what it does not cover. A panel implying completeness it lacks
       is the thing the ledger asked to avoid, in its own words.
     - and it ARRIVES rather than appearing: the rows are fetched async, so
       without the enter idiom they blink in a frame after the disclosure has
       finished opening — #196 at a smaller size, which is exactly the "there
       is no size below which this stops applying" case.

   Shown red on the pre-#165 build: no disclosure at all.

   usage: node history.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1000 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the composer chrome (#cmdplus) the guard drives first, not a fixed sleep (#428 class)
await waitFor(p, '#cmdplus');

const openComposer = async () => {
  if (!await p.evaluate(`!!document.querySelector('#cmdpalette.open')`)) {
    await p.click('#cmdplus'); await sleep(700);
  }
};

/* THE SUBJECT IS ASSERTED TO EXIST BEFORE ANYTHING DRIVES IT.

   Without this, a build without the feature makes the first `p.click` wait
   thirty seconds for a selector that will never appear and then throw, so the
   run costs half a minute and reports "the guard threw" — which says nothing
   about the page and sends the reader to the wrong file. Three guards in this
   batch hit that before it was written down. Absence is a FAIL with a
   sentence, and the rest is skipped rather than repeating the timeout. */
async function present(sel, what) {
  const there = await p.evaluate(`!!document.querySelector(${JSON.stringify(sel)})`);
  ok(`${what} exists (else every check below is about a page that has none)`,
     there);
  return there;
}
const rows = () => p.evaluate(`[...document.querySelectorAll('.cmdhrow')].map(r => ({
  kind: r.querySelector('.cmdhkind').textContent,
  text: r.querySelector('.cmdhtext').textContent,
  why: r.querySelector('.cmdhwhy') && r.querySelector('.cmdhwhy').textContent,
  age: r.querySelector('.cmdhage').textContent,
  bad: r.classList.contains('bad'),
}))`);

await openComposer();
const HAVE = await present('#cmdhistsum', 'the composer\'s history disclosure');

/* ── against nothing, first ───────────────────────────────────────────── */
if (HAVE) {
  await p.click('#cmdhistsum');
  await sleep(500);
  const r = await rows();
  const note = await p.evaluate(
    `(document.querySelector('.cmdhnote') || {}).textContent || ''`);
  notes.push(`empty: ${r.length} row(s); note ${JSON.stringify(note)}`);
  ok('with nothing sent, the history exists and says so rather than ' +
     'rendering an empty box', r.length === 0 && /nothing sent/.test(note));
  // ...and says NOT HERE rather than NOT AT ALL. A fresh profile or a second
  // machine lands here too, so "you have sent nothing" would be a confident
  // false statement about his own history — the empty state is where a
  // scoped panel is most tempted to overclaim.
  ok('...scoped to this browser even when empty, never claiming he sent ' +
     'nothing at all', /this browser/.test(note) && /other/.test(note));
  await p.click('#cmdhistsum');            // shut it again
  await sleep(300);
}

/* ── one that lands, one that does not ────────────────────────────────── */
const GOOD = 'an idea that lands ' + process.pid;
const DEAD = 'an idea into a dead socket ' + process.pid;
if (HAVE) {
  await p.evaluate(`(async () => {
    document.getElementById('cmdtext').value = ${JSON.stringify(GOOD)};
    document.getElementById('cmdform').requestSubmit();
    await new Promise(r => setTimeout(r, 900));
  })()`);
  await openComposer();
  await p.evaluate(`(async () => {
    const real = window.fetch;
    window.fetch = async (...a) => String(a[0]).startsWith('/command')
      ? Promise.reject(new TypeError('failed to fetch')) : real(...a);
    document.getElementById('cmdtext').value = ${JSON.stringify(DEAD)};
    document.getElementById('cmdform').requestSubmit();
    await new Promise(r => setTimeout(r, 700));
    window.fetch = real;
  })()`);
  await openComposer();
  await p.click('#cmdhistsum');
  await sleep(600);
  const r = await rows();
  notes.push(`after two sends: ${JSON.stringify(r)}`);
  ok('both sends are listed (else the checks below are vacuous)', r.length >= 2);
  // THE ASSERTION: a history that shows only successes reads as complete and
  // is the more dangerous lie.
  const dead = r.find(x => x.text === DEAD);
  ok('the send that never left is IN the history', !!dead);
  ok('...and is marked as a failure, with why', !!dead && dead.bad &&
     /never sent/.test(dead.why || ''));
  const good = r.find(x => x.text === GOOD);
  ok('the send that landed is there and is NOT marked bad',
     !!good && !good.bad);
  ok('newest first — the order he needs, not the store\'s',
     r[0] && r[0].text === DEAD);
  ok('every row carries when it happened, in `ago` and not `old`',
     r.every(x => /\d+[smhd] ago$/.test(x.age)));
  ok('the kind is marked, so one list can hold every act (#165: he does not ' +
     'think of an answer as a different act)',
     r.every(x => x.kind && x.kind.trim().length > 0));
}

/* ── it says what it does not cover ──────────────────────────────────── */
if (HAVE) {
  const note = await p.evaluate(
    `(document.querySelector('.cmdhnote') || {}).textContent || ''`);
  notes.push(`note: ${JSON.stringify(note)}`);
  ok('the panel states its own limit rather than implying completeness',
     /this browser/.test(note) && /other/.test(note));
}

/* ── the rows ARRIVE ─────────────────────────────────────────────────── */
if (HAVE) {
  await p.click('#cmdhistsum');            // shut
  await sleep(400);
  const trace = p.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      const b = document.getElementById('cmdhistbody');
      seen.push({ t: performance.now() - t0,
                  n: document.querySelectorAll('.cmdhrow').length,
                  op: b ? +getComputedStyle(b).opacity : 1 });
      if (performance.now() - t0 < 1200) requestAnimationFrame(step); else res(seen);
    })();
  })`);
  await sleep(50);
  await p.click('#cmdhistsum');
  const seen = await trace;
  const withRows = seen.filter(s => s.n > 0);
  const mid = withRows.filter(s => s.op > 0.02 && s.op < 0.98).length;
  notes.push(`arrival: rows present from t=${withRows.length ? Math.round(withRows[0].t) : -1}ms, ` +
             `${mid} frames part-way faded in`);
  ok('the rows really did render (else the arrival check is vacuous)',
     withRows.length > 0);
  // an async list that blinks in is #196 at a smaller size, and "it is only a
  // small panel" is exactly how a page ends up with one gesture that snaps
  ok('...and they ease in rather than blinking on', mid >= 3);
}

await p.screenshot({ path: `${OUT}/history.png`, fullPage: false });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
