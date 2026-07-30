# Dreamwork initialization

Run this once per session, at loop start or on resume — not on every reload
of SKILL.md. If the heartbeat is already armed and DREAMWORK.md has been
read, initialization has already happened; return to the loop.

1. **Target.** Confirm which project the loop is dreaming on (default:
   the session's cwd). Every later step is relative to the target.

2. **DREAMWORK.md — read first.** Look for `DREAMWORK.md` at the target's
   root — the persistent memory of what the human wants from this project.
   If it exists, read it before anything else: it holds the human's very
   high-level goals, the project's philosophy, working preferences and
   routines, and plugin decisions. Its goals are where every chain of
   work terminates. If it doesn't exist, note that — the wizard (step 4)
   will create it.

3. **Plugins.** `ud-dreamwork-*` packages are plugins to this loop; they
   may extend later initialization steps (including the wizard) and the loop
   itself. They are deliberately absent from ordinary harness skill discovery:
   a plugin exists for this target only when `DREAMWORK.md` records its exact ID
   under `## Plugins` as `- Load: `…``.

   Resolve declarations with the core's bounded loader:

   `python3 <skill-dir>/plugin_resolver.py --target <target>`

   A noncanonical package location must be supplied explicitly with
   `--path <id>=</path/to/SKILL.md>` (one exact package) or `--root
   <package-parent>` (a controlled package parent). The resolver checks bundled packages,
   the canonical sibling package location, then explicit roots; it never scans
   global skill directories. Read its bounded JSON, then **read each emitted
   `SKILL.md` directly** and follow that plugin before continuing. Do not invoke
   `/skill:<plugin>` or depend on an available-skills inventory: those surfaces
   are intentionally absent while Dreamwork is inactive. Missing, invalid,
   duplicate or ambiguous declarations fail initialization with the resolver's
   searched paths; never silently drop a recorded plugin.

   Recorded negatives remain durable reasons not to add a Load declaration.
   Installing or proposing a new plugin is an explicit human action/ask: on yes,
   install it outside ordinary discovery roots and record its ID under Load; on
   no, record it under Don't load. A target with no Load declarations loads
   none and is not prompted merely because a package exists on the machine.
   No `DREAMWORK.md` yet means no plugins until the wizard records an explicit
   decision. (Authoring guide: `writing-plugins.md`.)

   **Then write the loaded plugins' commands into the target**, because
   `watch.py` reads the target and cannot see a plugin's own files —
   they live in harness-specific skill directories that vary by machine.
   With at least one plugin loaded, write
   `.dreamwork/plugin-commands.json` **whole** from the declarations in
   every loaded plugin's SKILL.md; with none loaded, **remove the file
   if it is there**. Never append. That is what makes unloading a plugin
   the *absence of a write* rather than a deletion someone has to
   remember, so a command the human can send but nothing answers cannot
   survive an init. Shape and the rules `lint.py` enforces (namespacing,
   no shadowing a core command): `file-formats.md`. A plugin that
   declares no commands is normal — write `{"commands": []}`.

   A plugin may still be installed/declared mid-session through an explicit
   human action or answered proposal. Resolve it with the same CLI, record the
   decision, read its emitted `SKILL.md`, and run its init extension immediately
   (discovery, wizard questions, monitors), with no session restart. Unanswered
   proposals follow the questions.md discipline. **A yes also rewrites
   `plugin-commands.json` whole**; a mid-session load that skipped it would leave
   the composer unable to send the commands the plugin just promised.

4. **Setup wizard (only when DREAMWORK.md is absent).** Runs after plugins
   so loaded plugins can extend or reshape the interview. A short
   interview, not a questionnaire — smooth, and sized to the human:
   - Elicit as much as the human wants to give, and no more. Partial
     answers are first-class: skipped sections keep their template
     comments as visible unfinished markers, and the file fills in
     incrementally later as the human adds ideas and preferences.
   - When the repo already says a lot (CLAUDE.md, README, code), propose
     drafted answers and ask what's wrong or missing — don't ask cold
     open-ended questions the repo can answer.
   - One topic per message. Answers often spill across sections; file
     each point where it belongs instead of re-asking.

   Ask about, in order:
   - *Goals* — very high-level, human-focused: what does the human want
     this project to be or do for them/its users? (We should always know
     what the human wants so we can make what the human needs.)
   - *Philosophy* — values and taste that should shape decisions (e.g.
     "feels alive and communal", "boring tech, exciting product").
   - *Preferences & routines* — cadence, communication style, autonomy
     bounds (push/deploy?), recurring chores worth scheduling.
   - *Plugins* — confirm the step-3 decisions, positive and negative.
   - Any questions contributed by loaded plugins.
   Write the answers to `DREAMWORK.md` — start from `DREAMWORK.template.md`
   in this skill's directory (sections: Goals, Philosophy, Preferences &
   Routines, Plugins; replace the guidance comments with real content) —
   confirm it back to the human, and treat it as committable project
   content.

   Also ensure the target repo's `.gitignore` covers the machine-local
   dreamwork state (`.dreamwork/status.json`, `ledger.sqlite3`, `run-mode`,
   `submissions.log`, `chats-v1/`, etc.). `gitignore.example` in this
   skill's directory is the copy-paste block — point the human at it or
   add the lines directly.

