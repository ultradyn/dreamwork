/* research — #484: a listing surface for built research HTML
   (/research), with one artifact viewed at /research?p=<name> through the
   review view's own idiom (the raw page at /researchraw in the same
   #reviewwrap/#reviewframe iframe). What research deliberately does NOT
   reuse is the review SURFACE: no questions.md pairing, no
   archive-on-answered lifecycle — research outlives the decisions it
   informed (.dreamwork/docs/research/README.md).

   Production lines the red-proofs name (watch.py):
     · the "research" key in collect() — removing it empties the listing;
     · buildResearch's doc branch (the iframe src to /researchraw) —
       removing it reds the view-half checks;
     · the no-slash basename rule in /researchraw — removing it serves a
       src/ source as a finished artifact and reds the confinement check;
     · the crossfade path itself — the route-arrival evidence asks the
       browser (transitionstart, #442) whether the existing dissolve ran,
       so a snap navigation reds it.

   usage: node research.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { readdirSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const OUT = process.argv[2], PORT = process.argv[3] || '39886';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/research listing → row link (real click) → /research?p=… ' +
          'artifact view, the crumb back, /researchraw confinement, and a ' +
          'reduced-motion route swap',
  traceWindow: 'settle reads after ~1.6s per navigation (the dissolve is ' +
               '~1.15s). No frame traces: route-transition evidence is ' +
               'transitionstart on #view, the load-independent snap ' +
               'detector (#442).',
});

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions, derived from served data + the live fixture ─────────── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const listed = (d.research || []).map(r => r.name);
const target = d.target;
ok('precondition: the fixture serves at least one built research artifact',
   listed.length >= 1);
ok('precondition: every listed name is a bare .html basename (no slashes)',
   listed.length >= 1 &&
   listed.every(n => n.endsWith('.html') && !n.includes('/')));
const onDisk = readdirSync(join(target, '.dreamwork', 'docs', 'research'));
const srcOnDisk = readdirSync(join(target, '.dreamwork', 'docs', 'research',
                                   'src'));
ok('precondition: the fixture really has a src/ source (.html, on disk) — ' +
   'the ignore-half has a subject', srcOnDisk.some(n => n.endsWith('.html')));
ok('precondition: disk holds more .html than the listing shows (the src/ ' +
   'source is the difference)',
   onDisk.filter(n => n.endsWith('.html')).length +
   srcOnDisk.filter(n => n.endsWith('.html')).length > listed.length);
if (!listed.length || !target) { await b.close(); finish(); }
const name = listed[0];
const srcName = srcOnDisk.find(n => n.endsWith('.html'));
ok('the src/ source is NOT listed (non-recursive, the one builder trick)',
   !listed.includes(srcName));

/* ── the listing renders one row per artifact, each a real link ─────────── */
await p.goto(`${BASE}/research`, { waitUntil: 'networkidle' });
await sleep(900);
const rows = await p.evaluate(() =>
  [...document.querySelectorAll('#view [data-research]')].map(row => {
    const a = row.querySelector('a[href^="/research?p="]');
    return { key: row.dataset.research || null,
             href: a ? a.getAttribute('href') : null };
  }));
notes.push('rows: ' + JSON.stringify(rows));
ok('one row per served artifact, keyed by filename',
   rows.length === listed.length &&
   rows.every(r => r.key && listed.includes(r.key)));
ok('every row links its own /research?p= view (a real <a>: keyboard-operable, deep-linkable)',
   rows.every(r => r.href === '/research?p=' + encodeURIComponent(r.key)));

