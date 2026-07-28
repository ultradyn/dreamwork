# Brief — #401 + #406: make a hand-off that is wrong LOUD instead of invisible

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom — **read it carefully, the paths are absolute for a
reason that has already cost one lost report.**

## YOU ARE IN A WORKTREE — this changes two things and both are silent if you get them wrong

Your working directory is **`.worktrees/401-406`** on branch **`wt/401-406`**. The coordinator
merges it back. This is the first lane dispatched this way, so:

1. **`.dreamwork/inbox.md` does NOT EXIST in your worktree** — it is untracked, so a worktree
   checkout has no copy. Appending to the relative path creates a **new file nobody reads**. Your
   report goes to the absolute path in *How to report*. This is not pedantry: a lane lost its
   entire report this morning by writing to a channel nobody read.
2. **`.dreamwork/handoffs.md` DOES exist in your worktree** as its own copy. Your hand-off line
   goes to the **main checkout's absolute path**, not your local copy — your local copy is the
   *thing you are fixing* and you will be editing it as a deliverable.

Everything else (`git commit --only`, `pytest`, `lint.py`) works in a worktree unchanged —
verified.

**When you land your commit**, append **one line** to
**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`** under `## Pending`:
`- **#401** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by ccc @grok — <one line, what landed>`
Do **not** write to `.dreamwork/tasks.md` — the coordinator is its only writer.
**And yes: placing that line correctly is the very bug you are fixing.** Do it by insertion, not
`cat >>`, and note in your report what you had to do — that observation is part of the deliverable.

## The chain above this task

- **DREAMWORK.md goal**: the loop's durable state must tell the truth about the loop. A record
  whose readers silently drop entries is worse than none, because it looks healthy.
