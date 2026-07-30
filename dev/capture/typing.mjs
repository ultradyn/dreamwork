/* #118 — a live tick must not eat what the human is typing.

   Under #505, setContent reconciles #view by key (morphdom) so survivor
   card nodes are KEPT — text/caret/focus ride the node. Before #505 the
   tick wholesale-replaced via innerHTML and snapshotCardState re-applied
   the draft. Either path must keep what he typed.

   The hazard is invisible to a screenshot and to any check that does not
   force a real tick, so this script does both halves:
     - it makes the tick actually happen (a real write under `.dreamwork/`,
       which is what `watched_mtime` watches) and PROVES it happened by
       `__dwViewRenderGen` advancing (or, legacy, the textarea node being
       replaced). Node replacement is no longer required under
       reconciliation — a kept node is the success mode.
     - it then asserts the text, the caret, the focus and the destination
       mode survived — the mode because it decides which endpoint the text
       is sent to, so losing it would silently redirect his words.
   Two ticks are exercised: one where nothing about the questions changed
   (POST /command — the common case, the loop writing its own files) and one
   where the list content genuinely changed underneath him (POST /comment on
   a DIFFERENT entry, which also moves cards and so runs the regroup FLIP).

   Writes to the target it is pointed at, so point it at a scratch copy.
   usage: node typing.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions across two chromium contexts (normal + reduced-motion), ' +
          'typing into an open card while POSTing /command then /comment to ' +
          'force a real tick, plus opening a folded entry across a tick',
  traceWindow: 'two 5200ms rAF traces per context watching the textarea node ' +
               'identity and mode indicator; the tick must replace the node',
});

const TEXT = 'half a thought, still being written';
const BACK = 5;                       // caret parked this far from the end
const uniq = a => [...new Set(a)];

/* Run one tick while watching a single card, and report what survived it.
   `poke` is the write that makes the tick real; the rAF trace spans the
   whole thing so the mode indicator can be judged per frame rather than by
   its final resting place (it must LAND on restore, not slide). */
const TICK = (qid, poke) => `(async (qid, poke) => {
  const sel = '.qa[data-qid="' + qid + '"]';
  const box = () => document.querySelector(sel + ' textarea');
  const ta0 = box();
  const gen0 = window.__dwViewRenderGen || 0;
  // Force morph path even when markup is byte-identical (hash-skip would
  // otherwise make a quiet /command tick a no-op on /questions).
  if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
  const lefts = []; let replaced = false; let advanced = false;
  await fetch(poke.url, { method: 'POST',
    headers: {'Content-Type':'application/json'}, body: JSON.stringify(poke.body) });
  const t0 = performance.now();
  await new Promise(res => (function step() {
    const ind = document.querySelector(sel + ' .qmodes .sgind');
    if (ind) lefts.push(Math.round(ind.getBoundingClientRect().left));
    const now = box();
    if (now && now !== ta0) replaced = true;
    if ((window.__dwViewRenderGen || 0) > gen0) advanced = true;
    if (performance.now() - t0 < 5200) requestAnimationFrame(step); else res();
  })());
  const ta = box(), comp = ta && ta.closest('.qcompose');
  const lit = comp && comp.querySelector('.sgbtn.on');
  return {
    // #505: tickWorked = gen advanced OR (legacy) node replaced
    replaced, advanced, tickWorked: advanced || replaced, lefts,
    value: ta ? ta.value : null,
    start: ta ? ta.selectionStart : -1, end: ta ? ta.selectionEnd : -1,
    focused: !!ta && document.activeElement === ta,
    mode: comp ? comp.dataset.mode : null,
    lit: lit ? lit.dataset.mode : null,
    // nothing was restored into a card he never touched
    othersEmpty: [...document.querySelectorAll('.qa textarea')]
                   .filter(x => x !== ta).every(x => !x.value),
  };
})(${JSON.stringify(qid)}, ${JSON.stringify(poke)})`;

async function typeInto(p, qid) {
  const sel = `.qa[data-qid="${qid}"]`;
  // mode first: clicking a mode button takes focus, so switching after
  // typing would leave the caret measurement describing the button
  await p.click(`${sel} .qmode[data-mode="note"]`);
  await sleep(350);
  await p.click(`${sel} textarea`);
  await p.keyboard.type(TEXT);
  for (let i = 0; i < BACK; i++) await p.keyboard.press('ArrowLeft');
}

