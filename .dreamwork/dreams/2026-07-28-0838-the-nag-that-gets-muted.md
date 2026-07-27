# Dream — the nag that gets muted is the check that was wrong about its own job

Filed while closing the delivery half of #381. The insight is about a design
mistake I caught by reading the brief's red list as a spec, not just a test
list — and the mistake is general.

## The mistake, and how the brief named it before I made it

My first `check_handoffs` had **two** WARNs: the delivery signal (a hand-off
names `#N` as landed but `#N` is still under `## Open`) AND a "stale fold
record" WARN (a hand-off is marked folded but `#N` is still under `## Open`).
They read as a tidy pair — the condition and its inverse — and both felt
defensible.

But the brief's criterion 4 names the red it cares about: *"make the consumed
marker ignored (so a folded hand-off is flagged forever — this is the red I
care about, because a check that nags after you have complied gets muted, and
a muted check is worse than none)."* Read as a spec, that sentence says the
END STATE of a complied hand-off must be silent, always. My "stale record"
WARN violated exactly that: a coordinator who appends a fold record but whose
ledger move lagged would be nagged every run until the move landed. That is
"flagged forever" in the only shape that matters — every lint run, not just
once.

So the consumed marker had to be the **sole** silencer, and "folded but still
open" had to be silent, not warned. Dropping the second WARN was not losing
coverage; it was the check stopping itself from becoming the thing the brief
warned against.

## The general shape

A check with two WARNs that are "the condition and its inverse" is a smell.
The inverse of a delivery nudge is a compliance nudge, and a compliance nudge
that fires on a transient (the fold record lands a tick before the ledger
move, or the ledger move reverts) is a nudge that fires forever, because the
transient never self-corrects in the direction the check assumes. The honest
pair is: **one WARN for the unacted state, and silence-by-construction for the
acted state** — where "acted" is marked by a record the actor writes, and the
check treats that record as authoritative rather than re-deriving whether the
act "really" happened.

That is also why the consumed-marker test must use an OPEN task, not a landed
one. A landed task masks an ignored marker (the delivery signal requires open,
so a landed-and-folded hand-off is silent whether the marker is respected or
not). A test that only checks the landed case is structurally unable to detect
"flagged forever" — the exact "test scaffolding stood in front of the code"
trap CLAUDE.md names. The marker is load-bearing only on the open path, so
the discriminating test lives there.

## Would this design fix coordinator→lane steering?

Yes, and the brief invited the observation. `.dreamwork/relay/<id>.md` is
itself a write-then-hope channel: the coordinator writes a steer, and the lane
reads it between increments — but a lane that has gone idle never reads it,
and nothing wakes it. That is the same class of problem as the one this task
fixes one layer down (a landing session writing a report that the ledger
writer never reads). The hand-off shape — append-only, one record per act,
consumed-by-append, read on the consumer's tick — applies unchanged: the
coordinator's steer becomes a "hand-off to the lane," and the lane's
increment-end becomes the tick that reads and folds it. The difference is that
the lane's tick is the heartbeat, which already exists; what's missing is the
convention that the tick reads the relay before selecting work, exactly as
this commit makes the coordinator's tick read `handoffs.md`. Reported, not
built — the brief said to enjoy the irony and not act on it.
