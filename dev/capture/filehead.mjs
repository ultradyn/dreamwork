/* filehead — #284: the basename is the heading, the parent path is metadata,
   and the copy button hands back the EXACT path.

   His report, typed from the page: a full path like
   `.dreamwork/docs/research/contextual-review-annotations.md` competes with
   the document it names. His approved shape puts the basename on the primary
   line as a real heading, the parent beneath it as subdued selectable
   metadata, and a keyboard-reachable copy button beside it that copies the
   whole path.

   FOUR THINGS HERE CANNOT FAIL ANY EXISTING CHECK, and each is why this guard
   exists rather than a pytest substring:

     - **The split has to reassemble.** `heading + metadata === the path` is a
       property of two rendered elements, and the failure mode is a heading
       that quietly drops a segment or a metadata line that normalises one.
       Asserted as the concatenation, not as two remembered strings.
     - **The copy must be keyboard-only reachable and visibly focused.** A
       synthetic `el.click()` proves neither: it never enters the tab order and
       never sets `:focus-visible`. So this Tabs to the button and presses
       Enter and Space, and reads the clipboard back.
     - **The long path must WRAP, not shorten.** His reasoning: a path that
       lies about its own segments is worse than one that takes two lines. An
       end-state check on the text passes over an ellipsis (CSS truncation
       leaves `textContent` intact — the lie is in the pixels), so this asserts
       the declared properties AND the painted line boxes AND that nothing
       overflows the column, with the overflow CONDITION derived at runtime.
     - **The confirmation's DEPARTURE is a transition.** It holds ~5s and then
       fades, blurs and drifts. An end-state check ("the message is gone")
       cannot fail on a snap, so the departure is traced per rAF and asserted
       to have frames strictly part-way — and reduced motion is asserted to
       have NONE of them while keeping the same hold and the same words
       (transitions.md: timing, never function).

   THIS GUARD BUILDS ITS OWN TARGET and takes its own ephemeral port,
   gitrow.mjs-style. The reason is the wrap proof: the shared fixture's
   deepest path is `.dreamwork/dreams/…`, which fits one line at every width
   this guard measures, so every wrap check against it would pass over a page
   that ellipsised. The target it plants carries one directory segment
   deliberately longer than the reading column, so a break has to happen
   INSIDE a segment rather than at a slash.

   usage: node filehead.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
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
  drives: '/file at 520px and 1000px for a deep path and a root-level path: ' +
          'the heading/metadata split, the luminance order, Tab-then-Enter and ' +
          'Tab-then-Space on the copy button with the clipboard read back, a ' +
          'refused clipboard, and the wrap geometry; plus the confirmation\'s ' +
          'departure in normal and reduced motion',
  traceWindow: 'the confirmation departure is traced per rAF for 900ms starting ' +
               '4.8s after the copy — i.e. bounded to the hold\'s expiry, not to ' +
               'the whole 5s hold, so nothing else can supply the movement. ' +
               'Everything else is a static read after a settle.',
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
   ONE segment longer than the reading column, on purpose. Chrome offers a
   soft-wrap opportunity after `/`, so a path made only of short segments
   wraps at its slashes and never exercises `overflow-wrap:anywhere` at all —
   the property under test would be dead code and the check green over its
   absence. The long segment is what forces a break inside a segment. */
const LONG_SEG = 'a-single-directory-segment-longer-than-the-reading-column-can-hold';
const DEEP = `.dreamwork/docs/research/${LONG_SEG}/contextual-review-annotations.md`;
const ROOT_FILE = 'flat-file-at-the-root.md';
const BODY = [
  '# Contextual review annotations',
  '',
  'A paragraph so the rendered view has something to be, hard-wrapped at',
  'seventy-two columns the way the loop writes everything to disk.',
].join('\n');

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
mkdirSync(dirname(join(DIR, DEEP)), { recursive: true });
writeFileSync(join(DIR, DEEP), BODY + '\n');
writeFileSync(join(DIR, ROOT_FILE), BODY + '\n');

/* #461: serveVerified replaces poll + hand-check so a stranger cannot be graded. */
const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;

/* Frames strictly BETWEEN the two ends, with a 3% deadband so a frame that
   really is an end does not read as travel. transitions.md's one idiom,
   copied verbatim from reviewsplit.mjs / headertravel.mjs / qsec.mjs — it is
   deliberately not a second spelling. A snap has NO part-way frames at any
   frame rate, which is the whole reason this is not a count of positions. */
