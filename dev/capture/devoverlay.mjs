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
import { mkdirSync, cpSync, rmSync } from 'node:fs';
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

const review = ((await (await fetch(`${BASE}/data.json`)).json()).reviews || [])[0];
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
