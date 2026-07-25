/* The cross-contract guard: dreamhub against a REAL watch.py (#96, inc. 6).

   Stage 1 has exactly one cross-file dependency, and it is a protocol rather
   than an import: the hub polls each target's `GET /mtime` and re-reads
   `GET /data.json` when it changes. That is deliberate — it is what stops
   the hub growing a second questions.md parser and a second, subtly
   different open-question count.

   The cost of that choice is that `watch.py` belongs to another dreamer and
   can change under us. If `/mtime` stops being "<gen> <mtime>", or
   `open_questions` is renamed, or `/data.json` moves, the hub does not
   crash: it reports stale or unknown counts and looks completely fine doing
   it. Nothing else in stage 1 would notice.

   So this runs the real thing. It starts watch.py against a COPY of
   dev/capture/fixture (read-only use of a directory owned by another
   dreamer — copied, never edited), points a hub at it, and asserts the two
   agree. Then it changes the copy's questions.md and asserts the hub FOLLOWS
   — because agreeing once is also what a hub with a frozen cache does.

   usage: node dev/hub/contract.mjs <outdir> <port> */
import { mkdirSync, cpSync, readFileSync, writeFileSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = process.argv[2] || '/tmp/hubcontract';
const PORT = process.argv[3] || '39896';
/* Optional third argument: a path to run INSTEAD of the repo's watch.py.
   watch.py belongs to another dreamer and is not edited here, so this is how
   the guard is shown to discriminate — point it at a deliberately drifted
   COPY and watch it go red. A check that has only ever passed proves
   nothing, and this one exists precisely to catch a change nobody made on
   purpose. */
const WATCH = process.argv[4] || resolve(HERE, '..', '..', 'watch.py');
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const notes = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const kids = [];
const cleanup = () => kids.forEach(k => { try { k.kill(); } catch { } });
process.on('exit', cleanup);
const die = msg => { console.log(msg); cleanup(); process.exit(1); };

const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});

/* ---- a real watch.py over a copy of its own fixture ------------------ */
const target = join(OUT, 'target');
cpSync(join(ROOT, 'dev', 'capture', 'fixture'), target,
  { recursive: true, force: true });
const WPORT = await freePort();
writeFileSync(join(target, '.dreamwork', 'watch-port'), `${WPORT}\n`);

const watch = spawn('python3', [WATCH, '--target', target,
  '--port', String(WPORT)], { stdio: 'ignore' });
kids.push(watch);
let watchExit = null;
watch.on('exit', c => { watchExit = c; });

const fetchJson = async url => (await (await fetch(url)).json());
const WBASE = `http://127.0.0.1:${WPORT}`;
let wdata = null;
for (let i = 0; i < 60; i++) {
  if (watchExit !== null) die(`FAIL watch.py exited ${watchExit} (port ${WPORT} in use?)`);
  try {
    const d = await fetchJson(`${WBASE}/data.json`);
    // prove it is OUR watch, not a neighbour's on the same port
    if (d && d.target === target) { wdata = d; break; }
    die(`FAIL something else is serving ${WPORT} (target ${d && d.target})`);
  } catch { await sleep(250); }
}
if (!wdata) {
  // Distinguish "not running" from "running, but /data.json moved" — the
  // second is exactly the drift this guard exists to name, and reporting it
  // as a startup timeout would send the next reader to the wrong place.
  let alive = false;
  try { alive = (await fetch(`${WBASE}/`)).ok; } catch { }
  die(alive
    ? `FAIL watch.py is serving ${WPORT} but /data.json did not answer — `
      + `the endpoint the hub depends on has moved`
    : `FAIL watch.py never came up on ${WPORT}`);
}

/* ---- the shape the hub actually depends on --------------------------- */
const mtime = await (await fetch(`${WBASE}/mtime`)).text();
notes.push(`watch /mtime -> ${JSON.stringify(mtime)}`);
ok('/mtime is "<generation> <mtime>", the two-part cache key',
  /^\S+\s+\d+(\.\d+)?\s*$/.test(mtime));
ok('/data.json carries open_questions as a number',
  typeof wdata.open_questions === 'number');
// If the fixture ever has zero open questions, "the two agree" is satisfied
// by both being nothing, and this guard silently stops testing anything.
ok('the fixture has open questions to count', wdata.open_questions > 0);
notes.push(`watch open_questions = ${wdata.open_questions}`);

/* ---- a hub pointed at it --------------------------------------------- */
const home = join(OUT, 'hubhome');
mkdirSync(home, { recursive: true });
writeFileSync(join(home, 'projects.json'), JSON.stringify({
  version: 1,
  projects: [{ slug: 'fixture', path: target, added: '2026-07-25T12:00:00' }],
}, null, 2));

const hub = spawn('python3', [join(ROOT, 'dreamhub.py'), 'serve',
  '--port', PORT], { env: { ...process.env, DREAMHUB_HOME: home }, stdio: 'ignore' });
kids.push(hub);
let hubExit = null;
hub.on('exit', c => { hubExit = c; });
const HBASE = `http://127.0.0.1:${PORT}`;
const hubRow = async () => (await fetchJson(`${HBASE}/hub.json`)).projects[0];

let row = null;
for (let i = 0; i < 60; i++) {
  if (hubExit !== null) die(`FAIL dreamhub exited ${hubExit} (port ${PORT} in use?)`);
  try {
    const j = await fetchJson(`${HBASE}/hub.json`);
    if (j.projects && j.projects[0] && j.projects[0].slug === 'fixture') {
      row = j.projects[0]; break;
    }
    die(`FAIL something else is serving ${PORT}`);
  } catch { await sleep(250); }
}
if (!row) die(`FAIL dreamhub never came up on ${PORT}`);

notes.push(`hub row: watch=${row.watch} open_questions=${row.open_questions}`);
ok('the hub sees the watch instance as up', row.watch === 'up');
ok('the hub reports the SAME count the watch instance reports',
  row.open_questions === wdata.open_questions);

// and the page renders it, not just the JSON
const page = await (await fetch(`${HBASE}/`)).text();
ok('the count reaches the page',
  page.includes(`${wdata.open_questions} open question`));

/* ---- and it FOLLOWS ---------------------------------------------------
   Agreeing once is also what a hub with a permanently frozen cache does.
   The mutation is what separates "reads the contract" from "read it once". */
const qpath = join(target, '.dreamwork', 'questions.md');
const q = readFileSync(qpath, 'utf-8');
const marker = '- **2026-07-25 — a question added by the contract guard, to '
  + 'prove the hub follows a change rather than caching the first answer.** '
  + 'Its body exists so the entry is well formed.\n';
writeFileSync(qpath, q.replace('## Open\n\n', '## Open\n\n' + marker));

const want = wdata.open_questions + 1;
const after = await fetchJson(`${WBASE}/data.json`);
ok(`watch.py counts the new question (${after.open_questions} = ${want})`,
  after.open_questions === want);

let followed = null;
for (let i = 0; i < 30; i++) {
  const r = await hubRow();
  if (r.open_questions === want) { followed = i * 200; break; }
  await sleep(200);
}
notes.push(`hub followed after ${followed === null ? 'never' : followed + 'ms'}`);
ok('the hub follows the change within a poll', followed !== null);

cleanup();
console.log(notes.join('\n'));
console.log('----');
console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
