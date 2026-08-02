/* reviewsplit — #305: reading a review and answering its question are ONE act.

   His report, sent from /review while he was reading one: "should be able to
   scroll the question alongside a review document, and the answer/add note
   input should stay glued to the bottom in line with the bottom of the review
   document… an invisible vertical bar between review doc and question being
   answered that allows dragging left/right… we also can extend the height of
   the review doc and RHS column if the height of the window allows."

   Six claims, and the ones with motion in them are checked in the MIDDLE of
   the gesture, not at its ends (transitions.md): an end-state assertion cannot
   fail on a snap, and neither can "did it move".

     - the two columns are ONE pane: same top, same bottom, and the page does
       not scroll behind them.
     - the QUESTION scrolls in its own box — scrolling it must not move the
       artifact, which is the whole complaint.
     - the answer box is GLUED to the foot of the pane, in line with the
       artifact's bottom edge — checked as "its place in the flow is well above
       where it is painted", which a box that merely happens to be last fails.
     - the text passing UNDER it fades out, the head of the column dissolves
       once anything is above it, and both lift where his exception says they
       should. Each is a state with two ends, so each is traced part-way.
       #326 made them one mechanism — a mask on the question's body, at both
       edges — so what is traced is the two DEPTHS. Whether the fade is a fade
       or a painted band is a question about pixels and belongs to
       `qfade.mjs`; this guard owns the middle of the gesture.
     - the bar DRAGS, and the check asserts the SIGN (#174: "it moved" is
       satisfied by exactly backwards) plus conservation — what one column
       gains the other loses.
     - the bar is KEYBOARD-operable, and a keyed step TRAVELS: the count of
       distinct intermediate widths, with no frame past the final one. Under
       reduced motion the same key lands in one step with the same result —
       timing changes, function does not.
     - the width and how far he had READ both survive the live tick, which
       replaces the whole dock every two seconds (#118's rule, applied to the
       two pieces of state this feature invents).
     - the pane takes the HEIGHT THE WINDOW GIVES IT, which is a relationship
       and needs two windows plus a resize to show: 1240px grows the pane, a
       resize moves it, and 520px stops at the floor and lets the page scroll.
     - a narrow window STACKS rather than crushing: one column, no bar in the
       tab order, the question is not trapped in an inner scroller, and on a
       390px phone nothing in the pane hangs off the side.

   usage: node reviewsplit.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = []; const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});
const say = s => { notes.push(s); console.log(s); };

const data = await (await fetch(`${BASE}/data.json`)).json();
const review = (data.reviews || [])[0];
// the LONGEST open question, so "the question overflows its column" is a fact
// about the fixture rather than a hope — every check below it is vacuous
// against a question that fits.
const question = (data.questions_open || []).slice().sort((a, b) =>
  ((b.body || '').length + JSON.stringify(b.follows || []).length) -
  ((a.body || '').length + JSON.stringify(a.follows || []).length))[0];
if (!review || !question)
  throw new Error('fixture needs a review artifact and an open question');
const URL_ = `${BASE}/review?p=${encodeURIComponent(review.name)}` +
             `&q=${encodeURIComponent(question.title)}`;

/* geometry, in one shot. offsetWidth/offsetHeight are LAYOUT and cannot be
   read through a mid-flight transform; the rects are only used for "are these
   two boxes side by side", where both are read in the same space. */
