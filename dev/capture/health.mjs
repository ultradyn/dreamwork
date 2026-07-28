/* #136 — "nothing needs you" and "your channel to the loop is broken" produce
   the same number, and for one morning they produced the same page: a
   dashboard reading zero open questions over a questions.md holding six, four
   of them genuinely open. The count cannot tell them apart, so the page has to.

   Three states, and the value of this guard is that it holds all three at
   once — each is easy to get right alone and the failure is always that one
   of them swallowed another:

     MISSING     quiet. A fresh target has not failed at anything: init seeds
                 the file and the loop writes it the first time it needs him.
     UNREADABLE  loud, and it names the path. This is the fault.
     EMPTY       silent — the seeded skeleton, or everything answered. Says
                 nothing at all, exactly as before.

   THE EXEMPTION IS WHERE A CHECK LIKE THIS DIES. Whatever makes the calm
   states calm can just as easily make the broken one calm, and nothing on
   screen would say so. So the last assertion here takes the file the calm
   path blesses, adds one line of content to it, and requires the fault to
   surface — run against the same server, in the same browser, after the
   exemptions exist.

   Each state is served from its own scratch target, built here rather than
   from dev/capture/fixture: the fixture is deliberately healthy, and it is
   shared with every other guard.
   usage: node health.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, rmSync, cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveAllVerified } from './serve.mjs';
const OUT = process.argv[2], PORT = +(process.argv[3] || 39887);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'four scratch targets (unreadable / empty / missing / leak) each on its ' +
          'own port, read on /questions and /, plus a server-side 409 on /answer and ' +
          'a client-side refused-write injected through route.fulfill',
  traceWindow: 'static reads after ~1.1s settle per target per route; no motion traced',
});

const SKELETON = '# Questions for the human\n\n## Open\n\n## Answered\n';
// content the reader cannot see. Not a contrived string: this is the shape
// that actually happened — the loop wrote its questions AS `##` headings.
const BROKEN = '# Questions for the human\n\n' +
  '## Should we ship the daemon before the hub?\n' +
  'It matters because the hub depends on it.\n\n' +
  '## What are the privacy defaults?\n' +
  'Two options, both defensible.\n';

/* one scratch target per state, each on its own port, so the three renders
   can be compared without a server restart racing a screenshot */
const targets = {
  unreadable: BROKEN,
  empty: SKELETON,
  missing: null,
  // the exemption check: the blessed skeleton plus one line of prose
  leak: SKELETON + '\nWe should decide about the thing.\n',
};
/* Four fixtures written first, then served through `serve.mjs` (#461) rather
   than spawn-and-sleep. The old shape was `spawn(..., {stdio:'ignore'})`
   followed by `await sleep(2500)`: when a port was already held, python exited
   "address in use" invisibly, the sleep passed anyway, and every assertion
   below graded a stale server's target instead of the fixture just written —
   reporting feature bugs about a file nothing read. `serveAllVerified` proves
   per port that the responder is alive AND serving the directory we asked
   for. */
const entries = [];
for (const [name, body] of Object.entries(targets)) {
  const dir = join(OUT, name);
  rmSync(dir, { recursive: true, force: true });
  cpSync('dev/capture/fixture', dir, { recursive: true });
  const qpath = join(dir, '.dreamwork', 'questions.md');
  if (body === null) rmSync(qpath, { force: true });
  else writeFileSync(qpath, body);
  entries.push([name, dir]);
}
const { children: servers, ports } = await serveAllVerified(entries, PORT);
const stopAll = () => servers.forEach(s => { try { s.kill(); } catch (e) {} });
process.on('exit', stopAll);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });


/* what he can actually READ, plus whether the warn colour is on screen. The
   colour is resolved through a throwaway element: `--accent`/`--warn` off
   :root come back as authored (`#fcd34d`) while every computed `color` is
   `rgb(...)`, so comparing the two silently matches nothing. */
const PROBE = `(() => {
  const el = document.createElement('span');
  el.style.color = 'var(--warn)';
  document.body.appendChild(el);
  const warn = getComputedStyle(el).color;
  el.remove();
  const vis = n => !!(n && n.checkVisibility && n.checkVisibility());
  const shown = [...document.querySelectorAll('#view *, .crumbs *')]
    .filter(n => !n.children.length && vis(n));
  return {
    text: shown.map(n => n.textContent.trim()).filter(Boolean).join(' · '),
    warned: shown.filter(n => getComputedStyle(n).color === warn)
                 .map(n => n.textContent.trim()),
    railed: [...document.querySelectorAll('.qhealth')]
      .map(n => ({ cls: n.className,
                   rail: getComputedStyle(n).borderLeftColor === warn })),
    health: (window.data || {}).questions_health || null,
  };
})()`;

