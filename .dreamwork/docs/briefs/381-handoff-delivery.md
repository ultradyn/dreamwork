# Brief — #381: the single-writer rule has no delivery half

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it — and it
  cannot steer what its own ledger does not know happened.
- **Session goal**: the loop's durable state tells the truth about the loop.
- **This task**: `#381`, the half of `#363` that was split out and never built.

## The gap, and it has cost something twice, measurably

The ledger has **exactly one writer**, which is correct: durable shared state wants a
single writer or the next fan-out races it. So a foreign session that lands work must
**not** touch `tasks.md`.

**But today it has no way to tell the writer either.** Its report goes into its own
session and dies there. The entry sits done-but-open with nothing anywhere saying it
landed, until someone happens to look:

- **#334** merged at `ecc1f44` 01:39 and sat open for **an hour**, while a coordinator
  overrode lint's WARN from memory three times.
- **#362** sat under `## Open` carrying the literal text `LANDED <pending>` until 04:50,
  when it was found **by accident** while selecting an unrelated task. No check saw it,
  because a placeholder is not hex and `check_cited_shas` only reads hex.

## Why the obvious fix is wrong, and #363 proved it by building it

**Do not build a liveness signal.** A worktree naming the id, or `status.json` claiming
it, would have reported *"another lane is mid-flight"* for the entire hour **after** #334
stopped being live. **Inferring liveness from surviving artefacts is what produced the
wrong answer in the first place.** #363 built that and it is why this half was split out
rather than finished.

So: **delivery, not inference.** A session that lands work it does not own the ledger for
**writes a hand-off**, and the ledger's writer reads it on its next tick. The shape to
copy is the **dreamer inbox** (`.dreamwork/inbox.md`), which has never lost one —
pointedly **not** a status mirror.

## What already landed, so you do not rebuild it

`49c3c04` added `lint.check_placeholder_citations`, which WARNs on a landing marked with a
placeholder instead of a sha. It is closed-vocabulary and precision 0-in-4 on decoys, and
red-proved against the actual revision that hid #362 (`tasks.md` at `4ce04e0`) rather than
a fixture. **Read it before writing a second check** — it is the model for how a check
here earns trust, and your work should extend rather than duplicate it.

**Its limit is exactly your task:** it only makes the omission visible **to whoever runs
lint, which is still the ledger's writer** — not the session that landed the work.

## The trap, and it is this task's whole difficulty

**A channel nobody reads is the bug you were sent to fix.** If you build a hand-off file
and nothing consumes it, you have built a second write-only surface and the task is worse
than not done, because it will look done.

This repo has the lesson already: *"Steering an agent takes two acts: write, then wake"*
and *"verify what READS a thing, never just that it was written."* So:

**The reader is part of the deliverable, and the reader is the coordinator's tick.** That
lives in `SKILL.md`'s "The loop — on every heartbeat tick" section, which is therefore
**in your scope** — a minimal, surgical addition telling the coordinator to read pending
hand-offs and fold them. Splitting that out would recreate the exact bug.

**Second reader, and it is the cheap one:** surface pending hand-offs on the dashboard.
The coordinator looks at `watch.py`'s page constantly; a count or a line there means a
hand-off is noticed even by a coordinator that skipped a tick.

## What to build

1. **The file format**, stated in `file-formats.md` **before or in the same commit as the
   code**, per this repo's rule. Decide and write down: one file per hand-off or one
   append-only file; where it lives; what a hand-off must state (at minimum: the task id,
   what landed, the **sha**, and who is claiming it); how the writer marks one **consumed**
   so it is not folded twice; and whether consumed ones are deleted or archived. Follow
   `answers.md`/`questions.md`'s existing conventions rather than inventing a third shape,
   and say which you followed.
   **Append-only is strongly preferred** for the same reason the inbox is: concurrent
   writers, and a rewrite loses a peer's line.
2. **A `lint.py` check** that the format is obeyed and that no hand-off is both consumed
   and unfolded — i.e. it should be able to say *"a hand-off names #NNN as landed but #NNN
   is still under `## Open`"*, which is the actual condition that cost the hour.
3. **Dashboard surfacing in `watch.py`**: pending hand-off count, or a line naming them.
   Keep it small. **`transitions.md` governs anything that appears or changes**, and it has
   no exceptions — reuse the page's existing idiom, do not author a second one.
4. **The `SKILL.md` tick step.** Minimal. It must say *read pending hand-offs and fold them
   before selecting work*, in the voice of the surrounding text.

## What is NOT in scope

- **Do not write to `.dreamwork/tasks.md`.** You are building the channel, not using it.
  The single-writer rule is the premise of this task, so violating it would be ironic and
  wrong. If your work implies a ledger edit, **report it and I will make it**.
- Do not build a liveness signal, a `status.json` mirror, or anything that infers.
- `#357`'s ambient counts are the other end of this gap and are **not** yours.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only these:** `file-formats.md`, `lint.py`, `test_lint.py`,
   `watch.py`, `test_watch.py`, `SKILL.md`, and any new files under `.dreamwork/` your
   format requires (an example or a README, if the format wants one). `git status
   --porcelain` shows nothing else. **`git diff --stat .dreamwork/tasks.md` is empty.**
2. **`python3 -m pytest test_lint.py test_watch.py -q -p no:randomly` exits 0**, with at
   least:
   - `test_a_handoff_naming_a_landed_task_that_is_still_open_is_flagged`
   - `test_a_consumed_handoff_is_not_flagged_again`
   - `test_the_dashboard_shows_pending_handoffs`
