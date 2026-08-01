/* cmdmore — #835: the ⋯ disclosure control's geometry + appearance guard.

   #161 centred the `⋯` (.cmdmorebtn) on the command-kind row at 5ddb2559 and
   did genuinely excellent verification — then committed none of it. The check
   was ad-hoc and is gone; dev/capture/cmdcap.mjs is byte-identical to master
   and is not even registered in DEFAULT_GUARDS. So the next change to .cmdmore
   or .cmdpick can silently re-break the centring with nothing to catch it —
   which is exactly the history #123 recorded (same visual symptom, two wrong
   diagnoses). This guard is the durable instrument that verification left
   behind.

   WHAT IT ASSERTS, from a real Chromium render (getBoundingClientRect +
   computed style — never by asserting a rule exists in the stylesheet):

   - POPULATION (#671): a nonempty ⋯ text Range and a nonempty .cmdkind
     population, so a build without either is a named FAIL, not a vacuous pass.
   - GEOMETRY: the ⋯ shares the .cmdkind centreline (both the ink text-Range
     centre and the control box centre sit within tolerance of the kind row's
     centre); sits at the row's hard-right edge (its right == the row's right);
     has a separating gap from the last kind; and the row does not wrap (the
     control is on the same line as the kinds and the page does not overflow).
   - APPEARANCE (his vocabulary, load-bearing for #164): a computed surface
     fill (non-transparent background), ZERO computed border, and a NON-ACCENT
     fill. Outline means "this acts", fill means "this reveals" — a menu
     reveals, so it is filled, never outlined, never accent-coloured.
   - VISIBILITY / the false-green #161 found and closed: an invisible element
     retains perfect rectangles, so geometry-only PASSED at opacity:0 in all
     four cases. This guard asserts computed visibility/opacity AND emits a
     dedicated composite FAIL — "cmdmore geometry passed over an invisible
     control" — when geometry is sound but the control cannot be seen. That
     message names the exact class the guard can detect (#651).

   Four cases: 390px and 1100px × normal and reduced motion. Reduced motion is
   asserted as parity of geometry (the dots are placed identically), which is
   the half of transitions.md's contract a static guard can hold — the palette
   open/close motion itself is dissolve.mjs's gesture.

   This is a NEW sibling rather than an extension of cmdcap.mjs (#440's spirit
   — "one supported way" — invoked with an explicit "if it fits"): cmdcap.mjs
   is unregistered AND uses the pre-report.mjs inline reporter, so extending it
   would either leave this check unregistered too, or pull the whole 117-line
   palette-interaction suite into every sweep. The geometry check is one
   focused concern and gets the modern report.mjs / dom.mjs stack from day one.

   usage: node cmdmore.mjs <outdir> [port]   (port defaults to the guards port) */
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
  drives: 'the ⋯ disclosure control (.cmdmorebtn inside #cmdmore on the ' +
          'command-kind row), opened via #cmdplus, at 390px and 1100px in ' +
          'normal AND reduced motion',
  traceWindow: 'static reads after the palette-open transition settles (~800ms ' +
               'normal, ~150ms reduced); no motion is traced — the open/close ' +
               'gesture is dissolve.mjs\'s dissolve and the dots are static DOM',
});

// Centring tolerance: the fixed control sits <0.1px and the ink <0.9px off the
// kind centreline; breaking .cmdmore's top margin (the #161 fix) moves both to
// ~5px. 2px is safely between — tight enough to catch the break, loose enough
// not to flake on sub-pixel rounding.
const CENTRE_TOL = 2.0;
const CASES = [
  { w: 390, rm: false, label: '390px/no-preference' },
  { w: 1100, rm: false, label: '1100px/no-preference' },
  { w: 390, rm: true, label: '390px/reduced-motion' },
  { w: 1100, rm: true, label: '1100px/reduced-motion' },
];

