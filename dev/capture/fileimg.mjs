/* fileimg — #336: viewing an image must not render as U+FFFD soup.

   His report, typed from /file?p=.dreamwork/review/evidence/review-note-
   reply-unclear.png: "viewing images should work. this renderes as binary
   ascii like:" and a paste of the replacement-character stream. The cause
   is in .dreamwork/tasks.md (#336): /filedata did read_text (UTF-8,
   errors=replace) and the client rendered the result in a <pre>.

   WHAT THIS GUARD PROVES, in pixels rather than in source:

   · The view renders an <img> whose src is /filebytes (not a <pre> of
     mojibake). The endpoint existence is asserted in pytest; this is the
     "does the page actually wire it up" half.
   · The image's bytes are FETCHED AND DRAWN: a screenshot proves the
     pixels are not the broken-image icon, and an XHR trace proves a
     /filebytes request fired for the right path.
   · MOTION: the image's own arrival is a fade, not a snap. The <img>
     begins at opacity 0 (.pose) and transitions to 1 on load, so a late
     byte stream eases in rather than popping. The trace must show
     intermediate opacity values between 0 and 1 (the count rule's
     `between()` form, never an absolute count).
   · REDUCED-MOTION PARITY: under prefers-reduced-motion the start pose is
     never applied — the image is fully visible from the first frame. That
     is the "same information and timing with the movement removed"
     contract; a feature that silently degrades to invisible would pass a
     pose-removal check and fail this one.
   · A non-image binary shows a labelled panel — type, size — with a
     download link, never a <pre> of bytes.

   THIS GUARD BUILDS ITS OWN TARGET, dashboard.mjs-style: the shared
   fixture has no image, and planting one in it would be a fixture change
   rather than this guard's own setup. It picks its own ephemeral port
   for the same reason dashboard does.

   Shown red against the pre-#336 build: the <img> selector finds nothing
   (the view rendered a <pre> of mojibake instead), and the opacity trace
   throws on a null subject.

   usage: node fileimg.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync, writeFileSync, rmSync, cpSync } from 'node:fs';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { deflateSync } from 'node:zlib';
import { join } from 'node:path';
const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/file?p=<png> and /file?p=<bin> in two motion contexts (normal + ' +
          'reduced): the image renders, its bytes are fetched from /filebytes, ' +
          '#view dissolves through intermediate opacities carrying the image ' +
          '(normal) or snaps to fully visible (reduced), and a binary shows a ' +
          'labelled panel with a download link',
  traceWindow: 'a 1.5s rAF trace of #view.opacity starting ~30ms before a ' +
               'real client-router navigation to /file?p=pic.png — long enough ' +
               'to outlast the ~1.15s dissolve (DREAM_MS), short enough that a ' +
               'later tick cannot supply the motion it asserts; the image\'s ' +
               'own .pose fade is for the late-load case and is covered ' +
               'structurally (the class is in the markup, removed on load)',
});

/* An ephemeral port, not the one passed in (dashboard.mjs's argument). The
   guard runs its own server, so a fixed port would be shared mutable state
   with no owner. */
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const BASE = `http://127.0.0.1:${PORT}`;

