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

   THREE causes were measured, and this one guard has to stay discriminating
   for all three — so each names its production seam and the control that
   keeps the proof of it from going hollow:
     · `client/router.js`, `travelCard`: `el.style.overflow = 'clip'`.
       Restoring `'hidden'` reds this, because `hidden` makes the travelling
       card a SCROLL CONTAINER and the sticky compose inside it stops sticking
       for the length of the travel — two jumps per travel, one when the style
       is armed and one when the +1000ms cleanup clears it. Exercised only
       when the sticky offset is doing work; the gap is measured, not assumed.
     · `client/style.css`, the `.qa` / `.qa.awaiting` pair: the rail's gutter
       is reserved in EVERY state. Putting `padding-left/margin-left` back on
       `.awaiting` moves the card's border box .9rem = 14.4px while moving no
       content, and `regroupCards` measures the border box, so the FLIP
       inverts a displacement nobody saw.
     · `client/views.js`, `travelQuestionColumn`, called from `sendAnswer` and
       `sendComment`: the column's station is recomputed AT the morph and
       travels there. Disarming it defers the whole correction to the next
       tick, which lands it in one frame. Exercised only where the question's
       visible midpoint can move — see the scroll choice below.

   PORT DISCIPLINE: own-server guard — ALWAYS ephemeral, argv[3] deliberately
   ignored. The recipe passes the port its SHARED server already holds, so
   adopting it puts this guard's own `watch.py` into EADDRINUSE before the
   first assertion: it registers and never judges, which reads as a failure
   while gating nothing (#471, #461). 39880-39899 and :35110 are refused even
   when the kernel offers one, because that range collects orphans and 35110
   is his live dashboard.

   usage: node qjank.mjs <outdir> [port, ignored]  — DW_QJANK_TRACE=1 adds the
   frame-by-frame dump, which is the artefact #863 actually asked for.
*/
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { serveVerified } from './serve.mjs';
import { mkdirSync, rmSync, cpSync, readFileSync, writeFileSync } from 'node:fs';

const OUT = outdir(process.argv);
const LIVE_DASH = 35110, GUARD_LO = 39880, GUARD_HI = 39899;
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => {
    const p = s.address().port;
    s.close(() => res(p));
  });
});
let PORT;
do { PORT = await freePort(); }
while ((PORT >= GUARD_LO && PORT <= GUARD_HI) || PORT === LIVE_DASH);
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

/* ── WHICH CLIENT IS ON THE WIRE ─────────────────────────────────────────
   Two ways a green here could be about code that is not the code under test,
   and both are one fetch away from being closed rather than assumed.

   The first is the one a #863 hand-off actually asserted: that the served
   page runs `client/dist`, so anything measured before `just build-client`
   grades an unfixed client. It is false — `watch.py` assembles the page from
   `client/*.js` and `client/style.css` at import (`_CLIENT_SRC`), inlining
   each verbatim; the page carries no `<script src>` at all and names no dist
   asset, so no built byte can reach the browser. Asserted rather than
   explained, because the explanation is exactly the kind of thing that stops
   being true without anyone noticing.

   The second is general and matters far more when this file is used as it is
   meant to be: an injection into `client/router.js` or `client/style.css`
   that never reaches the browser produces a green red-run, which reads as
   "the check cannot fail" and gets a correct check deleted. Comparing the
   wire bytes to the tree's bytes makes "did my edit reach the code under
   test" a standing assertion instead of a thing to remember. */
const ROOT = new URL('../../', import.meta.url).pathname;
const page = await (await fetch(`${BASE}/question?qid=${enc}`)).text();
const stale = ['client/router.js', 'client/style.css', 'client/views.js']
  .filter(f => !page.includes(readFileSync(ROOT + f, 'utf8')));
ok('precondition: the browser is served THIS tree\'s client, byte for byte ' +
   '— so an edit to it (a fix, or a red-proof injection) is provably on the ' +
   'wire' + (stale.length ? ` — NOT ${stale.join(', ')}` : ''),
   stale.length === 0);
