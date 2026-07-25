/* The tab's identity — the title (#153), and later the favicon.

   This is the only part of the dashboard that exists while the tab is
   backgrounded, which is most of its life, so what it has to answer is not
   "what app is this" but DOES IT NEED ME and WHICH loop is this:

       (2) dreamwork/alpha-loop · dreaming · questions

   Four claims, and each of them was reachable only from a browser: the count
   comes from `status.awaiting_human` with `open_questions` as the fallback,
   the liveness word from `last_tick`'s AGE, the project from the target's
   own path, and the whole thing has to keep changing while nobody navigates.

   ONE SERVER, ONE TARGET, REWRITTEN BETWEEN STATES. health.mjs needs several
   targets at once because its three states must be compared; these are a
   sequence, and driving them through one live page is not a shortcut — it is
   the load-bearing half. A title set once at navigation would satisfy every
   check that reloads between states, and the whole feature is that it does
   not.

   The two checks worth knowing about:

     THE STALE FLIP HAPPENS ON THE CLOCK, WITH NOTHING TOUCHING DISK. A loop
     that stops writing produces no event at all — no mtime change, no tick,
     nothing for a re-render to hang off. So the guard writes a `last_tick`
     just short of the threshold and then waits, in real time, WITHOUT
     writing anything, and requires the title to flip anyway. That is the
     only version of this check that can fail if the flip is wired to the
     data instead of to the clock.

     AN UNPARSEABLE `last_tick` IS ITS OWN STATE. The status panel has always
     documented a verbatim fallback for one and had never once run it —
     `if (t)` is falsy for NaN, so the branch was unreachable and the fact
     vanished off the page instead (#154's shape). Both halves are checked:
     the title claims no liveness, and the panel still shows what the loop
     wrote.

   It picks its own EPHEMERAL port and ignores the one it is handed, for
   dashboard.mjs's reason. usage: node identity.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, readFileSync, rmSync, cpSync } from 'node:fs';
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
/* Report from an exit handler, never from the tail: a guard that throws part
   way through otherwise prints nothing, and a reader counting FAIL lines
   sees a crash as a clean run. */
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

/* The directory name is the project name, and it is deliberately NOT this
   repo's: a title hardcoding `dreamwork` would pass against a target called
   anything else. */
const DIR = join(OUT, 'alpha-loop');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const SPATH = join(DIR, '.dreamwork', 'status.json');
const QPATH = join(DIR, '.dreamwork', 'questions.md');
const QGOOD = readFileSync(QPATH, 'utf8');
// the shape that actually happened: the loop wrote its questions AS headings,
// so the reader sees no entries at all and every count derived from them lies
const QBROKEN = '# Questions for the human\n\n' +
  '## Should we ship the daemon before the hub?\nIt matters.\n';

const iso = ms => new Date(ms).toISOString().replace(/\.\d+Z$/, '+00:00');
const status = (extra) => JSON.stringify({
  task: 'dreamer-identity: the tab says whether you are needed',
  goal: 'a glance at the tab strip is enough',
  last_tick: iso(Date.now()),
  ...extra,
}, null, 2);
const writeStatus = extra => writeFileSync(SPATH, status(extra));

/* THE TWO NUMBERS MUST DIFFER, and neither of them is written down here any
   more. That gap is the whole check: with the same count of each, a title
   reading the derived number instead of the loop's own statement is
   byte-identical to a correct one, and the first deliberate bug injected
   here passed against it. It was a literal 3 beside a fixture that held 2,
   and #197 seeded a third open question — so the guard went vacuous without
   going red, which is the worse of the two failures. The count is derived
   from the server below and the gap is asserted rather than assumed. */
writeStatus({ awaiting_human: ['placeholder until the open count is known'] });

const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);

/* our server, not a neighbour's — a readiness probe that accepts any answer
   eventually grades a stranger's process */
const BASE = `http://127.0.0.1:${PORT}`;
let OPENQ = 0;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
  OPENQ = d.open_questions;
}
const AWAIT_N = OPENQ + 2;      // deliberately not the open count
writeStatus({ awaiting_human:
  Array.from({ length: AWAIT_N }, (_, i) => `the thing numbered ${i + 1}`) });

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await sleep(1200);

