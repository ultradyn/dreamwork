/* devoverlay — #434 + #435: the /review frame fills the phone window, and
   the --dev overlay does not paint on the project wordmark.

   #434  On a 390x844 phone the artifact iframe sat at a fixed 60vh (506px)
         under the chrome, leaving ~200px of EMPTY viewport beneath it
         (scrollHeight === innerHeight — not off-screen content). The narrow
         layout now reuses fitReview's measured --rvh for #reviewdoc. Dead
         space under the frame must be < 24px at 390x844; desktop must not
         regress past its prior ~40px.

   #435  At 1280x900 the overlay's third readout line painted across the
         trailing-edge wordmark. The fix is the wordmark YIELDING
         (body.dev .hproj margin-right), not removing the counter. Mobile
         must stay clear too. A probe that only greps for "fps" matches a
         <script> whose rect is 0x0 — every pair here requires the element
         to actually render (width>2 && height>2, not SCRIPT/STYLE).

   PRODUCTION LINES (red-first named):
     #434  the narrow-media rule `#reviewdoc { height:var(--rvh, …) }` —
           restoring `height:60vh` is the injection that fails the dead-
           space check.
     #435  `doc.body.classList.add('dev')` when the overlay mounts, and the
           CSS rule `body.dev .hproj { margin-right:… }` — removing either
           is the injection that fails the overlap check.

   Own ephemeral port + --dev (the overlay only mounts under --dev). Does
   NOT bind 39880–39899. usage: node devoverlay.mjs <outdir> [port ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, cpSync, rmSync, writeFileSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/review?p=… at 390x844, 1280x900 and 768x900 for frame dead space; '
        + '/ and /review with --dev at 1280x900 and 390x844 for overlay/wordmark '
        + 'overlap (rendering precondition on every pair)',
  traceWindow: 'settled geometry after ~0.9–1.2s; no motion traced — both '
             + 'claims are layout end-states (measured pane / settled chrome), '
             + 'not gestures',
});

const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => {
    const p = s.address().port;
    s.close(() => res(p));
  });
});
const PORT = await freePort();
// refuse the guard-suite and hub ranges even if freePort handed one back —
// a collision with the coordinator's suite is a real failure mode here.
if (PORT >= 39880 && PORT <= 39899) {
  console.log(`FAIL freePort returned ${PORT} inside the reserved guard range`);
  process.exit(1);
}

const DIR = join(OUT, 'devoverlay-target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });

const BASE = `http://127.0.0.1:${PORT}`;
const srv = await serveVerified(DIR, PORT, { args: ['--dev'] });   // #428/#461: poll+identity, no fixed sleep
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  notes.push(`target ${d.target}`);
  notes.push(`port ${PORT} (outside 39880-39899)`);
}

const allReviews = ((await (await fetch(`${BASE}/data.json`)).json()).reviews || []);
const review = allReviews[0];
if (!review) {
  console.log('FAIL fixture has no review artifact');
  process.exit(1);
}
const REVIEW = `/review?p=${encodeURIComponent(review.name)}`;
notes.push(`review ${review.name}`);
const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});

/* ── shared probes ─────────────────────────────────────────────────────── */

async function withPage(w, h, path, fn) {
  const ctx = await br.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
  await waitFor(page, '#hproj');   // #428 render readiness (header chrome on every route)
  const applied = await page.evaluate(({ w, h }) => ({
    iw: window.innerWidth, ih: window.innerHeight,
    ok: window.innerWidth === w && window.innerHeight === h,
  }), { w, h });
  // VIEWPORT_APPLIED — both axes. Chromium default is 1280x720; a wrong
  // newPage({viewportSize:…}) key is swallowed and only the height reveals it.
  ok(`viewport applied ${w}x${h} on ${path}`, applied.ok);
  if (!applied.ok) {
    notes.push(`viewport miss on ${path}: got ${applied.iw}x${applied.ih}`);
    await ctx.close();
    return null;
  }
  const out = await fn(page);
  if (errs.length) notes.push(`pageerrors ${path}: ${errs.join(' | ')}`);
  await ctx.close();
  return out;
}

function deadSpaceProbe() {
  return (() => {
    const frame = document.getElementById('reviewframe');
    if (!frame) return { missing: true };
    const r = frame.getBoundingClientRect();
    const dead = Math.max(0, window.innerHeight - r.bottom);
    const wrap = document.getElementById('reviewwrap');
    return {
      missing: false,
      top: +r.top.toFixed(1),
      bottom: +r.bottom.toFixed(1),
      h: +r.height.toFixed(1),
      dead: +dead.toFixed(1),
      scrollH: document.documentElement.scrollHeight,
      innerH: window.innerHeight,
      rvh: wrap ? getComputedStyle(wrap).getPropertyValue('--rvh').trim() : '',
    };
  });
}

