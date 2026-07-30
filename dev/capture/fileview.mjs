/* fileview — #252: Rendered / Source for markdown at `/file`.

   His approved shape: one compact two-position switch beside the path
   heading, Rendered by default, Source showing the exact escaped bytes in the
   existing `<pre>`, deep-linkable with `?view=source` so a copied link
   preserves intent, and a mode change that rides the page's own dissolve with
   the heading and control HELD FIXED.

   FIVE CLAIMS HERE, and each is asserted in the one form that can fail on the
   bug it names:

     - **`?view=source` deep-links.** Loaded directly, not clicked — a switch
       that works only on click is exactly the bug a click test cannot see,
       and the whole point of the query parameter is the link he pastes.
     - **The bytes are the file.** `pre.textContent` is compared to the bytes
       on disk, and the pane is asserted to hold NO element children at all —
       not "no `tok-` span", which would pass on any other rewrite. His words:
       byte fidelity is the whole point of the mode and not a detail to
       optimise away, and #351's highlighter must never reach this pane.
     - **Rendered never executes.** The fixture carries a `<script>` and an
       `onerror` attribute; both are proved inert AND proved still VISIBLE as
       text, because silently dropping them would also pass an inertness check
       while losing the file's content.
     - **The swap is a transition, and the chrome does not move through it.**
       Traced per rAF: the incoming view must pass through the middle, the
       indicator must slide rather than jump, and the heading and the switch
       must be at the SAME position on every frame. An end-state check cannot
       fail on any of the three.
     - **Reduced motion is parity, not degradation.** Same words, same mode,
       same bytes, same restored reading position — with no ghost and no
       part-way frame on the identical measure.

   THIS GUARD BUILDS ITS OWN TARGET and takes its own ephemeral port. The
   shared fixture has no markdown file that is both hostile (script + inline
   handler) and long enough for the two modes to have DIFFERENT scroll ranges,
   and both are preconditions here rather than nice-to-haves: with equal
   ranges, restoring a ratio is indistinguishable from keeping a pixel offset,
   so the check would pass over a page that did neither.

   usage: node fileview.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join, dirname } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'one markdown file at /file in both modes: the default load, the ' +
          '?view=source deep link, a real click on the switch, a Tab+Enter on ' +
          'it, the 390px row, and the swap in normal and reduced motion — plus ' +
          'a non-markdown path, which must offer no switch at all',
  traceWindow: '1500ms per rAF from the click that starts the swap (DREAM_MS is ' +
               '1150ms), so the window outlives the dissolve by ~350ms and ' +
               'nothing later — no tick, no second gesture — can supply the ' +
               'movement being asserted. Everything else is a static read.',
});
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored. #461 made this adopt argv[3] so a squatter red-proof could aim, and
// because the recipe always passes {{port}} that silently forced this guard onto
// the shared server's port, where serveVerified rightly refused -- so the guard
// stopped running at all (#471). Registration is not execution.
const PORT = await freePort();

/* ── the target ───────────────────────────────────────────────────────────
   Hostile AND long, for the two reasons above. The hostile markup is markdown
   PROSE, not a fenced block, because a fence is escaped by a different line of
   the renderer and the reported risk is the paragraph path.

   No CRLF anywhere, and that omission is deliberate rather than an oversight:
   `read_text` opens in text mode, so Python's universal-newline translation
   turns \r\n into \n before the page ever sees it. A CRLF fixture would fail
   the byte-exactness check for a reason that is upstream of everything this
   guard is about — it is recorded in watch-design.md as a stated limit. */
const HOSTILE = [
  '# A hostile little document',
  '',
  'A paragraph carrying live markup: <script>window.__pwn = 1;</script> and',
  'an image handler <img src=x onerror="window.__pwn2 = 1"> and a quoted',
  'attribute value like class="danger" plus a bare & ampersand.',
  '',
];
// enough body that both modes scroll at 900px, and enough MARKUP that the two
// modes' heights genuinely differ (the source carries every `#`, `**` and `-`
// the rendered view spends on layout instead)
const BULK = [];
for (let i = 0; i < 40; i++) {
  BULK.push(`## Section ${i}`, '',
    `- **a bold bullet** in section ${i}, hard-wrapped the way the loop`,
    `  writes it, with \`a/backticked/path.md\` in it too`,
    `- another bullet, *emphasised*, long enough to reflow in the column`,
    '');
}
const MD = HOSTILE.concat(BULK).join('\n') + '\n';
const MD_PATH = '.dreamwork/docs/hostile-and-long.md';
const PY_PATH = 'not-markdown.txt';

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
mkdirSync(dirname(join(DIR, MD_PATH)), { recursive: true });
writeFileSync(join(DIR, MD_PATH), MD);
writeFileSync(join(DIR, PY_PATH), 'plain text, never a switch\n');
// the bytes as the guard will compare them: read back off disk, so the
// comparison is against the file rather than against the string in this script
const ON_DISK = readFileSync(join(DIR, MD_PATH), 'utf8');

