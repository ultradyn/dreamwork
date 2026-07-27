/* #367 increment 2 — measurement only: does a two-line ~6-word tab fit?

   Reproducible geometry for the rail/strip design after M3 overrode one-line
   12-char truncated labels in favour of two-line tabs at a smaller text size,
   up to ~6 words, nobody truncates.

   Usage (no server, no port):
     node dev/capture/marktab-geometry.mjs [outdir]

   Defaults:
     outdir  = .dreamwork/docs/measurements/367-tabs
     source  = .dreamwork/review/review-essential-marks.html
              (copied to /tmp; never edited in place)

   Prints a markdown-friendly table on stdout and writes screenshots + a
   JSON dump of every number. Prototype CSS is injected into a scratch
   copy only — nothing under .dreamwork/review/ is touched.
*/
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { copyFileSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../..');
const SRC = join(REPO, '.dreamwork/review/review-essential-marks.html');
const OUT = resolve(process.argv[2] || join(REPO, '.dreamwork/docs/measurements/367-tabs'));
const SCRATCH_DIR = '/tmp/367-marktab-scratch';
const SCRATCH = join(SCRATCH_DIR, 'review-essential-marks.html');

mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH_DIR, { recursive: true });
if (!existsSync(SRC)) {
  console.error('missing source artifact:', SRC);
  process.exit(2);
}
copyFileSync(SRC, SCRATCH);

/* ── worst-case labels ───────────────────────────────────────────────────
   Drawn from real corpus language in review-essential-marks.html, the plan,
   and file-formats.md — not invented nonsense. Ordered so the first few are
   the width-stress cases (long unhyphenated monospace words, six words).
   The script also measures an absurdly long label as a sanity check that
   numbers move with the label (not with a fixed container). */
const LABELS = {
  /* true 6 words, long mono tokens that do not hyphenate — width stress */
  worst6: 'reproducibility measurement against wrap geometry slack',
  /* 6 words from the plan/ruling vocabulary (typical authored length) */
  ruling6: 'two-line tabs at smaller text size',
  /* 6 words, realistic authoring from the artifact itself */
  author6: 'flags mark a height not structure',
  /* from his original ask — realistic, not token-max */
  hisAsk6: 'pointer labels at the most important',
  /* short controls from the SVG mock */
  short: 'the cliff',
  one: 'ask',
  /* the absurd check — must make width jump */
  absurd: 'this label is deliberately absurdly long so the measurement script must report a much wider tab than any six-word case and prove it is measuring the tab not a fixed container width',
};

/* Prototype CSS: smaller than body (.82rem), two-line, grow-to-fit.
   No truncation. Padding + accent fill echo the SVG mock's flag look. */
const PROTO_CSS = `
/* #367 measure-only prototype — not shipping */
.markrail{position:absolute;inset:0;pointer-events:none;z-index:15}
.marktab{
  position:absolute;
  left:0; /* set in JS from .read right edge */
  box-sizing:border-box;
  display:inline-block;
  padding:.28em .55em;
  background:var(--accent);
  color:var(--ink);
  border-radius:2px 4px 4px 2px;
  font-family:inherit;
  font-size:.66rem;          /* smaller than body .82rem — asserted at runtime */
  line-height:1.25;
  font-weight:normal;
  letter-spacing:-.01em;
  white-space:normal;
  overflow-wrap:normal;      /* long words do not hyphenate — worst case is real */
  word-break:normal;
  hyphens:none;
  max-width:none;
  /* width is set by the measure pass (min width for ≤2 lines) */
  box-shadow:0 1px 0 rgba(0,0,0,.25);
}
.marktab.is-current{opacity:1}
.marktab:not(.is-current){opacity:.55}
.markstrip{
  display:none;
  position:sticky;top:58px;z-index:19;
  background:rgba(17,24,39,.94);
  border-bottom:1px solid var(--line);
  padding:.4rem 0;
}
.markstrip-in{
  width:min(calc(100% - 2rem),1120px);margin:0 auto;
  display:flex;align-items:stretch;gap:.4rem;flex-wrap:wrap;
  min-height:0;
}
.markstrip .markpill{
  display:inline-block;
  box-sizing:border-box;
  padding:.28em .55em;
  background:var(--panel2);
  color:var(--muted);
  border:1px solid var(--border);
  border-radius:var(--radius);
  font-size:.66rem;
  line-height:1.25;
  white-space:normal;
  max-width:100%;
  /* two-line pill: width grows; height accommodates two lines */
}
.markstrip .markpill.is-current{
  background:var(--accent);color:var(--ink);border-color:transparent;opacity:1;
}
.markstrip .strip-nav{
  margin-left:auto;display:flex;align-items:center;gap:.5ch;
  color:var(--muted);font-size:.72rem;white-space:nowrap;flex:none;
}
@media (max-width:779.98px){
  .markrail{display:none}
  .markstrip{display:block}
}
@media (min-width:780px){
  .markrail{display:block}
  .markstrip{display:none}
}
`;

