/* #140 — the page says which revision it is RUNNING, so a stale view
   announces itself instead of being mistaken for a bug.

   The motivating incident: #129 was reported 24 seconds after the commit
   that fixed it and about four minutes before the deploy. The report was
   accurate, the code was correct, and a tracing cycle went into the gap
   between them. A fix that is committed and not deployed is
   indistinguishable from a bug, and he is looking at the deployed page.

   THIS GUARD BUILDS ITS OWN TARGET and takes an ephemeral port, dashboard
   .mjs-style, for a sharper reason than usual: the state under test is a
   relationship between the RUNNING BYTES and a repository's history of
   `watch.py`. `dev/capture/fixture` is not a repository at all, so the
   shared server can only ever be in the "cannot tell" state — every check
   below except one would have passed vacuously against it.

   The four states are reached by evolving ONE repo in order, because the
   answer is a function of history and history only moves forwards:

     no repo    a checkout that tracks no watch.py — the ordinary state for
                a target that is somebody else's project
     untracked  watch.py has history, and the running bytes are in none of it
     current    the running bytes ARE HEAD's watch.py
     behind     the running bytes are an older revision, and we know which

   Only ONE of those means "I compared and they differ". That separation is
   the whole point of deployed.py and it is what this asserts — the bug it
   was written for was a shell script that reported "no match" three times
   with total confidence, having compared nothing.

   usage: node serving.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored. #461 made this adopt argv[3] so a squatter red-proof could aim, and
// because the recipe always passes {{port}} that silently forced this guard onto
// the shared server's port, where serveVerified rightly refused -- so the guard
// stopped running at all (#471). Registration is not execution.
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = []; const errs = [];
/* Print from an exit handler, never from the tail: a guard that throws part
   way through prints nothing at all, and that reads identically to printing
   no failures. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

// ── a target whose history we control, and a copy of the RUNNING file ──────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const git = args => execFileSync('git', ['-C', DIR, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x' },
}).toString().trim();
const commitWatch = (bytes, msg) => {
  writeFileSync(join(DIR, 'watch.py'), bytes);
  git(['add', 'watch.py']);
  git(['commit', '-q', '-m', msg]);
  return git(['rev-parse', '--short', 'HEAD']);
};
git(['init', '-q']);
git(['add', 'DREAMWORK.md']);
git(['commit', '-q', '-m', 'a project that is not this dashboard']);

// The bytes the server will be running. Copied from disk BEFORE the spawn so
// the two reads cannot straddle an edit, and it is the real file rather than
// a stand-in because "is this byte-identical to a revision" is the claim.
const RUNNING = readFileSync('watch.py');

/* #461: serveVerified proves the responder is the target we just built. */
const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });

const BASE = `http://127.0.0.1:${PORT}`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));

/* Read the line, and RETURN A READING when it is absent rather than throwing
   or waiting one out. Both of those cost thirty seconds and then name the
   guard instead of the page — and the state this check exists for (the line
   is not rendered at all) is exactly the state where its subject is missing.

   The rail colour is resolved through a throwaway element painted with the
   token, because `getComputedStyle(:root).getPropertyValue('--warn')` gives
   the token AS AUTHORED (`#fcd34d`) while every computed colour comes back
   as `rgb(…)`, and comparing those two matches nothing at all. */
const READ = `(() => {
  const el = document.querySelector('.gserve');
  if (!el) return { present: false };
  const cs = getComputedStyle(el);
  const probe = document.createElement('span');
  probe.style.color = 'var(--warn)';
  document.body.appendChild(probe);
  const warn = getComputedStyle(probe).color;
  probe.style.color = 'var(--dim)';
  const dim = getComputedStyle(probe).color;
  probe.style.color = 'var(--dimmer)';
  const dimmer = getComputedStyle(probe).color;
  probe.remove();
  const label = [...document.querySelectorAll('#sections > .label')]
    .find(l => l.textContent === 'commits');
  return {
    present: true,
    text: el.textContent,
    title: el.getAttribute('title') || '',
    stale: el.classList.contains('stale'),
    unknown: el.classList.contains('unknown'),
    colour: cs.color, rail: cs.borderLeftWidth, railColour: cs.borderLeftColor,
    warn, dim, dimmer,
    afterCommitsLabel: !!label && label.nextElementSibling === el,
    beforeRows: !!el.nextElementSibling &&
                el.nextElementSibling.classList.contains('git'),
  };
})()`;
const read = async why => {
  // a full load, not a tick: the deployed answer is cached on HEAD and the
  // page is being asked a fresh question each time
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(900);
  const r = await p.evaluate(READ);
  notes.push(`${why}: ${JSON.stringify(r)}`);
  return r;
};

