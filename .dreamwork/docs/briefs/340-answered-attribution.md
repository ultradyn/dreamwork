# Brief — #340: his answers render as raw prose, losing their attribution, on more than half the entries

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first; its
verification rules are the reason this brief exists and they are not optional.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

## You are in a worktree

Working directory: **`.worktrees/340`**, branch **`wt/340`**. The coordinator merges it back — do
**not** push and do **not** merge. Two consequences, both silent if you get them wrong:

- **`.dreamwork/inbox.md` is UNTRACKED and does not exist in your worktree.** Appending to the
  relative path creates a file nobody reads. Use the absolute path in *How to report*. A lane lost
  its whole report that way this morning.
- **This brief lives in the main checkout** — read it at
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/docs/briefs/340-answered-attribution.md`.

**When you land your commit**, append **one line** to
**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`**:
`- **#340** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <one line, what landed>`
`cat >>` works: `## Pending` is the last section as of `#406`. Do **not** write to
`.dreamwork/tasks.md`; the coordinator is its only writer.
**Commit that line among your paths** — "write this" is not "commit this", and three lanes today
left theirs unstaged.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it. This is his own
  writing, on a page he reads, rendered as though the loop had said it.
- **Session goal**: the surfaces he reads tell the truth.
- **This task**: `#340`, **P1**, from `#254`'s design agent and verified independently by the
  coordinator. `#109` already made mis-attributed authorship a **correctness** matter here, not a
  cosmetic one.

## The defect

In `## Answered`, `_parse_entries` runs with **`lift_answer=False`** (`watch.py:8282`), so a retained
`- **Answer (via watch, …):**` sub-bullet falls into the entry **body**, and `mdB` renders it as a
`·` item **with its raw author tag visible as literal text and no `you` label**. His words lose
their attribution and read as loop prose.

This is the **same visual defect** as the screenshot he filed `#254` about, on the more-travelled
path.

**Do NOT inherit the count.** A previous measurement said 17 of 31 answered entries (~55%) at
`0f9d753`; the count moves with the file, and this morning I told two lanes to inherit a measurement
of mine that was **wrong by three orders of magnitude**. **Re-derive it at runtime** and report
before/after. The check you write must derive it too — **never pin a literal**.

## The trap: this is a one-argument fix and that is exactly why it must not be done blind

`## Answered` **also** carries the `→ answered (…)` resolution head that **`answered_at()`**
(`watch.py:8407`) reads. Lifting the bullet must not create **a second thing able to disagree with
it** about when an entry was answered.

**That shape cost this repo a P1 today.** `#399` was two checks sharing the ledger and disagreeing
about what a bold id means; the fix was to make them read **different fields**. Before you change
`lift_answer`, answer in your report: **after the lift, what reads the timestamp, what reads the
author, and can they ever disagree?** If they can, say so and fix it or say why it is acceptable.

## Acceptance criteria — binary, and 2 is the one I read first

1. **Files touched, and only these:** `watch.py`, `test_watch.py`, `watch-design.md`, and — only if
   criterion 5 applies — one new `dev/capture/*.mjs` plus the `justfile`'s `DEFAULT_GUARDS` line.
   `git status --porcelain` shows nothing else. **`git diff --stat .dreamwork/questions.md
   .dreamwork/answers.md .dreamwork/tasks.md` is empty** — those are the human's channels and the
   coordinator's ledger.
2. **THE CRITERION I READ FIRST — assert the outcome, both halves, derived at runtime.** For a
   **real** answered entry taken from the live `.dreamwork/questions.md`, assert that the rendered
   output **contains the `you` label** AND **does not contain the raw author tag as literal text**.
   Deriving the fixture from the real file is the point: a hand-built fixture proves the renderer
   works on input you chose, which is the failure mode `#385` shipped and `#392a` had to fix.
   **Assert the precondition**: derive at runtime that the entry you picked genuinely carries a
   retained `- **Answer (via watch…):**` sub-bullet, and assert that before asserting the rendering.
3. **The before/after count, both derived.** Report how many answered entries were mis-rendered
   before and after. **After must be 0**, and the test must compute the number rather than compare
   against a literal — the file grows every time he answers something.
4. **`answered_at()` still returns the same value for every answered entry.** Assert it across the
   **whole real file**, before and after, and say so — this is the disagreement risk above, and a
   test that only checks one entry has not checked it.
5. **`transitions.md` governs anything that appears, disappears, moves or changes.** If your change
   only alters what an existing node renders as, that is not a transition — **say so explicitly and
   write no guard**. If a `you` label *appears* where none was, that is something appearing: read
   `transitions.md` and reuse the existing idiom rather than authoring a second one. If you write a
   guard, `DEFAULT_GUARDS` is granted, because an unregistered guard gates nothing.
   **Your guard port is `39896`.**
