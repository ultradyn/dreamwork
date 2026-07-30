# Brief — #264 research: concurrent-safe Dreamwork state and task ownership

Task: **#264** (P1, origin human — "can a second dreamer/coordinator work in
parallel without corrupting assignments, questions, user events or task
state?"). The body predates several landings — your first job is to evaluate
the question against what EXISTS, not what the filing assumed.

## Lane-owns

- `.dreamwork/docs/findings/264-concurrent-state.md` (new file, your only write)

Everything else is READ-ONLY. Do not edit watch.py, lint.py, dev/, SKILL.md,
or any other file. Do not start servers or bind ports.

## What exists now (verify each, cite file:line)

- **#294 SQLite ledger is LIVE** — the migration the filing asks you to
  "design" already happened. `.dreamwork/ledger.sqlite3`, table `task`,
  `dev/ledger.py` verbs (counts|fold|file|note|sweep). tasks.md is a one-line
  deprecation shim.
- **User-event journal (E3) is the durable spine** — every write route
  commits a receipt before dispatch (`user_events/`), and the drain
  machinery (`dev/journal_consume.py pending|consume --through`, #501/#526/
  #531) gives exactly-once cursor consumption with an applied-proof (#526).
- **Multi-lane operation is the lived reality** — 2-5 concurrent subagent
  lanes in harness clones (independent `.git` dirs, invisible to
  `git worktree list` and lane_guard — the #423 finding), coordinator-owned
  files by convention (`git commit --only`), the #537 `dispatch` field for
  liveness.
- **Known-live defects in this exact area**: #465 (a lane can edit the MAIN
  CHECKOUT and nothing notices until a merge fails — P1, awaiting his
  consent on one half), the #423 harness-clone invisibility, two live
  instances of lanes committing directly on master (accepted after
  verification).

## The question to answer

Given THAT architecture: what breaks when a second coordinator (or a second
dreamwork loop) runs against the same target? Walk the state stores one by
one — ledger.sqlite3, user-events journal, questions.md, chats-v1,
status.json, posture, the sig store, submissions.log — and for each name the
concurrency failure mode (or why none exists: single-writer, CAS,
append-only, atomic rename). Then compare the strategies the filing lists
(single-writer+workers, append-only events/materialised views, locks/atomic
replace/CAS, leases, SQLite, per-record spools) against the failure modes you
actually found — not in the abstract. End with: what is ALREADY safe, what is
safe-by-convention-only (name the convention and its enforcement gap), and
the smallest set of changes that would make a second loop safe — ranked,
each with its cost. If a piece of the filing is mooted by what landed, say
so and cite the landing.

## Reporting

Append to `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
`[lane-264research] DONE <sha> — <one line>` plus one line per store walked
(safe / safe-by-convention / unsafe + why). Use `dev/relay.py` if present;
never `attn`. Then append one line to `.dreamwork/handoffs.md` **inside your
worktree** and commit it there:
`- **#264** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`.
Do not claim a model you were not dispatched as.