/* ── the real gesture: click a row, arrive on the artifact view ─────────── */
await p.evaluate(() => {
  window.__rt = [];
  document.addEventListener('transitionstart', e => {
    if (e.target && e.target.id === 'view') window.__rt.push(e.propertyName);
  });
});
await p.click(`#view [data-research="${name}"] a[href^="/research?p="]`);
await sleep(1600);
const arrived = await p.evaluate(() => {
  const f = document.getElementById('reviewframe');
  return {
    path: location.pathname,
    param: new URLSearchParams(location.search).get('p'),
    frame: !!f,
    src: f ? f.getAttribute('src') : null,
    wide: document.body.classList.contains('review'),
    transitions: window.__rt,
  };
});
notes.push('arrived: ' + JSON.stringify(arrived));
ok('the click navigated to /research with the artifact as key',
   arrived.path === '/research' && arrived.param === name);
ok('the view embeds the raw artifact (/researchraw) in the review idiom\'s iframe',
   arrived.frame && arrived.src === '/researchraw?p=' + encodeURIComponent(name));
ok('the doc half borrows the review wide column (body.review)',
   arrived.wide);
ok('the arrival used the existing route dissolve (transitionstart on #view)',
   arrived.transitions.includes('opacity') ||
   arrived.transitions.includes('transform'));
await p.screenshot({ path: `${OUT}/artifact.png`, fullPage: true });

/* the raw endpoint serves the artifact bytes the iframe asked for */
{
  const res = await fetch(`${BASE}/researchraw?p=${encodeURIComponent(name)}`);
  const body = await res.text();
  ok('/researchraw serves the artifact itself (200, real markup)',
     res.status === 200 && body.toLowerCase().includes('<html'));
}

/* ── the crumb back to the listing ──────────────────────────────────────── */
await p.click('#meta .crumb a[href="/research"]');
await sleep(1600);
const back = await p.evaluate(() => ({
  path: location.pathname, search: location.search,
  rows: document.querySelectorAll('#view [data-research]').length,
  wide: document.body.classList.contains('review'),
}));
notes.push('back: ' + JSON.stringify(back));
ok('the crumb returns to the bare listing (normal column, all rows)',
   back.path === '/research' && back.search === '' &&
   back.rows === listed.length && !back.wide);

/* ── confinement: no escape, no src/ source served as an artifact ───────── */
for (const bad of ['../questions.md', 'src/' + srcName, 'missing.html']) {
  const res = await fetch(`${BASE}/researchraw?p=${encodeURIComponent(bad)}`);
  ok(`/researchraw refuses ${bad} (404, never a source or an escape)`,
     res.status === 404);
}

/* ── reduced motion: same function, no dissolve ─────────────────────────── */
{
  await p.emulateMedia({ reducedMotion: 'reduce' });
  // A FRESH load, not a click from the previous phase: the dissolve's ghost
  // outlives its gesture by a ~400ms safety net, and sampling right after
  // the crumb navigation can meet the LAST ghost instead of proving no NEW
  // one was made. Full load under RM settles with no ghost at all.
  await p.goto(`${BASE}/research`, { waitUntil: 'networkidle' });
  await sleep(600);
  await p.evaluate(() => {
    window.__rt2 = [];
    document.addEventListener('transitionstart', e => {
      if (e.target && e.target.id === 'view') window.__rt2.push(e.propertyName);
    });
  });
  await p.click(`#view [data-research="${name}"] a[href^="/research?p="]`);
  await sleep(500);
  const rm = await p.evaluate(() => ({
    path: location.pathname,
    param: new URLSearchParams(location.search).get('p'),
    ghost: !!document.querySelector('.ghost'),
    enter: document.getElementById('view').classList.contains('enter'),
    transitions: window.__rt2,
    frame: !!document.getElementById('reviewframe'),
  }));
  notes.push('reduced-motion arrival: ' + JSON.stringify(rm));
  ok('reduced motion: the swap is instant (no ghost, no enter pose, no ' +
     'transition on #view) and the same artifact view is there',
     rm.path === '/research' && rm.param === name && !rm.ghost &&
     !rm.enter && rm.transitions.length === 0 && rm.frame);
}

ok('no page errors', errs.length === 0);
if (errs.length) notes.push('page errors: ' + errs.join(' | '));
await b.close();
finish();