const GEO = `(() => {
  const q = s => document.querySelector(s);
  const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
    return { l:+b.left.toFixed(1), t:+b.top.toFixed(1), r:+b.right.toFixed(1),
             b:+b.bottom.toFixed(1), w:+b.width.toFixed(1), h:+b.height.toFixed(1) }; };
  const doc = q('#reviewdoc'), bar = q('.rsplit'), dock = q('#qdock');
  const card = q('.qdock > .qa'), frame = q('#reviewframe');
  /* THE SCROLLER IS THE QUESTION'S BODY, not the card (#326): the card holds
     the answer box too, and a scrollport that holds the box cannot fade its
     text at the box without fading the box. */
  const body = q('.qdock > .qa > .qbody');
  const comp = q('#qdock .qcompose');
  return {
    doc: r(doc), bar: r(bar), dock: r(dock), card: r(card), frame: r(frame),
    compose: r(comp),
    docW: doc ? doc.offsetWidth : 0, dockW: dock ? dock.offsetWidth : 0,
    barShown: !!(bar && bar.checkVisibility()),
    /* increment 2. flowEnd is where the question's TEXT would end on screen if
       the scroller could show all of it. If it runs on past the scroller's own
       bottom edge while the box is still on the artifact's bottom line, the box
       is being held there — which is the only reading of "stays glued" that a
       box merely happening to be last cannot pass.
       Since #326 the box is no longer inside the scroller, so the comparison is
       against the scroller's edge rather than against the box's own bottom: it
       is glued by construction now, and this is the check that the construction
       is doing something — a card that fits needs no holding at all, and the
       SHORT question is where that reading is tested (qfade.mjs). */
    flowEnd: body ? body.getBoundingClientRect().top + body.scrollHeight
                    - body.scrollTop : null,
    scrollerEnd: body ? +body.getBoundingClientRect().bottom.toFixed(1) : null,
    sticky: comp ? getComputedStyle(comp).position : null,
    /* THE FADES ARE ONE MASK ON ONE ELEMENT (#326), so "is it drawn" is asked
       of the element that carries it: display:contents — its value on every
       route but this one — generates no box, and a mask on a box that does not
       exist is not drawn. 'boxes' is that question, and it is the reason the
       narrow rule needs no override per fade.
       #305's version asked a pseudo-element's content AND its display, because
       a content:none pseudo is never generated and still reports opacity 1;
       that trap left with the band. (No backticks in here: this whole probe is
       a template literal.) */
    qfade: body ? parseFloat(getComputedStyle(body)
                             .getPropertyValue('--qfade')) : null,
    qfoot: body ? parseFloat(getComputedStyle(body)
                             .getPropertyValue('--qfoot')) : null,
    masked: body ? getComputedStyle(body).maskImage !== 'none' : null,
    boxes: body ? body.getClientRects().length : null,
    atend: dock ? dock.classList.contains('atend') : null,
    attop: dock ? dock.classList.contains('attop') : null,
    scroll: body ? { top: body.scrollTop, client: body.clientHeight,
                     full: body.scrollHeight } : null,
    pageOver: document.documentElement.scrollHeight - window.innerHeight,
    /* how far anything IN THE PANE hangs off the right of the window. Scoped
       to the pane on purpose: the command palette overflows by 122px at 390px
       on every route including the dashboard, so a page-wide assertion here
       would gate the whole suite on somebody else's bug, in #305's name. */
    paneOverX: (() => { const W = document.documentElement.clientWidth;
      let over = 0;
      for (const el of document.querySelectorAll('#reviewwrap, #reviewwrap *'))
        over = Math.max(over, el.getBoundingClientRect().right - W);
      return Math.round(over); })(),
    innerH: window.innerHeight,
    valuenow: bar ? bar.getAttribute('aria-valuenow') : null,
    role: bar ? bar.getAttribute('role') : null,
    tabindex: bar ? bar.getAttribute('tabindex') : null,
    stored: (() => { try { return localStorage.getItem('dw.review.split'); }
                     catch (e) { return null; } })(),
  };
})()`;

const distinct = xs => new Set(xs.map(v => Math.round(v))).size;

/* trace ANY number across a gesture. Same shape as TRACE below and used for
   the two fades, which are opacity and a length rather than a width. */
const TRACEV = (expr, ms) => `new Promise(res => {
  const seen = []; const t0 = performance.now();
  (function step() {
    seen.push(+(${expr}));
    if (performance.now() - t0 < ${ms}) requestAnimationFrame(step); else res(seen);
  })();
})`;
/* frames strictly BETWEEN the two ends, with a 3% deadband so a frame that is
   really an end does not read as travel. This is the frame-rate-free half of
   the motion check: a snap has none of these at any frame rate. */
const between = (seen, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return seen.filter(v => v > lo + eps && v < hi - eps).length;
};
const DEPTH = which => `parseFloat(getComputedStyle(
  document.querySelector('.qdock > .qa > .qbody'))
    .getPropertyValue('--${which}'))`;
const QFADE = DEPTH('qfade'), QFOOT = DEPTH('qfoot');
const scrollQ = to => `(() => { const c =
  document.querySelector('.qdock > .qa > .qbody');
  c.scrollTop = ${to === 'end' ? 'c.scrollHeight' : to}; })()`;
/* How far this question can scroll, read per page rather than assumed. A
   fixed 220 silently became "scrolled to the very end" the moment the card
   grew 16px taller, which turned three fade checks green-for-the-wrong-reason
   and two red — the middle of the range has to be computed from the range. */
const scrollMax = pg => pg.evaluate(`(() => { const c =
  document.querySelector('.qdock > .qa > .qbody');
  return c.scrollHeight - c.clientHeight; })()`);

