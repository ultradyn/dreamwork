/* posturerecuse — #565 (posture widget sticky on scroll) + #569 (the deploy
   countdown recused into the posture widget with a CSS width transition).

   These are the two RUNTIME behaviours the pytest render tests cannot hold:
     1. STICKY DOCK — when a posture arm is live, .posture.psticky docks to
        the viewport bottom so scrolling up keeps the countdown visible; when
        idle it does not (a probe proved always-on bottom:0 docks the
        end-of-page section permanently, so the class is conditional).
     2. WIDTH TRANSITION — the recused #pdep slot's width eases as its label
        changes (paintDeployStatus's explicit-width idiom), rather than
        snapping; reduced motion snaps.

   Sticky is not motion (transitions.md), so the dock assertion is a position
   check (load-independent). The width transition IS motion, so it uses the
   #442 shape — transitionstart (load-independent snap detector) OR between()
   (motion evidence) — exactly like the posture arm bar guard.

   Own server on a free port (39895 was held by another lane at write time;
   freePort avoids every collision). NOT registered in the justfile (it is
   coordinator-owned) — run solo: node posturerecuse.mjs <outdir>. */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const BASE = `http://127.0.0.1:${PORT}`;

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = []; const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

const dir = join(OUT, 'target');
rmSync(dir, { recursive: true, force: true });
cpSync('dev/capture/fixture', dir, { recursive: true });
const srv = await serveVerified(dir, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });

