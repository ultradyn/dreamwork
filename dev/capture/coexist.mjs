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

/* Mount the production /research entry over real builder markup, then remove
   it through the production registry. This is deliberately not P2's
   synthetic __probe: the component, registry entry, host, data, and builder
   markup are all the ones the router uses. The direct mount is what isolates
   the registry's round-trip promise from the router's intentional
   replaceChildren() when authority changes. */
const roundTrip = await p.evaluate(() => {
  const view = document.getElementById('view');
  const before = view.innerHTML;
  const beforeLabel = view.querySelector('.label')?.textContent || '';
  const registry = window.dwNative.registry;
  registry.mount('research', view, data, null);

  const owned = view.querySelector('[data-dw-mount="research"]');
  const research = owned?.querySelector('[data-dw-research-instance]');
  const delegates = owned
    ? owned.querySelectorAll('[data-dw-delegate]').length : -1;
  const mountedHtmlLen = owned ? owned.innerHTML.length : -1;

  /* Everything React created is inspected, including CHILDREN; only the
     builder-owned HTML below a Delegate boundary is skipped. Those builders
     legitimately carry their established styling/behaviour classes. */
  const classOffenders = [];
  function inspectRuntimeElement(el) {
    if (el.hasAttribute('class')) {
      const identity = ['data-dw-mount', 'data-dw-research-instance',
                        'data-dw-delegate']
        .filter(name => el.hasAttribute(name))
        .map(name => '[' + name + '="' + el.getAttribute(name) + '"]')
        .join('');
      classOffenders.push({
        element: el.tagName.toLowerCase() +
          (el.id ? '#' + el.id : '') + identity,
        className: el.getAttribute('class'),
      });
    }
    if (el.hasAttribute('data-dw-delegate')) return;
    Array.from(el.children).forEach(inspectRuntimeElement);
  }
  if (owned) inspectRuntimeElement(owned);

  registry.unmount('research');
  const after = view.innerHTML;
  const beforeBytes = new TextEncoder().encode(before);
  const afterBytes = new TextEncoder().encode(after);
  let offset = 0;
  while (offset < beforeBytes.length && offset < afterBytes.length &&
         beforeBytes[offset] === afterBytes[offset]) offset += 1;
  const byteDiff = offset === beforeBytes.length &&
      offset === afterBytes.length ? null : {
    offset,
    before: offset < beforeBytes.length
      ? '0x' + beforeBytes[offset].toString(16).padStart(2, '0') : '<end>',
    after: offset < afterBytes.length
      ? '0x' + afterBytes[offset].toString(16).padStart(2, '0') : '<end>',
    beforeLength: beforeBytes.length,
    afterLength: afterBytes.length,
  };
  return {
    beforeLength: beforeBytes.length,
    beforeLabel,
    mounted: registry.mounted(),
    mountedHtmlLen,
    research: !!research,
    delegates,
    classOffenders,
    byteDiff,
    leftovers: view.querySelectorAll('[data-dw-mount]').length,
  };
});
notes.push('round-trip: ' + JSON.stringify(roundTrip));
ok('precondition: #view held real reviews builder markup before the mount ' +
   '(an empty host would make byte equality vacuous)',
   roundTrip.beforeLength > 500 && roundTrip.beforeLabel.trim() === 'reviews');
ok('precondition: the real /research component rendered rows before unmount',
   roundTrip.research && roundTrip.delegates >= 1 &&
   roundTrip.mountedHtmlLen > 200);
const classDetail = roundTrip.classOffenders.length
  ? roundTrip.classOffenders.map(o => o.element + ' class="' +
      o.className + '"').join(', ')
  : 'none';
ok('THE RUNTIME ADDS NO CLASS to React-owned elements; offending element ' +
   'and class: ' + classDetail,
   roundTrip.classOffenders.length === 0);
const byteDetail = roundTrip.byteDiff
  ? 'offset ' + roundTrip.byteDiff.offset + ': ' +
    roundTrip.byteDiff.before + ' -> ' + roundTrip.byteDiff.after +
    ' (lengths ' + roundTrip.byteDiff.beforeLength + ' -> ' +
    roundTrip.byteDiff.afterLength + ')'
  : 'none';
ok('unmounting the real /research component restores #view byte-for-byte; ' +
   'first differing bytes: ' + byteDetail,
   roundTrip.byteDiff === null && roundTrip.leftovers === 0);

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