/* Wait for the title to become something, rather than for a fixed delay: the
   tick is 2s and the age sweep 1s, and a sleep tuned to those is a race that
   passes on this machine and fails on a slower one. Returns the title either
   way so the assertion — not the wait — is what reports. */
async function titleWhen(pred, ms = 9000) {
  const until = Date.now() + ms;
  for (;;) {
    const t = await p.title();
    if (pred(t) || Date.now() > until) return t;
    await sleep(250);
  }
}
const title = () => p.title();

// ── the count, front-loaded ───────────────────────────────────────────────
notes.push(`awaiting ${AWAIT_N}, ${OPENQ} open q`);
ok('the two counts differ, so a title reading the wrong one is visible ' +
   '(else every check about WHICH source is vacuous)',
   OPENQ > 0 && AWAIT_N !== OPENQ);
let t = await titleWhen(x => x.startsWith(`(${AWAIT_N})`));
notes.push(`awaiting ${AWAIT_N}:            ${t}`);
ok('the count is FIRST — tabs truncate from the right', /^\(\d+\) /.test(t));
ok('...and it is awaiting_human\'s length, not the open-question count',
   t.startsWith(`(${AWAIT_N}) `));
ok('the project is the target\'s own name', t.includes('alpha-loop'));
/* ...and the app's name is beside it (his ruling, 15:30). Asserted as the
   compound field rather than as a substring, so a title that dropped the
   project and kept only the app word cannot pass this. */
ok('...beside the app\'s, in one field', t.includes('dreamwork/alpha-loop'));
ok('...and the loop reads as alive', /·\s*dreaming/.test(t));
ok('the dashboard route adds nothing after the state',
   new RegExp(`^\\(${AWAIT_N}\\) dreamwork/alpha-loop · dreaming$`).test(t));

// ── it changes with no navigation at all ──────────────────────────────────
/* The whole feature. A title assembled once in navigate() passes every check
   above and none of the ones below. */
writeStatus({ awaiting_human: ['only this one now'] });
t = await titleWhen(x => x.startsWith('(1)'));
notes.push(`awaiting 1 (live):     ${t}`);
ok('a new count reaches the title with no navigation', t.startsWith('(1) '));

// ── zero reads as zero ────────────────────────────────────────────────────
writeStatus({ awaiting_human: [] });
t = await titleWhen(x => x.startsWith('(0)'));
notes.push(`awaiting none:         ${t}`);
ok('zero renders as (0), not as an empty bracket', t.startsWith('(0) '));

// ── the fallback: no status.json at all ───────────────────────────────────
/* A target whose loop has never written one still has questions.md, so the
   count falls back to the entries in it — the number the server reported
   above, not a literal, which is what #197 broke by adding one. */
rmSync(SPATH, { force: true });
t = await titleWhen(x => x.startsWith(`(${OPENQ})`));
notes.push(`no status.json:        ${t}`);
ok('with no status.json the count falls back to open questions',
   t.startsWith(`(${OPENQ}) `));
ok('...and no liveness word is invented', !/dreaming|stalled/.test(t));
ok('...the project is still named', t.includes('alpha-loop'));

// ── the broken channel outranks the count ─────────────────────────────────
/* In this state every count on the page is a lie, including this one — so
   the title stops reporting a number and reports that it cannot. */
writeStatus({ awaiting_human: ['this number cannot be trusted'] });
writeFileSync(QPATH, QBROKEN);
t = await titleWhen(x => x.startsWith('(!)'));
notes.push(`unreadable questions:  ${t}`);
ok('an unreadable questions.md replaces the count with (!)',
   t.startsWith('(!) '));
/* No digit ANYWHERE in the leading bracket. The obvious `\(!\)\s*\d` reads
   the alternative design — `(!1)`, bang and count together — as a pass,
   because the `)` it anchors on is not there in the state it exists to
   reject. It passed against exactly that injection. */
ok('...and no digit is offered beside it', !/^\([^)]*\d/.test(t));
writeFileSync(QPATH, QGOOD);

