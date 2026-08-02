/* #1058 — Pass route-specific payloads into native /file, /chat, /tasks2 mounts.

   Two halves of one defect:
   - The REGISTRY (dev/build/src/registry.js): mount must pass a route-specific
     payload to the component alongside base data and param. Tested by loading
     the real registry source into a vm with mock React.
   - The ROUTER (client/router.js): buildCurrent must fetch the payload for
     native routes and stash it; commitCurrent must pass it as the 5th argument
     to registry.mount. Tested by extracting the real functions from router.js
     into a vm with mocked globals.

   Both halves are needed: a router that stashes a payload the registry drops,
   and a registry that accepts a payload the router never sends, are the same
   false green from opposite ends. The registry test catches "accepted but not
   rendered" (#1058 direction 2); the router tests catch "fetched but not
   delivered" (#1058 direction 1).

   Run: node --test dev/registry_payload.test.mjs */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const ROOT = path.resolve('.');
const REGISTRY_SRC = fs.readFileSync(
  path.join(ROOT, 'dev/build/src/registry.js'), 'utf8');
const ROUTER_SRC = fs.readFileSync(
  path.join(ROOT, 'client/router.js'), 'utf8');

/* ── helpers ─────────────────────────────────────────────────────────── */

/* Extract a top-level function from source by name, brace-matching from its
   opening `{` to its closing `}`. Handles both `function name(` and
   `async function name(` — the async variant is preferred so the extracted
   body keeps its `async` keyword and `await` stays valid. */
function extractFunction(src, name) {
  const asyncIdx = src.indexOf('async function ' + name + '(');
  const syncIdx = src.indexOf('function ' + name + '(');
  const idx = asyncIdx >= 0 ? asyncIdx : syncIdx;
  assert(idx >= 0, name + ' must exist in source');
  const braceStart = src.indexOf('{', idx);
  let depth = 0;
  for (let i = braceStart; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(idx, i + 1); }
  }
  throw new Error('unterminated function ' + name);
}

/* Load registry.js into a vm with mock React/createRoot/flushSync. Strips ES
   module syntax and returns the exports via a closure. */
function loadRegistry(React, createRoot, flushSync) {
  let code = REGISTRY_SRC.replace(/^import\s+.*$/gm, '');
  code = code.replace(/^export\s+const\s+/gm, 'const ');
  code = code.replace(/^export\s+function\s+/gm, 'function ');
  code += '\nreturn { OWNED_ATTR, createRegistry };';
  const factory = new Function('React', 'createRoot', 'flushSync', code);
  return factory(React, createRoot, flushSync);
}

function mockHost() {
  const container = {
    tagName: 'div', _attrs: {}, _children: [],
    setAttribute(k, v) { this._attrs[k] = v; },
    getAttribute(k) { return this._attrs[k] !== undefined ? this._attrs[k] : null; },
    appendChild(c) { this._children.push(c); c.parentNode = this; return c; },
    removeChild(c) { this._children = this._children.filter(x => x !== c); c.parentNode = null; return c; },
    parentNode: null,
  };
  return {
    ownerDocument: { createElement: () => Object.assign({}, container) },
    appendChild(c) { this._child = c; c.parentNode = this; return c; },
    _child: null,
  };
}

function mocks() {
  const renders = [];
  const React = { createElement(type, props) { return { type, props: props || {} }; } };
  function createRoot() { return { render(el) { renders.push(el); }, unmount() {} }; }
  function flushSync(fn) { fn(); }
  return { React, createRoot, flushSync, renders };
}

/* ════════════════════════════════════════════════════════════════════════
   REGISTRY — the payload must ARRIVE at the mounted component
   ════════════════════════════════════════════════════════════════════════ */

