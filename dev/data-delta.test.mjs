import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const router = fs.readFileSync(new URL('../client/router.js', import.meta.url), 'utf8');
const startMarker = 'function applyDataResponse(';
const endMarker = 'async function cycleBurnStep';
assert.equal(router.split(startMarker).length - 1, 1,
  'client/router.js must contain one applyDataResponse marker');
assert.equal(router.split(endMarker).length - 1, 1,
  'client/router.js must contain one following cycleBurnStep marker');
const start = router.indexOf(startMarker);
const end = router.indexOf(endMarker, start);
assert.ok(end > start, 'cycleBurnStep must follow applyDataResponse');
const productionSlice = router.slice(start, end);

const derivedPath = process.env.DREAMWORK_DELTA_CASES;
assert.ok(derivedPath, 'DREAMWORK_DELTA_CASES must name Python-derived envelopes');
const cases = JSON.parse(fs.readFileSync(derivedPath, 'utf8'));

function productionContext({data, version, mtime = 'full-version', fetch, dataJsonUrl} = {}) {
  const context = vm.createContext({
    data: structuredClone(data),
    lastDataV: version,
    lastMtime: mtime,
    dataResponseSequence: 0,
    fetch,
    dataJsonUrl,
  });
  vm.runInContext(productionSlice, context, {filename: 'client/router.js#applyDataResponse'});
  return context;
}

function apply(context, response, requestedBase) {
  context.response = structuredClone(response);
  context.requestedBase = requestedBase;
  return vm.runInContext(
    'applyDataResponse(response, requestedBase)', context);
}

function plain(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function core(value) {
  const out = {...value};
  delete out.generated;
  return out;
}

function deferredFetch() {
  const requests = [];
  function fetch(url) {
    let resolve;
    const promise = new Promise(r => { resolve = r; });
    requests.push({url, respond: body => resolve({json: async () => structuredClone(body)})});
    return promise;
  }
  return {fetch, requests};
}

function fetchData(context, forceFull = false) {
  context.forceFull = forceFull;
  return vm.runInContext('fetchDataResponse(forceFull)', context);
}

test('Python-derived production deltas reconstruct through the production browser applier', () => {
  for (const item of cases) {
    const context = productionContext({data: item.base, version: item.baseVersion});
    const rebuilt = plain(apply(context, item.response, item.baseVersion));
    assert.deepEqual(core(rebuilt), core(item.next), `${item.label}: reconstruction diverged`);
    assert.equal(context.lastDataV, item.response.v, `${item.label}: version did not advance`);
  }
});

test('base mismatch rejects the delta without mutating or advancing the held document', () => {
  const item = cases[0];
  const held = {target: '/wrong-base', tint: 'blue', survivor: true};
  const context = productionContext({data: held, version: 'other-version'});
  const rebuilt = apply(context, item.response, item.baseVersion);
  assert.equal(rebuilt, undefined,
    'base mismatch: a delta for v1 was accepted against other-version');
  assert.deepEqual(plain(context.data), held,
    'base mismatch: the held document was mutated');
  assert.equal(context.lastDataV, 'other-version',
    'base mismatch: lastDataV advanced despite rejection');
});

test('burn-step interleaving rejects an old response after a new-bucketing document lands', () => {
  const item = cases[0];
  const newBucketing = {target: '/new-bucketing', tint: 'green', survivor: true};
  const context = productionContext({data: newBucketing, version: 'new-bucketing-version'});
  const rebuilt = apply(context, item.response, item.baseVersion);
  assert.equal(rebuilt, undefined,
    'burn-step stale base: the old response committed over the new bucketing');
  assert.deepEqual(plain(context.data), newBucketing);
  assert.equal(context.lastDataV, 'new-bucketing-version');
});

test('burn-step full fetch sequences out the older in-flight tick response', async () => {
  const item = cases[0];
  const pending = deferredFetch();
  const context = productionContext({
    data: item.base,
    version: item.baseVersion,
    mtime: 'new-bucketing-version',
    fetch: pending.fetch,
    dataJsonUrl: since => since ? `/data.json?since=${since}` : '/data.json',
  });
  const oldTick = fetchData(context);
  assert.equal(pending.requests[0].url, `/data.json?since=${item.baseVersion}`);

  context.lastDataV = null;
  const burnFetch = fetchData(context, true);
  assert.equal(pending.requests[1].url, '/data.json');
  const newBucketing = {target: '/new-bucketing', tint: 'green'};
  pending.requests[1].respond(newBucketing);
  const burnResult = plain(await burnFetch);
  context.data = structuredClone(burnResult);
  assert.deepEqual(burnResult, newBucketing);
  assert.equal(context.lastDataV, 'new-bucketing-version');

  pending.requests[0].respond(item.response);
  assert.equal(await oldTick, null,
    'late tick response was not discarded after the burn-step request started');
  assert.deepEqual(plain(context.data), newBucketing,
    'late tick response replaced the new-bucketing document');
  assert.equal(context.lastDataV, 'new-bucketing-version',
    'late tick response regressed the held version');
});

test('latest base mismatch clears since and refetches the full document once', async () => {
  const item = cases[0];
  const pending = deferredFetch();
  const context = productionContext({
    data: {target: '/held'},
    version: 'other-version',
    mtime: 'full-version',
    fetch: pending.fetch,
    dataJsonUrl: since => since ? `/data.json?since=${since}` : '/data.json',
  });
  const request = fetchData(context);
  assert.equal(pending.requests[0].url, '/data.json?since=other-version');
  pending.requests[0].respond(item.response);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.lastDataV, null,
    'base mismatch did not clear the cached version before recovery');
  assert.equal(pending.requests[1].url, '/data.json',
    'base mismatch recovery retained since instead of fetching in full');

  const full = {target: '/recovered', tint: 'gold'};
  pending.requests[1].respond(full);
  assert.deepEqual(plain(await request), full);
  assert.equal(context.lastDataV, 'full-version');
});

test('base-only guard exposes the open same-version corruption false-green', () => {
  const item = cases[0];
  const corruptHeld = {...item.base, survivor: 'not in the declared base'};
  const context = productionContext({data: corruptHeld, version: item.baseVersion});
  const rebuilt = plain(apply(context, item.response, item.baseVersion));
  assert.notDeepEqual(core(rebuilt), core(item.next),
    'direction 2 precondition: corrupt held data unexpectedly reconstructed correctly');
  assert.equal(context.lastDataV, item.response.v,
    'direction 2: the base-only guard did not accept the false-green');
  assert.match(item.response.check, /^[0-9a-f]{64}$/,
    'direction 2 precondition: Python did not provide a valid target check');
});

test('base-only guard exposes the open invalid-check false-green', () => {
  const item = cases[0];
  const response = {...item.response, check: 'deliberately-wrong'};
  const context = productionContext({data: item.base, version: item.baseVersion});
  const rebuilt = plain(apply(context, response, item.baseVersion));
  assert.deepEqual(core(rebuilt), core(item.next));
  assert.equal(context.lastDataV, response.v,
    'invalid-check precondition: the currently unimplemented guard did not accept it');
});
