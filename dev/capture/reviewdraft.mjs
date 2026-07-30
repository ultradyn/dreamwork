/* reviewdraft — #269 acute + #269/#459 DraftStore extract + unbound boxes.

   His report, verbatim into the composer: "draft answers to questions on
   review pages can be lost ... we must have persistence and never lose work
   on an autoreload of a page." The answer box had #118's IN-MEMORY snapshot,
   which carries a half-typed answer across a tick re-render — but a RELOAD
   (an F5, or `tick` calling `location.reload()` when the server's generation
   bumps) drops the page's memory and his words with it. The composer has had
   a localStorage store for the same shape of loss since #163; the answer box
   had none. This guard proves the answer box now has one, by the SAME rules.

   TWO LOSS MODES, both driven, because a guard that proves only the reload
   would pass over the live re-render if that were the one biting him (and he
   said "autoreload", which pointed there). Reproduced first to diagnose, and
   the diagnosis is in the report: mode 2 (the tick) was already covered by
   #118's snapshot; mode 1 (the reload) was the real loss. This guard drives
   BOTH and would catch a regression in either:

     MODE 2 (live re-render)  — type into the docked box, force a tick by
       bumping .dreamwork mtime, then assert the text survives. THE NODE IS
       PROVEN RECREATED: the textarea is tagged before the re-render and the
       guard asserts the tag is gone after, so a re-render that never
       happened cannot make this check pass over the bug (the exact trap that
       hit two checks here the day this landed).
     MODE 1 (reload)          — type, reload the page for real, assert the
       text is back in the box. This is the loss he reported; it is RED on
       the pre-fix build and GREEN after.

   THE CONTRACT, asserted both ways like draft.mjs does for the composer: the
   draft survives everything EXCEPT a successful send, and is GONE after one.
   A check for only the first passes on a page that never forgets; a check
   for only the second passes on a page that saves nothing. Both, or neither.

   RUN AGAINST NOTHING FIRST: with no draft stored, the box is left empty
   rather than filled with "null" or "undefined" — the vacuous-pass trap, at
   the feature.

   THE PARTITION IS ASSERTED AT RUNTIME, not against a literal. Post-extract
   the key is `dw:draft:v1:<target>:card:<title>` (DraftStore); dual-read of
   the pre-module `dw:adraft:<target>:<title>` is proved by planting an OLD
   key, asserting it exists in the old shape, then asserting the box restores
   it after reload. Both halves are DERIVED from the live page (data.target +
   data-qid).

   #459 DISCRIMINATING CHECKS (the extract's reason to exist beyond a rename):
   `#askbox` and popout `#ptext` had NO draft at all. Prove each survives a
   REAL reload — the mode he reported, not only a re-render. A check that
   only re-proves the review dock would pass identically before and after the
   extract and prove nothing about the module.

   Shape: own target and own server on an EPHEMERAL port (#471 -- it used to
   hardcode 39894, which both lost to argv[3] in a full run and squatted inside
   the reserved 39890-39899 range),
   because the clear-on-success phase POSTs a real answer and mutates the
   fixture — pristine for the next run, and never fighting the shared guard
   server for a port.

   usage: node reviewdraft.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';
import { resolveStoreKey, waitFor } from './dom.mjs';
import { mkdirSync, rmSync, cpSync, utimesSync } from 'node:fs';
import { createServer } from 'node:net';
import { join } from 'node:path';

const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const OUT = process.argv[2];
// OWN-SERVER GUARD: ephemeral port, argv[3] ignored (#471). The old hardcoded
// 39894 was doubly wrong: in a full run argv[3]=39899 won and collided with the
// shared server, and 39894 itself sits INSIDE the reserved 39890-39899 range that
// #319 says guard servers must not squat.
const PORT = await freePort();
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const r = makeReporter();
const { ok, present, declare, finish, checks, notes, errs } = r;
declare({
  drives: '/review dock answer box (tick + reload + reject/success); ' +
          'DraftStore dual-read of a planted legacy dw:adraft key; ' +
          '/answers #askbox reload survival; popout #ptext reload survival',
  traceWindow: 'polls up to ~6s for the textarea node identity to change after ' +
               'each forced mtime bump — the natural 2s /mtime poll is the ' +
               're-render trigger, so the window must cover at least one'
});

// ── own target + own server, reaped on every exit path ───────────────────
// Fixed exclusive port 39894 (#461): spawn-and-sleep graded a squatter when
// the port was held; the prior hand-check on /data.json exited 0 on mismatch
// so it did not gate. serveVerified proves the responder is ours and throws
// (non-zero) when it is not.
const DIR = join(OUT, 'target');
const reset = () => {
  rmSync(DIR, { recursive: true, force: true });
  cpSync('dev/capture/fixture', DIR, { recursive: true });
};
reset();
const srv = await serveVerified(DIR, PORT);
const reap = () => { try { srv.kill('SIGTERM'); } catch (e) {} };
process.on('exit', reap);
process.on('SIGINT', () => { reap(); process.exit(130); });
process.on('SIGTERM', () => { reap(); process.exit(143); });

const BASE = `http://127.0.0.1:${PORT}`;
let br = null;                                   // closed on every exit path
const br_safe_close = async () => { try { if (br) await br.close(); } catch (e) {} };

br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1400, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

// the fixture's P1 open question — its title is the stable data-qid identity
const Q = 'P1 · 2026-07-25 — a second open question, so answering the first leaves a neighbour to close the gap.';
const URL = `${BASE}/review?p=.dreamwork/review/fixture-review.html&q=${encodeURIComponent(Q)}`;
const load = async () => {
  await p.goto(URL, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the #qdock the guard tags first, not a fixed sleep (#428 class)
  await waitFor(p, '#qdock');
};

// tag the live textarea node so a re-render is detectable as an identity change
const TAG = '__reviewdraft_probe';
const tagNode = () => p.evaluate((tag) => {
  const t = document.querySelector('#qdock textarea[id^="qi"]');
  if (t) t[tag] = true;
}, TAG);
// bump .dreamwork mtime so the next /mtime poll re-renders #qdock for real
const bumpMtime = () => {
  const f = join(DIR, '.dreamwork', 'lessons.md');
  const now = new Date();
  try { utimesSync(f, now, now); } catch (e) {}
};
// poll until the tagged node is gone (a genuine re-render) or the budget ends
const awaitRerender = async (budgetMs = 6000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < budgetMs) {
    await sleep(150);
    const tagged = await p.evaluate((tag) => {
      const t = document.querySelector('#qdock textarea[id^="qi"]');
      return !!(t && t[tag]);
    }, TAG);
    if (!tagged) return { recreated: true, waited: Date.now() - t0 };
  }
  return { recreated: false, waited: budgetMs };
};
const boxValue = () => p.evaluate(() => {
  const t = document.querySelector('#qdock textarea[id^="qi"]');
  return t ? t.value : null;
});
// read the stored draft key + payload, deriving the expected halves at runtime.
// `data` is a top-level `let` in the page script (a lexical global, NOT on
// window — `window.data` is undefined), so it is read as a bare identifier
// with the same typeof guard the composer's draftKey uses.
// Post-#269-extract primary key is dw:draft:v1:<target>:card:<title>; legacy
// dw:adraft: is still dual-read (proved separately by planting one).
// #476: resolved through dom.mjs's resolveStoreKey (expected read + whole
// dw:draft: family in `family`), so a moved key builder fails the partition
// checks with found-vs-expected instead of a bare "nothing was stored".
const stored = async () => {
  const id = await p.evaluate(() => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    const card = document.querySelector('#qdock .qa[data-qid]');
    const qid = card ? card.dataset.qid : '';
    const title = qid ? decodeURIComponent(qid) : '';
    return { tgt, qid, title };
  });
  const { tgt, qid, title } = id;
  const v1 = tgt && title ? 'dw:draft:v1:' + tgt + ':card:' + title : '';
  const legacy = tgt && title ? 'dw:adraft:' + tgt + ':' + title : '';
  const r = await resolveStoreKey(p, v1, 'dw:draft:');
  let found = null;
  if (r.raw) found = { key: v1, raw: r.raw, shape: 'v1' };
  if (!found && legacy) {
    const rl = await resolveStoreKey(p, legacy, 'dw:adraft:');
    if (rl.raw) found = { key: legacy, raw: rl.raw, shape: 'legacy' };
  }
  return { tgt, qid, title, v1, legacy, found, family: r.found };
};
const typeReal = async text => {
  await p.click('#qdock textarea[id^="qi"]');
  await p.fill('#qdock textarea[id^="qi"]', '');
  // type with real input events — the save hangs off `input`, so .value alone
  // would test nothing (draft.mjs's rule, one surface over)
  await p.type('#qdock textarea[id^="qi"]', text, { delay: 1 });
  await sleep(150);
};

await load();
if (!(await present(p, '#qdock textarea[id^="qi"]',
                    'the review-dock answer box'))) {
  await br_safe_close(); reap(); finish(); process.exit(0);
}

// ── against nothing, first ───────────────────────────────────────────────
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  const v = await boxValue();
  notes.push(`with nothing stored, the box holds ${JSON.stringify(v)}`);
  ok('with no draft stored, the box is left empty (not "null", not "undefined")',
     v === '');
}

const TEXT = 'half-typed answer beside the artifact, mid-thought and';

// ── MODE 2: the live re-render — the one the brief named first ───────────
{
  await typeReal(TEXT);
  // tag the CURRENT node, then force the tick that recreates #qdock
  await tagNode();
  bumpMtime();
  const re = await awaitRerender();
  notes.push(`mode 2: re-render ${re.recreated ? 'detected' : 'NOT detected'} ` +
             `after ${re.waited}ms (tagged node ${re.recreated ? 'replaced' : 'still present'})`);
  // THE PRECONDITION: if the re-render never happened, every check below is
  // about a node that was never recreated — so assert it FIRST, by name.
  ok('MODE 2 precondition: the answer-box node was genuinely recreated ' +
     '(else the survival check below proves nothing)', re.recreated);
  const v = await boxValue();
  notes.push(`mode 2: box holds ${JSON.stringify(v)} after the re-render`);
  ok('MODE 2: the draft survives the live re-render that recreated the box',
     v === TEXT);
}

// ── MODE 1: the full reload — the loss he actually reported ─────────────
{
  // freshen the text (in case anything cleared it), then reload for real
  await typeReal(TEXT);
  const pre = await boxValue();
  notes.push(`mode 1: typed ${JSON.stringify(pre)} before reload`);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1300);
  const v = await boxValue();
  notes.push(`mode 1: box holds ${JSON.stringify(v)} after reload`);
  ok('MODE 1: the draft survives a full page reload (the reported loss)',
     v === TEXT);
}

// ── the partition: key derived from BOTH target and question title ───────
{
  const s = await stored();
  notes.push(`partition: v1=${JSON.stringify(s.v1)} found=${JSON.stringify(s.found && s.found.key)}`);
  // #476: a red names the contract — expected key vs the dw:draft:* keys the
  // store actually holds — so a moved builder points at watch.py, not here.
  const held = !!(s.found && s.found.raw);
  const contract = held ? ''
    : ` — key contract: expected ${JSON.stringify(s.v1 || '(no target/title)')}, ` +
      `store holds ${s.family.length ? s.family.join(', ') : 'NO dw:draft:* keys'}`;
  ok('a draft is stored at all (the save-on-input fired)' + contract, held);
  const wrongKey = held && s.found.key !== s.v1
    ? ` — found ${JSON.stringify(s.found.key)}, expected ${JSON.stringify(s.v1)}` : '';
  ok('the draft key is the DraftStore v1 shape partitioned by target ' +
     '(dw:draft:v1:<target>:card:…)' + wrongKey,
     !!(s.found && s.found.key === s.v1));
  ok('...and by the question\'s title identity (data-qid), never the positional ' +
     'key, so a re-sort or a re-index cannot put it under the wrong question',
     !!(s.found && s.title && s.found.key.endsWith(':card:' + s.title)));
  ok('the stored payload is the JSON the helper writes (not a bare string, so ' +
     'a future field can be added without a second format)',
     !!(s.found && /^\{"t":/.test(s.found.raw)));
}

// ── dual-read of a pre-module key (old-key precondition asserted first) ──
/* The extract must not orphan a draft already in his browser. Plant ONLY a
   legacy `dw:adraft:<target>:<title>` key (the shape before DraftStore),
   assert it is present in that shape, clear any v1 key, reload, and require
   the box to restore. Production line that reds this: DraftStore.readRaw's
   legacyKey branch (or get/restore dual-read). Reachable against pre-diff
   code? No — pre-diff only reads legacy, so planting legacy and restoring
   would also pass; the discriminating half is that AFTER the extract writes
   v1 on input, dual-read still lifts a *legacy-only* key that no save has
   rewritten. The precondition (legacy key present, v1 absent) is derived
   at runtime so a hollow check cannot pass on an empty store. */
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  const planted = await p.evaluate((text) => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    const card = document.querySelector('#qdock .qa[data-qid]');
    const qid = card ? card.dataset.qid : '';
    const title = qid ? decodeURIComponent(qid) : '';
    const legacy = tgt && title ? 'dw:adraft:' + tgt + ':' + title : '';
    const v1 = tgt && title ? 'dw:draft:v1:' + tgt + ':card:' + title : '';
    if (!legacy) return { ok: false, why: 'no target/title' };
    localStorage.setItem(legacy, JSON.stringify({ t: text }));
    localStorage.removeItem(v1);
    return {
      ok: true,
      legacy, v1,
      legacyPresent: localStorage.getItem(legacy) !== null,
      v1Present: localStorage.getItem(v1) !== null
    };
  }, 'legacy-only dual-read draft for review dock');
  notes.push(`dual-read plant: ${JSON.stringify(planted)}`);
  ok('DUAL-READ precondition: a legacy dw:adraft key was planted and is present',
     !!(planted && planted.ok && planted.legacyPresent));
  ok('DUAL-READ precondition: no v1 key exists yet (else restore could come from v1)',
     !!(planted && planted.ok && planted.v1Present === false));
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1300);
  const v = await boxValue();
  notes.push(`dual-read: box holds ${JSON.stringify(v)} after reload from legacy-only key`);
  ok('DUAL-READ: a pre-module dw:adraft key restores into the dock after reload',
     v === 'legacy-only dual-read draft for review dock');
}

