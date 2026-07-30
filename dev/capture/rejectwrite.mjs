/* #263 E5b — a write surface treats a rejected receipt exactly as it treats a
   failure: his words are kept, and the confirmation does not run.

   E5 made body-validation failures a 202 with a durable `rejected` transition
   and a bounded reason. 202 makes `res.ok` true, and every browser-side write
   check was `res.ok` — so the box emptied, the page said "asked", and on
   /answer+/comment `dwDraft.clear()` ran, which was the only remaining copy of
   what he typed. An HTTP assertion that the body carries `rejected:true` would
   pass with the bug fully present, which makes it worse than no check: the
   defect is that the PAGE confirms. So this drives a real submit and asserts
   his text is still in the box and the confirmation did NOT run.

   The interesting history is in health.mjs's two existing checks — "never shows
   the answered state for a write that did not land" and "keeps his text, which
   is now the only copy of it". They pass today against a 409 (res.ok false) and
   were NEVER driven against a rejected 202 (res.ok true): route.fulfill pinned
   status:409, so they are structurally blind to this regression. This guard is
   the successor: it injects the 202 the server actually sends.

   THREE surfaces, because the loss is permanent on two of them: /ask (box
   clears + "asked"), /answer (morph + dwDraft.clear), /comment (dwDraft.clear).
   Plus a SUCCESS baseline per surface — the anti-vacuity half: a guard that
   broke success too would pass every "text kept" check, so each surface proves
   the page CAN still clear on a real landed write before it proves it keeps his
   words on a rejected one.

   usage: node rejectwrite.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
// OWN-SERVER GUARD: ephemeral port, argv[3] deliberately ignored (#471).
// #461 taught that adopting argv[3] forces this onto the shared recipe port,
// serveVerified refuses, and the assertions never run.
const PORT = await freePort();
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'one scratch target read on /answers and /questions; real submits of ' +
          '/ask, /answer, /comment against a rejected 202 (route.fulfill) and a ' +
          'real 200 success baseline per surface',
  traceWindow: 'static reads ~0.7s after each submit; no motion traced — the ' +
               'failure surfaces (.qerr, #askmsg) are static textContent writes ' +
               'with no transition, like the 409 idiom health.mjs reads statically',
});

// a target with one genuinely open question, so /answer and /comment have a
// card to address by [data-qid] (not .qa.open — the bug under test is the card
// LEAVING that state, so a selector naming it stops matching on failure).
const QUESTIONS = '# Questions for the human\n\n## Open\n\n' +
  '- **Should the daemon ship before the hub?**\nIt matters because the hub depends on it.\n\n' +
  '## Answered\n';
const ANSWERS = '# Questions for the dreamer\n\n## Open\n';

const dir = join(OUT, 'target');
rmSync(dir, { recursive: true, force: true });
cpSync('dev/capture/fixture', dir, { recursive: true });
writeFileSync(join(dir, '.dreamwork', 'questions.md'), QUESTIONS);
writeFileSync(join(dir, '.dreamwork', 'answers.md'), ANSWERS);
const server = await serveVerified(dir, PORT);
const stop = () => { try { server.kill(); } catch (e) {} };
process.on('exit', stop);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* the body E5's server actually sends on a schema-invalid body. reason is one
   of REJECTION_REASONS in user_events/sqlite.py; schema_invalid is the one a
   missing/empty field produces, and the closed set the client maps to voice. */
const REJECTED = { status: 202, contentType: 'application/json',
                   body: JSON.stringify({ ok: false, rejected: true, reason: 'schema_invalid' }) };

