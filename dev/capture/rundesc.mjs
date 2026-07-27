/* rundesc — #300 one shared run-mode description popover.

   Contract under test:
   1. Exactly one description element after hovering every chip; its box is
      geometrically stable across button→button moves (no per-button tooltip).
   2. Hover/focus/Escape/leave produce ZERO side effects on #290's arm:
      event-log line count and run-mode file bytes unchanged. Sweep must
      actually surface description text (anti-vacuity).
   3. Button→button morph visits intermediate opacity via rAF + between()
      (transitions.md / dreamfade.mjs idiom — never a distinct-value count).
   4. Reduced motion swaps text instantly with identical meaning/function
      and the same aria-describedby wiring.
   5. Keyboard focus alone (no pointer) shows the same text as hover.

   Port: 39891 (this lane's assigned guard port).
   usage: node rundesc.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2], PORT = process.argv[3] || '39891';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'dashboard / — hover every .runchip, focus one by keyboard, ' +
          'button→button morph, Escape dismiss, reduced-motion parity',
  traceWindow: 'rAF morph samples ~700ms (dissolve+resolve); hover dwell 120ms; ' +
               'no 10s arm wait — hover must never arm',
});

/* between(vals, first, last) — frame-rate-free form (dreamfade.mjs /
   transitions.md). At least one frame STRICTLY between the two ends, with a
   ~3% deadband so a true endpoint does not read as travel. */
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}

function fileBytes(path) {
  if (!existsSync(path)) return null;
  return readFileSync(path);
}
function lineCount(path) {
  if (!existsSync(path)) return 0;
  const t = readFileSync(path, 'utf8');
  if (!t) return 0;
  return t.split('\n').filter(l => l.length > 0).length;
}

const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(700);

if (!(await present(p, '#runmode', 'run mode section'))) {
  await br.close();
  finish();
  process.exit(1);
}
if (!(await present(p, '#rundesc', 'shared description surface'))) {
  await br.close();
  finish();
  process.exit(1);
}

// ── discover chips at runtime (never hardcode three) ────────────────────
const chipInfo = await p.evaluate(() => {
  const bs = [...document.querySelectorAll('#runmode .runchip')];
  return bs.map(b => ({
    mode: b.dataset.mode,
    disabled: !!b.disabled,
    describedBy: b.getAttribute('aria-describedby'),
  }));
});
notes.push('chips: ' + JSON.stringify(chipInfo));
const nChips = chipInfo.length;
ok('at least one runchip is present (anti-vacuity for the sweep)', nChips >= 1);
ok('every chip points aria-describedby at rundesc-text',
   chipInfo.every(c => c.describedBy === 'rundesc-text'));

// Resolve the live id from the attribute (not a remembered string)
const a11y = await p.evaluate(() => {
  const b = document.querySelector('#runmode .runchip');
  const id = b && b.getAttribute('aria-describedby');
  const el = id ? document.getElementById(id) : null;
  return {
    id,
    exists: !!el,
    tag: el ? el.id : null,
  };
});
ok('aria-describedby resolves to a live element id',
   a11y.exists && a11y.tag === a11y.id);

// ── target paths for side-effect proof ──────────────────────────────────
const target = await p.evaluate(async () =>
  (await (await fetch('/data.json')).json()).target);
const modeFile = join(target, '.dreamwork', 'run-mode');
const eventsFile = join(target, '.dreamwork', 'watch-events.log');
// Seed a known mode file so "byte-identical" is meaningful (not both-absent)
if (!existsSync(modeFile)) {
  writeFileSync(modeFile, 'lackadaisical\n');
}
const eventsBefore = lineCount(eventsFile);
const modeBefore = fileBytes(modeFile);
// Also baseline the in-page arm state — pickRunMode does not POST for 10s,
// so a hollow "zero POSTs" check passes while hover arms the 10s countdown
// and writes localStorage. That is exactly the #290 interference forbidden.
const armBefore = await p.evaluate(() => {
  const count = document.getElementById('runcount');
  const pending = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.indexOf('dw:run-mode-pending:') === 0)
        pending.push({ k, v: localStorage.getItem(k) });
    }
  } catch (e) {}
  return {
    count: count ? count.textContent : '',
    pending,
  };
});
notes.push(`side-effect baseline: events=${eventsBefore} modeBytes=${modeBefore && modeBefore.length} arm=${JSON.stringify(armBefore)}`);

