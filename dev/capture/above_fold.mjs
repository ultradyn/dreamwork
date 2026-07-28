// above_fold.mjs — the one shared above-the-fold check for review artifacts (#429, #430).
// (#432: the fold is now MEASURED per artifact on the live /review route, not
//  declared. The three constants that moved it are measured rather than
//  modelled. See THE FOLD IS MEASURED below.)
//
//   node dev/capture/above_fold.mjs <file-or-url> [--id ask] [--no-first-child] [--target DIR]
//
// Exits 0 when every viewport passes, 1 otherwise. Prints one line per viewport
// with the numbers AND THE FOLD'S SOURCE, always — a check that only speaks
// when it fails teaches nobody what the margin was, and a fold that came from
// nowhere is exactly the failure this file was rewritten to end.
//
// WHY THIS FILE EXISTS, AND IT IS TWO SEPARATE FAILURES
// ----------------------------------------------------
// 1. Every brief that asks the human to rule on something demands the ask be
//    above the fold. `#ask` existed on TWO of twenty-two built artifacts, so on
//    the other twenty the criterion could not be evaluated at all and had been
//    silently unenforced since the day it was written. Each lane rolled its own
//    inline measurement, or didn't, and nothing noticed either way.
//
// 2. The coordinator's own ad-hoc version measured with
//    `newPage({viewportSize:…})`. Playwright's option is `viewport`; the wrong
//    key is accepted in silence, so a "1280x900" run and a "390x844" run were
//    BOTH the default 1280x720. The tell was that they agreed to the byte —
//    identical scrollHeight for a 1280px and a 390px render, impossible for a
//    responsive page. Had the page happened to pass at 720 it would have been
//    reported as two viewports verified while one was checked.
//
//    That is a new flavour of hollow check and worth naming precisely: the
//    assertion was CORRECT and was applied to the WRONG PAGE. No amount of
//    scrutiny of the assertion finds it. Only asserting the precondition does.
//    Hence VIEWPORT_APPLIED below, which runs before any measurement and is not
//    optional or skippable.
//
// WHAT "ABOVE THE FOLD" MEANS HERE, AND WHY IT IS NOT `bottom < innerHeight`
// -------------------------------------------------------------------------
// The obvious criterion — the ask's bounding box ends within the first screen —
// is unachievable for any ask carrying more than one decision. #263's ask block
// is 870px tall because it holds three of them; demanding `bottom < innerHeight`
// there would mean splitting one coherent decision into three pages to satisfy a
// measurement. So the criterion is the measurable form of the actual intent:
//
//   the ask block STARTS above the fold, and its FIRST decision is reachable
//   without scrolling  ->  ask.top < FOLD  AND  firstChild.top < FOLD
//
// Both halves matter. `ask.top < FOLD` alone passes when the block starts one
// pixel above the fold and every word of it is below. The first-child check is
// what makes the pass mean "he can read a decision", which is the thing the
// briefs were reaching for.
//
// THE FOLD IS MEASURED, NOT DECLARED (#432), AND IT WAS PROVEN, NOT SUSPECTED
// --------------------------------------------------------------------------
// He reads each artifact inside `#reviewframe` on the dashboard's `/review`
// route, so the visible fold is the FRAME's height, not `innerHeight`. Three
// separate inputs move that height and NONE of them is the viewport — a
// constant cannot be right for all three, and the history is the argument:
//
//   706  the TOP of a measured 693..708 range; a fold must take the floor.
//   691  the floor measured INSIDE A WORKTREE (project name `frame`, 5 chars).
//   670  the floor on the real target (`ud-dreamwork`, 12 chars) — correct
//        today, and still a dated constant.
//
// The three inputs, all data-dependent:
//   1. the artifact's FILENAME LENGTH — `SPAN.revname` wraps the title bar once
//      the name is long enough, the chrome grows and the frame shrinks.
//   2. the TARGET DIRECTORY'S BASENAME — that is the project name in `#hproj`
//      and it shares the title bar line. A worktree (`fold`) is not his surface
//      (`ud-dreamwork`); a fold verified in one is not verified for the other.
//   3. HOW THE NAME BREAKS — a padded `xxxx…` run of the right character count
//      has no hyphen to break on where real names do, so a derived LENGTH is
//      not a derived LAYOUT.
//
// So: per-artifact derivation. This tool serves the artifact's project root on
// an ephemeral port (its OWN port — never :35110, never 39880-39899), loads
// `/review?p=<name>`, and uses `#reviewframe`'s height as the fold for THAT
// artifact at THAT viewport. All three dependencies stop being modelled; they
// are measured, on the surface that will actually render it. Per-artifact is
// the right shape because two of the three inputs (filename length, name break)
// are per-artifact; a per-viewport-and-project fold would still guess them.
//
// THE FOLD IS NOT CACHED ACROSS INVOCATIONS. A cache keyed on `watch.py`'s mtime
// would be safe in principle, but the chrome lives in `watch.py` (which another
// lane edits) and a stale entry is exactly today's failure with a new hiding
// place. One server per invocation, reused across both viewports, is the cost:
// ~2.5s. Lanes call this per batch, not per edit. If a lane measures many
// artifacts in one go, call this once per artifact and read the printed fold.
//
// STRICT ON `#reviewframe`. The first probe fell back to `querySelector('iframe')`
// and silently measured a different box. This file waits for the real element
// and FAILS LOUDLY (FALLBACK mode, below) if it never appears. The iframe
// fallback is forbidden.
//
// MODES — printed on every viewport line, because a silent mode is a silent
// constant with a new hiding place:
//   live      the artifact is under `<root>/.dreamwork/review/`; a `watch.py`
//             serves `<root>`, `#reviewframe` answered, and its height IS the
//             fold. The target's basename is printed so a worktree run is
//             visible — pass `--target <real repo>` for the human's surface.
//   bare      the artifact is a loose file (no review dir reached, or an http
//             URL); there is no shell, so the fold IS `innerHeight`. This is
//             CORRECT for a chromeless page, not a fallback.
//   FALLBACK  the artifact is in a review dir BUT the server did not start or
//             `#reviewframe` never appeared. The pre-#432 floor constants are
//             used and the line says FALLBACK and why. Pessimistic by design —
//             this file's job is to refuse asks he cannot see, so the one
//             direction that matters is optimistic, and the floors take it.

