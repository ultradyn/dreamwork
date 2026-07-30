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
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = +(process.argv[3] || 39887);
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
/* #413 — a refusal can arrive as a 2xx, and that is the contract this guard
   was blind to until now. The client write path branches on `res.ok` alone
   (watch.py:3576, `if (!res || !res.ok)`), so a fake that pins the refusal at
   409 only ever drives the branch where `res.ok` is FALSE; a 202 refusal slips
   straight through and the confirm morph runs — the card restates itself
   answered, his text is cleared, the next tick puts the question back with no
   explanation. (Production's /answer refusal is 409 TODAY — watch.py:10267 —
   so the pinned value is not stale; the blindness is the fake's SCOPE: it
   drives one of the two statuses the client branches on.)

   CONVENTION for the next refusal guard: drive the refusal on a status the
   client treats as SUCCESS (2xx) as well as one it treats as failure, because
   the client branches on res.ok and the moved contract is always the 2xx one.

   So this drives BOTH a 4xx and a 2xx refusal. The 202 half is RED against
   the pre-E5b client BY DESIGN — it is the instrument that goes green when
   E5b lands its client fix; report the red, do not paper it over. */
const REFUSAL_STATUSES = [];   // filled by refusedWrite — the coverage fact
const refusedWrite = async (status, body, label) => {
  const qpath = join(OUT, 'empty', '.dreamwork', 'questions.md');
  writeFileSync(qpath,
    '# Q\n\n## Open\n\n- **A question he is about to answer?** ctx.\n');
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`${label}: ${e}`));
  await p.route('**/answer', r => r.fulfill({ status,
    contentType: 'application/json', body }));
  await p.goto(`http://127.0.0.1:${ports.empty}/questions`,
               { waitUntil: 'networkidle' });
  await sleep(900);
  const typed = 'an answer to a question that is no longer there';
  // Wait for an open card before typing — the file was rewritten just above,
  // and a sample taken before the first tick paints the card fills nothing
  // and click is a no-op (err stays null; "says so" fails for the wrong reason).
  await p.waitForSelector('.qa.open textarea', { timeout: 5000 });
  await p.fill('.qa.open textarea', typed);
  // Wait on the real premise: the /answer response returned AND the client
  // painted either a .qerr (refusal said so) or an .anstag (wrongly claimed
  // answered). A fixed 700ms sleep raced under load — the async sendAnswer
  // had not yet written .qerr, so err=null read as "says nothing" on a page
  // that was about to say so. Production line: qaFail → .qerr textContent.
  await Promise.all([
    p.waitForResponse(
      r => r.url().includes('/answer') && r.request().method() === 'POST',
      { timeout: 8000 }),
    p.click('.qa.open .qsend'),
  ]);
  await p.waitForFunction(() => {
    const card = document.querySelector('.qa[data-qid]');
    if (!card) return false;
    return !!(card.querySelector('.qerr') || card.querySelector('.anstag'));
  }, null, { timeout: 4000 }).catch(() => {});
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
  REFUSAL_STATUSES.push(status);
  notes.push(`${label} (${status}): card="${after.cls}" ` +
             `err=${JSON.stringify(after.err)} kept=${JSON.stringify(after.kept)}`);
  await p.screenshot({ path: `${OUT}/write-refused-${status}.png`, fullPage: true });
  await p.close();
  return { status, after, typed };
};

const refused409 = await refusedWrite(409, '{"ok":false}', 'refused-409');
const refused202 = await refusedWrite(202, '{"ok":false,"rejected":true}', 'refused-202');

/* #413 coverage (R5): a refusal guard must drive the refusal on a status the
   client treats as SUCCESS as well as one it treats as failure — the moved
   contract is always the 2xx one. Derived from what was driven, not a literal
   count, so it cannot quietly shrink back to 409-only (the blindness this
   exists to prevent). */
ok('COVERAGE #413: refusal driven on a 4xx AND a 2xx (client branches on res.ok)',
   REFUSAL_STATUSES.some(s => s >= 400 && s < 500) &&
   REFUSAL_STATUSES.some(s => s >= 200 && s < 300) &&
   REFUSAL_STATUSES.length >= 2);

// the 4xx path — the existing, green invariants, unchanged
ok('a refused write says so, instead of nothing at all',
   !!refused409.after.err && /not written \(409\)/.test(refused409.after.err));
ok('...and never shows the answered state for a write that did not land',
   !refused409.after.claimedAnswered && /\bopen\b/.test(refused409.after.cls || ''));
ok('...and keeps his text, which is now the only copy of it',
   refused409.after.kept === refused409.typed);

// the 2xx path — E5: a refusal the client treats as success. RED against the
// pre-E5b client (res.ok true → the morph runs, the card restates answered,
// the text is cleared); green once E5b distinguishes a rejected 2xx from a
// successful one.
ok('E5: a rejected 202 (res.ok true) never shows the answered state for a write that did not land',
   !refused202.after.claimedAnswered && /\bopen\b/.test(refused202.after.cls || ''));
ok('E5: ...and keeps his text, which is now the only copy of it',
   refused202.after.kept === refused202.typed);
ok('E5: ...and says so rather than nothing (the message, not just the state)',
   !!refused202.after.err && /not written \(rejected\)/.test(refused202.after.err));

ok('no page errors', errs.length === 0);
await br.close();
stopAll();
finish();
