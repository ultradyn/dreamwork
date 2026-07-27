/* qfade — #326, and it is a PIXEL guard on purpose.

   His words, about the band #305 (c) shipped an hour earlier: "the black stuff
   around the answer box to emulate the fade thing is ugly. the text itself
   should fade, not be covered by fake fade. and the buttons and text box
   shouldn't have anything behind them (should look like it did before)".

   Three claims, and the middle one is why this guard cannot be written against
   the CSS source. "There is no `.qcompose::before`" would pass the NEXT
   well-meaning band, because that one has a different selector; so would "the
   mask-image is a gradient", because a band and a mask can coexist. What he is
   complaining about is a property of the COMPOSITED RESULT — something opaque
   painted between the answer box and the page — so that is what is measured.

   THE PLATE. The page's background is a live WebGL shader, i.e. a different
   colour every frame at every pixel, which no assertion can be written against.
   So the guard hides `#dreambg` and paints the page one flat colour that
   nothing in the design uses (#00ff88). Everything the dock paints is then
   measurable against it:

     - a MASK paints nothing at all. It makes glyphs translucent, so every
       pixel where the card draws nothing stays EXACTLY the plate.
     - a BAND, or a scrim, or a blur, or anything else painted between the box
       and the page, cannot leave the plate exactly the plate.

   So the assertion is "still the plate", and that distinction holds for any
   selector, any element, any z-index and any opacity.

   IT MATTERS THAT IT IS "STILL THE PLATE" AND NOT "NEVER `--bg`", and this is
   the guard's own documented green red-run: the first version asserted that no
   pixel behind the box was within 8/255 of `var(--bg)` — the colour a band's
   gradient interpolates to — and it PASSED with #305 (c)'s band reinstated
   verbatim. The band was painting; the card it sits in is `.qa.awaiting`,
   which carries `opacity:.82`, so the band composited to rgb(9,58,44) instead
   of rgb(11,15,25) and the comparison missed it by a mile. Naming the colour
   the offender paints is a guess about the offender. Naming the colour that
   must survive is a fact about the requirement.

   Both of the other two claims fall out of the same plate: the strip above the
   box is where the text fades, so its ink profile must FALL toward the box and
   reach the plate at the scroller's edge; and the box's own box must be plate
   colour wherever its children are not.

   Preconditions are asserted, not hoped for (CLAUDE.md): a fade check on a
   question too short to scroll proves nothing, and an ink profile over a strip
   with no text in it proves nothing either. Both are derived at runtime.

   usage: node qfade.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const { ok, present, declare, finish, notes, errs } = makeReporter();
// the reporter prints `notes` on exit — including after a crash — so a second
// immediate console.log of every line would only double the output
const say = s => notes.push(s);
declare({
  drives: '/review?p=&q= at 1280x820 with the LONGEST open question (so the ' +
    'column overflows) and with the SHORTEST (so "glued" is tested where #305 ' +
    'failed it), plus 700px narrow; scrolls the question body to top, half way ' +
    'and to the end, and reads back a screenshot of the dock each time',
  traceWindow: 'no per-frame trace — every assertion here is about a settled ' +
    'composited frame, read after a 700ms rest so the .45s fade transitions ' +
    'have finished (reviewsplit.mjs owns the part-way frames)',
});

const PLATE = [0, 255, 136];          // #00ff88 — in no token, in no gradient
/* ...and it must BE in no token, or "still the plate" would be satisfiable by
   something the design paints. Asserted against the page's own variables rather
   than trusted, because a palette change is exactly the kind of thing that
   would rot this quietly. */
