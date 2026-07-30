/* #570 — the composer box is manually resizable; a drag disables autoexpand
   until the next submit.

   His report: "the text entry box should still be manually expandable by the
   user. Right now, it isn't. so once it is fully expanded, i can't make it
   bigger even if i wanted to. once the user manually drags it, disable the
   autoexpand entirely until the prompt is submitted (then it returns to
   normal behavior)."

   The whole cycle is one composition, driven through the REAL composer render
   + submit path (the same #cmdplus → #cmdtext → requestSubmit seam
   confirmation.mjs drives), not a mocked box:

     1. autoexpand WORKS — type several lines, the box grows past its floor.
     2. a manual DRAG disables autoexpand — the native handle is a UA control
        no selector or pointer can drive in headless Chromium, so the drag is
        simulated the way the BROWSER does it: a pointerdown (which the page's
        own handler turns into the transition-pause + press-height record), a
        direct `style.height` set (exactly what the native handle writes), and
        a pointerup (which the page's handler reads as a height change and so
        marks the composition manual). What is bound is the REAL detection, on
        the REAL node, through the REAL delegated input listener.
     3. typing MORE does not override his height — autoexpand yielded. The
        check is non-vacuous: the typed content's own scrollHeight is well
        past the dragged height, so a live autoexpand would have grown it.
     4. a SUBMIT re-enables autoexpand — the real POST lands, and the next
        thought grows again.

   This is a STATE guard, not a motion one: every assertion is on a settled
   height (or the resize CSS / the manual flag), never on frames. The
   autoexpand MOTION it leaves to autogrow.mjs (#177); #570 only owns whether
   autoexpand is ON or OFF for a composition. Reduced motion is covered by
   construction — the drag detection and the submit re-enable are
   motion-independent, and under RM the height transition is already `none`,
   so the pointerdown pause is a no-op. (transitions.md #305: a drag is
   continuous input; the page's own handler pauses the transition for the
   press so the box follows the pointer rather than trailing it.)

   The production lines whose change reds each check:
     - the CSS `resize:vertical` on #cmdform textarea  -> reds the "is
       resizable" precondition (a build without it has no handle at all).
     - the pointerup handler that sets `ta._manual`      -> reds "drag disables"
       (without it the height the drag set is overwritten on the next input).
     - `if (ta._manual) return;` at the top of fitText   -> reds "typing more
       does not override" for the same reason, from the other side.
     - the submit path clearing `cmdtext._manual`         -> reds "submit
       re-enables" (autoexpand stays off for the next thought).

   Own target and own server on port 39894 (39890-39893 are taken by merged
   lanes; 39894 is free), so it runs standalone without the shared suite's
   plumbing. The justfile is coordinator-owned, so this guard is not yet in
   DEFAULT_GUARDS — run it directly:
     node dev/capture/resize.mjs <outdir>
   usage: node resize.mjs <outdir> [port, ignored — self-serves on 39894] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { join } from 'node:path';

const OUT = outdir(process.argv);
const PORT = 39894;                       // #570: the lane's own guard port
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/questions composer: open → type (autoexpand) → simulate a native ' +
          'resize drag → type more (autoexpand off) → real submit → type again ' +
          '(autoexpand re-enabled). One composition, the real render + submit path.',
  traceWindow: 'no rAF trace — this is a state guard (settled heights + the ' +
               'resize CSS + the manual flag); the autoexpand MOTION is ' +
               'autogrow.mjs (#177)',
});

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const BASE = `http://127.0.0.1:${PORT}`;
const srv = await serveVerified(DIR, PORT);   // #461: poll+identity, no fixed sleep
process.on('exit', () => { try { srv.kill(); } catch (e) {} });

/* settle: poll the box's rendered height until it stops moving. The autoexpand
   growth rides a .85s height transition (#177), so a single read right after
   an input catches it mid-travel; polling until stable measures the height
   autoexpand actually committed. (Same shape as autogrow.mjs's settle; passed
   as a REAL function so Playwright calls it with the selector.) */
async function settleH(p, sel) {
  return p.evaluate(async (s) => {
    const t = document.querySelector(s); if (!t) return null;
    let prev = -1, stable = 0;
    for (let i = 0; i < 50; i++) {
      const h = +t.getBoundingClientRect().height.toFixed(2);
      if (Math.abs(h - prev) < 0.5) { if (++stable >= 2) return h; }
      else stable = 0;
      prev = h;
      await new Promise(r => setTimeout(r, 80));
    }
    return +t.getBoundingClientRect().height.toFixed(2);
  }, sel);
}

/* type into the box through the REAL delegated input listener — the same path
   his keystrokes take (the `pal` listener calls fitText). `text` REPLACES. */
const type = (p, text) => p.evaluate(t => {
  const ta = document.getElementById('cmdtext');
  ta.value = t;
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
}, text);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1200, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await waitFor(p, '.qa.open');
await p.click('#cmdplus');
if (!(await present(p, '#cmdtext', 'the composer textarea'))) {
  await br.close(); finish(); process.exit(1);
}
await p.waitForFunction(() => cmdpalette.classList.contains('open'));
await sleep(300);

// ── (0) the contract: the box is manually resizable (#570). ──────────────
const resizeCss = await p.evaluate(() => getComputedStyle(document.getElementById('cmdtext')).resize);
ok(`#570 contract: the composer box is manually resizable (resize:vertical, got "${resizeCss}")`,
   resizeCss === 'vertical');