ok('precondition: the page loads no external script, so `client/dist` is ' +
   'not what is running here and a stale bundle cannot explain a green ' +
   '(dist freshness is lint\'s check_client_dist, not this one)',
   !/<script[^>]*\ssrc=/i.test(page));

await p.goto(`${BASE}/question?qid=${enc}`, { waitUntil: 'networkidle' });
await waitFor(p, '#view .qa .qcompose textarea');
await sleep(1600);                       // past the route dissolve (~1.15s)

/* WHERE TO SCROLL TO, and it is the load-bearing choice in this file: one
   position has to make all three of #863's causes visible at once, and two of
   them have a precondition that a plausible scroll silently fails.

     · the scroll-container cause needs the sticky offset to be doing REAL
       work. On an unscrolled page the sticky and static tops coincide, so
       making the card a scroll container moves the box by almost nothing —
       the instrument is then structurally incapable of seeing the largest
       defect while reporting a confident count. That is not hypothetical:
       #863's second lane measured exactly that and reported "2 jumps".
     · the column-station cause needs the station to actually MOVE when the
       answer lands, and the station is the midpoint of the question's VISIBLE
       portion. With the body overflowing BOTH edges of the viewport that
       midpoint is pinned at the screen centre and growing the body changes
       nothing — measured here at scroll 400: `--qcol-top` was 364px in every
       one of 193 frames, so disarming that fix would have changed nothing and
       this guard was vacuous for the cause.

   So: put the body's BOTTOM inside the viewport, where growing it moves the
   midpoint, while its TOP stays above it, so the column is genuinely sticking
   rather than sitting where it would sit anyway. Derived from the served
   geometry rather than tuned to today's fixture, and every half asserted
   below — including the sticky-vs-static gap itself, measured rather than
   argued from the scroll offset. */
