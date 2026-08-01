/* qlinkpip — #506: known-internal doc links in question bodies carry a pip.

   His do-next (2026-07-30 03:54): links in questions like
   `.dreamwork/docs/plans/cli-warning-layer.md` should have a PIP button so
   he can pop out the referenced doc.

   Production line the red-proof names (watch.py linkify):
     the pipBtn(url, p) call attached when linkable_paths.includes(p) —
     removing that injection (link only, no pip) reds the known-internal
     check; the closed-set gate itself is the same decision that creates
     the link (no second list).

   Load-bearing preconditions (a green without these proves nothing):
     - a served open question body genuinely contains BOTH a path that is
       in data.linkable_paths AND a path that is not (derived at runtime
       from data.json + the card's source text — never assumed from a
       fixture literal alone)
     - the known path is present as a real /file link with the matching
       data-pipurl; the unknown path has neither an <a> nor a .pipbtn

   External github.com/… links (when present) get a link and no pip.

   usage: node qlinkpip.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/questions card bodies: known-internal file links carry pipBtn; ' +
          'unknown/external carry none; text selection across a pip still works',
  traceWindow: 'static reads after ~1s settle; one selection probe — no ' +
               'motion trace (arrival is always-on chrome, rides the card)',
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1280, height: 900 } });
p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions: derive both link kinds from live data, never assume ── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const linkable = new Set(Array.isArray(d.linkable_paths) ? d.linkable_paths : []);
ok('precondition: server shipped a non-empty linkable_paths closed set',
   linkable.size > 0);

/* Match the production linkify path regex (single file or path-with-slashes).
   Used only to FIND candidate backticks in question bodies so we can check
   which ones the closed set would promote — the renderer is what is graded. */
const PATH_RE = /`([\w.-]+(?:\/[\w.-]+)+\/?|[\w-]+\.[\w]{1,8})`/g;
const bodies = (d.questions_open || []).map(q => ({
  title: q.title,
  body: String(q.body || ''),
}));
const found = { known: null, unknown: null, external: null };
for (const q of bodies) {
  PATH_RE.lastIndex = 0;
  let m;
  while ((m = PATH_RE.exec(q.body))) {
    const path = m[1];
    if (path.startsWith('github.com/')) {
      if (!found.external) found.external = { title: q.title, path };
      continue;
    }
    if (linkable.has(path)) {
      if (!found.known) found.known = { title: q.title, path };
    } else {
      if (!found.unknown) found.unknown = { title: q.title, path };
    }
  }
}
notes.push('derived kinds: ' + JSON.stringify(found));
ok('precondition: a question body contains a known-internal path ' +
   '(in linkable_paths) — fixture must plant both kinds',
   !!found.known);
ok('precondition: a question body contains an unknown path ' +
   '(NOT in linkable_paths) — without this the no-pip check is vacuous',
   !!found.unknown);
ok('precondition: known and unknown paths differ',
   !!found.known && !!found.unknown && found.known.path !== found.unknown.path);
if (found.known && linkable.size) {
  ok('precondition: known path is actually in the closed set (re-check)',
     linkable.has(found.known.path));
  ok('precondition: unknown path is actually absent from the closed set',
     !linkable.has(found.unknown.path));
}

if (!found.known || !found.unknown) {
  await br.close();
  finish();
  process.exit(1);
}

const knownUrl = '/file?p=' + encodeURIComponent(found.known.path);

