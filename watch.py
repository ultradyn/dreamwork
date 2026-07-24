#!/usr/bin/env python3
"""watch.py — read-only localhost dashboard for a running dreamloop.

Plan: .dreamwork/docs/plans/watch-py.md (human-authorized 2026-07-25).
Stdlib only. Binds 127.0.0.1 exclusively. Read-only with ONE deliberate
exception (human-authorized 2026-07-25): POST /answer appends a marked
answer block under an open question in questions.md — the loop folds it
on its next tick. No other write paths exist.
"""

import argparse
import http.server
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

# Server generation: a fresh value every time this process (re)starts, so a
# client can tell "same server, data changed" from "server rebuilt, reload
# the shell". Sent on /mtime; the client reloads when it changes. This alone
# (no --autoreload) fixes stale open tabs after a manual restart/redeploy.
GENERATION = "%.6f" % time.time()

# Design tokens + shared shell: every watch page renders through these,
# so a redesign is a token/component edit, not a page-by-page hunt.
STYLE = """<style>
  :root { --bg:#0b0f19; --panel:#111827; --panel2:#1e293b;
    --line:#1f2937; --border:#334155; --text:#d1d5db; --bright:#f3f4f6;
    --lit:#e5e7eb; --muted:#9ca3af; --dim:#6b7280; --dimmer:#4b5563;
    --accent:#a5b4fc; --space:1.6rem; --radius:4px; }
  body { background:var(--bg); color:var(--text); margin:0;
         padding:2.5rem 1rem;
         font-family:ui-monospace,'JetBrains Mono',monospace; font-size:.8rem; }
  .wrap { max-width:72ch; margin:0 auto; position:relative; }
  header { color:var(--bright); font-size:1rem; margin-bottom:.25rem; }
  #meta { color:var(--dim); margin-bottom:2rem; }
  #meta .q { color:var(--accent); }
  .label { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
           font-size:.7rem; margin:var(--space) 0 .5rem; }
  details { margin:.25rem 0; }
  summary { cursor:pointer; color:var(--lit); list-style:none; }
  summary::before { content:"+ "; color:var(--dim); }
  details[open] > summary::before { content:"- "; }
  .age { color:var(--dim); margin-left:.5rem; }
  pre { white-space:pre-wrap; color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  .git div { color:var(--dim); }
  .git .maint { color:var(--accent); }
  .dim { color:var(--dimmer); }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .qa { margin:.6rem 0 1rem; }
  .qa .qt { color:var(--lit); }
  .qa textarea { width:100%; background:var(--panel); color:var(--text);
    border:1px solid var(--line); border-radius:var(--radius); font:inherit;
    padding:.4rem; margin:.3rem 0; min-height:3rem; box-sizing:border-box; }
  .qa button { background:var(--panel2); color:var(--accent);
    border:1px solid var(--border); border-radius:var(--radius);
    font:inherit; padding:.25rem .8rem; cursor:pointer; }
  /* answered-awaiting-fold: a quiet accent rail marks it apart from open
     questions; no input box, the answer shown plainly. */
  .qa.answered { border-left:2px solid var(--accent); padding-left:.9rem;
    margin-left:-1.1rem; opacity:.82; }
  .qa.answered .qt::before { content:"✓ "; color:var(--accent); }
  .anstag { color:var(--dim); text-transform:uppercase; letter-spacing:.07em;
    font-size:.65rem; margin:.35rem 0 .15rem; }
  .anstext { color:var(--muted); white-space:pre-wrap; }
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
  #devbox { position:fixed; top:.6rem; right:.8rem; z-index:10;
            color:var(--dimmer); font-size:.7rem; text-align:right; }
  #devbox canvas { display:block; margin-top:.25rem; opacity:.55; }
  #layerhint { position:fixed; bottom:1rem; right:1rem; z-index:10;
    color:var(--accent); background:rgba(17,24,39,.82);
    border:1px solid var(--line); border-radius:var(--radius);
    padding:.25rem .6rem; font-size:.7rem; opacity:0;
    transition:opacity .5s ease; pointer-events:none;
    letter-spacing:.04em; }
  /* single-document view swaps: the outgoing view liquifies into a
     swirling mist (SVG turbulence displacement + blur, enveloped per-frame
     in crossfade()) and drifts up as it fades; the incoming view coalesces
     from the same mist and settles perfectly crisp. Opacity + transform
     ride these CSS transitions; the mist (filter) is JS-driven so the
     middle of the dissolve lingers hazy. The shader stirs in sympathy. */
  #view { transition:opacity .9s cubic-bezier(.32,.12,.2,1),
                     transform .9s cubic-bezier(.32,.12,.2,1);
          transform-origin:50% 42%; will-change:opacity, transform, filter; }
  #view.enter { opacity:0; transform:translateY(12px) scale(.986); }
  .ghost { position:absolute; inset:0; z-index:1; pointer-events:none;
           opacity:1; transform-origin:50% 42%;
           transition:opacity 1.05s cubic-bezier(.4,0,.66,.38),
                      transform 1.05s cubic-bezier(.4,0,.66,.38); }
  .ghost.out { opacity:0; transform:translateY(-16px) scale(1.035); }
  @media (prefers-reduced-motion: reduce) {
    #view, .ghost { transition:none; }
  }
  /* review view: the artifact fills the main column; the originating
     question docks beside it (sticky) so it can be answered with the
     review in front of you. Wider than the 72ch reading column. */
  body.review .wrap { max-width:1360px; }
  #reviewwrap { display:grid; gap:1.3rem; align-items:start; margin-top:1rem;
    grid-template-columns:minmax(0,1fr) minmax(24ch,34ch); }
  #reviewwrap.nodock { grid-template-columns:minmax(0,1fr); }
  #reviewframe { width:100%; height:74vh; border:1px solid var(--border);
    border-radius:var(--radius); background:var(--bg); display:block; }
  .revname { color:var(--dim); margin-left:.6rem; font-size:.8rem; }
  .qdock { position:sticky; top:1rem; will-change:transform, filter; }
  .qdock .label { margin-top:0; }
  @media (max-width:900px) {
    #reviewwrap { grid-template-columns:minmax(0,1fr); }
    .qdock { position:static; }
    #reviewframe { height:60vh; }
  }
  /* command palette: the + opener sits in the heading's left gutter; the
     panel it toggles drifts in through a soft blur (the dream language),
     not a hard pop. reduced-motion just shows/hides. */
  .htitlebar { display:flex; align-items:baseline; gap:.55rem; }
  .htitle { display:inline; }
  #cmdplus { flex:none; align-self:center; margin-left:-2.4rem;
    width:1.7rem; height:1.7rem; display:grid; place-items:center;
    background:transparent; color:var(--muted);
    border:1px solid var(--border); border-radius:var(--radius);
    font:inherit; font-size:1.15rem; line-height:1; cursor:pointer;
    transition:color .3s ease, border-color .3s ease, background .3s ease,
               transform .35s cubic-bezier(.32,.12,.2,1); }
  #cmdplus:hover, #cmdplus.on { color:var(--accent);
    border-color:var(--accent); background:rgba(99,102,241,.09); }
  #cmdplus.on { transform:rotate(45deg); }
  @media (max-width:820px) { #cmdplus { margin-left:0; } }
  #cmdpalette { position:fixed; z-index:30; top:4rem; left:1rem;
    width:min(32ch,92vw); background:rgba(11,15,25,.94);
    border:1px solid var(--border); border-radius:8px; padding:1rem;
    box-shadow:0 14px 44px rgba(0,0,0,.5); backdrop-filter:blur(7px);
    visibility:hidden; opacity:0; transform:translateY(-8px) scale(.97);
    filter:blur(6px); pointer-events:none;
    transition:opacity .5s cubic-bezier(.32,.12,.2,1),
               transform .5s cubic-bezier(.32,.12,.2,1),
               filter .5s ease, visibility 0s linear .5s; }
  #cmdpalette.open { visibility:visible; opacity:1; transform:none;
    filter:none; pointer-events:auto; transition-delay:0s; }
  #cmdpalette .label { margin-top:0; }
  #cmdform select, #cmdform textarea { width:100%; box-sizing:border-box;
    background:var(--panel); color:var(--text); border:1px solid var(--line);
    border-radius:var(--radius); font:inherit; padding:.4rem; margin:.3rem 0; }
  #cmdform textarea { min-height:3.4rem; resize:vertical; }
  .cmdrow { display:flex; gap:.5rem; align-items:center; margin-top:.2rem; }
  .cmdrow button { background:var(--panel2); color:var(--accent);
    border:1px solid var(--border); border-radius:var(--radius); font:inherit;
    padding:.25rem .8rem; cursor:pointer; }
  #cmdpop { margin-left:auto; color:var(--muted); }
  #cmdpop:hover { color:var(--accent); }
  .cmdmsg { color:var(--dim); font-size:.7rem; min-height:1em; margin-top:.5rem;
    transition:color .4s ease; }
  .cmdmsg.ok { color:var(--accent); }
  /* dream ripple: a soft ring expanding from a received command / answer */
  .ripple { position:fixed; z-index:40; border-radius:50%; pointer-events:none;
    border:1px solid var(--accent); }
  @media (prefers-reduced-motion: reduce) {
    #cmdplus, #cmdpalette, #layerhint { transition:none; }
  }
</style>"""

