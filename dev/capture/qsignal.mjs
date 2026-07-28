/* qsignal — #472: a review-artifact link in a question WORKS.

   Own-server (await freePort(), IGNORE argv[3] — #461/#471). Builds a
   target from the capture fixture, plants a question carrying the #417
   markdown-link shape AND the preferred backticked shape, and asserts
   the discriminating half: the rendered <a class="rev"> href resolves
   to a real /reviewraw artifact (status 200, body present). An <a> that
   404s is the defect wearing a fix's clothes.

   #473 (updated-ago + event) is a later commit on the same guard file.

   usage: node qsignal.mjs <outdir>   (argv[3] accepted and ignored) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
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
          '/reviewraw fetch of the linked artifact (href must WORK)',
  traceWindow: 'static settle ~0.9s; no motion traced — links are not a gesture',
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
const planted = `# Questions for the human

## Open

- **${TITLE_MD}**
  Artifact: [\`${ART}\`](../review/${ART}) — the outlier shape that did
  not render as a link.

- **${TITLE_BT}**
  Artifact: \`.dreamwork/review/${ART}\` — the corpus-majority shape.

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

const links = await p.evaluate((titles) => {
  const out = {};
  for (const [key, title] of Object.entries(titles)) {
    const card = document.querySelector(`.qa[data-qid="${encodeURIComponent(title)}"]`);
    if (!card) { out[key] = { found: false }; continue; }
    const a = card.querySelector('a.rev');
    let p = null;
    if (a) {
      try { p = new URL(a.getAttribute('href'), location.origin).searchParams.get('p'); }
      catch (e) { p = null; }
    }
    out[key] = {
      found: true,
      hasA: !!a,
      href: a ? a.getAttribute('href') : null,
      p,
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

// DISCRIMINATING: the href WORKS — fetch /reviewraw and assert body.
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

ok('#472 no page errors', errs.length === 0);
if (errs.length) notes.push('  pageerrors: ' + errs.join(' | '));

await p.screenshot({ path: join(OUT, 'questions-links.png'), fullPage: true });
await b.close();
try { srv.kill(); } catch (e) {}

finish();
