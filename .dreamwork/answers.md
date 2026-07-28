# Questions for the dreamer

## Open

- **2026-07-28 — Also, can you give be a bit of a rundown on how many subagents you launched v…**
  Also, can you give be a bit of a rundown on how many subagents you launched via ccc in the last 12 hours or so and what they did, please?

## Answered

- **2026-07-28 — Did we do the migration to sqlite yet?** → answered
  (2026-07-28 15:02): **No — nothing is in a database.** `tasks.md` is still the ledger and
  every tool still parses it. No schema exists, no migration script has been written.

  **What IS built, so the gap is not what it looks like.** `#263`'s journal is largely
  implemented — lanes **A** (digest), **B** (journal, both batches), **C** (domain files) and
  **F** (CLI) all landed. `#264`'s transition-boundary **design** landed at `914648c` with its
  review artifact. `#346`'s design — the entity schema and read-only CLI, the half of `#294`
  that is *not* gated on `#263` — landed too and narrowed its open questions to four.

  **One thing is on your desk, and it is the only thing of this chain that is.** Ratify
  `#264`'s design: `.dreamwork/review/task-transition-boundary.html`. It decides where a task
  transition durably lives, and its answer is **neither of the two options you named** — *"never
  dual-write two fallible truths"* forbids storing one fact twice, not storing two facts, and
  *"he asked for this at 14:11"* and *"the loop started #264 at 01:47"* are two facts whose whole
  relationship is a foreign key. The shape: one row appended to an append-only `task_event` log,
  in the **same SQLite file** as `#263`'s journal, in the **same transaction** as the CAS that
  moves `task_state`. Until you rule, building the transition half means designing against an
  unsettled model — the double migration you have warned about twice.

  **One thing is on ours, and it is NOT blocked, and it has not started.** `#346`'s next
  increment is eight red-first fixtures, and they can be written before any ruling because each
  names the production line that must change for it to fail. That is the honest answer to *"what
  else is required first"*: for the schema half, **nothing** — we simply have not started it.
  Today went to verification debt (three guards red since 07:00 that turned out to be encoding a
  superseded contract rather than flaking) and to `#331`/`#411`/`#414`. Worth saying plainly
  since you marked `#294` next-up at 23:33 yesterday.

  **The order from here:** the eight fixtures now → your `#264` ruling → create the schema →
  the migration script's parse-and-report half (dry-run, exact counts, digests, conflicts) →
  verified cutover with rollback, keeping `tasks.md.deprecated`. `#263`'s lanes **E** and **H**
  stay withheld behind your second gate and the migration does not depend on them.

  **Human:** Did we do the migration to sqlite yet? What else is required first?

- **2026-07-27 — Test question, how you doing?** → answered
  (2026-07-27 11:32): Doing well — hot mode is active. #138/#156 just landed;
  #158's stale guard fix is review-PASS and ready to merge; #234 is in progress.
  A full browser-guard sweep also found two more red guards (`dashboard` and
  `answers`) that I am diagnosing. Dashboard PID 2583034 remains healthy.

  **Human:** Test question, how you doing?

- **2026-07-27 — What are the task dependencies of the run mode task?**
  → answered (2026-07-27 01:57): **Modes 1–3 have no hard dependency and I
  have sent the implementation to Grok.** The implementable v1 is:
  `lackadaisical`, `hot`, and `assisted`, backed by authoritative local
  `.dreamwork/run-mode`, mirrored into status, and emitted as one coalesced
  event after the resettable 10-second dashboard countdown.

  Only the proposed **hierarchical/many-agent** tier is dependency-blocked: it
  stays visible but disabled until #264 defines concurrent task ownership and
  #288 defines real containment/authority. #229/#270 are coordination inputs,
  not blockers for modes 1–3. Grok may use several disjoint read-only subagents
  for design, tests, and review while remaining the sole writer in its exact
  worktree. It will first finish the small new-commit #292/#293 stale-request
  lifecycle correction found by fresh review, then take #290 through red-first
  implementation and exceptional visual verification.

  **Human:** What are the task dependencies of the run mode task? If there are
  none, please send it to grok. you can send more tasks than you think -- it is
  fast and has subagents.



