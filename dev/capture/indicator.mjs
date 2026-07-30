/* indicator — #198: the composer's selection indicator lands on the button it
   marks, even though it is painted while the panel is still arriving.

   His report: it is misplaced when the composer reopens and "autocorrects
   itself after a bit, or when some rerender condition is triggered".

   WHAT IT ACTUALLY IS, measured before it was fixed. `openCmd` reveals the
   panel and paints the indicator on the SAME frame, and the panel reveals
   through a transform — `translateY(-8px) scale(.97)` -> `none` over .5s. So
   `slideIndicator`'s `getBoundingClientRect` calls came back in VISUAL space,
   3% small, and the values written were 3% short. Measured on the last button
   in the row, where the offset error is largest: the indicator sat 4.53px left
   of its button and 1.88px narrow.

   THE "AUTOCORRECTS" HALF IS THE TRAP, and it is why this guard's window is
   deliberately short. It does not heal on its own — the geometry it wrote is
   wrong and stays wrong. What heals it is the next thing that re-measures:
   `setContent` calls `paintIndicators(true)` on every view re-render, and his
   live dashboard re-renders every couple of seconds because status.json keeps
   changing. So a guard that opened the composer and looked a few seconds later
   would find it perfect and pass, forever, over a bug he can see. The
   assertions run inside a bounded window after the open and never re-enter it.

   The fixture cannot re-render on its own (its mtime is frozen), which would
   make a sloppy window pass by luck rather than by design — so the guard also
   proves the laundering path exists, by triggering a re-render itself and
   watching a deliberately-broken indicator become correct. That check is what
   keeps the short window honest rather than superstitious.

   Shown red on the pre-fix build: -4.53px offset and -1.88px width on the far
   button, both phases.

   usage: node indicator.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

/* Where the indicator is versus the button it marks, both in page space.

   Compared as RECTS ON SCREEN rather than as inline styles, because the inline
   style is the mechanism and this is about the outcome: the outline is around
   the option, or it is not. It also means the check is blind to how the fix
   was spelled, which is the property `states.mjs` earned the hard way. */
const READ = `(() => {
  const g = document.getElementById('cmdkinds');
  const ind = document.getElementById('cmdind');
  const btn = g && g.querySelector('.sgbtn.on');
  if (!g || !ind || !btn) return null;
  const b = btn.getBoundingClientRect(), i = ind.getBoundingClientRect();
  return { dLeft: +(i.left - b.left).toFixed(2),
           dTop: +(i.top - b.top).toFixed(2),
           dWidth: +(i.width - b.width).toFixed(2),
           btnW: +b.width.toFixed(2),
           kind: btn.dataset.kind,
           nBtns: g.querySelectorAll('.sgbtn').length };
})()`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);

/* open, select `which` button, close, reopen — his gesture — and read inside a
   window short enough that no re-render can have laundered it */
async function reopen(which) {
  await p.click('#cmdplus');
  await sleep(700);
  await p.evaluate(`(() => {
    const bs = [...document.querySelectorAll('#cmdkinds .cmdkind')];
    (${JSON.stringify(which)} === 'last' ? bs[bs.length - 1] : bs[0]).click();
  })()`);
  await sleep(600);                      // the slide finishes
  await p.evaluate(`window.__closeCmd()`);
  await sleep(700);                      // fully closed, transform back at .97
  await p.click('#cmdplus');
  // 650ms: past the .5s reveal, so the panel is settled and the comparison is
  // between two rests — and far short of anything that re-renders the view.
  await sleep(650);
  return await p.evaluate(READ);
}

const shape = await p.evaluate(READ);
ok('the composer has a kind row with at least two options ' +
   '(else the far-button case does not exist)',
   !!shape && shape.nBtns >= 2);

for (const which of ['first', 'last']) {
  const r = await reopen(which);
  notes.push(`reopen with the ${which} kind selected (${r.kind}, ${r.btnW}px): ` +
             `indicator offset ${r.dLeft}/${r.dTop}, width ${r.dWidth}`);
  // 1px: the geometry is written from a measurement, so sub-pixel rounding is
  // expected; the failure this catches is 3% of the row — 4.5px of offset and
  // 1.9px of width on the far button. Nothing lands in between.
  ok(`reopen (${which} kind): the outline sits ON the option it marks`,
     Math.abs(r.dLeft) <= 1 && Math.abs(r.dTop) <= 1);
  ok(`reopen (${which} kind): ...and is the size of it`, Math.abs(r.dWidth) <= 1);
}

/* ── the laundering path, proven rather than assumed ──────────────────────
   The window above is only meaningful if something really would have fixed
   this behind the guard's back. Break the indicator by hand, force a view
   re-render, and watch it come back correct: that is the mechanism his "or
   when some rerender condition is triggered" describes, and it is what a
   longer window would have silently ridden. */
{
  const broken = await p.evaluate(`(() => {
    const ind = document.getElementById('cmdind');
    // snap first: the indicator SLIDES, so writing a transform and reading
    // the rect on the same tick returns the rect it is still leaving. The
    // first version of this check did exactly that and reported no damage.
    // (No backticks in here: this string IS a template literal, and a pair of
    // them in a comment ends it — the bug TestBundleParses exists for.)
    ind.classList.add('snap');
    ind.style.transform = 'translate(0px, 40px)';
    ind.style.width = '4px';
    void ind.offsetWidth;
    ind.classList.remove('snap');
    return ${READ};
  })()`);
  // #505 hash-skip: setContent no-ops when html === lastViewHtml. Clear so
  // paintIndicators(true) actually re-runs (the laundering path under test).
  await p.evaluate(`(() => {
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    setContent(buildDashboard(data));
  })()`);
  await sleep(120);
  const healed = await p.evaluate(READ);
  notes.push(`laundering: forced offset ${broken.dLeft}/${broken.dTop} -> ` +
             `${healed.dLeft}/${healed.dTop} after one re-render`);
  ok('a re-render really does re-measure the indicator (else the short ' +
     'window above is superstition, not a bound)',
     Math.abs(broken.dTop) > 20 && Math.abs(healed.dTop) <= 1 &&
     Math.abs(healed.dWidth) <= 1);
}

await p.click('#cmdplus');
await sleep(700);
await p.screenshot({ path: `${OUT}/indicator.png`, fullPage: false });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