const PLATE_IS_ALIEN = `(() => {
  const cs = getComputedStyle(document.documentElement);
  const d = document.createElement('div'); document.body.appendChild(d);
  const rgb = c => { d.style.color = ''; d.style.color = c;
    const m = getComputedStyle(d).color.match(/[0-9.]+/g);
    return m ? m.slice(0, 3).map(Number) : null; };
  const hits = [];
  for (const name of ['--bg', '--fg', '--dim', '--dimmer', '--muted', '--lit',
                      '--bright', '--accent', '--warn', '--border', '--line',
                      '--panel']) {
    const v = cs.getPropertyValue(name).trim();
    if (!v) continue;
    const c = rgb(v);
    if (c && Math.abs(c[0]) <= 24 && Math.abs(c[1] - 255) <= 24 &&
        Math.abs(c[2] - 136) <= 24) hits.push(name + '=' + v);
  }
  d.remove();
  return hits;
})()`;
/* Hide the shader and flood the page with the plate colour. `!important` on the
   canvas because the shader is positioned chrome, and on the wrap/body because
   the page paints its own background; the dock itself is left completely alone,
   which is the point — whatever it paints, it paints over the plate. */
const PAINT_PLATE = `(() => {
  const s = document.createElement('style');
  s.id = 'qfade-plate';
  s.textContent = '#dreambg{display:none!important}' +
    'html,body{background:#00ff88!important}' +
    '.wrap{background:transparent!important}';
  document.head.appendChild(s);
})()`;

const data = await (await fetch(`${BASE}/data.json`)).json();
const review = (data.reviews || [])[0];
const len = q => (q.body || '').length + JSON.stringify(q.follows || []).length;
const qs = (data.questions_open || []).slice().sort((a, b) => len(b) - len(a));
if (!review || !qs.length)
  throw new Error('fixture needs a review artifact and an open question');
const urlFor = q => `${BASE}/review?p=${encodeURIComponent(review.name)}` +
                    `&q=${encodeURIComponent(q.title)}`;

/* WHERE TO SAMPLE. Two regions, both derived from the live layout:
     box   — the compose box's own border box, minus the descendants that
             actually PAINT. Which ones those are is derived, not listed: a
             descendant is skipped if it has a background of its own or if it
             is a leaf (so it may hold text). What is left is the compose box's
             own footprint — most of the mode row, which is full-width while
             only its two buttons paint, plus the gaps between the rows. That
             is the largest region the band covered and the region a reader
             would point at. Listing the children by class instead would go
             quietly vacuous the day the composer grows a third control.
     strip — the last `--qfoot` plus one line of the scroller: exactly the
             region the band used to cover and the mask now fades. */
const REGIONS = `(() => {
  const dock = document.getElementById('qdock');
  const body = dock.querySelector('.qa > .qbody');
  const comp = dock.querySelector('.qcompose');
  const R = el => { const b = el.getBoundingClientRect();
    return { x:b.left, y:b.top, w:b.width, h:b.height, b:b.bottom }; };
  const box = R(comp);
  const paints = el => {
    const cs = getComputedStyle(el);
    return cs.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
           cs.backgroundImage !== 'none' || !el.children.length;
  };
  const kids = [...comp.querySelectorAll('*')].filter(paints).map(el => {
    const b = el.getBoundingClientRect();
    return { x:b.left - 2, y:b.top - 2, r:b.right + 2, b:b.bottom + 2 };
  });
  const skipped = [...comp.querySelectorAll('*')].filter(paints)
    .map(el => el.className || el.tagName);
  const sb = R(body);
  const foot = parseFloat(getComputedStyle(body).getPropertyValue('--qfoot'));
  return { box, kids, skipped,
           strip: { x:sb.x, y:sb.b - (foot + 20), w:sb.w, h:foot + 20 },
           scroll: { top: body.scrollTop, client: body.clientHeight,
                     full: body.scrollHeight },
           foot, fade: parseFloat(getComputedStyle(body)
                                    .getPropertyValue('--qfade')),
           atend: dock.classList.contains('atend'),
           attop: dock.classList.contains('attop'),
           composeBottom: box.b,
           artifactBottom: R(document.getElementById('reviewframe')).b };
})()`;
/* THE MASK, OFF AND BACK ON, at one scroll position. The fade has to be
   measured against the same glyphs it is fading — a strip is two text lines
   tall, so which rows hold ink dominates any comparison between two different
   scroll positions, and an "upper half vs lower half" reading of one plate
   reports the fixture's line spacing as a fade (measured: 18.5 vs 15.3 with a
   fade that reaches zero). Toggling only the mask cancels that out completely:
   every pixel is the same pixel, and the ratio is the mask's whole effect.
   It is also what makes this assertion able to fail on a BAND, which the
   ratio between two scroll positions could not: switch a mask off and a band
   still covers the text, so nothing would change.

   It switches off EVERY mask in the dock, not `.qbody`'s. Named the narrow way
   it had its own green red-run: with the fade moved back onto `.qa` — the
   scroller-that-contains-the-box trap this guard exists to catch — an inline
   override on `.qbody` left the offending mask in place in both plates, so the
   answer box measured identically dimmed twice and the check passed. The
   question this comparison asks is "what does masking do here", and the answer
   must not depend on which element the author chose. */
