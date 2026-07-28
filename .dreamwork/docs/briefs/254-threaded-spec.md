# Brief — #254: the spec for threaded review notes — DESIGN ONLY, and the scope limit is his

Repo: `ud-dreamwork`. Worktree: **`.worktrees/threaded`**, branch **`wt/threaded`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## What he approved, and what he did not

Read `#254` in `.dreamwork/tasks.md`. He approved **N1**, for a **WRITTEN DESIGN ONLY** (2026-07-27 23:03,
`rec` = Accept N1). **The scope limit is part of the approval and is not the loop's to widen: his ask granted a
design/spec document and explicitly NOT parser, file-format, UI, migration, deployment or transition changes.**
So the deliverable is a spec plus a review artifact. **Implementation is a separate ask afterwards.** If you
find yourself editing `watch.py`, you have left the approval.

**N1, in his terms:** the loop **Answer** becomes the root response to the question; later human Notes plus
loop Replies render as one connected discussion branch beneath it at a **single** inset depth — conventional
comment→reply hierarchy **without a diagonal staircase**. Preserve exact chronology, author and timestamp;
recognise an explicit `Reply (loop, …)`; **never indent each turn more deeply**; **if no root exists, keep the
note top-level rather than guessing.**

The defect it fixes: a human Note followed by a loop Answer currently reads as sibling bullets on the main
question, obscuring authorship and causality. Evidence:
`.dreamwork/review/evidence/review-note-reply-unclear.png` — **look at it.**

## Deliverable

**`.dreamwork/docs/plans/threaded-notes-spec.md`** plus a `doc-map.md` row, covering:

- The **data** it reads: `questions.md`'s thread grammar as it exists today (`file-formats.md` states it, and
  `watch.py`'s parsers implement it) — **describe, do not change.** Name the exact markers and what is
  ambiguous about them, since ambiguity is what forces a guess at render time.
- The **rendering rule**, precisely enough to implement without re-deciding: what becomes root, what nests,
  the single inset depth, ordering, and the no-root fallback he specified.
- **Authorship and accessibility**: how a reader and a screen reader both know who said what. His asks
  repeatedly name accessibility and it is not decoration here — authorship *is* the content of this fix.
- **Responsive**: what happens to a nested branch at 390px, where a single inset already costs real width.
- **The transition**, described only. `transitions.md` binds with no size floor, so say which existing
  gesture this reuses when it is built — **do not author a new one**, and note reduced-motion parity.
- **What is NOT worth doing**, with reasons. A design recommending everything is not a design.
- **The open decision, if any**, framed for him.

## The review artifact

The repo's rule: **every request for a ruling ships a self-contained HTML artifact**. Build
`.dreamwork/review/src/254-threaded-notes.html` with `python3 review_artifact.py build`. It must carry an
**`#ask`** wrapping the actual decision with the accepted answers spelled out, and **show the before/after
rendering** — a spec about legibility that cannot be seen is unpersuasive. Check with
`node dev/capture/above_fold.mjs .dreamwork/review/254-threaded-notes.html`; the fold is now **derived** from
the live route (`#432`), so trust and print its number. **The `#ask` must be above it.**

**Note the table trap fixed tonight (`c19107a`)**: the template's `table{min-width:max-content}` makes a table
size to unwrapped content — 4197px inside a 1120px pane — so if you use a table, set
`min-width:0;width:100%;table-layout:fixed` on it and check both viewports. He could not read the last one.

If the design has **no** decision genuinely his, **say so and skip the artifact** — a decoy ask is worse than
none.

## Done means

1. The spec exists, answers every bullet, and each recommendation names what it costs as well as what it buys.
2. A `doc-map.md` row.
3. The artifact exists with a real `#ask` above the derived fold at **both** viewports, or is skipped with a
   reason.
4. **No implementation.** No `watch.py`, no `file-formats.md`, no parser, no migration — confirm this
   explicitly.
5. Report the exact `questions.md` entry text you want filed. **Do not edit `questions.md`** — the coordinator
   is its only writer.
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078). **Do not run the full
   `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.

## Files

Yours: `.dreamwork/docs/plans/threaded-notes-spec.md`, `.dreamwork/docs/doc-map.md`,
`.dreamwork/review/src/254-threaded-notes.html` and its build output.

**Not yours:** `watch.py`, `justfile` (**held for `#177`**), `file-formats.md` (**held for `#402a`**),
`review-artifact.template.html` and `.dreamwork/review/src/**` other than your own file (**held for `#436`**),
`dev/capture/*` (**held for `#444`** — you may *run* `above_fold.mjs`), `lint.py`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`.

## Practical

2 threads. `git add <newfiles>` then `git commit --only <paths>` — **never `git add -A`**. **Commit before you
finish.** **Push back with reasons if any of this is wrong** — but note the scope limit is his ruling, not my
preference, so widening it is not a push-back I can accept.

## Report

Which model you are; the rendering rule in brief; the ambiguities you found in the existing grammar; the
accessibility and 390px answers; what you recommend NOT doing; whether you shipped an artifact and the derived
fold with the `#ask` top; the exact `questions.md` text; and confirmation you changed no parser, format, UI or
transition.
