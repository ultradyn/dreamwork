/* #836 — durable task-group progress, real geometry and state-update motion.

   This guard builds a v004 store fixture, renders the production dashboard,
   and measures segment rectangles against their track. It then lands a task
   through TaskRepository and requires the SAME filled node to travel through
   a part-way width. Reduced motion must reach the same final geometry without
   registering a transition.

   usage: node dev/capture/groupprogress.mjs <outdir> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { execFileSync, spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join, resolve } from 'node:path';

import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv);
const TARGET = join(OUT, 'target');
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
rmSync(TARGET, { recursive: true, force: true });
cpSync('dev/capture/fixture', TARGET, { recursive: true });

const checks = [];
const notes = [];
const errors = [];
const ok = (name, pass) => checks.push(`${pass ? 'PASS' : 'FAIL'} ${name}`);
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errors.length) console.log(errors.join('\n'));
});

const seed = String.raw`
import sqlite3, sys
from pathlib import Path
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec

root = Path(sys.argv[1])
dw = root / '.dreamwork'
dw.mkdir(exist_ok=True)
(dw / 'tasks.md').write_text(
    '---\ndreamwork-ledger: migrated\nsource-of-truth: store\n---\n')
path = dw / 'ledger.sqlite3'
with open_database(task_store_spec(path), access=Access.WRITE) as store:
    with store.transaction():
        pass
conn = sqlite3.connect(path)
conn.executemany(
    'INSERT INTO task '
    '(id,state,title,body,priority,type,origin,blocked_on) '
    'VALUES (?,?,?,?,?,?,?,NULL)',
    [(101, 'landed', 'one', 'one', 'P2', 'task', 'loop'),
     (102, 'open', 'two', 'two', 'P2', 'task', 'loop'),
     (103, 'open', 'three', 'three', 'P2', 'task', 'loop')])
conn.commit(); conn.close()
with open_database(task_store_spec(path), access=Access.WRITE) as store:
    with store.transaction() as tx:
        gid = tx.groups.create(kind='epic', title='Rendered epic',
            actor='guard', at='2026-08-01T00:00:00Z')
        for tid in (101, 102, 103):
            tx.groups.add_task(gid, tid, actor='guard',
                at='2026-08-01T00:00:01Z')
        tx.groups.create(kind='lane', title='No tasks yet',
            actor='guard', at='2026-08-01T00:00:02Z')
`;
execFileSync('python3', ['-c', seed, TARGET], { stdio: 'inherit' });

const land = taskId => {
  const code = String.raw`
import sys
from pathlib import Path
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec
path = Path(sys.argv[1]) / '.dreamwork' / 'ledger.sqlite3'
with open_database(task_store_spec(path), access=Access.WRITE) as store:
    with store.transaction() as tx:
        tx.tasks.land(int(sys.argv[2]), note='guard landing', actor='guard')
`;
  execFileSync('python3', ['-c', code, TARGET, String(taskId)],
               { stdio: 'inherit' });
};

const freePort = () => new Promise(resolvePort => {
  const attempt = () => {
    const server = createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => {
        if (port === 35110 || port === 35113) attempt();
        else resolvePort(port);
      });
    });
  };
  attempt();
});

const port = await freePort();
const server = spawn('python3', ['watch.py', '--target', TARGET,
  '--port', String(port)], { stdio: ['ignore', 'pipe', 'pipe'] });
let serverLog = '';
server.stdout.on('data', b => { serverLog += b; });
server.stderr.on('data', b => { serverLog += b; });
process.on('exit', () => { try { server.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${port}`;
for (let i = 0; i < 40; i++) {
  try {
    const d = await (await fetch(`${BASE}/data.json`)).json();
    if (d.target === TARGET) break;
  } catch (e) { /* server not ready */ }
  if (i === 39) throw new Error(`server never came up: ${serverLog}`);
  await sleep(250);
}

const browser = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
page.on('pageerror', e => errors.push(String(e)));
await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => {
  const row = document.querySelector('.groupprogress[data-group-id="1"] .provsrc');
  return row && row.textContent.includes('1 of 3');
});

const datum = (await (await fetch(`${BASE}/data.json`)).json()).groups;
notes.push(`groups datum: ${JSON.stringify(datum)}`);
ok("epic #1 'Rendered epic' has exact members [101,102,103] and landed [101]",
   datum.length === 2 &&
   JSON.stringify(datum[0].member_task_ids) === '[101,102,103]' &&
   JSON.stringify(datum[0].landed_task_ids) === '[101]');
ok("empty lane #2 'No tasks yet' did not produce a ratio",
   !('total_count' in datum[1]) && /0 member tasks/.test(datum[1].progress_error));