APP_BODY = """<canvas id="dreambg"></canvas>
<svg id="dreamfx" width="0" height="0" aria-hidden="true"
     style="position:absolute;width:0;height:0;pointer-events:none">
 <filter id="dissolveOut" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <filter id="dissolveIn" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
</svg>
<div class="wrap">
<div id="view">loading…</div>
<div id="cmdpalette" role="dialog" aria-label="command palette">
 <form id="cmdform" autocomplete="off">
  <div class="label">command the dream</div>
  <select id="cmdkind" aria-label="command">
   <option value="add-idea">add idea</option>
   <option value="do-next">do next</option>
   <option value="do-now">do now</option>
   <option value="maintenance">maintenance</option>
  </select>
  <textarea id="cmdtext" placeholder="a thought for the dream…"></textarea>
  <div class="cmdrow">
   <button type="submit" id="cmdsend">send</button>
   <button type="button" id="cmdpop"
           title="pop out — stays while you navigate">pop out &#8689;</button>
  </div>
  <div class="cmdmsg" id="cmdmsg" aria-live="polite"></div>
 </form>
</div>"""

COMPONENTS_JS = """
window.DEV=/*DEV*/false;
const esc = t => { const d = document.createElement('div');
                   d.textContent = t ?? ''; return d.innerHTML; };
const ageStr = mt => {
  let s = Math.max(0, Date.now()/1000 - mt);
  for (const [u, div] of [["d",86400],["h",3600],["m",60]])
    if (s >= div) return `${Math.floor(s/div)}${u}`;
  return `${Math.floor(s)}s`;
};
/* components: every section on every watch page renders through these */
const label = t => `<div class="label">${t}</div>`;
/* every view's heading carries the command-palette opener, tucked into the
   left gutter — a persistent, subtle affordance to steer the dream. */
const pageHeader = inner =>
  `<header class="htitlebar"><button id="cmdplus" type="button"` +
  ` title="command the dream" aria-label="open command palette">+</button>` +
  `<span class="htitle">${inner}</span></header>`;
const expand = (s, inner, cls='') =>
  `<details><summary class="${cls}">${s}</summary>${inner}</details>`;
/* backticked repo-relative paths become /file links (zero agent burden) */
const linkify = h => h.replace(
  /`([\\w.-]+(?:\\/[\\w.-]+)+\\/?|[\\w-]+\\.[\\w]{1,8})`/g,
  (m, p) => '`<a href="/file?p=' + encodeURIComponent(p) + '">' + p + '</a>`');
const preB = t => `<pre>${linkify(esc(t))}</pre>`;
/* a backticked path to a review artifact docks THIS question onto the
   review page (carries its title); every other path stays a /file link. */
const linkifyReview = (escaped, title) => escaped.replace(
  /`\\.dreamwork\\/review\\/([\\w.-]+\\.html?)`/g,
  (m, name) => '`<a class="rev" href="/review?p=' + encodeURIComponent(name) +
    '&q=' + encodeURIComponent(title) + '">.dreamwork/review/' + name +
    '</a>`');
const preBReview = (t, title) =>
  `<pre>${linkify(linkifyReview(esc(t), title))}</pre>`;
/* three states: an open question shows an answer box; a question already
   answered from the dashboard (awaiting the loop to fold it) shows the
   answer distinctly with no box — never ambiguous; the folded Answered
   section is rendered separately by the view. */
const qaCard = (q, i) => {
  const head = `<div class="qt">${esc(q.title)}</div>`;
  const body = q.body.trim() ? preBReview(q.body.trim(), q.title) : '';
  if (q.answer)
    return `<div class="qa answered">${head}${body}` +
      `<div class="anstag">answered · awaiting fold</div>` +
      `<div class="anstext">${esc(q.answer)}</div></div>`;
  return `<div class="qa">${head}${body}` +
    `<textarea id="qa${i}" placeholder="answer…"></textarea>` +
    `<button onclick="sendAnswer(${i})">answer</button></div>`;
};
async function postAnswer(title, text) {
  await fetch('/answer', { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, answer: text }) });
}
"""

VIEWS_JS = """
/* view builders: each returns the inner HTML of #view for one route.
   The dashboard/questions views are data-driven (re-rendered live on
   mtime change); the file view is a static read. */
function dreamBlock(d) {
  return expand(
    `${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span>`,
    preB(d.content));
}
function buildDashboard(d) {
  const q = d.open_questions > 0
    ? ` · <a class="q" href="/questions">${d.open_questions} open question${d.open_questions>1?'s':''}</a>`
    : ` · <a class="q" href="/questions" style="color:var(--dimmer)">questions</a>`;
  let h = pageHeader('dreamwork watch') +
    `<div id="meta">${esc(d.target)} · ${esc(d.files['skill-version'])} · ` +
    `<span id="upd"></span>${q}</div><div id="sections">`;
  h += label(`dreams (${d.dreams.length})`) +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? expand(`archive (${d.dreams_archive.length})`,
                  d.dreams_archive.map(dreamBlock).join(''), 'dim') : '');
  {
    const qo = d.questions_open.map((q, i) => [q, i]);
    const openQ = qo.filter(([q]) => !q.answer);
    const foldQ = qo.filter(([q]) => q.answer);
    if (openQ.length)
      h += label('answer questions') +
           openQ.map(([q, i]) => qaCard(q, i)).join('');
    if (foldQ.length)
      h += label('answered · awaiting fold') +
           foldQ.map(([q, i]) => qaCard(q, i)).join('');
  }
  if (d.reviews.length) {
    h += label('reviews') + d.reviews.map(r =>
      `<div><a href="/review?p=${encodeURIComponent(r.name)}">${esc(r.name)}</a>` +
      `<span class="age" data-mt="${r.mtime}"></span></div>`).join('');
  }
  h += label('files') +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         expand(n, preB(d.files[n]))).join('');
  if (d.status)
    h += label('status') + preB(JSON.stringify(d.status, null, 2));
  h += label('commits') + `<div class="git">` +
       d.git.map(l => `<div class="${l.includes('dreamwork(maintain:') ? 'maint' : ''}">${esc(l)}</div>`).join('') +
       `</div></div>`;
  return h;
}
function buildQuestions(d) {
  const raw = d.files['questions.md'] || '';
  const answered = raw.split(/^## Answered$/m)[1] || '';
  // three explicit states: open (needs the human), answered-awaiting-fold
  // (the loop's to fold), and the folded Answered section.
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let h = pageHeader('questions') +
    `<div id="meta"><a href="/">&larr; dashboard</a></div><div id="qsections">`;
  h += label(`open (${openQ.length})`) +
       (openQ.map(([q, i]) => qaCard(q, i)).join('') ||
        '<div class="dim">none — all answered</div>');
  if (foldQ.length)
    h += label(`answered · awaiting fold (${foldQ.length})`) +
         foldQ.map(([q, i]) => qaCard(q, i)).join('');
  h += label('answered') + preB(answered.trim() || '(none yet)');
  return h + `</div>`;
}
function buildFile(param, text) {
  const body = text == null
    ? '<div class="dim">not found</div>'
    : `<pre>${esc(text)}</pre>`;
  return pageHeader(esc(param || '')) +
    `<div id="meta"><a href="/">&larr; dashboard</a></div>` +
    `<div id="filebody">${body}</div>`;
}
/* review view: the raw artifact in an iframe (style-isolated) with the
   originating question docked beside it (answer box included), so it can
   be answered with the review in front of you. Deep-loads without a
   question just show the artifact. */
function buildReview(name, q, d) {
  const src = '/reviewraw?p=' + encodeURIComponent(name || '');
  let dock = '';
  if (q && d) {
    const i = d.questions_open.findIndex(x => x.title === q);
    if (i >= 0)
      dock = `<aside class="qdock" id="qdock">` +
        label('answering') + qaCard(d.questions_open[i], i) + `</aside>`;
  }
  return pageHeader(`review<span class="revname">${esc(name || '')}</span>`) +
    `<div id="meta"><a href="/questions">&larr; questions</a> · ` +
    `<a href="/">dashboard</a></div>` +
    `<div id="reviewwrap"${dock ? '' : ' class="nodock"'}>` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="${src}" ` +
      `title="review artifact" loading="lazy"></iframe></div>` +
      dock +
    `</div>`;
}
function ages() {
  document.querySelectorAll('.age[data-mt]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.mt)) + ' old');
  const upd = document.getElementById('upd');
  if (upd && fetchedAt) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
}
async function sendAnswer(i) {
  const el = document.getElementById('qa' + i);
  if (!el || !el.value.trim() || !data) return;
  const btn = el.parentNode.querySelector('button');
  await postAnswer(data.questions_open[i].title, el.value.trim());
  el.value = '';
  if (btn && typeof ripple === 'function') {          // dream confirmation
    const r = btn.getBoundingClientRect();
    ripple(r.left + r.width / 2, r.top + r.height / 2);
    btn.textContent = 'received';
    setTimeout(() => { btn.textContent = 'answer'; }, 1600);
  }
}
"""

