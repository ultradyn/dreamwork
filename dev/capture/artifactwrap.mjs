/* artifactwrap — #347 + #372: a review artifact's words must not break mid-word.

   Two defects lived in the frame and both are invisible to any end-state
   assertion, which is why a screenshot that "looks fine" is not evidence here:

     #347  `.topactions a` had no `white-space:nowrap`, so once the rail ran out
           of room a two-word label split mid-syllable ("measur/ed"). Every other
           interactive text element in the top rail carries nowrap; the anchor
           was the only one without it.
     #372  `.scroller` is `overflow-x:auto` but the `<table>` inside carried no
           `min-width`, so at 390px it shrank until words broke inside cells and
           the container never scrolled.

   THE INSTRUMENT, and why it is not `getClientRects().length === 1` on the
   anchor: the anchor is `display:inline-flex`, so its box stays ONE rect while
   the text wraps *inside* it. That hollow instrument reported `1` for four
   labels that were visibly broken. What works is a `Range` over each WORD of a
   label — a word that wrapped mid-word spans two lines and so produces two
   rects. Words containing `-` or `/` are skipped, because breaking at a hyphen
   or a slash is correct typography for paths and compounds.

   THE INJECTION POINT, and why it is the source and not the DOM: rewriting the
   labels through the DOM did not reproduce the wrap, because the test's own
   scaffolding stood in front of the bug. The discriminating red comes from
   rebuilding the nav FROM SOURCE into a throwaway artifact (this guard builds
   one through review_artifact.py, so it exercises the real template + builder).
   Inject through the source, not the DOM.

   The fixture is served through the existing `(OUT, PORT)` contract at
   `/reviewraw` — the server the justfile already started, reading the target's
   `.dreamwork/review/`. No second serving contract is invented.

   usage: node artifactwrap.mjs <outdir> <port>   (port defaults to 39899) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { makeReporter } from './report.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..', '..');          // repo root: review_artifact.py lives here

const r = makeReporter();
const { ok, declare, finish, notes } = r;
declare({
  drives: '/reviewraw on a fixture artifact built from source — .topactions a ' +
          'and .scroller table cells, at three widths',
  traceWindow: 'none: reads finished layout at three widths; no gesture is traced'
});

/* THE FIXTURE SOURCE. A deliberately long context (to starve the rail the way
   #346's did) plus four two-word nav labels plus a four-column scroller table
   whose cells squeeze at 390px. It is built by review_artifact.py from the real
   template, so the frame's CSS — the thing under test — is what renders. */
const NAME = 'artifactwrap-fixture.html';
const FIXTURE = `<!--dreamwork-review-source
title: #AW · Artifact wrap fixture · nav and table word breaks
identity: review template · the frame
context: task #347 + #372 · a deliberately long context line that starves the nav so a missing nowrap shows
status: awaiting review
headline: A fixture that exercises every word the frame must not break.
tag: guard fixture — not a real review
no_ask: guard fixture — it exercises the frame's wrapping and asks nothing (#436)
no_if_silent: guard fixture — no decision to park, so there is nothing silence could block (#455)
sub: guard fixture · nav anchors and a scroller table at three widths
skip: Skip to the table
skip_href: #table
-->
<!--#nav-->
<a class="full" href="#findings">measured outcomes</a><a href="#shape">sequence review</a><a href="#decisions">fixture decisions</a><a href="#seam">priority bands</a>
<!--#lead-->
<p class="lead">This fixture exists to break words. Its nav carries four two-word labels and its
context is long enough to starve the rail, so a missing <code>white-space:nowrap</code> on the nav
anchor shows as a mid-word split, and a table without a <code>min-width</code> shows as cells
squeezed until their words break.</p>
<!--#body-->
<section id="findings">
  <div class="label">The findings</div>
  <p>Two measured defects live in the frame: the nav anchor wraps mid-word, and the scroller table
  shrinks instead of scrolling. Both are invisible to any end-state assertion, which is why a
  word-level <code>Range</code> is the instrument.</p>
  <div class="scroller" id="table"><table>
  <thead><tr><th>component</th><th>what it breaks at 390px</th><th>the fix</th><th>the check</th></tr></thead>
  <tbody>
    <tr><td>nav anchor</td><td>two-word labels split mid-syllable</td><td>white-space:nowrap</td><td>word Range rects exceed one</td></tr>
    <tr><td>scroller table</td><td>cells squeeze until words break inside them</td><td>min-width on the table</td><td>scroller scrolls, no word breaks</td></tr>
    <tr><td>compound priority</td><td>a value like P0/P1 cannot sort or group</td><td>closed band plus priority_uncertain</td><td>the band column is a closed set</td></tr>
  </tbody>
  </table></div>
</section>
<!--#footer-->
guard fixture for the artifact-wrap guard · not a real review
`;

