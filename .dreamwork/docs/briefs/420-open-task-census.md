# Brief — #420: a census of everything not done

Repo: `ud-dreamwork`. Worktree: **`.worktrees/420`**, branch **`wt/420`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

Lane-owns: .dreamwork/docs/open-task-census.md, .dreamwork/review/src/open-task-census.html

His instruction, verbatim (watch `/answers`, 2026-07-28 15:25):

> *"at some point soon, get a glm52 node to do a complete scan over our tasks and give you a report
> on everything not done so you have a concise view on it"*

The ledger has **138 open entries** and they are long — the file is over 250,000 characters. Nobody,
human or coordinator, has a view of it. **You are producing that view.**

## This is a read-only job

You change **no** behaviour and fix **nothing**. You write one report and, if it earns it, one review
artifact. Two other lanes are live and hold `watch.py`, `watch-design.md`, `justfile`,
`test_watch.py`, `status_sync.py` and `test_status_sync.py` — **do not touch any of them**, and do not
touch `.dreamwork/tasks.md` or `.dreamwork/questions.md` at all; the coordinator is their only
writer. If you find something that should change in the ledger, **say so in the report**; that is
the deliverable, not the edit.

## Use the production parser. This is not optional and it is today's most expensive lesson

`import watch` and use **`watch.parse_ledger(text)`** for open-vs-landed and **`watch.IDS_ONLY_SPAN`**
/ `watch.LEDGER_ENTRY` for entry heads. `watch.parse_open_questions` and `watch.parse_answered` for
`questions.md`.

**Four hand-rolled parsers were wrong in this repo today**, every one against a file whose production
parser was importable at the time:

- a section split on an **unanchored** `'## Recently landed'` — which matches **seven** prose
  mentions before the real heading — filed two closed tasks into the middle of `## Open`, and later
  made the coordinator claim a P1 had been falsely marked done. It had not.
- a title regex requiring `**` to close on the same line silently skipped an entry whose head
  **wraps across two lines**. Heads do wrap. `#402`'s `awaiting_human` count was 4 instead of 5 for
  exactly this reason.

So: **anchor every heading match** (`^## X[ \t]*$` with `re.M`) **and assert it matches exactly
once**, and prefer the imported parser to any regex you write. If you must write one, state in the
report which entries it found that the production parser did not, or vice versa — a disagreement is a
finding.

## What "everything not done" should tell him

Not 138 summaries — that is the file he already cannot read. A **concise view**, which means
structure and judgement. Build it in this order:

1. **The shape of the backlog, in derived numbers.** Count open by priority band, by type, and by
   age of the oldest mention. Every number derived at runtime; **no literal counts anywhere in the
   report**, because a literal is wrong the day after you write it.
2. **What is actually blocked, and on what.** Separate **blocked on the human** (awaiting a ruling)
   from **blocked on another task** from **startable now**. That third number is the one he will
   care about most: it is the answer to "what could be happening and is not". Blocked-on-human is
   currently expressed in **prose** (`"awaiting his ruling"`, `"blocked on #264 Q2"`, `"withheld
   behind a second gate"`) — there is no machine-readable marker, which is `#419`. **Report how you
   decided, and how confident you are per entry**; an honest "prose says blocked, no question found"
   list is more valuable than a clean-looking classification.
3. **Cross-check against `questions.md`, because this is where the loop has already failed him
   once.** For every entry you classify blocked-on-human, is there an entry in `questions.md` that is
   **open** or **answered-but-unfolded**? `#264` was blocked on a ruling with **no question filed**,
   and he found out by being unable to act. **List every entry with that shape.** This is the single
   highest-value section of your report.
4. **Entries the ledger and reality disagree about.** Two kinds, both real today:
   - **claimed open, actually done** — the work landed under another id or incidentally. Check
     cheaply: does the thing exist? `grep`, run the command, look at the served page
     (`http://127.0.0.1:35110/`, read-only GETs only).
   - **claimed open and genuinely unstarted, but a NEIGHBOUR landed** — `#172` is the specimen: he
     believed it was done because `#153` and `#318` both landed and both touch the title. Where a
     landed sibling could be mistaken for the open work, say so; that is what makes a backlog feel
     dishonest.
5. **Duplicates and overlaps.** `#412` was filed as new work when `#331` already covered it, better.
   Look for entries whose *symbol* overlaps (the same function, file, regex, or surface) rather than
   entries whose *words* overlap — the words diverge, the symbol does not.
6. **Stale entries**: ones whose premise has been superseded, whose blocker was cleared and nobody
   noticed, or which describe a file or line that no longer exists. `#252` was a blocker already
   cleared; assume there are more.
7. **Your recommended next five**, ranked, with one sentence each on why — and at least one that is
   *cheap and unblocks something else*, since that is the kind the coordinator systematically
   under-picks.

## Done means all of these

1. **`.dreamwork/docs/open-task-census.md`** — the report. Aimed at the coordinator: dense, no
   ceremony, every claim traceable to an id. Long is fine where it earns it; the summary at the top
   must be readable in under two minutes.
2. **Every count derived at runtime and shown with how you got it.** If you say "31 startable now",
   the report says what test produced 31. A number he cannot reproduce is a number he cannot trust.
3. **The parser cross-check** from above, stated explicitly even if it found nothing: *"parse_ledger
   and my own reader agree on all 138 ids"* is a sentence worth having.
4. **Section 3 (blocked-on-human with no question) is complete and per-entry**, because it is the one
   with a live cost.
5. **A review artifact** — `python3 review_artifact.py build .dreamwork/review/src/open-task-census.html`
   → `.dreamwork/review/open-task-census.html`, checked with `review_artifact.py check` (must report
   `current`, not `stale`/`untemplated`) — **only if** the census contains something he should rule
   on or see graphically. If it is purely a coordinator working document, say so and skip it; an
   artifact nobody needs is noise, and his rule is that a *review request* ships one, not that every
   document is one.
6. `python3 lint.py` clean, and `python3 -m pytest -q -p no:randomly` passes. **Do not run
   `just test`** — it binds guard ports 39890-39899 and another lane needs them. Say that you skipped
   it and why; that is correct here, not a gap.
7. **Report your own uncertainty per section.** A census whose weakest section is unmarked is worse
   than a shorter one, because the coordinator will act on the weak part with the same confidence as
   the strong part.

## Files

Yours: `.dreamwork/docs/open-task-census.md`, and — only if criterion 5 earns it —
`.dreamwork/review/src/open-task-census.html` plus its built output. **Nothing else at all.**
`git status --porcelain` proves it at the end.

## Practical

- 2 threads. **Do not bind ports 39890-39899.** Read-only GETs against the already-running dashboard
  on **:35110** are fine and encouraged for criterion 4.
- Commit with `git commit --only <paths> -m 'docs(#420): …'`. **`--only`, never `git add -A`** — three
  agents commit in this tree and a bare `git commit` sweeps up their staged work under your message.
  A **new** file needs `git add <file>` first.
- **Push back with reasons if any of this is wrong.** Seven lanes today have refuted something their
  brief asserted and every one was right to.
- Then append one line to `.dreamwork/handoffs.md` **inside your worktree** and commit it there:
  `- **#420** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`.
  Do **not** write it to the main checkout's copy — that lands the same line twice and blocks the
  merge.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`.

Say: the derived headline numbers (open, startable now, blocked on him, blocked on another task);
**the complete list from section 3**; how many ledger-vs-reality disagreements you found and the two
or three most consequential; your recommended next five; whether you built an artifact and why or why
not; and **which section of your own report you trust least**.
