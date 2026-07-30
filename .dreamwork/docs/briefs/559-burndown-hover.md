# Brief #559 — burndown hover: full-column hit zone + persistent cross-dissolving tip

Task: **#559** (P2, origin: human — his 23:07 do-next, verbatim below).
Lane: `lane-559bdhover`. Model: glm-5.2 (**substitution recorded**: grok-4.5 is
the UI-lane model but is down with 401s; coordinator does all visual verdicts —
you must NEVER `read_file` an image).

His words, verbatim:

> burndown chart hover currently works fine for the top bar (# tasks open & #
> commits that period). However, the hover should work over the full height of
> that column in the burndown chart, so both the top section and bottom
> section. Also, once the detailed hover is visible, it should stay visible
> when moving between columns (and the content just dissolves between old and
> new values when it changes).

Two acts, both his:

1. **The hit zone is the whole column.** Today the hover works over the top
   section (the open-tasks bar); the bottom section (landed/commits) is dead.
   The pointer handlers (`watch.py` ~7779–7811) resolve
   `e.target.closest('.bdnet .bdcol[data-open]')`; the column markup is built
   at ~3922–3928 and `.bdflow` is the bottom half (`watch.py:950`). Find why
   the bottom half never reaches a handler (a listener bound inside `.bdnet`
   only, a hit-test gap, a dead strip between sections — measure, don't guess)
   and make every pixel of a column's full height hoverable, top section and
   bottom section alike. Keyboard focus parity: whatever focuses a column
   today must keep working unchanged.
2. **The tip persists across columns and dissolves its content.** Once the
   detailed hover (`.bdtip`) is visible, moving the pointer from one column to
   another must NOT hide-and-show it. The tip stays; its content cross-
   dissolves from the old column's values to the new one's. First show and
   final departure keep today's arrive/depart envelopes.

## The one rule with no exceptions

Read `transitions.md` FIRST, before writing a line. Every transition obeys it —
and this task is *made of* transitions. The idiom that already exists is the
one you reuse:

- **Persistence is not a transition at all.** Moving between columns while the
  tip is live must produce no depart, no arrive, no opacity dip, no hash-skip
  rebuild. The gesture is: nothing happens to the container.
- **The content swap is a dissolve with part-way frames** — old values fade as
  new values fade in, never vanish-then-appear. Look at how `.bdtip.depart`
  (watch.py:965) and the existing swap machinery already do this elsewhere in
  the page before authoring anything new; a second idiom is a defect per
  transitions.md, however small.
- **Reduced-motion parity:** the tip still appears and stays; the swap snaps
  (no cross-fade), exactly as `bdtipReduced()` already decides for the
  existing transitions. Both modes are asserted.
- An end-state assertion cannot fail on a motion bug — "did it move" can't
  either. transitions.md opens with how to check; follow it.

## Lane-owns

`watch.py` (burndown region only — the `.bd`/`.bdnet`/`.bdflow` markup, the
`bdtip`/`bdinsp` hover machinery, their CSS), `dev/capture/bdhover.mjs`.

NOT yours: `transitions.md`, `watch-design.md`, `lint.py`, `justfile`,
`dev/ledger.py`, `ledger_parse.py`, anything another lane holds. If the change
needs a design-record or transitions-contract update, **FLAG it in your
report** (quote the stale passage, propose the new text) — the coordinator
lands those files.

## Verification demands (repo-standard, all four)

1. **Born-red.** Extend `dev/capture/bdhover.mjs` with the new assertions
   (full-height hit zone incl. the bottom section; tip persistence across a
   column-to-column move with no hidden/depart interval; content swap
   produces part-way frames — e.g. opacity sampled mid-swap strictly between
   0 and 1 — and snaps under reduced-motion). Watch them FAIL against the
   current page first. Assert preconditions at runtime: the fixture's columns
   must really have a bottom section taller than zero, the two columns used
   must really carry different values (derive both at runtime — a literal
   tuned to today's fixture is a check with an expiry date).
2. **Red-proof.** Name the production line that would have to change for each
   new check to fail, then change it (cp-backup → sabotage → FAIL →
   cp-restore → `cmp` byte-identical — NEVER `git checkout`). If a green
   red-run happens, that is a finding: report it, don't conclude the code was
   fine.
3. **Solo guard runs only.** NEVER `just test`, NEVER the full guard sweep.
   Run `DREAMWORK_GUARDS=bdhover just guards 39890` alone, and check the port
   is free first (`ss -tlnp | grep 3989`). The coordinator runs the full
   suite at the merge gate.
4. **Relevant pytest.** The burndown/provenance pytest tests
   (`python3 -m pytest test_lint.py -q -k burndown` and any test_watch
   burndown tests you touch) stay green; say what you ran.

## Mechanics

- You are in an isolated worktree. Commit each increment with
  `git commit --only <paths>`; a NEW file needs `git add <file>` before
  `git commit --only <file>`. Never `git add -A`, never commit outside
  Lane-owns.
- **#398 hand-off obligation:** when done, append ONE line under `## Pending`
  in `.dreamwork/handoffs.md`:
  `- **#559** · landed \`<sha>\` [\`<sha2>\`…] · 2026-07-30 · by lane-559bdhover — <what>`.
  Bare shas, no parentheticals, NO model claim (#469). Verify it parses via
  `watch.parse_handoffs`.
- Do not deploy. Do not touch ports outside 39890. No `attn`, no `pkill -f`.
- Report: commits, what changed and why, born-red output, red-proof lines
  named + restore evidence, guard/pytest results, edge decisions with
  evidence, any FLAGs for coordinator-owned files, and anything you found
  that you did NOT fix (filed as a finding, not silently worked around).
