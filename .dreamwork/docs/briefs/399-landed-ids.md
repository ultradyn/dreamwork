# Brief — #399: a bolded id inside a landed entry is not a landing, and right now the suite is red because of it

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## You are in a worktree

Working directory: **`.worktrees/399`**, branch **`wt/399`**. The coordinator merges it back — do
**not** push and do **not** merge. Two consequences, both silent if you get them wrong:

- **`.dreamwork/inbox.md` is UNTRACKED and so does not exist in your worktree.** Appending to the
  relative path creates a file nobody reads. Use the absolute path in *How to report*. A lane lost
  its entire report this morning that way.
- **This brief lives in the main checkout** and your worktree predates it — read it at
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/docs/briefs/399-landed-ids.md`.

**When you land your commit**, append **one line** to
**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`**:
`- **#399** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @grok — <one line, what landed>`
**`cat >>` now works for this**, and you are the first lane for which that is true: `#406` landed
two hours ago and moved `## Folded` above `## Pending`, so an end-of-file append lands under
Pending. **Verify that it did** rather than trusting this paragraph, and say so in your report — you
are the first test of a fix whose whole point was that the instruction had been impossible to obey.
Do **not** write to `.dreamwork/tasks.md`; the coordinator is its only writer.

## The chain above this task

- **DREAMWORK.md goal**: the loop's durable state must tell the truth about the loop. A ledger that
  reports open tasks as landed is the ledger failing at its one job.
- **Session goal**: the green baseline is actually green.
- **This task**: `#399`, **P1, next-up**. Read its ledger entry, and `#401`'s and `#395`'s landed
  entries — all three are the same class and two are now fixed, so their solutions are precedent.

## Why this is urgent: the suite is RED on master right now

`test_lint.py::TestLandedAsks::test_this_repo_has_no_forgotten_folds` **fails**. Measured on master:
**496 passed, 1 failed**. `check_landed_asks` WARNs that the `#367` open ask *"names only landed
task(s) #367 — fold the ask, or reopen the task"*. **`#367` is under `## Open`.** Its ask is the
human's unanswered strip-below-the-cliff question, so a coordinator obeying that WARN would close a
question he has not answered.

The coordinator missed this for hours because `python3 lint.py` **exits 0** (the finding is a WARN,
not an ERROR) and every pytest run was a `-k` selection that excluded this test. **Your acceptance
criterion is `just test` green — not "the WARN is gone".**

## The defect

`watch._landed_ids` takes **every ids-only bold span anywhere** in `## Recently landed`. Its
docstring states the intent — *"`**#96 stage 1**` (a prose reference) does not land #96"* — and that
exclusion only works when prose puts **words inside the bold**. **This ledger's natural voice is
`filed as **#392**`**, a bare bolded id, which lands it.

**Do NOT inherit a count from me.** A previous version of this entry said 7 ids appeared in both
sets; the ledger has changed a great deal since, and this morning I told two lanes to inherit a
measurement of mine that was **wrong by three orders of magnitude**. **Re-derive it**: report how
many ids `parse_ledger` returns in **both** the open and landed sets, and name each one with the
text that caused it.

## The hard part, which is a design decision and not a regex

**Two checks share this input and disagree about what a bold id means.**
`lint.check_related_markers` **requires** a landed entry to name its open counterpart — *"an entry is
read alone"* — and `_landed_ids` then reads that very marker as a landing. **So the more correctly
the ledger is cross-referenced, the more open tasks are reported landed.** Neither check is wrong
alone. You cannot fix this by making one of them stricter without breaking the other.

And a bare mention **does** sometimes mean landed: one commit closing two tasks is a real pattern, so
"only the entry head counts" is not obviously right either.

**My recommendation, and you should push back if you find better — say why:**

> **Make it explicit, the way `related:` already is.** A landed entry declares any *additional* ids
> it closed in a **dedicated field** — `· also-landed: **#123, #124**` — and **every other bold id in
> a landed entry is a reference, not a landing**. Then the two checks read *different fields* and
> cannot disagree. Prose scanning is what created this, and `#395` already established that an
> explicit anchored field is the fix for exactly this class.

The alternative — **entry heads only** — is smaller and needs no migration, but it silently loses the
multi-close case unless something else records it. **Whichever you choose, say what it costs and
whether any existing landed entry relies on the behaviour you are removing** (check, do not assume).

## Acceptance criteria — binary, and 1 is the one I read first

1. **`just test` is GREEN**, run in full, output quoted. Specifically
   `test_this_repo_has_no_forgotten_folds` passes **because `_landed_ids` is right**, not because the
   `#367` ask was folded, the test was relaxed, or `questions.md` was edited. **`#367` must still be
   under `## Open` in `questions.md` and you must not touch that file** — it is the human's channel
   and the coordinator writes it. Show `git diff --stat .dreamwork/questions.md` empty.
2. **`parse_ledger`'s two sets are disjoint**, or the overlap is principled and each remaining member
   is named with why it is legitimately both. Assert this **at runtime against the real ledger** in a
   test, with the count reported — so it cannot silently regress.
