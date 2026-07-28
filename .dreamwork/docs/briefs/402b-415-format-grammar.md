# Brief — #402b + #415: two format grammars that are narrower than reality

Repo: `ud-dreamwork`. Worktree: **`.worktrees/fmt`**, branch **`wt/fmt`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Two tasks, one lane, because both are the same shape in the same two files: a documented grammar that
is narrower than what the loop legitimately produces, each with a **live symptom from today**.

## `#402b` — the id vocabulary, and I hit it myself two hours ago

`status_sync.py` derives `current_task_ids` from each dreamer's `task` field. I recorded three lanes
with string task ids and `lint.py` errored:

> `ERROR status.json current_task_ids has non-integer member(s) '218', '263', '419' — ids are
> integers; a quoted id matches no task row, silently`

**lint was right and so was `status_sync`** — they simply disagree about the vocabulary.
`status_sync._normalise_live` deliberately keeps the string form, with a documented reason
(`#402a`): a live set can hold `396` (int) and `"401"` / `"392a"` (str) at once, and `sorted()` raises
`TypeError` on that mix, so it sorts by `str` and *"keeps the sub-id rather than dropping or coercing
it"*. Meanwhile `_base_id` exists precisely because `current_task_ids` **can** legitimately carry a
sub-id like `392a`.

**So the contract is real and nowhere written down.** The rule the code already implies:

- a **plain** id is an **integer** — `263`, never `"263"`;
- a **sub-id** is a **string** — `"392a"`, `"402b"`;
- a **quoted plain id is always wrong** and is what lint should catch.

**Your job is to write that down in `file-formats.md` and make `lint.py` enforce exactly it** — today
lint rejects every string, which would reject a legitimate `"392a"`. **Check that claim before you
build on it**: construct a `status.json` whose `current_task_ids` is `[263, "392a"]` and see what lint
does now. If it accepts that already, say so — the bug is narrower than I have described and you
should report the difference rather than widening a check that is already right.

I worked around it by writing ints in `status.json`. **That workaround is not the fix and should not be
mistaken for one** — the next author to write `"392a"` hits the same wall from the other side.

## `#415` — a task landing in two commits is the ordinary case

`file-formats.md:246` specifies the hand-off grammar as `· landed \`<sha>\` ·` — **singular**. `#411`
landed as `54c68e8` (the fix) plus `25a3fe4` (the lint count), the lane honestly wrote both, and lint
reported *"a hand-off entry the grammar does not recognise"*. **The lane was right and the format was
wrong.** It was normalised by hand to the final sha with the other in prose, which loses the
structure: a tool can find the first commit no longer, only a human reading the sentence.

Widen the grammar to accept one **or more** shas, and make `lint` read all of them. Decide and state:
are they ordered (first→last, or landing→last)? Is there a cap? What does a **zero**-sha hand-off mean
— is that still legal for a fold-only entry? **The entry notes this is `#401` one field over**, which
widened the hand-off *id* vocabulary; read what `#401` did and follow its shape rather than inventing
a second style.

## Red-first, and this repo's reds have a documented habit of passing

For each of the two:

1. **Write the test, watch it fail, then fix.** Name in the report the **exact** production line whose
   removal makes each test fail. If you cannot name one, there isn't one.
2. **A green red-run is a finding, never a relief.** If reinstating the narrow grammar leaves your test
   green, say so plainly — the test is wrong, and that is the more valuable result. Two checks in this
   repo were structurally incapable of failing about the one decision they were named for.
3. **The negative direction matters more than usual here**, because both of these are *widenings* and a
   widening's easy failure is accepting everything. So for each: **a test that the still-invalid form is
   still rejected.** A quoted plain id `"263"` must remain an ERROR; whatever hand-off shape stays
   malformed must stay reported. **A widening with no negative test has removed a check rather than
   improved it** — this is the single most likely way to get this task wrong.
4. **Assert your fixtures' preconditions.** If a test's meaning needs an int and a sub-id to coexist,
   derive and assert that both types are present rather than trusting the literal you typed.
5. **Real history for `#415`**: recover `#411`'s two-sha hand-off line from `git log`/`git show` rather
   than inventing a fixture. A red from a defect that really existed is worth more than a synthetic one.

## Done means all of these

1. **`file-formats.md` documents both grammars** — the id vocabulary (plain → int, sub-id → string,
   quoted plain id never) and the multi-sha hand-off — **in the same commit as the check that enforces
   it.** That is this repo's standing rule, not a preference.
2. **`lint.py` enforces exactly the documented grammar, no wider and no narrower**, with the counts
   **derived at runtime** and never a literal — `lint` already has that idiom (*"3 of 51 answered
   entries have no resolution date"*).
3. **Both positive and negative tests for each task**, per point 3 above.
4. **`lint.py` is clean on the live repo** at the end — it is clean now apart from one known `#411`
   warning, so a new ERROR is either a real finding you should report or your check misfiring.
   Distinguish them and say which.
5. **Two commits, one per task** (`fix(#402b): …`, `feat(#415): …`), because they are separately
   verifiable and the ledger cites them separately.
6. `python3 -m pytest test_lint.py test_status_sync.py -q -p no:randomly` passes. **Note `test_lint.py`
   grew 214 lines an hour ago** (`#419`'s human-blocker check, 277 tests in that file now) — if any of
   those fail, that is a real interaction and worth its own paragraph in your report.
7. **Do NOT run `just test`.** Guards bind 39890-39899, three other lanes are live, and one holds
   39899; the recipe hard-aborts on a held port. The coordinator runs the full suite at merge (`#424`).
   Do not bind any port in 39880-39899 and do not kill a process holding one. Say you skipped it.

## Files

Yours: `file-formats.md`, `lint.py`, `test_lint.py`, `status_sync.py`, `test_status_sync.py`.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md` (a lane holds those),
`user_events/*` (another), `.dreamwork/review/*` (a third), and `.dreamwork/tasks.md` /
`.dreamwork/questions.md` / `.dreamwork/status.json` — the coordinator is their only writer. **If a live
`status.json` value violates the grammar you document, report the exact value; do not edit the file.**

## Practical

- 2 threads. `git commit --only <paths> -m '…'` — **`--only`, never `git add -A`**: three other agents
  commit in this tree and a bare `git commit` sweeps their staged work into your commit under your
  message.
- **Push back with reasons if any of this is wrong.** Thirteen lanes today have refuted something their
  brief asserted and every one was right to — most recently `#419`, which refused half its brief and
  was correct, and the lane that found `lane C 3/3` meant `3 of 5`. **If `lint` already accepts
  `[263, "392a"]`, or if you think the hand-off should stay single-sha, say so with evidence before
  building.**

## Report

Say: what `lint` does today with `current_task_ids = [263, "392a"]` (the measurement, not your reading
of the code); the exact production line whose removal fails each new test; your **negative** tests by
name and what each still rejects; the multi-sha ordering and cap decisions with reasons; whether
`#419`'s new tests interacted with yours; and confirmation you skipped `just test` and bound no guard
port.
