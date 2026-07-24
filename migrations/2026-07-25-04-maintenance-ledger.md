# 2026-07-25 — maintenance ledger (markers + staleness-aware roll)

## What changed

Maintenance commits are marked `dreamwork(maintain:<item>): ...` — git is
the maintenance ledger. roll.py reads it: item weights grow with commits
since the item's last marker (integer hunger, ×1 fresh → ×9 at 200
commits; `--no-staleness` disables; silently off outside git). The
maintenance-pool default is now 5 × item count instead of fixed 30, so
new items grow the pool rather than diluting per-item shares.

## How to apply

Adopt the marker prefix for maintenance commits from now on (a clean pass
may record an `--allow-empty` marker). No state files to create; history
accrues naturally. Explicit `--maintenance N` flags in any recorded
`roll:` line of DREAMWORK.md keep working unchanged.