- **Session goal**: the channels the loop depends on fail loudly or not at all.
- **This task**: `#401` (fix half) **and** `#406`, together. Read both ledger entries, plus
  `#381` (which built this file) and `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md`
  (**your own audit** — you wrote it an hour ago; §3's harness is the instrument for this fix).

## The three defects, all measured, all in one region

`watch.py:7706-7712` — `HANDOFF_PENDING_RE`, `HANDOFF_FOLDED_RE`, `HANDOFF_BARE_RE`, and
`parse_handoffs`. `lint.py` **imports** the parser rather than copying it, so the fix is one place.

1. **A sub-id or combined id is dropped by the parser AND by the fallback.** All three patterns are
   `#(\d+)`. Measured: `- **#392a** · landed \`abc\` · … · by x` yields `pending=[]` **and**
   `malformed=[]`. The ledger's documented combined head `- **#367/#392**` drops identically.
2. **`malformed` structurally cannot fire for that class**, because `HANDOFF_BARE_RE` is `#(\d+)`
   like the grammar it is meant to backstop. The fallback shares the parser's blind axis.
3. **`## Pending` is not the last section, so the instructed `cat >>` append lands in `## Folded`.**
   `malformed` only runs inside section `P`, so a Pending-shaped line inside `## Folded` is invisible
   to all three buckets. **You found this yourself** and reported it under "not confident about",
   then committed a fix for your own line (`75e6139`). Three of four lanes got the section right
   only by **disobeying** the instruction.

## What to build

**The load-bearing change, needed under any policy: `HANDOFF_BARE_RE` must match ANY bolded-id
entry head, and `malformed` must be reachable for a line in the wrong section.** Everything else
is a policy choice on top of that.

**The policy I recommend, with reasons — push back if you find a better one and say why:**

> **Accept the ledger's full id vocabulary** (plain `#392`, sub-id `#392a`, combined `#367/#392`),
> and **normalise to the parent only for correlation** against `## Open` — explicitly, in a named
> function, with a test. Do **not** leave normalisation to `ENTRY_ID`'s incidental
> letter-stripping, which is your audit's third finding: `#392a` → `392` *silently*, a wrong value
> rather than a missing one.

Why not "require a plain ledger head and reject the rest"? It is smaller, but `#392a`'s line is
**already in the file** and the record should stay readable rather than be rewritten to suit the
parser. Accepting the vocabulary that the loop actually writes is the honest direction.

**For the sections, decide between these and justify it:** move `## Folded` **above** `## Pending`
so an EOF append lands correctly and the instruction becomes true; or **drop the sections** and
parse by line shape (`· landed \`sha\`` vs `→ folded (ts):`), which your audit implies are already
self-distinguishing. **Either way the `malformed` check must run outside any section.** State
which you chose and what it costs.

**`ENTRY_ID` itself is OUT OF SCOPE to change** — it is used by `parse_ledger` and others, and
changing it is a separate blast radius. **Say what changing it would break**; that is a useful
result and the next task's brief.

## Acceptance criteria — binary, and criterion 3 is the one I read first

1. **Files touched, and only these:** `watch.py`, `lint.py`, `test_watch.py`, `test_lint.py`,
   `file-formats.md`, and `.dreamwork/handoffs.md` (your worktree copy — only if your section
   decision requires reordering it). `git status --porcelain` shows nothing else.
2. **`python3 -m pytest test_watch.py test_lint.py -q -p no:randomly` exits 0**, with at least:
   - `test_a_sub_id_handoff_is_parsed_not_dropped`
   - `test_a_combined_id_handoff_is_parsed`
   - `test_a_pending_line_in_the_wrong_section_is_reported_malformed`
   - `test_an_unrecognised_id_shape_is_malformed_not_silent`
   - `test_correlation_normalises_a_sub_id_to_its_parent`
3. **THE CRITERION I CARE ABOUT MOST — the red already exists in the tree; prove it before you
   tidy it.** `#392a`'s misfiled line is sitting under `## Folded` in
   `.dreamwork/handoffs.md` **right now**, deliberately left there as your fixture. Sequence, in
   this order, and report all three verbatim:
   1. **Before your fix:** show `parse_handoffs` returning it in **none** of the three buckets, and
      `python3 lint.py` saying **nothing** about it.
   2. **After your fix, before relocating the line:** show `lint.py` **naming it loudly**. This is
      the red, and it needed **no injection at all** — a real defect caught by a real check.
   3. **Then** relocate the line so the tree ends clean, and show `lint.py` green.
   **A fix that starts by tidying the line has destroyed its own evidence** and cannot demonstrate
   step 2. That is the hollow outcome for this task.
4. **A coverage number in the OK line**, in `#395`'s idiom: how many pending, how many folded, how
   many malformed. A check that counts what it examined cannot silently stop examining things.
5. **Three further discriminating reds by injection**, each with the exact failing test name and
   confirmation neighbours stayed green: revert `HANDOFF_BARE_RE` to `#(\d+)`; move the `malformed`
   check back inside section `P`; break the parent-normalisation. Separate injections, restored from
   a `cp` snapshot — **never** `git checkout -- `. **A green red-run is a finding, never a relief**,
   and **grep your injection to confirm it reached the code, then `python3 -c "import ast;
   ast.parse(open('watch.py').read())"`** — a coordinator injection this morning left a file that
   would not parse, and `IndentationError` at collection means **zero tests ran**, which is not a red.
6. **`file-formats.md`'s hand-off row states the id grammar and the section rule** — it is free and
   it is yours. It currently says only `- **#N** · landed …`, and `#N`'s ambiguity is what allowed
   all of this. **Same commit as the code.**
7. **`python3 lint.py` exits 0** at the end, run as its **own command** — never in the same shell
   command as a `git commit`. That has committed through a lint ERROR twice here.

## The rules that matter most here

**A fallback validator shares the parser's blind axis.** That is defect 2, it is the general lesson,
and it applies to *your own* new fallback: after you widen `HANDOFF_BARE_RE`, ask what shape it
still cannot see, and say so.

**Assert the precondition your check depends on.** The malformed test's meaning depends on the line
being in a section the parser is not scanning; derive that at runtime rather than trusting a literal
fixture.

**Before you report an edge case, enumerate its neighbours.** Yours: a Pending line **before** any
`## ` heading at all; a `→ folded` line in the **Pending** section; **two** Pending lines with the
same id (a lane landing twice — does one fold silence both?); an id with a **four-digit** number
(the ledger is at #408); and a **combined** id where only one half is still open.

**`grep -c` exits 1 when the count is zero**, so an `&&` chain reports a skipped tail as a pass.

## Files

**Yours:** `watch.py`, `lint.py`, `test_watch.py`, `test_lint.py`, `file-formats.md`, and your
worktree's `.dreamwork/handoffs.md`.

**Read, do not edit:** `.dreamwork/tasks.md` (`#401`, `#406`, `#399`, `#381`, `#395`),
`.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md` (yours — §3's harness),
`.dreamwork/lessons.md`, `SKILL.md`, `justfile`.

**Do not touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`bin/ud-dw-generate`, `SKILL.md`, `watch-design.md`, and **`_landed_ids` at `watch.py:7685`** —
that is `#399`, it is 27 lines from your region, and it is the next lane. Leave it alone so the
merge is clean.

## Operational constraints

- Limit builds/tests to **2 threads**. **You need no server, no port, and no guards** — this is
  parser work and nothing renders. Do not run `just guards`.
- **Commit with `git commit --only <paths> -m …`** on branch `wt/401-406`. **Do not push** and
  **do not merge** — the coordinator merges.
- Use **`fix(#401): …`** / **`fix(#406): …`**, or one commit naming both. `dream(...)` is reserved
  for a commit that lands a dream journal; if you write one, **name it in its own
  `git commit --only <path>`**.
- Cap yourself at roughly **35 minutes**. **Priority order: criterion 3's three-step sequence
  first** (it is the evidence and it perishes the moment anyone tidies the file), then the widened
  fallback, then the sub-id/combined parsing, then the section decision, then `file-formats.md`.
  **Report what you did not reach.**

## How to report

Append **once**, at the end, in a single shell append, to the **ABSOLUTE** path — your worktree has
no copy of this file and a relative path silently creates one nobody reads:

**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`**

State: **criterion 3's three steps verbatim** (I read this first — the before-silence, the
loud-after, and the final green); each other criterion and whether it holds; your **section
decision and its cost**; your **policy decision** on the id vocabulary and whether you kept my
recommendation; the coverage numbers; the three injected reds with exact test names and which
neighbours stayed green; **what shape your widened fallback still cannot see**; what changing
`ENTRY_ID` would break; what each of the five neighbour cases does; the exact `file-formats.md`
text you added; **what you had to do to place your own hand-off line, and whether `cat >>` worked**;
and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` **in the main checkout** and say so.
