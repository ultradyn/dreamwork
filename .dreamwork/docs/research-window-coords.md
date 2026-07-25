# Research: getting a web page's absolute screen position, robustly

Scope: how a page can find where its viewport sits in physical screen coordinates, well enough that
several browser windows showing the same site agree on a shared world-space coordinate system.
Target runtime: vanilla JS, single Python file, no build step, localhost, Chromium primary / Firefox
secondary, Linux/Wayland as primary desktop environment.

---

## Short answer

Call this, in this order, and recompute on every plausible move/resize/zoom event (there is no
reliable "window moved" event — see Q7):

```js
function getWindowOrigin() {
  // 1. Best case: Window Management API already granted (Chromium only).
  //    Gives multi-monitor-aware left/top and per-screen devicePixelRatio.
  //    Requires an earlier permission grant; see Q3.
  if (window.__screenDetails) {
    const s = window.__screenDetails.currentScreen;
    // window.screenX/Y is still the right source for *this window's* position;
    // screenDetails mainly adds the ability to reason about *which* screen and
    // its bounds/scale, which window.screen (legacy) does not give you.
  }

  // 2. Universal fallback: legacy properties (CSS pixels, viewport-relative).
  const x = window.screenLeft ?? window.screenX;
  const y = window.screenTop  ?? window.screenY;
  return { x, y, dpr: window.devicePixelRatio };
}
```

Practical recipe used by the one real-world open-source precedent for this exact problem
(bgstaal's `multipleWindow3dScene`, a three.js scene synced across windows via `screenLeft`/
`screenTop` + `localStorage`, see Q-sources): poll `window.screenLeft`/`screenTop` (+ `innerWidth`/
`innerHeight`) on your own render/animation loop (rAF or a ~30-60Hz interval), diff against the last
known value, and broadcast the new shape via `localStorage` + the `storage` event (or `BroadcastChannel`,
which is cheaper and same-origin-only, fine for localhost). There is no cheaper "give me an event"
option that is broadly supported — see Q7.

**Where the naive `screenX`/`screenY` + scale-constant approach breaks, concretely:**
1. It silently returns `0` for both windows on Wayland (native Wayland toolkits in Firefox/Chromium),
   so "two windows side by side" collapses to "two windows both at origin." **This is not a bug you can
   fix from the page** — it's a deliberate Wayland protocol restriction. See Q6/"what breaks".
2. `screenX`/`screenY` are in **CSS pixels**, and CSS pixels stretch/shrink with **page zoom** (Ctrl+/-)
   independently per window. If window A is at 100% zoom and window B is at 110% zoom, "1 CSS px" is a
   different physical distance in each — your shared "scale constant" is wrong for one of them. See Q4.
3. `screenX`/`screenY` measure the **viewport's left/top edge**, not the outer window frame — so if you
   were trying to infer chrome thickness from `outerWidth - innerWidth`, that's a separate, only-partially-recoverable
   quantity (Q2), but it does NOT affect the viewport-origin approach itself (screenX/Y already give you
   the viewport edge, not the frame edge — this is a common misconception, see Q1/Q2).
4. No standard change event exists for "window moved" — dragging a window produces no reliable
   cross-browser callback, so you must poll (Q7).

---

## Q1: What do `screenX`/`screenY`/`screenLeft`/`screenTop` actually measure?

**Verified (MDN):** `Window.screenX`/`Window.screenLeft` return "the horizontal distance, in CSS
pixels, of the left border of the user's browser **viewport** to the left side of the screen."
Same for `screenY`/`screenTop` vertically. `screenLeft`/`screenTop` are plain aliases of
`screenX`/`screenY` (originally IE-only, now universal; Baseline since July 2015) — use whichever,
there is no behavioral difference, but a `screenLeft ?? screenX` fallback costs nothing.

Key points, all verified against MDN:
- **They measure the viewport (content area), not the outer window frame.** This directly answers
  "outer frame or viewport?" — it's the viewport's top-left corner already. You do not need to
  subtract chrome to get to the viewport; the legacy API gives you the viewport position directly.
  (`Window.outerWidth`/`outerHeight` and `moveTo`/`moveBy` operate on the *window frame*; screenX/Y do not.)
- **Unit is CSS pixels**, not device/physical pixels. CSS pixels are zoom-dependent (Q4) but not
  directly device-scale-dependent in the same way — see the Chromium coordinate-spaces detail below.
