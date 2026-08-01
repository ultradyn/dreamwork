# 2026-08-02-0610 — #940 guard says what it means

The guard's `MISSING` line was true and told the reader nothing. The fix was
text, not logic, and that made the whole task unusually clean to reason about:
no behavior changed, only what the guard *says* when it goes red.

## The note is scoped, not blanket

The brief named a direction-2 candidate I almost walked into: "you improve the
message but only on the MISSING path, while the UNPINNED path stays silent."
I caught it by reading the candidate list before implementing, not after. The
note fires for both MISSING and UNPINNED — both are what a correct repair
produces (a moved coordinate, or one retired to prose). It does NOT fire for
UNRESOLVABLE, because an unresolvable hash is a defect, not a correct repair.
The test asserts the negative on the UNRESOLVABLE path explicitly, which is
the direction-2 check that the note is scoped rather than blanket.

## The four-literal problem was the harder half

Retiring literals (3) and (4) required arguing redundancy against (2), which
is the contract the brief explicitly protected. The argument turns on a
property worth naming: **a Counter comparison is a strictly stronger
assertion than a total comparison.** If two Counters are equal entry-by-entry,
their totals are equal by construction. The reverse does not hold — two
Counters with the same total can have different entries. So (3) added nothing
(2) did not already cover for every single-sided change, and for the
both-sided edit case (the #852 trap) it was itself one of the four literals
being bumped.

The harder call was (4): the PASS-line text checked something real (the
"pinned, not verified" wording from #921), but it baked the count into the
same literal. Splitting it into a wording check (4a) and a structure regex
(4b) separates the two concerns. The regex deliberately uses `\d+` rather
than a derived count — it asserts the denominators are *visible* (degrade-to-
zero, #868), not that they equal a hardcoded number. That avoids the
"compares itself to itself" trap the brief warned about.

## What I assessed and did NOT do

The brief offered a direction-2 candidate: "the message names the two files
but not that enrolment is a coordinator act, so a lane reads it as an
invitation to edit both." I considered adding a second sentence, but the note
already says "This is a COORDINATOR act at fold" and "a lane must not resolve
it by editing the guard or its test to force green." Adding more would be
volume without discrimination — the note is already explicit on the actor and
the prohibition.

## The note is only reachable when findings exist

This is the last direction-2 candidate, and it is true: a lane deciding what
to do next in the green case never sees the note. But the green case is the
one where the lane has nothing to do — the guard passed, the enrolment is
current. The note exists for the exact moment the brief describes: a lane
sees a red guard caused by its own correct edit and needs to know why. In the
green case the docstring carries the same information for anyone reading the
guard proactively. Two channels for two audiences.