/* #461: serveVerified replaces poll+/data.json hand-check so a stranger on
   the port cannot be graded (and so a forced argv port can red-proof). */
const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
const URL_R = `${BASE}/file?p=${encodeURIComponent(MD_PATH)}`;
const URL_S = `${URL_R}&view=source`;

/* transitions.md's one idiom, verbatim (reviewsplit / headertravel / qsec /
   filehead): frames strictly BETWEEN the ends with a 3% deadband. A snap has
   none at any frame rate, which is why this is not a count of positions. */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};
const span = vals => Math.abs(vals.at(-1) - vals[0]);
const spread = pts => Math.max(...pts.map(p => Math.abs(p[0] - pts[0][0])),
                               ...pts.map(p => Math.abs(p[1] - pts[0][1])));

/* Tag nothing, measure everything, and START THE TRACE BEFORE THE CLICK — a
   trace begun after the gesture has already missed the frames that decide
   whether it was a travel or a teleport.

   The chrome is a SIBLING of #view, so nothing measured here sits beneath the
   mid-transform ancestor the dissolve creates (transitions.md's rule about
   visual space); the heading and switch rects are therefore honest. #view's
   own opacity is a computed style, not a rect, and is unaffected either way. */
const TRACE = (sel, ms) => `((sel, ms) => new Promise(res => {
  const frames = [];
  const at = el => { const r = el.getBoundingClientRect();
                     return [+r.left.toFixed(2), +r.top.toFixed(2)]; };
  const t0 = performance.now();
  (function step() {
    const v = document.getElementById('view');
    const h = document.getElementById('htitle');
    const g = document.querySelector('#meta .fmodes');
    const ind = g && g.querySelector('.sgind');
    frames.push({
      t: Math.round(performance.now() - t0),
      op: +getComputedStyle(v).opacity,
      head: h ? at(h) : null,
      ctl: g ? at(g) : null,
      ind: ind ? +(ind.getBoundingClientRect().left -
                   g.getBoundingClientRect().left).toFixed(2) : null,
      ghost: !!document.querySelector('.ghost'),
      pre: !!document.querySelector('#filebody > pre'),
      md: !!document.querySelector('#filebody > .md'),
    });
    if (performance.now() - t0 < ms) requestAnimationFrame(step);
    else res(frames);
  })();
  const a = document.querySelector(sel);
  if (!a) { res(frames); return; }
  a.click();
}))(${JSON.stringify(sel)}, ${ms})`;

const readMode = () => `(() => {
  const on = [...document.querySelectorAll('.fmode')]
    .filter(a => a.classList.contains('on')).map(a => a.dataset.mode);
  const cur = [...document.querySelectorAll('.fmode[aria-current]')]
    .map(a => a.dataset.mode);
  const pre = document.querySelector('#filebody > pre');
  const md = document.querySelector('#filebody > .md');
  return {
    on, cur, url: location.pathname + location.search,
    hasPre: !!pre, hasMd: !!md,
    preText: pre ? pre.textContent : null,
    // element children of the pane, of any kind: a highlighter, a linkifier
    // or any other rewrite shows up here, and 'no tok- span' would not
    preKids: pre ? pre.children.length : null,
    tokens: pre ? pre.querySelectorAll('[class*="tok-"]').length : null,
    // what the body says, whichever mode is up
    bodyText: document.getElementById('filebody').textContent,
    scripts: document.querySelectorAll('#filebody script').length,
    imgs: document.querySelectorAll('#filebody img').length,
    handlers: [...document.querySelectorAll('#filebody *')]
      .filter(e => [...e.attributes].some(a => /^on/i.test(a.name))).length,
    pwn: [typeof window.__pwn, typeof window.__pwn2],
    heading: document.getElementById('htitle').textContent,
  };
})()`;

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await browser.newContext({ viewport: { width: 1000, height: 900 } });
const page = await ctx.newPage();
page.on('pageerror', e => errs.push(String(e)));
await page.goto(URL_R, { waitUntil: 'networkidle' });
await sleep(700);