test('mount renders the component with a payload alongside base data and param', () => {
  const m = mocks();
  const { createRegistry } = loadRegistry(m.React, m.createRoot, m.flushSync);
  const registry = createRegistry();
  function FileNative(props) { return { uses: props.payload }; }
  registry.register('file', { component: FileNative });

  const baseData = { target: '/repo' };
  const payload = { text: 'FILE CONTENTS', hl: '<span>hl</span>' };
  registry.mount('file', mockHost(), baseData, 'src/app.js', payload);

  assert.equal(m.renders.length, 1, 'mount renders exactly once');
  assert.deepEqual(m.renders[0].props.payload, payload,
    'the component must receive the route-specific payload');
  assert.equal(m.renders[0].props.data, baseData,
    'base /data.json must still arrive — payload is additive, not a replacement');
  assert.equal(m.renders[0].props.param, 'src/app.js');
});

test('mount carries each of the three payload families to the component', () => {
  const families = [
    { route: 'file', param: 'a.txt', payload: { text: 'body', hl: null } },
    { route: 'chat', param: '42', payload: { id: 42, entries: [] } },
    { route: 'tasks2', param: null, payload: { list: { tasks: [] }, detail: null, selected: null } },
  ];
  for (const { route, param, payload } of families) {
    const m = mocks();
    const { createRegistry } = loadRegistry(m.React, m.createRoot, m.flushSync);
    const registry = createRegistry();
    registry.register(route, { component: () => null });
    registry.mount(route, mockHost(), { target: '/r' }, param, payload);
    assert.deepEqual(m.renders[0].props.payload, payload,
      `route ${route}: a seam that silently no-ops for one family is a partial fix`);
  }
});

test('mount with null payload still renders (routes without route-specific data)', () => {
  const m = mocks();
  const { createRegistry } = loadRegistry(m.React, m.createRoot, m.flushSync);
  const registry = createRegistry();
  registry.register('research', { component: () => null });
  registry.mount('research', mockHost(), { target: '/r' }, null, null);
  assert.equal(m.renders.length, 1);
  assert.equal(m.renders[0].props.payload, null);
  assert.ok(m.renders[0].props.data, 'base data still received');
});

test('update re-renders with new base data while preserving the payload', () => {
  const m = mocks();
  const { createRegistry } = loadRegistry(m.React, m.createRoot, m.flushSync);
  const registry = createRegistry();
  registry.register('file', { component: () => null });
  const payload = { text: 'file', hl: null };
  registry.mount('file', mockHost(), { target: '/r', v: 1 }, 'a.txt', payload);
  const nextData = { target: '/r', v: 2 };
  registry.update(nextData);
  const tick = m.renders[m.renders.length - 1];
  assert.equal(tick.props.data, nextData, 'tick pushes new base data');
  assert.deepEqual(tick.props.payload, payload,
    'tick must preserve the route-specific payload');
  assert.equal(tick.props.param, 'a.txt');
});

test('mount without a payload argument still renders (backward compat)', () => {
  const m = mocks();
  const { createRegistry } = loadRegistry(m.React, m.createRoot, m.flushSync);
  const registry = createRegistry();
  registry.register('probe', { component: () => null });
  registry.mount('probe', mockHost(), { target: '/r' }, null);
  assert.equal(m.renders.length, 1);
  assert.equal(m.renders[0].props.payload, undefined,
    'omitting the arg must not error — existing 4-arg callers must not break');
});

/* ════════════════════════════════════════════════════════════════════════
   ROUTER — commitCurrent must deliver the stashed payload to registry.mount
   ════════════════════════════════════════════════════════════════════════ */

