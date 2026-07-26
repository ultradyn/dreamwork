/* #271 — a note written in one browser propagates to a second browser's
   review dock without reload. Two chromium.launch() calls are deliberate:
   this is the cross-browser path, not two pages sharing one browser process.
   usage: node noteprop.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39951';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
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
// position. The live tick must replace the dock card without disturbing these.
const seeded = await review.evaluate(() => {
  const ta = document.querySelector('#qdock textarea');
  const frame = document.querySelector('iframe');
  ta.value = Array(12).fill('draft kept across remote note').join('\n');
  ta.style.height = '80px'; ta.scrollTop = 30;
  const card = document.querySelector('#qdock .qa');
  const details = document.querySelector('#qdock details');
  if (details) details.open = !details.open;
  card.classList.add('guard-fold-state');
  ta.focus(); ta.setSelectionRange(6, 10, 'forward');
  frame.contentWindow.scrollTo(0, 40);
  return { src: frame.src, frameY: frame.contentWindow.scrollY, scroll: ta.scrollTop,
    detailsOpen: details?.open ?? null, cardClass: card.classList.contains('guard-fold-state') }; 
});
await review.evaluate(() => { document.querySelector('#qdock .qa').dataset.guardOld = 'yes'; });
const response = await a.evaluate(async ({ title, marker }) => {
  const r = await fetch('/comment', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, comment: marker, section: 'Open' }) });
  return { ok: r.ok, body: await r.text() };
}, { title, marker });
ok('iframe has a nonzero seeded scroll precondition', seeded.frameY > 0);
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

await review.waitForTimeout(100);
const preserved = await review.evaluate(() => {
  const ta = document.querySelector('#qdock textarea');
  const frame = document.querySelector('iframe');
  return { value: ta?.value, height: ta?.style.height, scroll: ta?.scrollTop,
    start: ta?.selectionStart, end: ta?.selectionEnd, dir: ta?.selectionDirection,
    focused: document.activeElement === ta, src: frame?.src,
    detailsOpen: document.querySelector('#qdock details')?.open ?? null,
    cardClass: document.querySelector('#qdock .qa')?.classList.contains('guard-fold-state'),
    frameY: frame?.contentWindow.scrollY }; 
});
const newDock = await review.$('#qdock .qa');
const replaced = await review.evaluate(() => !document.querySelector('#qdock .qa')?.dataset.guardOld);
ok('the review dock card was genuinely rerendered', replaced);
ok('the dock stays on the same stable target', !!newDock &&
   (await review.locator('#qdock .qt').first().textContent()).includes(title));
ok('the iframe URL survives the tick', preserved.src === seeded.src);
ok('the iframe scroll survives the tick', preserved.frameY === seeded.frameY);
ok('the dock disclosure state survives', preserved.detailsOpen === seeded.detailsOpen);
// The production snapshot intentionally owns semantic disclosure state, not
// arbitrary classes; this assertion keeps the fixture honest about replacement.
ok('the dock fold fixture is non-default before replacement', seeded.cardClass === true);
ok('the textarea draft survives', preserved.value === Array(12).fill('draft kept across remote note').join('\n'));
ok('the textarea selection survives', preserved.start === 6 && preserved.end === 10 && preserved.dir === 'forward');
ok('the textarea resize and scroll survive', preserved.height === '80px' && preserved.scroll === seeded.scroll);
ok('focus survives in the textarea', preserved.focused);
ok('no page errors', errors.length === 0);
console.log(checks.join('\n'));
if (checks.some(x => x.startsWith('FAIL'))) process.exitCode = 1;
} finally {
  await Promise.allSettled([browserA?.close(), browserB?.close()]);
}