- **Not explicitly documented by MDN**: exact interaction with OS-level display scaling and with
  browser zoom. This gap is filled by the Chromium source doc (see "what breaks," verified) and by
  community bug reports (Firefox Bugzilla), which is called out below as inference/community, not
  spec text.

**Verified via Chromium's own coordinate-spaces design doc**
(chromium.org/developers/design-documents/blink-coordinate-spaces/): "Blink implements UI scaling
by applying the device scale factor to the browser zoom" and geometry exposed to web content is
"converted to CSS pixels by dividing by the browser zoom, which combines both the user's zoom
preference (ctrl +/-) and device scale factor." CSS pixels and DIPs (device-independent pixels) are
equivalent **only** at 100% page zoom; zooming makes a CSS pixel bigger or smaller relative to a DIP.
**Consequence, confirmed by this doc's own logic:** if a window's physical position on the monitor is
unchanged but the user zooms the page, `window.screenX` (reported in CSS px) changes numerically,
because the same physical offset now divides by a different zoom factor. This is a real, verifiable
gotcha, not a hypothetical — see the "what breaks" section.

**OS display scaling** (Windows/macOS/Linux desktop scaling, e.g. 150%/200%): the device scale
factor is folded into the same "browser zoom" divisor above, so `screenX`/`screenY` in CSS pixels are
already OS-scale-normalized — a monitor at 200% OS scaling and one at 100% will each report `screenX`
in that monitor's own CSS-pixel space, which is the *correct* per-window behavior for laying out CSS,
but means a naive single "scale constant" applied identically to both windows will misplace content
if the two monitors have different scale factors. You need each window's own `devicePixelRatio` (or,
better, the per-screen `devicePixelRatio` from the Window Management API, Q3) to normalize before
combining across windows — this is unverified-by-direct-test but follows necessarily from the
documented CSS-pixel/DIP relationship above, and is corroborated by community reports of `screenX`
being "unzoomed"/inconsistent across browsers in the whatwg/css mailing list threads (community
report, not spec).

---

## Q2: The chrome-offset problem — is there a reliable way to get the viewport's offset within the window?

Reframe: you likely don't need this. Because `screenX`/`screenY` already give the **viewport's**
screen position directly (Q1), you do not need `outerHeight - innerHeight` to find the viewport
inside the window — that quantity only tells you the *total* chrome thickness (toolbars + title bar +
borders combined), and MDN's own docs and community examples only ever use it to answer "how much
chrome is there," not "where does the viewport start," because `screenX/Y` already answers the latter.

If you specifically needed the *window frame's* origin (e.g., to call `moveTo`/`moveBy` predictably,
or to know how much chrome is above vs. below/beside the viewport):
- **Verified:** `Window.outerHeight` "returns the height, in pixels, of the whole browser window,
  including any sidebar, window chrome, and window-resizing borders" (MDN, paraphrased above from
  search extract — treat exact wording as community-paraphrase-of-MDN, re-check if wording matters).
  `outerHeight - innerHeight` gives total vertical chrome but not its split between top (title bar +
  tab strip + toolbar + bookmarks bar, all variable and user-configurable) and bottom (status bar, rare
  today). **There is no documented API that splits this** — MDN does not expose "chrome above" vs.
  "chrome below" separately. This is a real, unresolved gap; the closest people get is inference:
  `window.screenY - <window frame top>`, but you can't get "window frame top" either without the
  legacy `moveTo`-style frame origin, which no read-only property exposes. **Unverified / inference:**
  common community workaround is to just not need this number — anchor everything to the *viewport*
  origin (`screenX`/`screenY`), which sidesteps the chrome-split problem entirely. This matches the
  "what we already do" approach the team described, and is the right call.

---

## Q3: The Window Management API (`getScreenDetails()`, `screen.isExtended`, `window-management` permission)

**Verified, MDN + Chrome for Developers + W3C explainer:**

- `Screen.isExtended` — boolean, **no permission prompt required**. True iff the device has more than
  one screen. If a `window-management` Permissions-Policy blocks the API (e.g. cross-origin iframe
  without `allow="window-management"`), `isExtended` always returns `false`. Cheap to poll/read anytime.
