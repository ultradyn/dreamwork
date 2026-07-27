# Brief — lane B second batch: claims, cursor, two processes, contract (#263, increments 7–10)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: the second half of lane B — leases, the cursor, and the two
  checks that decide whether any of the first half is actually true across
  processes.

## What already landed — build on it, do not revisit it

The first batch is **done and green**, all in `user_events/sqlite.py`:

| inc | sha | what |
|---|---|---|
| `B1` | `6a865e4` | `open_journal` — WAL, `synchronous=FULL`, `busy_timeout`, schema |
| `B2` | `9bea281` | `receive()` — insert / replay / conflict by UUID+digest |
| `B3` | `2e1e987` | event ordinal + hash chain + `verify_chain` |
| `B4` | `37d0066` | transitions + `claim` refuses a rejected receipt |

**Read `user_events/sqlite.py` and `test_user_events_sqlite.py` before you start.**
You now own both. 8/8 tests are green; keep them green.

**One thing the previous batch learned that applies directly to you.** The plan's
`B1` red line was **wrong**, and the lane found it by obeying it: it said "delete
the `PRAGMA synchronous=FULL` execute and the assertion fails", but SQLite 3.53's
compile-time default is *already* FULL, so the deletion changed nothing and the
prescribed red came back **green**. The fix was to pin `NORMAL` then `FULL` so the
deletion genuinely leaves `1`.

**Carry the generalisation:** a red that depends on a value differing from the
platform default is only as discriminating as that default, and neither the plan
nor I can see the default. **A written red line is a hypothesis about the platform,
so it earns the same scepticism as the code.** Your increment 7 has exactly this
shape — it depends on real elapsed time — so treat it accordingly.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have **lane
B, increments 7, 8, 9 and 10 only** (`B5 claims`, `B6 cursor`, `B7 twoproc`,
`B8 contract`). Lanes E (the HTTP cutover) and H (the version gate) are
**withheld**. **Do not touch `watch.py`** — another lane holds it — and do not
change any response or wire your module into anything.

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane B — journal"**, increments 7–10. Each row
names the functions, the test, the **production line whose deletion must make it
fail**, and what the test may not fake. That is the spec. If you think a row is
wrong, **say so** — the last batch found one, and the plan has an amendment
section.

## The two increments that carry the real risk

**Increment 9 (`B7 twoproc`) is the one that decides whether increments 4–8 are
true.** The plan is blunt about why, and this is the most important paragraph in
this brief:

> **Threads are not processes.** The existing code's only mutual exclusion is a
> `threading.Lock` (`watch.py:8026`), and a **threaded version of this test passes
> with no database constraint at all** — which is precisely #262's bug reproduced
> as a green test.

So: `multiprocessing` children in **separate interpreters**, with a barrier. If you
write this with threads it will pass, it will look thorough, and it will be
evidence of nothing. State in your report which you used and how you know
(e.g. distinct `os.getpid()` values asserted at runtime).

**Increment 7 (`B5 claims`) must not patch the clock.** The design's law is
"backend/server time, never client clocks", so a monkeypatched `time.time` proves
the *opposite* of what the test is named for. Use a real short lease and a real
sleep, and **assert at runtime that the observed elapsed time exceeded the lease** —
a sleep that returned early on a loaded box would otherwise make the test pass
vacuously. The box is at load ~50, so this is a live possibility, not a formality.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `user_events/sqlite.py`,
   `test_user_events_sqlite.py`. `git diff --stat watch.py user_events/digest.py
   user_events/domain_files.py` is **empty** — the last two belong to other lanes,
   one of them **active right now**.
2. **`python3 -m pytest test_user_events_sqlite.py -q -p no:randomly` exits 0**,
   with the previous 8 tests still green plus at least:
   `test_expired_lease_is_reclaimable_and_the_stale_claimant_cannot_finish`,
   `test_broken_chain_forces_rebuild_not_a_silent_advance`,
   `test_two_processes_one_uuid_make_one_receipt`,
   `test_every_contract_test_runs_under_every_registered_backend`.
3. **One discriminating red per increment**, each with the exact failing test name
   and confirmation neighbours stayed green:
   - `B5`: delete the `lease_until > <backend now>` predicate in the claim
     `UPDATE`.
   - `B6`: delete the `expected == stored_chain_hash` comparison in
     `advance_cursor`.
   - `B7`: **remove the `UNIQUE(client_action_id)` constraint from the schema.**
     This is the red that matters most in the whole lane — if the two-process test
     still passes without the constraint, your test is threaded or otherwise not
     concurrent, and **you must report that** rather than move on.
   - `B8`: remove a backend from the registry ⇒ the meta-test fails on the
     **product**, not on a literal.
   Separate injections, others restored, from a `cp` snapshot — **never**
   `git checkout -- `.
4. **`B6` counts the ordinals the rebuild read, asserted against a
   runtime-derived total** — never a literal. A literal tuned to today's fixture is
   a check with an invisible expiry date.
5. **`B8`'s meta-test holds no hand-copied list of the contract tests.** Derive
   from the registry and the collected node ids at runtime (`lessons.md:991` — a
   copied list drifts, then agrees with itself while covering less).
6. **`just test` exits 0 for your file**, and you record the tree's pre-existing
   reds separately. **Expect one:** a `test_watch.py` failure caused by another
   lane holding a dirty `watch.py`. That is not yours; note it and do not chase it.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`.

## The rules that matter most here

**A green red-run is a finding, never a relief.** The previous batch hit exactly
this and handled it correctly; you may too. If an injection leaves the suite green,
the check is wrong — report it, and do **not** conclude the code was fine.

**Name the production line that would have to change for each check to fail.**
Required per test in your report. If you cannot name one, there isn't one.

## Files

**Yours:** `user_events/sqlite.py`, `test_user_events_sqlite.py`.

**Read, do not edit — live owners:** `user_events/domain_files.py` and
`test_user_events_domain_files.py` (**lane C, active**), `user_events/digest.py`,
`ud-dw-user-events` and `test_user_events_cli.py` (**lane F, active**), `watch.py`
(**another lane, active** — read `8026` to see the `threading.Lock` the plan is
warning you about, then leave it alone). Also read: the two plan documents,
`.dreamwork/lessons.md`, `file-formats.md`, `test_watch.py` (subprocess idioms —
reuse rather than authoring a second), `justfile`.

**Never touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`dev/capture/*`, `bin/ud-dw-generate`.

**You need no server and no port.** Do not run `just guards` — two lanes are using
that range.

## Operational constraints

- Limit builds/tests to **2 threads**. **Four other lanes are live on this box and
  load has been 40–50 on 16 cores.** That matters for you specifically: your
  increment 7 depends on real elapsed time and your increment 9 spawns processes,
  so give every wait a **generous bounded timeout** and never an unbounded one.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after
  `git add` commits the whole index, not the paths you named, and will bury a
  concurrent lane's staged work — that happened in this tree today. **Do not push.**
- Commit **each increment separately**.
- Cap yourself at roughly **40 minutes**. Four will likely not fit. **Priority order
  if you must choose: 9 (`B7 twoproc`) first, then 7, then 8, then 10** — because
  `B7` is the increment that tells us whether the whole first batch is true across
  processes, and it is the one whose absence would let #262's original bug survive
  as a green suite. Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because four other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the red per
increment verbatim — what you injected, the exact test name that failed, and that
neighbours stayed green**; **for `B7`, whether removing `UNIQUE(client_action_id)`
actually broke it, and how you know your children were separate processes**; for
`B5`, the observed elapsed time versus the lease; the production line named per
test; which increments you did not reach; anything in the plan you believe is
wrong; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