const look = async (name, route) => {
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`${name}: ${e}`));
  await p.goto(`http://127.0.0.1:${ports[name]}${route}`,
               { waitUntil: 'networkidle' });
  await sleep(1100);
  const r = await p.evaluate(PROBE);
  await p.screenshot({ path: `${OUT}/${name}${route === '/' ? '-dash' : ''}.png`,
                       fullPage: true });
  await p.close();
  return r;
};

const unreadable = await look('unreadable', '/questions');
const unreadDash = await look('unreadable', '/');
const empty = await look('empty', '/questions');
const missing = await look('missing', '/questions');
const leak = await look('leak', '/questions');

notes.push(`unreadable: warn on ${JSON.stringify(unreadable.warned)}`);
notes.push(`unreadable rails: ${JSON.stringify(unreadable.railed)}`);
notes.push(`empty text: ${empty.text.slice(0, 160)}`);
notes.push(`missing text: ${missing.text.slice(0, 160)}`);

// ── the fault looks like a fault, and says where to look ────────────────
ok('the broken file is announced, not silently counted as zero',
   /unreadable/i.test(unreadable.text));
ok('...and it names the path',
   /\.dreamwork\/questions\.md/.test(unreadable.text));
ok('...in the one colour that means broken, on a rail',
   unreadable.warned.length > 0 &&
   unreadable.railed.some(r => /unreadable/.test(r.cls) && r.rail));
ok('...and it never claims the questions were all answered',
   !/all answered/.test(unreadable.text));
// the badge he glances at from every route must not read as all-clear either
ok('the crumb badge stops saying the calm thing',
   /questions unreadable/i.test(unreadable.text));
ok('the dashboard says it too, not only /questions',
   /unreadable/i.test(unreadDash.text) &&
   /\.dreamwork\/questions\.md/.test(unreadDash.text));

// ── the calm states stay calm, which is what keeps the loud one credible ─
ok('a seeded skeleton says nothing at all',
   !/unreadable/i.test(empty.text) && empty.warned.length === 0 &&
   empty.railed.length === 0);
ok('...and still reads as all answered', /all answered/.test(empty.text));
ok('a missing file is a quiet line, not a fault',
   /no \.dreamwork\/questions\.md yet/.test(missing.text) &&
   missing.warned.length === 0 &&
   !missing.railed.some(r => r.rail));
ok('...and it does not claim everything was answered',
   !/all answered/.test(missing.text));

// ── and the exemption did not swallow the check ─────────────────────────
// the file the calm path blesses, plus ONE line of content
ok('EXEMPTION CHECK: one line of prose in a blessed skeleton is still a fault',
   /unreadable/i.test(leak.text) && leak.warned.length > 0);

