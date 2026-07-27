# Brief — lane B: the journal store (#263, increments 3–6)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  He types answers, asks and commands into the dashboard; today they survive only
  in a best-effort append that cannot tell a complete body from a truncated one.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: lane B, the journal itself — the durable store that decides
  whether a request was received, exactly once. It is the centre of the design;
  lanes D and F both consume it.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have
**lane B, increments 3, 4, 5 and 6 only** (`B1 database`, `B2 receive`,
`B3 chain`, `B4 states`). Increments 7–10 (`B5`–`B8`) are lane B too but are
**not in this batch** — do not start them.

Lanes E (the HTTP cutover) and H (the version gate) are **withheld** behind a
second gate. **Do not touch `watch.py`**, do not change any response, do not wire
your module into anything. Lane B is new files only, and that is what makes it
safe to land unattended.

## Your one dependency, and what to do about it

**`B2` needs `A2`** — `canonical_media_type()`, `canonical_route()` and
`canonical_method()` in `user_events/digest.py`, which **lane A owns and is
building right now**. `A1` (`length_framed` + `request_digest`) is already
committed at `aad1d8d`.

So: **start with `B1`, which has no dependency at all.** By the time it is
committed, `A2` will almost certainly be in. Then:

- `git log --oneline -- user_events/digest.py` and check for an `A2` commit;
- if `canonical_media_type` exists, **import it and use it**;
- if it does not, **do `B3` and `B4` first** — neither needs the digest — and
  report `B2` as not reached. **Do not write your own canonicalisers.** Two
  implementations of one canonical form is the exact bug the digest exists to
  prevent, and it would be invisible until two servers disagreed.

**`user_events/digest.py` is not yours. Read it; never edit it.**

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane B — journal"**, increments 3–6. Each row
names the functions, the test, what it asserts, **the production line whose
deletion must make it fail**, and what the test **may not fake**. That is the
spec. Follow it rather than inventing a decomposition; if you believe a row is
wrong, **say so in your report** — the plan has an amendment section for that.

Read also `user-event-journal.md` §"Receive and idempotency" for the contract
`B2` implements, including **law 2 as amended 2026-07-28**, and the two rules
stated once above the per-increment list (the `ImportError`-red rule, and
assert-the-precondition-at-runtime).

## Acceptance criteria — binary, and I will check each one

1. **Files created, and only these:** `user_events/sqlite.py`,
   `test_user_events_sqlite.py`. `git diff --stat watch.py user_events/digest.py`
   is **empty** — both are other people's files. `git status --porcelain` shows no
   other path modified.
2. **`python3 -m pytest test_user_events_sqlite.py -q -p no:randomly` exits 0**,
   containing at least these named tests for the increments you reached:
   `test_pragmas_are_what_the_durability_boundary_claims`,
   `test_same_uuid_same_digest_replays_and_does_not_insert`,
   `test_same_uuid_different_bytes_conflicts_and_preserves_the_original`,
   `test_rejected_receipt_can_never_be_claimed`,
   `test_stale_revision_transition_is_refused`, plus `B3`'s three chain
   properties under whatever names you give them.
3. **`just test` still exits 0.** Record what was already red *before* you
   started, so your damage is separable from the tree's.
4. **One discriminating red per increment, each with the exact failing test name
   and confirmation its neighbours stayed green.** The plan names the line for
   each; these are the four:
   - `B1`: delete the `PRAGMA synchronous=FULL` execute ⇒ the pragma test fails.
   - `B2`: delete the `SELECT request_digest … WHERE client_action_id = ?`
     comparison before insert ⇒ the replay test fails. **Note the trap the plan
     names**: without that comparison the unique constraint raises
     `IntegrityError`, which is a *different* failure — so your test must assert
     the result **kind**, not only the row count, or it will "fail" for the wrong
     reason and tell you nothing.
   - `B3`: delete the `prev_hash` term from the hash input ⇒ property (c) must
     fail **by naming the ordinal**. The plan is explicit that (c) still passes on
     the row's own hash without the chain linking, so the assertion has to be on
     the verifier naming the ordinal, and (b)'s mutation must be on an event
     **earlier than the head**.
   - `B4`: delete the `AND state = 'validated'` predicate in the claim `UPDATE` ⇒
     `test_rejected_receipt_can_never_be_claimed` fails.
   Separate injections, others restored, undone from a snapshot
   (`cp user_events/sqlite.py $S/bak`), **never** `git checkout -- `.