ROUTER_JS = """
/* Single-document router. Views swap inside #view; the shader canvas is
   its sibling and is never touched, so the background is unbroken across
   navigations. Deep links still work: the server hands back this same
   shell for /, /questions, /file and /review, and we render the matching
   view on load. /review embeds the raw artifact (served at /reviewraw) in
   an iframe; a question that links to it travels along, docked. */
const rmr = matchMedia('(prefers-reduced-motion: reduce)').matches;
let data = null, fetchedAt = 0, lastMtime = null, serverGen = null;
/* /mtime is "<generation> <mtime>": a changed generation means the server
   was rebuilt (--autoreload) or restarted (redeploy) — reload to pick up the
   new shell; a changed mtime just re-renders the live data. */
const parseMtime = raw => {
  raw = (raw || '').trim();
  const sp = raw.indexOf(' ');
  return sp >= 0 ? { gen: raw.slice(0, sp), mtime: raw.slice(sp + 1) }
                 : { gen: '', mtime: raw };
};
let view = { name: null, param: null, q: null };
let fileCache = { param: null, text: undefined };
/* per-page atmosphere: a tiny tint bias the shader lerps toward (~1.5s) */
const TINT = { dashboard: 0.0, questions: 0.14, file: -0.14, review: 0.22 };
/* per-route dissolve signature: each destination swirls from its own
   turbulence seed, so arriving somewhere has a consistent feel (pairs with
   the per-route tint). Distinct small integers give distinct fields. */
const SEED = { dashboard: 7, questions: 23, file: 41, review: 61 };
const TITLE = { dashboard: () => 'dreamwork watch',
                questions: () => 'questions — dreamwork watch',
                file: p => (p || 'file') + ' — dreamwork watch',
                review: p => 'review ' + (p || '') + ' — dreamwork watch' };

function routeOf(loc) {
  if (loc.pathname === '/questions') return { name: 'questions', param: null };
  if (loc.pathname === '/file')
    return { name: 'file',
             param: new URLSearchParams(loc.search).get('p') };
  if (loc.pathname === '/review') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'review', param: sp.get('p'), q: sp.get('q') };
  }
  return { name: 'dashboard', param: null };
}
async function ensureData() {
  if (data) return data;
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    lastMtime = mtime;
    fetchedAt = Date.now();
    data = await (await fetch('/data.json')).json();
  } catch (e) {}
  return data;
}
async function fetchFile(param) {
  if (fileCache.param === param) return fileCache.text;
  let text = null;
  try {
    const res = await fetch('/filedata?p=' + encodeURIComponent(param || ''));
    if (res.ok) text = (await res.json()).content;
  } catch (e) {}
  fileCache = { param, text };
  return text;
}
async function buildCurrent() {
  if (view.name === 'file')
    return buildFile(view.param, await fetchFile(view.param));
  const d = await ensureData();
  if (view.name === 'review') return buildReview(view.param, view.q, d);
  if (!d) return '<div class="dim">loading…</div>';
  return view.name === 'questions' ? buildQuestions(d) : buildDashboard(d);
}
function setContent(html) {
  document.getElementById('view').innerHTML = html;
  ages();
}
/* Dream dissolve: the outgoing view becomes a ghost that liquifies into a
   swirling mist (turbulence displacement + blur grow) and drifts upward as
   it fades; the incoming view coalesces from the same mist and settles
   perfectly crisp. Opacity + transform ride CSS; the mist is an SVG filter
   whose displacement + blur we envelope per-frame here, so the middle of
   the dissolve lingers hazy. The shader stirs in sympathy (pulseWarp).
   reduced-motion swaps instantly — no ghost, no mist. */
const DREAM_MS = 1150;                     // dwell of the whole dissolve
const fxNode = (id, tag) => document.querySelector('#' + id + ' ' + tag);
function crossfade(html, xopts) {
  xopts = xopts || {};
  const viewEl = document.getElementById('view');
  if (rmr) {
    document.body.classList.toggle('review', !!xopts.review);
    setContent(html);
    return;
  }
  const ghost = viewEl.cloneNode(true);
  ghost.removeAttribute('id'); ghost.className = 'ghost';
  // a cloned iframe would re-fetch and flash while dissolving — drop it;
  // the ghost only needs the chrome/text to blur away.
  ghost.querySelectorAll('iframe').forEach(f => f.remove());
  viewEl.parentNode.appendChild(ghost);
  document.body.classList.toggle('review', !!xopts.review);   // width flips now
  setContent(html);
  // measure the docked question's resting rect BEFORE the enter transform,
  // so a shared-element FLIP from the clicked question lands true.
  const dock = document.getElementById('qdock');
  const dockRect = dock ? dock.getBoundingClientRect() : null;
  ghost.style.filter = 'url(#dissolveOut)';
  viewEl.style.filter = 'url(#dissolveIn)';
  viewEl.classList.add('enter');
  void viewEl.offsetWidth;                 // commit the hidden start state
  if (xopts.fromRect && dock && dockRect) flipDock(dock, xopts.fromRect, dockRect);
  if (window.dreambg) window.dreambg.pulseWarp();
  requestAnimationFrame(() => {
    viewEl.classList.remove('enter');      // CSS eases opacity + drift in
    ghost.classList.add('out');            // CSS eases opacity + drift out
  });
  const dOut = fxNode('dissolveOut', 'feDisplacementMap');
  const bOut = fxNode('dissolveOut', 'feGaussianBlur');
  const tOut = fxNode('dissolveOut', 'feTurbulence');
  const dIn = fxNode('dissolveIn', 'feDisplacementMap');
  const bIn = fxNode('dissolveIn', 'feGaussianBlur');
  const tIn = fxNode('dissolveIn', 'feTurbulence');
  // per-destination swirl signature: this arrival's turbulence field
  const seed = SEED[view.name] != null ? SEED[view.name] : 7;
  if (tOut) tOut.setAttribute('seed', seed);
  if (tIn) tIn.setAttribute('seed', seed);
  const smooth = x => x * x * (3 - 2 * x);
  const t0 = performance.now();
  let raf = 0;
  const finish = () => {
    if (raf) cancelAnimationFrame(raf), raf = 0;
    if (ghost.isConnected) ghost.remove();
    viewEl.style.filter = '';              // crisp at rest, zero filter cost
  };
  function stepFx(now) {
    const u = Math.min(1, (now - t0) / DREAM_MS);
    const eo = smooth(u);                          // ghost: mist grows in
    if (dOut) dOut.setAttribute('scale', (eo * 25).toFixed(2));
    if (bOut) bOut.setAttribute('stdDeviation', (eo * 3.8).toFixed(2));
    const ui = Math.min(1, Math.max(0, (now - t0 - 160) / (DREAM_MS - 160)));
    const ei = smooth(ui);                         // incoming: mist clears
    if (dIn) dIn.setAttribute('scale', ((1 - ei) * 19).toFixed(2));
    if (bIn) bIn.setAttribute('stdDeviation', ((1 - ei) * 3.2).toFixed(2));
    const bf = (0.009 + eo * 0.009).toFixed(4);    // field tightens: it flows
    if (tOut) tOut.setAttribute('baseFrequency', bf);
    if (tIn) tIn.setAttribute('baseFrequency', bf);
    if (u < 1) raf = requestAnimationFrame(stepFx);
    else finish();
  }
  raf = requestAnimationFrame(stepFx);
  setTimeout(finish, DREAM_MS + 400);      // safety net
}
/* shared-element morph: the docked question travels from where it was
   clicked (its list rect) to its docked rect — auto-animate style, but the
   dream twist is a blurred, low-opacity drift rather than a crisp slide. */
function flipDock(dock, fromRect, toRect) {
  const dx = fromRect.left - toRect.left;
  const dy = fromRect.top - toRect.top;
  const sx = Math.max(0.15, fromRect.width / (toRect.width || 1));
  const sy = Math.max(0.15, fromRect.height / (toRect.height || 1));
  // Lift the travelling question above the page mist (z-index) and keep it
  // luminous, so the eye tracks THIS element gliding to its dock while the
  // rest of the page dissolves behind it — a shared-element morph, but
  // dream-blurred not crisp. Its glide outlasts the mist so the travel reads.
  dock.style.zIndex = '4';
  dock.style.transformOrigin = 'top left';
  dock.style.transform = `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`;
  dock.style.filter = 'blur(5px)';
  dock.style.opacity = '0.4';
  dock.style.transition = 'none';
  void dock.offsetWidth;                    // commit the inverted start
  requestAnimationFrame(() => {
    dock.style.transition =
      'transform 1.15s cubic-bezier(.22,.61,.36,1), filter .95s ease, ' +
      'opacity .85s ease';
    dock.style.transform = 'none';
    dock.style.filter = '';
    dock.style.opacity = '1';
  });
  const clear = () => {
    for (const p of ['transition', 'transform', 'transformOrigin', 'filter',
                     'opacity', 'zIndex']) dock.style[p] = '';
  };
  dock.addEventListener('transitionend', clear, { once: true });
  setTimeout(clear, 1500);                  // safety net
}
async function navigate(name, param, opts) {
  opts = opts || {};
  if (window.__closeCmd) window.__closeCmd();   // context is changing
  view = { name, param, q: opts.q || null };
  document.title = (TITLE[name] || TITLE.dashboard)(param);
  if (window.dreambg) window.dreambg.setTint(TINT[name] || 0);
  const url = name === 'questions' ? '/questions'
    : name === 'file' ? '/file?p=' + encodeURIComponent(param || '')
    : name === 'review' ? '/review?p=' + encodeURIComponent(param || '') +
        (opts.q ? '&q=' + encodeURIComponent(opts.q) : '')
    : '/';
  if (opts.push) history.pushState({ name, param, q: opts.q || null }, '', url);
  const html = await buildCurrent();
  if (opts.transition === false) {
    document.body.classList.toggle('review', name === 'review');
    setContent(html);
  } else {
    crossfade(html, { fromRect: opts.fromRect, review: name === 'review' });
  }
}
/* only same-document routes are intercepted; external links, new-tab and
   modified clicks fall through to the browser. */
function isInternal(a) {
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return false;
  if (a.origin !== location.origin) return false;
  return a.pathname === '/' || a.pathname === '/questions'
      || a.pathname === '/file' || a.pathname === '/review';
}
addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey ||
      e.shiftKey || e.altKey) return;
  const a = e.target.closest('a');
  if (!isInternal(a)) return;
  e.preventDefault();
  const r = routeOf(a);
  const opts = { push: true, q: r.q };
  // a review link fired from inside a question card seeds the shared-element
  // morph: remember where the question sat so it can travel to its dock.
  if (r.name === 'review' && r.q) {
    const card = a.closest('.qa');
    if (card) opts.fromRect = card.getBoundingClientRect();
  }
  navigate(r.name, r.param, opts);
});
addEventListener('popstate', () => {
  const r = routeOf(location);
  navigate(r.name, r.param, { push: false, q: r.q });
});
/* live tick: re-render the active data-driven view in place, no fade.
   Tolerates the brief unreachable window while the server restarts. */
async function tick() {
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    else if (gen && gen !== serverGen) { location.reload(); return; }
    if (mtime !== lastMtime) {
      lastMtime = mtime; fetchedAt = Date.now();
      data = await (await fetch('/data.json')).json();
      if (view.name === 'dashboard') setContent(buildDashboard(data));
      else if (view.name === 'questions') setContent(buildQuestions(data));
    }
  } catch (e) { /* server restarting; retry next tick */ }
  setTimeout(tick, 2000);
}
setInterval(ages, 1000);
(function () {                              // initial view from the URL
  const r = routeOf(location);
  navigate(r.name, r.param, { push: false, transition: false, q: r.q });
  tick();
})();
"""

