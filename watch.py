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

# The steering vocabulary — ONE source. The server validates POST /command
# against it, the composer renders its buttons and its hover menu from it,
# and the popped-out form fills its options from it, so a new kind is one
# entry here and nothing else. Order is display order; `common` kinds get a
# button in the composer, the rest live in the hover menu. Plugin-contributed
# kinds (#86) append to this list — nothing downstream assumes a fixed set.
COMMANDS = (
    {"kind": "add-idea", "label": "add idea", "common": True,
     "desc": "park a thought; the loop picks it up when it chooses next"},
    {"kind": "do-next", "label": "do next", "common": True,
     "desc": "jump this to the front of the queue (text optional)"},
    {"kind": "do-now", "label": "do now", "common": True,
     "desc": "interrupt the current increment and start this instead"},
    {"kind": "maintenance", "label": "maintenance", "common": False,
     "desc": "housekeeping: grooming, re-reads, alignment passes"},
)

# Design tokens + shared shell: every watch page renders through these,
# so a redesign is a token/component edit, not a page-by-page hunt.
STYLE = """<style>
  :root { --bg:#0b0f19; --panel:#111827; --panel2:#1e293b;
    --line:#1f2937; --border:#334155; --text:#d1d5db; --bright:#f3f4f6;
    --lit:#e5e7eb; --muted:#9ca3af; --dim:#6b7280; --dimmer:#4b5563;
    --accent:#a5b4fc; --space:1.6rem; --radius:4px; }
  /* Scrollbars are chrome, and chrome should recede: hairline track,
     dim thumb, no arrows. Firefox first, then the WebKit pseudos. */
  * { scrollbar-width:thin; scrollbar-color:var(--dimmer) transparent; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:var(--dimmer);
                              border-radius:var(--radius); }
  ::-webkit-scrollbar-thumb:hover { background:var(--dim); }
  ::-webkit-scrollbar-corner { background:transparent; }
  body { background:var(--bg); color:var(--text); margin:0;
         padding:2.5rem 1rem;
         font-family:ui-monospace,'JetBrains Mono',monospace; font-size:.8rem; }
  .wrap { max-width:72ch; margin:0 auto; position:relative;
          perspective:1500px; }
  header { color:var(--bright); font-size:1rem; margin-bottom:.25rem; }
  #meta { color:var(--dim); margin-bottom:2rem; }
  #meta .q { color:var(--accent); }
  /* The heading survives navigation, so its parts travel rather than
     reload (#110). Crumbs are inline-block because a transform does nothing
     to an inline box; the separator belongs to the crumb that FOLLOWS, so a
     departing crumb takes no punctuation with it. */
  #chrome { position:relative; }
  .crumb, .htitle { display:inline-block;
    transition:transform .85s cubic-bezier(.32,.1,.2,1),
               opacity .55s ease, filter .55s ease; }
  /* non-breaking spaces: an inline-block collapses the leading/trailing
     whitespace of generated content, so " · " would render flush */
  .crumb + .crumb::before { content:"\\00a0\\00b7\\00a0"; color:var(--dim); }
  /* the snapped start state for anything arriving: transition:none so it
     BEGINS here instead of animating toward here (the enter-snap rule) */
  .dreamin { transition:none; opacity:0; filter:blur(4px);
             transform:translateY(5px); }
  /* a departing crumb is lifted out of flow at its own rect, so survivors
     close the gap underneath it while it dreams away in place */
  .crumb.crumbout { position:absolute; z-index:2; pointer-events:none; }
  .crumb.crumbout::before { content:none; }
  .crumb.crumbgone { opacity:0; filter:blur(5px); transform:translateY(-7px); }
  @media (prefers-reduced-motion: reduce) {
    .crumb, .htitle { transition:none; }
  }
  .label { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
           font-size:.7rem; margin:var(--space) 0 .5rem; }
  details { margin:.25rem 0; }
  summary { cursor:pointer; color:var(--lit); list-style:none; }
  summary::before { content:"+ "; color:var(--dim); }
  details[open] > summary::before { content:"- "; }
  .age { color:var(--dim); margin-left:.5rem; }
  pre { white-space:pre-wrap; color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  /* rendered prose (#102). Same hairline rail and colour as the <pre> it
     replaces — this changes how the text WRAPS, not how the page reads. */
  .md { color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  .md > :first-child { margin-top:0; }
  .md > :last-child { margin-bottom:0; }
  .md p { margin:.45rem 0; }
  .md .mdh { color:var(--lit); margin:.7rem 0 .25rem; }
  /* a bullet hangs: the marker sits in the gutter and wrapped lines line up
     under the text, so nesting stays legible at any column width. */
  .md .mdli { margin:.28rem 0 .28rem calc(var(--lvl, 0) * 1.9ch);
              padding-left:1.6ch; text-indent:-1.6ch; }
  .md .mdli::before { content:"\\00b7  "; color:var(--dim); }
  .md pre.mdcode { margin:.45rem 0; white-space:pre; overflow-x:auto; }
  /* emphasis is luminance, not weight (see mdSpans) */
  .md strong, .anstext strong, .follow strong {
    font-weight:inherit; color:var(--bright); }
  .md em, .anstext em, .follow em { font-style:italic; color:var(--muted); }
  code { color:var(--lit); background:var(--panel);
         border-radius:3px; padding:0 .3ch; }
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
  /* the three qaCard states (#105) are class modifiers on one card, so the
     shared parts are styled once and only the differences are stated here.
     awaiting: a quiet accent rail marks it apart from open questions; no
     input box, the answer shown plainly. folded: the loop has filed it, so
     it recedes. */
  .qa.awaiting { border-left:2px solid var(--accent); padding-left:.9rem;
    margin-left:-1.1rem; opacity:.82; }
  .qa.awaiting .qt::before { content:"✓ "; color:var(--accent); }
  .qa.folded .qt { color:var(--muted); }
  .anstag { color:var(--dim); text-transform:uppercase; letter-spacing:.07em;
    font-size:.65rem; margin:.35rem 0 .15rem; }
  /* an answer is the human's, in a card whose body the loop wrote — so it
     reads at the same brightness as his notes do (#109) */
  .anstext { color:var(--lit); white-space:pre-wrap; }
  /* follow-up thread + a quiet add-a-note box on every question entry */
  .thread { border-left:1px solid var(--line); padding-left:1ch;
    margin:.3rem 0 .2rem; }
  .follow { color:var(--muted); font-size:.75rem; margin:.25rem 0;
    padding-left:2.6ch; text-indent:-2.6ch; }
  .follow::before { content:"\\21b3  "; color:var(--dim); }
  /* authorship (#109): the human's words sit a step up the text ramp from
     the loop's, and each carries a dim label. Luminance, not accent. */
  .follow.human { color:var(--lit); }
  .who { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
    font-size:.62rem; margin-right:.7ch; }
  .notewrap { display:flex; gap:.4rem; align-items:flex-start;
    margin:.3rem 0 .2rem; max-width:56ch; }
  .notebox { flex:1; background:var(--panel); color:var(--text);
    border:1px solid var(--line); border-radius:var(--radius); font:inherit;
    font-size:.75rem; padding:.25rem .45rem; min-height:1.7rem; resize:vertical;
    box-sizing:border-box; opacity:.65; transition:opacity .3s ease; }
  .notebox:focus { opacity:1; }
  .notebtn { background:transparent; color:var(--dim); border:1px solid var(--line);
    border-radius:var(--radius); font:inherit; font-size:.7rem;
    padding:.2rem .6rem; cursor:pointer; align-self:stretch;
    transition:color .3s ease, border-color .3s ease; }
  .notebtn:hover { color:var(--accent); border-color:var(--border); }
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
  /* The incoming view surfaces from BEHIND the outgoing ghost (z-index): it
     starts pushed back in depth (translateZ), lower and scaled down, at true
     opacity 0 — a delayed, slow-start opacity so it's genuinely absent for
     the first ~150ms, then rises as it drifts forward into focus. The ghost
     (in front) lifts up and toward the viewer as it dissolves. */
  #view { transition:opacity .8s cubic-bezier(.62,0,.34,1) .14s,
                     transform 1s cubic-bezier(.32,.1,.2,1);
          transform-origin:50% 40%; will-change:opacity, transform, filter; }
  /* the start state must SNAP (transition:none) — with the transition live,
     adding .enter would animate *toward* opacity 0 and get removed a frame
     later, so it never actually left ~1 (the old "pops in" bug). Snapping to
     0 + pushed-back, then removing .enter, gives a true fade-up from depth. */
  #view.enter { transition:none; opacity:0;
                transform:translateY(30px) translateZ(-110px) scale(.93); }
  /* the ghost is pinned to the box the outgoing view occupied (top/width/
     height set in crossfade), not stretched to the wrapper — the chrome now
     sits above #view, and a resizing column must not re-wrap the departing
     content while it is still opaque (#107). */
  .ghost { position:absolute; left:0; top:0; z-index:1; pointer-events:none;
           opacity:1; transform-origin:50% 40%;
           transition:opacity 1.05s cubic-bezier(.4,0,.66,.38),
                      transform 1.15s cubic-bezier(.34,0,.6,.4); }
  .ghost.out { opacity:0;
               transform:translateY(-34px) translateZ(70px) scale(1.07); }
  @media (prefers-reduced-motion: reduce) {
    #view, .ghost { transition:none; }
  }
  /* review view: the artifact fills the main column; the originating
     question docks beside it (sticky) so it can be answered with the
     review in front of you. Wider than the 72ch reading column. */
  body.review .wrap { max-width:1360px; }
  /* The column is the one thing on this page that changes SIZE, and the
     motion language says things that change travel rather than teleport
     (#107). So the width glides, on the dissolve's own easing and duration.
     Gated behind .wsliding, added only for a route change: a direct load of
     /review must arrive already wide, not animate its column on first paint.
     overflow-x is clipped for the same window because the departing ghost is
     pinned to its OLD width and would otherwise push a horizontal scrollbar
     while the column narrows underneath it. */
  body.wsliding .wrap { transition:max-width 1s cubic-bezier(.32,.1,.2,1); }
  body.wsliding { overflow-x:hidden; }
  @media (prefers-reduced-motion: reduce) {
    body.wsliding .wrap { transition:none; }
  }
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
  /* the composer: the + opener sits in the heading's left gutter; the
     panel it toggles drifts in through a soft blur (the dream language),
     not a hard pop. reduced-motion just shows/hides. */
  .htitlebar { display:flex; align-items:baseline; gap:.55rem; }
  .htitle { display:inline; }
  /* The opener hangs in the gutter LEFT of the reading column, so its offset
     is only affordable when the gutter exists. It does not on the review
     view's 1360px column, or in any narrow window — the button was sliced in
     half by the page edge (#108). So the pull is CLAMPED to the room that
     actually exists: it hangs out as far as it can, then locks; 0 parks it
     flush with the column, still inset by the body padding.

     `100%` is the containing block's width — .htitlebar's, which is the
     column's — so `(100vw - 100%)/2` IS the gutter, with no need to name the
     column's width (it is `ch`-sized, and `ch` would resolve against the
     button's own font rather than the column's). Doing this in CSS rather
     than JS is what makes the guarantee hold on every frame: the column
     GLIDES on a route change (#107), and a measure-then-write in rAF always
     paints one frame behind that. */
  #cmdplus { flex:none; align-self:center;
    margin-left:calc(-1 * clamp(0px, (100vw - 100%) / 2 - .6rem, 2.4rem));
    width:1.7rem; height:1.7rem; display:grid; place-items:center;
    background:transparent; color:var(--muted);
    border:1px solid var(--border); border-radius:var(--radius);
    font:inherit; font-size:1.15rem; line-height:1; cursor:pointer;
    transition:color .3s ease, border-color .3s ease, background .3s ease,
               transform .35s cubic-bezier(.32,.12,.2,1); }
  #cmdplus:hover, #cmdplus.on { color:var(--accent);
    border-color:var(--accent); background:rgba(99,102,241,.09); }
  #cmdplus.on { transform:rotate(45deg); }
  #cmdpalette { position:fixed; z-index:30; top:4rem; left:1rem;
    width:min(38ch,92vw); background:rgba(11,15,25,.94);
    border:1px solid var(--border); border-radius:8px; padding:1rem 1rem .85rem;
    box-shadow:0 14px 44px rgba(0,0,0,.5); backdrop-filter:blur(7px);
    visibility:hidden; opacity:0; transform:translateY(-8px) scale(.97);
    filter:blur(6px); pointer-events:none;
    transition:opacity .5s cubic-bezier(.32,.12,.2,1),
               transform .5s cubic-bezier(.32,.12,.2,1),
               filter .5s ease, visibility 0s linear .5s; }
  #cmdpalette.open { visibility:visible; opacity:1; transform:none;
    filter:none; pointer-events:auto; transition-delay:0s; }
  #cmdpalette .label { margin-top:0; }
  #cmdform textarea { width:100%; box-sizing:border-box;
    background:var(--panel); color:var(--text); border:1px solid var(--line);
    border-radius:var(--radius); font:inherit; padding:.4rem; margin:.3rem 0;
    min-height:3.4rem; resize:vertical; }
  /* command selection: a button group whose background indicator SLIDES to
     the active option. The one piece of crisp motion in the composer, kept
     soft (.3s, the dream easing). The selected label glows rather than
     changing metrics — a text effect that moved layout would resize the
     buttons and so move the target the indicator is chasing. */
  .cmdkinds { position:relative; display:flex; flex-wrap:wrap; gap:.1rem;
    margin:.3rem 0 .1rem; }
  .cmdind { position:absolute; top:0; left:0; z-index:0; width:0; height:0;
    background:var(--panel2); border:1px solid var(--border);
    border-radius:var(--radius); box-sizing:border-box;
    transition:transform .3s cubic-bezier(.32,.12,.2,1),
               width .3s cubic-bezier(.32,.12,.2,1),
               height .3s cubic-bezier(.32,.12,.2,1); }
  .cmdind.snap { transition:none; }        /* land, never slide (see JS) */
  .cmdkind { position:relative; z-index:1; background:none; font:inherit;
    border:1px solid transparent; border-radius:var(--radius);
    color:var(--dim); padding:.28rem .45rem; cursor:pointer;
    transition:color .3s ease, text-shadow .3s ease; }
  .cmdkind:hover { color:var(--muted); }
  .cmdkind.on { color:var(--accent);
    text-shadow:0 0 12px rgba(165,180,252,.45); }
  /* Hover discoverability: the row carries the common kinds, and the ⋯ icon
     reveals EVERY command with a one-line description — so a rarely-used kind
     is discoverable rather than hidden knowledge. Rendered from COMMANDS at
     any length, so plugin-contributed kinds (#86) just appear. */
  .cmdpick { display:flex; align-items:flex-start; gap:.1rem; }
  .cmdmore { position:relative; display:inline-flex; align-items:center; }
  .cmdmorebtn { background:none; border:1px solid transparent; font:inherit;
    color:var(--dimmer); padding:.28rem .5rem; cursor:pointer; line-height:1;
    border-radius:var(--radius); transition:color .3s ease; }
  .cmdmore:hover .cmdmorebtn, .cmdmore:focus-within .cmdmorebtn {
    color:var(--accent); }
  /* no gap between icon and menu: the pointer must be able to travel from one
     to the other without ever leaving .cmdmore, or the menu closes en route */
  .cmdmenu { position:absolute; z-index:31; top:100%; left:0;
    width:max(32ch,100%); padding:.3rem;
    background:rgba(11,15,25,.97); border:1px solid var(--border);
    border-radius:8px; box-shadow:0 14px 44px rgba(0,0,0,.55);
    backdrop-filter:blur(7px);
    visibility:hidden; opacity:0; transform:translateY(-6px);
    filter:blur(5px); pointer-events:none;
    transition:opacity .34s cubic-bezier(.32,.12,.2,1),
               transform .34s cubic-bezier(.32,.12,.2,1),
               filter .34s ease, visibility 0s linear .34s; }
  .cmdmore:hover .cmdmenu, .cmdmore:focus-within .cmdmenu {
    visibility:visible; opacity:1; transform:none; filter:none;
    pointer-events:auto; transition-delay:0s; }
  .cmdmenuitem { display:block; width:100%; box-sizing:border-box;
    text-align:left; background:none; border:1px solid transparent;
    border-radius:var(--radius); font:inherit; color:var(--muted);
    padding:.3rem .45rem; cursor:pointer;
    transition:background .25s ease, color .25s ease; }
  .cmdmenuitem:hover, .cmdmenuitem:focus-visible {
    background:var(--panel2); color:var(--lit); }
  .cmdmenuitem.on .cmk { color:var(--accent); }
  .cmdmenuitem .cmd { display:block; color:var(--dim); font-size:.7rem;
    margin-top:.1rem; }
  .cmdrow { display:flex; gap:.5rem; align-items:center; margin-top:.2rem; }
  .cmdrow button { background:var(--panel2); color:var(--accent);
    border:1px solid var(--border); border-radius:var(--radius); font:inherit;
    padding:.25rem .8rem; cursor:pointer; }
  #cmdpop { margin-left:auto; color:var(--muted); }
  #cmdpop:hover { color:var(--accent); }
  .pipbtn { background:none; border:none; color:var(--dim); cursor:pointer;
    padding:0 .35rem; line-height:1; vertical-align:middle;
    transition:color .3s ease; }
  .pipbtn:hover, .pipbtn:focus-visible { color:var(--accent); }
  .pipbtn svg { display:inline-block; vertical-align:-2px; }
  .cmdmsg { color:var(--dim); font-size:.7rem; min-height:1em; margin-top:.5rem;
    transition:color .4s ease; }
  /* no reserved slack under the buttons: the status line only takes room
     once it has something to say, and the panel grows downward to meet it
     (nothing above it moves). */
  .cmdmsg:empty { display:none; }
  .cmdmsg.ok { color:var(--accent); }
  /* dream ripple: a soft ring expanding from a received command / answer */
  .ripple { position:fixed; z-index:40; border-radius:50%; pointer-events:none;
    border:1px solid var(--accent); }
  @media (prefers-reduced-motion: reduce) {
    #cmdplus, #cmdpalette, #layerhint, .cmdind, .cmdkind, .cmdmenu,
    .cmdmenuitem, .cmdmorebtn { transition:none; }
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
<div id="chrome">
 <header class="htitlebar"><button id="cmdplus" type="button"
   title="command the dream" aria-label="open command palette">+</button>
  <span class="htitle"></span></header>
 <div id="meta"></div>
</div>
<div id="view">loading…</div>
<div id="cmdpalette" role="dialog" aria-label="command palette">
 <form id="cmdform" autocomplete="off">
  <div class="label">command the dream</div>
  <div class="cmdpick">
   <div class="cmdkinds" id="cmdkinds" role="radiogroup"
        aria-label="command"></div>
   <div class="cmdmore" id="cmdmore">
    <button type="button" class="cmdmorebtn" aria-haspopup="menu"
            aria-expanded="false" aria-label="all commands">&#8943;</button>
    <div class="cmdmenu" id="cmdmenu" role="menu"></div>
   </div>
  </div>
  <textarea id="cmdtext" placeholder="a thought for the dream…"></textarea>
  <div class="cmdrow">
   <button type="submit" id="cmdsend">send</button>
   <button type="button" id="cmdpop"
           title="pop out — stays while you navigate"><svg viewBox="0 0 22 18"
     width="13" height="11" aria-hidden="true"><rect x="1" y="1" width="20"
     height="16" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"
     /><rect x="10.5" y="8.5" width="9" height="7" rx="1.2"
     fill="currentColor"/></svg> pop out</button>
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
/* a small standard picture-in-picture glyph — a low-emphasis button placed
   after doc/review affordances so pop-out is discoverable, never surprising.
   Clicking it floats the target (data-pipurl) in an identity-headed window. */
const PIP_SVG = '<svg viewBox="0 0 22 18" width="14" height="12"' +
  ' aria-hidden="true"><rect x="1" y="1" width="20" height="16" rx="2.5"' +
  ' fill="none" stroke="currentColor" stroke-width="1.6"/>' +
  '<rect x="10.5" y="8.5" width="9" height="7" rx="1.2"' +
  ' fill="currentColor"/></svg>';
const pipBtn = (url, label) =>
  `<button class="pipbtn" type="button" title="pop out — floats while you` +
  ` navigate" aria-label="pop out ${esc(label)}" data-pipurl="${esc(url)}"` +
  ` data-piplabel="${esc(label)}">${PIP_SVG}</button>`;
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
/* ── rendered prose (#102) ────────────────────────────────────────────────
   The loop writes its files hard-wrapped at ~72 columns. A <pre> renders
   those breaks literally and the browser re-wraps them again at a narrower
   reading column, so every paragraph breaks twice into a ragged mess. So we
   join the wraps back into paragraphs and let the column do the wrapping.

   The line this draws: MARKDOWN PROSE REFLOWS, RAW TEXT DOES NOT. Question
   bodies, answers, follow-ups, dreams and the dashboard's .md peeks are
   prose the page composes, and they reflow. `/file`, status JSON and the git
   tail are shown as they are on disk, and stay verbatim in a <pre>.

   Four things must survive the join, because each one carries meaning a
   joined line would destroy:
     · a blank line is a paragraph break
     · a leading `- ` is a real list item and its INDENT is its nesting —
       questions.md's whole parser rests on a sub-bullet never looking like
       an entry, and flattening the marker would render the two identically
     · a ``` fence is code, and code is not prose
     · a `#` heading stands alone
   Every other line break is a wrap, and gets joined with a space. */
const MD_BULLET = /^(\\s*)[-*]\\s+(.*)$/;
function mdBlocks(text) {
  const out = [];
  let cur = null, fence = null;
  const flush = () => { if (cur) { out.push(cur); cur = null; } };
  for (const line of String(text == null ? '' : text).split('\\n')) {
    if (/^\\s*```/.test(line)) {                 // fence open or close
      if (fence) { out.push({ kind:'fence', text: fence.join('\\n') }); fence = null; }
      else { flush(); fence = []; }
      continue;
    }
    if (fence) { fence.push(line); continue; }
    if (!line.trim()) { flush(); continue; }      // blank line ends a block
    if (/^\\s*#{1,6}\\s/.test(line)) {
      flush(); out.push({ kind:'h', text: line.replace(/^\\s*#+\\s*/, '') }); continue;
    }
    const m = line.match(MD_BULLET);
    if (m) { flush(); cur = { kind:'li', indent:m[1].length, text:m[2] }; continue; }
    if (cur) { cur.text += ' ' + line.trim(); continue; }   // a wrap: join it
    cur = { kind:'p', indent:0, text: line.trim() };
  }
  flush();
  if (fence) out.push({ kind:'fence', text: fence.join('\\n') });
  return out;
}
/* Nesting is the RANK of a bullet's indent among the indents actually used,
   not the raw column count: a question body carries the source file's own
   2-space indent, so absolute columns would push every sub-bullet one level
   too deep. Rank is invariant to whatever base indent the text arrived with. */
function mdRender(text, inline) {
  const blocks = mdBlocks(text);
  const levels = [...new Set(blocks.filter(b => b.kind === 'li')
    .map(b => b.indent))].sort((a, b) => a - b);
  return blocks.map(b =>
    b.kind === 'fence' ? `<pre class="mdcode">${esc(b.text)}</pre>` :
    b.kind === 'h' ? `<div class="mdh">${inline(b.text)}</div>` :
    b.kind === 'li' ? `<div class="mdli" style="--lvl:${levels.indexOf(b.indent)}">` +
                      `${inline(b.text)}</div>`
                    : `<p>${inline(b.text)}</p>`).join('');
}
/* Inline markdown the loop actually writes: **bold**, *em*, `code`. Bold is
   rendered as LUMINANCE — the page already says "more important" with its
   text ramp, and a mono bold would change metrics to say no more. Order is
   load-bearing: the linkifiers inject <a> INSIDE the backticks, so code
   spans convert after them and swallow the link; ** before * so a bold pair
   is never read as two emphases. */
const mdSpans = h => h
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
  .replace(/(^|[\\s(\\[])\\*([^*\\s][^*]*?)\\*(?=$|[\\s.,;:)\\]])/g, '$1<em>$2</em>');
const mdInline = t => mdSpans(linkify(esc(t)));
const mdInlineReview = title => t =>
  mdSpans(linkify(linkifyReview(esc(t), title)));
const mdB = t => `<div class="md">${mdRender(t, mdInline)}</div>`;
const mdBReview = (t, title) =>
  `<div class="md">${mdRender(t, mdInlineReview(title))}</div>`;
/* a follow-up thread and a quiet add-a-note box, carried by every question
   entry in every state. */
/* Authorship is visible wherever the human's words sit beside the loop's
   (#109). A note carries who wrote it, and the page says so QUIETLY: a dim
   uppercase label — the same idiom as every other label here — and the
   human's words a step brighter on the text ramp, because emphasis on this
   page is luminance. No accent: the accent is for live and actionable
   things, and a note is neither. An unattributed note (an unknown tag) gets
   no label at all — a wrong attribution is worse than an absent one. */
const WHO = { human: 'you', loop: 'loop' };
const followThread = follows => (follows && follows.length)
  ? `<div class="thread">` + follows.map(f => {
      const a = f && f.author, txt = f && f.text != null ? f.text : f;
      return `<div class="follow${a ? ' ' + a : ''}">` +
        (WHO[a] ? `<span class="who">${WHO[a]}</span>` : '') +
        `${mdInline(txt)}</div>`;
    }).join('') + `</div>`
  : '';
const noteBox = key =>
  `<div class="notewrap"><textarea class="notebox" id="nb${key}"` +
  ` placeholder="add a note…"></textarea>` +
  `<button class="notebtn" onclick="sendComment('${key}')">note</button></div>`;
const qaFoot = (follows, key) => followThread(follows) + noteBox(key);
/* THE question component (#105). Every question on every surface —
   dashboard, /questions, the review dock, and the answer-submit morph —
   renders through this one card, so a change to how a question looks is one
   edit rather than a hunt.

   Contract: `qaCard(q, key)`. The key ADDRESSES the entry in live `data`:
   'o'+index into `questions_open`, 'a'+index into `answered_entries`. It is
   never a title round-tripped through the DOM, so a stale render cannot
   write to the wrong entry. The state is DERIVED from the key and the entry,
   never passed in, so no caller can render an entry in a state its own data
   contradicts:
     open     — needs the human; shows an answer box
     awaiting — answered from the page, the loop hasn't folded it yet; the
                answer on a quiet accent rail with a ✓, no box, so it never
                reads as still-open
     folded   — key is 'a…'; the loop has folded it into `## Answered`
   `qaInner` is split out so the submit morph can restate a live card in its
   new state in place instead of assembling look-alike markup. */
const qaState = (q, key) =>
  key[0] === 'a' ? 'folded' : (q.answer ? 'awaiting' : 'open');
const qaInner = (q, key) => {
  const st = qaState(q, key);
  const body = q.body && q.body.trim() ? mdBReview(q.body.trim(), q.title) : '';
  const answer = st === 'awaiting'
    ? `<div class="anstag">answered · awaiting fold</div>` +
      `<div class="anstext">${mdInline(q.answer)}</div>` : '';
  const box = st === 'open'
    ? `<textarea id="qa${key}" placeholder="answer…"></textarea>` +
      `<button onclick="sendAnswer('${key}')">answer</button>` : '';
  return `<div class="qt">${esc(q.title)}</div>${body}${answer}${box}` +
    qaFoot(q.follows, key);
};
const qaCard = (q, key) =>
  `<div class="qa ${qaState(q, key)}" data-qkey="${key}">` +
  `${qaInner(q, key)}</div>`;
/* resolve a card key against live data — the one place a key becomes an
   entry, for both writes and re-renders. */
const qaEntry = key => {
  if (!data || !key) return null;
  const list = key[0] === 'a' ? data.answered_entries : data.questions_open;
  return (list || [])[+key.slice(1)] || null;
};
async function postAnswer(title, text) {
  await fetch('/answer', { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, answer: text }) });
}
async function postComment(title, note, section) {
  await fetch('/comment', { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, comment: note, section }) });
}
"""

