# Brief — #399b: `_landed_ids` fixed the present and lost the past. `master` is red.

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.

## You are in a worktree

Working directory **`.worktrees/399b`**, branch **`wt/399b`**. The coordinator merges it back — do
**not** push, do **not** merge.

- **`.dreamwork/inbox.md` is UNTRACKED and does not exist in your worktree.** Report to the absolute
  path in *How to report*; a relative append creates a file nobody reads.
- **This brief lives in the main checkout**:
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/docs/briefs/399b-landed-history.md`.

**When you land**, append one line to
**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`** —
`- **#399** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>` — and **commit it among
your paths**. `cat >>` works (`## Pending` is last since `#406`). Do not write `.dreamwork/tasks.md`.

## The situation, already diagnosed — do not re-derive it, verify it

**`master` is red and has been all day.** `just test` fails on the **burndown** guard.

`#399` landed at `8e37db3` (merged `3344e43`). It changed `_landed_ids` from *"every ids-only bold
span in `## Recently landed`"* to *"entry heads + an explicit `· also-landed: **#N**` field"*. That
fixed a real P1 — `lint` was reading a landed entry's `related: **#367**` marker as a **landing** and
instructing the coordinator to close the human's unanswered question — and its unit tests are sound.

**It also broke the burndown, and the bisect is done:** `dev/capture/burndown.mjs` **PASSES at
`c42af82`** (the merge's first parent) and **FAILS at HEAD**. Two assertions, at `:183` and `:185`:

```
FAIL the head states the three totals it is a picture of
FAIL ...and a completion GROOMED out of the landed section still counts (#1, #2 and #3 were pruned)
```

**Why.** The guard builds its own git history inline (`burndown.mjs:91-107`) and writes landed
entries in the **inline-mention** form — `**#1** landed (aaa1111).` — **not** as `- **#N**` entry
heads. Under the new rule those parse as **zero landed ids**.

**And that form is not the guard being unrealistic.** `ledger_series` walks **old revisions** of
`.dreamwork/tasks.md`, and the historical landed shape *was* the inline mention — the pre-`#399`
docstring said so in as many words. So the new rule is correct for today's file and wrong for
history, and a burndown that silently drops historical completions renders the loop as having
achieved less than it did (`#136`'s shape).

## What to do

**Recommended, and smaller than what landed — push back with reasons if you disagree:**

> Do not exclude *all* mentions. Exclude ids that sit inside a **known field** — `related:` above
> all, plus any other field-anchored marker you find — and let a bare landing mention continue to
> count. That kills the `#367` false landing, which *was* a `related:` marker, without discarding
> the historical form. **Keep `also-landed:`**; it is a good addition and costs nothing.

**Do not revert `8e37db3`.** It fixed a real defect and its tests are good. This is additive.

## Acceptance criteria — 1 is a GATE, not a report

1. **`just test` GREEN.** Run it, wait for it, and **read the exit code correctly** — do **not**
   pipe it to `tail`, because a pipeline returns the *last* command's status and that is precisely
   how this regression reached `master`. Redirect to a file and read the file, or use
   `set -o pipefail`. **Quote the tail of the output and the real exit code.** Nothing is done until
   this passes.
2. **BOTH previously-failing things pass**: `test_lint.py::TestLandedAsks::test_this_repo_has_no_forgotten_folds`
   **and** the `burndown` guard. Fixing either by breaking the other is the failure mode this task
   exists for — it is what `#399` did.
3. **`test_the_real_ledger_has_no_id_both_open_and_landed` still passes**, and `parse_ledger`'s two
   sets stay disjoint on the real ledger, with the precondition asserted at runtime (both sections
   non-empty) so the check cannot go vacuous.
4. **THE DISCRIMINATING PAIR — two reds in opposite directions**, which together prove the fix
   threads the needle rather than sliding to one side:
   - restore *scan-every-mention* ⇒ `test_this_repo_has_no_forgotten_folds` fails;
   - restore *entry-heads-only* ⇒ the **burndown guard** fails.
   Plus a third for whatever field-exclusion you add. Separate injections, restored from a `cp`
   snapshot — **never** `git checkout -- `. Grep each injection to confirm it reached the code, then
   `python3 -c "import ast; ast.parse(open('watch.py').read())"`; a broken injection gives
   `IndentationError` at collection and **zero tests running is not a red**. **A green red-run is a
   finding, never a relief.**
5. **A unit test that covers the history shape**, so this cannot regress without pytest noticing —
   the guard caught it and the unit tests did not, which is why it reached `master`. Feed
   `_landed_ids` the inline-mention form and assert it lands; feed it a `related:` marker and assert
   it does not.
6. **Files touched, and only these:** `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`,
   `file-formats.md`, and your one `handoffs.md` line. `git status --porcelain` shows nothing else.
7. **`python3 lint.py` exits 0**, as its **own command**, never in the same shell command as a
   `git commit`.

## The hollow outcome, and it is very tempting here

**Editing `dev/capture/burndown.mjs`'s fixture to use entry heads.** The guard goes green in one
line and the property it exists to test — *a completion groomed out of the landed section still
counts* — is silently deleted. **The fixture encodes the ledger's real history; it is evidence, not
scaffolding.** If you believe the fixture is genuinely wrong, say so in your report with your
reasoning and **change nothing** — that is a coordinator decision.

## The rules that matter most here

**Two readers wanted different things from one function, and that is the whole bug** — the same
shape `#399` itself was about (`check_related_markers` and `_landed_ids` disagreeing over what a
bold id means). Ask, before you finish: **who else calls `_landed_ids`, and does each caller want
"landed now" or "ever landed"?** Name them in your report. If the two genuinely differ, two
functions is a legitimate answer.

**Before you report an edge case, enumerate its neighbours.** Yours: an old revision where the
landed section is **empty**; a mention inside a **fold note**; an `also-landed:` field in an **old**
revision (there are none — what does that imply for the walk?); a landed entry that is **both** a
head and mentioned inline; and a combined head in history.

**`grep -c` exits 1 when the count is zero.**

## Files

**Yours:** `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`, `file-formats.md`, one line in the
main checkout's `.dreamwork/handoffs.md`.

**Read, do not edit:** `dev/capture/burndown.mjs` (**read it first** — `:91-107` is the fixture and
`:183-186` the assertions), `.dreamwork/tasks.md` (`#399`, `#401`, `#409`), `.dreamwork/lessons.md`,
`justfile`, `SKILL.md`.

**Do not touch:** `dev/capture/**` (see the hollow outcome), `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/status.json`, `SKILL.md`, `watch-design.md`,
`bin/ud-dw-generate`.

## Operational constraints

- Limit builds/tests to **2 threads**. `just test` runs the browser guards and takes **~15 minutes**;
  budget for it. Guards bind **39890-39899**; a focused re-run is
  `DREAMWORK_GUARDS=burndown DREAMWORK_HUB_GUARDS= just guards 39897`. Load manufactures **false reds
  only**, so re-run a red at low load (`cut -d' ' -f1-3 /proc/loadavg`) — but note this failure is an
  **assertion about totals**, not timing, so load will not explain it away.
- **Commit with `git commit --only <paths> -m …`** on `wt/399b`. **Do not push, do not merge.**
- Use **`fix(#399): …`**. Commit early and often — a lane finished this task's predecessor and
  **died before committing**; the work survived only because it was in a worktree.
- Cap yourself at roughly **40 minutes** (the suite is 15 of them). **Priority order: the
  field-exclusion fix and criterion 5's unit test first, then criterion 4's opposite-direction reds,
  then the full `just test`.** Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append, to the **ABSOLUTE** path:

**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`**

State: **the real `just test` exit code and how you obtained it** (criterion 1 — I read this first,
and I will re-run it); that **both** `forgotten_folds` and `burndown` pass; the **two
opposite-direction reds** verbatim with exact names; **who calls `_landed_ids` and whether each
wants "landed now" or "ever landed"**; what each of the five neighbour cases does; whether you
concluded the guard fixture is wrong (and you changed nothing); the exact `file-formats.md` text;
whether you wrote **and committed** the hand-off line; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` **in the main checkout** and say so.
