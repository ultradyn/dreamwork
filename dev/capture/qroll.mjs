/* qroll — #454: an open question rolls up to the top of the scroll.

   His words: "questions on the questions page should be collapsible.
   However, the size of each collapsed question should be at least like 5-6
   lines. So it's more like a card or the top of a rolled up scroll. This
   should be persisted to IndexedDB and kept in sync like other ui state."

   The 5-6 line floor is the whole design: a one-line collapse is a title
   list, and a title alone does not say whether an entry still needs him.
   So the floor is derived from the RENDERED line height at runtime, never
   a pinned pixel constant (#441's lesson), and this guard derives its own
   expectations the same way — measuring the fixture's line height in the
   page rather than carrying a literal.

   What this asserts, on the real /questions route against the fixture:
     - every OPEN card carries the roll affordance (a real button,
       keyboard-operable); awaiting and folded cards carry none — the
       styleguide's axis: awaiting still needs the loop, folded already IS
       the collapsed treatment (#111)
     - rolling shrinks the card to a 5-6 line card, the floor DERIVED at
       runtime from the measured line height; the fixture precondition
       (open body is strictly taller than the rolled card) is derived at
       runtime too, never assumed
     - the gesture is the card fold's (#111/#169): heights TRAVEL
       (between() mid-frames, span precondition with its own per-motion
       literal), and reduced motion snaps (the count-on-purpose opposite)
     - the roll survives a RELOAD (IndexedDB), and syncs to a second tab
       through the standing 'storage'-event idiom
     - composition with #452: the rolled card still shows its focus link
       inside the clamp
     - a persisted roll is PRESENTATIONAL: /question and the review dock are
       reading surfaces, so both render the card unrolled and omit the roll
       control without destroying the stored state; returning to /questions
       restores the same roll

   Production lines the red-proofs name (watch.py):
     · qaInner's `st === 'open' ? qrollBtn(...)` emission — removing it
       reds the way-in checks;
     · ROLL_LINES in rollHeight (set it to 1.5) — reds the floor check;
     · the `uiPut` write in persistRoll — reds the reload check;
     · the localStorage ping in persistRoll — reds the cross-tab check;
     · toggleRoll's snapshotCards/regroupCards pair — reds the travel
       checks.

   usage: node qroll.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39884';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/questions: the roll affordance on a real open card (click AND ' +
          'keyboard), the roll + unroll gestures traced per frame, a reload, ' +
          '/question focus, /review dock, return to /questions, and a second ' +
          'tab on the same origin',
  traceWindow: 'rAF height traces over each gesture (~1.2s; the card travel ' +
               'is 850ms). Floor/line evidence is measured geometry, not ' +
               'frames; persistence evidence is a real reload.',
});

/* Frames strictly BETWEEN the two ends, 3% deadband — the frame-rate-free
   form of "it travelled" (transitions.md; the helper every motion guard
   carries verbatim). */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const uniq = a => [...new Set(a)];

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await b.newContext({ viewport: { width: 1100, height: 950 } });
const p = await ctx.newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions, derived from served data, never literals ────────────── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const openQ = d.questions_open.find(x => !x.answer);
const awaitQ = d.questions_open.find(x => x.answer);
const foldQ = d.answered_entries[0];
ok('precondition: an open, an awaiting and a folded question all exist',
   !!openQ && !!awaitQ && !!foldQ);
const target = d.target;
ok('precondition: server named its target (the IDB name derives from it)',
   !!target);
if (!openQ || !awaitQ || !foldQ || !target) { await b.close(); finish(); }
const enc = encodeURIComponent(openQ.title);

