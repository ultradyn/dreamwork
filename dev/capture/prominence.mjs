/* prominence — #169: an expanded element becomes PROMINENT, not just taller.

   His words: expanding should grow padding above and below, so the thing he
   opened reads as foregrounded. It is an IDIOM rather than a treatment on one
   component, so this guard visits every kind of disclosure the page has —
   a standalone `expand`, the dashboard's questions fold, a settled follow-up
   thread, and a folded question card — and requires all four to gain air and
   to step UP the text ramp.

   Two things this measures that a simpler check would not:

     - THE RAMP STEP IS PER SURFACE. These sit at four different brightnesses
       when closed, on purpose, so "the open summary is #f3f4f6" is true of one
       of them and wrong about the other three. The assertion is on the
       DIRECTION — strictly brighter than the same element measured closed —
       which is the rule the styleguide actually states.

     - THE GROWTH IS ONE GESTURE. A card-nested disclosure measures its new
       rect immediately after `det.open` flips, so a padding TRANSITION would
       hand the FLIP a height the card never reaches and it would snap at the
       end of the travel. That is invisible in an end-state check and invisible
       in "did it travel" — both pass on it. So the neighbour below is traced
       per frame and its largest single-frame step is asserted small: a
       snap-back is one big step in an otherwise smooth ramp.

   Shown red with the padding rule deleted (no air anywhere, four FAILs) and
   again with the per-surface ramp lines deleted (a folded card's summary and
   a settled thread's summary each come back unchanged).

   usage: node prominence.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
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

/* Read a disclosure's air and its summary's colour. `sel` addresses the
   <details>; the summary is its own child, never a descendant — a question
   card nested inside another disclosure carries one too. */
const READ = sel => `(() => {
  const d = document.querySelector(${JSON.stringify(sel)});
  if (!d) return null;
  const s = d.querySelector(':scope > summary');
  const cs = getComputedStyle(d);
  return { open: d.open,
           padTop: parseFloat(cs.paddingTop), padBottom: parseFloat(cs.paddingBottom),
           sum: s ? getComputedStyle(s).color : null };
})()`;
/* luminance of an `rgb(r, g, b)` string — the page's whole emphasis axis, so
   comparing it is comparing the thing the rule is about. */
const lum = c => {
  const m = /(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(c || '');
  if (!m) return -1;
  return 0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3];
};

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 1600 } });
p.on('pageerror', e => errs.push(String(e)));

/* One surface: read it closed, click its summary, read it open. Clicked with a
   real pointer rather than `element.click()` — #141's lesson, since a
   synthetic click sails straight through `pointer-events:none` and a summary
   the human cannot click would pass. */
async function surface(name, sel) {
  const before = await p.evaluate(READ(sel));
  if (!before) { ok(`${name}: is on the page at all (else vacuous)`, false); return; }
  if (before.open) {
    await p.click(`${sel} > summary`);
    await sleep(400);
  }
  const closed = await p.evaluate(READ(sel));
  await p.click(`${sel} > summary`);
  await sleep(1400);                    // past CARD_MS, so the travel is done
  const open = await p.evaluate(READ(sel));
  notes.push(`${name}: pad ${closed.padTop}/${closed.padBottom} -> ` +
             `${open.padTop}/${open.padBottom} | ` +
             `summary ${closed.sum} (${lum(closed.sum).toFixed(0)}) -> ` +
             `${open.sum} (${lum(open.sum).toFixed(0)})`);
  ok(`${name}: it really did open (else every check here is vacuous)`,
     closed.open === false && open.open === true);
  ok(`${name}: expanding claims air above and below`,
     open.padTop > closed.padTop + 2 && open.padBottom > closed.padBottom + 2);
  // the DIRECTION, not a value: these four sit at four different brightnesses
  // closed, so any fixed colour would be right about one of them
  ok(`${name}: ...and its summary steps UP the ramp`,
     lum(open.sum) > lum(closed.sum) + 4);
  return { closed, open };
}

// ── the dashboard: a standalone expand, and the questions fold (#141) ──────
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);
await surface('the questions fold', '.qsec');
await surface('a standalone expand', '.wrap details:not(.qsec):not(.qthread)');

// ── /questions: the two card-nested disclosures ───────────────────────────
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);
const thread = await surface('a settled thread', '.qthread');
const fold = await surface('a folded question card', '.qa.folded .qfold');

