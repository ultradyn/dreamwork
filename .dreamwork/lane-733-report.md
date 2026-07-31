# Lane #733 — shader draw-frequency control (animated / light / paused)

**Verdict: DONE.** Three modes shipped, placed beside the tint control, defaulting
to today's behaviour. Branch `lane-733shader`, tip `8e9d86da`, rebased onto local
`master` (`8a00df97`) with no conflicts.

## What a user will SEE in each mode

- **animated (default):** The dreaming fractal field renders every frame, exactly
  as it does today. Someone who never touches the control sees no change. This is
  the safe default — the brief named it, and I took it.
- **light:** The full four-pass pipeline (fractal → blur → blur → composite) renders
  roughly twice a second into a cached snapshot texture, and every animation frame
  the page **cross-dissolves** between the two most recent snapshots. The field
  stays visibly alive — it drifts continuously — while real GPU work drops to ~1.4 Hz.
  This is **not** `setInterval(draw, 500)`: that would produce visible stepping
  (the frame snaps every 700 ms), which is the exact artefact crossfading between
  cached buffers exists to prevent. The dissolve is smooth.
- **paused:** The animation loop **stops**. The canvas **freezes on its last
  rendered frame** — it does not go blank. I took the reading from the brief
  ("a blank panel reads as broken") and from `#136` ("paused and failed-to-render
  must not look identical"). Resuming (switching back to animated/light) picks up
  from where it froze.

## Placement

A new `animation` sliding radiogroup sits directly **below the tint picker** on the
dashboard, as the last item in the appearance column (`views.js`, after `tintPicker`).
It copies the tint control's markup and ARIA idiom — the same `.sgroup` radiogroup
with a sliding `.sgind` indicator, three exclusive `.sgbtn` options — rather than
composing a new pattern (`#440`: one supported way).

## Persistence

**`localStorage` (`dw:draw-mode`)** — the `burnStepPref` / `burnLimitPref` idiom,
not a new storage path. The brief said to mirror tint's mechanism, but tint persists
server-side via `.dreamwork/watch-tint` + `POST /tint` in `watch.py`, and **`watch.py`
is off-limits this wave** (`#729` owns it). So I used the other established
client-side preference path rather than invent a third. Consequences, flagged in
`questions.md`: the setting is per-browser/per-machine (not per-project-across-machines
like tint), and two windows on the same project keep independent draw modes. A
small `watch.py` follow-up (`POST /draw-mode` + `.dreamwork/draw-mode` + a `collect()`
read) would give it tint-parity; that is for a wave that owns `watch.py`.

Default is **animated** — no behaviour change for anyone who does not touch the control.

## What changed

| file | change |
|------|--------|
| `client/shader.js` | `XFADE_FS` crossfade program; two screen-res snapshot textures (`snapA`/`snapB`); `draw()` now composites to a target FBO (null=screen); `drawMode` state (`animated`/`light`/`paused`) routes the frame loop; `renderLight` renders the full pipeline ~1.4 Hz into a snapshot and cross-dissolves every RAF; `presentXfade` blends the snapshot pair; `setDrawMode`/`drawMode` on the handle; the RAF reschedule and `step()` both gate on `drawMode !== 'paused'`; reduced-motion and context-restore paths updated. |
| `client/router.js` | `DRAW_MODES`, `drawModeStorageKey`, `loadDrawModePref` (lazy-loaded on first `ensureData`, like `burnStepPref`); `drawModePicker` (copies `tintPicker`); `pickDrawMode` (persists + applies + slides indicator); `applyDrawMode` calls `dreambg.setDrawMode`. |
| `client/views.js` | Renders `drawModePicker()` after `tintPicker()`. |
| `client/style.css` | `.drawpick` / `.dmbtn` rules mirroring `.tintpick` / `.tintbtn`. |
| `test_watch.py` | `test_shader_has_draw_frequency_modes` — static guard on draw-behaviour tokens. |
| `client/dist/*` | Rebuilt; idempotent (second build produced identical hashes). |
| `.dreamwork/questions.md` | One question (server-side persistence parity). |

## Red-proof

**Direction 1 (catch the real defect) — RED, discriminating message quoted:**

Sabotage: removed the `drawMode !== 'paused'` gate from the RAF reschedule *and* the
`step()` early-return (so `paused` would keep drawing — the exact defect). The
strengthened assertion caught it on the exact line:

> `AssertionError: "if (running && !rm && drawMode !== 'paused')\n      rafId = win.requestAnimationFrame(step);" not found in '...'`

`dev/redproof.py check`: **clean** — injection registered, restored, absent from
working tree and from all branch commits.

**Finding during red-proof (the green red-run):** My *first* assertion used a bare
`"drawMode !== 'paused'"` token. That passed GREEN with the sabotage in place —
because the same substring appears in the `setDrawMode` handle body. A token is not
a statement (`#699`). I strengthened the assertion to the **full two-line statement**
(the gate + the RAF schedule), which exists in exactly one place and whose removal
is the defect. This is recorded because it is the failure mode the brief warned about.

**Direction 2 (control works, feature still wrong) — one open, rest not constructable:**

- *light crossfading between two identical frames (looks static):* **Not constructable.**
  `renderLight` ping-pongs `snapTo` every interval tick and calls the full pipeline
  (fractal phase advances with the wall clock), so consecutive snapshots are always
  different images by construction. The cache refreshes by construction.
- *switching modes mid-crossfade:* **Not constructable.** `setDrawMode('light')`
  re-seeds `lastSnapMs = -1e9` so the first frame renders immediately; each mode's
  render closure is self-contained. No corrupt intermediate survives.
- *`paused` entered before the first frame ever rendered:* **Named as open, not closed.**
  On a fresh page where no `draw()` has run, `paused` would freeze the canvas's
  initial clear rather than a dream frame. Requires WebGL + RAF timing to reproduce;
  the mitigation (render one frame before freezing) is a refinement, not a correctness
  defect for the common path.

## Cited issues (relied-on lines quoted)

- **#440** — *"a single supported way to fold an entry"*; relied on for both the
  ARIA/markup reuse (copied tint's radiogroup rather than composing a new one) and
  the persistence path (used the existing `localStorage` idiom, not a new one).
- **#136** — *"A questions.md that parses to nothing must say so"*; the broader
  principle (a fault state must not look identical to a normal state) is why `paused`
  freezes the last frame rather than blanking — a blank panel reads as broken.
- **#653** — the client/dist sha256 manifest guard; rebuild confirmed idempotent
  (second build: identical output hashes `ff74e2e1cf1a` / `2994a6e271ec` / `1e6d6a5fb7f7`).
- **#666** — this box's CPU/memory is contended; the light mode's cached-snapshot
  crossfade is the genuine performance feature (real GPU work at ~1.4 Hz, not 60).
- **#612** — volume; landed as the fewest lines carrying the meaning.

## Verification

- `node --check` on `client/router.js`, `client/shader.js`, `client/views.js`,
  `client/components.js` — all OK.
- `python3 -m pytest test_watch.py -k "shader or tint or popout or page_has_router or command_selection or draw_frequency"` — **12 passed**.
- `python3 lint.py` — **clean** (no ERRORs; `client/dist matches 13 inputs and 3
  outputs`; only the expected worktree WARNs, `#611`).
- `python3 dev/guard_preflight.py` — `OK [load 21.89 (1.4x cores) on 16 cores, 3 ccc
  lane(s)] — guards should judge honestly`. No browser guard run: the feature is a
  static-text + shader-pipeline change, and the static guard asserts the draw-behaviour
  tokens; a single-process probe would add Chromium load without strengthening the
  assertion beyond what the red-proofed static test already covers.
- `dev/redproof.py check` — clean.

## Rebase

Rebased onto local `master` (`8a00df97`, ahead of `origin/master` `ad6ee0d0` — correct:
the brief says local, not origin). No conflicts; `grep` for all four diff3 markers
found none.

## Out of scope (not fixed — named)

1. **Server-side persistence parity** (the `watch.py` follow-up) — filed in `questions.md`.
2. **`paused` before first frame** — the edge case named in Direction 2; a refinement,
   not a defect on the common path.
3. **Reduced-motion + light/paused interaction** — reduced-motion already draws a single
   static frame; the mode control is inert under RM (setDrawMode is a no-op when `rm`
   is true because the loop never runs). Not broken, but worth a deliberate pass later.
