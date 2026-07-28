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
import { mkdirSync, cpSync, rmSync, readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
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

const srv = spawn(
  'python3',
  ['watch.py', '--target', DIR, '--port', String(PORT), '--dev'],
  { stdio: 'ignore' },
);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);

const BASE = `http://127.0.0.1:${PORT}`;
{
  let d;
  try {
    d = await (await fetch(`${BASE}/data.json`)).json();
  } catch (e) {
    notes.push(`server not ready: ${e}`);
    console.log('FAIL server never answered /data.json');
    process.exit(1);
  }
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
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
  await sleep(1100);
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

/* ── the mobile fold constant is the FLOOR of the frame height, not the top ──
   `above_fold.mjs` decides whether an ask he must rule on is visible, using a
   hard-coded effective fold per viewport. That constant is only as good as the
   SHORTEST frame the shell produces, and at 390px the shell produces more than
   one height: `SPAN.revname` wraps the title bar once the artifact's name is long
   enough, the chrome grows and the frame shrinks. The constant had been set to
   the TALL case (706 against a real floor of 693), which calls clipped content
   visible — optimistic, and that is the one direction that matters for a check
   whose whole job is refusing asks he cannot see.

   IT MEASURES THE REAL TARGET, NOT THE FIXTURE, and that is not incidental.
   Two fixture-based versions of this check were wrong in the same direction,
   both demanding a fold no real artifact needs:

     - a 60-character invented name wrapped to THREE lines -> 651
     - a padded stem of the right character count also wrapped to three, because
       `xxxx…` has no hyphen to break on where real names do -> 672
     - and the fixture's own target directory is `devoverlay-target`, which is
       LONGER than the real project name and shares the title bar with the
       artifact name, so even the real longest name measured 672 there

   A derived length is not a derived layout, and a fixture is not the surface.
   The fold is a property of the real corpus rendered in the real chrome, so this
   block serves the actual repo read-only on its own port and measures the real
   shortest- and longest-named artifacts. It follows that filing an artifact with
   a longer name than any today can turn this red — which is the correct
   behaviour: it means the constant needs revisiting, and `#432` wants the whole
   constant replaced by this derivation.

   Injection that fails it: restore `fold: 706` in above_fold.mjs. */
{
  const REAL = process.cwd();
  let rport = await freePort();
  while (rport >= 39880 && rport <= 39899) rport = await freePort();
  const rsrv = spawn('python3',
    ['watch.py', '--target', REAL, '--port', String(rport)], { stdio: 'ignore' });
  try {
    await sleep(2500);
    const rbase = `http://127.0.0.1:${rport}`;
    let names = [];
    try {
      const rd = await (await fetch(`${rbase}/data.json`)).json();
      if (rd.target !== REAL) throw new Error(`serving ${rd.target}, not ${REAL}`);
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
        const src = readFileSync('dev/capture/above_fold.mjs', 'utf8');
        const mm = src.match(/label:\s*'mobile'[^}]*fold:\s*(\d+)/);
        ok('fold: mobile fold constant is parseable from above_fold.mjs', !!mm);
        if (mm) {
          const declared = Number(mm[1]);
          const minH = Math.min(...heights.map(x => x.h));
          notes.push(`fold: declared ${declared}, measured real min ${minH}`);
          ok(`fold: above_fold.mjs mobile fold ${declared} <= shortest real frame `
             + `${minH} (a long artifact name wraps the title bar and shortens it)`,
             declared <= minH);
        }
      }
    }
  } finally {
    try { rsrv.kill(); } catch (e) {}
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
