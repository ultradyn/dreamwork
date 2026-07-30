/* note82 — adding a note to an OPEN question and to a folded ANSWERED entry.
   #82: the thread under each question takes a follow-up; the dashboard writes
   it back via POST /comment. This guard drives both note targets and reads the
   thread the page renders from the response.

   HARNESS-CONTRACT REPAIR (#538): the guard died at `page.fill('#nbo0')` with a
   30s Playwright timeout because `#nbo0` was a literal tuned to a DOM contract
   that moved. The compose textarea is now `#qi${key}` where `key` is the
   positional entry address ('o'+i into questions_open, 'a'+j into
   answered_entries — see watch.py qaCard), and the send button calls
   `submitCard('${key}')`, not `sendComment`. The layout reads (`.notebox`,
   `.aentry`, the `reconsider` text) were the same class of expiry: the real
   compose box is `.qcompose`, folded entries are `.qa.folded`, and a follow-up
   thread is asserted against a follow DERIVED from data, never a literal.

   The repo rule a literal tuned to today's fixture breaks against: derive the
   subject at runtime and assert the precondition it depends on. So the entry
   KEYS, the review of a real follow, and the compose-box presence are all read
   from data.json / the live DOM, and a build that removes any of them is a
   named FAIL in seconds (absence-first via present()), not a thirty-second
   timeout reported as "the guard threw".

   usage: node note82.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`; const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions — types a note into an OPEN question (Ctrl+Enter) and a ' +
          'folded ANSWERED entry (send button); captures the POST /comment writes',
  traceWindow: 'static reads ~300ms after each submit; no motion trace',
});

/* ── derive the note targets from data, never assume a positional literal ─
   `o0`/`a0` are positions into data.questions_open / data.answered_entries,
   so a fixture reorder or a removed entry silently moves what `o0` addresses.
   The guard needs an entry it can actually note: an OPEN question (no answer,
   so the compose box is offered) and a folded ANSWERED entry (notes-only box).
   Both are found by STATE, not by index, and the precondition that each exists
   is itself a check — a fixture without an open-or-folded target makes the
   note checks below vacuous, and that is named, not hidden. */
const d = await (await fetch(`${BASE}/data.json`)).json();
const openQs = Array.isArray(d.questions_open) ? d.questions_open : [];
const answered = Array.isArray(d.answered_entries) ? d.answered_entries : [];
const oIdx = openQs.findIndex(q => !q.answer);
const aIdx = answered.length ? 0 : -1;
const oKey = oIdx >= 0 ? 'o' + oIdx : null;
const aKey = aIdx >= 0 ? 'a' + aIdx : null;
ok('precondition: an OPEN question (no answer, takes a note) exists in data',
   oIdx >= 0);
ok('precondition: a folded ANSWERED entry exists in data', aIdx >= 0);

/* a real follow-up thread to assert is rendered — derived from data so the
   check cannot expire against a fixture whose note copy changes. The first
   follow across open+answered entries; its `.text` is a substring of the
   rendered `.follow` (author+date+text are concatenated in the card). */
const firstFollow = [...openQs, ...answered]
  .flatMap(e => Array.isArray(e.follows) ? e.follows : [])
  .map(f => (f && f.text) || '')
  .find(t => t.length > 0);
ok('precondition: the fixture ships an existing follow-up thread to render',
   !!firstFollow);
notes.push(`derived: oKey=${oKey} aKey=${aKey} followSample=${JSON.stringify((firstFollow || '').slice(0, 40))}`);

if (oKey === null || aKey === null) {
  await (async () => { /* nothing to drive — the preconditions above name it */ })();
  finish();
  process.exit(1);
}

const NOTE_OPEN = 'a follow-up on the open one';
const NOTE_ANS = 'a note on the folded one';

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1000, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));
const posts = []; p.on('request', r => { if (r.url().endsWith('/comment')) posts.push(r.method()); });

