/* #102 — hard-wrapped source prose must reflow to the reading column.

   The measurement. A Range's getClientRects() returns one rect per inline
   BOX, not per line — a paragraph holding a <code> or an <a> fragments into
   three rects on that line — so rects are first grouped by their top edge
   into real line boxes. Then the signal: how many lines does the block use
   versus the fewest it could (total inked width / column width)? Honouring
   source breaks roughly DOUBLES that ratio, because a 72-column source line
   re-wraps inside a narrower card — which is the "breaks twice into a ragged
   mess" the human screenshotted. Ratio is robust where "are any lines short"
   is not: an unbreakable 37-character path legitimately leaves a half-empty
   line behind it.

   And the control, because a metric that can only pass is worth nothing: the
   same source text is measured twice in the same column, once through preB
   (the old <pre>) and once through mdB. The <pre> must score materially
   worse or the metric is not reading what it claims to.

   And the #158 tail: `/file` branches on WHAT the file is. A .md reflows
   through the same mdB; a source file stays verbatim; and hostile markup
   inside a rendered .md is escaped text, never honoured HTML — this route
   serves arbitrary repo content.
   usage: node reflow.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync, writeFileSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });
import { join } from 'node:path';

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions, /, and /file?p= for .md / .py / hostile markup — A/B of ' +
          'preB vs mdB over a 380/460/545px width sweep, plus nesting and inline ' +
          'rendering on known input, plus link classification',
  traceWindow: 'static reads after ~0.6-0.9s settle per route; hostile-markup ' +
               'dialog listener armed before load; no motion traced',
});

// group a range's rects into line boxes, then lines-used vs lines-needed
const MEASURE = `(sel, root) => {
  const blocks = [...(root || document).querySelectorAll(sel)];
  let used = 0, need = 0;
  for (const el of blocks) {
    const r = document.createRange(); r.selectNodeContents(el);
    const rects = [...r.getClientRects()].filter(x => x.width > 1);
    if (!rects.length) continue;
    const rows = new Map();
    for (const x of rects) {
      const k = Math.round(x.top);
      rows.set(k, (rows.get(k) || 0) + x.width);
    }
    // the column is the WIDEST line the text actually reached, not the box
    // width — hanging indents and padding are not available to the text, and
    // measuring against the box would understate what fits
    const col = Math.max(...rows.values());
    const ink = [...rows.values()].reduce((a, b) => a + b, 0);
    used += rows.size;
    need += Math.max(1, Math.ceil(ink / col));
  }
  return { blocks: blocks.length, used, need,
           ratio: need ? +(used / need).toFixed(3) : 0 };
}`;

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .md prose surface the guard measures first, not a fixed sleep (#428 class)
await waitFor(p, '.md');
const qm = await p.evaluate(`(${MEASURE})('.md p, .md .mdli, .follow')`);

/* A/B control: EVERY live question body, rendered both ways, swept across
   column widths. Threshold-free — the statement is just "the same words, in
   the same column, cost this many line boxes each way".

   The sweep is the point. The source is wrapped at ~72 columns, so the
   damage depends on how much narrower than that the card is: at a wide
   column a <pre> looks almost fine, and at the widths a question card
   actually gets it wraps every single source line a second time. Measuring
   one width would let the fix look either trivial or heroic depending on
   which width you picked. */
const ab = await p.evaluate(`(async () => {
  const d = await (await fetch('/data.json')).json();
  const srcs = d.questions_open.concat(d.answered_entries)
    .map(q => q.body).filter(s => s && s.trim().length > 120);
  const host = document.createElement('div');
  host.style.cssText = 'position:absolute;left:0;top:0;visibility:hidden';
  host.innerHTML = '<div id="ctlPre">' + srcs.map(preB).join('') + '</div>' +
                   '<div id="ctlMd">' + srcs.map(s => mdB(s)).join('') + '</div>';
  document.querySelector('.wrap').appendChild(host);
  const m = ${MEASURE};
  const sweep = [];
  for (const w of [380, 460, 545]) {
    host.style.width = w + 'px';
    void host.offsetWidth;
    sweep.push({ col: w,
      pre: m('pre', document.getElementById('ctlPre')).used,
      md: m('.md p, .md .mdli', document.getElementById('ctlMd')).used });
  }
  host.remove();
  return { bodies: srcs.length, sweep };
})()`);