// Instrument POSTs — hover must never fire /run-mode
const posts = [];
ctx.on('request', req => {
  if (req.method() === 'POST' && req.url().includes('/run-mode'))
    posts.push({ t: Date.now(), url: req.url() });
});

// ── hover sweep: every chip, collect geometry + text ────────────────────
// Hold the tick so a mid-sweep /mtime re-render cannot wipe #rundesc
// (the list re-renders through innerHTML; a 2s poll over a 4×700ms
// dwell would destroy the open shell and make geometry vacuously fail).
const sweep = await p.evaluate(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // holdRerenderUntil is the page's own seam (answer morph); use it.
  if (typeof holdRerenderUntil !== 'undefined')
    holdRerenderUntil = Date.now() + 20000;
  const chips = [...document.querySelectorAll('#runmode .runchip')];
  const rects = [];
  const texts = [];
  const descCount = () => document.querySelectorAll('#rundesc').length;
  for (const b of chips) {
    // Drive the real pointerover path (not a private test hook).
    b.dispatchEvent(new PointerEvent('pointerover', {
      bubbles: true, cancelable: true, view: window,
    }));
    // Wait for morph resolve (~.38s dissolve + settle).
    const want = (typeof RUN_MODE_DESC !== 'undefined')
      ? RUN_MODE_DESC[b.dataset.mode] : null;
    const t0 = performance.now();
    while (performance.now() - t0 < 900) {
      const cur = document.getElementById('rundesc-text');
      const shell = document.getElementById('rundesc');
      if (shell && shell.classList.contains('open') && cur && want
          && cur.textContent === want && !cur.classList.contains('out'))
        break;
      await sleep(25);
    }
    await sleep(30);
    const shell = document.getElementById('rundesc');
    const text = document.getElementById('rundesc-text');
    const r = shell ? shell.getBoundingClientRect() : null;
    rects.push(r ? { x: r.x, y: r.y, w: r.width, h: r.height,
                     hidden: shell.hidden, open: shell.classList.contains('open') }
                 : null);
    texts.push(text ? text.textContent : '');
  }
  return {
    nChips: chips.length,
    descCount: descCount(),
    rects,
    texts,
    anyNonEmpty: texts.some(t => t && t.trim().length > 0),
  };
});
notes.push('hover sweep: ' + JSON.stringify({
  nChips: sweep.nChips, descCount: sweep.descCount,
  anyNonEmpty: sweep.anyNonEmpty,
  texts: sweep.texts,
  rects: sweep.rects,
}));

// Precondition: the sweep actually hovered something
ok('hover sweep surfaced a non-empty description (anti-vacuity)',
   sweep.anyNonEmpty);
ok('exactly one #rundesc element in the DOM after hovering all chips',
   sweep.descCount === 1);

// Geometry stable: among open rects, max delta in x/y/w/h within tolerance
const openRects = (sweep.rects || []).filter(r => r && r.open && !r.hidden);
if (openRects.length >= 2) {
  const xs = openRects.map(r => r.x);
  const ys = openRects.map(r => r.y);
  const ws = openRects.map(r => r.w);
  const hs = openRects.map(r => r.h);
  const span = a => Math.max(...a) - Math.min(...a);
  const dx = span(xs), dy = span(ys), dw = span(ws), dh = span(hs);
  notes.push(`geometry span: dx=${dx.toFixed(2)} dy=${dy.toFixed(2)} ` +
             `dw=${dw.toFixed(2)} dh=${dh.toFixed(2)}`);
  // Tolerance: shell must not jump between buttons. 6px absorbs subpixel +
  // scrollbar gutters when the section sits near the viewport floor; a
  // per-button tooltip would move tens of px.
  ok('description shell x stable across chips (≤6px span)', dx <= 6);
  ok('description shell y stable across chips (≤6px span)', dy <= 6);
  ok('description shell width stable across chips (≤8px span)', dw <= 8);
  ok('description shell height stable across chips (≤8px span)', dh <= 8);
  // Distinct mode texts actually landed (retarget morph works)
  const uniqTexts = new Set((sweep.texts || []).filter(t => t && t.trim()));
  ok('hover sweep produced >1 distinct description texts across chips',
     uniqTexts.size > 1);
} else {
  ok('description shell geometry comparable across ≥2 open samples', false);
}

// Leave the section so description dismisses before side-effect read
await p.evaluate(() => {
  const sec = document.getElementById('runmode');
  if (sec) sec.dispatchEvent(new PointerEvent('pointerout', {
    bubbles: true, cancelable: true, view: window,
    relatedTarget: document.body,
  }));
  if (typeof hideRunDesc === 'function') hideRunDesc(true);
});
await sleep(200);