/* Rendering precondition: a rect that is not a real painted box cannot
   report "no overlap" over a collision visible in a screenshot. The first
   attempt at this check matched a <script> containing the letters "fps"
   whose rect is 0x0. */
function overlapProbe() {
  return (() => {
    const dev = document.getElementById('devbox');
    const mark = document.getElementById('hproj');
    if (!dev) return { noDev: true };
    if (!mark || mark.hidden || !mark.textContent) return { noMark: true };
    const isRendered = el => {
      if (!el || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return false;
      const r = el.getBoundingClientRect();
      return r.width > 2 && r.height > 2;
    };
    if (!isRendered(mark)) return { markNotRendered: true };
    const markR = mark.getBoundingClientRect();
    const kids = [...dev.children].filter(isRendered);
    if (!kids.length) return { noRenderedKids: true };
    const pairs = [];
    for (const el of kids) {
      const r = el.getBoundingClientRect();
      const ox = Math.max(0, Math.min(r.right, markR.right) - Math.max(r.left, markR.left));
      const oy = Math.max(0, Math.min(r.bottom, markR.bottom) - Math.max(r.top, markR.top));
      if (ox > 0 && oy > 0) {
        pairs.push({
          tag: el.tagName,
          text: (el.textContent || '').slice(0, 48),
          ox: +ox.toFixed(1),
          oy: +oy.toFixed(1),
        });
      }
    }
    return {
      overlaps: pairs.length,
      pairs,
      mark: {
        text: mark.textContent,
        l: +markR.left.toFixed(1), r: +markR.right.toFixed(1),
        t: +markR.top.toFixed(1), b: +markR.bottom.toFixed(1),
      },
      bodyDev: document.body.classList.contains('dev'),
      kids: kids.length,
    };
  });
}

/* ── #434 frame dead space ─────────────────────────────────────────────── */

const VIEWPORTS = [
  { label: 'mobile',  w: 390,  h: 844, maxDead: 24 },
  { label: 'desktop', w: 1280, h: 900, maxDead: 40 }, // must not regress past prior ~40
  { label: 'mid',     w: 768,  h: 900, maxDead: 24 }, // stacked layout (<900)
];

for (const vp of VIEWPORTS) {
  const m = await withPage(vp.w, vp.h, REVIEW, page => page.evaluate(deadSpaceProbe()));
  if (!m) continue;
  notes.push(
    `#434 ${vp.label} ${vp.w}x${vp.h}: frame top=${m.top} h=${m.h} bottom=${m.bottom} `
    + `dead=${m.dead} rvh=${m.rvh} scrollH=${m.scrollH}/${m.innerH}`,
  );
  ok(`#434 ${vp.label}: reviewframe present`, !m.missing);
  if (m.missing) continue;
  ok(
    `#434 ${vp.label}: dead space under frame < ${vp.maxDead}px (got ${m.dead})`,
    m.dead < vp.maxDead,
  );
  // anti-vacuity: the frame must actually be tall — a 1px frame with 0 dead
  // space would pass the threshold and mean nothing.
  const minH = vp.label === 'desktop' ? 500 : 400;
  ok(
    `#434 ${vp.label}: frame is at least ${minH}px tall (got ${m.h})`,
    m.h >= minH,
  );
}

/* ── #432 the fold is derived, not declared; this guard holds the derivation honest ──
   `above_fold.mjs` decides whether an ask he must rule on is visible, and #432
   replaced the hard-coded fold it compared against with a per-artifact
   MEASUREMENT on the live /review route (`#reviewframe`'s height). So the old
   shape of this block — parse `fold: <num>` out of above_fold.mjs's source and
   assert it <= the measured real minimum — no longer earns its runtime: there
   is no constant to parse, and that was the whole point of #432. Two parts of
   the old check do, and both are kept:

   1. ANTI-VACUITY (the part the brief named as worth keeping). Per-artifact
      derivation only matters if the corpus still exercises the wrap that moves
      the fold. If the shortest- and longest-named artifacts render the SAME
      frame height, the wrap never happened, the per-artifact fold is a
      per-viewport fold in disguise, and a `derived === measured` pass would
      mean nothing. The spread between the two is derived from the subjects
      themselves, so a corpus change that flattened the wrap goes red rather
      than hollow.

   2. THE DERIVATION EQUALS AN INDEPENDENT MEASUREMENT (the repoint). This
      block measures `#reviewframe` itself, then runs `above_fold.mjs` on the
      same shortest artifact and compares the tool's printed fold to this
      block's own number. The two are independent: this is the guard's own
      `getBoundingClientRect`, not the tool's code path. If the tool measured
      the wrong box — the first probe fell back to `querySelector('iframe')`
      and did, which is the reason #432 forbids that fallback — this is where
      it shows, because the tool's whole path (arg parse, server start, live
      load, `#reviewframe` wait, the height assignment) has to land on the same
      number the DOM reports to this block.

   IT MEASURES THE REAL TARGET, NOT THE FIXTURE, and that is not incidental.
   Two fixture-based versions of the old check were wrong in the same
   direction, both demanding a fold no real artifact needs: a 60-character
   invented name and a padded `xxxx…` stem both wrapped further than any real
   name because they have no hyphen to break on. A derived LENGTH is not a
   derived LAYOUT, and a fixture is not the surface; the fold is a property of
   the real corpus in the real chrome, so this block serves the actual repo
   read-only on its own port. (In a worktree, the repo IS the worktree and the
   project name is the worktree's basename — `above_fold.mjs` prints it; the
   spread still exercises the wrap because it compares two names within the
   same corpus. The human-surface number comes from running both against the
   real checkout, not from this guard.)

   Injection that fails it (red-first, #432 criterion 5): in above_fold.mjs's
   measureFold, change the height assignment `fold: r.h` to `fold: r.ih`
   (report innerHeight instead of the frame). The tool then prints
   `[live:fold=844]` for mobile where the real frame is ~708, and this block's
   `derived === independent (±2)` goes red. The production line is the
   `return { ok: true, fold: r.h, ... }` in above_fold.mjs's measureFold. */
{
  const REAL = process.cwd();
  let rport = await freePort();
  while ((rport >= 39880 && rport <= 39899) || rport === 35110) rport = await freePort();
  const rbase = `http://127.0.0.1:${rport}`;
  let rsrv;
  try {
    let names = [];
    try {
      rsrv = await serveVerified(REAL, rport);   // #428/#461: poll+identity, no fixed sleep
      const rd = await (await fetch(`${rbase}/data.json`)).json();
      names = (rd.reviews || []).map(r => r.name);
    } catch (e) { notes.push(`fold: real-target server unusable: ${e}`); }
    ok('fold: real target served its review corpus', names.length >= 2);
    if (names.length >= 2) {
      const byLen = [...names].sort((a, b) => a.length - b.length);
      const subjects = [byLen[0], byLen[byLen.length - 1]];
      const heights = [];
      for (const n of subjects) {
        const ctx = await br.newContext({ viewport: { width: 390, height: 844 } });
        const page = await ctx.newPage();
        await page.goto(`${rbase}/review?p=${encodeURIComponent(n)}`,
                        { waitUntil: 'networkidle' });
        // STRICT: wait for the real element. A `|| querySelector('iframe')`
        // fallback would silently measure a different box.
        await page.waitForSelector('#reviewframe', { timeout: 8000 }).catch(() => {});
        await sleep(1000);
        const m = await page.evaluate(() => {
          const f = document.getElementById('reviewframe');
          if (!f) return null;
          const r = f.getBoundingClientRect();
          return { iw: innerWidth, ih: innerHeight,
                   top: Math.round(r.top), h: Math.round(r.height) };
        });
        await ctx.close();
        if (!m) { notes.push(`fold: no #reviewframe for ${n}`); continue; }
        // VIEWPORT_APPLIED, both axes — same reason as withPage.
        if (m.iw !== 390 || m.ih !== 844) {
          notes.push(`fold: viewport miss on ${n}: ${m.iw}x${m.ih}`);
          continue;
        }
        heights.push({ name: n, h: m.h, top: m.top });
        notes.push(`fold: ${n} (${n.length} chars) -> frame top=${m.top} h=${m.h}`);
      }
      ok('fold: measured a frame height for both extremes', heights.length === 2);
      if (heights.length === 2) {
        // ANTI-VACUITY: if the shortest and longest name render the SAME height
        // the wrap never happened, the "minimum" is not a minimum, and a
        // `fold <= min` pass would mean nothing. Derived from the two subjects
        // rather than compared to a literal, so a corpus change cannot quietly
        // hollow it out — it goes red instead.
        const spread = Math.abs(heights[0].h - heights[1].h);
        ok(`fold: shortest and longest names give DIFFERENT frame heights `
           + `(spread ${spread}px: ${heights.map(x => `${x.h}`).join(' vs ')})`,
           spread >= 8);
        // ── THE DERIVATION EQUALS AN INDEPENDENT MEASUREMENT (#432 repoint) ──
        // Run above_fold.mjs on the SHORTEST subject and compare its printed
        // mobile fold to THIS block's own #reviewframe height for the same
        // artifact. Independent measurements: this is the guard's own
        // getBoundingClientRect, not the tool's code path, so a tool that reads
        // the wrong element (the probe that fell back to querySelector('iframe')
        // and did) is caught here. exit 1 means #ask was MISSING on a
        // pre-#436 artifact — the fold is still printed and is what we compare;
        // anything else is a crash.
        const shortest = subjects[0];
        const shortestH = heights.find(x => x.name === shortest);
        if (!shortestH) {
          ok('fold: shortest artifact has an independent height to compare against',
             false);
        } else {
          const out = spawnSync('node',
            ['dev/capture/above_fold.mjs', '--target', REAL,
             join(REAL, '.dreamwork', 'review', shortest)],
            { encoding: 'utf8', timeout: 45000 });
          ok(`fold: above_fold.mjs ran on ${shortest} and exited with a verdict `
             + `(0 pass / 1 #ask-missing, not a crash; got ${out.status})`,
             out.status === 0 || out.status === 1);
          // The mobile viewport line carries `[live:fold=N ...]`; capture the
          // digits right after `live:fold=` (the `]` sits later in the tag, so
          // do not anchor on it). Match only a LIVE fold, because a FALLBACK
          // fold (server/element unavailable) is itself the failure this guard
          // exists to surface.
          const lived = out.stdout.match(/mobile[^\n]*\[live:fold=(\d+)/);
          ok(`fold: above_fold.mjs reported a LIVE mobile fold for ${shortest}`,
             !!lived);
          if (lived) {
            const derived = Number(lived[1]);
            notes.push(`fold: above_fold derived mobile=${derived} for ${shortest}; `
              + `this block's independent #reviewframe height=${shortestH.h}`);
            ok(`fold: above_fold derived fold (${derived}) === independent `
               + `#reviewframe height (${shortestH.h}, ±2) for ${shortest}`,
               Math.abs(derived - shortestH.h) <= 2);
          } else if (out.stdout) {
            notes.push(`fold: above_fold mobile line: `
              + (out.stdout.split('\n').find(l => l.includes('mobile')) || '').trim());
          }
        }
      }
    }
  } finally {
    try { rsrv && rsrv.kill(); } catch (e) {}
  }
}

/* ── #435 overlay / wordmark overlap ───────────────────────────────────── */

for (const [label, w, h, path] of [
  ['desktop-dash', 1280, 900, '/'],
  ['desktop-review', 1280, 900, REVIEW],
  ['mobile-dash', 390, 844, '/'],
  ['mobile-review', 390, 844, REVIEW],
]) {
  const m = await withPage(w, h, path, async page => {
    // wait for the overlay's first text paint (100ms window + a beat)
    await page.waitForFunction(() => {
      const box = document.getElementById('devbox');
      if (!box) return false;
      const t = box.textContent || '';
      return /\dfps|\d\s*fps/i.test(t) || /\dms/.test(t);
    }, null, { timeout: 4000 }).catch(() => null);
    await sleep(200);
    return page.evaluate(overlapProbe());
  });
  if (!m) continue;
  notes.push(`#435 ${label}: ${JSON.stringify(m)}`);
  ok(`#435 ${label}: #devbox mounted (--dev)`, !m.noDev);
  if (m.noDev) continue;
  ok(`#435 ${label}: body.dev set (yield signal)`, !!m.bodyDev);
  ok(`#435 ${label}: wordmark present and rendered`,
     !m.noMark && !m.markNotRendered);
  ok(`#435 ${label}: overlay has rendered children (precondition)`,
     !m.noRenderedKids && (m.kids || 0) > 0);
  if (m.noMark || m.markNotRendered || m.noRenderedKids) continue;
  ok(
    `#435 ${label}: zero overlapping pairs (got ${m.overlaps})`,
    m.overlaps === 0,
  );
}

await br.close();
try { srv.kill(); } catch (e) {}
finish();