// ── an unparseable last_tick claims nothing, and is still shown ───────────
writeStatus({ awaiting_human: [], last_tick: 'whenever' });
t = await titleWhen(x => x.startsWith('(0)') && !/dreaming|stalled/.test(x));
notes.push(`last_tick 'whenever':  ${t}`);
ok('an unparseable last_tick produces no liveness word',
   !/dreaming|stalled/.test(t));
const shown = await p.evaluate(
  () => (document.querySelector('#status .stfacts') || {}).textContent || '');
notes.push(`status facts row:      ${shown.trim()}`);
ok('...and the status panel shows it verbatim rather than dropping it',
   shown.includes('whenever'));

// ── stalled: the loop stopped writing ─────────────────────────────────────
writeStatus({ awaiting_human: ['still waiting on you'],
              last_tick: iso(Date.now() - 11 * 60 * 1000) });
t = await titleWhen(x => /stalled/.test(x));
notes.push(`tick 11m old:          ${t}`);
ok('a tick older than two heartbeats reads as stalled', /stalled/.test(t));
ok('...and the count is still there beside it — both facts, not one',
   /^\(1\) dreamwork\/alpha-loop · stalled/.test(t));

// ── the flip rides the CLOCK, not a disk change ───────────────────────────
/* A loop that stops writing generates no event: no mtime change, no tick,
   nothing to re-render from. So this state is set just short of the
   threshold and then NOTHING is written for the rest of the check. */
const EDGE_MS = 6000;
writeStatus({ awaiting_human: [],
              last_tick: iso(Date.now() - (10 * 60 * 1000 - EDGE_MS)) });
t = await titleWhen(x => /dreaming/.test(x));
ok('just inside the threshold, it still reads as dreaming', /dreaming/.test(t));
const beforeMtime = await (await fetch(`${BASE}/mtime`)).text();
t = await titleWhen(x => /stalled/.test(x), EDGE_MS + 6000);
const afterMtime = await (await fetch(`${BASE}/mtime`)).text();
notes.push(`after the threshold:   ${t}`);
ok('it flips to stalled with nothing touching disk', /stalled/.test(t));
ok('...and nothing did touch disk (the mtime never moved)',
   beforeMtime === afterMtime);

// ── the route is the LAST field, so it truncates first ────────────────────
writeStatus({ awaiting_human: ['one'] });
await titleWhen(x => x.startsWith('(1)'));
const routed = {};
for (const [name, path] of [['questions', '/questions'],
                            ['file', '/file?p=watch.py'],
                            ['review', '/review?p=goal-hierarchies.html']]) {
  await p.goto(BASE + path, { waitUntil: 'networkidle' });
  routed[name] = await titleWhen(x => x.startsWith('(1)'));
}
notes.push('routes:\n' + Object.entries(routed)
  .map(([k, v]) => `  ${k.padEnd(10)} ${v}`).join('\n'));
ok('a route appends itself after the state', /· questions$/.test(routed.questions));
ok('...the file route names the file', /· watch\.py$/.test(routed.file));
ok('...the review route names the artifact',
   /· review goal-hierarchies\.html$/.test(routed.review));
ok('...and every route still leads with the count and the project',
   Object.values(routed).every(v => /^\(1\) dreamwork\/alpha-loop · /.test(v)));

// ── the favicon (#153) ────────────────────────────────────────────────────
/* Read PIXELS, not the href. Two icons differ as strings the moment anything
   at all changed, so a string comparison can prove "it moved" and nothing
   else — not which state it is in, not that the pip is the right colour, not
   that a stalled loop looks stalled. The icon is decoded back into a canvas
   inside the page and sampled at three known points.

   Sample geometry, from favPaint: the ring is at r=0.315·S about the centre,
   the badge at (0.79·S, 0.21·S). Three o'clock is the one ring point that is
   under neither the frame-0 trail (which sweeps backwards from the top) nor
   the badge's knockout. */
