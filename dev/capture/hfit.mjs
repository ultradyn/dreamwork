// #312 + #595 — no route scrolls the page sideways at phone width.
//
// #312 (the original): the command menu (`.cmdmenu`) lives in the PERSISTENT
// chrome, so it is on every route. It is `position:absolute` anchored to the ⋯
// button at the right end of the command-kinds row, and it used to declare
// `width:max(32ch,100%)` with `left:0` — so it grew rightward from the ⋯
// and poked ~122px past a 390px viewport. A `visibility:hidden` box is still
// LAID OUT (it is not `display:none`), so it counts toward
// `documentElement.scrollWidth` whether the palette is open or shut, and a
// phone could thumb the whole dashboard sideways. watch-design.md forbids
// that; this guard is the red light for it.
//
// #595 — WHY THIS GUARD WAS GREEN WHILE THE PAGE WAS BROKEN. A visual audit
// measured the live dashboard scrolling sideways by 28px at 390px, and
// `/file?p=DREAMWORK.md` by 32px, while this guard passed. Nothing was wrong
// with the assertion: it says `overflow <= 0` on each route at 390px, which is
// exactly the styleguide's promise. What was wrong is that it could not SEE the
// offenders, in two distinct ways, and both are the same mistake:
//
//   - THE FIXTURE'S UNBOUNDED VALUES WERE SHORT BY ACCIDENT. The two crumbs
//     that broke — `target` (an absolute checkout path) and `version` (an
//     arbitrary-length migration FILENAME) — carry values whose length is set by
//     DATA. The fixture's skill-version was `2026-07-25-fixture`, 18 characters,
//     against the live target's 42. The check ran; its subject was a value too
//     short to overflow. #312's own precondition already understood this shape
//     ("run it against nothing") and applied it to the MENU only — the subject
//     the guard was written for — so the two subjects it acquired later had no
//     precondition at all. Cured below: the fixture now carries a realistic
//     worst-case version name, and §0b FAILS if a future fixture edit shortens
//     it back under the width where it can prove anything.
//
//   - `/file` WAS NEVER IN THE LIST. The routes here are the param-less ones,
//     which is the honest reading of "every route reachable by plain
//     navigation" — and the styleguide sentence that promises no sideways
//     scroll is IN the file view's own section. Added below, on a planted doc.
//
// And a check with no expiry date, because both of the above are still checks
// against a particular string: §3 injects a 160-character value into every
// unbounded slot and re-measures. That is the contract as actually written —
// "the page never scrolls sideways" is a claim about ANY value, and a fixture
// tuned to today's is a guard that goes quiet the day the data changes.
//
// Ordinary guard shape: takes (OUT, PORT) — an output dir and a running
// watch server on the fixture. See dev/capture/README.md.
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39890';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: 'phone-width (390px) horizontal-overflow on /, /questions, ' +
          '/answers and /file (planted long path) with palette closed, / with ' +
          'the cmd menu open, and an injected 160-char value in every ' +
          'unbounded-length slot',
  traceWindow: 'static scrollWidth measurement per route after ~0.5-0.7s ' +
               'settle; no motion traced',
});
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

const PHONE = { width: 390, height: 844 };        // iPhone 12/13/14 class
const log = notes;

/* #595 — /file needs a rendered markdown pane holding a long known-internal
   path, and the fixture's prose is shared with a dozen other guards. So plant
   one, the way mdquote/mdtable do: the REFERENCED path is one the fixture
   already ships (so it is already in `linkable_paths` and there is no
   closed-set readiness race), and only the doc that mentions it is new.
   `just guards` resets the target before every guard, so this cannot leak. */
const data0 = await (await fetch(`${BASE}/data.json`)).json();
const TARGET = data0.target;
const LONG_PATH = '.dreamwork/docs/research/src/fixture-research-source.html';
const PLANT = 'hfit-longpath.md';
ok('precondition: the referenced long path is already in the closed set '
 + '(else /file renders it as plain code and this guard proves nothing)',
   Array.isArray(data0.linkable_paths) && data0.linkable_paths.includes(LONG_PATH));
writeFileSync(join(TARGET, PLANT),
  '# hfit long-path plant\n\n' +
  'A known-internal path long enough to reach the document edge at 390px:\n' +
  '`' + LONG_PATH + '` sits inline in ordinary prose, outside any `<details>`\n' +
  '— #595 note: `/questions` and `/` escaped this bug only because their long\n' +
  'paths sat inside CLOSED folds and had no geometry. That is luck, not\n' +
  'containment, so the plant is deliberately unfolded.\n');

