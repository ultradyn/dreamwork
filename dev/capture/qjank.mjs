/* qjank — #863: the answer box's POSITION through the whole submit sequence.

   His words, typed from a focus page: "the answer box on focused questions
   ... jumps all over the place. multiple times."

   That is a MOTION complaint with a plural in it, and the plural is the whole
   problem. Every instrument this repo already had for the submit morph is an
   end-state instrument: `morph` asserts the card ends answered, `qdual`
   asserts the compose is sticky and beside the body, `answers` asserts the
   text landed. A sequence that leaves and comes back passes all three, and he
   still watches it leave and come back. So this guard samples the box's
   bounding rect EVERY FRAME across the submit and grades the SEQUENCE:

     · the count of DISCONTINUITIES (a frame whose box moved further than any
       frame of eased travel ever does), and
     · the largest single-frame displacement,

   never the endpoints. A single before/after pair cannot see "multiple times"
   and will produce a confident wrong answer; that is the trap this file
   exists to not fall into. Measured on b91bb4a2 it found FOUR, all ±279.8px,
   in one submit.

   WHICH ELEMENT. `.qcompose textarea` — the box he types in and watches. The
   card `.qa` and the wrapper `.qcompose` move independently of it under
   `#qfocus.qdual` (the compose is `position:sticky` inside a grid whose row
   the card owns), so all three are traced and the report says which moved;
   the textarea is the one graded, because it is the one he means. Measured,
   the card's own top NEVER moves — only the box does, which is why a check on
   the card would have passed over every one of the four.

   WHY A JUMP FLOOR AND NOT ZERO. The travel is a real animation: `travelCard`
   interpolates the card's height for 850ms, and a sticky child riding a
   changing container may move a pixel or two per frame on purpose. A jump is
   a DISCONTINUITY — a frame that moves further than an easing curve ever does
   in one frame. 12px is a deliberate constant well under the 279.8px signal
   and well over the ~0px the settled travel produces (transitions.md: a
   motion floor is the one place a literal is right, and it gets its own
   literal per motion rather than a shared one).

   Production lines the red-proofs name (client/router.js, `travelCard`):
     · `el.style.overflow = 'clip'` — restoring `'hidden'` reds this, because
       `overflow:hidden` makes the travelling card a SCROLL CONTAINER and the
       sticky compose inside it stops sticking to the viewport for the length
       of the travel. Two jumps per travel: one when the style is armed, one
       when the +1000ms cleanup clears it.
     · the `hasSticky` guard on that same write — removing it reds the same
       check for the same reason via a different route.

   usage: node qjank.mjs <outdir> [port]   — DW_QJANK_TRACE=1 adds the
   frame-by-frame dump, which is the artefact #863 actually asked for.
*/
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { serveVerified } from './serve.mjs';
import { mkdirSync, rmSync, cpSync, readFileSync, writeFileSync } from 'node:fs';

const OUT = outdir(process.argv);
const PORT = +(process.argv[3] || 39897);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: 'the answer box\'s position through a real /question submit — the ' +
          'planted long question opened, scrolled past so its response column ' +
          'is genuinely sticking, typed into, sent, and sampled every frame',
  traceWindow: 'per-frame requestAnimationFrame from the send click to ' +
               '+5200ms — the 850ms card travel, its +1000ms style cleanup, ' +
               'the 1250ms re-render hold and the two 2s ticks after it. Long ' +
               'on purpose: this guard asserts the ABSENCE of motion, so a ' +
               'longer window can only find more, never manufacture a pass.',
});

/* Its own target, pristine: this guard ANSWERS a question for real, and it
   PLANTS the question it answers. The shared fixture's questions are all
   shorter than a viewport, and on this route that is fatal to the measurement
   rather than merely weak: `#qfocus.qdual .qa` carries `min-height:100vh`, so
   a short card's height is pinned at 100vh and answering it changes NOTHING
   the regroup can see (`travelCard` early-returns on dh < 1). Measured that
   way first, and the control below caught it — 900px -> 900px, delta 0. A card
   that cannot reflow cannot exercise the travel, so this plants one that
   overflows the viewport, the way the question he wrote this from does. */
