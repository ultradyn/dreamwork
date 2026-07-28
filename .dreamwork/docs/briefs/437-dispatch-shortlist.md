# Brief — #437: a dispatch shortlist, so selection stops depending on what the coordinator remembers

Repo: `ud-dreamwork`. **Work in the main checkout, READ-ONLY. Create no worktree, no branch, and change
no tracked file except the one output below.**
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that at merge time, and this lane is read-only besides.
**State which model you are** at
the top — a lane report today was labelled `grok` when `glm52` was dispatched and I am tracking that.

## Why this exists

`.dreamwork/tasks.md` is over 250,000 characters with ~144 open entries, each long by design: the detail is
what makes an entry useful individually and unreadable collectively. The consequence, stated plainly in
`#420`: **the coordinator selects work from the part of the ledger it happens to remember.** `#420`'s census
(`.dreamwork/docs/open-task-census.md`) fixed the *inventory* problem once, and it paid for itself — ten
entries claimed to be blocked on tasks that had already landed, because **a blocker that clears is
invisible from the blocked side**, nothing ever re-reading a blocked entry.

What is still missing is the *dispatch* question, which is different and is asked several times an hour:
**given these files are already owned by live lanes, what should go out next, and what would it own?**

## What to produce

**One file: `.dreamwork/docs/dispatch-shortlist.md`.** Overwrite it if it exists. Nothing else.

A **ranked shortlist of 8–12 startable tasks**, each with:

1. **id, title, priority, and origin** (`human` origin outranks `loop` — an explicit human steer beats the
   loop's own ideas, and the ledger records which is which).
2. **The file set it would own**, concretely, as paths. This is the part with no substitute: parallel lanes
   are only safe when their file sets are **disjoint**, so a shortlist without ownership sets cannot be
   dispatched from. Derive it from the entry's own text and from what the code actually touches — if an
   entry's prose does not say, look, and mark the set **inferred** rather than stated.
3. **Conflicts with the currently live lanes**, called out explicitly. As of 20:10 the live lanes own:
   `dev/capture/above_fold.mjs`, `dev/capture/devoverlay.mjs`, `justfile`'s `DEFAULT_GUARDS` (lane
   `wt/fold`, `#432`); and — check `.dreamwork/status.json`'s `dreamers` array at the time you run, because
   it is the live record and this brief's list is a snapshot.
4. **Size**, as a judgement: does it fit one ~15–20 minute increment, or does it need splitting? If it
   needs splitting, **say where the seam is.** `#432` was split tonight because it held two unrelated
   tasks under one number; that is a common shape here.
5. **Whether it is genuinely startable**, which is the claim most likely to be wrong. Rule these out:
   - anything whose blocker is a **human decision** — those wait on his desk, not on capacity. The
     `· blocked-on: **human** ·` marker exists now (`#419`, landed `c58edc4`) but **almost no entry
     carries it yet**, so you must also read the prose for *"awaiting his ruling"*, *"blocked on #N Q2"*,
     *"WITHHELD"*, *"behind a second gate"*.
   - **anything in lanes E, G or H of `#263`.** That gate is his to open, the ask is live on his desk, and
     building any of it is forbidden. Exclude and say you did.
   - anything blocked on a task that is **still open** (and note: verify the blocker is actually open —
     ten entries were wrong about this in exactly this way).
6. **One sentence on why it is worth doing now**, in the entry's own terms rather than invented ones.

Then a short closing section: **what you would dispatch first and why**, and **which two or three could run
in parallel** because their file sets do not intersect. That pairing is the actual deliverable — a ranked
list that cannot be run two-at-a-time has not answered the question.

## Constraints that matter

- **Use the production parsers, not a hand-rolled reader.** `import watch` and use `watch.parse_ledger` /
  `ledger_entries`. **Five hand-rolled ledger parsers were wrong here in a single day**, two of which
  damaged sectioned files, against a file whose production parser was importable every time. If the
  production parser cannot answer something, say so rather than writing a second one.
- **Every count derived at runtime and shown with the expression that produced it. No literal counts** — a
  literal is wrong the day after it is written, and `#420`'s own brief said "138" when the answer was
  already 139.
- **Assert your preconditions.** Confirm both section headings (`## Open`, `## Recently landed`) match
  exactly once and that Open precedes landed, and say so — an unanchored split hits a prose mention of the
  heading, a defect this ledger records twice **about itself**.
- **Read-only.** Do not modify `.dreamwork/tasks.md`, `questions.md`, `status.json`, `handoffs.md`, or any
  source file. Do not start a server, bind a port, or touch :35110. Do not run `just test`.
- If `.dreamwork/docs/open-task-census.md` is still accurate, **build on it rather than redoing it** — and
  say which of its findings you verified still hold versus carried forward. It is a few hours old and the
  ledger has moved: `#427`, `#433`, `#434`, `#435` landed tonight and `#436` was filed.

## Done means

1. `.dreamwork/docs/dispatch-shortlist.md` exists with 8–12 ranked entries, each carrying all six fields.
2. **A `doc-map.md` row** for it — the repo's doc-map says what each doc covers and a new doc without a row
   is undiscoverable. This is the one other file you may touch.
3. **At least one parallel-safe pair or triple named**, with the file sets shown to be disjoint.
4. **Counts derived and shown**, with the expression. Preconditions asserted and stated.
5. `python3 lint.py` still clean afterwards — you changed nothing it checks, so a change here means you
   touched more than you meant to.

## Practical

- `git add .dreamwork/docs/dispatch-shortlist.md` then
  `git commit --only .dreamwork/docs/dispatch-shortlist.md .dreamwork/docs/doc-map.md -m 'docs(#437): …'`
  — **`--only`, never `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps
  their staged work into yours. Commit on **master**, since you are read-only elsewhere and this is a doc.
- **Commit before you finish.**
- **This should be fast.** If it is taking long, the ranking is where to spend the time, not the prose.
- **Push back with reasons if any of this is wrong** — including if you think the shortlist is the wrong
  artifact and something else would serve dispatch better. Say so and argue it.

## Report

Say: which model you are; the top three with their file sets; the parallel-safe grouping; anything you ruled
out as not-startable and why (especially anything whose prose hides a human blocker); which census findings
you verified versus carried; and the derived counts with their expressions.