const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
  ignoreDefaultArgs: ['--hide-scrollbars'],
});
const open = async (opts = {}) => {
  const ctx = await br.newContext({
    viewport: opts.viewport || { width: 1280, height: 820 },
    reducedMotion: opts.reduced ? 'reduce' : 'no-preference' });
  if (opts.split != null)
    await ctx.addInitScript(`try { localStorage.setItem('dw.review.split',
      '${opts.split}'); } catch (e) {}`);
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL_, { waitUntil: 'networkidle' });
  // absence costs one line, not a 30s Playwright timeout that reads as "the
  // guard threw" and names nothing
  await p.waitForSelector('.qdock > .qa > .qbody', { timeout: 10000 })
    .catch(() => ok('the review route rendered a docked question at all', false));
  await sleep(700);
  return { ctx, p };
};

// Refuse to grade horizontal geometry through Playwright's normally hidden
// scrollbar. The phone review is deliberately used because it must overflow
// vertically; without overflow, a zero-width reading means "could not test".
{
  const { ctx, p } = await open({ viewport: { width: 390, height: 844 } });
  const sb = await p.evaluate(() => ({
    width: window.innerWidth - document.documentElement.clientWidth,
    scrollH: document.documentElement.scrollHeight,
    innerH: window.innerHeight,
  }));
  say(`scrollbar precondition: width ${sb.width}px, page ${sb.scrollH}px ` +
      `inside ${sb.innerH}px viewport`);
  ok(`scrollbar precondition: phone review genuinely overflows vertically `
   + `(${sb.scrollH} > ${sb.innerH}) — else scrollbar width could not be tested`,
     sb.scrollH > sb.innerH);
  ok(`scrollbar precondition: this browser's scrollbar consumes width `
   + `(sb=${sb.width}px) — else --hide-scrollbars survived ignoreDefaultArgs `
   + `and every horizontal-geometry verdict below is blind`,
     sb.scrollH > sb.innerH && sb.width > 0);
  await ctx.close();
}

/* ── one pane, two columns, and the window is full ─────────────────────── */
const { ctx: c1, p } = await open();
{
  const g = await p.evaluate(GEO);
  say(`layout: doc ${g.doc?.w}x${g.doc?.h} @${g.doc?.t}..${g.doc?.b}, ` +
      `bar ${g.bar?.w} @${g.bar?.l}, dock ${g.dock?.w} @${g.dock?.t}..${g.dock?.b}; ` +
      `card scroll ${g.scroll?.top}/${g.scroll?.client} of ${g.scroll?.full}; ` +
      `page overflow ${g.pageOver}px`);
  ok('the review route has both columns and a bar between them ' +
     '(else every check here is vacuous)',
     !!g.doc && !!g.dock && !!g.bar && g.doc.r <= g.bar.l + 1 &&
     g.bar.r <= g.dock.l + 1);
  ok('the columns are one pane: same top, same bottom',
     Math.abs(g.doc.t - g.dock.t) <= 1 && Math.abs(g.doc.b - g.dock.b) <= 1);
  // (e) — the pane grows to the window rather than stopping at 74vh
  ok('the pane fills the window rather than running off the bottom of it',
     g.pageOver <= 1 && g.doc.b >= 820 - 60);
  ok('the artifact fills its column', !!g.frame && g.frame.h >= g.doc.h - 2);
  // (a) — the premise of everything about scrolling the question
  ok('the question is taller than its column, so it must scroll ' +
     '(else the scroll checks below are vacuous)',
     !!g.scroll && g.scroll.full > g.scroll.client + 40);
}
const MAX = await scrollMax(p), HALF = Math.round(MAX / 2);
say(`the question can scroll ${MAX}px; the checks below read it at ${HALF}`);
ok('...and by enough that HALF way down is neither end (else the fade ' +
   'checks below are vacuous)', MAX >= 100);
{
  // scrolling the question must not move the artifact, and must not scroll
  // the page — that pairing IS the report.
  const before = await p.evaluate(GEO);
  await p.evaluate(scrollQ(HALF));
  await sleep(120);
  const after = await p.evaluate(GEO);
  say(`scrolling the question: card top ${before.scroll.top} -> ` +
      `${after.scroll.top}; artifact top ${before.frame.t} -> ${after.frame.t}; ` +
      `page overflow ${after.pageOver}`);
  ok('the question scrolls ALONGSIDE: it moves and the artifact does not',
     after.scroll.top >= HALF - 2 && Math.abs(after.frame.t - before.frame.t) <= 1 &&
     after.pageOver <= 1);

  /* ── (b) the answer box is GLUED to the foot of the pane ──────────────── */
  say(`glued: box ${after.compose.t}..${after.compose.b}, artifact ends ` +
      `${after.frame.b}, the scroller ends ${after.scrollerEnd}, the ` +
      `question's text runs to ${after.flowEnd} (position:${after.sticky})`);
  ok('the answer box ends in line with the bottom of the review document',
     Math.abs(after.compose.b - after.frame.b) <= 1);
  // "in line with the bottom" is also satisfied by a box that just happens to
  // be the last thing in a card that fits. This is the reading that is not:
  // there is still text below the fold, and the box is held above it.
  ok('...and it is GLUED there rather than merely last — the question runs ' +
     'on below the fold while the box stays on the artifact\'s line',
     after.flowEnd > after.scrollerEnd + 40 &&
     Math.abs(after.compose.b - after.frame.b) <= 1);
}

