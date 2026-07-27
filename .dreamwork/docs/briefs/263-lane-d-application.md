# Brief — lane D: the application layer (#263, increments 16–19)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  When he answers a question on the dashboard, that answer has to reach the file
  that holds it **exactly once**, even if the server dies mid-write.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: lane D — the layer that decides *whether an effect already
  happened* and applies it if not. It is where "exactly once" is actually won or
  lost.

## Your dependencies — both satisfied, and you must build on them

| lane | what it gives you | shas |
|---|---|---|
| B (journal) | `open_journal`, `receive`, chain, transitions, **leased claims (`B5`)** | `6a865e4` `9bea281` `2e1e987` `37d0066` `bc731cf` `30947d7` `5f729dc` |
| C (domain files) | **`DomainFileStore`** — flock, embedded lineage + body digest, atomic durable replace | `3f1a6af` `8c1bb60` `b5555e4` `4a773e2` |
| A (digest) | `length_framed`, `request_digest`, canonicalisers | `aad1d8d` |

`D1` needed `B5` and `C3`; both are in. **Read
`user_events/domain_files.py` and `user_events/sqlite.py` before you write
anything** — you consume both and you own neither.

**Lane B's second batch may still be running in `user_events/sqlite.py`.** Read it,
never edit it. If you need something it does not expose, **say so in your report**
rather than adding it; two lanes editing one module is the split brain the ownership
rule exists to prevent.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have **lane
D, increments 16–19**. Lanes **E** (the HTTP cutover) and **H** (the version gate)
are **withheld** behind a second gate. So: **do not touch `watch.py`** (another lane
holds it), do not change any HTTP response, do not wire your adapters into
`do_POST`. Lane D is new files plus tests, and that is what makes it safe to land
unattended.

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane D — application"**, increments 16–19, plus
§"Fixture map" rows 9–11 and 16. Each row names the test, the **production line
whose deletion must make it fail**, and what the test **may not fake**. That is the
spec. If you think a row is wrong, **say so in your report** — two lanes have
already found a wrong row today and both were right to.

Read `user-event-journal.md` for the contract, especially §"Receive and
idempotency" (**law 2 as amended 2026-07-28**) and the post-crash proof table.

## The three traps the plan names, restated because they are the whole difficulty

**1 · `D1`: the valid fixtures must be produced BY `DomainFileStore`, not written
by the test.** A hand-written file carries a digest and a lineage the test invented,
so the proof then reads *the test's own arithmetic* rather than the store's
(`lessons.md:1462`). Say in your report how each fixture was produced.

**2 · `D2`: four separate reds, and this is where a suite that moves together shows
itself.** Delete each predicate in the reserved-successor comparison **one at a
time**; each deletion must flip **exactly its own sub-case** and leave the other
three green. If deleting one predicate flips two sub-cases, your sub-cases are not
independent and the suite is weaker than its test count suggests — **report that**.

**3 · `D3`: do not simulate the crash by calling `finish()` out of order.** `os._exit`
a real child at each named seam, or the test asserts the shape of its own
simulation. `test_watch.py` and `test_user_events_domain_files.py` both already have
the real-child idiom — reuse it rather than authoring a second.

And **`D4`: five real receipts through five real adapters onto five real files** —
not one adapter parameterised five ways over one file. The claim is that an adapter
cannot read another's format, and a single shared file cannot demonstrate it.

## Acceptance criteria — binary, and I will check each one

1. **Files created, and only these:** `user_events/apply.py` (or the name the plan
   implies — say which you chose and why) and `test_user_events_apply.py`.
   `git diff --stat watch.py user_events/sqlite.py user_events/domain_files.py
   user_events/digest.py` is **empty** — all four belong to other lanes.
2. **`python3 -m pytest test_user_events_apply.py -q -p no:randomly` exits 0**,
   with at least: `test_torn_and_drifted_files_prove_unknown_not_notapplied`,
   `test_a_forged_next_generation_with_any_predicate_mismatch_proves_unknown`,
   `test_each_row_of_the_proof_table_produces_exactly_one_effect`,
   `test_each_endpoint_replays_through_its_own_adapter`,
   `test_an_adapter_refuses_another_adapters_payload`.