test('commitCurrent passes the view payload as the 5th mount argument', () => {
  const fnSrc = extractFunction(ROUTER_SRC, 'commitCurrent');
  let mountArgs = null;
  const mockRegistry = { mount(...args) { mountArgs = args; } };
  const payload = { text: 'PAYLOAD_FROM_BUILD', hl: null };
  const ctx = {
    nativeRegistry: () => mockRegistry,
    isNativeRoute: () => true,
    view: { name: 'file', param: 'test.js', payload },  // payload rides on view
    unmountNativeRoots: () => {},
    setContent: () => {},
    document: { getElementById: () => ({ replaceChildren: () => {} }) },
    lastViewHtml: null,
    window: {},
    data: { target: '/repo' },
    finishViewCommit: () => {},
  };
  vm.createContext(ctx);
  vm.runInContext(fnSrc, ctx);
  vm.runInContext('commitCurrent(null)', ctx);

  assert.ok(mountArgs, 'registry.mount must be called for a native route');
  assert.ok(mountArgs.length >= 5,
    'mount must receive at least 5 arguments: route, host, data, param, payload — ' +
    '4 args means the payload was fetched then discarded (#1058)');
  assert.deepEqual(mountArgs[4], payload,
    'the 5th argument must be view.payload (the navigation that fetched it)');
});

/* ════════════════════════════════════════════════════════════════════════
   ROUTER — buildCurrent must fetch and stash the payload for native routes
   ════════════════════════════════════════════════════════════════════════ */

test('buildCurrent fetches and stashes the route payload on the view before returning null', async () => {
  const fnSrc = extractFunction(ROUTER_SRC, 'buildCurrent');
  const fetchedPayload = { text: 'FETCHED_FILE_BODY', hl: null };
  const ctx = {
    isNativeRoute: () => true,
    view: { name: 'file', param: 'a.js', q: null, mode: null },
    ensureData: async () => ({ target: '/r' }),
    fetchRoutePayload: async (name, param) => {
      ctx._frpArgs = { name, param };
      return fetchedPayload;
    },
    data: null,
    buildFile: () => '', fetchFile: async () => null,
    buildChat: () => '', fetchChat: async () => null,
    buildTasks2: () => '', fetchTaskTriage: async () => null,
    buildReview: () => '', buildQuestion: () => '',
    buildReviews: () => '', buildSettings: () => '',
    buildQuestions: () => '', buildAnswers: () => '',
    buildDashboard: () => '',
  };
  vm.createContext(ctx);
  vm.runInContext(fnSrc, ctx);
  const html = await vm.runInContext('buildCurrent()', ctx);

  assert.equal(html, null,
    'a native route must return null (no builder HTML) so commitCurrent mounts the component');
  assert.deepEqual(ctx.view.payload, fetchedPayload,
    'buildCurrent must stash the fetched payload ON THE CAPTURED VIEW OBJECT ' +
    '(view.payload), so payload and route identity are the same object and a ' +
    'later navigation — a different view — can never read this fetch result');
  assert.deepEqual(ctx._frpArgs, { name: 'file', param: 'a.js' },
    'fetchRoutePayload must receive the route name and param');
});

/* ── the fetchRoutePayload dispatch must cover all three families ──────── */

test('fetchRoutePayload dispatches to all three payload families', async () => {
  const fnSrc = extractFunction(ROUTER_SRC, 'fetchRoutePayload');
  const calls = [];
  const ctx = {
    fetchFile: async (p) => { calls.push(['file', p]); return { text: 'f' }; },
    fetchChat: async (p) => { calls.push(['chat', p]); return { id: 1 }; },
    fetchTaskTriage: async (p) => { calls.push(['tasks2', p]); return { list: {} }; },
  };
  vm.createContext(ctx);
  vm.runInContext(fnSrc, ctx);
  await vm.runInContext('fetchRoutePayload("file", "a.txt")', ctx);
  await vm.runInContext('fetchRoutePayload("chat", "42")', ctx);
  await vm.runInContext('fetchRoutePayload("tasks2", null)', ctx);
  const noPayload = await vm.runInContext('fetchRoutePayload("reviews", null)', ctx);

  assert.deepEqual(calls, [['file', 'a.txt'], ['chat', '42'], ['tasks2', null]],
    'all three families must dispatch — a seam that serves /file and no-ops ' +
    'for /chat or /tasks2 is the shape of a partial fix');
  assert.equal(noPayload, null,
    'routes without a route-specific payload must get null, not undefined');
});

