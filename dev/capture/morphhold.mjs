/* morphhold — #234: the answer-morph re-render hold, raced against /mtime.

   After a send, `holdRerenderUntil` defers the live tick's DOM replacement
   so the morph (flipDock's 1150ms glide + the 850ms regroup travel) cannot
   be interrupted mid-flight. The hold used to be a flat 1600ms; #234
   derived `MORPH_HOLD_MS` (1250) from the measured critical path. This
   guard proves both halves of that number with a FORCED-mtime race:

     BLOCK    — with an /mtime change pending (the send's own write, plus a
                forced /command write), tick() is driven every ~60ms from
                400ms into the hold until it ends. The card node must
                survive every probe, and the flip element must be gliding
                through many computed transforms — sampled per frame,
                because "did it move" and end-state checks pass over
                interruptions (transitions.md). Red-proven against a 100ms
                hold: the first probes replace the node mid-glide and every
                sameNode assertion fails.
     RELEASE  — the gate must also open EARLY: probing continues past the
                hold, and the release must measure ~MORPH_HOLD_MS after the
                hold was set — inside [1200, 1600). Against the old 1600ms
                hold this is RED with a measured release at ~1600-1650ms:
                the old value really did hold too long (the visible pause
                the human asked about in .dreamwork/answers.md). The forced
                /command write lands 400ms into the hold, so the race is
                explicit rather than implied by the send's own write.

   The whole race runs IN PAGE, referenced to the moment `holdRerenderUntil`
   turns non-zero (the POST's resolution), never to the click: on a loaded
   machine a Playwright roundtrip costs 100-300ms and the POST itself 200+,
   which is most of the window being measured. tick() is page-global
   (qsec.mjs's pattern), so the 2s poll's phase never enters the budget
   either — a hold measurement that depends on poll luck is not one.

   And probes are classified by when their tick DECIDED, never by when they
   were scheduled: tick()'s gate samples `Date.now() >= holdRerenderUntil`
   right after its /mtime fetch resolves AND its body is read — and under
   load (pytest -n 2 on the same machine) EACH of those hops stretches, so
   a probe that STARTS at 1100ms can legitimately DECIDE at 1300ms, and a
   correct 1250ms release can MEASURE past 1600ms once /data.json + setData
   are included. Both flaked in practice, and so did timestamping the fetch
   resolution alone (the .text() hop then crossed the deadline behind the
   stamp and the gate legitimately passed). So the guard wraps window.fetch
   and timestamps each /mtime response's text() completion — the last await
   before the gate's own Date.now(), after which only synchronous work
   remains: a probe is inside the hold iff its tick's decision preceded
   holdWall (5ms epsilon), and the release is the FIRST decision at/after
   it, independent of render latency and of whether the driven tick or the
   2s poll landed it.

   The note path (sendComment) shares the constant and gets the same race;
   the reduced-motion phase proves the RM path — no flip, no travel, the
   card just swaps state — releases through the same gate in the same
   window, because reduced motion changes timing, never function.

   Shape: own target and own server on an EPHEMERAL port (the morph.mjs
   shape), because each phase needs a pristine questions.md — answering
   the first open question changes which card the next phase would pick.

   usage: node morphhold.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
/* Report from an exit handler, not from the tail — a guard that throws part
   way through prints nothing, and a reader counting FAIL lines reads a crash
   as a clean run. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

const DIR = join(OUT, 'target');
const reset = () => {
  rmSync(DIR, { recursive: true, force: true });
  cpSync('dev/capture/fixture', DIR, { recursive: true });
};
reset();
const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);
const BASE = `http://127.0.0.1:${PORT}`;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
}

/* Send through the REAL UI in the mode under test — the hold lives in the
   client's submit path, so a bare POST would drive the wrong code — then
   run the race in page time. `data-mh` marks the card NODE itself:
   `card.innerHTML = …` (the morph) keeps the node, the tick's view swap
   does not, so the marker dying IS the re-render. The flip element's
   COMPUTED transform is sampled per frame because the inline value only
   ever holds the two endpoints; the glide lives in the interpolation.

   Returns: holdAt (page ms from click when the hold was set), probes
   (every driven tick: scheduled ms, DECIDED ms, inside-hold, gone),
   releaseAt (ms after the hold was set of the gate's first passing
   decision), ends (every gate decision, ms after hold-set), frames (the
   rAF sample), and whether the forced /command write landed. */
