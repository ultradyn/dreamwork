/* The structural guard for dreamhub's page (#96, increment 5).

   `test_dreamhub.py` asserts on generated SOURCE. That is worth having and it
   is worth being honest about what it cannot do: a component can be correct
   in source and wrong on screen, and a pytest that reads a string passes on a
   blank page for as many commits as you like. #117 was exactly that, twice.
   So this runs a real browser against a real server and asks what RENDERED.

   Contract, same as dev/capture/: `node hub.mjs <OUT> <PORT>`. One
   difference, stated because a silent second contract is what #117 cost —
   this guard STARTS ITS OWN SERVER. The hub's input is N targets plus a
   registry rather than one target directory, and gluing that into a shared
   recipe is exactly the second contract worth avoiding. So the justfile line
   that wires this in (#134) is one line and needs no server plumbing.

   Everything runs against a copy of dev/hub/fixture, prepared by prep.py, and
   nothing here touches the repo.

   usage: node dev/hub/hub.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = process.argv[2] || '/tmp/hubguard';
const PORT = process.argv[3] || '39897';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const notes = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);

/* A stub watch on its own port, so the page has one row that is UP.
   Without it "the down row does not link to a dead port" is satisfied by a
   page that never renders a link at all — a check that can only pass. */
const stub = createServer((req, res) => {
  const body = req.url === '/mtime' ? '1 100.0'
    : req.url === '/data.json' ? JSON.stringify({ open_questions: 3 })
      : null;
  if (body === null) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
});
await new Promise(r => stub.listen(0, '127.0.0.1', r));
const STUB_PORT = stub.address().port;

const targets = join(OUT, 'targets');
const home = join(OUT, 'hubhome');
const prep = spawnSync('python3', [join(HERE, 'prep.py'), targets,
  '--home', home], { encoding: 'utf-8' });
if (prep.status !== 0) {
  console.log('FAIL prep.py did not run\n' + prep.stderr);
  process.exit(1);
}
// point ONE target at the live stub; the rest keep their dead ports
writeFileSync(join(targets, 'quiet', '.dreamwork', 'watch-port'),
  `${STUB_PORT}\n`);

const srv = spawn('python3', [join(ROOT, 'dreamhub.py'), 'serve',
  '--port', PORT], { env: { ...process.env, DREAMHUB_HOME: home } });
let srvlog = ''; let srvExit = null;
srv.stdout.on('data', d => { srvlog += d; });
srv.stderr.on('data', d => { srvlog += d; });
srv.on('exit', code => { srvExit = code; });
const die = (msg) => {
  console.log(msg + '\n' + srvlog);
  srv.kill(); stub.close();
  process.exit(1);
};
process.on('exit', () => { try { srv.kill(); stub.close(); } catch { } });

/* Wait for OUR server, and prove it is ours.

   The first version waited for anything that answered on PORT. On a machine
   where another dreamer is running watch instances a few ports away, that is
   a real event: dreamhub failed to bind, the loop found a STRANGER'S page
   answering, and the guard went on to assert against it — reporting zero rows
   over a page that was never the hub. A readiness probe that cannot tell
   "mine" from "something" is worse than no probe, because it converts a
   loud bind failure into a confusing assertion failure. */
let up = false;
for (let i = 0; i < 60; i++) {
  if (srvExit !== null) {
    die(`FAIL dreamhub exited ${srvExit} before serving — port ${PORT} in use?`);
  }
  try {
    const r = await fetch(`${BASE}/hub.json`);
    const j = await r.json();
    if (Array.isArray(j.projects) && j.projects.some(x => x.slug === 'torn')) {
      up = true; break;
    }
    die(`FAIL something else is serving ${PORT} — it answered /hub.json ` +
        `without this guard's fixture in it`);
  } catch (e) {
    // not JSON, or nothing listening yet: if it is a page, it is not ours
    try {
      const t = await (await fetch(`${BASE}/`)).text();
      if (!/<title>dreamhub<\/title>/.test(t)) {
        die(`FAIL something else is already serving ${PORT} — pick another`);
      }
    } catch { /* nothing listening yet, keep waiting */ }
    await sleep(250);
  }
}
if (!up) die(`FAIL dreamhub never came up on ${PORT}`);

