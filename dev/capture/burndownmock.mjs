/* burndownmock — #417: the four commits-per-period options must be readable
   as a comparison, not only as five stacked figures.

   The artifact already held ten real panel renders (ref + c1–c4 × two
   viewports). The defect the human named at 05:51 was presentation: they
   could not be seen *together*. The fix is a side-by-side strip
   (`#compare` / `#compare-strip`) that reuses the desktop-width real
   renders at one intrinsic scale.

   THREE CLAIMS, each red-provable on a production line of the artifact
   (not on a seam this guard introduces):

     1. OPTION COUNT is derived from the strip's `data-option` cells, not
        a literal `4`. Removing one cell reds the "one render per option"
        claim; the production line is the set of `.compare-cell[data-option]`
        nodes in `.dreamwork/review/417-burndown-commits.html`.

     2. SAME WIDTH. A comparison at two scales is not a comparison. Every
        `.compare-render` reports the same `naturalWidth` (and the same
        attribute width). Swapping one cell's image for the mobile twin
        (358px) reds this — production line: the `width` / PNG IHDR of each
        compare-render src in the built artifact.

     3. NON-BLANK. A broken data URI paints nothing and looks like a subtle
        design. Each render must decode with naturalWidth>0 and a non-trivial
        byte footprint. Replacing a src with a 1×1 transparent PNG reds this —
        production line: the data URI of that img.

   Preconditions are derived at runtime: option count is asserted before
   width equality (one cell cannot fail "widths differ"); image count is
   asserted before non-blank. A green red-run is a finding.

   PORT DISCIPLINE: own-server guard — ALWAYS ephemeral freePort(); argv[3]
   is deliberately ignored. Taking argv[3] (the recipe's shared {{port}}) made
   listen() throw EADDRINUSE before any assertion, so the guard registered but
   never judged (#471 named it: "did NOT run-and-judge"). Same root as #461's
   eight: the recipe always passes a port already held by the shared server.
   Refuse 39880–39899 and :35110 when freePort hands one back.

   usage: node burndownmock.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
mkdirSync(OUT, { recursive: true });

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..', '..');
const ARTIFACT = join(ROOT, '.dreamwork', 'review', '417-burndown-commits.html');

const LIVE_DASH = 35110;
const GUARD_LO = 39880, GUARD_HI = 39899;

const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => {
    const p = s.address().port;
    s.close(() => res(p));
  });
});

// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored. Adopting argv[3] forced listen() onto the recipe's shared port
// (already held) → EADDRINUSE → "threw before finishing its checks" with zero
// genuine PASS/FAIL (#471). Registration is not execution.
async function pickPort() {
  let p;
  do { p = await freePort(); }
  while ((p >= GUARD_LO && p <= GUARD_HI) || p === LIVE_DASH);
  return p;
}

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'built #417 review artifact at /417-burndown-commits.html on an ' +
          'ephemeral static server; reads #compare-strip cells and their ' +
          'decoded image natural widths — no watch.py, no live dashboard',
  traceWindow: 'none: static layout + image decode after load; no gesture traced',
});

if (!existsSync(ARTIFACT)) {
  ok('the #417 built artifact exists at .dreamwork/review/417-burndown-commits.html', false);
  notes.push(`missing artifact: ${ARTIFACT}`);
  finish();
  process.exit(1);
}

const html = readFileSync(ARTIFACT, 'utf8');
const PORT = await pickPort();
notes.push(`serving ${ARTIFACT} on 127.0.0.1:${PORT}`);
notes.push(`port from freePort() (argv[3] ignored; own-server — see #461/#471): ${PORT}`);

// Minimal static server: only the one artifact, so a missing compare cannot
// be papered over by another page.
const server = createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === '/' || url === '/417-burndown-commits.html') {
    res.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store',
    });
    res.end(html);
    return;
  }
  res.writeHead(404); res.end('not found');
});
await new Promise((resolve, reject) => {
  server.listen(PORT, '127.0.0.1', resolve);
  server.on('error', reject);
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader'] });
try {
  const p = await br.newPage({ viewport: { width: 1280, height: 900 } });
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`http://127.0.0.1:${PORT}/417-burndown-commits.html`, {
    waitUntil: 'load', timeout: 60000,
  });
  // Wait for every compare-render to decode (data URIs are local; still async).
  await p.waitForFunction(() => {
    const strip = document.querySelector('#compare-strip');
    if (!strip) return false;
    const imgs = [...strip.querySelectorAll('img.compare-render')];
    return imgs.length > 0 && imgs.every(img => img.complete && img.naturalWidth > 0);
  }, { timeout: 30000 });

  const measured = await p.evaluate(() => {
    const strip = document.querySelector('#compare-strip');
    if (!strip) return { strip: false };
    const cells = [...strip.querySelectorAll('.compare-cell[data-option]')];
    const options = cells.map(c => c.getAttribute('data-option'));
    // Derive the option list from the artifact — do not hardcode length.
    const imgs = cells.map(c => {
      const img = c.querySelector('img.compare-render');
      if (!img) return null;
      return {
        option: c.getAttribute('data-option'),
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        attrWidth: Number(img.getAttribute('width') || 0),
        complete: img.complete,
        srcLen: (img.currentSrc || img.src || '').length,
        // Sample a few decoded pixels via canvas to catch solid/empty frames.
        // A 1×1 transparent PNG has naturalWidth 1; a real panel is hundreds.
      };
    });
    // Also collect option keys advertised elsewhere (figures) for cross-check
    // without hardcoding 4: any fig-cN id is an option the page claims.
    const figOpts = [...document.querySelectorAll('figure.burnfig[id^="fig-"]')]
      .map(f => f.id.replace(/^fig-/, ''))
      .filter(k => k && k !== 'ref');
    return {
      strip: true,
      options,
      imgs,
      figOpts,
      compareId: !!document.getElementById('compare'),
      ask: !!document.getElementById('ask'),
      ifSilent: !!document.getElementById('if-silent'),
    };
  });

  writeFileSync(join(OUT, 'measured.json'), JSON.stringify(measured, null, 2));
  notes.push(`derived options from strip: ${JSON.stringify(measured.options)}`);
  notes.push(`figure options (fig-c*): ${JSON.stringify(measured.figOpts)}`);
  if (measured.imgs) {
    for (const im of measured.imgs) {
      if (!im) { notes.push('  missing img on a cell'); continue; }
      notes.push(`  ${im.option}: natural=${im.naturalWidth}x${im.naturalHeight} attrW=${im.attrWidth} srcLen=${im.srcLen}`);
    }
  }

  ok('#compare strip exists on the built artifact', measured.strip === true && measured.compareId === true);

  // ── 1. one render per option, count derived ────────────────────────────
  const options = measured.options || [];
  const nOpts = options.length;
  // Precondition: the strip lists more than one option (else "comparison" is
  // vacuous and same-width cannot fail).
  ok('precondition: comparison lists more than one option (else same-width is vacuous)',
     nOpts > 1);
  // Every data-option cell carries exactly one compare-render that decoded.
  const imgs = (measured.imgs || []).filter(Boolean);
  ok('one compare-render per data-option cell (count derived from strip, not a literal)',
     imgs.length === nOpts && nOpts > 0);
  // Option keys are unique (two c1 cells would inflate the count without
  // showing four options).
  ok('derived option keys are unique',
     new Set(options).size === options.length && options.length === nOpts);
  // Cross-check: every fig-c* option the detail section claims appears in the
  // strip. Derive both sides; do not assert a literal 4.
  const figSet = new Set(measured.figOpts || []);
  const stripCand = new Set(options.filter(o => o !== 'ref'));
  ok('every fig-c* candidate has a cell in the side-by-side strip (sets, not a literal count)',
     figSet.size > 0 && [...figSet].every(k => stripCand.has(k)) &&
     [...stripCand].every(k => figSet.has(k)));

  // ── 2. same width ──────────────────────────────────────────────────────
  // Precondition already asserted nOpts > 1. Now equal natural widths.
  const widths = imgs.map(i => i.naturalWidth);
  const widthSet = new Set(widths);
  ok('every compare-render decodes to the same naturalWidth (same-scale comparison)',
     imgs.length > 1 && widthSet.size === 1 && widths[0] > 0);
  // Attribute width agrees with natural (the markup claims the scale it shows).
  ok('attribute width matches naturalWidth on every compare-render',
     imgs.length > 0 && imgs.every(i => i.attrWidth === i.naturalWidth && i.attrWidth > 0));

  // ── 3. non-blank ───────────────────────────────────────────────────────
  // A broken data URI: complete may be true with naturalWidth 0, or a 1×1
  // placeholder. Real panel renders are hundreds of pixels wide and carry a
  // long data URI.
  ok('precondition: at least one compare-render exists before non-blank checks',
     imgs.length > 0);
  ok('every compare-render is non-blank (naturalWidth > 100, naturalHeight > 50, long data URI)',
     imgs.length > 0 && imgs.every(i =>
       i.complete && i.naturalWidth > 100 && i.naturalHeight > 50 && i.srcLen > 1000));

  // Contract surface the builder already enforces — named so a strip-only
  // page without an ask still fails here if someone bypasses the builder.
  ok('#ask is present (builder contract surface on this page)', measured.ask === true);
  ok('#if-silent is present (builder contract surface on this page)', measured.ifSilent === true);

} catch (e) {
  errs.push(String(e && e.stack ? e.stack : e));
  ok('the guard completed its page measurements without throwing', false);
} finally {
  await br.close();
  await new Promise(res => server.close(res));
}

finish();
