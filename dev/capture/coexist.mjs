/* coexist — #630 P2: does a React root and morphdom's reconciler share one
   page, and on what protocol?

   This is the guard the plan asks for at P2 (§5-P2(i)) and it exists to
   retire the transition's TOP-RANKED risk: "React and morphdom fight over
   DOM — wrong here and the whole shape wobbles" (§6-R1). Its own suggested
   probe is "a scratch page with one component root inside `#view` under
   forced ticks"; this does it on the REAL page instead, which is strictly
   stronger and costs nothing extra.

   HOW IT REACHES A RUNTIME THE PAGE DOES NOT SERVE. P2 mounts nothing, so
   `client/dist/native.js` is not in PAGE and the served page is byte-
   identical to master's (604299 bytes, sha256 db2b848b…, `cmp` clean). The
   guard injects the committed bundle as a second classic <script> — which is
   exactly the position P3 will serve it from — so everything below is
   measured against the production assembly rather than a mock of it.

   WHAT IT MEASURES, and the two of these are DIFFERENT CLAIMS:

     1. The intended protocol WORKS. `#view` has one owner at a time. With
        the builder's re-render suppressed for the duration — the smallest
        possible stand-in for the route-level exclusion P3 implements — a
        real tick's data reaches the mounted component, its React state
        survives, and unmounting hands `#view` back byte-for-byte.

     2. The violation is DETECTED. With the builder's re-render live, a tick
        renders a builder string over the live root, and morphdom deletes the
        component's container out from under React. That is not a bug to fix
        here; it is the measured fact that makes the exclusion rule
        necessary. What P2 owes is that it cannot happen SILENTLY, so the
        check is that `registry.verify()` reports the root detached.

   Reporting one of these as the other is the failure mode to avoid: "React
   and morphdom coexist" is false, and "they cannot be made to coexist" is
   also false. The true statement is that they partition, and the partition
   is enforced by the router and audited by `verify()`.

   PRODUCTION LINES THE RED-PROOFS NAME:
     · `dev/build/src/registry.js` mount/unmount — removing the container
       removal reds the round-trip check;
     · `registry.verify()`'s `doc.contains` — inverting it reds the
       detection check;
     · `dev/build/src/probe.js`'s `useState` instance id — replacing it with
       a module-level counter reds the state-survival check (and is the
       false-green a naive version of this guard would have shipped);
     · `dev/build/src/delegate.js`'s `dangerouslySetInnerHTML` — any markup
       of its own reds the wrapper-equality check.

   usage: node coexist.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { readFileSync, mkdirSync, utimesSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
// .../dev/capture/coexist.mjs → .../dev/capture → .../dev → the repo root.
const REPO = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/research with client/dist/native.js injected as a second classic ' +
          'script: registry mount/unmount inside #view, a delegated ' +
          'buildResearch wrapper, real /mtime-driven ticks through the ' +
          "page's own setData, and a deliberate morphdom-over-live-root " +
          'collision',
  traceWindow: 'up to 8s per forced tick, polled at 100ms for the probe ' +
               'sentinel to change. No frame sampling: every claim here is ' +
               'an end state (a DOM string, an attribute value, a verify() ' +
               'reading), never a transition.',
});

const NATIVE = readFileSync(join(REPO, 'client', 'dist', 'native.js'), 'utf8');
ok('precondition: the committed native.js is a real bundle (>50KB)',
   NATIVE.length > 50_000);

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
p.on('pageerror', e => errs.push('pageerror: ' + String(e)));

const d = await (await fetch(`${BASE}/data.json`)).json();
const target = d.target;
ok('precondition: the fixture serves at least one research artifact (the ' +
   'delegated builder has something to render)', (d.research || []).length >= 1);

await p.goto(`${BASE}/research`, { waitUntil: 'networkidle' });
if (!(await present(p, '#view', 'the #view container'))) {
  await b.close(); finish();
} else {

/* ── the scope claim the whole delegation design rests on ─────────────────
   The builders are top-level declarations in the PAGE's script scope, not
   module exports. `buildResearch` is a `function` (so it lands on the global
   object); `qaCard` is a `const` (so it lands in the global LEXICAL
   environment, which is NOT window). A separately-injected classic script
   must be able to name BOTH — the const half is the one that could plausibly
   fail, and P5's wrappers depend on it. Measured, never assumed. */
