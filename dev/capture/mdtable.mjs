/* mdtable — #525: GFM pipe tables in the /file rendered-markdown view.

   His report (third of the family after #521 quotes and #522 links):
     pipe tables fell through to plain paragraphs (raw `|` glyphs).

   Production lines each assertion binds (red-prove by injection + cp restore):
     (a) mdBlocks table kind + mdRender's `table.mdtable` branch
         (delete the table kind / render branch → no .mdtable element)
     (b) fence-before-pipes order in mdBlocks
         (table parsed inside a fence → pipe-looking fence lines become a table)
     (c) cell inline pipeline (inline(c) via linkifyMd)
         (skip inline on cells → [text](known) stays raw brackets)

   Fixture is planted into the shared target copy: a doc with a well-formed
   pipe table (header + delimiter + multi-row body, one cell holding a known
   markdown link), a fence holding pipe-looking lines, and a malformed ragged
   pair (header/delimiter column mismatch). Table column/row counts are
   DERIVED at runtime so a one-row fixture asserted present cannot go vacuous.

   Readiness (#507 class): plants land on disk, then the guard BOUNDED-POLLS
   /data.json until every planted path is visible in linkable_paths AND
   /filedata serves the fixture — never asserts a precondition against a
   stale closed set, and never navigates /file before the bytes are there.

   usage: node mdtable.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/file?p= on a planted .md: GFM pipe table renders as table.mdtable; ' +
          'cells run linkifyMd; fence wins over pipes; ragged header/delimiter ' +
          'degrades to prose (no half-render)',
  traceWindow: 'readiness poll of /data.json + /filedata until plants are ' +
               'visible (bounded ~8s), then static reads after ~0.4s settle; ' +
               'no motion (table styling is static — no state change)',
});

/* Bounded poll: plants must be VISIBLE to the server before any closed-set
   precondition. collect() walks the tree per /data.json request, but a
   plant→immediate-fetch race (and a wrong TARGET path) both present as a
   missing linkable entry — wait, then fail by name if it never appears. */
async function waitForLinkable(paths, { timeoutMs = 8000, everyMs = 100 } = {}) {
  const need = [...paths];
  const t0 = Date.now();
  let last = null, tries = 0;
  while (Date.now() - t0 < timeoutMs) {
    tries++;
    try {
      const d = await (await fetch(`${BASE}/data.json`)).json();
      last = d;
      const set = new Set(Array.isArray(d.linkable_paths) ? d.linkable_paths : []);
      if (need.every(p => set.has(p))) {
        notes.push(`readiness: linkable_paths saw all ${need.length} plants ` +
                   `after ${tries} tries / ${Date.now() - t0}ms`);
        return d;
      }
    } catch (e) {
      last = { err: String(e) };
    }
    await sleep(everyMs);
  }
  const set = new Set(Array.isArray(last?.linkable_paths) ? last.linkable_paths : []);
  const missing = need.filter(p => !set.has(p));
  throw new Error(
    `readiness: planted paths never appeared in data.linkable_paths within ` +
    `${timeoutMs}ms (${tries} tries). missing=[${missing.join(', ')}] ` +
    `target=${last?.target || '?'} — server is not serving the plant dir, ` +
    `or the plant never landed on disk`);
}

async function waitForFiledata(rel, { timeoutMs = 8000, everyMs = 100 } = {}) {
  const t0 = Date.now();
  let tries = 0, lastStatus = null;
  while (Date.now() - t0 < timeoutMs) {
    tries++;
    try {
      const res = await fetch(
        `${BASE}/filedata?p=${encodeURIComponent(rel)}`);
      lastStatus = res.status;
      if (res.ok) {
        const j = await res.json();
        if (j && typeof j.content === 'string' && j.content.length > 0) {
          notes.push(`readiness: /filedata served ${rel} ` +
                     `(${j.content.length}B) after ${tries} tries / ` +
                     `${Date.now() - t0}ms`);
          return j;
        }
      }
    } catch (e) {
      lastStatus = String(e);
    }
    await sleep(everyMs);
  }
  throw new Error(
    `readiness: /filedata never served ${rel} within ${timeoutMs}ms ` +
    `(${tries} tries, last=${lastStatus}) — plant missing or wrong target`);
}