const RACE = (mode, probeFrom, probeCap) => `((probeFrom, probeCap) =>
  (async () => {
    const cards = () => [...document.querySelectorAll('.qa[data-qid]')];
    const first = cards().find(c => c.classList.contains('open'));
    if (!first) return { nofixture: 'no open card' };
    first.dataset.mh = 'probe';
    const t0 = performance.now();
    const frames = [];
    let sampling = true;
    (function step() {
      const probe = document.querySelector('.qa[data-mh=probe]');
      const flip = probe && (probe.querySelector('.anstext')
        || [...probe.querySelectorAll('.follow.human')].pop());
      frames.push({ t: Math.round(performance.now() - t0),
        sameNode: !!probe,
        tf: flip ? getComputedStyle(flip).transform : '',
        cls: probe ? probe.className.replace(/ ?dreamin/, '') : '' });
      if (sampling) requestAnimationFrame(step);
    })();
    first.querySelector('.qmode[data-mode=${mode}]').click();
    first.querySelector('textarea').value =
      'a traced ${mode} long enough to change the card height by more than a line';
    first.querySelector('.qsend').click();
    /* wait for the POST to resolve — the hold being set IS that moment */
    while (!holdRerenderUntil) await new Promise(r => setTimeout(r, 5));
    const holdAt = Math.round(performance.now() - t0);
    const holdWall = holdRerenderUntil;
    /* the constant read FROM THE PAGE, with the old value as fallback so
       the red-proof against a pre-#234 build still measures a number
       instead of throwing on the missing name */
    const HOLD = typeof MORPH_HOLD_MS === 'number' ? MORPH_HOLD_MS : 1600;
    const holdSetAt = holdWall - HOLD;   // wall-clock of the POST resolving
    const gone = () => !document.querySelector('.qa[data-mh=probe]');
    /* decision-time instrumentation, per the header: timestamp each /mtime
       response's text() completion — the last await before the gate's
       Date.now() sample, so this IS the decision clock (sub-ms). The fetch
       resolution alone is NOT: reading the body is a second await that
       load stretches across the deadline behind the stamp. */
    const mtimeEnds = [];
    const realFetch = window.fetch.bind(window);
    window.fetch = (...a) => realFetch(...a).then(r => {
      if (String(a[0]).includes('/mtime')) {
        const realText = r.text.bind(r);
        r.text = () => realText().then(t => {
          mtimeEnds.push(Date.now());
          return t;
        });
      }
      return r;
    });
    /* the forced half of the race, 400ms into the hold: an /mtime change
       that is inside the OLD 1600ms window and outside the new one, made
       the sanctioned way (qsec.mjs's pattern — a real /command write,
       which watched_mtime walks) */
    while (Date.now() < holdSetAt + 400) await new Promise(r => setTimeout(r, 5));
    const forced = await fetch('/command', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea',
                             text: 'morphhold guard forced tick' }) })
      .then(r => r.ok).catch(() => false);
    const probes = [];
    let releaseAt = null;
    while (Date.now() - holdSetAt < probeCap) {
      const msAfterHold = Date.now() - holdSetAt;
      if (msAfterHold >= probeFrom) {
        const before = mtimeEnds.length;
        await tick();                    // page-global, per qsec.mjs
        const g = gone();
        /* this probe's decision: the latest /mtime text() end since we
           drove it (a concurrent 2s-poll tick may add one too — the max is
           still a decision that preceded the look). A probe is INSIDE the
           hold iff that decision preceded the deadline (5ms epsilon for
           the synchronous parseMtime + Date.now() that follow the stamp);
           a tick load stretched across it is the release it legitimately
           is, not a violation. */
        const ends = mtimeEnds.slice(before);
        const decided = ends.length ? Math.max(...ends) : Date.now();
        probes.push({ ms: Math.round(msAfterHold),
                      decided: Math.round(decided - holdSetAt),
                      inside: decided < holdWall - 5, gone: g });
        if (g) {
          /* the gate's FIRST pass, whichever tick landed it: the first
             decision at/after the deadline (same epsilon) */
          const first = mtimeEnds.find(e => e >= holdWall - 5);
          releaseAt = Math.round((first === undefined ? decided : first)
                                 - holdSetAt);
          break;
        }
      }
      await new Promise(r => setTimeout(r, 60));
    }
    sampling = false;
    window.fetch = realFetch;
    /* the decision trace IS the evidence for the classification above, so
       it ships in the notes: every gate decision, and each probe stamped
       with the decision it observed rather than its scheduled instant */
    return { holdAt, holdMs: HOLD, forced, probes, releaseAt, frames,
             ends: mtimeEnds.map(e => Math.round(e - holdSetAt)) };
  })())(${probeFrom}, ${probeCap})`;

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