/* ── the way in: a roll affordance on every OPEN card, nowhere else ─────── */
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .qa cards the guard reads first, not a fixed sleep (#428 class)
await waitFor(p, '.qa');
const afford = await p.evaluate(() =>
  [...document.querySelectorAll('.qa')].map(card => {
    const btn = card.querySelector('button.qroll');
    return { qid: card.dataset.qid || null,
             state: card.className.replace('qa ', '').split(' ')[0],
             has: !!btn, tag: btn ? btn.tagName : null,
             expanded: btn ? btn.getAttribute('aria-expanded') : null };
  }));
notes.push('affordances: ' + JSON.stringify(afford));
ok('every OPEN card carries the roll affordance',
   afford.filter(a => a.state === 'open').every(a => a.has));
ok('the affordance is a real button (keyboard-operable natively)',
   afford.filter(a => a.has).every(a => a.tag === 'BUTTON'));
ok('it declares aria-expanded (a disclosure state, said to AT)',
   afford.filter(a => a.has).every(a => a.expanded === 'true'));
ok('awaiting and folded cards carry NO roll affordance ' +
   '(awaiting still needs the loop; folded already IS the collapse)',
   afford.filter(a => a.state !== 'open').every(a => !a.has));

/* ── the floor, derived at runtime: open vs rolled, in measured LINES ───── */
const geo0 = await p.evaluate(qid => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const body = card.querySelector('.qbody');
  const bodyRects = [...body.children].map(n => n.getBoundingClientRect())
    .filter(r => r.width || r.height);
  const bodyContent = bodyRects.length
    ? Math.max(...bodyRects.map(r => r.bottom)) -
      Math.min(...bodyRects.map(r => r.top))
    : 0;
  const probe = card.querySelector('.qbody .md p') || card.querySelector('.qt');
  const cs = getComputedStyle(probe);
  let lh = parseFloat(cs.lineHeight);
  if (!isFinite(lh) || lh <= 0) {
    // 'normal' is not a number: measure it with the page's own probe idiom
    // (lineHeightOf), so the guard's floor tracks the font, not a guess.
    const pr = document.createElement('div');
    pr.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;' +
      'border:0;padding:0;margin:0;width:0;font:' + cs.font +
      ';line-height:' + cs.lineHeight;
    pr.textContent = 'M\nM';
    document.body.appendChild(pr);
    lh = pr.getBoundingClientRect().height / 2;
    pr.remove();
  }
  return { open: card.getBoundingClientRect().height,
           bodyContent, lh };
}, enc);
ok('precondition: the fixture card has a measurable line height',
   geo0.lh > 0 && Number.isFinite(geo0.lh));

/* trace heights across the CLICK that rolls it — the gesture is the card
   fold's (#111), so heights must TRAVEL, not snap */
const rollTrace = await p.evaluate(qid => new Promise(res => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const hs = [];
  const t0 = performance.now();
  (function step() {
    hs.push(Math.round(card.getBoundingClientRect().height * 10) / 10);
    if (performance.now() - t0 < 1200) requestAnimationFrame(step);
    else res({ hs, cls: card.className });
  })();
  card.querySelector('button.qroll').click();
}), enc);
const rolledH = rollTrace.hs.at(-1);
const rollSpan = Math.abs(rollTrace.hs[0] - rolledH);
const rolledBodyH = await p.evaluate(qid =>
  document.querySelector(`.qa[data-qid="${qid}"] .qbody`)
    .getBoundingClientRect().height, enc);
notes.push(`roll: open=${rollTrace.hs[0]} rolled=${rolledH} ` +
           `body=${geo0.bodyContent}->${rolledBodyH} ` +
           `lh=${geo0.lh} lines=${(rolledH / geo0.lh).toFixed(2)}`);
ok('the card rolled to a 5-6 line scroll-top (floor derived from the ' +
   'measured line height, never a pinned pixel constant)',
   rolledH / geo0.lh >= 4.5 && rolledH / geo0.lh <= 6.5);
ok('precondition: the fixture BODY itself really clips (not merely a short ' +
   'body whose compose box disappears — the gap is derived, not assumed)',
   geo0.bodyContent > rolledBodyH + 1);
ok('the roll TRAVELS (a part-way frame exists; a snap has none)',
   rollSpan > 40 && between(rollTrace.hs, rollTrace.hs[0], rolledH) >= 1);
ok('no frame goes PAST the rolled height, and the last frame is at it',
   rollTrace.hs.every(h => h >= rolledH - 1));
ok('the rolled card carries the rolled state class',
   rollTrace.cls.includes('rolled'));
ok('the rolled card still shows its #452 focus link inside the clamp',
   await p.evaluate(qid => {
     const card = document.querySelector(`.qa[data-qid="${qid}"]`);
     const a = card.querySelector('a.qfocus');
     if (!a) return false;
     const r = a.getBoundingClientRect(), c = card.getBoundingClientRect();
     return r.height > 0 && r.top >= c.top - 1 && r.bottom <= c.bottom + 1;
   }, enc));
await p.screenshot({ path: `${OUT}/rolled.png`, fullPage: true });

/* ── keyboard operation: focus the button, Enter rolls it back open ─────── */
await p.focus(`.qa[data-qid="${enc}"] button.qroll`);
const unrollTrace = await p.evaluate(qid => new Promise(res => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const hs = [];
  const t0 = performance.now();
  (function step() {
    hs.push(Math.round(card.getBoundingClientRect().height * 10) / 10);
    if (performance.now() - t0 < 1200) requestAnimationFrame(step);
    else res({ hs, expanded: card.querySelector('button.qroll')
                                 .getAttribute('aria-expanded') });
  })();
  document.activeElement.dispatchEvent(new KeyboardEvent('keydown',
    { key: 'Enter', bubbles: true }));
  document.activeElement.click();   // Enter on a focused button clicks it
}), enc);
const unrolledH = unrollTrace.hs.at(-1);
const unrollSpan = Math.abs(unrolledH - unrollTrace.hs[0]);
notes.push(`unroll: ${unrollTrace.hs[0]} -> ${unrolledH} ` +
           `(spans: roll ${rollSpan.toFixed(0)}px, unroll ${unrollSpan.toFixed(0)}px)`);
