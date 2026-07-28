// above_fold.mjs — the one shared above-the-fold check for review artifacts (#429, #430).
//
//   node dev/capture/above_fold.mjs <file-or-url> [--id ask] [--first-child]
//
// Exits 0 when every viewport passes, 1 otherwise. Prints one line per viewport
// with the numbers, always — a check that only speaks when it fails teaches
// nobody what the margin was.
//
// WHY THIS FILE EXISTS, AND IT IS TWO SEPARATE FAILURES
// ----------------------------------------------------
// 1. Every brief that asks the human to rule on something demands the ask be
//    above the fold. `#ask` existed on TWO of twenty-two built artifacts, so on
//    the other twenty the criterion could not be evaluated at all and had been
//    silently unenforced since the day it was written. Each lane rolled its own
//    inline measurement, or didn't, and nothing noticed either way.
//
// 2. The coordinator's own ad-hoc version measured with
//    `newPage({viewportSize:…})`. Playwright's option is `viewport`; the wrong
//    key is accepted in silence, so a "1280x900" run and a "390x844" run were
//    BOTH the default 1280x720. The tell was that they agreed to the byte —
//    identical scrollHeight for a 1280px and a 390px render, impossible for a
//    responsive page. Had the page happened to pass at 720 it would have been
//    reported as two viewports verified while one was checked.
//
//    That is a new flavour of hollow check and worth naming precisely: the
//    assertion was CORRECT and was applied to the WRONG PAGE. No amount of
//    scrutiny of the assertion finds it. Only asserting the precondition does.
//    Hence VIEWPORT_APPLIED below, which runs before any measurement and is not
//    optional or skippable.
//
// WHAT "ABOVE THE FOLD" MEANS HERE, AND WHY IT IS NOT `bottom < innerHeight`
// -------------------------------------------------------------------------
// The obvious criterion — the ask's bounding box ends within the first screen —
// is unachievable for any ask carrying more than one decision. #263's ask block
// is 870px tall because it holds three of them; demanding `bottom < innerHeight`
// there would mean splitting one coherent decision into three pages to satisfy a
// measurement. So the criterion is the measurable form of the actual intent:
//
//   the ask block STARTS above the fold, and its FIRST decision is reachable
//   without scrolling  ->  ask.top < FOLD  AND  firstChild.top < FOLD
//
// Both halves matter. `ask.top < FOLD` alone passes when the block starts one
// pixel above the fold and every word of it is below. The first-child check is
// what makes the pass mean "he can read a decision", which is the thing the
// briefs were reaching for.
//
// FOLD is deliberately not `innerHeight` — see the VIEWPORTS note below. He reads
// these inside an iframe, so `innerHeight` overstates the visible area by 40% on
// mobile, and a check that used it would pass an ask he cannot see.

import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';

// THE FOLD HE ACTUALLY SEES IS NOT THE VIEWPORT, and this was measured on the
// real surface rather than assumed. Artifacts are served to him inside an iframe
// on the dashboard's `/review` route (raw at `/reviewraw?p=`, for style
// isolation), so the shell's chrome eats the top (and, before #434, a large
// empty band under a fixed 60vh frame) of the page:
//
//   viewport 1280x900 -> iframe ~740px tall at top≈120  -> effective fold 738
//   viewport  390x844 -> iframe 672..708px tall           -> effective fold 670
//
// MOBILE IS A RANGE, AND A FOLD MUST TAKE THE FLOOR OF IT.
// The iframe's BOTTOM is pinned (828 at 390x844) but its TOP is not: on the
// stacked layout `SPAN.revname` in the title bar wraps to a second line once the
// artifact's filename is long enough, which makes the chrome 15px taller and the
// frame 15px shorter. Measured across six real artifacts at 390x844, strictly on
// `#reviewframe`:
//
//   top=120 h=708  tasks-page / ud-dreamtask / threaded-topic-chats   (<=25 chars)
//   top=135 h=693  task-transition-boundary / threaded-topic-chats-v2 /
//                  user-event-journal-implementation                  (>=28 chars)
//
// So the fold is 670, NOT 706 and NOT 691. Taking the top of the range would call
// content at y=700 "above the fold" while it is clipped for every long-named
// artifact — optimistic, which is the one direction that matters, because this
// file exists to refuse asks he cannot see.
//
// AND THE FLOOR DEPENDS ON THE TARGET DIRECTORY'S NAME, which is how 691 was
// wrong too. `SPAN.revname` shares the title bar with `#hproj`, the project name,
// and the project name IS the target dir's basename. Measured in the worktree
// `.worktrees/frame` the project reads `frame` (5 chars) and the floor is 693;
// on the real dashboard it reads `ud-dreamwork` (12) and the same artifact wraps
// one line further, floor 672. His dashboard is the second one. A fold verified
// in a worktree is not verified for the surface he uses — which is a fresh
// instance of measuring the wrong product, and it was caught only because the
// guard re-measures in place instead of trusting the number.
// The guard `devoverlay.mjs` now asserts this constant against the measured
// minimum rather than trusting the comment; the number and the check move
// together or the check is decoration.
//
// It also makes `#432` necessary rather than tidy: the offset is DATA-dependent,
// so no constant is right for all inputs — a longer name than any yet filed, or
// a name long enough to wrap at 1280, moves it again and nothing here would know.
//
// (#434 reclaimed the mobile dead space: the frame was 506px / fold 504 under
// a fixed 60vh; it now uses fitReview's measured --rvh, fills the window, and
// tightens the review-route bottom pad to 1rem on the stacked layout.)
// Mobile is still the one that matters: 670 against 844 is an ~21%
// overstatement of what a naive innerHeight check would claim. An ask sitting
// at 780px passes a naive 844 check and is invisible where he reads it. So
// `fold` below is the effective height, not `innerHeight`, and the viewport is
// still set to the real device size because layout depends on WIDTH.
// Measured 2026-07-28 (post-#434). These move if the shell's chrome changes,
// which is why `#432` wants the checker to derive them from the live route —
// and why `devoverlay.mjs` measures the real corpus in the real chrome and
// holds the mobile number to the floor it finds. The comment is no longer the
// only thing keeping this honest.
const VIEWPORTS = [
  { label: 'desktop', width: 1280, height: 900, fold: 738 },
  { label: 'mobile', width: 390, height: 844, fold: 670 },
];