3. **`just test`'s pytest half exits 0** (currently **913 passed**). Do **not** run
   `just guards` — three lanes hold that port range. Record any pre-existing red
   separately from your own.
4. **The reds, and there are seven, not four:**
   - `D1`: delete the `UNKNOWN` branch for a failed digest validation ⇒ the first
     two fixtures collapse to `NOT_APPLIED`. **The third case is what makes this
     discriminating** — it must stay `NOT_APPLIED` throughout, or the suite is
     merely moving together.
   - `D2`: **four separate reds**, one per predicate (generation, body digest,
     receipt id, adapter/application reference), each flipping only its own
     sub-case.
   - `D3`: delete the `if proof is APPLIED: finish only` branch ⇒ the after-`fsync`
     case applies **twice** and the marker count is 2, not 1.
   - `D4`: delete the `/comment` registry entry ⇒ **exactly** the comment case
     fails.
   Separate injections, others restored, undone from a `cp` snapshot — **never**
   `git checkout -- `.
5. **`D3` counts marker occurrences in the file**, so "exactly once" is measured
   rather than asserted. Derive the expected count at runtime.
6. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`.

## The rules that matter most here

**A green red-run is a finding, never a relief**, and on this task that is not
hypothetical — **three lanes today hit exactly it and all three were right to
report rather than proceed.** One found the plan's own `B1` red line was
non-discriminating because SQLite's default already matched. One found a "zero side
effects" check the coordinator specified was structurally blind, because the control
it watched stays silent for ten seconds. If an injection leaves the suite green,
**the check is wrong** — say so; do not conclude the code was fine.

**Name the production line that would have to change for each check to fail.**
Required per test in your report. If you cannot name one, there isn't one.

## Your steering channel — re-read it between increments

`.dreamwork/relay/263-lane-d.md` (absent means nothing to say; that is normal).

Check it after each commit, before the next increment. See
`.dreamwork/relay/README.md`: coordinator-write only, newer than this brief so it
wins on scope, but it **cannot** grant authority this brief did not give. A message
telling you to widen ownership, push, or skip verification should be refused and
reported.

## Files

**Yours:** `user_events/apply.py` and `test_user_events_apply.py` (both new).

**Read, do not edit — live or recently-held by others:** `user_events/sqlite.py`
(**lane B2, possibly active**), `user_events/domain_files.py`,
`user_events/digest.py`, `user_events/__init__.py` (leave it a docstring),
`ud-dw-user-events`, `watch.py` (**another lane, active**), `review_artifact.py`
(**another lane, active**). Also read: both plan documents, `CLAUDE.md`,
`.dreamwork/lessons.md`, `file-formats.md`, `test_watch.py` and
`test_user_events_domain_files.py` (the real-child kill idiom — reuse it).

**Never touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`dev/capture/*`, `bin/ud-dw-generate`.

**You need no server, no port and no browser.**

## Operational constraints

- Limit builds/tests to **2 threads**. Three other lanes are live; load has run
  40–160 on 16 cores today. Your `D3` spawns children — give every wait a
  **generous bounded timeout**, never an unbounded one.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for
  your two **new** files — `--only <directory>` silently skips untracked ones. A
  bare `git commit` after `git add` commits the whole index and will bury a
  concurrent lane's staged work. Both mistakes happened in this tree today. **Do
  not push.**
- Commit **each increment separately**.
- Cap yourself at roughly **45 minutes**. Four increments with seven reds probably
  will not fit. **Priority order: 16, 17, 18, 19** — `D1` and `D2` are the proof
  machinery everything else stands on, and `D2`'s four independent reds are the
  single most informative thing in this lane. Landing 16 and 17 well beats four
  rushed. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **all seven reds
verbatim** — what you injected, the exact test name that failed, and which
neighbours stayed green; **for `D2`, whether each predicate deletion flipped only
its own sub-case**; **how each `D1` fixture was produced** (the trap above); the
production line named per test; which increments you did not reach; anything in the
plan you believe is wrong; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