const MASK = on => `(() => {
  const id = 'qfade-nomask';
  const had = document.getElementById(id);
  if (${on}) { if (had) had.remove(); }
  else if (!had) {
    const s = document.createElement('style'); s.id = id;
    s.textContent = '#qdock, #qdock *{-webkit-mask-image:none!important;' +
      'mask-image:none!important}';
    document.head.appendChild(s);
  }
  return getComputedStyle(
    document.querySelector('#qdock .qa > .qbody')).maskImage;
})()`;

/* Read the plate back. Runs in the page with the screenshot as a data URL —
   the same idiom popbg.mjs and identity.mjs use for pixel evidence.
     painted — pixels that are NOT the plate any more (8/255 per channel): a
               glyph, or anything drawn between the box and the page.
     ink     — mean distance from the plate, per row, so a fade can be read as
               a profile rather than as a single number.
   `skip` is the descendant rects, so the box's own field and buttons are not
   mistaken for something painted behind them. */
const MEASURE = async ([url, region, skip, plate]) => {
  const img = await new Promise(r => {
    const i = new Image(); i.onload = () => r(i); i.src = url; });
  const cv = document.createElement('canvas');
  cv.width = img.width; cv.height = img.height;
  const g = cv.getContext('2d'); g.drawImage(img, 0, 0);
  const x0 = Math.round(region.x), y0 = Math.round(region.y);
  const w = Math.round(region.w), h = Math.round(region.h);
  const d = g.getImageData(x0, y0, w, h).data;
  const rows = []; let painted = 0, sampled = 0, worst = null;
  for (let y = 0; y < h; y++) {
    let ink = 0, n = 0;
    for (let x = 0; x < w; x++) {
      const px = x0 + x, py = y0 + y;
      if ((skip || []).some(k => px >= k.x && px <= k.r && py >= k.y && py <= k.b))
        continue;
      const i = (y * w + x) * 4;
      n++; sampled++;
      const off = Math.max(Math.abs(d[i] - plate[0]), Math.abs(d[i+1] - plate[1]),
                           Math.abs(d[i+2] - plate[2]));
      // distance from the plate, over the two channels it is extreme in, so a
      // half-faded glyph reads as half the ink of a lit one
      ink += Math.abs(d[i] - plate[0]) + Math.abs(d[i+2] - plate[2]);
      if (off > 8) { painted++; if (!worst) worst = { px, py,
        rgb: [d[i], d[i+1], d[i+2]] }; }
    }
    rows.push({ y: y0 + y, ink: n ? +(ink / n).toFixed(1) : null, n });
  }
  return { rows, painted, sampled, worst };
};

/* PAIR TWO PLATES ROW BY ROW, and never compare their means. Both places this
   guard asks "did the mask change anything here" had a documented green
   red-run against a mean: the box's mean moved 1.2% when the fade was moved
   back onto `.qa` and dimmed its bottom 24px (57.41 -> 56.7), and the
   end-of-question strip's mean moved 11.9% with the foot fade jammed on
   (12.37 -> 10.9). Both were under any tolerance worth having, because a fade
   is a local effect and a mean over the whole region dilutes it by exactly the
   ratio of the region to the fade. Rows with no ink are dropped: a ratio into
   the thread's blank padding is a division into nothing. */