// ── the contract, asserted both ways ─────────────────────────────────────
/* a REJECTED send keeps it — the moment he most needs it back. The box is
   reloaded-fresh so the only draft in storage is the one this phase writes,
   and the next /answer is forced to fail the way a restarting server does. */
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  await typeReal(TEXT);
  await p.evaluate(() => {
    const real = window.fetch;
    window.fetch = (...a) => String(a[0]).indexOf('/answer') === 0
      ? Promise.resolve(new Response('no', { status: 500 }))
      : real(...a);
    document.querySelector('#qdock .qsend').click();
  });
  await sleep(600);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1300);
  const v = await boxValue();
  notes.push(`rejected send: box holds ${JSON.stringify(v)} after a 500 + reload`);
  ok('a REJECTED send keeps the draft (cleared only on durable success)', v === TEXT);
}

/* a SUCCESSFUL answer forgets it — the one moment it is safe. The real POST
   mutates the fixture (P1 gains an answer), which is why this guard owns its
   target. After it, the card leaves the open list, so the box is gone too:
   the assertion is that storage no longer holds a draft for this question. */
{
  await p.evaluate(`localStorage.clear()`);
  await load();
  await typeReal(TEXT);
  await p.evaluate(() => document.querySelector('#qdock .qsend').click());
  await sleep(800);
  const s = await stored();
  notes.push(`successful answer: stored=${JSON.stringify(s.found)} (title no ` +
             `longer open, so a fresh card may be absent — the key is what counts)`);
  // #476: assert against the resolved family too — under a moved key contract
  // a bare "expected key absent" passes vacuously while the page's own key
  // still holds the draft for this question.
  const left = s.title ? s.family.filter(k => k.endsWith(':card:' + s.title)) : [];
  ok('a SUCCESSFUL answer clears the draft (no key remains for the question)' +
     (left.length ? ` — store still holds ${left.join(', ')}` : ''),
     !(s.found && s.found.raw) && left.length === 0);
}