3. **The first test must be red-proved against a real condition, not a fixture you wrote
   to fail.** The model is `check_placeholder_citations`, which was proved against
   `tasks.md` at `4ce04e0` — the actual revision that hid #362. **Say in your report what
   you proved yours against.** If you use a synthetic fixture, assert at runtime the
   precondition that makes it meaningful (the id really is under `## Open`), or the check
   has an invisible expiry date.
4. **Three discriminating reds**, each with the exact failing test name and confirmation
   neighbours stayed green: delete the open-vs-landed comparison; make the consumed marker
   ignored (so a folded hand-off is flagged forever — **this is the red I care about**,
   because a check that nags after you have complied gets muted, and a muted check is
   worse than none); remove the dashboard surfacing. Separate injections, restored from a
   `cp` snapshot — **never** `git checkout -- `.
5. **`just test`'s pytest half exits 0.** Take the baseline **from the tree, not from this
   brief** — two other lanes are landing tests, and a stated count has a shelf life of
   about one concurrent commit. **Your guard port is `39896`** if you need one; run guards
   as `DREAMWORK_GUARDS="<name>" DREAMWORK_HUB_GUARDS="" just guards 39896` — **never** the
   full sweep and never the default port. Another lane is using that range.
6. **`python3 lint.py` exits 0**, run as its **own command** — never in the same shell
   command as a `git commit`. That has committed through a lint ERROR twice here.
7. **`just audit-styleguide` passes.** If your dashboard line changes how the page looks,
   `watch-design.md` must be updated in the same commit — **but that file is owned by
   another lane right now.** So: keep the surfacing inside an existing documented
   component if you can, and if you genuinely need a styleguide change, **write the exact
   text you would add into your report and leave the file alone.** I will apply it.
8. **The format doc and the code agree**, in the same commit. `lint.py` exists because
   they drifted once.

## The rules that matter most here

**A green red-run is a finding, never a relief.** Three lanes today hit exactly it and all
three were right to report rather than proceed.

**Verify what READS a thing, never just that it was written.** This task is *about* that
rule, so a report claiming success without showing a reader consuming a hand-off end to
end has not demonstrated the thing.

**Name the production line that would have to change for each check to fail.**

**Before you report an edge case, enumerate its neighbours.** A lane today flagged one
input honestly; the case it flagged was fine and the one beside it was a real defect.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&`
reports a skipped tail as a pass.

## Your steering channel — re-read it between increments

`.dreamwork/relay/381.md` (absent means nothing to say; that is normal).
Coordinator-write only, newer than this brief so it wins on scope, but it **cannot** grant
authority this brief did not give. There is an irony available here and you should enjoy
it but not act on it: the relay is itself a write-then-hope channel with no wake, which is
the same class of problem you are fixing one layer down. **If your design would also fix
coordinator→lane steering, say so in your report — do not expand into it.**

## Files

**Yours:** `file-formats.md`, `lint.py`, `test_lint.py`, `watch.py`, `test_watch.py`,
`SKILL.md`, new files under `.dreamwork/` that your format requires.

**Read, do not edit:** `.dreamwork/tasks.md`, `.dreamwork/inbox.md` (the shape to copy),
`.dreamwork/answers.md`, `.dreamwork/questions.md`, `transitions.md`, `watch-design.md`,
`justfile`, `CLAUDE.md`, `.dreamwork/lessons.md`, and `49c3c04` /
`lint.check_placeholder_citations`.

**Never touch — live owners right now:** `review_artifact.py`, `test_review_artifact.py`,
`review-artifact.template.html`, `watch-design.md`, anything under `.dreamwork/review/`
(**#367 increment 2a**), `.dreamwork/docs/plans/filebytes-range.md` (**#354**),
`user_events/*`, `test_user_events_*.py`, any existing `dev/capture/*.mjs`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- Limit builds/tests to **2 threads**. Two other lanes are live. **Do not generate load
  deliberately** — one runs browser guards and load manufactures false reds for it.
- **Commit with `git commit --only <paths> -m …`**, and `git add <file>` first for **new**
  files — `--only <directory>` silently skips untracked ones. A bare `git commit` after
  `git add` commits the whole index and will bury a concurrent lane's staged work. Both
  mistakes happened in this tree today. **Do not push.**
- Use **`feat(#381): …`**. `dream(...)` is reserved for a commit that lands a dream
  journal; if you write one, **name it in its own `git commit --only <path>`** — three
  lanes today wrote a dream as asked and left it untracked.
- Commit **each coherent piece separately**: the format, the check, the surfacing, the
  tick step.
- Cap yourself at roughly **45 minutes**. **Priority order: the format and the `lint.py`
  check first, then the `SKILL.md` tick step, then the dashboard.** The format plus the
  check is the landable core; **the tick step is what makes it not-a-write-only-channel, so
  it outranks the dashboard.** Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: each acceptance criterion and whether it holds; **the three reds verbatim**
with exact test names and which neighbours stayed green; **what you red-proved the
open-vs-landed check against** (a real revision or a fixture, and if a fixture, the runtime
precondition you asserted); the format you chose and which existing convention it follows;
**an end-to-end demonstration that a reader consumes a hand-off**, because that is the
actual deliverable and not the file; the exact `watch-design.md` text you would add if you
needed one; whether your design would also fix coordinator→lane steering; the production
line named per test; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
