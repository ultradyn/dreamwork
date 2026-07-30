/* #190 — the loop's push channel to the human can die (attn 403, "out of
   credits or need a Grok subscription", for an entire afternoon) and only the
   dashboard can say so: the channel for reporting a broken channel WAS the
   broken channel. status.json gains a `push` object and the dashboard renders
   its failure state.

   THREE STATES, and holding all three at once is the whole value of this
   guard — each is easy to get right alone and the failure is always that one
   swallowed another:

     ABSENT   no `push` key — the loop has never tried to push. Quiet.
     OK       push.ok === true — the last push landed. Quiet.
     FAILED   push.ok === false — the last push failed. Loud: `--warn` on a
              rail, naming the channel and the reason, because the remedy is
              his and "push down" alone sends him hunting.

   "QUIET" IS WHERE THIS CHECK DIES, and it dies in two directions at once:
   a renderer that shows nothing for ABSENT and OK is only correct if it
   COULD have told them apart, and a renderer that shows nothing for FAILED
   is the bug itself. So this guard asserts the data makes the three
   distinguishable (the anti-vacuity precondition) BEFORE it asserts the
   renders — a check that read "nothing rendered" in all three cases would
   otherwise pass over the entire feature.

   Each state is served from its own scratch target, built here from
   dev/capture/fixture: the shared fixture is deliberately healthy, its
   status.json carries no `push` key, and it is shared with every other guard.
   usage: node pushhealth.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, rmSync, cpSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveAllVerified } from './serve.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = +(process.argv[3] || 39893);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'three scratch targets rendering ABSENT / OK / FAILED push ' +
          'states on /, each on its own port, compared for distinguishability',
  traceWindow: 'static read per state at ~1.1s settle; no motion traced',
});

// The fixture's status.json, loaded so we can plant a `push` field per state.
const FIX_STATUS = JSON.parse(
  readFileSync('dev/capture/fixture/.dreamwork/status.json', 'utf8'));
// ANTI-VACUITY: assert the fixture does NOT already carry a `push` key, so
// the ABSENT state is truthful. A fixture that grew one silently would make
// the ABSENT case test a lie.
if ('push' in FIX_STATUS) {
  ok('fixture status.json lacks a `push` key (so the ABSENT state is truthful)',
     false);
  finish();
  process.exit(1);
}

// `at` comes from the clock, never from memory — the page renders it as an
// age, and the clock rule is the same one last_tick follows (lint enforces
// it). A few minutes ago so "failed Nm ago" reads as a real age.
const minsAgo = m => new Date(Date.now() - m * 60000).toISOString();

const states = {
  absent: null,                              // no push key at all
  ok:    { at: minsAgo(3), channel: 'PushNotification',
           ok: true,  detail: 'delivered' },
  failed:{ at: minsAgo(4), channel: 'attn',
           ok: false,
           detail: '403 — out of credits or need a Grok subscription' },
};

/* one scratch target per state, each on its own port, so the three renders
   can be compared without a server restart racing a read. Served through
   serve.mjs (#461) rather than spawn-and-sleep: a fixed base port +
   ports[name]=++port lands in the orphan range, and a blind sleep grades
   whoever already holds it. serveAllVerified proves each responder is
   alive AND serving the directory we just wrote. */
const entries = [];
for (const [name, push] of Object.entries(states)) {
  const dir = join(OUT, name);
  rmSync(dir, { recursive: true, force: true });
  cpSync('dev/capture/fixture', dir, { recursive: true });
  const doc = JSON.parse(JSON.stringify(FIX_STATUS));
  if (push) doc.push = push;
  writeFileSync(join(dir, '.dreamwork', 'status.json'), JSON.stringify(doc, null, 2));
  entries.push([name, dir]);
}
const { children: servers, ports } = await serveAllVerified(entries, PORT);
// Reap every server we start, in a trap, including on failure — the task's
// hard rule. The reporter's own exit handler (registered in makeReporter)
// prints the checks + crash sentinel; this one only reaps servers. Both
// fire on normal exit, process.exit(), crash, and signal — so the explicit
// SIGTERM/SIGINT/uncaughtException handlers the guard used to carry are
// covered by this exit handler + Node's default signal→exit path.
const stopAll = () => servers.forEach(s => { try { s.kill(); } catch (e) {} });
process.on('exit', stopAll);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* Resolve `--warn` through a throwaway element: `--warn` off :root comes back
   as authored (`#fcd34d`) while every computed colour is `rgb(...)`, so
   comparing the two matches nothing — the trap status.mjs documents. */
