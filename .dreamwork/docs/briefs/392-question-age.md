# Brief — #392(b): the humanized question age is measured from midnight, so it is wrong by up to a day

Repo: `ud-dreamwork`. Worktree: **`.worktrees/qage`**, branch **`wt/qage`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## The defect, measured on the live page

Read `#392` in `.dreamwork/tasks.md`. `#385` shipped the *format* correctly; the **input** is date-precision.
A `questions.md` headline carries `P2 · 2026-07-28 — title` and **there is no time in the data**, so `data-ct`
resolves to **midnight local** of that date.

Measured at 08:18 on the deployed dashboard: a question that **landed at 07:54** (`git log -S` on its headline,
exact) rendered **`08h 17m ago`**. It was 24 minutes old. **The error is bounded by 24h and is largest for the
newest entries** — precisely where "how long has this been waiting" carries the most meaning, since a fresh ask
looks like a neglected one.

**Note `#392a` has already landed**; this is the remaining half. Read the entry to see which part that was, and
say in your report what you found already done.

## The real question: where does the time come from

There is no timestamp in the headline, so **the fix is a source of truth, not a format change.** Options, and
**argue rather than assume**:

- **Git.** `git log -S<headline> --format=%aI` gives the commit that introduced the entry — exact, already how
  the defect was measured, and correct for entries written by any hand. Cost: a subprocess per entry, and
  `questions.md` is re-read often. **Measure that cost before rejecting or accepting it** — say how long it
  takes across the real file, and consider whether one `git log` over the file's history answers for all
  entries at once rather than one call each.
- **A time in the headline.** Exact and cheap to read, but it is a **format change** to a file the human
  writes by hand, and every existing entry lacks it — so it needs a fallback anyway and does not fix history.
- **File mtime.** Cheap and wrong: one write re-stamps every entry.
- **Something you think of.** Fine, argue it.

**Whatever you choose, an unknown time must render as unknown, not as midnight.** *"today"* or *"2026-07-28"*
is honest; `08h 17m ago` is a fabrication, and the dashboard's whole thesis is liveness — `status.json`'s
timestamps come from the clock rather than memory for exactly this reason.

## Done means all of these

1. A fresh entry's age is right to the minute, or is honestly imprecise. No fabricated precision.
2. **Red-first, and name the production line.** A test that fails on the midnight-derived value and passes on
   the corrected one. **A green red-run is a finding, never a relief** — if reinstating midnight keeps it green,
   the test is not reaching the code and that is the more valuable result.
3. **Assert the precondition your test depends on**, derived at runtime: if it needs an entry whose true time
   differs from its date's midnight by a known amount, **derive both and assert the gap** — a literal tuned to
   today's file is a check with an invisible expiry. This has bitten repeatedly here.
4. **Cost stated**: what your fix adds per `collect()` / per request, measured, not estimated.
5. `file-formats.md` states anything you add to a parsed file, in the same commit. **Never change the format
   ahead of the parser.**
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1091 at dispatch). **Do not run the
   full `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop — no `just deploy`.
7. If anything on the page changes state or appears, **`transitions.md` binds with no size floor**; most likely
   you introduce no gesture, so say so explicitly.

## Files

Yours: `watch.py`, `test_watch.py`, `file-formats.md`.

**Not yours:** `dev/capture/*`, `justfile`, `lint.py`, `dev/ledger.py`, `status_sync.py`,
`review_artifact.py`, `review-artifact.template.html`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` —
report exact lines. **Do not edit the live `questions.md` to add timestamps**; test against fixtures.

## Practical

2 threads. `git commit --only <paths>` — **never `git add -A`**: other agents commit in this tree.
**Commit before you finish** — two lanes today exited with correct work uncommitted and had to be recovered.

## Report

Which model you are; what `#392a` already did; the source of truth you chose and the argument against the
others; the measured cost; the exact production line whose reversion reds your test; the precondition you
derived; what an unknown time renders as; and confirmation you did not deploy, run the full `just test`, or
touch :35110.