// ── 1. no repo — history exists, watch.py's does not ──────────────────────
{
  const r = await read('no repo');
  ok('the line is rendered even when the answer is "cannot tell"', r.present);
  ok('...it says unknown rather than staying silent',
     !!r.present && r.unknown && /unknown/.test(r.text));
  ok('...and it is NOT dressed as a fault', !!r.present && !r.stale &&
     r.rail === '0px' && r.colour === r.dimmer);
  ok('...it sits between the commits label and the rows',
     !!r.present && r.afterCommitsLabel && r.beforeRows);
}

// ── 2. untracked — watch.py has history, the running bytes are in none ────
{
  commitWatch(Buffer.from('# an older dashboard, byte-different\n'),
              'feat: a dashboard this guard is not running');
  const r = await read('untracked');
  // the precondition, asserted rather than assumed: with no watch.py history
  // this state is indistinguishable from "no repo" and the check below is
  // satisfied by the wrong answer
  ok('...watch.py now HAS history (or the state below is vacuous)',
     git(['log', '--format=%H', '--', 'watch.py']).split('\n').filter(Boolean).length === 1);
  ok('running bytes in no commit reads as a fault',
     !!r.present && r.stale && /no commit/.test(r.text));
  ok('...on the rail, in --warn', !!r.present &&
     r.rail === '2px' && r.railColour === r.warn && r.colour === r.warn);
}

// ── 3. current — the running bytes ARE HEAD's watch.py ────────────────────
let servedRev;
{
  servedRev = commitWatch(RUNNING, 'feat: the revision this guard is running');
  const r = await read('current');
  ok('a page running HEAD names the revision it is running',
     !!r.present && r.text === `serving ${servedRev}`);
  ok('...quietly: no rail, no warn, one step above the unknown line',
     !!r.present && !r.stale && !r.unknown &&
     r.rail === '0px' && r.colour === r.dim && r.dim !== r.dimmer);
  ok('...and it carries no missing-commit list', !!r.present && r.title === '');
}

// ── 4. behind — an older revision, and we know which ──────────────────────
{
  git(['commit', '-q', '--allow-empty', '-m',
       'docs: a commit that does not touch the dashboard']);
  commitWatch(Buffer.from('# newer\n'), 'fix: the first change he cannot see');
  commitWatch(Buffer.from('# newer still\n'), 'feat: the second change he cannot see');
  const head = git(['rev-parse', '--short', 'HEAD']);
  const r = await read('behind');
  // the same vacuity guard as above, one level up: if the served revision
  // were HEAD, "behind" and "current" would render the same words
  ok('...HEAD has really moved past the served revision (or this is vacuous)',
     head !== servedRev);
  ok('a page behind HEAD says so, and by how much',
     !!r.present &&
     r.text === `this page is 2 watch.py commits behind · serving ${servedRev}`);
  ok('...as a fault, on the rail, in --warn', !!r.present &&
     r.stale && r.rail === '2px' && r.railColour === r.warn);
  // detail is ranked, never withheld: the summary is the line and the
  // individual commits are in its title, so the row never grows to hold them
  ok('...and hovering gives him every commit he is missing', !!r.present &&
     /the first change he cannot see/.test(r.title) &&
     /the second change he cannot see/.test(r.title));
  // pathspec-filtered, which is why the copy says "watch.py commits": HEAD
  // moved three times and the dashboard moved twice
  ok('...counting watch.py commits, not every commit',
     !!r.present && !/does not touch the dashboard/.test(r.title));
}

finished = true;
await br.close();
try { srv.kill(); } catch (e) {}
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