COMMAND_JS = """
/* Command palette (#71): the heading's + opener reveals a small form to
   steer the dreaming loop without a chat turn. Submitting POSTs /command,
   which drops a source-tagged line into watch-events.log — the loop's tail
   monitor wakes on it (same transport as answers). A pop-out (Document
   Picture-in-Picture, window.open fallback) keeps the form handy while the
   main tab navigates; it identifies its project so multi-target popouts
   don't blur together. reduced-motion skips the drift, never the function. */
function ripple(x, y) {                     // soft expanding ring, dream feel
  if (rmr) return;
  const r = document.createElement('div');
  r.className = 'ripple';
  const s = 14;
  r.style.left = (x - s / 2) + 'px'; r.style.top = (y - s / 2) + 'px';
  r.style.width = r.style.height = s + 'px';
  r.style.transition = 'transform 1.1s cubic-bezier(.22,.61,.36,1), ' +
    'opacity 1.1s ease';
  r.style.opacity = '0.5';
  document.body.appendChild(r);
  requestAnimationFrame(() => {
    r.style.transform = 'scale(18)'; r.style.opacity = '0';
  });
  setTimeout(() => r.remove(), 1200);
}
/* the popped-out window is a bare document — give it its own dark theme and
   an identity band tinted like the page it came from. */
const POPOUT_CSS = `
  :root { color-scheme:dark; }
  body { margin:0; background:#0b0f19; color:#d1d5db;
    font-family:ui-monospace,'JetBrains Mono',monospace; font-size:13px; }
  .strip { height:4px; background:__STRIP__; }
  .phead { padding:.7rem .9rem .1rem; }
  .ptitle { color:#f3f4f6; }
  .ppath { color:#6b7280; font-size:.72rem; word-break:break-all;
    margin-top:.15rem; }
  form { padding:.3rem .9rem .9rem; }
  .plabel { color:#6b7280; text-transform:uppercase; letter-spacing:.08em;
    font-size:.66rem; margin:.6rem 0 .3rem; }
  select, textarea { width:100%; box-sizing:border-box; background:#111827;
    color:#d1d5db; border:1px solid #1f2937; border-radius:4px; font:inherit;
    padding:.4rem; margin:.2rem 0; }
  textarea { min-height:3.2rem; resize:vertical; }
  button { background:#1e293b; color:__ACCENT__; border:1px solid #334155;
    border-radius:4px; font:inherit; padding:.3rem .9rem; cursor:pointer;
    margin-top:.4rem; }
  .pmsg { color:#6b7280; font-size:.7rem; min-height:1em; margin-top:.4rem; }
  .pmsg.ok { color:__ACCENT__; }`;
const POPOUT_BODY = (base, path) => `
  <div class="strip"></div>
  <div class="phead"><div class="ptitle">+ command &middot; ${esc(base)}</div>
    <div class="ppath">${esc(path)}</div></div>
  <form id="pform" autocomplete="off">
    <div class="plabel">command the dream</div>
    <select id="pkind">
      <option value="add-idea">add idea</option>
      <option value="do-next">do next</option>
      <option value="do-now">do now</option>
      <option value="maintenance">maintenance</option>
    </select>
    <textarea id="ptext" placeholder="a thought for the dream…"></textarea>
    <div><button type="submit">send</button></div>
    <div class="pmsg" id="pmsg" aria-live="polite"></div>
  </form>`;
function mountPopout(w, base, path, tint) {
  const doc = w.document;
  doc.title = '+ ' + base + ' · dreamwork';
  const warm = tint >= 0;                    // carry the page's hue as identity
  const accent = warm ? '#c4b5fd' : '#a5b4fc';
  const strip = warm ? 'linear-gradient(90deg,#6d5bd0,#a855f7)'
                     : 'linear-gradient(90deg,#4f5bd5,#5b8def)';
  doc.head.innerHTML = '<meta charset="utf-8">';
  const st = doc.createElement('style');
  st.textContent = POPOUT_CSS.replace(/__ACCENT__/g, accent)
                             .replace('__STRIP__', strip);
  doc.head.appendChild(st);
  doc.body.innerHTML = POPOUT_BODY(base, path);
  const endpoint = location.origin + '/command';   // opener origin, absolute
  const msg = doc.getElementById('pmsg');
  doc.getElementById('pform').addEventListener('submit', async ev => {
    ev.preventDefault();
    const kind = doc.getElementById('pkind').value;
    const text = doc.getElementById('ptext').value.trim();
    if (kind !== 'do-next' && !text) { msg.textContent = 'a thought is needed';
      msg.className = 'pmsg'; return; }
    try {
      const r = await fetch(endpoint, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, text }) });
      if (r.ok) { msg.textContent = 'sent to the dream'; msg.className = 'pmsg ok';
        doc.getElementById('ptext').value = ''; }
      else { msg.textContent = 'rejected (' + r.status + ')'; msg.className = 'pmsg'; }
    } catch (e) { msg.textContent = 'no connection'; msg.className = 'pmsg'; }
  });
}
async function requestPopout() {
  const d = await ensureData();
  const path = (d && d.target) || '';
  const base = path.split('/').filter(Boolean).pop() || 'dreamwork';
  const tint = TINT[view.name] || 0;
  if (window.documentPictureInPicture &&
      documentPictureInPicture.requestWindow) {
    try {
      const w = await documentPictureInPicture.requestWindow(
        { width: 340, height: 320 });
      mountPopout(w, base, path, tint);
      if (window.__closeCmd) window.__closeCmd();
      return;
    } catch (e) { /* fall through to a positioned popup */ }
  }
  const w = window.open('', 'dreamcmd_' + base,
    'width=360,height=340,left=80,top=80');
  if (w) { mountPopout(w, base, path, tint);
    if (window.__closeCmd) window.__closeCmd(); }
}
(function () {
  const pal = document.getElementById('cmdpalette');
  if (!pal) return;
  const cmsg = () => document.getElementById('cmdmsg');
  let open = false;
  function place() {
    const plus = document.getElementById('cmdplus');
    if (!plus) return;
    const r = plus.getBoundingClientRect();
    const w = pal.offsetWidth || Math.min(innerWidth * 0.92, 340);
    pal.style.left = Math.max(8, Math.min(r.left, innerWidth - w - 8)) + 'px';
    pal.style.top = (r.bottom + 8) + 'px';
  }
  function openCmd() {
    place(); pal.classList.add('open'); open = true;
    const plus = document.getElementById('cmdplus');
    if (plus) plus.classList.add('on');
    const t = document.getElementById('cmdtext');
    if (t) setTimeout(() => t.focus(), rmr ? 0 : 140);
  }
  function closeCmd() {
    pal.classList.remove('open'); open = false;
    document.querySelectorAll('#cmdplus.on').forEach(p =>
      p.classList.remove('on'));
    const m = cmsg(); if (m) { m.textContent = ''; m.className = 'cmdmsg'; }
  }
  window.__closeCmd = closeCmd;
  document.addEventListener('click', e => {
    const plus = e.target.closest && e.target.closest('#cmdplus');
    if (plus) { e.preventDefault(); open ? closeCmd() : openCmd(); return; }
    if (open && e.target.closest && !e.target.closest('#cmdpalette')) closeCmd();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && open) closeCmd();
  });
  addEventListener('resize', () => { if (open) place(); });
  document.getElementById('cmdform').addEventListener('submit', async e => {
    e.preventDefault();
    const kind = document.getElementById('cmdkind').value;
    const text = document.getElementById('cmdtext').value.trim();
    const m = cmsg();
    if (kind !== 'do-next' && !text) {
      if (m) { m.textContent = 'a thought is needed'; m.className = 'cmdmsg'; }
      return;
    }
    try {
      const r = await fetch('/command', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, text }) });
      if (r.ok) {
        if (m) { m.textContent = 'sent to the dream'; m.className = 'cmdmsg ok'; }
        const plus = document.getElementById('cmdplus');
        if (plus) { const b = plus.getBoundingClientRect();
          ripple(b.left + b.width / 2, b.top + b.height / 2); }
        document.getElementById('cmdtext').value = '';
        setTimeout(closeCmd, 950);
      } else if (m) { m.textContent = 'rejected (' + r.status + ')';
        m.className = 'cmdmsg'; }
    } catch (e) { if (m) { m.textContent = 'no connection';
      m.className = 'cmdmsg'; } }
  });
  document.getElementById('cmdpop').addEventListener('click', requestPopout);
})();
"""