async function phase(mode, reduced) {
  reset();
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1400 },
    reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
  const r = await p.evaluate(RACE(mode, 400, 2600));
  await ctx.close();
  return r;
}

const uniq = a => [...new Set(a)];
const glide = frames =>
  uniq(frames.map(f => f.tf).filter(t => t && t !== 'none')).length;

for (const [mode, reduced] of [['answer', false], ['note', false],
                               ['answer', true]]) {
  const tag = reduced ? `${mode}-rm` : mode;
  const r = await phase(mode, reduced);
  if (r.nofixture) {
    ok(`${tag}: the fixture gives an open card`, false);
    continue;
  }
  const gl = glide(r.frames);
  const heldProbes = r.probes.filter(x => x.inside);
  const heldMax = heldProbes.length
    ? Math.max(...heldProbes.map(x => x.decided)) : 'none';
  notes.push(`${tag}: hold set ${r.holdAt}ms after click, forced=${r.forced}, ` +
             `release=${r.releaseAt}ms after hold-set (gate decision), ` +
             `probes=${r.probes.length} held=${heldProbes.length} ` +
             `heldMaxDecided=${heldMax}ms frames=${r.frames.length} glide=${gl}`);
  notes.push(`${tag} decisions=${JSON.stringify(r.ends)} ` +
             `probes=${JSON.stringify(r.probes)}`);
  ok(`${tag}: the forced-mtime race is real (the /command write landed ` +
     `400ms into the hold)`, r.forced === true);
  /* BLOCK — the invariant under test on every build. Three legs, because
     probe COUNT is load-dependent (a driven tick() costs 200-400ms under
     load, so only a couple may fit inside the hold) while the proof is
     not: classification is by DECISION time (the tick's /mtime text()
     end — the gate's own clock), so a tick that load stretches across the
     deadline is counted as the release it legitimately is rather than a
     hold violation; the per-frame sample is dense at any frame rate; and
     `releaseAt >= 1200` below proves nothing got through before the
     constant. Red-proven against a 100ms hold. */
  ok(`${tag}: driven ticks inside the hold never replace the card, though `
     + 'the mtime change is pending',
     heldProbes.length >= 1 && heldProbes.every(x => !x.gone));
  ok(`${tag}: ...and the per-frame sample agrees — the node survives every `
     + 'frame of the window, not just the probed instants',
     r.frames.filter(f => f.t < r.holdAt + 1200).every(f => f.sameNode));
  /* RELEASE — the discriminator. releaseAt is the FIRST gate decision at
     or after holdWall (5ms epsilon), so it cannot precede ~1250 by
     construction of the gate and — the point of the task — must land
     BEFORE 1600, the moment the old value would have unlocked. Measuring
     the decision rather than the observed re-render keeps /data.json +
     setData latency out of the budget (they added 200-400ms under load
     and pushed a correct release past the bound). RED on the old 1600ms
     hold: its first passing decision is >= 1600 here by construction of
     the gate. */
  ok(`${tag}: the re-render releases EARLY — ~1250ms after hold-set, ` +
     'in [1200, 1600) (the old 1600ms hold cannot pass this)',
     r.releaseAt !== null && r.releaseAt >= 1200 && r.releaseAt < 1600);
  ok(`${tag}: the node was never replaced BEFORE that release — the early `
     + 'release did not come from interrupting the morph',
     r.frames.filter(f => r.releaseAt === null ||
                          f.t < r.holdAt + r.releaseAt - 100)
             .every(f => f.sameNode));
  if (!reduced) {
    ok(`${tag}: the morph glided through the hold (intermediate computed ` +
       'transforms sampled per frame, not just the end state)', gl >= 8);
  } else {
    /* RM parity: no glide to measure — the function is the state swap, and
       it must have happened locally well before the release. */
    ok(`${tag}: reduced motion swapped the card to its answered state ` +
       'locally (timing changes, never function)',
       r.frames.some(f => f.cls.includes('awaiting')));
  }
}

await br.close();
try { srv.kill(); } catch (e) {}
ok('no page errors', errs.length === 0);
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