const scope = await p.evaluate(() => {
  const out = {};
  const s = document.createElement('script');
  s.textContent =
    'window.__dwScope = {' +
    '  fnDecl: typeof buildResearch,' +
    '  lexicalConst: typeof qaCard,' +
    '  constOnWindow: typeof window.qaCard };';
  document.head.appendChild(s);
  Object.assign(out, window.__dwScope || {});
  return out;
});
notes.push('scope: ' + JSON.stringify(scope));
ok('a later classic script can name a builder declared with `function` ' +
   '(buildResearch)', scope.fnDecl === 'function');
ok('a later classic script can name a builder declared with `const` ' +
   '(qaCard) — the global lexical environment is shared, and P5 wrappers ' +
   'need this', scope.lexicalConst === 'function');
ok('and that const is NOT on window — so this is genuinely lexical scope ' +
   'resolution and not a property lookup that happened to work',
   scope.constOnWindow === 'undefined');

/* ── inject the runtime, and prove it mounts nothing ──────────────────── */
await p.addScriptTag({ content: NATIVE });
const boot = await p.evaluate(() => ({
  present: typeof window.dwNative === 'object' && window.dwNative !== null,
  react: window.dwNative && window.dwNative.version,
  routes: window.dwNative ? window.dwNative.registry.routes() : null,
  mounted: window.dwNative ? window.dwNative.registry.mounted() : null,
  ownedNodes: document.querySelectorAll('[data-dw-mount]').length,
}));
notes.push('boot: ' + JSON.stringify(boot));
ok('the injected bundle exposes window.dwNative', boot.present);
ok('it carries a real React (version reported)',
   typeof boot.react === 'string' && /^\d+\./.test(boot.react));
ok('the registry has the probe registered',
   Array.isArray(boot.routes) && boot.routes.includes('__probe'));
ok('LOADING IT MOUNTS NOTHING — no roots live, no owned nodes in the DOM ' +
   '(this is the phase claim: the runtime is inert until a router asks)',
   Array.isArray(boot.mounted) && boot.mounted.length === 0 &&
   boot.ownedNodes === 0);

/* ── phase A: the round trip is lossless ──────────────────────────────── */
const roundTrip = await p.evaluate(async () => {
  const view = document.getElementById('view');
  const before = view.innerHTML;
  const data = await (await fetch('/data.json')).json();
  window.dwNative.registry.mount('__probe', view, data);
  const sentinel = view.querySelector('[data-dw-probe]');
  const delegated = view.querySelector('[data-dw-delegate="buildResearch"]');
  const container = view.querySelector('[data-dw-mount]');
  const out = {
    beforeLen: before.length,
    mounted: !!sentinel,
    /* THE VACUITY THIS CLOSES, and it is not hypothetical — the first run of
       this guard hit it. React 18 commits `root.render` concurrently, so the
       container was still EMPTY when the round trip was measured, and
       "unmounting restores #view byte-for-byte" PASSED by removing an empty
       div. A restore check over a mount that rendered nothing is free. */
    mountedHtmlLen: container ? container.innerHTML.length : -1,
    delegatedRows: delegated
      ? delegated.querySelectorAll('[data-research]').length : -1,
    /* The wrapper's subtree against the builder's own output for the same
       data, BOTH passed through the same parser + serializer so that entity
       and quoting normalisation cannot false-red. This is the plan's P5
       "wrapper equality" check, born early on the one wrapper that exists. */
    wrapperEqualsBuilder: (function () {
      if (!delegated) return null;
      const probe = document.createElement('div');
      probe.innerHTML = buildResearch(null, data);
      return probe.innerHTML === delegated.innerHTML;
    })(),
    /* Max's spike rule (9b54b4f0): the runtime must not introduce a shared
       class, because the page addresses behavioural heroes by class and a
       shared class destroys the uniqueness those addresses rely on. */
    hostClasses: [
      view.querySelector('[data-dw-mount]'),
      delegated,
      sentinel,
    ].map(el => (el ? el.getAttribute('class') : 'MISSING')),
    builderClassCount: delegated
      ? delegated.querySelectorAll('[class]').length : -1,
  };
  window.dwNative.registry.unmount('__probe');
  out.after = view.innerHTML;
  out.restored = view.innerHTML === before;
  out.leftovers = view.querySelectorAll('[data-dw-mount]').length;
  return out;
});
notes.push('roundTrip: ' + JSON.stringify({
  beforeLen: roundTrip.beforeLen, delegatedRows: roundTrip.delegatedRows,
  hostClasses: roundTrip.hostClasses,
  builderClassCount: roundTrip.builderClassCount }));

