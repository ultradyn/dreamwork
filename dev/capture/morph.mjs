/* morph — #191: the answer-submit morph carries its neighbours.

   The submit morph is the page's most carefully taught gesture — the card
   restates itself in place and the typed text lifts into the answer — and it
   was the one path that changed a card's height with NO snapshot and NO
   regroup. So every card below it jumped the height delta in a single frame,
   in the one gesture the page has most carefully taught to travel.

   Why nothing caught it for so long: `regroup.mjs` answers through the real
   UI too, but it traces for 5.2s — past `holdRerenderUntil` — so the tick's
   own regroup travels the neighbour and every "it slid" check passes over a
   teleport that happened 1.6s earlier. THE WINDOW IS THE WHOLE MEASUREMENT.
   This guard traces 1200ms, inside the hold (`MORPH_HOLD_MS`, 1250 — #234),
   and asserts the card node was never replaced across it — so whatever
   moved, the MORPH moved, not a tick.

   `sendComment` has the identical shape (it appends a note, the card grows),
   so it is measured here too rather than left for the next person to find
   one done and one not.

   Shape: its own target and its own server on an EPHEMERAL port (the
   dashboard.mjs/motion.mjs shape), because each phase needs a pristine
   `questions.md` — answering the first open question changes which card the
   next phase would pick, and an order-dependent guard reports run order as a
   bug in the page.

   usage: node morph.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
/* Report from an exit handler, not from the tail — a guard that throws part
   way through prints nothing, and a reader counting FAIL lines reads a crash
   as a clean run. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

const DIR = join(OUT, 'target');
const reset = () => {
  rmSync(DIR, { recursive: true, force: true });
  cpSync('dev/capture/fixture', DIR, { recursive: true });
};
reset();
const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);
const BASE = `http://127.0.0.1:${PORT}`;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
}

/* The trace starts BEFORE the send and runs for 1200ms: the hold
   (`MORPH_HOLD_MS`, 1250) starts when the POST resolves and `flipDock`'s
   1150ms transform is the longest visible leg, so the whole gesture fits
   inside the window and the tick cannot be the thing that moved anything.

   `data-trace` is set on the card node itself. `card.innerHTML = …` keeps the
   node, a tick's `innerHTML` swap of the LIST does not — so this attribute
   surviving every frame is the proof that the morph is what is under
   measurement. */
const TRACE = mode => `((ms) => new Promise(res => {
  const cards = () => [...document.querySelectorAll('.qa[data-qid]')];
  const first = cards().find(c => c.classList.contains('open'));
  if (!first) { res({ nofixture: 'no open card' }); return; }
  const top0 = first.getBoundingClientRect().top;
  const below = cards().filter(c => c.getBoundingClientRect().top > top0)[0];
  if (!below) { res({ nofixture: 'no card below the one being answered' }); return; }
  const target = first.dataset.qid, neighbour = below.dataset.qid;
  first.dataset.trace = 'target';
  const frames = [];
  const t0 = performance.now();
  (function step() {
    const byId = {};
    for (const c of cards()) {
      const r = c.getBoundingClientRect();
      byId[c.dataset.qid] = { top: Math.round(r.top), h: Math.round(r.height),
                              cls: c.className.replace(/ ?dreamin/, '') };
    }
    frames.push({ t: Math.round(performance.now() - t0),
      target: byId[target] || null,
      neighbour: byId[neighbour] || null,
      sameNode: !!document.querySelector('.qa[data-trace=target]'),
      flipping: cards().filter(c => c.style.transform).length });
    if (performance.now() - t0 < ms) requestAnimationFrame(step);
    else res({ target, neighbour, frames });
  })();
  // through the real UI, in the mode under test — the bug lives in the
  // client's submit path, so a POST would drive the wrong code entirely
  first.querySelector('.qmode[data-mode=${mode}]').click();
  first.querySelector('textarea').value =
    'a traced ${mode} long enough to change the card height by more than a line';
  first.querySelector('.qsend').click();
}))(1200)`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
async function phase(mode, reduced) {
  reset();
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const r = await p.evaluate(TRACE(mode));
  if (!reduced) await p.screenshot({ path: `${OUT}/${mode}.png`, fullPage: true });
  await ctx.close();
  return r;
}

const uniq = a => [...new Set(a)];
const tops = (f, who) => f.filter(x => x[who]).map(x => x[who].top);
const heights = (f, who) => f.filter(x => x[who]).map(x => x[who].h);

const runs = {};
for (const mode of ['answer', 'note']) {
  for (const reduced of [false, true])
    runs[`${mode}${reduced ? '-rm' : ''}`] = await phase(mode, reduced);
}
await br.close();
try { srv.kill(); } catch (e) {}

for (const mode of ['answer', 'note']) {
  const n = runs[mode], r = runs[`${mode}-rm`];
  if (n.nofixture || r.nofixture) {
    ok(`${mode}: the fixture gives a card with a neighbour below it`, false);
    notes.push(`${mode}: ${n.nofixture || r.nofixture}`);
    continue;
  }
  const nTops = tops(n.frames, 'neighbour'), nHs = heights(n.frames, 'target');
  const net = nTops.at(-1) - nTops[0];
  notes.push(`${mode}: neighbour tops ${JSON.stringify(uniq(nTops))}`);
  notes.push(`${mode}: target heights ${JSON.stringify(uniq(nHs))}`);
  notes.push(`${mode}: frames=${n.frames.length} span=${n.frames.at(-1).t}ms ` +
             `flipped=${Math.max(...n.frames.map(x => x.flipping))} ` +
             `rm neighbour tops ${JSON.stringify(uniq(tops(r.frames, 'neighbour')))}`);

  /* Vacuity first, and it is not ceremony: EVERY assertion below is about how
     the neighbour got somewhere, so a run where it never went anywhere would
     satisfy none of them for the wrong reason. */
  ok(`${mode}: the send changes the card's height, so the neighbour has ` +
     `somewhere to go (else every check below is vacuous)`,
     uniq(nHs).length > 1 && Math.abs(net) >= 8);
  ok(`${mode}: the card node is never replaced across the window — so this ` +
     `measures the MORPH and not a tick`,
     n.frames.every(x => x.sameNode));
  /* THE check. Two distinct positions is a teleport; that is exactly what was
     measured on the bug (744 -> 791, no transform, across 354 frames). Outcome
     rather than mechanism, per states.mjs: a card carried by the animated
     height of the card above it travels perfectly with no transform of its own,
     and demanding one would forbid the better motion. */
  ok(`${mode}: the neighbour TRAVELS to its new place rather than jumping`,
     uniq(nTops).length >= 6);
  ok(`${mode}: ...and the card's own height travels with it`,
     uniq(nHs).length >= 6);
  /* reduced motion changes timing, never function: the same regrouping
     happens, in discrete steps. */
  const rTops = tops(r.frames, 'neighbour');
  ok(`${mode}: reduced motion lands it instead, in discrete steps`,
     uniq(rTops).length * 3 <= uniq(nTops).length);
  ok(`${mode}: ...and still ends up in the same place`,
     Math.abs((rTops.at(-1) - rTops[0]) - net) <= 2);
}

ok('no page errors', errs.length === 0);
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
