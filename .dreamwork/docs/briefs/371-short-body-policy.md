# Brief — #371: a short body becomes a partial witness, marked incomplete

Repo: `ud-dreamwork`. Worktree: **`.worktrees/371`**, branch **`wt/371`**. Do not push, do not merge.
**Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: watch.py, test_watch.py

## This is a P1 that has been sitting on a settled answer for ten hours

`do_POST` witnesses an interrupted body as **complete**: a client promises N bytes in
`Content-Length`, sends fewer, and the server records the submission as if it were whole.

**Half of this already landed (`d33cc2f`).** `submissions.log` now records `short: true` and
`got: <bytes>` when fewer bytes arrive than were promised, and `file-formats.md` states that `short`
and `truncated` are **opposite conditions** — a cap *this server* applied versus a promise *the
client* broke — with `lint.py` refusing either half of the pair alone. **The witness is already
truthful. What is missing is the behaviour.**

The remaining question was `#263`'s Q2 — refuse a short body, or keep it as a partial witness marked
incomplete and let it proceed. **He answered it at 05:43**, verbatim:

> **"Q2 yes** (amend law 2 to keep a partial witness marked incomplete)"

So: **keep it, mark it incomplete, allow it to proceed.** Do not refuse. The entry sat blocked
because that ruling arrived inside a *neighbouring* question and nothing pointed back here — that
part is `#419`'s problem, not yours. **Your side is settled and implementable in one increment.**

`#263`'s plan places this at its increment 20 — *the envelope is decided before the body is read* —
which is the ordering constraint worth respecting: the decision about the request cannot depend on
having successfully read all of it.

## The trap, and it is already documented in the entry

**A mocked read proves nothing about the read.** `urllib` will not lie about `Content-Length`, so the
only way to produce this condition is a **real socket**: send a larger `Content-Length` than the
bytes you actually write, then `shutdown(SHUT_WR)`. The landed half was proved exactly that way and
your test must be too.

Say in your report which production line would have to change for your test to fail. If a mock or a
fake stands anywhere between the test and the socket read, that is the failure mode this repo has
been bitten by twice today — a test structurally incapable of failing about the one decision it is
named for.

## Done means all of these

1. **A short body is kept, marked incomplete, and proceeds** — his ruling, implemented. Whatever
   "marked incomplete" means in the witness must be *machine-readable*, not prose in a log line, and
   consistent with the already-landed `short: true` / `got: <bytes>` fields rather than a third
   spelling of the same fact.
2. **A complete body is unaffected** — byte-identical behaviour and witness. Prove it, do not assert
   it; this is the check that makes the change safe and the one easiest not to think of.
3. **A real-socket test** in `test_watch.py`: oversized `Content-Length`, fewer bytes, `SHUT_WR`.
   Assert the request proceeded **and** that the witness says incomplete. No mock between the test
   and the read.
4. **The envelope-before-body ordering holds**: the response status cannot depend on having read the
   whole body. State how you verified this rather than that you intended it.
5. **Two red-proofs**, from `cp` snapshots, each `grep`- and `ast.parse`-confirmed before running:
   revert the incomplete marking ⇒ your test fails on the *marking* assertion; make a short body
   refuse ⇒ your test fails on the *proceeds* assertion. Two directions, because "keep it" and "mark
   it" are two claims and one red can only cover one.
6. **A green red-run is a finding, not a relief.** If reinstating either bug leaves your test green,
   say so — the test is wrong and that is the more useful result.
7. `python3 -m pytest test_watch.py -q -p no:randomly` passes, `python3 lint.py` clean.
8. **`just test`.** Do **not** pipe it — a pipeline returns the last command's status. Write to a
   file, read the file, quote the tail and the real exit code. **The suite is fully green as of
   16:05** (52 guards, 0 failures, 1009 pytest passed), so any failure is yours. Guard ports
   **39890-39899** may be held by another lane — check `ss -ltnp | grep 3989` and say if you waited.

## Files

Yours: `watch.py`, `test_watch.py`.

**Not yours:** `file-formats.md`, `lint.py` and `test_lint.py` — another lane holds all three right
now. This matters for you specifically: `file-formats.md` already documents `short`/`truncated`, and
if your "marked incomplete" needs a **new** field documented there, **do not add it** — either reuse
what is already specified, or report the field you need and let the coordinator sequence it. A field
in the log that `file-formats.md` does not describe is exactly what `lint.py` exists to catch.

Do not touch `.dreamwork/tasks.md` or `.dreamwork/questions.md`.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#371): …'` — **never `git add -A`**; other agents
  commit in this tree and a bare `git commit` sweeps up their staged work under your message.
- **Push back with reasons if any of this is wrong.** Eight lanes today have refuted something their
  brief asserted, and every one was right to. In particular: if you think his ruling implies something
  different from what I have written above, quote it and say so before building.

## Report

Say: the real `just test` exit code and how you got it; both red-proofs with exact test names and
which assertion failed in each; how the "incomplete" mark is represented and why that spelling rather
than a new field; how you verified the envelope-before-body ordering; and the production line that
would have to change for your real-socket test to fail.