function usage(msg) {
  console.error(msg ? `above_fold: ${msg}\n` : '');
  console.error('usage: node dev/capture/above_fold.mjs <file-or-url> [--id ask] [--no-first-child]');
  process.exit(2);
}

const argv = process.argv.slice(2);
if (!argv.length) usage('no target given');
let target = null, id = 'ask', wantFirstChild = true;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--id') { id = argv[++i]; if (!id) usage('--id needs a value'); }
  else if (a === '--no-first-child') wantFirstChild = false;
  else if (a.startsWith('--')) usage(`unknown flag ${a}`);
  else if (target === null) target = a;
  else usage('more than one target given');
}
if (!target) usage('no target given');
const url = /^[a-z]+:\/\//.test(target)
  ? target
  : 'file://' + (target.startsWith('/') ? target : `${process.cwd()}/${target}`);

const rows = [];
let failures = 0;
const browser = await chromium.launch();
try {
  for (const vp of VIEWPORTS) {
    // The right key is `viewport`. See the header: `viewportSize` is swallowed.
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForTimeout(250);

    const m = await page.evaluate((elId) => {
      const box = (e) => {
        const r = e.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height) };
      };
      const el = document.getElementById(elId);
      // The first element child that actually renders — a wrapper with zero
      // height is not the first decision, and neither is a hidden one.
      let first = null;
      if (el) {
        for (const c of el.children) {
          const r = c.getBoundingClientRect();
          if (r.height >= 8) { first = { tag: c.tagName.toLowerCase(), ...box(c) }; break; }
        }
      }
      return {
        innerWidth, innerHeight,
        scrollHeight: document.documentElement.scrollHeight,
        found: !!el,
        ask: el ? box(el) : null,
        first,
      };
    }, id);
    await page.close();

    // ---- PRECONDITION 1: VIEWPORT_APPLIED. Before anything is measured. ----
    // A wrong-keyed viewport option is accepted silently, so every figure below
    // would be the default 1280x720 wearing this viewport's label.
    if (m.innerWidth !== vp.width) {
      console.error(`FATAL ${vp.label}: asked for width ${vp.width}, page reports ${m.innerWidth} — `
        + `the viewport was NOT applied and every measurement here would be a different page. `
        + `Check the newPage option is 'viewport', not 'viewportSize'.`);
      process.exit(3);
    }
    // BOTH assertions are required and the height one is not redundant — this
    // was proved, not reasoned. Chromium's default viewport is 1280x720, and the
    // desktop case here asks for 1280x900. So when the option key is wrong the
    // WIDTH MATCHES ANYWAY (1280 === 1280) and only the height reveals it. A
    // width-only precondition would have passed the exact bug this file exists
    // for, at the exact viewport most artifacts are judged at. Do not simplify
    // these into one check.
    if (Math.abs(m.innerHeight - vp.height) > 40) {
      console.error(`FATAL ${vp.label}: asked for height ${vp.height}, page reports ${m.innerHeight}.`);
      process.exit(3);
    }

    // ---- PRECONDITION 2: the page must actually scroll. ----
    // An above-the-fold assertion passes trivially on a page that fits entirely,
    // so a short page would report a pass it never earned.
    const scrolls = m.scrollHeight > m.innerHeight;

    const parts = [];
    let ok = true;
    if (!m.found) {
      ok = false;
      parts.push(`#${id} MISSING`);
    } else {
      const askOk = m.ask.top < vp.fold;
      parts.push(`#${id}.top=${m.ask.top} h=${m.ask.height} ${askOk ? 'above' : 'BELOW'} fold(${vp.fold})`);
      if (!askOk) ok = false;
      if (wantFirstChild) {
        if (!m.first) {
          ok = false;
          parts.push('first-decision NONE (no rendering child)');
        } else {
          const fOk = m.first.top < vp.fold;
          parts.push(`first(${m.first.tag}).top=${m.first.top} ${fOk ? 'above' : 'BELOW'}`);
          if (!fOk) ok = false;
        }
      }
    }
    if (!scrolls) {
      ok = false;
      parts.push(`VACUOUS (scrollHeight ${m.scrollHeight} <= innerHeight ${m.innerHeight}: `
        + 'the page fits, so above-the-fold is not a claim about anything)');
    }

    if (!ok) failures++;
    rows.push(`${ok ? 'ok  ' : 'FAIL'} ${vp.label.padEnd(8)} ${vp.width}x${vp.height} `
      + `innerHeight=${m.innerHeight} scrollHeight=${m.scrollHeight} | ${parts.join(' | ')}`);
  }
} finally {
  await browser.close();
}

console.log(`above_fold: ${url}  (#${id}${wantFirstChild ? ' + first decision' : ''})`);
for (const r of rows) console.log('  ' + r);
if (failures) {
  console.log(`\nABOVE-FOLD CHECK FAILED — ${failures} of ${VIEWPORTS.length} viewport(s).`);
  console.log('The ask must START above the fold and its first decision must be readable there.');
  process.exit(1);
}
console.log(`\nabove-fold check passed — ${VIEWPORTS.length} viewport(s).`);