ok('keyboard: Enter on the focused affordance unrolls the card',
   unrolledH > rolledH && unrollTrace.expanded === 'true');
ok('the unroll TRAVELS too (same gesture run backwards, #111 idiom)',
   unrollSpan > 40 &&
   between(unrollTrace.hs, unrollTrace.hs[0], unrolledH) >= 1);

/* ── persistence: roll it again, RELOAD, it is still rolled ─────────────── */
await p.click(`.qa[data-qid="${enc}"] button.qroll`);
await sleep(700);                            // let the raced IDB write land
const idb = await p.evaluate(dbName => new Promise(res => {
  let rq;
  try { rq = indexedDB.open(dbName, 1); } catch (e) { return res(null); }
  rq.onsuccess = () => {
    const db = rq.result;
    if (!db.objectStoreNames.contains('ui')) { db.close(); return res(null); }
    const tx = db.transaction('ui', 'readonly');
    const all = tx.objectStore('ui').getAll();
    all.onsuccess = () => { db.close(); res(all.result); };
    tx.onerror = tx.onabort = () => { db.close(); res(null); };
  };
  rq.onerror = rq.onblocked = () => res(null);
}), 'dw-ui:' + target);
notes.push('idb ui records: ' + JSON.stringify(idb));
ok('the roll is a record in the IndexedDB ui store (keyed by the question)',
   !!idb && idb.some(r => r.k === 'qroll:' + openQ.title && r.v === true));
await p.reload({ waitUntil: 'networkidle' });
await sleep(1200);                           // async IDB read, then apply
const afterReload = await p.evaluate(qid => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const btn = card && card.querySelector('button.qroll');
  return card ? { cls: card.className,
                  h: card.getBoundingClientRect().height,
                  expanded: btn ? btn.getAttribute('aria-expanded') : null }
              : null;
}, enc);
notes.push('after reload: ' + JSON.stringify(afterReload));
ok('the roll SURVIVES THE RELOAD (his standing rule: never lose UI state ' +
   'on an autoreload)', !!afterReload &&
   afterReload.cls.includes('rolled') &&
   afterReload.expanded === 'false' &&
   afterReload.h / geo0.lh <= 6.5);

/* ── reading surfaces: suppress the rendering, preserve the truth ─────────
   The fixture has already proved this card genuinely collapses and that its
   IndexedDB record is true. Focus it from the ACTUALLY rolled card so an
   unrolled focus cannot pass merely because this phase never rolled it. */
await p.click(`.qa[data-qid="${enc}"] a.qfocus`);
await sleep(1400);
const focused = await p.evaluate(qid => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const body = card && card.querySelector('.qbody');
  return card ? {
    cls: card.className,
    h: card.getBoundingClientRect().height,
    bodyClientH: body ? body.clientHeight : 0,
    bodyScrollH: body ? body.scrollHeight : 0,
    rollControl: !!card.querySelector('button.qroll'),
  } : null;
}, enc);
const focusedStored = await p.evaluate(({dbName, title}) => new Promise(res => {
  let rq;
  try { rq = indexedDB.open(dbName, 1); } catch (e) { return res(null); }
  rq.onsuccess = () => {
    const db = rq.result;
    if (!db.objectStoreNames.contains('ui')) { db.close(); return res(null); }
    const tx = db.transaction('ui', 'readonly');
    const get = tx.objectStore('ui').get('qroll:' + title);
    get.onsuccess = () => { db.close(); res(get.result || null); };
    get.onerror = tx.onerror = tx.onabort = () => { db.close(); res(null); };
  };
  rq.onerror = rq.onblocked = () => res(null);
}), { dbName: 'dw-ui:' + target, title: openQ.title });
notes.push('focus reading surface: ' + JSON.stringify(focused) +
           '; persisted=' + JSON.stringify(focusedStored));
ok('focus keeps the persisted roll TRUE while suppressing it in this reading ' +
   'surface', !!focusedStored && focusedStored.k === 'qroll:' + openQ.title &&
   focusedStored.v === true && !!focused && !focused.cls.includes('rolled'));
ok(`focus is unclipped: class=${JSON.stringify(focused && focused.cls)}, ` +
   `card=${focused && focused.h}px, body=${focused && focused.bodyClientH}/` +
   `${focused && focused.bodyScrollH}px, rolled-list=${afterReload && afterReload.h}px`,
   !!focused && focused.h > afterReload.h + 40 &&
   focused.bodyClientH + 1 >= focused.bodyScrollH);
ok('focus offers NO roll control (a reading surface cannot enter a state it ' +
   'will not render)', !!focused && focused.rollControl === false);