import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { basename, dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SKILL_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const WATCH_PY = join(SKILL_ROOT, 'watch.py');
const LIVE_DASH_PORT = 35110;          // the human's dashboard — never bind it
const GUARD_LO = 39880, GUARD_HI = 39899;  // the guard/hub suites — never bind

const VIEWPORTS = [
  { label: 'desktop', width: 1280, height: 900 },
  { label: 'mobile',  width: 390,  height: 844 },
];

// Pre-#432 measured floors on the real target, used ONLY in FALLBACK mode.
// Pessimistic (the floor of the measured range): this file refuses asks he
// cannot see, so optimistic is the one direction that matters. These are NOT
// the fold for any live run; they are what a stated fallback falls back to.
const FLOOR_FALLBACK = { desktop: 738, mobile: 670 };

const sleep = ms => new Promise(r => setTimeout(r, ms));

function usage(msg) {
  console.error(msg ? `above_fold: ${msg}\n` : '');
  console.error('usage: node dev/capture/above_fold.mjs <file-or-url> [--id ask] [--no-first-child] [--target DIR]');
  process.exit(2);
}

const argv = process.argv.slice(2);
if (!argv.length) usage('no target given');
let target = null, id = 'ask', wantFirstChild = true, targetRoot = null;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--id') { id = argv[++i]; if (!id) usage('--id needs a value'); }
  else if (a === '--no-first-child') wantFirstChild = false;
  else if (a === '--target') { targetRoot = argv[++i]; if (!targetRoot) usage('--target needs a value'); }
  else if (a.startsWith('--')) usage(`unknown flag ${a}`);
  else if (target === null) target = a;
  else usage('more than one target given');
}
if (!target) usage('no target given');