ok('precondition: #view held real builder markup before the mount (a ' +
   'round-trip over an empty container is byte-equal for free)',
   roundTrip.beforeLen > 500);
ok('the probe mounted — its sentinel is in the DOM', roundTrip.mounted);
ok('the delegated wrapper rendered the builder\'s real rows',
   roundTrip.delegatedRows >= 1);
ok('WRAPPER EQUALS BUILDER: the wrapper\'s subtree serialises identically ' +
   'to buildResearch\'s own output for the same data (both through the ' +
   'same parser) — the wrapper restates nothing',
   roundTrip.wrapperEqualsBuilder === true);
ok('precondition: the builder\'s markup DOES carry classes, so the ' +
   'no-class assertion below is made by a detector that can see classes',
   roundTrip.builderClassCount >= 1);
ok('THE RUNTIME ADDS NO CLASS to anything (spike 9b54b4f0: a shared class ' +
   'destroys the uniqueness the page\'s FLIP heroes are addressed by) — ' +
   'its identity is data-* attributes only',
   roundTrip.hostClasses.every(c => c === null));
ok('precondition: the mount had actually RENDERED something before the ' +
   'unmount (a round trip that removes an empty div restores #view for ' +
   'free — the exact false-green this guard\'s first run scored)',
   roundTrip.mountedHtmlLen > 200);
ok('unmounting restores #view BYTE-FOR-BYTE — the builders cannot tell a ' +
   'component was ever there', roundTrip.restored === true);
ok('and leaves no owned nodes behind', roundTrip.leftovers === 0);

/* ── phase B: a real tick reaches the component, state survives ────────── */
const wired = await p.evaluate(async () => {
  const view = document.getElementById('view');
  const data = await (await fetch('/data.json')).json();
  window.dwNative.registry.mount('__probe', view, data);

  /* P3's one-line wiring, stood in for here. `setData` (router.js:1044) is
     THE one place `data` is replaced — both the first paint and the live
     tick go through it — so this is where components receive data, and there
     is no second fetch and no second authority. */
  window.__dwOrigSetData = window.setData;
  window.setData = function (next) {
    const applied = window.__dwOrigSetData(next);
    window.dwNative.registry.update(applied);
    return applied;
  };
  /* The route-level EXCLUSION, stood in for here. On a component-owned route
     a P3 router does not build a string at all, so setContent never runs.
     Suppressing it is the smallest possible stand-in for that, and phase C
     puts it back to measure what happens without it. */
  window.__dwOrigSetContent = window.setContent;
  window.setContent = function () { window.__dwSuppressed = (window.__dwSuppressed || 0) + 1; };

  return true;
});

/* SETTLE THE MOUNT EFFECT BEFORE TAKING A BASELINE, and this is the trap this
   guard actually fell into rather than a precaution against a hypothetical
   one. `flushSync` commits the DOM synchronously but the mount's `useEffect`
   still runs after the commit, so `seen` goes 0 → 1 on its own with no tick
   involved. The first version polled for "seen increased" immediately after
   forcing a tick, and it PASSED — on the mount effect landing, before the
   tick had happened at all (`suppressed: 0` was the tell). A green whose
   cause is not the thing under test is worth less than a red. */
let settled = null;
for (let i = 0; i < 80; i++) {
  settled = await p.evaluate(() => {
    const el = document.querySelector('[data-dw-probe-instance]');
    return el ? { instance: el.getAttribute('data-dw-probe-instance'),
                  seen: el.getAttribute('data-dw-probe-seen') } : null;
  });
  if (settled && settled.seen === '1') break;
  await sleep(50);
}
notes.push('mount settled: ' + JSON.stringify(settled));
ok('precondition: the mount effect has SETTLED (seen === 1) before any tick ' +
   'is forced — otherwise a later increment cannot be attributed to the tick',
   !!settled && settled.seen === '1' && !!settled.instance);
const wiredBase = settled || { instance: null, seen: '1' };

/* A REAL tick: bump the newest mtime under the target so watch.py's /mtime
   changes and the page's OWN poll does the rest. Nothing here calls the
   component; the whole chain — poll, fetch /data.json, setData, registry —
   is the page's. */
