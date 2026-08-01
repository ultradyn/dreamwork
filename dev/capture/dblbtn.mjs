/* dblbtn — #844: durable render + timing guard for #829's double-click action.

   This drives the real /chat/<id> archive button. Playwright's browser clock
   advances Date, timers, rAF, and CSS animations, so both sides of the 4000ms
   boundary are exact without adding several wall-clock waits to every sweep.
   That is deliberately an emulated-browser-clock proof, not a claim about
   wall-clock scheduling under suspension.

   Assertion order mirrors cmdmore.mjs: population, geometry, appearance, then
   a composite invisible-control failure. The countdown is also sampled at
   1000ms and 3000ms in COMPUTED style and in painted pixels; an elapsed-time
   (inverted) conic ring therefore grows and fails instead of looking plausible.

   usage: node dblbtn.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { waitFor, waitForServer } from './dom.mjs';

const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const PORT = process.argv[3] || '39898';
const BASE = `http://127.0.0.1:${PORT}`;
const CHAT_ID = 'dblbtn-guard';
const WINDOW_MS = 4000;
const INSIDE_MS = 3500; // margin for the few real milliseconds around a click
const { ok, present, declare, finish, notes, errs } = makeReporter();

declare({
  drives: 'the real .chatarchbtn on /chat/dblbtn-guard: first/second clicks ' +
          'inside and outside its 4-second window, normal-motion countdown ' +
          'paint, and reduced-motion armed-state parity',
  traceWindow: 'Playwright browser-clock advances to 3500ms and 4001ms for ' +
               'the boundary, and samples the countdown at 1000ms + 3000ms; ' +
               'no wall-clock wait is used',
});

const clockTime = new Date('2026-01-01T00:00:00Z');
const actionRGB = [251, 146, 60]; // --uibtn-action, sampled only in the outer ring

async function newPage(browser, reducedMotion = false) {
  const ctx = await browser.newContext({
    viewport: { width: 900, height: 700 },
    reducedMotion: reducedMotion ? 'reduce' : 'no-preference',
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  let posts = 0;
  await p.route('**/chat-archive', async route => {
    posts += 1;
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  await p.goto(`${BASE}/chat/${CHAT_ID}`, { waitUntil: 'networkidle' });
  await waitFor(p, '.chatarchbtn');
  // Install only once the subject exists: navigation uses ordinary time, then
  // the controlled advance begins with no navigation-time clock drift.
  await p.clock.install({ time: clockTime });
  return { ctx, p, posts: () => posts };
}

async function readButton(p) {
  return p.evaluate(() => {
    const btn = document.querySelector('.chatarchbtn');
    if (!btn) return { missing: true };
    const labels = btn.querySelector('.uibtnlabels');
    const rest = labels && labels.querySelector('span:first-child');
    const armed = btn.querySelector('.uibtnarmed');
    const br = btn.getBoundingClientRect();
    const ar = armed ? armed.getBoundingClientRect() : null;
    const acs = armed ? getComputedStyle(armed) : null;
    const pcs = getComputedStyle(btn, '::before');
    return {
      missing: false,
      buttonText: (btn.textContent || '').trim(),
      labelCount: labels ? labels.querySelectorAll(':scope > span').length : 0,
      restText: rest ? (rest.textContent || '').trim() : '',
      armedText: armed ? (armed.textContent || '').trim() : '',
      isArmed: btn.classList.contains('armed'),
      pressed: btn.getAttribute('aria-pressed'),
      rect: { x: br.x, y: br.y, width: br.width, height: br.height },
      armedRect: ar ? { width: ar.width, height: ar.height } : null,
      opacity: acs ? parseFloat(acs.opacity) : 0,
      visibility: acs ? acs.visibility : 'missing',
      transitionProperty: acs ? acs.transitionProperty : '',
      transitionDuration: acs ? acs.transitionDuration : '',
      remaining: parseFloat(pcs.getPropertyValue('--uibtn-remaining')),
      ringOpacity: parseFloat(pcs.opacity),
      ringImage: pcs.backgroundImage,
      pseudoTransitionDuration: pcs.transitionDuration,
    };
  });
}