const pair = (lit, bare, floor = 3) => {
  const rows = lit.rows.map((x, i) => ({ y: x.y, on: x.ink, off: bare.rows[i].ink }))
                       .filter(x => x.off > floor);
  return { rows, worst: rows.reduce((a, x) => x.on / x.off < a.on / a.off ? x : a),
           lowest: rows.at(-1) };
};
const pct = x => (x.on / x.off).toFixed(2);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const open = async (q, opts = {}) => {
  const ctx = await br.newContext({
    viewport: opts.viewport || { width: 1280, height: 820 },
    reducedMotion: opts.reduced ? 'reduce' : 'no-preference' });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(urlFor(q), { waitUntil: 'networkidle' });
  await sleep(700);
  await p.evaluate(PAINT_PLATE);
  await sleep(200);
  return { ctx, p };
};
const scrollTo = async (p, to) => {
  await p.evaluate(t => {
    const b = document.querySelector('#qdock .qa > .qbody');
    b.scrollTop = t === 'end' ? b.scrollHeight : t;
  }, to);
  await sleep(700);          // the .45s fades have settled by here
};
const read = async (p, region, skip, file) => {
  const shot = await p.screenshot(file ? { path: `${OUT}/${file}` } : {});
  return p.evaluate(MEASURE, ['data:image/png;base64,' + shot.toString('base64'),
                              region, skip, PLATE]);
};

const { ctx: c1, p } = await open(qs[0]);
if (!(await present(p, '#qdock .qa > .qbody', "the docked question's scroller"))) {
  await br.close(); finish(); process.exit(0);
}
const alien = await p.evaluate(PLATE_IS_ALIEN);
say(`the plate under the dock is rgb(${PLATE}) with the shader hidden`);
ok('the plate is a colour the design never paints (else "still the plate" ' +
   'is satisfiable by the page itself)', alien.length === 0);