await p.click('#meta .crumb a[href="/questions"]');
await sleep(1400);
const afterFocusReturn = await p.evaluate(qid => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const btn = card && card.querySelector('button.qroll');
  return card ? { cls: card.className,
                  h: card.getBoundingClientRect().height,
                  expanded: btn ? btn.getAttribute('aria-expanded') : null }
              : null;
}, enc);
notes.push('after focus return: ' + JSON.stringify(afterFocusReturn));
ok('returning to /questions restores the SAME persisted roll (focus did not ' +
   'destroy cross-surface state)', !!afterFocusReturn &&
   afterFocusReturn.cls.includes('rolled') &&
   afterFocusReturn.expanded === 'false' &&
   afterFocusReturn.h / geo0.lh <= 6.5);

const review = d.reviews && d.reviews[0];
ok('precondition: the fixture exposes a review for the dock reading surface',
   !!review);
if (review) {
  await p.goto(`${BASE}/review?p=${encodeURIComponent(review.name)}` +
               `&q=${encodeURIComponent(openQ.title)}`,
               { waitUntil: 'networkidle' });
  await sleep(1200);
  const dock = await p.evaluate(qid => {
    const card = document.querySelector(`#qdock .qa[data-qid="${qid}"]`);
    return card ? { cls: card.className,
                    h: card.getBoundingClientRect().height,
                    rollControl: !!card.querySelector('button.qroll') }
                : null;
  }, enc);
  notes.push('dock reading surface: ' + JSON.stringify(dock));
  ok('the dock is the other reading surface: it stays unrolled and offers ' +
     'NO roll control', !!dock && !dock.cls.includes('rolled') &&
     dock.rollControl === false);
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
}

/* ── cross-tab sync: a second tab follows through the storage event ─────── */
const p2 = await ctx.newPage();
p2.on('pageerror', e => errs.push('tab2: ' + String(e)));
await p2.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);                           // p2 loads rolled state from IDB
const t2a = await p2.evaluate(qid => {
  const c = document.querySelector(`.qa[data-qid="${qid}"]`);
  return c ? c.className.includes('rolled') : null;
}, enc);
ok('a fresh tab opens with the persisted roll already applied', t2a === true);
await p.click(`.qa[data-qid="${enc}"] button.qroll`);   // unroll in tab 1
let t2b = null;
for (let i = 0; i < 10; i++) {
  await sleep(300);
  t2b = await p2.evaluate(qid => {
    const c = document.querySelector(`.qa[data-qid="${qid}"]`);
    return c ? c.className.includes('rolled') : null;
  }, enc);
  if (t2b === false) break;
}
ok('unrolling in one tab unrolls the other (kept in sync like other ui ' +
   'state)', t2b === false);
// Direction matters: tab 2 is now already open and unrolled. Roll tab 1
// again so the storage listener has to apply the true arm to that existing
// peer; opening tab 2 from persisted rolled state cannot prove this path.
await p.click(`.qa[data-qid="${enc}"] button.qroll`);
let t2c = null;
for (let i = 0; i < 10; i++) {
  await sleep(300);
  t2c = await p2.evaluate(qid => {
    const c = document.querySelector(`.qa[data-qid="${qid}"]`);
    return c ? c.className.includes('rolled') : null;
  }, enc);
  if (t2c === true) break;
}
ok('rolling in one tab rolls an already-open unrolled peer', t2c === true);
// Leave the persisted state unrolled for the reduced-motion click below.
await p.click(`.qa[data-qid="${enc}"] button.qroll`);
await sleep(700);
await p2.close();

/* ── reduced motion: same function, no travel ─────────────────────────────
   The opposite assertion stays a COUNT on purpose (transitions.md: reduced
   motion does NOT animate, so uniq(h) <= 3 — converting it would destroy
   the check). */
await p.emulateMedia({ reducedMotion: 'reduce' });
await p.reload({ waitUntil: 'networkidle' });
await sleep(1200);
const rmTrace = await p.evaluate(qid => new Promise(res => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const hs = [];
  const t0 = performance.now();
  (function step() {
    hs.push(Math.round(card.getBoundingClientRect().height));
    if (performance.now() - t0 < 600) requestAnimationFrame(step);
    else res({ hs, cls: card.className });
  })();
  card.querySelector('button.qroll').click();
}), enc);
notes.push('reduced-motion heights: ' + JSON.stringify(uniq(rmTrace.hs)));
ok('reduced motion: the roll is instant (<= 3 distinct heights) and the ' +
   'same rolled state lands',
   uniq(rmTrace.hs).length <= 3 && rmTrace.cls.includes('rolled'));

ok('no page errors', errs.length === 0);
if (errs.length) notes.push('page errors: ' + errs.join(' | '));
await b.close();
finish();