function hasPositiveDuration(css) {
  return String(css).split(',').some(v => parseFloat(v) > 0);
}

/* Count action-orange pixels ONLY outside the button box. The armed label and
   ordinary 1px border are inside, so they cannot make an absent conic ring
   look painted. The clip has a 5px apron; ::before reaches 3px into it. */
async function ringPixels(p, stem) {
  const rect = await p.locator('.chatarchbtn').boundingBox();
  const pad = 5;
  const clip = {
    x: Math.floor(rect.x) - pad,
    y: Math.floor(rect.y) - pad,
    width: Math.ceil(rect.x + rect.width) - Math.floor(rect.x) + pad * 2,
    height: Math.ceil(rect.y + rect.height) - Math.floor(rect.y) + pad * 2,
  };
  const png = await p.screenshot({ path: `${OUT}/${stem}.png`, clip });
  const rgba = execFileSync('magick', ['png:-', '-depth', '8', 'rgba:-'], {
    input: png, maxBuffer: 4 * 1024 * 1024,
  });
  let count = 0;
  for (let y = 0; y < clip.height; y++) {
    for (let x = 0; x < clip.width; x++) {
      if (!(x < pad || y < pad || x >= clip.width - pad || y >= clip.height - pad)) continue;
      const i = (y * clip.width + x) * 4;
      if (Math.abs(rgba[i] - actionRGB[0]) <= 18 &&
          Math.abs(rgba[i + 1] - actionRGB[1]) <= 18 &&
          Math.abs(rgba[i + 2] - actionRGB[2]) <= 18 && rgba[i + 3] > 200) count++;
    }
  }
  return count;
}

