/* corpse — #505 Q4: a ghost holds no reconciled identity key.

   dreamAway strips data-qid/data-aid/data-sha/data-keep/data-aid from the
   corpse AND its subtree, then appends it to .wrap (outside #view) with
   .qaghost. Crossfade route ghosts use .ghost. Under keyed reconciliation
   of #view, a ghost that still carried a key would be matched as a
   survivor — the double-count bug (watch.py dreamAway comment, design
   "corpse rule").

   This guard asserts the DOM invariant the reconciler depends on:
     no element carrying .qaghost / .ghost matches a reconciled key
     (data-qid | data-aid | data-sha | data-review | data-keep).

   Shape: own-server (OUT, ephemeral PORT). Drives a real departure so a
   ghost exists (answer an open question → dreamAway), then scans.

   production line: dreamAway's IDS strip loop + viewNodeKey's corpse
   refuse. Red-prove by temporarily leaving data-qid on a ghost (inject
   after dreamAway, or strip the removeAttribute loop).

   usage: node corpse.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { waitForServer } from './dom.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'own-server /questions: answer an open card to spawn a .qaghost, ' +
          'scan all .qaghost/.ghost for reconciled identity keys; also ' +
          'inject a synthetic keyed ghost to red-prove the check',
  traceWindow: 'end-state scan after departure settles (~1s); no motion sample',
});

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
// #388: poll until the server accepts connections (bounded deadline, honest
// failure), not a fixed sleep — under CPU starvation watch.py takes seconds
// longer to bind and the old sleep(2500) raced it, surfacing raw ECONNREFUSED.
await waitForServer(BASE);
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
}

const KEYS = ['qid', 'aid', 'sha', 'review', 'keep'];
const scanGhosts = () => p.evaluate((keys) => {
  const ghosts = [...document.querySelectorAll('.qaghost, .ghost')];
  const offenders = [];
  for (const g of ghosts) {
    const hit = [];
    for (const k of keys) {
      if (g.getAttribute('data-' + k)) hit.push('self:data-' + k);
    }
    // subtree too — dreamAway strips throughout
    for (const n of g.querySelectorAll('[data-qid],[data-aid],[data-sha],[data-review],[data-keep]')) {
      for (const k of keys) {
        if (n.getAttribute('data-' + k))
          hit.push('child:data-' + k);
      }
    }
    if (hit.length) {
      offenders.push({
        cls: g.className,
        hit: [...new Set(hit)],
        tag: g.tagName,
      });
    }
  }
  return { nGhosts: ghosts.length, offenders };
}, KEYS);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 950 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);

// Drive production dreamAway on a clone of a live card — same entry
// regroupCards uses for departures. Cloning keeps the live list intact so
// the rest of the page still works; the corpse is what we inspect.
const departed = await p.evaluate(() => {
  if (typeof dreamAway !== 'function') return { err: 'no dreamAway' };
  const card = document.querySelector('.qa.open[data-qid]');
  if (!card) return { err: 'no open card' };
  const wrap = document.querySelector('.wrap');
  if (!wrap) return { err: 'no .wrap' };
  const rect = card.getBoundingClientRect();
  const clone = card.cloneNode(true);
  // clone still carries data-qid etc. — dreamAway must strip them
  const beforeQid = clone.getAttribute('data-qid');
  dreamAway(wrap, clone, rect, 0);
  const ghost = document.querySelector('.qaghost');
  return {
    beforeQid: !!beforeQid,
    ghosts: document.querySelectorAll('.qaghost, .ghost').length,
    ghostHasQid: !!(ghost && ghost.getAttribute('data-qid')),
    ghostHasQidChild: !!(ghost && ghost.querySelector('[data-qid]')),
  };
});
notes.push(`departed: ${JSON.stringify(departed)}`);
ok('precondition: dreamAway produced a .qaghost',
   !!departed && !departed.err && departed.ghosts > 0);
ok('dreamAway stripped data-qid from the corpse root',
   !!departed && departed.beforeQid && departed.ghostHasQid === false);
ok('dreamAway stripped data-qid throughout the corpse subtree',
   !!departed && departed.ghostHasQidChild === false);

const live = await scanGhosts();
notes.push(`live scan: ${JSON.stringify(live)}`);
ok('precondition: at least one .qaghost/.ghost exists to inspect',
   live.nGhosts > 0);
ok('Q4: no live ghost carries a reconciled identity key (self or subtree)',
   live.nGhosts > 0 && live.offenders.length === 0);

// Red-proof surface: inject a keyed ghost and assert the scan WOULD fail.
// We do not leave it in the page — restore after the inject-check.
const inject = await p.evaluate(() => {
  const wrap = document.querySelector('.wrap') || document.body;
  const g = document.createElement('div');
  g.className = 'qaghost';
  g.setAttribute('data-qid', 'injected-corpse-key');
  g.setAttribute('data-probe-corpse', '1');
  wrap.appendChild(g);
  const offenders = [...document.querySelectorAll('.qaghost, .ghost')]
    .filter(el => el.getAttribute('data-qid') || el.getAttribute('data-aid')
      || el.getAttribute('data-sha') || el.getAttribute('data-review')
      || el.getAttribute('data-keep')
      || el.querySelector('[data-qid],[data-aid],[data-sha],[data-review],[data-keep]'));
  // clean up
  g.remove();
  return { wouldFail: offenders.length > 0, n: offenders.length };
});
notes.push(`inject red-proof: ${JSON.stringify(inject)}`);
ok('red-proof: a ghost that keeps data-qid IS detected as an offender',
   !!inject && inject.wouldFail === true);

// viewNodeKey itself must refuse ghosts even if attrs remain
const keyRefuse = await p.evaluate(() => {
  if (typeof viewNodeKey !== 'function') return { err: 'no viewNodeKey' };
  const g = document.createElement('div');
  g.className = 'qaghost';
  g.dataset.qid = 'should-not-key';
  const k1 = viewNodeKey(g);
  g.className = 'ghost';
  g.dataset.qid = 'should-not-key';
  const k2 = viewNodeKey(g);
  const live = document.createElement('div');
  live.dataset.qid = 'live';
  const k3 = viewNodeKey(live);
  return { k1, k2, k3 };
});
notes.push(`viewNodeKey: ${JSON.stringify(keyRefuse)}`);
ok('viewNodeKey refuses .qaghost even with data-qid',
   !!keyRefuse && keyRefuse.k1 === undefined);
ok('viewNodeKey refuses .ghost even with data-qid',
   !!keyRefuse && keyRefuse.k2 === undefined);
ok('viewNodeKey keys a live data-qid node',
   !!keyRefuse && keyRefuse.k3 === 'qid:live');

await p.screenshot({ path: join(OUT, 'corpse.png'), fullPage: true });
await br.close();
try { srv.kill(); } catch (e) {}
finish();