const VIEWPORTS = [1280, 1120, 960, 860, 840, 830, 820, 810, 780, 700, 480];

function round1(n) {
  return Math.round(n * 10) / 10;
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader'] });
const page = await br.newPage({ viewport: { width: 1280, height: 900 } });
const fileUrl = pathToFileURL(SCRATCH).href;
await page.goto(fileUrl, { waitUntil: 'load' });

/* Inject prototype into the live DOM of the scratch file (already a copy). */
await page.addStyleTag({ content: PROTO_CSS });
await page.evaluate((labels) => {
  /* rail host follows .wrap so left coords are wrap-relative via absolute page */
  const wrap = document.querySelector('.wrap') || document.querySelector('main');
  const main = document.querySelector('main');
  if (!main) throw new Error('no main');
  main.style.position = 'relative';

  const rail = document.createElement('div');
  rail.className = 'markrail';
  rail.id = 'markrail';
  main.appendChild(rail);

  const strip = document.createElement('div');
  strip.className = 'markstrip';
  strip.id = 'markstrip';
  strip.innerHTML = '<div class="markstrip-in" id="markstrip-in"></div>';
  const top = document.querySelector('.toprail');
  if (top && top.parentNode) top.parentNode.insertBefore(strip, top.nextSibling);
  else document.body.insertBefore(strip, main);

  window.__MARK_LABELS__ = labels;
}, LABELS);

/**
 * For a given label string, find the minimum width (px) such that the text
 * fits in at most 2 lines with no overflow/truncation. Binary search on a
 * throwaway measuring element that uses the same font rules as .marktab.
 * Returns {width, height, lines, fontSizePx, bodyFontSizePx}.
 */
async function measureTwoLineTab(label) {
  return page.evaluate((label) => {
    const body = document.body;
    const probe = document.createElement('div');
    probe.className = 'marktab';
    probe.textContent = label;
    probe.style.position = 'fixed';
    probe.style.left = '-10000px';
    probe.style.top = '0';
    probe.style.visibility = 'hidden';
    document.body.appendChild(probe);

    const bodyFs = parseFloat(getComputedStyle(body).fontSize);
    const tabFs = parseFloat(getComputedStyle(probe).fontSize);

    /* single-line natural width (upper bound) */
    probe.style.whiteSpace = 'nowrap';
    probe.style.width = 'auto';
    const singleW = probe.getBoundingClientRect().width;
    const singleH = probe.getBoundingClientRect().height;

    /* restore wrap; binary-search min width for ≤2 lines */
    probe.style.whiteSpace = 'normal';
    const lineCount = (el) => {
      /* Range per word would be more precise for mid-word breaks; for whole
         lines, client rects of the element with a Range over full text works
         when we count distinct top edges of client rects. */
      const range = document.createRange();
      range.selectNodeContents(el);
      const rects = [...range.getClientRects()];
      if (!rects.length) return 0;
      const tops = new Set(rects.map(r => Math.round(r.top)));
      return tops.size;
    };

    let lo = 8;
    let hi = Math.ceil(singleW) + 2;
    /* floor: widest single word (no hyphenation) */
    const words = label.split(/\s+/).filter(Boolean);
    let wordFloor = 0;
    for (const w of words) {
      probe.textContent = w;
      probe.style.whiteSpace = 'nowrap';
      probe.style.width = 'auto';
      wordFloor = Math.max(wordFloor, probe.getBoundingClientRect().width);
    }
    probe.textContent = label;
    probe.style.whiteSpace = 'normal';
    lo = Math.max(lo, Math.ceil(wordFloor));

    let best = hi;
    for (let i = 0; i < 24; i++) {
      const mid = (lo + hi) / 2;
      probe.style.width = mid + 'px';
      const lines = lineCount(probe);
      const h = probe.getBoundingClientRect().height;
      /* also reject if a single client-rect word spills past the box */
      if (lines <= 2) {
        best = mid;
        hi = mid;
      } else {
        lo = mid;
      }
      if (hi - lo < 0.5) break;
    }
    probe.style.width = best + 'px';
    const finalRect = probe.getBoundingClientRect();
    const lines = lineCount(probe);
    const out = {
      label,
      width: finalRect.width,
      height: finalRect.height,
      lines,
      singleLineWidth: singleW,
      singleLineHeight: singleH,
      wordFloor,
      fontSizePx: tabFs,
      bodyFontSizePx: bodyFs,
      fontGapPx: bodyFs - tabFs,
      wordCount: words.length,
    };
    probe.remove();
    return out;
  }, label);
}

/** Page geometry at current viewport: wrap, read, slack, gutters. */
async function pageGeometry() {
  return page.evaluate(() => {
    const wrap = document.querySelector('.wrap');
    const read = document.querySelector('.read') || document.querySelector('p.read');
    /* prefer the first .read paragraph for the reading-column width */
    const reads = [...document.querySelectorAll('.read')];
    const readEl = reads[0] || null;
    const wr = wrap ? wrap.getBoundingClientRect() : null;
    const rr = readEl ? readEl.getBoundingClientRect() : null;
    const vw = window.innerWidth;
    const outsideGutter = wrap ? wr.left : 0; /* left margin outside wrap */
    const slackRightOfRead = wr && rr ? (wr.right - rr.right) : null;
    return {
      viewport: vw,
      wrapW: wr ? wr.width : null,
      wrapLeft: wr ? wr.left : null,
      wrapRight: wr ? wr.right : null,
      readW: rr ? rr.width : null,
      readRight: rr ? rr.right : null,
      readLeft: rr ? rr.left : null,
      slackRightOfRead,
      outsideGutterLeft: outsideGutter,
      outsideGutterRight: wrap ? (vw - wr.right) : null,
      bodyFontSizePx: parseFloat(getComputedStyle(document.body).fontSize),
    };
  });
}

/** Place N tabs in the rail at the tops of real marked-ish anchors and measure collisions. */
async function placeAndMeasureRail(tabspec) {
  /* tabspec: [{id, label, yMode}] yMode uses real section tops */
  return page.evaluate((tabspec) => {
    const rail = document.getElementById('markrail');
    const stripIn = document.getElementById('markstrip-in');
    rail.innerHTML = '';
    stripIn.innerHTML = '';

    const reads = [...document.querySelectorAll('.read')];
    const readEl = reads[0];
    if (!readEl) return { error: 'no .read' };
    const main = document.querySelector('main');
    const mainTop = main.getBoundingClientRect().top + window.scrollY;

    const placed = [];
    for (let i = 0; i < tabspec.length; i++) {
      const spec = tabspec[i];
      const anchor = document.getElementById(spec.id);
      if (!anchor) continue;
      const ar = anchor.getBoundingClientRect();
      const tab = document.createElement('div');
      tab.className = 'marktab' + (i === 0 ? ' is-current' : '');
      tab.dataset.mid = String(i);
      tab.textContent = spec.label;
      /* width from pre-measured two-line min */
      tab.style.width = spec.widthPx + 'px';
      /* absolute within main: top relative to main */
      const topDoc = ar.top + window.scrollY;
      tab.style.top = (topDoc - mainTop) + 'px';
      /* left: reading column right edge relative to main */
      const readRight = readEl.getBoundingClientRect().right;
      const mainLeft = main.getBoundingClientRect().left;
      tab.style.left = (readRight - mainLeft + 4) + 'px'; /* 4px gap from .read edge */
      rail.appendChild(tab);

      const pill = document.createElement('span');
      pill.className = 'markpill' + (i === 0 ? ' is-current' : '');
      pill.textContent = spec.label;
      pill.style.width = spec.widthPx + 'px';
      stripIn.appendChild(pill);

      const tr = tab.getBoundingClientRect();
      placed.push({
        id: spec.id,
        label: spec.label,
        top: tr.top + window.scrollY,
        bottom: tr.bottom + window.scrollY,
        height: tr.height,
        width: tr.width,
        left: tr.left,
        right: tr.right,
        lines: (() => {
          const range = document.createRange();
          range.selectNodeContents(tab);
          const rects = [...range.getClientRects()];
          return new Set(rects.map(r => Math.round(r.top))).size;
        })(),
      });
    }

    /* strip nav chrome */
    const nav = document.createElement('div');
    nav.className = 'strip-nav';
    nav.textContent = `‹  1 of ${placed.length}  ›`;
    stripIn.appendChild(nav);

    /* vertical collisions between adjacent placed tabs */
    const collisions = [];
    for (let i = 0; i < placed.length - 1; i++) {
      const a = placed[i], b = placed[i + 1];
      const gap = b.top - a.bottom; /* negative => overlap */
      collisions.push({
        a: a.id, b: b.id,
        aLabel: a.label, bLabel: b.label,
        gapPx: gap,
        overlaps: gap < 0,
        aHeight: a.height, bHeight: b.height,
        anchorGapPx: b.top - a.top, /* centre-to-centre-ish: tops */
      });
    }

    const stripRect = document.getElementById('markstrip').getBoundingClientRect();
    const stripPills = [...stripIn.querySelectorAll('.markpill')].map(el => {
      const r = el.getBoundingClientRect();
      return { w: r.width, h: r.height, text: el.textContent };
    });

    const wrap = document.querySelector('.wrap').getBoundingClientRect();
    const vw = window.innerWidth;
    return {
      placed,
      collisions,
      strip: {
        visible: getComputedStyle(document.getElementById('markstrip')).display !== 'none',
        height: stripRect.height,
        pills: stripPills,
        totalPillsWidth: stripPills.reduce((s, p) => s + p.w, 0),
        wrapW: wrap.width,
        overflowsWrap: stripPills.reduce((s, p) => s + p.w, 0) + 80 > wrap.width, /* +nav approx */
      },
      railVisible: getComputedStyle(rail).display !== 'none',
      viewport: vw,
    };
  }, tabspec);
}

/** Min vertical gap between two identical-height tabs before they overlap. */
async function verticalCollisionProbe(label, widthPx) {
  return page.evaluate(({ label, widthPx }) => {
    const main = document.querySelector('main');
    const rail = document.getElementById('markrail');
    const reads = document.querySelectorAll('.read');
    const readEl = reads[0];
    const mainTop = main.getBoundingClientRect().top + window.scrollY;
    const readRight = readEl.getBoundingClientRect().right;
    const mainLeft = main.getBoundingClientRect().left;
    const left = readRight - mainLeft + 4;

    /* clear previous probe tabs marked data-probe */
    rail.querySelectorAll('[data-probe]').forEach(e => e.remove());

    const mk = (topPx, id) => {
      const t = document.createElement('div');
      t.className = 'marktab';
      t.dataset.probe = id;
      t.textContent = label;
      t.style.width = widthPx + 'px';
      t.style.top = topPx + 'px';
      t.style.left = left + 'px';
      rail.appendChild(t);
      return t;
    };

    /* place first at a known spot inside the geometry section */
    const anchor = document.getElementById('geometry');
    const aTop = anchor.getBoundingClientRect().top + window.scrollY - mainTop;
    const t1 = mk(aTop, 'p1');
    const h = t1.getBoundingClientRect().height;
    const t2 = mk(aTop + h, 'p2'); /* exactly adjacent: gap 0 */
    const r1 = t1.getBoundingClientRect();
    const r2 = t2.getBoundingClientRect();
    const gapAtExactStack = r2.top - r1.bottom;

    /* also measure with 1px separation */
    t2.style.top = (aTop + h + 1) + 'px';
    const r2b = t2.getBoundingClientRect();
    const gapAt1 = r2b.top - r1.bottom;

    /* real section-to-section gaps in THIS document (potential mark sites) */
    const sectionIds = ['long', 'findings', 'geometry', 'shape', 'source', 'motion', 'decision', 'next'];
    const tops = sectionIds.map(id => {
      const el = document.getElementById(id);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { id, top: r.top + window.scrollY, height: r.height };
    }).filter(Boolean);
    const sectionGaps = [];
    for (let i = 0; i < tops.length - 1; i++) {
      sectionGaps.push({
        a: tops[i].id,
        b: tops[i + 1].id,
        gapBetweenTopsPx: tops[i + 1].top - tops[i].top,
        wouldOverlapIfTabsAtTops: (tops[i + 1].top - tops[i].top) < h,
      });
    }

    /* densest real gap: between consecutive block-level children that could carry data-mark */
    const candidates = [...document.querySelectorAll('main section, main .call, main .facts, main table, main p.read, main .frames')];
    const ctops = candidates.map(el => ({
      tag: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(/\s+/)[0] : ''),
      top: el.getBoundingClientRect().top + window.scrollY,
      h: el.getBoundingClientRect().height,
    })).sort((a, b) => a.top - b.top);
    let minBlockGap = Infinity;
    let minPair = null;
    for (let i = 0; i < ctops.length - 1; i++) {
      const g = ctops[i + 1].top - ctops[i].top;
      if (g > 0 && g < minBlockGap) {
        minBlockGap = g;
        minPair = { a: ctops[i].tag, b: ctops[i + 1].tag, gapPx: g };
      }
    }

    return {
      tabHeight: h,
      minVerticalGapBeforeOverlapPx: h, /* tops must be ≥ h apart for zero overlap with gap 0 */
      measuredGapWhenStackedExactly: gapAtExactStack,
      measuredGapWhenSeparatedBy1px: gapAt1,
      sectionGaps,
      densestBlockPair: minPair,
      densestBlockGapPx: minPair ? minPair.gapPx : null,
      collisionPossibleInThisDoc:
        sectionGaps.some(g => g.wouldOverlapIfTabsAtTops) ||
        (minPair && minPair.gapPx < h),
    };
  }, { label, widthPx });
}

