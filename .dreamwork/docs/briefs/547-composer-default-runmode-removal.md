# Brief — #547: composer default back to add-idea + remove run-mode from the dashboard

Lane: lane-547default (glm-5.2). Filed from Max's add-idea (journal receipt `836e8b15`, ord 49):

> command composer: default should still be 'add idea', not 'chat' (or 'topic chat')
> also: remove run mode from dashbaord now that it's been superseded by posture

Two separable changes; land as TWO commits in the one lane (same regions).

## Part 1 — the composer's DEFAULT kind becomes add-idea (row order unchanged)

Context: #504 made `chat` the far-left kind (`COMMANDS[0]`) per his Q2 ruling, and the
composer's default selection is derived positionally from `COMMANDS[0]` — so chat became
the default by position. He wants **add-idea** to be the default again. He did NOT ask to
reorder the row: chat stays far-left (Q2 stands), the default selection changes.

Shape (recommended; you may improve but the invariant is fixed): introduce an EXPLICIT
default marker on the add-idea entry (e.g. `"default": True`) in BOTH the Python COMMANDS
(watch.py:~321) and its JS mirror (find it near watch.py:10165), plus one resolver idiom
("the entry marked default, else COMMANDS[0]") used at every read site:

- watch.py:10165 `let activeKind = (COMMANDS[0] || {}).kind;` (initial selection)
- watch.py:10256 `setKind((CORE_COMMANDS[0] || {}).kind);`
- watch.py:10507 `if (sent && !sent.sticky) setKind((COMMANDS[0] || {}).kind);` (decay)
- watch.py:304 comment (default = COMMANDS[0]) — update so it names the marker.

The invariant the work must honour: **the default is declared, never positional.** A future
reorder of the row must not change the default; a future change of default must not reorder
the row.

Bound checks that must move with the change (same commit):
- `test_watch.py` `test_chat_command_entry_is_far_left_default` (:~8605-8615) asserts chat
  is COMMANDS[0] AND the default. Split it: chat stays far-left (assert COMMANDS[0].kind ==
  'chat'); a NEW assertion pins add-idea as the declared default; assert exactly one entry
  carries the default marker (the precondition the resolver depends on).
- `dev/capture/draft.mjs` derives its decay target from `COMMANDS[0]` (:227-255, with
  comments saying "the decay target is the far-left kind"). Re-derive from the default
  marker the same way production resolves it, update the comments and the ok() at :255.
  Keep the sticky-membership floor (`chat`, `add-idea` both sticky) untouched.

## Part 2 — remove the run-mode picker from the dashboard

Max: run mode is superseded by posture (the pace axis covers it; posturePicker is the
sibling control at watch.py:4101 @ 6edcf95b). Scope:

- Remove the `runModePicker(d)` call (watch.py:4100 @ 6edcf95b) and the now-dead picker
  template/JS/CSS (the #290 arm JS ~5363-5400+, the chips description surface :1975 —
  trace what is picker-only vs shared with posturePicker; posturePicker stays).
- KEEP the `/run-mode` POST route and the `.dreamwork/run-mode` file: other readers exist
  and removal is a separate decision. Record on the task whatever still reads them (flag
  to the coordinator).
- The `runmode` browser guard's subject is the picker. Delete `dev/capture/runmode.mjs`,
  remove `runmode` from `DEFAULT_GUARDS` in the justfile, and keep the registration census
  consistent (lint's guard-registration check must pass: file deleted + entry deleted).
  If anything else in dev/capture references runmode, name it in your report.
- watch-design.md / dreamhub-design.md: if either documents the run-mode picker as a
  surface, update in the same commit (styleguide stays single-source).

## Constraints

- The composer kind row is a visible surface: `transitions.md` governs any
  appear/disappear — the picker's REMOVAL is a code change, but if any remaining element
  changes visibility at runtime, reuse the existing idiom, never a snap.
- Lane-owns: watch.py (composer COMMANDS + run-mode picker regions), test_watch.py (the
  chat/default tests), dev/capture/draft.mjs, dev/capture/runmode.mjs (deletion), justfile
  (DEFAULT_GUARDS), lint.py (only if the registration check needs a NOT_GUARDS touch —
  prefer delete-and-stay-consistent), watch-design.md (only if it documents the picker).
- Verification: pytest subsets only for the red/green loop (`-k chat` / `-k draft` /
  `-k runmode` / `-k lint`); solo guards via `DREAMWORK_GUARDS="draft" DREAMWORK_HUB_GUARDS=
  just guards 3989X` ONLY after `ss -ltn` shows the port free — never the full suite, never
  while another lane runs browsers. Red-first: the default-resolution change must fail the
  updated draft guard and the updated tests when the marker is removed/moved (cp snapshot →
  sabotage → watch FAIL → cp-restore byte-identical, never git checkout). A green red-run is
  a finding, not a relief — report it, don't conclude the code was fine.
- NEVER read_file an image (your API 400s and the lane dies). Text-only verification; the
  coordinator does the visual verdict from your screenshots.
- Commit `git commit --only <paths>` (new files: `git add` first). Append ONE line to
  `.dreamwork/handoffs.md` under `## Pending` before your last commit (#398 obligation).
  No attn, no pkill -f, no servers on 39880-39899 left running at exit.
