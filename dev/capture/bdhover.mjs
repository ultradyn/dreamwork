/* bdhover — #298: the burndown column inspector.

   One restrained chart-native inspector (`.bdinsp`) on #417's seam — the
   RICHER reading a deliberate look gets: a hover that dwells, a keyboard
   focus, or a tap. It names the exact interval, the open level, arrivals
   and completions, the commits, and the coverage state the geometry
   cannot say (a period with no ledger commit CARRIES the level; the
   current period is still arriving).

   OWN TARGET + OWN EPHEMERAL PORT, same reason as burndown.mjs: the datum
   is a property of a repository's ledger HISTORY. The history is PLANTED
   so the numbers are known, and every figure asserted here is derived
   from /data.json at runtime — never a literal tuned to today's fixture.

   What this guard proves (an end-state check could fail on none of it):
     - exact values: the inspector names the HOVERED column's served
       numbers, parsed by role (a wrong column's numbers would pass any
       visibility check);
     - the interval line corresponds to the bucket's served t0/t1;
     - coverage honesty: quiet period = carried, busy period = measured,
       last period = in progress;
     - edge-column clamping: first and last columns keep the inspector
       inside the panel and ABOVE the level track (never on a neighbour);
     - arrival has mid-frames (a snap has none); reduced motion snaps;
     - hover→focus parity, Escape and tap dismissal.

   usage: node bdhover.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const { ok, declare, finish, checks, notes, errs } = makeReporter();
const nameThrow = (kind, e) => {
  const msg = e && e.stack ? e.stack : String(e);
  errs.push(`${kind}: ${msg}`);
  checks.push(`FAIL the guard threw before finishing its checks: ${String(e)}`);
};
process.on('uncaughtException', e => nameThrow('uncaughtException', e));
process.on('unhandledRejection', e => nameThrow('unhandledRejection', e));
declare({
  drives: 'one own-server target (a planted git ledger) on an ephemeral ' +
          'port; GET / and /data.json; dispatched pointerover/out, focus, ' +
          'click and Escape keydown events on level columns; a ' +
          'reduced-motion context on the same target',
  traceWindow: '1.6s per inspector arrival capture (700ms dwell + the ' +
               '.42s ease-in, with margin); 500ms for reduced-motion'
});

// ── a planted ledger history ──────────────────────────────────────────────
// Hourly steps, six buckets, and each edge the inspector must name:
//   bucket 0: TWO revs (busy, measured) — the exact-values column
//   bucket 2: QUIET (no rev) — carried level, covered=0
//   bucket 5: last and quiet — carried AND in progress
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const T0 = Math.floor(Date.now() / 1000) - 6 * 3600;
const git = (args, at) => execFileSync('git', ['-C', DIR, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x',
         GIT_AUTHOR_DATE: `@${at} +0000`, GIT_COMMITTER_DATE: `@${at} +0000` },
}).toString().trim();
const entry = i => `- **#${i}** — task ${i} · P2 · task\n`;
const ledger = (open, done) =>
  `# Task ledger\n\nNext id: **99**\n\n## Open\n\n${open.map(entry).join('')}` +
  `\n## Recently landed\n\n${done.map(i => `**#${i}** landed (aaa111${i}).`).join(' ')}\n`;
const commit = (open, done, at) => {
  writeFileSync(join(DIR, '.dreamwork', 'tasks.md'), ledger(open, done));
  git(['add', '.dreamwork/tasks.md'], at);
  git(['commit', '-q', '-m', `ledger at ${at}`], at);
};
git(['init', '-q'], T0);
commit([1, 2, 3], [], T0);
commit([1, 2, 3, 4], [], T0 + 300);          // bucket 0: two revs
commit([2, 3, 4, 5], [1], T0 + 3600);        // bucket 1: arrive + land
//                                           // bucket 2: quiet — no rev
commit([2, 4, 5, 6], [3], T0 + 3 * 3600);    // bucket 3
commit([2, 4, 5, 6, 7], [], T0 + 4 * 3600);  // bucket 4
//                                           // bucket 5: quiet, in progress

const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);
const BASE = `http://127.0.0.1:${PORT}`;
const served = await (await fetch(`${BASE}/data.json`)).json();
if (served.target !== DIR) {
  console.log(`FAIL :${PORT} is serving ${served.target}, not ${DIR}`);
  process.exit(1);
}
const buckets = (served.burndown && served.burndown.buckets) || [];
const commits = buckets.map(b => b.commits || 0);
// THE PRECONDITIONS, asserted before anything that depends on them: the
// planted history really produced a busy bucket, a quiet middle bucket,
// and a quiet in-progress last bucket — a flat fixture would make every
// coverage check below vacuous (the born-hollow rule).
ok('precondition: six served buckets with the planted commit profile',
   buckets.length === 6 && commits[0] === 2 && commits[2] === 0 &&
   commits[5] === 0 && commits[1] === 1 && commits[3] === 1 && commits[4] === 1);
const quietIdx = 2, lastIdx = 5;
let busyIdx = 0;
commits.forEach((c, i) => { if (c > commits[busyIdx]) busyIdx = i; });
notes.push(`served buckets: ${JSON.stringify(buckets.map(b =>
  ({ t0: b.t0, o: b.open, a: b.arrived, l: b.landed, c: b.commits || 0 })))}`);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1500 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);
