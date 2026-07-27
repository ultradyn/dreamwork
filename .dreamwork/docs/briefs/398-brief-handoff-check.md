# Brief — #398: a brief written after the obligation landed must carry it

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**When you land a commit**, also append **one line** to `.dreamwork/handoffs.md` under
`## Pending`:
`- **#398** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @grok — <one line, what landed>`
Append only (`cat >>`), never rewrite — other sessions append concurrently. Do **not** touch
`## Folded` and do **not** write to `.dreamwork/tasks.md`. **Note the irony and enjoy it: you
are building the check for the very obligation this paragraph imposes on you. It applies to
you anyway.**

## The chain above this task

- **DREAMWORK.md goal**: the loop's durable state must tell the truth about the loop, and it
  cannot when landed work is invisible to the ledger's writer.
- **Session goal**: turn a coordinator habit into something that fails loudly.
- **This task**: `#398`, the enforcement half of `#394`. Read `#394`'s ledger entry.

## Why this exists

`#381` built `.dreamwork/handoffs.md` — the channel a session uses to tell the ledger's writer
that it landed something — and both its readers were verified end to end. **Nothing wrote to
it.** `## Pending` sat empty while two lanes landed, because no producer had been told to use
it.

The first fix was a relay to three in-flight lanes. **It failed, measured:** the lane that
landed wrote no line and its report never mentions the relay. So the obligation moved into the
dispatch prompt and into `SKILL.md` (`6f72b8d`).

**But a coordinator habit with no check decays silently** — the failure mode is a lane that
simply does not write a line, which looks like nothing at all. And I wrote in the ledger that
this could not be checked because "lint cannot know a lane ran". **That was wrong, and the
thing that is checkable is the brief.** A brief is a committed file, its add-commit is
resolvable, and a brief that dispatches a lane without the obligation is exactly the defect.

## What to build

A `lint.py` check: **every brief under `.dreamwork/docs/briefs/` whose add-commit is newer than
the commit that introduced the obligation must mention `.dreamwork/handoffs.md`.**

The cutoff is resolved **from git, by content — never as a pinned literal**:

- the obligation landed in `SKILL.md`. Resolve its commit the way
  `test_review_artifact.py::_prechange_review_artifact` resolves its baseline: walk history and
  find the commit by **what the file contains**, not by a sha you typed. `git log -S` on a
  distinctive phrase from that `SKILL.md` paragraph is the mechanism; **pick the phrase and say
  which you picked**, because a phrase that later gets reworded silently disables the check.
  If you conclude a content-resolved cutoff is too fragile, **say so and propose the
  alternative** — that is a useful result, not a failure.
- a brief's own age comes from `git log --diff-filter=A -1 -- <path>`.

**Measured for you, so you can check your work against it:** there are **29** briefs; **2**
mention `handoffs.md`; the obligation landed at **`6f72b8d`, 2026-07-28T08:57**; the two
compliant briefs were added at **09:15** and later, and the newest non-compliant one at
**06:13**. So **the cutoff cleanly separates them and the check must be GREEN on today's tree
with 27 grandfathered and 2 in scope.** If your check reddens on the live tree, it is wrong —
that is criterion 4 and it is how this makes the repo worse rather than better.

## Two things to decide, and both have a defensible wrong answer

1. **An untracked brief has no add-commit.** `git log --diff-filter=A` returns nothing for a
   brief that exists but was never committed — which is the state a brief is in *while the
   coordinator is writing it*. **Treat it as in scope or skip it?** Decide and justify. Consider
   that `lint.py` is run mid-increment, constantly, and a check that fires on a file being
   written is a check that gets muted.
2. **What counts as "mentioning" it.** A substring match on `handoffs.md` is crude and will pass
   on a brief that says *"do not touch `.dreamwork/handoffs.md`"* — the exact opposite of the
   obligation. Decide how strict to be, state the tradeoff, and **do not over-engineer**: a
   check that tries to parse intent will have false positives, and criterion 4 says a false
   positive is the failure that matters. Erring loose is acceptable **if you say so**.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `lint.py`, `test_lint.py`, plus one line in
   `.dreamwork/handoffs.md`. `git status --porcelain` shows nothing else.
   **`git diff --stat watch.py file-formats.md review_artifact.py SKILL.md` is empty** — all
   four have live owners or are not yours.
2. **`python3 -m pytest test_lint.py -q -p no:randomly` exits 0**, with at least:
   - `test_a_brief_added_after_the_obligation_without_it_is_flagged`
   - `test_a_brief_added_before_the_obligation_is_grandfathered`
   - `test_the_cutoff_is_resolved_from_content_not_a_pinned_sha`
