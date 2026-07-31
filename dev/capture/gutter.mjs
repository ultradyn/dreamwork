/* gutter — #597: the page never moves sideways because a scrollbar came or went.

   THE DEFECT. Some routes are tall (`/`, `/questions`, `/file`) and some are
   not (`/answers`, `/reviews`, `/research`, `/chat/<id>`). With a classic
   scrollbar, the tall ones take ~10px out of `clientWidth` and the short ones
   do not, so the centred column SNAPS 5px on every navigation between the two
   kinds. Measured by the 2026-07-31 visual audit at 1440x900: `#htitle`'s `x`
   visits exactly two values across a `/` -> `/answers` transition, 436.2 and
   441.2, while the scrollbar width goes 10 -> 0. One frame, no easing.

   WHY IT MATTERS ENOUGH TO GATE. transitions.md's whole premise is that the
   page "arrives and departs, it never appears", and the persistent chrome was
   hoisted out of `#view` precisely because a route change "read as 'the
   elements jump around' rather than as the page opening up". A 5px snap is that
   original complaint, reintroduced under the fix for it, on a page that spends
   real effort making a column-WIDTH change glide (`body.wsliding`). Five pixels
   is also exactly the size nobody notices deliberately and everybody feels,
   which is why it survived to a manual audit.

   WHY NO EXISTING GUARD COULD EVER HAVE SEEN IT — the finding this file exists
   to make permanent. Playwright passes `--hide-scrollbars` in headless by
   default, so in EVERY other guard in this directory the scrollbar has zero
   width and `clientWidth` never changes between routes. The whole class of
   scrollbar-driven layout effects is structurally invisible to the suite. This
   guard is the one that launches with

       ignoreDefaultArgs: ['--hide-scrollbars']

   and §0 refuses to grade anything until it has confirmed that flag actually
   produced a space-consuming scrollbar in THIS browser. Without that check a
   browser upgrade turns this file back into the green light it was written to
   replace, and nothing would say so.

   THE FIX IT GUARDS is one line in style.css — `html { scrollbar-gutter:
   stable; }` — which reserves the gutter on every route so the column never
   moves. Delete that line and §2 and §3 go red.

   Ordinary guard shape: takes (OUT, PORT) — an output dir and a running watch
   server on the fixture. usage: node gutter.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39890';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'a client-side nav between a TALL route (/) and a SHORT one ' +
          '(/answers) at 1440x900 and at 390x844, in a browser launched ' +
          'WITHOUT --hide-scrollbars so the scrollbar consumes width',
  traceWindow: 'rAF-sampled for ~40 frames across each transition — a snap is ' +
               'ONE frame, so a settled before/after read would miss a page ' +
               'that moved and moved back',
});

/* The one launch in dev/capture/ that keeps the scrollbar. See the header. */
const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
  ignoreDefaultArgs: ['--hide-scrollbars'],
});

const TALL = '/', SHORT = '/answers';
const read = () => ({
  x: +document.querySelector('#chrome .htitle').getBoundingClientRect().x.toFixed(1),
  wrapX: +document.querySelector('.wrap').getBoundingClientRect().x.toFixed(1),
  sb: window.innerWidth - document.documentElement.clientWidth,
  scrollH: document.documentElement.scrollHeight,
  innerH: window.innerHeight,
  gutter: getComputedStyle(document.documentElement).scrollbarGutter,
});

/* Sample every animation frame across a client-side nav. A snap lasts one
   frame; a before/after pair reads a page that jumped and came back as a page
   that never moved, which is the failure mode this whole file is about.

   THE WINDOW MUST CONTAIN THE SCROLLBAR FLIP, and this was written wrong first.
   A fixed 40 frames is ~660ms, and the departing route's content does not
   collapse to the new height until its dissolve completes — so the sampler saw
   `sb` at 10 for all 40 frames, ended before the scrollbar ever went away, and
   reported ONE x value against a page that was about to snap. It passed its own
   red proof. So the window runs until the flip is observed (plus a settle tail)
   rather than for a fixed count, and it reports `sbs` so §2 can refuse to grade
   a window that never saw the transition it exists to sample. */
