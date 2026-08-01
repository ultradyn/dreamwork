/* pipfill — #860: the command popout's textarea fills the window exactly.

   The property is TWO-SIDED, and side 2 is the whole task:
     1. the popout document does NOT scroll (de.scrollHeight <= de.clientHeight), AND
     2. if the textarea were ANY taller, it WOULD scroll.
   Side 1 alone is satisfied by a 1px textarea, so this guard asserts the
   +1px overflow (side 2) and not only the no-scroll (side 1). A one-sided
   check is the exact false green this feature is most likely to ship, because
   "no scrollbar" is the natural thing to assert and it passes trivially.

   Side 2 is measured on the LIVE layout, never computed from the same
   expression production uses. The textarea is frozen at its rendered height
   +1px and the document's scrollHeight is observed to exceed clientHeight.
   A check that derived the expected height from the production arithmetic
   would agree with a broken implementation; this one asks the browser whether
   it overflowed.

   WHY documentElement not body: de.scrollHeight reports max(content,
   clientHeight), so it floors at clientHeight when content is below the
   viewport — which is exactly what makes it the right signal: at the maximal
   fill, de.scrollHeight == de.clientHeight (no scroll), and +1px pushes
   de.scrollHeight above de.clientHeight (scrolls). body.scrollHeight does
   NOT floor at clientHeight, so it can never distinguish "no scroll with
   slack" from "no scroll, maximal" — using it for side 2 would pass on a
   textarea with 50px of slack.

   FALSE-GREEN CLOSURES (each named, each asserted):
     - popout never opened: assert the popup handle is non-null, #ptext
       exists, and its rendered height is > 0 — else every geometry reads 0
       and compares equal (the zero-denominator green).
     - nothing typed: real content is typed and asserted present, because an
       empty textarea in a large popout may not overflow at any height.
     - height-1 textarea: side-2 +1 overflow catches it (a 1px textarea grown
       to 2px still does not overflow a large popout, so side 2 reds); plus
       the fill-fraction assertion (taH >= 50% of innerH) reds on a tiny box.
     - main-shell composer changed instead: the main document.body is asserted
       NOT to carry .cmdpop, so a fill that landed on the dashboard composer
       would fail here while the popout read green.
     - holds at open but not after resize: both sides are re-proved after a
       viewport resize, because the fill must survive the user resizing the
       window, not only hold at open time.

   PATH EXERCISED: the command popout is opened. Headless Chromium reports
   documentPictureInPicture as available but Playwright surfaces it as a
   'popup' event in both the Doc-PiP and window.open cases — the guard reports
   which it observed. This guard exercises whichever path production takes in
   this Chromium; the other path is NOT separately verified.

   usage: node pipfill.mjs <outdir> [port]   (port defaults to the guards port) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { waitFor, waitForServer } from './dom.mjs';

const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'the command popout (opened via #cmdplus then #cmdpop) — measures ' +
          'textarea/documentElement/viewport geometry, grows the textarea by 1px ' +
          'to prove it would scroll, then resizes the popup and re-proves both sides',
  traceWindow: 'static reads after the popout DOM settles (~1.4s); the +1px probe ' +
               'is a synchronous reflow-and-restore inside one evaluate, not a motion trace',
});

// Read the live geometry of the popout document.
const measure = (p) => p.evaluate(() => {
  const ta = document.getElementById('ptext');
  const de = document.documentElement;
  if (!ta) return { missing: true };
  const r = ta.getBoundingClientRect();
  return {
    missing: false,
    taH: Math.round(r.height),
    taW: Math.round(r.width),
    taValue: ta.value,
    deSH: de.scrollHeight,
    deCH: de.clientHeight,
    innerH: window.innerHeight,
    bodyCmdpop: document.body.classList.contains('cmdpop'),
    hasPform: !!document.getElementById('pform'),
  };
});

// SIDE 2 — the maximal property. Freeze the textarea at its rendered height
// +1px (flex/min-height defeated so it cannot re-absorb the pixel) and read
// whether the document now overflows via documentElement.scrollHeight. The
// expectation comes from observed overflow (afterSH > afterCH), not from any
// height the production JS computes — so it cannot agree with a broken fill.
const plusOne = (p) => p.evaluate(() => {
  const ta = document.getElementById('ptext');
  const de = document.documentElement;
  if (!ta) return { missing: true };
  const H = Math.round(ta.getBoundingClientRect().height);
  const prev = { h: ta.style.height, mh: ta.style.minHeight, fl: ta.style.flex };
  ta.style.minHeight = '0'; ta.style.flex = 'none'; ta.style.height = (H + 1) + 'px';
  void ta.offsetWidth;
  const afterSH = de.scrollHeight, afterCH = de.clientHeight;
  ta.style.height = prev.h; ta.style.minHeight = prev.mh; ta.style.flex = prev.fl;
  void ta.offsetWidth;
  return { missing: false, H, afterSH, afterCH, overflowAfter: afterSH > afterCH };
});

try {
  await waitForServer(BASE);
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const p = await br.newPage({ viewport: { width: 1100, height: 820 } });
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(p, '#cmdplus');

  const isOpen = await p.evaluate(`!!document.querySelector('#cmdpalette.open')`);
  if (!isOpen) { await p.click('#cmdplus'); await sleep(700); }

  const hasPiP = await p.evaluate(
    `!!(window.documentPictureInPicture && window.documentPictureInPicture.requestWindow)`);
  notes.push(`documentPictureInPicture API available in this Chromium: ${hasPiP}`);

  const popP = p.waitForEvent('popup', { timeout: 8000 }).catch(() => null);
  await p.click('#cmdpop');
  const pop = await popP;

  // CLOSURE: the popout never opened. A null handle makes every geometry read
  // 0 and compare equal — so this is asserted before anything is measured.
  ok('the command popout opened (popup event captured)', !!pop);
  if (!pop) {
    notes.push('NO POPUP CAPTURED — every geometry check below is skipped');
    await br.close(); finish(); process.exit(0);
  }
  await pop.waitForLoadState('domcontentloaded').catch(() => {});
  await sleep(1400);

  if (!(await present(pop, '#ptext', 'the popout composer textarea #ptext'))) {
    await br.close(); finish(); process.exit(0);
  }

  // CLOSURE: nothing was typed, so nothing could scroll. Real content goes in
  // through the real box (input events), and its presence is asserted — an
  // empty textarea in a large popout may not overflow at any height.
  const TYPED = 'a thought for the dream that runs to more than one line so ' +
                'the box has real content and something could in fact scroll';
  await pop.fill('#ptext', TYPED);
  await pop.evaluate(
    `document.getElementById('ptext').dispatchEvent(new Event('input',{bubbles:true}))`);
  await sleep(120);

  let m = await measure(pop);
  // CLOSURE: the composer really rendered with non-zero geometry. taH > 0
  // refuses the zero-denominator green where a never-rendered box reads 0==0.
  ok('the popout textarea rendered with non-zero height ' +
     `(taH=${m.taH}, taW=${m.taW}, value present=${!!m.taValue})`,
     !m.missing && m.taH > 0 && m.taW > 0 && !!m.taValue);
  notes.push(`OPEN geometry: ${JSON.stringify(m)}`);
  await pop.screenshot({ path: `${OUT}/01-popout-open.png` });

  // SIDE 1 — the document does not scroll.
  ok('SIDE 1 (open): the popout document does not scroll ' +
     `(deSH=${m.deSH} <= deCH=${m.deCH}, innerH=${m.innerH})`,
     !m.missing && m.deSH <= m.deCH);
  // FILL: the textarea must actually be filling (most of the viewport), not a
  // tiny box on a page that happens not to scroll. A small taH would pass
  // side 1 for the wrong reason.
  ok('the textarea is filling the popout, not sitting tiny ' +
     `(taH=${m.taH} vs innerH=${m.innerH}; fill fraction ` +
     `${m.innerH ? (m.taH / m.innerH).toFixed(2) : '?'})`,
     !m.missing && m.innerH > 0 && m.taH >= m.innerH * 0.5);

  // SIDE 2 — if it were any taller, it would scroll. THE assertion.
  let p1 = await plusOne(pop);
  ok('SIDE 2 (open): a textarea 1px taller would scroll ' +
     `(froze at H+1=${p1.H + 1}px; deSH ${p1.afterSH} > deCH ${p1.afterCH})`,
     !p1.missing && p1.overflowAfter);

  // CLOSURE: the main-shell composer was NOT changed instead.
  const mainProbe = await p.evaluate(() => {
    const ta = document.getElementById('cmdtext');
    const de = document.documentElement;
    return {
      bodyCmdpop: document.body.classList.contains('cmdpop'),
      cmdTextH: ta ? Math.round(ta.getBoundingClientRect().height) : null,
      innerH: window.innerHeight,
      deSH: de.scrollHeight, deCH: de.clientHeight,
    };
  });
  ok('the MAIN dashboard body does NOT carry .cmdpop (fill is popout-only)',
     mainProbe.bodyCmdpop === false);
  ok('the MAIN composer textarea is not viewport-filling ' +
     `(cmdTextH=${mainProbe.cmdTextH} vs innerH=${mainProbe.innerH})`,
     mainProbe.cmdTextH !== null && mainProbe.cmdTextH < mainProbe.innerH * 0.5);
  notes.push(`MAIN geometry: ${JSON.stringify(mainProbe)}`);

  // CLOSURE: holds at open but not after resize. Re-prove BOTH sides after
  // resizing the popup viewport.
  await pop.setViewportSize({ width: 360, height: 460 });
  await sleep(600);
  const mr = await measure(pop);
  ok('SIDE 1 (after resize): the popout document still does not scroll ' +
     `(deSH=${mr.deSH} <= deCH=${mr.deCH}, innerH=${mr.innerH})`,
     !mr.missing && mr.deSH <= mr.deCH);
  ok('after resize the textarea still fills ' +
     `(taH=${mr.taH} vs innerH=${mr.innerH}; fill fraction ` +
     `${mr.innerH ? (mr.taH / mr.innerH).toFixed(2) : '?'})`,
     !mr.missing && mr.innerH > 0 && mr.taH >= mr.innerH * 0.5);
  const p1r = await plusOne(pop);
  ok('SIDE 2 (after resize): a textarea 1px taller would still scroll ' +
     `(H=${p1r.H}; deSH ${p1r.afterSH} > deCH ${p1r.afterCH})`,
     !p1r.missing && p1r.overflowAfter);
  notes.push(`RESIZE geometry: ${JSON.stringify(mr)}`);
  await pop.screenshot({ path: `${OUT}/02-popout-resized.png` });

  await p.screenshot({ path: `${OUT}/03-main.png` });
  ok('no page errors', errs.length === 0);
  await br.close();
} catch (e) {
  errs.push('guard threw: ' + (e && e.stack ? e.stack : String(e)));
}

finish();
