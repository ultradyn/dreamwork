# Questions for the dreamer

## Open

## Answered

- **2026-07-28 — I cannot see any question for #264 in the webui, how am I meant to provide a…** → answered
  (2026-07-28 15:24): **You are right, it was my failure, and it is fixed two ways.**

  **The question now exists** — `#264: ratify the task-transition boundary, and one deployment call
  only you can make`, at the top of `/questions`, P1, with the artifact
  `.dreamwork/review/task-transition-boundary.html` linked from the dashboard's review list. Two
  questions, not six: ratify the boundary (rec: yes), and the git-portability call that is genuinely
  yours because a SQLite store is machine-local while today's committed ledger means the burndown
  works on a fresh clone (rec: gitignore the DB, commit a deterministic text export of the event
  log). You can rule on both from the composer.

  **How it happened, plainly.** The design landed at `914648c` with its artifact at 01:47 and **the
  ask was simply never filed.** Then at 15:02 I answered your sqlite question by telling you
  ratifying `#264` was *"the only thing of this chain on your desk"* — so I named a blocker, told you
  it was yours, and gave you nothing to act on. The web UI was never the problem: it answers entries
  that exist, and this one did not exist.

  **Your structural point is filed as `#419`, P1**, and I have written the invariant so it can be
  checked rather than remembered: *every open task whose blocker is a human decision has a
  `questions.md` entry that is either **open** or **answered-but-unfolded** — both are legitimate
  states, **absent is not**, and absent is a lint ERROR.* That is your *"there always has to be an
  answer in our data"* turned into one assertion.
  **The honest catch, and it is why `#419` is not a one-liner:** a task cannot currently *say* it is
  blocked on you. Today that lives in prose — *"awaiting his ruling"*, *"blocked on #264 Q2"*,
  *"withheld behind a second gate"* — and prose is not checkable. So the marker has to be designed
  into `file-formats.md` first (a `blocked-on: **human**` field, or a `gate:` naming the question),
  in the same commit as the check. A check over a field nobody fills would be exactly the hollow
  check this repo has spent the day learning to distrust.
  I also added the reverse direction, which is the cheaper error and equally invisible to you: an
  entry you have already **answered** that sits unfolded is also a stall, and `lint` already has the
  idiom for it (it derives *"3 of 51 answered entries have no resolution date"* today).

  **One thing I will not claim:** `#419` is filed, not built. Until it is, the guarantee is my
  discipline rather than a check — so if you ever believe you are blocking something and cannot find
  the question, that is a bug in the loop and worth telling me exactly as you just did.

  **Human:** I cannot see any question for #264 in the webui, how am I meant to provide a ruling?
  (Note: we must have a way to do this via the webui, and we should structure things in such a way
  that it's impossible for us to be blocked on a user decision without a corresponding question or
  sometihng either pending an answer/ruling, or that question could be answered but waiting for
  processing, but yea hthere always has to be an answer in our data for these kinds of questions.

- **2026-07-28 — Also, can you give be a bit of a rundown on how many subagents you launched v…** → answered
  (2026-07-28 15:05): **~16 lanes across ~20 dispatch attempts**, all on this repo, two running
  right now. The two ways of counting disagree, and the disagreement is the part worth knowing.

  **The hard count, from `~/.local/state/cc-w/ccc/runs/`: 50 ccc invocations in 13 hours** — 19
  produced substantial output (≥5k), 19 small, 3 were one-line probes, and **9 died producing
  nothing at all**. That last bucket is mostly the `grok-4.5` 401 you just fixed.
  **The caveat is a real gap:** a ccc run directory holds only `output.txt` and `transcript.txt`
  — **no record of the prompt** — so I cannot separate lanes *I* dispatched from subagents the
  lanes themselves spawned. 50 is an upper bound on my dispatches, not a count of them.

  **What they did, from the durable record (ledger + `dogfood-orchestration.md`):**

  - **Batch 1, 05:11–05:52 — four lanes, all landed.** `#382` plugcmd race (`@oc-glm52`, 19m),
    `#383` three motion guards (`@grok`, 38m), `#354` filebytes plan (`@pi-glm52`, 25m, design),
    `#384` two-line selector (`@pi-glm52`, 18m).
  - **`#263`'s journal implementation — five lanes.** A/digest (`@grok`, 12m), B/journal
    (`@grok`, ~20m), C/domain files (`@pi-glm52`, ~45m), F/CLI (`@glm52`, ~35m), B second batch
    (`@grok`, ~25m). E and H stay withheld behind your second gate.
  - **`#386`** gitrow 0px-open, and **`#300`** the run-mode hover popover (`@grok`, closed
    `97c4fac`+`a6959cf`) — that one found that *my* acceptance criterion was unsound.
  - **`#399b` — four dispatches on one task.** Two killed by the 401 with no artifact, one by my
    own bad measurement. The most expensive hour of the day, and invisible where I was looking
    because I dispatched with `> /dev/null 2>&1`.
  - **`#331`** one ledger-span definition (`@glm52`, landed `cb476a7`, recovering 19 ids that
    were invisible to every reader) and **`#411`** the `answered_at` anchor (`@glm52`, landed
    `1f01a95`) — two dispatches, the first stopped by my own harness at ~1 minute.
  - **Running now:** `#402a` status_sync liveness (`@glm52`) and `#367` the A/B/C previews you
    asked to see (`@grok`, routed there for vision).

  **Three findings worth your time:**

  1. **Six of the first nine lanes refuted something their brief stated as established** — and
     each refuted claim sat in the passage I had measured most carefully. Three error classes: a
     wrong causal story attached to a correct measurement; a check that cannot observe its
     subject; a red line naming the wrong layer. **Both runners produced work that corrected me**,
     which is the property worth selecting for. Two brief lines bought that, about thirty words:
     *disbelieve a green red-run*, and *you may contradict this brief*.
  2. **From 05:52 to 14:50 the fleet was one alias**, so most of today's "comparison" is one
     runner measured repeatedly rather than two compared. Your key refresh is what makes the two
     lanes running now the first honest side-by-side.
  3. **Parallel lanes are capped by this repo's verification, not by the models.** The guards bind
     fixed ports and `just test` cannot run twice at once, so lane count is limited by the test
     harness.

  **Runner shape, tentatively:** `@grok` is markedly faster and is the only multimodal option, so
  vision work routes there by capability rather than preference. `@glm52` produced the single best
  artifact of the day. Neither has produced work that was wrong in a way I did not catch.

  **Human:** Also, can you give be a bit of a rundown on how many subagents you launched via ccc
  in the last 12 hours or so and what they did, please?

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