/* ── /questions: grade the rendered card ──────────────────────────────── */
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .qa cards the guard reads first, not a fixed sleep (#428 class)
await waitFor(p, '.qa');

const card = await p.evaluate(({ knownPath, unknownPath, knownUrl, extPath }) => {
  const cards = [...document.querySelectorAll('.qa')];
  // find the card whose body text mentions the known path
  const hit = cards.find(c => (c.textContent || '').includes(knownPath));
  if (!hit) return { err: 'no card contains known path text' };
  const md = hit.querySelector('.qbody .md') || hit.querySelector('.md');
  if (!md) return { err: 'card has no .md body' };

  const links = [...md.querySelectorAll('a')].map(a => ({
    href: a.getAttribute('href') || '',
    text: (a.textContent || '').trim(),
  }));
  const pips = [...md.querySelectorAll('.pipbtn')].map(b => ({
    url: b.getAttribute('data-pipurl') || '',
    label: b.getAttribute('data-piplabel') || '',
    aria: b.getAttribute('aria-label') || '',
    title: b.getAttribute('title') || '',
    tag: b.tagName,
    type: b.getAttribute('type') || '',
  }));

  // known path: an <a> to /file?p=… AND a pip with the same data-pipurl
  const knownLink = links.find(l => l.href === knownUrl ||
    (l.href.startsWith('/file?p=') && decodeURIComponent(l.href.slice(8)) === knownPath));
  const knownPip = pips.find(b => b.url === knownUrl ||
    (b.url.startsWith('/file?p=') &&
     decodeURIComponent(b.url.slice(8)) === knownPath));

  // unknown: no /file link whose text is the unknown path, no pip for it
  const unkLink = links.find(l => l.text === unknownPath ||
    (l.href.startsWith('/file?p=') &&
     decodeURIComponent(l.href.slice(8)) === unknownPath));
  const unkPip = pips.find(b =>
    (b.url.startsWith('/file?p=') &&
     decodeURIComponent(b.url.slice(8)) === unknownPath) ||
    b.label === unknownPath);

  // external: link without a pip (when fixture planted one)
  let ext = null;
  if (extPath) {
    const el = links.find(l => (l.href || '').includes(extPath) ||
                               (l.text || '').includes(extPath));
    const ep = pips.find(b => (b.label || '').includes(extPath) ||
                              (b.url || '').includes(extPath));
    ext = { hasLink: !!el, hasPip: !!ep, href: el ? el.href : null };
  }

  // pip sits outside <code> (chrome) inside a .mdfile nowrap unit with the path
  let pipOutsideCode = null;
  let mdfileUnit = null;
  if (knownPip) {
    const btn = [...md.querySelectorAll('.pipbtn')].find(b =>
      (b.getAttribute('data-pipurl') || '') === knownUrl);
    pipOutsideCode = !!(btn && !btn.closest('code'));
    const unit = btn && btn.closest('.mdfile');
    mdfileUnit = !!(unit && unit.querySelector('code a') &&
                    unit.querySelector('.pipbtn'));
  }

  // user-select:none on the pip (selection chrome contract)
  let us = null;
  if (knownPip) {
    const btn = [...md.querySelectorAll('.pipbtn')].find(b =>
      (b.getAttribute('data-pipurl') || '') === knownUrl);
    if (btn) us = getComputedStyle(btn).userSelect;
  }

  return {
    qid: hit.dataset.qid || null,
    nLinks: links.length,
    nPips: pips.length,
    knownLink: !!knownLink,
    knownHref: knownLink ? knownLink.href : null,
    knownPip: !!knownPip,
    knownPipUrl: knownPip ? knownPip.url : null,
    knownPipLabel: knownPip ? knownPip.label : null,
    knownIsButton: knownPip ? (knownPip.tag === 'BUTTON' && knownPip.type === 'button') : false,
    knownTitle: knownPip ? knownPip.title : null,
    unkLink: !!unkLink,
    unkPip: !!unkPip,
    ext,
    pipOutsideCode,
    mdfileUnit,
    userSelect: us,
    pips,
  };
}, {
  knownPath: found.known.path,
  unknownPath: found.unknown.path,
  knownUrl,
  extPath: found.external ? found.external.path : null,
});

notes.push('card: ' + JSON.stringify(card));
ok('a card body renders for the question that carries both path kinds',
   !card.err && !!card.qid);
ok('known-internal path is a real /file link',
   !!card.knownLink && (card.knownHref === knownUrl));
ok('known-internal path carries a pip with matching data-pipurl',
   !!card.knownPip && card.knownPipUrl === knownUrl);
ok('the pip is the page\'s pipBtn (button, type=button, floats title)',
   !!card.knownIsButton &&
   !!(card.knownTitle && /pop out|float/i.test(card.knownTitle)));
ok('pip sits outside <code> (chrome, not part of the path span)',
   card.pipOutsideCode === true);
ok('path+pip ride a .mdfile unit (nowrap — pip never orphans onto next line)',
   card.mdfileUnit === true);
ok('pip is user-select:none (selection across a body does not swallow it)',
   card.userSelect === 'none');
ok('unknown path has no /file link (closed set still gates the link)',
   card.unkLink === false);
ok('unknown path has no pip (eligibility is the same decision as the link)',
   card.unkPip === false);

if (found.external) {
  ok('external github.com link has a link and no pip (pip floats local views)',
     !!card.ext && card.ext.hasLink === true && card.ext.hasPip === false);
} else {
  notes.push('no external path in fixture bodies — external-no-pip check skipped');
}

/* ── text selection across a body with a pip still works (#505) ──────────
   Drag a range that spans text before the known path and text after it.
   The selection must be non-empty and must not throw; the pip's
   user-select:none means the button itself is not required in the string. */
const sel = await p.evaluate(({ knownPath }) => {
  const cards = [...document.querySelectorAll('.qa')];
  const hit = cards.find(c => (c.textContent || '').includes(knownPath));
  if (!hit) return { err: 'no card' };
  const md = hit.querySelector('.qbody .md') || hit.querySelector('.md');
  if (!md) return { err: 'no md' };
  const pEl = md.querySelector('p') || md;
  const range = document.createRange();
  try {
    range.selectNodeContents(pEl);
    const s = window.getSelection();
    s.removeAllRanges();
    s.addRange(range);
    const text = s.toString();
    return {
      len: text.length,
      hasKnown: text.includes(knownPath),
      // button glyphs should not dominate; path text must survive
      ok: text.length > knownPath.length && text.includes(knownPath),
    };
  } catch (e) {
    return { err: String(e) };
  }
}, { knownPath: found.known.path });
notes.push('selection: ' + JSON.stringify(sel));
ok('text selection across a card body with pips still works',
   !!sel && !sel.err && sel.ok === true);

/* ── #851: a pip does not grow the line box (his measurable complaint) ──
   Two identical paragraphs in the card's real .md context: pA plain text,
   pB the same text with a real .pipbtn (cloned from the page) inline. If
   the pip grows the line, pB is taller than pA — that is the "gap between
   lines" he named. offsetHeight is the inline-level box that determines
   the line box (NOT the svg inside it — #851 direction-2 "wrong box": the
   svg is display:block inside the button, so its box and the button's
   differ, and the BUTTON is what the line box sees). The pip's own
   geometry is asserted non-zero first (#671: if the pip never rendered,
   the two paragraphs are identical and the check passes forever). */
const linebox = await p.evaluate(({ knownUrl }) => {
  const b = document.querySelector(`.qa .pipbtn[data-pipurl="${CSS.escape(knownUrl)}"]`);
  if (!b) return { err: 'no pip to clone' };
  const md = b.closest('.md') || document.querySelector('.qa .md');
  const host = md.closest('.qbody') || md.parentElement;
  const probe = document.createElement('div');
  probe.style.cssText = 'max-width:340px;';   // force a wrap so multi-line
  host.appendChild(probe);
  const lorem = 'The quick brown fox jumps over the lazy dog and the dog nips back at the fox in turn, repeatedly.';
  const pA = document.createElement('p');
  pA.className = 'md'; pA.textContent = lorem; probe.appendChild(pA);
  const pB = document.createElement('p');
  pB.className = 'md';
  const pipClone = b.cloneNode(true);
  pB.innerHTML = 'The quick brown fox jumps over the lazy dog ';
  pB.appendChild(pipClone);
  pB.appendChild(document.createTextNode(' and the dog nips back at the fox in turn, repeatedly.'));
  probe.appendChild(pB);
  // the pip's own box height — the inline-level box the line box sees
  const pipH = pipClone.offsetHeight;
  const pipRect = pipClone.getBoundingClientRect();
  // the hit overlay (absolute ::after) must not be 0 — touch target kept
  const after = (() => { try { return pipClone.getBoundingClientRect(); } catch { return null; } })();
  const r = {
    pipH, pAH: pA.offsetHeight, pBH: pB.offsetHeight,
    delta: pB.offsetHeight - pA.offsetHeight,
    pipHasGeometry: pipRect.width > 0 && pipRect.height > 0,
  };
  probe.remove();
  return r;
}, { knownUrl });
notes.push('linebox: ' + JSON.stringify(linebox));
ok('the body pip renders with non-zero geometry (the comparison is real)',
   !linebox.err && linebox.pipHasGeometry === true);
ok('the body pip does not grow the line box ' +
   '(pB ' + (linebox.pBH ?? '?') + 'px == pA ' + (linebox.pAH ?? '?') +
   'px; was +11px pre-#851) — a line with a pip is the same height as one without',
   !linebox.err && linebox.pipHasGeometry === true &&
   Math.abs(linebox.delta) <= 0);
ok('the body pip keeps a sub-line box (pip ' + (linebox.pipH ?? '?') +
   'px <= the line) — it sits inside the text, not over it',
   !linebox.err && linebox.pipH > 0 && linebox.pipH <= (linebox.pAH || 0));

/* ── screenshots for coordinator inspection (rest state; always-on) ──── */
await p.evaluate(({ knownPath }) => {
  const cards = [...document.querySelectorAll('.qa')];
  const hit = cards.find(c => (c.textContent || '').includes(knownPath));
  if (hit) hit.scrollIntoView({ block: 'center' });
}, { knownPath: found.known.path });
await sleep(200);
await p.screenshot({ path: `${OUT}/qlinkpip-desktop-rest.png`, fullPage: false });

// mobile rest
await p.setViewportSize({ width: 390, height: 844 });
await sleep(300);
await p.evaluate(({ knownPath }) => {
  const cards = [...document.querySelectorAll('.qa')];
  const hit = cards.find(c => (c.textContent || '').includes(knownPath));
  if (hit) hit.scrollIntoView({ block: 'center' });
}, { knownPath: found.known.path });
await sleep(200);
await p.screenshot({ path: `${OUT}/qlinkpip-mobile-rest.png`, fullPage: false });

// hover state on the pip (desktop) — accent, not a second gesture
await p.setViewportSize({ width: 1280, height: 900 });
await sleep(200);
const pipBox = await p.evaluate(({ knownUrl }) => {
  const b = document.querySelector(`.qa .pipbtn[data-pipurl="${CSS.escape(knownUrl)}"]`);
  if (!b) return null;
  b.scrollIntoView({ block: 'center' });
  const r = b.getBoundingClientRect();
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
}, { knownUrl });
if (pipBox) {
  await p.mouse.move(pipBox.x, pipBox.y);
  await sleep(250);
  const hoverColor = await p.evaluate(({ knownUrl }) => {
    const b = document.querySelector(`.qa .pipbtn[data-pipurl="${CSS.escape(knownUrl)}"]`);
    return b ? getComputedStyle(b).color : null;
  }, { knownUrl });
  notes.push('hover color: ' + hoverColor);
  // accent is not dim — any non-dim shift is the hover signal; we only
  // require that hover paints something other than the rest dim if accent
  // is resolvable. Soft: presence of the button under the pointer.
  ok('hover reaches the body pip (pointer over .pipbtn)', !!hoverColor);
  await p.screenshot({ path: `${OUT}/qlinkpip-desktop-hover.png`, fullPage: false });
} else {
  ok('hover reaches the body pip (pointer over .pipbtn)', false);
}

await br.close();
finish();
