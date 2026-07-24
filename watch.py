#!/usr/bin/env python3
"""watch.py — read-only localhost dashboard for a running dreamloop.

Plan: .dreamwork/docs/plans/watch-py.md (human-authorized 2026-07-25).
Stdlib only. Binds 127.0.0.1 exclusively. Read-only with ONE deliberate
exception (human-authorized 2026-07-25): POST /answer appends a marked
answer block under an open question in questions.md — the loop folds it
on its next tick. No other write paths exist.
"""

import argparse
import html
import http.server
import json
import os
import random
import subprocess
import threading
import time
import urllib.parse
import webbrowser

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
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
  #fps { position:fixed; top:.6rem; right:.8rem; z-index:10;
         color:var(--dimmer); font-size:.7rem; }
  #layerhint { position:fixed; bottom:1rem; right:1rem; z-index:10;
    color:var(--accent); background:rgba(17,24,39,.82);
    border:1px solid var(--line); border-radius:var(--radius);
    padding:.25rem .6rem; font-size:.7rem; opacity:0;
    transition:opacity .5s ease; pointer-events:none;
    letter-spacing:.04em; }
</style>"""

BODY = """<canvas id="dreambg"></canvas>
<div class="wrap">
<header>dreamwork watch</header>
<div id="meta">loading…</div>
<div id="sections"></div>"""

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
const expand = (s, inner, cls='') =>
  `<details><summary class="${cls}">${s}</summary>${inner}</details>`;
/* backticked repo-relative paths become /file links (zero agent burden) */
const linkify = h => h.replace(
  /`([\\w.-]+(?:\\/[\\w.-]+)+\\/?|[\\w-]+\\.[\\w]{1,8})`/g,
  (m, p) => '`<a href="/file?p=' + encodeURIComponent(p) + '">' + p + '</a>`');
const preB = t => `<pre>${linkify(esc(t))}</pre>`;
const qaCard = (q, i) =>
  `<div class="qa"><div class="qt">${esc(q.title)}</div>` +
  preB(q.body.trim()) +
  `<textarea id="qa${i}" placeholder="answer…"></textarea>` +
  `<button onclick="sendAnswer(${i})">answer</button></div>`;
async function postAnswer(title, text) {
  await fetch('/answer', { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: title, answer: text }) });
}
"""

APP_JS = """
function dreamBlock(d) {
  return expand(
    `${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span>`,
    preB(d.content));
}
let data = null, fetchedAt = 0;
function render(d) {
  const q = d.open_questions > 0
    ? ` · <a class="q" href="/questions">${d.open_questions} open question${d.open_questions>1?'s':''}</a>`
    : ` · <a class="q" href="/questions" style="color:var(--dimmer)">questions</a>`;
  document.getElementById('meta').innerHTML =
    `${esc(d.target)} · ${esc(d.files['skill-version'])} · <span id="upd"></span>${q}`;
  let h = '';
  h += label(`dreams (${d.dreams.length})`) +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? expand(`archive (${d.dreams_archive.length})`,
                  d.dreams_archive.map(dreamBlock).join(''), 'dim') : '');
  if (d.questions_open.length) {
    h += label('answer questions') + d.questions_open.map(qaCard).join('');
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
       `</div>`;
  document.getElementById('sections').innerHTML = h;
  ages();
}
function ages() {
  document.querySelectorAll('.age[data-mt]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.mt)) + ' old');
  const upd = document.getElementById('upd');
  if (upd) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
}
async function sendAnswer(i) {
  const el = document.getElementById('qa' + i);
  if (!el || !el.value.trim()) return;
  await postAnswer(data.questions_open[i].title, el.value.trim());
}
let last = null;
async function tick() {
  try {
    const m = await (await fetch('/mtime')).text();
    if (m !== last) { last = m; fetchedAt = Date.now();
      data = await (await fetch('/data.json')).json(); render(data); }
  } catch (e) { /* server restarting; retry */ }
  setTimeout(tick, 2000);
}
setInterval(ages, 1000);
tick();
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
    uniform float t; uniform vec2 r;
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
      vec2 p=vec2(uv.x*(r.x/r.y),uv.y)*2.3;
      float tt=t*0.03;
      vec2 q=vec2(fbm(p+vec2(0.0,tt)), fbm(p+vec2(5.2,1.3)-tt));
      /* pinch of curl: divergence-free swirl advecting the domain —
         fluid (navier-stokes-ish) drift without a sim */
      vec2 curl=vec2(q.y-0.5, 0.5-q.x);
      p+=curl*(0.38+0.14*sin(tt*1.7));
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
           r: gl.getUniformLocation(progF, 'r') };
    uB = { tex: gl.getUniformLocation(progB, 'tex'),
           r: gl.getUniformLocation(progB, 'r'),
           t: gl.getUniformLocation(progB, 't') };
    uC = { raw: gl.getUniformLocation(progC, 'texRaw'),
           blur: gl.getUniformLocation(progC, 'texBlur'),
           r: gl.getUniformLocation(progC, 'r'),
           t: gl.getUniformLocation(progC, 't'),
           mode: gl.getUniformLocation(progC, 'mode') };
    buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    size();
  }
  initGL();

  let mode = 0, lastMs = 0;
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
    const secs = ms / 1000;
    if (!fboOK || gl.isContextLost()) return;
    unbindTextures();                       // no cross-frame feedback
    // pass 1: fractal -> A
    gl.bindFramebuffer(gl.FRAMEBUFFER, A.fbo);
    gl.viewport(0, 0, fboW, fboH);
    gl.useProgram(progF); bindQuad(progF);
    gl.uniform1f(uF.t, secs); gl.uniform2f(uF.r, fboW, fboH);
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
    hint.textContent = 'layer ' + mode + ' - ' + MODES[mode];
    hint.style.opacity = '1';
    clearTimeout(hintT);
    hintT = setTimeout(() => { hint.style.opacity = '0'; }, 1500);
    if (rm) draw(lastMs);
  }
  addEventListener('keydown', e => {
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
  let fpsEl = null, fpsN = 0, fpsT = 0;
  if (window.DEV) {
    fpsEl = document.createElement('div');
    fpsEl.id = 'fps'; document.body.appendChild(fpsEl);
  }
  function frame(ms) {
    draw(ms);
    if (fpsEl) {
      fpsN++;
      if (ms - fpsT >= 1000) {
        fpsEl.textContent = fpsN + ' fps';
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
    running = true;
    if (rm) draw(lastMs);
    else rafId = requestAnimationFrame(step);
  });
  if (rm) draw(0);
  else rafId = requestAnimationFrame(step);
})();
"""