try {
  await waitForServer(BASE);
  const target = await (await fetch(`${BASE}/data.json`)).json();
  // The shared fixture is intentionally chatless. Plant one real transcript
  // through the production writer in the runner's disposable target.
  execFileSync('python3', ['-c',
    `import watch; watch.apply_chat_turn(${JSON.stringify(target.target)}, ` +
    `${JSON.stringify(CHAT_ID)}, 'human', 'guard turn', ` +
    `'2026-01-01T00:00:00')`], { stdio: 'ignore' });

  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

  // ── POPULATION (#671): no button / no labels is a named failure ────────
  const normal = await newPage(br);
  const { p } = normal;
  if (!(await present(p, '.chatarchbtn', 'the double-click action button'))) {
    await normal.ctx.close(); await br.close(); finish();
  } else {
    const pop = await readButton(p);
    ok('button population is nonempty (archive label rendered)', pop.buttonText.length > 0);
    ok('label population is nonempty (rest + armed labels rendered)',
       pop.labelCount === 2 && pop.restText.length > 0 && pop.armedText === 'Action');

    // ── GEOMETRY + APPEARANCE + TRANSITION ───────────────────────────────
    await p.click('.chatarchbtn');
    const armed0 = await readButton(p);
    ok('first click arms without performing the action (0 POSTs)',
       armed0.isArmed && armed0.pressed === 'true' && normal.posts() === 0);
    ok('armed label transition exists on the element that changes (not a snap)',
       /(^|, )opacity(,|$)|(^|, )all(,|$)/.test(armed0.transitionProperty) &&
       hasPositiveDuration(armed0.transitionDuration));
    await p.clock.runFor(500);
    const armedFinal = await readButton(p);
    const geometryOk = armedFinal.rect.width > 0 && armedFinal.rect.height > 0 &&
      armedFinal.armedRect && armedFinal.armedRect.width > 0 && armedFinal.armedRect.height > 0;
    const visible = armedFinal.opacity > 0 && armedFinal.visibility === 'visible';
    ok('armed Action control has nonzero rendered geometry', geometryOk);
    ok(`armed Action control is visible (opacity ${armedFinal.opacity}, ` +
       `${armedFinal.visibility})`, visible);
    ok('geometry did not pass over an invisible control', !(geometryOk && !visible));
    const normalRect = armedFinal.rect;
    await normal.ctx.close();

    // ── BOTH SIDES of the exact 4-second boundary ────────────────────────
    const inside = await newPage(br);
    await inside.p.click('.chatarchbtn');
    await inside.p.clock.runFor(INSIDE_MS);
    const beforeDeadline = await readButton(inside.p);
    await inside.p.click('.chatarchbtn');
    await new Promise(r => setTimeout(r, 50));
    ok('second click at 3500ms (inside the 4-second window) performed exactly once',
       beforeDeadline.isArmed && inside.posts() === 1);
    await inside.ctx.close();

    const outside = await newPage(br);
    await outside.p.click('.chatarchbtn');
    await outside.p.clock.runFor(WINDOW_MS + 1);
    const expired = await readButton(outside.p);
    ok('button disarmed when the 4-second window expired',
       !expired.isArmed && expired.pressed === 'false');
    await outside.p.click('.chatarchbtn');
    await new Promise(r => setTimeout(r, 50));
    ok('second click outside the 4-second window did not act (0 POSTs)',
       outside.posts() === 0);
    await outside.ctx.close();

    // ── COUNTDOWN POLARITY: remaining time SHRINKS at two points ─────────
    const count = await newPage(br);
    await count.p.click('.chatarchbtn');
    await count.p.clock.runFor(1000);
    const early = await readButton(count.p);
    const earlyPx = await ringPixels(count.p, 'dblbtn-remaining-1000ms');
    await count.p.clock.runFor(2000);
    const late = await readButton(count.p);
    const latePx = await ringPixels(count.p, 'dblbtn-remaining-3000ms');
    ok('radial countdown is painted into the border at 1000ms',
       early.ringOpacity > 0 && early.ringImage.includes('conic-gradient') && earlyPx > 12);
    ok(`countdown polarity is remaining-time: computed thick arc SHRANK ` +
       `1000ms→3000ms (${early.remaining.toFixed(3)}→${late.remaining.toFixed(3)})`,
       Number.isFinite(early.remaining) && Number.isFinite(late.remaining) &&
       early.remaining > late.remaining);
    ok(`countdown polarity is remaining-time in painted pixels: thick border ` +
       `SHRANK 1000ms→3000ms (${earlyPx}→${latePx} action pixels)`,
       earlyPx > 12 && latePx + 20 < earlyPx);
    notes.push(`countdown samples: 1000ms remaining=${early.remaining.toFixed(3)} ` +
               `pixels=${earlyPx}; 3000ms remaining=${late.remaining.toFixed(3)} pixels=${latePx}`);
    await count.ctx.close();

    // ── REDUCED MOTION: same final geometry and state, no motion ─────────
    const reduced = await newPage(br, true);
    await reduced.p.click('.chatarchbtn');
    await reduced.p.clock.runFor(1);
    const rm = await readButton(reduced.p);
    const sameGeometry = Math.abs(rm.rect.width - normalRect.width) < 0.5 &&
      Math.abs(rm.rect.height - normalRect.height) < 0.5;
    ok('reduced motion reaches the same armed final geometry and visible Action state',
       sameGeometry && rm.isArmed && rm.opacity === 1 && rm.visibility === 'visible');
    ok('reduced motion has no label or countdown transition',
       !hasPositiveDuration(rm.transitionDuration) &&
       !hasPositiveDuration(rm.pseudoTransitionDuration));
    await reduced.ctx.close();

    await br.close();
  }
} catch (e) {
  errs.push('guard threw: ' + (e && e.stack ? e.stack : String(e)));
}

finish();