const survived = (r, label, reduced) => {
  ok(`${label}: the tick really ran (render gen advanced or node replaced)`,
     !!(r && r.tickWorked));
  ok(`${label}: the typed text survived`, r.value === TEXT);
  ok(`${label}: the caret survived`,
     r.start === TEXT.length - BACK && r.end === r.start);
  ok(`${label}: focus stayed in the box he was typing in`, r.focused);
  ok(`${label}: the destination mode survived`, r.mode === 'note' && r.lit === 'note');
  ok(`${label}: nothing leaked into a card he never touched`, r.othersEmpty);
  if (!reduced)
    ok(`${label}: the mode indicator LANDS across the tick (it does not slide)`,
       uniq(r.lefts).length === 1);
};

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 950 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1200);

  const qids = await p.evaluate(() =>
    [...document.querySelectorAll('.qa.open[data-qid]')].map(e => e.dataset.qid));
  if (qids.length < 2) {
    ok('fixture has two open questions for the two-context tick', false);
    notes.push('fixture needs two open questions — reset the scratch target');
    await br.close(); finish(); process.exit(1);
  }
  const [mine, other] = qids;
  const otherTitle = decodeURIComponent(other);
  const tag = reduced ? 'reduced-motion' : 'normal';

  // (1) the loop writes its own files; the questions themselves did not change
  await typeInto(p, mine);
  const a = await p.evaluate(TICK(mine,
    { url: '/command', body: { kind: 'add-idea', text: 'typing guard tick' } }));
  survived(a, `${tag}, quiet tick`, reduced);
  if (!reduced) await p.screenshot({ path: `${OUT}/mid-typing.png`, fullPage: true });

  // (2) the list content genuinely changed underneath him: a note lands on
  //     ANOTHER entry, so cards move and the regroup FLIP runs too
  const b = await p.evaluate(TICK(mine,
    { url: '/comment',
      body: { question: otherTitle, comment: 'a note arriving while he types',
              section: 'Open' } }));
  survived(b, `${tag}, content changed`, reduced);

  // (3) #111 — a folded entry he has opened up to READ is the same class of
  //     state as half-typed text: it exists only in the node the tick
  //     replaces, so it rides the same seam under the same key
  const fqid = await p.evaluate(() => {
    const c = document.querySelector('.qa.folded[data-qid]');
    return c ? c.dataset.qid : null;
  });
  if (!fqid) {
    ok(`${tag}: fixture has a folded entry to open across a tick`, false);
    notes.push('fixture has no folded entry');
    await br.close(); finish(); process.exit(1);
  }
  await p.click(`.qa[data-qid="${fqid}"] .qfold > summary`);
  await sleep(250);
  const f = await p.evaluate(`(async (qid) => {
    const sel = '.qa[data-qid="' + qid + '"] > .qfold';
    const d0 = document.querySelector(sel);
    const wasOpen = !!(d0 && d0.open);
    const gen0 = window.__dwViewRenderGen || 0;
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    let replaced = false, advanced = false;
    await fetch('/command', { method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ kind: 'add-idea', text: 'fold guard tick' }) });
    const t0 = performance.now();
    await new Promise(res => (function step() {
      const d = document.querySelector(sel);
      if (d && d !== d0) replaced = true;
      if ((window.__dwViewRenderGen || 0) > gen0) advanced = true;
      if (performance.now() - t0 < 5200) requestAnimationFrame(step); else res();
    })());
    const d = document.querySelector(sel);
    return { wasOpen, replaced, advanced, tickWorked: advanced || replaced,
             stillOpen: !!(d && d.open), kept: !!(d0 && d && d0 === d && d.open) };
  })(${JSON.stringify(fqid)})`);
  ok(`${tag}: a folded entry can be expanded`, f.wasOpen);
  ok(`${tag}: the tick really ran (render gen advanced or node replaced)`,
     !!(f && f.tickWorked));
  ok(`${tag}: one he opened up to read stays open across a tick`, f.stillOpen);

  ok(`${tag}: no page errors`, errs.length === 0);
  await br.close();
}

finish();
