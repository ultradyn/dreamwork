/* runmode — #290 dashboard-settable main-dreamer run mode.

   Contract under test:
   - selectable chips: lackadaisical / hot / assisted; hierarchical disabled
   - 10s shared arm with draining progress + text countdown; reselection resets
   - only final POST writes file + one events line; identical final silent
   - reduced motion: no continuous bar width animation; same text + apply time
   - hard refresh / re-render follows authoritative file when no pending
   - cross-tab: page B arms pending; page A adopts via storage listener without
     writing localStorage back; one shared final POST/event (not two)

   usage: node runmode.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const OUT = process.argv[2], PORT = process.argv[3] || '39890';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
  process.exitCode = checks.some(l => l.startsWith('FAIL')) ? 1 : 0;
});

const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});
const ctx = await br.newContext();
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(800);

const has = await p.evaluate(() => !!document.getElementById('runmode'));
ok('run mode section exists on the dashboard', has);
if (!has) { finished = true; await br.close(); process.exit(1); }

const chips = await p.evaluate(() => {
  const bs = [...document.querySelectorAll('.runmodes .runchip')];
  return bs.map(b => ({
    mode: b.dataset.mode,
    disabled: !!b.disabled,
    on: b.classList.contains('on'),
    checked: b.getAttribute('aria-checked'),
  }));
});
notes.push('chips: ' + JSON.stringify(chips));
const modes = chips.map(c => c.mode);
ok('v1 chips include lackadaisical, hot, assisted',
   ['lackadaisical', 'hot', 'assisted'].every(m => modes.includes(m)));
ok('hierarchical is present and disabled',
   chips.some(c => c.mode === 'hierarchical' && c.disabled));
ok('default selection is lackadaisical (or committed)',
   chips.some(c => c.on && !c.disabled));

// ── arm + intermediate progress (normal motion) ─────────────────────────
// Context-level: every page's /run-mode must be counted for cross-tab once.
const posts = [];
ctx.on('request', req => {
  if (req.method() === 'POST' && req.url().includes('/run-mode'))
    posts.push({ t: Date.now(), url: req.url() });
});

await p.click('.runchip[data-mode="hot"]');
await sleep(200);
const arming = await p.evaluate(() => {
  const fill = document.getElementById('runbarfill');
  const count = document.getElementById('runcount');
  const bar = document.getElementById('runbar');
  const widths = [];
  // sample for ~2.5s of the 10s drain
  return new Promise(resolve => {
    const t0 = performance.now();
    const tick = () => {
      if (fill) widths.push(+getComputedStyle(fill).width.replace('px', '') || 0);
      if (performance.now() - t0 < 2500) requestAnimationFrame(tick);
      else resolve({
        n: widths.length,
        distinct: new Set(widths.map(w => w.toFixed(1))).size,
        first: widths[0],
        last: widths[widths.length - 1],
        count: count ? count.textContent : '',
        barHidden: bar ? bar.hidden : true,
        postsEarly: 0,
      });
    };
    requestAnimationFrame(tick);
  });
});
notes.push('arm progress: ' + JSON.stringify(arming));
ok('progress bar is visible while arming (normal motion)', !arming.barHidden);
ok('bar width visits many intermediate values during drain (>5 distinct)',
   arming.distinct > 5);
ok('bar width decreases over the sample (ticks down)',
   arming.last < arming.first - 1);
ok('countdown text names the pending mode',
   /hot/.test(arming.count) && /arms in \d+s/.test(arming.count));
ok('no POST during the first ~2.5s of the arm', posts.length === 0);

// reselection resets the countdown
await p.click('.runchip[data-mode="assisted"]');
await sleep(300);
const afterReset = await p.evaluate(() => {
  const count = document.getElementById('runcount');
  const fill = document.getElementById('runbarfill');
  const w = fill ? parseFloat(getComputedStyle(fill).width) : 0;
  return { count: count ? count.textContent : '', w };
});
notes.push('after reset: ' + JSON.stringify(afterReset));
ok('reselection resets text to assisted with a high remaining second',
   /assisted/.test(afterReset.count) && /arms in (9|10)s/.test(afterReset.count));

// wait for commit (~10s from last click)
const tWait = Date.now();
while (posts.length === 0 && Date.now() - tWait < 14000) await sleep(200);
ok('exactly one POST after the arm completes', posts.length === 1);

await sleep(400);
const committed = await p.evaluate(async () => {
  const d = await (await fetch('/data.json')).json();
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return {
    run_mode: d.run_mode,
    on: on && on.dataset.mode,
    count: count ? count.textContent : '',
  };
});
notes.push('committed: ' + JSON.stringify(committed));
ok('data.json run_mode is assisted after arm', committed.run_mode === 'assisted');
ok('UI selection matches committed mode', committed.on === 'assisted');
ok('arm UI clears after apply', !committed.count || !/arms in/.test(committed.count));

// target path from data.json for filesystem checks
const target = await p.evaluate(async () =>
  (await (await fetch('/data.json')).json()).target);
const modeFile = join(target, '.dreamwork', 'run-mode');
const eventsFile = join(target, '.dreamwork', 'watch-events.log');
ok('run-mode file exists on disk', existsSync(modeFile));
if (existsSync(modeFile)) {
  const body = readFileSync(modeFile, 'utf8').trim();
  ok('run-mode file holds assisted', body === 'assisted');
}
let eventLines = [];
if (existsSync(eventsFile)) {
  eventLines = readFileSync(eventsFile, 'utf8').split('\n')
    .filter(l => l.includes('run-mode'));
}
notes.push('events: ' + JSON.stringify(eventLines));
ok('exactly one run-mode events line after first change',
   eventLines.length === 1);
ok('events line names assisted',
   eventLines.some(l => /run-mode via watch.*assisted/.test(l)));

// identical re-arm of same mode cancels; re-post same is idempotent
const postsBefore = posts.length;
await p.click('.runchip[data-mode="assisted"]');
await sleep(400);
ok('re-selecting committed mode cancels arm (no countdown)',
   await p.evaluate(() => {
     const c = document.getElementById('runcount');
     return !c || !/arms in/.test(c.textContent || '');
   }));

// force immediate same-mode POST via fetch to prove server idempotency
const idem = await p.evaluate(async () => {
  const r = await fetch('/run-mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'assisted' }),
  });
  const j = await r.json().catch(() => ({}));
  return { status: r.status, changed: j.changed };
});
notes.push('idempotent: ' + JSON.stringify(idem));
ok('identical final returns 200', idem.status === 200);
ok('identical final reports changed:false', idem.changed === false);
if (existsSync(eventsFile)) {
  eventLines = readFileSync(eventsFile, 'utf8').split('\n')
    .filter(l => l.includes('run-mode'));
}
ok('identical final emits no second events line', eventLines.length === 1);

// hierarchical click does nothing
await p.click('.runchip[data-mode="hierarchical"]', { force: true }).catch(() => {});
await sleep(200);
ok('hierarchical remains unselected',
   await p.evaluate(() => {
     const b = document.querySelector('.runchip[data-mode="hierarchical"]');
     return b && b.disabled && !b.classList.contains('on');
   }));

// ── reduced motion: text countdown, no bar width animation ──────────────
const p2 = await ctx.newPage();
await p2.emulateMedia({ reducedMotion: 'reduce' });
await p2.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(600);
await p2.click('.runchip[data-mode="hot"]');
await sleep(150);
const rm = await p2.evaluate(() => {
  const bar = document.getElementById('runbar');
  const fill = document.getElementById('runbarfill');
  const count = document.getElementById('runcount');
  const widths = [];
  const t0 = performance.now();
  // sample ~1.2s
  while (performance.now() - t0 < 1200) {
    if (fill) widths.push(+getComputedStyle(fill).width.replace('px', '') || 0);
  }
  const distinct = new Set(widths.map(w => w.toFixed(1))).size;
  const cs = bar ? getComputedStyle(bar) : null;
  return {
    barDisplay: cs ? cs.display : 'none',
    barHidden: bar ? bar.hidden : true,
    distinct,
    count: count ? count.textContent : '',
  };
});
notes.push('reduced motion: ' + JSON.stringify(rm));
ok('RM hides continuous bar (display:none or hidden)',
   rm.barDisplay === 'none' || rm.barHidden);
ok('RM bar width does not continuously animate (≤2 distinct samples)',
   rm.distinct <= 2);
ok('RM still shows second-by-second text countdown',
   /arms in \d+s/.test(rm.count) && /hot/.test(rm.count));
// cancel so we do not wait another 10s
await p2.click('.runchip[data-mode="assisted"]'); // will re-arm; reselect committed
await p2.evaluate(() => {
  // pick committed to cancel if already assisted from page1
  if (typeof pickRunMode === 'function') pickRunMode('assisted');
});
await sleep(200);

// hard refresh settles on file without replaying stuck pose
await p.reload({ waitUntil: 'networkidle' });
await sleep(700);
const afterReload = await p.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return {
    on: on && on.dataset.mode,
    count: count ? count.textContent : '',
  };
});
notes.push('after reload: ' + JSON.stringify(afterReload));
ok('hard refresh shows committed mode without a stuck arm',
   afterReload.on === 'assisted' &&
   (!afterReload.count || !/arms in/.test(afterReload.count)));

// ── cross-tab: shared pending via storage event ─────────────────────────
// Premise: two pages, same origin/context, same data.target. Page B writes
// localStorage pending; page A must adopt through the `storage` listener
// without calling setItem itself. Sabotage first so the check is shown RED
// when the adoption path cannot run.
await p.evaluate(() => {
  if (typeof pickRunMode === 'function') pickRunMode('assisted'); // cancel arm
  try {
    Object.keys(localStorage)
      .filter(k => k.indexOf('dw:run-mode-pending:') === 0)
      .forEach(k => localStorage.removeItem(k));
  } catch (e) {}
});
await sleep(200);

const pA = p; // follower
const pB = await ctx.newPage();
pB.on('pageerror', e => errs.push('B:' + String(e)));
await pB.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(700);

const targets = await Promise.all([
  pA.evaluate(async () => (await (await fetch('/data.json')).json()).target),
  pB.evaluate(async () => (await (await fetch('/data.json')).json()).target),
]);
notes.push('cross-tab targets: ' + JSON.stringify(targets));
ok('both pages share the same data.target (cross-tab premise)',
   targets[0] && targets[0] === targets[1]);

// Instrument setItem on A — adoption must not write pending back
await pA.evaluate(() => {
  window.__setItemLog = [];
  const orig = localStorage.setItem.bind(localStorage);
  localStorage.setItem = function (k, v) {
    window.__setItemLog.push({ k, v: String(v).slice(0, 80) });
    return orig(k, v);
  };
});

// RED: poison A's lexical `data.target` so runPendingKey() ≠ B's storage
// key — the storage listener's key match fails closed and A must NOT show
// B's arm. (Must mutate `data`, not window.data: the bundle uses a top-level
// let, which is not a window property.)
const aBeforeSab = await pA.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  return on && on.dataset.mode;
});
await pA.evaluate(() => { data.target = data.target + '-sabotage'; });
await pB.click('.runchip[data-mode="hot"]');
await sleep(600);
const sabotaged = await pA.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return {
    on: on && on.dataset.mode,
    count: count ? count.textContent : '',
  };
});
notes.push('sabotaged A: ' + JSON.stringify({ sabotaged, aBeforeSab }));
ok('RED premise: with mismatched target, A does NOT adopt B hot arm',
   sabotaged.on !== 'hot' && !/arms in.*hot/.test(sabotaged.count || ''));

// cancel B arm + clear pending before the real path
await pB.evaluate(() => {
  if (typeof pickRunMode === 'function') pickRunMode('assisted');
  try {
    Object.keys(localStorage)
      .filter(k => k.indexOf('dw:run-mode-pending:') === 0)
      .forEach(k => localStorage.removeItem(k));
  } catch (e) {}
});
// restore A's target and wipe any poison-side effects
await pA.evaluate((tgt) => {
  data.target = tgt;
  window.__setItemLog = [];
  try {
    Object.keys(localStorage)
      .filter(k => k.indexOf('dw:run-mode-pending:') === 0)
      .forEach(k => localStorage.removeItem(k));
  } catch (e) {}
  if (typeof pickRunMode === 'function') pickRunMode('assisted');
}, targets[0]);
await sleep(300);

// GREEN: B arms hot; A must adopt intermediate countdown via storage only
await pA.evaluate(() => { window.__setItemLog = []; }); // drop setup cancel noise
const eventsBefore = existsSync(eventsFile)
  ? readFileSync(eventsFile, 'utf8').split('\n').filter(l => l.includes('run-mode')).length
  : 0;
const postsAtArm = posts.length;
await pB.click('.runchip[data-mode="hot"]');
// sample A for intermediate adoption (not only end state)
let intermediate = null;
const t0 = Date.now();
while (Date.now() - t0 < 2500) {
  intermediate = await pA.evaluate(() => {
    const on = document.querySelector('.runchip.on:not([disabled])');
    const count = document.getElementById('runcount');
    const bar = document.getElementById('runbar');
    const fill = document.getElementById('runbarfill');
    const w = fill ? parseFloat(getComputedStyle(fill).width) || 0 : 0;
    return {
      on: on && on.dataset.mode,
      count: count ? count.textContent : '',
      barHidden: bar ? bar.hidden : true,
      fillW: w,
    };
  });
  if (intermediate.on === 'hot' && /arms in \d+s/.test(intermediate.count || ''))
    break;
  await sleep(100);
}
notes.push('A intermediate adopt: ' + JSON.stringify(intermediate));
ok('cross-tab: A selects hot while B is arming (storage adopt)',
   intermediate && intermediate.on === 'hot');
ok('cross-tab: A shows intermediate arms-in countdown for hot',
   intermediate && /arms in \d+s/.test(intermediate.count || '') &&
   /hot/.test(intermediate.count || ''));
ok('cross-tab: A does not POST during B-led arm (no early write)',
   posts.length === postsAtArm);

const setItems = await pA.evaluate(() => window.__setItemLog || []);
notes.push('A setItem log during adopt: ' + JSON.stringify(setItems));
ok('cross-tab: A never setItem run-mode-pending (no write-back)',
   !setItems.some(x => String(x.k).indexOf('dw:run-mode-pending:') === 0));

// wait for shared final commit
const tWait2 = Date.now();
while (posts.length === postsAtArm && Date.now() - tWait2 < 14000) await sleep(200);
const postsThisArm = posts.length - postsAtArm;
notes.push('cross-tab posts this arm: ' + postsThisArm);
ok('cross-tab: exactly one POST for the shared arm', postsThisArm === 1);

// follower settles via /mtime poll after initiator POST — wait for it
let settledA = null;
const tSettle = Date.now();
while (Date.now() - tSettle < 5000) {
  settledA = await pA.evaluate(async () => {
    const d = await (await fetch('/data.json')).json();
    const on = document.querySelector('.runchip.on:not([disabled])');
    const count = document.getElementById('runcount');
    return {
      run_mode: d.run_mode,
      on: on && on.dataset.mode,
      count: count ? count.textContent : '',
    };
  });
  if (settledA.run_mode === 'hot' && settledA.on === 'hot' &&
      (!settledA.count || !/arms in/.test(settledA.count)))
    break;
  await sleep(250);
}
const settledB = await pB.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return {
    on: on && on.dataset.mode,
    count: count ? count.textContent : '',
  };
});
notes.push('settled A/B: ' + JSON.stringify({ settledA, settledB }));
ok('cross-tab: settled run_mode is hot', settledA && settledA.run_mode === 'hot');
ok('cross-tab: A settles on hot without stuck arm text',
   settledA && settledA.on === 'hot' &&
   (!settledA.count || !/arms in/.test(settledA.count)));
ok('cross-tab: B settles on hot',
   settledB.on === 'hot' &&
   (!settledB.count || !/arms in/.test(settledB.count)));

let eventLines2 = [];
if (existsSync(eventsFile)) {
  eventLines2 = readFileSync(eventsFile, 'utf8').split('\n')
    .filter(l => l.includes('run-mode'));
}
const newEvents = eventLines2.length - eventsBefore;
notes.push('cross-tab events delta: ' + newEvents + ' total=' + eventLines2.length);
ok('cross-tab: exactly one new run-mode events line for the shared commit',
   newEvents === 1);
ok('cross-tab: newest events line names hot',
   eventLines2.length && /run-mode via watch.*hot/.test(eventLines2[eventLines2.length - 1]));

// ── cross-tab CANCEL: B arms then reselects committed; A must snap back ─
// (cancel produces no mtime change — tombstone is the only signal)
await pA.evaluate(() => { window.__setItemLog = []; });
await pB.evaluate(() => {
  if (typeof pickRunMode === 'function') pickRunMode('hot');
});
await sleep(400);
const aArmed = await pA.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return { on: on && on.dataset.mode, count: count ? count.textContent : '' };
});
ok('cancel setup: A adopted B hot arm',
   aArmed.on === 'hot' && /arms in/.test(aArmed.count || ''));
// B cancels by re-selecting committed hot... wait, committed is hot now.
// Arm assisted then cancel back to hot.
await pB.evaluate(() => {
  if (typeof pickRunMode === 'function') pickRunMode('assisted');
});
await sleep(400);
const aOnAssisted = await pA.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  return on && on.dataset.mode;
});
ok('cancel setup: A shows assisted pending', aOnAssisted === 'assisted');
await pB.evaluate(() => {
  // re-select committed (hot) → cancel tombstone
  if (typeof pickRunMode === 'function') pickRunMode('hot');
});
await sleep(500);
const aAfterCancel = await pA.evaluate(() => {
  const on = document.querySelector('.runchip.on:not([disabled])');
  const count = document.getElementById('runcount');
  return {
    on: on && on.dataset.mode,
    count: count ? count.textContent : '',
  };
});
notes.push('A after cancel: ' + JSON.stringify(aAfterCancel));
ok('cross-tab cancel: A converges to committed hot without arm text',
   aAfterCancel.on === 'hot' &&
   (!aAfterCancel.count || !/arms in/.test(aAfterCancel.count)));
ok('cross-tab cancel: A still does not write pending',
   !(await pA.evaluate(() =>
     (window.__setItemLog || []).some(x =>
       String(x.k).indexOf('dw:run-mode-pending:') === 0 &&
       !String(x.v).includes('cancel')))));
// cancel must not emit another run-mode event
const eventsAfterCancel = existsSync(eventsFile)
  ? readFileSync(eventsFile, 'utf8').split('\n').filter(l => l.includes('run-mode')).length
  : 0;
ok('cross-tab cancel: no extra events line',
   eventsAfterCancel === eventLines2.length);

// ── leave-dashboard mid-arm: initiator still POSTs (Standards fix) ─────
// Arm assisted on dashboard, navigate to /questions before deadline; the
// commit timer must survive missing .runmodes DOM.
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(600);
// ensure known committed baseline for a real change
await p.evaluate(async () => {
  await fetch('/run-mode', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'hot' }),
  });
  if (data) data.run_mode = 'hot';
  try {
    Object.keys(localStorage)
      .filter(k => k.indexOf('dw:run-mode-pending:') === 0)
      .forEach(k => localStorage.removeItem(k));
  } catch (e) {}
});
await sleep(300);
const postsLeave = posts.length;
const eventsLeave = existsSync(eventsFile)
  ? readFileSync(eventsFile, 'utf8').split('\n').filter(l => l.includes('run-mode')).length
  : 0;
await p.evaluate(() => {
  if (typeof pickRunMode === 'function') pickRunMode('assisted');
});
await sleep(300);
const midArm = await p.evaluate(() => {
  const count = document.getElementById('runcount');
  return count ? count.textContent : '';
});
ok('leave-dashboard setup: arm text present on dashboard',
   /arms in \d+s.*assisted/.test(midArm));
// leave the dashboard while arm is live
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(400);
const onQuestions = await p.evaluate(() => ({
  path: location.pathname,
  hasPicker: !!document.querySelector('.sgroup.runmodes'),
}));
notes.push('on questions mid-arm: ' + JSON.stringify(onQuestions));
ok('leave-dashboard: picker absent on /questions', !onQuestions.hasPicker);
// wait past arm for the POST (up to 12s)
const tLeave = Date.now();
while (posts.length === postsLeave && Date.now() - tLeave < 13000) await sleep(200);
const postsAfterLeave = posts.length - postsLeave;
notes.push('leave-dashboard posts: ' + postsAfterLeave);
ok('leave-dashboard: exactly one POST after navigating mid-arm',
   postsAfterLeave === 1);
await sleep(400);
const afterLeave = await p.evaluate(async () =>
  (await (await fetch('/data.json')).json()).run_mode);
ok('leave-dashboard: file/data settled to assisted', afterLeave === 'assisted');
const eventsLeaveAfter = existsSync(eventsFile)
  ? readFileSync(eventsFile, 'utf8').split('\n').filter(l => l.includes('run-mode')).length
  : 0;
ok('leave-dashboard: exactly one new events line for assisted',
   eventsLeaveAfter === eventsLeave + 1);
if (existsSync(eventsFile)) {
  const last = readFileSync(eventsFile, 'utf8').split('\n')
    .filter(l => l.includes('run-mode')).pop() || '';
  ok('leave-dashboard: last events line names assisted',
     /assisted/.test(last));
}

finished = true;
await br.close();