const measure = () => page.evaluate(() => {
  const group = document.querySelector('.groupprogress[data-group-id="1"]');
  const empty = document.querySelector('.groupprogress[data-group-id="2"]');
  const track = group.querySelector('.provbar');
  const filled = group.querySelector('.provseg.phuman');
  const rest = group.querySelector('.provseg.punknown');
  const tw = track.getBoundingClientRect().width;
  return {
    track: tw,
    filled: filled.getBoundingClientRect().width,
    rest: rest.getBoundingClientRect().width,
    restClass: rest.className,
    restPaint: getComputedStyle(rest).backgroundImage,
    transition: getComputedStyle(filled).transitionProperty,
    emptyText: empty.textContent.trim(),
    emptyHasBar: !!empty.querySelector('.provbar'),
  };
});

const initial = await measure();
notes.push(`initial geometry: ${JSON.stringify(initial)}`);
ok("epic #1 'Rendered epic' filled width is one third of its real track",
   initial.track > 100 && Math.abs(initial.filled / initial.track - 1 / 3) < .02);
ok("epic #1 'Rendered epic' unfilled width is two thirds of its real track",
   Math.abs(initial.rest / initial.track - 2 / 3) < .02);
ok('the unfilled segment uses the base bar unknown class and hatch',
   initial.restClass.includes('punknown') && initial.restPaint.includes('gradient'));
ok("empty lane #2 'No tasks yet' renders progress unavailable and no bar",
   initial.emptyText.includes('progress unavailable') && !initial.emptyHasBar);

await page.evaluate(() => {
  const el = document.querySelector(
    '.groupprogress[data-group-id="1"] .provseg.phuman');
  // An expando, not data-* markup: morphdom is supposed to remove an
  // attribute absent from the next render even when it keeps the node.
  el.__gpKept = true;
  window.__gpFrames = [];
  window.__gpTransitionStarts = 0;
  el.addEventListener('transitionstart', e => {
    if (e.propertyName === 'flex-grow') window.__gpTransitionStarts++;
  });
  const started = performance.now();
  (function sample(now) {
    const live = document.querySelector(
      '.groupprogress[data-group-id="1"] .provseg.phuman');
    const track = live && live.parentElement;
    if (live && track) window.__gpFrames.push({
      at: now, width: live.getBoundingClientRect().width,
      track: track.getBoundingClientRect().width,
    });
    if (now - started < 5000) requestAnimationFrame(sample);
  })(started);
});
land(102);
await page.waitForFunction(() => {
  const row = document.querySelector('.groupprogress[data-group-id="1"] .provsrc');
  return row && row.textContent.includes('2 of 3');
}, null, { timeout: 10000 });
await page.waitForTimeout(650);
const moved = await page.evaluate(() => ({
  kept: document.querySelector(
    '.groupprogress[data-group-id="1"] .provseg.phuman').__gpKept,
  starts: window.__gpTransitionStarts,
  frames: window.__gpFrames,
}));
const final = await measure();
const lo = initial.filled + (final.filled - initial.filled) * .03;
const hi = final.filled - (final.filled - initial.filled) * .03;
const partway = moved.frames.filter(f => f.width > lo && f.width < hi).length;
notes.push(`animated: starts=${moved.starts} partway=${partway} ` +
  `final=${JSON.stringify(final)}`);
ok("epic #1 'Rendered epic' updated the same filled node on durable landing",
   moved.kept === true);
ok("epic #1 'Rendered epic' filled width animates from 1/3 to 2/3 on state update",
   moved.starts >= 1 && partway >= 1 &&
   Math.abs(final.filled / final.track - 2 / 3) < .02);

await page.emulateMedia({ reducedMotion: 'reduce' });
await page.evaluate(() => {
  window.__gpReducedStarts = 0;
  document.querySelector(
    '.groupprogress[data-group-id="1"] .provseg.phuman')
    .addEventListener('transitionstart', () => window.__gpReducedStarts++);
});
land(103);
await page.waitForFunction(() => {
  const row = document.querySelector('.groupprogress[data-group-id="1"] .provsrc');
  return row && row.textContent.includes('3 of 3');
}, null, { timeout: 10000 });
await page.waitForTimeout(100);
const reduced = await page.evaluate(() => ({
  starts: window.__gpReducedStarts,
  transition: getComputedStyle(document.querySelector(
    '.groupprogress[data-group-id="1"] .provseg.phuman')).transitionDuration,
}));
const complete = await measure();
ok("reduced motion: epic #1 'Rendered epic' snaps to complete geometry",
   reduced.starts === 0 && reduced.transition === '0s' &&
   Math.abs(complete.filled / complete.track - 1) < .02);

writeFileSync(join(OUT, 'groupprogress.png'), await page.screenshot());
ok('no page errors', errors.length === 0);
await page.close();
await browser.close();
server.kill();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
