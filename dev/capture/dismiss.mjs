/* The composer's behaviour guard: #131 (it must not close under him), #159
   (its status line arrives rather than appearing) and #126 (a command carries
   the page it was sent from).

   #159 — the confirmation ARRIVES.

   Traced per frame, and that is the whole design of the check: "did the text
   turn up" passes on the bug, and so does a two-frame fade — it looks instant
   and satisfies every end-state assertion. What separates arriving from
   appearing is the NUMBER of intermediate values on the way, so that is what
   is asserted, on opacity and on the drift. It was shown red by returning
   early from `setCmdMsg` before the `.dreamin` snap: one distinct opacity
   (100), one distinct transform (none), from the first lit frame.

   #131/#255 — the composer must not close under him, while a valid success
   confirmation keeps and completes its own lifecycle.

   His words: "if on the composer, someone enters something, ctrl+enter
   submits, then starts typing again, the composer should not fade away. also
   the timeout before fading away should be increased by 1.5x."

   The auto-dismiss is a courtesy — it gets the panel out of the way once the
   thought has landed. A courtesy must never take a channel away from someone
   still using it, which is the same rule as #118. Three things are checked,
   and the first is the one a "does it close?" test would miss:

     - typing again CANCELS the dismiss, and it stays cancelled (the panel is
       still open well past the point it would have closed)
     - with no further typing it closes after ~1.5s (#291 / original #131
       1425ms courtesy). Panel close is destruction: the confirmation is
       hard-cleared with the panel. #255's ~5s lifecycle applies when the
       panel STAYS open (typing cancelled the courtesy)
     - typing does not truncate a valid success; that success departs/clears
       independently while the panel remains open

   Writes to the target it is pointed at (POST /command), so point it at a
   scratch copy.  usage: node dismiss.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];

/* Submit through the real UI, then sample "is the panel open" every frame for
   `ms`. `resumeAt` types one more character at that many ms after the submit,
   which is the whole point of the task. */
const RUN = (resumeAt, ms) => `((resumeAt, ms) => new Promise(res => {
  const pal = document.getElementById('cmdpalette');
  const ta = document.getElementById('cmdtext');
  const msg = document.getElementById('cmdmsg');
  const seen = [];
  ta.value = 'a thought for the dream';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('cmdform').requestSubmit();
  const t0 = performance.now();
  let typed = false;
  (function step() {
    const t = performance.now() - t0;
    if (resumeAt >= 0 && !typed && t >= resumeAt) {
      typed = true;
      ta.value = 'and a second thought';
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    }
    seen.push([Math.round(t), pal.classList.contains('open'),
               (msg.textContent || '').slice(0, 20)]);
    if (t < ms) requestAnimationFrame(step);
    else res(seen);
  })();
}))(${resumeAt}, ${ms})`;

/* #159: submit through the real UI and sample the status line every frame.
   The computed values, not the class — a class that is added and removed
   proves the code ran, never that anything moved. */
const ARRIVE = ms => `((ms) => new Promise(res => {
  const m = document.getElementById('cmdmsg');
  const ta = document.getElementById('cmdtext');
  const seen = [];
  ta.value = 'a thought whose confirmation is traced';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('cmdform').requestSubmit();
  const t0 = performance.now();
  (function step() {
    const cs = getComputedStyle(m);
    seen.push({ t: Math.round(performance.now() - t0),
                text: (m.textContent || '').slice(0, 24),
                op: Math.round(parseFloat(cs.opacity) * 100),
                tf: cs.transform });
    if (performance.now() - t0 < ms) requestAnimationFrame(step); else res(seen);
  })();
}))(${ms})`;

const openPanel = async p => {
  await p.click('#cmdplus');
  await p.waitForFunction(
    () => document.getElementById('cmdpalette').classList.contains('open'));
  await sleep(250);
};
// when did it first report closed? null means it never did
const closedAt = seen => {
  const i = seen.findIndex(s => !s[1]);
  return i < 0 ? null : seen[i][0];
};

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1200, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1000);

// (0) #159 — the confirmation arrives. First, because the page is freshly
// loaded and the panel is shut; it ends with Escape so the phases below start
// from the same place they always did.
{
  await openPanel(p);
  const seen = await p.evaluate(ARRIVE(700));
  const lit = seen.filter(s => s.text);
  const ops = lit.map(s => s.op), tfs = lit.map(s => s.tf);
  notes.push(`arrival: ${lit.length} lit frames, ` +
             `opacity ${[...new Set(ops)].slice(0, 12).join(',')}` +
             `${new Set(ops).size > 12 ? ',…' : ''} ` +
             `| ${new Set(tfs).size} distinct transforms`);
  ok('the confirmation reaches the page at all (else the rest is vacuous)',
     lit.length > 0 && /sent to the dream/.test(lit.at(-1).text));
  ok('#159 it begins at nothing rather than fully lit',
     lit.length > 0 && Math.min(...ops) <= 5);
  // the trap the task named: a two-frame fade looks instant and passes
  // every "did it fade in" check there is
  ok('#159 ...and eases up through many intermediate values',
     new Set(ops).size >= 6);
  ok('#159 ...drifting into place as it comes, not only fading',
     new Set(tfs).size >= 4);
  ok('#159 ...and it ends fully lit', lit.length > 0 && ops.at(-1) >= 95);
  await p.keyboard.press('Escape');
  await p.waitForFunction(
    () => !document.getElementById('cmdpalette').classList.contains('open'));
}

