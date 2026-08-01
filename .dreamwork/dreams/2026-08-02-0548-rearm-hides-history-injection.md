# Re-arming after rebase can hide the injection that required the re-arm

While finishing task #935, the final rebase changed the pinned expectation
file. `redproof.py check` correctly refused expectation drift and instructed me
to forget, begin, re-inject, and restore against the rebased bytes.

After I followed that instruction without creating a new injection commit, the
history scan printed:

```
history: examined 4 commit(s) ... 0 holding a recorded injection.
```

That was a false green. Commit `f1ace5ce` still held the wrong-checkout
injection, and its `dev/land_lane.py` blob had the same SHA-1 as the newly
recorded injected bytes. Re-arming at the rebased branch tip made every earlier
commit an ancestor of the new `begun_head`, so the registration-boundary rule
excluded the injection commit as preexisting.

I did not change `redproof.py` in this lane. To make this lane's final evidence
honest, I created a fresh post-rebase injection commit; the final check refused
and named it. The general gap remains: the documented re-arm remedy for
post-rebase expectation drift can erase the scan's authority over injections
recorded before that remedy.
