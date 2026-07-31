/* coexist — #630 P2's ownership protocol, exercised through #751's first
   production route. React and morphdom partition #view; they never render it
   concurrently. The router unmounts before a builder commit, and verify()
   names the deliberately-constructed violation.

   usage: node coexist.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { mkdirSync } from 'node:fs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/research native ownership → /reviews builder ownership → ' +
          '/research remount, then a deliberate builder-over-live-root ' +
          'collision read through registry.verify()',
  traceWindow: 'settled DOM end states only; transition:false keeps the ' +
               'ownership boundary load-independent.',
});

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
p.on('pageerror', e => errs.push('pageerror: ' + String(e)));
await p.goto(`${BASE}/research`, { waitUntil: 'networkidle' });
await waitFor(p, '[data-dw-mount="research"]');

const native = await p.evaluate(() => ({
  react: window.dwNative && window.dwNative.version,
  routes: window.dwNative && window.dwNative.registry.routes(),
  mounted: window.dwNative && window.dwNative.registry.mounted(),
  verify: window.dwNative && window.dwNative.registry.verify(),
  owned: document.querySelectorAll('[data-dw-mount]').length,
  delegates: document.querySelectorAll('[data-dw-delegate="artifactRow"]').length,
  oldBuilder: typeof buildResearch,
  instance: document.querySelector('[data-dw-research-instance]')
    .dataset.dwResearchInstance,
}));
notes.push('native: ' + JSON.stringify(native));
ok('one production React runtime is present',
   typeof native.react === 'string' && /^18\./.test(native.react));
ok('/research has one native authority and verify() sees it attached',
   native.routes.includes('research') && native.mounted.length === 1 &&
   native.mounted[0] === 'research' && native.owned === 1 &&
   native.verify.mounted[0] === 'research' && native.verify.detached.length === 0);
ok('the deleted whole-surface builder is absent',
   native.oldBuilder === 'undefined');
ok('the native shell reaches builder-owned rows only through Delegate',
   native.delegates >= 1);

await p.evaluate(() => navigate('reviews', null, {
  push: true, transition: false,
}));
const builder = await p.evaluate(() => ({
  mounted: window.dwNative.registry.mounted(),
  owned: document.querySelectorAll('[data-dw-mount]').length,
  label: document.querySelector('#view .label')?.textContent || '',
}));
notes.push('builder: ' + JSON.stringify(builder));
ok('the builder route receives #view only after React unmounts',
   builder.mounted.length === 0 && builder.owned === 0 &&
   builder.label.trim() === 'reviews');

await p.evaluate(() => navigate('research', null, {
  push: true, transition: false,
}));
await waitFor(p, '[data-dw-mount="research"]');
const remount = await p.evaluate(() => ({
  instance: document.querySelector('[data-dw-research-instance]')
    .dataset.dwResearchInstance,
  mounted: window.dwNative.registry.mounted(),
}));
ok('returning mounts a fresh research instance (navigation really unmounted)',
   remount.instance !== native.instance && remount.mounted[0] === 'research');

const collided = await p.evaluate(() => {
  setContent(buildReviews(data));
  return {
    verify: window.dwNative.registry.verify(),
    owned: document.querySelectorAll('[data-dw-mount]').length,
  };
});
notes.push('collision: ' + JSON.stringify(collided));
ok('MEASURED: morphdom deletes an unpartitioned live root',
   collided.owned === 0);
ok('the ownership violation is named, never a silent blank box',
   collided.verify.detached.includes('research') &&
   collided.verify.mounted.length === 0);

await p.evaluate(() => window.dwNative.registry.unmount('research'));
ok('no page errors before the deliberate collision',
   errs.length === 0);
if (errs.length) notes.push(errs.join(' | '));
await b.close();
finish();