/* ── /ask: the site measured to fail (watch.py:3109 cleared the box + said
        "asked" for a rejected question). TWO halves: success clears (proves
        the page can), rejected keeps (the fix). */
{
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`ask: ${e}`));
  // SUCCESS baseline first — a real write the server accepts.
  await p.goto(`http://127.0.0.1:${PORT}/answers`, { waitUntil: 'networkidle' });
  await sleep(700);
  await p.fill('#askbox', 'a real question that will land');
  await p.click('.askform button[type=submit]');
  await sleep(700);
  const succ = await p.evaluate(() => ({
    box: (document.getElementById('askbox') || {}).value || '',
    msg: (document.getElementById('askmsg') || {}).textContent || '',
  }));
  notes.push(`ask success: box=${JSON.stringify(succ.box)} msg=${JSON.stringify(succ.msg)}`);
  ok('SUCCESS /ask clears the box on a write that lands', succ.box === '');
  // ('asked' is transient — tick() re-renders the form after success, so the
  // durable success signal is the cleared box, not the momentary message.)

  // REJECTED — inject the 202 E5 sends and drive the same submit.
  await p.route('**/ask', r => r.fulfill(REJECTED));
  const typed = 'a question whose body the server rejects';
  await p.fill('#askbox', typed);
  await p.click('.askform button[type=submit]');
  await sleep(700);
  const rej = await p.evaluate(() => ({
    box: (document.getElementById('askbox') || {}).value || '',
    msg: (document.getElementById('askmsg') || {}).textContent || '',
  }));
  notes.push(`ask rejected: box=${JSON.stringify(rej.box)} msg=${JSON.stringify(rej.msg)}`);
  ok('a rejected /ask keeps his text — the box does not empty',
     rej.box === typed);
  ok('...and never says asked for a write that did not land',
     !/asked/.test(rej.msg));
  ok('...and names the reason in his voice, not a code',
     /not written/.test(rej.msg) && /words are kept/.test(rej.msg) &&
     !/schema_invalid/.test(rej.msg));
  await p.screenshot({ path: `${OUT}/ask-rejected.png`, fullPage: true });
  await p.close();
}

/* ── /answer: the permanent-loss site. dwDraft.clear() ran on a rejected
        write, and the draft was the only copy. Address by [data-qid] — see
        health.mjs: the bug is the card leaving .open, so .qa.open stops
        matching the moment the failure happens. */
{
  const qpath = join(dir, '.dreamwork', 'questions.md');
  writeFileSync(qpath, QUESTIONS);   // reset: success mutates the file
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`answer: ${e}`));
  await p.goto(`http://127.0.0.1:${PORT}/questions`, { waitUntil: 'networkidle' });
  await sleep(700);
  const title = await p.evaluate(() => {
    const c = document.querySelector('.qa[data-qid]');
    return c ? c.getAttribute('data-qid') : null;
  });
  notes.push(`answer: addressed card data-qid=${JSON.stringify(title)}`);
  const hasBox = await p.evaluate(() => !!document.querySelector('.qa.open textarea'));
  if (!hasBox) {
    checks.push('FAIL an open answer box exists (else every check below is about a page that has none)');
  } else {
  // seed the draft store by TYPING (dwDraft.save → DraftStore on input).
  // Post-ca799f5 (#269/#459 DraftStore) the live key is
  // dw:draft:v1:<target>:card:<title>, not dw:adraft:<target>:<title>.
  // Derive the expected key at runtime from data.target + data-qid so a
  // hollow prefix count cannot pass on an empty store (and cannot FAIL when
  // the page is correct but the shape has moved). Production line that reds
  // the survival half: isDurable / the clear-on-success branch of sendAnswer
  // (watch.py: if (DraftStore.isDurable(res)) dwDraft.clear(...)).
  await p.fill('.qa.open textarea', 'pre-seeded draft that must survive');
  await p.dispatchEvent('.qa.open textarea', 'input');
  await sleep(150);
  const seeded = await p.evaluate(t => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    const title = t ? decodeURIComponent(t) : '';
    const v1 = tgt && title ? 'dw:draft:v1:' + tgt + ':card:' + title : '';
    const legacy = tgt && title ? 'dw:adraft:' + tgt + ':' + title : '';
    return {
      v1, legacy, target: tgt, title,
      v1Present: !!(v1 && localStorage.getItem(v1)),
      legacyPresent: !!(legacy && localStorage.getItem(legacy)),
    };
  }, title);
  notes.push(`answer: seeded ${JSON.stringify(seeded)}`);
  // Precondition: the save-on-input path actually wrote the DraftStore key.
  // Without this, "does not clear" passes vacuously when nothing was stored.
  ok('answer precondition: typing wrote the DraftStore v1 card key',
     !!seeded.target && !!seeded.title && seeded.v1Present &&
     seeded.v1.indexOf(seeded.target) >= 0);
  await p.route('**/answer', r => r.fulfill(REJECTED));
  const typed = 'an answer whose body the server rejects';
  await p.fill('.qa.open textarea', typed);
  await p.dispatchEvent('.qa.open textarea', 'input');
  await p.click('.qa.open .qsend');
  await sleep(800);
  const rej = await p.evaluate(({ t, expectedV1 }) => {
    const card = document.querySelector(`.qa[data-qid="${CSS.escape(t)}"]`) ||
                 document.querySelector('.qa[data-qid]');
    const ta = card && card.querySelector('textarea');
    const err = card && card.querySelector('.qerr');
    const v1Still = !!(expectedV1 && localStorage.getItem(expectedV1));
    return { cls: card ? card.className : null,
             kept: ta ? ta.value : null,
             err: err ? err.textContent : null,
             answered: !!(card && card.querySelector('.anstag')),
             v1Still, expectedV1 };
  }, { t: title, expectedV1: seeded.v1 });
  notes.push(`answer rejected: cls="${rej.cls}" kept=${JSON.stringify(rej.kept)?.slice(0,40)} err=${JSON.stringify(rej.err)?.slice(0,60)} v1Still=${rej.v1Still}`);
  ok('a rejected /answer keeps his text — the only copy of it',
     rej.kept === typed);
  ok('...and never shows the answered state for a write that did not land',
     !rej.answered && /\bopen\b/.test(rej.cls || ''));
  ok('...and does not clear the draft store (the permanent-loss vector)',
     rej.v1Still);
  ok('...and names the reason in his voice', !!rej.err &&
     /not written \(rejected\)/.test(rej.err) && /what you typed is still here/.test(rej.err));
  await p.screenshot({ path: `${OUT}/answer-rejected.png`, fullPage: true });
  } // end hasBox
  await p.close();
}