utimesSync(join(target, 'DREAMWORK.md'), new Date(), new Date());
let ticked = null;
for (let i = 0; i < 120; i++) {
  ticked = await p.evaluate(() => {
    const el = document.querySelector('[data-dw-probe-instance]');
    return el ? { instance: el.getAttribute('data-dw-probe-instance'),
                  seen: el.getAttribute('data-dw-probe-seen'),
                  suppressed: window.__dwSuppressed || 0 } : null;
  });
  // BOTH conditions, so the loop cannot exit on a render the tick did not
  // cause: the page must have tried to re-render AND the component must have
  // seen new data.
  if (ticked && ticked.suppressed >= 1 &&
      Number(ticked.seen) > Number(wiredBase.seen)) break;
  await sleep(100);
}
notes.push('after tick: ' + JSON.stringify(ticked));
ok('precondition: the tick actually fired (the page tried to re-render, ' +
   'which the exclusion stand-in absorbed) — else nothing below is about a ' +
   'tick at all', !!ticked && ticked.suppressed >= 1);
ok('THE UPDATE ARRIVED: the component re-rendered with the tick\'s data ' +
   '(seen incremented past the settled mount value) — data reaches ' +
   'components through setData, the same one authority the builders read',
   !!ticked && Number(ticked.seen) === Number(wiredBase.seen) + 1);
ok('AND ITS STATE SURVIVED: the React instance id is unchanged, so the ' +
   'component was re-rendered rather than destroyed and rebuilt',
   !!ticked && ticked.instance === wiredBase.instance);

const clean = await p.evaluate(() => window.dwNative.registry.verify());
notes.push('verify (exclusion held): ' + JSON.stringify(clean));
ok('verify() reports the root attached while the exclusion held',
   clean.mounted.includes('__probe') && clean.detached.length === 0);

/* ── phase C: the violation, and that it is detected ──────────────────── */
const collided = await p.evaluate(async () => {
  /* Put the builder's renderer back — this is a route whose authority is the
     BUILDER, with a component root sitting in its #view. Exactly the state
     the ownership rule forbids, constructed on purpose. */
  window.setContent = window.__dwOrigSetContent;
  const view = document.getElementById('view');
  const data = await (await fetch('/data.json')).json();
  /* A DIFFERENT builder's output, and that is required rather than
     incidental: `setContent` opens with `if (html === lastViewHtml) return;`
     (the #505 I5 hash-skip, `router.js:1658`). Re-rendering /research's own
     markup is byte-identical to what is already there, so the skip fires,
     morphdom never runs, and the collision this phase exists to measure does
     not happen — the first version of this check scored a green that way.
     `buildReviews` is what a real navigation to /reviews would render, which
     is exactly the scenario: a component mounted on one route, a builder
     string arriving for another. */
  const html = buildReviews(data);
  const distinct = html !== buildResearch(null, data);
  window.setContent(html);
  return { verify: window.dwNative.registry.verify(),
           distinct: distinct,
           ownedNodes: view.querySelectorAll('[data-dw-mount]').length };
});
notes.push('verify (after a builder render over the live root): ' +
           JSON.stringify(collided));
ok('precondition: the builder markup pushed is genuinely DIFFERENT from ' +
   'what is on screen, so setContent\'s hash-skip cannot absorb it and ' +
   'morphdom really runs', collided.distinct === true);
ok('MEASURED: a builder render over a live root DOES delete it — morphdom ' +
   'reconciles #view\'s children and the component container is not one it ' +
   'knows, so the root is gone. This is why the ownership rule exists',
   collided.ownedNodes === 0);
ok('AND IT IS DETECTED, not silent: verify() reports the root as detached, ' +
   'which is the reading a P3 router asserts before it renders a string',
   collided.verify.detached.includes('__probe') &&
   collided.verify.mounted.length === 0);

const cleanup = await p.evaluate(() => {
  try {
    window.dwNative.registry.unmount('__probe');
    return { threw: null, mounted: window.dwNative.registry.mounted().length };
  } catch (e) { return { threw: String(e), mounted: -1 }; }
});
ok('unmounting a root morphdom already detached does not throw — recovery ' +
   'from the violation must not itself be a second failure',
   cleanup.threw === null && cleanup.mounted === 0);

ok('no uncaught page errors across the whole run', errs.length === 0);
await b.close();
finish();
}
