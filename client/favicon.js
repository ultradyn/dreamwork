
/* ── the favicon: which loop, is it alive, does it need you (#153) ────────
   His words: "favicon required (we should make a great favicon, maybe
   animated? could render offline and load dynamically via round robin or
   whatever to loop)".

   THE MARK IS A RING WITH ONE TRAVELLER ON IT — the loop, and the thing
   going round it. Three facts in three channels that do not compete at 16
   pixels, which is the size this is really drawn at:

     hue       WHICH loop this is. #143's per-project tint lands here for
               free, so a tab strip of dreaming projects is legible by
               colour alone; six hues were checked at 16px before this shape
               was chosen.
     motion    the loop is ALIVE. It orbits while the loop ticks, and parks
               — dimmed, and with its trail gone — when it stalls, so the
               state reads from a single glance as well as from two.
     the pip   HE is the bottleneck: a crisp dot on the badge convention,
               knocked out of the ring so it reads as a separate object
               rather than a bulge. Amber rather than accent when the reader
               cannot see questions.md — that is #136's FIRST use on a new
               surface, not a third use of --warn.

   MOTION IS THE STATUS, which is the only reason it is here: an
   always-animating favicon is decoration, and this page's motion is opt-in
   and meaningful (see Motion language). The two channels are the title's
   two fields exactly — the pip is its count, the orbit is its liveness word
   — because both are derived from `titleNeed`/`titleLive` and a tab that
   contradicts itself would be worse than either half alone.

   INLINE, ALWAYS. `just deploy` snapshots watch.py alone, so a file beside
   the server does not exist in production. Canvas → PNG data URI rather
   than an SVG data URI, because Chrome renders an SVG favicon as ONE static
   frame and this one has twenty.

   THE GROUND IS TRANSPARENT. The first version painted the page's own
   near-black tile, which is right on his dark browser theme and becomes a
   black block on a light one — seen at 16px against real tab-strip greys,
   not reasoned about.

   MOTION IS DESIGNED FOR THE FRAME RATE THE TAB WILL ACTUALLY GET. A hidden
   document is given no rendering opportunities, so requestAnimationFrame
   does not run in a background tab at all — and a background tab is where
   this surface spends its life. Timers do survive there, clamped (≥1s, and
   ≥1min once Chrome throttles a long-hidden tab intensively). So the orbit
   is quantised to ONE FRAME PER SECOND, twenty frames to a revolution,
   riding the standing `ages()` sweep: right at 60fps, right at the 1s
   clamp, and degrading to nearly-still rather than to a stutter if the
   clamp becomes a minute. Frames are cached on first use — his round robin
   — so after one revolution a tick is a string assignment.

   Honest note: the clamp figures are documented behaviour, NOT measured
   here. Two attempts to put a page into the hidden state under Playwright
   failed (a second `newPage()` is a separate window, and `window.open`
   opened one too, so `visibilityState` stayed `visible` both times). The
   design does not rest on those numbers; it rests on rAF being unavailable,
   which is what "hidden" means.

   THE PHASE IS THE WALL CLOCK, not a counter. So every window watching the
   same loop shows the same frame — the shader's "one world, many viewports"
   rule one surface over — and a reload does not restart the orbit. */
const FAV_N = 20;                  // frames per revolution, one per second
const FAV_PX = 32;
const FAV_WARN_HUE = 45;           // --warn  #fcd34d
const favCache = new Map();
let favCv = null;
const favHsl = (h, s, l, a) => `hsla(${h}, ${s}%, ${l}%, ${a})`;
/* the hue comes from the project's tint (#143, `favHue` lives with it), so
   a strip of dreaming projects is legible by colour alone. */

function favPaint(hue, moving, pip, frame) {
  const S = FAV_PX;
  if (!favCv) {
    favCv = document.createElement('canvas');
    favCv.width = favCv.height = S;
  }
  const g = favCv.getContext('2d');
  g.clearRect(0, 0, S, S);
  const cx = S / 2, cy = S / 2, R = S * 0.315, W = S * 0.115;
  const dim = moving ? 1 : 0.6;    // a stalled loop reads faded, not absent
  g.lineCap = 'round';
  g.strokeStyle = favHsl(hue, 54, 57, 0.74 * dim);
  g.lineWidth = W;
  g.beginPath(); g.arc(cx, cy, R, 0, 7); g.stroke();
  const a0 = -Math.PI / 2 + (frame / FAV_N) * Math.PI * 2;
  // the trail: which way it is going, and the page's own softness. It is
  // also what makes "moving" legible in a single static frame, which is what
  // reduced motion is left with.
  if (moving) {
    const steps = 16, span = Math.PI * 0.9;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      g.strokeStyle = favHsl(hue, 88, 76, (1 - t) * 0.55);
      g.lineWidth = W * (1 - t * 0.3);
      g.beginPath();
      g.arc(cx, cy, R, a0 - span * (t + 1 / steps), a0 - span * t);
      g.stroke();
    }
  }
  const hx = cx + Math.cos(a0) * R, hy = cy + Math.sin(a0) * R;
  const gl = g.createRadialGradient(hx, hy, 0, hx, hy, W * 2.1);
  gl.addColorStop(0, favHsl(hue, 96, 88, 0.95 * dim));
  gl.addColorStop(0.35, favHsl(hue, 96, 84, 0.55 * dim));
  gl.addColorStop(1, favHsl(hue, 96, 80, 0));
  g.fillStyle = gl;
  g.beginPath(); g.arc(hx, hy, W * 2.1, 0, 7); g.fill();
  g.fillStyle = favHsl(hue, 96, 90, dim);
  g.beginPath(); g.arc(hx, hy, W * 0.66, 0, 7); g.fill();
  if (pip) {
    // knock a transparent gap first: the badge has to read as a separate
    // object, and with no ground to paint one there is nothing else to cut
    // it out with.
    g.save();
    g.globalCompositeOperation = 'destination-out';
    g.beginPath(); g.arc(S * 0.79, S * 0.21, S * 0.168, 0, 7); g.fill();
    g.restore();
    g.fillStyle = pip === 'warn' ? favHsl(FAV_WARN_HUE, 95, 62, 1)
                                 : favHsl(hue, 92, 74, 1);
    g.beginPath(); g.arc(S * 0.79, S * 0.21, S * 0.118, 0, 7); g.fill();
  }
  return favCv.toDataURL('image/png');
}
function favURL(hue, moving, pip, frame) {
  const k = hue + '|' + (moving ? 1 : 0) + '|' + (pip || '-') + '|' + frame;
  let u = favCache.get(k);
  if (u === undefined) { u = favPaint(hue, moving, pip, frame);
                         favCache.set(k, u); }
  return u;
}
/* Derived from the title's own two functions, so the icon and the words in
   the same tab can never disagree. Nothing is drawn before data arrives —
   an invented state is worse here than no icon, because this one is read
   from across the room. */
function applyFavicon() {
  const link = document.getElementById('favicon');
  if (!link || !data) return;
  const need = titleNeed(data);
  const moving = titleLive(data) === 'dreaming';
  const pip = need === '!' ? 'warn'
            : (need && need !== '0') ? 'accent' : null;
  // Reduced motion pins the FRAME and keeps everything else: the trail and
  // the full brightness still say "in flight" with no motion at all, which
  // is the wisp's rule (timing changes, never function or legibility).
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const frame = (moving && !rm) ? Math.floor(Date.now() / 1000) % FAV_N : 0;
  const url = favURL(favHue(), moving, pip, frame);
  if (link.href !== url) link.href = url;
}
