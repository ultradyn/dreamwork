/* markrail — #367 increment 2a: the flag rail lands settled, and it fits.

   His idea: thin postit flags at a review's essentials, with next/prev, because
   reviews run to twenty screens. Increment 2a renders the rail (the tab at each
   passage's height) and next/prev ABOVE the cliff only; below it, nothing. The
   rail is CSS-only — the artifact is offline-clean (no script), so "current" is
   :target and next/prev are real fragment links.

   This guard proves the things a source-text check cannot:

     - the worst-case flag FITS inside .wrap at the cliff (the boundary the
       pytest reads as geometry, proven here in pixels — the half that catches a
       flag that grew past the slack, or a cliff that moved below where it fits);
     - next/prev LANDS SETTLED on the marked element, not as a journey
       (transitions.md: a long-range smooth scroll is refuted; the template
       declares no scroll-behavior, so the jump is the function). Traced
       part-way: an instant jump has no frame between the ends; a smooth scroll
       has many. The red is `html{scroll-behavior:smooth}`;
     - the arriving flag's change of state (opacity, the page's idiom) TRAVELS
       under normal motion and is instant under reduced motion — timing changes,
       function and legibility do not (transitions.md's hard contract);
     - the flag anchors at the READING COLUMN's edge (the `.marktab` outer box
       inherits the body font so `--measure:78ch` resolves in body ch, not the
       tab's smaller font — a one-element flag would sit at the wrong column);
     - below the cliff NOTHING renders (absent, not a broken flag);
     - flags are FOCUSABLE, next/prev is reachable, and the current passage is
       announced (each host carries tabindex="-1", each flag is a labelled link);
     - two flags closer than a tab height (a section and its first marked child)
       do not OVERLAP — the renderer's problem, not the author's.

   It BUILDS ITS OWN artifact (a source with a worst-case label and a close
   parent-child pair) through the real review_artifact.py and loads it via
   file://, like dev/capture/marktab-geometry.mjs: the rail is a property of the
   artifact, not of the server, and file:// is the most direct proof. The port
   arg is accepted for the runner's signature and unused.

   usage: node dev/capture/markrail.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { execSync } from 'node:child_process';
import { mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../..');
const OUT = process.argv[2] || join(REPO, '.dreamwork/docs/measurements/367-markrail');
const SCRATCH = '/tmp/367-markrail';
mkdirSync(OUT, { recursive: true });

const r = makeReporter();
const { ok, present, declare, finish, checks, notes, errs } = r;
declare({
  drives: 'a built review artifact with essential marks, loaded via file:// at ' +
          'the cliff viewport and below it; next/prev driven by real clicks',
  traceWindow: '~900ms after each next/prev click — an instant jump finishes in ' +
               'one frame, a smooth scroll fills the window with part-way frames'
});

const sleep = ms => new Promise(res => setTimeout(res, ms));

/* ── read the cliff and the flag's max-width from the template, the same way
   the pytest does, so the guard and the pytest agree on what "the cliff" is. */