// ── #459: #askbox survives a real reload ─────────────────────────────────
/* Discriminating for the extract: before #459 this box stored nothing.
   Production line that reds this: bindAskDraft / DraftStore.bind for ask:main,
   or the input→save path. Pre-diff code had no save for #askbox, so a reload
   left it empty — the check is reachable against pre-diff without needing a
   seam the extract invented. */
{
  await p.evaluate(`localStorage.clear()`);
  await p.goto(`${BASE}/answers`, { waitUntil: 'networkidle' });
  await sleep(1300);
  const has = await present(p, '#askbox', 'the /answers #askbox');
  if (has) {
    const ASK = 'askbox half-typed question for the dreamer mid-thought';
    await p.click('#askbox');
    await p.fill('#askbox', '');
    await p.type('#askbox', ASK, { delay: 1 });
    await sleep(150);
    // precondition: a store key exists before we trust the reload
    // (#476: resolved with the family listing, so a red names found-vs-expected)
    const tgt = await p.evaluate(
      () => (typeof data !== 'undefined' && data && data.target) || '');
    const k = tgt ? 'dw:draft:v1:' + tgt + ':ask:main' : '';
    const pre = await resolveStoreKey(p, k, 'dw:draft:');
    notes.push(`askbox pre-reload store: key=${pre.expected} ` +
               `raw=${JSON.stringify(pre.raw)}`);
    const wrote = !!(pre.raw && pre.raw.indexOf(ASK) >= 0);
    ok('#askbox precondition: typing wrote a DraftStore key (save-on-input)' +
       (wrote ? '' : ` — key contract: expected ` +
        `${JSON.stringify(k || '(no target)')}, store holds ` +
        `${pre.found.length ? pre.found.join(', ') : 'NO dw:draft:* keys'}`),
       wrote);
    await p.reload({ waitUntil: 'networkidle' });
    await sleep(1300);
    const v = await p.evaluate(() => {
      const b = document.getElementById('askbox');
      return b ? b.value : null;
    });
    notes.push(`askbox after reload: ${JSON.stringify(v)}`);
    ok('#askbox: typed text survives a full page reload (#459)', v === ASK);
  }
}