// nesting is content-dependent on a live page, so assert it on known input
const nest = await p.evaluate(`(() => {
  const src = 'lead in that\\nwraps here\\n- top bullet that\\n  wraps too\\n' +
              '  - deeper bullet\\n\\nnew **para** with *em* and \`a/path.md\`\\n' +
              '\\n\`\`\`\\ncode  kept\\n\`\`\`\\n';
  const host = document.createElement('div');
  host.innerHTML = mdB(src);
  return { paras: host.querySelectorAll('p').length,
           lis: [...host.querySelectorAll('.mdli')]
                  .map(e => e.style.getPropertyValue('--lvl') + ':' + e.textContent),
           fence: (host.querySelector('pre.mdcode') || {}).textContent || null,
           firstPara: (host.querySelector('p') || {}).textContent || null,
           strong: (host.querySelector('strong') || {}).textContent || null,
           em: (host.querySelector('em') || {}).textContent || null,
           code: (host.querySelector('code') || {}).textContent || null,
           links: [...host.querySelectorAll('a')].map(a => a.getAttribute('href')),
           stars: host.textContent.includes('**') };
})()`);

const inline = await p.evaluate(() => ({
  strongs: [...document.querySelectorAll('.md strong')].map(s => s.textContent).slice(0, 4),
  codes: [...document.querySelectorAll('.md code')].map(s => s.textContent).slice(0, 4),
  ems: [...document.querySelectorAll('.md em')].map(s => s.textContent).slice(0, 3),
  // asterisks INSIDE a code span are content, not an unrendered marker
  literalStars: (() => {
    const v = document.querySelector('#view').cloneNode(true);
    v.querySelectorAll('code, pre').forEach(c => c.remove());
    return (v.innerText.match(/\*\*/g) || []).length;
  })(),
  newlinesInParas: [...document.querySelectorAll('.md p')]
            .filter(e => e.textContent.includes('\n')).length,
  follows: [...document.querySelectorAll('.follow')].map(f => f.textContent),
}));
await p.screenshot({ path: `${OUT}/questions-reflowed.png`, fullPage: true });

await p.goto(`${BASE}/`, { waitUntil: 'networkidle' }); await sleep(600);
await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
await sleep(400);
const dm = await p.evaluate(`(${MEASURE})('.md p, .md .mdli, .follow')`);
await p.screenshot({ path: `${OUT}/dashboard-reflowed.png`, fullPage: true });

/* #158: the two halves the frozen fixture cannot hold. A SOURCE file must
   stay verbatim, and a markdown file carrying hostile markup must render
   inert — so both are planted into the shared fixture COPY (the runner
   resets it before every guard, and no guard ever runs against a real
   repo; the target sits beside OUT by the runner's own layout). */
writeFileSync(join(OUT, '..', 'target', 'fixture-src.py'),
  '# a comment, not a heading\n\n\ndef f():\n    return 1  # code stays code\n');
writeFileSync(join(OUT, '..', 'target', 'fixture-hostile.md'),
  '# Title\n\n<script>alert(1)</script>\n\n' +
  '<img src=x onerror="alert(2)">\n\n<iframe src="//evil"></iframe>\n\n' +
  'some **bold** prose\n');

await p.goto(`${BASE}/file?p=DREAMWORK.md`, { waitUntil: 'networkidle' }); await sleep(600);
const md = await p.evaluate(() => ({
  md: document.querySelectorAll('#filebody > .md').length,
  pre: document.querySelectorAll('#filebody > pre').length,
  heads: document.querySelectorAll('#filebody .mdh').length,
}));

await p.goto(`${BASE}/file?p=fixture-src.py`, { waitUntil: 'networkidle' }); await sleep(600);
const src = await p.evaluate(() => ({
  md: document.querySelectorAll('#filebody > .md').length,
  pre: document.querySelectorAll('#filebody > pre').length,
  verbatim: (document.querySelector('#filebody > pre') || {}).textContent || '',
}));

// a dialog can only fire if injected markup was HONOURED; listen before load
let dialog = null;
p.on('dialog', d => { dialog = d.message; d.dismiss(); });
await p.goto(`${BASE}/file?p=fixture-hostile.md`, { waitUntil: 'networkidle' }); await sleep(600);
const hostile = await p.evaluate(() => ({
  scripts: document.querySelectorAll('#filebody script').length,
  iframes: document.querySelectorAll('#filebody iframe').length,
  imgs: document.querySelectorAll('#filebody img').length,
  handlers: [...document.querySelectorAll('#filebody *')]
    .filter(e => [...e.attributes].some(a => /^on/i.test(a.name))).length,
  // the attack is still THERE — as visible, escaped text
  shown: (document.getElementById('filebody') || {}).innerText || '',
  bold: (document.querySelector('#filebody strong') || {}).textContent || null,
}));
await p.screenshot({ path: `${OUT}/file-md.png`, fullPage: true });