/* ── (c) the question fades out into the box, unless it ends there ───────── */
{
  await p.evaluate(scrollQ(0));
  await sleep(600);
  const top = await p.evaluate(GEO);
  // the head of the column fades once there is text above it and NOT before:
  // an unscrolled question shows its own title, crisply.
  ok('at the top of the question nothing is cut off and nothing is dimmed',
     top.attop === true && top.qfade <= 0.5 && top.masked === true);

  const th = p.evaluate(TRACEV(QFADE, 700));
  await sleep(60);
  await p.evaluate(scrollQ(HALF));
  const head = await th;
  await sleep(400);
  const mid = await p.evaluate(GEO);
  say(`head fade: --qfade ${head[0]} -> ${mid.qfade} over ` +
      `${between(head, head[0], head.at(-1))} of ${head.length} part-way frames`);
  ok('once he has scrolled, the first line dissolves instead of being cut',
     mid.attop === false && mid.qfade >= 12);
  ok('...and that edge ARRIVES rather than blinking on',
     between(head, head[0], head.at(-1)) >= 2);

  say(`foot fade while text passes under: --qfoot ${mid.qfoot}px, ` +
      `atend=${mid.atend}, mask drawn=${mid.masked}`);
  ok('text passing under the answer box fades out into it',
     mid.masked === true && mid.qfoot >= 12 && mid.atend === false);

  // ...unless the body ends at the box — his own exception, and a state with
  // two ends, so it crosses rather than switching (transitions.md).
  const tf = p.evaluate(TRACEV(QFOOT, 800));
  await sleep(60);
  await p.evaluate(scrollQ('end'));
  const foot = await tf;
  await sleep(400);
  const end = await p.evaluate(GEO);
  say(`at the end of the question: atend=${end.atend}, --qfoot ` +
      `${mid.qfoot} -> ${end.qfoot} over ` +
      `${between(foot, foot[0], foot.at(-1))} of ${foot.length} part-way frames`);
  ok('at the end of the question the fade lifts off his last line',
     end.atend === true && end.qfoot <= 0.5);
  ok('...having faded away rather than switched off',
     between(foot, foot[0], foot.at(-1)) >= 2);
  ok('...and the box is still glued to the foot of the pane',
     Math.abs(end.compose.b - end.frame.b) <= 2);

  // it comes back: the exception is a state, not a one-way door
  await p.evaluate(scrollQ(HALF));
  await sleep(700);
  const back = await p.evaluate(GEO);
  ok('scrolling back up brings the fade back', back.atend === false &&
     back.qfoot >= 12);
}