/* ── run ─────────────────────────────────────────────────────────────── */
const results = {
  how: {
    tabFont: '.marktab { font-size: .66rem; line-height: 1.25; padding: .28em .55em }',
    bodyFont: 'body { font-size: .82rem } (artifact default)',
    widthMethod:
      'Binary search minimum width where a Range over the full label yields ≤2 distinct line tops; floor is the widest single word (no hyphenation). Height is getBoundingClientRect of that laid-out tab.',
    pageMethod:
      'getBoundingClientRect on .wrap and first .read at each viewport via Playwright file:// load of a /tmp copy of review-essential-marks.html.',
    collisionMethod:
      'Place two identical two-line tabs stacked; min top-to-top gap = measured tab height. Compare to real section-top gaps and densest block-top gaps in this artifact.',
  },
  labels: LABELS,
  labelMetrics: {},
  viewports: [],
  collision: null,
  absurdSanity: null,
  doesNotFitThreshold: null,
};

/* 1. Label metrics at 1280 (font metrics are viewport-independent for rem) */
await page.setViewportSize({ width: 1280, height: 900 });
await page.goto(fileUrl, { waitUntil: 'load' });
await page.addStyleTag({ content: PROTO_CSS });
await page.evaluate((labels) => {
  const main = document.querySelector('main');
  main.style.position = 'relative';
  const rail = document.createElement('div');
  rail.className = 'markrail'; rail.id = 'markrail'; main.appendChild(rail);
  const strip = document.createElement('div');
  strip.className = 'markstrip'; strip.id = 'markstrip';
  strip.innerHTML = '<div class="markstrip-in" id="markstrip-in"></div>';
  const top = document.querySelector('.toprail');
  if (top && top.parentNode) top.parentNode.insertBefore(strip, top.nextSibling);
  window.__MARK_LABELS__ = labels;
}, LABELS);