// Every route reachable by plain navigation (the param-less ones), plus the
// file view — whose own styleguide section is where the promise is written.
const ROUTES = [
  ['dashboard', '/'],
  ['questions', '/questions'],
  ['answers',   '/answers'],
  ['filemd',    '/file?p=' + encodeURIComponent(PLANT)],
];

// Measure the document's horizontal overflow AND name the element whose right
// edge is furthest past the viewport, so a red names the offender rather than
// only the number.
//
// THE VERDICT IS `scrollWidth`, and it is also confirmed by an actual
// `scrollTo(9999,0)` — a reachable scroll position is the thing the reader
// experiences, and it cannot be produced by a phantom rect.
//
// THE CULPRIT NAME IS FILTERED ON `checkVisibility()` (#595). `visibility:
// hidden` keeps layout, so #312's own subject — a hidden menu poking out — must
// still be findable, and it is: `checkVisibility()` defaults to
// `visibilityProperty:false`, so a `visibility:hidden` box still counts. What it
// DOES exclude is content inside a closed `<details>`, which reports a non-zero
// `getBoundingClientRect()` while occupying no space at all. This page is
// disclosure-heavy; a naive rect sweep of it reported ~300 phantom offenders,
// and a guard that names the wrong element sends the next person to the wrong
// file. `display:none` reads zeros and is skipped as before.
async function measure(page) {
  return page.evaluate(async () => {
    const de = document.documentElement;
    window.scrollTo(9999, 0);
    await new Promise(r => requestAnimationFrame(r));
    const reachedX = Math.round(window.scrollX);
    window.scrollTo(0, 0);
    let culprit = null, maxRight = de.clientWidth;
    for (const el of document.querySelectorAll('*')) {
      if (el.checkVisibility && !el.checkVisibility()) continue;  // closed <details> etc
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;   // display:none / never laid out
      if (r.right > maxRight + 0.5) { maxRight = r.right; culprit = el; }
    }
    const id = culprit && culprit.id ? '#' + culprit.id
      : culprit && culprit.className ? '.' + String(culprit.className).split(/\s+/)[0]
      : culprit ? culprit.tagName.toLowerCase() : null;
    return {
      scrollWidth: de.scrollWidth,
      clientWidth: de.clientWidth,
      overflow: de.scrollWidth - de.clientWidth,
      reachedX,
      culprit: id,
      culpritRight: culprit ? +culprit.getBoundingClientRect().right.toFixed(1) : null,
    };
  });
}

// ── 0. Precondition: the subject this guard exists for must actually be in
//    the DOM, or "no overflow" is satisfied by an absent subject. The palette
//    carries the menu; the menu must carry at least one item rendered from
//    COMMANDS, or it has no width to overflow with. (README: "Run it against
//    nothing" / "Absence costs one line, not a timeout.")
{
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the #cmdpalette the guard measures first, not a fixed sleep (#428 class)
  await waitFor(page, '#cmdpalette');
  const subj = await page.evaluate(() => {
    const pal = document.getElementById('cmdpalette');
    const menu = document.getElementById('cmdmenu');
    return {
      palette: !!pal,
      menu: !!menu,
      items: menu ? menu.querySelectorAll('.cmdmenuitem').length : 0,
    };
  });
  log.push('subject: ' + JSON.stringify(subj));
  ok('command palette present in chrome', subj.palette);
  ok('cmd menu present and populated (guard is non-vacuous)',
     subj.menu && subj.items > 0);
  await ctx.close();
}

// ── 0b. #595's precondition, and the one #312 never wrote. The other two
//    subjects of this guard are the head's UNBOUNDED-LENGTH crumbs, whose
//    length comes from data. If the fixture's value is short, `overflow <= 0`
//    is satisfied by a value too small to prove anything and the guard reports
//    the same PASS it would report if the page were correct — which is exactly
//    what it did while the live dashboard scrolled 28px sideways.
//
//    The threshold is derived from the geometry, not chosen: the dashboard's
//    reading column is ~348px at 390px and the crumb row's font is ~0.8rem
//    monospace, so a value under ~40 characters fits on one line whatever its
//    wrapping says and cannot discriminate. `target` is NOT asserted this way —
//    it is `mktemp -d`'s path under `just guards` and its length is not the
//    fixture's to control — so §3 covers it instead, at a length nothing can
//    accidentally satisfy.
{
  const sv = (data0.files && data0.files['skill-version']) || '';
  log.push(`fixture skill-version: ${JSON.stringify(sv)} (${sv.length} chars); `
         + `target: ${TARGET} (${TARGET.length} chars)`);
  ok(`fixture's skill-version is long enough to overflow a 390px crumb row if it `
   + `could not wrap (${sv.length} chars, need >= 40) — else this guard passes `
   + `on a value too short to discriminate, which is #595`,
     sv.length >= 40);
}

