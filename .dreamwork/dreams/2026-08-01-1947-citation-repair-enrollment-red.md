# Dream — #847 citation repair: three signals worth keeping

Three things surfaced on the citation-repair lane that generalize past
the one task.

## 1. A guard red on coordinate drift is a merge-time signal now, not a lane-time one

`dev/check_watch_citations.py` exits 1 with MISSING findings whenever
a citation's coordinate changes (line number or revision), because the
old enrolled coordinate no longer matches. After #921's narrowing
("pinned, not verified against the pinned revision"), a false pin is a
documentation defect the guard no longer catches — so a lane that
repairs a pin correctly makes the guard go red, on its own correct work.

That is the right design (the guard checks enrollment, not prose
truth), but it means the guard's red is now a signal the *coordinator*
resolves at fold (by updating enrollment), not a signal a *lane* can
treat as a pass/fail gate. The brief handled this correctly by saying
"leave the guard alone." Worth stating in the guard's own output or
docstring, because a lane that runs the guard expecting green will
block on its own fix — or worse, "repair" the guard to force green and
silence the enrollment update the coordinator needed.

## 2. Do not hand-transcribe a census you can extract verbatim

My first census reproduction reported `false=13 unresolved=6` — six
spurious UNRESOLVEDs — because the shell mangled the unicode in the
locator strings when I retyped the ROWS table (`→`→`->`, `·`→`.`,
`—`→`-`). The census block in the doc is a re-runnable script; the
honest way to run it is `sed -n '<line>,<line>p' doc > /tmp/c.py`.
A lane that trusts its retyped copy will diagnose a locator mismatch
and might "repair" the locator instead of the real pin — exactly the
wrong-file trap the campaign exists to close. Not a brief defect; a
habit. When a doc holds a re-runnable block, extract it; do not retype it.

## 3. The brief's "15 STALE occurrences" denominator has grown

`dev/dangling_citations.py` now reports `apply_reanchors_i3.py` at 12
(not 7) and `runmode.mjs` at 6 (not 3). #925's curated 15 was right at
its measurement; the corpus has grown since. The scanner is a census,
not a guard, so this is not a defect — but a lane taking this task
fresh should re-derive from the main checkout (the brief's warning
about worktree over-counting is correct and load-bearing). Denominators
in briefs are a snapshot; the live number is the scanner's.
