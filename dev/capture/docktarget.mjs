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
import { makeReporter } from './report.mjs';
import { dockHeadlineParts } from './dom.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/review docked on one open question, note + answer each intercepted ' +
          'at their own endpoint, then a P1 planted ahead of it in questions.md',
  traceWindow: 'two dock pages held across a 7s waitForFunction for the tick that ' +
               'replaces lexical data; no motion traced',
});

const browser = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const initial = await (await fetch(`${BASE}/data.json`)).json();
const original = initial.questions_open[0];
const review = initial.reviews[0];
if (!original || !review) {
  ok('fixture provides an open question and a review', false);
  notes.push('fixture needs an open question and review');
  await browser.close(); finish(); process.exit(1);
}
const url = `${BASE}/review?p=${encodeURIComponent(review.name)}` +
            `&q=${encodeURIComponent(original.title)}`;

async function openPhase(mode) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url, { waitUntil: 'networkidle' });
  const before = await dockHeadlineParts(page);
  const shownBefore = before.stable;
  let posted = null;
  await page.route(`**/${mode === 'note' ? 'comment' : 'answer'}`, async route => {
    posted = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  return { mode, page, errors, before, shownBefore, posted: () => posted };
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

for (const phase of phases) {
  const { mode, page, errors, before, shownBefore } = phase;
  // Wait for tick() to replace lexical `data`; a server-side reorder alone is
  // insufficient and would let the guard pass without exercising the bug.
  await page.waitForFunction(title =>
    typeof data !== 'undefined' && data.questions_open[0].title !== title,
    original.title, { timeout: 7000 });
  const after = await dockHeadlineParts(page);
  const shownAfter = after.stable;
  if (mode === 'note') await page.locator('#qdock .qmode[data-mode="note"]').click();
  const text = `stable ${mode} target sentinel`;
  await page.locator('#qdock textarea').fill(text);
  await page.locator('#qdock .qsend').click();
  for (let i = 0; i < 20 && !phase.posted(); i++) await page.waitForTimeout(25);
  const posted = phase.posted();
  ok(`${mode}: no page errors`, errors.length === 0);
  // #385 put a live age INSIDE this headline, so the raw title is no longer a
  // contiguous substring of `.qt`'s textContent -- `dockHeadline` strips the
  // age node and asks the identity question of the stable part. The check the
  // #266 invariant actually rests on is `posted.question` below, which reads
  // data rather than pixels and never broke.
  ok(`${mode}: dock visibly remains original after in-memory reorder`,
     shownBefore?.includes(original.title) && shownAfter?.includes(original.title));
  // Anti-vacuity: `includes` on a null/empty headline is not a match, but an
  // empty ORIGINAL title would make both sides trivially true. Derive it.
  ok(`${mode}: precondition -- a non-empty original title to match against`,
     typeof original.title === 'string' && original.title.length > 10);
  // #474: and the strip must have REMOVED something, before and after. A
  // no-op strip passes the compare above for as long as the headline happens
  // to be bare, then fails on a correct page the moment chrome changes shape
  // -- which is exactly what #456's bare-text separator did for two days.
  // Both sides derived at runtime; a literal would silently expire.
  ok(`${mode}: precondition -- stripping chrome changed the headline both times`,
     typeof after.raw === 'string' && after.raw !== after.stable &&
     typeof before.raw === 'string' && before.raw !== before.stable);
  ok(`${mode}: request was made`, !!posted);
  ok(`${mode}: request targets visibly docked question after reorder (#266)`,
     posted?.question === original.title);
  ok(`${mode}: request carries exact text`,
     (mode === 'note' ? posted?.comment : posted?.answer) === text);
  notes.push(`${mode}: original=${JSON.stringify(original.title)}`);
  notes.push(`${mode}: posted=${JSON.stringify(posted?.question || null)}`);
}

await browser.close();
finish();