6. **Three discriminating reds**, each with the exact failing test name and neighbours confirmed
   green: restore `lift_answer=False`; make the `you` label render but leave the raw tag in; break
   `answered_at` for a lifted entry. Separate injections, restored from a `cp` snapshot — **never**
   `git checkout -- `. **Grep each injection to confirm it reached the code, then `python3 -c
   "import ast; ast.parse(open('watch.py').read())"`** — a broken injection this morning gave
   `IndentationError` at collection, and **zero tests running is not a red**. **A green red-run is a
   finding, never a relief.**
7. **`just test` is GREEN**, in full, quoted. It was red on master until an hour ago, so do not
   assume — and it runs browser guards, so if one reds, **re-run at low load before reporting it**;
   load manufactures **false reds only** for those. Check `cut -d' ' -f1-3 /proc/loadavg`.
8. **`just audit-styleguide` passes** and `watch-design.md` documents the change **in the same
   commit**.
9. **`python3 lint.py` exits 0**, run as its **own command**, never in the same shell command as a
   `git commit`.

## The hollow outcome

**Flipping `lift_answer` to `True` and asserting the flag.** A test that asserts the argument rather
than the rendering proves nothing about what he sees, and this defect is entirely about what he sees.
Criterion 2 exists for that.

## The rules that matter most here

**One value must come from outside the system.** Criterion 2's fixture is a real entry from the real
file, not one you wrote to match your renderer.

**A count is the only thing a silent skip cannot fake** — hence criterion 3's before/after.

**Before you report an edge case, enumerate its neighbours.** Yours: an answered entry with **no**
`Answer (via watch…)` bullet at all (loop-resolved); one with **two** such bullets (a threaded
follow-up); one whose answer bullet contains a **nested list**; an entry answered via a channel other
than `watch` (the tag differs); and an entry in `## Open` that happens to contain the same bullet
shape — **that last one must not change**, since `## Open` already uses `lift_answer=False`
deliberately.

**`grep -c` exits 1 when the count is zero.**

## Files

**Yours:** `watch.py`, `test_watch.py`, `watch-design.md`, and — only under criterion 5 — one new
`dev/capture/*.mjs` and the `justfile`'s `DEFAULT_GUARDS` line, plus one line in the main checkout's
`.dreamwork/handoffs.md`.

**Read, do not edit:** `.dreamwork/questions.md` and `.dreamwork/answers.md` (**the data — read
only**), `transitions.md`, `file-formats.md`, `.dreamwork/tasks.md` (`#340`, `#254`, `#109`),
`.dreamwork/lessons.md`, `justfile`, `CLAUDE.md`.

**Do not touch:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/answers.md`,
`.dreamwork/status.json`, `SKILL.md`, `lint.py`, `file-formats.md`, `bin/ud-dw-generate`.

## Operational constraints

- Limit builds/tests to **2 threads**. Guards bind **39890-39899**; yours is **39896**.
- **Commit with `git commit --only <paths> -m …`** on `wt/340`, and `git add` any **new** file first
  — `--only <directory>` silently skips untracked ones. **Do not push, do not merge.**
- Use **`fix(#340): …`**. `dream(...)` is reserved for a commit that lands a dream journal; if you
  write one, name it in its own `git commit --only <path>`.
- Cap yourself at roughly **35 minutes**. **Priority order: criterion 2's runtime-derived assertion
  first, then criterion 4's `answered_at` invariant, then the fix, then the count, then the
  styleguide.** Writing the assertion first is deliberate: it is the instrument this defect got past.
  **Report what you did not reach.**
- **Commit as you go.** A lane finished this task's predecessor and **died before committing**; the
  work survived only because it was in a worktree. Land a coherent commit early rather than one at
  the end.

## How to report

Append **once**, at the end, in a single shell append, to the **ABSOLUTE** path:

**`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`**

State: **criterion 2's runtime precondition and the exact rendered strings, before and after** (I
read this first); the **before/after mis-rendered counts and how you derived them**; **what reads the
timestamp and what reads the author after your change, and whether they can disagree**; the three
reds with exact test names and neighbours green; whether the change is a transition and so whether
you wrote a guard, and the load at which any guard verdict was taken; the `just test` result in full;
the exact `watch-design.md` text you added; what each of the five neighbour cases does; whether you
wrote **and committed** the hand-off line; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` **in the main checkout** and say so.