async function xAcrossNav(page, href, { maxFrames = 300, tail = 20 } = {}) {
  return page.evaluate(async ({ href, maxFrames, tail }) => {
    const sbNow = () => window.innerWidth - document.documentElement.clientWidth;
    const seen = [], sb = [];
    const t = document.querySelector('#chrome .htitle');
    const sb0 = sbNow();
    const link = document.querySelector(`a[href="${href}"]`);
    if (link) link.click(); else location.href = href;
    let flippedAt = -1;
    for (let i = 0; i < maxFrames; i++) {
      await new Promise(r => requestAnimationFrame(r));
      const el = document.querySelector('#chrome .htitle') || t;
      seen.push(+el.getBoundingClientRect().x.toFixed(1));
      const s = sbNow();
      sb.push(s);
      if (flippedAt < 0 && s !== sb0) flippedAt = i;
      if (flippedAt >= 0 && i - flippedAt >= tail) break;
    }
    return { xs: [...new Set(seen)].sort((a, b) => a - b),
             sbs: [...new Set(sb)].sort((a, b) => a - b),
             flippedAt, path: location.pathname, frames: seen.length };
  }, { href, maxFrames, tail });
}

for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  const W = vp.width;
  const ctx = await browser.newContext({ viewport: vp });
  const page = await ctx.newPage();
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto(BASE + TALL, { waitUntil: 'networkidle' });
  await waitFor(page, '#chrome .htitle');
  await sleep(700);
  const tall = await page.evaluate(read);

  // ── 0. THE GUARD IS NOT BLIND. Everything below compares a scrolling route
  //    against a non-scrolling one, so BOTH halves of that premise are asserted
  //    first: the browser must give a scrollbar that consumes width, and the
  //    two routes must genuinely differ in whether they need one. If either is
  //    untrue the comparison is between two identical situations and passes for
  //    a reason that has nothing to do with the page.
  notes.push(`${W}px tall(${TALL}): ` + JSON.stringify(tall));
  ok(`${W}px: this browser's scrollbar consumes width (sb=${tall.sb}px) — else `
   + `--hide-scrollbars survived ignoreDefaultArgs and this guard is blind to `
   + `the entire class of bug it exists for`,
     tall.sb > 0);
  ok(`${W}px: ${TALL} is genuinely taller than the viewport `
   + `(${tall.scrollH} > ${tall.innerH}) — else it has no scrollbar to lose`,
     tall.scrollH > tall.innerH);

  // ── 1. The transition itself, frame by frame.
  const nav = await xAcrossNav(page, SHORT);
  await sleep(900);
  const short = await page.evaluate(read);
  notes.push(`${W}px short(${SHORT}): ` + JSON.stringify(short));
  notes.push(`${W}px nav ${TALL}->${SHORT}: x values ${JSON.stringify(nav.xs)} `
           + `sb values ${JSON.stringify(nav.sbs)} over ${nav.frames} frames, `
           + `scrollbar flipped at frame ${nav.flippedAt}`);
  ok(`${W}px: the nav actually landed on ${SHORT} (else the samples below are `
   + `frames of a page that never navigated)`,
     nav.path === SHORT);
  ok(`${W}px: ${SHORT} genuinely does NOT need a scrollbar `
   + `(${short.scrollH} <= ${short.innerH}) — the scrollbar-flip is the premise`,
     short.scrollH <= short.innerH);
  // The sampled window has to CONTAIN the event. Written as a fixed 40 frames
  // first, this ended ~660ms in, before the departing route's dissolve let the
  // page shrink, and reported one clean x value about a page that snapped a
  // moment later — green on its own red proof. Named as its own check so a
  // future timing change says "I stopped sampling too early" rather than "no
  // snap".
  ok(`${W}px: the sampled window contains the scrollbar flip `
   + `(sb values ${JSON.stringify(nav.sbs)} at frame ${nav.flippedAt} of `
   + `${nav.frames}) — else §2 below is a sample of a page mid-dissolve and `
   + `proves nothing`,
     nav.sbs.length > 1 && nav.flippedAt >= 0);

  // ── 2. THE CONTRACT. One x value across the whole transition. Stated on the
  //    SET of sampled values rather than on a start/end delta, because a value
  //    that appears for one frame and resolves is still a snap the eye catches
  //    and is exactly what the audit measured.
  ok(`${W}px: #htitle visits ONE x across the ${TALL} -> ${SHORT} transition `
   + `(saw ${JSON.stringify(nav.xs)}) — a second value is the 5px snap`,
     nav.xs.length === 1);

  // ── 3. And the settled positions agree, which is the same claim measured a
  //    different way: a direct load of each route puts the chrome in the same
  //    place, so arriving by link and arriving by URL cannot disagree either.
  ok(`${W}px: #htitle sits at the same x on a scrolling and a non-scrolling `
   + `route (${tall.x} vs ${short.x})`,
     tall.x === short.x);
  ok(`${W}px: the reading column sits at the same x on both `
   + `(${tall.wrapX} vs ${short.wrapX})`,
     tall.wrapX === short.wrapX);

  await page.screenshot({ path: `${OUT}/short-${W}.png` });
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await browser.close();
finish();
