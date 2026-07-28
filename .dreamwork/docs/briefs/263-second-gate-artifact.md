# Brief — the review artifact for #263's second gate

Repo: `ud-dreamwork`. Worktree: **`.worktrees/gate`**, branch **`wt/gate`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: .dreamwork/review/src/263-second-gate.html, .dreamwork/review/263-second-gate.html

## What you are building and why it has to be good

He has to make three authorisation calls on `#263` and there is nothing for him to look at. The ask
went into `.dreamwork/questions.md` at 16:24 (top entry, `#263: A-D and F are all landed. Open the
second gate, or don't?`) — **read that entry first; it is the specification of what the artifact must
answer**, and its standing rule is that every request for a ruling ships a self-contained HTML
artifact.

The plan's own artifact, `.dreamwork/review/user-event-journal-implementation.html`, **predates the
lanes landing** and shows the plan as authored, not as executed. That is the gap you are closing.

**The three questions, in his priority order:**

- **Q1** — open the gate for **lane E** (increments 20–25, the HTTP cutover)?
- **Q2** — open it for **lane H** (34–35, the mixed-version gate)?
- **Q3 — the one he most needs to see, and the reason this is a visual job.** Lane E's six
  increments all live inside the single large `watch.py`, and lane G would too. **His own note in
  the plan** says *"lanes E and G both live inside the one 8,647-line `watch.py`, so they are a
  single lane in practice. That is an argument for #368 (the modular split) landing before the
  second gate opens."* So: **split first (a batch's delay, then parallel lanes), or run E serially
  now (a P1 fixed sooner, one big blast radius)?** He needs the trade-off *shown*, not described.

## Derive every number. I have been wrong about this document's numbers twice today

**Do not copy a figure from this brief or from the questions entry** — including `8,647`, which was
true when the plan was written and may not be now. Every number in the artifact is computed by you
at build time from the repo, and the artifact says **how** each was obtained. Two figures the
coordinator handed a lane today were wrong (`214px` for a measured `167.9px`; an `open=138` literal
already stale), and both were derived-by-reasoning instead of measured.

Specifically, measure at least: `watch.py`'s current line count; how many of lane E's increments
touch `watch.py` versus new files (read the per-increment rows, plan lines ~71–76 and the detailed
sections); the landed lanes' actual commit shas and dates (`git log`); and the test counts each lane
added (`git show --stat`). **If a number you measure contradicts the plan or the questions entry, say
so in your report — that is a finding, not an inconvenience.**

## The evidence half — "proved" is the word his condition turns on

His 05:43 condition was *"until A–D are proved"*, so the artifact's job is to let him judge whether
they are. Not a green tick per lane: **the actual evidence**, per lane, compactly.

Lane commits: **A** `aad1d8d` · **B** `6a865e4`..`bc731cf` (two batches) · **C** `3f1a6af`, `8c1bb60`
· **D** `6cd9f95` · **F** `2386345`. Verify each with `git log`/`git show` rather than trusting this
list. Read their commit **messages** — they are unusually substantive and contain the strongest
evidence in the repo:

- **Lane D's message reports finding a hollow red inside itself** — the body-digest predicate lived
  in two places, so deleting the copy under test changed nothing — and consolidating it to one line.
  **Surface that.** It is the difference between "the tests pass" and "the tests were proved capable
  of failing", which is exactly what he means by *proved*.
- **Lane B's `B7` red came back GREEN** (removing `UNIQUE(client_action_id)` left the suite passing)
  and the lane reported it rather than hiding it. That is also evidence, of a different kind: it is
  a known hole, and he should see that it is known. Check whether it was subsequently closed and say
  which.

**Do not flatten these into a status table.** A lane that found a hole in its own proof and a lane
that reported none are not the same fact, and a green row makes them look identical.

## What opening the gate does NOT authorise — this section must be impossible to miss

Lane **G** (30–33) was never in G1 and stays withheld whatever he decides. Increment 18's active-store
purge and increment 19's PostgreSQL half stay `UNPLACEABLE` per his Q4 ruling. **No migration of a
live target.** Lane H's fixture is *code and temp targets only*.

He has been given an artifact before whose limits were in prose at the bottom; a boundary that only
appears as a paragraph is one he can ratify without seeing.