/* ── plant the fixture ────────────────────────────────────────────────── */
const TARGET = join(OUT, '..', 'target');
const KNOWN = 'DREAMWORK.md';           // always present in the fixture
const PLANS_DIR = join(TARGET, '.dreamwork', 'docs', 'plans');
mkdirSync(PLANS_DIR, { recursive: true });

// well-formed table: MULTIPLE body rows so "one table of N rows" is
// load-bearing (a one-row fixture asserted present is the vacuous
// precondition the brief forbids). Derive counts at runtime below.
const TABLE_HEADER = '| Feature | Path | Notes |';
const TABLE_DELIM  = '|---------|------|-------|';
const TABLE_BODY = [
  '| prose reflow | `mdB` | hard wraps join |',
  `| link promote | [the contract](${KNOWN}) | closed set only |`,
  '| fence wins | pre.mdcode | pipes stay code |',
];
// A COMPLETE well-formed pipe table inside a fence — if fences lose, this
// becomes a real .mdtable with headers "fenced"/"not"/"a table". The marker
// phrase is the header row; the delimiter + body make it recognisable as a
// table by mdBlocks. Both halves of the fence-wins check bind this region.
const FENCE_PIPE_HEADER = '| fenced | not | a table |';
const FENCE_PIPE_DELIM  = '|--------|-----|---------|';
const FENCE_PIPE_BODY   = '| stay | as | code |';
const FENCE_PIPE_MARKER = 'fenced'; // distinctive text inside the fence
// ragged: 3-col header, 1-col delimiter — must degrade to prose
const RAGGED_HEADER = '| only | three | cols |';
const RAGGED_DELIM  = '|---|';  // one cell — column-count mismatch
const RAGGED_BODY   = '| x | y | z |';

const FIXTURE_PATH = '.dreamwork/docs/plans/mdtable-fixture.md';
const FIXTURE = [
  '# mdtable fixture — #525',
  '',
  'A well-formed GFM pipe table (header + delimiter + body):',
  '',
  TABLE_HEADER,
  TABLE_DELIM,
  ...TABLE_BODY,
  '',
  'A fence must win over pipes (the pipes are code, not a table):',
  '```',
  FENCE_PIPE_HEADER,
  FENCE_PIPE_DELIM,
  FENCE_PIPE_BODY,
  '```',
  '',
  'A malformed ragged pair must degrade to prose (no half-render):',
  '',
  RAGGED_HEADER,
  RAGGED_DELIM,
  RAGGED_BODY,
  '',
  'Trailing prose after the ragged attempt.',
  '',
].join('\n');
writeFileSync(join(TARGET, FIXTURE_PATH), FIXTURE);

const PLANTED_LINKABLE = [KNOWN, FIXTURE_PATH];

let d;
try {
  d = await waitForLinkable(PLANTED_LINKABLE);
  await waitForFiledata(FIXTURE_PATH);
  ok('readiness: planted paths visible in data.linkable_paths before asserts',
     true);
  ok('readiness: /filedata serves the planted fixture before /file navigate',
     true);
} catch (e) {
  notes.push(String(e.message || e));
  ok('readiness: planted paths visible in data.linkable_paths before asserts',
     false);
  ok('readiness: /filedata serves the planted fixture before /file navigate',
     false);
  finish();
  process.exit(1);
}

/* ── preconditions from the readiness-fresh data + fixture source ─────── */
const linkable = new Set(Array.isArray(d.linkable_paths) ? d.linkable_paths : []);
ok('precondition: server shipped a non-empty linkable_paths closed set',
   linkable.size > 0);
ok('precondition: known path is in the closed set',
   linkable.has(KNOWN));