const eventsAfterHover = lineCount(eventsFile);
const modeAfterHover = fileBytes(modeFile);
const armAfterHover = await p.evaluate(() => {
  const count = document.getElementById('runcount');
  const pending = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.indexOf('dw:run-mode-pending:') === 0)
        pending.push({ k, v: localStorage.getItem(k) });
    }
  } catch (e) {}
  return {
    count: count ? count.textContent : '',
    pending,
    onMode: (document.querySelector('.runchip.on:not([disabled])') || {}).dataset?.mode || null,
  };
});
notes.push('arm after hover: ' + JSON.stringify(armAfterHover));
ok('hover sweep did not append any watch-events.log line',
   eventsAfterHover === eventsBefore);
ok('hover sweep left run-mode file byte-identical',
   modeBefore && modeAfterHover &&
   Buffer.compare(modeBefore, modeAfterHover) === 0);
ok('hover sweep issued zero /run-mode POSTs', posts.length === 0);
// The production line that must change for these to fail: showRunDesc
// calling pickRunMode / writeRunPending. A 10s arm is silent to POST/file
// for ten seconds — these two catch it immediately.
ok('hover sweep did not start an arm countdown (runcount empty of arms-in)',
   !/arms in/.test(armAfterHover.count || ''));
ok('hover sweep left run-mode pending localStorage unchanged',
   JSON.stringify(armAfterHover.pending) === JSON.stringify(armBefore.pending));

// ── keyboard focus alone shows same text as hover ───────────────────────
// Pick first enabled chip; hover text vs focus text must match at runtime.
const modeForParity = chipInfo.find(c => !c.disabled)?.mode
                   || chipInfo[0]?.mode;
let hoverText = '', focusText = '';
if (modeForParity) {
  // Hover path
  await p.hover(`.runchip[data-mode="${modeForParity}"]`);
  await sleep(180);
  hoverText = await p.evaluate(() => {
    const t = document.getElementById('rundesc-text');
    return t ? t.textContent : '';
  });
  await p.mouse.move(0, 0);
  await p.evaluate(() => { if (typeof hideRunDesc === 'function') hideRunDesc(true); });
  await sleep(100);
  // Focus path — no pointer on the chip
  await p.evaluate(m => {
    if (typeof hideRunDesc === 'function') hideRunDesc(true);
    const b = document.querySelector(`.runchip[data-mode="${m}"]`);
    if (b) b.focus();
  }, modeForParity);
  await sleep(180);
  focusText = await p.evaluate(() => {
    const t = document.getElementById('rundesc-text');
    return t ? t.textContent : '';
  });
  notes.push(`hover/focus parity for ${modeForParity}: ` +
             JSON.stringify({ hoverText, focusText }));
}
ok('hover produced non-empty text for parity mode (precondition)',
   !!hoverText && hoverText.trim().length > 0);
ok('keyboard focus alone shows the same description text as hover',
   hoverText === focusText && hoverText.length > 0);

// Escape dismisses with no mode side effect
const eventsBeforeEsc = lineCount(eventsFile);
const modeBeforeEsc = fileBytes(modeFile);
// Ensure description is open first (focus path may have left it open).
const openBeforeEsc = await p.evaluate(() => {
  const shell = document.getElementById('rundesc');
  return !!(shell && shell.classList.contains('open') && !shell.hidden);
});
if (!openBeforeEsc && modeForParity) {
  await p.evaluate(m => {
    const b = document.querySelector(`.runchip[data-mode="${m}"]`);
    if (b) b.focus();
    if (typeof showRunDesc === 'function') showRunDesc(m);
  }, modeForParity);
  await sleep(100);
}
await p.keyboard.press('Escape');
// Departure is animated (~.42s); wait for completion, not a fixed clock
// that fails under load mid-fade (transitions.md terminal-state rule).
const afterEsc = await p.evaluate(async () => {
  const shell = document.getElementById('rundesc');
  if (!shell) return { open: false, hidden: true, text: '', waited: 0 };
  const t0 = performance.now();
  while (performance.now() - t0 < 900) {
    if (shell.hidden || !shell.classList.contains('open')) break;
    await new Promise(r => requestAnimationFrame(r));
  }
  return {
    open: shell.classList.contains('open'),
    hidden: shell.hidden,
    text: (document.getElementById('rundesc-text') || {}).textContent || '',
    waited: performance.now() - t0,
  };
});
notes.push('after Escape: ' + JSON.stringify(afterEsc));
ok('Escape dismisses the description (not open / hidden)',
   !afterEsc.open || afterEsc.hidden);
