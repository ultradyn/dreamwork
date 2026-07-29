# Brief — lane-restcollapse: index "+ the rest (xx)" collapsible resets open→closed after ~1s (his do-next, 2026-07-30 03:30)

Lane-owns: the index-page status-glance section in `watch.py` (the
`ST_GLANCE` / `expand()` machinery around line 3150–3260 and whatever
live-refresh path re-renders it), plus its guard in `dev/capture/`, plus
`watch-design.md` if a contract row changes (same commit). Nothing else.
NOTE: lane-burndown2 concurrently owns the burndown panel in the same
file — stay out of the burndown panel's generation/JS/CSS entirely.

**Model:** grok-4.5 · **Isolation:** worktree (coordinator merge-gates).

## His report (verbatim)

*"get a subagent to investigate and fix this: the '+ the rest (xx)'
collapsible section on watch index page resets after being open for ~1
second."*

## Prime hypothesis (verify, don't assume)

The `+ the rest (N)` disclosure is rendered by `expand()` at
`watch.py:~3253` inside the status-glance block. The index live-refreshes
on a poll and re-renders that section from fresh data, replacing the DOM
node — so any open disclosure snaps shut on the next render (~1s matches
the poll cadence). This is the SAME CLASS as #494 (the burndown tooltip
resetting 1–2s after hover, fixed this session) — find that fix first
(`git log --oneline --grep=494` / the merge around `d62265d9`-era) and
reuse its shape if it applies.

But INVESTIGATE first: confirm the actual reset mechanism (poll re-render?
a class re-applied? a keyed transition re-mount?) by reproducing against a
local server with a real `.dreamwork` before touching anything. If the
cause is not the poll, the brief's hypothesis is wrong and your report
says what it actually is.

## The fix's shape (constraints, not a prescription)

- Open/closed state of that disclosure must survive re-renders —
  preserved across the poll, keyed stably (not by index, which shifts).
- Restoring state on re-render must NOT re-run the arrival transition
  every poll (a disclosure that visibly re-opens every second is the same
  bug wearing a fix). `transitions.md` governs: the user's own
  open/close gesture arrives/departs; a state restore is silent and
  instant in both motion modes. Read `transitions.md` before choosing the
  mechanism.
- The fix generalises honestly: if the same `expand()` helper serves
  other disclosures on the page with the same defect, fixing the helper
  is preferred over a one-off — but say in the report which disclosures
  you verified.

## Constraints (hard)

- Red-first guard: a `dev/capture/` check that opens the disclosure,
  waits across a refresh cycle, and asserts it is still open — RED on
  master, green after. It must assert its preconditions at runtime (the
  disclosure exists and starts closed; a refresh genuinely occurred —
  e.g. the section's generation/content changed or a poll fired), or the
  check proves nothing. Register it in the justfile.
- **A green red-run is a finding, never a relief.** Name the production
  line your guard depends on, break it (e.g. remove the state-restore
  call), watch the guard fail, restore byte-identical with `cp`.
- Reproduce evidence: headless screenshots or a DOM-state capture showing
  open→reset on master and open→held after your fix.
- Commit with `git commit --only <paths> -m …` (new files `git add`
  first). NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899; leave no
  fixture server running. The worktree lacks the live store — copy the
  main checkout's `.dreamwork/ledger.sqlite3` (+ watermark if any) into a
  /tmp scratch target and serve with `--target` (never write the main
  checkout's `.dreamwork/`).
- Do NOT deploy. Work on a branch in your worktree.

## Acceptance criteria (measurable)

1. Root cause named with evidence (not just the hypothesis accepted).
2. After the fix, the disclosure holds its state across ≥3 consecutive
   poll cycles (guard proves it; the guard was red on master).
3. No visible re-animation on state restore in either motion mode.
4. Guard registered, red-proved with the production line named; full
   guard run PASS; `python3 lint.py` no new findings vs master baseline.
5. `git diff master --stat` touches only owned paths.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
the confirmed root cause, the fix mechanism, the guard's red-proof, which
other disclosures share the helper and were verified, and any pushback.