/* ── half way down: text passes the box, and the box has nothing behind it ── */
{
  const r0 = await p.evaluate(REGIONS);
  const max = r0.scroll.full - r0.scroll.client;
  ok('the question overflows its column, so text really does pass the box ' +
     '(else every check below is vacuous)', max >= 100);
  await scrollTo(p, Math.round(max / 2));
  const r = await p.evaluate(REGIONS);
  say(`half way (${r.scroll.top} of ${max}): --qfade ${r.fade}px, ` +
      `--qfoot ${r.foot}px, atend=${r.atend}`);
  ok('...and half way down is not the end (else the foot fade is switched off ' +
     'and the plate below proves nothing)', r.atend === false && r.foot > 0);

  const box = await read(p, r.box, r.kids, 'qfade-half.png');
  say(`behind the answer box: ${box.painted} of ${box.sampled} sampled pixels ` +
      `are no longer the plate` +
      (box.worst ? `, first at ${box.worst.px},${box.worst.py} = ` +
      `rgb(${box.worst.rgb})` : '') +
      ` (skipping what paints: ${r.skipped.join(', ')})`);
  // the region has to BE there: if the composer's children covered all of it
  // the count would be zero and the assertion below would pass over anything.
  ok('the answer box has a footprint of its own to look behind ' +
     '(else the check below is vacuous)', box.sampled > 2000);
  // THE ASSERTION HE WOULD MAKE. Not "there is no ::before": that would pass
  // the next band under a different selector. The box's own footprint is
  // still, exactly, the page behind it — which nothing painted there can be.
  ok('nothing is painted between the answer box and the page',
     box.painted === 0);
  /* ...AND THE BOX IS NOT DIMMED EITHER — the other half of "nothing behind
     them", and the trap the obvious fix falls into: move the fade to a mask
     over a scroller that still CONTAINS the box and the box fades with the
     text. Nothing about the band's absence can see that, and a screenshot
     taken with an empty box looks plausible. Measured as the mask making no
     difference at all inside the compose box, children included. */
  {
    const whole = { ...r.box, w: r.box.w, h: r.box.h };
    const lit = await read(p, whole, null);
    await p.evaluate(MASK(false));
    const bare = await read(p, whole, null);
    await p.evaluate(MASK(true));
    // per row, never on the mean over the box — see `pair`
    const { rows, worst, lowest } = pair(lit, bare);
    say(`the answer box itself, ink with the mask vs without it, worst row ` +
        `${worst.y}: ${worst.on}/${worst.off} = ${pct(worst)}; lowest inked ` +
        `row ${lowest.y}, ${(r.box.b - lowest.y).toFixed(1)}px above the box's ` +
        `bottom edge`);
    ok('the box has ink of its own to dim, down to its bottom edge where a ' +
       'foot fade would land (else the check below is vacuous)',
       rows.length >= 10 && r.box.b - lowest.y <= 12);
    ok('...and the fade does not touch the box: no row of it loses ink to ' +
       'the mask', worst.on / worst.off >= 0.9);
  }

  const on = await read(p, r.strip, null);
  await p.evaluate(MASK(false));
  const off = await read(p, r.strip, null, 'qfade-half-nomask.png');
  await p.evaluate(MASK(true));
  const last = rows => rows.at(-1).ink;
  const ratio = (a, b) => b > 0 ? +(a / b).toFixed(2) : null;
  const rows = on.rows.map((x, i) => ({ y: x.y, on: x.ink, off: off.rows[i].ink }));
  say(`the fade strip (${r.strip.h}px, ending at the scroller's edge), ink with ` +
      `the mask vs without it: ` +
      rows.filter((_, i) => i % 8 === 0 || i === rows.length - 1)
          .map(x => `${x.y}:${x.on}/${x.off}`).join(' ') +
      `; ${on.sampled - on.painted} of ${on.sampled} pixels in it are still ` +
      `exactly the plate with the mask on`);
  // the precondition, derived: with the mask off there IS text in this strip,
  // and there is text on its very last row — without which a ratio at the edge
  // is a division into nothing.
  ok('there is text in the strip the fade covers, at its edge included ' +
     '(else every ratio below is vacuous)',
     off.rows.some(x => x.ink > 3) && last(off.rows) > 2);
  ok('the TEXT fades: the mask takes the ink at the scroller\'s edge almost ' +
     'entirely away',
     ratio(last(on.rows), last(off.rows)) <= 0.25);
  // ...and it is a gradient, not a cut: a row a whole fade-depth higher is
  // barely touched, which no single hard edge produces.
  {
    const above = rows.find(x => x.y >= r.strip.y && x.off > 3);
    say(`the top of the strip (${above.y}): ${above.on}/${above.off} = ` +
        `${ratio(above.on, above.off)} of its unmasked ink`);
    ok('...and it is a gradient rather than a cut — the top of the strip keeps ' +
       'most of its ink', ratio(above.on, above.off) >= 0.6);
  }
  /* ...and it fades by going TRANSLUCENT rather than being covered: between
     the glyphs the page is still the page. A band covers the whole strip, so
     it leaves none of it. The floor is a fraction rather than zero because
     glyphs legitimately paint here — it is the one region of this guard where
     they do — and it is printed beside the assertion so a drift is visible. */
  ok('...by going translucent rather than being covered over',
     (on.sampled - on.painted) / on.sampled >= 0.4);
}

/* ── at the end: his own exception, and the last line is untouched ───────── */
{
  await scrollTo(p, 'end');
  const r = await p.evaluate(REGIONS);
  say(`at the end: atend=${r.atend}, --qfoot ${r.foot}px, box ends ` +
      `${r.composeBottom.toFixed(1)}, artifact ends ${r.artifactBottom.toFixed(1)}`);
  ok('at the end of the question the foot fade has lifted entirely',
     r.atend === true && r.foot === 0);
  /* HIS OWN EXCEPTION, measured the same way: with `--qfoot` at zero the mask
     is a no-op over this strip, so turning it off must change NOTHING. An
     absolute ink floor cannot say that — the rows below his last line are the
     thread's own padding and are blank whatever the fade is doing, which is
     how the first version of this check read a perfectly undimmed last line as
     dimmed (peak ink 0.8 over rows that hold no glyphs). */
  const on = await read(p, r.strip, null, 'qfade-end.png');
  await p.evaluate(MASK(false));
  const off = await read(p, r.strip, null);
  await p.evaluate(MASK(true));
  const { rows, worst, lowest } = pair(on, off);
  say(`at the end, the strip's inked rows with the mask vs without it: worst ` +
      `row ${worst.y}: ${worst.on}/${worst.off} = ${pct(worst)}; lowest inked ` +
      `row ${lowest.y}, ${(r.strip.y + r.strip.h - lowest.y).toFixed(1)}px above ` +
      `the scroller's edge; ${on.sampled - on.painted} of ${on.sampled} pixels ` +
      `still the plate`);
  // the rows have to reach the EDGE, or a fade jammed on there would land where
  // nothing is measured. (The strip's own last rows are the thread's padding
  // and hold no glyphs — which is how the first version of this check read a
  // perfectly undimmed last line as dimmed, at peak ink 0.8.)
  ok('his last line reaches the scroller\'s edge, where a fade would land ' +
     '(else the comparison is vacuous)',
     rows.length >= 5 && (r.strip.y + r.strip.h) - lowest.y <= 14);
  ok('the fade has lifted off his last line: no row of it loses ink to the mask',
     worst.on / worst.off >= 0.9);
  ok('...and nothing is painted over it either',
     (on.sampled - on.painted) / on.sampled >= 0.4);
  const box = await read(p, r.box, r.kids);
  ok('...and the box still has nothing behind it at the end',
     box.sampled > 2000 && box.painted === 0);
  ok('...and is still on the artifact\'s bottom line',
     Math.abs(r.composeBottom - r.artifactBottom) <= 1);
}
await c1.close();