SHADER_JS = """
/* dreambg: dream-like fractal background (task #51).
   Four passes, all cheap by construction — the costly work stays on a
   ~1/6-CSS-res buffer and only a flat upscale touches full res:
     pass 1 — domain-warped fBm fractal -> low-res texture A.
     pass 2 — tilt-shift blur A -> B (8 golden-angle taps; a drifting
              focus band keeps radius small, growing away from it).
     pass 3 — blur B -> C again; the two passes compound into a wide,
              smooth depth-of-field (most of the frame softly defocused).
     pass 4 — upscale C to screen, tint indigo/violet, dither, composite
              very subtly over #0b0f19.
   Blur stays low-res on purpose: it IS the perf budget, and splitting it
   across two <=8-tap passes also sidesteps a headless-SwiftShader quirk
   where many texture taps of a high-frequency buffer drop the context.
   Text always wins: shader luminance is capped far below the dim text.
   Hidden layer switcher: press 'l' (or triple-click the bottom-right
   corner) to cycle raw components — fractal, warp field, focus mask,
   blurred fractal. Pauses when tab hidden; reduced-motion => 1 frame;
   no WebGL / no FBO => canvas hidden (flat #0b0f19 shows through). */
(function () {
  const cv = document.getElementById('dreambg');
  const gl = cv.getContext('webgl',
    { antialias: false, depth: false, alpha: false });
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!gl) { cv.style.display = 'none'; return; }

  const VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const FRACTAL_FS = `precision highp float;
    uniform float t; uniform vec2 r; uniform float warp;
    uniform vec2 domainOffset;   /* screen-space anchor: world-space dream */
    float hash(vec2 p){ p=fract(p*vec2(123.34,345.45));
      p+=dot(p,p+34.345); return fract(p.x*p.y); }
    float noise(vec2 p){ vec2 i=floor(p),f=fract(p);
      vec2 u=f*f*(3.0-2.0*f);
      return mix(mix(hash(i),hash(i+vec2(1,0)),u.x),
                 mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x),u.y); }
    float fbm(vec2 p){ float s=0.0,a=0.5;
      mat2 m=mat2(1.6,1.2,-1.2,1.6);
      for(int i=0;i<5;i++){ s+=a*noise(p); p=m*p; a*=0.5; } return s; }
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      /* world-space: offset the sampling domain by the window's on-screen
         position, so adjacent watch windows sample one continuous field and
         the pattern stays pinned to the screen as a window is dragged. */
      vec2 p=vec2(uv.x*(r.x/r.y),uv.y)*2.3 + domainOffset;
      float tt=t*0.03;
      vec2 q=vec2(fbm(p+vec2(0.0,tt)), fbm(p+vec2(5.2,1.3)-tt));
      /* pinch of curl: divergence-free swirl advecting the domain —
         fluid (navier-stokes-ish) drift without a sim */
      vec2 curl=vec2(q.y-0.5, 0.5-q.x);
      p+=curl*(0.38+0.14*sin(tt*1.7));
      /* transition: the dream stirs — deepen the curl advection and twist
         the domain about screen-centre while a page dissolves, then relax
         back (warp is a 0->1->0 pulse driven by the router). */
      p+=curl*warp*0.6;
      vec2 ctr=vec2(0.5*(r.x/r.y),0.5)*2.3;
      float wa=warp*0.15;
      float cw=cos(wa), sw=sin(wa);
      p=ctr+mat2(cw,-sw,sw,cw)*(p-ctr);
      vec2 s=vec2(fbm(p+2.6*q+vec2(1.7,9.2)+tt*0.6),
                  fbm(p+2.6*q+vec2(8.3,2.8)-tt*0.4));
      float f=fbm(p+3.2*s);
      f=clamp(f*1.15-0.05,0.0,1.0);
      gl_FragColor=vec4(f, clamp(q.x*0.5+0.5,0.,1.),
                        clamp(s.y*0.5+0.5,0.,1.), 1.0);
    }`;
  const FOCUS_GLSL = `
    float focusMask(vec2 uv){
      float band=0.5+0.30*sin(t*0.045);
      float foc=smoothstep(0.05,0.44,abs(uv.y-band));
      foc=clamp(foc+0.18*smoothstep(0.35,1.0,abs(uv.x-0.5)*2.0),0.0,1.0);
      return foc;
    }`;
  const BLUR_FS = `precision highp float;
    uniform sampler2D tex; uniform vec2 r; uniform float t;` + FOCUS_GLSL + `
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      float rad=mix(0.0,0.045,focusMask(uv));
      vec4 acc=texture2D(tex,uv); float w=1.0;
      for(int i=0;i<8;i++){
        float fi=float(i);
        float rr=sqrt((fi+0.5)/8.0)*rad;
        vec2 off=vec2(cos(fi*2.399963),sin(fi*2.399963))*rr;
        off.x*=r.y/r.x;
        acc+=texture2D(tex,uv+off); w+=1.0;
      }
      gl_FragColor=acc/w;
    }`;
  const COMPOSITE_FS = `precision highp float;
    uniform sampler2D texRaw; uniform sampler2D texBlur;
    uniform vec2 r; uniform float t; uniform int mode;
    uniform float pageTint;   /* per-page atmosphere: hue bias only */
    float hash(vec2 p){ p=fract(p*vec2(123.34,345.45));
      p+=dot(p,p+34.345); return fract(p.x*p.y); }` + FOCUS_GLSL + `
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      vec4 raw=texture2D(texRaw,uv);
      vec4 bl=texture2D(texBlur,uv);
      if(mode==1){ gl_FragColor=vec4(vec3(raw.r),1.0); return; }
      if(mode==2){ gl_FragColor=vec4(raw.g,0.25,raw.b,1.0); return; }
      if(mode==3){ gl_FragColor=vec4(vec3(1.0-focusMask(uv)),1.0); return; }
      if(mode==4){ gl_FragColor=vec4(vec3(bl.r),1.0); return; }
      float foc=focusMask(uv);
      vec4 img=mix(raw,bl,smoothstep(0.0,0.55,foc));
      float glow=smoothstep(0.34,0.92,img.r);
      vec3 indigo=vec3(0.28,0.30,0.62);
      vec3 violet=vec3(0.44,0.31,0.66);
      vec3 peri=vec3(0.33,0.41,0.74);
      vec3 tint=mix(indigo,violet,clamp(img.g,0.,1.));
      tint=mix(tint,peri,smoothstep(0.42,0.72,img.b));
      /* per-page identity: nudge the tint's hue a pinch. Luminance-safe —
         the glow multiplier below is untouched, so the peak-brightness
         cap that keeps text winning is unchanged. warm one page, cool
         another; magnitude stays a whisper (<=0.07 mix). */
      vec3 warmRef=vec3(0.50,0.33,0.62);
      vec3 coolRef=vec3(0.30,0.42,0.72);
      tint=mix(tint, pageTint>=0.0?warmRef:coolRef,
               clamp(abs(pageTint),0.0,1.0)*0.5);
      vec3 base=vec3(0.043,0.059,0.098);
      vec3 col=base+tint*(glow*0.105);
      col*=1.0-0.22*smoothstep(0.35,1.25,length(uv-0.5));
      col+=(hash(gl_FragCoord.xy+t)-0.5)/255.0;
      gl_FragColor=vec4(col,1.0);
    }`;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
      console.warn('dreambg shader:', gl.getShaderInfoLog(s));
    return s;
  }
  function program(fs) {
    const pr = gl.createProgram();
    gl.attachShader(pr, compile(gl.VERTEX_SHADER, VS));
    gl.attachShader(pr, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr); return pr;
  }
  // GL objects live in these; initGL() (re)creates them so the whole
  // pipeline can be rebuilt if the browser loses/restores the context.
  let progF, progB, progC, uF, uB, uC, buf;
  let A = null, B = null, C = null, fboOK = false;
  let canW = 2, canH = 2, fboW = 2, fboH = 2;
  function bindQuad(pr) {
    const loc = gl.getAttribLocation(pr, 'p');
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  }
  function makeTarget(w, h) {   // low-res RGBA render target
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0,
      gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
      gl.TEXTURE_2D, tex, 0);
    const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER)
               === gl.FRAMEBUFFER_COMPLETE;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return ok ? { fbo, tex } : null;
  }
  function size() {
    canW = Math.max(2, Math.floor(innerWidth / 2));
    canH = Math.max(2, Math.floor(innerHeight / 2));
    cv.width = canW; cv.height = canH;
    fboW = Math.max(2, Math.floor(canW / 2));
    fboH = Math.max(2, Math.floor(canH / 2));
    for (const tgt of [A, B, C]) if (tgt) {
      gl.deleteTexture(tgt.tex); gl.deleteFramebuffer(tgt.fbo);
    }
    A = makeTarget(fboW, fboH);
    B = makeTarget(fboW, fboH);
    C = makeTarget(fboW, fboH);
    fboOK = !!(A && B && C);
    if (!fboOK) cv.style.display = 'none';
  }
  function initGL() {
    A = B = C = null;                 // context loss invalidated them
    progF = program(FRACTAL_FS);
    progB = program(BLUR_FS);
    progC = program(COMPOSITE_FS);
    uF = { t: gl.getUniformLocation(progF, 't'),
           r: gl.getUniformLocation(progF, 'r'),
           warp: gl.getUniformLocation(progF, 'warp'),
           domainOffset: gl.getUniformLocation(progF, 'domainOffset') };
    uB = { tex: gl.getUniformLocation(progB, 'tex'),
           r: gl.getUniformLocation(progB, 'r'),
           t: gl.getUniformLocation(progB, 't') };
    uC = { raw: gl.getUniformLocation(progC, 'texRaw'),
           blur: gl.getUniformLocation(progC, 'texBlur'),
           r: gl.getUniformLocation(progC, 'r'),
           t: gl.getUniformLocation(progC, 't'),
           mode: gl.getUniformLocation(progC, 'mode'),
           pageTint: gl.getUniformLocation(progC, 'pageTint') };
    buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    size();
  }
  initGL();

  let mode = 0, lastMs = 0;
  // per-page atmosphere lerped in JS then handed to the composite shader;
  // frameCount is a monotonic draw tally (never resets) so a view swap's
  // continuity can be checked from outside.
  let tintCur = 0, tintTarget = 0, lastDrawMs = 0, frameCount = 0;
  // transition stir: a 0->1->0 envelope the router pulses per navigation;
  // deepens the fractal's curl advection + twist, then relaxes back.
  let warpStart = -1e9, lastWarp = 0;
  function unbindTextures() {
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, null);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, null);
  }
  function blurPass(src, dst, secs) {   // src.tex -> dst.fbo, low res
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fbo);
    gl.viewport(0, 0, fboW, fboH);
    gl.useProgram(progB); bindQuad(progB);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, src.tex);
    gl.uniform1i(uB.tex, 0);
    gl.uniform2f(uB.r, fboW, fboH); gl.uniform1f(uB.t, secs);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function draw(ms) {
    lastMs = ms;
    // Shader phase comes from the wall clock (shared by every window), not
    // page-local time — so windows animate in lockstep. UTC-day-wrapped to
    // stay small enough for float precision (a single simultaneous reshuffle
    // at UTC midnight; frame deltas below still use page-local ms).
    const secs = (Date.now() * 0.001) % 86400;
    if (!fboOK || gl.isContextLost()) return;
    // world-space anchor: shift the fractal domain by the window's on-screen
    // position (polled per frame, so dragging pins the pattern to the
    // screen). Same units as the domain's per-pixel mapping (2.3/innerHeight).
    const wScale = 2.3 / Math.max(1, innerHeight);
    const chromeTop = Math.max(0, outerHeight - innerHeight);
    const domX = (window.screenX || 0) * wScale;
    const domY = ((window.screenY || 0) + chromeTop) * wScale;
    const dt = lastDrawMs ? Math.min(0.1, (ms - lastDrawMs) / 1000) : 0;
    lastDrawMs = ms;
    tintCur += (tintTarget - tintCur) * (1.0 - Math.exp(-dt / 0.6));
    // warp envelope: fast attack, slow relax to 0 by ~1.6s after a pulse.
    const wage = (ms - warpStart) / 1000;
    let w = 0;
    if (wage >= 0 && wage < 1.6) {
      const atk = 0.22;
      w = wage < atk ? wage / atk : 1.0 - (wage - atk) / (1.6 - atk);
      w = Math.max(0, w); w = w * w * (3 - 2 * w);
    }
    lastWarp = w;
    frameCount++;
    unbindTextures();                       // no cross-frame feedback
    // pass 1: fractal -> A
    gl.bindFramebuffer(gl.FRAMEBUFFER, A.fbo);
    gl.viewport(0, 0, fboW, fboH);
    gl.useProgram(progF); bindQuad(progF);
    gl.uniform1f(uF.t, secs); gl.uniform2f(uF.r, fboW, fboH);
    gl.uniform1f(uF.warp, w);
    gl.uniform2f(uF.domainOffset, domX, domY);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // passes 2 & 3: tilt-shift blur A -> B -> C
    blurPass(A, B, secs);
    blurPass(B, C, secs);
    // pass 4: upscale + composite C (blurred) with A (raw) -> screen
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canW, canH);
    gl.useProgram(progC); bindQuad(progC);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, A.tex);
    gl.uniform1i(uC.raw, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, C.tex);
    gl.uniform1i(uC.blur, 1);
    gl.uniform2f(uC.r, canW, canH);
    gl.uniform1f(uC.t, secs);
    gl.uniform1i(uC.mode, mode);
    gl.uniform1f(uC.pageTint, tintCur);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  addEventListener('resize', () => { size(); if (rm) draw(lastMs); });

  const MODES = ['dream (composite)', 'raw fractal', 'warp field',
                 'focus mask', 'blurred fractal'];
  let hint = null, hintT = 0;
  function cycle() {
    mode = (mode + 1) % MODES.length;
    if (!hint) {
      hint = document.createElement('div');
      hint.id = 'layerhint'; document.body.appendChild(hint);
    }
    // Self-explanatory feedback: names the layer AND how to cycle, so an
    // accidental switch (stray 'l', triple-click corner) is legible and
    // reversible rather than a mysterious background change.
    hint.textContent = 'background: ' + MODES[mode] + ' — press l to cycle';
    hint.style.opacity = '1';
    clearTimeout(hintT);
    hintT = setTimeout(() => { hint.style.opacity = '0'; }, 2200);
    if (rm) draw(lastMs);
  }
  addEventListener('keydown', e => {
    // never hijack a keystroke aimed at a text field (command palette etc.)
    if (e.target.closest && e.target.closest('input, textarea, select')) return;
    if (e.key === 'l' && !e.metaKey && !e.ctrlKey && !e.altKey) cycle();
  });
  let clicks = 0, clickT = 0;
  addEventListener('click', e => {
    if (!(e.clientX > innerWidth - 90 && e.clientY > innerHeight - 90)) {
      clicks = 0; return;
    }
    const now = Date.now();
    if (now - clickT > 600) clicks = 0;
    clickT = now;
    if (++clicks >= 3) { clicks = 0; cycle(); }
  });

  let rafId = 0, running = true;
  let fpsEl = null, dtEl = null, ftEl = null, sparkCtx = null;
  let fpsN = 0, fpsT = 0, prevMs = 0;
  const fts = [];                       // inter-frame deltas (missed-vsync)
  const dts = [];                       // measured CPU-side draw time (ms)
  const gts = [];                       // measured GPU frame time (ms), if any
  // GPU timer (dev-only): true per-frame GPU cost via one in-flight
  // TIME_ELAPSED query. Feature-gated to WebGL2 + the disjoint-timer ext;
  // dormant (the CPU number shows) otherwise, and never touched when the
  // overlay is off — no query machinery runs in prod.
  let gpuExt = null, gpuQuery = null, gpuPending = false, gpuOpen = false;
  function acquireGpuTimer() {
    gpuExt = gl.getExtension('EXT_disjoint_timer_query_webgl2');
    if (!(gpuExt && typeof gl.createQuery === 'function')) gpuExt = null;
    gpuQuery = null; gpuPending = false; gpuOpen = false;
  }
  if (window.DEV) {
    const box = document.createElement('div');
    box.id = 'devbox';
    fpsEl = document.createElement('div');
    dtEl = document.createElement('div');
    ftEl = document.createElement('div');
    const sp = document.createElement('canvas');
    sp.width = 120; sp.height = 22;
    box.append(fpsEl, dtEl, ftEl, sp);
    document.body.appendChild(box);
    sparkCtx = sp.getContext('2d');
    acquireGpuTimer();
  }
  function drawSpark() {
    const c = sparkCtx; if (!c || !fts.length) return;
    c.clearRect(0, 0, 120, 22);
    const worst = Math.max(16.8, ...fts);
    c.fillStyle = '#a5b4fc';
    fts.forEach((v, i) =>
      c.fillRect(i, 22 - (v / worst) * 22, 1, (v / worst) * 22));
    c.fillStyle = '#4b5563';           // 60fps guide line
    c.fillRect(0, 22 - (16.7 / worst) * 22, 120, 1);
  }
  const avgOf = a => a.reduce((x, y) => x + y, 0) / (a.length || 1);
  // draw() wrapped with a CPU stopwatch (JS + GL submission) and, when the
  // GPU timer is live, a TIME_ELAPSED query straddling the same draw.
  function timedDraw(ms) {
    if (gpuExt && gpuPending) {                    // reap the prior query
      const ready = gl.getQueryParameter(gpuQuery, gl.QUERY_RESULT_AVAILABLE);
      const disjoint = gl.getParameter(gpuExt.GPU_DISJOINT_EXT);
      if (ready || disjoint) {
        if (ready && !disjoint) {
          const ns = gl.getQueryParameter(gpuQuery, gl.QUERY_RESULT);
          gts.push(ns / 1e6); if (gts.length > 120) gts.shift();
        }
        gpuPending = false;
      }
    }
    if (gpuExt && !gpuPending) {
      gpuQuery = gpuQuery || gl.createQuery();
      gl.beginQuery(gpuExt.TIME_ELAPSED_EXT, gpuQuery); gpuOpen = true;
    }
    const t0 = performance.now();
    draw(ms);
    const cpuMs = performance.now() - t0;
    if (gpuOpen) {
      gl.endQuery(gpuExt.TIME_ELAPSED_EXT); gpuOpen = false; gpuPending = true;
    }
    return cpuMs;
  }
  function frame(ms) {
    const cpuMs = fpsEl ? timedDraw(ms) : (draw(ms), 0);
    if (fpsEl) {
      fpsN++;
      if (prevMs) {
        fts.push(ms - prevMs);
        if (fts.length > 120) fts.shift();
      }
      prevMs = ms;
      dts.push(cpuMs); if (dts.length > 120) dts.shift();
      if (ms - fpsT >= 1000) {
        fpsEl.textContent = fpsN + ' fps';
        // measured work per frame: real GPU time when the timer is live,
        // else CPU-side draw (JS + GL submission — understates true GPU).
        const useGpu = gts.length > 0, work = useGpu ? gts : dts;
        dtEl.textContent =
          avgOf(work).toFixed(1) + '·' + Math.max(0, ...work).toFixed(1) +
          'ms ' + (useGpu ? 'gpu' : 'draw');
        ftEl.textContent =
          avgOf(fts).toFixed(1) + 'ms avg · ' +
          Math.max(0, ...fts).toFixed(1) + 'ms worst';
        drawSpark();
        fpsN = 0; fpsT = ms;
      }
    }
    if (running && !rm) rafId = requestAnimationFrame(step);
  }
  function step(ms) {
    if (!running) return;
    if (!document.hidden) frame(ms);
    else setTimeout(() => { if (running) rafId = requestAnimationFrame(step); }, 500);
  }
  // Context loss (GPU reset, tab backgrounding, driver hiccup) is
  // recoverable: rebuild every GL object on restore and resume.
  cv.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
  });
  cv.addEventListener('webglcontextrestored', () => {
    initGL();
    if (window.DEV) acquireGpuTimer();     // ext + query died with the context
    running = true;
    if (rm) draw(lastMs);
    else rafId = requestAnimationFrame(step);
  });
  // The router talks to the shader through this handle: setTint nudges
  // the per-page atmosphere target (lerped inside draw); pulseWarp fires
  // the transition stir; frames exposes the monotonic draw tally so a view
  // swap's continuity is observable. reduced-motion never stirs.
  window.dreambg = {
    setTint(v) { tintTarget = v; if (rm) { tintCur = v; draw(lastMs); } },
    pulseWarp() { if (!rm) warpStart = lastMs; },
    get frames() { return frameCount; },
    get tint() { return tintCur; },
    get warp() { return lastWarp; }
  };
  if (rm) draw(0);
  else rafId = requestAnimationFrame(step);
})();
"""