/* ── the same failure from the WRITING end ──────────────────────────────
   A file the reader cannot see is a file `/answer` cannot write to, so the
   read-side fault and the write-side "no match" are one failure. Before this,
   a refused write still ran the submit morph: the card restated itself as
   answered, his text was cleared, and the next tick put the question silently
   back with no explanation anywhere.

   TWO HALVES, MEASURED SEPARATELY, because the first version of this tried to
   do both at once and measured neither. It rewrote questions.md under a live
   page and then clicked — but the live tick removes the card in the 2s
   window, and `holdRerenderUntil` is a module-scope `let` rather than a
   window property, so freezing it from outside silently did nothing. The
   guard was timing a race and reporting it as a feature.

     - the SERVER genuinely refuses a title that is no longer in the file
       (asked directly, no UI, no race);
     - the CLIENT, handed that refusal, says so and keeps his words. The
       refusal is injected with `route.fulfill`, so it is the client's
       behaviour under test and nothing else. */
{
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`write: ${e}`));
  await p.goto(`http://127.0.0.1:${ports.empty}/questions`,
               { waitUntil: 'networkidle' });
  await sleep(900);
  const status = await p.evaluate(async () => {
    const r = await fetch('/answer', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'a title that is not in the file',
                             answer: 'x' }) });
    return r.status;
  });
  notes.push(`server on an unmatched title: ${status}`);
  ok('the server refuses a write it cannot place', status === 409);
  await p.close();
}
{
  const qpath = join(OUT, 'empty', '.dreamwork', 'questions.md');
  writeFileSync(qpath,
    '# Q\n\n## Open\n\n- **A question he is about to answer?** ctx.\n');
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`write2: ${e}`));
  await p.route('**/answer', r => r.fulfill({ status: 409,
    contentType: 'application/json', body: '{"ok":false}' }));
  await p.goto(`http://127.0.0.1:${ports.empty}/questions`,
               { waitUntil: 'networkidle' });
  await sleep(900);
  const typed = 'an answer to a question that is no longer there';
  await p.fill('.qa.open textarea', typed);
  await p.click('.qa.open .qsend');
  await sleep(700);
  // addressed by [data-qid], NOT by .qa.open — the bug under test is that the
  // card LEAVES the open state, so a selector that names that state stops
  // matching the moment the failure happens and every check on it passes
  // vacuously. It did, on the first version of this.
  const after = await p.evaluate(() => {
    const card = document.querySelector('.qa[data-qid]');
    const err = card && card.querySelector('.qerr');
    const ta = card && card.querySelector('textarea');
    return { cls: card ? card.className : null,
             err: err ? err.textContent : null,
             kept: ta ? ta.value : null,
             claimedAnswered: !!(card && card.querySelector('.anstag')) };
  });
  notes.push(`write-refused: card="${after.cls}" err=${JSON.stringify(after.err)}`);
  ok('a refused write says so, instead of nothing at all',
     !!after.err && /not written \(409\)/.test(after.err));
  ok('...and never shows the answered state for a write that did not land',
     !after.claimedAnswered && /\bopen\b/.test(after.cls || ''));
  ok('...and keeps his text, which is now the only copy of it',
     after.kept === typed);
  await p.screenshot({ path: `${OUT}/write-refused.png`, fullPage: true });
  await p.close();
}
/* ── #263 E5b: the same three invariants against a REJECTED 202, not a 409.
   E5 made body-validation failures 202 + a durable `rejected` transition, and
   202 makes `res.ok` true — so the two checks above (named for exactly these
   invariants) passed green over the regression: `route.fulfill` pinned 409, so
   they were never driven against the 202 the server actually sends. A fake's
   hardcoded parameter is part of the check's scope. This half closes that. */
{
  const qpath = join(OUT, 'empty', '.dreamwork', 'questions.md');
  writeFileSync(qpath,
    '# Q\n\n## Open\n\n- **A question he is about to answer?** ctx.\n');
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`write3: ${e}`));
  await p.route('**/answer', r => r.fulfill({ status: 202,
    contentType: 'application/json',
    body: JSON.stringify({ ok:false, rejected:true, reason:'schema_invalid' }) }));
  await p.goto(`http://127.0.0.1:${ports.empty}/questions`,
               { waitUntil: 'networkidle' });
  await sleep(900);
  const typed = 'an answer whose body the server rejects';
  await p.fill('.qa.open textarea', typed);
  await p.click('.qa.open .qsend');
  await sleep(700);
  const after = await p.evaluate(() => {
    const card = document.querySelector('.qa[data-qid]');
    const err = card && card.querySelector('.qerr');
    const ta = card && card.querySelector('textarea');
    return { cls: card ? card.className : null,
             err: err ? err.textContent : null,
             kept: ta ? ta.value : null,
             claimedAnswered: !!(card && card.querySelector('.anstag')) };
  });
  notes.push(`write-rejected202: card="${after.cls}" err=${JSON.stringify(after.err)}`);
  ok('a REJECTED 202 (res.ok true) still says so, not nothing',
     !!after.err && /not written \(rejected\)/.test(after.err));
  ok('...and never shows the answered state for a write that did not land',
     !after.claimedAnswered && /\bopen\b/.test(after.cls || ''));
  ok('...and keeps his text, which is now the only copy of it',
     after.kept === typed);
  await p.screenshot({ path: `${OUT}/write-rejected202.png`, fullPage: true });
  await p.close();
}

ok('no page errors', errs.length === 0);
await br.close();
stopAll();
finish();
