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
const browserA = await chromium.launch();
const browserB = await chromium.launch();
const a = await browserA.newPage();
const questions = await browserB.newPage();
const review = await browserB.newPage({ viewport: { width: 1200, height: 900 } });
const errors = [];
for (const p of [a, questions, review]) p.on('pageerror', e => errors.push(String(e)));
await Promise.all([
  a.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
  questions.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
  review.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }),
]);
const fixtureData = await (await fetch(`${BASE}/data.json`)).json();
const title = fixtureData.questions_open.find(q => q.title.includes('bold title is hard-wrapped')).title;
await review.goto(`${BASE}/review?p=fixture-review.html&q=${encodeURIComponent(title)}`, { waitUntil: 'networkidle' });
// Let B's first poll establish lastMtime before A writes; otherwise the initial
// data fetch can race the write and defer observation by a whole extra period.
await Promise.all([questions.waitForFunction(() => lastMtime !== null), review.waitForFunction(() => lastMtime !== null)]);

// Seed every #269-compatible piece of human-owned composer state, plus iframe
// position. The live tick must replace the dock card without disturbing these.
const seeded = await review.evaluate(() => {
  const ta = document.querySelector('#qdock textarea');
  const frame = document.querySelector('iframe');
  ta.value = Array(12).fill('draft kept across remote note').join('\n');
  ta.style.height = '80px'; ta.scrollTop = 30;
  ta.focus(); ta.setSelectionRange(6, 10, 'forward');
  frame.contentWindow.scrollTo(0, 40);
  return { src: frame.src, frameY: frame.contentWindow.scrollY, scroll: ta.scrollTop };
});
await review.evaluate(() => { document.querySelector('#qdock .qa').dataset.guardOld = 'yes'; });
const response = await a.evaluate(async ({ title, marker }) => {
  const r = await fetch('/comment', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, comment: marker, section: 'Open' }) });
  return { ok: r.ok, body: await r.text() };
}, { title, marker });
ok('browser A wrote the note', response.ok);

async function sees(page, selector) {
  try { await page.waitForFunction(({ selector, marker }) =>
    document.querySelector(selector)?.textContent.includes(marker), { selector, marker }, { timeout: 3000 });
    return true;
  } catch { return false; }
}
const [controlSaw, dockSaw] = await Promise.all([
  sees(questions, '#view'), sees(review, '#qdock'),
]);
ok('browser B /questions control sees the note within 3s', controlSaw);
ok('browser B /review #qdock sees the same-target note without reload within 3s', dockSaw);

const preserved = await review.evaluate(() => {
  const ta = document.querySelector('#qdock textarea');
  const frame = document.querySelector('iframe');
  return { value: ta?.value, height: ta?.style.height, scroll: ta?.scrollTop,
    start: ta?.selectionStart, end: ta?.selectionEnd, dir: ta?.selectionDirection,
    focused: document.activeElement === ta, src: frame?.src,
    frameY: frame?.contentWindow.scrollY };
});
const newDock = await review.$('#qdock .qa');
const replaced = await review.evaluate(() => !document.querySelector('#qdock .qa')?.dataset.guardOld);
ok('the review dock card was genuinely rerendered', replaced);
ok('the dock stays on the same stable target', !!newDock &&
   (await review.locator('#qdock .qt').first().textContent()).includes(title));
ok('the iframe URL survives the tick', preserved.src === seeded.src);
ok('the iframe scroll survives the tick', preserved.frameY === seeded.frameY);
ok('the textarea draft survives', preserved.value === Array(12).fill('draft kept across remote note').join('\n'));
ok('the textarea selection survives', preserved.start === 6 && preserved.end === 10 && preserved.dir === 'forward');
ok('the textarea resize and scroll survive', preserved.height === '80px' && preserved.scroll === seeded.scroll);
ok('focus survives in the textarea', preserved.focused);
ok('no page errors', errors.length === 0);
console.log(checks.join('\n'));
await Promise.all([browserA.close(), browserB.close()]);
if (checks.some(x => x.startsWith('FAIL'))) process.exit(1);
