/* #105 — ONE question component. Proves every surface that shows a question
   renders the SAME card: /questions (all three states), the dashboard, and
   the review dock. Structural equality is the assertion — same tag path,
   same class vocabulary, same footer — because "looks the same" is exactly
   what a shared component buys and what a fork would quietly lose.
   usage: node qacard.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

// the shape of a card, independent of its content — what a second
// implementation would drift on
const SHAPE = `(card) => ({
  cls: card.className,
  key: card.dataset.qkey || null,
  hasTitle: !!card.querySelector(':scope > .qt'),
  hasNoteBox: !!card.querySelector(':scope > .notewrap .notebox'),
  noteId: (card.querySelector(':scope > .notewrap .notebox') || {}).id || null,
  hasAnswerBox: !!card.querySelector(':scope > textarea[id^=qa]'),
  hasAnsTag: !!card.querySelector(':scope > .anstag'),
  order: [...card.children].map(c => c.className || c.tagName.toLowerCase())
})`;

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(900);
const qs = await p.evaluate(`[...document.querySelectorAll('.qa')].map(${SHAPE})`);
await p.screenshot({ path: `${OUT}/questions.png`, fullPage: true });

await p.goto(`${BASE}/`, { waitUntil: 'networkidle' }); await sleep(900);
const dash = await p.evaluate(`[...document.querySelectorAll('.qa')].map(${SHAPE})`);

// the review dock: deep-load /review with a question title so it docks
const title = await p.evaluate(async () => {
  const d = await (await fetch('/data.json')).json();
  const q = d.questions_open.find(x => !x.answer) || d.questions_open[0];
  return q ? q.title : null;
});
let dock = [];
if (title) {
  const rev = await p.evaluate(async () => (await (await fetch('/data.json')).json()).reviews[0]);
  if (rev) {
    await p.goto(`${BASE}/review?p=${encodeURIComponent(rev.name)}&q=${encodeURIComponent(title)}`,
                 { waitUntil: 'networkidle' });
    await sleep(900);
    dock = await p.evaluate(`[...document.querySelectorAll('#qdock .qa')].map(${SHAPE})`);
    await p.screenshot({ path: `${OUT}/review-dock.png`, fullPage: true });
  }
}

const byState = s => qs.filter(c => c.cls.includes(s));
const open = byState('open'), awaiting = byState('awaiting'), folded = byState('folded');
const sameShape = (a, b2) => JSON.stringify(a.order) === JSON.stringify(b2.order) &&
  a.hasTitle === b2.hasTitle && a.hasNoteBox === b2.hasNoteBox &&
  a.hasAnswerBox === b2.hasAnswerBox && a.cls === b2.cls;

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
ok('no page errors', errs.length === 0);
ok('all three states present on /questions',
   open.length > 0 && awaiting.length > 0 && folded.length > 0);
ok('every card is a .qa with a data-qkey', qs.every(c => c.key));
ok('every card carries a note box keyed to itself',
   qs.every(c => c.hasNoteBox && c.noteId === 'nb' + c.key));
ok('open cards (and only open cards) have an answer box',
   qs.every(c => c.hasAnswerBox === c.cls.includes('open')));
ok('awaiting cards (and only awaiting) show the answered tag',
   qs.every(c => c.hasAnsTag === c.cls.includes('awaiting')));
ok('folded entries are keyed a<n>, open/awaiting o<n>',
   folded.every(c => /^a\d+$/.test(c.key)) &&
   [...open, ...awaiting].every(c => /^o\d+$/.test(c.key)));
ok('dashboard renders the identical card as /questions',
   dash.length > 0 && dash.every(d => qs.some(q => sameShape(d, q))));
ok('the review dock renders the identical card as /questions',
   dock.length === 1 && qs.some(q => sameShape(dock[0], q)));

console.log('states: open=' + open.length + ' awaiting=' + awaiting.length +
            ' folded=' + folded.length + ' dash=' + dash.length +
            ' dock=' + dock.length);
if (dock[0]) console.log('dock: ' + JSON.stringify(dock[0]));
if (errs.length) console.log('errors: ' + errs.join(' | '));
console.log('----'); console.log(checks.join('\n'));
await b.close();
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