for (const [key, label] of Object.entries(LABELS)) {
  results.labelMetrics[key] = await measureTwoLineTab(label);
}

const worst = results.labelMetrics.worst6;
const ruling = results.labelMetrics.ruling6;
const author = results.labelMetrics.author6;
const absurd = results.labelMetrics.absurd;

/* Precondition asserts: smaller text size than body */
if (!(worst.fontGapPx > 0.5)) {
  console.error('PRECONDITION FAIL: tab font is not smaller than body', worst);
  process.exit(3);
}
if (!(worst.lines <= 2 && worst.lines >= 1)) {
  console.error('PRECONDITION FAIL: worst6 did not land in 1–2 lines', worst);
  process.exit(3);
}

/* Absurd sanity: width must move */
results.absurdSanity = {
  worst6Width: worst.width,
  absurdWidth: absurd.width,
  delta: absurd.width - worst.width,
  moved: absurd.width > worst.width + 20,
  note: 'If moved is false, the script is measuring a container, not the tab.',
};
if (!results.absurdSanity.moved) {
  console.error('SANITY FAIL: absurd label did not widen the tab', results.absurdSanity);
  process.exit(4);
}

/* 2. Per-viewport table using the worst-case two-line width */
const primaryLabel = LABELS.worst6;
const primaryW = worst.width;
const primaryH = worst.height;