// ── locate the server's target, drop the fixture in, build it from source ───
const data = await (await fetch(`${BASE}/data.json`)).json();
const target = data.target;
if (!target) throw new Error('no target in /data.json — is this the guards server?');
const reviewDir = join(target, '.dreamwork', 'review');
const srcDir = join(reviewDir, 'src');
mkdirSync(srcDir, { recursive: true });
const srcPath = join(srcDir, NAME);
writeFileSync(srcPath, FIXTURE);
// Build through the real builder so the frame's CSS is exercised. review_artifact.py
// writes beside src/ (src/<slug>.html -> <slug>.html); the output is what /reviewraw serves.
execFileSync('python3', [join(ROOT, 'review_artifact.py'), 'build', srcPath],
             { cwd: ROOT, stdio: ['ignore', 'ignore', 'pipe'] });
const URL_ = `${BASE}/reviewraw?p=${NAME}`;

/* THE INSTRUMENT. For each scanned element, walk its text nodes; for each word
   with no `-` or `/`, lay a Range over it and count rects. >1 means the word
   was split across lines — a mid-word break. Returns per-region break counts
   plus the scroller geometry that proves the table is actually squeezed. */
const INSTRUMENT = `(() => {
  const breaks = [];
  const scan = (el, where) => {
    if (!el || !el.checkVisibility()) return;
    const boxRects = el.getClientRects().length;   // stays 1 for inline-flex; reported not asserted
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const raw = node.nodeValue;
      if (!raw) continue;
      const re = /\\S+/g;
      let m;
      while ((m = re.exec(raw))) {
        const word = m[0];
        if (word.includes('-') || word.includes('/')) continue;   // correct break points
        const range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + word.length);
        const rects = range.getClientRects();
        if (rects.length > 1) breaks.push({ where, word, rects: rects.length, boxRects });
      }
    }
  };
  const navs = [...document.querySelectorAll('.topactions a')];
  navs.forEach((a, i) => scan(a, 'nav[' + i + ']'));
  const cells = [...document.querySelectorAll('.scroller table td, .scroller table th')];
  cells.forEach((c, i) => scan(c, 'cell[' + i + ']'));
  // multi-word label present? the precondition that a break is even possible.
  const multiWordNav = navs.some(a => /\\s/.test(a.textContent));
  const scroller = document.querySelector('.scroller');
  return {
    navCount: navs.length,
    cellCount: cells.length,
    multiWordNav,
    navBreaks: breaks.filter(b => b.where.startsWith('nav')).length,
    cellBreaks: breaks.filter(b => b.where.startsWith('cell')).length,
    sample: breaks.slice(0, 4),
    scrollW: scroller ? scroller.scrollWidth : null,
    clientW: scroller ? scroller.clientWidth : null,
    pageOver: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
})()`;

const WIDTHS = [1280, 900, 390];
const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
  ignoreDefaultArgs: ['--hide-scrollbars'],
});