## The honest provenance, and do not soften it

The artifact must state why it exists now rather than at 07:25 when the condition was met: at 16:14
the coordinator **dispatched a lane onto withheld work** (`#371` = increment 20 = `E1 envelope` =
lane E), having read his *"Q2 yes"* as authorisation when it amended the design. Killed at 16:20,
nothing committed, retracted at `6ea8f6b`. Lane D had landed at 07:25 and was **never recorded** in
`#263`'s ledger entry, so the entry could not show its own condition was met.

**Nine hours, and it was found by walking into the gate rather than by checking.** Put it in plainly,
near the top, not in a footnote. He is deciding how much to trust the gate mechanism, and that is
data he is entitled to.

## Done means all of these

1. **`.dreamwork/review/src/263-second-gate.html`** exists, and
   `python3 review_artifact.py build .dreamwork/review/src/263-second-gate.html` produces
   `.dreamwork/review/263-second-gate.html`. **`python3 review_artifact.py check` reports `current`**
   for it — not `stale`, not `untemplated`. Quote the check output.
2. **Self-contained and offline-clean**: no external fetches of any kind — no CDN, no webfont, no
   remote image. Inline every style, script and asset (data URIs where you need one). **Verify it,
   don't assert it**: grep the built file for `http://`/`https://` outside of link text and say what
   you found.
3. **Q1, Q2 and Q3 each have their own clearly-marked section with a recommendation and its
   reasoning**, and Q3 has a **visual** comparison of split-first versus serial-now — the two
   sequencings side by side with what each costs and buys. Inline SVG or CSS; no chart library.
4. **Every number derived at build time with its provenance stated in the artifact.** A figure he
   cannot reproduce is a figure he cannot trust.
5. **The evidence-per-lane section**, with lane D's hollow red and lane B's green red both visible as
   the distinct things they are.
6. **The does-not-authorise boundary is structurally prominent** — its own block, visually distinct,
   not a trailing paragraph.
7. **It matches the repo's dark-mode design language.** Read `watch-design.md` for tokens and type,
   and look at two existing artifacts (`.dreamwork/review/task-transition-boundary.html`,
   `.dreamwork/review/user-event-journal-implementation.html`) before writing any CSS. **Reuse the
   idiom; do not author a second one.** If the template system gives you tokens, use them rather than
   hex literals.
8. **Look at your own output.** You were chosen partly because you can see. Render it desktop and
   mobile, capture both, and give **your own visual verdict**: can he find the three questions
   without scrolling hunting? Does the boundary block read as a limit or as decoration? Is anything
   unreadable at normal reading size?
9. `python3 lint.py` clean. **Do not run `just test`** — it binds guard ports 39890–39899 and another
   lane holds them. Say that you skipped it and why; that is correct here, not a gap.

## Files

Yours: `.dreamwork/review/src/263-second-gate.html` and its built output
`.dreamwork/review/263-second-gate.html`. **Nothing else at all** — `git status --porcelain` proves
it at the end.

**Not yours:** `file-formats.md`, `lint.py`, `test_lint.py` (another lane holds all three right now),
`watch.py`, `watch-design.md` (read-only for you), and `.dreamwork/tasks.md` /
`.dreamwork/questions.md` — the coordinator is their only writer. If the questions entry needs
correcting, **report the exact lines**; do not edit it.

## Practical

- 2 threads. **Do not bind ports 39890–39899.** Read-only GETs against the running dashboard on
  **:35110** are fine.
- `git add <file>` for each new file, then `git commit --only <paths> -m 'docs(#263): …'`.
  **`--only`, never `git add -A`** — other agents commit in this tree and a bare `git commit` sweeps
  their staged work into your commit under your message.
- **Push back with reasons if any of this is wrong.** Nine lanes today have refuted something their
  brief asserted and every one was right to. In particular: if you think the split-first
  recommendation is wrong, or that the artifact should not carry the provenance paragraph, say so
  with your reasoning before building to it.

## Report

Say: the `review_artifact.py check` output verbatim; every number you derived and the command that
produced it, flagging any that contradicted this brief or the plan; whether lane B's `B7` hole was
later closed and by what; your offline-clean verification method and result; and **your own visual
verdict** on the desktop and mobile renders.