// derive table shape from the planted source — never a one-row hope.
// Walk like mdBlocks: fences win; a well-formed header+matching-delim
// starts a table; count its body rows until a non-row.
function deriveTables(src) {
  const lines = src.split('\n');
  const tables = [];
  let inFence = false;
  const splitRow = line => {
    let s = line.trim();
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|')) s = s.slice(0, -1);
    return s.split('|').map(c => c.trim());
  };
  const isDelim = line => {
    const cells = splitRow(line);
    return cells.length >= 1 &&
      cells.every(c => /^:?-{1,}:?$/.test(c) && /-+/.test(c));
  };
  const looksRow = line => line.includes('|') && splitRow(line).length >= 2;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) { inFence = !inFence; continue; }
    if (inFence) continue;
    if (looksRow(line) && i + 1 < lines.length && isDelim(lines[i + 1])) {
      const header = splitRow(line);
      const delim = splitRow(lines[i + 1]);
      if (header.length === delim.length && header.length >= 2) {
        const rows = [];
        i += 2;
        while (i < lines.length && lines[i].trim() && looksRow(lines[i])) {
          rows.push(splitRow(lines[i]));
          i++;
        }
        i--;
        tables.push({ cols: header.length, rows: rows.length, header });
      }
    }
  }
  return tables;
}
const derived = deriveTables(FIXTURE);
notes.push(`derived well-formed tables outside fences: ${JSON.stringify(derived)}`);
ok('precondition: fixture has exactly one well-formed table outside fences',
   derived.length === 1);
ok('precondition: derived table has >= 2 columns (distinguishable from prose)',
   derived.length === 1 && derived[0].cols >= 2);
ok('precondition: derived table has >= 2 body rows (multi-row is load-bearing)',
   derived.length === 1 && derived[0].rows >= 2);
ok('precondition: derived body row count matches planted TABLE_BODY',
   derived.length === 1 && derived[0].rows === TABLE_BODY.length);
// fixture source must contain the fence marker AND the ragged pair so the
// checks that assert their ABSENCE as tables are not vacuous
ok('precondition: fixture source contains the fenced pipe table (header+delim)',
   FIXTURE.includes(FENCE_PIPE_HEADER) && FIXTURE.includes(FENCE_PIPE_DELIM));
ok('precondition: fixture source contains the ragged header+delim pair',
   FIXTURE.includes(RAGGED_HEADER) && FIXTURE.includes(RAGGED_DELIM));
// gap assertion: well-formed cols != ragged delim cols (the mismatch is why
// the ragged pair is not a table — a check tuned to today's fixture alone
// would not notice if both became 3-col)
const raggedDelimCols = (() => {
  let s = RAGGED_DELIM.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map(c => c.trim()).length;
})();
notes.push(`well-formed cols=${derived[0]?.cols} ragged-delim cols=${raggedDelimCols}`);
ok('precondition: ragged delimiter column count DIFFERS from well-formed header',
   derived.length === 1 && raggedDelimCols !== derived[0].cols);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

/* ── render via /file (binds the production functions) ───────────────── */
await p.goto(`${BASE}/file?p=${encodeURIComponent(FIXTURE_PATH)}`,
             { waitUntil: 'networkidle' });
try {
  await p.waitForSelector('#filebody .md', { timeout: 8000 });
} catch (e) {
  const body = await p.evaluate(() =>
    (document.getElementById('filebody') || document.getElementById('view') ||
     {}).textContent || '');
  notes.push('filebody after waitFor .md: ' + JSON.stringify(body.slice(0, 200)));
  ok('fixture rendered as .md at /file', false);
  await br.close();
  finish();
  process.exit(1);
}
await sleep(400);

