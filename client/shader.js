
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
    uniform float projHue;    /* HIS colour for this project (#143), radians */
    float hash(vec2 p){ p=fract(p*vec2(123.34,345.45));
      p+=dot(p,p+34.345); return fract(p.x*p.y); }
    /* Rodrigues rotation about the grey axis (1,1,1)/sqrt(3). A HUE rotation
       and nothing else: the component along that axis — the achromatic part,
       which is what luminance contrast is made of — is its own eigenvector
       and comes back untouched. So "contrast survives" is a property of the
       operation rather than a claim about the six values we happened to
       pick, and #143 cannot cost the page a text ramp or an accent. */
    vec3 hueRot(vec3 c, float a){
      const vec3 k=vec3(0.5773502691896258);
      float ca=cos(a);
      return c*ca + cross(k,c)*sin(a) + k*dot(k,c)*(1.0-ca);
    }` + FOCUS_GLSL + `
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
      /* ...and THEN his project's hue, over the COMPOSED colour rather than
         over the tint alone. (No backticks anywhere in this shader source:
         it lives in a JS template literal, and a pair of them in a COMMENT
         ends the literal and turns the rest of the GLSL into JavaScript.
         That is what "SyntaxError: Unexpected identifier 'tint'" means here,
         and it takes the whole page down.)

         Rotating only the tint moved almost nothing: the tint is multiplied
         by glow*0.105 and the near-black base — which is most of what is on
         screen — carried its own fixed blue through unchanged. Measured, not guessed: the mean field hue moved 2 degrees
         between indigo and green, and the guard that says so is the reason
         this line is here. Rotating the whole composite is also the version
         whose luminance guarantee is exact, since the achromatic component
         of the WHOLE colour is the rotation's eigenvector.

         Before the vignette and the dither on purpose: the dither is a
         neutral ±1/255 and rotating it would tint the noise. */
      col=hueRot(col, projHue);
      col*=1.0-0.22*smoothstep(0.35,1.25,length(uv-0.5));
      col+=(hash(gl_FragCoord.xy+t)-0.5)/255.0;
      gl_FragColor=vec4(col,1.0);
    }`;
  // #733 — crossfade between two cached composite frames. The light-mode
  // loop renders the full pipeline into a snapshot ~1.4x/sec; every RAF
  // frame this blends the previous snapshot and the newest one so the
  // dissolve is smooth (the page stays alive) while real GPU work stays
  // ~1-2Hz. A plain mix(); the two snapshots already carry tint/hue/dither.
  const XFADE_FS = `precision highp float;
    uniform sampler2D a; uniform sampler2D b; uniform vec2 r; uniform float k;
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      gl_FragColor=mix(texture2D(a,uv),texture2D(b,uv),clamp(k,0.0,1.0));
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
  let progF, progB, progC, progX, uF, uB, uC, uX, buf;
  let A = null, B = null, C = null, fboOK = false;
  // #733 light-animation: two screen-res snapshots that the crossfade
  // program blends. snap* holds a full-resolution composite frame; the
  // light-mode loop renders the expensive four-pass pipeline into one of
  // them ~1.4x/sec and every RAF frame cross-dissolves between the pair.
  let snapA = null, snapB = null;
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
    // #733 light-animation snapshots: same dimensions as the composite's
    // screen target (canW x canH), so the crossfade upscale is 1:1 and a
    // cached frame holds the full-resolution image the draw pass produced.
    for (const tgt of [snapA, snapB]) if (tgt) {
      gl.deleteTexture(tgt.tex); gl.deleteFramebuffer(tgt.fbo);
    }
    snapA = makeTarget(canW, canH);
    snapB = makeTarget(canW, canH);
    fboOK = !!(A && B && C && snapA && snapB);
    if (!fboOK) cv.style.display = 'none';
  }
  function initGL() {
    A = B = C = null;                 // context loss invalidated them
    snapA = snapB = null;             // #733: snapshots die with the context too
    progF = program(FRACTAL_FS);
    progB = program(BLUR_FS);
    progC = program(COMPOSITE_FS);
    progX = program(XFADE_FS);        // #733 crossfade pass
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
           pageTint: gl.getUniformLocation(progC, 'pageTint'),
           projHue: gl.getUniformLocation(progC, 'projHue') };
    uX = { a: gl.getUniformLocation(progX, 'a'),
           b: gl.getUniformLocation(progX, 'b'),
           r: gl.getUniformLocation(progX, 'r'),
           k: gl.getUniformLocation(progX, 'k') };
    buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    size();
  }
  initGL();

  let mode = 0, lastMs = 0;
  // #733 draw frequency: 'animated' (default, every RAF frame), 'light'
  // (render the full pipeline ~1.4Hz into cached snapshots, crossfade
  // between them every RAF frame), 'paused' (stop the RAF loop; the canvas
  // keeps its last composited frame — a freeze, not a blank).
  let drawMode = 'animated';
  // light-mode snapshot/crossfade state. snapFrom/snapTo index into
  // [snapA,snapB]; xfadeMs/xfadeDur drive the per-frame blend fraction.
  let snapFrom = 0, snapTo = 1, lastSnapMs = -1e9, xfadeMs = 0;
  const LIGHT_INTERVAL_MS = 700, XFADE_MS = 600;
  // per-page atmosphere lerped in JS then handed to the composite shader;
  // frameCount is a monotonic draw tally (never resets) so a view swap's
  // continuity can be checked from outside.
  let tintCur = 0, tintTarget = 0, lastDrawMs = 0, frameCount = 0;
  /* his project hue, in radians off the default. Lerped like the
     route tint so picking a colour drifts rather than snaps — it is
     a change to the page's atmosphere, and the atmosphere moves the
     way everything ambient here moves. */
  let hueCur = 0, hueTarget = 0;
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
  function draw(ms, dst) {
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
    hueCur += (hueTarget - hueCur) * (1.0 - Math.exp(-dt / 0.6));
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
    // pass 4: upscale + composite C (blurred) with A (raw). dst=null is the
    // screen; a snapshot FBO is the light-mode cache target (#733).
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst ? dst.fbo : null);
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
    gl.uniform1f(uC.projHue, hueCur);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  // #733 — blend the two cached snapshots to the screen. k is the dissolve
  // fraction toward snapTo (0 = frozen on snapFrom, 1 = settled on snapTo).
  function presentXfade(k) {
    const from = [snapA, snapB][snapFrom], to = [snapA, snapB][snapTo];
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canW, canH);
    gl.useProgram(progX); bindQuad(progX);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, from.tex);
    gl.uniform1i(uX.a, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, to.tex);
    gl.uniform1i(uX.b, 1);
    gl.uniform2f(uX.r, canW, canH);
    gl.uniform1f(uX.k, k);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    unbindTextures();
  }

  win.addEventListener('resize', () => { size(); if (rm) draw(lastMs, null); });

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
    if (rm) draw(lastMs, null);
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
    // body.dev is the yield signal for the project wordmark (#435): the CSS
    // rule that cedes the overlay's column keys on it, so removing this class
    // (or never setting it) is the production line that makes the overlap
    // guard fail. The overlay itself still mounts exactly as before.
    doc.body.classList.add('dev');
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
  // #733 — one render closure per mode. 'animated' composites to screen
  // every frame (today's behaviour). 'light' runs the full pipeline into a
  // snapshot ~1.4Hz and cross-dissolves between snapshots every frame.
  // 'paused' is handled in frame() by NOT scheduling another RAF, so the
  // canvas keeps its last image (a freeze, never a blank — #136).
  function renderAnimated(ms) { draw(ms, null); }
  function renderLight(ms) {
    // advance the cache on the interval; the dissolve runs every frame
    // regardless, so the page stays alive between renders.
    if (ms - lastSnapMs >= LIGHT_INTERVAL_MS) {
      // ping-pong: the newest snapshot becomes 'from', render into 'to'.
      snapFrom = snapTo; snapTo = 1 - snapTo;
      draw(ms, [snapA, snapB][snapTo]);
      lastSnapMs = ms; xfadeMs = 0;
    } else {
      xfadeMs += ms - (lastDrawFrameMs || ms);
    }
    lastDrawFrameMs = ms;
    const k = Math.min(1, xfadeMs / XFADE_MS);
    presentXfade(k);
  }
  let lastDrawFrameMs = 0;
  // draw() wrapped with a CPU stopwatch (JS + GL submission) and, when the
  // GPU timer is live, a TIME_ELAPSED query straddling the same draw.
  function timedRender(ms, render) {
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
    render(ms);
    const cpuMs = performance.now() - t0;
    if (gpuOpen) {
      gl.endQuery(gpuExt.TIME_ELAPSED_EXT); gpuOpen = false; gpuPending = true;
    }
    return cpuMs;
  }
  function frame(ms) {
    // #733: the per-mode render closure. 'paused' never reaches frame()
    // (the RAF loop is stopped), so every closure here is a live draw.
    const render = drawMode === 'light' ? renderLight : renderAnimated;
    const cpuMs = fpsEl ? timedRender(ms, render) : (render(ms), 0);
    if (fpsEl) {
      fpsN++;
      if (prevMs) {
        fts.push(ms - prevMs);
        if (fts.length > 120) fts.shift();
      }
      prevMs = ms;
      dts.push(cpuMs); if (dts.length > 120) dts.shift();
      drawSpark();
      if (!fpsT) fpsT = ms;            // anchor the first window, else a
                                       // slow first paint reports a bogus
                                       // rate (count over a long elapsed)
      if (ms - fpsT >= 100) {
        // fps over the elapsed window, scaled to a per-second rate: the
        // window shrunk from 1s to 100ms for a livelier readout, so the
        // raw count would show "6 fps" at 60 real fps.
        const elapsed = ms - fpsT;
        fpsEl.textContent = Math.round(fpsN * 1000 / elapsed) + ' fps';
        // measured work per frame: real GPU time when the timer is live,
        // else CPU-side draw (JS + GL submission — understates true GPU).
        const useGpu = gts.length > 0, work = useGpu ? gts : dts;
        dtEl.textContent =
          avgOf(work).toFixed(1) + '·' + Math.max(0, ...work).toFixed(1) +
          'ms ' + (useGpu ? 'gpu' : 'draw');
        ftEl.textContent =
          avgOf(fts).toFixed(1) + 'ms avg · ' +
          Math.max(0, ...fts).toFixed(1) + 'ms worst';
        fpsN = 0; fpsT = ms;
      }
    }
    // #733: 'paused' stops the loop — the canvas keeps its last frame (a
    // freeze). 'animated'/'light' keep scheduling as before.
    if (running && !rm && drawMode !== 'paused')
      rafId = win.requestAnimationFrame(step);
  }
  function step(ms) {
    if (!running) return;
    if (drawMode === 'paused') return;       // #733: frozen, do not advance
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
    lastSnapMs = -1e9;                     // #733: re-seed the cache
    if (rm) draw(lastMs, null);
    else if (drawMode !== 'paused')
      rafId = win.requestAnimationFrame(step);
  });
  // The router talks to the shader through this handle: setTint nudges
  // the per-page atmosphere target (lerped inside draw); pulseWarp fires
  // the transition stir; frames exposes the monotonic draw tally so a view
  // swap's continuity is observable. reduced-motion never stirs.
  // #733 setDrawMode switches draw frequency: 'animated' (default, resume
  // the RAF loop), 'light' (cached-snapshot crossfade, resume the loop),
  // 'paused' (stop the loop; the canvas freezes on its last frame).
  const handle = {
    setTint(v) { tintTarget = v; if (rm) { tintCur = v; draw(lastMs, null); } },
    setProjHue(rad) { hueTarget = rad;
                      if (rm) { hueCur = rad; draw(lastMs, null); } },
    setDrawMode(m) {
      if (m !== 'animated' && m !== 'light' && m !== 'paused') return;
      const wasPaused = drawMode === 'paused';
      drawMode = m;
      // entering light: seed the cache so the first frame is real, not a
      // dissolve from nothing. entering paused from a live mode: stop the
      // loop now; the canvas retains its last composited frame.
      if (m === 'light') {
        lastSnapMs = -1e9;
        if (rm) { draw(lastMs, [snapA, snapB][snapTo]); }
      } else if (m === 'paused') {
        if (rafId) win.cancelAnimationFrame(rafId);
      } else if (wasPaused) {
        // leaving paused: resume the RAF loop from where it froze
        rafId = win.requestAnimationFrame(step);
      }
    },
    get drawMode() { return drawMode; },
    pulseWarp() { if (!rm) warpStart = lastMs; },
    get frames() { return frameCount; },
    get tint() { return tintCur; },
    get warp() { return lastWarp; },
    stop() { running = false; if (rafId) win.cancelAnimationFrame(rafId); }
  };
  if (rm) draw(0, null);
  else rafId = win.requestAnimationFrame(step);
  return handle;
}
window.dreambg = mountDreambg(window, document.getElementById('dreambg'),
                              { dev: window.DEV, switcher: true });