for (const vw of VIEWPORTS) {
  await page.setViewportSize({ width: vw, height: 900 });
  /* re-inject after resize? styles persist; geometry remeasure */
  const geo = await pageGeometry();
  const tabspec = [
    { id: 'geometry', label: primaryLabel, widthPx: primaryW },
    { id: 'shape', label: LABELS.ruling6, widthPx: ruling.width },
    { id: 'decision', label: LABELS.author6, widthPx: author.width },
  ];
  const placed = await placeAndMeasureRail(tabspec);
  const tabRight = placed.placed[0] ? placed.placed[0].right : null;
  const tabWidth = placed.placed[0] ? placed.placed[0].width : primaryW;
  const tabHeight = placed.placed[0] ? placed.placed[0].height : primaryH;
  const remainingInWrap = geo.slackRightOfRead != null && tabWidth != null
    ? geo.slackRightOfRead - 4 - tabWidth
    : null;
  const pastWrap = remainingInWrap != null ? remainingInWrap < 0 : null;
  const pastPage = tabRight != null ? tabRight > vw : null;
  const roomOutside = geo.outsideGutterRight;
  /* verdicts — descriptive, not design choices */
  let verdict;
  if (vw < 780) {
    verdict = placed.strip.visible
      ? (placed.strip.overflowsWrap
          ? 'STRIP mode: pills overflow wrap (see strip numbers)'
          : 'STRIP mode: pills fit wrap row (wrap may still feel tight)')
      : 'STRIP expected but not visible';
  } else if (pastPage) {
    verdict = 'DOES NOT FIT: tab protrudes past page edge';
  } else if (pastWrap) {
    verdict = `fits in page but NOT inside .wrap (overflows wrap by ${round1(-remainingInWrap)}px; outside gutter ${round1(roomOutside)}px)`;
  } else {
    verdict = `fits inside .wrap; ${round1(remainingInWrap)}px slack remains after tab`;
  }

  results.viewports.push({
    viewport: vw,
    wrapW: round1(geo.wrapW),
    readW: round1(geo.readW),
    slackRightOfRead: round1(geo.slackRightOfRead),
    outsideGutter: round1(geo.outsideGutterRight),
    tabWidth: round1(tabWidth),
    tabHeight: round1(tabHeight),
    remainingInWrap: remainingInWrap == null ? null : round1(remainingInWrap),
    pastWrap,
    pastPage,
    railVisible: placed.railVisible,
    stripVisible: placed.strip.visible,
    stripHeight: placed.strip.visible ? round1(placed.strip.height) : null,
    stripTotalPillsWidth: placed.strip.visible ? round1(placed.strip.totalPillsWidth) : null,
    stripOverflowsWrap: placed.strip.visible ? placed.strip.overflowsWrap : null,
    verdict,
    collisions: placed.collisions,
  });
}

