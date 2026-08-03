/* qdual — #583: the dual-column /question focus view, asserted in the real DOM.

   The focus view splits the shared question card into two columns — question
   body left, answer/note compose right (taller than normal) — so the response
   is always present while he reads. The split is CSS-driven and scoped to
   #qfocus.qdual because qaCard is the one component the dashboard, /questions
   and the dock all render through; only the focus container opts the same
   card into two columns, so the dashboard is UNCHANGED. This guard proves
   both halves in a real browser: the focus card renders the body and compose
   SIDE BY SIDE (rendered geometry, not the grid-column declaration — see
   below), the compose is sticky with a taller-than-normal field, and a
   dashboard card is stacked. pytest cannot see rendered structure, so this is
   the authoritative geometry check; the source contract it is built from is
   test_question_dual_column.py.

   Why RENDERED geometry and not grid-column-start: the `grid-column` property
   computes to its declared value ('1'/'2') whether or not the parent actually
   grids the item, so a check on `getComputedStyle(body).gridColumnStart`
   passes over the very bug it stands beside (the parent collapsing to block).
   The contract is that the two are drawn side by side, so the guard measures
   their rects: the compose starts to the right of the body AND their vertical
   ranges overlap. A stacked layout (display:block) fails both — the compose
   sits at the body's left edge, below it.

   Production lines the red-proofs name (client):
     · `display:grid` on the `#qfocus.qdual` rule in style.css — removing it
       reds "body and compose are side by side" (the card collapses to a
       stacked block). `grid-template-columns` alone does NOT red it (a grid
       with two children auto-makes two columns), which is why the line named
       is display:grid, not the template;
     · the `qdual` class on #qfocus in the registered native Question
       component — removing it reds the same check (the CSS keys off .qdual);
     · `min-height:9rem` on the focus textarea — removing it reds the
       "taller than normal" check.

   The breakpoint (min-width:1000px) is why the viewport is 1280×900: below it
   the columns stack on purpose, so a guard that ran narrow would assert the
   degraded layout rather than the feature.

   usage: node qdual.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39886';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const { mkdirSync } = await import('node:fs');
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: 'the dual-column /question focus view in a real browser — body and ' +
          'compose rendered side by side, compose sticky and taller than ' +
          'normal, and the dashboard card stacked (unchanged)',
  traceWindow: 'no frame traces: this is a structural assertion on computed ' +
               'styles and rendered rects, read once after settle (~1.4s ' +
               'past the dissolve).',
});

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
// 1280 wide so the min-width:1000px breakpoint engages (below it the columns
// stack on purpose and this guard would test the degraded layout instead).
const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions, derived from served data, never literals ────────────── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const openQ = d.questions_open.find(x => !x.answer);
ok('precondition: an open question exists on the fixture', !!openQ);
if (!openQ) { await b.close(); finish(); }
const enc = encodeURIComponent(openQ.title);

/* ── the focus view: body and compose side by side, sticky, taller field ── */
await p.goto(`${BASE}/question?qid=${enc}`, { waitUntil: 'networkidle' });
await waitFor(p, '#view .qa');
await sleep(1500);                       // the dissolve is ~1.15s
const focus = await p.evaluate(() => {
  const card = document.querySelector('#view .qa');
  const body = card && card.querySelector('.qbody');
  const comp = card && card.querySelector('.qcompose');
  const ta = comp && comp.querySelector('textarea');
  if (!card || !body || !comp || !ta) return null;
  const cs = el => getComputedStyle(el);
  const br = body.getBoundingClientRect(), cr = comp.getBoundingClientRect();
  return {
    cardDisplay: cs(card).display,
    // rendered geometry — the actual "two columns" contract
    bodyRight: br.right, compLeft: cr.left,
    bodyTop: br.top, bodyBottom: br.bottom,
    compTop: cr.top, compBottom: cr.bottom,
    sideBySide: cr.left >= br.right,           // compose starts right of body
    verticallyAligned: cr.top < br.bottom && br.top < cr.bottom, // overlap
    compPosition: cs(comp).position,
    taHeight: ta.getBoundingClientRect().height,
    oneCard: document.querySelectorAll('#view .qa').length === 1,
  };
});
notes.push('focus: ' + JSON.stringify(focus));
ok('precondition: the focus card, body, compose and textarea all exist',
   !!focus);
if (focus) {
  ok('the focus card is a grid (the dual-column container)',
     focus.cardDisplay === 'grid');
  ok('the question body and response compose are rendered SIDE BY SIDE ' +
     '(compose starts to the right of the body — not stacked beneath it)',
     focus.sideBySide);
  ok('the two columns vertically overlap (a row, not two stacked blocks)',
     focus.verticallyAligned);
  ok('the response compose is sticky — always present regardless of scroll',
     focus.compPosition === 'sticky');
  ok('exactly one card on the focus view', focus.oneCard);
}
await p.screenshot({ path: `${OUT}/focus-dual.png`, fullPage: true });

/* ── taller than normal: the focus field vs the SAME question on /questions */
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await waitFor(p, '.qa');
await sleep(900);
const dash = await p.evaluate(qid => {
  const card = document.querySelector(`.qa[data-qid="${qid}"]`);
  const body = card && card.querySelector('.qbody');
  const comp = card && card.querySelector('.qcompose');
  const ta = comp && comp.querySelector('textarea');
  if (!card || !body || !comp || !ta) return null;
  const cs = card && getComputedStyle(card);
  const br = body.getBoundingClientRect(), cr = comp.getBoundingClientRect();
  return {
    cardDisplay: cs.display,
    // dashboard contract: body and compose are STACKED (compose below body),
    // i.e. NOT side by side
    stacked: cr.top >= br.bottom - 1,
    taHeight: ta.getBoundingClientRect().height,
    hasCompose: !!card.querySelector('.qcompose'),
  };
}, enc);
notes.push('dashboard: ' + JSON.stringify(dash));
ok('precondition: the same question renders on /questions with a compose box',
   !!dash && dash.hasCompose);
if (focus && dash) {
  ok('the focus response field is TALLER than the dashboard field ' +
     '(taller than normal, by his spec)',
     focus.taHeight > dash.taHeight);
  // the gap is derived at runtime (a literal would be a floor with an expiry
  // date), but assert it is non-trivial so a 1px rounding win cannot pass it
  const gap = focus.taHeight - dash.taHeight;
  notes.push('taller-by: ' + gap.toFixed(1) + 'px');
  ok('the height gap is real, not a rounding artifact (>= 16px)',
     gap >= 16);
}
if (dash) {
  ok('the dashboard card is UNCHANGED — body and compose are STACKED ' +
     '(single column), not side by side',
     dash.cardDisplay !== 'grid' && dash.stacked);
}

ok('no page errors', errs.length === 0);
if (errs.length) notes.push('page errors: ' + errs.join(' | '));
await b.close();
finish();