const TARGET = `${OUT}/qjank-target`;
rmSync(TARGET, { recursive: true, force: true });
cpSync(new URL('./fixture/', import.meta.url).pathname, TARGET, { recursive: true });
const QFILE = `${TARGET}/.dreamwork/questions.md`;
const LONG_MARK = 'taller than the viewport';
{
  const para = n => `  Paragraph ${n} of a question long enough that the ` +
    `reading column overflows the viewport and the response column genuinely ` +
    `rides it rather than sitting at its static position. It wraps several ` +
    `times, which is what makes the card taller than the 100vh floor the ` +
    `focus view puts under it, so answering it changes the card's height and ` +
    `the regroup has something to travel.`;
  const body = Array.from({ length: 14 }, (_, i) => para(i + 1)).join('\n\n');
  const src = readFileSync(QFILE, 'utf8');
  const entry = `\n- **P1 · 2026-07-25 — a long open question, ${LONG_MARK}, so ` +
                `its card can genuinely reflow when answered.**\n${body}\n`;
  /* into ## Open, at its END — find the NEXT line-anchored section head rather
     than assuming this file's ordering, so a fixture that grows a section does
     not silently weld this entry into a neighbour's body (#373's rule). */
  const open = src.indexOf('\n## Open\n');
  if (open < 0) throw new Error('qjank: fixture has no "## Open" section');
  let next = src.indexOf('\n## ', open + 1);
  if (next < 0) next = src.length;
  writeFileSync(QFILE, src.slice(0, next) + entry + src.slice(next));
}

const BASE = `http://127.0.0.1:${PORT}`;
const server = await serveVerified(TARGET, PORT);

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
// 1280 wide so the min-width:1000px `.qdual` breakpoint engages — below it the
// columns stack and the compose is not sticky, which is a different page.
const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions, derived from served data ─────────────────────────────── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const openQ = (d.questions_open || []).find(
  x => !x.answer && x.title.includes(LONG_MARK));
ok('precondition: the planted long open question is served', !!openQ);
if (!openQ) { await b.close(); server.kill(); finish(); }
const enc = encodeURIComponent(openQ.title);

await p.goto(`${BASE}/question?qid=${enc}`, { waitUntil: 'networkidle' });
await waitFor(p, '#view .qa .qcompose textarea');
await sleep(1600);                       // past the route dissolve (~1.15s)

/* the compose must actually be STICKING before we grade its travel: a compose
   at its static position cannot be dislodged by a change of scroll container,
   so a green here would say nothing. Scroll down so the card's top is above
   the viewport and the sticky offset is doing work. */
await p.evaluate(() => window.scrollTo(0, 400));
await sleep(300);
const pre = await p.evaluate(() => {
  const card = document.querySelector('#view .qa');
  const comp = card && card.querySelector('.qcompose');
  const body = card && card.querySelector('.qbody');
  const r = e => { const b = e.getBoundingClientRect();
                   return { top: b.top, left: b.left, h: b.height, w: b.width }; };
  return {
    dual: !!document.querySelector('#qfocus.qdual'),
    sticky: comp ? getComputedStyle(comp).position : null,
    cardTop: card ? r(card).top : null,
    cardH: card ? r(card).h : null,
    bodyH: body ? r(body).h : null,
    vh: window.innerHeight,
  };
});
ok('precondition: the focus view is in its dual-column layout', pre.dual);
ok(`precondition: the compose column is position:sticky (is ${pre.sticky})`,
   pre.sticky === 'sticky');
/* the sticky offset only does work while the card's top is off-screen above:
   otherwise the column sits at its static position and the container swap the
   travel performs is invisible. Derived at runtime, never assumed. */
ok('precondition: the card is scrolled past, so sticky is engaged ' +
   `(card top ${Math.round(pre.cardTop)}px, needs < 0)`, pre.cardTop < 0);
ok('precondition: the question is taller than the viewport, so the column ' +
   `genuinely rides it (body ${Math.round(pre.bodyH)}px vs viewport ${pre.vh}px)`,
   pre.bodyH > pre.vh);