const rendered = await p.evaluate(({ known, fenceMarker, raggedHeader }) => {
  const body = document.getElementById('filebody');
  if (!body) return { err: 'no #filebody' };
  const md = body.querySelector('.md');
  if (!md) return { err: 'no .md (rendered mode missing?)' };

  const hasData = !!(typeof data !== 'undefined' && data &&
                     Array.isArray(data.linkable_paths));
  const knownInData = hasData && data.linkable_paths.includes(known);

  const tables = [...md.querySelectorAll('table.mdtable')];
  const tableInfo = tables.map(t => {
    const ths = [...t.querySelectorAll('thead th')].map(
      th => (th.textContent || '').trim());
    const rows = [...t.querySelectorAll('tbody tr')].map(tr =>
      [...tr.querySelectorAll('td')].map(td => (td.textContent || '').trim()));
    const links = [...t.querySelectorAll('a')].map(a => ({
      href: a.getAttribute('href') || '',
      text: (a.textContent || '').trim(),
    }));
    const pips = [...t.querySelectorAll('.pipbtn')].map(b => ({
      url: b.getAttribute('data-pipurl') || '',
      label: b.getAttribute('data-piplabel') || '',
    }));
    return { ths, nRows: rows.length, rows, links, pips, html: t.outerHTML.slice(0, 400) };
  });

  // fence: a pre.mdcode whose text contains the fenced pipe marker word
  const fences = [...md.querySelectorAll('pre.mdcode')];
  const fenceWithPipes = fences.find(f =>
    (f.textContent || '').includes(fenceMarker));
  // if fences lose, the in-fence well-formed table becomes a .mdtable
  // whose headers are fenced / not / a table — that IS the fence-wins break.
  const tableHasFenceMarker = tables.some(t => {
    const ths = [...t.querySelectorAll('thead th')].map(
      th => (th.textContent || '').trim().toLowerCase());
    return ths.includes('fenced') && ths.includes('not') &&
           ths.some(h => h === 'a table' || h.includes('table'));
  });

  // ragged: the header words "only" "three" "cols" must NOT form a table
  // (they may appear as prose text). No table whose headers are that trio.
  const raggedAsTable = tables.some(t => {
    const ths = [...t.querySelectorAll('thead th')].map(
      th => (th.textContent || '').trim().toLowerCase());
    return ths.includes('only') && ths.includes('three') && ths.includes('cols');
  });
  // and the raw pipe glyphs of the ragged header should still be visible
  // as prose somewhere (degrade to prose keeps the pipes as text)
  const allText = md.textContent || '';
  // ragged header as prose may have been reflow-joined; look for distinctive words
  const raggedProseVisible =
    allText.includes('only') && allText.includes('three') && allText.includes('cols');

  // known link inside a table cell
  const pathOf = href => {
    if (!href.startsWith('/file?p=')) return null;
    try { return decodeURIComponent(href.slice(8)); } catch (e) { return null; }
  };
  const cellLinks = tables.flatMap(t =>
    [...t.querySelectorAll('a')].map(a => ({
      href: a.getAttribute('href') || '',
      text: (a.textContent || '').trim(),
    })));
  const knownCellLink = cellLinks.find(l => pathOf(l.href) === known);
  // bleed: `](DREAMWORK.md)` must not remain if the cell pipeline ran
  const cellBleed = tables.some(t =>
    (t.textContent || '').includes('](' + known + ')') ||
    (t.textContent || '').includes('](DREAMWORK.md)'));

  let tableStyle = null;
  if (tables[0]) {
    const td = tables[0].querySelector('td') || tables[0].querySelector('th');
    if (td) {
      const cs = getComputedStyle(td);
      tableStyle = {
        borderTopWidth: cs.borderTopWidth,
        borderTopStyle: cs.borderTopStyle,
        borderTopColor: cs.borderTopColor,
        fontVariantNumeric: cs.fontVariantNumeric,
      };
    }
  }

  return {
    nTables: tables.length,
    tableInfo,
    hasData,
    knownInData,
    fenceWithPipes: !!fenceWithPipes,
    fenceText: fenceWithPipes ? fenceWithPipes.textContent : null,
    tableHasFenceMarker,
    raggedAsTable,
    raggedProseVisible,
    knownCellLink: !!knownCellLink,
    knownCellHref: knownCellLink ? knownCellLink.href : null,
    cellBleed,
    tableStyle,
    allTextSlice: allText.slice(0, 600),
  };
}, {
  known: KNOWN,
  fenceMarker: FENCE_PIPE_MARKER,
  raggedHeader: RAGGED_HEADER,
});