/* Refuse to grade horizontal geometry through Playwright's normally hidden
   scrollbar. Both halves matter: a zero-width reading on a page with no
   vertical overflow means the instrument could not run, not that it passed. */
{
  const pctx = await br.newContext({ viewport: { width: 1280, height: 900 } });
  const ppage = await pctx.newPage();
  await ppage.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  const sb = await ppage.evaluate(() => ({
    width: window.innerWidth - document.documentElement.clientWidth,
    scrollH: document.documentElement.scrollHeight,
    innerH: window.innerHeight,
  }));
  notes.push('scrollbar precondition: ' + JSON.stringify(sb));
  ok(`scrollbar precondition: dashboard genuinely overflows vertically `
   + `(${sb.scrollH} > ${sb.innerH}) — else scrollbar width could not be tested`,
     sb.scrollH > sb.innerH);
  ok(`scrollbar precondition: this browser's scrollbar consumes width `
   + `(sb=${sb.width}px) — else --hide-scrollbars survived ignoreDefaultArgs `
   + `and every horizontal-overflow verdict below is blind`,
     sb.scrollH > sb.innerH && sb.width > 0);
  await pctx.close();
}

let served = false;
for (const w of WIDTHS) {
  const ctx = await br.newContext({ viewport: { width: w, height: 900 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => r.errs.push(String(e)));
  try {
    await p.goto(URL_, { waitUntil: 'networkidle' });
  } catch (e) {
    ok(`at ${w}px the fixture artifact is served at /reviewraw (else every check below is vacuous)`, false);
    notes.push(`      (${String(e).slice(0, 120)})`);
    await ctx.close();
    continue;
  }
  served = true;
  // #536 render readiness — wait for the .scroller the guard instruments first, not a fixed sleep (#428 class)
  await waitFor(p, '.scroller');
  const g = await p.evaluate(INSTRUMENT);

  // precondition: there is a nav with words to break, and a table with cells.
  ok(`at ${w}px the nav carries anchors with words (else the nav check is vacuous)`,
     g.navCount >= 3 && g.multiWordNav);
  ok(`at ${w}px the scroller table carries cells (else the table check is vacuous)`,
     g.cellCount >= 8);

  // #347 — no nav label word splits mid-word.
  ok(`at ${w}px no nav label word breaks mid-syllable (#347)`, g.navBreaks === 0);
  // #372 — no table cell word splits mid-word.
  ok(`at ${w}px no table cell word breaks mid-word (#372)`, g.cellBreaks === 0);
  // the frame must not push the page sideways to "fix" the nav.
  ok(`at ${w}px the page does not scroll horizontally`, g.pageOver <= 1);

  notes.push(`  ${w}px: nav=${g.navCount} cells=${g.cellCount} ` +
             `navBreaks=${g.navBreaks} cellBreaks=${g.cellBreaks} ` +
             `scroller=${g.scrollW}/${g.clientW} pageOver=${g.pageOver}` +
             (g.sample.length ? '  e.g. ' + JSON.stringify(g.sample[0]) : ''));
  await ctx.close();
}

// #372's discriminating precondition at the phone width: the table must be wide
// enough to NEED the scroller, so "no cell breaks" is not satisfied by a table
// that simply fit. With the fix the scroller scrolls; without `min-width` it
// squeezed (scrollW === clientW) and the cells broke.
if (served) {
  const ctx = await br.newContext({ viewport: { width: 390, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(URL_, { waitUntil: 'networkidle' });
  await new Promise(res => setTimeout(res, 150));
  const sc = await p.evaluate(`(() => { const s = document.querySelector('.scroller');
    return s ? { scrollW: s.scrollWidth, clientW: s.clientWidth } : null; })()`);
  ok('at 390px the scroller actually scrolls rather than squeezing the table ' +
     '(else the no-cell-breaks check is vacuous — a table that fit never broke)',
     !!sc && sc.scrollW > sc.clientW + 40);
  notes.push(`  390px scroller geometry: scrollW=${sc && sc.scrollW} clientW=${sc && sc.clientW} ` +
             `(gap ${sc ? sc.scrollW - sc.clientW : 'n/a'})`);
  await ctx.close();
}

ok('no page errors', r.errs.length === 0);
await br.close();

// the fixture is a throwaway in the temp target; clean it so a later guard run
// on the same target does not list it as a review.
try {
  rmSync(srcPath);
  rmSync(join(reviewDir, NAME));
  rmSync(srcDir);
} catch (e) { /* best-effort; the target is ephemeral anyway */ }

finish();