def page_shell(title, body, js):
    """Shared page shell. Contract: `body` opens `<div class="wrap">`
    (the shell closes it) so every watch page shares chrome and tokens."""
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{title}</title>' + STYLE + '</head><body>'
            + body + '<script>' + js
            + '</script></div></body></html>')


# One shell serves every same-document view. The router (last, so
# window.dreambg from the shader exists before it runs) picks the initial
# view from the URL; SHADER_JS mounts the persistent background.
PAGE = page_shell('dreamwork watch', APP_BODY,
                  COMPONENTS_JS + VIEWS_JS + SHADER_JS + ROUTER_JS
                  + COMMAND_JS)


def age_str(seconds):
    for unit, div in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= div:
            return f"{int(seconds // div)}{unit}"
    return f"{int(seconds)}s"


def read_text(path, limit=200_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return None


def list_dreams(dirpath, now):
    out = []
    if not os.path.isdir(dirpath):
        return out
    for name in sorted(os.listdir(dirpath), reverse=True):
        p = os.path.join(dirpath, name)
        if name.endswith(".md") and os.path.isfile(p):
            out.append({"name": name,
                        "mtime": os.path.getmtime(p),
                        "age": age_str(now - os.path.getmtime(p)),
                        "content": read_text(p)})
    return out


def git_tail(target, n=15):
    try:
        res = subprocess.run(
            ["git", "-C", target, "log", "-n", str(n), "--pretty=%h %s"],
            capture_output=True, text=True, timeout=5)
        return res.stdout.splitlines() if res.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        return []


def parse_open_questions(text):
    """[{title, body, answer}] for each '- **Title**' entry in Open.

    A `- **Answer (via watch...):** ...` sub-bullet (submitted from the
    dashboard, not yet folded by the loop) is lifted out into `answer` and
    kept out of `body`, so the view can show an answered-awaiting-fold state
    distinctly instead of an ambiguous open one. `answer` is None while
    unanswered. An Answer bullet is never mistaken for a new entry (even
    un-indented), so it can't swallow the questions that follow it.
    """
    items = []
    if not text:
        return items
    in_open = False
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            in_open = line.strip() == "## Open"
            current = None
            continue
        if not in_open:
            continue
        is_answer = line.strip().startswith("- **Answer (via watch")
        if line.startswith("- **") and not is_answer:
            title, _, rest = line[4:].partition("**")
            current = {"title": title,
                       "body": rest.strip() + "\n" if rest.strip() else "",
                       "answer": None}
            items.append(current)
        elif current is not None:
            if is_answer:
                current["answer"] = line.strip().split(":**", 1)[-1].strip()
            else:
                current["body"] += line + "\n"
    return items


def append_answer(text, title, answer, stamp):
    """Insert an answer bullet at the end of the titled Open entry.

    Returns (new_text, matched). Pure — testable without a filesystem.
    """
    block = f"  - **Answer (via watch, {stamp}):** {answer}"
    lines = text.splitlines()
    out = []
    in_open = False
    in_target = False
    matched = False

    def close_target():
        nonlocal in_target
        if in_target:
            out.append(block)
            in_target = False

    for line in lines:
        if line.startswith("## "):
            close_target()
            in_open = line.strip() == "## Open"
        elif in_open and line.startswith("- **"):
            close_target()
            if line[4:].split("**", 1)[0] == title:
                in_target = True
                matched = True
        out.append(line)
    close_target()
    return "\n".join(out) + "\n", matched


def open_question_count(questions_text):
    """Count of Open entries still awaiting an answer — the badge should
    reflect what needs the human, so answered-awaiting-fold entries don't
    count (they're the loop's to fold, not the human's to answer)."""
    return sum(1 for q in parse_open_questions(questions_text)
               if not q["answer"])


def _safe_json(text):
    try:
        return json.loads(text) if text else None
    except ValueError:      # torn mid-write read: degrade, don't 500
        return None


def collect(target):
    now = time.time()
    dw = os.path.join(target, ".dreamwork")
    questions = read_text(os.path.join(dw, "questions.md"))
    return {
        "target": os.path.abspath(target),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dreams": list_dreams(os.path.join(dw, "dreams"), now),
        "dreams_archive": list_dreams(
            os.path.join(dw, "dreams", "archive"), now),
        "files": {
            "DREAMWORK.md": read_text(os.path.join(target, "DREAMWORK.md")),
            "questions.md": questions,
            "lessons.md": read_text(os.path.join(dw, "lessons.md")),
            "skill-version": (read_text(
                os.path.join(dw, "skill-version")) or "").strip(),
        },
        "reviews": [
            {"name": n, "mtime": os.path.getmtime(
                os.path.join(dw, "review", n))}
            for n in sorted(os.listdir(os.path.join(dw, "review")),
                            reverse=True)
            if n.endswith(".html")
        ] if os.path.isdir(os.path.join(dw, "review")) else [],
        "open_questions": open_question_count(questions),
        "questions_open": parse_open_questions(questions),
        "status": _safe_json(read_text(os.path.join(dw, "status.json"))),
        "git": git_tail(target),
    }


def watched_mtime(target):
    latest = 0.0
    paths = [os.path.join(target, "DREAMWORK.md"),
             os.path.join(target, ".git", "logs", "HEAD")]
    dw = os.path.join(target, ".dreamwork")
    for root, _dirs, files in os.walk(dw):
        paths.extend(os.path.join(root, f) for f in files)
    for p in paths:
        try:
            latest = max(latest, os.path.getmtime(p))
        except OSError:
            pass
    return latest


def persistent_port(target):
    marker = os.path.join(target, ".dreamwork", "watch-port")
    saved = read_text(marker)
    if saved and saved.strip().isdigit():
        return int(saved.strip())
    port = random.randrange(3000, 63000)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as f:
            f.write(f"{port}\n")
    except OSError:
        pass
    return port


ANSWER_LOCK = threading.Lock()


def resolve_confined(target, rel):
    """Absolute path for `rel` iff it stays under target root, else None.

    The confinement gate for every file-serving path (/file, review
    artifacts). Pure; testable.
    """
    if not rel or rel.startswith(("/", "~")):
        return None
    full = os.path.realpath(os.path.join(target, rel))
    root = os.path.realpath(target)
    if full == root or not full.startswith(root + os.sep):
        return None
    return full


def log_event(target, line):
    """One-line user-action summary for agents (.dreamwork/watch-events.log).

    Best-effort append; points an agent at the right file and next step.
    Gitignored ephemera. Agents tail it with a Monitor tool (instant wake)
    or check its mtime each tick.
    """
    try:
        path = os.path.join(target, ".dreamwork", "watch-events.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


# Human-submitted loop commands (POST /command) — the canonical steering
# vocabulary. Each becomes a source-tagged watch-events.log line the loop's
# tail monitor wakes on (same transport as answers); no file is written.
COMMAND_KINDS = ("add-idea", "do-next", "do-now", "maintenance")


def command_line(kind, text):
    """Source-tagged watch-events.log line for a human-submitted command.

    Pure; testable. do-next may carry no text (it just nudges selection)."""
    body = f": {text}" if text else ""
    return f"command via watch: {kind}{body}"


def make_handler(target, dev=False):
    page = PAGE.replace("/*DEV*/false", "true") if dev else PAGE

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body, ctype):
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            # Same-document routes all return the one app shell; the client
            # router renders the matching view (deep links keep working).
            if parsed.path in ("/", "/questions", "/file", "/review"):
                self._send(page, "text/html")
            elif parsed.path == "/data.json":
                self._send(json.dumps(collect(target)), "application/json")
            elif parsed.path == "/mtime":
                # "<generation> <watched-mtime>": generation gates a full
                # reload (new server build), mtime gates a data re-render.
                self._send(f"{GENERATION} {watched_mtime(target)}",
                           "text/plain")
            elif parsed.path == "/filedata":
                rel = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = resolve_confined(target, rel)
                text = read_text(full) if full else None
                if text is None:
                    self.send_error(404)
                    return
                self._send(json.dumps({"path": rel, "content": text}),
                           "application/json")
            elif parsed.path == "/reviewraw":
                # The raw self-contained artifact, for the /review view's
                # iframe (style isolation). /review itself serves the shell;
                # the client router renders the review view around this.
                name = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = (resolve_confined(
                    target, os.path.join(".dreamwork", "review", name))
                    if name and "/" not in name else None)
                text = read_text(full, limit=2_000_000) if full else None
                if text is None:
                    self.send_error(404)
                    return
                self._send(text, "text/html")   # self-contained artifact
            else:
                self.send_error(404)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 20_000:
                self.send_error(413)
                return None
            try:
                return json.loads(self.rfile.read(length))
            except ValueError:
                self.send_error(400)
                return None

        def do_POST(self):
            # Two human-authorized write paths, both localhost-only: /answer
            # folds an answer into questions.md; /command drops a steering
            # line into the events log. Everything else is read-only.
            if self.path == "/answer":
                self._handle_answer()
            elif self.path == "/command":
                self._handle_command()
            else:
                self.send_error(404)

        def _handle_answer(self):
            req = self._read_json()
            if req is None:
                return
            try:
                title = str(req["question"]).strip()
                answer = str(req["answer"]).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if not title or not answer:
                self.send_error(400)
                return
            qpath = os.path.join(target, ".dreamwork", "questions.md")
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with ANSWER_LOCK:
                text = read_text(qpath)
                if text is None:
                    self.send_error(404)
                    return
                new_text, matched = append_answer(text, title, answer, stamp)
                if not matched:
                    self.send_error(409)
                    return
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(new_text)
            log_event(target,
                      f'answer: "{title}" -> .dreamwork/questions.md '
                      f'(fold the answer, act, move to Answered)')
            self._send(json.dumps({"ok": True}), "application/json")

        def _handle_command(self):
            req = self._read_json()
            if req is None:
                return
            try:
                kind = str(req["kind"]).strip()
                text = str(req.get("text", "")).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if kind not in COMMAND_KINDS or (kind != "do-next" and not text):
                self.send_error(400)
                return
            log_event(target, command_line(kind, text))
            self._send(json.dumps({"ok": True}), "application/json")

        def log_message(self, *_args):
            pass

    return Handler


def _watch_source_and_restart(interval=1.0):
    """--autoreload: re-exec this process when its own source changes, so an
    edit takes effect with no manual restart. The listening socket is
    close-on-exec (Python default) so the port frees for the new image;
    clients reload on the changed GENERATION. Daemon thread; never blocks."""
    try:
        last = os.path.getmtime(__file__)
    except OSError:
        return
    while True:
        time.sleep(interval)
        try:
            now = os.path.getmtime(__file__)
        except OSError:
            continue
        if now != last:
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable] + sys.argv)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--target", default=".", metavar="DIR")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--open", action="store_true",
                   help="open the dashboard in a browser")
    p.add_argument("--dev", action="store_true",
                   help="dev mode: show an fps counter on the page")
    p.add_argument("--autoreload", action="store_true",
                   help="re-exec on source change (implied by --dev)")
    args = p.parse_args(argv)
    port = args.port or persistent_port(args.target)
    try:
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port), make_handler(args.target, dev=args.dev))
    except OSError as e:
        raise SystemExit(
            f"watch.py: cannot bind 127.0.0.1:{port} ({e.strerror}). "
            f"Another instance may be running (port persisted in "
            f".dreamwork/watch-port); stop it or pass --port.")
    url = f"http://127.0.0.1:{port}/"
    print(f"dreamwork watch: {url} (target {os.path.abspath(args.target)})")
    if args.open:
        webbrowser.open(url)
    if args.autoreload or args.dev:
        threading.Thread(target=_watch_source_and_restart,
                         daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