notes.push('rendered: ' + JSON.stringify({
  nTables: rendered.nTables,
  tableInfo: rendered.tableInfo,
  fenceWithPipes: rendered.fenceWithPipes,
  tableHasFenceMarker: rendered.tableHasFenceMarker,
  raggedAsTable: rendered.raggedAsTable,
  knownCellLink: rendered.knownCellLink,
  cellBleed: rendered.cellBleed,
  tableStyle: rendered.tableStyle,
}, null, 0).slice(0, 1600));

ok('no page errors', errs.length === 0);
ok('fixture rendered as .md at /file', !rendered.err);
ok('precondition: page data.linkable_paths is loaded on /file (ensureData)',
   !!rendered.hasData);
ok('precondition: known path is in the page\'s closed set at render time',
   !!rendered.knownInData);

/* (a) well-formed table renders as table.mdtable — multi-row precondition
   already asserted; here the element must exist with the derived shape */
ok('exactly one table.mdtable for the well-formed fixture table',
   rendered.nTables === 1);
const t0 = rendered.tableInfo && rendered.tableInfo[0];
ok('table header column count matches derived cols',
   !!t0 && t0.ths.length === derived[0].cols);
ok('table body row count matches derived rows',
   !!t0 && t0.nRows === derived[0].rows);
ok('table header carries the planted Feature column',
   !!t0 && t0.ths.some(h => /feature/i.test(h)));
ok('table body carries the planted prose-reflow cell',
   !!t0 && t0.rows.some(r => r.some(c => /prose reflow/i.test(c))));

/* (b) fences still win over pipes */
ok('fence still holds the pipe-looking lines as code (pre.mdcode present)',
   rendered.fenceWithPipes === true);
ok('the fenced pipe region is NOT also a table',
   rendered.tableHasFenceMarker === false);

/* (c) cell inline pipeline — [text](known) promoted via linkifyMd */
ok('known-absolute [text](DREAMWORK.md) inside a cell is a real /file link',
   rendered.knownCellLink === true);
ok('cell known-absolute target is CONSUMED (no ](DREAMWORK.md) bleed)',
   rendered.cellBleed === false);

/* (d) malformed ragged pair degrades to prose */
ok('ragged header/delimiter is NOT rendered as a table',
   rendered.raggedAsTable === false);
ok('ragged header words still visible as prose (degrade, not drop)',
   rendered.raggedProseVisible === true);

/* static style: dim rules present, tabular-nums */
ok('table cells have a visible border (the dim rule)',
   rendered.tableStyle &&
   parseFloat(rendered.tableStyle.borderTopWidth) >= 1 &&
   rendered.tableStyle.borderTopStyle !== 'none');
ok('table uses tabular-nums (monospaced-numeric-friendly)',
   rendered.tableStyle &&
   /tabular-nums/.test(rendered.tableStyle.fontVariantNumeric || ''));

/* ── visual captures: desktop + 390px mobile ──────────────────────────── */
await p.goto(`${BASE}/file?p=${encodeURIComponent(FIXTURE_PATH)}`,
             { waitUntil: 'networkidle' });
await sleep(600);
await p.screenshot({ path: join(OUT, 'mdtable-desktop.png'), fullPage: true });
await p.setViewportSize({ width: 390, height: 844 });
await sleep(300);
await p.screenshot({ path: join(OUT, 'mdtable-mobile-390.png'), fullPage: true });
// also write to a stable screenshots path the lane can read_file
const SHOT_DIR = join(dirname(new URL(import.meta.url).pathname),
  '..', '..', 'screenshots', 'lane-525tables');
mkdirSync(SHOT_DIR, { recursive: true });
await p.setViewportSize({ width: 1100, height: 900 });
await sleep(200);
await p.screenshot({ path: join(SHOT_DIR, 'mdtable-desktop.png'), fullPage: true });
await p.setViewportSize({ width: 390, height: 844 });
await sleep(200);
await p.screenshot({ path: join(SHOT_DIR, 'mdtable-mobile-390.png'), fullPage: true });
notes.push('screenshots: ' + SHOT_DIR);

await br.close();
finish();
