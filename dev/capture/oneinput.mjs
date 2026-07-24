/* #103 — ONE input per card, a mode group beneath it, a send button flush
   against its right edge.

   Three things a screenshot cannot check and this does:
     - the field and its send button are ONE object: same top and bottom, no
       gap between them, the wrapper's border around both
     - the mode picks the ENDPOINT — the same typed text goes to /answer or
       /comment depending only on which button is lit
     - the indicator LANDS on first paint and SLIDES on a switch (the
       enter-snap rule), verified per frame, and jumps under reduced motion
   Writes to the target it is pointed at, so point it at a scratch copy.
   usage: node oneinput.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

// per-frame trace of one card's indicator while something happens to it
const TRACE = act => `((act, ms) => new Promise(res => {
  const frames = [];
  const g = document.querySelector('.qa.open .qmodes');
  const t0 = performance.now();
  (function step() {
    const ind = g && g.querySelector('.sgind');
    frames.push(ind ? Math.round(ind.getBoundingClientRect().left) : null);
    if (performance.now() - t0 < ms) requestAnimationFrame(step);
    else res(frames);
  })();
  if (act) { const t = document.querySelector(act);
             if (!t) { res([]); return; } t.click(); }
}))(${JSON.stringify(act)}, 700)`;

const uniq = a => [...new Set(a)];
const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 950 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  const posts = [];
  p.on('request', r => { if (/\/(answer|comment)$/.test(r.url()))
    posts.push(r.url().split('/').pop()); });
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1000);
  // this script ANSWERS things, so it needs a target's worth of open cards;
  // say so rather than crashing three checks later on a null
  const open = await p.evaluate(() => document.querySelectorAll('.qa.open').length);
  if (!open) { console.log('FAIL fixture has no open question — reset the ' +
    'scratch target from the live questions.md and re-run'); process.exit(1); }

  if (!reduced) {
    // geometry: field + send button are one object
    const geo = await p.evaluate(() => {
      // scope to ONE card: the page shows several, and counting across them
      // measures the page, not the component
      const card = document.querySelector('.qa.open');
      const f = card.querySelector('.qfield');
      const ta = f.querySelector('textarea'), b = f.querySelector('.qsend');
      const F = f.getBoundingClientRect(), T = ta.getBoundingClientRect(),
            B = b.getBoundingClientRect();
      const cs = getComputedStyle(ta);
      return { gap: +(B.left - T.right).toFixed(2),
               // the button spans the FIELD, not the textarea's own box —
               // that full-height edge is what makes them read as one object
               spansField: Math.abs(B.top - F.top) < 2 &&
                           Math.abs(B.bottom - F.bottom) < 2,
               flushRight: Math.abs(B.right - F.right) < 2,
               fieldHasBorder: getComputedStyle(f).borderTopWidth !== '0px',
               textareaBorder: cs.borderTopWidth,
               // one input, not two
               inputs: card.querySelectorAll('textarea').length,
               modeBtns: [...card.querySelectorAll('.qmode')]
                           .map(x => x.textContent),
               openDefault: document.querySelector('.qa.open .qcompose').dataset.mode,
               awaitingDefault: (document.querySelector('.qa.awaiting .qcompose')
                                 || {}).dataset?.mode,
               // a folded entry cannot answer, so it is offered no choice
               foldedModes: document.querySelectorAll('.qa.folded .qmode').length,
               foldedMode: document.querySelector('.qa.folded .qcompose').dataset.mode,
             };
    });
    await p.screenshot({ path: `${OUT}/one-input.png`, fullPage: true });
    ok('exactly one text input per card', geo.inputs === 1);
    ok('send sits flush: no gap, full field height, at the field edge',
       geo.gap === 0 && geo.spansField && geo.flushRight);
    ok('the border belongs to the wrapper, not the textarea',
       geo.fieldHasBorder && geo.textareaBorder === '0px');
    ok('the mode group reads [answer | add note]',
       JSON.stringify(geo.modeBtns) === '["answer","add note"]');
    ok('an open entry defaults to answer', geo.openDefault === 'answer');
    ok('an answered entry defaults to add note', geo.awaitingDefault === 'note');
    ok('a folded entry is note-only, with no choice to get wrong',
       geo.foldedModes === 0 && geo.foldedMode === 'note');

    // the indicator: lands on first paint, slides on a switch
    const land = await p.evaluate(TRACE(null));
    const slide = await p.evaluate(TRACE('.qa.open .qmode[data-mode="note"]'));
    ok('the indicator LANDS on first paint (it does not tween in)',
       uniq(land.filter(x => x !== null)).length === 1);
    ok('the indicator SLIDES on a mode switch',
       uniq(slide.filter(x => x !== null)).length >= 5);

    // the mode picks the endpoint: same field, same text, two destinations
    await p.fill('.qa.open textarea', 'a note routed by the mode group');
    await p.click('.qa.open .qsend'); await sleep(500);
    const afterNote = await p.evaluate(() => ({
      follows: [...document.querySelectorAll('.qa.open .follow')].map(f => f.textContent),
      placeholder: document.querySelector('.qa.open textarea').placeholder,
    }));
    ok('note mode POSTs /comment', posts.includes('comment') && !posts.includes('answer'));
    ok('the note lands in the thread, attributed to him',
       afterNote.follows.some(f => /YOU|you/.test(f) &&
                                   /routed by the mode group/.test(f)));
    ok('the placeholder follows the mode', afterNote.placeholder === 'add a note…');

    // ...and the same field in answer mode reaches /answer
    await p.click('.qa.open .qmode[data-mode="answer"]'); await sleep(350);
    await p.fill('.qa.open textarea', 'an answer routed by the mode group');
    await p.keyboard.press('Control+Enter'); await sleep(600);
    const afterAns = await p.evaluate(() => ({
      awaiting: document.querySelectorAll('.qa.awaiting').length,
      text: [...document.querySelectorAll('.anstext')].map(a => a.textContent),
    }));
    ok('answer mode POSTs /answer', posts.includes('answer'));
    ok('Ctrl/Cmd+Enter still submits from the field',
       afterAns.text.some(t => /an answer routed by the mode group/.test(t)));
    ok('the submit morph still lands the awaiting state', afterAns.awaiting >= 1);
    await p.screenshot({ path: `${OUT}/after-both.png`, fullPage: true });
    ok('no page errors', errs.length === 0);
  } else {
    const jump = await p.evaluate(TRACE('.qa.open .qmode[data-mode="note"]'));
    ok('reduced-motion: the indicator JUMPS, it does not slide',
       uniq(jump.filter(x => x !== null)).length <= 2);
    ok('reduced-motion: no page errors', errs.length === 0);
  }
  await br.close();
}

console.log(checks.join('\n'));
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