- **2026-07-27 — Do we have a task for SQLite/tool-based task access?**
  → answered (2026-07-27 01:19): **Yes, partly: #264 was already the broad
  design task.** It covers concurrent-safe task ownership, SQLite, CAS/leases,
  multi-process same-target access, and migration; it is blocked on the #263
  user-event model. But it did not state the concrete tool seam or safe
  `tasks.md` retirement strongly enough.

  I have now extended #264 to require a public tool/CLI seam such as `dreamwork
  tasks list|get|grab|cycle`, and added dependent implementation task **#294**.
  #294 explicitly requires a readable, user-modifiable migration script with
  dry-run, exact import reporting, atomic backup/import, verification, rollback,
  mixed-writer cutover, and provenance/history handling. After successful
  verification it keeps the old ledger as `tasks.md.deprecated`—never deletes
  it—and adds YAML frontmatter saying it is deprecated and pointing to canonical
  task access plus recovery instructions. Dashboard/lint/docs/compaction
  consumers are in scope too.

  **Human:** “do we have a task yet for migrating tasks stuff to sqlite? Maybe
  that was in something I reviewed? Anyway it was to do with working towards
  allowing simultaneous access to tasks for multiple agents. Part of that I
  would think would be migrating to a tool based way to access tasks. like
  dreamwork tasks list etc. is that right, do we have that as a task yet? If so,
  I would like to extend it to make sure we include a script (which can be
  modified by the user's agent if need be) that is intended to migrate the
  tasks.md file to the sqlite DB (it should also add some yaml frontmatter about
  it being deprecated and point to instructions for how to get tasks, and should
  rename to like tasks.md.deprecated or something (keep it around in case
  something goes wrong)).”

- **2026-07-27 — #283 safe Dolphin-window falsification observation**
  → answered: the authorised 60-second observation saw zero events, but two
  later holderless recurrences at 00:46 and 00:57 falsified the strong
  closed-window interpretation. The exact creator remains unknown; a new
  dashboard question gates bounded audit preparation, user-tracer research, or
  stopping with unknown. No privileged tracing or host mitigation is authorised.

- **2026-07-26 — What causes the pause between answer and question movement?**
  → answered (2026-07-26 14:00): it is mostly an intentional **1.6-second
  client-side rerender hold**. After `POST /answer` succeeds, `sendAnswer()`
  immediately restates the existing card as `answered · awaiting fold`, lifts
  the answer text from the textarea, and starts the card/neighbour travel.
  That travel is nominally 850ms, while `holdRerenderUntil = Date.now() +
  1600` prevents the live `/mtime` tick from replacing the DOM until the
  confirmation morph has settled. The visible consequence is roughly 750ms
  of quiet after the first animation.

  The second movement begins on the first eligible live tick that sees the
  changed file. `tick()` recurs every 2 seconds, so the exact pause also
  depends on poll phase: a poll just after the hold regroups promptly; one
  arriving just before it waits another cycle. The later coordinator move
  from `## Open` into `## Answered` is separate and not a fixed part of this
  middle pause. This separation was introduced deliberately so a tick cannot
  replace the card during the answer-submit morph; `morph.mjs` traces the
  first 1400ms inside the hold, while `regroup.mjs` proves the later live-data
  movement.

  **Human:** When submitting an answer to a question, it animates first the
  answer, then pauses for about a second, then animates the question as it
  moves into answered · awaiting fold. What causes the middle pause?

  **Update (2026-07-27, #234):** the hold is now a named `MORPH_HOLD_MS`
  of **1250ms**, derived from the measured critical path (flipDock's
  1150ms transform is the longest visible leg, plus a beat of slack) rather
  than padded — the quiet middle is ~350ms shorter, and
  `dev/capture/morphhold.mjs` red-proved the early release against the old
  1600ms value.


- **2026-07-26 — Can an answer re-block or reopen a question?** → answered
  (2026-07-26 13:45): an answer first leaves the dreamer's question in
  **answered · awaiting fold**. The coordinator reads and acts on it, and
  folds only when it resolves the decision. If it does not, the entry may
  remain open or receive a narrower follow-up. A later amendment on a folded
  question can reopen the same entire entry, preserving its notes and answer;
  a materially different issue becomes a new question that names the prior
  title or task. The existing linear thread is enough for this governance
  channel. #229 topic chats are the deliberate heavier model when a subject
  needs repeated fresh-agent discussion rather than one decision thread.

  **Human:** I might answer a question in such a way that could unblock the
  dreamer, or might not. How is this handled at the moment? Can a question for
  the user that gets answered be changed back to unanswered, or does the agent
  just start a new question? How does it link back to prior questions? Should
  we consider building something more complex?