if (!(await present(page, '#meta .fmodes', 'the Rendered/Source switch')) ||
    !(await present(page, '#filebody', 'the file body'))) {
  try { srv.kill(); } catch (e) {}
  await browser.close(); finish();
} else {

// ── the default, and the precondition every "source is active" check needs ─
const rendered = await page.evaluate(readMode());
ok(`Rendered is the DEFAULT (on=${JSON.stringify(rendered.on)}), ` +
   `else every source assertion below is trivially true`,
   rendered.on.length === 1 && rendered.on[0] === 'rendered' &&
   rendered.hasMd && !rendered.hasPre);
ok('...and the URL stays clean when the default is in force',
   !rendered.url.includes('view='));
ok(`the heading is untouched by the mode (${JSON.stringify(rendered.heading)})`,
   rendered.heading === MD_PATH.slice(MD_PATH.lastIndexOf('/') + 1));

// PROOF 6 — Rendered renders markup as TEXT and never as behaviour.
// The precondition first, derived from the file: if the fixture lost its
// hostile bytes, "nothing executed" is a statement about an empty threat.
ok(`the fixture really carries live markup, else inertness is vacuous ` +
   `(<script> and onerror= present on disk)`,
   ON_DISK.includes('<script>') && ON_DISK.includes('onerror="'));
ok(`Rendered executes nothing (window.__pwn/__pwn2 = ` +
   `${JSON.stringify(rendered.pwn)})`,
   rendered.pwn[0] === 'undefined' && rendered.pwn[1] === 'undefined');
ok(`...and creates no <script>, no <img> and no inline handler ` +
   `(${rendered.scripts}/${rendered.imgs}/${rendered.handlers})`,
   rendered.scripts === 0 && rendered.imgs === 0 && rendered.handlers === 0);
/* The other half, and the half an inertness check alone would miss: a page
   that DELETED the markup is also inert, and has silently lost the file's
   content. It must be on screen, as characters. */
ok('...and shows the markup as text rather than dropping it',
   rendered.bodyText.includes('<script>window.__pwn = 1;</script>') &&
   rendered.bodyText.includes('onerror="window.__pwn2 = 1"'));

// PROOF 4 — the deep link, loaded rather than clicked.
const deep = await ctx.newPage();
deep.on('pageerror', e => errs.push(String(e)));
await deep.goto(URL_S, { waitUntil: 'networkidle' });
await sleep(700);
const src = await deep.evaluate(readMode());
ok(`?view=source DEEP-LINKS: loaded directly, Source is the active mode ` +
   `(on=${JSON.stringify(src.on)}, aria-current=${JSON.stringify(src.cur)})`,
   src.on.length === 1 && src.on[0] === 'source' &&
   src.cur.length === 1 && src.cur[0] === 'source');
ok('...and the body is the verbatim <pre>, not the rendered document',
   src.hasPre && !src.hasMd);

// PROOF 5 — the bytes are the file.
ok(`the fixture contains bytes a naive path would mangle, else byte-exactness ` +
   `is a weak claim (< & " all present)`,
   /</.test(ON_DISK) && /&/.test(ON_DISK) && /"/.test(ON_DISK));
ok(`Source holds the file's bytes EXACTLY ` +
   `(${(src.preText || '').length} of ${ON_DISK.length} chars)`,
   src.preText === ON_DISK);
ok(`...in one text node, with no rewrite of any kind ` +
   `(${src.preKids} element children, ${src.tokens} tok- spans)`,
   src.preKids === 0 && src.tokens === 0);
ok(`Source executes nothing either (${JSON.stringify(src.pwn)})`,
   src.pwn[0] === 'undefined' && src.pwn[1] === 'undefined' &&
   src.scripts === 0 && src.imgs === 0);
await deep.close();

// the switch is markdown-only
const other = await ctx.newPage();
await other.goto(`${BASE}/file?p=${encodeURIComponent(PY_PATH)}&view=source`,
                 { waitUntil: 'networkidle' });
await sleep(500);
const plain = await other.evaluate(() => ({
  sw: !!document.querySelector('#meta .fmodes'),
  pre: !!document.querySelector('#filebody > pre'),
}));
ok('a non-markdown path offers no switch, and is verbatim either way',
   !plain.sw && plain.pre);
await other.close();

// mobile: both labels in ONE row, neither hidden
const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
const pp = await phone.newPage();
await pp.goto(URL_R, { waitUntil: 'networkidle' });
await sleep(600);
const row = await pp.evaluate(() => {
  const as = [...document.querySelectorAll('.fmode')];
  const de = document.documentElement;
  const g = document.querySelector('.fmodes');
  const gs = getComputedStyle(g);
  const crumb = g.closest('.crumb');
  return {
    n: as.length,
    // The page's DECLARED decision, not only today's fit. Two labels fit in
    // 390px whatever `flex-wrap` says, so the observable check below cannot
    // fail on a wrap rule that was silently overridden — and one was:
    // `.sgroup` re-declares `display:flex; flex-wrap:wrap` later in the sheet
    // at the same specificity, which made the switch a BLOCK flex container
    // and broke its own crumb in two.
    display: gs.display, flexWrap: gs.flexWrap,
    // ...and the consequence that was actually visible: the crumb must be ONE
    // line tall, so its separator cannot orphan above its content.
    crumbH: +crumb.getBoundingClientRect().height.toFixed(1),
    groupH: +g.getBoundingClientRect().height.toFixed(1),
    tops: as.map(a => Math.round(a.getBoundingClientRect().top)),
    shown: as.every(a => { const cs = getComputedStyle(a);
      return cs.display !== 'none' && cs.visibility !== 'hidden' &&
             a.getBoundingClientRect().width > 4; }),
    texts: as.map(a => a.textContent),
    overflow: de.scrollWidth - de.clientWidth,
  };
});
await pp.screenshot({ path: `${OUT}/fileview-390.png` });
ok(`at 390px both labels are present and on ONE row ` +
   `(${JSON.stringify(row.texts)} at tops ${JSON.stringify(row.tops)})`,
   row.n === 2 && row.shown && new Set(row.tops).size === 1);
ok(`...because the switch DECLARES it, not because two words happened to fit ` +
   `(display:${row.display}, flex-wrap:${row.flexWrap})`,
   row.display === 'inline-flex' && row.flexWrap === 'nowrap');
ok(`...and its crumb is one line tall, so the separator cannot orphan above ` +
   `it (crumb ${row.crumbH}px vs group ${row.groupH}px)`,
   row.crumbH <= row.groupH + 1);
ok(`...and the page still does not scroll sideways (${row.overflow}px)`,
   row.overflow <= 0);
await phone.close();

// the switch is operable by keyboard, like everything else on this page
const kb = await ctx.newPage();
await kb.goto(URL_R, { waitUntil: 'networkidle' });
await sleep(600);
let stops = 0;
for (let i = 1; i <= 12; i++) {
  await kb.keyboard.press('Tab');
  const there = await kb.evaluate(() => document.activeElement &&
    document.activeElement.dataset && document.activeElement.dataset.mode === 'source');
  if (there) { stops = i; break; }
}
if (stops) { await kb.keyboard.press('Enter'); await sleep(1500); }
const kbMode = stops ? await kb.evaluate(readMode()) : null;
ok(`Source is reachable and activatable by keyboard alone (${stops || 'never'} stops)`,
   !!stops && kbMode.on[0] === 'source' && kbMode.hasPre);
await kb.close();

/* ── PROOF 7: the swap's motion, plus the reading position ───────────────── */
const runs = {};
for (const reduced of [false, true]) {
  const c = await browser.newContext({
    viewport: { width: 1000, height: 900 },
    reducedMotion: reduced ? 'reduce' : 'no-preference',
  });
  const p = await c.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL_R, { waitUntil: 'networkidle' });
  await p.waitForSelector('#filebody > .md', { timeout: 15000 });
  await sleep(700);
  /* THE MOTION TRACE RUNS AT THE TOP OF THE DOCUMENT, and that is not
     incidental. "Held fixed" is a claim about where the heading and the switch
     are on SCREEN while the body dissolves under them, and
     `getBoundingClientRect` is viewport-relative — so a trace taken while the
     scroll restore is moving the viewport reports the scroll delta (403px
     here) as chrome drift. Two different claims, so two different gestures:
     fixity where the chrome is actually visible, and the reading position on a
     second page below. */
  const frames = await p.evaluate(TRACE('.fmode[data-mode="source"]', 1500));
  await sleep(300);
  const mode = await p.evaluate(readMode());
  if (!reduced) await p.screenshot({ path: `${OUT}/fileview-source.png` });

  /* ...and the reading position, on its own page because it needs a scrolled
     start and the trace above needs an unscrolled one. */
  const sp = await c.newPage();
  sp.on('pageerror', e => errs.push(String(e)));
  await sp.goto(URL_R, { waitUntil: 'networkidle' });
  /* Wait for the rendered PANE, not for the network. `/filedata` is fetched by
     the router after load, so `networkidle` plus a sleep can still measure a
     `loading…` placeholder as the whole document — the range then reads 0 and
     the ratio checks red on a healthy commit. It happened twice while
     red-proving this guard, under three concurrent browsers, and a check that
     reddens with load is a load meter (transitions.md). */
  await sp.waitForSelector('#filebody > .md', { timeout: 15000 });
  await sleep(700);
  const before = await sp.evaluate(() => {
    const bottom = (() => { let y = 0;
      for (let n = document.getElementById('view'); n; n = n.offsetParent) y += n.offsetTop;
      return y + document.getElementById('view').offsetHeight +
        (parseFloat(getComputedStyle(document.body).paddingBottom) || 0); })();
    const range = Math.max(0, bottom - window.innerHeight);
    window.scrollTo(0, Math.round(range * 0.5));
    return { range, y: window.scrollY };
  });
  await sleep(200);
  /* Clicked IN THE PAGE, not through Playwright's mouse. `page.click` scrolls
     its target into view first, and the switch lives at the top of the
     document — so the driver would scroll to 0 before the gesture and the
     ratio being restored would be the ratio it had just destroyed. It read
     `0.500 -> 0.000` and looked like a broken feature.

     Worth knowing rather than hiding: the same geometry means a POINTER user
     scrolled halfway down has to come back to the top to reach the switch, so
     the restore earns its keep on popstate (back/forward between the two
     modes) and on a keyboard activation, not on this click. */
  await sp.evaluate(() =>
    document.querySelector('.fmode[data-mode="source"]').click());
  await sleep(1600);
  const after = await sp.evaluate(() => {
    const bottom = (() => { let y = 0;
      for (let n = document.getElementById('view'); n; n = n.offsetParent) y += n.offsetTop;
      return y + document.getElementById('view').offsetHeight +
        (parseFloat(getComputedStyle(document.body).paddingBottom) || 0); })();
    const range = Math.max(0, bottom - window.innerHeight);
    return { range, y: window.scrollY,
             ratio: range > 0 ? window.scrollY / range : null };
  });
  const scrolledMode = await sp.evaluate(readMode());
  runs[reduced ? 'reduced' : 'normal'] = { before, frames, after, mode, scrolledMode };
  await c.close();
}
try { srv.kill(); } catch (e) {}
await browser.close();

for (const [name, r] of Object.entries(runs)) {
  const f = r.frames;
  const ops = f.map(x => x.op);
  const inds = f.map(x => x.ind).filter(v => v !== null);
  // it actually happened, in both contexts — the parity half of the pair
  ok(`${name}: the swap LANDS on Source with the file's bytes`,
     r.mode.on[0] === 'source' && r.mode.hasPre &&
     r.mode.preText === ON_DISK);
  ok(`${name}: the pane really changed during the window ` +
     `(md ${f[0].md ? 'yes' : 'no'} -> pre ${f.at(-1).pre ? 'yes' : 'no'}), ` +
     `else every motion assertion below is about a page that did nothing`,
     f[0].md && f.at(-1).pre);
  /* HELD FIXED — his word. The heading and the control must be in the same
     place on every frame of the swap, so the eye has an anchor while the body
     dissolves under it. A rect per frame is the only way to see the 2px
     reflow an end-state comparison would call identical. */
  ok(`${name}: the heading is HELD FIXED through the swap ` +
     `(max ${spread(f.map(x => x.head)).toFixed(2)}px of drift, at scroll 0)`,
     spread(f.map(x => x.head)) < 1);
  ok(`${name}: the switch is held fixed too ` +
     `(max ${spread(f.map(x => x.ctl)).toFixed(2)}px)`,
     spread(f.map(x => x.ctl)) < 1);
  if (name === 'normal') {
    ok('normal: the outgoing pane becomes a ghost (it departs, it does not vanish)',
       f.some(x => x.ghost));
    ok(`normal: the incoming pane really changes opacity, else the travel ` +
       `check is vacuous (${Math.min(...ops).toFixed(2)} -> ` +
       `${Math.max(...ops).toFixed(2)})`,
       Math.max(...ops) - Math.min(...ops) >= 0.5);
    ok(`normal: it DISSOLVES — frames strictly part-way, at any frame rate ` +
       `(${between(ops, Math.min(...ops), Math.max(...ops))} of ${ops.length})`,
       between(ops, Math.min(...ops), Math.max(...ops)) >= 1);
    ok(`normal: the indicator really moves, else its travel check is vacuous ` +
       `(${span(inds).toFixed(1)}px)`, span(inds) >= 20);
    ok(`normal: the indicator SLIDES to the other label rather than jumping ` +
       `(${between(inds, inds[0], inds.at(-1))} of ${inds.length} part-way)`,
       between(inds, inds[0], inds.at(-1)) >= 1);
    /* Timing-free arrival (transitions.md): no frame goes PAST the end. An
       "arrived by t=Nms" assertion measures the guard's own click latency and
       breaks as soon as the travel distance changes. */
    ok('normal: ...and no frame overshoots its destination',
       inds.every(v => v <= Math.max(inds[0], inds.at(-1)) + 0.5 &&
                       v >= Math.min(inds[0], inds.at(-1)) - 0.5));
  } else {
    ok('reduced: no ghost at any frame', f.every(x => !x.ghost));
    ok(`reduced: the pane swaps instantly — no frame part-way ` +
       `(${between(ops, Math.min(...ops), Math.max(...ops))} of ${ops.length})`,
       between(ops, Math.min(...ops), Math.max(...ops)) === 0);
    ok(`reduced: the indicator LANDS on the other label in one step ` +
       `(${span(inds).toFixed(1)}px moved, ` +
       `${between(inds, inds[0], inds.at(-1))} part-way)`,
       span(inds) >= 20 && between(inds, inds[0], inds.at(-1)) === 0);
  }
  /* The reading position, and the precondition that gives it meaning: if the
     two modes had the SAME scroll range, restoring a ratio would be
     indistinguishable from keeping the pixel offset — and from doing nothing
     at all. Both ranges are derived at runtime; the gap is asserted. */
  ok(`${name}: the two modes have DIFFERENT scroll ranges, else the ratio ` +
     `restore is indistinguishable from doing nothing ` +
     `(${r.before.range.toFixed(0)}px -> ${r.after.range.toFixed(0)}px)`,
     r.before.range > 0 && r.after.range > 0 &&
     Math.abs(r.after.range - r.before.range) > 200);
  ok(`${name}: the scrolled page also lands on Source (the ratio check's own ` +
     `precondition)`,
     r.scrolledMode.on[0] === 'source' && r.scrolledMode.hasPre);
  ok(`${name}: the same reading RATIO survives the swap ` +
     `(0.500 -> ${(r.after.ratio === null ? NaN : r.after.ratio).toFixed(3)}; ` +
     `pixels ${r.before.y} -> ${r.after.y})`,
     r.after.ratio !== null && Math.abs(r.after.ratio - 0.5) <= 0.06);
  notes.push(`${name}: opacities ` +
    JSON.stringify(f.filter((_, i) => i % 4 === 0).map(x => [x.t, +x.op.toFixed(2)])));
  notes.push(`${name}: indicator ` +
    JSON.stringify(f.filter((_, i) => i % 4 === 0).map(x => [x.t, x.ind])));
}
ok('no page errors on any phase', errs.length === 0);
notes.push(`md path: ${MD_PATH} (${ON_DISK.length} bytes)`);
finish();
}
