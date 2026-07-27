# Brief — lane F: the `ud-dw-user-events` CLI (#263, increments 26–29)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  A journal he cannot read from a terminal is a black box, and the whole point of
  the journal is that his words are recoverable.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: lane F, the CLI — the only human-facing surface on the journal,
  and the only place `replay` can cause a domain effect.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have
**lane F, increments 26–29 only**. Lanes E (the HTTP cutover) and H (the version
gate) are **withheld** behind a second gate. **Do not touch `watch.py`** — another
lane holds it right now for a different task — and do not change any HTTP response.

## Your dependency, already satisfied

**`F1` needs `B2`, and `B2` landed at `9bea281`.** So `user_events/sqlite.py`
exists with `open_journal()` and `receive()`. **Lane B still owns that file and is
actively working in it** — read it, import from it, **never edit it**. If you need
a function it does not expose, **say so in your report** rather than adding one;
two lanes editing one module is the split brain this repo's ownership rule exists
to prevent.

`F3` nominally needs `D4` (the adapters), which is **not built**. So for `F3`,
implement the **read-only guard in the command dispatcher** and prove that
`list`/`show`/`health` cannot touch a managed file — that is the half that is
testable now and it is the half that matters. **Do not implement replay's actual
domain effects**; assert that `replay` is the only command *permitted* to, and
report the rest as not reached.

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane F — CLI"**, increments 26–29. Each row names
the command, the test, the **production line whose deletion must make it fail**,
and what the test may not fake. That is the spec; follow it rather than inventing a
decomposition, and if you think a row is wrong, **say so in your report**.

Read also `user-event-journal.md` §"Failure semantics" — `F4` asserts coverage of
that list, so you need to have read it.

## Acceptance criteria — binary, and I will check each one

1. **Files created, and only these:** `ud-dw-user-events` (executable, no `.py`
   extension — match the existing `bin/ud-dw-generate` style but **do not touch
   that file, it is the human's**) and `test_user_events_cli.py`.
   `git diff --stat watch.py user_events/` is **empty** — every file under
   `user_events/` belongs to another lane.
2. **`python3 -m pytest test_user_events_cli.py -q -p no:randomly` exits 0**, with
   at least: `test_list_is_bounded_and_never_exceeds_limit`,
   `test_exit_codes_are_stable`,
   `test_truncation_reports_the_original_length_and_digest`,
   `test_no_command_but_replay_touches_a_domain_file`,
   `test_every_failure_semantic_has_a_health_row`.
3. **`just test` exits 0.** Record what was already red before you started.
4. **One discriminating red per increment**, each with the exact failing test name
   and confirmation neighbours stayed green:
   - `F1`: delete the `LIMIT ?` bind ⇒ the bounded-list test fails. **The plan
     names the trap**: a test that only checks field presence passes with the bind
     deleted, so assert the **row count** against a fixture whose size is derived
     at runtime **and asserted to exceed the limit**. A fixture smaller than the
     limit makes this test vacuous forever.
   - `F2`: delete the truncation-metadata emit ⇒ the truncation test fails. The
     payload's length must be **asserted at runtime** to exceed `--max-bytes`.
   - `F3`: delete the read-only guard in the dispatcher ⇒
     `test_no_command_but_replay_touches_a_domain_file` fails.
   - `F4`: remove a health-row entry ⇒ the coverage test fails **naming the
     missing semantic**.
   Separate injections, others restored, undone from a `cp` snapshot — **never**
   `git checkout -- `.
5. **`F3` derives the managed-file set by walking the directory, not from a list
   in the test.** The plan is explicit about why: *a directory that grows is how a
   check goes hollow after its red run.* A hardcoded list keeps passing while
   silently covering less.
6. **`F4` cannot pass vacuously**, and this is the criterion I will look at
   hardest. It parses the design document, so **if the parse finds zero semantics
   the test must FAIL LOUDLY**, not pass having checked nothing. Assert the parsed
   count is plausible and derived from the document. This is the
   `lessons.md:1447` shape — a silent third verdict read as reassurance — and it
   has cost this repo real time three times.
7. **Exit codes are stable and documented** in the script's own `--help`, and the
   test asserts the specific integers rather than merely "non-zero".
8. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`. That has committed through a lint ERROR twice
   here because the error scrolled past above the commit output.
9. **`git grep -n 'submissions' -- user_events/ ud-dw-user-events` is empty**, and
   your test asserts it as a precondition. The plan requires this: `submissions.log`
   is best-effort by design, and if the journal ever needs it to answer a question,
   the journal is incomplete. Cheap to check, and it stops a whole class of drift.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject one of the four
named regressions and the test still passes, the check is hollow — **report it**,
and do not conclude the code was fine. Twice today in this repo a red-run came back
green with the bug in place, both times because the test's own scaffolding stood in
front of the code: once a fixture built the very thing the function was supposed to
decide, once a fake returned `""` for exactly the input that would have reached the
branch under test.

**Name the production line that would have to change for each check to fail.** If
you cannot name one, there isn't one. Required in your report, per test.

**Assert the precondition the check depends on, derived at runtime.** Three of this
lane's four increments have a precondition that makes the difference between a real
check and a decorative one — a fixture bigger than the limit, a payload longer than
`--max-bytes`, a parse that found something. A literal tuned to today's fixture is
a check with an expiry date nobody can see.

## Files

**Yours:** `ud-dw-user-events` (new, executable) and `test_user_events_cli.py`
(new).

**Read freely, do not edit — all three have live owners:**
`user_events/sqlite.py` (**lane B, active right now**), `user_events/digest.py`,
`user_events/domain_files.py` (**lane C, active right now**), `watch.py` (another
lane). Also read, and do not edit: the two plan documents, `CLAUDE.md`,
`.dreamwork/lessons.md`, `file-formats.md`, `bin/ud-dw-generate` (**the human's
file — read for style only, never modify**), `justfile`.

**Never touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/status.json`, `.dreamwork/inbox.md` (except the single append below),
`dev/capture/*`.

**You need no server and no port.** Do not run `just guards` — two lanes are using
that range.

## Operational constraints

- Limit builds/tests to **2 threads**. Three other lanes are live on this box.
- **Commit with `git commit --only <paths> -m …`**, and for your two **new** files
  `git add <file>` first — `--only <directory>` silently skips untracked files. A
  bare `git commit` after `git add` commits the whole index and will bury a
  concurrent lane's staged work; that happened in this tree an hour ago. **Do not
  push.**
- Commit **each increment separately**.
- Cap yourself at roughly **40 minutes**. Four increments probably will not fit,
  and that is fine: **`F1` alone, done properly with a fixture that actually
  exceeds the limit, is worth more than four rushed commands.** Report what you did
  not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because three other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the red per
increment verbatim — what you injected, the exact test name that failed, and that
neighbours stayed green**; the production line named per test; the exit-code table;
whether `F4`'s parse found a plausible count and what it was; anything you needed
from `user_events/sqlite.py` that it does not expose; which increments you did not
reach; and what you are not confident about. An honest "not confident about X, and
here is what would settle it" is worth more than a confident guess.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
