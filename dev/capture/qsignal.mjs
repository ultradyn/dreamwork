/* qsignal — #472 + #473: review-artifact links WORK, and a question that
   changed says so.

   Own-server (await freePort(), IGNORE argv[3] — #461/#471). Builds a
   target from the capture fixture.

   #472: plants a question carrying the #417 markdown-link shape AND the
   preferred backticked shape; asserts the discriminating half — the
   rendered <a class="rev"> href resolves to a real /reviewraw artifact
   (status 200, body present). An <a> that 404s is the defect wearing a
   fix's clothes.

   #473: plants an entry, forces a content change after first collect,
   asserts an updated-ago node appears with a runtime-derived create≠update
   gap, and that a best-effort question-updated line lands in
   watch-events.log (channel is lossy by design — the log assert is "when
   the store can write, the event is there"; the display half is the
   reliable deliverable). Digit flips are pure text (ages()); the NODE's
   first appearance is an arrival — reduced-motion settles fully lit.

   usage: node qsignal.mjs <outdir>   (argv[3] accepted and ignored) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2] || '.';
// #461/#471: own-server guards take freePort() and IGNORE argv[3].
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/questions with planted md-link + backtick review shapes; ' +
          '/reviewraw fetch; #473 updated-ago after per-entry rewrite + ' +
          'watch-events.log (best-effort)',
  traceWindow: 'static settle + one forced rewrite + reload; updated-ago ' +
               'arrival is an enter-snap (.dreamin), digit flips are pure text',
});

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });

const ART = 'qsignal-probe.html';
const ART_BODY = '<!doctype html><title>qsignal probe</title><p id="marker">probe-body-qsignal</p>';
const reviewDir = join(DIR, '.dreamwork', 'review');
mkdirSync(reviewDir, { recursive: true });
writeFileSync(join(reviewDir, ART), ART_BODY);

const QPATH = join(DIR, '.dreamwork', 'questions.md');
const TITLE_MD = '2026-07-29 — qsignal markdown-link probe';
const TITLE_BT = '2026-07-29 — qsignal backtick-link probe';
const TITLE_UP = '2026-07-01 — qsignal update-signal probe';
const ORIG_BODY = 'First body of the update probe. It will be rewritten after the first collect so the entry content digest changes.';
const planted = `# Questions for the human

## Open

- **${TITLE_MD}**
  Artifact: [\`${ART}\`](../review/${ART}) — the outlier shape that did
  not render as a link.

- **${TITLE_BT}**
  Artifact: \`.dreamwork/review/${ART}\` — the corpus-majority shape.

- **${TITLE_UP}**
  ${ORIG_BODY}

## Answered

`;
writeFileSync(QPATH, planted);

const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 900 } });
const errs = [];
p.on('pageerror', e => errs.push(String(e)));

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(900);

// ── #472 ────────────────────────────────────────────────────────────────
const links = await p.evaluate((titles) => {
  const out = {};
  for (const [key, title] of Object.entries(titles)) {
    const card = document.querySelector(`.qa[data-qid="${encodeURIComponent(title)}"]`);
    if (!card) { out[key] = { found: false }; continue; }
    const a = card.querySelector('a.rev');
    let pp = null;
    if (a) {
      try { pp = new URL(a.getAttribute('href'), location.origin).searchParams.get('p'); }
      catch (e) { pp = null; }
    }
    out[key] = {
      found: true,
      hasA: !!a,
      href: a ? a.getAttribute('href') : null,
      p: pp,
      rawBrackets: /\]\(/.test(card.innerHTML),
      relativeLeak: (card.innerHTML || '').includes('../review/'),
    };
  }
  return out;
}, { md: TITLE_MD, bt: TITLE_BT });

notes.push('  links: ' + JSON.stringify(links));

ok('#472 precondition: markdown-shape card is on /questions', !!links.md?.found);
ok('#472 precondition: backtick-shape card is on /questions', !!links.bt?.found);
ok('#472 md-shape renders <a class="rev">', !!links.md?.hasA);
ok('#472 bt-shape renders <a class="rev">', !!links.bt?.hasA);
ok('#472 md-shape p= is the artifact basename', links.md?.p === ART);
ok('#472 bt-shape p= is the artifact basename', links.bt?.p === ART);
ok('#472 md-shape leaves no raw ]( markdown', links.md && !links.md.rawBrackets);
ok('#472 md-shape does not leak ../review/ as a navigable path',
   links.md && !links.md.relativeLeak);

let rawStatus = 0, rawBody = '';
try {
  const res = await fetch(`${BASE}/reviewraw?p=${encodeURIComponent(ART)}`);
  rawStatus = res.status;
  rawBody = await res.text();
} catch (e) {
  notes.push('  reviewraw fetch threw: ' + e);
}
ok('#472 /reviewraw serves the linked artifact (status 200)', rawStatus === 200);
ok('#472 /reviewraw body is the planted artifact',
   rawBody.includes('probe-body-qsignal'));

let revStatus = 0;
try {
  const res = await fetch(`${BASE}/review?p=${encodeURIComponent(ART)}`);
  revStatus = res.status;
} catch (e) { /* */ }
ok('#472 /review shell serves for the linked artifact', revStatus === 200);

