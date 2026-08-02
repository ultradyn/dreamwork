/* goalfault — #1029: an unreadable goal node must not look like a healthy tree.

   The /goals renderer degrades a single node rather than discarding the tree,
   and the dashboard's goalHandle names a faulted CURRENT goal. But when the
   current goal was healthy and a SIBLING carried state_error, the dashboard
   selected only the current node and checked state_error on it alone — so the
   handle rendered an ordinary open/healthy state with no hint that part of
   the tree could not be read. That is #136 at the surface that matters most:
   a tree with an unreadable node must not look identical to a healthy one.

   This is the THIRD time the renderer-contract seam has been wrong on this
   task, because no committed guard executes the renderers. The payload tests
   proved the backend was healthy and could not see a frontend that threw, and
   the token-only native check could not see structure. So this guard asserts
   RENDERED OUTPUT — not payload — across all four cells of the fault matrix:

     surface   faulted current     faulted NOT current
     /goals    good id + fault     good id + fault
     dashboard fault visible       fault visible (Finding 1)

   Good nodes are asserted BY TITLE (the fixture's unique identifier, 1:1 with
   its id) so "renders nothing at all" cannot pass. The dashboard assertions
   confirm the CURRENT goal's healthy title is present alongside the fault
   count — not merely that the word "unreadable" appears for any reason.

   Finding 1 binds the identity contract: the faulted node must be the one
   named unreadable (by FAULT_TITLE), the healthy node must NOT be, and the
   current-goal panel's data-goal-id pins identity by id — so a swap of the
   fault onto the healthy node, or a title collision, cannot pass.

   Finding 1 (two-sided): the dashboard handle shows a .goalwarn count for
   non-current unreadable nodes. The faulted-CURRENT cell must show ZERO
   warnings and the faulted-NOT-current cell exactly ONE. A presence-only
   check caught the DOWN direction (zeroed-out warning) but was blind to
   the UP direction (spurious warning on the current cell) — only a COUNT
   distinguishes "correct" from "spurious", and both directions are asserted.

   Finding 3: the /goals assertions run through a case table over
   {current, noncurrent} so a future identity assertion cannot land in one
   mode only — the asymmetry that let Finding 1's one-sidedness survive.

   THIS GUARD BUILDS ITS OWN TARGET and takes an ephemeral port. The shared
   fixture has no goals at all, let alone one with a NULL goal_state. The
   Python helper (goalfault_fixture.py) creates two goals both in the 'open'
   state — one destined to be faulted — and sets the current-goal pointer per
   mode. The NULL goal_state injection runs in this guard (lines above), not
   the fixture, because the no-raw-connect guard (#645) scans .py files.

   usage: node goalfault.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveAllVerified } from './serve.mjs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const BASE = await freePort();

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'two own-server targets (a faulted-current goal tree and a ' +
          'faulted-sibling tree) each on its own port; GET /goals and / on ' +
          'each; no writes, no motion traced',
  traceWindow: 'static reads after ~1.1s settle per target per route; the ' +
               'claim is about structure, not motion',
});

/* Build the two fixtures. Each copies the shared fixture's .dreamwork skeleton
   (questions.md etc.) then plants goals via the Python helper. The NULL
   goal_state injection runs as a separate inline python3 -c call here rather
   than in the .py fixture: the no-raw-connect guard (#645) scans every
   non-test .py file, and this is test infrastructure, not production — but the
   guard cannot tell the difference, so the injection lives in the .mjs guard. */
