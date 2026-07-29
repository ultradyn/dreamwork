# Brief — #494: burndown hover tooltip fades in, then resets 1–2s later (mouse unmoved)

Lane: `wt/lane-494tip` · one task · work in the isolated worktree only.

## The bug, in the human's words (do-next, 2026-07-30 00:27)

> after hovering a burndown chart tasks/commits bar, the big tooltip-helper
> thing fades in and like 1-2s later it all resets. This happens even if the
> mouse doesn't move.

Both hover surfaces are implicated until diagnosed: `.bdtip` (the glance tip)
and `.bdinsp` (the richer dwell inspector). "Resets" = the visible hover UI
disappears / returns to the un-hovered state while the pointer is still over
the same column.

## Where to look (pointers, not conclusions — diagnose for real)

- `watch.py` ~7413–7600: the hover state machine — `bdtipCol`,
  `bdtipHideTimer`, `showBdTip/hideBdTip`, `bdinspCol`, `bdinspPin`,
  `bdinspDwell`, `bdinspSchedule/bdinspCancel`, `hideBdInsp`.
- `watch.py` ~861–905: the `.bdtip`/`.bdinsp` CSS (`.pose`, `.depart`,
  transitions).
- **Prime suspect class:** the dashboard's data poll re-renders the `.bd`
  panel HTML while a hover is active. The new DOM has fresh `[hidden]`
  tip/inspector nodes and the JS `bdtipCol`/`bdinspCol` still reference
  detached columns — visually "it all resets". Confirm or refute this before
  fixing; a 1–2s cadence smells like a poll or a timer, and the difference
  matters.
- `test_watch.py` and `dev/capture/` hold the existing browser-guard
  idioms. Burndown guards exist (`burndown` in the justfile guard list) —
  read them before writing a new one.

## Acceptance criteria

1. **Red first.** A deterministic check (browser guard or DOM-level test in
   the existing idiom) that fails on the pre-fix code: hover a column, do
   NOT move the mouse, advance past the reset window (and past at least one
   data poll, if the poll is the cause), assert the hover surface is still
   the active one for that same column. Prove the check is not born hollow:
   it must fail on un-fixed `master` code and pass after your fix — show both
   runs in the report. Assert in the check the precondition the check depends
   on (e.g. that a poll/render really occurred during the window, if that is
   the mechanism), per CLAUDE.md.
2. **Fix is minimal and causal.** Name the exact line(s) that cause the
   reset; the fix addresses that cause. If the poll re-render is the cause,
   the natural shape is: re-render preserves/rearms the hover state for the
   column still under the pointer (or defers the `.bd` re-render while a
   hover is live) — but follow the diagnosis, not this guess.
3. **transitions.md governs.** Any show/hide/move you touch uses the existing
   `.pose`/`.depart` idioms; nothing snaps; reduced-motion parity preserved.
   Read `transitions.md` before editing any of it.
4. **Constraints carried by the surface:** `.bdtip`/`.bdinsp` remain the ONE
   hover surface (no native `title=`, #487); keyboard-focus parity
   (`tabindex` columns) keeps working; a pinned (tapped) inspector still
   survives (#298).
5. `python3 -m pytest test_watch.py -x -q` green, `python3 lint.py --target .`
   no new warnings, and if any guard idiom changes, the guard was red first.

## Working agreement

- Commit in small increments (~80-line chunks) with `#494` in each message;
  use `git commit --only <paths>` (and `git add` new files first — `--only`
  on a directory does not pick up untracked files).
- Do NOT touch the main checkout; your worktree is the whole world. The
  ledger store (`.dreamwork/ledger.sqlite3`) is gitignored and absent in your
  worktree — that is expected; `tasks.md` there is a one-line shim, do not
  read it as the ledger.
- Another lane may be merging `watch.py` work to master concurrently; keep
  your diff minimal and expect a rebase at merge time.
- Hand-off obligation (#398): if you cannot finish, you hand off — append
  your state to `.dreamwork/handoffs.md` (in the MAIN checkout, read-only
  otherwise) before stopping, so the next lane resumes from your words
  rather than your diff.
- Never use `attn`. Never `pkill -f`. Guards bind ports 39890–39899 — check
  ownership before running.
- Report: the diagnosed cause (exact lines), the red run output, the fix, the
  green run, and the commit ids.