// (1) submit and walk away: ~1.5s courtesy (#291), not the ~5s confirm hold
await openPanel(p);
const alone = await p.evaluate(RUN(-1, 2800));
const tc = closedAt(alone);
const msgAt1s = (alone.find(s => s[0] >= 1000) || [])[2];
notes.push(`left alone: closed at ${tc}ms` +
           ` | msg at 1000ms "${msgAt1s}"`);
ok('left alone, the panel still closes itself', tc !== null);
// was 950ms; his 1.5x → 1425ms. Bound so a 5s confirm-tied close fails red.
ok('#291 ...after the ~1.5s courtesy window', tc !== null && tc > 1200);
ok('#291 ...without waiting out the confirmation lifecycle',
   tc !== null && tc < 2200);
// panel close is destruction: by the time it is shut the line is gone
ok('#291 ...and closing the panel hard-clears the confirmation with it',
   tc !== null && !(alone.find(s => s[0] >= tc + 50) || [])[2]);

// (2) he starts typing again inside the dismiss window
await openPanel(p);
const resumed = await p.evaluate(RUN(400, 6800));
const tr = closedAt(resumed);
const msgAfter = (resumed.find(s => s[0] >= 900) || [])[2];
const msgFinal = resumed.at(-1)[2];
notes.push(`resumed at 400ms: closed at ${tr} | msg at 900ms "${msgAfter}" final "${msgFinal}"`);
ok('typing again CANCELS the dismiss — the panel stays open', tr === null);
ok('...and it stays cancelled, not merely postponed',
   resumed.at(-1)[1] === true && resumed.at(-1)[0] > 3000);
ok('#255 typing does not truncate the valid success confirmation',
   /sent to the dream/.test(msgAfter));
ok('#255 ...and success clears on its own lifecycle', !msgFinal);

await p.screenshot({ path: `${OUT}/composer.png` });

/* #126 — a command carries the page it was sent from, all the way to the line
   the loop wakes on. The client half is what could silently stop working: the
   server's formatting is a pure function with its own unit tests, but nothing
   else proves the page ever puts `from` in the body.

   Read back from the real events log rather than from the POST, because the
   log line is the artifact — it is what an agent tails and acts on. */
const rev = await p.evaluate(async () =>
  (await (await fetch('/data.json')).json()).reviews[0]);
if (rev) {
  const url = `/review?p=${encodeURIComponent(rev.name)}`;
  await p.goto(BASE + url, { waitUntil: 'networkidle' }); await sleep(900);
  await openPanel(p);
  await p.evaluate(() => {
    const ta = document.getElementById('cmdtext');
    ta.value = 'a steer sent while reading the artifact';
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('cmdform').requestSubmit();
  });
  await sleep(600);
  const log = await p.evaluate(async () => {
    const r = await fetch('/filedata?p=' +
      encodeURIComponent('.dreamwork/watch-events.log'));
    return r.ok ? (await r.json()).content : '';
  });
  const line = log.trim().split('\n').filter(Boolean).at(-1) || '';
  notes.push(`events line: ${line}`);
  ok('the command line names the page it was sent from, query string and all',
     line.includes(`[${url}]`));
  // it is a hint, so it sits OUTSIDE the command rather than inside it — an
  // agent reading the line must not be able to mistake it for what was typed
  ok('...beside the command, not inside it',
     line.includes(`[${url}]: `) && !line.split(': ').slice(1).join(': ')
       .includes(url));
} else {
  ok('fixture has a review artifact to send a command from', false);
}

/* #159 under reduced motion — timing changes, function never does. The line
   must still say the steer landed; it simply says it at once. */
{
  const ctx = await br.newContext({ viewport: { width: 1200, height: 900 },
                                    reducedMotion: 'reduce' });
  const rp = await ctx.newPage();
  rp.on('pageerror', e => errs.push(String(e)));
  await rp.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(900);
  await openPanel(rp);
  const seen = await rp.evaluate(ARRIVE(500));
  const lit = seen.filter(s => s.text);
  const ops = lit.map(s => s.op);
  notes.push(`reduced arrival: ${lit.length} lit frames, ` +
             `opacity ${[...new Set(ops)].join(',')}`);
  ok('reduced motion: the confirmation still says the steer landed',
     lit.length > 0 && /sent to the dream/.test(lit.at(-1).text));
  ok('reduced motion: ...and it is simply there, never ramping',
     lit.length > 0 && ops.every(o => o >= 95));
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();

console.log(notes.join('\n'));
console.log('----');
console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
