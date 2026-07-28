# Brief — #419: no human blocker without a question, made checkable

Repo: `ud-dreamwork`. Worktree: **`.worktrees/419`**, branch **`wt/419`**. Do not push, do not merge.
**Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md` at all** — the coordinator writes that line when it merges. (Earlier briefs
told lanes to write it; both wordings caused merge conflicts, so the rule changed.)

## Why this exists

He tried to rule on `#264`, found no question, and wrote (watch `/answers`, 15:19):

> *"we must have a way to do this via the webui, and we should structure things in such a way that
> it's impossible for us to be blocked on a user decision without a corresponding question or
> sometihng either pending an answer/ruling, or that question could be answered but waiting for
> processing, but yea hthere always has to be an answer in our data for these kinds of questions."*

The loop had told him `#264` was the only thing on his desk while no entry existed for him to act on.
**The invariant:** every open task whose blocker is a human decision has a `questions.md` entry that
is either **open** or **answered-but-unfolded**. Both are legitimate. **Absent is not.**

## The design decision that comes first, and must not be skipped

**A task cannot currently say it is blocked on a human.** It lives in prose — `"awaiting his
ruling"`, `"blocked on #264 Q2"`, `"withheld behind a second gate"`, `"do not start without his
ruling on S1/S2/S4"` — and prose is not checkable. **So design the marker before writing the
check.** A check over a field nobody fills is the hollow check this repo has spent a day learning to
distrust: it would pass on every entry, including the ones it exists to catch.

Options to weigh (your call, with reasons): a `blocked-on: **human**` field in the metadata chain;
a `gate: <question title or id>` naming the entry; or reusing the existing `owner`/`blocked-on`
slot. Whatever you choose goes in **`file-formats.md` in the same commit as the check** — that is
this repo's standing rule, not a preference.

**Do not retrofit the marker onto all 137 open entries.** Pick the honest subset the evidence
supports (the ones below, plus any you can justify from their own words) and make the check's scope
explicit: an entry with no marker is *not* claimed to be unblocked, it is simply not making a claim.
Say in the report how many entries you marked and how many you deliberately left alone.

## Both directions, and the second one is where the live cost is now

`#420`'s census measured this by hand an hour ago:

1. **Blocked on him, no question.** Largely closed — filing `#419` and the `#264` ask fixed it. One
   ambiguity remains: **`#353`** forbids starting without his S1/S2/S4 ruling and **no question names
   `#353`**, though open `Q#264` covers it transitively. A reader on `#353` alone cannot tell. Decide
   whether transitive coverage counts, and make the check say which it means.
2. **He ruled and nobody processed it.** This is the expensive half. Four entries:
   **`#254`** (R1/R2/R3 answered 2026-07-27 23:03 and 23:38), **`#367`** (2b ruled 15:11),
   **`#371`** (Q2 ruled **05:43** — its body still said *"blocked on #263 Q2"* ten hours later, and
   it is a **P1 bug**), **`#50`**. The coordinator has since unblocked all four, so **their fixed
   forms are your regression corpus, and their pre-fix forms are your reds** — recover those from
   `git show` rather than inventing fixtures.

**`#371` teaches the sharpest lesson and your check must survive it:** Q2 was never its own
question. It rode *inside another entry*, so when he answered, nothing pointed back at `#371`. **A
ruling that arrives on a neighbouring question is invisible to the entry that needed it.** So a check
that only asks "does a question with this task's id exist?" would have passed `#371` while it sat
blocked. Key on the *decision*, or state explicitly that transitive/neighbouring rulings are out of
scope and why.

## Done means all of these

1. **The marker is specified in `file-formats.md`**, with its vocabulary and what absence means.
2. **`lint.py` enforces both directions.** Direction 1 (marked blocked-on-human, no open or
   answered-unfolded entry) is an **ERROR** — his words are *"there always has to be an answer in our
   data"*. Direction 2 (a ruling landed and the entry still claims to be waiting) is at least a
   **WARN** with the entries named; argue for ERROR if you can make it precise enough.
3. **Every count derived, never a literal.** `lint` already has this idiom — *"3 of 51 answered
   entries have no resolution date"*.
4. **Reds from real history, both directions.** Direction 1: an entry marked blocked-on-human with
   its question removed from `questions.md` ⇒ ERROR. Direction 2: restore `#371`'s **pre-fix body**
   from `git show 7c5fc82^:.dreamwork/tasks.md` ⇒ your check flags it. **That second red is the one
   that matters** — it is a real defect that really existed, not a synthetic one.