await p.evaluate(() => {
  const b = document.querySelector('#view .qa .qbody').getBoundingClientRect();
  window.scrollTo(0,
    Math.round(b.bottom + window.scrollY - window.innerHeight + 150));
});
await sleep(300);
const pre = await p.evaluate(() => {
  const card = document.querySelector('#view .qa');
  const comp = card && card.querySelector('.qcompose');
  const body = card && card.querySelector('.qbody');
  const r = e => { const b = e.getBoundingClientRect();
                   return { top: b.top, left: b.left, h: b.height, w: b.width,
                            bottom: b.bottom }; };
  /* How far the sticky offset is actually displacing the column — ASKED, not
     inferred: drop the compose to `position:static`, read where it lands, put
     it back. The scroll offset is not this number and cannot substitute for
     it; a card whose bottom has come up the screen stops sticking while still
     being scrolled past. If this is ~0 the two positions coincide and the
     scroll-container cause cannot move the box however broken it is, so this
     is the value that decides whether a green below means anything. */
  let gap = null;
  if (comp) {
    const was = comp.style.position;
    const stuck = comp.getBoundingClientRect().top;
    comp.style.position = 'static';
    const staticTop = comp.getBoundingClientRect().top;
    comp.style.position = was;
    gap = stuck - staticTop;
  }
  return {
    dual: !!document.querySelector('#qfocus.qdual'),
    sticky: comp ? getComputedStyle(comp).position : null,
    cardTop: card ? r(card).top : null,
    cardH: card ? r(card).h : null,
    bodyH: body ? r(body).h : null,
    bodyTop: body ? r(body).top : null,
    bodyBottom: body ? r(body).bottom : null,
    gap,
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
/* THE precondition. Everything below grades the box's position, and the
   largest defect displaces the box by exactly this many pixels — so a green
   over a gap of zero is not a weak result, it is no result. Stated in the
   message so the number travels with the verdict. */
ok('precondition: the sticky offset is doing real work — the compose sits ' +
   `${Math.round(pre.gap)}px above where it would sit statically, and that ` +
   'gap is the whole size of the scroll-container defect (needs > 0)',
   pre.gap > 0);
/* and the OTHER half of the scroll choice: the question's visible midpoint
   must be able to move when the answer lands inside it. */
ok('precondition: the question body overflows the TOP of the viewport but ' +
   `ends inside it (top ${Math.round(pre.bodyTop)}px, bottom ` +
   `${Math.round(pre.bodyBottom)}px, viewport ${pre.vh}px), so its visible ` +
   'midpoint — the column\'s station — moves when the answer grows it',
   pre.bodyTop < 0 && pre.bodyBottom < pre.vh);

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

/* This browser's OWN frame cadence, measured on a quiet page, so the coverage
   floor below is derived rather than tuned. A literal ("expect ~300 frames")
   is a threshold with an expiry date on a host whose load sits near 30; what
   actually has to be true is that the trace sampled at a rate comparable to
   the one this browser manages when nothing is happening — because every one
   of #863's causes lands in a SINGLE frame, and a trace that samples coarsely
   grades 0 discontinuities over a page that teleported. */
const cadence = await p.evaluate(() => new Promise(res => {
  const ts = []; const t0 = performance.now();
  const tick = () => {
    ts.push(performance.now());
    if (performance.now() - t0 < 600) requestAnimationFrame(tick);
    else res(ts.length > 1 ? (ts[ts.length - 1] - ts[0]) / (ts.length - 1) : 0);
  };
  requestAnimationFrame(tick);
}));

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

/* ── the controls ────────────────────────────────────────────────────────
   Each one asserts a precondition some part of the grade below DEPENDS on.
   They are here because this guard's whole subject is an absence — no jump —
   and an absence is what a fixture that stopped exercising the gesture also
   reports. Every one of these has a specific way the grade goes hollow. */
const JUMP_PX = 12;      // a frame of eased travel never steps this far
const first = trace[0], last = trace[trace.length - 1];
const cardGrew = first && last ? Math.abs(last.card.h - first.card.h) : 0;
ok('control: restating the card genuinely changed its height (else there ' +
   `is nothing to jump) — ${Math.round(first.card.h)}px -> ` +
   `${Math.round(last.card.h)}px, delta ${Math.round(cardGrew)}px`,
   cardGrew >= 24);
/* A frame with no textarea is skipped by BOTH the step loop and maxStep — the
   one `continue`s, the other returns its accumulator — so a window in which
   the box is absent grades "largest 0.0px, 0 discontinuities" and passes. The
   absence is the blind spot exactly where a teleport would hide. */
const missing = trace.filter(f => !f.ta).length;
ok(`control: the box was present in every sampled frame — ${missing} of ` +
   `${trace.length} missing (both the step loop and maxStep SKIP a missing ` +
   'frame, so a gap grades 0.0px and passes)', missing === 0);
/* The morph replaces the card's innerHTML, so the textarea the trace starts
   on is destroyed mid-window and every comparison after that spans a node
   swap by construction. If the swap never happened the trace is not of the
   gesture this file is named for, and "it never moved" is trivially true. */
const gens = last ? last.taGen : 0;
ok('control: the submit really replaced the textarea node, so this is a ' +
   'measurement ACROSS the morph rather than of a page that never changed ' +
   `— node generation reached ${gens}`, gens >= 2);
/* `travelCard` sets the inline overflow only when the card resizes. If it
   never armed, `clip` versus `hidden` is unexercised — restoring `hidden`
   would change nothing and the proof of that cause would come back green. */
const sawOverflow = trace.some(f => f.cardOv);
ok('control: travelCard actually armed its inline overflow during the ' +
   'window, so clip-vs-hidden is exercised (the scroll-container cause is ' +
   'invisible when it does not)', sawOverflow);
/* the rail gutter arrives with `.awaiting`; without that state change the
   border-box cause cannot be exercised either. */
const sawAwaiting = trace.some(f => /\bawaiting\b/.test(f.state || ''));
ok('control: the card entered its `awaiting` state during the window, which ' +
   'is what paints the rail into the gutter — the border-box cause is ' +
   'unexercised without it', sawAwaiting);
/* and the column's station has to MOVE, or the third cause is unexercised in
   the same silent way — measured here at scroll 400: 364px in all 193 frames. */
const qcols = trace.map(f => parseFloat(f.qcol)).filter(v => !Number.isNaN(v));
const qcolMove = qcols.length ? Math.max(...qcols) - Math.min(...qcols) : 0;
ok('control: the response column\'s station genuinely moved when the answer ' +
   `landed — ${qcolMove.toFixed(0)}px against the ${JUMP_PX}px floor, so an ` +
   'unarmed re-station would land as a discontinuity and this guard is not ' +
   'vacuous for that cause', qcolMove >= JUMP_PX);
/* and the trace has to be dense enough to SEE a one-frame teleport at all.
   A QUARTER of the idle cadence, not half: the traced window is a genuinely
   busy page — an 850ms travel, a full innerHTML morph and two ticks — so its
   frame rate is legitimately below the one measured on a quiet one, and half
   was a coin flip (109 frames against a floor of 110, on a run whose real
   verdict was two 730.8px teleports). What has to be true is that this is a
   per-FRAME trace rather than a poll: at a quarter cadence the sample gap is
   still far under the ~1000ms the defect this file was written for holds the
   box off-screen for. The gaps themselves are printed, so drift toward the
   floor is visible rather than sudden. */
const gaps = trace.slice(1).map((f, i) => f.t - trace[i].t).sort((a, b) => a - b);
const median = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0;
const frameFloor = cadence > 0 ? Math.round((WINDOW_MS / cadence) * 0.25) : 0;
ok(`control: the trace really sampled per frame — ${trace.length} frames ` +
   `over ${WINDOW_MS}ms against a floor of ${frameFloor} (a quarter of this ` +
   `browser's ${cadence.toFixed(1)}ms/frame on a quiet page); median gap ` +
   `${median.toFixed(1)}ms, worst ${(gaps[gaps.length - 1] || 0).toFixed(1)}ms. ` +
   'A before/after pair cannot see a one-frame teleport and all three causes ' +
   'land in one frame', cadence > 0 && trace.length >= frameFloor);

/* ── the sequence ───────────────────────────────────────────────────────── */
const steps = [];
for (let i = 1; i < trace.length; i++) {
  const a = trace[i - 1].ta, c = trace[i].ta;
  if (!a || !c) continue;
  const dy = c.top - a.top, dx = c.left - a.left;
  if (Math.abs(dy) >= JUMP_PX || Math.abs(dx) >= JUMP_PX)
    steps.push({ i, t: trace[i].t, dy: +dy.toFixed(1), dx: +dx.toFixed(1),
                 from: trace[i - 1], to: trace[i] });
}
/* BOTH AXES. This was `Math.abs(top - top)` and it is the one place the two
   grades disagreed: the border-box cause moves the box 14.4px SIDEWAYS and
   not a pixel down, so the largest-step grade read 7.0px and passed while the
   discontinuity grade caught it. A grade that says "no single frame moves it
   more than the travel does" and means "vertically" is a grade a purely
   lateral defect of any size walks past. Found by this file's own red-proof
   of the `.qa` gutter. */
const maxStep = trace.slice(1).reduce((m, f, i) => {
  const prev = trace[i];
  if (!f.ta || !prev.ta) return m;
  return Math.max(m, Math.abs(f.ta.top - prev.ta.top),
                     Math.abs(f.ta.left - prev.ta.left));
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
/* naming the AXIS in the summary, because a lateral jump printed as its dy
   reads `1 at t=1627.9ms (0px)` — a discontinuity of zero pixels, which is
   the summary telling a reader the opposite of what it just found. */
const px = (v, ax) => `${v > 0 ? '+' : ''}${v}px ${ax}`;
ok('the answer box never jumps: the whole submit sequence contains no ' +
   'discontinuity' + (steps.length
     ? ` — ${steps.length} at ` +
       steps.map(s => `t=${s.t}ms (` +
         [Math.abs(s.dy) >= JUMP_PX ? px(s.dy, 'down') : null,
          Math.abs(s.dx) >= JUMP_PX ? px(s.dx, 'across') : null]
           .filter(Boolean).join(', ') + ')').join(', ')
     : ''),
   steps.length === 0);

ok('no page errors' + (errs.length ? ` — ${errs.join(' | ')}` : ''),
   errs.length === 0);
await b.close();
server.kill();
finish();