3. **Files touched, and only these:** `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`,
   `file-formats.md`, and `.dreamwork/handoffs.md` (your one line). `git status --porcelain` shows
   nothing else. **`_landed_ids` is at `watch.py:7685` and `parse_handoffs`/`handoff_parent_ids` sit
   just below it** — `#401` landed there two hours ago, so **read that code before editing near it**
   and do not undo it.
4. **Tests, at least:**
   - `test_a_bare_bolded_id_in_a_landed_entry_is_not_landed`
   - `test_a_landed_entry_head_is_landed`
   - `test_the_real_ledger_has_no_id_both_open_and_landed`
   - plus whatever your chosen policy needs (an `also-landed:` field test, if you take my rec)
5. **Three discriminating reds**, each naming the exact failing test with neighbours confirmed green.
   One of them must be: **restore the old mention-scanning behaviour ⇒
   `test_the_real_ledger_has_no_id_both_open_and_landed` fails**, which is the red that proves the
   fix is load-bearing rather than incidental. Separate injections, restored from a `cp` snapshot —
   **never** `git checkout -- `. **Grep each injection to confirm it reached the code, then
   `python3 -c "import ast; ast.parse(open('watch.py').read())"`** — a broken injection this morning
   gave `IndentationError` at collection, and **zero tests running is not a red**. **A green red-run
   is a finding, never a relief.**
6. **`check_related_markers` still passes** and its coverage line still reports **44 related pair(s),
   all reciprocal; 0 entries unparseable** — or a different number you explain. That check is the
   other half of the tension and breaking it is the obvious way to make this worse.
7. **`file-formats.md` states the rule** — what marks a task landed in the ledger, and that a bold id
   in a landed entry is otherwise a reference. **Same commit as the code.**
8. **`python3 lint.py` exits 0**, run as its **own command**, never in the same shell command as a
   `git commit`. That has committed through a lint ERROR twice here.

## The hollow outcome

**Making the test pass by folding the `#367` ask.** That is what the WARN literally instructs, it
would be green, and it would lose the human's unanswered question — the exact damage this entry was
filed to prevent. If at any point your fix requires editing `questions.md`, stop: you are solving
the wrong problem.

## The rules that matter most here

**Assert the precondition.** Criterion 2's meaning depends on the real ledger having entries in both
sections; derive both counts at runtime and assert they are non-zero, or the test is vacuous the day
the ledger is empty.

**A fallback shares the parser's blind axis** — `#401`'s lesson, one region away from your code.

**Before you report an edge case, enumerate its neighbours.** Yours: a combined head
`- **#353/#367**` in the landed section; an id mentioned in a landed entry that is **genuinely** also
landed; an id in a landed entry's `related:` marker (the tension's centre); a **four-digit** id; and
an id appearing in `## Open` **and** as a landed entry head (a real reopening — what should that do?).

**`grep -c` exits 1 when the count is zero.**

## Files

**Yours:** `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`, `file-formats.md`, one line in the
main checkout's `.dreamwork/handoffs.md`.

**Read, do not edit:** `.dreamwork/tasks.md` (`#399`, `#401`, `#395`, `#409`),
`.dreamwork/questions.md` (**read only — the `#367` entry is the thing being protected**),
`.dreamwork/lessons.md`, `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md`
(the id-form matrix — your neighbours are in it), `justfile`, `SKILL.md`.

**Do not touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`SKILL.md`, `watch-design.md`, `bin/ud-dw-generate`.

## Operational constraints

- Limit builds/tests to **2 threads**. **No server, no port, no browser guards needed** — this is
  parser work. `just test` does run the browser guards; if one reds, **re-run it at low load** before
  reporting it, because load manufactures **false reds only** for those. Check
  `cut -d' ' -f1-3 /proc/loadavg`.
- **Commit with `git commit --only <paths> -m …`** on `wt/399`. A bare `git commit` after `git add`
  commits the whole index and has buried a concurrent lane's work in this tree.
- Use **`fix(#399): …`**. `dream(...)` is reserved for a commit that lands a dream journal; if you
  write one, name it in its own `git commit --only <path>`.
- Cap yourself at roughly **35 minutes**. **Priority order: the policy decision and criterion 2's
  runtime disjointness test first, then the fix, then `just test` green, then `file-formats.md`.**
  Report what you did not reach.

## How to report

Append **once**, at the end, in a single shell append, to the **ABSOLUTE** path:

**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`**

State: **the `just test` result in full** (criterion 1 — I read this first, and I will re-run it);
**your re-derived both-sets count and each id with the text that caused it**; your **policy decision
and what it costs**, including whether any existing landed entry relied on the behaviour you removed;
the three reds with exact test names and neighbours green; the `check_related_markers` coverage line;
**whether `cat >>` placed your hand-off line correctly** (you are the first test of `#406`'s fix);
what each of the five neighbour cases does; the exact `file-formats.md` text you added; and what you
are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` **in the main checkout** and say so.