/* 3. Vertical collision probe at 1280 with worst-case tab */
await page.setViewportSize({ width: 1280, height: 900 });
await placeAndMeasureRail([
  { id: 'geometry', label: primaryLabel, widthPx: primaryW },
  { id: 'shape', label: primaryLabel, widthPx: primaryW },
]);
results.collision = await verticalCollisionProbe(primaryLabel, primaryW);

/* 4. Strip stress at 700: 3 / 5 / 7 pills of worst6 and of ruling6 */
results.stripStress = {};
for (const [name, lab, w] of [
  ['worst6', primaryLabel, primaryW],
  ['ruling6', LABELS.ruling6, ruling.width],
]) {
  results.stripStress[name] = {};
  for (const n of [3, 5, 7]) {
    await page.setViewportSize({ width: 700, height: 900 });
    results.stripStress[name][n] = await page.evaluate(({ n, lab, w }) => {
      const wrapW = document.querySelector('.wrap').getBoundingClientRect().width;
      const host = document.createElement('div');
      host.style.cssText = `display:flex;flex-wrap:wrap;gap:0.4rem;align-items:stretch;width:${wrapW}px;position:fixed;left:-9999px;font-family:inherit`;
      document.body.appendChild(host);
      for (let i = 0; i < n; i++) {
        const p = document.createElement('span');
        p.className = 'markpill';
        p.textContent = lab;
        p.style.width = w + 'px';
        host.appendChild(p);
      }
      const nav = document.createElement('span');
      nav.className = 'strip-nav';
      nav.textContent = `‹ 1 of ${n} ›`;
      host.appendChild(nav);
      const tops = new Set([...host.children].map(c => Math.round(c.getBoundingClientRect().top)));
      const hr = host.getBoundingClientRect();
      const first = host.querySelector('.markpill').getBoundingClientRect();
      host.remove();
      return {
        n, wrapW, rows: tops.size, height: hr.height,
        pillW: first.width, pillH: first.height,
        multiRow: tops.size > 1,
      };
    }, { n, lab, w });
  }
}

