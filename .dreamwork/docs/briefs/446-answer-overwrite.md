# Brief — #446: a second `Answer` overwrites the first, and his words are gone at parse time

Repo: `ud-dreamwork`. Worktree: **`.worktrees/answerloss`**, branch **`wt/answerloss`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## The defect, and why it is P1

`watch.py`'s `questions.md` parser keeps **one** answer per entry: a second `Answer (via watch, …)`
**replaces** the first, so the earlier text is lost **at parse time** — before any render rule, thread rule or
dashboard code runs. Nothing reports it and nothing in the file records that it happened.

`questions.md` is the durable record of **what the human decided**. The ledger and `DREAMWORK.md` both defer to
it. A silent overwrite there is the worst class of bug this system can have, because **the loop cannot know what
it forgot.**

Found by `#254`'s design lane while reading a grammar it was forbidden to change. **Verify it before fixing
it** — construct an entry with two answers, parse it with the real parser, and show what survives. If both are
already retained, the finding is stale: say so with the evidence and stop.

## What to decide, then build

**Decide what a second answer means** and say why: an **amendment** to the first, a **correction**, or a
genuine second answer to a re-opened entry. The entry grammar already threads timestamped follow-ups
(`file-formats.md` states it), so the shape you need may exist — **prefer extending the existing thread grammar
over inventing a second one.**

**Then, in order of value:**

1. **Stop losing text.** Retain every answer with its author tag and timestamp, in file order.
2. **Failing that — and only if retention proves genuinely out of reach in one increment — make the discard
   loud.** A parse that discards human input must at minimum say so. Silent is the unacceptable part.
3. **Check the mirrors**: does `answers.md` (his questions *to* the loop) have the same defect? Does
   `## Answered`'s `lift_answer=False` hide a second instance? **Report what you found for each**, even if you
   fix neither.

## The red-first trap, stated because it is easy to walk into

**A fixture with two answers must assert both texts are retrievable, derived at runtime — never that a count is
2.** A count of 2 passes on a parse that kept the wrong one, or kept one twice. Derive both expected strings
from the fixture you built and assert each is present and attributed correctly.

- **Red-first, and name the production line.** Reinstate the overwrite and watch your test fail. **A green
  red-run is a finding, never a relief** — if it stays green, your test is not reaching the parser, and that is
  the more valuable result. Two tests in this repo were structurally incapable of failing about the single
  decision they were named for.
- **Assert the precondition your test depends on**: that the two answers differ, derived at runtime. A literal
  tuned to today's fixture is a check with an invisible expiry — this has bitten repeatedly here, three times
  today.

## Done means all of these

1. A two-answer entry parses with **both** answers retrievable and correctly attributed (or the loud-discard
   fallback, with the reason retention was deferred).
2. **`file-formats.md` states the grammar** in the same commit — the standing rule, checked by `lint.py`.
   **Never change the format ahead of the parser**, which is the ordering `#427` and `#415` established here.
3. Every existing caller and test still passes, or you name the one that changed and why the change is correct
   rather than convenient. **Find every caller before choosing a return shape** — `#427` chose `sha` + `shas`
   on a tuple subclass precisely so nothing downstream had to change; that pattern may apply.
4. The mirrors are reported on.
5. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). **Do not run the
   full `just test`.**
6. **Do not touch :35110**, the heartbeat, the monitors, or the loop. **Do not edit the live
   `.dreamwork/questions.md`** — the coordinator is its only writer; test against fixtures, and report any lines
   you want changed.

## Files

Yours: `watch.py`, `test_watch.py`, `file-formats.md`.

**Not yours:** `.dreamwork/questions.md` and `.dreamwork/tasks.md` (coordinator only — report lines),
`dev/capture/*`, `justfile`, `lint.py`, `dev/ledger.py`, `status_sync.py`, `review-artifact.template.html`.
**Check `git log` before you start**: other lanes are live in this tree tonight and one may hold `watch.py` or
`file-formats.md` — if `git status` shows a conflict you did not create, **stop and report** rather than working
around it.

## Practical

2 threads. `git commit --only <paths>` — **never `git add -A`**: five agents are committing in this tree.
**Commit before you finish** — a lane tonight did correct work and exited without committing, and had to be
recovered by hand.

## Report

Which model you are; what a two-answer entry does today (before your fix); what you decided a second answer
means and why; the parsed structures before and after, side by side; the exact production line whose reversion
reds your test; the precondition you asserted; what you found in `answers.md` and `## Answered`; and
confirmation you did not edit the live `questions.md`, run the full `just test`, or touch :35110.
