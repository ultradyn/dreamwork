/* submitlog — #199: a submission that is REFUSED still leaves his words on disk.

   His framing: "because the user's time is the most valuable thing". Before
   this, an answer he typed lived in exactly one place — questions.md — and
   `_handle_answer` returned on `not matched` with nothing written anywhere.

   THE CHECK THAT MATTERS IS THE FAILING SUBMISSION, and it is the only one
   here that could not have been written before the feature. That a successful
   answer is recorded proves nothing: it is recorded *by having been written to
   questions.md*, which was always true. So the driving phases deliberately
   produce a real 409 and then look for his text.

   THE 409 IS PRODUCED AT THE REQUEST BOUNDARY. #266 made logical question IDs
   fail closed when a rendered card cannot resolve to its live record, so the
   old guard's mutation of `data.questions_open[i].title` correctly stopped the
   send before fetch and no longer tested #199. The temporary fetch wrapper now
   changes only the outgoing question title to a guaranteed non-match. The real
   box, send handler, client witness, HTTP request, authority checks and server
   `append_*` path still run; only the stale title condition is injected.

   Everything else is real: his text goes into the real box, the real `.qsend`
   is clicked with a real pointer, the client's own fetch carries it, and the
   log is read back over HTTP rather than off disk — the guard is handed a
   port, not a target directory, and inventing a path from `OUT/..` is how a
   guard ends up asserting against the wrong tree.

   Shown red against the pre-#199 server: the log file does not exist, so
   /filedata 404s and every phase FAILs on "his text survived".

   usage: node submitlog.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
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

/* the log, read back through the server the same way any other target file is
   read. A missing file is [] rather than a throw: "it was never written" is
   the pre-feature state and belongs in a FAIL line, not a stack trace. */
async function submissions() {
  const r = await fetch(
    `${BASE}/filedata?p=${encodeURIComponent('.dreamwork/submissions.log')}`);
  if (!r.ok) return null;
  return (await r.json()).content.split('\n').filter(Boolean)
    .map(ln => { try { return JSON.parse(ln); } catch { return { BAD: ln }; } });
}
const questionsMd = async () => {
  const r = await fetch(
    `${BASE}/filedata?p=${encodeURIComponent('.dreamwork/questions.md')}`);
  return r.ok ? (await r.json()).content : '';
};

/* Each phase's text carries an unbroken TOKEN, and questions.md is only ever
   searched for that.

   The reason is worth keeping: `append_answer` HARD-WRAPS what he wrote, so
   the answer in the file is not his string — the first version of this guard
   searched for the whole sentence, found "an answer that lands\n    3160481",
   and reported that an accepted answer had not landed. Which is also the
   sharpest argument for this whole feature: questions.md is a rendering of his
   words, and `submissions.log` is the only verbatim copy. So the LOG is
   checked for the complete text and questions.md only for the token. */
const TOKEN = k => `SUBMITLOG-${process.pid}-${k}`;

/* One submission through the real UI. `breakIt` rewrites only the outgoing
   request's title, producing a genuine server-side 409 without defeating
   #266's fail-closed logical-card resolver. Returns the status the client saw. */
const SEND = (mode, text, breakIt) => `(async () => {
  const card = document.querySelector('.qa.open');
  if (!card) return { err: 'no open card on /questions' };
  const ta = card.querySelector('textarea');
  const key = ta.id.slice(2);
  const entry = data.questions_open[+key.slice(1)];
  if (!entry) return { err: 'no entry behind the card' };
  const titleSent = entry.title;
  let status = 0;
  const realFetch = window.fetch;
  window.fetch = async (...a) => {
    const write = String(a[0]).startsWith('/answer') ||
                  String(a[0]).startsWith('/comment');
    if (write && ${breakIt}) {
      const opt = Object.assign({}, a[1] || {});
      const req = JSON.parse(opt.body);
      req.question = 'a title no entry in the file has ' + Date.now();
      opt.body = JSON.stringify(req);
      a = [a[0], opt];
    }
    const res = await realFetch(...a);
    if (write) status = res.status;
    return res;
  };
  card.querySelector('.qmode[data-mode=${mode}]').click();
  ta.value = ${JSON.stringify(text)};
  card.querySelector('.qsend').click();
  await new Promise(r => setTimeout(r, 600));
  window.fetch = realFetch;
  return { status, titleSent, cls: card.className };
})()`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1400 } });
p.on('pageerror', e => errs.push(String(e)));

/* ── a refused ANSWER ─────────────────────────────────────────────────── */
const ANS = `an hour of his thinking, refused at the door ${TOKEN('ANS')}`;
{
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.qa.open textarea', { state: 'visible', timeout: 10000 });
  await sleep(1200);
  const r = await p.evaluate(SEND('answer', ANS, true));
  const log = await submissions();
  const md = await questionsMd();
  notes.push(`refused answer: client saw ${r.status}; ` +
             `${log ? log.length : 'NO'} log line(s); setup ${JSON.stringify(r)}`);
  ok('the refused answer really was refused (else this proves nothing)',
     r.status === 409);
  ok('...and questions.md really did not take it (else it was never at risk)',
     !md.includes(TOKEN('ANS')));
  // THE ASSERTION.
  ok('...and his words are on disk anyway',
     !!log && log.some(l => l.path === '/answer' &&
                            JSON.stringify(l.req || l.raw || '').includes(ANS)));
}

/* ── a refused NOTE, because two write paths had the identical hole ───── */
const NOTE = `his follow-up, refused at the door ${TOKEN('NOTE')}`;
{
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.qa.open textarea', { state: 'visible', timeout: 10000 });
  await sleep(1200);
  const r = await p.evaluate(SEND('note', NOTE, true));
  const log = await submissions();
  notes.push(`refused note: client saw ${r.status}`);
  ok('the refused note really was refused', r.status === 409);
  ok('...and his words are on disk anyway',
     !!log && log.some(l => l.path === '/comment' &&
                            JSON.stringify(l.req || l.raw || '').includes(NOTE)));
}

/* ── and the accepted one is kept too, so the file is a complete record ─ */
const GOOD = `an answer that lands ${TOKEN('GOOD')}`;
{
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.qa.open textarea', { state: 'visible', timeout: 10000 });
  await sleep(1200);
  const r = await p.evaluate(SEND('answer', GOOD, false));
  await sleep(400);
  const log = await submissions();
  const md = await questionsMd();
  notes.push(`accepted answer: client saw ${r.status}`);
  // the TOKEN in questions.md, the whole string in the log — the file wraps
  ok('the accepted answer landed', r.status === 200 && md.includes(TOKEN('GOOD')));
  ok('...and is in the log as well as in questions.md',
     !!log && log.some(l => l.path === '/answer' &&
                            JSON.stringify(l.req || '').includes(GOOD)));
}

/* ── the shape, over everything the three phases produced ─────────────── */
{
  const log = await submissions();
  notes.push(`shape: ${log ? log.length : 'NO'} line(s) checked`);
  ok('there is a log to check the shape of (else the loop below is vacuous)',
     !!log && log.length >= 3);
  if (log && log.length) {
    ok('every line parses as a JSON object', log.every(l => l && !l.BAD));
    ok('...carrying t, path and bytes',
       log.every(l => typeof l.t === 'string' && typeof l.path === 'string' &&
                      typeof l.bytes === 'number'));
    ok('...and exactly one of req / raw, with why iff raw',
       log.every(l => (('req' in l) !== ('raw' in l)) &&
                      (('why' in l) === ('raw' in l))));
  }
}

await p.screenshot({ path: `${OUT}/submitlog.png`, fullPage: false });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