/* ════════════════════════════════════════════════════════════════════════
   ROUTER — the deferred-navigation RACE (#1058 round 2)

   round 1 shipped a routePayload that is a MODULE GLOBAL: buildCurrent
   assigns it AFTER an `await` and commitCurrent reads it independently of
   the view it is mounting. So a navigation held pending across an await can
   have its payload mounted under a LATER route. These tests drive the REAL
   navigate / buildCurrent / commitCurrent / fetchRoutePayload together in
   one vm, with controllable (deferred) fetches, so the interleaving is
   deterministic rather than actually racy.

   Two properties (#1058 r2):
   1. A payload can only ever mount with its OWN navigation's route+param.
   2. A navigation superseded while awaiting must not commit.
   ════════════════════════════════════════════════════════════════════════ */

/* A controllable promise: the test resolves it in the order that exercises
   the race, and `resolved` lets the test PROVE the interleaving happened
   (the first fetch was genuinely still pending when the second began). */
function deferred() {
  let r;
  const d = { promise: new Promise(res => { r = res; }), resolved: false };
  d.resolve = v => { d.resolved = true; r(v); };
  return d;
}

/* Build a fresh vm with the REAL navigate/buildCurrent/commitCurrent/
   fetchRoutePayload loaded together, sharing one `view` and one
   (round-1) `routePayload`. Fetches are controllable via deferreds keyed
   by "route:param". `mounts` records every registry.mount. */
function raceHarness() {
  const mounts = [];
  const calls = [];
  const fetchDeferreds = new Map();
  function deferredFor(route, param) {
    const key = route + ':' + param;
    if (!fetchDeferreds.has(key)) fetchDeferreds.set(key, deferred());
    return fetchDeferreds.get(key);
  }
  const registry = {
    has: n => n === 'file' || n === 'chat' || n === 'tasks2',
    mount: (...a) => mounts.push({ route: a[0], param: a[3], payload: a[4] }),
    verify: () => ({ detached: [] }),
    unmountAll: () => {},
  };
  const ctx = {
    view: { name: 'dashboard', param: null, q: null, mode: null },
    data: { target: '/repo' },
    routePayload: null,          // round-1 channel; harmless once the fix binds to view
    TINT: {}, SEED: {},
    window: { dreambg: { setTint: () => {} } },
    document: {
      body: { classList: { toggle: () => {} } },
      getElementById: () => ({ replaceChildren: () => {} }),
    },
    history: { pushState: () => {} },
    lastViewHtml: null,
    fileMsg: null,               // navigate guards `if (fileMsg && …)`
    nativeRegistry: () => registry,
    isNativeRoute: n => n === 'file' || n === 'chat' || n === 'tasks2',
    unmountNativeRoots: () => {},
    setContent: () => {},
    finishViewCommit: () => {},
    applyTitle: () => {},
    renderChrome: () => {},
    crossfade: html => { throw new Error('crossfade should not run under transition:false'); },
    scrollRatio: () => 0,
    restoreScrollRatio: () => {},
    invalidateAskFlight: () => {},
    invalidateChatReplyFlight: () => {},
    invalidateChatArchiveFlight: () => {},
    ensureData: async () => {},
    fetchFile: p => { calls.push(['file', p]); return deferredFor('file', p).promise; },
    fetchChat: p => { calls.push(['chat', p]); return deferredFor('chat', p).promise; },
    fetchTaskTriage: p => { calls.push(['tasks2', p]); return deferredFor('tasks2', p).promise; },
    buildFile: () => '', buildChat: () => '', buildTasks2: () => '',
    buildReview: () => '', buildQuestion: () => '', buildReviews: () => '',
    buildSettings: () => '', buildQuestions: () => '', buildAnswers: () => '',
    buildDashboard: () => '',
  };
  const code = ['navigate', 'buildCurrent', 'commitCurrent', 'fetchRoutePayload']
    .map(n => extractFunction(ROUTER_SRC, n)).join('\n\n');
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  return { ctx, mounts, calls, fetchDeferreds };
}