await p.goto(BASE + '/questions', { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .qa surface the guard reads first (#428 class)
await waitFor(p, '.qa');

// absence-first: a build without the compose box is one named FAIL, not a 30s
// timeout on the fill that follows. The textarea id is `qi${key}` (watch.py).
if (!(await present(p, `#qi${oKey}`, `the OPEN question's compose box (#qi${oKey})`))) { await b.close(); finish(); process.exit(1); }
if (!(await present(p, `#qi${aKey}`, `the ANSWERED entry's compose box (#qi${aKey})`))) { await b.close(); finish(); process.exit(1); }

const layout = await p.evaluate(({ oKey, aKey, firstFollow }) => ({
  compose: document.querySelectorAll('.qcompose').length,
  threads: document.querySelectorAll('.thread').length,
  follows: [...document.querySelectorAll('.follow')].map(f => f.textContent || ''),
  folded: document.querySelectorAll('.qa.folded').length,
  openHasBox: !!document.querySelector(`.qa[data-qkey="${oKey}"] .qcompose`),
  ansHasBox: !!document.querySelector(`.qa[data-qkey="${aKey}"] .qcompose`),
}), { oKey, aKey, firstFollow });
// a derived floor: every open-without-answer question and every answered entry
// is offered a compose box, so the page should carry at least that many.
const minBoxes = openQs.filter(q => !q.answer).length + answered.length;
await p.screenshot({ path: `${OUT}/questions-threads.png`, fullPage: true });
notes.push('layout: ' + JSON.stringify(layout));
const followRenders = !!firstFollow && layout.follows.some(t => (t || '').includes(firstFollow));

ok('compose boxes render on entries (>= open+answered count derived from data)',
   layout.compose >= minBoxes && minBoxes > 0);
ok('an existing follow-up thread renders (text derived from data, not a literal)',
   followRenders);
ok('folded ANSWERED entries render (.qa.folded, count from data)',
   layout.folded === answered.length && answered.length > 0);

// add a NOTE to the OPEN question via Ctrl+Enter. An open question defaults to
// ANSWER mode (qaDefaultMode('open')='answer') and submitCard routes by mode,
// so Ctrl+Enter on the default would POST /answer — not a note at all. Switch
// the card to 'note' first (the gesture a user makes), so the submit POSTs
// /comment and lands a follow-up. waitFor(visible): a submit triggers a
// setContent re-render that swaps the cards, so a bare fill can arm against a
// node mid-swap and time out on "not visible" though the textarea is plainly
// there a moment later.
await p.locator(`#qi${oKey}`).waitFor({ state: 'visible', timeout: 5000 });
const noteMode = await p.evaluate(oKey => {
  const card = document.querySelector(`.qa[data-qkey="${oKey}"]`);
  const btn = card && card.querySelector('.qmode[data-mode="note"]');
  if (btn) btn.click();
  const comp = card && card.querySelector('.qcompose');
  return { offered: !!btn, mode: comp ? comp.dataset.mode : null };
}, oKey);
notes.push('open note-mode switch: ' + JSON.stringify(noteMode));
ok('OPEN question switched to note mode (else Ctrl+Enter POSTs /answer, not /comment)',
   noteMode.offered && noteMode.mode === 'note');
await p.fill(`#qi${oKey}`, NOTE_OPEN);
await p.focus(`#qi${oKey}`); await p.keyboard.press('Control+Enter');
await sleep(300);
const afterOpen = await p.evaluate(({ oKey }) => ({
  follows: [...document.querySelectorAll(`.qa[data-qkey="${oKey}"] .follow`)]
    .map(f => f.textContent || '') }), { oKey });
// add a note to the folded ANSWERED entry via its send button (submitCard(key)).
// A folded card collapses through <details class="qfold">, so open it first
// (the real gesture — you expand a folded entry to note it) and wait for the
// box to be visible+stable after the open-note re-render.
await p.evaluate(aKey => {
  const card = document.querySelector(`.qa[data-qkey="${aKey}"]`);
  const d = card && card.querySelector('details.qfold');
  if (d) d.open = true;
}, aKey);
await p.locator(`#qi${aKey}`).waitFor({ state: 'visible', timeout: 5000 });
await p.fill(`#qi${aKey}`, NOTE_ANS);
await p.click(`.qa[data-qkey="${aKey}"] .qsend`);
await sleep(300);
const afterAns = await p.evaluate(({ aKey }) => ({
  follows: [...document.querySelectorAll(`.qa[data-qkey="${aKey}"] .follow`)]
    .map(f => f.textContent || '') }), { aKey });
await p.screenshot({ path: `${OUT}/after-notes.png`, fullPage: true });
notes.push('afterOpen: ' + JSON.stringify(afterOpen));
notes.push('afterAns: ' + JSON.stringify(afterAns));
notes.push('posts to /comment: ' + JSON.stringify(posts));

ok('note added to OPEN entry via Ctrl+Enter',
   afterOpen.follows.some(f => f.includes(NOTE_OPEN)));
ok('note added to ANSWERED entry (send button)',
   afterAns.follows.some(f => f.includes(NOTE_ANS)));
ok('both notes POSTed to /comment', posts.filter(m => m === 'POST').length >= 2);
ok('no page errors', errs.length === 0);

await b.close();
finish();