/* ── a POLL is not a gesture (#326) ───────────────────────────────────────
   The dashboard replaces this whole dock every two seconds, and the depths
   above TRANSITION — so a fresh dock that arrives without the state classes
   resolves 24px first and eases to its real value a style pass later. What
   that looked like: both edges of a question he was only READING dimmed and
   lifted, twice a second-and-a-half, forever. Motion with nothing behind it
   is the one thing transitions.md forbids outright, so the assertion is that
   the depth holds ONE value across a tick that really did swap the dock.
   The companion fact — that these depths can still move at all — is the
   (c) block above, which fails first if the transition is ever deleted. */
{
  const range = xs => Math.max(...xs) - Math.min(...xs);
  const settled = {};
  // three positions because each one asks a different question of the swap:
  // at the top the head is lifted and the foot is down, half way down BOTH are
  // down, and at the end the foot is lifted — and the last of those is the only
  // one where the pre-restore scroll (0) disagrees with where he actually is.
  for (const [where, to] of [['at the top', 0], ['half way down', HALF],
                             ['at the end', 'end']]) {
    await p.evaluate(scrollQ(to));
    await sleep(700);
    const before = await p.evaluate(GEO);
    // #505 p2: the dock is RECONCILED (morphdom), not replaceWith'd, so the
    // .qbody node is KEPT and a pollmark on it would persist. The render
    // generation is the universal "a render committed" signal under
    // reconciliation, so capture it before the trigger and prove it advanced.
    const gen0 = await p.evaluate(() => window.__dwViewRenderGen || 0);
    const th = p.evaluate(TRACEV(QFADE, 3200));
    const tf = p.evaluate(TRACEV(QFOOT, 3200));
    await sleep(80);
    // the real trigger: the tick re-renders when /mtime differs from what it
    // last saw. Nothing else is faked — buildCurrent, setLiveContent, the
    // restores and syncDockFade all run as they do on a loop write.
    await p.evaluate(`lastMtime = 'poll-' + Math.random()`);
    const head = await th, foot = await tf;
    await sleep(300);
    const after = await p.evaluate(GEO);
    const gen1 = await p.evaluate(() => window.__dwViewRenderGen || 0);
    const swapped = gen1 > gen0;
    say(`poll ${where}: dock re-rendered=${swapped} (gen ${gen0}->${gen1}); --qfade ${before.qfade} -> ` +
        `${after.qfade} over ${distinct(head)} value(s) ` +
        `(range ${range(head).toFixed(2)}px, ${head.length} frames); --qfoot ` +
        `${before.qfoot} -> ${after.qfoot} over ${distinct(foot)} value(s) ` +
        `(range ${range(foot).toFixed(2)}px); scroll ${before.scroll.top} -> ` +
        `${after.scroll.top}`);
    ok(`the tick really did re-render the dock ${where} ` +
       `(else this check is vacuous)`, swapped === true);
    // at the top one depth is lifted and the other is down, so the pair
    // covers both directions: a 0 that must stay 0 and a 24 that must stay 24.
    ok(`a poll does not move the head fade ${where}`,
       distinct(head) === 1 && range(head) <= 0.5 &&
       Math.abs(after.qfade - before.qfade) <= 0.5);
    ok(`a poll does not move the foot fade ${where}`,
       distinct(foot) === 1 && range(foot) <= 0.5 &&
       Math.abs(after.qfoot - before.qfoot) <= 0.5);
    ok(`...and he is still reading the same line afterwards ${where}`,
       Math.abs(after.scroll.top - before.scroll.top) <= 2);
    settled[where] = before;
  }
  // "held still" is only worth anything where there was something to hold: the
  // three positions between them pinned each depth both DOWN and LIFTED, which
  // is derived here rather than assumed of a fixture that may change length.
  ok('across the three positions each depth was pinned once down and once ' +
     'lifted, so "did not move" is a fade holding, not a fade absent',
     settled['half way down'].qfade >= 12 &&
     settled['half way down'].qfoot >= 12 &&
     settled['at the top'].qfade <= 0.5 &&
     settled['at the end'].qfoot <= 0.5);
}

/* ── the bar drags, in the direction it is dragged ─────────────────────── */
{
  const g0 = await p.evaluate(GEO);
  const box = await p.locator('.rsplit').boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.mouse.down();
  await p.mouse.move(box.x + box.width / 2 - 140, box.y + box.height / 2,
                     { steps: 12 });
  await p.mouse.up();
  await sleep(200);
  const g1 = await p.evaluate(GEO);
  say(`drag left 140px: doc ${g0.docW} -> ${g1.docW}, ` +
      `question ${g0.dockW} -> ${g1.dockW}, stored ${g1.stored}`);
  // #174: a magnitude check cannot fail on exactly backwards.
  ok('dragging the bar LEFT narrows the artifact and widens the question',
     g1.docW < g0.docW - 100 && g1.dockW > g0.dockW + 100);
  ok('...and what one column loses the other gains (the pane is unchanged)',
     Math.abs((g1.docW + g1.dockW) - (g0.docW + g0.dockW)) <= 2);
  ok('...and the bar reports its new value to assistive tech',
     +g1.valuenow < +g0.valuenow);

  // it is a preference, so it survives leaving and coming back
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(400);
  await p.goto(URL_, { waitUntil: 'networkidle' });
  await sleep(700);
  const g2 = await p.evaluate(GEO);
  say(`after a round trip through the dashboard: doc ${g2.docW} ` +
      `(was ${g1.docW}), stored ${g2.stored}`);
  ok('the width he dragged survives a route change and a reload',
     Math.abs(g2.docW - g1.docW) <= 2);
}