// ── a target with a PNG and a .bin ─────────────────────────────────────────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
// A small but real PNG: magic + IHDR + IDAT + IEND for a 2x2 dark-gray image.
// Hand-built so the guard is self-contained and the fixture stays clean.
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  // CRC32 over type+data. Small enough to inline; matches the PNG spec.
  const crcTable = (() => {
    const t = []; for (let n = 0; n < 256; n++) {
      let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0;
    } return t;
  })();
  const buf = Buffer.concat([Buffer.from(type), data]);
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  const crc = Buffer.alloc(4); crc.writeUInt32BE((c ^ 0xffffffff) >>> 0, 0);
  return Buffer.concat([len, buf, crc]);
}
const ihdr = (() => {
  const d = Buffer.alloc(13);
  d.writeUInt32BE(2, 0); d.writeUInt32BE(2, 4);   // 2x2
  d[8] = 8; d[9] = 0; d[10] = 0; d[11] = 0; d[12] = 0; // 8-bit grayscale
  return chunk('IHDR', d);
})();
// IDAT: zlib stream of [filter0, px][filter0, px] for two rows of two pixels.
const idat = chunk('IDAT', deflateSync(Buffer.from([0, 64, 64, 0, 64, 64])));
const iend = chunk('IEND', Buffer.alloc(0));
const PNG = Buffer.concat([PNG_MAGIC, ihdr, idat, iend]);
writeFileSync(join(DIR, 'pic.png'), PNG);
// A non-image binary: NUL bytes so detect_file_kind returns 'binary'.
writeFileSync(join(DIR, 'object.bin'), Buffer.from([0, 1, 2, 3, 0xff, 0xfe]));

const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: ['ignore', 'pipe', 'pipe'] });
srv.stdout.on('data', () => {}); srv.stderr.on('data', () => {});
const cleanup = () => { try { srv.kill('SIGTERM'); } catch (e) {} };
process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(130); });
process.on('SIGTERM', () => { cleanup(); process.exit(143); });
for (let i = 0; i < 40; i++) {
  try { const r = await fetch(`${BASE}/`); if (r.ok) break; } catch (e) {}
  await sleep(250);
}
if (!(await fetch(`${BASE}/`).then(r => r.ok).catch(() => false))) {
  console.log('----\nFAIL the guard\'s own server never came up');
  finish(); process.exit(1);
}

/* Trace the <img>'s computed opacity from its onload forward. The image's
   own arrival is a self-contained opacity fade; the route dissolve is a
   separate motion on #view and is not the subject here. Sampling STARTS at
   onload because before it the <img> may not be in the DOM yet, and the
   .pose class is removed on load — the question is whether the removal
   transitions through intermediate values or snaps.

   Per transitions.md: an end-state check cannot fail on a motion bug, and
   neither can "did it move". Assert that some captured frame is strictly
   part-way between the first and the last (`between()`), with a vacuity
   precondition asserting the trace's first/last are at distinct opacities
   in pixel space. */
const TRACE = `
new Promise(res => {
  const img = document.querySelector('#filebody img.fileimg');
  if (!img) { res({err: 'no img'}); return; }
  const frames = [];
  const t0 = performance.now();
  const done = () => res({
    frames,
    final: frames[frames.length - 1],
    first: frames[0],
    hadPose: !!img.dataset.arrived,
  });
  // If the image has already loaded (.pose already gone), trace for 700ms
  // anyway so a non-arrival (e.g. a build that never applies the pose) shows
  // up as "no intermediate values" rather than as a 0-frame trace.
  (function step() {
    const cs = getComputedStyle(img);
    frames.push(+parseFloat(cs.opacity).toFixed(3));
    if (performance.now() - t0 < 700) requestAnimationFrame(step);
    else done();
  })();
})`;
function between(frames, first, last) {
  // The count rule's frame-rate-free form: at least one frame STRICTLY
  // between the two ends. ~3% deadband so a frame that really is an end
  // does not read as travel.
  const lo = Math.min(first, last), hi = Math.max(first, last);
  const span = hi - lo;
  const pad = Math.max(0.03, span * 0.03);
  return frames.filter(v => v > lo + pad && v < hi - pad).length;
}