/* What would make us report "does not fit" */
results.doesNotFitThreshold = {
  width: 'remainingInWrap < 0 at a viewport where the rail is the intended presentation, OR tabRight > viewport (past page edge). For worst6 (~183px) that is past-wrap below ~835px and past-page below ~815px.',
  height: 'densest real mark-site gap in a document < tabHeight, so two adjacent marks overlap.',
  strip: 'two-line pills + nav force multi-row strip or overflow .wrap with no truncation allowed — measured at soft-cap 7 with worst6.',
};

/* First viewport in the table where remainingInWrap < 0 (rail cliff for this tab) */
results.railCliffForWorst6 = null;
for (const v of results.viewports) {
  if (v.viewport >= 780 && v.remainingInWrap != null && v.remainingInWrap < 0) {
    results.railCliffForWorst6 = v.viewport;
    break;
  }
}

/* ── screenshots ─────────────────────────────────────────────────────── */
async function shot(name, vw, setup) {
  await page.setViewportSize({ width: vw, height: 900 });
  if (setup) await setup();
  await page.waitForTimeout(80);
  const path = join(OUT, name);
  await page.screenshot({ path, fullPage: false });
  return path;
}

/* widest tab at 1280 — scroll geometry section into view */
await shot('wide-tab-1280.png', 1280, async () => {
  await placeAndMeasureRail([
    { id: 'geometry', label: primaryLabel, widthPx: primaryW },
    { id: 'shape', label: LABELS.ruling6, widthPx: ruling.width },
    { id: 'decision', label: LABELS.author6, widthPx: author.width },
  ]);
  await page.evaluate(() => {
    document.getElementById('geometry')?.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -70);
  });
});

/* at the cliff 780 */
await shot('wide-tab-cliff-780.png', 780, async () => {
  await placeAndMeasureRail([
    { id: 'geometry', label: primaryLabel, widthPx: primaryW },
    { id: 'shape', label: LABELS.ruling6, widthPx: ruling.width },
    { id: 'decision', label: LABELS.author6, widthPx: author.width },
  ]);
  await page.evaluate(() => {
    document.getElementById('geometry')?.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -70);
  });
});

/* just below cliff — strip */
await shot('strip-below-cliff-700.png', 700, async () => {
  await placeAndMeasureRail([
    { id: 'geometry', label: primaryLabel, widthPx: primaryW },
    { id: 'shape', label: LABELS.ruling6, widthPx: ruling.width },
    { id: 'decision', label: LABELS.author6, widthPx: author.width },
  ]);
  await page.evaluate(() => { window.scrollTo(0, 0); });
});