// ── 1. The contract, per route, palette CLOSED: the document never scrolls
//    sideways at phone width. #312's bug is here — the hidden menu is laid out
//    off-screen and still pushes scrollWidth out. #595's two are here too: the
//    dashboard's `version`/`target` crumbs, and `/file`'s rendered `.mdfile`.
for (const [name, path] of ROUTES) {
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + path, { waitUntil: 'networkidle' });
  await sleep(500);
  const m = await measure(page);
  await page.screenshot({ path: `${OUT}/${name}-closed.png` });
  log.push(`${name} closed: scrollWidth=${m.scrollWidth} clientWidth=${m.clientWidth} `
         + `overflow=${m.overflow}px reachedX=${m.reachedX} culprit=${m.culprit} `
         + `right=${m.culpritRight}`);
  ok(`${name}: no horizontal scroll at 390px closed `
   + `(overflow ${m.overflow}px${m.culprit ? ', ' + m.culprit : ''})`,
     m.overflow <= 0);
  // The number and the experience, separately: `scrollWidth` is a measurement,
  // a reachable scroll offset is what the reader can actually do to the page.
  ok(`${name}: scrollTo(9999,0) moves the page nowhere (reachedX ${m.reachedX})`,
     m.reachedX === 0);
  await ctx.close();
}

// ── 2. The contract with the menu actually OPEN, on the dashboard: a fix
//    that only suppresses the closed-state overflow (e.g. display:none until
//    hovered) would re-introduce it the moment he opens the palette and
//    hovers the ⋯. The real-world failure is a phone scrolling sideways while
//    he uses the composer, so the open state is checked too.
{
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await sleep(500);
  await page.click('#cmdplus');
  await sleep(600);                                 // palette reveal (.5s)
  await page.hover('.cmdmorebtn');
  await sleep(500);                                 // menu reveal (.34s)
  const m = await measure(page);
  await page.screenshot({ path: `${OUT}/dashboard-menu-open.png` });
  log.push(`dashboard menu-open: scrollWidth=${m.scrollWidth} clientWidth=${m.clientWidth} `
         + `overflow=${m.overflow}px culprit=${m.culprit} right=${m.culpritRight}`);
  ok(`dashboard: no horizontal scroll at 390px with menu open `
   + `(overflow ${m.overflow}px${m.culprit ? ', ' + m.culprit : ''})`,
     m.overflow <= 0);
  await ctx.close();
}

// ── 3. #595, THE CHECK WITH NO EXPIRY DATE. Everything above is still a check
//    against a particular string. The contract is not "this fixture's values
//    fit" — it is "the page never scrolls sideways", which is a claim about ANY
//    value, and every slot named here holds one the design does not choose:
//    an absolute checkout path, a migration filename, a repo-relative path in
//    prose. Two checkouts deeper, or one longer migration slug, and a check
//    tuned to today's data goes quiet without anyone touching the page.
//
//    So put 160 characters in each of them, in the live DOM, and re-measure.
//    Nothing accidental satisfies that: 160 monospace characters at 0.8rem is
//    ~4x the reading column. The injection is measured SYNCHRONOUSLY, inside one
//    evaluate — the live tick's `renderChrome` rewrites a crumb whose html
//    changed, and would put the real value back within the second.
const HUGE = 'z'.repeat(160);
for (const [name, path, slots] of [
  ['dashboard', '/', '.crumb .wrapany'],
  ['filemd', '/file?p=' + encodeURIComponent(PLANT), '.mdfile code a .wrapany'],
]) {
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + path, { waitUntil: 'networkidle' });
  await sleep(500);
  const r = await page.evaluate(async ({ sel, huge }) => {
    const els = [...document.querySelectorAll(sel)];
    for (const el of els) el.textContent = huge;
    const de = document.documentElement;
    void de.scrollWidth;                              // force layout
    window.scrollTo(9999, 0);
    await new Promise(f => requestAnimationFrame(f));
    const reachedX = Math.round(window.scrollX);
    window.scrollTo(0, 0);
    return { injected: els.length, reachedX,
             overflow: de.scrollWidth - de.clientWidth };
  }, { sel: slots, huge: HUGE });
  log.push(`${name} stress(${slots}): injected=${r.injected} `
         + `overflow=${r.overflow}px reachedX=${r.reachedX}`);
  // Absence first — an injection into zero elements is a check against nothing,
  // and it would report the same clean overflow the fixed page reports.
  ok(`${name}: the unbounded slot \`${slots}\` exists to inject into `
   + `(found ${r.injected})`, r.injected > 0);
  ok(`${name}: 160 chars in \`${slots}\` still does not scroll the page sideways `
   + `(overflow ${r.overflow}px, reachedX ${r.reachedX}) — the contract is about `
   + `any value, not today's`,
     r.injected > 0 && r.overflow <= 0 && r.reachedX === 0);
  await page.screenshot({ path: `${OUT}/${name}-stress.png` });
  await ctx.close();
}

