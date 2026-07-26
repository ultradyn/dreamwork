/* draft — #163: the composer's half-typed thought survives a reload, and is
   forgotten at exactly one moment.

   The panel already keeps its text across a close and a route change — it
   lives outside `#view`, so nothing rebuilds it. What loses his words is a
   RELOAD, including the one the page performs on him: `tick` calls
   `location.reload()` when the server's generation changes. So every phase
   here reloads for real rather than closing and reopening, because closing and
   reopening passed before this feature existed.

   THE TWO ASSERTIONS THAT ARE THE CONTRACT, and they pull against each other:

     - it SURVIVES everything except a successful send — a reload, a rejected
       send, an emptied-then-refilled box, the mode-switch defocus path (#162b,
       which the brief asked to be checked here rather than assumed);
     - it is GONE after a successful send, because a draft that outlives the
       command it became would re-appear as a thought he already had.

   A check for only the first passes on a page that never forgets anything, and
   a check for only the second passes on a page that saves nothing. Both, or
   neither is evidence.

   RUN AGAINST NOTHING FIRST: with no draft stored, the restore path must leave
   an empty box empty rather than writing "null" or "undefined" into it — the
   vacuous-pass trap, aimed at the feature instead of at the guard.

   Shown red on the pre-#163 build: the reload phases came back with an empty
   box, and the clear-on-send phase passed (nothing was ever stored), which is
   exactly why both directions are asserted.

   usage: node draft.mjs <outdir> <port> */
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

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

const load = async () => {
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1200);
};
/* IDEMPOTENT, because `#cmdplus` is a toggle: calling this on an already-open
   composer used to close it, and the next `p.click('#cmdtext')` then hung on a
   `pointer-events:none` panel until the guard timed out — a real failure that
   read as "the guard threw", which says nothing about the page. */
const openComposer = async () => {
  const isOpen = await p.evaluate(
    `!!document.querySelector('#cmdpalette.open')`);
  if (!isOpen) { await p.click('#cmdplus'); await sleep(700); }
};
/* type through the real box, with real input events — the save hangs off
   `input`, so setting `.value` would test nothing */
const type = async text => {
  await p.click('#cmdtext');
  await p.fill('#cmdtext', '');
  await p.type('#cmdtext', text, { delay: 1 });
  await sleep(120);
};
const boxAfterReload = async () => {
  await load();
  await openComposer();
  return await p.evaluate(`(() => {
    const t = document.getElementById('cmdtext');
    const on = document.querySelector('#cmdkinds .sgbtn.on');
    return { value: t ? t.value : null, kind: on ? on.dataset.kind : null };
  })()`);
};
const stored = () => p.evaluate(`(() => {
  const k = 'dw:draft:' + (data && data.target);
  const raw = localStorage.getItem(k);
  return { key: k, raw };
})()`);

await load();

/* ── against nothing, first ───────────────────────────────────────────── */
{
  await p.evaluate(`localStorage.clear()`);
  await openComposer();
  const v = await p.evaluate(`document.getElementById('cmdtext').value`);
  notes.push(`with nothing stored, the box holds ${JSON.stringify(v)}`);
  ok('with no draft stored, the box is left empty (not "null", not "undefined")',
     v === '');
}

/* ── it survives a real reload, with its kind ─────────────────────────── */
const TEXT = 'a half-typed thought about the regroup, mid-sentence and';
{
  // pick a NON-default kind, so the restore has something to prove
  const kind = await p.evaluate(`(() => {
    const bs = [...document.querySelectorAll('#cmdkinds .cmdkind')];
    const b = bs[bs.length - 1]; b.click(); return b.dataset.kind;
  })()`);
  await type(TEXT);
  const s = await stored();
  notes.push(`stored under ${s.key}: ${s.raw}`);
  ok('typing writes a draft for THIS project (keyed by the target path)',
     !!s.raw && s.key.startsWith('dw:draft:/') && s.raw.includes('thought'));

  const after = await boxAfterReload();
  notes.push(`after reload: ${JSON.stringify(after)}`);
  // THE ASSERTION.
  ok('after a reload, his words are back in the box', after.value === TEXT);
  ok('...and so is the kind they were meant for (#103: the kind is WHERE the ' +
     'text goes)', after.kind === kind);
}

