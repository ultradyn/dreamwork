# Brief — #433: the rail crumb cannot shrink, and the fix re-stamps 23 artifacts

Repo: `ud-dreamwork`. Worktree: **`.worktrees/rail`**, branch **`wt/rail`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: review-artifact.template.html, .dreamwork/review/

## The defect, and the fix is already known and verified

`review-artifact.template.html` styles `.identity b` as `white-space:nowrap` with **no**
`overflow:hidden` and **no** `text-overflow:ellipsis` — while its own sibling one declaration away,
`.identity span`, has both. So a long identity crumb cannot shrink and **collides with the nav chips**
instead of ellipsising. **The sibling proves the intent.**

The fix is one declaration and I verified it by runtime injection rather than reasoning:

```
.identity b{...;overflow:hidden;text-overflow:ellipsis;min-width:0}
```

At 390x844 and 1280x900 the overlap goes to **zero**, and the text still renders in full because
ellipsis only engages when it must. **Confirm that yourself before relying on it.**

Evidence it is the template and not one artifact's content: `263-second-gate`'s crumb was shortened from
56 characters to 20 (`a1b0dbc`), which fixed the 84px overflow — and **one overlap survived on mobile
anyway**. Of 13 artifacts with a `.toprail`, 11 are clean and 2 were broken, so the template is one long
crumb away from breaking for anyone.

## Why this is a task and not a one-line commit — the part that needs your judgement

The build stamp is derived from the template's hash (`review_artifact.py`: *"the stamp is
`v<series>+<8 hex of the template …>`"*). So touching the template marks **all 23** built artifacts
`stale` and takes `lint` from 1 warning to **12**. I measured this, then reverted rather than landing it.

**Only 11 of 23 have a `src/`.** These 12 have none and cannot be rebuilt by `review_artifact.py build`:

```
do-now-urgency-treatment      explore-command-contract    goal-hierarchies
hub-public-auth               lan-bind-threat-model       protected-service-boundary-288
review-datetime-order         task-origin-contract        tasks-page
threaded-topic-chats          threaded-topic-chats-v2     ud-dreamtask
```

`review_artifact.py`'s own docstring calls migrating them *"a separate call, deliberately"*.

**So decide, with reasons, and say which you chose before doing it:**

- **(a)** Land the CSS fix and rebuild the 11, accepting 12 standing `stale` warnings until a later
  migration. Cheap, and it leaves `lint` noisy — which trains people to ignore `lint`.
- **(b)** Land the CSS fix *and* migrate the 12 by reconstructing a `src/` for each from its built
  output, so all 23 rebuild and `lint` returns to 1 warning. Complete, and the risk is real: a
  reconstructed source that does not round-trip **silently changes an artifact he may re-read**.
- **(c)** Neither yet — a reason the fix should wait.

**I lean (b) only if round-tripping is provable**, and that is the crux: for each migrated artifact,
rebuilding from the reconstructed `src/` must produce output whose **rendered text and structure match
the current built file**, not merely "look similar". If you cannot demonstrate that per file, prefer
**(a)** and say so. **Do not migrate an artifact you cannot prove round-trips.** Four of the 12 have no
`<header>` at all, so they may not be template-shaped in the first place — check before assuming they can
be sources.

## Done means all of these

1. **Your choice of (a)/(b)/(c) stated with reasons, before the work**, in your report.
2. **The CSS fix landed**, with **zero** overlapping pairs in the `.toprail` at 390x844 and 1280x900 for
   **every** artifact that has one. Measure it: for each, compare the rail's `scrollWidth` against its
   client width, and count pairwise overlaps of its rendering leaf text elements. Print the table.
3. **Every artifact you rebuilt reports `current`** via `python3 review_artifact.py check <paths>`, and
   for each, the **rendered visible text is unchanged** — diff the text extracted from before and after,
   not the HTML, and report the word counts and any delta. A CSS-only template change must not alter one
   word.
4. **If you chose (b): a per-file round-trip proof** for each of the 12, and any that fails stays
   unmigrated with its failure named. Partial migration is an acceptable outcome; a silent content change
   is not.
5. **`lint.py`'s final warning count reported**, with each remaining warning named and attributed.
6. **Every viewport probe asserts the viewport was applied** — `innerWidth === requested` **and**
   `innerHeight === requested`. Both, because chromium's default is 1280x720 and the desktop case asks
   for 1280x900, so on the wrong `newPage` option key (`viewportSize` instead of `viewport`, silently
   swallowed) **the width matches anyway** and only the height reveals it. `dev/capture/above_fold.mjs`
   has the idiom and the playwright import path.
7. **Red-first**: reinstate the missing `overflow`/`text-overflow` and watch your overlap check fail.
   **A green red-run is a finding, never a relief** — if it stays green, your check is wrong and that is
   the more valuable result. **Name the exact declaration whose removal fails it.**
8. **`transitions.md` binds with no size floor.** A crumb that now ellipsises may change on a data
   refresh; if anything appears, disappears, grows or shrinks, read that file and reuse the existing
   idiom. State whether you introduced a gesture.
9. **`watch-design.md` documents any presentation change in the same commit** if the change touches
   documented tokens or components; `just audit-styleguide` measures that.
10. `python3 lint.py` runs. **Do NOT run `just test`** — guard ports 39890–39899 are held by the
    coordinator's suite and another lane is live. Bind nothing in 39880–39899, kill nothing holding one,
    and **do not touch the live dashboard on :35110.**

## Files

Yours: `review-artifact.template.html`, `.dreamwork/review/*.html` and `.dreamwork/review/src/*.html`
(the rebuilds and any reconstructed sources), `review_artifact.py` **only if** the migration genuinely
needs it — say why before editing it, and `test_review_artifact.py` if you change its behaviour.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md`'s dashboard sections, `dev/capture/*`
(a live lane holds those), `lint.py`, `dev/deploy_state.py`, and `.dreamwork/tasks.md` /
`questions.md` — the coordinator is their only writer; report exact lines instead.

**One live conflict to respect:** another lane is editing `watch.py` and `dev/capture/above_fold.mjs`
right now. Do not touch either.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'fix(#433): …'` — **`--only`, never
  `git add -A`**: another agent commits in this tree and a bare `git commit` sweeps its staged work into
  yours. `--only <directory>` silently skips untracked files inside it.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing;
  it was recovered by hand from the dirty worktree.
- **Push back with reasons if any of this is wrong.** Many lanes today refuted something their brief
  asserted and every one was right to — including one that improved on its brief by reordering a guard
  before a `pkill`. If you think the right answer is **(c)**, say so; "not yet" is a complete answer.

## Report

Say: your (a)/(b)/(c) choice and why; the per-artifact rail table with overflow and overlap counts before
and after; the visible-text diff result per rebuilt artifact with word counts; per-file round-trip proofs
if you migrated any, and which you refused; the exact declaration whose removal fails your overlap check;
`lint`'s final warning count with each warning attributed; any transition introduced; and confirmation
you skipped `just test`, bound no guard port, and left :35110 alone.