/* ── a SHORT question: glued is glued, without sticky ────────────────────── */
{
  const { ctx, p: sp } = await open(qs[qs.length - 1]);
  const r = await sp.evaluate(REGIONS);
  const over = r.scroll.full - r.scroll.client;
  say(`short question ("${qs[qs.length - 1].title.slice(0, 40)}…"): overflow ` +
      `${over}px, box ends ${r.composeBottom.toFixed(1)}, artifact ends ` +
      `${r.artifactBottom.toFixed(1)}`);
  // #305's own failure, restated as a precondition: a question that overflows
  // would be held up by the flow alone and would prove nothing about glue.
  ok('the short question does NOT overflow its column (else this is the same ' +
     'case as above)', over <= 2);
  ok('a short question still ends with its box on the artifact\'s bottom line ' +
     '(#305 (b): 200px of dead space without it)',
     Math.abs(r.composeBottom - r.artifactBottom) <= 1);
  const box = await read(sp, r.box, r.kids, 'qfade-short.png');
  ok('...with nothing painted behind it',
     box.sampled > 2000 && box.painted === 0);
  await ctx.close();
}

/* ── narrow: no scroller, so no fade to paint or to lift ─────────────────── */
{
  const { ctx, p: np } = await open(qs[0], { viewport: { width: 700, height: 900 } });
  const g = await np.evaluate(`(() => {
    const b = document.querySelector('#qdock .qa > .qbody');
    const cs = getComputedStyle(b);
    return { rects: b.getClientRects().length, display: cs.display,
             scrollable: b.scrollHeight > b.clientHeight + 1 };
  })()`);
  say(`narrow (700px): the body wrapper is display:${g.display} with ` +
      `${g.rects} client rects, scrollable=${g.scrollable}`);
  ok('narrow: the wrapper generates no box, so it carries no mask and no ' +
     'scroller', g.rects === 0 && !g.scrollable);
  await ctx.close();
}

/* ── reduced motion: the same rest states, reached without a transition ──── */
{
  const { ctx, p: rp } = await open(qs[0], { reduced: true });
  const r0 = await rp.evaluate(REGIONS);
  const max = r0.scroll.full - r0.scroll.client;
  ok('reduced: the question still overflows (else vacuous)', max >= 100);
  await scrollTo(rp, Math.round(max / 2));
  const mid = await rp.evaluate(REGIONS);
  await scrollTo(rp, 'end');
  const end = await rp.evaluate(REGIONS);
  say(`reduced: half way --qfade ${mid.fade} --qfoot ${mid.foot}; ` +
      `at the end --qfoot ${end.foot}`);
  ok('reduced motion: both fades still reach the same rest states ' +
     '(function, not timing)',
     mid.fade > 0 && mid.foot > 0 && end.foot === 0);
  const box = await read(rp, end.box, end.kids);
  ok('reduced motion: ...and still nothing behind the box',
     box.sampled > 2000 && box.painted === 0);
  await ctx.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finish();