5. **Heartbeat.** Start the wake timer — 4.75 min stays under the 5-minute
   prompt-cache TTL, keeping the loop cheap. The message carries the
   micro-protocol, and — because monitor text survives compaction while
   conversation context may not — a self-recovery clause:

   `Monitor command="heartbeat 4.75m 'dream tick (ud-dreamwork): run the tick flow; keep the task list truthful; reflect — reload the ud-dreamwork skill if this means nothing to you'" triggerTurn=true persistent=true`

   No regex filter. (Same mechanism as the heartbeat-monitor skill.)

   If the `heartbeat` CLI is absent, use the vendored port —
   `python3 <skill-dir>/heartbeat.py 4.75m '<same message>'` — which
   takes the same arguments and needs nothing but Python. Only if that
   is somehow unavailable, fall back to
   `while true; do echo '<same message>'; sleep 285; done`, and know
   what you are giving up: the shell loop cannot align to the wall
   clock, so an `@`-style interval silently becomes "every N from
   whenever this started". That degradation is why the port exists.

   Arm exactly one. Already armed = tick notifications are arriving in
   this session (or you armed one and haven't stopped it) — never arm a
   second; duplicate heartbeats multiply cost. Monitors die with the
   session, so a fresh or resumed session re-arms; when replacing one
   (interval change, uncertain state), `TaskStop` the old monitor first —
   stop-then-arm is the clean swap.

   If watch.py runs and a Monitor tool exists, also arm a tail on
   `.dreamwork/watch-events.log` — dashboard actions (answers, commands,
   and committed run-mode changes) then wake you immediately instead of
   waiting for a tick. On a `run-mode via watch` line, re-read
   `.dreamwork/run-mode` (authoritative; file-formats.md) before acting.
   Without a Monitor tool, check that file's mtime in the tick loop.

6. **Task backend.** Native Claude Code task tools (TaskCreate / TaskList /
   TaskGet / TaskUpdate) by default. If the target already has backlog
   configured (a `.backlog/` dir at its root), use `bl` instead: `bl howto`,
   `bl idea`, `bl next` / `bl grab` / `bl cycle`. With `bl`, map the
   skill's task conventions (priority, type, size, next-up queue-jumps)
   onto bl's own fields and mechanisms — the loop semantics stay the same.
   Note which kind you have, because the ledger follows from it: `bl`
   survives a restart on its own and *is* the ledger, while the native
   tools are session-scoped and need `.dreamwork/tasks.md` alongside
   them (restored in step 8).

7. **Orient.** Read the project's CLAUDE.md and any goals/philosophy docs —
   together with DREAMWORK.md these bound what the loop may do (including
   whether push/deploy is authorized). Create `.dreamwork/{dreams,docs}/`
   if missing — and on first creation, seed `.dreamwork/docs/doc-map.md`:
   a cross-reference of the repo's existing docs (what lives where, what
   it covers, what the loop must keep current).

   **Seed `.dreamwork/questions.md` too, if absent**, with exactly its
   skeleton — `# Questions for the human`, then `## Open`, then
   `## Answered`. Do not leave the first entry to invent the file's
   shape: `watch.py` matches those section headings literally, and a
   questions.md without them parses to zero entries and renders as
   "nothing to answer" with no error anywhere. A whole project's
   escalations were invisible this way (2026-07-25). Formats for every
   loop-written, tool-parsed file: `file-formats.md` in this skill's
   directory — read it before writing one of them for the first time.

   Build on top of existing
   docs and link outward — never fork or replace them; dreamwork docs
   hold the internal, not-necessarily-public knowledge. Notice the
   repo's existing work-management and improvement systems — task
   backends beyond `.backlog/`, installed skill suites, justfile
   maintenance targets, TODO/issue conventions: the loop works *with*
   them, never in parallel to them. Where one would repay deeper
   integration (e.g. running a repo's improvement skill as a periodic
   maintenance item), suggest a bridge plugin via `questions.md` —
   suggesting is free; building needs a yes (see the bridge-plugin
   pattern in `writing-plugins.md`). Then read
   `.dreamwork/docs/` (living docs maintained by the dreamers), read the **recent** end of
   `.dreamwork/lessons.md` and search it on demand thereafter — it is the
   cheapest memory and also thousands of lines, so "read it" at init means
   the newest entries plus a grep when a decision touches one, never the
   whole file (#400). Skim recent
   `.dreamwork/dreams/` entries — they carry memory from earlier sessions
   and subagents — and check `.dreamwork/questions.md` for open questions
   to surface in the opening status. Update check: compare
   `.dreamwork/skill-version` against the latest entry in the skill's
   `migrations/` — behind means read the intervening entries, apply
   what's relevant, bump the version file (`migrations/README.md` has the
   protocol). **A migration may have left a notice in a data file** (#458)
   — a declared comment block at the top of `tasks.md` or another hot file,
   which exists because a long-running loop never re-initializes and so
   never sees a migration at all. Its data files are the only channel that
   reaches it. So after bumping the version, retire any notice the bump
   makes spent — the version argument is **required** and the tool refuses
   rather than guessing a path:
   `python3 <skill-dir>/migration_notice.py retire --path <hot-file>
   --skill-version-file .dreamwork/skill-version`. It prints `removed` or
   `kept`, and `kept` is the correct answer while the version is still
   behind. A notice that outlives its migration is the next agent's
   confusion, and the retirement is the half nobody is prompted to do. Learn the project's verify commands (justfile, package
   scripts: test, lint, build) — you'll run them every increment. Skim
   the recent git log (~10 commits) to absorb current direction and
   granularity.

