/* reviewdraft — #269 acute: a drafted answer never leaves him on an autoreload.

   His report, verbatim into the composer: "draft answers to questions on
   review pages can be lost ... we must have persistence and never lose work
   on an autoreload of a page." The answer box had #118's IN-MEMORY snapshot,
   which carries a half-typed answer across a tick re-render — but a RELOAD
   (an F5, or `tick` calling `location.reload()` when the server's generation
   bumps) drops the page's memory and his words with it. The composer has had
   a localStorage store for the same shape of loss since #163; the answer box
   had none. This guard proves the answer box now has one, by the SAME rules.

   TWO LOSS MODES, both driven, because a guard that proves only the reload
   would pass over the live re-render if that were the one biting him (and he
   said "autoreload", which pointed there). Reproduced first to diagnose, and
   the diagnosis is in the report: mode 2 (the tick) was already covered by
   #118's snapshot; mode 1 (the reload) was the real loss. This guard drives
   BOTH and would catch a regression in either:

     MODE 2 (live re-render)  — type into the docked box, force a tick by
       bumping .dreamwork mtime, then assert the text survives. THE NODE IS
       PROVEN RECREATED: the textarea is tagged before the re-render and the
       guard asserts the tag is gone after, so a re-render that never
       happened cannot make this check pass over the bug (the exact trap that
       hit two checks here the day this landed).
     MODE 1 (reload)          — type, reload the page for real, assert the
       text is back in the box. This is the loss he reported; it is RED on
       the pre-fix build and GREEN after.

   THE CONTRACT, asserted both ways like draft.mjs does for the composer: the
   draft survives everything EXCEPT a successful send, and is GONE after one.
   A check for only the first passes on a page that never forgets; a check
   for only the second passes on a page that saves nothing. Both, or neither.

   RUN AGAINST NOTHING FIRST: with no draft stored, the box is left empty
   rather than filled with "null" or "undefined" — the vacuous-pass trap, at
   the feature.

   THE PARTITION IS ASSERTED AT RUNTIME, not against a literal. The key is
   `dw:adraft:<target>:<title>` — partitioned by the absolute project path
   (so two checkouts sharing a basename stay apart) AND by the question's
   title identity. Both halves are DERIVED from the live page (data.target +
   data-qid), and the guard asserts the stored key matches both, so a check
   tuned to today's fixture does not read green against tomorrow's.

   Shape: own target and own server on the guard's exclusive port (39894),
   because the clear-on-success phase POSTs a real answer and mutates the
   fixture — pristine for the next run, and never fighting the shared guard
   server for a port.

   usage: node reviewdraft.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync, rmSync, cpSync, utimesSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join } from 'node:path';

const OUT = process.argv[2];
const PORT = process.argv[3] || '39894';   // this guard's exclusive port
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const r = makeReporter();
const { ok, present, declare, finish, checks, notes, errs } = r;
declare({
  drives: '/review route — types into the docked answer box; forces a tick ' +
          're-render by bumping .dreamwork mtime; reloads the page; POSTs a ' +
          'real answer and a forced-failure send',
  traceWindow: 'polls up to ~6s for the textarea node identity to change after ' +
               'each forced mtime bump — the natural 2s /mtime poll is the ' +
               're-render trigger, so the window must cover at least one'
});

// ── own target + own server, reaped on every exit path ───────────────────
const DIR = join(OUT, 'target');
const reset = () => {
  rmSync(DIR, { recursive: true, force: true });
  cpSync('dev/capture/fixture', DIR, { recursive: true });
};
reset();
const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', PORT],
                  { stdio: 'ignore' });
const reap = () => { try { srv.kill('SIGTERM'); } catch (e) {} };
process.on('exit', reap);
process.on('SIGINT', () => { reap(); process.exit(130); });
process.on('SIGTERM', () => { reap(); process.exit(143); });

await sleep(2200);
const BASE = `http://127.0.0.1:${PORT}`;
let br = null;                                   // closed on every exit path
const br_safe_close = async () => { try { if (br) await br.close(); } catch (e) {} };
{
  let d = null;
  try { d = await (await fetch(`${BASE}/data.json`)).json(); } catch (e) {}
  if (!d || d.target !== DIR) {
    // #203: a stale server holding the port would otherwise be graded. Name it
    // and stop rather than assert fixture facts at a server that is not ours.
    notes.push(`:${PORT} is serving ${d && d.target} (not ${DIR}); aborting`);
    reap(); finish(); process.exit(0);
  }
}

br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1400, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

// the fixture's P1 open question — its title is the stable data-qid identity
const Q = 'P1 · 2026-07-25 — a second open question, so answering the first leaves a neighbour to close the gap.';
const URL = `${BASE}/review?p=.dreamwork/review/fixture-review.html&q=${encodeURIComponent(Q)}`;
const load = async () => { await p.goto(URL, { waitUntil: 'networkidle' }); await sleep(1300); };

// tag the live textarea node so a re-render is detectable as an identity change
const TAG = '__reviewdraft_probe';
const tagNode = () => p.evaluate((tag) => {
  const t = document.querySelector('#qdock textarea[id^="qi"]');
  if (t) t[tag] = true;
}, TAG);
// bump .dreamwork mtime so the next /mtime poll re-renders #qdock for real
const bumpMtime = () => {
  const f = join(DIR, '.dreamwork', 'lessons.md');
  const now = new Date();
  try { utimesSync(f, now, now); } catch (e) {}
};
// poll until the tagged node is gone (a genuine re-render) or the budget ends
const awaitRerender = async (budgetMs = 6000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < budgetMs) {
    await sleep(150);
    const tagged = await p.evaluate((tag) => {
      const t = document.querySelector('#qdock textarea[id^="qi"]');
      return !!(t && t[tag]);
    }, TAG);
    if (!tagged) return { recreated: true, waited: Date.now() - t0 };
  }
  return { recreated: false, waited: budgetMs };
};
const boxValue = () => p.evaluate(() => {
  const t = document.querySelector('#qdock textarea[id^="qi"]');
  return t ? t.value : null;
});
// read the stored draft key + payload, deriving the expected halves at runtime.
// `data` is a top-level `let` in the page script (a lexical global, NOT on
// window — `window.data` is undefined), so it is read as a bare identifier
// with the same typeof guard the composer's draftKey uses.
const stored = () => p.evaluate(() => {
  const tgt = (typeof data !== 'undefined' && data && data.target) || '';
  const card = document.querySelector('#qdock .qa[data-qid]');
  const qid = card ? card.dataset.qid : '';
  const prefix = 'dw:adraft:' + tgt + ':';
  let found = null;
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.indexOf(prefix) === 0) { found = { key: k, raw: localStorage.getItem(k) }; break; }
  }
  return { tgt, qid, prefix, found };
});
const typeReal = async text => {
  await p.click('#qdock textarea[id^="qi"]');
  await p.fill('#qdock textarea[id^="qi"]', '');
  // type with real input events — the save hangs off `input`, so .value alone
  // would test nothing (draft.mjs's rule, one surface over)
  await p.type('#qdock textarea[id^="qi"]', text, { delay: 1 });
  await sleep(150);
};

await load();
if (!(await present(p, '#qdock textarea[id^="qi"]',
                    'the review-dock answer box'))) {
  await br_safe_close(); reap(); finish(); process.exit(0);
}

// ── against nothing, first ───────────────────────────────────────────────
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  const v = await boxValue();
  notes.push(`with nothing stored, the box holds ${JSON.stringify(v)}`);
  ok('with no draft stored, the box is left empty (not "null", not "undefined")',
     v === '');
}

const TEXT = 'half-typed answer beside the artifact, mid-thought and';

// ── MODE 2: the live re-render — the one the brief named first ───────────
{
  await typeReal(TEXT);
  // tag the CURRENT node, then force the tick that recreates #qdock
  await tagNode();
  bumpMtime();
  const re = await awaitRerender();
  notes.push(`mode 2: re-render ${re.recreated ? 'detected' : 'NOT detected'} ` +
             `after ${re.waited}ms (tagged node ${re.recreated ? 'replaced' : 'still present'})`);
  // THE PRECONDITION: if the re-render never happened, every check below is
  // about a node that was never recreated — so assert it FIRST, by name.
  ok('MODE 2 precondition: the answer-box node was genuinely recreated ' +
     '(else the survival check below proves nothing)', re.recreated);
  const v = await boxValue();
  notes.push(`mode 2: box holds ${JSON.stringify(v)} after the re-render`);
  ok('MODE 2: the draft survives the live re-render that recreated the box',
     v === TEXT);
}

// ── MODE 1: the full reload — the loss he actually reported ─────────────
{
  // freshen the text (in case anything cleared it), then reload for real
  await typeReal(TEXT);
  const pre = await boxValue();
  notes.push(`mode 1: typed ${JSON.stringify(pre)} before reload`);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1300);
  const v = await boxValue();
  notes.push(`mode 1: box holds ${JSON.stringify(v)} after reload`);
  ok('MODE 1: the draft survives a full page reload (the reported loss)',
     v === TEXT);
}

// ── the partition: key derived from BOTH target and question title ───────
{
  const s = await stored();
  notes.push(`partition: prefix=${JSON.stringify(s.prefix)} qid=${JSON.stringify(s.qid)}`);
  ok('a draft is stored at all (the save-on-input fired)',
     !!(s.found && s.found.raw));
  ok('the draft key is partitioned by the absolute target path ' +
     '(dw:adraft:<target>:…)', !!(s.found && s.found.key.indexOf(s.prefix) === 0));
  ok('...and by the question\'s title identity (data-qid), never the positional ' +
     'key, so a re-sort or a re-index cannot put it under the wrong question',
     !!(s.found && s.qid && s.found.key === s.prefix + decodeURIComponent(s.qid)));
  ok('the stored payload is the JSON the helper writes (not a bare string, so ' +
     'a future field can be added without a second format)',
     !!(s.found && /^\{"t":/.test(s.found.raw)));
}

// ── the contract, asserted both ways ─────────────────────────────────────
/* a REJECTED send keeps it — the moment he most needs it back. The box is
   reloaded-fresh so the only draft in storage is the one this phase writes,
   and the next /answer is forced to fail the way a restarting server does. */
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  await typeReal(TEXT);
  await p.evaluate(() => {
    const real = window.fetch;
    window.fetch = (...a) => String(a[0]).indexOf('/answer') === 0
      ? Promise.resolve(new Response('no', { status: 500 }))
      : real(...a);
    document.querySelector('#qdock .qsend').click();
  });
  await sleep(600);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1300);
  const v = await boxValue();
  notes.push(`rejected send: box holds ${JSON.stringify(v)} after a 500 + reload`);
  ok('a REJECTED send keeps the draft (cleared only on durable success)', v === TEXT);
}

/* a SUCCESSFUL answer forgets it — the one moment it is safe. The real POST
   mutates the fixture (P1 gains an answer), which is why this guard owns its
   target. After it, the card leaves the open list, so the box is gone too:
   the assertion is that storage no longer holds a draft for this question. */
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  await typeReal(TEXT);
  await p.evaluate(() => document.querySelector('#qdock .qsend').click());
  await sleep(800);
  const s = await stored();
  notes.push(`successful answer: stored=${JSON.stringify(s.found)} (title no ` +
             `longer open, so a fresh card may be absent — the key is what counts)`);
  ok('a SUCCESSFUL answer clears the draft (no key remains for the question)',
     !(s.found && s.found.raw));
}

ok('no page errors', errs.length === 0);

await br_safe_close();
reap();
finish();