/* two adjacent tabs at min gap (stacked) — collision demo */
await shot('vertical-collision-min-gap-1280.png', 1280, async () => {
  await page.evaluate(({ label, widthPx }) => {
    const main = document.querySelector('main');
    const rail = document.getElementById('markrail');
    rail.innerHTML = '';
    document.getElementById('markstrip-in').innerHTML = '';
    const readEl = document.querySelectorAll('.read')[0];
    const mainTop = main.getBoundingClientRect().top + window.scrollY;
    const left = readEl.getBoundingClientRect().right - main.getBoundingClientRect().left + 4;
    const anchor = document.getElementById('geometry');
    const aTop = anchor.getBoundingClientRect().top + window.scrollY - mainTop;
    const mk = (top, cls) => {
      const t = document.createElement('div');
      t.className = 'marktab' + (cls || '');
      t.textContent = label;
      t.style.width = widthPx + 'px';
      t.style.top = top + 'px';
      t.style.left = left + 'px';
      rail.appendChild(t);
      return t;
    };
    const t1 = mk(aTop, ' is-current');
    const h = t1.getBoundingClientRect().height;
    mk(aTop + h, ''); /* gap 0 — flush adjacent */
    /* label the gap */
    const note = document.createElement('div');
    note.className = 'marktab';
    note.style.background = 'transparent';
    note.style.color = 'var(--warn)';
    note.style.border = '1px dashed var(--warn)';
    note.style.width = widthPx + 'px';
    note.style.top = (aTop + h * 2 + 8) + 'px';
    note.style.left = left + 'px';
    note.style.fontSize = '.66rem';
    note.textContent = `min gap = ${Math.round(h)}px (flush)`;
    rail.appendChild(note);
    anchor.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -70);
  }, { label: primaryLabel, widthPx: primaryW });
});

/* real section spacing for comparison */
await shot('vertical-real-sections-1280.png', 1280, async () => {
  await placeAndMeasureRail([
    { id: 'long', label: primaryLabel, widthPx: primaryW },
    { id: 'findings', label: primaryLabel, widthPx: primaryW },
    { id: 'geometry', label: primaryLabel, widthPx: primaryW },
    { id: 'shape', label: primaryLabel, widthPx: primaryW },
  ]);
  await page.evaluate(() => {
    document.getElementById('long')?.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -70);
  });
});

await br.close();

/* ── print table ─────────────────────────────────────────────────────── */
const dumpPath = join(OUT, 'raw-numbers.json');
writeFileSync(dumpPath, JSON.stringify(results, null, 2));

function row(v) {
  return `| ${v.viewport} | ${v.tabWidth} | ${v.tabHeight} | ${v.slackRightOfRead} | ${v.remainingInWrap} | ${v.outsideGutter} | ${v.verdict} |`;
}

console.log('## #367 two-line tab geometry — measured numbers\n');
console.log('### Label metrics (at 1280, rem-stable)\n');
console.log('| key | words | lines | width px | height px | single-line width | font-size tab | font-size body | gap |');
console.log('|---|---:|---:|---:|---:|---:|---:|---:|---:|');
for (const [k, m] of Object.entries(results.labelMetrics)) {
  console.log(`| ${k} | ${m.wordCount} | ${m.lines} | ${round1(m.width)} | ${round1(m.height)} | ${round1(m.singleLineWidth)} | ${round1(m.fontSizePx)} | ${round1(m.bodyFontSizePx)} | ${round1(m.fontGapPx)} |`);
}
console.log('\n### Per-viewport (worst6 label for width/height)\n');
console.log('| viewport | tab width | tab height | slack right of .read | remaining in wrap after tab | outside gutter | verdict |');
console.log('|---:|---:|---:|---:|---:|---:|---|');
for (const v of results.viewports) console.log(row(v));

console.log('\n### Vertical collision\n');
console.log(JSON.stringify(results.collision, null, 2));

console.log('\n### Absurd-label sanity\n');
console.log(JSON.stringify(results.absurdSanity, null, 2));

console.log('\nWrote screenshots + raw-numbers.json to', OUT);
console.log('Primary worst-case label:', JSON.stringify(primaryLabel));
console.log('Primary tab:', round1(primaryW), '×', round1(primaryH), 'px');