const FAV_READ = `(async () => {
  const href = document.getElementById('favicon').href;
  const img = new Image();
  /* An icon that never loads — the shell's placeholder, because nothing ever
     set it — must come back as a READING, not as a rejection. Rejecting made
     the whole guard throw on that injection, so the run said only "the guard
     threw" where it should have said "the favicon is not a PNG and nothing
     is drawn". A crash reads like silence; a zero reading names the fault. */
  const loaded = await new Promise(res => {
    img.onload = () => res(true); img.onerror = () => res(false);
    img.src = href;
  });
  if (!loaded) return { href, pip: [0, 0, 0, 0], ring: [0, 0, 0, 0], lum: 0 };
  const S = 32, c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  g.drawImage(img, 0, 0, S, S);
  const d = g.getImageData(0, 0, S, S).data;
  const at = (x, y) => { const i = (y * S + x) * 4;
                         return [d[i], d[i+1], d[i+2], d[i+3]]; };
  let lum = 0;
  for (let i = 0; i < d.length; i += 4)
    lum += (d[i] + d[i+1] + d[i+2]) / 3 * (d[i+3] / 255);
  return { href, pip: at(25, 7), ring: at(26, 16), lum: Math.round(lum) };
})()`;
const favRead = () => p.evaluate(FAV_READ);

/* PIXELS ARE READ WITH THE FRAME PINNED, which means with the loop stalled.
   The head's glow has a radius of 2.1 ring-widths and its orbit carries it
   within reach of the badge's corner on some frames, so a badge assertion
   taken at an arbitrary moment is really an assertion about WHEN it ran —
   the first version read alpha 115 at that point with no badge present and
   would have failed roughly one run in four. Stalled pins the frame at 0,
   where the head sits at the top and nothing else is near either sample
   point. The badge is orthogonal to liveness, so this costs the checks
   nothing. */
const stalled = extra => writeStatus({ awaiting_human: [],
  last_tick: iso(Date.now() - 11 * 60 * 1000), ...extra });
stalled();
await titleWhen(x => /^\(0\).*stalled/.test(x));
const favA = await favRead();
notes.push(`favicon: ${favA.href.slice(0, 24)}… ${favA.href.length}b ` +
           `ring=${favA.ring} pip=${favA.pip} lum=${favA.lum}`);
ok('the favicon is inline — a data URI, not a file beside the server',
   /^data:image\/png;base64,/.test(favA.href));
ok('...and it is drawn, not blank', favA.lum > 0);
ok('the ring carries the page\'s hue, not grey',
   favA.ring[3] > 40 && favA.ring[2] > favA.ring[0] + 20);
ok('nothing waiting: no badge', favA.pip[3] < 20);

// it rests while the loop is not ticking
await sleep(3000);
const stall2 = await favRead();
ok('a stalled loop\'s icon holds still', stall2.href === favA.href);

// ...and it advances once a second while the loop is dreaming. Polled
// rather than sampled after a fixed sleep: on a loaded machine a 1s
// interval can drift, and a one-shot comparison would then be reporting the
// machine rather than the feature.
writeStatus({ awaiting_human: [] });
await titleWhen(x => /dreaming/.test(x));
let moved = false, favDream = null;
for (let i = 0; i < 24 && !moved; i++) {
  const r = await favRead();
  if (favDream && r.href !== favDream.href) moved = true;
  favDream = favDream || r;
  if (!moved) await sleep(300);
}
notes.push(`dreaming lum=${favDream.lum} vs stalled lum=${favA.lum}`);
ok('while dreaming, the orbit advances', moved);
ok('...and a stalled icon reads faded in a single frame, not only across two',
   favA.lum < favDream.lum * 0.8);

// the badge, frame pinned again
stalled({ awaiting_human: ['you are the bottleneck'] });
await titleWhen(x => x.startsWith('(1)'));
const favPip = await favRead();
notes.push(`pip accent: ${favPip.pip}`);
ok('something waiting: a badge appears', favPip.pip[3] > 200);
ok('...in the accent, which is blue against this page\'s ramp',
   favPip.pip[2] > favPip.pip[0] + 20);

writeFileSync(QPATH, QBROKEN);
await titleWhen(x => x.startsWith('(!)'));
const favWarn = await favRead();
notes.push(`pip warn:   ${favWarn.pip}`);
ok('an unreadable channel: the badge is amber, not the accent',
   favWarn.pip[3] > 200 && favWarn.pip[0] > favWarn.pip[2] + 60);
writeFileSync(QPATH, QGOOD);

