/* mdquote — #521 + #522: blockquotes and [text](target) markdown links.

   His report (07:41 screenshot on render-architecture.md):
     - `>` lines fell through to plain paragraphs (raw `>` glyphs)
     - ``[`path`](relative)`` half-rendered: text linkified, `](…)` bled

   Production lines each assertion binds (red-prove by injection + cp restore):
     (a/b) mdBlocks quote kind + mdRender's `blockquote.mdquote` branch
           (delete the quote kind / render branch → no .mdquote element)
     (c)   linkifyMd's known-internal promotion (return m early → `](` bleeds)
     (d)   linkifyMd's literal branch for unknown targets (promote always →
           unknown becomes a link)
     (e)   fence-before-quote order in mdBlocks (quote before fence → `>`
           inside a fence becomes a quote element)

   Fixture is planted into the shared target copy: a doc with multi-line
   quote, known-path md link, unknown-target md link, and a fence holding
   a `>` line. Quote line count and known path are DERIVED at runtime so a
   one-line fixture asserted present cannot go vacuous.

   Readiness (#507 class): plants land on disk, then the guard BOUNDED-POLLS
   /data.json until every planted path is visible in linkable_paths AND
   /filedata serves the fixture — never asserts a precondition against a
   stale closed set, and never navigates /file before the bytes are there.

   usage: node mdquote.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';

const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/file?p= on a planted .md: blockquote renders as .mdquote with ' +
          'zero `>` glyphs; [text](known) consumed; [text](unknown) fully ' +
          'literal; fence wins over `>`; relative targets resolve via base',
  traceWindow: 'readiness poll of /data.json + /filedata until plants are ' +
               'visible (bounded ~8s), then static reads after ~0.4s settle; ' +
               'no motion (quote styling is static — no state change)',
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

/* Bounded poll: /filedata must serve the planted fixture before /file is
   navigated. A 404 here is the same race as a missing linkable entry. */
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

/* ── plant the fixture ──────────────────────────────────────────────────
   Known path must be a real file in the target so it lands in
   data.linkable_paths. The shared fixture always has DREAMWORK.md and
   .dreamwork/lessons.md; we also plant a nested doc so relative resolution
   from plans/ can be exercised the way his corpus does. */
const TARGET = join(OUT, '..', 'target');
const KNOWN = 'DREAMWORK.md';           // always present in the fixture
const UNKNOWN = 'nosuch/vanished-quote.md';
const PLANS_DIR = join(TARGET, '.dreamwork', 'docs', 'plans');
mkdirSync(PLANS_DIR, { recursive: true });
mkdirSync(join(TARGET, '.dreamwork', 'docs', 'briefs'), { recursive: true });
// a real brief the relative link can resolve to
const BRIEF_REL = '.dreamwork/docs/briefs/mdquote-target.md';
writeFileSync(join(TARGET, BRIEF_REL),
  '# mdquote target\n\na real file so linkable_paths admits it.\n');
// corpus render-architecture.md also links these — plant stubs so relative
// resolution into the closed set is what the page exercises (not a 404).
for (const stub of [
  '.dreamwork/docs/briefs/505-render-architecture.md',
  'transitions.md',
  '.dreamwork/handoffs.md',
]) {
  const sp = join(TARGET, stub);
  mkdirSync(dirname(sp), { recursive: true });
  if (!existsSync(sp)) writeFileSync(sp, `# stub ${stub}\n`);
}

// quote block: MULTIPLE consecutive `>` lines so "one block" is load-bearing
// (a one-line fixture asserted present is the vacuous precondition the brief
// forbids). Derive the source line count at runtime below.
const QUOTE_LINES = [
  '> re the reset when data.json is recieved selecting text from any of the',
  '> questions deselects on update. selecting quesitons at the top or the',
  '> project name works fine could we use ids on html elements to avoid this',
];
const FIXTURE_PATH = '.dreamwork/docs/plans/mdquote-fixture.md';
const FIXTURE = [
  '# mdquote fixture — #521 + #522',
  '',
  'Lane-owns and a known path for absolute promotion:',
  `[the dreamwork contract](${KNOWN}) sits at the root.`,
  '',
  'A corpus-shaped relative link with backticked label:',
  `[\`${BRIEF_REL}\`](../../docs/briefs/mdquote-target.md).`,
  '',
  'An unknown-target markdown link must stay fully literal:',
  `[ghost path](${UNKNOWN}).`,
  '',
  'His words, as a multi-line quote:',
  ...QUOTE_LINES,
  '',
  'A fence must win over `>` (the `>` is code, not a quote):',
  '```',
  '> this is code not a quote',
  'const x = 1;',
  '```',
  '',
  'Trailing prose after the fence.',
  '',
].join('\n');
writeFileSync(join(TARGET, FIXTURE_PATH), FIXTURE);