8. **Reconcile.** First, get the queue in front of you. A session-scoped
   backend starts empty — that is not an empty queue: restore it from
   `.dreamwork/tasks.md`, keeping the ids. A durable backend already
   has it.

   Then check that queue against reality, because nothing else will:
   `git status` and the recent log say what actually happened since
   anyone last looked. Mark done what's done, split what's half-done,
   drop what's moot — trust neither a ledger line nor a stale
   in-progress status — and bring the ledger back into line. A dirty
   tree is unfinished prior work: understand it first, then land it as
   an increment or park it (stash + task) before starting anything new.

9. **Green baseline.** With the tree reconciled, run the project's
   verification once (tests/lint, or its stated routine — see
   DREAMWORK.md) before any new work. Green means every later failure is
   attributable to your own increments. Red means fixing (or explicitly
   documenting) the breakage is your first task — never dream on top of
   an unexplained red baseline.

   Also run the loop's own check on this target's state:
   `python3 <skill-dir>/lint.py --target .` — it calls the real readers,
   so a clean pass means the dashboard can genuinely see what the loop
   has written. An ERROR here is not cosmetic and outranks other first
   tasks: it means a file the loop writes is invisible to the tool that
   reads it, and the failure mode is silence — an unreadable
   `questions.md` renders as "nothing to answer" while real questions sit
   in it. Warnings about absent files are normal on a fresh target.

10. **Seed (first run).** If the task list is empty, capture obvious
    candidates surfaced while orienting — TODO/FIXME markers, planning
    docs, README roadmap items — as pending tasks with priority/size
    metadata. Don't force volume; the selection algorithm's brainstorm
    step handles a thin list later.

11. **Status.** One-paragraph opening status to the human: project,
    baseline state, loaded plugins, what you'll do first, queue depth —
    and the **session goal**: one line naming what this session is for
    and which DREAMWORK.md goal it hangs under. Write it to
    `status.json` (`goal`). It forms once the queue is reconciled and is
    merely *reported* here — init's own recovery work (landing a dirty
    tree at step 8, fixing a red baseline at step 9) predates it and is
    exempt from stating a chain. It is a claim, not a contract: the human's
    next steer may replace it, and a pivot means re-declaring it rather
    than quietly working to the old one.