// ── resolve the artifact into a mode + project root ──────────────────────
// live:   the file is under `<some dir>/.dreamwork/review/<name>` (or
//         `--target` pins the root and the name is the file's basename) — the
//         fold is derived from the live /review route on that root.
// url:    an http(s) URL — no derivation, fold = innerHeight (see header).
// bare:   a loose file with no review dir — fold = innerHeight, correctly.
function resolveMode(fileArg, targetFlag) {
  if (/^https?:\/\//.test(fileArg)) return { mode: 'url', url: fileArg };
  const abs = fileArg.startsWith('/') ? fileArg : resolve(process.cwd(), fileArg);
  const name = basename(abs);
  const roots = [];
  if (targetFlag) roots.push(resolve(targetFlag));
  else {
    let d = dirname(abs);
    for (let i = 0; i < 10 && d; i++) {
      roots.push(d);
      const p = dirname(d);
      if (p === d) break;
      d = p;
    }
  }
  for (const root of roots) {
    if (existsSync(join(root, '.dreamwork', 'review', name))) {
      return { mode: 'live', artifactPath: abs, artifactName: name, projectRoot: resolve(root) };
    }
  }
  return { mode: 'bare', artifactPath: abs, artifactName: name };
}
const aim = resolveMode(target, targetRoot);
if (targetRoot && aim.mode !== 'live') {
  console.error(`above_fold: --target ${targetRoot} given but ${aim.artifactName} `
    + `is not under ${resolve(targetRoot)}/.dreamwork/review/ — falling back to bare mode (fold=innerHeight).`);
}

// ── ephemeral port outside the guard/hub suites and the live dashboard ───
function freePort() {
  return new Promise(res => {
    const s = createServer();
    s.listen(0, '127.0.0.1', () => {
      const p = s.address().port;
      s.close(() => res(p));
    });
  });
}
async function pickPort() {
  let p;
  do { p = await freePort(); }
  while ((p >= GUARD_LO && p <= GUARD_HI) || p === LIVE_DASH_PORT);
  return p;
}

// ── serve the project root and wait until /data.json answers for it ───────
// Returns { base, port, projectRoot, basename, stop } or null. `watch.py` is
// THIS worktree's (the lane's branch); the target is the artifact's project.
async function startServer(projectRoot) {
  if (!existsSync(WATCH_PY)) return { ok: false, reason: `watch.py not found at ${WATCH_PY}` };
  const root = resolve(projectRoot);
  const port = await pickPort();
  const srv = spawn('python3', [WATCH_PY, '--target', root, '--port', String(port)],
    { stdio: 'ignore' });
  const base = `http://127.0.0.1:${port}`;
  const stop = () => { try { srv.kill(); } catch (e) {} };
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (srv.exitCode !== null) return { ok: false, reason: `watch.py exited (code ${srv.exitCode})`, stop };
    try {
      const r = await fetch(`${base}/data.json`);
      if (r.ok) {
        const d = await r.json();
        if (d.target === root) {
          return { ok: true, base, port, projectRoot: root, basename: basename(root), stop };
        }
      }
    } catch (e) {}
    await sleep(250);
  }
  stop();
  return { ok: false, reason: 'watch.py never answered /data.json on its port', stop };
}

// ── measure #reviewframe on /review?p=<name> at a viewport ───────────────
// STRICT on the real element; the iframe fallback is forbidden (see header).
// VIEWPORT_APPLIED is checked here too: a wrong-keyed viewport on the /review
// page would measure the frame at the 1280x720 default and report a desktop
// fold for every viewport — both axes, height reveals the wrong-key bug.
async function measureFold(browser, base, name, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  try {
    const page = await ctx.newPage();
    try {
      await page.goto(`${base}/review?p=${encodeURIComponent(name)}`,
                      { waitUntil: 'load', timeout: 15000 });
    } catch (e) {
      return { ok: false, reason: `/review goto failed: ${e.message}` };
    }
    try {
      await page.waitForSelector('#reviewframe', { timeout: 8000 });
    } catch (e) {
      return { ok: false, reason: '#reviewframe never appeared on /review' };
    }
    await sleep(700);  // settle chrome + the frame's measured --rvh layout
    const r = await page.evaluate(() => {
      const f = document.getElementById('reviewframe');
      if (!f) return null;
      const b = f.getBoundingClientRect();
      return { iw: innerWidth, ih: innerHeight, top: Math.round(b.top), h: Math.round(b.height) };
    });
    if (!r) return { ok: false, reason: '#reviewframe vanished after wait' };
    if (r.iw !== vp.width || r.ih !== vp.height) {
      return { ok: false,
        reason: `viewport not applied on /review (got ${r.iw}x${r.ih}, asked ${vp.width}x${vp.height})` };
    }
    return { ok: true, fold: r.h, frameTop: r.top, frameHeight: r.h };
  } finally {
    await ctx.close();
  }
}