// ── (1) autoexpand WORKS — a precondition, so "stayed after drag" is not
//         vacuous. Type several lines; the box grows past its empty floor. ─
await type(p, '');                                   // start at the floor
const floorH = await settleH(p, '#cmdtext');
const BLOCK = Array.from({ length: 6 }, (_, i) => 'a thought long enough to wrap ' + i).join('\n');
await type(p, BLOCK);
const grownH = await settleH(p, '#cmdtext');
const lineH = await p.evaluate(() => {
  const ta = document.getElementById('cmdtext');
  const cs = getComputedStyle(ta), lh = parseFloat(cs.lineHeight);
  if (isFinite(lh) && lh > 0) return lh;
  return parseFloat(cs.fontSize) * 1.2;
});
notes.push(`floor=${floorH} grown=${grownH} (line ${lineH.toFixed(1)}px)`);
ok(`precondition: autoexpand works — typing grew the box past its floor ` +
   `(${floorH} -> ${grownH}, +${(grownH - floorH).toFixed(0)}px)`,
   grownH > floorH + lineH);

// ── (2) a manual DRAG disables autoexpand. ───────────────────────────────
//    The native handle is a UA control no pointer can drive headless, so the
//    drag is simulated as the browser performs it: pointerdown (the page's
//    handler records the press height + pauses the transition), a direct
//    style.height write (what the handle writes), pointerup (the page's
//    handler sees the change and marks the composition manual). The detection
//    bound is the REAL pointerup handler on the REAL #cmdtext node.
const DRAG = 240;
const drag = await p.evaluate(d => {
  const ta = document.getElementById('cmdtext');
  const before = +ta.getBoundingClientRect().height.toFixed(2);
  const manualBefore = !!ta._manual;
  ta.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
  ta.style.height = (before + d) + 'px';      // the native handle's write
  ta.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
  return {
    before, after: +ta.getBoundingClientRect().height.toFixed(2),
    manual: !!ta._manual, manualBefore,
  };
}, DRAG);
notes.push(`drag: ${drag.before} -> ${drag.after} (manual ${drag.manualBefore}->${drag.manual})`);
ok(`a drag is detected as manual (the pointerup handler set _manual)`,
   drag.manual && !drag.manualBefore);
ok(`the drag really enlarged the box (${drag.before} -> ${drag.after}, +${(drag.after - drag.before).toFixed(0)}px)`,
   drag.after - drag.before >= DRAG - 2);

// ── (3) typing MORE does not override his height — autoexpand yielded. ────
//    Non-vacuous by construction: the typed content's scrollHeight is well
//    past the dragged height, so a live autoexpand would have grown the box
//    toward it. fitText early-returns on _manual, so the box stays put.
const MORE = Array.from({ length: 14 }, (_, i) => 'more line ' + i + ' that would force growth').join('\n');
await type(p, BLOCK + '\n' + MORE);
const afterMore = await settleH(p, '#cmdtext');
const sh = await p.evaluate(() => +document.getElementById('cmdtext').scrollHeight.toFixed(2));
notes.push(`after typing more: box=${afterMore} (dragged ${drag.after}); content scrollHeight=${sh}`);
ok(`vacuity: the typed content wants to be taller than the drag (${sh} > ${drag.after})`,
   sh > drag.after + lineH);
ok(`after a drag, typing MORE does NOT override his height — autoexpand is off ` +
   `(box stayed at ${afterMore}, dragged ${drag.after}; a live autoexpand would grow toward ${sh})`,
   Math.abs(afterMore - drag.after) < 2);

// ── (4) a SUBMIT re-enables autoexpand for the next composition. ──────────
//    The real POST lands (cv.landed shows "sent to the dream"); the submit
//    path clears the box AND _manual, so the next thought grows again.
await p.locator('#cmdform').evaluate(f => f.requestSubmit());
await p.waitForFunction(() => cmdmsg.textContent === 'sent to the dream', null, { timeout: 8000 })
  .catch(() => {});
const landed = await p.evaluate(() => cmdmsg.textContent === 'sent to the dream');
notes.push(`submit landed=${landed}`);
ok(`the submit really landed (the real /command POST succeeded)`, landed);
if (landed) {
  // the box cleared to its floor; _manual cleared with it
  const clearedH = await settleH(p, '#cmdtext');
  const manualAfter = await p.evaluate(() => !!document.getElementById('cmdtext')._manual);
  notes.push(`after submit: box=${clearedH} (floor ${floorH}); _manual=${manualAfter}`);
  ok(`submit cleared the manual flag so autoexpand can return (box back near its floor ${clearedH})`,
     !manualAfter && clearedH < drag.after - DRAG / 2);
  // type a fresh thought BEFORE the ~1.5s courtesy close: it must grow again
  await type(p, BLOCK);
  const regrownH = await settleH(p, '#cmdtext');
  notes.push(`after submit + type: regrown=${regrownH} (floor ${floorH})`);
  ok(`after submit, autoexpand is RE-ENABLED — the next thought grows again ` +
     `(${clearedH} -> ${regrownH}, +${(regrownH - clearedH).toFixed(0)}px)`,
     regrownH > clearedH + lineH);
}

ok('no page errors', errs.length === 0);
await br.close();
try { srv.kill(); } catch (e) {}      // #461: the spawned child holds the loop
finish();