await p.screenshot({ path: join(OUT, 'questions-links.png'), fullPage: true });

// ── #473 ────────────────────────────────────────────────────────────────
const before = await p.evaluate((title) => {
  const card = document.querySelector(`.qa[data-qid="${encodeURIComponent(title)}"]`);
  if (!card) return { found: false };
  const up = card.querySelector('.age.qup[data-ut]');
  return {
    found: true,
    hasUpdated: !!(up && !up.hidden && (up.textContent || '').trim()),
    hasNode: !!up,
  };
}, TITLE_UP);
notes.push('  before-update: ' + JSON.stringify(before));
ok('#473 precondition: update-probe card is present', !!before.found);
ok('#473 precondition: no updated-ago on first sight of unchanged entry',
   before.found && !before.hasUpdated);

// Force a per-entry content change (not a neighbour rewrite).
const nowQ = readFileSync(QPATH, 'utf8');
const rewritten = nowQ.replace(
  ORIG_BODY,
  'REWRITTEN body of the update probe — a real per-entry change, not a neighbour answer. ' + Date.now()
);
ok('#473 precondition: planted body found for rewrite', rewritten !== nowQ);
writeFileSync(QPATH, rewritten);

// Hard reload so collect() re-reads and stamps updated_at (and the store
// is durable across the process that already first-sighted the entry).
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1000);

const after = await p.evaluate((title) => {
  const card = document.querySelector(`.qa[data-qid="${encodeURIComponent(title)}"]`);
  if (!card) return { found: false };
  const up = card.querySelector('.age.qup[data-ut]');
  const age = card.querySelector('.age.qage[data-ct]');
  return {
    found: true,
    hasUt: !!up,
    ut: up ? up.dataset.ut : null,
    upText: up ? (up.textContent || '') : '',
    upHidden: up ? !!up.hidden : true,
    ageText: age ? (age.textContent || '') : '',
    ct: age ? age.dataset.ct : null,
    hasDreamin: up ? up.classList.contains('dreamin') : false,
  };
}, TITLE_UP);
notes.push('  after-update: ' + JSON.stringify(after));

// Runtime-derived gap: updated_at later than title-date ct by more than 1s,
// and the painted text names "updated". Never a fixture-literal threshold.
const ut = parseFloat(after.ut || 0);
const ct = parseFloat(after.ct || 0);
const gapSec = ut - ct;
notes.push(`  gap sec (ut-ct): ${gapSec}`);
ok('#473 runtime gap: updated_at later than created ct by >1s',
   after.found && after.hasUt && gapSec > 1);
ok('#473 updated-ago appears after a real per-entry content change',
   after.found && after.hasUt && !after.upHidden && /updated/i.test(after.upText));

// Event channel: best-effort. When the store could write, the line is there.
const logPath = join(DIR, '.dreamwork', 'watch-events.log');
const logText = existsSync(logPath) ? readFileSync(logPath, 'utf8') : '';
notes.push('  events log: ' + logText.trim().slice(0, 200));
ok('#473 best-effort event: question-updated in watch-events.log ' +
   '(lossy by design; asserts the write path when the store can write)',
   /question-updated/.test(logText));

// Reduced-motion parity: function present, no start pose on a fresh load.
const ctxRM = await b.newContext({
  viewport: { width: 1100, height: 900 },
  reducedMotion: 'reduce',
});
const pRM = await ctxRM.newPage();
await pRM.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(700);
const rm = await pRM.evaluate((title) => {
  const card = document.querySelector(`.qa[data-qid="${encodeURIComponent(title)}"]`);
  if (!card) return { found: false };
  const up = card.querySelector('.age.qup[data-ut]');
  return {
    found: true,
    text: up ? (up.textContent || '') : '',
    hidden: up ? !!up.hidden : true,
    dreamin: up ? up.classList.contains('dreamin') : false,
  };
}, TITLE_UP);
notes.push('  reduced-motion: ' + JSON.stringify(rm));
ok('#473 reduced-motion: updated-ago still present (function, not timing)',
   rm.found && !rm.hidden && /updated/i.test(rm.text));
ok('#473 reduced-motion: no stuck .dreamin pose on settled content',
   rm.found && !rm.dreamin);
await ctxRM.close();

ok('#472/#473 no page errors', errs.length === 0);
if (errs.length) notes.push('  pageerrors: ' + errs.join(' | '));

await p.screenshot({ path: join(OUT, 'questions-updated.png'), fullPage: true });
await b.close();
try { srv.kill(); } catch (e) {}

finish();