- `window.getScreenDetails()` — async, returns a `ScreenDetails` promise. **Triggers a permission
  prompt** ("manage windows on all your displays") the first time it's called, gated behind the
  `window-management` permission (renamed from the older `window-placement`). Must be called from a
  secure context (HTTPS) — **note: `localhost` counts as a secure context**, so this works for your
  local dev/dashboard use case without a real TLS cert.
- What it adds over `window.screen`/`screenX`/`screenY`: `window.screen` only ever describes the
  **current/primary** screen. `getScreenDetails()` returns `screens: ScreenDetailed[]` — every
  connected display — each with `left`, `top` (position relative to the shared **multi-screen origin**,
  see Q6), `width`/`height`, `availLeft`/`availTop`/`availWidth`/`availHeight` (usable area, excluding
  OS taskbars etc.), `devicePixelRatio` **per screen** (critical if your monitors have different scale
  factors — this is exactly the normalization Q1 said you'd need), `isPrimary`, `isInternal` (built-in
  vs external), `label` (human-readable, e.g. "Samsung Electric Company 28\""), and `orientation`.
  Also exposes `currentScreen` (which of the `screens` entries the calling window is currently on) and
  two events: `screenschange` (display connected/disconnected) and `currentscreenchange` (fires when
  **the current screen's attributes change, including the window moving to a different display** —
  this is the closest thing to a "window moved (across screens)" event that exists, though it does not
  fire for an in-screen drag, only a cross-screen move).
- **Browser support, verified via caniuse (mdn-api_window_getscreendetails) as of the page's latest
  snapshot (dated in this research to ~June 2026):** Chrome/Edge/Opera and their Android equivalents:
  supported (Chrome/Edge since ~v100-111 depending on sub-feature). **Firefox: not supported, any
  version. Safari/Safari iOS: not supported, any version.** This is the single most important support
  fact for your Firefox requirement: **you cannot rely on this API in Firefox at all**, only on the
  legacy `screenX`/`screenY`/`screen` properties, which Firefox does support.
- **Practically for your case:** treat `getScreenDetails()` as a **Chromium-only enhancement layer**.
  Feature-detect with `'getScreenDetails' in window`, request it lazily behind a user gesture (a button
  click, not on page load — browsers generally require/strongly prefer a user activation for the
  permission prompt), cache the resulting `ScreenDetails` object, and fall back to legacy properties
  everywhere else (including Firefox and ungranted/denied Chromium).

---

## Q4: `devicePixelRatio` and zoom — how CSS px, device px, and OS scaling interact

**Verified (MDN):** `window.devicePixelRatio` is "the ratio of the resolution in physical pixels to
the resolution in CSS pixels for the current display device." Both **page zoom** (Ctrl+/-) and **OS
display scaling** move this number in Chrome and Firefox — zooming in increases `devicePixelRatio`.
**Verified, cited from CSS-Tricks/MDN cross-check:** desktop **Safari is the odd one out — it reports
a constant `devicePixelRatio` regardless of page zoom** (not relevant to your stated Chromium+Firefox
scope, but worth remembering if Safari is ever added).
**Verified, MDN:** **pinch-zoom does not change `devicePixelRatio`** (it's a visual-viewport-only
transform, see Q5) — only actual page/browser zoom does.

**Detecting a change (verified MDN pattern, no polling needed for this one):**
```js
function watchDPR(onChange) {
  let remove = null;
  const update = () => {
    remove?.();
    const mq = matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    mq.addEventListener('change', update, { once: true });
    remove = () => mq.removeEventListener('change', update);
    onChange(window.devicePixelRatio);
  };
  update();
  return () => remove?.();
}
```
This is the standard `matchMedia` self-rearming pattern from MDN's own devicePixelRatio docs page —
it fires when the ratio changes for any reason (zoom, or dragging the window to a monitor with a
different scale factor).