async function readCase(browser, c) {
  const ctx = c.rm
    ? await browser.newContext({ reducedMotion: 'reduce', viewport: { width: c.w, height: 820 } })
    : await browser.newContext({ viewport: { width: c.w, height: 820 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(p, '#cmdplus');
  await p.click('#cmdplus');
  // Wait for the palette-open transition to settle so getBoundingClientRect
  // reads the final position, not a mid-transform offset. Reduced motion is
  // instant; normal motion rides the dissolve (~.8s).
  await sleep(c.rm ? 150 : 850);
  await p.screenshot({ path: `${OUT}/cmdmore-${c.label.replace('/', '-')}.png` });

  const d = await p.evaluate(() => {
    const more = document.getElementById('cmdmore');
    const btn = more && more.querySelector('.cmdmorebtn');
    const kinds = [...document.querySelectorAll('.cmdkind')];
    const pick = document.querySelector('.cmdpick');
    if (!more || !btn || !kinds.length || !pick) {
      return { missing: true, hasMore: !!more, hasBtn: !!btn, kindCount: kinds.length, hasPick: !!pick };
    }
    const cs = getComputedStyle(btn);
    const br = btn.getBoundingClientRect();
    const pr = pick.getBoundingClientRect();
    // The ⋯ ink: a Range over the button's text content. A nonempty Range is
    // the population assertion (#671) — a control with no glyph must not pass.
    const rg = document.createRange();
    rg.selectNodeContents(btn);
    const ink = rg.getBoundingClientRect();
    const kindRects = kinds.map(k => k.getBoundingClientRect());
    const kindCY = kindRects.reduce((s, r) => s + r.top + r.height / 2, 0) / kindRects.length;
    const lastKind = kindRects[kindRects.length - 1];
    const accent = getComputedStyle(document.documentElement)
      .getPropertyValue('--accent').trim().toLowerCase();
    return {
      missing: false,
      kindCount: kinds.length,
      inkW: ink.width, inkH: ink.height,
      inkCY: ink.top + ink.height / 2, btnCY: br.top + br.height / 2,
      inkOff: (ink.top + ink.height / 2) - kindCY,
      ctrlOff: (br.top + br.height / 2) - kindCY,
      btnR: br.right, pickR: pr.right,
      gap: br.left - lastKind.right,
      sameLine: br.top < lastKind.bottom,
      scrollW: document.documentElement.scrollWidth,
      clientW: document.documentElement.clientWidth,
      bg: cs.backgroundColor, bgImage: cs.backgroundImage,
      borderStyle: cs.borderTopStyle, borderWidth: cs.borderTopWidth,
      opacity: parseFloat(cs.opacity), visibility: cs.visibility,
      btnW: br.width, btnH: br.height,
      accent,
    };
  });
  await ctx.close();
  return d;
}

try {
  await waitForServer(BASE);
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

  for (const c of CASES) {
    const tag = c.label;
    const d = await readCase(br, c);

    if (d.missing) {
      ok(`${tag}: #cmdmore + .cmdmorebtn + .cmdkind all render`, false);
      notes.push(`${tag}: missing ${JSON.stringify({ hasMore: d.hasMore, hasBtn: d.hasBtn, kindCount: d.kindCount, hasPick: d.hasPick })}`);
      continue;
    }

    // ── POPULATION (#671): examine nothing, pass nothing ─────────────────
    ok(`${tag}: a nonempty ⋯ population renders (${d.inkW.toFixed(1)}px ink)`,
       d.inkW > 0);
    ok(`${tag}: a nonempty .cmdkind population renders (${d.kindCount} kinds)`,
       d.kindCount > 0);
    if (d.inkW <= 0 || d.kindCount <= 0) {
      notes.push(`${tag}: population empty — skipping geometry/appearance`);
      continue;
    }

    // ── APPEARANCE (his vocabulary, #164): fill not outline, surface not accent
    const filled = d.bg !== 'rgba(0, 0, 0, 0)' && d.bg !== 'transparent';
    const noBorder = d.borderStyle === 'none' || d.borderWidth === '0px';
    const nonAccent = d.bg.toLowerCase() !== d.accent && d.bg !== d.accent;
    ok(`${tag}: the ⋯ control has a computed surface fill (bg ${d.bg})`, filled);
    ok(`${tag}: the ⋯ control has ZERO computed border (${d.borderStyle}/${d.borderWidth})`, noBorder);
    ok(`${tag}: the ⋯ fill is non-accent (accent is ${d.accent})`, nonAccent);

    // ── GEOMETRY: centreline, hard-right, gap, no-wrap ───────────────────
    const inkCentred = Math.abs(d.inkOff) <= CENTRE_TOL;
    const ctrlCentred = Math.abs(d.ctrlOff) <= CENTRE_TOL;
    ok(`${tag}: the ⋯ ink shares the .cmdkind centreline ` +
       `(ink offset ${d.inkOff.toFixed(2)}px, tol ${CENTRE_TOL}px)`, inkCentred);
    ok(`${tag}: the ⋯ control shares the .cmdkind centreline ` +
       `(control offset ${d.ctrlOff.toFixed(2)}px, tol ${CENTRE_TOL}px)`, ctrlCentred);
    ok(`${tag}: the ⋯ sits at the row's hard-right edge ` +
       `(btn right ${d.btnR.toFixed(1)}, row right ${d.pickR.toFixed(1)})`,
       Math.abs(d.btnR - d.pickR) <= 2);
    ok(`${tag}: a separating gap precedes the ⋯ (${d.gap.toFixed(1)}px)`, d.gap > 0);
    ok(`${tag}: the kind row does not wrap (⋯ on the same line; no overflow)`,
       d.sameLine && d.scrollW <= d.clientW + 1);

    // ── VISIBILITY — the false-green #161 found and closed ──────────────
    // An invisible element retains perfect rectangles: with opacity:0 the
    // geometry above still passes. So the control must be live, and when
    // geometry is sound but the control is not visible, the dedicated message
    // below names the exact class (#651: name a mode the guard can detect).
    // visibility === 'visible' (positive), not !== 'hidden' (negative), so
    // `visibility:collapse` — which paints the same as `hidden` on a non-table
    // element while retaining its rectangles — is caught too.
    const visible = d.opacity > 0 && d.visibility === 'visible' &&
                    d.btnW > 0 && d.btnH > 0;
    ok(`${tag}: the ⋯ control is live (opacity ${d.opacity}, ${d.visibility}, ` +
       `${d.btnW.toFixed(0)}×${d.btnH.toFixed(0)})`, visible);

    const geomOk = inkCentred && ctrlCentred &&
                   Math.abs(d.btnR - d.pickR) <= 2 && d.gap > 0 &&
                   d.sameLine && d.scrollW <= d.clientW + 1;
    ok(`${tag}: cmdmore geometry did not pass over an invisible control`,
       !(geomOk && !visible));
    notes.push(`${tag}: ${JSON.stringify({ inkOff: +d.inkOff.toFixed(2), ctrlOff: +d.ctrlOff.toFixed(2), gap: +d.gap.toFixed(1), bg: d.bg, border: d.borderStyle + '/' + d.borderWidth, opacity: d.opacity })}`);
  }
  await br.close();
} catch (e) {
  errs.push('guard threw: ' + (e && e.stack ? e.stack : String(e)));
}

finish();