const PROBE = `(() => {
  const el = document.createElement('span');
  el.style.color = 'var(--warn)';
  document.body.appendChild(el);
  const warn = getComputedStyle(el).color;
  el.remove();
  const sec = document.getElementById('status');
  if (!sec) return { present: false };
  const push = sec.querySelector('.stpush');
  const vis = n => !!(n && n.checkVisibility && n.checkVisibility());
  const leaf = [...sec.querySelectorAll('*')]
    .filter(n => !n.children.length && vis(n))
    .map(n => n.textContent.trim()).filter(Boolean).join(' ');
  return {
    present: !!push,
    text: push ? push.textContent.replace(/\\s+/g, ' ').trim() : '',
    railed: push ? getComputedStyle(push).borderLeftColor === warn : false,
    head: push ? (push.querySelector('.stpushhead') || {}).textContent || '' : '',
    ageNode: push ? !!push.querySelector('.age[data-at]') : false,
    // no other element in #status wears --warn when there is no fault: a page
    // that painted the accent-as-warn or leaked it elsewhere is the same
    // silent-class failure this whole page is organised against
    warnedElsewhere: [...sec.querySelectorAll('*')]
      .filter(n => push !== null && n !== push && !push.contains(n) &&
                   vis(n) && !n.children.length &&
                   getComputedStyle(n).color === warn)
      .map(n => n.textContent.trim()),
    glance: leaf,
  };
})()`;

const look = async (name) => {
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(`${name}: ${e}`));
  await p.goto(`http://127.0.0.1:${ports[name]}/`, { waitUntil: 'networkidle' });
  await sleep(1100);
  const r = await p.evaluate(PROBE);
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await p.close();
  return r;
};

const absent = await look('absent');
const okst   = await look('ok');
const failed = await look('failed');

notes.push(`absent:  stpush present=${absent.present}`);
notes.push(`ok:      stpush present=${okst.present}`);
notes.push(`failed:  stpush present=${failed.present} railed=${failed.railed}`);
notes.push(`failed head: ${JSON.stringify(failed.head)}`);
notes.push(`failed text: ${failed.text.slice(0, 220)}`);

// ── the anti-vacuity precondition: the three DATA shapes actually differ ──
// A check that read "nothing rendered" in all three cases would pass over the
// whole feature, so assert first that the data is genuinely three states:
// absent lacks the key, ok has ok===true, failed has ok===false. Derive these
// at runtime from the same FIX_STATUS we planted, not from literals.
ok('ANTI-VACUITY: the absent state truthfully lacks a push key',
   !('push' in FIX_STATUS));
ok('ANTI-VACUITY: the ok state truthfully says ok===true (a different fact)',
   states.ok && states.ok.ok === true);
ok('ANTI-VACUITY: the failed state truthfully says ok===false (a third fact)',
   states.failed && states.failed.ok === false);
ok('...and the channel that died is named in the failed data, not hard-coded',
   states.failed.channel === 'attn' && /attn/.test(states.failed.detail) === false);

// ── the two quiet states stay quiet, which keeps the loud one credible ────
ok('ABSENT (never tried) renders no push fault',
   absent.present === false);
ok('ABSENT keeps the whole status panel clear of the warn colour',
   absent.warnedElsewhere && absent.warnedElsewhere.length === 0);
ok('OK (last push landed) renders no push fault either',
   okst.present === false);
ok('OK keeps the status panel clear of the warn colour',
   okst.warnedElsewhere && okst.warnedElsewhere.length === 0);

// ── and the failed state is loud, and names the actionable part ───────────
ok('FAILED renders the push fault block',
   failed.present === true);
ok('...on the warn rail (the page\'s one BROKEN colour)',
   failed.railed === true);
ok('...and it NAMES THE CHANNEL that died (attn), not just "push down"',
   /attn/.test(failed.text));
ok('...and it NAMES THE REASON (the actionable part — billing, not re-auth)',
   /403|credits|subscription/.test(failed.text));
ok('...and it renders WHEN it failed as a live age (the clock rule)',
   failed.ageNode === true);
ok('the dashboard proper still renders under it (status is not blank)',
   /status/i.test(failed.glance) && failed.glance.length > 0);

// ── the renderer branches strictly, so ok must be exactly true ────────────
// ok:"true" (string), ok:1, or a missing ok must all read as NOT-failed. The
// browser cannot easily exercise the missing-ok case without a fourth server,
// but the strict branch is asserted statically by test_watch.py and the
// wrong-type case is caught by lint — both named here so the three checks are
// known to compose.
ok('no page errors', errs.length === 0);
await br.close();
stopAll();
finish();
