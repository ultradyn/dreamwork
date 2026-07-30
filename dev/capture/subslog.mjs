/* subslog — #175: the client records every submission, and the field that
   matters is the OUTCOME.

   #199 gave the SERVER a verbatim record of everything it received. This is
   the witness for the case that cannot cover: a submission the server never
   accepted, or never heard at all. A 409 from `append_answer` (#136), a
   rejection he clicked past (#162), a POST that never left because the server
   was restarting — in every one of those the client is the only party that
   knows what he tried to do.

   SO THE THREE OUTCOMES ARE THE THREE PHASES, and the interesting two are the
   failures: `ok`, `rejected` (the server said no), `unreachable` (it never
   answered). A guard that only drove a successful send would pass on a page
   that recorded nothing but successes, which is the shape with no recovery
   value at all.

   AND `pending` IS ASSERTED TO EXIST, not skipped over. The record is written
   BEFORE the request, so a tab that dies mid-POST leaves one saying exactly
   that. Checking it means catching the write in flight — the guard holds the
   response open and reads the store while the request is still outstanding,
   which is the only moment that state is true. Without it, "write first" is
   an unverified claim about ordering, and ordering is the entire feature.

   ALL THREE ENDPOINTS, because the composer used to own a `fetch` of its own
   and a third of his submissions would go unwitnessed if it still did.

   Shown red on the pre-#175 build: no database at all, so every phase FAILed
   including the vacuity check.

   usage: node subslog.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { waitFor } from './dom.mjs';
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

/* read through the page's own documented accessor — "it must be readable or
   it is theatre" is the task's own line, so the guard reads it the way a human
   would rather than reaching into IndexedDB behind the feature's back */
/* NULL when the accessor is absent, never a throw. A guard that dies on a page
   without the feature reports "the guard threw", which says nothing about the
   page and sends the reader to the wrong file — the same mistake this batch
   already made once, in draft.mjs. Absence is a FAIL with a sentence. */
const all = () => p.evaluate(
  `(typeof window.__dwSubmissions === 'function'
     ? window.__dwSubmissions().then(r => r || []) : Promise.resolve(null))`);
/* THE PAGE'S name, not one the guard rebuilds. Asking the guard to construct
   the expected string tests the guard: it passed on a build with no store at
   all. `subsDbName` is the function the feature actually uses. */
const dbName = () => p.evaluate(
  `(typeof subsDbName === 'function' ? subsDbName() : null)`);

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #428: networkidle fires when data.json is fetched but the client JS that
// defines __dwSubmissions and builds the .qa cards has not run; a fixed sleep
// graded a half-rendered page under load. Wait for the card the guard drives.
await waitFor(p, '.qa.open');