ok('Escape left run-mode file byte-identical',
   modeBeforeEsc && Buffer.compare(modeBeforeEsc, fileBytes(modeFile)) === 0);
ok('Escape did not append any events line',
   lineCount(eventsFile) === eventsBeforeEsc);

// Blur focus cleanly
await p.evaluate(() => {
  if (document.activeElement && document.activeElement.blur)
    document.activeElement.blur();
  if (typeof hideRunDesc === 'function') hideRunDesc(true);
});

// ── morph: button→button, rAF sample opacity, between() ─────────────────
// Production line that must change for this to fail: the .rundesc-text
// opacity transition during showRunDesc's swap (class .out / resolve).
const enabled = chipInfo.filter(c => !c.disabled).map(c => c.mode);
ok('≥2 enabled modes so a button→button morph is possible (precondition)',
   enabled.length >= 2);

let morph = null;
if (enabled.length >= 2) {
  const a = enabled[0], b = enabled[1];
  // open on A first
  // Open A via the real presentation path and wait until settled, so the
  // swap is a true button→button morph (not a first arrival onto an empty
  // shell, which has no .out dissolve).
  const readyA = await p.evaluate(async m => {
    if (typeof holdRerenderUntil !== 'undefined')
      holdRerenderUntil = Date.now() + 15000;
    if (typeof hideRunDesc === 'function') hideRunDesc(true);
    if (typeof showRunDesc === 'function') showRunDesc(m);
    const want = (typeof RUN_MODE_DESC !== 'undefined') ? RUN_MODE_DESC[m] : null;
    const t0 = performance.now();
    while (performance.now() - t0 < 800) {
      const shell = document.getElementById('rundesc');
      const text = document.getElementById('rundesc-text');
      if (shell && shell.classList.contains('open') && !shell.hidden
          && text && text.textContent === want && !text.classList.contains('out')
          && parseFloat(getComputedStyle(text).opacity) > 0.95)
        return { ok: true, text: text.textContent };
      await new Promise(r => requestAnimationFrame(r));
    }
    const text = document.getElementById('rundesc-text');
    return { ok: false, text: text ? text.textContent : '' };
  }, a);
  notes.push('morph ready A: ' + JSON.stringify(readyA));
  ok('morph precondition: mode A description is open and settled',
     readyA && readyA.ok);
  morph = await p.evaluate(async ({ a, b }) => {
    /* between helper inlined so the page eval is self-contained */
    const between = (frames, first, last) => {
      const lo = Math.min(first, last), hi = Math.max(first, last);
      const pad = Math.max(0.03, (hi - lo) * 0.03);
      return frames.filter(v => v > lo + pad && v < hi - pad).length;
    };
    const text = document.getElementById('rundesc-text');
    const shell = document.getElementById('rundesc');
    if (!text || !shell || !shell.classList.contains('open')) {
      return { n: 0, minOp: 0, maxOp: 0, midCount: 0, startText: '',
               endText: '', hadOut: false, why: 'shell not open' };
    }
    const startText = text.textContent || '';
    const startOp = parseFloat(getComputedStyle(text).opacity);
    // start morph by showing B (same function pointerover calls)
    const frames = [];
    const t0 = performance.now();
    const MS = 750;
    let switched = false;
    return await new Promise(resolve => {
      const step = () => {
        const t = performance.now() - t0;
        const cs = getComputedStyle(text);
        frames.push({
          t,
          op: parseFloat(cs.opacity),
          blur: (() => {
            const f = cs.filter || '';
            const m = f.match(/blur\(([\d.]+)px\)/);
            return m ? parseFloat(m[1]) : 0;
          })(),
          txt: text.textContent,
          out: text.classList.contains('out'),
        });
        // fire the swap once we have a baseline of settled A
        if (!switched && frames.length >= 3) {
          switched = true;
          if (typeof showRunDesc === 'function') showRunDesc(b);
          else {
            const chipB = document.querySelector(`.runchip[data-mode="${b}"]`);
            if (chipB) chipB.dispatchEvent(new PointerEvent('pointerover', {
              bubbles: true, cancelable: true, view: window,
            }));
          }
        }
        if (t < MS) requestAnimationFrame(step);
        else {
          const ops = frames.map(f => f.op);
          const minOp = Math.min(...ops);
          const maxOp = Math.max(...ops);
          const midCount = between(ops, maxOp, minOp);
          const endText = text.textContent || '';
          const shellRect = (() => {
            const r = shell.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height };
          })();
          resolve({
            n: frames.length,
            first: ops[0], last: ops[ops.length - 1],
            minOp, maxOp, midCount,
            startText, endText,
            startOp,
            hadOut: frames.some(f => f.out),
            shellRect,
            opsSample: ops.filter((_, i) => i % 3 === 0).map(v => +v.toFixed(3)),
          });
        }
      };
      requestAnimationFrame(step);
    });
  }, { a, b });
  notes.push('morph: ' + JSON.stringify(morph));
  ok('morph trace captured frames (precondition)', morph && morph.n > 4);
  ok('morph opacity span is real (≥0.25 from peak to trough)',
     morph && (morph.maxOp - morph.minOp) >= 0.25);
  // THE load-bearing motion claim: at least one frame strictly between ends
  ok('morph visits ≥1 intermediate opacity (between(); not a snap)',
     morph && morph.midCount >= 1);
  ok('morph ends on a different mode text than it started',
     morph && morph.startText !== morph.endText && morph.endText.length > 0);
  ok('morph engaged the .out dissolve class at least once',
     morph && morph.hadOut);
}

