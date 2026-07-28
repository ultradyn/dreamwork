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
//   without scrolling  ->  ask.top < innerHeight  AND  firstChild.top < innerHeight
//
// Both halves matter. `ask.top < innerHeight` alone passes when the block starts
// one pixel above the fold and every word of it is below. The first-child check
// is what makes the pass mean "he can read a decision", which is the thing the
// briefs were reaching for.

import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';

const VIEWPORTS = [
  { label: 'desktop', width: 1280, height: 900 },
  { label: 'mobile', width: 390, height: 844 },
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
      const askOk = m.ask.top < m.innerHeight;
      parts.push(`#${id}.top=${m.ask.top} h=${m.ask.height} ${askOk ? 'above' : 'BELOW'}`);
      if (!askOk) ok = false;
      if (wantFirstChild) {
        if (!m.first) {
          ok = false;
          parts.push('first-decision NONE (no rendering child)');
        } else {
          const fOk = m.first.top < m.innerHeight;
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