// ── #459: popout #ptext survives a real reload of the popout document ────
/* Popout is a separate window sharing origin storage. Type into #ptext,
   plant is via real input; close and re-open popout OR reload the popout
   document and assert restore. Document PiP may be unavailable under
   headless; requestPopout falls back to window.open. Production line:
   DraftStore.bind on #ptext in requestPopout's fill. Pre-diff: no bind. */
{
  await p.evaluate(`localStorage.clear()`);
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1000);
  // ensure data.target is known so DraftStore can key
  await p.evaluate(async () => {
    if (typeof ensureData === 'function') await ensureData();
  });
  const pop = await p.evaluate(async () => {
    // open the real popout path
    if (typeof requestPopout !== 'function') return { ok: false, why: 'no requestPopout' };
    const w = await requestPopout();
    if (!w) return { ok: false, why: 'popout null' };
    return { ok: true };
  });
  notes.push(`popout open: ${JSON.stringify(pop)}`);
  // Playwright: the popout is a new page; find it
  const pages = br.contexts()[0].pages();
  let popPage = null;
  for (const pg of pages) {
    if (pg === p) continue;
    try {
      if (await pg.$('#ptext')) { popPage = pg; break; }
    } catch (e) {}
  }
  if (popPage) {
    const PT = 'popout half-typed command thought for the dream';
    await popPage.click('#ptext');
    await popPage.fill('#ptext', '');
    await popPage.type('#ptext', PT, { delay: 1 });
    await sleep(150);
    const pre = await popPage.evaluate(() => {
      // popout shares the opener's storage; data may be only on opener
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.indexOf('popout:main') >= 0) keys.push({ k, raw: localStorage.getItem(k) });
      }
      return keys;
    });
    // also check from main page (same origin)
    const preMain = await p.evaluate(() => {
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.indexOf('popout:main') >= 0) keys.push({ k, raw: localStorage.getItem(k) });
      }
      return keys;
    });
    notes.push(`ptext store keys: pop=${JSON.stringify(pre)} main=${JSON.stringify(preMain)}`);
    const hit = (preMain && preMain[0]) || (pre && pre[0]);
    ok('#ptext precondition: typing wrote a popout:main DraftStore key',
       !!(hit && hit.raw && hit.raw.indexOf(PT) >= 0));
    // close and re-open — a full reload of the popout shell
    await popPage.close();
    await p.evaluate(async () => {
      if (typeof requestPopout === 'function') await requestPopout();
    });
    await sleep(400);
    const pages2 = br.contexts()[0].pages();
    let pop2 = null;
    for (const pg of pages2) {
      if (pg === p) continue;
      try {
        if (await pg.$('#ptext')) { pop2 = pg; break; }
      } catch (e) {}
    }
    if (pop2) {
      const v = await pop2.evaluate(() => {
        const t = document.getElementById('ptext');
        return t ? t.value : null;
      });
      notes.push(`ptext after re-open: ${JSON.stringify(v)}`);
      ok('#ptext: typed text survives closing and re-opening the popout (#459)',
         v === PT);
      try { await pop2.close(); } catch (e) {}
    } else {
      ok('#ptext: re-opened popout after close (found #ptext)', false);
    }
  } else {
    notes.push('popout page not found — window.open may have been blocked');
    ok('#ptext: popout window opened with #ptext (precondition for bind test)',
       false);
  }
}

ok('no page errors', errs.length === 0);

await br_safe_close();
reap();
finish();
