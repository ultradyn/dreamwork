# Brief — lane C: the managed domain-file store (#263, increments 11–13)

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
  The files that hold his words — `questions.md`, `answers.md` — are edited by the
  loop, by him in an editor, and by several agents at once.
- **Session goal**: build the user-event journal so his words have a durable,
  replayable home.
- **This task**: lane C, the store that makes a domain-file write safe: an
  OS-visible lock, embedded lineage, and one atomic durable replace. It is
  independent of every other lane, which is why it is dispatched now.

**Why this one is worth doing carefully:** `watch.py:8462` today writes a domain
file with a direct `open(path, "w")`. A crash mid-write truncates the file that
holds his answers. Increment 13 is the fix, and its test is the only thing that
can tell the fix from a plausible imitation of it.

## Your authority, exactly

He granted lanes **A–D and F** at 05:43 on 2026-07-28 (`8c5c9cf`). You have
**lane C, increments 11, 12 and 13 only**. Increments 14 and 15 are lane C too but
are **not** in this batch — do not start them. Lanes E (the HTTP cutover) and H
(the version gate) are **withheld** behind a second gate.

**You are building a new module, not changing an existing one.** Do not touch
`watch.py`, do not migrate its writer to your store, do not change any response.
Wiring is a later increment behind a later gate. Lane C is new files only, and
that is what makes it safe to land unattended.

## The specification — read it, do not re-derive it

`.dreamwork/docs/plans/user-event-journal-implementation.md`, section
**"Red-first, per increment" → "Lane C — domain files"**, increments 11–13. Each
row already names the functions, the test, what it asserts, **the production line
whose deletion must make it fail**, and what the test **may not fake**. That is
the spec; follow it rather than inventing a decomposition. If you think a row is
wrong, **say so in your report** rather than quietly doing something else — the
plan has an amendment section for exactly that.

Read also, in the same file, section **"`DomainFileStore` — the durable half
exists, the lock and lineage halves do not"**, which measured what is already
there, and the two rules stated once above the per-increment list: the
`ImportError`-red rule and assert-the-precondition-at-runtime.

## Acceptance criteria — binary, and I will check each one

1. **Files created, and only these:** `user_events/__init__.py` (if lane A has not
   already made it — if it exists, **leave it alone**),
   `user_events/domain_files.py`, `test_user_events_domain_files.py`.
   `git diff --stat watch.py` is **empty**. `git status --porcelain` shows no other
   path modified.
2. **`python3 -m pytest test_user_events_domain_files.py -x -p no:randomly` exits
   0**, containing at least the three named tests:
   `test_a_second_process_cannot_read_while_the_lock_is_held`,
   `test_body_digest_excludes_only_itself`,
   `test_kill_at_rename_leaves_the_previous_generation_intact`.
3. **`just test` still exits 0.** If the tree was already red before you started,
   record what was red *before* your change so your damage is separable from the
   tree's.
4. **Three discriminating reds, each with the exact failing test name recorded
   and confirmation its neighbours stayed green:**
   - remove the `fcntl.flock(fd, LOCK_EX)` call ⇒ the lock test fails;
   - remove the field-exclusion filter in the canonical-body builder ⇒
     `test_body_digest_excludes_only_itself` fails **on its third assertion**
     (the digest-unchanged one), which is the exclusion property itself;
   - replace temp-then-`os.replace` with a direct `open(path, "w")` — i.e. make
     your module do what `watch.py:8462` does today ⇒
     `test_kill_at_rename_leaves_the_previous_generation_intact` fails.
   Separate injections, others restored, undone from a snapshot
   (`cp user_events/domain_files.py $S/bak`), **never** `git checkout -- `.
5. **The lock test uses two real OS processes.** The plan is explicit: *do not
   patch `fcntl` and assert it was called — that asserts the mock.* A patched
   `fcntl` proves nothing about OS visibility, which is the entire claim. State in
   your report that you grepped your test file for `mock`/`patch` around the lock
   test and say what you found.
6. **The crash test really kills a child.** `os._exit` at a named seam between
   `fsync` and `os.replace`, and the parent compares against **pre-state bytes
   captured before the run**, not against a recomputed expectation. An
   end-state-only assertion cannot fail on a crash-window bug — that is precisely
   why this test exists, and it is the failure mode this repo keeps finding.
7. **The temp file is accounted for.** After the kill, assert the temp file is
   either gone or provably ignorable (state which you chose and why); a stray temp
   that a later read would pick up is the bug wearing a disguise.
8. **`python3 lint.py` exits 0**, run as its **own command**, never in the same
   shell command as a `git commit` — that has committed through a lint ERROR twice
   here because the error scrolled past above the commit output.

## The rules that matter most here

**A green red-run is a finding, never a relief.** If you inject one of the three
named regressions and the test still passes, the check is hollow — report it, and
do **not** conclude the code was fine. Twice in one day in this repo a red-run
came back green while the bug was in place, both times because the test's own
scaffolding stood in front of the code: once a fixture built the thing the
function was supposed to decide, once a fake returned `""` for exactly the input
that would have reached the branch.

**So: when your test patches, fakes, or hand-builds anything, name the production
line that would have to change for it to fail — then change that line and watch.**
If you cannot name one, there isn't one. Your report must name that line for each
of the three tests.

## Files

**Yours:** `user_events/domain_files.py` and `test_user_events_domain_files.py`
(both new).

**Shared, and the one collision to be careful about:** `user_events/__init__.py`.
Another lane (A, the digest) is being dispatched at the same time and also needs
the package to exist. If it is already there, **do not edit it**; if you create
it, keep it **empty** — no imports, no re-exports. An `__init__.py` that imports
submodules will make the two lanes collide for no benefit.

**Read freely, do not edit:** the plan, `CLAUDE.md`, `.dreamwork/lessons.md`,
`file-formats.md`, `watch.py` (read `8462` and its surroundings — it is the
behaviour you are replacing, and reading it is the point), `test_watch.py` (for
the existing subprocess/kill idiom — reuse it rather than authoring a second),
`justfile`.

**Never touch:** `watch.py` (three other agents are in the tree; lanes E/G are
withheld), `user_events/digest.py` (lane A owns it), `dev/capture/*`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

**You need no server and no port.** Do not run `just guards`.

## Operational constraints

- Limit builds/tests to **2 threads**. The box is at load ~60 with other lanes
  live, so subprocess tests will be slow — give your child-process waits generous
  bounded timeouts, and **never an unbounded wait**.
- Commit **each increment separately**, staging **by explicit path only** —
  `git add -A` will bury other agents' half-finished work, and several are live in
  this tree. **Do not push.**
- Cap yourself at roughly **30–40 minutes**. Three increments may not fit; if they
  do not, **land increment 11 or 11+12 and report the remainder**. A coherent
  committed point beats three half-done ones, and increment 13 is the one that
  most deserves unhurried attention.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by
rewriting the file, because other agents append concurrently:

`.dreamwork/inbox.md`

Follow the shape of existing entries. It must state: each acceptance criterion and
whether it holds; **the three reds verbatim — what you injected, the exact test
name that failed, and that neighbours stayed green**; **the production line named
for each test**; the commit shas; which increments you did not reach; anything in
the plan you believe is wrong; and what you are not confident about. An honest
"not confident about X, and here is what would settle it" is worth more than a
confident guess.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