QUESTIONS_BODY = """<div class="wrap">
<header>questions</header>
<div id="meta"><a href="/">&larr; dashboard</a></div>
<div id="qsections">loading…</div>"""

QUESTIONS_JS = """
window.DEV=false;
function sendAnswer(i) {
  const el = document.getElementById('qa' + i);
  if (!el || !el.value.trim()) return;
  postAnswer(window.qopen[i].title, el.value.trim());
}
function renderQ(d) {
  window.qopen = d.questions_open;
  const raw = d.files['questions.md'] || '';
  const answered = raw.split(/^## Answered$/m)[1] || '';
  let h = '';
  h += label(`open (${d.questions_open.length})`) +
       (d.questions_open.map(qaCard).join('') ||
        '<div class="dim">none — all answered</div>');
  h += label('answered') + preB(answered.trim() || '(none yet)');
  document.getElementById('qsections').innerHTML = h;
}
let last = null;
async function qtick() {
  try {
    const m = await (await fetch('/mtime')).text();
    if (m !== last) { last = m;
      renderQ(await (await fetch('/data.json')).json()); }
  } catch (e) {}
  setTimeout(qtick, 2000);
}
qtick();
"""


def page_shell(title, body, js):
    """Shared page shell. Contract: `body` opens `<div class="wrap">`
    (the shell closes it) so every watch page shares chrome and tokens."""
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{title}</title>' + STYLE + '</head><body>'
            + body + '<script>' + js
            + '</script></div></body></html>')


PAGE = page_shell('dreamwork watch', BODY,
                  COMPONENTS_JS + APP_JS + SHADER_JS)
QUESTIONS_PAGE = page_shell('questions — dreamwork watch', QUESTIONS_BODY,
                            COMPONENTS_JS + QUESTIONS_JS)


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
    """[{title, body}] for each '- **Title**' entry in the Open section."""
    items = []
    if not text:
        return items
    in_open = False
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            in_open = line.strip() == "## Open"
            current = None
        elif in_open and line.startswith("- **"):
            title, _, rest = line[4:].partition("**")
            current = {"title": title,
                       "body": rest.strip() + "\n" if rest.strip() else ""}
            items.append(current)
        elif in_open and current is not None:
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
    if not questions_text:
        return 0
    in_open = False
    count = 0
    for line in questions_text.splitlines():
        if line.startswith("## "):
            in_open = line.strip() == "## Open"
        elif in_open and line.startswith("- **"):
            count += 1
    return count


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
            if parsed.path == "/":
                self._send(page, "text/html")
            elif parsed.path == "/data.json":
                self._send(json.dumps(collect(target)), "application/json")
            elif parsed.path == "/mtime":
                self._send(str(watched_mtime(target)), "text/plain")
            elif parsed.path == "/questions":
                self._send(QUESTIONS_PAGE, "text/html")
            elif parsed.path == "/review":
                name = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = (resolve_confined(
                    target, os.path.join(".dreamwork", "review", name))
                    if name and "/" not in name else None)
                text = read_text(full, limit=2_000_000) if full else None
                if text is None:
                    self.send_error(404)
                    return
                self._send(text, "text/html")   # self-contained artifact
            elif parsed.path == "/file":
                rel = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = resolve_confined(target, rel)
                text = read_text(full) if full else None
                if text is None:
                    self.send_error(404)
                    return
                body = ('<div class="wrap"><header>' + html.escape(rel)
                        + '</header><pre>' + html.escape(text) + '</pre>')
                self._send(page_shell(html.escape(rel), body, ""),
                           "text/html")
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/answer":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 20_000:
                self.send_error(413)
                return
            try:
                req = json.loads(self.rfile.read(length))
                title = str(req["question"]).strip()
                answer = str(req["answer"]).strip()
            except (ValueError, KeyError):
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

        def log_message(self, *_args):
            pass

    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--target", default=".", metavar="DIR")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--open", action="store_true",
                   help="open the dashboard in a browser")
    p.add_argument("--dev", action="store_true",
                   help="dev mode: show an fps counter on the page")
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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
