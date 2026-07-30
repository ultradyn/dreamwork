/* #130 — the status section reads, rather than being a JSON dump.

   His words: "on main dashboard page for a dreamworker, the status section
   shows json. It should render that json nicely, using colors effectively,
   and making good use of space, and cutting out or hiding bulk or boring
   stuff."

   The section answers three questions — what is happening, who is doing it,
   whether anything needs him — and folds the rest, which exists so an agent
   can resume and is therefore load-bearing rather than junk.

   Four properties, and the last one is the one that will actually break:

     - it is not a JSON dump: no braces, quotes or key punctuation in what he
       reads at a glance
     - `awaiting_human` is impossible to miss when non-empty, and it is the
       only thing here wearing the accent
     - the bulk is FOLDED, not deleted: still in the DOM, an expand away
     - AN UNKNOWN KEY IS NEVER DROPPED. status.json is a schema rather than a
       fixed shape and the loop keeps adding to it, so a renderer that showed
       a known list would silently hide the next thing it learned to say. The
       fixture carries a key this renderer has never heard of, and it must
       still be findable.
   usage: node status.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'the status panel on / (one route, one glance read, one fold toggle)',
  traceWindow: 'static read at ~1.2s and a re-read ~0.4s after fold-open; ' +
               'no motion traced',
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1400 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the #status section the guard reads first, not a fixed sleep (#428 class)
await waitFor(p, '#status');

const raw = await p.evaluate(async () =>
  (await (await fetch('/data.json')).json()).status);
if (!raw) {
  ok('fixture provides a .dreamwork/status.json to read', false);
  notes.push('fixture needs a .dreamwork/status.json');
  await br.close(); finish(); process.exit(1);
}

const probe = await p.evaluate(() => {
  const sec = document.getElementById('status');
  if (!sec) return null;
  const vis = el => !!(el && el.checkVisibility && el.checkVisibility());
  // what he READS at a glance: text outside any collapsed disclosure
  const shown = [...sec.querySelectorAll('*')]
    .filter(el => !el.children.length && vis(el))
    .map(el => el.textContent.trim()).filter(Boolean);
  /* the accent as the browser RENDERS it. Reading `--accent` off :root gives
     the token as authored (`#a5b4fc`) while every computed `color` comes back
     as `rgb(165, 180, 252)`, so comparing the two silently matches nothing and
     "the accent is used nowhere else" passes on a page painted entirely in it.
     Resolve it through a throwaway element instead. */
  const probeEl = document.createElement('span');
  probeEl.style.color = 'var(--accent)';
  document.body.appendChild(probeEl);
  const accent = getComputedStyle(probeEl).color;
  probeEl.remove();
  const need = [...sec.querySelectorAll('.stneed *')].filter(el => vis(el));
  return {
    glance: shown.join(' · '),
    all: sec.textContent,
    height: Math.round(sec.getBoundingClientRect().height),
    folds: sec.querySelectorAll('details').length,
    openFolds: [...sec.querySelectorAll('details')].filter(d => d.open).length,
    accent,
    // the accent, spent here and only here
    needColours: need.map(el => getComputedStyle(el).color),
    accentElsewhere: [...sec.querySelectorAll('*')].filter(el =>
      !el.closest('.stneed') && vis(el) && !el.children.length &&
      getComputedStyle(el).color === accent).map(el => el.textContent.trim()),
  };
});
if (!probe) {
  ok('#status section rendered', false);
  notes.push('no #status section rendered');
  await br.close(); finish(); process.exit(1);
}

notes.push(`glance (${probe.height}px tall): ${probe.glance.slice(0, 400)}`);
notes.push(`folds: ${probe.folds} (${probe.openFolds} open)`);
notes.push(`accent ${probe.accent} on: needs-you ${probe.needColours.length} el` +
           ` | elsewhere ${JSON.stringify(probe.accentElsewhere)}`);

// ── it is not a JSON dump ───────────────────────────────────────────────
ok('no JSON punctuation in what he reads at a glance',
   !/[{}]|":\s|\[\s*"/.test(probe.glance));
ok('the section is a panel, not a wall — under ~30 lines at a glance',
   probe.height > 0 && probe.height < 700);

// ── the three facts it exists to carry ──────────────────────────────────
ok('what is happening', probe.glance.includes(raw.task));
ok('who is doing it', (raw.agents || []).every(a =>
   probe.glance.includes(a.name) && probe.glance.includes(a.in_flight)));
ok('and the goal the work serves', probe.glance.includes(raw.goal));

// ── whether anything needs him ──────────────────────────────────────────
const need = raw.awaiting_human || [];
ok('everything awaiting him is visible without a click',
   need.length > 0 && need.every(x => probe.glance.includes(x)));
ok('...and it is the only thing here wearing the accent',
   probe.needColours.length > 0 &&
   probe.needColours.some(c => c === probe.accent) &&
   probe.accentElsewhere.length === 0);

// ── the bulk is demoted, never dropped ──────────────────────────────────
ok('the bulk is folded away, not on screen',
   probe.folds > 0 &&
   !probe.glance.includes(raw.deploy) &&
   !probe.glance.includes((raw.monitors || [])[0]));
ok('...but still in the DOM, because an agent resumes from it',
   probe.all.includes(raw.deploy) &&
   (raw.monitors || []).every(m => probe.all.includes(m)) &&
   (raw.coordinator_next || []).every(c => probe.all.includes(c)));

// the one that will actually break: a key added after this shipped
const novelKey = Object.keys(raw)
  .find(k => /invented_after/.test(k));
ok('a key this renderer has never heard of is demoted, never dropped',
   !!novelKey && probe.all.includes(String(raw[novelKey])));

await p.screenshot({ path: `${OUT}/status.png`, fullPage: true });

// expanding the fold shows the rest, and does not break the page
await p.evaluate(() => {
  const d = document.querySelector('#status details');
  if (d) d.open = true;
});
await sleep(400);
const opened = await p.evaluate(() => {
  const sec = document.getElementById('status');
  const vis = el => !!(el && el.checkVisibility && el.checkVisibility());
  return [...sec.querySelectorAll('*')].filter(el => !el.children.length && vis(el))
    .map(el => el.textContent.trim()).join(' ');
});
ok('opening the fold reveals what it was holding',
   opened.includes(raw.deploy));
await p.screenshot({ path: `${OUT}/status-open.png`, fullPage: true });

ok('no page errors', errs.length === 0);
await br.close();
finish();