/* ── /comment: the second permanent-loss site. Same shape as /answer; the
        note is the newest thing in the thread, so a rejected note that cleared
        lost his follow-up. Switch the card to note mode first. */
{
  const qpath = join(dir, '.dreamwork', 'questions.md');
  writeFileSync(qpath, QUESTIONS);
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`comment: ${e}`));
  await p.goto(`http://127.0.0.1:${PORT}/questions`, { waitUntil: 'networkidle' });
  await sleep(700);
  const title = await p.evaluate(() => {
    const c = document.querySelector('.qa[data-qid]');
    return c ? c.getAttribute('data-qid') : null;
  });
  // switch to note mode so the send routes to /comment
  const noteBtn = await p.evaluate(() => {
    const card = document.querySelector('.qa.open') || document.querySelector('.qa');
    const btns = card && [...card.querySelectorAll('.sgbtn')];
    const nb = btns && btns.find(b => /note/i.test(b.textContent));
    if (nb) { nb.click(); return true; } return false;
  });
  notes.push(`comment: switched to note mode=${noteBtn}`);
  await p.fill('.qa.open textarea, .qa textarea', 'pre-seeded note that must survive');
  await p.dispatchEvent('.qa.open textarea, .qa textarea', 'input');
  await sleep(150);
  // Same DraftStore v1 shape as /answer (ca799f5); derive at runtime.
  const seeded = await p.evaluate(t => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    const title = t ? decodeURIComponent(t) : '';
    const v1 = tgt && title ? 'dw:draft:v1:' + tgt + ':card:' + title : '';
    return {
      v1, target: tgt, title,
      v1Present: !!(v1 && localStorage.getItem(v1)),
    };
  }, title);
  notes.push(`comment: seeded ${JSON.stringify(seeded)}`);
  ok('comment precondition: typing wrote the DraftStore v1 card key',
     !!seeded.target && !!seeded.title && seeded.v1Present);
  await p.route('**/comment', r => r.fulfill(REJECTED));
  const typed = 'a follow-up whose body the server rejects';
  await p.fill('.qa.open textarea, .qa textarea', typed);
  await p.dispatchEvent('.qa.open textarea, .qa textarea', 'input');
  await p.click('.qa.open .qsend, .qa .qsend');
  await sleep(800);
  const rej = await p.evaluate(({ t, expectedV1 }) => {
    const card = document.querySelector(`.qa[data-qid="${CSS.escape(t)}"]`) ||
                 document.querySelector('.qa[data-qid]');
    const ta = card && card.querySelector('textarea');
    const err = card && card.querySelector('.qerr');
    const v1Still = !!(expectedV1 && localStorage.getItem(expectedV1));
    return { kept: ta ? ta.value : null,
             err: err ? err.textContent : null,
             v1Still };
  }, { t: title, expectedV1: seeded.v1 });
  notes.push(`comment rejected: kept=${JSON.stringify(rej.kept)?.slice(0,40)} err=${JSON.stringify(rej.err)?.slice(0,60)} v1Still=${rej.v1Still}`);
  ok('a rejected /comment keeps his text', rej.kept === typed);
  ok('...and does not clear the draft store', rej.v1Still);
  ok('...and names the reason in his voice', !!rej.err &&
     /not written \(rejected\)/.test(rej.err));
  await p.screenshot({ path: `${OUT}/comment-rejected.png`, fullPage: true });
  await p.close();
}

ok('no page errors', errs.length === 0);
await br.close();
stop();
finish();