const modes = ['current', 'other'];
const entries = [];
const ids = {};
for (const mode of modes) {
  const dir = join(OUT, mode);
  rmSync(dir, { recursive: true, force: true });
  cpSync('dev/capture/fixture', dir, { recursive: true });
  const raw = execFileSync(
    'python3', ['dev/capture/goalfault_fixture.py', dir, mode],
    { stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf-8' }).trim();
  ids[mode] = JSON.parse(raw);
  /* NULL the faulted node's goal_state — the real production fault. */
  execFileSync('python3', ['-c',
    `import sqlite3; c=sqlite3.connect(${JSON.stringify(ids[mode].db_path)}); ` +
    `c.execute("UPDATE task_group SET goal_state = NULL WHERE id = ?", ` +
    `(${ids[mode].fault_id},)); c.commit(); c.close()`],
    { stdio: 'ignore' });
  entries.push([mode, dir]);
}
notes.push(`current: good=${ids.current.good_id} fault=${ids.current.fault_id} ` +
           `current=${ids.current.current_id}`);
notes.push(`other: good=${ids.other.good_id} fault=${ids.other.fault_id} ` +
           `current=${ids.other.current_id}`);

const { children: servers, ports } = await serveAllVerified(entries, BASE);
const stopAll = () => servers.forEach(s => { try { s.kill(); } catch (e) {} });
process.on('exit', stopAll);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* The good goal's title is the fixture's unique identifier — 1:1 with its id.
   Asserting it present proves the renderer did not silently emit an empty tree. */
const GOOD_TITLE = 'Healthy goal';
const FAULT_TITLE = 'Broken goal';

/* Read the dashboard's goal handle: its text, the current goal's title and
   state, whether the fault word appears, and the COUNT of .goalwarn spans.
   The state span distinguishes a faulted-current handle (state reads
   "unreadable") from a healthy-current handle that carries a non-current
   fault count. The warnCount is what Finding 1 binds on: presence of the
   word cannot prove whether a warning is correct or spurious — only the
   count can, because production emits exactly one .goalwarn per non-current
   unreadable node and zero when the only faulted node IS current. */
const PROBE_DASH = `(() => {
  const handle = document.querySelector('.goalhandle');
  if (!handle) return { present: false };
  const stateEl = handle.querySelector('.goalstate');
  const titleEl = handle.querySelector('.goaltitle');
  const text = handle.textContent.trim();
  return {
    present: true,
    text,
    state: stateEl ? stateEl.textContent.trim() : null,
    title: titleEl ? titleEl.textContent.trim() : null,
    faultClass: /\\bfault\\b/.test(handle.className),
    hasUnreadable: /unreadable/i.test(text),
    /* Finding 1 — count the .goalwarn elements, not just whether the word
       appears. Presence cannot distinguish a correct warning from a spurious
       one; only a count can. Production emits exactly one .goalwarn per
       non-current unreadable node (views.js:270-278). */
    warnCount: handle.querySelectorAll('.goalwarn').length,
  };
})()`;

/* Read the /goals page. Each row is returned as {title, meta, unreadable} so
   assertions can pair a node's identity with its fault state — "unreadable
   appears somewhere" does not prove WHICH node faulted (Finding 1). The
   current-goal panel's data-goal-id pins the current goal's identity by id,
   not just by title. */
const PROBE_GOALS = `(() => {
  const rows = [...document.querySelectorAll('.goaltree-row')];
  const rowDetails = rows.map(r => {
    const t = r.querySelector('.goaltree-title');
    const m = r.querySelector('.goalmeta');
    const metaText = m ? m.textContent.trim() : '';
    return {
      title: t ? t.textContent.trim() : '',
      meta: metaText,
      unreadable: /unreadable/i.test(metaText),
    };
  });
  const fullText = document.querySelector('#view')
    ? document.querySelector('#view').textContent : '';
  const currentEl = document.querySelector('.goalcurrent');
  return {
    rowCount: rows.length,
    rows: rowDetails,
    titles: rowDetails.map(r => r.title),
    hasUnreadable: /unreadable/i.test(fullText),
    currentGoalId: currentEl ? currentEl.getAttribute('data-goal-id') : null,
    fullText: fullText.slice(0, 400),
  };
})()`;

const look = async (name, route, probe) => {
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`${name}${route}: ${e}`));
  await p.goto(`http://127.0.0.1:${ports[name]}${route}`,
               { waitUntil: 'networkidle' });
  /* Wait for the route's subject before probing — under load the client-side
     render (data.json → goalHandle/goalsTree) can take longer than a fixed
     sleep, and the report.mjs absence-first rule says assert the subject
     exists before driving it (#192). The dashboard renders .goalhandle; /goals
     renders .goaltree-row. A missing subject is a named FAIL, not a timeout. */
  const sel = route === '/goals' ? '.goaltree-row' : '.goalhandle';
  await p.waitForSelector(sel, { timeout: 8000 }).catch(() => {});
  await sleep(300);
  const r = await p.evaluate(probe);
  await p.screenshot({ path: `${OUT}/${name}${route === '/' ? '-dash' : ''}.png`,
                       fullPage: true });
  await p.close();
  return r;
};

// ── /goals: both modes show good nodes by id AND the fault ──────────────
const goalsCurrent = await look('current', '/goals', PROBE_GOALS);
const goalsOther = await look('other', '/goals', PROBE_GOALS);

notes.push(`/goals current: ${goalsCurrent.rowCount} rows, ` +
           `titles=${JSON.stringify(goalsCurrent.titles)}`);
notes.push(`/goals other: ${goalsOther.rowCount} rows, ` +
           `titles=${JSON.stringify(goalsOther.titles)}`);