3. **THE CRITERION I CARE ABOUT MOST — the cutoff test must fail if the cutoff resolution
   breaks.** The third test's job is to prove the check is not silently disabled: assert that
   the resolved cutoff commit is a real commit **and** that it actually contains the obligation,
   so a reworded phrase becomes a **loud failure rather than a check that grandfathers
   everything**. A check whose cutoff resolves to "no commit found" and therefore skips every
   brief is the exact hollow outcome, and it would look identical to a clean pass.
   **Assert the precondition**: derive at runtime that at least one brief is in scope and at
   least one is grandfathered, and assert both counts are non-zero. A check that is vacuous
   because everything fell on one side of the cutoff must say so.
4. **`python3 lint.py` exits 0 against the live tree.** 29 briefs, 27 grandfathered, 2 in scope
   and both compliant. **A false positive here is the way to make this worse**, because a check
   that nags on correct files gets muted and a muted check is worse than none.
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - remove the `handoffs.md` mention from a brief added after the cutoff ⇒ the first test
     fails, and **the message must name the brief**;
   - make the cutoff resolution return nothing ⇒ the third test fails **rather than the check
     silently passing** — this is the red I care about most;
   - move the cutoff to before every brief ⇒ the second test fails.
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
   **A green red-run is a finding, never a relief**, and **grep for your injection to confirm it
   reached the code**: a coordinator injection this morning targeted a line that did not exist
   and the check passed.
6. **A coverage number**, in the idiom `#395` just established: the OK line reports how many
   briefs were **in scope** and how many **grandfathered**. A check that counts what it examined
   cannot silently stop examining things — that lesson is three hours old and cost four hidden
   defects.
7. **`python3 lint.py` run as its own command**, never in the same shell command as a
   `git commit`. That has committed through a lint ERROR twice here.
8. **`file-formats.md` is NOT yours** (live owner). If the rule needs documenting there, write
   the exact text into your report and I will apply it.

## The rules that matter most here

**Assert the precondition your check depends on.** This check's meaning depends on briefs
existing on both sides of a cutoff; derive both counts at runtime and assert the gap. A literal
tuned to today's 27/2 split is a check with an invisible expiry date — and the split moves
every time I write a brief.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** Yours: a brief **renamed** after
being added (`--diff-filter=A` on the new path); a brief added and then **amended**; a brief
whose add-commit is the **same** commit as the cutoff; and the directory containing a
**non-brief** file. Say what each does.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a pass —
and you are counting things whose counts can legitimately be zero.

## Files

**Yours:** `lint.py`, `test_lint.py`, one appended line in `.dreamwork/handoffs.md`.

**Read, do not edit:** `SKILL.md` (the obligation's text — read it to pick your phrase),
`.dreamwork/docs/briefs/*.md`, `.dreamwork/tasks.md` (`#394`, `#398`), `file-formats.md`,
`.dreamwork/lessons.md`, `test_review_artifact.py` (its `_prechange_review_artifact` is the
content-resolution idiom to copy).

**Never touch — live owners right now:** `watch.py`, `test_watch.py`, `watch-design.md`
(**#392a**); `review_artifact.py`, `test_review_artifact.py`, `file-formats.md`,
`dev/capture/fixture/**` (**#396**); `.dreamwork/docs/plans/watch-client-extraction.md`
(**#397**); `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`, `SKILL.md`.

## Operational constraints

- Limit builds/tests to **2 threads**. Three other lanes are live. **Do not generate load
  deliberately** — two run browser guards and load manufactures false reds for them.
- **You need no server, no port, and no guards.** Do not run `just guards`; two ports are held.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add` commits
  the whole index and will bury a concurrent lane's staged work — that happened in this tree.
  **Do not push.**
- Use **`feat(#398): …`**. `dream(...)` is reserved for a commit that lands a dream journal; if
  you write one, **name it in its own `git commit --only <path>`**.
- Cap yourself at roughly **30 minutes**. **Priority order: the cutoff resolution and its test
  first, then the scope check, then the coverage number.** The cutoff is the part that can fail
  silently, so it is the part worth building first. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the file,
because other agents append concurrently:

`.dreamwork/inbox.md`

State: each acceptance criterion and whether it holds; **the phrase you chose for the cutoff
resolution and why** (criterion 3 — I read this first); the three reds verbatim with exact test
names and which neighbours stayed green; **your in-scope and grandfathered counts on the live
tree**; both decisions from the two-things-to-decide section with their justifications; what each
of the four neighbour cases does; whether you wrote the hand-off line; the exact `file-formats.md`
text you would add; the production line named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