5. **`B1`'s pragmas are read from a second, fresh connection.** `synchronous` is
   per-connection; asserting on the setter's own handle can pass while the pragma
   was applied to the wrong scope. State in your report which connection you read
   from.
6. **`B2`'s test contains no raw `INSERT`.** Both calls go through `receive()`.
   A test that hand-builds the state is asserting a property of its own fixture —
   the #320 trap in `.dreamwork/lessons.md`. Say you grepped your test for
   `INSERT` and what you found.
7. **`B3`'s test holds no copy of the `H_i` formula and asserts no expected
   digest literal.** Assert *relations between outputs* — same sequence twice
   gives the same head; one changed byte changes the head; a mutated low ordinal
   makes the verifier name it. A check and the thing it checks cannot hold
   separate copies of one rule (`lessons.md:874`); when they do, they agree with
   each other and both are wrong.
8. **`B4`'s revisions are read back from the store between calls**, not tracked in
   the test. A test that remembers the revision it expects cannot see the store
   failing to advance it.
9. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`. That has committed through a lint ERROR twice
   here because the error scrolled past above the commit output.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject one of the four
named regressions and the test still passes, the check is hollow — **report it**,
and do not conclude the code was fine. Twice in one day in this repo a red-run came
back green with the bug in place, both times because the test's own scaffolding
stood in front of the code: once a fixture built the very thing the function was
supposed to decide, once a fake returned `""` for exactly the input that would have
reached the branch under test. Both read as thorough unit tests.

**So: for every test that patches, fakes or hand-builds anything, name the
production line that would have to change for it to fail — then change it and
watch.** If you cannot name one, there isn't one. Your report must name that line
per test.

**And a warning specific to this lane:** SQLite makes hollow durability tests very
easy to write. A pragma that was set on the wrong connection, a transaction that
was never actually committed, a unique constraint doing work you believe your own
`SELECT` is doing — each of these passes a test that looks correct. The plan's
"must not fake" lines are all about exactly this. Treat them as the spec, not as
advice.

## Files

**Yours:** `user_events/sqlite.py` and `test_user_events_sqlite.py` (both new).

**Read freely, do not edit:** `user_events/digest.py` (**lane A owns it** — import
from it, never change it), `user_events/__init__.py` (leave it exactly as it is —
it is a docstring and it must stay one; an `__init__` that imports submodules will
make the concurrent lanes collide), the two plan documents, `CLAUDE.md`,
`.dreamwork/lessons.md`, `file-formats.md`, `test_watch.py` (existing test idioms —
reuse rather than authoring a second), `justfile`.

**Never touch:** `watch.py`, `user_events/digest.py`,
`user_events/domain_files.py` (**lane C owns it, running concurrently**),
`dev/capture/*`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`bin/ud-dw-generate`.

**You need no server and no port.** Do not run `just guards`.

## Operational constraints

- Limit builds/tests to **2 threads**. Another lane is live in this tree.
- **`B5` is not yours, and this matters for a reason you might not expect:** it is
  the increment that needs a real 1-second lease and a real sleep. Nothing in
  *your* batch should sleep or poll on wall-clock time. If you find yourself
  writing a `sleep`, you have probably wandered into `B5` — stop and report it.
- Commit **each increment separately**, committing with **`git commit --only <paths> -m …`** —
  `git add <path>` alone does **not** isolate your commit, because `git commit`
  commits the whole index and will bury other agents' staged work, and lanes A and C are
  live in this tree right now. **Do not push.**
- Cap yourself at roughly **40 minutes**. Four increments will likely not fit, and
  **that is expected and fine**: land `B1` and `B2` well rather than four badly.
  `B1` alone is a coherent, committable, verifiable point. Report what you did not
  reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

Follow the shape of existing entries. It must state: each acceptance criterion and
whether it holds; **the red per increment verbatim — what you injected, the exact
test name that failed, and that neighbours stayed green**; **the production line
named per test**; whether `A2` existed when you got to `B2` and what you did about
it; the commit shas; which increments you did not reach; anything in the plan you
believe is wrong; and what you are not confident about. An honest "not confident
about X, and here is what would settle it" is worth more than a confident guess,
and this repo has paid for the latter repeatedly.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