{
  const before = await all();
  const name = await dbName();
  notes.push(`store ${name}, ${before ? before.length + ' record(s)' : 'NO READER'}` +
             ' at start');
  ok('the log is reachable from the page (else it is theatre — the task\'s ' +
     'own words)', Array.isArray(before));
  ok('...and partitioned by the project PATH, so another loop\'s submissions ' +
     'cannot appear by a forgotten filter', /^dw-submissions:\//.test(name));
}

/* ── an ACCEPTED answer ───────────────────────────────────────────────── */
const OKTEXT = 'an answer that lands, witnessed ' + process.pid;
{
  await p.evaluate(`(async () => {
    const card = document.querySelector('.qa.open');
    card.querySelector('.qmode[data-mode=answer]').click();
    card.querySelector('textarea').value = ${JSON.stringify(OKTEXT)};
    card.querySelector('.qsend').click();
    await new Promise(r => setTimeout(r, 800));
  })()`);
  const recs = await all();
  const r = (recs || []).find(x => x.text === OKTEXT);
  notes.push(`accepted: ${JSON.stringify(r)}`);
  ok('an accepted answer is recorded', !!r && r.path === '/answer' &&
     r.kind === 'answer');
  ok('...with the outcome it actually had', !!r && r.outcome === 'ok' &&
     r.status === 202);
  ok('...and the page it was sent from (#126)', !!r && typeof r.from === 'string');
}

/* ── a REJECTED note: the server said no ─────────────────────────────── */
const REJTEXT = 'a note the file will not take ' + process.pid;
{
  await p.reload({ waitUntil: 'networkidle' });
  await waitFor(p, '.qa.open');   // #428 render readiness (same as the first load)
  await p.evaluate(`(async () => {
    const card = document.querySelector('.qa.open');
    // #266 correctly fails closed when a card cannot resolve its logical live
    // record, so inject #116's stale-title condition at the request boundary:
    // the real UI/client witness still run and the real server produces 409.
    const realFetch = window.fetch;
    window.fetch = async (...a) => {
      if (String(a[0]).startsWith('/comment')) {
        const opt = Object.assign({}, a[1] || {});
        const req = JSON.parse(opt.body);
        req.question = 'no such entry ' + Date.now();
        opt.body = JSON.stringify(req);
        a = [a[0], opt];
      }
      return realFetch(...a);
    };
    card.querySelector('.qmode[data-mode=note]').click();
    card.querySelector('textarea').value = ${JSON.stringify(REJTEXT)};
    card.querySelector('.qsend').click();
    await new Promise(r => setTimeout(r, 800));
    window.fetch = realFetch;
  })()`);
  const r = ((await all()) || []).find(x => x.text === REJTEXT);
  notes.push(`rejected: ${JSON.stringify(r)}`);
  // THE ASSERTION: the only witness to a submission the server refused.
  ok('a REJECTED note is recorded', !!r && r.path === '/comment');
  ok('...and says so, with the status the server gave',
     !!r && r.outcome === 'rejected' && r.status === 409);
}

/* ── UNREACHABLE: the server never answered ──────────────────────────── */
const OFFTEXT = 'a command into a dead socket ' + process.pid;
{
  const msg = await p.evaluate(`(async () => {
    const real = window.fetch;
    window.fetch = async (...a) => String(a[0]).startsWith('/command')
      ? Promise.reject(new TypeError('failed to fetch')) : real(...a);
    document.getElementById('cmdplus').click();
    await new Promise(r => setTimeout(r, 500));
    document.getElementById('cmdtext').value = ${JSON.stringify(OFFTEXT)};
    document.getElementById('cmdform').requestSubmit();
    await new Promise(r => setTimeout(r, 700));
    window.fetch = real;
    const m = document.querySelector('#cmdmsg');
    return m && m.textContent;
  })()`);
  const r = ((await all()) || []).find(x => x.text === OFFTEXT);
  notes.push(`unreachable: ${JSON.stringify(r)} (page said ${JSON.stringify(msg)})`);
  ok('a command that never reached the server is recorded', !!r &&
     r.path === '/command');
  ok('...as unreachable rather than as a rejection',
     !!r && r.outcome === 'unreachable' && r.status === 0);
  // the composer used to own its own fetch; if it still did, this record
  // would not exist at all and the page would still look correct
  ok('...which also proves the composer goes through the shared seam', !!r);
  ok('and the page still told him it failed', msg === 'no connection');
}

/* ── `pending` exists, caught in flight ──────────────────────────────── */
{
  const seen = await p.evaluate(`(async () => {
    let release;
    const gate = new Promise(r => { release = r; });
    const real = window.fetch;
    window.fetch = async (...a) => {
      if (String(a[0]).startsWith('/command')) { await gate; }
      return real(...a);
    };
    document.getElementById('cmdtext').value = 'held open mid-flight';
    document.getElementById('cmdform').requestSubmit();
    await new Promise(r => setTimeout(r, 400));
    // the request is still outstanding: this is the only moment the record is
    // allowed to say pending, and the only way to prove it is written FIRST
    // (no backticks in here — this whole string is a template literal)
    const rd = () => typeof window.__dwSubmissions === 'function'
      ? window.__dwSubmissions() : Promise.resolve([]);
    const mid = (await rd()) || [];
    release(); window.fetch = real;
    await new Promise(r => setTimeout(r, 600));
    const after = (await rd()) || [];
    const pick = rs => rs.find(x => x.text === 'held open mid-flight');
    return { mid: pick(mid), after: pick(after) };
  })()`);
  notes.push(`in flight: ${JSON.stringify(seen.mid && seen.mid.outcome)} -> ` +
             `${JSON.stringify(seen.after && seen.after.outcome)}`);
  ok('the record is written BEFORE the request, so a tab that dies mid-send ' +
     'leaves one', !!seen.mid && seen.mid.outcome === 'pending');
  ok('...and the outcome is attached when the answer comes back',
     !!seen.after && seen.after.outcome === 'ok');
}

/* ── nothing is ever removed ─────────────────────────────────────────── */
{
  const recs = (await all()) || [];
  const kinds = recs.map(r => r.outcome).sort();
  notes.push(`${recs.length} records kept: ${kinds.join(',')}`);
  ok('every submission of the run is still there (append-only: an entry is ' +
     'rewritten only to attach its outcome, and never deleted)',
     recs.length >= 4);
  ok('...and ids are monotonic, so a reader can order them',
     recs.length > 1 &&        // `every` over [] is true: say so explicitly
     recs.every((r, i) => i === 0 || r.id > recs[i - 1].id));
}

await p.screenshot({ path: `${OUT}/subslog.png`, fullPage: false });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