// Side effects still zero after morph
ok('morph issued zero /run-mode POSTs', posts.length === 0);
ok('morph left events log line count unchanged',
   lineCount(eventsFile) === eventsBefore);
ok('morph left run-mode file byte-identical',
   modeBefore && Buffer.compare(modeBefore, fileBytes(modeFile)) === 0);

// ── reduced-motion parity ───────────────────────────────────────────────
await p.evaluate(() => { if (typeof hideRunDesc === 'function') hideRunDesc(true); });
const pRM = await ctx.newPage();
await pRM.emulateMedia({ reducedMotion: 'reduce' });
pRM.on('pageerror', e => errs.push('RM:' + String(e)));
await pRM.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(500);

const rmParity = await pRM.evaluate(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const between = (frames, first, last) => {
    const lo = Math.min(first, last), hi = Math.max(first, last);
    const pad = Math.max(0.03, (hi - lo) * 0.03);
    return frames.filter(v => v > lo + pad && v < hi - pad).length;
  };
  const chips = [...document.querySelectorAll('#runmode .runchip:not([disabled])')];
  if (chips.length < 2) return { ok: false, why: 'need 2 chips' };
  const a = chips[0], b = chips[1];
  // show A
  a.dispatchEvent(new PointerEvent('pointerover', {
    bubbles: true, cancelable: true, view: window,
  }));
  await sleep(50);
  const textA = document.getElementById('rundesc-text')?.textContent || '';
  const descA = a.getAttribute('aria-describedby');
  // swap to B while sampling — RM must NOT visit intermediate opacity
  const text = document.getElementById('rundesc-text');
  const ops = [];
  const t0 = performance.now();
  b.dispatchEvent(new PointerEvent('pointerover', {
    bubbles: true, cancelable: true, view: window,
  }));
  while (performance.now() - t0 < 200) {
    if (text) ops.push(parseFloat(getComputedStyle(text).opacity));
    await new Promise(r => requestAnimationFrame(r));
  }
  const textB = text?.textContent || '';
  const descB = b.getAttribute('aria-describedby');
  const mid = between(ops, Math.max(...ops, 0), Math.min(...ops, 1));
  // Also: same RUN_MODE_DESC content as normal path would use
  const expectedA = (typeof RUN_MODE_DESC !== 'undefined')
    ? RUN_MODE_DESC[a.dataset.mode] : null;
  const expectedB = (typeof RUN_MODE_DESC !== 'undefined')
    ? RUN_MODE_DESC[b.dataset.mode] : null;
  return {
    ok: true,
    textA, textB,
    descA, descB,
    midCount: mid,
    opsN: ops.length,
    expectedA, expectedB,
    matchA: textA === expectedA,
    matchB: textB === expectedB,
    modes: [a.dataset.mode, b.dataset.mode],
  };
});
notes.push('reduced-motion: ' + JSON.stringify(rmParity));
ok('RM: description text matches RUN_MODE_DESC for first chip',
   rmParity && rmParity.matchA);