/* ── a keyed step TRAVELS ──────────────────────────────────────────────────
   The drag is continuous input and needs no transition — his pointer is the
   motion. A KEY is a discrete state change, so it obeys transitions.md, and
   the assertion is the one that can fail on a snap: how many distinct widths
   the column visits, and that no frame goes past where it ends up. */
const TRACE = ms => `new Promise(res => {
  const doc = document.getElementById('reviewdoc');
  const seen = []; const t0 = performance.now();
  (function step() {
    const t = performance.now() - t0;
    seen.push({ t, w: doc.getBoundingClientRect().width });
    if (t < ${ms}) requestAnimationFrame(step); else res(seen);
  })();
})`;
/* `mid` is the frame-rate-free half of this: the number of frames strictly
   BETWEEN the two ends. A snap has none of those however slowly the machine
   is drawing, while `positions` is capped by how many frames a loaded
   SwiftShader box managed inside a .38s step — which is why the count is
   printed and the threshold is 4 rather than qsec's 8 (its gesture is .85s). */
function travel(seen) {
  const ws = seen.map(s => s.w);
  const from = ws[0], final = ws.at(-1), dir = Math.sign(final - from);
  const lo = Math.min(from, final) + 1, hi = Math.max(from, final) - 1;
  return { moved: Math.abs(final - from), positions: distinct(ws),
           frames: ws.length, mid: ws.filter(v => v > lo && v < hi).length,
           over: Math.max(0, ...ws.map(v => dir * (v - final))) };
}
{
  await p.locator('.rsplit').focus();
  const t = p.evaluate(TRACE(700));
  await sleep(60);
  await p.keyboard.press('Shift+ArrowRight');       // +8% of the pane
  const seen = await t;
  const tr = travel(seen);
  say(`shift+right: the artifact column travelled ${tr.moved.toFixed(0)}px ` +
      `over ${tr.positions} distinct widths (${tr.mid} of ${tr.frames} frames ` +
      `part-way), ${tr.over.toFixed(1)}px past its end`);
  ok('a keyed step moves the columns at all (else vacuous)', tr.moved >= 60);
  // THE ASSERTION. A snap visits two widths and passes every other check here.
  ok('...and the column travels there rather than snapping',
     tr.positions >= 4 && tr.mid >= 2);
  ok('...having never gone past where it ends up', tr.over <= 2);
}
{
  // the invisible bar is not invisible to focus: it shows a hairline, and
  // that hairline ARRIVES rather than blinking on.
  await p.evaluate(`document.querySelector('.rsplit').blur()`);
  // and take the POINTER off it too. The bar follows the pointer during a
  // drag, so at the end of the drag above the cursor is sitting on the bar and
  // `:hover` is lit — "at rest" that still reads the hairline as visible, and
  // whether it does depends on a few pixels of layout, which is a flake.
  await p.mouse.move(12, 12);
  await sleep(600);
  const hair = `(() => getComputedStyle(document.querySelector('.rsplit'),
     '::after').opacity)()`;
  const rest = +await p.evaluate(hair);
  const t = p.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      seen.push(+getComputedStyle(document.querySelector('.rsplit'),
        '::after').opacity);
      if (performance.now() - t0 < 600) requestAnimationFrame(step);
      else res(seen);
    })();
  })`);
  await sleep(60);
  await p.locator('.rsplit').focus();
  await p.keyboard.press('ArrowRight');
  const seen = await t;
  const mid = seen.filter(v => v > 0.02 && v < 0.98).length;
  // the SETTLED value is read after the transition can have finished, not off
  // the last traced frame: a loaded box draws 8fps and would report a clean
  // fade as an unfinished one (that is a red about the machine, not the page)
  await sleep(500);
  const lit = +await p.evaluate(hair);
  say(`hairline: ${rest} at rest, ${lit} focused and settled, ` +
      `${mid} of ${seen.length} frames part-way in`);
  ok('the bar is invisible at rest', rest <= 0.02);
  ok('...and visible once the keyboard is on it', lit >= 0.9);
  ok('...having faded in rather than blinked on', mid >= 2);
}

/* ── his width and his place in the question survive the tick ───────────── */
{
  // let the last keyed step settle first: a width read mid-transition is not
  // a width the tick can be blamed for changing
  await sleep(700);
  /* The range is measured HERE and not reused from line 205's: the keyed steps
     above changed the split, so this column is a different width and its
     question wraps to a different height. A literal would be this guard's own
     documented failure — `scrollTop = 260` sat here until the merge, and by
     then the flex-column change had moved the range under it again. */
  const tickMax = await scrollMax(p);
  await p.evaluate(scrollQ(Math.round(tickMax / 2)));
  const before = await p.evaluate(GEO);
  // Without this the block is vacuous rather than wrong: at range 0 the
  // survival assertion below compares 0 with 0 and passes over a build with no
  // read-position carry at all. `r.replaced` does not cover it — the node is
  // replaced whether or not any scroll was ever restored.
  ok('the question can scroll far enough for a middle to exist (else vacuous)',
     tickMax > 40 && before.scroll.top > 20);
  const r = await p.evaluate(`(async () => {
    const card = document.querySelector('.qdock > .qa');
    const gen0 = window.__dwViewRenderGen || 0;
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'reviewsplit guard tick' }) });
    await tick();
    const fresh = document.querySelector('.qdock > .qa');
    const body = fresh && fresh.querySelector(':scope > .qbody');
    // #505 p2: the dock is reconciled, so the card node is KEPT (fresh ===
    // card). The render gen advancing is the proof the tick re-rendered.
    return { kept: fresh === card, rendered: (window.__dwViewRenderGen || 0) > gen0,
             top: body ? body.scrollTop : -1 };
  })()`);
  const after = await p.evaluate(GEO);
  say(`tick: dock re-rendered=${r.rendered} (card kept=${r.kept}); card scroll ` +
      `${before.scroll.top} -> ${r.top}; doc ${before.docW} -> ${after.docW}`);
  ok('the tick really does re-render the docked card (else vacuous)', r.rendered);
  ok('...and how far he had read into the question survives it',
     Math.abs(r.top - before.scroll.top) <= 2);
  ok('...and so does the width he dragged',
     Math.abs(after.docW - before.docW) <= 2);
}
await p.screenshot({ path: `${OUT}/reviewsplit.png` });
await c1.close();

/* ── reduced motion: the same key, one step, same outcome ───────────────── */
{
  const { ctx, p: rp } = await open({ reduced: true, split: 60 });
  await rp.locator('.rsplit').focus();
  const before = await rp.evaluate(GEO);
  const t = rp.evaluate(TRACE(700));
  await sleep(60);
  await rp.keyboard.press('Shift+ArrowRight');
  const seen = await t;
  const tr = travel(seen);
  const after = await rp.evaluate(GEO);
  say(`reduced: ${tr.moved.toFixed(0)}px over ${tr.positions} distinct widths ` +
      `(${before.docW} -> ${after.docW})`);
  ok('reduced motion: the keyboard still resizes the columns (function intact)',
     after.docW > before.docW + 60);
  ok('reduced motion: ...in one step, not a travel', tr.positions <= 2);

  // both fades: the STATES still hold, the travel between them does not
  await rp.evaluate(scrollQ(0));
  await sleep(400);
  // this page is 60/40, so it wraps differently and has its own range
  const rhalf = Math.round(await scrollMax(rp) / 2);
  const th = rp.evaluate(TRACEV(QFADE, 500));
  await sleep(60);
  await rp.evaluate(scrollQ(rhalf));
  const head = await th;
  const tf = rp.evaluate(TRACEV(QFOOT, 500));
  await sleep(60);
  await rp.evaluate(scrollQ('end'));
  const foot = await tf;
  await sleep(300);
  const g = await rp.evaluate(GEO);
  say(`reduced: head fade over ${distinct(head)} values, foot fade over ` +
      `${distinct(foot)}, ending atend=${g.atend} --qfoot=${g.qfoot} ` +
      `--qfade=${g.qfade}`);
  ok('reduced motion: the fades still say the same thing at rest',
     g.atend === true && g.qfoot <= 0.5 && g.qfade >= 12);
  ok('reduced motion: ...arriving in one step, both of them',
     between(head, head[0], head.at(-1)) === 0 &&
     between(foot, foot[0], foot.at(-1)) === 0);
  await ctx.close();
}

/* ── (e) the pane takes the height the window gives it ─────────────────────
   "We also can extend the height of the review doc and RHS column if the
   height of the window allows." Two windows, because the claim is a
   RELATIONSHIP between the window and the pane: one height cannot show that
   the pane follows, and 74vh passes any single-height assertion you write. */
{
  const { ctx, p: tp } = await open({ viewport: { width: 1280, height: 1240 } });
  const g = await tp.evaluate(GEO);
  say(`tall (1240px): doc ${g.doc?.w}x${g.doc?.h} ending ${g.doc?.b}, ` +
      `dock ends ${g.dock?.b}, box ends ${g.compose?.b}, ` +
      `page overflow ${g.pageOver}`);
  ok('a taller window gives a taller pane, not a taller page',
     g.doc.h > 1000 && g.pageOver <= 1 && g.doc.b >= g.innerH - 60);
  ok('...with both columns still ending together and the box on that line',
     Math.abs(g.dock.b - g.doc.b) <= 1 &&
     Math.abs(g.compose.b - g.frame.b) <= 1);

  // and it FOLLOWS the window, rather than being measured once at load
  await tp.setViewportSize({ width: 1280, height: 700 });
  await sleep(500);
  const r = await tp.evaluate(GEO);
  say(`resized to 700px: doc ends ${r.doc?.b} of ${r.innerH}, ` +
      `box ends ${r.compose?.b}, page overflow ${r.pageOver}`);
  ok('the pane follows the window when it is resized',
     r.doc.b <= r.innerH && r.doc.b >= r.innerH - 60 && r.pageOver <= 1 &&
     Math.abs(r.compose.b - r.frame.b) <= 1);
  await ctx.close();
}
{
  // ...and the floor is the other half of "if the height allows": below it the
  // PAGE scrolls again, rather than two columns becoming slivers.
  const { ctx, p: sp } = await open({ viewport: { width: 1280, height: 520 } });
  const g = await sp.evaluate(GEO);
  say(`short (520px): doc ${g.doc?.h} tall, page overflow ${g.pageOver}`);
  ok('a short window stops at the 26rem floor and lets the PAGE scroll ' +
     'instead of crushing both columns', Math.abs(g.doc.h - 416) <= 2 &&
     g.pageOver > 0);
  await ctx.close();
}

/* ── narrow stacks, it does not crush ──────────────────────────────────── */
{
  const { ctx, p: np } = await open({ viewport: { width: 700, height: 900 } });
  const g = await np.evaluate(GEO);
  say(`narrow (700px): doc ${g.doc?.w}x${g.doc?.h}, dock ${g.dock?.w} at ` +
      `y=${g.dock?.t}, bar shown=${g.barShown}, ` +
      `card ${g.scroll?.client}/${g.scroll?.full}, page overflow ${g.pageOver}`);
  ok('narrow: the columns stack instead of splitting into slivers',
     g.dock.t > g.doc.b - 2 && g.dock.w > 600);
  ok('narrow: the bar is gone, not present-but-useless', !g.barShown);
  ok('narrow: the question is a document again, not trapped in a box',
     g.scroll.full <= g.scroll.client + 1 && g.pageOver > 0);
  // nothing is glued to a column that is now just a document, and nothing
  // passes under the box, so both fades would be lying about the layout
  // ONE question answers both: the wrapper generates no box, so it is neither
  // a scrollport nor a masked element, and the box is simply the last thing in
  // a card that runs its natural height (#326).
  ok('narrow: the answer box sits at the end of the question, not glued ' +
     'over it', g.sticky === 'static' && g.boxes === 0);
  ok('narrow: and neither end of the question is dimmed', g.boxes === 0);
  await np.screenshot({ path: `${OUT}/reviewsplit-narrow.png` });
  await ctx.close();
}
{
  // a phone, where 32ch + 26ch of floors could not both fit if the split were
  // still on: nothing may hang off the side, and the answer box must be
  // reachable by scrolling the PAGE, which is what stacking is for.
  const { ctx, p: pp } = await open({ viewport: { width: 390, height: 844 } });
  const g = await pp.evaluate(GEO);
  say(`phone (390px): doc ${g.doc?.w}x${g.doc?.h}, dock ${g.dock?.w} at ` +
      `y=${g.dock?.t}, box ${g.compose?.w} wide, ` +
      `page scrolls ${g.pageOver} down, pane hangs ${g.paneOverX} off the side`);
  ok('phone: no part of the pane hangs off the side of the window',
     g.paneOverX <= 1);
  ok('phone: the artifact and the question are both full width',
     g.doc.w > 300 && g.dock.w > 300 && g.dock.t > g.doc.b - 2);
  ok('phone: the answer box is in the page rather than floating over it',
     g.sticky === 'static' && g.compose.w > 280);
  await pp.screenshot({ path: `${OUT}/reviewsplit-phone.png`, fullPage: true });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