/* Flush the shared microtask queue until a predicate holds (or attempts run
   out). navigate suspends first in ensureData, then in its route fetch; this
   lets the test advance a navigation exactly to its pending fetch without
   resolving it. */
async function advanceUntil(pred) {
  for (let i = 0; i < 50; i++) {
    if (pred()) return true;
    await Promise.resolve();
  }
  return pred();
}

test('race: a held-pending route payload never mounts under a later route', async () => {
  const h = raceHarness();
  const navA = vm.runInContext('navigate("file","A",{transition:false})', h.ctx);
  // advance navA past ensureData into its pending fetchFile(A)
  await advanceUntil(() => h.fetchDeferreds.has('file:A'));
  assert.equal(h.fetchDeferreds.get('file:A').resolved, false,
    'PRECONDITION: file/A still pending when chat/B starts — else the interleaving the test exists for never occurs');
  const navB = vm.runInContext('navigate("chat","B",{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('chat:B'));
  // chat/B completes first and mounts…
  h.fetchDeferreds.get('chat:B').resolve({ id: 'B', entries: [] });
  await navB;
  // …then the held file/A resolves — round 1 commits it under view (now chat/B)
  h.fetchDeferreds.get('file:A').resolve({ text: 'PAYLOAD_A' });
  await navA;

  const poisoned = h.mounts.find(m =>
    m.route === 'chat' && m.param === 'B' && m.payload && m.payload.text === 'PAYLOAD_A');
  assert.ok(!poisoned,
    'a held-pending payload must not mount under a later route; mounts=' +
    JSON.stringify(h.mounts));
  // the chat/B mount that DID happen must carry chat/B's own payload
  const good = h.mounts.find(m => m.route === 'chat' && m.param === 'B');
  assert.ok(good, 'chat/B must still mount once it completed');
  assert.deepEqual(good.payload, { id: 'B', entries: [] });
});

test('race: not order-dependent — 20 iterations, both resolution orders', async () => {
  for (let i = 0; i < 20; i++) {
    for (const order of ['chat-first', 'file-first']) {
      const h = raceHarness();
      const navA = vm.runInContext('navigate("file","A",{transition:false})', h.ctx);
      await advanceUntil(() => h.fetchDeferreds.has('file:A'));
      const navB = vm.runInContext('navigate("chat","B",{transition:false})', h.ctx);
      await advanceUntil(() => h.fetchDeferreds.has('chat:B'));
      if (order === 'chat-first') {
        h.fetchDeferreds.get('chat:B').resolve({ id: 'B', entries: [] });
        await navB;
        h.fetchDeferreds.get('file:A').resolve({ text: 'PAYLOAD_A' });
        await navA;
      } else {
        h.fetchDeferreds.get('file:A').resolve({ text: 'PAYLOAD_A' });
        await navA;
        h.fetchDeferreds.get('chat:B').resolve({ id: 'B', entries: [] });
        await navB;
      }
      const poisoned = h.mounts.find(m =>
        m.route === 'chat' && m.param === 'B' && m.payload && m.payload.text === 'PAYLOAD_A');
      assert.ok(!poisoned,
        `iter ${i} ${order}: held payload leaked; mounts=` + JSON.stringify(h.mounts));
    }
  }
});

test('race: same route, different param — guard must catch param-level supersession', async () => {
  // /chat/A held pending, then /chat/B. A name-only guard (view.name !== navView.name)
  // would treat these as the same route and let the superseded /chat/A commit too.
  // Two independent observables break under that flaw: (a) navA commits a DUPLICATE
  // chat/B mount (property 2: a superseded nav must not commit), and (b) a payload-on-
  // global variant would cross-contaminate the payload. Assert BOTH so the test catches
  // the flaw whichever shape it takes.
  const h = raceHarness();
  const navA = vm.runInContext('navigate("chat","A",{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('chat:A'));
  assert.equal(h.fetchDeferreds.get('chat:A').resolved, false, 'PRECONDITION: chat/A pending');
  const navB = vm.runInContext('navigate("chat","B",{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('chat:B'));
  assert.equal(h.fetchDeferreds.get('chat:B').resolved, false, 'PRECONDITION: chat/B pending');
  h.fetchDeferreds.get('chat:B').resolve({ id: 'B', entries: [] });
  await navB;
  h.fetchDeferreds.get('chat:A').resolve({ id: 'A', entries: ['A_BODY'] });
  await navA;

  const aUnderB = h.mounts.find(m => m.route === 'chat' && m.param === 'B' &&
    m.payload && m.payload.id === 'A');
  assert.ok(!aUnderB,
    'chat/A payload must never mount under chat/B; mounts=' + JSON.stringify(h.mounts));
  const chatMounts = h.mounts.filter(m => m.route === 'chat');
  assert.equal(chatMounts.length, 1,
    'a superseded same-route navigation must not commit a duplicate mount; ' +
    'name-only guard would pass payload checks but still commit twice; mounts=' +
    JSON.stringify(h.mounts));
  assert.equal(chatMounts[0].param, 'B', 'the one chat mount is chat/B');
});

test('race: three navigations — a discarded nav must not poison a later mount', async () => {
  // navA is superseded and discarded; its payload write must not land on a
  // DIFFERENT navigation's view and surface in any later mount. Round 1 has no
  // discard at all, so navA commits under whatever view is current (tasks2),
  // producing a tasks2 mount carrying file/A's payload — check EVERY mount,
  // not just the first, because a later correct mount can mask an earlier
  // poisoned one.
  const h = raceHarness();
  const navA = vm.runInContext('navigate("file","A",{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('file:A'));
  assert.equal(h.fetchDeferreds.get('file:A').resolved, false, 'PRECONDITION: file/A pending');
  const navB = vm.runInContext('navigate("chat","B",{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('chat:B'));
  assert.equal(h.fetchDeferreds.get('chat:B').resolved, false, 'PRECONDITION: chat/B pending');
  const navC = vm.runInContext('navigate("tasks2",null,{transition:false})', h.ctx);
  await advanceUntil(() => h.fetchDeferreds.has('tasks2:null'));
  assert.equal(h.fetchDeferreds.get('tasks2:null').resolved, false, 'PRECONDITION: tasks2 pending');
  // B completes and mounts correctly…
  h.fetchDeferreds.get('chat:B').resolve({ id: 'B', entries: [] });
  await navB;
  // …then A resolves (discarded by the fix, but its payload write is the
  // hazard a flawed fix leaves exposed)…
  h.fetchDeferreds.get('file:A').resolve({ text: 'PAYLOAD_A' });
  await navA;
  // …then C completes — its mount must carry C's own payload, never A's
  h.fetchDeferreds.get('tasks2:null').resolve({ list: { tasks: ['C'] }, detail: null, selected: null });
  await navC;

  // Property: NO mount may carry a payload from a different navigation. A
  // file payload ({text}) on a chat or tasks2 route, or a chat payload
  // ({id,entries}) on a tasks2 route, is cross-contamination. Checking all
  // mounts catches the case where the poisoned mount is not the last one.
  const foreign = h.mounts.filter(m => {
    if (m.route === 'tasks2') return !!(m.payload && (m.payload.text || m.payload.id));
    if (m.route === 'chat') return !!(m.payload && m.payload.text);
    if (m.route === 'file') return !!(m.payload && m.payload.id);
    return false;
  });
  assert.equal(foreign.length, 0,
    'a discarded navigation poisoned a later mount; mounts=' + JSON.stringify(h.mounts));
  // The final tasks2 mount (what the user sees) must carry C's own payload.
  const tasks2Mounts = h.mounts.filter(m => m.route === 'tasks2');
  const last = tasks2Mounts[tasks2Mounts.length - 1];
  assert.ok(last && last.payload && last.payload.list,
    'tasks2 must mount with its own payload; mounts=' + JSON.stringify(h.mounts));
});