// ── 4. #506 SURVIVES THE #595 FIX, AT EVERY LENGTH. `.mdfile` keeps its
//    `white-space:nowrap` and the wrapping is bought at the emit site instead:
//    `mdFileUnit` splits the path so everything but its last few characters
//    rides a `.wrapany` span and the tail stays bare in the unit's nowrap. The
//    claim is asserted GEOMETRICALLY — the pip shares a line box with the
//    path's last fragment — rather than by reading back a computed style,
//    because a computed style cannot tell you where Chromium put the break.
//
//    IT IS A LENGTH SWEEP, and that is not thoroughness — the single-length
//    version of this check went GREEN on its own red proof, and the fix that
//    shipped is not the one that was written first BECAUSE of it. Whether the
//    pip orphans depends on `len mod lineCapacity`: one length tests one
//    residue and passes on ~93% of them. The sweep walks a range wide enough to
//    contain every residue, which makes it a check about the RULE rather than
//    about a string. The `.wrapany` head is what varies — that is production's
//    own shape, so a build that stopped splitting the path fails here.
{
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(BASE + '/file?p=' + encodeURIComponent(PLANT),
                  { waitUntil: 'networkidle' });
  await sleep(500);
  const r = await page.evaluate(() => {
    const unit = document.querySelector('.mdfile');
    if (!unit) return { unit: false };
    const code = unit.querySelector('code'), pip = unit.querySelector('.pipbtn');
    const a = code && code.querySelector('a');
    const head = a && a.querySelector('.wrapany');
    if (!code || !pip || !a || !head)
      return { unit: true, code: !!code, pip: !!pip, a: !!a, head: !!head };
    const orphans = [], wrapped = [];
    const LO = 30, HI = 160;
    for (let len = LO; len <= HI; len++) {
      head.textContent = 'z'.repeat(len);
      void unit.offsetWidth;                          // force layout
      const rects = [...code.getClientRects()];
      const last = rects[rects.length - 1];
      const pr = pip.getBoundingClientRect();
      if (rects.length > 1) wrapped.push(len);
      if (Math.abs((last.top + last.height / 2) -
                   (pr.top + pr.height / 2)) >= 6) orphans.push(len);
    }
    return { unit: true, code: true, pip: true, a: true, head: true,
             lo: LO, hi: HI, swept: HI - LO + 1, orphans,
             wrappedCount: wrapped.length };
  });
  log.push('mdfile pip sweep: ' + JSON.stringify(r));
  ok('the planted long path renders as a .mdfile unit with a <code>, an <a>, '
   + 'a .wrapany head and a pip — the emit still splits the path',
     r.unit === true && r.code === true && r.pip === true && r.a === true &&
     r.head === true);
  ok(`the swept lengths actually WRAP the path at 390px `
   + `(${r.wrappedCount} of ${r.swept} lengths took more than one line box) — `
   + `else "the pip did not orphan" is a claim about a path that never broke`,
     r.wrappedCount > 0);
  ok(`the pip shares a line box with the path's LAST fragment at EVERY swept `
   + `length ${r.lo}..${r.hi} (orphaned at ${JSON.stringify(r.orphans)}) — #506 `
   + `holds under the #595 wrap`,
     Array.isArray(r.orphans) && r.orphans.length === 0);
  await page.screenshot({ path: `${OUT}/filemd-pip.png` });
  await ctx.close();
}

await browser.close();
finish();
