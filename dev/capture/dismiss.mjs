/* The composer's behaviour guard: #131 (it must not close under him) and #126
   (a command carries the page it was sent from).

   #131 — the composer must not close under him.

   His words: "if on the composer, someone enters something, ctrl+enter
   submits, then starts typing again, the composer should not fade away. also
   the timeout before fading away should be increased by 1.5x."

   The auto-dismiss is a courtesy — it gets the panel out of the way once the
   thought has landed. A courtesy must never take a channel away from someone
   still using it, which is the same rule as #118. Three things are checked,
   and the first is the one a "does it close?" test would miss:

     - typing again CANCELS the dismiss, and it stays cancelled (the panel is
       still open well past the point it would have closed)
     - with no further typing it does still close, so the courtesy survives
     - it waits ~1.4s rather than ~0.95s, and it has NOT closed at 1.0s —
       asserting only the end state would pass on the old timing

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

// (1) submit and walk away: the courtesy still happens, on the new timing
await openPanel(p);
const alone = await p.evaluate(RUN(-1, 2600));
const tc = closedAt(alone);
notes.push(`left alone: closed at ${tc}ms` +
           ` | msg at 1000ms "${(alone.find(s => s[0] >= 1000) || [])[2]}"`);
ok('left alone, the panel still closes itself', tc !== null);
// the 1.5x is the point: at 1.0s the old build had already gone
ok('...but not on the old timing — still open at 1.0s', tc === null || tc > 1050);
ok('...and it does not linger either', tc !== null && tc < 2200);

// (2) he starts typing again inside the dismiss window
await openPanel(p);
const resumed = await p.evaluate(RUN(400, 3200));
const tr = closedAt(resumed);
const msgAfter = (resumed.find(s => s[0] >= 900) || [])[2];
notes.push(`resumed at 400ms: closed at ${tr} | msg at 900ms "${msgAfter}"`);
ok('typing again CANCELS the dismiss — the panel stays open', tr === null);
ok('...and it stays cancelled, not merely postponed',
   resumed.at(-1)[1] === true && resumed.at(-1)[0] > 3000);
// a "sent to the dream" above a fresh unsent thought is a false confirmation
ok('the stale confirmation clears when he resumes', !msgAfter);

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

ok('no page errors', errs.length === 0);
await br.close();

console.log(notes.join('\n'));
console.log('----');
console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