// also copy the exact doc from his screenshot when present in the repo the
// guard is running from (acceptance: fixes visible on that corpus shape)
const REPO_ROOT = join(dirname(new URL(import.meta.url).pathname), '..', '..');
const REPO_DOC = join(REPO_ROOT, '.dreamwork', 'docs', 'plans',
                      'render-architecture.md');
if (existsSync(REPO_DOC)) {
  try {
    copyFileSync(REPO_DOC, join(PLANS_DIR, 'render-architecture.md'));
    notes.push('planted render-architecture.md from repo for corpus check');
  } catch (e) {
    notes.push('render-architecture copy skipped: ' + e.message);
  }
}

/* ── readiness: plants must be visible to the server before any assert ──
   Paths the closed set must admit after the plant (known fixture file is
   always there; the rest are what THIS guard wrote). Poll, don't hope. */
const PLANTED_LINKABLE = [KNOWN, BRIEF_REL, FIXTURE_PATH];

let d;
try {
  d = await waitForLinkable(PLANTED_LINKABLE);
  await waitForFiledata(FIXTURE_PATH);
  if (existsSync(join(TARGET, '.dreamwork/docs/plans/render-architecture.md')))
    await waitForFiledata('.dreamwork/docs/plans/render-architecture.md');
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
  // still finish with named FAILs rather than a crash-sentinel
  finish();
  process.exit(1);
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions from the readiness-fresh data + fixture source ─────── */
const linkable = new Set(Array.isArray(d.linkable_paths) ? d.linkable_paths : []);
ok('precondition: server shipped a non-empty linkable_paths closed set',
   linkable.size > 0);
ok('precondition: known path is in the closed set',
   linkable.has(KNOWN));
ok('precondition: brief target is in the closed set (relative resolve)',
   linkable.has(BRIEF_REL));
ok('precondition: unknown path is absent from the closed set',
   !linkable.has(UNKNOWN));

// derive quote line count from the planted source — never a one-line hope
let inFence = false, derivedQuoteLines = 0;
for (const line of FIXTURE.split('\n')) {
  if (/^\s*```/.test(line)) { inFence = !inFence; continue; }
  if (!inFence && /^>\s?/.test(line)) derivedQuoteLines++;
}
notes.push(`derived quote source lines outside fences: ${derivedQuoteLines}`);
ok('precondition: fixture has multi-line quote (derived count >= 2)',
   derivedQuoteLines >= 2);
ok('precondition: derived quote count matches the planted QUOTE_LINES',
   derivedQuoteLines === QUOTE_LINES.length);

/* ── render via mdB on known input (binds the production functions) ───── */
await p.goto(`${BASE}/file?p=${encodeURIComponent(FIXTURE_PATH)}`,
             { waitUntil: 'networkidle' });
// readiness already proved /filedata; now wait for the rendered pane (not
// "not found"). Swallowing a timeout here is what made a 404 look like a
// missing .md assertion with no cause — fail loud if it never arrives.
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

const rendered = await p.evaluate(({ known, unknown, brief }) => {
  const body = document.getElementById('filebody');
  if (!body) return { err: 'no #filebody' };
  const md = body.querySelector('.md');
  if (!md) return { err: 'no .md (rendered mode missing?)' };

  // data must be loaded for link promotion (#522 / ensureData on file view)
  const hasData = !!(typeof data !== 'undefined' && data &&
                     Array.isArray(data.linkable_paths));
  const knownInData = hasData && data.linkable_paths.includes(known);
  const briefInData = hasData && data.linkable_paths.includes(brief);

  const quotes = [...md.querySelectorAll('blockquote.mdquote')];
  const quoteText = quotes.map(q => q.textContent || '').join('\n');
  // literal `>` glyphs in the rendered quote text — must be ZERO
  const gtInQuotes = (quoteText.match(/>/g) || []).length;
  const gtGlyphs = quotes.reduce((n, q) =>
    n + ((q.textContent || '').match(/>/g) || []).length, 0);

  const allText = md.textContent || '';
  const links = [...md.querySelectorAll('a')].map(a => ({
    href: a.getAttribute('href') || '',
    text: (a.textContent || '').trim(),
  }));
  const pips = [...md.querySelectorAll('.pipbtn')].map(b => ({
    url: b.getAttribute('data-pipurl') || '',
    label: b.getAttribute('data-piplabel') || '',
  }));
  const pathOf = href => {
    if (!href.startsWith('/file?p=')) return null;
    try { return decodeURIComponent(href.slice(8)); } catch (e) { return null; }
  };
  const knownLink = links.find(l => pathOf(l.href) === known);
  const knownPip = pips.find(b => pathOf(b.url) === known || b.label === known);
  const briefLink = links.find(l => pathOf(l.href) === brief);
  // unknown: the literal form remains; no /file link to the unknown path
  const unkLink = links.find(l =>
    l.text === 'ghost path' || pathOf(l.href) === unknown);
  const unkLiteral = allText.includes('](' + unknown + ')') ||
                     allText.includes('](' + unknown);
  // fence: a pre.mdcode whose text contains `> this is code`
  const fences = [...md.querySelectorAll('pre.mdcode')];
  const fenceWithGt = fences.find(f =>
    (f.textContent || '').includes('> this is code not a quote'));
  const quoteHasCodeGt = quotes.some(q =>
    (q.textContent || '').includes('this is code not a quote'));

  let quoteStyle = null;
  if (quotes[0]) {
    const cs = getComputedStyle(quotes[0]);
    quoteStyle = {
      color: cs.color,
      borderLeftWidth: cs.borderLeftWidth,
      borderLeftStyle: cs.borderLeftStyle,
    };
  }

  return {
    nQuotes: quotes.length,
    quoteText,
    gtInQuotes,
    gtGlyphs,
    hasData,
    knownInData,
    briefInData,
    knownLink: !!knownLink,
    knownHref: knownLink ? knownLink.href : null,
    knownPip: !!knownPip,
    briefLink: !!briefLink,
    briefHref: briefLink ? briefLink.href : null,
    links,
    unkLink: !!unkLink,
    unkLiteral,
    fenceWithGt: !!fenceWithGt,
    fenceText: fenceWithGt ? fenceWithGt.textContent : null,
    quoteHasCodeGt,
    quoteStyle,
    quoteTextLen: quoteText.length,
  };
}, { known: KNOWN, unknown: UNKNOWN, brief: BRIEF_REL });

notes.push('rendered: ' + JSON.stringify(rendered, null, 0).slice(0, 1200));

ok('no page errors', errs.length === 0);
ok('fixture rendered as .md at /file', !rendered.err);
ok('precondition: page data.linkable_paths is loaded on /file (ensureData)',
   !!rendered.hasData);
ok('precondition: known path is in the page\'s closed set at render time',
   !!rendered.knownInData);
ok('precondition: brief path is in the page\'s closed set at render time',
   !!rendered.briefInData);

/* (a) a fixture quote renders as the quote element — multi-line precondition
   already asserted; here the element must exist and carry the joined text */
ok('quote renders as blockquote.mdquote (one block for consecutive > lines)',
   rendered.nQuotes === 1);
ok('quote element carries the fixture quote prose (joined reflow)',
   !!rendered.quoteText &&
   QUOTE_LINES.every(l => {
     const body = l.replace(/^>\s?/, '').trim();
     // each source line's content appears in the joined quote
     // (first few words are enough; full join may reflow punctuation)
     const head = body.split(/\s+/).slice(0, 4).join(' ');
     return rendered.quoteText.includes(head);
   }));

/* (b) literal `>` glyph count in the rendered quote is ZERO */
ok('literal > glyph count in rendered quote is ZERO',
   rendered.gtInQuotes === 0 && rendered.gtGlyphs === 0);

/* (c) [text](known-path) consumed — no `](` bleed for the known/relative */
ok('known-absolute [text](DREAMWORK.md) is a real /file link',
   rendered.knownLink === true);
ok('known-absolute md link carries a pip (#506 idiom)',
   rendered.knownPip === true);
ok('relative [text](../../briefs/…) resolved into the closed set and linked',
   rendered.briefLink === true);
// the promoted known + relative must not leave `](known` or `](../../` tails;
// unknown still has `](` by design (fully literal) — so check specifically
const bodyText = await p.evaluate(() =>
  (document.querySelector('#filebody .md') || {}).textContent || '');
ok('known-absolute target is CONSUMED (no ](DREAMWORK.md) tail)',
   !bodyText.includes('](' + KNOWN + ')') && !bodyText.includes('](DREAMWORK.md)'));
ok('relative target is CONSUMED (no ](../../docs/briefs/…) tail)',
   !bodyText.includes('](../../docs/briefs/mdquote-target.md)'));

/* (d) unknown-target markdown link stays fully literal */
ok('unknown-target md link is NOT promoted to a /file <a>',
   rendered.unkLink === false);
ok('unknown-target md link stays fully literal (brackets + target visible)',
   rendered.unkLiteral === true);

/* (e) fences still win over `>` */
ok('fence still holds the > line as code (pre.mdcode present)',
   rendered.fenceWithGt === true);
ok('the fenced > line is NOT also a blockquote',
   rendered.quoteHasCodeGt === false);

/* static style: left rule present, no animation claim */
ok('quote has a visible left border (the quiet rule)',
   rendered.quoteStyle &&
   parseFloat(rendered.quoteStyle.borderLeftWidth) >= 1 &&
   rendered.quoteStyle.borderLeftStyle !== 'none');

/* ── corpus doc from his screenshot, when planted ─────────────────────── */
const CORPUS_PATH = '.dreamwork/docs/plans/render-architecture.md';
if (existsSync(join(TARGET, CORPUS_PATH))) {
  await p.goto(`${BASE}/file?p=${encodeURIComponent(CORPUS_PATH)}`,
    { waitUntil: 'networkidle' });
  try {
    await p.waitForSelector('#filebody .md', { timeout: 8000 });
  } catch (e) {
    notes.push('corpus: #filebody .md never arrived');
  }
  await sleep(400);
  const corpus = await p.evaluate(() => {
    const md = document.querySelector('#filebody .md');
    if (!md) return { err: 'no .md' };
    const quotes = [...md.querySelectorAll('blockquote.mdquote')];
    const text = md.textContent || '';
    return {
      nQuotes: quotes.length,
      gtInQuotes: quotes.reduce((n, q) =>
        n + ((q.textContent || '').match(/>/g) || []).length, 0),
      hasResetProse: quotes.some(q =>
        /reset when data\.json/i.test(q.textContent || '')),
      bleedBrief: text.includes('](../../docs/briefs/'),
      bleedTransitions: text.includes('](../../../../transitions.md)'),
    };
  });
  notes.push('corpus: ' + JSON.stringify(corpus));
  ok('corpus render-architecture.md: quote block present',
     !corpus.err && corpus.nQuotes >= 1 && corpus.hasResetProse);
  ok('corpus: zero > glyphs inside quotes',
     !corpus.err && corpus.gtInQuotes === 0);
  ok('corpus: relative brief link consumed (no ](../../docs/briefs/ bleed)',
     !corpus.err && corpus.bleedBrief === false);
}

/* ── visual captures: desktop + 390px mobile ──────────────────────────── */
await p.goto(`${BASE}/file?p=${encodeURIComponent(FIXTURE_PATH)}`,
             { waitUntil: 'networkidle' });
await sleep(600);
await p.screenshot({ path: join(OUT, 'mdquote-desktop.png'), fullPage: true });
await p.setViewportSize({ width: 390, height: 844 });
await sleep(300);
await p.screenshot({ path: join(OUT, 'mdquote-mobile-390.png'), fullPage: true });
// also write to a stable screenshots path the lane can read_file
const SHOT_DIR = join(dirname(new URL(import.meta.url).pathname),
  '..', '..', 'screenshots', 'lane-521md');
mkdirSync(SHOT_DIR, { recursive: true });
await p.setViewportSize({ width: 1100, height: 900 });
await sleep(200);
await p.screenshot({ path: join(SHOT_DIR, 'mdquote-desktop.png'), fullPage: true });
await p.setViewportSize({ width: 390, height: 844 });
await sleep(200);
await p.screenshot({ path: join(SHOT_DIR, 'mdquote-mobile-390.png'), fullPage: true });
notes.push('screenshots: ' + SHOT_DIR);

await br.close();
finish();
