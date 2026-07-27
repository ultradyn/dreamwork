# Brief — the review-artifact frame batch: #347, #372, #364

You are a dreamer on the dreamwork loop for this repo. Your coordinator is a
Claude session in the main checkout. You work **only** in this worktree:
`/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/347-review-frame`
(branch `wt/347-review-frame`).

Three tasks, **one commit**, because `template_stamp()` digests the template's
bytes — touching the frame stales all 15 built artifacts at once and they want
rebuilding once, not three times.

Read the full ledger entries before starting: `.dreamwork/tasks.md`, entries
`#347`, `#372`, `#364`. They carry measurements and two corrections you must
not re-derive. This brief is the summary, they are the source.

## Read first, not optional

1. `CLAUDE.md` — the verification discipline. It is stricter than you expect
   and the reasons are all scars.
2. `transitions.md` — only if you touch anything that appears, disappears,
   moves or changes state. If you do, its rule has no exceptions.
3. `.dreamwork/lessons.md` — how checks here have passed over the exact thing
   they were written for.
4. `review_artifact.py` and `review-artifact.template.html` — the builder and
   the frame.

## #347 — the nav breaks words mid-syllable

**The diagnosis is already exact; do not re-investigate it.** It is one missing
declaration: `.topactions a` in `review-artifact.template.html:120` has
`display:inline-flex; align-items:center; min-height:44px` and **no
`white-space:nowrap`**, while `.identity b`, `.identity span`, `.status`,
`.framebar b` and `.sgbtn` all carry it. It is the only interactive text
element in the top rail without it, so **any** two-word label breaks however
correctly it was authored.

Fix it in the frame: a word-boundary rule plus a min-width that **ellipsises
rather than breaking**, so the next author cannot author their way back into it.

**Two corrections that cost real time — inherit them, do not rediscover them:**

- `getClientRects().length === 1` on the nav anchor is **hollow**. The anchor
  is `inline-flex`, so its box stays **one rect** while the text wraps inside
  it. It reported `1` for four labels that were visibly broken
  ("measur/ed", "sequen/ce", "fixtur/es", "decisi/ons").
- **The instrument that works** is a `Range` over each **word** of the label,
  flagging any word whose rects exceed one — and **skipping words containing
  `-` or `/`**, because breaking at a hyphen or a slash is correct typography
  for paths and compounds.
- **The guard's own first red-proof came back GREEN**: rewriting the labels
  through the DOM did not reproduce the wrap, because the test's scaffolding
  stood in front of the bug. The discriminating red came from rebuilding the
  nav **from source** into a throwaway artifact — `textRects` 1→2 on all four
  while `boxRects` stayed 1. **Inject through the source, not the DOM.**

The guard goes in `dev/capture/`, not in `review_artifact.py` — that module is
stdlib-only and renders nothing, so `getClientRects()` is unavailable to it even
in principle, and pytest here has no browser. Serve the fixture through the
existing `(OUT, PORT)` contract at `/reviewraw`; do not invent a second one.
Adopt `report.mjs` (the #324/#334 idiom) rather than hand-rolling an exit
handler. Load at three widths.

## #372 — the template squeezes tables instead of scrolling them

`.scroller` is `overflow-x:auto` but the table inside carries no `min-width`, so
at 390px it shrinks until words break inside cells and the container never
scrolls. Measured: the shipped `task-transition-boundary.html` has **18**
mid-word breaks at 390px.

Fix: a `min-width` on the table so `.scroller` does the job it exists for. Check
it with the same word-`Range` instrument — a break inside a cell is invisible to
any end-state assertion, which is why "the page looks fine" is not evidence here.

## #364 — the #346 artifact still asks four questions he has already answered

`.dreamwork/review/src/task-store-schema.html` is the page the human opens to
rule on the task store, and his own 01:23 ruling has overtaken it. **The design
doc `.dreamwork/docs/task-store-schema.md` is already correct** — this is a
one-way sync into the artifact, not a decision. Do not decide anything; if the
doc and the artifact disagree about intent, stop and report rather than choosing.

Stale in four measured places: the intro still frames the four decisions as open
(line 22); the normalisation table still says `resolve compound bands · 4` when
three deliberately stay and the fourth was a concatenation artefact (125); the S2
block still poses the question rather than stating the answer (146-147); and the
`priority + priority_rank` pair (85) is superseded by a **closed band column plus
`priority_uncertain`**, which is the shape that preserves *"urgent, not yet
certain which"* without a compound value.

Verify by **looking at the rendered pixels**, not the diff:
`review_artifact.py check` reports `current` on a page whose text is wrong.

## Verification discipline — the part that gets people here

- **A new check is not verification until it has been red.** Reinstate the bug,
  watch the check fail, and **name which test failed**. "The suite went red" is
  not evidence; a discriminating red is.
- **Undo the injection from a `cp` snapshot you took first**, never
  `git checkout --`.
- **A green red-run is a finding, never a relief.** If you reinstate the bug and
  the check passes, the **check** is wrong — do not conclude the code was fine.
  This has happened three times in this repo in two hours, twice on the very
  instruments in this brief.
- **Assert the precondition your check depends on**, derived at runtime. If the
  check's meaning needs two numbers to differ, compute both and assert the gap.
- Every `str.replace`/edit you make asserts that it applied. One silent no-op in
  this exact area was caught only in the pixels.
- Ports: guards bind **39890-39899** (watch) and **39880-39889** (hub). `:39894`
  is held by another lane. Check before you bind, and use your own ephemeral port
  if you serve anything.

## Ownership — narrow on purpose

Yours, in this worktree only: `review-artifact.template.html`,
`review_artifact.py`, `.dreamwork/review/src/*`, the built
`.dreamwork/review/*.html`, one new guard file under `dev/capture/`, and
`file-formats.md` / `watch-design.md` **if** your change alters a documented
contract (document it in the same commit — that is a repo rule, and
`just audit-styleguide` measures it).

**Do not touch:**
- `justfile`'s `DEFAULT_GUARDS`. Another lane is adding two entries to that same
  list right now and you would collide. **Report the exact line your guard needs
  and the coordinator adds it after both branches merge.** Your guard will
  therefore gate nothing until then; say so in your report.
- `watch.py`, `test_watch.py`, `watch-design.md`'s dashboard sections, and
  anything else under `dev/capture/` that already exists — a dreamer holds those.
- `.dreamwork/tasks.md` and `.dreamwork/questions.md`. The coordinator is their
  only writer. Report queue changes instead of making them.
- `#367` (tabbed pointers with next/prev). It is the same frame and it is
  deliberately **not** yours.

Commit with **`git commit --only <paths> -m …`** — a bare `git commit` takes the
whole index, not the paths you added — (`git add -A` sweeps up other agents' work in this
tree). One commit for all three tasks. Do not merge to master. Do not push.

## Reporting

- **Never use `attn`.** Only the coordinator talks to the human.
- Append one block to
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`
  (absolute path, append, do not rewrite the file). State what durable state
  changed, with paths, and your commit sha.
- Say explicitly: which check you red-proved, **which test failed** when you did,
  and the before/after numbers for the mid-word-break counts at 390px.
- If you learned something that should outlive this batch, write
  `.dreamwork/dreams/2026-07-28-<HHMM>-<slug>.md` and put its one-line
  distillation in `.dreamwork/lessons.md`. Nothing to say → no file; empty dreams
  are noise.
- If a task turns out to be blocked or wrong, finish the others in full and say
  precisely what you left out and why. Do not silently narrow scope.