/* `#qfocus.qdual .qa` has min-height:100vh, so a SHORT card's height is pinned
   and answering it cannot move anything — the regroup's travel early-returns
   on dh < 1 and half this guard would be vacuous. Against the viewport
   actually running, never a literal. */
ok('precondition: the card is off its 100vh floor, so answering it can ' +
   `change its height (card ${Math.round(pre.cardH)}px vs 100vh ${pre.vh}px)`,
   pre.cardH > pre.vh + 1);

/* ── the answer, long enough that restating the card CHANGES its height ───
   A one-word answer leaves the card the size it had and there is nothing to
   jump; the control below asserts the height genuinely changed, so a fixture
   that stopped reflowing announces itself instead of passing. */
const ANSWER = ('the answer he typed, long enough to wrap several times inside ' +
  'the card once it is restated as the rendered answer, because a one-line ' +
  'answer leaves the card the height it already had and nothing below it ' +
  'moves at all. ').repeat(3).trim();

await p.evaluate(t => {
  const ta = document.querySelector('#view .qa .qcompose textarea');
  ta.focus();
  ta.value = t;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
}, ANSWER);
await sleep(400);                        // the autogrow settles

/* ── the instrument ──────────────────────────────────────────────────────
   Sample every frame, RE-QUERYING each subject: the submit morph replaces the
   card's innerHTML, so the textarea the trace started on is destroyed
   mid-window. A held reference would trace a detached node whose rect is all
   zeros — which reads as a colossal jump and is an artefact. Node identity is
   counted (`taGen`) so the report can say where the swap happened, and the
   card's inline height/overflow ride along so each jump names its trigger. */
