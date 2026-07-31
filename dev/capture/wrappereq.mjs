/* #630 P5 stage 2 — permanent QaCard builder/wrapper equality.

   The expected side comes from the production builder on the served page.
   The actual side comes from the committed design bundle on a detached page.
   Both strings then pass through the SAME template parser and serializer
   before strict equality. This guard proves local derivation, not successful
   ingestion by claude.ai/design; that external, authenticated judgement is
   deliberately outside the lane.

   usage: node wrappereq.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { readFileSync, mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'production qaCard(fixture) on the served page, then the one ' +
          'DreamworkDesign.QaCard export mounted in an isolated root in the ' +
          'real shell its concatenated client sources require',
  traceWindow: 'settled DOM only; strict serialization equality, no motion',
});

const fixture = JSON.parse(readFileSync(
  new URL('../../client/dist/ds/QaCard.fixture.json', import.meta.url)));
const designBundle = readFileSync(
  new URL('../../client/dist/ds/index.js', import.meta.url), 'utf8');
const nativeBundle = readFileSync(
  new URL('../../client/dist/native.js', import.meta.url), 'utf8');

const browser = await chromium.launch();
const builderPage = await browser.newPage();
builderPage.on('pageerror', e => errs.push('builder page: ' + String(e)));
await builderPage.goto(BASE + '/questions', { waitUntil: 'networkidle' });
const builder = await builderPage.evaluate(props => qaCard(props.q, props.k), fixture);

/* The design package intentionally concatenates the client sources. Load it
   into the real shell they expect, not an invented blank document whose
   missing composer/morphdom makes the bundle throw before it can export. */
await builderPage.addScriptTag({ content: nativeBundle });
await builderPage.evaluate(() => {
  delete document.getElementById('cmdpalette').dataset.composerMount;
});
await builderPage.addScriptTag({ content: designBundle });
const mounted = await builderPage.evaluate(async props => {
  const root = document.createElement('div');
  root.id = 'wrapper-equality-mount';
  document.body.append(root);
  dwNative.ReactDOM.createRoot(root).render(
    dwNative.React.createElement(DreamworkDesign.QaCard, props));
  for (let i = 0; i < 100; i++) {
    const host = root.querySelector('[data-dw-delegate="qaCard"]');
    if (host && host.querySelector('.qa')) return host.innerHTML;
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  return '';
}, fixture);

const readings = await builderPage.evaluate(({ builder, mounted }) => {
  const serialize = raw => {
    const template = document.createElement('template');
    template.innerHTML = raw;
    const host = document.createElement('div');
    host.append(template.content.cloneNode(true));
    return host.innerHTML;
  };
  return { expected: serialize(builder), actual: serialize(mounted) };
}, { builder, mounted });

/* Runtime-derived rather than tuned to today's markup: the real fixture's
   builder output establishes the floor the mounted wrapper must clear. */
const floor = Math.max(1, readings.expected.length - 1);
notes.push('serialized lengths: builder=' + readings.expected.length +
  ', wrapper=' + readings.actual.length + ', runtime floor=' + floor);
ok('builder precondition: fixture output is non-empty', builder.length > 0);
ok('builder precondition: fixture output carries class="qa"',
   /class="qa(?:\s|\")/.test(builder));
ok('wrapper precondition: mounted output clears the runtime-derived floor',
   readings.actual.length > floor);
ok('QaCard wrapper serialization strictly equals qaCard builder serialization',
   readings.actual === readings.expected);
ok('no page errors', errs.length === 0);
if (errs.length) notes.push(errs.join(' | '));
await browser.close();
finish();
