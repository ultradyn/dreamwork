/* #113 — the awaiting-fold state looks alive.

   It is the only genuinely in-progress thing on the page, so it is the one
   deliberate exception to the opt-in motion rule — which means it has to
   earn the exception on three counts, and this checks all three:

     - it BREATHES rather than spins: the intensity rises AND falls, slowly.
       A one-way loop and a fast pulse both read as a spinner, and both would
       pass a naive "does it move" check, so the assertion is on the number
       of direction reversals over a fixed window, not on movement.
     - it is CHEAP BY CONSTRUCTION, not by a measurement that could drift:
       the keyframes are read out of the live stylesheet and asserted to
       touch nothing but opacity and background-position, and the animated
       boxes are asserted to be small. Frame timings are measured too, but
       only as a loose ceiling — under SwiftShader they are far too noisy to
       gate on, and a flaky red trains you to ignore the light.
     - under reduced motion it HOLDS STILL rather than vanishing: the state
       must still read as in-progress with no motion at all.

   usage: node wisp.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions in two contexts (normal + reduced-motion), sampling the ' +
          'awaiting-fold .anstag rail and label every rAF for 6.4s, reading the ' +
          'qbreathe/qwisp keyframes out of the live stylesheet, and an A/B of ' +
          'frame timings with animations killed',
  traceWindow: 'one 6.4s rAF sample per context (~one full breath) plus a 200-frame ' +
               'p50/p95 frame-time A/B; motion is the subject, sampled not asserted at ends',
});

// sample the wisp's two channels every frame for a full cycle and a bit
const SAMPLE = `(ms => new Promise(res => {
  if (!document.querySelector('.qa.awaiting')) { res(null); return; }
  const rail = [], drift = [];
  const t0 = performance.now();
  (function step() {
    // Re-acquire the awaiting card and its tag EVERY frame. The live tick
    // re-renders /questions and REPLACES the .qa.awaiting node mid-sample; a
    // reference cached once detaches, and getComputedStyle on the detached
    // card's ::before returns a one-directional transient (rail down~0.05,
    // drift down~1.0) that reads as a sweep on a page that breathes correctly.
    // Re-querying tracks the live node through the re-render — the same
    // do-not-cache-across-a-re-render lesson as qsec and oneinput. (#475.)
    const card = document.querySelector('.qa.awaiting');
    const tag = card && card.querySelector('.anstag');
    if (card) rail.push(+getComputedStyle(card, '::before').opacity);
    else if (rail.length) rail.push(rail.at(-1));
    if (tag) drift.push(parseFloat(getComputedStyle(tag).backgroundPosition) || 0);
    else if (drift.length) drift.push(drift.at(-1));
    if (performance.now() - t0 < ms) requestAnimationFrame(step); else res({ rail, drift });
  })();
}))(6400)`;

// frame deltas with nothing else going on — run twice, once with every
// animation killed, so the comparison is an A/B rather than a threshold
const FRAMES = kill => `(async () => {
  if (${kill}) {
    const s = document.createElement('style');
    s.textContent = '*,*::before,*::after{animation:none !important}';
    document.head.appendChild(s);
    await new Promise(r => setTimeout(r, 300));
  }
  const d = []; let last = performance.now();
  await new Promise(res => (function step() {
    const t = performance.now(); d.push(t - last); last = t;
    if (d.length < 200) requestAnimationFrame(step); else res();
  })());
  d.sort((a, b) => a - b);
  return { p50: d[100], p95: d[190] };
})()`;

/* The shape of the envelope, in the two numbers that tell a breath from the
   two things it must not be.

   `reversals` catches a spinner: one breath in and out over the sampled
   window turns around about twice, a fast pulse turns around a dozen times.

   `down` catches a SAWTOOTH, and it exists because counting reversals alone
   does not. A one-way sweep that snaps back to its start also "turns around"
   twice per cycle — the snap is one frame of steep negative slope — so the
   first version of this check passed a deliberately introduced sweep. What
   actually separates them is how LONG the fall takes: a breath spends about
   as long fading out as fading in, a sawtooth spends one frame. So the
   assertion is on the fraction of moving samples that are falling. */