// between(vals, first, last) — transitions.md: at least one frame STRICTLY
// between the two ends, ~3% deadband. End-state alone cannot fail on a snap.
function between(frames, first, last) {
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const pad = Math.max(0.03, (hi - lo) * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

// ═══ 1. STICKY DOCK (#565, narrowed to .parm by #674) ════════════════════
// Use a viewport short enough that #parm (near the page bottom) sits below
// the fold at scrollY=0, so "docked" vs "not docked" is unambiguous. #674
// moved the .psticky class from the whole #posture component to #parm (the
// bar + "arms in …" line), so every class/geometry check reads #parm.
{
  const ctx = await br.newContext({ viewport: { width: 1000, height: 700 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#parm');
  await sleep(300);
  const vh = 700;
  // idle: no arm → no .psticky → #parm in natural flow (below the fold at
  // the top of the page), NOT docked. #674: the class must NOT leak back onto
  // #posture (the whole component).
  await p.evaluate(() => window.scrollTo(0, 0));
  await sleep(120);
  const idle = await p.evaluate(() => {
    const parm = document.getElementById('parm');
    const r = parm.getBoundingClientRect();
    return { top: Math.round(r.top), bottom: Math.round(r.bottom),
             psticky: parm.classList.contains('psticky'),
             postureSticky: document.getElementById('posture')
               .classList.contains('psticky') };
  });
  notes.push(`idle @top: ${JSON.stringify(idle)}`);
  ok('#674 idle: no .psticky on #parm when no countdown is live',
     idle.psticky === false);
  ok('#674 idle: .psticky is NOT on the whole #posture component',
     idle.postureSticky === false);
  ok('#565 idle: #parm is NOT docked (below the fold, not pinned to bottom)',
     idle.top >= vh);   // natural flow, below the viewport

  // arm a posture change → paintPosturePin adds .psticky on the live arm.
  await p.evaluate(() => document.getElementById('posture')
    .scrollIntoView({ block: 'center' }));
  await sleep(100);
  await p.click('.paxis-chips[data-axis="pace"] .pchip[data-stop="steady"]');
  await sleep(250);
  const armedClass = await p.evaluate(() => ({
    parm: document.getElementById('parm').classList.contains('psticky'),
    posture: document.getElementById('posture').classList.contains('psticky'),
  }));
  ok('#674 armed: .psticky is on #parm while the posture arm is live',
     armedClass.parm === true);
  ok('#674 armed: .psticky is NOT on the whole #posture component',
     armedClass.posture === false);

  // scroll back to the top: the docked #parm stays visible at the bottom.
  await p.evaluate(() => window.scrollTo(0, 0));
  await sleep(150);
  const docked = await p.evaluate(() => {
    const el = document.getElementById('parm');
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top), bottom: Math.round(r.bottom),
             psticky: el.classList.contains('psticky') };
  });
  notes.push(`armed @top: ${JSON.stringify(docked)}`);
  ok('#565 armed: #parm stays visible (top inside the viewport) on scroll-up',
     docked.top < vh && docked.psticky === true);
  ok('#565 armed: #parm is docked to the viewport bottom (bottom â vh)',
     Math.abs(docked.bottom - vh) <= 2);

  // #636/#674 — the docked #parm must not PAINT, and (#674) must carry NO
  // top hairline. --bg is the flat page colour; #dreambg (z-index:-1) is what
  // the page shows, so an opaque fill punches a flat rectangle through the
  // shader. The hairline #565 added rode the whole .posture section and
  // appeared above "posture / arming overrideâ¦"; narrowing the dock to .parm
  // removed it (the .pbar is itself a visible boundary). Computed, not
  // declared.
  const fill = await p.evaluate(() => {
    const cs = getComputedStyle(document.getElementById('parm'));
    const cv = document.getElementById('dreambg');
    return { bg: cs.backgroundColor, shadow: cs.boxShadow,
             canvas: cv ? getComputedStyle(cv).display : null };
  });
  notes.push(`#636/#674 docked fill: ${JSON.stringify(fill)}`);
  ok(`#636 docked: the #parm fill is transparent, not a block (${fill.bg})`,
     fill.bg === 'rgba(0, 0, 0, 0)' || fill.bg === 'transparent');
  ok('#674 docked: #parm carries NO top hairline (box-shadow removed)',
     fill.shadow === 'none');

  // clear the arm (module-scope, like the staleremedy guard sets staleDeploy*)
  // and confirm the dock releases — back to natural flow, below the fold.
  await p.evaluate(() => {
    postArmUntil = 0; postArmGen++; clearPostPending();
    if (postArmTimer) { clearTimeout(postArmTimer); postArmTimer = null; }
    if (postArmTick) { clearInterval(postArmTick); postArmTick = null; }
    paintPosturePin();
  });
  await sleep(120);
  const released = await p.evaluate(() => {
    const el = document.getElementById('parm');
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top), psticky: el.classList.contains('psticky') };
  });
  notes.push(`cleared @top: ${JSON.stringify(released)}`);
  ok('#565 cleared: .psticky removed from #parm when no countdown is live',
     released.psticky === false);
  await ctx.close();
}

// ═══ 2. WIDTH TRANSITION (#569) ══════════════════════════════════════════
// Drive paintDeployStatus directly (the production line) with a short then a
// long label, and capture the width travel — the #442 shape: transitionstart
// (load-independent) OR between() (motion evidence).
async function widthTrace(page, short, long) {
  return page.evaluate(async ({ short, long }) => {
    const el = document.getElementById('pdep');
    let ranWidth = false;
    const onT = e => {
      if (e.propertyName !== 'width') return;
      if (e.target === el && e.type === 'transitionstart') ranWidth = true;
    };
    document.addEventListener('transitionrun', onT, true);
    document.addEventListener('transitionstart', onT, true);
    paintDeployStatus(short);                 // first show (short)
    await new Promise(r => setTimeout(r, 450));
    const widths = [];
    paintDeployStatus(long);                   // the reflow under test
    const t0 = performance.now();
    const tick = () => {
      widths.push(parseFloat(getComputedStyle(el).width) || 0);
      if (performance.now() - t0 < 650) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    await new Promise(r => setTimeout(r, 700));
    document.removeEventListener('transitionrun', onT, true);
    document.removeEventListener('transitionstart', onT, true);
    return { widths, ranWidth, first: widths[0], last: widths[widths.length - 1] };
  }, { short, long });
}

{
  const ctx = await br.newContext({ viewport: { width: 1000, height: 800 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#pdep', { state: 'attached' });
  await sleep(200);
  const t = await widthTrace(p, 'arms in 9s',
                              'updating — waiting for the new page');
  const span = Math.abs((t.first || 0) - (t.last || 0));
  const mid = between(t.widths, t.first, t.last);
  notes.push(`#569 width: first=${t.first} last=${t.last} span=${span.toFixed(1)} ` +
             `mid=${mid} transitionstart=${t.ranWidth} n=${t.widths.length}`);
  ok(`#569 width span measured ${span.toFixed(1)}px (floor 20)`, span >= 20);
  ok(`#569 width eases (transitionstart=${t.ranWidth} or mid=${mid})`,
     t.ranWidth || mid >= 1);
  await ctx.close();
}

// ═══ 2b. reduced motion snaps the width (#569 parity) ════════════════════
{
  const ctx = await br.newContext({
    viewport: { width: 1000, height: 800 }, reducedMotion: 'reduce',
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push('rm: ' + e));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#pdep', { state: 'attached' });
  await sleep(200);
  const t = await widthTrace(p, 'arms in 9s',
                              'updating — waiting for the new page');
  const distinct = new Set(t.widths.map(w => Math.round(w))).size;
  notes.push(`#569 rm width: distinct=${distinct} transitionstart=${t.ranWidth}`);
  ok('#569 reduced motion: width does NOT transition (snaps, ≤2 distinct)',
     !t.ranWidth && distinct <= 2);
  await ctx.close();
}

// ═══ 3. A FAILED DEPLOY RELEASES THE DOCK (#636) ═════════════════════════
// #565 gates .psticky on posturePinnedLive(), which reads staleDeployPhase.
// Every path that RAISES the pin called paintPosturePin(); the three that
// LOWER it (refused / unreachable / never-finished) did not, so a deploy that
// did not land welded the widget to the viewport bottom until the next
// data-change render. Measured stuck 17s on all three before the fix.
// Driven through the production lines (armStaleDeploy -> fireStaleDeploy)
// with the POST refused at the route; `just deploy` is never run.
{
  const ctx = await br.newContext({ viewport: { width: 1000, height: 700 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push('deployfail: ' + e));
  await p.route('**/deploy', route => route.fulfill({
    status: 202, contentType: 'application/json',
    body: JSON.stringify({ ok: false, rejected: true,
                           reason: 'domain_invalid', detail: 'not_local' }),
  }));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#parm');
  await sleep(300);

  await p.evaluate(() => armStaleDeploy());
  await sleep(200);
  const armed = await p.evaluate(() => ({
    psticky: document.getElementById('parm').classList.contains('psticky'),
    phase: staleDeployPhase,
  }));
  notes.push(`#636 deploy armed: ${JSON.stringify(armed)}`);
  // precondition: without the raise there is nothing for the release to prove
  ok('#636 precondition: a live deploy arm docks #parm',
     armed.psticky === true && armed.phase === 'arming');

  // fire it now rather than waiting out RUN_ARM_MS; drop the arm's own timer
  // first so it cannot fire a second time behind us.
  await p.evaluate(async () => {
    if (staleDeployTimer) { clearTimeout(staleDeployTimer); staleDeployTimer = null; }
    if (staleDeployTick) { clearInterval(staleDeployTick); staleDeployTick = null; }
    await fireStaleDeploy(staleDeployGen);
  });
  await sleep(400);
  const after = await p.evaluate(() => {
    const el = document.getElementById('parm');
    return { psticky: el.classList.contains('psticky'),
             position: getComputedStyle(el).position,
             phase: staleDeployPhase,
             fmsg: (document.querySelector('.fmsg') || {}).textContent || '' };
  });
  notes.push(`#636 after refusal: ${JSON.stringify(after)}`);
  ok('#636 refused: the deploy phase ended', after.phase === null);
  ok('#636 refused: the refusal is still named in #fmsg',
     /refused/.test(after.fmsg));
  ok('#636 refused: .psticky is released (the dock does not stay welded)',
     after.psticky === false);
  ok('#636 refused: #parm is back in natural flow (not position:sticky)',
     after.position !== 'sticky');
  await ctx.close();
}

ok('no page errors', errs.length === 0);
finished = true;
await br.close();
try { srv.kill(); } catch (e) {}
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
