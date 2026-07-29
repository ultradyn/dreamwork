/* restcollapse — status "+ the rest (N)" open state survives the live tick.

   His report (2026-07-30 03:30): the collapsible resets after being open
   for ~1 second.

   Cause: expand() emitted details.peek without data-keep. snapshotFolds
   only walks details[data-keep]; the live tick rebuilds the dashboard
   through innerHTML whenever a watched file's mtime moves (status.json /
   /command → watch-events.log), so the disclosure reappears closed. Same
   class as #141 (qsec) and #494 (burndown tip).

   Load-bearing preconditions (a green without these proves nothing):
     - the disclosure exists and starts closed
     - after open, a real re-render detached the node (not a no-op tick)
     - open is still true after ≥3 consecutive re-renders
     - restore did not re-pose (no mid-travel height, body fully opaque)

   production line the green depends on: restoreFolds(folds) after
   setLiveContent in tick(), fed by data-keep="status-rest" on expand().
   Break either (strip data-keep from status expand, or skip restoreFolds)
   and the open-survives checks go red.

   usage: node restcollapse.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';

const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'dashboard status "+ the rest (N)" peek open across live ticks',
  traceWindow: 'no motion trace — end-state + re-render identity across ' +
               'forced ticks (POST /command + tick()); hold ≥3 cycles',
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1600 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1000);

/* ── preconditions: subject present, starts closed, carries stable keep ── */
const pre = await p.evaluate(() => {
  const sec = document.getElementById('status');
  if (!sec) return { err: 'no #status' };
  // the status overflow is the only .peek inside #status
  const d = sec.querySelector('details.peek');
  if (!d) return { err: 'no #status details.peek' };
  const sum = (d.querySelector('summary') || {}).textContent || '';
  return {
    open: !!d.open,
    keep: d.getAttribute('data-keep'),
    summary: sum.trim(),
    isRest: /^the rest \(\d+\)$/.test(sum.trim()),
  };
});
notes.push(`pre: ${JSON.stringify(pre)}`);
ok('precondition: #status "+ the rest" disclosure exists',
   !!pre && !pre.err && pre.isRest);
ok('precondition: disclosure starts closed',
   !!pre && !pre.err && pre.open === false);
ok('precondition: disclosure carries stable data-keep (not the counted summary)',
   !!pre && pre.keep === 'status-rest');

if (!pre || pre.err || !pre.isRest) {
  await br.close();
  finish();
  process.exit(1);
}

/* ── open it (real pointer — synthetic click can pass through pointer-events) ──
   Wait past CARD_MS+150 (~1s) so the open travel has cleared its inline height.
   A tick mid-gesture correctly resumes travel via restoreFolds; the silent-
   restore contract is about a SETTLED open, not an interrupted one. */
await p.locator('#status details.peek > summary').click();
await p.waitForFunction(() => {
  const d = document.querySelector('#status details.peek');
  return !!(d && d.open && d.style.height === '');
}, null, { timeout: 2500 });
const opened = await p.evaluate(() => {
  const d = document.querySelector('#status details.peek');
  if (!d) return null;
  d.dataset.probeRest = '1';
  d.__restMark = 1;
  return {
    open: !!d.open,
    keep: d.getAttribute('data-keep'),
    settled: d.style.height === '',
  };
});
ok('precondition: disclosure is open after click (travel settled)',
   !!opened && opened.open === true && opened.settled === true);

/* force one real production tick: /command moves a watched mtime, tick()
   re-renders. The column/node must detach — an end-state-only "still open"
   would pass if the tick never ran. */
async function forceTickCycle() {
  return p.evaluate(async () => {
    const before = document.querySelector(
      '#status details.peek[data-probe-rest="1"]') ||
      document.querySelector('#status details.peek');
    if (before) before.__restMark = 1;
    await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'restcollapse tick' }),
    });
    await tick();
    if (before && before.isConnected) {
      await new Promise(r => setTimeout(r, 50));
      await tick();
    }
    const d = document.querySelector('#status details.peek');
    // Settled open restore: restoreFolds sets el.open=true only (no
    // travelCard/revealBody). A re-pose every poll would leave inline height
    // or a body still fading in — both are the bug wearing a fix.
    const body = d && [...d.children].find(c => c.tagName !== 'SUMMARY');
    const op = body ? parseFloat(getComputedStyle(body).opacity) : null;
    return {
      detached: !before || !before.isConnected,
      open: !!(d && d.open),
      keep: d && d.getAttribute('data-keep'),
      summary: d && ((d.querySelector('summary') || {}).textContent || '').trim(),
      markSurvived: !!(d && d.__restMark),
      heightInline: d ? d.style.height : '',
      bodyOp: op,
      travelling: !!(d && d.style.height !== ''),
    };
  });
}

const ticks = [];
for (let i = 0; i < 3; i++) {
  const st = await forceTickCycle();
  ticks.push(st);
  notes.push(`tick${i + 1}: ${JSON.stringify(st)}`);
  // re-mark the fresh node so the next cycle can prove detach again
  await p.evaluate(() => {
    const d = document.querySelector('#status details.peek');
    if (d) { d.dataset.probeRest = '1'; d.__restMark = 1; }
  });
}

ok('precondition: tick 1 really re-rendered (status peek node detached)',
   !!ticks[0] && ticks[0].detached === true);
ok('open survives tick 1', !!ticks[0] && ticks[0].open === true &&
   ticks[0].keep === 'status-rest');
ok('open survives tick 2', !!ticks[1] && ticks[1].open === true &&
   ticks[1].detached === true);
ok('open survives tick 3 (≥3 consecutive poll cycles)',
   !!ticks[2] && ticks[2].open === true && ticks[2].detached === true);

/* silent restore: no re-animation every poll. restoreFolds sets el.open=true
   without revealBody / travelCard when not mid-gesture. */
const silent = ticks.every(t => t && t.open && !t.travelling &&
  (t.bodyOp === null || t.bodyOp >= 0.99));
ok('restore is silent (no mid-travel height, body fully opaque after each tick)',
   silent && ticks.length === 3);

/* peer expand() peeks share the helper — verify they carry keep and hold too */
const peers = await p.evaluate(async () => {
  const files = [...document.querySelectorAll('details.peek')]
    .filter(d => (d.getAttribute('data-keep') || '').startsWith('file:'));
  if (!files.length) return { err: 'no file peeks' };
  const target = files[0];
  target.open = true;
  target.__peerMark = 1;
  const keep = target.getAttribute('data-keep');
  await fetch('/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'add-idea', text: 'restcollapse peer' }),
  });
  await tick();
  if (target.isConnected) { await new Promise(r => setTimeout(r, 50)); await tick(); }
  const after = document.querySelector(`details.peek[data-keep="${CSS.escape(keep)}"]`);
  const allKeeps = [...document.querySelectorAll('details.peek')]
    .map(d => d.getAttribute('data-keep'));
  return {
    keep,
    detached: !target.isConnected,
    open: !!(after && after.open),
    allKeeps,
  };
});
notes.push(`peers: ${JSON.stringify(peers)}`);
ok('peer file peek carries data-keep=file:*',
   !!peers && !peers.err && /^file:/.test(peers.keep || ''));
ok('peer file peek open survives a tick (expand() helper, not a one-off)',
   !!peers && peers.detached && peers.open === true);
ok('all expand peeks on the dashboard carry a data-keep',
   !!peers && Array.isArray(peers.allKeeps) &&
   peers.allKeeps.length > 0 && peers.allKeeps.every(k => !!k));

await p.screenshot({ path: `${OUT}/restcollapse-held.png`, fullPage: true });
await br.close();
finish();