const envelope = xs => {
  let up = 0, down = 0, rev = 0, prev = 0;
  for (let i = 1; i < xs.length; i++) {
    const d = xs[i] - xs[i - 1];
    if (Math.abs(d) < 1e-4) continue;
    const s = Math.sign(d);
    if (s > 0) up++; else down++;
    if (prev && s !== prev) rev++;
    prev = s;
  }
  return { rev, down: down / Math.max(1, up + down) };
};
const span = xs => Math.max(...xs) - Math.min(...xs);

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({ viewport: { width: 1100, height: 950 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(1200);
  const tag = reduced ? 'reduced-motion' : 'normal';

  const s = await p.evaluate(SAMPLE);
  if (!s) {
    ok(`${tag}: fixture has an awaiting-fold entry to sample`, false);
    notes.push('fixture has no awaiting-fold entry');
    await br.close(); finish(); process.exit(1);
  }
  const R = envelope(s.rail), D = envelope(s.drift);
  notes.push(`${tag}: rail span=${span(s.rail).toFixed(2)} rev=${R.rev}` +
             ` down=${R.down.toFixed(2)} | drift span=${span(s.drift).toFixed(1)}px` +
             ` rev=${D.rev} down=${D.down.toFixed(2)}`);

  if (!reduced) {
    ok(`${tag}: the rail's intensity actually varies`, span(s.rail) > 0.3);
    ok(`${tag}: the wisp drifts along the label`, span(s.drift) > 20);
    // it spends as long fading OUT as fading in — a sweep that snaps back
    // would spend one frame on the return
    ok(`${tag}: the intensity fades in and OUT — a breath, not a sweep`,
       R.down > 0.25 && R.down < 0.75 && D.down > 0.25 && D.down < 0.75);
    // 6.4s of a 5.5s cycle is a little over one breath; a spinner would turn
    // around many more times in the same window
    ok(`${tag}: it breathes slowly — not a spinner`, R.rev <= 4 && D.rev <= 4);

    // cheap BY CONSTRUCTION: read the keyframes out of the live stylesheet
    const shape = await p.evaluate(() => {
      const props = new Set(); const names = [];
      for (const sheet of document.styleSheets) {
        let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
        for (const r of rules) {
          if (r.type !== CSSRule.KEYFRAMES_RULE) continue;
          if (!/^q(breathe|wisp)$/.test(r.name)) continue;
          names.push(r.name);
          for (const kf of r.cssRules) for (const pr of kf.style) props.add(pr);
        }
      }
      const card = document.querySelector('.qa.awaiting');
      const t = card.querySelector('.anstag').getBoundingClientRect();
      const railW = parseFloat(getComputedStyle(card, '::before').width);
      return { props: [...props].sort(), names: [...new Set(names)].sort(),
               railW, tagArea: Math.round(t.width * t.height),
               railAnim: getComputedStyle(card, '::before').animationName,
               tagAnim: getComputedStyle(card.querySelector('.anstag')).animationName,
               // the exception is for awaiting ONLY
               elsewhere: [...document.querySelectorAll('.qa:not(.awaiting)')]
                 .filter(c => getComputedStyle(c, '::before').animationName !== 'none')
                 .length };
    });
    notes.push(`${tag}: keyframes=${shape.names} props=${shape.props} ` +
               `rail=${shape.railW}px label=${shape.tagArea}px2`);
    ok(`${tag}: both halves of the envelope are live`,
       shape.railAnim === 'qbreathe' && shape.tagAnim === 'qwisp');
    // the CSSOM serialises background-position as its two longhands, so the
    // expected set is stated the way the browser reports it rather than the
    // way the stylesheet writes it
    ok(`${tag}: the keyframes touch ONLY opacity and background-position`,
       shape.props.every(x => /^(opacity|background-position-[xy])$/.test(x)) &&
       shape.props.includes('opacity'));
    ok(`${tag}: the animated boxes are small (a 2px rail, one short label)`,
       shape.railW <= 3 && shape.tagArea < 3000);
    ok(`${tag}: no other card state animates — the exception is awaiting only`,
       shape.elsewhere === 0);

    // ...and measured anyway, as a loose ceiling only
    const withIt = await p.evaluate(FRAMES(false));
    const without = await p.evaluate(FRAMES(true));
    notes.push(`${tag}: frames p50 ${withIt.p50.toFixed(1)}→${without.p50.toFixed(1)}ms` +
               ` p95 ${withIt.p95.toFixed(1)}→${without.p95.toFixed(1)}ms (wisp→none)`);
    ok(`${tag}: the wisp is not measurable in frame time`,
       withIt.p95 < Math.max(without.p95 * 2.5, without.p95 + 8));
    await p.screenshot({ path: `${OUT}/awaiting.png`, fullPage: true });
  } else {
    ok(`${tag}: the wisp holds still`,
       span(s.rail) < 0.01 && span(s.drift) < 1 && R.rev === 0 && D.rev === 0);
    // still, but still reading as in-progress: the rail is there and lit,
    // and the label still carries the accent through it
    const still = await p.evaluate(() => {
      const card = document.querySelector('.qa.awaiting');
      const cs = getComputedStyle(card, '::before');
      const tag = getComputedStyle(card.querySelector('.anstag'));
      return { railOpacity: +cs.opacity, railW: parseFloat(cs.width),
               clipped: /text/.test(tag.backgroundClip + tag.webkitBackgroundClip),
               hasGradient: /gradient/.test(tag.backgroundImage) };
    });
    ok(`${tag}: the rail is still there and fully lit`,
       still.railOpacity === 1 && still.railW >= 1);
    ok(`${tag}: the label still carries the wisp, frozen at its brightest`,
       still.clipped && still.hasGradient);
  }
  ok(`${tag}: no page errors`, errs.length === 0);
  await br.close();
}

finish();