// reduced motion: the frame is pinned, everything else survives
{
  const ctx2 = await br.newContext({ reducedMotion: 'reduce',
                                     viewport: { width: 900, height: 700 } });
  const p2 = await ctx2.newPage();
  p2.on('pageerror', e => errs.push('rm: ' + e));
  writeStatus({ awaiting_human: [] });
  await p2.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1600);
  const read2 = () => p2.evaluate(FAV_READ);
  const rm1 = await read2();
  await sleep(3000);
  const rm2 = await read2();
  notes.push(`reduced motion: lum=${rm1.lum} (dreaming ${favDream.lum}, ` +
             `stalled ${favA.lum})`);
  ok('reduced motion pins the frame', rm1.href === rm2.href);
  /* ...but it must not turn a live loop into a stalled-looking one: timing
     changes, never function or legibility (the wisp's rule). The trail and
     the full brightness still say "in flight" with no motion at all. */
  ok('...without demoting a live loop to the stalled treatment',
     rm1.lum > favA.lum * 1.25);
  await ctx2.close();
}

// ── his colour for this project (#143) ────────────────────────────────────
/* The requirement has two halves and only one of them is easy. "Persist for
   that project" is a file. "Update any other windows for that project too"
   is the half a single page cannot test at all, so there is a SECOND page
   open throughout, never told anything, which has to arrive at the new
   colour on its own. */
{
  const TPATH = join(DIR, '.dreamwork', 'watch-tint');
  /* BACK TO THE DASHBOARD FIRST. The route checks above leave the page on
     /review, whose iframe covers the right margin this block samples — so
     the field measurement was reading an artifact and reporting a 6 degree
     shift for a 79 degree rotation. The third time this measurement was
     wrong and the feature was right. */
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  stalled();                       // frame 0, for the same reason as above
  await titleWhen(x => /^\(0\).*stalled/.test(x));

  /* Read it as a VALUE, never as a throw. The injection where the write
     silently does nothing left no file at all, and `readFileSync` turned the
     check written for exactly that case into a stack trace — the run said
     "the guard threw" and named nothing. Third time in this file: a guard
     assertion whose subject may not exist has to degrade to a reading. */
  const readTint = () => { try { return readFileSync(TPATH, 'utf8'); }
                           catch (e) { return ''; } };
  const post = async (tint) => (await p.evaluate(async t => {
    const r = await fetch('/tint', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tint: t }),
    });
    return r.status;
  }, tint));

  /* the accent, resolved THROUGH AN ELEMENT: `--accent` off :root comes back
     as authored (`#a5b4fc`) while every computed colour is `rgb(…)`, so
     comparing the two matches nothing and any assertion about it passes on a
     page painted entirely in it (status.mjs learned this). */
  const ACCENT = `(() => {
    const e = document.createElement('span');
    e.style.color = 'var(--accent)';
    document.body.appendChild(e);
    const c = getComputedStyle(e).color; e.remove(); return c;
  })()`;
  /* the shader's own pixels, which is the outcome rather than the uniform:
     a clip of the page is screenshotted by the driver, handed BACK into the
     page as a data URI, and decoded there — the WebGL canvas has no
     preserveDrawingBuffer, so it cannot be read any other way. */
  /* SAMPLE THE MARGIN, NOT THE COLUMN. The first version clipped a region
     overlapping the 72ch reading column and measured a 7 degree shift for a
     79 degree rotation — the field was moving exactly as asked and the
     instrument was standing in the one place full of grey text. The right
     margin is canvas and nothing else. */
  const meanHue = async (page) => {
    const shot = (await page.screenshot({
      clip: { x: 950, y: 120, width: 140, height: 700 } })).toString('base64');
    return page.evaluate(async b64 => {
      const img = new Image();
      await new Promise(r => { img.onload = r; img.src = 'data:image/png;base64,' + b64; });
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const g = c.getContext('2d');
      g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, c.width, c.height).data;
      // circular mean of hue, weighted by chroma: a near-black field has a
      // real hue but a tiny one, and averaging the angles unweighted would
      // let the darkest pixels shout
      let x = 0, y = 0;
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i] / 255, gg = d[i+1] / 255, b = d[i+2] / 255;
        const mx = Math.max(r, gg, b), mn = Math.min(r, gg, b), ch = mx - mn;
        if (ch < 0.004) continue;
        let h;
        if (mx === r) h = ((gg - b) / ch + 6) % 6;
        else if (mx === gg) h = (b - r) / ch + 2;
        else h = (r - gg) / ch + 4;
        h *= Math.PI / 3;
        x += Math.cos(h) * ch; y += Math.sin(h) * ch;
      }
      return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
    }, shot);
  };
  const hueGap = (a, b) => { const d = Math.abs(a - b) % 360;
                             return d > 180 ? 360 - d : d; };

  // a SECOND window on the same project, opened before anything changes and
  // never told anything afterwards
  const w2 = await ctx.newPage();
  w2.on('pageerror', e => errs.push('w2: ' + e));
  await w2.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(1500);

  const accentBefore = await p.evaluate(ACCENT);
  const hueIndigo = await meanHue(p);
  const favIndigo = await favRead();

  ok('POST /tint is accepted for a name in the set', await post('green') === 200);
  await sleep(400);
  ok('...and persists to .dreamwork/watch-tint',
     readTint().trim() === 'green');

  const before = readTint();
  ok('a name outside the set is refused', await post('chartreuse') === 400);
  ok('...and nothing was written', readTint() === before);

  /* Wait for the PAGE to have the tint, then for the shader to have finished
     lerping to it (0.6s time constant). A fixed sleep here measured a
     half-applied rotation, and then — once it was shorter than the 2s poll —
     an entirely unapplied one, reporting a gap of 0 for a feature that
     works. Wait for the state, never for a duration. */
  await p.evaluate(() => new Promise(res => {
    const until = Date.now() + 9000;
    (function poll() {
      if (projTint === 'green' || Date.now() > until) return res();
      setTimeout(poll, 200);
    })();
  }));
  await sleep(2200);
  const hueGreen = await meanHue(p);
  const favGreen = await favRead();
  notes.push(`tint: field hue ${hueIndigo.toFixed(0)}° -> ` +
             `${hueGreen.toFixed(0)}°  (gap ${hueGap(hueIndigo, hueGreen).toFixed(0)}°)`);
  notes.push(`tint: favicon ring ${favIndigo.ring} -> ${favGreen.ring}`);
  // indigo 229 to green 150 is a 79 degree rotation; anything under half
  // of that means the rotation is being diluted somewhere.
  ok('the ambient field actually changes hue', hueGap(hueIndigo, hueGreen) > 40);
  ok('...and the favicon travels with it — the tab strip is where the tint navigates',
     favGreen.ring[1] > favIndigo.ring[1] && favGreen.ring[2] < favIndigo.ring[2]);

  /* THE ACCENT IS THE ONE THING A TINT MAY NOT MOVE. It marks the live and
     actionable thing, and a tint that dragged it along would cost the page
     its only loud signal to make its background prettier. */
  ok('the accent is untouched by a tint',
     (await p.evaluate(ACCENT)) === accentBefore);

  // the half a single window cannot test
  const w2tint = await w2.evaluate(() => new Promise(res => {
    const until = Date.now() + 9000;
    (function poll() {
      if (projTint === 'green' || Date.now() > until) return res(projTint);
      setTimeout(poll, 250);
    })();
  }));
  notes.push(`second window arrived at: ${w2tint}`);
  ok('a window nobody told follows within a tick', w2tint === 'green');
  ok('...and its favicon followed too',
     (await w2.evaluate(FAV_READ)).ring[1] > favIndigo.ring[1]);
  await w2.close();

  // it survives a reload, which is what "persist" has to mean
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1500);
  ok('the tint survives a reload',
     (await p.evaluate(() => projTint)) === 'green');

  /* A name the page does not know falls back to the default rather than
     leaving the field colourless — the failure that loses nothing. It is
     also silent, which is exactly why lint.py checks this file. */
  writeFileSync(TPATH, 'chartreuse\n');
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(1500);
  ok('an unknown name in the file falls back to the default, not to nothing',
     (await p.evaluate(() => projTint)) === 'indigo');
  writeFileSync(TPATH, 'indigo\n');
}

ok('no page errors', errs.length === 0);
finished = true;
await br.close();
srv.kill();
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