const TEMPLATE = readFileSync(join(REPO, 'review-artifact.template.html'), 'utf8');
function cliffPx() {
  for (const m of TEMPLATE.matchAll(/@media\s*\(\s*max-width\s*:\s*([0-9.]+)px\s*\)\s*\{[^@]*?\.marktab\s*\{[^}]*display\s*:\s*none/gs))
    return Math.round(parseFloat(m[1])) + 1;
  return null;
}
const CLIFF = cliffPx();
notes.push(`cliff read from template: ${CLIFF}px (rail shows at/above it, nothing below)`);

/* ── build the fixture artifact through the real builder ──────────────────
   A worst-case ~6-word label (the one the geometry was measured against), a
   few typical marks to walk with next/prev, and a section whose FIRST child is
   also marked — the measured densest pair (29px against a 32px tab). */
const SRC_DIR = join(SCRATCH, 'src');
rmSync(SCRATCH, { recursive: true, force: true });
mkdirSync(SRC_DIR, { recursive: true });
writeFileSync(join(SRC_DIR, 'marks-rail.html'), `<!--dreamwork-review-source
title: #367 mark-rail guard fixture
identity: mark rail · guard
context: task #367 · the flag rail, above the cliff only
status: guard fixture
headline: The rail lands settled, and it fits.
skip: Skip to the marks
skip_href: #long
-->
<!--#lead-->
<p class="lead">A fixture for the mark-rail browser guard.</p>
<!--#body-->
<section aria-labelledby="crux-t">
  <div class="label" id="crux-t">The crux</div>
  <p class="read">The reading column is fixed and the flag anchors to its right edge.</p>
</section>
<section id="long" data-mark="reproducibility measurement against wrap geometry slack">
  <div class="label">The long passage</div>
  <p class="read">This is the worst-case ~6-word two-line label. The flag must fit inside the wrap at the cliff viewport, with margin to spare, and never clip past the page edge.</p>
  <p class="read">More body so the section is tall and the flag has room beneath it.</p>
</section>
<div style="height:900px" aria-hidden="true"></div>
<section id="findings" data-mark="the findings at a glance">
  <div class="label">Findings</div>
  <p class="read">A typical authored-length label walks next/prev in document order.</p>
</section>
<div style="height:900px" aria-hidden="true"></div>
<section id="decision" data-mark="the decision and its evidence">
  <div class="label">Decision</div>
  <p class="read">A third mark, so next/prev has a middle to walk through.</p>
</section>
<div style="height:900px" aria-hidden="true"></div>
<section id="close" data-mark="the close pair parent">
  <div class="label">Close pair</div>
  <p class="read" id="closechild" data-mark="the close pair child">This paragraph is the measured densest case: a section marked and its first reading paragraph marked, close together against a two-line tab. The child flag must stagger, not overlap.</p>
</section>
<!--#footer-->
Guard fixture for #367 · offline-clean, no external requests.
`);
let BUILT;
try {
  execSync(`python3 review_artifact.py build ${join(SRC_DIR, 'marks-rail.html')}`,
           { cwd: REPO, stdio: 'pipe' });
  BUILT = join(SCRATCH, 'marks-rail.html');
} catch (e) {
  ok('the guard built its own marks fixture through review_artifact.py', false);
  notes.push('build error: ' + String(e.message).slice(0, 200));
  finish();
  process.exit(1);
}
const URL_ = pathToFileURL(BUILT).href;

/* ── geometry + flag layout, read in one shot at a viewport ─────────────── */
const GEO = `(() => {
  const q = s => document.querySelector(s);
  const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
    return { l:+b.left.toFixed(1), t:+b.top.toFixed(1), r:+b.right.toFixed(1),
             b:+b.bottom.toFixed(1), w:+b.width.toFixed(1), h:+b.height.toFixed(1) }; };
  const wrap = q('.wrap'), read = q('p.read');
  const worst = document.querySelector('[data-mid="0"]');
  const worstHost = q('#long');
  const closeParent = document.querySelector('#close.is-marked .marktab');
  const closeChild = document.querySelector('#closechild.is-marked .marktab');
  return {
    vw: window.innerWidth,
    wrap: r(wrap), read: r(read),
    worst: r(worst), worstHost: r(worstHost),
    worstShown: worst ? getComputedStyle(worst).display !== 'none' : null,
    closeParent: r(closeParent), closeChild: r(closeChild),
    cliffHide: (() => { const t = q('.marktab');
      return t ? getComputedStyle(t).display : null; })(),
    scrollY: window.scrollY,
  };
})()`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const open = async (opts = {}) => {
  const ctx = await br.newContext({
    viewport: opts.viewport || { width: CLIFF || 860, height: 900 },
    reducedMotion: opts.reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL_, { waitUntil: 'load' });
  await sleep(300);
  return { ctx, p };
};

/* ── 1. the worst-case flag fits at the cliff, and anchors at the column ─── */
{
  const { ctx, p } = await open();
  if (!(await present(p, '.marktab', 'a flag (the rail)'))) { await ctx.close(); await br.close(); finish(); process.exit(1); }
  const g = await p.evaluate(GEO);
  notes.push(`cliff=${g.vw}: wrap ${g.wrap?.w}@${g.wrap?.l}..${g.wrap?.r}, read r=${g.read?.r}, ` +
    `worst flag ${g.worst?.w}x${g.worst?.h} @${g.worst?.l}..${g.worst?.r} (host top ${g.worstHost?.t})`);
  // the precondition: the cliff viewport really is where the pytest says the rail shows
  ok('the guard is testing at the cliff the template declares (else vacuous)',
     CLIFF != null && g.vw >= CLIFF);
  // fits inside .wrap — the pixel half of the pytest's geometry check
  ok('the worst-case flag fits inside .wrap at the cliff',
     g.worst.r <= g.wrap.r + 0.5);
  // and never past the page edge (a clipped flag is worse than none)
  ok('...and never clips past the page edge', g.worst.r <= g.vw + 0.5);
  // anchors at the reading column's right edge: the .marktab outer box inherits
  // the body font so --measure resolves in body ch; a one-element flag drifts.
  ok('the flag anchors at the reading column\'s right edge (within 2px)',
     Math.abs(g.worst.l - g.read.r - 4) <= 2);
  // the flag sits at its passage's top (a flag at a height, not a sidebar)
  ok('the flag sits at its passage\'s top', Math.abs(g.worst.t - g.worstHost.t) <= 2);
  await p.screenshot({ path: join(OUT, 'markrail-cliff.png') });
  await ctx.close();
}

/* ── 2. next/prev LANDS SETTLED — an instant jump, not a journey ──────────
   transitions.md: a long-range smooth scroll is refuted; the template declares
   no scroll-behavior, so fragment navigation jumps. Traced part-way: an instant
   jump has NO frame strictly between the start and the landing; a smooth scroll
   fills the window with them. The red is `html{scroll-behavior:smooth}`.

   …and the arrival's state change (opacity, the page's idiom) travels under
   normal motion and is instant under reduced. */
async function traceScroll(p, ms) {
  return p.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      seen.push(window.scrollY);
      if (performance.now() - t0 < ${ms}) requestAnimationFrame(step); else res(seen);
    })();
  })`);
}
async function traceOpacity(p, sel, ms) {
  return p.evaluate(({ s, ms }) => new Promise(res => {
    const el = document.querySelector(s); const seen = []; const t0 = performance.now();
    (function step() {
      seen.push(+getComputedStyle(el).opacity);
      if (performance.now() - t0 < ms) requestAnimationFrame(step); else res(seen);
    })();
  }), { s: sel, ms });
}
function betweenCount(seen) {
  // frames strictly between the trace's OWN endpoints, ~3% deadband so a frame
  // that really is an end does not read as travel (transitions.md's idiom). An
  // instant jump has none of these at any frame rate; a smooth scroll has many.
  const a = seen[0], b = seen.at(-1);
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03 || 1;
  return seen.filter(v => v > lo + eps && v < hi - eps).length;
}
async function targetTopAfter(p, id) {
  return p.evaluate(`(() => {
    const el = document.getElementById(${JSON.stringify(id)});
    return el ? +el.getBoundingClientRect().top.toFixed(1) : null;
  })()`);
}
{
  const { ctx, p } = await open();
  // establish a :target by clicking the first flag, so the arriving flag's
  // opacity transition has a real "from" state to travel from
  await p.locator('[data-mid="0"] .markflag').click();
  await sleep(600);
  const before = await p.evaluate(GEO);
  // trace scroll across the click: instant jump → the trace has only its two
  // endpoint values, 0 part-way; smooth scroll fills the window with them.
  const trace = traceScroll(p, 900);
  await sleep(40);
  await p.locator('[data-mid="0"] .marknext').click();
  const seen = await trace;
  await sleep(500);
  const after = await p.evaluate(GEO);
  const partway = betweenCount(seen);
  const reachedTop = await targetTopAfter(p, 'findings');
  notes.push(`next/prev: scrollY ${before.scrollY} -> ${after.scrollY} over ` +
    `${partway} of ${seen.length} frames part-way; #findings rect.top=${reachedTop}px`);
  // "reaches the passage": the element scrolled into the upper viewport (under
  // the sticky rail). Exact scrollY depends on scroll-padding + scroll-margin
  // + the rail, so the observable is the element's own position, not a number.
  ok('next/prev reaches the marked passage (it scrolls into the upper viewport)',
     reachedTop != null && reachedTop >= 0 && reachedTop <= 260);
  ok('...and LANDS SETTLED — an instant jump, not a smooth journey (0 part-way)',
     partway === 0);
  ok('...and the passage it landed on is now :target (current announced)',
     await p.evaluate('!!document.querySelector("#findings:target")'));

  // the arriving flag's opacity travels under normal motion (the page's idiom)
  // — reset to the first mark, then click next and trace the new current's opacity
  await p.locator('[data-mid="0"] .markflag').click();
  await sleep(600);
  const opTrace = traceOpacity(p, '[data-mid="1"]', 700);
  await sleep(40);
  await p.locator('[data-mid="0"] .marknext').click();
  const ops = await opTrace;
  const opPartway = betweenCount(ops);
  notes.push(`arrival opacity: ${ops[0]?.toFixed(2)} -> ${ops.at(-1)?.toFixed(2)} ` +
    `over ${opPartway} of ${ops.length} frames part-way`);
  ok('the arriving flag\'s state change travels (>=2 part-way opacity frames)',
     opPartway >= 2);
  await ctx.close();
}
/* reduced motion: the same jump, the same destination, and the state change is
   instant — timing changes, function and legibility do not */
{
  const { ctx, p } = await open({ reduced: true });
  await p.locator('[data-mid="0"] .markflag').click();
  await sleep(500);
  const trace = traceScroll(p, 600);
  await sleep(40);
  await p.locator('[data-mid="0"] .marknext').click();
  const seen = await trace;
  await sleep(300);
  const reachedTop = await targetTopAfter(p, 'findings');
  notes.push(`reduced next/prev: ${betweenCount(seen)} of ${seen.length} part-way; ` +
    `#findings rect.top=${reachedTop}px`);
  ok('reduced motion: next/prev still reaches the passage (function intact)',
     reachedTop != null && reachedTop >= 0 && reachedTop <= 260);
  ok('reduced motion: ...and still lands settled (0 part-way)',
     betweenCount(seen) === 0);
  await ctx.close();
}