**What breaks:** if two windows of your app sit on monitors with different OS scale factors (e.g. a
200%-scaled 4K laptop panel next to a 100% external monitor), each window's `screenX`/`screenY` are
each internally consistent CSS-pixel coordinates *for that monitor*, but 1 CSS px is a different
physical distance on each monitor. A single global "world scale constant" cannot be correct for both
windows simultaneously unless you multiply each window's contribution by its own
`devicePixelRatio` (or, with the Window Management API, the specific screen's `devicePixelRatio` —
more robust because `window.devicePixelRatio` only ever describes the screen the *calling* window is
currently on, whereas `ScreenDetailed.devicePixelRatio` lets you look up any screen's factor even from
a window that isn't on it).

---

## Q5: `visualViewport` — pinch-zoom, on-screen keyboards; relevant to a desktop dashboard?

**Verified (MDN):** `window.visualViewport` exposes `offsetLeft`/`offsetTop` — "the offset of the
left/top edge of the visual viewport from the left/top edge of the **layout viewport**, in CSS
pixels" — plus a `scale` factor for pinch-zoom. **Verified, MDN, important distinction:** "On desktop
browsers, `window.scrollX`/`scrollY` update as the window scrolls — the visual viewport position does
not change [relative to layout viewport]. On mobile browsers, it is usually the **visual viewport**
that changes rather than the window position" (e.g., pinch-zoomed-in mobile Safari).

**For your case (desktop, localhost, Chromium/Firefox, no touch pinch-zoom expected):**
`visualViewport` is **largely irrelevant** — its whole purpose is reconciling pinch-zoom and the
on-screen-keyboard-shrinks-the-viewport case on mobile, neither of which applies to a desktop
dashboard driven by ctrl+scroll/trackpad-pinch-as-page-zoom (which, per Q4, shows up as
`devicePixelRatio` change instead, on desktop Chrome/Firefox — verified/consistent with the MDN
device-vs-visual-viewport distinction above). Only reach for it if you must support a touch-desktop or
tablet scenario where OS/browser lets users pinch-zoom without changing `devicePixelRatio`.

---

## Q6: Known gotchas and lies

- **Multi-monitor + negative coordinates — verified, MDN "Multi-screen origin" page.** There's one
  shared **multi-screen origin** (0,0), by OS convention the top-left of the primary monitor, though
  the spec allows any point. Screens/windows to the left of or above the primary report **negative**
  `left`/`top`/`screenX`/`screenY`. Worked example straight from MDN: primary 1920x1080 with 25px of
  OS chrome at its top; a 1440x900 secondary monitor placed to the *left* reports
  `ScreenDetailed.left = -1440`. Your shared world-space math must handle negative offsets — don't
  clamp or `Math.abs()` them.
- **Wayland: `screenX`/`screenY` (and the whole legacy positioning surface) return 0 / are
  unreliable, by design — verified via the w3c/window-management GitHub issue #68 discussion and
  corroborated by multiple Firefox Bugzilla reports (community-report tier, but consistent across
  independent sources).** Wayland's compositor security model deliberately does not tell client apps
  their absolute position on screen, and does not let clients set an absolute position either.
  Concretely this means, on native Wayland Firefox/Chromium: `window.screenX`/`screenY` read 0 (or a
  stale/meaningless value), `window.open(..., 'left=x,top=y')` and `window.moveTo()`/`moveBy()` are
  ignored, and `element.requestFullscreen({screen})` targeting a specific screen doesn't work either.
  **This is the single biggest failure mode for your use case** — on a Wayland desktop, the naive
  approach doesn't degrade gracefully, it silently returns the same wrong answer (0,0) for every
  window. **Mitigations (all partial, none solve it fully):**
  - Chromium under **XWayland** (X11 compat layer) generally *does* get real coordinates, because
    XWayland still exposes X11-style absolute positioning to the app even while the compositor is
    Wayland underneath. So "Wayland" isn't monolithic — it depends on whether the browser itself is
    running as a native-Wayland client or under XWayland. You cannot detect this distinction from JS.
  - The Window Management API's `getScreenDetails()` does **not** fix this on native-Wayland Chromium
    either, per the linked issue — the underlying protocol gap is the same one; Chrome OS is
    exploring proprietary Wayland protocol extensions / Mojo side channels to work around it, but
    that's not a solution available to a normal web page, and isn't standard Linux Wayland.
  - Practical fallback discussed in that issue thread: display-relative positioning (e.g., "put me on
    screen N" via `set_output`-style requests) rather than absolute x/y — doesn't help you recover a
    lost absolute position, only helps if you're the one placing a new window.
  - **Recommendation for your case:** detect the degenerate case (`screenX === 0 && screenY === 0` for
    more than one open window simultaneously, or just always) and have the page fall back to a
    **manual calibration step** — e.g., the user drags a marker/crosshair from one window to a matching
    one in the other window once, and you compute the offset from that, or you accept an explicit
    "arrange these windows left-to-right" input. There is no fully automatic fix available to page JS
    on native Wayland.
- **Fullscreen mode:** could not find authoritative documentation of exact `screenX`/`screenY`
  behavior when `requestFullscreen()` is active. **Unverified/inference:** since fullscreen removes all
  chrome and the viewport occupies the full screen, `screenX`/`screenY` should read `(0,0)` (or the
  target screen's origin if using the Window Management API's `{screen}` option to fullscreen onto a
  specific non-primary display) — but treat this as inference, not a verified fact; test it directly if
  fullscreen matters to the design. It did not come up as a documented edge case in MDN's screenX/Y
  page.
- **Values only updating on certain events / stale values:** community reports (Firefox Bugzilla
  #171482, "screenX and screenY do not function correctly before window is shown") indicate the values
  can be wrong very early in the window lifecycle (before first paint/show) — read them after load,
  not synchronously at script-start, if you can avoid it.
- **`resize` event firing on pure window *move* (no size change), on HiDPI displays** — community
  report (nwjs/nw.js issue #5686, Chromium-based): dragging a window on a HiDPI display can spuriously
  fire the `resize` event due to a documented ±1px rounding artifact in the reported width/height
  during the drag, even though nothing was actually resized. Don't treat every `resize` firing as
  proof of an actual size change; re-check `innerWidth`/`innerHeight` against your last known values
  before reacting.
- **Screens array ordering**: per the W3C explainer, `ScreenDetailed[]` entries are sorted by
  `(left, top)`, but the spec itself flags this ordering as unreliable in the presence of mirrored
  displays — don't index into the array positionally, match by `label`/`isPrimary`/geometry instead.

---

## Q7: How do you detect a CHANGE (the window being moved)?

**Verified: there is no standards-track "window moved" event.** The historical `onmove`/`onMove`
handler is Netscape-4-era, non-standard, and effectively dead — do not rely on it (the search results
surfaced it only as a historical curiosity; it is not in any current spec or MDN page).

**What actually exists, in order of how much it helps:**
1. `ScreenDetails.currentscreenchange` (Window Management API, Chromium-only, requires the granted
   permission from Q3) — fires when the window's *current screen* changes, i.e., **a cross-screen
   move**, not an in-screen drag. Verified via MDN's `ScreenDetails: currentscreenchange` page and the
   W3C explainer. Useful as a coarse, low-cost signal layered on top of polling, not a replacement for it.
2. `matchMedia('(resolution: ...)').addEventListener('change', ...)` (Q4) — fires on `devicePixelRatio`
   change, which happens if the window is dragged to a monitor with a different scale factor. Also
   coarse (same-scale-factor moves produce nothing), and Chromium/Firefox-verified, not a general move
   detector.
3. **Polling is the only complete, cross-browser answer**, and it's what the one concrete prior-art
   example (bgstaal/multipleWindow3dScene, verified by reading its `WindowManager.js` source) actually
   does: read `screenLeft`/`screenTop` (+`innerWidth`/`innerHeight`) once per animation frame (or on a
   timer), compare to the last-known shape, and only broadcast (via `localStorage` + the `storage`
   event, so other same-origin windows get notified) when it actually changed. This is cheap — reading
   four numbers per frame is negligible — so there's no real reason to poll less often than your
   render loop already runs; a dedicated `setInterval` in the 100-250ms range is more than fine if you
   don't already have a rAF loop.
4. For cross-window notification specifically (not detection): `BroadcastChannel` (same-origin, all
   evergreen browsers, no localStorage-quota/write-race concerns) is a cleaner primitive than
   `localStorage` + `storage` event for a localhost multi-window app with no build step — a few lines
   of vanilla JS, and no data actually needs to persist. `localStorage` is what the prior-art example
   uses (simpler mental model, works even if you want the "last known layout" to survive a reload), but
   `BroadcastChannel` is the better fit for your stated constraints if persistence isn't a requirement.

---

## What breaks — summary table

| Assumption in the naive approach | Reality | Verified? |
|---|---|---|
| `screenX`/`screenY` give a stable, comparable coordinate across windows | True only if all windows share the same zoom level and the same `devicePixelRatio`; CSS-px meaning shifts with zoom (and OS scale) per window | Verified (Chromium coordinate-spaces doc) |
| A single scale constant is enough | Breaks across monitors with different scale factors; need per-window (or per-screen) `devicePixelRatio` | Verified reasoning from MDN devicePixelRatio + Chromium doc |
| `screenX`/`screenY` work the same on Linux as elsewhere | Return 0 / unreliable on native-Wayland Firefox/Chromium by design; may work under XWayland, but you can't detect which mode you're in from JS | Verified (w3c/window-management #68, corroborated by Firefox Bugzilla reports) |
| There's an event for "window moved" | No standard event exists; only coarse cross-screen (`currentscreenchange`, Chromium-only + permission) or scale-change (`matchMedia` on resolution) signals exist; polling is required for real-time in-screen drags | Verified (MDN pages for both events; absence of a move event confirmed by lack of any current spec reference) |
| Negative coordinates are a bug to clamp away | They're correct and expected for monitors left of/above the primary | Verified (MDN Multi-screen origin page) |
| `outerHeight - innerHeight` tells you where the viewport starts within the window | It only gives total chrome thickness, not the top/bottom split, and you don't need it anyway since `screenX/Y` already gives the viewport's screen position directly | Verified (MDN outerHeight description) + inference for the "no split available" claim |
| The Window Management API is a drop-in universal upgrade | Chromium-only (Chrome/Edge/Opera + Android variants); **no Firefox or Safari support at all** as of mid-2026 | Verified (caniuse mdn-api_window_getscreendetails snapshot) |

---

## Sources

Verified against official documentation:
- [Window: screenX property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/screenX)
- [Window: screenLeft property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/screenLeft)
- [Window: screenTop property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/screenTop)
- [Window: outerHeight property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/outerHeight)
- [Window: innerHeight property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/innerHeight)
- [Viewport concepts — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/CSSOM_view/Viewport_concepts)
- [Window: getScreenDetails() method — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/getScreenDetails)
- [Window Management API — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window_Management_API)
- [Multi-screen origin — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window_Management_API/Multi-screen_origin)
- [Screen: isExtended property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Screen/isExtended)
- [ScreenDetailed: devicePixelRatio property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/ScreenDetailed/devicePixelRatio)
- [ScreenDetails: currentscreenchange event — MDN](https://developer.mozilla.org/en-US/docs/Web/API/ScreenDetails/currentscreenchange_event)
- [ScreenDetails: screenschange event — MDN](https://developer.mozilla.org/en-US/docs/Web/API/ScreenDetails/screenschange_event)
- [Window: devicePixelRatio property — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/devicePixelRatio)
- [VisualViewport — MDN](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport)
- [Manage several displays with the Window Management API — Chrome for Developers](https://developer.chrome.com/docs/capabilities/web-apis/window-management)
- [window-management EXPLAINER.md — w3c/window-management (GitHub)](https://github.com/w3c/window-management/blob/main/EXPLAINER.md)
- [Window Management — W3C spec draft](https://www.w3.org/TR/window-management/)
- [Blink Coordinate Spaces — chromium.org design doc](https://www.chromium.org/developers/design-documents/blink-coordinate-spaces/)
- [Window API: getScreenDetails — caniuse](https://caniuse.com/mdn-api_window_getscreendetails)
- [Support for window placement in Wayland — w3c/window-management issue #68](https://github.com/w3c/window-management/issues/68)

Community reports / secondary sources (flagged inline above as such):
- [1761033 — window size/position not restored in Wayland — Bugzilla](https://bugzilla.mozilla.org/show_bug.cgi?id=1761033)
- [171482 — screenX/screenY incorrect before window shown — Bugzilla](https://bugzilla.mozilla.org/show_bug.cgi?id=171482)
- [1292571 — Wrong real screen size while zoomed — Bugzilla](https://bugzilla.mozilla.org/show_bug.cgi?id=1292571)
- [Window 'resize' event fires when window dragged on HiDPI displays — nwjs/nw.js #5686](https://github.com/nwjs/nw.js/issues/5686)
- [Can JavaScript Detect the Browser's Zoom Level? — CSS-Tricks](https://css-tricks.com/can-javascript-detect-the-browsers-zoom-level/)
- [bgstaal/multipleWindow3dScene — GitHub (prior-art implementation, source read directly)](https://github.com/bgstaal/multipleWindow3dScene)

Direct code read: `WindowManager.js` from bgstaal/multipleWindow3dScene (fetched raw source) —
confirms the polling + `localStorage`/`storage`-event pattern described in Q7.
