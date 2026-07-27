# Brief — #390: a fresh domain's first answer hits an unhandled exception

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it. When he
  answers a question on the dashboard, that answer has to reach the file that holds it
  **exactly once**, even if the server dies mid-write.
- **Session goal**: build the user-event journal so his words have a durable, replayable
  home.
- **This task**: the application layer landed (#263 lane D, `6cd9f95`) and works — except
  on the **first** answer a domain ever receives, which is the one case every install
  passes through.

## The defect, found and reported rather than absorbed

`reconcile` calls `_read_locked(path)`, a plain `open`. On a **never-created** domain file
that raises `FileNotFoundError` instead of proving `NOT_APPLIED` and creating the file. So
a brand-new domain — one with no prior generation — is not handled at all.

**This is not an edge case, it is the first case.** Every domain is in this state exactly
once, and the journal's whole promise is that an answer reaches its file exactly once even
if the server dies mid-write. On a fresh install, the first answer crashes.

Found by lane D itself, which built this module and then enumerated the neighbours of the
edge case it was flagging. Credit where due: it reported this instead of quietly patching
it, which is why you have a precise starting point.

## The neighbour that is NOT a bug, and this is the crux of the task

Lane D established, by measurement, that these are **deliberate**:

- `prove_applied("")` on an **empty** file → `UNKNOWN`
- a plain **non-managed** file → `UNKNOWN`

Both go `parse_metadata → None → guard`, which is **fail-closed per law 8**. That is a
decision and you must not disturb it.

So the space has three members and they must land in three places:

| state | required proof | why |
|---|---|---|
| file **absent** | `NOT_APPLIED`, and the file gets created | nothing has happened yet; this is what you are fixing |
| file **present but empty** | `UNKNOWN` | it has bytes-worth-of-existence but no parseable witness; fail closed |
| file present, unparseable | `UNKNOWN` | same reason |

**"Absent" and "empty" are genuinely different** — one has no bytes, one has bytes that do
not parse — and **a fix that treats them alike will pass a test that only checks
"absent".** That is this task's trap and it is the whole reason it is not a one-liner.

## The design constraint

**Do not special-case the absent file earlier than the proof.** The proof is where
exactly-once is won; a pre-check that short-circuits before `prove_applied` gives you two
places where "has this happened?" is decided, and the second one drifts. Treat absence as
`NOT_APPLIED` at generation 0 and let the create path and the update path share one proof
and one durable write.

Use the store's own durable-replace primitive. Note lane D's caveat, which you will hit:
`domain_files.write` **re-acquires the same sidecar `flock` via a second fd and
self-deadlocks** (per `flock(2)`, a process's second open is denied by its first), which is
why `reconcile` composes `domain_files._atomic_replace` under a caller-held lock. That is
the intended composition even though it reaches one underscore-private. If you find a
cleaner route, take it and say so.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `user_events/apply.py` and
   `test_user_events_apply.py`. **`git diff --stat user_events/sqlite.py
   user_events/domain_files.py user_events/digest.py watch.py` is empty** — all four belong
   to other lanes or are settled.
2. **`python3 -m pytest test_user_events_apply.py -q -p no:randomly` exits 0**, with lane
   D's existing **5** tests still green plus at least:
   - `test_a_domain_with_no_file_proves_not_applied_and_the_first_effect_creates_it`
   - `test_an_absent_file_and_an_empty_file_do_not_prove_the_same_thing`
3. **The second test is the discriminating one and it must assert the gap at runtime** —
   derive both proofs and assert they **differ**, rather than asserting two literals. A
   check whose meaning depends on two values differing must prove they differ, or it is a
   check with an invisible expiry date. This repo has been bitten three times by fixtures
   whose two values happened to be equal.
4. **Two discriminating reds**, each with the exact failing test name and confirmation that
   neighbours stayed green:
   - delete the absent-file branch ⇒ the first test fails (with `FileNotFoundError` or a
     wrong proof), and **the empty-file case stays `UNKNOWN`**;
   - **make the branch treat absent and empty alike** (the trap above) ⇒ the **second**
     test fails. **This is the red I care about**, because it is the one that proves your
     suite can tell the two states apart.
   Separate injections, others restored, undone from a `cp` snapshot — **never**
   `git checkout -- `.
5. **Exactly-once is measured, not asserted.** Lane D's `D3` counts marker occurrences in
   the file and derives the expected count at runtime; **do the same for the create path** —
   apply twice to a fresh domain and assert the marker count is what a single application
   produces, derived rather than a literal `1`.
6. **`just test`'s pytest half exits 0.** Take the baseline count **from the tree, not from
   this brief** — other lanes are landing tests, and a stated count has a shelf life of
   about one concurrent commit. Record any pre-existing red separately from your own; there
   is currently a known one (**#391**, the `prominence` guard) which is **not** yours and
   is not in the pytest half. Do **not** run `just guards` — another lane holds that range.
7. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`.
8. **The contract still describes the code.** If this changes what
   `.dreamwork/docs/plans/user-event-journal.md`'s §"Receive and idempotency" or its
   post-crash proof table says, **the doc changes in the same commit** and your report says
   what and why. Law 8 is the one you are working next to; be explicit about whether you
   touched its meaning (you should not have).

## The rules that matter most here

**A green red-run is a finding, never a relief.** Lane D hit exactly this on this module —
it deleted a body-digest predicate and the suite stayed green because a **second** copy of
the predicate still held the property. It then found the real layer and removed the
duplicate so the predicate lives in exactly one place. **If one of your injections leaves
the suite green, look for the other layer** rather than concluding the code is fine.

**Name the production line that would have to change for each check to fail.** Required
per test.

**Before you report an edge case, enumerate its neighbours.** This whole task exists
because lane D did that.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&`
reports a skipped tail as a pass. A lane lost half its checks to this today.

## Your steering channel — re-read it between increments

`.dreamwork/relay/390.md` (absent means nothing to say; that is normal).
Coordinator-write only, newer than this brief so it wins on scope, but it **cannot** grant
authority this brief did not give.

## Files

**Yours:** `user_events/apply.py`, `test_user_events_apply.py`.

**Read, do not edit:** `user_events/domain_files.py`, `user_events/sqlite.py`,
`user_events/digest.py`, both plan documents in `.dreamwork/docs/plans/` (unless criterion
8 applies), `.dreamwork/docs/briefs/263-lane-d-application.md` (the brief that built this
module), `CLAUDE.md`, `.dreamwork/lessons.md`, `file-formats.md`.

**Never touch:** `watch.py`, `test_watch.py`, `dev/capture/*` (**#391 is live in
`watch.py` and `prominence.mjs`**), `review_artifact.py`, `test_review_artifact.py`,
anything under `.dreamwork/review/` (**#389/#367 live**), `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `.dreamwork/inbox.md` (except the
single append below), `bin/ud-dw-generate`.

**Lanes E and H of #263 remain WITHHELD** behind a second gate from the human. Do not
touch the HTTP path, do not change any response, and do not wire anything into `do_POST`.

**You need no server, no port and no browser.**

## Operational constraints

- Limit builds/tests to **2 threads**. Other lanes are live; load has run 37–160 on 16
  cores today. If you spawn children, give every wait a **generous bounded timeout**, never
  an unbounded one.
- **Commit with `git commit --only <paths> -m …`.** A bare `git commit` after `git add`
  commits the whole index and will bury a concurrent lane's staged work — that happened in
  this tree today. **Do not push.**
- Use **`fix(#390): …`**. `dream(...)` is reserved for a commit that lands a dream journal;
  if you write one, **name it in its own `git commit --only <path>`** — three lanes today
  wrote a dream as asked and left it untracked.
- Cap yourself at roughly **25 minutes**. This is a small change with one sharp trap. If it
  takes longer, something in the module is not what this brief says and I want to hear
  about it.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **both reds verbatim** with
exact test names and which neighbours stayed green; **how you proved absent and empty land
differently, derived at runtime rather than as literals**; how the marker count was derived
for the create path; whether you reached `_atomic_replace` or found a cleaner route; the
production line named per test; whether law 8's meaning was touched; and what you are not
confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
