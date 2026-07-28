/* #271 — a note written in one browser propagates to a second browser's
   review dock without reload. Two chromium.launch() calls are deliberate:
   this is the cross-browser path, not two pages sharing one browser process.
   usage: node noteprop.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
import { dockHeadline } from './dom.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39951';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: 'two chromium.launch() processes against /questions and /review, A ' +
          'posting /comment while B (normal + reduced-motion) observes #qdock',
  traceWindow: 'observers poll lastMtime then waitForFunction a 3s sees() window ' +
               'after A writes; 100ms settle; no motion traced',
});
const marker = `cross-browser note ${process.pid}`;

// Separate launch calls are the invariant under test: A writes, B observes.
let browserA, browserB;
try {
browserA = await chromium.launch();
browserB = await chromium.launch();
const a = await browserA.newPage();
const questions = await browserB.newPage();
const review = await browserB.newPage({ viewport: { width: 1200, height: 900 } });
const reduced = await browserB.newPage({ viewport: { width: 1200, height: 900 }, reducedMotion: 'reduce' });
const errors = [];
for (const p of [a, questions, review, reduced]) p.on('pageerror', e => errors.push(String(e)));
await Promise.all([
  a.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
  questions.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
  review.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
  reduced.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
]);
const fixtureData = await (await fetch(`${BASE}/data.json`)).json();
const title = fixtureData.questions_open.find(q => q.title.includes('bold title is hard-wrapped')).title;
await Promise.all([
  review.goto(`${BASE}/review?p=fixture-review.html&q=${encodeURIComponent(title)}`, { waitUntil: 'networkidle' }),
  reduced.goto(`${BASE}/review?p=fixture-review.html&q=${encodeURIComponent(title)}`, { waitUntil: 'networkidle' }),
]);
// Let B's first poll establish lastMtime before A writes; otherwise the initial
// data fetch can race the write and defer observation by a whole extra period.
await Promise.all([questions, review, reduced].map(p => p.waitForFunction(() => lastMtime !== null)));

// Seed every #269-compatible piece of human-owned composer state, plus iframe
// position. Both motion modes must replace the dock card without disturbing it.
async function seedReviewState(page) {
  return page.evaluate(() => {
    const ta = document.querySelector('#qdock textarea');
    const frame = document.querySelector('iframe');
    const card = document.querySelector('#qdock .qa');
    const details = document.querySelector('#qdock details');
    ta.value = Array(12).fill('draft kept across remote note').join('\n');
    ta.style.height = '80px'; ta.scrollTop = 30;
    if (details) details.open = !details.open;
    card.classList.add('guard-fold-state');
    card.dataset.guardOld = 'yes';
    ta.focus(); ta.setSelectionRange(6, 10, 'forward');
    frame.contentWindow.scrollTo(0, 40);
    return { src: frame.src, frameY: frame.contentWindow.scrollY, scroll: ta.scrollTop,
      detailsOpen: details?.open ?? null, cardClass: card.classList.contains('guard-fold-state') };
  });
}
const [seeded, reducedSeeded] = await Promise.all([
  seedReviewState(review), seedReviewState(reduced),
]);
const response = await a.evaluate(async ({ title, marker }) => {
  const r = await fetch('/comment', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, comment: marker, section: 'Open' }) });
  return { ok: r.ok, body: await r.text() };
}, { title, marker });
ok('normal iframe has a nonzero seeded scroll precondition', seeded.frameY > 0);
ok('reduced iframe has a nonzero seeded scroll precondition', reducedSeeded.frameY > 0);
ok('browser A wrote the note', response.ok);

async function sees(page, selector) {
  try { await page.waitForFunction(({ selector, marker }) =>
    document.querySelector(selector)?.textContent.includes(marker), { selector, marker }, { timeout: 3000 });
    return true;
  } catch { return false; }
}
const [controlSaw, dockSaw, reducedSaw] = await Promise.all([
  sees(questions, '#view'), sees(review, '#qdock'), sees(reduced, '#qdock'),
]);
ok('browser B /questions control sees the note within 3s', controlSaw);
ok('browser B /review #qdock sees the same-target note without reload within 3s', dockSaw);
ok('reduced-motion /review has functional propagation parity', reducedSaw);
await Promise.all([review.waitForTimeout(100), reduced.waitForTimeout(100)]);
async function checkPreservedReviewState(page, seeded, phase) {
  const preserved = await page.evaluate(() => {
    const ta = document.querySelector('#qdock textarea');
    const frame = document.querySelector('iframe');
    return { value: ta?.value, height: ta?.style.height, scroll: ta?.scrollTop,
      start: ta?.selectionStart, end: ta?.selectionEnd, dir: ta?.selectionDirection,
      focused: document.activeElement === ta, src: frame?.src,
      detailsOpen: document.querySelector('#qdock details')?.open ?? null,
      frameY: frame?.contentWindow.scrollY,
      replaced: !document.querySelector('#qdock .qa')?.dataset.guardOld };
  });
  // headline minus its live age -- see dom.mjs; #385's age broke the raw compare
  const target = await dockHeadline(page);
  ok(`${phase}: the review dock card was genuinely rerendered`, preserved.replaced);
  ok(`${phase}: the dock stays on the same stable target`, !!target && target.includes(title));
  ok(`${phase}: precondition -- the docked headline is non-empty`,
     typeof target === 'string' && target.length > 10);
  ok(`${phase}: the iframe URL survives the tick`, preserved.src === seeded.src);
  ok(`${phase}: the iframe scroll survives the tick`, preserved.frameY === seeded.frameY);
  ok(`${phase}: the dock disclosure/fold state survives`, preserved.detailsOpen === seeded.detailsOpen);
  ok(`${phase}: the dock fold fixture was non-default before replacement`, seeded.cardClass === true);
  ok(`${phase}: the textarea draft survives`,
     preserved.value === Array(12).fill('draft kept across remote note').join('\n'));
  ok(`${phase}: the textarea selection survives`,
     preserved.start === 6 && preserved.end === 10 && preserved.dir === 'forward');
  ok(`${phase}: the textarea resize and scroll survive`,
     preserved.height === '80px' && preserved.scroll === seeded.scroll);
  ok(`${phase}: focus survives in the textarea`, preserved.focused);
}
await checkPreservedReviewState(review, seeded, 'normal motion');
await checkPreservedReviewState(reduced, reducedSeeded, 'reduced motion');
ok('no page errors', errors.length === 0);
finish();
} finally {
  await Promise.allSettled([browserA?.close(), browserB?.close()]);
}
