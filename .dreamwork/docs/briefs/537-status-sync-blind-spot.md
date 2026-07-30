# Brief — #537 status_sync must not prune lanes it cannot see

**Lane-owns:** `status_sync.py`, `test_status_sync.py`
**Read, do not edit:** `.dreamwork/docs/findings/423-dead-runner-audit.md`
(the topology facts — verified file:line citations), `SKILL.md` (the
`.dreamwork/status.json` durable-state entry), `lint.py` (the status.json
checks).

## Task

#537 (open in the store, verified 2026-07-30; origin: a live incident this
session). `status_sync.py`'s `dreamers` field is DERIVED (`DERIVED =
("queue", "current_task_ids", "dreamers")`, status_sync.py:72) from live
`ccc @` processes (`live_lanes`, :146: pid-liveness via `kill -0` with a
brief-path fallback). Under the current dispatch topology (DREAMWORK.md
:364-370: the harness's native `spawn_subagent`, since 2026-07-29 18:02)
lanes are harness clones — no `ccc` process exists, no pid to probe, no
`wt/*` worktree registration (the #423 audit verified: independent `.git`,
absent from `git worktree list`). The live instance: `just status-sync`
ran while FOUR spawn_subagent lanes were alive and rewrote `dreamers` to
empty — a live fleet pruned to 0 by a tool that could not see it. The
author-owned `agents` field (coordinator-written, carries each lane's id/
task/owns/model) held the truth and was left alone — but anything reading
`dreamers` (the dashboard) saw a lie.

**The fix shape (a direction, not a prescription — refute it with evidence
if the code says otherwise):** distinguish "no ccc lanes visible" from "no
lanes". The derivation must never let an observation that is BLIND to a
dispatch form clobber records of that form. Options the lane should weigh
(IGC only if they are genuine rivals): (a) when zero `ccc` lanes are
visible, leave any existing `dreamers` untouched (absence of evidence is
not evidence of absence — but then a genuinely-dead last ccc lane never
prunes); (b) prune only entries the derivation can actually evaluate
(ccc-dispatched, pid-carrying) and carry entries of unobservable forms
verbatim, with the shape declared in the file so a reader can tell which
is which; (c) record the derivation's blind spot explicitly in the field
(a `dreamers_note` or per-entry provenance). The audit's Q3 refutes
extending the registry to enumerate harness clones as TOO BIG for this
gap — do not rebuild lane discovery here; this is about not lying with
what the tool already has.

## Hard constraints (the repo's, all measured)

1. **Worktree only.** Edit nothing in the main checkout. Commit with
   `git commit --only <paths>` (new files need `git add` first).
2. **Red-first, per ARM.** Every new check: sabotage the production line
   it binds (name that line in the docstring), watch it FAIL, restore
   byte-identical with `cp` — never `git checkout`. If the fix branches
   (observable vs unobservable entries), the red set names an injection
   per arm (the #274 gate lesson, lessons.md 2026-07-30: the path you
   were told to fix gets bound, the sibling arm is the one that ships
   unbound). A green red-run is a finding, never a relief.
3. **Preconditions derived at runtime** — if the fixture needs a state
   the check depends on (e.g. a dreamers entry whose form the derivation
   cannot observe), the fixture builds it and ASSERTS it is that form,
   or the check is vacuous.
4. **Targeted pytest + lint only:** `python3 -m pytest test_status_sync.py
   -q` and `python3 lint.py`; never `just test`, never the guard suite,
   no servers, no ports.
5. **Honest about the other direction too:** a genuinely-dead ccc lane
   must STILL prune (the existing liveness tests must stay green
   UNCHANGED unless one pins the old clobbering behaviour — if one does,
   name it and repin with the reason in the commit message).
6. **Hand-off:** append ONE line to the main checkout's
   `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`
   `## Pending` (absolute path) and COMMIT it among your paths.
7. No `attn`, no `pkill -f`. Report durable state changed. Note the
   model running you is glm-5.2 (from the dispatch record — repeat it,
   a lane cannot know its own model).

## Acceptance

- A live fleet of spawn_subagent lanes (represented as author-owned
  `agents`/unobservable `dreamers` entries per the chosen shape) survives
  `status_sync` intact; a dead ccc lane still prunes; the derivation's
  blind spot is named in the code (comment or field) so the next reader
  does not re-learn it by incident; full `test_status_sync.py` green with
  each new check red-proved; `lint.py` no new findings.