/* ── 3. two flags closer than a tab height do not overlap ──────────────────
   The close pair: #close (section) and #closechild (its first .read). The
   child flag is staggered down (data-stagger). Their painted boxes must not
   overlap — the renderer's problem, not the author's. */
{
  const { ctx, p } = await open();
  const g = await p.evaluate(GEO);
  notes.push(`close pair: parent ${g.closeParent?.t}..${g.closeParent?.b}, ` +
    `child ${g.closeChild?.t}..${g.closeChild?.b}`);
  ok('the close pair both rendered flags (else vacuous)',
     !!g.closeParent && !!g.closeChild);
  if (g.closeParent && g.closeChild) {
    const overlap = Math.min(g.closeParent.b, g.closeChild.b) -
                    Math.max(g.closeParent.t, g.closeChild.t);
    ok('the close-pair flags do not overlap (child staggered clear)', overlap <= 0);
  }
  await ctx.close();
}

/* ── 4. below the cliff, NOTHING renders ───────────────────────────────────
   Absent, not a broken flag: the whole rail (flag + nav) lives inside .marktab,
   so the cliff's display:none removes all of it. */
{
  const below = Math.max(480, (CLIFF || 860) - 80);
  const { ctx, p } = await open({ viewport: { width: below, height: 900 } });
  const shown = await p.evaluate(`(() => {
    const t = document.querySelector('.marktab');
    return t ? { display: getComputedStyle(t).display,
                 rect: t.getBoundingClientRect() } : null;
  })()`);
  notes.push(`below cliff (${below}px): .marktab display=${shown?.display}, ` +
    `box ${JSON.stringify(shown?.rect)}`);
  ok(`below the cliff (${below}px) the rail renders nothing`,
     shown && (shown.display === 'none' || (shown.rect.width === 0 && shown.rect.height === 0)));
  await p.screenshot({ path: join(OUT, 'markrail-below-cliff.png') });
  await ctx.close();
}

/* ── 5. flags are focusable; next/prev is reachable; current is announced ── */
{
  const { ctx, p } = await open();
  // the hosts are focusable (tabindex="-1") so fragment nav announces them
  const hosts = await p.evaluate(`[...document.querySelectorAll('.is-marked')]
    .map(el => ({ id: el.id, tabindex: el.getAttribute('tabindex') }))`);
  ok('every marked host is focusable (tabindex="-1") so the current passage is announced',
     hosts.length > 0 && hosts.every(h => h.tabindex === '-1'));
  // the flags and the nav controls are real links in the tab order
  await p.locator('[data-mid="0"] .markflag').focus();
  const focusedTag = await p.evaluate(`document.activeElement && document.activeElement.tagName + '.' + (document.activeElement.className || '')`);
  ok('a flag is a focusable control (focus lands on it)', /markflag/.test(focusedTag));
  // Tab from a flag reaches the next control (the next-mark link when current)
  await p.keyboard.press('Tab');
  const afterTab = await p.evaluate(`document.activeElement && (document.activeElement.className || '')`);
  ok('Tab from a flag reaches another rail control', /mark(next|prev|flag)/.test(afterTab));
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finish();