// ── the main loop ────────────────────────────────────────────────────────
const rows = [];
let failures = 0;
const browser = await chromium.launch();
let server = null;           // { base, basename, stop } when live
let serverNote = '';
// Die cleanly if a parent guard SIGTERMs this process (e.g. devoverlay's
// spawnSync timeout): stop the server so the watch.py child does not leak and
// close the browser so chromium does not either.
const die = () => { try { if (server) server.stop(); } catch (e) {} try { browser.close(); } catch (e) {} process.exit(130); };
process.on('SIGTERM', die);
process.on('SIGINT', die);
if (aim.mode === 'live') {
  const s = await startServer(aim.projectRoot);
  if (s.ok) {
    server = s;
    // The basename is the safety print: a worktree run reads `fold` here, the
    // human's surface reads `ud-dreamwork`, and a fold verified in one is not
    // verified for the other.
    serverNote = `live: serving ${aim.projectRoot} (project=${s.basename}) on :${s.port} — `
      + (s.basename === 'ud-dreamwork'
         ? 'this is the human surface'
         : `NOT the human surface (project is ${s.basename}, not ud-dreamwork); re-run with --target <real repo> for the surface fold`);
  } else {
    serverNote = `FALLBACK: live derivation unavailable (${s.reason}); using pre-#432 floor constants`;
    if (s.stop) s.stop();
  }
}