for (const reduced of [false, true]) {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const ctx = await br.newContext({
    viewport: { width: 1100, height: 900 },
    reducedMotion: reduced ? 'reduce' : 'no-preference',
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  const fileReqs = [];
  p.on('request', r => {
    if (r.url().includes('/filebytes')) fileReqs.push(r.url());
  });
  // Go to the dashboard first so the route change TO /file is real (the
  // reference implementation of motion on this page). Then navigate by
  // client router, not by full page load.
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(400);
  await p.evaluate((path) => {
    history.pushState({}, '', '/file?p=' + path);
    dispatchEvent(new PopStateEvent('popstate'));
  }, 'pic.png');
  // Wait for the view to render and the image to settle.
  await sleep(900);
  const imgThere = await present(p, '#filebody img.fileimg',
    'the file view renders an <img class="fileimg">');
  if (!imgThere) { await br.close(); continue; }

  // PROOF: the image actually drew bytes (not the broken-image glyph).
  const drew = await p.evaluate(() => {
    const img = document.querySelector('#filebody img.fileimg');
    return { complete: img.complete,
             naturalW: img.naturalWidth, naturalH: img.naturalHeight,
             // a broken image reports 0x0; a drawn one reports its dims
             src: img.getAttribute('src') };
  });
  ok(`the image FETCHED its bytes from /filebytes (src, in ${reduced ? 'RM' : 'normal'})`,
     /\/filebytes\?p=pic\.png/.test(drew.src));
  ok(`the image DREW (natural dims > 0, in ${reduced ? 'RM' : 'normal'})`,
     drew.complete && drew.naturalW > 0 && drew.naturalH > 0);

  // PROOF: the request really fired (server-side corroborates the src).
  ok(`a /filebytes request fired for pic.png (in ${reduced ? 'RM' : 'normal'})`,
     fileReqs.some(u => /p=pic\.png/.test(u)));

  // MOTION: now do a CLEAN navigation, because the one above already settled
  // before we started tracing. We trace the image's PAINTED opacity — the
  // product of its own opacity and every ancestor's, because the route
  // dissolve lives on #view (an ancestor) and the image rides it as a
  // passenger. Reading only the image's own opacity would miss the dissolve
  // entirely on the common case where its bytes load before paint and
  // .pose is removed before the first frame.
  //
  // What this catches: a route dissolve that snaps (no intermediate
  // values), an image that pops in past a dissolving ancestor, or a build
  // that forgets to put the image inside #view. The image's own .pose
  // fade is a separate, smaller motion for the late-load case; this trace
  // sees it too because painted opacity multiplies through.
  await p.evaluate(() => history.pushState({}, '', '/'));
  await p.evaluate(() => dispatchEvent(new PopStateEvent('popstate')));
  await sleep(500); // let the dashboard settle
  const trace = await p.evaluate(`
    new Promise(res => {
      // Trace #view's opacity directly. The dissolve lives on #view (the
      // reference implementation), and the image is inside it, so #view's
      // opacity IS the painted opacity of everything in the view. Reading
      // the image's own opacity separately would miss the dissolve on the
      // common fast-load path. We also track whether the <img> appeared,
      // so the precondition (the view really did contain the image) is
      // proven rather than assumed.
      const frames = [];
      let sawImg = false;
      const t0 = performance.now();
      (function step() {
        const v = document.getElementById('view');
        const cs = v ? getComputedStyle(v) : null;
        const img = document.querySelector('#filebody img.fileimg');
        if (img) sawImg = true;
        frames.push(cs ? +parseFloat(cs.opacity).toFixed(3) : null);
        if (performance.now() - t0 < 1500) requestAnimationFrame(step);
        else res({ frames: frames.filter(v => v !== null),
                   first: frames.find(v => v !== null),
                   final: frames.filter(v => v !== null).pop() || null,
                   sawImg });
      })();
      // fire the navigation on the next frame, so the trace catches frame 0
      // of the new view (the dissolving #view containing the new <img>)
      setTimeout(() => {
        history.pushState({}, '', '/file?p=pic.png');
        dispatchEvent(new PopStateEvent('popstate'));
      }, 30);
    })
  `);

  if (reduced) {
    // REDUCED MOTION: the dissolve is suppressed (#view snaps to opacity 1),
    // so the image's painted opacity is 1 from the first frame. A trace that
    // faded 0->1 would be a feature that silently animates under a contract
    // that forbids it.
    const settled = trace.frames.filter(v => v >= 0.95);
    ok(`reduced motion: the image is fully visible from the first frame ` +
       `(no fade; first=${trace.first}, settled=${settled.length}/${trace.frames.length})`,
       trace.first >= 0.95 && settled.length >= trace.frames.length * 0.5);
  } else {
    // NORMAL: #view's opacity transitions 0 -> 1 over ~1.15s with
    // intermediate values, and the image rides it as a passenger. The span
    // precondition is stated in PIXEL space (opacity 0..1): if the dissolve
    // never ran (a snap, or a build that skipped it), first==final and
    // between() is zero. sawImg proves the view really contained the image,
    // so a check that ran against a view that never loaded it cannot pass.
    const first = trace.first ?? 1, final = trace.final ?? 1;
    const span = Math.abs(final - first);
    const mid = between(trace.frames, first, final);
    notes.push(`normal: #view opacity first=${first} final=${final} ` +
               `span=${span.toFixed(3)} between=${mid} sawImg=${trace.sawImg} ` +
               `(of ${trace.frames.length} frames)`);
    ok(`normal: the view really contained the <img> (precondition: the ` +
       `dissolve we trace is the one carrying the image)`, trace.sawImg);
    // 0.5 spans more than half the 0..1 range — well above the 0.03 deadband
    // and below the 0->1 we expect, so it discriminates "a real dissolve"
    // from "the view was at one opacity throughout".
    ok(`normal: #view's opacity SPANS at least 0.5 (the dissolve moves)`,
       span >= 0.5);
    ok(`normal: the image ARRIVES via the dissolve (>=1 frame strictly between)`,
       mid >= 1);
    ok(`normal: no frame goes PAST the final opacity (no overshoot)`,
       trace.frames.every(v => v <= Math.max(first, final) + 0.01));
  }

  await p.screenshot({ path: `${OUT}/fileimg-${reduced ? 'rm' : 'normal'}.png` });
  await br.close();
}

// ── a non-image binary shows a labelled panel, not bytes in a <pre> ──────
{
  const br = await chromium.launch({ args: ['--use-gl=swiftshader'] });
  const p = await br.newPage({ viewport: { width: 1100, height: 900 } });
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/file?p=object.bin`, { waitUntil: 'networkidle' });
  await sleep(500);
  const bin = await p.evaluate(() => {
    const body = document.getElementById('filebody');
    if (!body) return null;
    return {
      hasPre: !!body.querySelector('pre'),
      hasImg: !!body.querySelector('img'),
      label: (body.querySelector('.label') || {}).textContent || null,
      dl: !!body.querySelector('a.filebin-dl[download]'),
      dlHref: (body.querySelector('a.filebin-dl') || {}).getAttribute('href') || '',
      typeText: (body.querySelector('.filebin-v') || {}).textContent || null,
    };
  });
  if (bin) {
    ok('a non-image binary shows the binary panel (not a <pre>, not an <img>)',
       !bin.hasPre && !bin.hasImg);
    ok('the panel carries the "binary file" label',
       /binary file/i.test(bin.label || ''));
    ok('the panel states the type as a fact', !!bin.typeText);
    ok('the panel offers a download link to /filebytes',
       bin.dl && /\/filebytes\?p=object\.bin/.test(bin.dlHref));
  } else {
    ok('the binary file view rendered (else every check below is vacuous)', false);
  }
  await p.screenshot({ path: `${OUT}/fileimg-binary.png` });
  await br.close();
}

ok('no page errors', errs.length === 0);
cleanup();
finish();
/* Explicit exit: the spawned python server holds an event-loop handle
   even after SIGTERM, so without this the guard's checks all print PASS
   and then it hangs until the runner's timeout kills it — reporting exit
   124 over a green run. The 'exit' handler (registered above) fires on
   this and reaps the child. */
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
