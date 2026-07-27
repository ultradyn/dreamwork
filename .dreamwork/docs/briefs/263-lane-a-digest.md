# Brief — lane A: the request digest (#263, increments 1–2)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  His answers, asks and commands are typed into the dashboard, and today they
  survive only in a best-effort append.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: lane A, the digest that gives every request one stable identity.
  Two increments. Nothing else in the journal can be built until a digest exists,
  because `B2` and `G2` both consume it.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have
**lane A only**. Lanes E (the HTTP cutover) and H (the version gate) are
**explicitly withheld** behind a second gate — do not touch `watch.py`, do not
change any response, do not wire your module into anything. Lane A is new files
and nothing else, and that is what makes it safe to land while he is asleep.

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane A — digest"** (increments 1 and 2). That
section already names, for each increment: the functions, the test, what it
asserts, **the production line whose deletion must make it fail**, and what the
test **may not fake**. It is the spec. Follow it rather than inventing your own
decomposition, and if you think a row is wrong, **say so in your report instead
of quietly doing something else** — that is a valuable result and there is a
standing amendment section in the plan for it.

Read also the two rules stated once above that section and applying to every
increment: the `ImportError`-red rule, and assert-the-precondition-at-runtime.

## Acceptance criteria — binary, and I will check each one

A second agent must be able to tell pass from fail here without asking me.

1. **Files created, and only these:** `user_events/__init__.py`,
   `user_events/digest.py`, `test_user_events_digest.py`. `git status
   --porcelain` at the end shows no other path modified. **Zero lines of
   `watch.py` changed** — `git diff --stat watch.py` is empty.
2. **`python3 -m pytest test_user_events_digest.py -x -p no:randomly` exits 0**,
   with at least the two named tests present:
   `test_framing_boundary_cannot_be_shifted` and
   `test_case_and_parameter_order_do_not_fork_a_digest`.
3. **`just test` still exits 0** — the whole suite, not only your file. If it was
   already red before you started, record what was red *before* your change so we
   can tell your damage from the tree's.
4. **Three discriminating reds, each recorded with the exact test name that
   failed and the ones that stayed green:**
   - delete the length-prefix write in `length_framed` ⇒
     `test_framing_boundary_cannot_be_shifted` fails;
   - delete the `.lower()` on the media-type subtype ⇒
     `test_case_and_parameter_order_do_not_fork_a_digest` fails;
   - delete the parameter `sorted()` ⇒ the same test fails **on its own**, i.e.
     with the `.lower()` restored.
   Each red is a **separate** injection with the others restored. Restore from a
   snapshot you took (`cp user_events/digest.py $S/bak`), **never** `git checkout
   -- `.
5. **The precondition assertions exist and are derived at runtime.** For the
   framing test, the naive concatenations of `("ab","c")` and `("a","bc")` must be
   computed in the test and asserted equal — if they are not equal the test proves
   nothing and must fail loudly saying so. A literal tuned to today's values is a
   check with an expiry date.
6. **The discriminating half of increment 2 is present:** a *different* media
   type must give a *different* digest. Without that assertion `return ""` passes
   the whole test, and you must state in your report that you checked this by
   trying it.
7. **The test does not build framed bytes itself and does not call `hashlib`
   directly.** Both are named in the plan as the fake that would make the test
   assert a property of the fixture (the #320 trap in `.dreamwork/lessons.md`).
   Say in your report that you grepped your own test file for `hashlib` and found
   nothing.
8. **`python3 lint.py` exits 0**, run as its **own command** — never in the same
   shell command as a `git commit`. That has committed through a lint ERROR twice
   in this repo because the error scrolled past above the commit output.

## The rule that matters most here

**A green red-run is a finding, never a relief.** If you delete one of the three
named lines and the test still passes, the check is hollow — **report that**, and
do not conclude the code was fine. This repo has had three checks that were
structurally incapable of failing, two of them invisible in the guard output. A
new module makes an `ImportError` red trivially available, and an `ImportError`
red is **not** verification: it proves the test runs, not that it discriminates.

## Files

**Yours:** `user_events/` (new package — you create it), and
`test_user_events_digest.py` (new).

**Read freely, do not edit:** the plan, `CLAUDE.md`, `.dreamwork/lessons.md`,
`file-formats.md`, `test_watch.py` (for the existing test idiom), `justfile`.

**Never touch:** `watch.py` (three other agents are in the tree and lanes E/G are
withheld), `dev/capture/*` (other lanes own files there), `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `.dreamwork/inbox.md`
(except the single append below), `bin/ud-dw-generate`.

**You need no server and no port.** Do not run `just guards`; other lanes hold
that range.

## Operational constraints

- Limit builds/tests to **2 threads**. The box is at load ~60 with other lanes
  live; prefer `-p no:randomly -x` and a single file where you can.
- Commit **each increment separately**, staging **by explicit path only** —
  `git add -A` will bury other agents' half-finished work, and several are live
  in this tree right now. **Do not push.**
- Cap yourself at roughly **30 minutes**. If it grows past that, land increment 1
  alone — it is a coherent, committable point — and report the remainder.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append to it concurrently:

`.dreamwork/inbox.md`

Follow the shape of the existing entries. It must state: each acceptance
criterion above and whether it holds; **the three reds verbatim — what you
deleted, the exact test name that failed, and that its neighbours stayed
green**; the commit shas; anything in the plan you think is wrong; and what you
are not confident about. An honest "not confident about X, and here is what would
settle it" is worth more than a confident guess, and this repo has paid for the
latter repeatedly.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
