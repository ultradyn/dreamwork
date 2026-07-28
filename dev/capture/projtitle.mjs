/* #172 — project identity in the visible title bar, edge-pinned.

   The tab title already carries dreamwork/<project> (#153 / identity.mjs).
   This guard is about the VISIBLE chrome: `#hproj` must show the target's
   basename on every route, and its box must not move when the route word
   changes length — "anchor what is invariant to an edge, not to a
   variable-width neighbour".

   The load-bearing check is the three-route rectangle equality, not mere
   presence. A layout that sits the name beside the route and slides as
   `questions` becomes `review <long>` fails that even when the name is
   visible on one screenshot.

   Own ephemeral port and own target (basename deliberately NOT this repo's),
   for identity.mjs's reason: a hard-coded `ud-dreamwork` would pass against
   any target. usage: node projtitle.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, cpSync, rmSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/, /questions, and a long /review?p=… on one live page; tab title; '
        + 'desktop + phone screenshots of the identity bar',
  traceWindow: 'settled reads after navigation (~1.2s each); no per-frame motion '
             + 'trace — the claim is geometry invariance, not travel',
});

const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

/* Directory name IS the project name, and it is deliberately not this repo. */
const DIR = join(OUT, 'gamma-loop');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
/* A long review param needs a real artifact under the fixture so /review
   paints rather than erroring into a different chrome height. */
/* Long param: real fixture artifact under .dreamwork/review/. The name is
   short; the ROUTE WORD becomes `review fixture-review.html` which is still
   longer than `questions` and empty dashboard — enough to shove a neighbour-
   anchored identity. */
const longParam = '.dreamwork/review/fixture-review.html';

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
  notes.push(`target ${d.target}`);
  notes.push(`open_questions ${d.open_questions}`);
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));

async function go(path) {
  await p.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
  await sleep(1200);
}

const read = () => p.evaluate(() => {
  const el = document.getElementById('hproj');
  const title = document.getElementById('htitle');
  const bar = document.querySelector('.htitlebar');
  if (!el) return { missing: true };
  const r = el.getBoundingClientRect();
  const br = bar ? bar.getBoundingClientRect() : null;
  const cs = getComputedStyle(el);
  /* The heading is flex:1, so its BOX always fills to the identity. The
     route WORD's ink width is what actually varies — measure that, not
     the flex box, or "title widths differ" is vacuous. */
  let inkW = 0, inkRight = 0;
  if (title) {
    const range = document.createRange();
    range.selectNodeContents(title);
    const rects = range.getClientRects();
    for (const rr of rects) {
      inkW += rr.width;
      inkRight = Math.max(inkRight, rr.right);
    }
  }
  return {
    missing: false,
    hidden: !!el.hidden || cs.display === 'none' || cs.visibility === 'hidden',
    text: el.textContent,
    titleAttr: el.getAttribute('title') || '',
    tab: document.title,
    route: title ? title.textContent : '',
    left: r.left, top: r.top, width: r.width, height: r.height,
    right: r.right, bottom: r.bottom,
    /* distance from identity's right edge to the bar's right edge — the pin.
       Zero (within a pixel) means edge-anchored, not neighbour-anchored. */
    trailGap: br ? br.right - r.right : null,
    inkW, inkRight,
    barRight: br ? br.right : 0,
  };
});

const sameBox = (a, b, tol = 0.5) =>
  Math.abs(a.left - b.left) <= tol &&
  Math.abs(a.top - b.top) <= tol &&
  Math.abs(a.width - b.width) <= tol &&
  Math.abs(a.height - b.height) <= tol;

// ── presence + content on the dashboard ──────────────────────────────────
await go('/');
let a = await read();
notes.push(`/: hproj=${JSON.stringify(a)}`);
ok('#hproj is in the DOM at all (else every check here is vacuous)',
   !a.missing);
ok('#hproj is visible (not hidden)', a && !a.missing && !a.hidden && a.width > 0);
ok('the visible name is the target basename', a && a.text === 'gamma-loop');
ok('the full path rides title= (two checkouts can share a basename)',
   a && a.titleAttr === DIR);
ok('the tab title still carries dreamwork/<project>',
   a && a.tab.includes('dreamwork/gamma-loop'));
