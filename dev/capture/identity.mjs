/* The tab's identity — the title (#153), and later the favicon.

   This is the only part of the dashboard that exists while the tab is
   backgrounded, which is most of its life, so what it has to answer is not
   "what app is this" but DOES IT NEED ME and WHICH loop is this:

       (2) alpha-loop · dreaming · questions

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

/* THREE, and the fixture holds TWO open questions. That gap is the whole
   check: with two of each, a title reading the derived count instead of the
   loop's own statement is byte-identical to a correct one, and the first
   deliberate bug injected here passed against it. A fixture that cannot tell
   two sources apart makes every assertion about the source vacuous. */
writeStatus({ awaiting_human: ['the first thing', 'the second thing',
                               'and a third'] });

const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);

/* our server, not a neighbour's — a readiness probe that accepts any answer
   eventually grades a stranger's process */
const BASE = `http://127.0.0.1:${PORT}`;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
}

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
let t = await titleWhen(x => x.startsWith('(3)'));
notes.push(`awaiting 3, 2 open q:  ${t}`);
ok('the count is FIRST — tabs truncate from the right', /^\(\d+\) /.test(t));
ok('...and it is awaiting_human\'s length, not the open-question count',
   t.startsWith('(3) '));
ok('the project is the target\'s own name', t.includes('alpha-loop'));
ok('...and the loop reads as alive', /·\s*dreaming/.test(t));
ok('the dashboard route adds nothing after the state',
   /^\(3\) alpha-loop · dreaming$/.test(t));

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
/* A target whose loop has never written one still has questions.md, and the
   fixture holds two unanswered entries. */
rmSync(SPATH, { force: true });
t = await titleWhen(x => x.startsWith('(2)'));
notes.push(`no status.json:        ${t}`);
ok('with no status.json the count falls back to open questions',
   t.startsWith('(2) '));
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
   /^\(1\) alpha-loop · stalled/.test(t));

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
   Object.values(routed).every(v => /^\(1\) alpha-loop · /.test(v)));

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

writeStatus({ awaiting_human: [] });
await titleWhen(x => /^\(0\).*dreaming/.test(x));
const favA = await favRead();
notes.push(`favicon: ${favA.href.slice(0, 24)}… ${favA.href.length}b ` +
           `ring=${favA.ring} pip=${favA.pip} lum=${favA.lum}`);
ok('the favicon is inline — a data URI, not a file beside the server',
   /^data:image\/png;base64,/.test(favA.href));
ok('...and it is drawn, not blank', favA.lum > 0);
ok('the ring carries the page\'s hue, not grey',
   favA.ring[3] > 40 && favA.ring[2] > favA.ring[0] + 20);
ok('nothing waiting: no badge', favA.pip[3] < 20);

// it advances once a second while the loop is dreaming
await sleep(1400);
const favB = await favRead();
ok('while dreaming, the orbit advances', favB.href !== favA.href);

// ...and it rests when the loop is not
writeStatus({ awaiting_human: [],
              last_tick: iso(Date.now() - 11 * 60 * 1000) });
await titleWhen(x => /stalled/.test(x));
const stall1 = await favRead();
await sleep(3000);
const stall2 = await favRead();
notes.push(`stalled: lum=${stall1.lum} vs dreaming lum=${favA.lum}`);
ok('a stalled loop\'s icon holds still', stall1.href === stall2.href);
ok('...and reads faded in a single frame, not only across two',
   stall1.lum < favA.lum * 0.8);

// the badge
writeStatus({ awaiting_human: ['you are the bottleneck'] });
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
  notes.push(`reduced motion: lum=${rm1.lum} (dreaming ${favA.lum}, ` +
             `stalled ${stall1.lum})`);
  ok('reduced motion pins the frame', rm1.href === rm2.href);
  /* ...but it must not turn a live loop into a stalled-looking one: timing
     changes, never function or legibility (the wisp's rule). The trail and
     the full brightness still say "in flight" with no motion at all. */
  ok('...without demoting a live loop to the stalled treatment',
     rm1.lum > stall1.lum * 1.25);
  await ctx2.close();
}

ok('no page errors', errs.length === 0);
finished = true;
await br.close();
srv.kill();
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
