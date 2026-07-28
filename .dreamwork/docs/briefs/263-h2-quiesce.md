# Brief — #263 H2: the cutover lease, the drain, and the watermark

Repo: `ud-dreamwork`. Worktree: **`.worktrees/quiesce`**, branch **`wt/quiesce`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: user_events/sqlite.py, user_events/journal.py, test_user_events_sqlite.py, test_user_events_http.py, .dreamwork/docs/plans/user-event-journal-implementation.md

(If a path in that list does not exist, it is not yours to invent — report it. Take the union of what exists.)

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[quiesce]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/quiesce-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the
lines you want added. **Commit each increment as it lands.**

## What this is, and why it is the last gate

Read `#263` in `.dreamwork/tasks.md`, then **increment 35 (`H2 quiesce`)** in
`.dreamwork/docs/plans/user-event-journal-implementation.md` (§"Lane H — version gate"), and the paragraph
above the increment table that says *"`H2` is the only increment that writes an irreversible watermark"*.

`H1` landed at `7dc8763` and found the gap was not where the task assumed: `schema_version` already refused to
open a journal on mismatch, but `protocol_version` on the envelope was **digest-only** and accepted any string,
so an older reader could never have refused a newer record. Expect the same shape here — **measure what exists
before building**, because the plan describes a design and the code may already hold half of it.

`#294`'s ledger cutover is gated on this increment plus `#352`. That is the whole reason it is worth doing now.

## The increment, in the plan's words

> Cutover lease, drain, watermark; a request spanning the cutover completes under the drained generation or is
> retried under the new one.
> *Test:* two server instances over one temp target, a request held at a named seam across the cutover; assert
> exactly one receipt and no legacy direct write.
> *Red line:* the drain wait. Deleting it must produce either two receipts or a legacy write.

**The three parts are not equally hard and the difficulty is in the middle one.** A lease is a file and a CAS;
a watermark is a write. The **drain** is the part where a request already in flight has to be allowed to finish
under the generation it started in, and it is the part whose absence the test must be able to see. Do not let
the lease and the watermark consume the time.

## Hard constraint, and it is the human's, not mine

**This runs against TEMP TARGETS ONLY.** The plan states it: *"Nothing in this increment may be executed
against a live target — that is migration, and migration is not authorised."* The watermark is
**irreversible**. So:

- Every test builds its own `tempfile.mkdtemp()` target. No test, no probe, no scratch script and no
  exploratory one-liner touches `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/`.
- If you find yourself wanting to run the cutover against the real tree "just to see", that is the exact thing
  this paragraph exists to stop. Report the question instead.

## Decisions that are yours, each needing an argument

1. **What the generation IS.** A counter in the store, a lease-file token, a directory name — say what you
   chose and what makes a request's generation *unforgeable* from inside a request that started earlier.
2. **What a drained request does when the cutover wins the race.** The plan allows two outcomes ("completes
   under the drained generation **or** is retried under the new one"). Pick one, and say why the other is
   worse *here* — they have different failure modes under `#263`'s standing promise that a `202` means a
   durable receipt.
3. **Whether the lease can be stolen, and after how long.** A lease nobody can break wedges the target the
   first time a holder dies; a lease anyone can break is not a lease. `#263`'s reclaimer (increment 7, the
   "dual reclaimer and stale claimant ⇒ one CAS winner" fixture) is prior art in this repo — reuse its
   mechanism rather than authoring a second one, or say why it does not fit.

## Verification

- **Two real processes, not two threads** — increment 6's fixture in this plan says
  *"processes, not threads"* for the concurrency case and the same reasoning applies: a threaded fake shares
  the interpreter's view of the filesystem and cannot exhibit the interleaving this increment is about.
- **Red-proof on the production line, and the plan names it for you: the drain wait.** Delete it and the test
  must produce **two receipts or a legacy write**. **A green red-run is a finding, never a relief** — and if a
  red comes back green, **suspect your injection before the test**: confirm you edited the line the check
  names. That cost the coordinator a near-miss twice tonight, once because a fixture built the filtered list
  itself instead of calling the function that decides it.
- **Assert the precondition at runtime.** A test named "exactly one receipt" is vacuous if the request never
  reached the seam: assert the request was genuinely **held** at the seam and that the cutover genuinely
  **happened** (generation before ≠ generation after, derived, not a literal) before asserting the count.
- **`202` does not mean the write landed** (`#263` E5). `_reject(reason_code, detail)` responds **202** with
  `rejected` in the body, and `REJECTION_REASONS` is a closed set. A test that asserts a status alone passes on
  a rejected write — assert the **verdict**.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly test_user_events_sqlite.py
  test_user_events_http.py` passing, and do not regress the other suites. **Do not run the full `just test`** —
  the coordinator has one running in the main checkout and it holds **39899**.
- Bind nothing in 39880–39899; kill what you start by exact pid; `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110**, the heartbeat, the monitors or the loop.
  Never `pkill -f`.
- Any shape a tool parses goes in **`file-formats.md`** — that file is **not** yours; report the paragraph. The
  lease file and the watermark are both almost certainly such shapes.
- Trailer: `Feature:`, plus `Migration:` if an existing install would have to do anything.

## Files

**Yours:** those in `Lane-owns:` above.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md`, `dev/capture/burndown.mjs` (a lane holds all
four), `justfile` (guard registration is centralised at merge), `lint.py`, `test_lint.py`, `file-formats.md`,
`dev/lane_guard.py`, `ledger_store.py`, `review_artifact.py`, `dreamhub.py`, every `dev/capture/*.mjs`,
`bin/ud-dw-generate` (**never** touch it), `SKILL.md`, `DREAMWORK.md`, and everything under `.dreamwork/`
except the one plan.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**.
- **Work only inside `.worktrees/quiesce`.** Verify cwd and branch before every write.
- ~35 minutes. **Commit before you finish**, and land the drain even if the lease is still coarse — the drain
  is the increment's meaning and the other two parts are plumbing around it.
- **Push back with reasons.** If measurement says the drain cannot be observed without a seam that only exists
  for the test, say so and name the seam: a test-only seam is acceptable here if it is honest about being one,
  and a lie about it is not.

## Report

Say: what already existed before you built (the `H1` lesson — measure first); what a generation is and why it
is unforgeable from an older request; which of the two drained-request outcomes you chose and why the other is
worse here; the lease's steal rule and whether you reused increment 7's mechanism; the exact red you produced
by deleting the drain wait, **which of the two failure modes appeared**, and confirmation the injection reached
the code; the runtime-derived preconditions including the held-at-seam and generation-changed assertions; the
`file-formats.md` paragraphs you want for the lease and the watermark; and confirmation that **nothing ran
against a live target**, that you worked only in `.worktrees/quiesce` (state cwd and branch), edited no
`justfile`, left nothing listening, never touched :35110, and did not run the full `just test`.
