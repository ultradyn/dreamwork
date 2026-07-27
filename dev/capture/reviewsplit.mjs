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
     - a narrow window STACKS rather than crushing: one column, no bar in the
       tab order, and the question is not trapped in an inner scroller.

   usage: node reviewsplit.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
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
  const comp = q('#qdock .qcompose');
  return {
    doc: r(doc), bar: r(bar), dock: r(dock), card: r(card), frame: r(frame),
    compose: r(comp),
    docW: doc ? doc.offsetWidth : 0, dockW: dock ? dock.offsetWidth : 0,
    barShown: !!(bar && bar.checkVisibility()),
    scroll: card ? { top: card.scrollTop, client: card.clientHeight,
                     full: card.scrollHeight } : null,
    pageOver: document.documentElement.scrollHeight - window.innerHeight,
    valuenow: bar ? bar.getAttribute('aria-valuenow') : null,
    role: bar ? bar.getAttribute('role') : null,
    tabindex: bar ? bar.getAttribute('tabindex') : null,
    stored: (() => { try { return localStorage.getItem('dw.review.split'); }
                     catch (e) { return null; } })(),
  };
})()`;

const distinct = xs => new Set(xs.map(v => Math.round(v))).size;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
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
  await p.waitForSelector('.qdock > .qa', { timeout: 10000 })
    .catch(() => ok('the review route rendered a docked question at all', false));
  await sleep(700);
  return { ctx, p };
};

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
{
  // scrolling the question must not move the artifact, and must not scroll
  // the page — that pairing IS the report.
  const before = await p.evaluate(GEO);
  await p.evaluate(`document.querySelector('.qdock > .qa').scrollTop = 220`);
  await sleep(120);
  const after = await p.evaluate(GEO);
  say(`scrolling the question: card top ${before.scroll.top} -> ` +
      `${after.scroll.top}; artifact top ${before.frame.t} -> ${after.frame.t}; ` +
      `page overflow ${after.pageOver}`);
  ok('the question scrolls ALONGSIDE: it moves and the artifact does not',
     after.scroll.top >= 200 && Math.abs(after.frame.t - before.frame.t) <= 1 &&
     after.pageOver <= 1);
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
  await p.evaluate(`document.querySelector('.qdock > .qa').scrollTop = 260`);
  const before = await p.evaluate(GEO);
  const r = await p.evaluate(`(async () => {
    const card = document.querySelector('.qdock > .qa');
    await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'reviewsplit guard tick' }) });
    await tick();
    const fresh = document.querySelector('.qdock > .qa');
    return { replaced: fresh !== card, top: fresh ? fresh.scrollTop : -1 };
  })()`);
  const after = await p.evaluate(GEO);
  say(`tick: dock node replaced=${r.replaced}; card scroll ` +
      `${before.scroll.top} -> ${r.top}; doc ${before.docW} -> ${after.docW}`);
  ok('the tick really does replace the docked card (else vacuous)', r.replaced);
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
  await np.screenshot({ path: `${OUT}/reviewsplit-narrow.png` });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