/* ── #162(b): the mode-switch defocus path, checked rather than assumed ── */
{
  // TYPED FRESH, not inherited from the phase above. The first version of this
  // check ran straight after a reload, so in a red run its "the live text
  // survived" assertion was really re-testing the restore — it would have
  // reported the mode-switch path as broken on a build where only the restore
  // was missing. A check that cannot fail for its own stated reason is worse
  // than no check, because its message names the wrong thing.
  await openComposer();
  await type(TEXT);
  await p.evaluate(`(() => {
    const bs = [...document.querySelectorAll('#cmdkinds .cmdkind')];
    bs[0].click();                       // switch back to a default kind
  })()`);
  await sleep(400);
  const live = await p.evaluate(`document.getElementById('cmdtext').value`);
  const after = await boxAfterReload();
  notes.push(`after the mode switch: live box ${JSON.stringify(live)}, ` +
             `after reload ${JSON.stringify(after.value)}`);
  ok('#162(b): switching mode does not take the live text with it',
     live === TEXT);
  ok('#162(b): ...and the stored draft survives it too', after.value === TEXT);
}

/* ── a REJECTED send keeps it — the moment he most needs it back ──────── */
{
  const status = await p.evaluate(`(async () => {
    // make the next POST fail the way a restarting server does
    const real = window.fetch;
    window.fetch = async (...a) => String(a[0]).startsWith('/command')
      ? new Response('no', { status: 500 }) : real(...a);
    document.getElementById('cmdform').requestSubmit();
    await new Promise(r => setTimeout(r, 400));
    window.fetch = real;
    return document.querySelector('.cmdmsg') &&
           document.querySelector('.cmdmsg').textContent;
  })()`);
  const after = await boxAfterReload();
  notes.push(`after a rejected send (msg ${JSON.stringify(status)}): ` +
             `${JSON.stringify(after.value)}`);
  ok('a REJECTED send keeps the draft', after.value === TEXT);
}

/* ── ...and a successful one forgets it ───────────────────────────────── */
{
  await p.evaluate(`document.getElementById('cmdform').requestSubmit()`);
  await sleep(600);
  const s = await stored();
  const after = await boxAfterReload();
  notes.push(`after a successful send: stored ${JSON.stringify(s.raw)}, ` +
             `after reload ${JSON.stringify(after.value)}`);
  ok('a SUCCESSFUL send clears the draft', !s.raw);
  ok('...so a reload does not resurrect a thought he already sent',
     after.value === '');
}

/* ── do-now is immediate; after success the composer returns to capture ── */
{
  await openComposer();
  await p.click('.cmdkind[data-kind="do-now"]');
  await type('the urgent thing');
  await p.evaluate(`document.getElementById('cmdform').requestSubmit()`);
  await sleep(600);
  const kind = await p.evaluate(
    `document.querySelector('#cmdkinds .cmdkind.on').dataset.kind`);
  ok('after a successful do-now, the composer returns to add idea',
     kind === 'add-idea');
}

/* ── emptying the box is his act, and the store follows it ────────────── */
{
  await type('something he then thinks better of');
  await p.fill('#cmdtext', '');
  await p.evaluate(`document.getElementById('cmdtext')
    .dispatchEvent(new Event('input', { bubbles: true }))`);
  await sleep(150);
  const s = await stored();
  notes.push(`after emptying the box by hand: stored ${JSON.stringify(s.raw)}`);
  ok('emptying the box clears the store (deleting text is deliberate, ' +
     'unlike closing or a failed send)', !s.raw);
}

await p.screenshot({ path: `${OUT}/draft.png`, fullPage: false });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
