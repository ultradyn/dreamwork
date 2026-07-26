/* #266 — A review dock must submit to the question named by its URL/card, even
   after live data reorders questions_open. The bug needs all three facts:
   review DOM keeps its old positional data-qkey; tick() replaces in-memory
   data; submit resolves that stale key against the new order.

   Note and answer run in separate pages with separately intercepted endpoints:
   either path regressing must fail on its own request payload.
   usage: node docktarget.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const initial = await (await fetch(`${BASE}/data.json`)).json();
const original = initial.questions_open[0];
const review = initial.reviews[0];
if (!original || !review) throw new Error('fixture needs an open question and review');
const url = `${BASE}/review?p=${encodeURIComponent(review.name)}` +
            `&q=${encodeURIComponent(original.title)}`;

async function openPhase(mode) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url, { waitUntil: 'networkidle' });
  const shownBefore = await page.locator('#qdock .qt').first().textContent();
  let posted = null;
  await page.route(`**/${mode === 'note' ? 'comment' : 'answer'}`, async route => {
    posted = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  return { mode, page, errors, shownBefore, posted: () => posted };
}

// Both pages render A with o0 before the fixture changes. This keeps answer and
// note independent without letting either intercepted success mutate the server.
const phases = [await openPhase('note'), await openPhase('answer')];

// Insert another P1 ahead of the docked P1. Priority sorting keeps it first,
// shifting the original question from o0 to o1 without changing either route.
const questions = join(initial.target, '.dreamwork', 'questions.md');
const source = readFileSync(questions, 'utf8');
const injected = '- **P1 · 2026-07-26 — injected reorder sentinel.**\n' +
                 '  Exists only inside the #266 fixture run.\n\n';
writeFileSync(questions, source.replace('## Open\n\n', `## Open\n\n${injected}`));

const checks = [];
const ok = (name, value) => checks.push(`${value ? 'PASS' : 'FAIL'} ${name}`);
for (const phase of phases) {
  const { mode, page, errors, shownBefore } = phase;
  // Wait for tick() to replace lexical `data`; a server-side reorder alone is
  // insufficient and would let the guard pass without exercising the bug.
  await page.waitForFunction(title =>
    typeof data !== 'undefined' && data.questions_open[0].title !== title,
    original.title, { timeout: 7000 });
  const shownAfter = await page.locator('#qdock .qt').first().textContent();
  if (mode === 'note') await page.locator('#qdock .qmode[data-mode="note"]').click();
  const text = `stable ${mode} target sentinel`;
  await page.locator('#qdock textarea').fill(text);
  await page.locator('#qdock .qsend').click();
  for (let i = 0; i < 20 && !phase.posted(); i++) await page.waitForTimeout(25);
  const posted = phase.posted();
  ok(`${mode}: no page errors`, errors.length === 0);
  ok(`${mode}: dock visibly remains original after in-memory reorder`,
     shownBefore?.includes(original.title) && shownAfter?.includes(original.title));
  ok(`${mode}: request was made`, !!posted);
  ok(`${mode}: request targets visibly docked question after reorder (#266)`,
     posted?.question === original.title);
  ok(`${mode}: request carries exact text`,
     (mode === 'note' ? posted?.comment : posted?.answer) === text);
  console.log(`${mode}: original=${JSON.stringify(original.title)}`);
  console.log(`${mode}: posted=${JSON.stringify(posted?.question || null)}`);
}

console.log('----');
console.log(checks.join('\n'));
await browser.close();
process.exit(checks.some(line => line.startsWith('FAIL')) ? 1 : 0);