ok('no page errors', errs.length === 0);
// the decisive pair: same words, same column, both renderers
ok('A/B: reflow never costs more lines than the <pre>, at any width',
   ab.sweep.every(s => s.md <= s.pre));
// the win peaks in the middle of the sweep, not at its ends: at a very narrow
// column BOTH renderers are ink-limited and wrap constantly, and at a wide one
// the source's own 72 columns nearly fit. It is the widths in between — the
// ones a question card actually gets — where a <pre> wraps every line twice.
ok('A/B: at some real card width the <pre> wraps a second time (>=20% more)',
   Math.max(...ab.sweep.map(s => s.pre / s.md)) >= 1.2);
ok('A/B measured real content (3+ bodies)', ab.bodies >= 3);
// loose bounds on the live pages: a catastrophic regression, not precision
ok('questions prose is not double-wrapped', qm.ratio < 1.45);
ok('dashboard prose is not double-wrapped', dm.ratio < 1.45);
ok('measured enough lines to be meaningful (>40)', qm.used > 40);
// asserted on known input, not on whatever the live file happens to contain
ok('inline **bold**, *em* and `code` render, no literal markers left',
   nest.strong === 'para' && nest.em === 'em' && nest.code === 'a/path.md' &&
   !nest.stars);
ok('an unresolved local-looking code span does not promise a broken /file',
   nest.links.length === 0);
const refs = await p.evaluate(`(() => {
  data.linkable_paths = ['DREAMWORK.md', '.dreamwork/questions.md'];
  const host = document.createElement('div');
  host.innerHTML = mdB('\`DREAMWORK.md\` \`.dreamwork/questions.md\` ' +
                       '\`newerrand.py\` \`github.com/pingdotgg/t3code\`');
  return [...host.querySelectorAll('code')].map(c => ({
    text: c.textContent,
    href: (c.querySelector('a') || {}).getAttribute?.('href') || null
  }));
})()`);
ok('known target paths link locally; unknown ones stay plain code',
   refs[0].href === '/file?p=DREAMWORK.md' &&
   refs[1].href === '/file?p=.dreamwork%2Fquestions.md' &&
   refs[2].href === null);
ok('github.com references link externally, never to /file',
   refs[3].href === 'https://github.com/pingdotgg/t3code');
ok('no literal ** leaks onto the live page', inline.literalStars === 0);
ok('code spans render on live content', inline.codes.length > 0);
ok('joined paragraphs hold no source newline', inline.newlinesInParas === 0);
ok('a wrapped follow-up shows its whole note (#106)',
   inline.follows.some(f => f.length > 60));
ok('wrapped lead-in joins into one paragraph',
   nest.firstPara === 'lead in that wraps here');
ok('bullets survive, wrapped lines joined, nesting kept',
   nest.lis.length === 2 && nest.lis[0] === '0:top bullet that wraps too' &&
   nest.lis[1] === '1:deeper bullet');
ok('a blank line still breaks a paragraph', nest.paras === 2);
ok('a fence stays verbatim', nest.fence === 'code  kept');
ok('/file reflows .md through mdB (#158)',
   md.md === 1 && md.pre === 0 && md.heads > 0);
ok('/file keeps source verbatim in a <pre>',
   src.md === 0 && src.pre === 1 &&
   src.verbatim.includes('# a comment, not a heading\n\n\ndef f():'));
ok('hostile markup at /file renders inert: no script/iframe/img nodes, no handlers, no dialog',
   hostile.scripts === 0 && hostile.iframes === 0 && hostile.imgs === 0 &&
   hostile.handlers === 0 && dialog === null);
ok('hostile markup shows as escaped text while prose still renders',
   hostile.shown.includes('<script>alert(1)</script>') &&
   hostile.bold === 'bold');

notes.push('questions: ' + JSON.stringify(qm));
notes.push('dashboard: ' + JSON.stringify(dm));
notes.push("A/B sweep (same text, both renderers): " + JSON.stringify(ab));
notes.push('nesting: ' + JSON.stringify(nest));
notes.push('inline: ' + JSON.stringify(inline, null, 1));
if (errs.length) notes.push('errors: ' + errs.join(' | '));
await b.close();
finish();
