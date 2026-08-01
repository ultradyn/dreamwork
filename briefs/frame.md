# Lane brief frame — the closing sections `dev/brief.py` emits

The coordinator retyped `## Standing rules` 33 times across the 40 most recent
briefs and produced **32 distinct bodies**; `## Live-state prohibitions` 31
times and 30 distinct. The rules themselves are stable (`never merge` 33/33,
`no attn` 31/33, `2 threads` 29/33, `--only` 27/33) — the *block* is what
drifts, so a lane's rule set depended on what the coordinator remembered at
20:40. Measurement: `.dreamwork/docs/measurements/881-brief-frame.md`.

This file is that block, written once. It carries the **union** of every rule
that appeared in a majority of blocks, not the intersection: the drift measured
above is omission, not deliberate scoping — nobody decided the 9-in-33 briefs
were the ones that needed the rebase rule.

**Corrections belong here**, same duty as `briefs/boilerplate.md`: when a lane
reports a rule wrong, missing, or unreachable, fix it in this file in the same
increment that acts on the report.

Sections are `## ` headings and are emitted in the order they appear below.
`dev/brief.py` refuses to emit a brief if this file yields zero of them — a
frame generator that silently finds nothing to template produces a brief that
looks fine and carries no rules, which is a failure mode this loop has already
had for real (a shell-quoting bug delivered a 24-character prompt and every
instrument read normal).

## Live-state prohibitions — absolute

- **NEVER open the live `.dreamwork/ledger.sqlite3` for writing.** It has a
  single writer and it is the coordinator. Read with `--ledger`; use a fixture
  for any mutating verb.
- Do not write `.dreamwork/status.json`, `.dreamwork/questions.md`,
  `.dreamwork/handoffs.md`, or anything under `.dreamwork/chats-v1/` — those are
  the human's real conversations.
- **Do not disturb another live lane.** Other worktrees are running; if your
  change collides with one, say so and coordinate rather than racing it.
- **NEVER `pkill -f` a pattern that can appear in another agent's command
  line — kill by pid.**
- Do not bind `:35110` (the deployed dashboard) or `:35113` (dev). Browser
  guards bind 39890–39899 and the hub 39880–39889; check who holds a port
  before taking it.
- The harness scratchpad is **not** lane-private (`#652`) — every concurrent
  lane inherits one session id and resolves to the same directory. Use
  `dev/lane_scratch.py`.

## Standing rules

- `git commit --only <paths>`, never `git commit -a`. Run `git add -N` for new
  files first so `--only` can see them.
- **Never `git stash` / `git stash pop`** — the stash stack is shared across
  worktrees and you would pop another lane's work.
- **You never merge and you never push.** The coordinator gates and merges.
- Name the task id in every commit subject as `verb(#NNN): <subject>`. The
  parens are load-bearing: `#NNN: <subject>` is invisible to `ledger.py sweep`
  and *looks* compliant.
- **Commit incrementally.** You can be killed without warning and uncommitted
  work is lost.
- Limit builds and tests to **2 threads**.
- **Run the full test files you touch**, plus the always-run set
  (`just pytest $(python3 dev/repo_wide_guards.py list)`). Not the whole tree —
  the coordinator owns the single full merged-tree sweep.
- Run `python3 lint.py`: require no ERRORs and compare the complete **WARN ROW
  SET** against your baseline, not the trailer count. Rows are indented, so
  `grep -c '^WARN'` returns a false `0` (`#794`). Take the baseline from a real
  file path, never process substitution, which silently reports zero rows.
- **Rebase onto local `master` before you report**, and report the sha *after*
  the rebase — a rebase rewrites shas, so a sha captured first names a commit
  that no longer exists. Local `master`, not `origin/master`, which is behind.
- **Do not use `attn`.** You report to the coordinator, who decides whether to
  ping the human. This is absolute.

## What to report back

- **The branch head sha**, captured after the rebase.
- What you changed and why, in the shape the task asked for.
- **Both directions of every red-proof.** Direction 1: the production seam you
  broke, and the *discriminating* failure message quoted. Direction 2: each
  false-green you constructed and ran, closed or open — and if you could not
  construct one, why not.
- Quote `python3 dev/redproof.py check --require 1` if an injection was owed.
- Every issue number you cite, with the line you relied on quoted.
- The rebase outcome.
- Anything out of scope that you found: name it, do not fix it.
- A **DOGFOOD REPORT** — required, not optional (`#589`). What about this
  loop's tooling, docs, or briefs cost you time or misled you? Its value is
  what you found *beyond* the direct task. "No friction found" is a valid
  answer that is **stated**; an omitted section reads as "no friction" and is
  indistinguishable from a lane that did not look.