/* Finding 3 — a case table over {current, noncurrent} so a future identity
   assertion lands in BOTH cells, not one. Finding 1's asymmetry was possible
   because the two modes repeated their assertions by hand: an identity check
   written for one mode could be absent from the other and the guard still
   passed. Each row asserts the SAME shape against mode-specific expectations,
   so the class of one-sided drift is removed. */
const goalCases = [
  { label: 'faulted CURRENT',     data: goalsCurrent, expectedId: ids.current.fault_id },
  { label: 'faulted NOT current', data: goalsOther,   expectedId: ids.other.good_id   },
];
/* Finding 3 gate — cardinality + identity BEFORE the loop. The table exists so
   a one-sided drift cannot pass, but a table that can silently shrink to one
   case reintroduces exactly that defect: six assertions quietly vanish and the
   suite still reports green. A length check alone is not enough — it passes a
   table with the same case twice — so both the COUNT and the NAMES are gated. */
const REQUIRED_GOAL_LABELS = ['faulted CURRENT', 'faulted NOT current'];
ok('goalCases: exactly two cases (current + noncurrent)',
   goalCases.length === REQUIRED_GOAL_LABELS.length);
for (const required of REQUIRED_GOAL_LABELS) {
  ok(`goalCases: required case '${required}' is present`,
     goalCases.some(c => c.label === required));
}
for (const { label, data, expectedId } of goalCases) {
  ok(`/goals (${label}): the good goal title is present`,
     data.titles.includes(GOOD_TITLE));
  ok(`/goals (${label}): the faulted node is visible as unreadable`,
     data.hasUnreadable);
  ok(`/goals (${label}): the tree rendered >1 node`,
     data.rowCount >= 2);
  ok(`/goals (${label}): the faulted node (Broken goal) is the unreadable row`,
     data.rows.some(r => r.title === FAULT_TITLE && r.unreadable));
  ok(`/goals (${label}): the healthy node (Healthy goal) is NOT unreadable`,
     data.rows.some(r => r.title === GOOD_TITLE && !r.unreadable));
  ok(`/goals (${label}): the current-goal panel names the expected id`,
     data.currentGoalId === String(expectedId));
}

// ── dashboard: both modes show the fault ────────────────────────────────
const dashCurrent = await look('current', '/', PROBE_DASH);
const dashOther = await look('other', '/', PROBE_DASH);

notes.push(`/ (faulted CURRENT): state=${dashCurrent.state} ` +
           `title=${dashCurrent.title} fault=${dashCurrent.faultClass} ` +
           `warns=${dashCurrent.warnCount}`);
notes.push(`/ (faulted NOT current): state=${dashOther.state} ` +
           `title=${dashOther.title} warns=${dashOther.warnCount} ` +
           `text=${JSON.stringify(dashOther.text)}`);

ok('dashboard (faulted CURRENT): the handle exists',
   dashCurrent.present);
ok('dashboard (faulted CURRENT): the faulted current goal shows unreadable',
   dashCurrent.present && /unreadable/i.test(dashCurrent.state || ''));
ok('dashboard (faulted CURRENT): the unreadable current goal is named Broken goal',
   dashCurrent.present && dashCurrent.title === FAULT_TITLE);

/* Finding 1 — the guard is TWO-SIDED. The faulted-CURRENT mode must show
   ZERO .goalwarn elements (the faulted node IS current, so no non-current
   node is unreadable), and the faulted-NOT-current mode must show EXACTLY
   ONE. The old presence-only check ("does unreadable appear?") caught the
   DOWN direction (a zeroed-out warning) but was blind to the UP direction
   (a spurious warning on the current cell), because in the current mode the
   word "unreadable" already appears in the state span. A COUNT distinguishes
   "the warning is correct" from "there is a spurious warning" — and counts
   are asserted in BOTH directions here so neither blind spot can return. */
ok('FINDING 1: dashboard (faulted CURRENT): exactly 0 non-current unreadable warnings',
   dashCurrent.present && dashCurrent.warnCount === 0);

ok('dashboard (faulted NOT current): the handle exists',
   dashOther.present);
ok('dashboard (faulted NOT current): the current goal is the HEALTHY one',
   dashOther.present && dashOther.title === GOOD_TITLE);
ok('dashboard (faulted NOT current): the current state reads healthy (open)',
   dashOther.present && dashOther.state === 'open');
ok('FINDING 1: dashboard (faulted NOT current): exactly 1 non-current unreadable warning',
   dashOther.present && dashOther.warnCount === 1);

ok('no page errors', errs.length === 0);
await br.close();
stopAll();
finish();
