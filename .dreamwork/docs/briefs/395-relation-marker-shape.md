# Brief — #395: a relation marker without bold parses as absent

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop's durable state must tell the truth about the loop.
- **Session goal**: the checks that guard the ledger actually guard it.
- **This task**: `#395`. Read its ledger entry; every number below is measured, not guessed.

## The defect

`lint.check_related` enforces that a relation between two ledger entries is named by **both**
entries, because *"an entry is read alone"*. `RELATED_MARKER` requires a **bold** span, and
the function does `if not found: continue`.

So an entry that writes the marker **without asterisks** is read as having *no marker at
all*, and is skipped **in silence**. `file-formats.md:503-504` already documents the required
forms — one id `· related: **#251** ·`, several `· related: **#251, #292** ·` — so the
unbolded form was always wrong. Nothing said so.

**Four broken relations were hiding behind it, measured before repair:** `#388 → #383`
(nothing back), `#388 → #386` (#386 named only #383), `#387 → #361` (nothing back),
`#386 → #383` (nothing back). Three entries, all unbolded. **I have already repaired the
data** — bolded the three markers, added the back-references — so the ledger is clean today
and your job is the check, not the cleanup.

## Three traps, all found by walking into them. Inherit them.

1. **It is not a dead branch.** I assumed the "wrong case" ERROR was unreachable and had to
   correct myself by measuring: `Related: **#7**`, `RELATED: **#7**` and `related:**#7**` all
   produce a match while failing the `"related: **" not in flat` test, so that branch **does**
   fire. The hole is specifically **missing bold**, not case. Do not delete that branch.
2. **Two adjacent bold spans yield only the first id.** `**#393**, **#394**` gives `#393`,
   because the regex captures one span. The correct form is one span holding the list.
   **This failure surfaces as a *reciprocity* complaint about the ids it silently dropped** —
   the message points away from the cause, which is its own small defect and worth fixing in
   the same pass if it is cheap.
3. **The marker vocabulary cannot be quoted in prose.** Naming it in an entry body lets the
   non-greedy `[^*]*?` run forward to the next `**` *anywhere in the entry* and manufactures a
   phantom marker. My own ledger entry **about this bug** produced **five** before I reworded
   it. So the fix should anchor the marker to its own `·` field rather than matching it
   mid-sentence — otherwise writing about the ledger corrupts the ledger's own checks.

## What to build

**Flag a marker that is present-but-unparseable rather than skipping it**, and make the
message name the shape problem rather than a downstream symptom. Trap 3 says the matcher
should be anchored to a field boundary; decide how, and say why your anchoring does not
create a new phantom-marker class.

**Do not change `file-formats.md`'s required forms** — they are already right, and that file
has a live owner (**#396**). If you believe the spec needs a word, put the exact text in your
report and I will apply it. One thing you *may* usefully report: line 516 says *"the live
ledger has zero `related:` markers at the time of writing"*, which is now stale prose. Do not
fix it; it is not yours.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `lint.py`, `test_lint.py`. `git status --porcelain`
   shows nothing else. **`git diff --stat file-formats.md review_artifact.py watch.py` is
   empty** — all three have live owners.
2. **`python3 -m pytest test_lint.py -q -p no:randomly` exits 0**, with at least:
   - `test_an_unbolded_relation_marker_is_flagged_not_skipped`
   - `test_a_correctly_bolded_marker_still_passes`
   - `test_two_adjacent_bold_spans_are_flagged_rather_than_silently_truncated`
   - `test_the_marker_vocabulary_in_prose_does_not_manufacture_a_marker`
3. **THE CRITERION I CARE ABOUT MOST — red-prove the first test against the REAL revision, not
   a fixture you wrote to fail.** `tasks.md` at **`660a294^`** contains the three unbolded
   markers and the four broken relations. Run your check against that blob and it must name
   them. The model here is `lint.check_placeholder_citations`, which was proved against the
   actual revision that hid `#362`. **Say in your report which sha you proved yours against
   and which ids it named.** If you also use a synthetic fixture, assert at runtime the
   precondition that makes it meaningful — that `RELATED_MARKER` genuinely does not match it —
   rather than trusting the literal.
4. **A coverage number, because that is the general fix and it is one line.** `check_related`
   already prints `N related pair(s), all reciprocal`. Make it also report **how many entries
   it skipped as unparseable**. Had it printed *"3 pairs checked, 3 entries skipped"* this hole
   would have been on screen for days. A check that counts what it examined cannot silently
   stop examining things.
5. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green:
   - restore `if not found: continue` ⇒ the first test fails;
   - accept two adjacent spans as one marker ⇒ the third fails;
   - remove the field anchoring ⇒ the fourth fails.
   Separate injections, restored from a `cp` snapshot — **never** `git checkout -- `.
   **A green red-run is a finding, never a relief.** My own injection for another task an hour
   ago targeted a line that did not exist and the check passed — **grep for your injection to
   verify it reached the code** before believing any result.
6. **`python3 lint.py` exits 0 against the live tree** — the data is already repaired, so a
   new ERROR here means your check has a false positive on correct entries. That is the
   single most likely way to make this worse: 129 open entries, and a check that nags on
   good ones gets muted.
7. **`python3 -m pytest test_lint.py test_watch.py -q -p no:randomly` exits 0.** Take the
   baseline **from the tree, not from this brief** — other lanes are landing tests.
8. **`python3 lint.py` run as its own command**, never in the same shell command as a
   `git commit`. That has committed through a lint ERROR twice here.

## The hollow outcome

**A check that flags the three revisions I already repaired and nothing else.** The data is
clean now, so a check tuned to today's tree passes trivially. Criterion 3 exists for that:
prove it against `660a294^`, where the defect is real.

Second hollow outcome: **a false positive on prose.** Trap 3 means the ledger's own entries
discuss markers. Criterion 6 is the guard.

## The rules that matter most here

**Assert the precondition your check depends on.** A literal tuned to today's fixture is a
check with an expiry date nobody can see.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** Yours: a marker with **one**
bold span and a trailing comma; a marker naming an id that does not exist; a marker on an
entry with a **combined head** (`- **#7/#8**` — the ledger has these and both ids must
reciprocate); and a marker in the `## Recently landed` section rather than `## Open`. Say what
each does.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a
pass — and you are counting things whose counts can legitimately be zero.

## Files

**Yours:** `lint.py`, `test_lint.py`.

**Read, do not edit:** `file-formats.md` (lines 490-520 are the spec — **owned by #396**),
`.dreamwork/tasks.md` (**read-only, I am its only writer**), `watch.py`'s `ledger_entries`,
`CLAUDE.md`, `.dreamwork/lessons.md`.

**Never touch — live owners right now:** `review_artifact.py`, `test_review_artifact.py`,
`file-formats.md`, `dev/capture/fixture/**` (**#396**);
`.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md` (**#264**);
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`, `watch.py`.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately** — one runs browser guards and load manufactures false reds for it.
- **You need no server, no port, and no guards.** Do not run `just guards`; a port is held.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add`
  commits the whole index and will bury a concurrent lane's staged work — that happened in
  this tree. **Do not push.**
- Use **`fix(#395): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`**.
- Cap yourself at roughly **30 minutes**. **Priority order: criterion 3's real-revision red
  first, then the coverage number, then traps 2 and 3.** The real-revision red is what makes
  this a check rather than an assertion. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **which sha you red-proved
against and which ids your check named** (criterion 3 — I will read this first); the three
reds verbatim with exact test names and which neighbours stayed green; the exact new coverage
line your check prints; how you anchored the matcher and why that does not create a new
phantom-marker class; what each of the four neighbour cases does; the production line named
per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