const between = (vals, a, b) => {
  const lo = Math.min(a, b), hi = Math.max(a, b), eps = (hi - lo) * 0.03;
  return vals.filter(v => v > lo + eps && v < hi - eps).length;
};

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* Tab from the document into the copy button. `el.click()` would activate it
   without ever entering the tab order, which is precisely the behaviour under
   test — so this walks the real focus ring and reports how many stops it
   took, because a button that needs eleven Tabs is a different bug from one
   that needs none. */
async function tabToCopy(page) {
  await page.evaluate(() => { document.body.focus(); document.activeElement.blur(); });
  for (let i = 1; i <= 12; i++) {
    await page.keyboard.press('Tab');
    const there = await page.evaluate(() =>
      !!(document.activeElement && document.activeElement.classList &&
         document.activeElement.classList.contains('fcopy')));
    if (there) return i;
  }
  return 0;
}

// relative luminance of a computed `rgb(...)`, so "brighter" is measured
// rather than asserted from the token names
const lum = css => {
  const [r, g, b] = (css.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
  const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

// ── phase 1: the lockup, at the narrow width where geometry is tightest ───
const ctx = await browser.newContext({
  viewport: { width: 520, height: 900 },
  permissions: ['clipboard-read', 'clipboard-write'],
});
const page = await ctx.newPage();
page.on('pageerror', e => errs.push(String(e)));
await page.goto(`${BASE}/file?p=${encodeURIComponent(DEEP)}`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the #htitle file head the guard reads first, not a fixed sleep (#428 class)
await waitFor(page, '#htitle');

if (!(await present(page, '#htitle', 'the file heading (#htitle)')) ||
    !(await present(page, '.fdir', 'the path metadata line (.fdir)')) ||
    !(await present(page, '.fcopy', 'the copy button (.fcopy)'))) {
  await browser.close(); finish();
} else {

const lockup = await page.evaluate(() => {
  const h = document.getElementById('htitle');
  const d = document.querySelector('.fdir');
  const cs = getComputedStyle(d), hs = getComputedStyle(h);
  // one rect per inline BOX, so group by top edge into real line boxes —
  // reflow.mjs's rule, for the same reason: rect count is not line count
  const tops = [...d.getClientRects()].map(r => Math.round(r.top));
  // The natural single-line width of the SAME text in the SAME font, so the
  // overflow condition is derived from today's layout instead of pinned to a
  // width some fixture happened to have.
  const probe = document.createElement('span');
  probe.textContent = d.textContent;
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;' +
                        'left:-9999px;top:0';
  probe.style.font = cs.font;
  document.body.appendChild(probe);
  const natural = probe.getBoundingClientRect().width;
  probe.remove();
  const de = document.documentElement;
  return {
    heading: h.textContent, headingTag: h.tagName,
    headingIsHeading: h.tagName === 'H1' ||
                      h.getAttribute('role') === 'heading',
    dir: d.textContent,
    lines: new Set(tops).size,
    natural, avail: document.getElementById('meta').clientWidth,
    /* The right edge of the FURTHEST line box, against the column's own right
       edge. NOT scrollWidth/clientWidth: `.fdir` is an inline box, so both of
       those read 0 and `scrollWidth <= clientWidth` is `0 <= 1` — true on a
       page that ellipsised, true on a page with no path at all. This guard
       shipped that version and it passed while measuring nothing. */
    inkRight: Math.max(...[...d.getClientRects()].map(r => r.right)),
    colRight: document.getElementById('meta').getBoundingClientRect().right,
    textOverflow: cs.textOverflow, whiteSpace: cs.whiteSpace,
    overflowWrap: cs.overflowWrap, clamp: cs.webkitLineClamp,
    direction: cs.direction, bidi: cs.unicodeBidi,
    userSelect: cs.userSelect || cs.webkitUserSelect,
    headColor: hs.color, dirColor: cs.color,
    pageOverflow: de.scrollWidth - de.clientWidth,
    describedby: document.querySelector('.fcopy').getAttribute('aria-describedby'),
    tag: document.querySelector('.fcopy').tagName,
  };
});

// PROOF 1 — the heading is the basename and the split loses nothing.
ok(`the heading is a real top-level heading (${lockup.headingTag})`,
   lockup.headingIsHeading);
ok(`the heading is the BASENAME alone (${JSON.stringify(lockup.heading)})`,
   lockup.heading === DEEP.slice(DEEP.lastIndexOf('/') + 1) &&
   !lockup.heading.includes('/'));
/* Derived, not two remembered strings: the metadata line and the heading must
   REASSEMBLE into the route's own path, character for character. A dropped
   segment, an inserted separator or a normalised `./` all fail here, and none
   of them fails "the heading looks right". */
ok(`metadata + heading === the exact path (${lockup.dir.length} + ` +
   `${lockup.heading.length} = ${DEEP.length} chars)`,
   lockup.dir + lockup.heading === DEEP);
ok('the metadata line keeps the segment boundary it really has (trailing /)',
   lockup.dir.endsWith('/'));
// the luminance hierarchy his approval asks for, measured rather than named
ok(`the heading outranks the path in LUMINANCE ` +
   `(${lum(lockup.headColor).toFixed(3)} vs ${lum(lockup.dirColor).toFixed(3)})`,
   lum(lockup.headColor) > lum(lockup.dirColor) * 1.2);
ok('the path is selectable text (the fallback when the clipboard is refused)',
   lockup.userSelect === 'text');
ok(`the copy button is a real <button> associated with the heading ` +
   `(describedby=${JSON.stringify(lockup.describedby)})`,
   lockup.tag === 'BUTTON' && /\bhtitle\b/.test(lockup.describedby || '') &&
   /\bfdir\b/.test(lockup.describedby || ''));

// PROOF 3 — it wraps, and it is never shortened.
ok(`the path really is too long for one line, else every wrap check below is ` +
   `vacuous (${lockup.natural.toFixed(0)}px of text in a ${lockup.avail}px row)`,
   lockup.natural > lockup.avail);
ok(`...and one SEGMENT is longer than the row, so the break has to happen ` +
   `inside a segment rather than at a slash (${LONG_SEG.length} chars)`,
   lockup.natural * (LONG_SEG.length / lockup.dir.length) > lockup.avail);
ok(`it wraps onto more than one line (${lockup.lines} line boxes)`,
   lockup.lines >= 2);
ok(`it is not ellipsised (text-overflow:${lockup.textOverflow}, ` +
   `white-space:${lockup.whiteSpace}, line-clamp:${lockup.clamp})`,
   lockup.textOverflow !== 'ellipsis' && !/nowrap|pre$/.test(lockup.whiteSpace) &&
   (lockup.clamp === 'none' || lockup.clamp === '' || lockup.clamp === 'auto'));
ok(`it breaks anywhere rather than refusing (overflow-wrap:${lockup.overflowWrap})`,
   /anywhere|break-word/.test(lockup.overflowWrap));
ok('no part of the path is painted outside the reading column ' +
   `(ink to ${lockup.inkRight.toFixed(0)}px, column ends ${lockup.colRight.toFixed(0)}px)`,
   lockup.inkRight <= lockup.colRight + 1);
ok('...and it is not reordered (no bidi override, no ellipsis character)',
   lockup.direction === 'ltr' && /normal|isolate/.test(lockup.bidi) &&
   !lockup.dir.includes('…'));
ok(`the page still does not scroll sideways at 520px ` +
   `(${lockup.pageOverflow}px)`, lockup.pageOverflow <= 0);

// PROOF 2 — copy by keyboard alone, focus-visible, and the success speaks.
const stops = await tabToCopy(page);
ok(`the copy button is reachable by Tab alone (${stops || 'never'} stops)`,
   stops > 0 && stops <= 6);
/* Wait on the FOCUSED ELEMENT'S OWN transitions, not on a sleep and not on
   every animation on the page. `.fcopy` transitions its colour and border over
   .3s, so a computed read taken on the frame after Tab catches the border
   11% of the way from transparent to the accent and reports
   `rgba(165,180,252,0.114)` — a real value, mid-travel, that looks like a
   wrong colour. transitions.md's rule, applied to a static assertion rather
   than to a trace: wait for the transition's completion, THEN assert. */
await page.evaluate(() => Promise.all(
  document.activeElement.getAnimations().map(a => a.finished.catch(() => {}))));
const focus = await page.evaluate(() => {
  const el = document.activeElement, cs = getComputedStyle(el);
  /* The accent RESOLVED, not spelled: the token's value is a styleguide
     decision and this must not need editing when it changes. */
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent)';
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  return { fv: el.matches(':focus-visible'),
           outlineStyle: cs.outlineStyle,
           outlineWidth: parseFloat(cs.outlineWidth) || 0,
           outlineColor: cs.outlineColor, accent,
           borderColor: cs.borderColor, color: cs.color };
});
ok('...and Tab lands it in :focus-visible', focus.fv);
ok(`...with a ring that is actually drawn, not a colour shift ` +
   `(outline ${focus.outlineStyle} ${focus.outlineWidth}px)`,
   focus.outlineStyle !== 'none' && focus.outlineWidth > 0);
/* A FINDING, recorded because it cost a red run that came back green: the
   check above passes on Chromium's DEFAULT `:focus-visible` ring, so deleting
   this page's own focus rule left it green — it was asserting the browser, not
   the page. The ring has to be the page's OWN, in the page's own accent, or a
   dark surface gets a foreign white halo and the styleguide has no say. The
   accent is resolved from the token at runtime, never spelled here. */
ok(`...and it is THIS PAGE's ring, in the accent ` +
   `(${focus.outlineColor} vs accent ${focus.accent})`,
   focus.outlineColor === focus.accent);
ok(`...and focus is not merely hover restated (border ${focus.borderColor})`,
   focus.borderColor === focus.accent);

await page.keyboard.press('Enter');
await sleep(250);
const okMsg = await page.evaluate(async () => {
  const m = document.getElementById('fmsg');
  let clip = null;
  try { clip = await navigator.clipboard.readText(); } catch (e) { clip = 'ERR:' + e; }
  return { text: m.textContent, cls: m.className, clip };
});
ok(`Enter on the focused button copies (message ${JSON.stringify(okMsg.text)})`,
   okMsg.text.length > 0 && / ok\b|\bok$/.test(okMsg.cls));
/* The whole point of the task, and stated as an identity rather than as
   "starts with" or "contains": not a prefix, not the basename, not a
   normalised form — the complete route path, character for character. */
ok(`...the clipboard holds the COMPLETE path, character for character ` +
   `(${(okMsg.clip || '').length} of ${DEEP.length} chars)`,
   okMsg.clip === DEEP);

// ...and the FAILURE speaks too. Refuse the clipboard the way a browser does
// (a rejected promise) and drive the OTHER keyboard activation.
await page.evaluate(() => {
  Object.defineProperty(navigator.clipboard, 'writeText', {
    configurable: true,
    value: () => Promise.reject(new Error('refused by the guard')),
  });
});
const stops2 = await tabToCopy(page);
await page.keyboard.press('Space');
await sleep(250);
const badMsg = await page.evaluate(() => {
  const m = document.getElementById('fmsg');
  return { text: m.textContent, cls: m.className };
});
ok(`Space activates it too (${stops2} stops)`, stops2 > 0);
ok(`a refused clipboard SPEAKS rather than failing silently ` +
   `(${JSON.stringify(badMsg.text)})`,
   badMsg.text.length > 0);
ok('...and does not claim success', !/\bok\b/.test(badMsg.cls));
ok('...and names the fallback, which is the selectable path beside it',
   /select/i.test(badMsg.text));
notes.push('success message: ' + JSON.stringify(okMsg.text));
notes.push('failure message: ' + JSON.stringify(badMsg.text));

// a root-level file has no parent, and must not invent one
const p2 = await ctx.newPage();
await p2.goto(`${BASE}/file?p=${encodeURIComponent(ROOT_FILE)}`,
              { waitUntil: 'networkidle' });
await sleep(500);
const flat = await p2.evaluate(() => ({
  heading: document.getElementById('htitle').textContent,
  dir: document.querySelector('.fdir') ? document.querySelector('.fdir').textContent : null,
  copy: !!document.querySelector('.fcopy'),
  describedby: document.querySelector('.fcopy')
    ? document.querySelector('.fcopy').getAttribute('aria-describedby') : null,
}));
ok(`a root-level file is its own heading and invents no parent ` +
   `(${JSON.stringify(flat.heading)}, metadata ${JSON.stringify(flat.dir)})`,
   flat.heading === ROOT_FILE && flat.dir === null);
ok('...and still offers copy, described by the heading alone',
   flat.copy && flat.describedby === 'htitle');
await p2.close();
await ctx.close();

/* ── phase 2: the confirmation's departure, in both contexts ──────────────
   It is a transition, so it is traced. The window opens 4.8s after the copy —
   inside the hold, just before its expiry — and runs 900ms, which is long
   enough for a .35s fade and short enough that nothing else on the page could
   supply the movement being asserted. */
const DEPART = 900;
const traceDepart = () => `new Promise(res => {
  const m = document.getElementById('fmsg');
  const frames = [];
  const t0 = performance.now();
  (function step() {
    const cs = getComputedStyle(m);
    frames.push({ t: Math.round(performance.now() - t0),
                  op: +cs.opacity,
                  blur: cs.filter,
                  txt: m.textContent });
    if (performance.now() - t0 < ${DEPART}) requestAnimationFrame(step);
    else res(frames);
  })();
})`;

const departures = {};
for (const reduced of [false, true]) {
  const c = await browser.newContext({
    viewport: { width: 1000, height: 900 },
    permissions: ['clipboard-read', 'clipboard-write'],
    reducedMotion: reduced ? 'reduce' : 'no-preference',
  });
  const p = await c.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/file?p=${encodeURIComponent(DEEP)}`, { waitUntil: 'networkidle' });
  await sleep(600);
  const st = await tabToCopy(p);
  await p.keyboard.press('Enter');
  await sleep(200);
  const shown = await p.evaluate(() => {
    const m = document.getElementById('fmsg');
    return { text: m.textContent, dreamin: m.classList.contains('dreamin') };
  });
  await sleep(4600);                       // 4.8s after the copy
  const frames = await p.evaluate(traceDepart());
  await sleep(400);
  const after = await p.evaluate(() =>
    document.getElementById('fmsg').textContent);
  departures[reduced ? 'reduced' : 'normal'] = { st, shown, frames, after };
  await c.close();
}
await browser.close();

for (const [ctxName, d] of Object.entries(departures)) {
  const lit = d.frames.filter(f => f.txt);
  const ops = lit.map(f => f.op);
  ok(`${ctxName}: the same words, whatever the motion setting ` +
     `(${JSON.stringify(d.shown.text)})`,
     d.shown.text === okMsg.text);
  /* The precondition every assertion below rests on: the message must still
     be on screen when the window opens, or "no part-way frames" and "it
     departed" are both statements about an empty element. */
  ok(`${ctxName}: it is still readable when the window opens ` +
     `(${lit.length} of ${d.frames.length} frames carry the text)`,
     lit.length >= 1 && ops.length >= 1);
  ok(`${ctxName}: the hold is the SAME — it clears by the end of the window`,
     d.after === '');
  if (ctxName === 'normal') {
    ok(`normal: it does not appear — no start pose left lit`, !d.shown.dreamin);
    ok(`normal: it DEPARTS through the middle, at any frame rate ` +
       `(${between(ops, 1, 0)} of ${ops.length} frames strictly part-way)`,
       between(ops, 1, 0) >= 1);
    ok('normal: ...and blurs as it goes, on the page\'s departure idiom',
       lit.some(f => /blur\((?!0px)/.test(f.blur)));
  } else {
    /* The pair that makes both halves mean something: identical measure,
       opposite expectation. `uniq(...) <= 2` would be satisfied by a box that
       sampled a real ramp twice; part-way frames are the frame-rate-free
       form, and instant means NONE of them however few frames were drawn. */
    ok(`reduced: it snaps — no frame part-way ` +
       `(${between(ops, 1, 0)} part-way of ${ops.length})`,
       between(ops, 1, 0) === 0);
    ok('reduced: no start pose either', !d.shown.dreamin);
    ok('reduced: and no blur at any frame', !lit.some(f => /blur\((?!0px)/.test(f.blur)));
  }
  notes.push(`${ctxName} departure opacities: ` +
    JSON.stringify(lit.map(f => [f.t, +f.op.toFixed(3)])));
}
ok('no page errors on any phase', errs.length === 0);
notes.push('deep path: ' + DEEP);
notes.push('lockup: ' + JSON.stringify(lockup));
// a live child process keeps Node's loop alive: without this the guard
// finishes its checks and then hangs until the runner's timeout kills it,
// which reads as a crash rather than as a pass (gitrow.mjs's ending).
try { srv.kill(); } catch (e) {}
finish();
}