try {
  for (const vp of VIEWPORTS) {
    // ── determine this viewport's fold + its source ──────────────────────
    let fold = null, foldSource = '';
    if (aim.mode === 'live' && server) {
      const m = await measureFold(browser, server.base, aim.artifactName, vp);
      if (m.ok) {
        fold = m.fold;
        foldSource = `live:fold=${fold} (#reviewframe h=${m.frameHeight} top=${m.frameTop} on /review at ${vp.width}x${vp.height})`;
      } else {
        fold = FLOOR_FALLBACK[vp.label];
        foldSource = `FALLBACK:fold=${fold} (${m.reason}; pre-#432 floor)`;
      }
    } else if (aim.mode === 'live' && !server) {
      fold = FLOOR_FALLBACK[vp.label];
      foldSource = `FALLBACK:fold=${fold} (server unavailable; pre-#432 floor)`;
    } else {
      // bare / url: no shell, so the fold IS innerHeight. For bare this is
      // correct; for url it is the documented assumption (pass a file path or
      // --target for live derivation). The exact innerHeight is read off the
      // artifact page below and substituted in, so this is a placeholder tag.
      foldSource = aim.mode === 'url'
        ? `url:fold=innerHeight (no live derivation for http URLs; pass a path or --target)`
        : `bare:fold=innerHeight (no shell; the artifact IS the page)`;
    }

    // ── load the artifact page and measure ask/first/scroll ──────────────
    // live: the raw artifact off the SAME server (byte-identical to file:// of
    // the path, so ask.top is unchanged from the pre-#432 tool). bare: file://.
    // url: the URL itself. The fold is derived on /review; the ask is measured
    // here on the artifact page, exactly as before — #432 changes the fold, not
    // the ask. (The ask sits inside #reviewframe on /review; measuring it
    // top-level at the viewport width matches the iframe's width on mobile and
    // is the historical desktop measurement. Scoping the fold kept the change
    // honest; re-scoping the ask is its own task.)
    const artifactUrl = aim.mode === 'live' && server
      ? `${server.base}/reviewraw?p=${encodeURIComponent(aim.artifactName)}`
      : aim.mode === 'url' ? aim.url
      : `file://${aim.artifactPath || target}`;

    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    await page.goto(artifactUrl, { waitUntil: 'load' });
    await sleep(250);
    const m = await page.evaluate((elId) => {
      const box = (e) => {
        const r = e.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height) };
      };
      const el = document.getElementById(elId);
      let first = null;
      if (el) {
        for (const c of el.children) {
          const r = c.getBoundingClientRect();
          if (r.height >= 8) { first = { tag: c.tagName.toLowerCase(), ...box(c) }; break; }
        }
      }
      return {
        innerWidth, innerHeight,
        scrollHeight: document.documentElement.scrollHeight,
        found: !!el,
        ask: el ? box(el) : null,
        first,
      };
    }, id);
    await page.close();

    // ---- PRECONDITION 1: VIEWPORT_APPLIED. Before anything is measured. ----
    // A wrong-keyed viewport option is accepted silently, so every figure below
    // would be the default 1280x720 wearing this viewport's label.
    if (m.innerWidth !== vp.width) {
      console.error(`FATAL ${vp.label}: asked for width ${vp.width}, page reports ${m.innerWidth} — `
        + `the viewport was NOT applied and every measurement here would be a different page. `
        + `Check the newPage option is 'viewport', not 'viewportSize'.`);
      if (server) server.stop();
      process.exit(3);
    }
    // BOTH assertions are required and the height one is not redundant — this
    // was proved, not reasoned. Chromium's default viewport is 1280x720, and the
    // desktop case here asks for 1280x900. So when the option key is wrong the
    // WIDTH MATCHES ANYWAY (1280 === 1280) and only the height reveals it. A
    // width-only precondition would have passed the exact bug this file exists
    // for, at the exact viewport most artifacts are judged at. Do not simplify
    // these into one check.
    if (Math.abs(m.innerHeight - vp.height) > 40) {
      console.error(`FATAL ${vp.label}: asked for height ${vp.height}, page reports ${m.innerHeight}.`);
      if (server) server.stop();
      process.exit(3);
    }

    // bare / url: now that innerHeight is known, it IS the fold.
    if (fold === null) fold = m.innerHeight;

    // ---- PRECONDITION 2: the page must actually scroll. ----
    // An above-the-fold assertion passes trivially on a page that fits entirely,
    // so a short page would report a pass it never earned.
    const scrolls = m.scrollHeight > m.innerHeight;

    const parts = [`[${foldSource}]`];
    let ok = true;
    if (!m.found) {
      ok = false;
      parts.push(`#${id} MISSING`);
    } else {
      const askOk = m.ask.top < fold;
      parts.push(`#${id}.top=${m.ask.top} h=${m.ask.height} ${askOk ? 'above' : 'BELOW'} fold(${fold})`);
      if (!askOk) ok = false;
      if (wantFirstChild) {
        if (!m.first) {
          ok = false;
          parts.push('first-decision NONE (no rendering child)');
        } else {
          const fOk = m.first.top < fold;
          parts.push(`first(${m.first.tag}).top=${m.first.top} ${fOk ? 'above' : 'BELOW'}`);
          if (!fOk) ok = false;
        }
      }
    }
    if (!scrolls) {
      ok = false;
      parts.push(`VACUOUS (scrollHeight ${m.scrollHeight} <= innerHeight ${m.innerHeight}: `
        + 'the page fits, so above-the-fold is not a claim about anything)');
    }

    if (!ok) failures++;
    rows.push(`${ok ? 'ok  ' : 'FAIL'} ${vp.label.padEnd(8)} ${vp.width}x${vp.height} `
      + `innerHeight=${m.innerHeight} scrollHeight=${m.scrollHeight} | ${parts.join(' | ')}`);
  }
} finally {
  if (server) server.stop();
  await browser.close();
}

const headUrl = aim.mode === 'url' ? aim.url
              : aim.mode === 'live' ? `${aim.projectRoot}/.dreamwork/review/${aim.artifactName}`
              : aim.artifactPath;
console.log(`above_fold: ${headUrl}  (#${id}${wantFirstChild ? ' + first decision' : ''})`);
if (serverNote) console.log(`  ${serverNote}`);
for (const r of rows) console.log('  ' + r);
if (failures) {
  console.log(`\nABOVE-FOLD CHECK FAILED — ${failures} of ${VIEWPORTS.length} viewport(s).`);
  console.log('The ask must START above the fold and its first decision must be readable there.');
  process.exit(1);
}
console.log(`\nabove-fold check passed — ${VIEWPORTS.length} viewport(s).`);