VIEWS_JS = """
/* view builders: each returns the inner HTML of #view for one route.
   The dashboard/questions views are data-driven (re-rendered live on
   mtime change); the file view is a static read. */
function dreamBlock(d) {
  return expand(
    `${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span>`,
    mdB(d.content));
}
function buildDashboard(d) {
  let h = `<div id="sections">`;
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
           openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
    if (foldQ.length)
      h += label('answered · awaiting fold') +
           foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  }
  if (d.reviews.length) {
    h += label('reviews') + d.reviews.map(r =>
      `<div><a href="/review?p=${encodeURIComponent(r.name)}">${esc(r.name)}</a>` +
      pipBtn('/reviewraw?p=' + encodeURIComponent(r.name), r.name) +
      `<span class="age" data-mt="${r.mtime}"></span></div>`).join('');
  }
  h += label('files') +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         expand(n, mdB(d.files[n]))).join('');
  if (d.status)
    h += label('status') + preB(JSON.stringify(d.status, null, 2));
  h += label('commits') + `<div class="git">` +
       d.git.map(l => `<div class="${l.includes('dreamwork(maintain:') ? 'maint' : ''}">${esc(l)}</div>`).join('') +
       `</div></div>`;
  return h;
}
function buildQuestions(d) {
  // three explicit states: open (needs the human), answered-awaiting-fold
  // (the loop's to fold), and the folded Answered section — all three the
  // same qaCard, grouped by the state it derives from the key + entry.
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let h = `<div id="qsections">`;
  h += label(`open (${openQ.length})`) +
       (openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('') ||
        '<div class="dim">none — all answered</div>');
  if (foldQ.length)
    h += label(`answered · awaiting fold (${foldQ.length})`) +
         foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  h += label('answered') + (d.answered_entries.length
    ? d.answered_entries.map((e, j) => qaCard(e, 'a' + j)).join('')
    : '<div class="dim">(none yet)</div>');
  return h + `</div>`;
}
function buildFile(param, text) {
  const body = text == null
    ? '<div class="dim">not found</div>'
    : `<pre>${esc(text)}</pre>`;
  return `<div id="filebody">${body}</div>`;
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
        label('answering') + qaCard(d.questions_open[i], 'o' + i) + `</aside>`;
  }
  return `<div id="reviewwrap"${dock ? '' : ' class="nodock"'}>` +
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
async function sendAnswer(key) {
  const el = document.getElementById('qa' + key);
  const q = qaEntry(key);
  if (!el || !el.value.trim() || !q) return;
  const val = el.value.trim();
  const card = el.closest('.qa');
  const fromRect = el.getBoundingClientRect();   // the box the text lived in
  await postAnswer(q.title, val);
  if (!card) return;
  holdRerenderUntil = Date.now() + 1600;   // let the morph settle before regroup
  // the morph IS the confirmation: the box reshapes into the answered state,
  // the typed text lifting from the box into the rendered answer (the
  // lifted-hero rule — the answer text is the tracked element). A soft
  // ripple accents it. reduced-motion just swaps to the answered state.
  // Restated through the SAME component, so it cannot drift from a fresh
  // render of the same entry.
  const next = Object.assign({}, q, { answer: val });
  card.className = 'qa ' + qaState(next, key);
  card.innerHTML = qaInner(next, key);
  const anstext = card.querySelector('.anstext');
  if (typeof ripple === 'function')
    ripple(fromRect.left + fromRect.width / 2, fromRect.top + 22);
  if (!rmr && anstext && typeof flipDock === 'function')
    flipDock(anstext, fromRect, anstext.getBoundingClientRect());
}
/* thread a follow-up note onto any entry — same lifted-hero morph as an
   answer: the note lifts from the box into the thread, ripple accenting. */
async function sendComment(key) {
  const el = document.getElementById('nb' + key);
  const entry = qaEntry(key);
  if (!el || !el.value.trim() || !entry) return;
  const val = el.value.trim();
  const card = el.closest('.qa');
  const fromRect = el.getBoundingClientRect();
  await postComment(entry.title, val, key[0] === 'o' ? 'Open' : 'Answered');
  el.value = '';
  holdRerenderUntil = Date.now() + 1600;
  if (!card) return;
  let thread = card.querySelector('.thread');
  if (!thread) {
    thread = document.createElement('div'); thread.className = 'thread';
    card.insertBefore(thread, card.querySelector('.notewrap'));
  }
  const f = document.createElement('div');
  f.className = 'follow human';        // it is his; say so, same as a reload
  f.innerHTML = `<span class="who">${WHO.human}</span>` + mdInline(val);
  thread.appendChild(f);
  if (typeof ripple === 'function') ripple(fromRect.left + 24, fromRect.top + 14);
  if (!rmr && typeof flipDock === 'function')
    flipDock(f, fromRect, f.getBoundingClientRect());
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
/* after a local answer morph, hold the live re-render briefly so the card
   settles in place before the loop's fresh data regroups it (#79/#81). */
let holdRerenderUntil = 0;
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
/* ── the persistent chrome (#110) ─────────────────────────────────────────
   The heading is not content, it is the page's frame: the same + opener, a
   title, and a crumb row, on every route. While it lived inside #view it
   dissolved and was rebuilt on every navigation, which is why a route change
   read as "the elements jump around" rather than as the page opening up. So
   it is a SIBLING of #view — the standing #dreambg already has — it survives
   the route change, and it travels to its new position.

   Crumbs are KEYED, and that is the whole trick: a survivor has to be
   literally the same element before and after, or a FLIP has nothing to
   measure and you get a fade where a glide was asked for. `home` is one
   crumb across three routes even though its text gains and loses an arrow. */
const TITLES = {
  dashboard: () => 'dreamwork watch',
  questions: () => 'questions',
  file: v => esc(v.param || ''),
  review: v => `review<span class="revname">${esc(v.param || '')}</span>`,
};
function crumbsFor(v, d) {
  const home = { k:'home', html:'<a href="/">&larr; dashboard</a>' };
  if (v.name === 'questions') return [home];
  if (v.name === 'file') return [home,
    { k:'pip', html: pipBtn('/file?p=' + encodeURIComponent(v.param || ''),
                            v.param || 'file') }];
  if (v.name === 'review') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' },
    { k:'pip', html: pipBtn('/reviewraw?p=' + encodeURIComponent(v.param || ''),
                            'review: ' + (v.param || '')) }];
  if (!d) return [];
  return [
    { k:'target', html: esc(d.target) },
    { k:'version', html: esc(d.files['skill-version']) },
    { k:'updated', html:'<span id="upd"></span>' },
    { k:'openq', html: d.open_questions > 0
        ? `<a class="q" href="/questions">${d.open_questions} open ` +
          `question${d.open_questions > 1 ? 's' : ''}</a>`
        : `<a class="q" href="/questions" style="color:var(--dimmer)">` +
          `questions</a>` },
  ];
}
/* where the heading sits RIGHT NOW — taken before the column class flips,
   because that flip is what moves everything. */
function chromeSnapshot() {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return null;
  const at = new Map();
  for (const el of meta.children) at.set(el.dataset.k, el.getBoundingClientRect());
  return { at, title: titleEl.getBoundingClientRect() };
}
/* a departing crumb dreams away where it stood: lifted out of flow at its own
   rect so the survivors can close the gap underneath it, then dissolved on
   the page's mist idiom rather than simply vanishing. */
function departCrumbs(gone) {
  const ch = document.getElementById('chrome');
  if (!ch) return;
  const org = ch.getBoundingClientRect();
  for (const [el, r] of gone) {
    if (!r) { el.remove(); continue; }
    el.classList.add('crumbout');
    el.style.left = (r.left - org.left) + 'px';
    el.style.top = (r.top - org.top) + 'px';
    el.style.width = r.width + 'px';
    ch.appendChild(el);
    void el.offsetWidth;
    el.classList.add('crumbgone');
    setTimeout(() => el.remove(), 900);
  }
}
function renderChrome(v, d, snap) {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return;
  const nextTitle = (TITLES[v.name] || TITLES.dashboard)(v, d);
  const next = crumbsFor(v, d);
  const prev = new Map([...meta.children].map(el => [el.dataset.k, el]));
  const row = [], arrived = [];
  for (const c of next) {
    let el = prev.get(c.k);
    if (el) { prev.delete(c.k); if (el.innerHTML !== c.html) el.innerHTML = c.html; }
    else {
      el = document.createElement('span');
      el.className = 'crumb'; el.dataset.k = c.k; el.innerHTML = c.html;
      if (snap && !rmr) { el.classList.add('dreamin'); arrived.push(el); }
    }
    row.push(el);
  }
  const gone = [...prev].map(([k, el]) => [el, snap ? snap.at.get(k) : null]);
  meta.replaceChildren(...row);
  if (snap && !rmr) departCrumbs(gone); else gone.forEach(([el]) => el.remove());
  if (titleEl.innerHTML !== nextTitle) {
    titleEl.innerHTML = nextTitle;
    if (snap && !rmr) { titleEl.classList.add('dreamin'); arrived.push(titleEl); }
  }
  ages();
  if (!snap || rmr) return;
  // FLIP the survivors from where they stood to where the new row puts them,
  // then release the arrivals from their snapped start state (the enter-snap
  // rule: with an always-on transition, adding the start class animates
  // TOWARD the start value instead of beginning there).
  for (const el of row) {
    const b = snap.at.get(el.dataset.k);
    if (!b) continue;
    const a = el.getBoundingClientRect();
    const dx = b.left - a.left, dy = b.top - a.top;
    if (!dx && !dy) continue;
    el.style.transition = 'none';
    el.style.transform = `translate(${dx}px, ${dy}px)`;
    void el.offsetWidth;
    el.style.transition = '';
    el.style.transform = '';
  }
  requestAnimationFrame(() => arrived.forEach(el => el.classList.remove('dreamin')));
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
    renderChrome(view, data, null);
    return;
  }
  // The review view is a wider column, so a route change onto or off it
  // RESIZES the page. Measure everything that is about to move BEFORE the
  // class flip that moves it.
  const outRect = viewEl.getBoundingClientRect();
  const outW = outRect.width, outH = outRect.height;
  const outTop = viewEl.offsetTop;
  const snap = chromeSnapshot();
  const ghost = viewEl.cloneNode(true);
  ghost.removeAttribute('id'); ghost.className = 'ghost';
  // a cloned iframe would re-fetch and flash while dissolving — drop it;
  // the ghost only needs the chrome/text to blur away.
  ghost.querySelectorAll('iframe').forEach(f => f.remove());
  viewEl.parentNode.appendChild(ghost);
  // Pin the ghost to the box it was rendered in. It is LEAVING: it should
  // dissolve as it was, not re-wrap every paragraph into a new column while
  // still fully opaque — that reflow, at frame 0 and at full opacity, was
  // the "elements jump around" (#107). The chrome now sits above #view, so
  // the ghost is placed at #view's own offset rather than stretched to the
  // wrapper with `inset:0`.
  ghost.style.top = outTop + 'px';
  ghost.style.width = outW + 'px';
  ghost.style.height = outH + 'px';
  // ...and the column itself glides to its new width rather than snapping
  // (see body.wsliding). The incoming view reflows as it widens, behind the
  // mist and up from opacity 0, so the resize reads as the page opening.
  document.body.classList.add('wsliding');
  document.body.classList.toggle('review', !!xopts.review);
  setContent(html);
  renderChrome(view, data, snap);   // the heading travels; it does not reload
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
    document.body.classList.remove('wsliding');
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
    renderChrome(view, data, null);   // first paint: arrive, don't animate
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
    if (mtime !== lastMtime && Date.now() >= holdRerenderUntil) {
      lastMtime = mtime; fetchedAt = Date.now();
      data = await (await fetch('/data.json')).json();
      if (view.name === 'dashboard') setContent(buildDashboard(data));
      else if (view.name === 'questions') setContent(buildQuestions(data));
      // the crumbs carry live numbers too (open count, version) — and the
      // tick re-renders in place, instantly, so they never animate
      renderChrome(view, data, null);
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
  * { scrollbar-width:thin; scrollbar-color:#4b5563 transparent; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#4b5563; border-radius:4px; }
  ::-webkit-scrollbar-thumb:hover { background:#6b7280; }
  body { margin:0; background:#0b0f19; color:#d1d5db;
    font-family:ui-monospace,'JetBrains Mono',monospace; font-size:13px; }
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
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
  .pmsg.ok { color:__ACCENT__; }
  iframe { border:0; width:100%; height:calc(100vh - 54px); display:block;
    background:#0b0f19; }`;
const POPOUT_BODY = (base, path) => `
  <div class="strip"></div>
  <div class="phead"><div class="ptitle">+ command &middot; ${esc(base)}</div>
    <div class="ppath">${esc(path)}</div></div>
  <form id="pform" autocomplete="off">
    <div class="plabel">command the dream</div>
    <select id="pkind">${COMMANDS.map(c =>
      `<option value="${c.kind}">${esc(c.label)}</option>`).join('')}</select>
    <textarea id="ptext" placeholder="a thought for the dream…"></textarea>
    <div><button type="submit">send</button></div>
    <div class="pmsg" id="pmsg" aria-live="polite"></div>
  </form>`;
/* Every popped-out window (command form OR a doc/review iframe) wears the
   same identity: a hue-tinted band, the project basename + full path, and a
   matching title — so multiple target popouts never blur together. */
function popoutShell(w, base, path, tint, titleWord) {
  const doc = w.document;
  doc.title = titleWord + ' · ' + base + ' · dreamwork';
  const warm = tint >= 0;
  const accent = warm ? '#c4b5fd' : '#a5b4fc';
  const strip = warm ? 'linear-gradient(90deg,#6d5bd0,#a855f7)'
                     : 'linear-gradient(90deg,#4f5bd5,#5b8def)';
  doc.head.innerHTML = '<meta charset="utf-8">';
  const st = doc.createElement('style');
  st.textContent = POPOUT_CSS.replace(/__ACCENT__/g, accent)
                             .replace('__STRIP__', strip);
  doc.head.appendChild(st);
  return doc;
}
const popHead = (label, base, path) =>
  `<div class="strip"></div><div class="phead">` +
  `<div class="ptitle">${esc(label)} &middot; ${esc(base)}</div>` +
  `<div class="ppath">${esc(path)}</div></div>`;
/* Every floated window dreams the same dream. The shader is world-space
   anchored (#74): it reads ITS OWN window's screenX/screenY, so a popout
   parked anywhere over the page samples the identical deterministic field
   and the pattern stays continuous across the seam. Mounted after `fill`,
   because the fills assign body.innerHTML and would wipe the canvas. */
function mountPopoutBg(w, tint) {
  try {
    const cv = w.document.createElement('canvas');
    cv.id = 'dreambg';
    w.document.body.appendChild(cv);
    const bg = mountDreambg(w, cv, {});     // no dev overlay, no layer switcher
    if (!bg) return;
    bg.setTint(tint);                       // wear the spawning view's hue
    w.addEventListener('pagehide', () => bg.stop());
  } catch (e) { /* no WebGL here: the flat #0b0f19 still reads fine */ }
}
/* open a floating window — Document Picture-in-Picture where available (stays
   put while the main tab navigates), else a positioned window.open — and let
   `fill` render into it with the shared identity. */
async function openPopout(name, size, fill) {
  const d = await ensureData();
  const path = (d && d.target) || '';
  const base = path.split('/').filter(Boolean).pop() || 'dreamwork';
  const tint = TINT[view.name] || 0;
  let w = null;
  if (window.documentPictureInPicture &&
      documentPictureInPicture.requestWindow) {
    try { w = await documentPictureInPicture.requestWindow(size); }
    catch (e) { /* fall through */ }
  }
  if (!w) w = window.open('', name + '_' + base,
    'width=' + (size.width + 20) + ',height=' + (size.height + 20) +
    ',left=80,top=80');
  if (w) { fill(w, base, path, tint); mountPopoutBg(w, tint); }
  return w;
}
async function requestPopout() {
  const w = await openPopout('dreamcmd', { width: 340, height: 320 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, '+ command');
      doc.body.innerHTML = POPOUT_BODY(base, path);
      const endpoint = location.origin + '/command';
      const msg = doc.getElementById('pmsg');
      doc.addEventListener('keydown', ev => {        // Ctrl/Cmd+Enter submits
        if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
          ev.preventDefault(); doc.getElementById('pform').requestSubmit();
        }
      });
      doc.getElementById('pform').addEventListener('submit', async ev => {
        ev.preventDefault();
        const kind = doc.getElementById('pkind').value;
        const text = doc.getElementById('ptext').value.trim();
        if (kind !== 'do-next' && !text) {
          msg.textContent = 'a thought is needed'; msg.className = 'pmsg'; return;
        }
        try {
          const r = await fetch(endpoint, { method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind, text }) });
          if (r.ok) { msg.textContent = 'sent to the dream';
            msg.className = 'pmsg ok'; doc.getElementById('ptext').value = ''; }
          else { msg.textContent = 'rejected (' + r.status + ')';
            msg.className = 'pmsg'; }
        } catch (e) { msg.textContent = 'no connection'; msg.className = 'pmsg'; }
      });
    });
  if (w && window.__closeCmd) window.__closeCmd();
}
/* pop a doc/review into a floating iframe window (kept identity header) so it
   stays handy while the main tab navigates. */
function popoutDoc(url, label) {
  openPopout('dreamdoc', { width: 620, height: 560 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, label);
      doc.body.innerHTML = popHead(label, base, path) +
        `<iframe src="${esc(url)}" title="${esc(label)}"></iframe>`;
    });
}
(function () {
  const pal = document.getElementById('cmdpalette');
  if (!pal) return;
  const cmsg = () => document.getElementById('cmdmsg');
  let open = false;
  const CMD_GAP = 18;            // breathing room under the +/× opener
  // The composer is position:fixed, but `.wrap` carries `perspective`, which
  // makes IT the containing block — so `top`/`left` are measured from .wrap,
  // not the viewport. Rects are viewport coords, so subtract that origin or
  // the panel drifts right of the + and hangs a body-padding too low.
  function fixedOrigin() {
    const cb = document.querySelector('.wrap');
    if (!cb) return { x: 0, y: 0 };
    const b = cb.getBoundingClientRect();
    return { x: b.left, y: b.top };
  }
  function place() {
    const plus = document.getElementById('cmdplus');
    if (!plus) return;
    const r = plus.getBoundingClientRect();
    const w = pal.offsetWidth || Math.min(innerWidth * 0.92, 340);
    const o = fixedOrigin();
    // The opener rotates 45deg into an × when open, which swells its painted
    // box by its half-diagonal. Anchor off the centre (invariant under that
    // rotation) and the painted extent, so the breathing room is what the eye
    // sees and is the same whether we place while closed or while open.
    const bw = plus.offsetWidth || r.width;          // layout box, transform-free
    const bh = plus.offsetHeight || r.height;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const left = cx - bw / 2;
    const bottom = cy + (bw + bh) * Math.SQRT2 / 4;   // rotated half-height
    pal.style.left =
      (Math.max(8, Math.min(left, innerWidth - w - 8)) - o.x) + 'px';
    pal.style.top = (bottom + CMD_GAP - o.y) + 'px';
  }
  // Command selection: a radiogroup of buttons with one background indicator
  // that slides between them. `snap` lands it without a slide — used for the
  // first placement and for reflows, because an indicator that animates from
  // its 0-width start reads as a glitch, not a choice (the enter-snap rule).
  const kindsEl = document.getElementById('cmdkinds');
  const menuEl = document.getElementById('cmdmenu');
  let indEl = null;
  let activeKind = (COMMANDS[0] || {}).kind;
  // The row carries the common kinds PLUS the active one when it is uncommon,
  // so whatever is selected always has a button for the indicator to sit on.
  // Rebuilding is membership-only: a common->common switch leaves the row
  // (and so the indicator) alone, which is what lets it slide.
  let rowKinds = [];
  const rowWant = () => COMMANDS
    .filter(c => c.common || c.kind === activeKind).map(c => c.kind);
  function renderKinds() {
    if (!kindsEl) return false;
    const want = rowWant();
    if (want.join('\\u0000') === rowKinds.join('\\u0000')) return false;
    rowKinds = want;
    kindsEl.innerHTML =
      '<span class="cmdind" id="cmdind" aria-hidden="true"></span>' +
      COMMANDS.filter(c => want.indexOf(c.kind) >= 0).map(c =>
        '<button type="button" class="cmdkind" data-kind="' + esc(c.kind) +
        '" role="radio" aria-checked="false" title="' + esc(c.desc) + '">' +
        esc(c.label) + '</button>').join('');
    indEl = document.getElementById('cmdind');
    return true;
  }
  // The menu lists EVERY kind with its description — the discoverability
  // surface. Built once from COMMANDS, whatever its length.
  function renderMenu() {
    if (!menuEl) return;
    menuEl.innerHTML = COMMANDS.map(c =>
      '<button type="button" role="menuitem" class="cmdmenuitem" data-kind="' +
      esc(c.kind) + '"><span class="cmk">' + esc(c.label) +
      '</span><span class="cmd">' + esc(c.desc) + '</span></button>').join('');
  }
  function moveIndicator(snap) {
    if (!kindsEl || !indEl) return;
    const btn = kindsEl.querySelector('.cmdkind.on');
    if (!btn) return;
    const g = kindsEl.getBoundingClientRect(), b = btn.getBoundingClientRect();
    if (!b.width) return;                  // not laid out yet; nothing to chase
    if (snap || rmr) indEl.classList.add('snap');
    indEl.style.width = b.width + 'px';
    indEl.style.height = b.height + 'px';
    indEl.style.transform = 'translate(' + (b.left - g.left) + 'px,' +
                            (b.top - g.top) + 'px)';
    if (snap && !rmr) {
      void indEl.offsetWidth;              // reflow so the landing is not a slide
      indEl.classList.remove('snap');
    }
  }
  function setKind(kind) {
    activeKind = kind;
    // a rebuilt row has a brand-new 0-width indicator, so land it rather than
    // slide it up from nothing (the enter-snap rule)
    const rebuilt = renderKinds();
    kindsEl.querySelectorAll('.cmdkind').forEach(b => {
      const on = b.dataset.kind === kind;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    if (menuEl) menuEl.querySelectorAll('.cmdmenuitem').forEach(b =>
      b.classList.toggle('on', b.dataset.kind === kind));
    moveIndicator(rebuilt);
  }
  if (kindsEl) kindsEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdkind');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); }
  });
  if (menuEl) menuEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdmenuitem');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); }
  });
  // the menu opens on hover/focus in CSS; mirror that into aria-expanded,
  // which CSS cannot set.
  const moreEl = document.getElementById('cmdmore');
  if (moreEl) {
    const btn = moreEl.querySelector('.cmdmorebtn');
    const expose = v => btn && btn.setAttribute('aria-expanded', v);
    moreEl.addEventListener('pointerenter', () => expose('true'));
    moreEl.addEventListener('pointerleave', () => expose('false'));
    moreEl.addEventListener('focusin', () => expose('true'));
    moreEl.addEventListener('focusout', () => expose('false'));
  }
  renderMenu();
  setKind(activeKind);              // paint the initial row + selection
  function openCmd() {
    place(); pal.classList.add('open'); open = true;
    moveIndicator(true);          // land under the active kind, never slide in
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
    const pip = e.target.closest && e.target.closest('.pipbtn');
    if (pip) { e.preventDefault();
      popoutDoc(pip.dataset.pipurl, pip.dataset.piplabel || 'doc'); return; }
    const plus = e.target.closest && e.target.closest('#cmdplus');
    if (plus) { e.preventDefault(); open ? closeCmd() : openCmd(); return; }
    if (open && e.target.closest && !e.target.closest('#cmdpalette')) closeCmd();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && open) closeCmd();
  });
  // Ctrl/Cmd+Enter submits from a text field: an answer box (anywhere —
  // questions view, review dock) or the command palette.
  document.addEventListener('keydown', e => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'Enter')) return;
    const t = e.target;
    if (t && t.tagName === 'TEXTAREA' && /^qa[oa]\\d+$/.test(t.id)) {
      e.preventDefault(); sendAnswer(t.id.slice(2));
    } else if (t && /^nb[oa]\\d+$/.test(t.id)) {
      e.preventDefault(); sendComment(t.id.slice(2));
    } else if (t && t.id === 'cmdtext') {
      e.preventDefault();
      document.getElementById('cmdform').requestSubmit();
    }
  });
  addEventListener('resize', () => {
    if (!open) return;
    place(); moveIndicator(true);         // the group may have re-wrapped
  });
  document.getElementById('cmdform').addEventListener('submit', async e => {
    e.preventDefault();
    const kind = activeKind;
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
// Domain units per CSS pixel — a WORLD constant, not a per-window one. It
// used to be 2.3/innerHeight, which pinned the field's origin to the screen
// but let each window pick its own zoom; two windows then showed the same
// dream at two scales and the seam between them could never line up. 900 is
// the reference height that keeps the density it always had.
const WORLD_SCALE = 2.3 / 900;
function mountDreambg(win, cv, opts) {
  opts = opts || {};
  const doc = win.document;
  const gl = cv.getContext('webgl',
    { antialias: false, depth: false, alpha: false });
  const rm = win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!gl) { cv.style.display = 'none'; return null; }

  const VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const FRACTAL_FS = `precision highp float;
    uniform float t; uniform vec2 r; uniform float warp;
    uniform vec2 domainOffset;   /* screen-space anchor: world-space dream */
    uniform float domScale;      /* domain units per buffer pixel (world-fixed) */
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
      /* World-space: the domain is a fixed number of units per SCREEN pixel
         (domScale) offset by the window's on-screen position — so the pattern
         is pinned to the screen under both dragging AND resizing, and two
         windows of different sizes sample one continuous field rather than
         the same field at two zooms. */
      vec2 p=gl_FragCoord.xy*domScale + domainOffset;
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
      vec2 ctr=r*0.5*domScale + domainOffset;   /* this window's centre */
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
    canW = Math.max(2, Math.floor(win.innerWidth / 2));
    canH = Math.max(2, Math.floor(win.innerHeight / 2));
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
           domainOffset: gl.getUniformLocation(progF, 'domainOffset'),
           domScale: gl.getUniformLocation(progF, 'domScale') };
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
    const chromeTop = Math.max(0, win.outerHeight - win.innerHeight);
    const domX = (win.screenX || 0) * WORLD_SCALE;
    // gl_FragCoord.y counts UP from the viewport's bottom while screenY counts
    // DOWN from the desktop's top, so the vertical anchor is the negated screen
    // position of the viewport's BOTTOM edge. (Adding the top edge instead
    // makes the field slide the wrong way, at double rate, as a window moves.)
    const domY = -((win.screenY || 0) + chromeTop + win.innerHeight)
                 * WORLD_SCALE;
    // buffer pixels are ~4 CSS px; convert so domScale is units per BUFFER
    // pixel while WORLD_SCALE stays units per CSS pixel (window-independent).
    const domScale = WORLD_SCALE * (win.innerHeight / Math.max(1, fboH));
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
    gl.uniform1f(uF.domScale, domScale);
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

  win.addEventListener('resize', () => { size(); if (rm) draw(lastMs); });

  const MODES = ['dream (composite)', 'raw fractal', 'warp field',
                 'focus mask', 'blurred fractal'];
  let hint = null, hintT = 0;
  function cycle() {
    mode = (mode + 1) % MODES.length;
    if (!hint) {
      hint = doc.createElement('div');
      hint.id = 'layerhint'; doc.body.appendChild(hint);
    }
    // Self-explanatory feedback: names the layer AND how to cycle, so an
    // accidental switch (stray 'l', triple-click corner) is legible and
    // reversible rather than a mysterious background change.
    hint.textContent = 'background: ' + MODES[mode] + ' — press l to cycle';
    hint.style.opacity = '1';
    win.clearTimeout(hintT);
    hintT = win.setTimeout(() => { hint.style.opacity = '0'; }, 2200);
    if (rm) draw(lastMs);
  }
  // Debug switcher on the main page only: a popout carries no #layerhint
  // styles, and a stray 'l' there should stay a keystroke.
  if (opts.switcher) {
    win.addEventListener('keydown', e => {
      // never hijack a keystroke aimed at a text field (the composer etc.)
      if (e.target.closest && e.target.closest('input, textarea, select')) return;
      if (e.key === 'l' && !e.metaKey && !e.ctrlKey && !e.altKey) cycle();
    });
    let clicks = 0, clickT = 0;
    win.addEventListener('click', e => {
      if (!(e.clientX > win.innerWidth - 90 &&
            e.clientY > win.innerHeight - 90)) { clicks = 0; return; }
      const now = Date.now();
      if (now - clickT > 600) clicks = 0;
      clickT = now;
      if (++clicks >= 3) { clicks = 0; cycle(); }
    });
  }

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
  if (opts.dev) {
    const box = doc.createElement('div');
    box.id = 'devbox';
    fpsEl = doc.createElement('div');
    dtEl = doc.createElement('div');
    ftEl = doc.createElement('div');
    const sp = doc.createElement('canvas');
    sp.width = 120; sp.height = 22;
    box.append(fpsEl, dtEl, ftEl, sp);
    doc.body.appendChild(box);
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
    if (running && !rm) rafId = win.requestAnimationFrame(step);
  }
  function step(ms) {
    if (!running) return;
    if (!doc.hidden) frame(ms);
    else win.setTimeout(() => {
      if (running) rafId = win.requestAnimationFrame(step);
    }, 500);
  }
  // Context loss (GPU reset, tab backgrounding, driver hiccup) is
  // recoverable: rebuild every GL object on restore and resume.
  cv.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    running = false;
    if (rafId) win.cancelAnimationFrame(rafId);
  });
  cv.addEventListener('webglcontextrestored', () => {
    initGL();
    if (opts.dev) acquireGpuTimer();       // ext + query died with the context
    running = true;
    if (rm) draw(lastMs);
    else rafId = win.requestAnimationFrame(step);
  });
  // The router talks to the shader through this handle: setTint nudges
  // the per-page atmosphere target (lerped inside draw); pulseWarp fires
  // the transition stir; frames exposes the monotonic draw tally so a view
  // swap's continuity is observable. reduced-motion never stirs.
  const handle = {
    setTint(v) { tintTarget = v; if (rm) { tintCur = v; draw(lastMs); } },
    pulseWarp() { if (!rm) warpStart = lastMs; },
    get frames() { return frameCount; },
    get tint() { return tintCur; },
    get warp() { return lastWarp; },
    stop() { running = false; if (rafId) win.cancelAnimationFrame(rafId); }
  };
  if (rm) draw(0);
  else rafId = win.requestAnimationFrame(step);
  return handle;
}
window.dreambg = mountDreambg(window, document.getElementById('dreambg'),
                              { dev: window.DEV, switcher: true });
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
# The one vocabulary reaches the client here, so the composer's buttons, its
# menu, and the popped-out form never drift from what POST /command accepts.
PAGE = page_shell('dreamwork watch', APP_BODY,
                  "const COMMANDS = " + json.dumps(list(COMMANDS)) + ";\n"
                  + COMPONENTS_JS + VIEWS_JS + SHADER_JS + ROUTER_JS
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


"""Who wrote a note (#109).

A page that mixes what the human said with what the loop wrote will
eventually mislead one of them — and the loop is the one that would then act
on its own invention as if it were an instruction. So the tag records the
AUTHOR, not just the channel, and the page shows it.

Four forms are live: the two current tags and two legacy ones that must keep
parsing, because the file is a record and is never rewritten. An unknown tag
attributes NOTHING — a wrong attribution is worse than an absent one.
"""
NOTE_TAGS = (
    ("- **Note (human,", "human"),           # current: the human, any channel
    ("- **Follow-up (via watch,", "human"),  # legacy: only he used it
    ("- **Follow-up (loop,", "loop"),        # current: the loop
    ("- **Follow-up (in-session,", "loop"),  # legacy: the loop, hand-written
)


def note_author(stripped):
    """'human', 'loop', or None for a sub-bullet note line. None is a real
    answer: render it, attribute nothing, never guess."""
    for prefix, author in NOTE_TAGS:
        if stripped.startswith(prefix):
            return author
    return None


def _note_entry(stripped, author):
    return {"text": stripped.split(":**", 1)[-1].strip(), "author": author}


ENTRY_MARK = "- **"


def _entry_title_parts(segment):
    """Split an entry line's text at the title's closing `**`.

    Returns (title_segment, closed, rest). `closed` is False when the title
    is hard-wrapped and continues on the next line."""
    seg, closed, rest = segment.partition("**")
    return seg, bool(closed), rest


def _join_title(parts):
    """One definition of how a wrapped title becomes a string, so the reader
    and the writer can never disagree about what an entry is called."""
    return " ".join(p.strip() for p in parts if p.strip())


def _parse_entries(text, section, lift_answer):
    """Entries under `## {section}` as [{title, body, follows[, answer]}].

    Four invariants, each of which was a bug at some point:

    1. A top-level `- **` line ALWAYS starts a new entry. Nothing can absorb
       it — not an unterminated title, not an open sub-bullet — so an entry
       can never silently vanish into the one above it.
    2. A TITLE may be hard-wrapped: it closes at its `**` wherever that
       falls, including several lines down. The loop writes this file at ~72
       columns, so a wrapped title is normal input, not malformed (#116).
    3. A SUB-BULLET may be hard-wrapped too: its continuation lines belong to
       it, not to the body. Keeping only the first line truncated the note
       AND spilled its tail into the body as orphaned prose (#106).
    4. An Answer or Note sub-bullet is never mistaken for an entry, even
       un-indented, so it cannot swallow the entries that follow it.

    `lift_answer` pulls a `- **Answer (via watch…):**` bullet out into
    `answer` (Open only), so the view can show answered-awaiting-fold
    distinctly rather than as an ambiguous open question.
    """
    items = []
    if not text:
        return items
    in_sec = False
    cur = None
    sub = None            # which sub-bullet is absorbing wrapped lines
    title_parts = None    # non-None while a title is still open
    for line in text.splitlines():
        if line.startswith("## "):
            in_sec = line.strip() == f"## {section}"
            cur, sub, title_parts = None, None, None
            continue
        if not in_sec:
            continue
        s = line.strip()
        is_answer = lift_answer and s.startswith("- **Answer (via watch")
        author = note_author(s)
        # invariant 1: this test comes FIRST and is unconditional
        if line.startswith(ENTRY_MARK) and not is_answer and author is None:
            seg, closed, rest = _entry_title_parts(line[len(ENTRY_MARK):])
            cur = {"title": _join_title([seg]), "body": "", "follows": []}
            if lift_answer:
                cur["answer"] = None
            items.append(cur)
            sub = None
            title_parts = None if closed else [seg]
            if closed and rest.strip():
                cur["body"] = rest.strip() + "\n"
            continue
        if cur is None:
            continue
        if title_parts is not None:            # invariant 2
            seg, closed, rest = _entry_title_parts(s)
            title_parts.append(seg)
            cur["title"] = _join_title(title_parts)
            if closed:
                title_parts = None
                if rest.strip():
                    cur["body"] = rest.strip() + "\n"
            continue
        if is_answer:
            cur["answer"] = s.split(":**", 1)[-1].strip()
            sub = "answer"
        elif author is not None:
            cur["follows"].append(_note_entry(s, author))
            sub = "follow"
        elif not s or s.startswith("- ") or s.startswith("* "):
            sub = None                          # a new bullet ends invariant 3
            cur["body"] += line + "\n"
        elif sub == "answer":
            cur["answer"] += " " + s
        elif sub == "follow":
            cur["follows"][-1]["text"] += " " + s
        else:
            cur["body"] += line + "\n"
    return items


def parse_open_questions(text):
    """[{title, body, answer, follows}] for each entry in `## Open`."""
    return _parse_entries(text, "Open", lift_answer=True)


def parse_answered(text):
    """[{title, body, follows}] for each entry in `## Answered`, so the view
    can render each with its follow-up thread and an add-a-note box."""
    return _parse_entries(text, "Answered", lift_answer=False)


def append_subbullet(text, title, block, section="Open"):
    """Insert `block` at the end of the entry titled `title` inside
    `## {section}` (Open or Answered). Indented sub-bullets (Answer / Note)
    never count as entry boundaries. Returns (new_text, matched).
    Pure — testable without a filesystem.

    The writer must find an entry exactly the way the reader named it, so it
    walks titles with the same rules and the same `_join_title` — including
    hard-wrapped ones (#116). Comparing against the first source line only
    meant a wrapped-title entry could never be matched, and /answer and
    /comment would report failure for an entry plainly on screen.
    """
    lines = text.splitlines()
    out = []
    in_section = False
    in_target = False
    matched = False
    title_parts = None       # non-None while a wrapped title is still open

    def close_target():
        nonlocal in_target
        if in_target:
            out.append(block)
            in_target = False

    def claim(parts):
        nonlocal in_target, matched
        if _join_title(parts) == title:
            in_target = True
            matched = True

    for line in lines:
        s = line.strip()
        if line.startswith("## "):
            close_target()
            in_section = line.strip() == f"## {section}"
            title_parts = None
        elif (in_section and line.startswith(ENTRY_MARK)
                and not s.startswith("- **Answer (via watch")
                and note_author(s) is None):
            close_target()
            seg, closed, _rest = _entry_title_parts(line[len(ENTRY_MARK):])
            if closed:
                claim([seg])
                title_parts = None
            else:
                title_parts = [seg]
        elif in_section and title_parts is not None:
            seg, closed, _rest = _entry_title_parts(s)
            title_parts.append(seg)
            if closed:
                claim(title_parts)
                title_parts = None
        out.append(line)
    close_target()
    return "\n".join(out) + "\n", matched


def append_answer(text, title, answer, stamp):
    """Insert an answer bullet at the end of the titled Open entry."""
    return append_subbullet(
        text, title, f"  - **Answer (via watch, {stamp}):** {answer}", "Open")


def append_comment(text, title, note, stamp, section="Open"):
    """Append a note to an entry (Open or Answered) — a chronological
    mini-thread inside the entry.

    The tag names the AUTHOR as well as the channel (#109): a note left here
    is the human's, and it must be impossible to mistake for something a
    dreamer wrote. `note_author` reads it back."""
    return append_subbullet(
        text, title, f"  - **Note (human, via watch, {stamp}):** {note}",
        section)


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
        "answered_entries": parse_answered(questions),
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


# Accepted POST /command kinds, derived from the one vocabulary (COMMANDS,
# top of file). Each becomes a source-tagged watch-events.log line the loop's
# tail monitor wakes on (same transport as answers); no file is written.
COMMAND_KINDS = tuple(c["kind"] for c in COMMANDS)


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
            # Human-authorized write paths, all localhost-only: /answer folds
            # an answer into questions.md; /comment threads a follow-up note
            # onto any entry; /command drops a steering line into the events
            # log. Everything else is read-only.
            if self.path == "/answer":
                self._handle_answer()
            elif self.path == "/comment":
                self._handle_comment()
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

        def _handle_comment(self):
            req = self._read_json()
            if req is None:
                return
            try:
                title = str(req["question"]).strip()
                note = str(req["comment"]).strip()
                section = str(req.get("section", "Open")).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if not title or not note or section not in ("Open", "Answered"):
                self.send_error(400)
                return
            qpath = os.path.join(target, ".dreamwork", "questions.md")
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with ANSWER_LOCK:
                text = read_text(qpath)
                if text is None:
                    self.send_error(404)
                    return
                new_text, matched = append_comment(text, title, note, stamp,
                                                    section)
                if not matched:
                    self.send_error(409)
                    return
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(new_text)
            hint = ("(re-evaluate — a note on an answered entry may amend it)"
                    if section == "Answered" else "(fold with the entry)")
            log_event(target,
                      f'follow-up: "{title}" -> .dreamwork/questions.md {hint}')
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