await p.evaluate(() => {
  window.__jank = { frames: [], t0: 0, stop: 0 };
  let taSeen = null, taGen = 0;
  const rect = e => { if (!e) return null; const b = e.getBoundingClientRect();
    return { top: +b.top.toFixed(2), left: +b.left.toFixed(2),
             h: +b.height.toFixed(2), w: +b.width.toFixed(2) }; };
  const tick = () => {
    const now = performance.now();
    if (window.__jank.t0 && now > window.__jank.stop) return;
    const card = document.querySelector('#view .qa');
    const comp = card && card.querySelector('.qcompose');
    const ta = comp && comp.querySelector('textarea');
    if (ta && ta !== taSeen) { taSeen = ta; taGen++; }
    window.__jank.frames.push({
      t: window.__jank.t0 ? +(now - window.__jank.t0).toFixed(1) : null,
      ta: rect(ta), comp: rect(comp), card: rect(card),
      taGen,
      qcol: document.body.style.getPropertyValue('--qcol-top') || '',
      cardH: card ? card.style.height : '',
      cardOv: card ? card.style.overflow : '',
      cardTf: card ? card.style.transform : '',
      state: card ? card.className : '',
    });
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
});

const WINDOW_MS = 5200;
await p.evaluate(ms => {
  window.__jank.t0 = performance.now();
  window.__jank.stop = window.__jank.t0 + ms;
  window.__jank.frames.length = 0;
  document.querySelector('#view .qa .qcompose .qsend').click();
}, WINDOW_MS);
await sleep(WINDOW_MS + 500);

const trace = await p.evaluate(() => window.__jank.frames);

/* ── the write actually landed ───────────────────────────────────────────
   A failed submit does not move the box either, so every no-jank assertion
   below passes on a broken send. Read the answer back off the SERVER, not off
   the page: the morph restates the card from local data and would say the
   answer is there whether or not it was ever written. */
const after = await (await fetch(`${BASE}/data.json`)).json();
const wrote = [...(after.questions_open || []), ...(after.answered_entries || [])]
  .find(x => x.title === openQ.title);
const posted = !!(wrote && (wrote.answer || '').includes('the answer he typed'));
ok('the answer was actually posted, read back off the SERVER (else every ' +
   'check below is vacuous)', posted);

/* ── the control: the card genuinely reflowed ────────────────────────────── */
const first = trace[0], last = trace[trace.length - 1];
const cardGrew = first && last ? Math.abs(last.card.h - first.card.h) : 0;
ok('control: restating the card genuinely changed its height (else there ' +
   `is nothing to jump) — ${Math.round(first.card.h)}px -> ` +
   `${Math.round(last.card.h)}px, delta ${Math.round(cardGrew)}px`,
   cardGrew >= 24);

/* ── the sequence ───────────────────────────────────────────────────────── */
const JUMP_PX = 12;      // a frame of eased travel never steps this far
const steps = [];
for (let i = 1; i < trace.length; i++) {
  const a = trace[i - 1].ta, c = trace[i].ta;
  if (!a || !c) continue;
  const dy = c.top - a.top, dx = c.left - a.left;
  if (Math.abs(dy) >= JUMP_PX || Math.abs(dx) >= JUMP_PX)
    steps.push({ i, t: trace[i].t, dy: +dy.toFixed(1), dx: +dx.toFixed(1),
                 from: trace[i - 1], to: trace[i] });
}
const maxStep = trace.slice(1).reduce((m, f, i) => {
  const prev = trace[i];
  if (!f.ta || !prev.ta) return m;
  return Math.max(m, Math.abs(f.ta.top - prev.ta.top));
}, 0);

if (process.env.DW_QJANK_TRACE) {
  const rows = trace.map((f, i) =>
    `${String(i).padStart(4)} t=${String(f.t).padStart(7)}ms ` +
    `ta.top=${f.ta ? String(f.ta.top).padStart(8) : '  (none)'} ` +
    `ta.left=${f.ta ? String(f.ta.left).padStart(7) : ' (none)'} ` +
    `ta.h=${f.ta ? String(f.ta.h).padStart(7) : '   -   '} ` +
    `comp.top=${f.comp ? String(f.comp.top).padStart(8) : '  (none)'} ` +
    `card.top=${f.card ? String(f.card.top).padStart(9) : '  (none)'} ` +
    `card.left=${f.card ? String(f.card.left).padStart(7) : ' (none)'} ` +
    `card.h=${f.card ? String(f.card.h).padStart(8) : '   -   '} ` +
    `tf=${(f.cardTf || '-').padEnd(24)} ` +
    `gen=${f.taGen} qcol=${(f.qcol || '-').padStart(7)} ` +
    `inl(h=${f.cardH || '-'},ov=${f.cardOv || '-'}) ${f.state}`);
  notes.push(['── frame trace (DW_QJANK_TRACE) ──', ...rows].join('\n'));
}
notes.push(`frames sampled: ${trace.length} over ${WINDOW_MS}ms; ` +
      `largest single-frame move of the box: ${maxStep.toFixed(1)}px; ` +
      `discontinuities (>= ${JUMP_PX}px in one frame): ${steps.length}`);
for (const s of steps)
  notes.push(`  jump @frame ${s.i} t=${s.t}ms  dy=${s.dy}px dx=${s.dx}px  ` +
        `box.top ${s.from.ta.top} -> ${s.to.ta.top}  ` +
        `[card inline height ${s.from.cardH || 'none'} -> ${s.to.cardH || 'none'}, ` +
        `overflow ${s.from.cardOv || 'none'} -> ${s.to.cardOv || 'none'}, ` +
        `qcol ${s.from.qcol || 'none'} -> ${s.to.qcol || 'none'}, ` +
        `gen ${s.from.taGen}->${s.to.taGen}]`);

/* THE grade, and it is over the whole sequence rather than the endpoints: a
   box that leaves and returns has identical endpoints and he still watched it
   go. Both halves are asserted because either alone is passable — one huge
   move is a single discontinuity, and a dozen small ones never exceed a
   per-frame ceiling. */
ok('the answer box never jumps: no single frame moves it more than the ' +
   `travel does — largest ${maxStep.toFixed(1)}px, floor ${JUMP_PX}px`,
   maxStep < JUMP_PX);
ok('the answer box never jumps: the whole submit sequence contains no ' +
   'discontinuity' + (steps.length
     ? ` — ${steps.length} at ` +
       steps.map(s => `t=${s.t}ms (${s.dy > 0 ? '+' : ''}${s.dy}px)`).join(', ')
     : ''),
   steps.length === 0);

ok('no page errors' + (errs.length ? ` — ${errs.join(' | ')}` : ''),
   errs.length === 0);
await b.close();
server.kill();
finish();
