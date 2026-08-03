/* #630 P5 stage 2 — permanent builder/wrapper equality.

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
  drives: 'each registered production builder(fixture) on the served page, ' +
          'then its DreamworkDesign export mounted in an isolated root in ' +
          'the real shell its concatenated client sources require',
  traceWindow: 'settled DOM only; strict serialization equality, no motion',
});

const fixture = name => JSON.parse(readFileSync(
  new URL(`../../client/dist/ds/${name}.fixture.json`, import.meta.url)));
const CASES = [
  {
    name: 'QaCard', delegate: 'qaCard', expectedClass: 'qa',
    fixture: fixture('QaCard'),
    build: props => {
      const previousData = data;
      const previousView = view;
      try {
        data = (props.ctx && props.ctx.data) || {};
        view = (props.ctx && props.ctx.view) || { name: null, param: null, q: null };
        return qaCard(props.q, props.k);
      } finally {
        data = previousData;
        view = previousView;
      }
    },
  },
  {
    name: 'Label', delegate: 'label', expectedClass: 'label',
    fixture: fixture('Label'),
    build: props => label(props.text),
  },
  {
    name: 'PipBtn', delegate: 'pipBtn', expectedClass: 'pipbtn',
    fixture: fixture('PipBtn'),
    build: props => pipBtn(props.url, props.label),
  },
];
const hasContent = value => {
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.some(hasContent);
  return value && typeof value === 'object' && Object.values(value).some(hasContent);
};
if (!CASES.length) throw new Error('wrappereq has no registered cases');
for (const testCase of CASES) {
  if (!hasContent(testCase.fixture)) {
    throw new Error(`${testCase.name} equality fixture is absent or empty`);
  }
}
const designBundle = readFileSync(
  new URL('../../client/dist/ds/index.js', import.meta.url), 'utf8');
const nativeBundle = readFileSync(
  new URL('../../client/dist/native.js', import.meta.url), 'utf8');

const browser = await chromium.launch();
const builderPage = await browser.newPage();
builderPage.on('pageerror', e => errs.push('builder page: ' + String(e)));
await builderPage.goto(BASE + '/questions', { waitUntil: 'networkidle' });

/* The design package intentionally concatenates the client sources. Load it
   into the real shell they expect, not an invented blank document whose
   missing composer/morphdom makes the bundle throw before it can export. */
await builderPage.addScriptTag({ content: nativeBundle });
await builderPage.evaluate(() => {
  delete document.getElementById('cmdpalette').dataset.composerMount;
});
await builderPage.addScriptTag({ content: designBundle });
for (const testCase of CASES) {
  const builder = await builderPage.evaluate(testCase.build, testCase.fixture);
  const mounted = await builderPage.evaluate(async ({ name, delegate, props }) => {
    const root = document.createElement('div');
    root.id = `wrapper-equality-mount-${name}`;
    /* Keep the equality subject detached: the live page's one-second ages()
       sweep fills `.age` nodes after mount, which compares post-render DOM to
       the builder's raw string and makes equality depend on tick timing. */
    dwNative.ReactDOM.createRoot(root).render(
      dwNative.React.createElement(DreamworkDesign[name], props));
    for (let i = 0; i < 100; i++) {
      const host = root.querySelector(`[data-dw-delegate="${delegate}"]`);
      if (host && host.innerHTML) return host.innerHTML;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    return '';
  }, { name: testCase.name, delegate: testCase.delegate, props: testCase.fixture });

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

  /* Runtime-derived rather than tuned to today's markup: each real fixture's
     builder output establishes the floor its mounted wrapper must clear. */
  const floor = Math.max(1, readings.expected.length - 1);
  notes.push(`${testCase.name} serialized lengths: builder=${readings.expected.length}` +
    `, wrapper=${readings.actual.length}, runtime floor=${floor}`);
  if (readings.actual !== readings.expected) {
    let at = 0;
    while (readings.expected[at] === readings.actual[at] &&
           at < readings.expected.length && at < readings.actual.length) at++;
    notes.push(`${testCase.name} first mismatch at ${at}: expected ` +
      JSON.stringify(readings.expected.slice(at, at + 100)) + ', wrapper ' +
      JSON.stringify(readings.actual.slice(at, at + 100)));
  }
  ok(`${testCase.name} builder precondition: fixture output is non-empty`,
     builder.length > 0);
  ok(`${testCase.name} builder precondition: output carries class="${testCase.expectedClass}"`,
     new RegExp(`class="[^"]*\\b${testCase.expectedClass}\\b`).test(builder));
  ok(`${testCase.name} wrapper precondition: mounted output clears the runtime-derived floor`,
     readings.actual.length > floor);
  ok(`${testCase.name} wrapper serialization strictly equals ${testCase.delegate} builder serialization`,
     readings.actual === readings.expected);
}
notes.push(`registered cases run: ${CASES.length}`);
ok('no page errors', errs.length === 0);
if (errs.length) notes.push(errs.join(' | '));
await browser.close();
finish();
