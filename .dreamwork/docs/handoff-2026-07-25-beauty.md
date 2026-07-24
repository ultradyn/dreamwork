# Handoff — dreamer-beauty, 2026-07-25

For the next dreamer touching `watch.py`. The authoritative references are
`watch-design.md` (skill root — tokens, components, the motion language,
voice) and `.dreamwork/lessons.md`. This doc does **not** duplicate them; it
records the one unfinished item and gotchas specific to my recent landings.

## What's done (this session)

All committed to master, deployed to `:35110`, tests green (36 watch + 10
roll): #63 #64 #65 (transitions) · #66 (review morph) · #67 (dev overlay
draw-time) · #68 (per-route seed) · #71 (command palette / composer + PiP
pop-out) · #72 (styleguide) · #74 (world-space shader) · #78 #79 #81 #82 #83
#84 #85. Nothing from that set is mid-flight.

## UNFINISHED: #91 — "the composer" tweaks (NOT STARTED)

Human tweaks to the #71 command form. The human named the form **"the
composer"** — adopt that name in `watch-design.md` and in code comments.
Where the composer lives:

- **Markup:** `APP_BODY` → `#cmdpalette` (form `#cmdform`: the label,
  `select#cmdkind`, `textarea#cmdtext`, buttons `#cmdsend` / `#cmdpop`,
  `#cmdmsg`).
- **CSS:** `STYLE` → `#cmdplus`, `#cmdpalette`, `#cmdform`, `.cmdrow`,
  `#cmdpop`, `.cmdmsg`.
- **JS:** `COMMAND_JS` IIFE → `place()` (positions the panel under the +
  button), `openCmd`/`closeCmd`, the `#cmdform` submit handler (reads the
  kind via `document.getElementById('cmdkind').value`), `requestPopout` /
  `popoutDoc` / `openPopout` / `popoutShell` / `POPOUT_CSS` / `POPOUT_BODY`,
  `ripple`.
- **Server:** `COMMAND_KINDS`, `command_line`, `_handle_command` (`/command`).

The five items (verbatim intent), with pointers:

1. **Composer sits a bit LOWER** — more breathing room between the +/×
   button and the form. In `COMMAND_JS place()`: `pal.style.top =
   (r.bottom + 8) + 'px'` → bump the gap (e.g. `+ 18`). (CSS default
   `#cmdpalette { top:4rem }` is only the pre-first-open fallback.)

2. **Pop-out should have the shader background too**, wired with #74
   world-space anchoring (offset by the *popout window's* global screen
   coords) so any window at the same screen position shows the identical,
   deterministic field. THIS IS THE HARD ONE.
   - Today the popout is a plain document (identity band + form/iframe),
     built in `popoutShell` + `openPopout`.
   - `SHADER_JS` is one IIFE bound to the *main* document's `#dreambg` +
     `window.dreambg`. To reuse it you must extract a mountable
     `mountDreambg(win)` that operates on `win.document` / `win.requestAnimation
     Frame` / `win.innerWidth` etc. instead of the implicit globals, then
     call it on a canvas injected into the popout document.
   - #74's anchoring already reads `window.screenX/screenY/innerHeight/
     outerHeight`; in the popout those are the popout's own values, so the
     field aligns at the seam automatically. VERIFY the chrome estimate
     (`outerHeight - innerHeight`) in a Document-PiP window — PiP chrome is
     minimal, so it should be ~0; confirm it doesn't skew the offset.
   - If the full 4-pass shader in a second context proves too heavy/awkward,
     a fallback is a lighter CSS tinted-noise band — but the human asked for
     "the shade of background", i.e. the real field; prefer the extraction.
   - Watch the headless-GL context-loss gotcha (lessons.md) — a second GL
     context doubles the exposure.

3. **Trim the dead space under the composer buttons.** Look at `.cmdmsg`
   (`min-height:1em; margin-top:.5rem`) and `#cmdform` bottom padding —
   there's slack below `.cmdrow` when `#cmdmsg` is empty.

4. **Command selection → a button group** with an animated selection: a
   background indicator that SLIDES between options + a subtle text effect on
   the selected label. Replace `select#cmdkind` with a row of buttons (one
   per `COMMAND_KINDS` value); track the active kind in JS; the submit
   handler reads the active button instead of `cmdkind.value`. The sliding
   indicator = an absolutely-positioned element transitioned to the active
   button's offset/width (FLIP or left/width transition). Keep it on the
   motion language (soft, ~.3s cubic-bezier); reduced-motion = no slide.

5. **Hover-discoverability menu** — hovering an icon reveals ALL commands:
   the main ~3 that fit as buttons AND the less common ones, each with a
   one-line description, easy to select. The kinds live in `COMMAND_KINDS`
   (server) — the client hard-codes the same list in the composer; consider a
   single source (e.g. a `COMMANDS` array of `{kind, label, desc}` in the
   shell). This pairs with **#86** (plugin-contributed command kinds) — design
   the menu to render an arbitrary list so #86 slots in.

Styleguide: every page-changing commit updates `watch-design.md` in the same
commit (the DREAMWORK.md routine). The composer/motion vocabulary is already
there — extend it; rename "command palette" → "composer".

## Gotchas for a successor touching my recent code

- **Enter animations must SNAP their start state** (`transition:none` on the
  start-state class). `#view` carries an always-on transition; the composer's
  sliding indicator (item 4) and any new enter effect will hit the same trap
  I fixed in #85 — see the lesson. Verify true-zero/true-start with a
  per-frame trace, not a single screenshot (headless screenshot timing is
  coarse; the CSS compositor runs independent of the stalled main thread).
- **`--autoreload` makes iteration fast:** run
  `python3 watch.py --target <t> --port <your-port> --autoreload`; editing
  `watch.py` re-execs the server and reloads open capture pages (generation
  on `/mtime`). Use a port that is NOT 35110/35111.
- **Answer/comment submit morphs set `holdRerenderUntil`** (~1.6s) so the
  live tick doesn't regroup mid-morph. If you change the submit flow, keep
  that or the card jumps. The eventual regroup (open→awaiting-fold section) is
  still a plain `setContent` — a graceful cross-group morph is #77.
- **Entries are keyed `o<i>`/`a<j>`** (open/answered index) so `sendAnswer`/
  `sendComment` look the entry up in live `data` — don't round-trip titles
  through DOM attributes.
- **Sub-bullets never break entry parsing:** `parse_open_questions` /
  `parse_answered` treat `- **Answer…**` / `- **Follow-up…**` as fields, never
  entry boundaries (even un-indented). Keep that invariant if you touch them.
- **Popout identity is shared:** `openPopout` + `popoutShell` give every
  floated window the tint band + project basename + path. Item 2's shader
  goes inside that shell.
- Test capture scripts + instrumentation live in the session scratchpad
  (`/tmp/claude-1000/-home-xertrov-src-grok-hark/.../scratchpad/`) —
  `beautycap.mjs`, `optrace.mjs` (per-frame opacity), `rm-check2.mjs`,
  `reviewcap.mjs`, `cmdcap.mjs`, `note82.mjs`, `pip83.mjs`. They target a
  running server; adapt the port. They may be cleaned between sessions —
  the patterns (per-frame trace for motion; multi-timestamp for dissolves;
  fresh page per frame to dodge screenshot stall) are the durable part.