const br = await chromium.launch();
const p = await br.newPage({ viewport: { width: 1200, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(400);

/* ---- what actually rendered ---------------------------------------- */
const seen = await p.evaluate(() => {
  const rows = [...document.querySelectorAll('.row')];
  return {
    count: rows.length,
    bodyText: (document.body.innerText || '').length,
    labels: [...document.querySelectorAll('.cols .label')]
      .map(e => e.textContent.trim()),
    rows: rows.map(r => ({
      slug: r.dataset.slug,
      state: (r.querySelector('.state') || {}).textContent || '',
      age: (r.querySelector('.age') || {}).textContent || '',
      href: (r.querySelector('a.slug') || {}).getAttribute
        ? r.querySelector('a.slug').getAttribute('href') : null,
      text: r.innerText,
      // presence is not visibility: a component can be correct in source,
      // present in the DOM, and still not on screen
      h: r.getBoundingClientRect().height,
      right: r.getBoundingClientRect().right,
    })),
    docWidth: document.documentElement.scrollWidth,
    winWidth: window.innerWidth,
  };
});
notes.push(seen.rows.map(r =>
  `${r.slug.padEnd(9)} ${r.state.padEnd(10)} ${r.age.padEnd(5)} ` +
  `${r.href || '(no link)'}`).join('\n'));

/* A row lookup that cannot crash the guard. When the page renders one row
   instead of six, `find` returns undefined and the FIRST property access
   throws — the guard exits non-zero, which is right, but with a TypeError
   instead of a named check, and every assertion after it never runs. A guard
   that dies on the first symptom reports one bug per run. */
const absent = [];
const BLANK = { slug: '', state: '', age: '', href: null, text: '', h: 0 };
const row = s => {
  const r = seen.rows.find(x => x.slug === s);
  if (!r) { absent.push(s); return BLANK; }
  return r;
};

// the blank-page check comes first: everything below is satisfiable by a
// page that rendered nothing at all
ok('the page has content', seen.bodyText > 100);
ok('a row per registry entry (6)', seen.count === 6);
ok('every row is actually visible, not merely in the DOM',
  seen.rows.length === 6 && seen.rows.every(r => r.h > 0));
ok('the columns are labelled, not the gaps',
  seen.labels.length === 2 && seen.labels.join(',') === 'project,last tick');

// the #117 shape: green pytest over a page showing one row, or six identical
const states = seen.rows.map(r => r.state);
ok('the rows are not all identical', new Set(states).size >= 4);
ok('the stalled row says stalled', row('stalled').state === 'stalled');
ok('the stalled row carries its age', /^\d+h$/.test(row('stalled').age));
ok('the dreaming row says dreaming', row('fresh').state === 'dreaming');
ok('the never-ticked row says no status', row('nostatus').state === 'no status');
ok('the deleted target is still listed, as missing',
  row('gone') && row('gone').state === 'missing');
ok('the mid-write row is still live, not blank',
  row('torn').state === 'dreaming');

// down rows: no link to a dead port, and the command to fix it
ok('the down row does not link to its dead port', row('fresh').href === null);
ok('the down row shows the command to start a dashboard',
  /--target/.test(row('fresh').text) && /watch\.py/.test(row('fresh').text));
// ...and the same assertion has to be able to FAIL, so one row is genuinely up
ok('an up row links out to its own origin',
  row('quiet').href === `http://127.0.0.1:${STUB_PORT}/`);
ok('an up row reports the count from that watch, not its own',
  /3 open questions/.test(row('quiet').text));
ok('a down row says the count is unknown rather than zero',
  /questions unknown/.test(row('fresh').text));
// both found by LOOKING at the screenshot, after every assertion above passed
ok('the missing row offers no command it cannot honour',
  !/--target/.test(row('gone').text) && /directory is gone/.test(row('gone').text));
ok('the mid-write row keeps BOTH its notes',
  /unreadable/.test(row('torn').text) && /--target/.test(row('torn').text));

ok('no horizontal overflow at 1200px', seen.docWidth <= seen.winWidth);
await p.screenshot({ path: `${OUT}/hub.png`, fullPage: true });

// narrow: long absolute paths and owns-lists are the things that blow out
await p.setViewportSize({ width: 380, height: 900 });
await sleep(300);
const narrow = await p.evaluate(() => ({
  doc: document.documentElement.scrollWidth, win: window.innerWidth,
  rows: document.querySelectorAll('.row').length,
}));
notes.push(`narrow: doc ${narrow.doc} win ${narrow.win} rows ${narrow.rows}`);
ok('no horizontal overflow at 380px', narrow.doc <= narrow.win);
ok('every row survives the narrow viewport', narrow.rows === 6);
await p.screenshot({ path: `${OUT}/hub-narrow.png`, fullPage: true });

ok(`every expected row is on the page${absent.length ? ' — absent: ' +
  absent.join(',') : ''}`, absent.length === 0);
ok('no page errors', errs.length === 0);
if (errs.length) notes.push(errs.join('\n'));

await br.close();
srv.kill();
stub.close();

console.log(notes.join('\n'));
console.log('----');
console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
