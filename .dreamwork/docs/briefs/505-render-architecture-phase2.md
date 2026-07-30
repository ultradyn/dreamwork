# Brief — #505 phase 2: retire the remaining hand snapshot/restore pairs + fold the review dock into the reconciler

Task: **#505** (P1, open — verified in the store before writing this brief).
Phase 1 landed (`5e4b90ea`): vendored morphdom, keyed reconciliation of
`#view`, the content-hash skip, the corpse-rule guard. His ruling (Q3):
**phase 2 = the review dock**, and phase 1's own design says the hand
snapshot/restore pairs become **dead code** under reconciliation
(`.dreamwork/docs/plans/render-architecture.md` — "Subsumes #141/#503/#494
(their snapshot/restore pairs become dead code; `data-keep` stays as a
reconciliation key)").

Lane-owns: `watch.py`, `test_watch.py`, `dev/capture/` (guard files you touch only)

**Read first:** the design doc (esp. the IGC and the phase split), the
phase-1 diff (`git show 5e4b90ea` and its merge `8d9ae68e`), and
`transitions.md` — every transition on this UI obeys it, no exceptions;
reuse the existing idiom, never author a second one.

## Scope (three acts, one lane)

1. **Inventory, then retire, the surviving hand snapshot/restore pairs.**
   Phase 1 reconciled `#view`'s lists and disclosures; the pairs the
   coordinator recorded as remaining are the **bdHover pair** and the
   **cardState / viewInputs / askState belts** — but VERIFY that against
   the code: enumerate every remaining snapshot/restore site around the
   reconciled root (grep the phase-1 survivors), and for each either
   (a) delete it because keyed reconciliation now preserves the state it
   defended, with the reconciliation key named, or (b) keep it with a
   one-line comment saying why reconciliation cannot cover it. A pair
   that survives without a reason is the failure this act exists to
   prevent. Dead-code deletion is the goal — every deleted pair is a
   class of focus/selection bug that cannot regress.
2. **Fold the review-dock swap into the reconciler (Q3 phase 2).**
   `setLiveContent` (~`watch.py:6685` at design time — verify) does a
   narrower `replaceWith` today; route it through the same keyed
   reconciliation phase 1 built for `#view`, so selection/caret state
   inside the review dock survives data.json ticks the same way. The
   dock's identity key needs a stated choice (the review artifact's
   name/path is the natural key — verify it is stable across ticks).
3. **Guards, red-first.** The corpse-rule guard idiom from phase 1 is
   the shape. Any NEW invariant you rely on (e.g. "no snapshot/restore
   pair remains around the reconciled root" — a structural test) gets a
   test that is shown to fail when the invariant is broken: name the
   production line, sabotage it, watch the test fail, restore
   byte-identical (`cp`, never `git checkout`). If you touch a
   `dev/capture/` guard, 5× solo PASS via the real justfile harness
   (`DREAMWORK_GUARDS=<name> DREAMWORK_HUB_GUARDS= just guards 3989X`
   after checking the port range is free), including 2 under load.

## Constraints

- **transitions.md is law.** Phase 2 must not introduce a snap: a state
  that used to be restored by hand and is now preserved by reconciliation
  is the SAME settled outcome with less machinery — if anything visibly
  changes in motion, that is a finding to report, not a detail to ship.
- The review-dock fold must not change what the dock SHOWS — same
  content, same lifecycle; only the swap mechanism changes.
- **Model-dependent verification wording (read this):** if you are
  grok-4.5 you may read your own screenshots. If you are glm-5.2 you
  MUST NOT `read_file` any image (the API 400s on image content blocks
  and it KILLS the lane — this exact crash ended lane-504chat): verify
  text-only (DOM assertions via the capture harness), and write
  before/after screenshots to `screenshots/lane-505p2/` for the
  coordinator's visual verdict instead.
- No edits outside Lane-owns. `file-formats.md`, `SKILL.md`,
  `watch-design.md` are coordinator-owned — if the work changes a
  documented contract, FLAG it in your DONE line instead of editing.
- Small commits in your worktree, message prefix `505p2: …`. Run
  `python3 -m pytest test_watch.py -q` green before reporting.
- DONE report: append ONE line to
  `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
  `[lane-505p2] DONE <shas> — <one line>` plus lines for: pairs retired
  vs kept-with-reason, the dock key choice, every red-proof (production
  line → test that failed), guard runs, and anything flagged.
  Use `dev/relay.py` if present; never `attn`.
- Do not claim a model you were not dispatched as.