/* Each of these states its own step rather than taking the generic one, so
   the guard checks they really are DIFFERENT — a per-surface rule that
   resolved to the same colour everywhere would be the flat rule it exists to
   avoid, and would pass every check above. */
if (thread && fold) {
  ok('the surfaces keep their own places on the ramp rather than all going ' +
     'to one brightness',
     Math.abs(lum(thread.open.sum) - lum(fold.open.sum)) > 4);
}

/* ── the growth is ONE gesture ────────────────────────────────────────────
   Trace the card below a settled thread across the whole expand. A padding
   transition would make `regroupCards` aim at a height the card never
   reaches, and the card would SNAP to its real position when the inline
   height is cleared — one large step at the end of an otherwise smooth ramp,
   which every end-state and every "did it travel" check passes over. */
{
  // collapse it again so there is a fresh expand to trace
  await p.click('.qthread > summary');
  await sleep(1400);
  const trace = p.evaluate(`new Promise(res => {
    const below = () => {
      const cards = [...document.querySelectorAll('.qa[data-qid]')];
      const host = document.querySelector('.qthread').closest('.qa');
      const y = host.getBoundingClientRect().top;
      return cards.filter(c => c.getBoundingClientRect().top > y)[0] || null;
    };
    const el = below();
    if (!el) { res(null); return; }
    const seen = []; const t0 = performance.now();
    (function step() {
      const t = performance.now() - t0;
      seen.push({ t, top: el.getBoundingClientRect().top });
      if (t < 2000) requestAnimationFrame(step); else res(seen);
    })();
  })`);
  await sleep(60);
  await p.click('.qthread > summary');
  const seen = await trace;
  if (!seen) {
    ok('there is a card below the thread to be carried (else vacuous)', false);
  } else {
    const tops = seen.map(s => s.top);
    const total = Math.abs(tops.at(-1) - tops[0]);
    const at = ms => seen.reduce((a, b) =>
      Math.abs(b.t - ms) < Math.abs(a.t - ms) ? b : a);
    /* ANCHORED TO THE FRAME THE CARD FIRST MOVES, not to the frame the trace
       armed — `transitions.md`, "do not anchor an arrival assertion to a
       clock". It was `at(950)` measured from trace start, which silently
       includes however long the real pointer click took to land: clean runs
       read 0.8-2.6px against a 4px threshold, so a loaded machine pushed one
       over and this guard went red on a page that was behaving perfectly.
       Anchoring removes the machine from the measurement — after the travel
       ends every sample is at the final position, however sparse the frames.

       950ms: `CARD_MS` is 850 and the inline height clears at 1000, so this is
       the last moment the FLIP is still driving the layout. */
    const from = tops[0];
    const i0 = tops.findIndex(v => Math.abs(v - from) > 1);
    const t0 = i0 < 0 ? 0 : seen[i0].t;
    const late = Math.abs(at(t0 + 950).top - tops.at(-1));
    notes.push(`one gesture: neighbour travelled ${total.toFixed(0)}px over ` +
               `${new Set(tops.map(Math.round)).size} distinct positions; ` +
               `still ${late.toFixed(1)}px from its final place when the ` +
               `travel ended`);
    ok('the card below is carried at all (else vacuous)', total >= 8);
    ok('...continuously, rather than in a couple of jumps',
       new Set(tops.map(Math.round)).size >= 6);
    /* The padding-transition failure, stated as the thing it does. If the
       growth is not in the layout before `regroupCards` measures, the FLIP
       aims at a height the card never reaches; it plays to that wrong height
       and then SNAPS the difference when the inline height is cleared. So the
       neighbour is asserted to have ARRIVED when the travel ends — not merely
       to arrive eventually, which it does either way, and which is why an
       end-state check is blind to this. */
    // 6px: anchored, the tail of the ease lands within ~1px of final, and the
    // failure this catches is the padding itself — 2 x .5rem, so 16px. There
    // is no threshold in between to tune, and the margin is now spent on
    // sub-pixel rounding rather than on how loaded the machine is.
    ok('...and it has arrived when its travel ends, not after a correction',
       late <= 6);
  }
}

await p.screenshot({ path: `${OUT}/prominence.png`, fullPage: true });
ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
