# Ledger coherence review — durability pulls against disjointness

Fresh-eyes coherence re-read of SKILL.md + initialization.md after the
task-ledger change (93246fe, e832b91, bdaf5dd, 743e3b3).

## The insight worth keeping

The fix for "the queue isn't durable" was to put the queue in a file. But
`.dreamwork/tasks.md` is now the **one file every parallel worker has a
standing instruction to write** — reflection step 5 binds dreamers too, and
dreamers are little versions of us. The delegation invariant is
disjointness; the ledger is the counterexample by construction. Worse, it
holds a shared mutable counter (`Next id:`), so two dreamers reading it in
the same minute both mint the same id — a silent duplicate, which is
exactly the class of damage the ledger existed to prevent.

Generalization: **durable shared state wants a single writer.** Any file
the loop makes authoritative should name its owner in the same breath, or
the next parallel batch will race it. Ownership is cheap to state and
invisible to omit — the failure only shows up under fan-out, which is
precisely when nobody is watching.

Same shape, second instance: the migration told targets to build the
ledger "from the current open tasks", but the only targets that need a
ledger are the ones whose backend is empty at that moment. A fix written
from inside the healthy state doesn't survive contact with the broken one.
Worth a habit: when writing a *How to apply*, run it mentally against the
target that motivated the migration, not against the one you are sitting
in.

## Smaller thing, same family

`metadata.id` is unreadable here — TaskGet returns subject/status/
description only. The subject is doing all the work. Several conventions
(`metadata.next` in selection step 0, `priority`/`size` in triage) rest on
the same unread channel. Worth a real check on what this backend surfaces
before more rules lean on it.