ok('RM: description text matches RUN_MODE_DESC for second chip',
   rmParity && rmParity.matchB);
ok('RM: aria-describedby still rundesc-text on both chips',
   rmParity && rmParity.descA === 'rundesc-text' &&
   rmParity.descB === 'rundesc-text');
// Instant swap: no intermediate opacity travel on the text
ok('RM: text opacity does not travel through intermediate frames (instant swap)',
   rmParity && rmParity.midCount === 0);
// Meaning identical to normal-motion page for the same mode
if (modeForParity && hoverText) {
  const rmSame = await pRM.evaluate(m => {
    const b = document.querySelector(`.runchip[data-mode="${m}"]`);
    if (b) b.dispatchEvent(new PointerEvent('pointerover', {
      bubbles: true, cancelable: true, view: window,
    }));
    const t = document.getElementById('rundesc-text');
    return t ? t.textContent : '';
  }, modeForParity);
  await sleep(80);
  const rmText = await pRM.evaluate(() =>
    (document.getElementById('rundesc-text') || {}).textContent || '');
  notes.push(`RM vs normal text for ${modeForParity}: ` +
             JSON.stringify({ normal: hoverText, rm: rmText || rmSame }));
  ok('RM and normal motion show identical text for the same mode',
     (rmText || rmSame) === hoverText);
}

// Final side-effect ledger
ok('entire guard: zero /run-mode POSTs', posts.length === 0);
ok('entire guard: events log line count still at baseline',
   lineCount(eventsFile) === eventsBefore);
ok('entire guard: run-mode file still byte-identical to baseline',
   modeBefore && Buffer.compare(modeBefore, fileBytes(modeFile)) === 0);

// Screenshots for visual review (pixels, not structure)
const shot = async (page, name, sel) => {
  try {
    if (sel) {
      const loc = page.locator(sel);
      if (await loc.count()) {
        await loc.screenshot({ path: join(OUT, name) });
        return;
      }
    }
    await page.screenshot({ path: join(OUT, name), fullPage: false });
  } catch (e) { notes.push(`shot ${name}: ${e}`); }
};
// each mode hovered on normal page
for (const c of chipInfo) {
  await p.hover(`.runchip[data-mode="${c.mode}"]`);
  await sleep(200);
  await shot(p, `hover-${c.mode}.png`, '#runmode');
}
// mid-morph is hard to freeze; capture settled after swap
if (enabled.length >= 2) {
  await p.hover(`.runchip[data-mode="${enabled[0]}"]`);
  await sleep(100);
  await p.hover(`.runchip[data-mode="${enabled[1]}"]`);
  await sleep(120); // mid-ish
  await shot(p, 'morph-mid.png', '#runmode');
  await sleep(400);
  await shot(p, 'morph-settled.png', '#runmode');
}
// reduced-motion state
await pRM.hover(`.runchip[data-mode="${enabled[0] || chipInfo[0].mode}"]`);
await sleep(100);
await shot(pRM, 'reduced-motion.png', '#runmode');
// narrow viewport with countdown visible — arm deliberately NOT from hover;
// click to arm so we can see desc + countdown together, then cancel.
const pNarrow = await ctx.newPage();
await pNarrow.setViewportSize({ width: 390, height: 800 });
await pNarrow.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(500);
// hover only first (zero side effect still for hover); then click to arm
// so countdown exists under the description for the visual plate.
await pNarrow.hover(`.runchip[data-mode="${enabled[1] || 'hot'}"]`);
await sleep(150);
await pNarrow.click(`.runchip[data-mode="${enabled[1] || 'hot'}"]`);
await sleep(200);
// re-hover so description is open over the arming countdown
await pNarrow.hover(`.runchip[data-mode="${enabled[1] || 'hot'}"]`);
await sleep(150);
await shot(pNarrow, 'narrow-with-countdown.png', '#runmode');
// cancel arm by re-selecting committed so we do not leave a pending POST
await pNarrow.evaluate(() => {
  if (typeof pickRunMode === 'function') {
    const on = document.querySelector('.runchip.on:not([disabled])');
    // cancel by picking the committed file mode
    const cur = (typeof committedRunMode === 'function' && data)
      ? committedRunMode(data) : 'lackadaisical';
    pickRunMode(cur);
  }
  if (typeof hideRunDesc === 'function') hideRunDesc(true);
});
await sleep(200);

ok('no page errors on main context', errs.filter(e => !e.startsWith('RM:')).length === 0);

await br.close();
finish();