5. **A green red-run is a finding, not a relief.** If restoring `#371`'s old body does not trip the
   check, say so plainly — the check is wrong, and that is more valuable than a passing suite.
6. `python3 -m pytest test_lint.py -q -p no:randomly` passes, `python3 lint.py` is **clean on the
   live repo** (it is clean now — 1 warning — so any new ERROR you introduce is either a real finding
   you should report, or your check misfiring; distinguish them and say which).
7. **`just test`.** Do **not** pipe it — a pipeline returns the last command's status. Write to a
   file, read the file, quote the tail and the real exit code. **The suite is fully green as of
   16:05** (52 guards, 0 failures, 1009 pytest). There are no excused reds; any failure is yours.
8. Guard ports **39890-39899** may be held by another lane — check `ss -ltnp | grep 3989` first and
   say so if you waited.

## Files

Yours: `file-formats.md`, `lint.py`, `test_lint.py`. **Not yours:** `watch.py` (another lane holds
it), `.dreamwork/tasks.md` and `.dreamwork/questions.md` (the coordinator is their only writer — if
entries need markers added, **report the exact lines and let it apply them**, or add markers only if
you can do it without touching anything else in those files; say which you did).

`status_sync.py` is also not yours, but note its neighbour: `#402b` needs the **id vocabulary** in
`file-formats.md` too (plain id → int, sub-id → string, never a quoted plain id). If adding that row
while you are in the file is cheap and does not entangle your check, do it and say so; if it grows
your diff, leave it.

## Practical

- 2 threads. `git commit --only <paths> -m 'feat(#419): …'` — **never `git add -A`**; other agents
  commit here. A new file needs `git add <file>` first.
- **Push back with reasons if any of this is wrong.** Eight lanes today have refuted something their
  brief asserted and every one was right to.

## Report

Say: which marker you chose and why; how many entries you marked and how many you left alone; both
red-proofs with exact test names, including the `#371` history red; whether you decided transitive
coverage counts and what that means for `#353`; and the real `just test` exit code with how you got it.

---

## AMENDMENT, 2026-07-28 16:26 — your `#371` fixture is poisoned, and it is my fault

**Read this before you build direction 2.** If you have already built it against `#371`, re-check it
against what follows; if you have already reported, say in the inbox whether this changes your
verdict.

The brief above tells you that `#371` is the sharpest specimen of direction 2 — *"a ruling landed and
the entry still claims to be waiting"* — and to use `git show 7c5fc82^:.dreamwork/tasks.md` as the
red. **`7c5fc82` is my own defect, not the fix.** I unblocked `#371` because he answered its question
at 05:43, and that was wrong: his *"Q2 yes"* amended the **design**, while the **implementation** of
that answer is increment 20 = `E1 envelope` = **lane E**, which his same answer withheld behind a
second gate. `#371`'s pre-fix body saying *"blocked on #263 Q2"* was **imprecise but not false** — it
really was blocked, on a stricter gate than the one it named.

Retracted in the live ledger at `6ea8f6b`. So:

1. **`#371` is not a direction-2 red. It is a direction-2 FALSE POSITIVE, and a better test than the
   red was.** If your check flags the live `#371` (which now names a landed ruling *and* says it is
   blocked), your check is wrong in the way that costs most — it would have told the coordinator to do
   exactly what I did. **Use it as a must-NOT-flag case** and say in your report that it does not
   flag, and by what mechanism it avoids doing so.
2. **The distinction your check has to encode is "answered" vs "authorised".** A ruling landing on a
   decision an entry names does **not** imply the entry may proceed: the answer may amend a design
   whose implementation is separately gated, or grant a contract while withholding its build. The
   repo had already written this down once — `#294`'s note says *"the approval covers the CONTRACT,
   not `#263`'s implementation"* — and I made the identical error one question later.
3. **This is an argument for your marker naming the gate rather than the question.** A `gate:` field
   that points at *what is withheld* survives this; one that points at *which question was asked*
   reads a landed answer as a green light. Weigh it and say which you chose and why. If your design
   already handles it, say how — I would rather read that than a change.
4. Your remaining direction-2 reds — `#254`, `#367`, `#50` — are unaffected as far as I know, but **I
   have now been wrong about one of the four, so treat the other three as claims to check rather than
   fixtures to trust.** For each, say whether the ruling authorised the work or only amended a design.

**A green red-run is a finding, not a relief** applies to this amendment too: if you conclude I am
wrong about `#371` again, quote the lines and say so. Lanes here have refuted their briefs nine times
today and every one was right to.