ok('...and still front-loads the count', a && /^\(\d+\) /.test(a.tab));
await p.screenshot({ path: join(OUT, 'projtitle-desktop.png') });

// ── route invariance ─────────────────────────────────────────────────────
/* Three routes. On same-column routes (/, /questions) the absolute box must
   be identical. On /review the column itself widens, so absolute coords may
   move with the whole bar — the pin is the trail gap, and the anti-pattern
   is identity sitting beside the route word (its left tracking titleRight). */
await go('/questions');
let b = await read();
notes.push(`/questions: hproj=${JSON.stringify(b)}`);
ok('/questions still shows the same basename', b && b.text === 'gamma-loop');

await go(`/review?p=${encodeURIComponent(longParam)}`);
let c = await read();
notes.push(`/review?p=${longParam}: hproj=${JSON.stringify(c)} route=${c && c.route}`);
ok('long review route still shows the same basename',
   c && c.text === 'gamma-loop');
ok('the three routes actually differ in the route word (else invariance is vacuous)',
   a && b && c && a.route !== b.route && b.route !== c.route);
ok('route ink widths actually differ across the three (else the shove cannot show)',
   a && b && c &&
   (Math.abs(a.inkW - b.inkW) > 4 || Math.abs(b.inkW - c.inkW) > 4));
notes.push(`ink widths: /=${a && a.inkW} /q=${b && b.inkW} /rev=${c && c.inkW}`);
notes.push(`identity rects: /=${a && a.left},${a && a.top},${a && a.width}x${a && a.height}`
  + ` /q=${b && b.left},${b && b.top},${b && b.width}x${b && b.height}`
  + ` /rev=${c && c.left},${c && c.top},${c && c.width}x${c && c.height}`);
/* Absolute box identical where the column width is the same — this is the
   brief's "identical, not merely present" proof for the invariant.
   Both boxes must have positive size first: two empty rects are identical
   and would pass over a missing identity. */
ok('identity has a real painted box on / and on /questions (else same-box is vacuous)',
   a && b && a.width > 0 && a.height > 0 && b.width > 0 && b.height > 0);
ok('identity box on / and /questions is IDENTICAL (not merely present)',
   a && b && a.width > 0 && b.width > 0 && sameBox(a, b));
/* Edge pin holds on every route — including the wide /review column. */
ok('identity is edge-pinned on / (trail gap ~0, and a real box)',
   a && a.width > 0 && a.trailGap != null && Math.abs(a.trailGap) <= 1);
ok('identity is edge-pinned on /questions (trail gap ~0, and a real box)',
   b && b.width > 0 && b.trailGap != null && Math.abs(b.trailGap) <= 1);
ok('identity is edge-pinned on long /review (trail gap ~0, and a real box)',
   c && c.width > 0 && c.trailGap != null && Math.abs(c.trailGap) <= 1);
/* Not neighbour-anchored: if identity sat beside the route word, its left
   would equal the route ink's right plus a fixed gap, so left would move
   when inkW grows. On an edge pin, left is barRight - width and does NOT
   track inkRight. Requires both real boxes or the deltas are zero. */
ok('identity left does not track the route ink right (/ vs long /review)',
   a && c && a.width > 0 && c.width > 0 &&
   Math.abs((c.left - a.left) - (c.inkRight - a.inkRight)) > 8);
ok('identity still has a real box on long /review',
   c && c.width > 0 && c.height > 0);

// ── mobile: still present, still the basename ────────────────────────────
const phone = await br.newContext({ viewport: { width: 390, height: 844 } });
const pp = await phone.newPage();
await pp.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);
const ph = await pp.evaluate(() => {
  const el = document.getElementById('hproj');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { text: el.textContent, w: r.width, h: r.height, left: r.left };
});
notes.push(`phone /questions: ${JSON.stringify(ph)}`);
ok('phone width still shows the project basename',
   ph && ph.text === 'gamma-loop' && ph.w > 0);
await pp.screenshot({ path: join(OUT, 'projtitle-phone.png') });
await phone.close();

if (errs.length) notes.push('page errors: ' + errs.join(' | '));
ok('no page errors', errs.length === 0);

await br.close();
try { srv.kill(); } catch (e) {}
finish();
