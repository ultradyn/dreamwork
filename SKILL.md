---
name: ud-dreamwork
description: >
  Continuous low-cost autonomous dev loop ("dreamwork" / "productive dreaming"):
  a 4.75-minute heartbeat keeps the session cache-warm and wakes it when idle;
  work happens in small committed increments (15-20 min cap) with post-change
  reflection; every idea is captured to the task list; an explicit algorithm
  picks the next task when idle. Use when Max says dreamwork, productive
  dreaming, dream loop, start dreaming, or wants long-running free-flowing
  autonomous dev on a project.
---

# Dreamwork — the productive dreaming loop

## Philosophy (load-bearing)

- **Small increments are the error-catching mechanism.** Cap each task at
  ~15-20 minutes of work. After every change, pause and reflect: re-read the
  diff, run the tests. Mistakes get caught the moment they're made, while you
  are still on the path that made them. Split anything bigger into multiple
  tasks; each increment must end in a verifiable, committable state.
- **Ideas always go in the task list.** No idea is lost, and no work happens
  that isn't a task. The list is the loop's brain, and it must be durable —
  a record that forgets on restart is a cache, not a memory. (Which record
  that is depends on the backend; see Durable state.)
- **Know what the human wants.** `DREAMWORK.md` (repo root) records the
  human's high-level goals, philosophy, preferences, and routines. We should
  always know what the human wants so we can make what the human needs —
  it is where every chain of work terminates. It
  grows incrementally: when the human expresses a durable preference or
  goal mid-loop, record it there.
- **Reflection over momentum.** The heartbeat buys thinking time after each
  change. Use it — a beat spent noticing a mistake is cheaper than an hour
  spent undoing it.
- **Unclear is a goals problem.** All unclear things trace to unclear
  goals; always be improving clarity where it lacks. Any time we need to
  talk to the human is also a time to sharpen the recorded goals — fold
  what their answer reveals into DREAMWORK.md, don't just unblock the
  moment.

## Initialization (once per session)

Read `initialization.md` from this skill's base directory and follow it —
in order: confirm the target project, read the
target's DREAMWORK.md (if present), resolve plugins (`ud-dreamwork-*`
skills, which may extend later steps), run the setup wizard when
DREAMWORK.md is absent, then heartbeat, task backend, orientation,
reconciliation, green baseline, first-run seeding, and the opening status
report.

Initialization runs once per session (or on resume). This SKILL.md may be
loaded multiple times in a long session — if the heartbeat is already armed
and DREAMWORK.md has been read, skip initialization and return to the loop.

## The loop — on every heartbeat tick

Ticks are monitor events, not user input — never treat one as a reply or an
approval. Real user messages always take priority over the loop. When the
human is actively streaming messages, prefer capture and consultation over
starting new increments — resume autonomous work when the stream pauses.

- **Mid-task** → checkpoint: still on track? Past the ~20-minute cap? (Land a
  coherent point, commit, split the remainder into a new task.) Did the last
  change introduce an error? Look before continuing.
- **Task just finished** → reflect and verify (checklist: `reflection.md`
  in this skill's directory): re-read the diff, run the project's
  verification, commit the increment, mark the task completed. Then
  select the next task.
- **Idle** → run the selection algorithm below.

On each tick, best-effort, refresh `.dreamwork/status.json` (current task,
queue depth, last tick time, last commit, and the session goal — which
persists across ticks, rewritten only on a pivot) — the watch.py
dashboard reads it; failing to write it never blocks the loop.
**Run `just status-sync` rather than editing the derived fields by hand**: the
queue count and `current_task_ids` are computed from the ledger and from live
`ccc @` processes, and hand-maintaining them is how `current_task_ids` came to
name three tasks that had closed hours earlier while the dashboard rendered
them. It refuses rather than writes when the ledger is unreadable or holds a
duplicate id, so it is safe on a bad tick; `--check` exits 1 without writing.
Everything written by judgement — notes, owed verifications, queued dispatches,
the session goal — it leaves alone, because those are the fields a tool cannot
derive and the coordinator must still keep true. And if
`answers.md` has Open entries, answer and fold those human-to-dreamer asks
before selecting work. If `questions.md` changed since your last look, check
for new human-authored blocks (`Note (human, via …)`) — fold them first: act
on the answer, then move the entry to Answered.

**Discover landings from git first: run `python3 <skill-dir>/dev/ledger.py
sweep` before selecting work** (#404). It scans commit subjects since the
most recent fold commit (`--since REF` to override) for id-bearing landings,
correlates against the open ids, subtracts entries that already cite the
sha, and prints the remainder **plus how many commits it examined AND how
many open ids it correlated them against, with the source it read them
from** — a sweep that found nothing is distinguishable from one that did
not run. Read BOTH counts: for a year the commit count alone was printed,
and after the #294 cutover the ledger half silently returned zero while the
commit count stayed real, so every tick got a confident all-clear from a
correlation that never happened (#671). `(store)` after the open-id count
is the normal post-cutover reading; `(markdown)` in a project that HAS cut
over means the store did not resolve and the answer is built on whatever
`tasks.md` still holds. A sweep that read no entries at all says `DID NOT
REVIEW` instead of reporting a clean result. It
is advisory (exit 0 always). This is the primary route because a lane
cannot land work without committing, and the commit convention puts the id
in the subject by construction — git knows about every same-tree landing,
while an inbox report is an extra act a lane must remember (and `#392a`
showed what forgetting looks like). Fold what it reports into `## Recently
landed` citing the sha, or cite the sha in the entry when the open state is
deliberate.

**The fold step now also runs `reach`** (#688): `fold` tacks a compact
branch-reachability trailer onto its output, the twin of `sweep` that sweep
cannot be. `sweep` examines commit *subjects* on master, so a branch that
was folded but never merged has no commit on master for it to see — invisible
by construction (#590). `reach` enumerates every local branch and
`git cherry`-marks each against master (`-` = patch-equivalent / already
landed; `+` = genuinely absent, or squashed, or refactored — a question,
never a verdict). It runs at fold time because that is the moment branches
are created and abandoned, so the check needs no second command to remember.
It reports only branches with at least one `+`, collapses duplicate sha
sets, and always says how many it examined — silent where there are no
branches, loud where a gap could hide. `python3 <skill-dir>/dev/ledger.py
reach` runs it standalone.

**Then read `.dreamwork/handoffs.md`'s `## Pending`** — the supplementary
route, for the case git cannot see: a lane on a different machine or repo,
or landed work that is not a commit. A
session that lands work it does not own the ledger for (every session but you)
appends one line per landing there — the delivery half of the single-writer
rule, because its report dies in its own session otherwise and the entry sits
done-but-open until someone happens to look (#334 sat an hour; #362 was found
by accident). For each pending hand-off, fold the task into `## Recently
landed` citing the hand-off's sha, then append a `→ folded (<ts>)` line under
`## Folded` so it is not flagged again — nothing ever moves between the
sections, both only grow by append. This is the one act on `tasks.md` a
foreign session cannot do for itself, so consuming its hand-off is how its
landed work reaches the ledger at all.

Check `.dreamwork/watch-events.log`'s mtime too. Since the E3 cutover a
command he types into the dashboard composer is ALSO durable: every
`/command` POST commits a journal receipt before dispatch, so the tick's
cursor read (`pending`) lists it even when the tail monitor missed the
wake line (a resumed session, a compacted one, a `watch.py` started after
init). The wake line is the interrupt; the receipt is the record. Two
cautions (#519): the wake line carries no receipt id, so if you acted on a
do-now from the wake line and the SAME instruction later appears in
`pending`, it is the same instruction delivered twice — act once (this is
#527's proper fix); and pre-E3 this paragraph said the command channel was
wake-only, which is why the drain must run on every tick regardless of
delivery mode (#528).

**Run mode (#290) and posture (#445).** On tick start (and when an events
line matches `run-mode via watch`), re-read `.dreamwork/run-mode` — that file
is authoritative, gitignored, and one of `lackadaisical` (default), `hot`,
or `assisted`. The dashboard arms a 10s shared cooldown before writing it
and emits one events line only on a real change.

`run-mode` bundles three independent decisions — **pace** (how often the
loop acts), **asking** (how much surfaces to the human), and **delegation**
(whether it works through subagents) — and `#443` measured that the bundle
is the defect: *"lackadaisical but delegating"* was unexpressible. His `#445`
ruling ratified **three orthogonal axes: pace × asking × delegation**, and
deferred widening `run-mode`. Today's vocabulary lives in `lint.py`
(`POSTURE_STOPS_PACE` / `POSTURE_STOPS_ASKING` / the delegation target):

- **pace** — `idle` / `steady` / `hot`: how fast the loop works.
- **asking** — `ask` / `inform` / `near-auto` / `auto`: how much surfaces
  to the human, in his own four dictated levels. `ask` surfaces every
  material choice as a question; `inform` mostly emits documentation;
  `near-auto` journals each choice silently; `auto` never blocks on a reply.
- **delegation** — an **average-concurrency target** (an integer: `0` =
  occasional, `1` = assist, `2+` = delegate), never a cap or a refusal
  (`#445` Q3). Two subagents may pair on one worktree, talking via the
  `subagent-protocols` handshake, bundled at
  `<skill-dir>/subagent-protocols-for-subagents.md`.
- **orchestration** — `hands-on` / `orchestrator` (`#510`, his ruling:
  mode not identity; binary; absent → `hands-on`). Whether the
  coordinator's own hands touch the work — orthogonal to delegation,
  which is only the fleet-size number. `hands-on` = the coordinator
  implements increments inline between dispatches (the long-standing
  default). `orchestrator` = the coordinator implements **nothing**
  inline: every increment is dispatched to a lane, and the coordinator's
  role is adjudication, review, merge-gates, and the ledger. It answers
  a different question than `delegation: 4` does — a coordinator can run
  a fleet of four and still implement inline (`hands-on`), and that
  combination is what the axis makes sayable.

**Absent posture → derived from run-mode** (the mapping lives in
`lint.derive_posture`, the single source): `lackadaisical` → idle pace;
`hot` → hot pace, own hands; `assisted` → hot pace, assist. All three
derive asking = `ask`, because today the loop asks on ~every material
choice — deriving `inform` would be a silent behaviour change. A present
`.dreamwork/posture` file overrides any one axis independently. Read it on
every tick alongside run-mode; it is the same per-tick-re-read contract
(`#426`). Treat the posture as **selection/policy posture for this host**;
do **not** invent kill/sandbox authority from it alone (`#288`).

**Restate the posture at each tick, don't just re-read it** (#513, human
steer). The file read is silent; what keeps the loop honest is saying the
resolved axes back to yourself at tick start — *pace hot, asking near-auto,
delegation 4, delivery batched, orchestration hands-on* — and checking the
last few ticks against
them: a `delegation: 4` posture with zero lanes out is drift; so is
implementing inline what a lane could carry — and under `orchestration:
orchestrator`, ANY coordinator-implemented increment is drift, however
small: dispatch it or file it, and let the merge-gate be the hands. The
steer named the failure
exactly: *"agents drifting back into implementing themselves or not using
subagents where they could otherwise."* A manual refresh button was
considered and rejected — the reminder belongs to the tick, not to him.

**And since #673 the tick line carries it, so the restatement no longer
depends on remembering to make it.** `tick_line.py` sits downstream of
`heartbeat` in the monitor command (`initialization.md` step 5) and appends
the resolved axes, the open count and the fleet counts to every pulse. Read
it as a *measurement*, not as a reminder to comply: it prints what the fleet
IS (`lanes N recorded (opus 5, ccc 1) · M ccc-live`) beside what the posture
SAYS, because a rule you believe you are already following is not
checkable and a count is. Still do the restatement — the line feeds it, it
does not replace it.

Two things it deliberately does NOT do. It never renders an unqualified
fleet size: `live_lanes` probes `pgrep -af ccc`, so Agent-tool lanes are
structurally invisible to it, and every count therefore names how it was
obtained (`recorded` = your `status.json` bookkeeping, `ccc-live` = the OS).
Where they disagree, that gap is the finding — see `#675`. And it never
issues a verdict: zero lanes minutes after a merge is normal, so a flag that
fired most of the time would just train you to skip the line.

**The journal drains on EVERY tick, whatever the delivery mode** (#342,
#501, #528). The E3 cutover journals a receipt for every write route in
BOTH modes — instant mode only adds the wake line on top, it never
replaces the durable receipt — so the drain is not batched-mode plumbing,
it is the loop's memory. In `instant` mode most drained receipts will be
ones the wake line already delivered: recognise them (by content today;
by receipt id once #527 lands) and consume past them — the cursor reading
"already handled" is the NORMAL instant-mode case, not an error. What you
must never do is skip the drain because the mode is instant: that leaves
`(cursor, head]` growing forever and mass-replays the day the posture
flips to batched (#519 F2). In `batched` mode the drain is the ONLY
delivery for the ambiguous class (ideas, notes, anything not addressed to
*now*) — do-now/do-next still pre-empt by wake line. The tick habit is
`pending → process → consume` via `dev/journal_consume.py` (the ruling:
`.dreamwork/docs/plans/delivery-modes.md`):

1. `python3 <skill-dir>/dev/journal_consume.py pending` — read-only; one
   line per event, receipt id first, 80-char preview. Quiet on empty. It
   also states its coverage on **stderr** — `listed N receipt(s),
   ordinals L..H (consume --through H)` — so a `| tail` that truncates
   the listing cannot truncate the count, and step 3 is a copy-paste.
   Fewer lines in hand than that count is a truncated read (#712).
2. Process each event — act on it, file it as a task, or fold it into a
   question. The preview is a triage aid, not the content; when it is not
   enough, read the receipt's full payload with
   `python3 <skill-dir>/dev/journal_consume.py show <ord|receipt-id>...`
   (read-only, opens `mode=ro`, never moves the cursor) before acting —
   never hand-write SQL against the journal (#855: the documented path used
   to end at a truncated line and hand you to a heredoc one typo away from a
   writing open).
3. Only then `python3 <skill-dir>/dev/journal_consume.py consume
   --through <head-ordinal-from-step-1>` — the verifying
   read-then-advance that moves the cursor past what you read, bounded
   to exactly what the `pending` read reported (#531: an event landing
   between the read and the consume is otherwise advanced past unread;
   every `pending` line carries `ord=<n>`, the last line's is head).
   That ordinal must be **the** head of that read, not merely inside it
   (#712) — a lower bound came from an older or truncated view, so it is
   refused. There is no partial drain and none is needed: consuming
   nothing re-lists the whole range next tick, losing nothing.
   Bare `consume` still advances to the live head — the right form only
   when there was no prior read to bound against, which the rule below
   forbids in a tick anyway.

**An `EXPEDITED` line in `consume`'s output is not an act-list entry** (#864).
It names a receipt the stop hook already handed you at a pause, so it is
correctly absent from `UNAPPLIED` — acted on once, per #519/#527. It is
printed rather than left to the `applied` count precisely so a hook whose
output you never saw cannot swallow one of his instructions in silence: if you
do not recognise it, `show <id>` has the text. The hook never moves the cursor,
so nothing it delivers escapes this drain.

**Never consume without a prior `pending` read in the same tick — and the
consume is bounded to what that read reported.** The coordinator ran
`consume` blind once and discarded two events' content
unread — one was a human instruction (the #513 steer above), recovered
only by hand-written SQL against the events table. `consume` prints
receipt ids, not content; a blind consume is a silent loss with a green
exit code, the exact failure batched mode exists to prevent. The
`--through` bound is the same rule one level tighter: even with a prior
read, an unbounded consume silently claims events the read never listed.
**Never pipe `pending` through `head`/`tail`** (#658): the coordinator did
exactly that, saw ordinals 97/98/99, and consumed `--through 96` past a
receipt the `tail` had scrolled off — a read whose output was truncated is
not a read. `pending` now writes a read-coverage marker and `consume
--through N` refuses unless N is exactly the head that marker records
(four named refusals: no read on record, marker from a different journal,
N beyond the read's head — which names the uncovered ordinals — and N
below it, which names the ordinals that would be advanced past). That
makes the truncation LOUD, but it is not a licence to truncate: **the
marker proves every line was *printed*, not that every line was *seen***,
and no in-process check can prove the second — so `pending | tail -3`
followed by `consume --through <the head you can still see>` still
consumes the lines the tail removed, with only the stderr coverage count
disagreeing with what you hold (#712). The discipline and the refusals are
both needed, and the discipline is the half that closes that case.

## Selecting the next task

0. **Sync.** Check the task list first. Resume unblocked in-progress work
   before starting anything new; then take any task marked next-up —
   `ledger.py list` puts them first, newest mark first, tagged `NEXT-UP`, and
   `ledger.py next-up <id> --clear --why …` clears the mark as you start —
   an explicit human steer outranks the agent's own ideas. Then: any
   goal/philosophy misalignment **you already know about** (DREAMWORK.md
   stale or contradicted) outranks everything below — restore alignment
   before other work. This is not a licence to audit DREAMWORK.md before
   every selection; the periodic check that *produces* such findings is
   step 4.
1. **Out-of-scope leftovers.** In recent work, did anything occur to you that
   was out of scope at the time? If complex: do a quick feasibility check,
   then add it to the task list. Otherwise: do it now (add it as in_progress
   first so the list stays truthful).
2. **Idea beat.** Does anything recent give you an idea for a productive
   thing to do? (a new feature, refactoring, integrating a new library and
   updating some things,
   ...).....................................................................
   (The dots are intentional: explicit thinking time. Let the idea surface
   before reading on.) If a good idea comes: do it (scope gate applies).
   Multiple ideas: add them all to the task list, then pick with IGC
   (see Guardrails) — not by feel.
3. **Still nothing:**
   1. **Brainstorm (rare).** Only when few actionable ideas remain (fewer
      than ~3 pending unblocked tasks) and no brainstorm has run recently:
      dispatch a dreamer subagent (see Subagents) with the
      superpowers:brainstorming skill. Constraints for it: ideas must be
      consistent with the project's goals and philosophy (per DREAMWORK.md
      and CLAUDE.md — pass the relevant parts into the subagent prompt);
      experiments are fine but must be feature-gated (see Guardrails); big
      feature swings and pivots are rejected (big changes genuinely necessary
      to solve a problem are exempt — those are a fact of life). Record when
      the brainstorm ran (metadata on a marker task) so it stays occasional.
   2. **Backlog.** Otherwise pick the highest-priority unblocked pending
      task. When torn between backlog and maintenance (or which
      maintenance item), you may roll `roll.py` in this skill's directory
      — advisory, never binding: a mess, an easier-now-than-later, or a
      human steer always overrides. Custom weights persist as a Routines
      line in DREAMWORK.md.
4. **Maintenance rotation.** No unblocked actionable work, and brainstorm
   recent? A non-empty queue whose remaining tasks are all blocked is idle
   too — do not spend ticks reconsidering work that cannot start. Rotate
   through: goal alignment first — does DREAMWORK.md still reflect what
   the human wants and what the loop has learned? fold in any drift, and
   check every task `parent` still resolves to a DREAMWORK.md heading;
   then
   self-review recent commits for introduced errors; test-coverage gaps;
   docs freshness — the repo's own docs, `.dreamwork/docs/`, the
   doc-map, and any reference docs the target ships for others to
   consume, alike (keeping the repo's docs current is loop work; the
   doc-map's rows say what that covers);
   task-list grooming (dedupe, reprioritize, prune stale); dream grooming (archive dreams whose ideas and lessons are
   captured); dogfood reflection — friction with the loop itself: fix
   small, file the rest. If truly nothing: idle quietly until the next tick — no
   make-work.

## Subagents — utilities and dreamers

Two kinds, nothing in between:

**Launch through the governed route:** run `just launch-lane <task-id> <lane>
<@agent> <human-head-file> [ccc options] >launch.log 2>&1 &`. It obtains the
current `master` sha, adds only the canonical lane metadata and standing
boilerplate, validates the exact final bytes and persists their digest before
creating the worktree, then supervises the existing dispatcher until its real exit. Its
machine-local attempt record says `unverified attempt` before the runner starts;
a retry is explicit (`--resume <attempt-id>`) and accepts only the identical
SHA-256 digest. The background spelling is load-bearing: a foreground terminal
job is refused, and a context without a controlling tty is reported as
unobservable rather than guessed.

**Generate the frame; author only the core** (#881). `python3 dev/brief.py
--task <id> --owns <paths> --core <file>` emits a complete brief — identity
header with the base sha derived from `git merge-base`, the worktree asked of
`git worktree list`, the `--ledger` read form, `Lane-owns:`, the standing rules
and live-state prohibitions from `briefs/frame.md`, the report skeleton, and the
boilerplate. It **refuses** a core that is empty, all placeholder, or carries no
direction-2 section with a body. Measured over the 40 most recent briefs
(`.dreamwork/docs/measurements/881-brief-frame.md`): the rules block was retyped
33 times and produced **32 distinct bodies**, so what this fixes is a lane's
rule set depending on what was remembered, not typing volume — the frame is only
7.3% of a brief's bytes. Write the core; never let the tool write it.

The lower-level checked dispatcher remains `just dispatch-lane <prompt-file>
<@agent> [ccc options]`. The prompt file ends with `briefs/boilerplate.md`
appended verbatim; `dev/dispatch_lane.py` validates that exact delivered string,
writes it once to `.dreamwork/docs/briefs/<task>-<lane>.md` with a sibling
dispatch-time SHA-256 receipt, and then replaces itself with `ccc`, passing the
prompt as one argv item. The task comes from the first-level heading and the lane
from the prompt's unique `Branch:` line, so repeated task ids on distinct lanes do
not overwrite one another. A persistence failure refuses the launch.
Direct `ccc` lane dispatch is unsupported: shell quoting can turn a command
substitution into the literal prompt `$(cat ...)` while every process-level
health signal still looks normal. This pre-launch check proves what the wrapper
passes, not what a downstream process ultimately received; `/proc/<pid>/cmdline`
inspection is a separate, stronger check with a short observation window.

**The wrapper records a pending brief; it does not guarantee durable
persistence.** The `.md` and `.sha256` remain uncommitted for the lane's lifetime,
so the coordinator runs `python3 dev/dispatch_lane.py --verify-pending` at the
merge gate and commits both. That check distinguishes matched content, changed
content, a missing half of the pair, an unclassifiable receipt, and no governed
input examined. It detects ordinary edits or one-sided deletion during the
uncommitted window; deleting both files can only be exposed by the corpus-reach
gap, not reconstructed. This is the one supported writer, time, and destination:
the validated dispatch wrapper writes once, before runner exec, into the brief
corpus. A lane does not persist its own brief and an abandoned or never-started
lane has no persistence duty to forget.

- **Utility subagents** — narrow tools: answer a question (e.g. an Explore
  agent for "how does X work?" or "what's relevant to Y?") or run a scoped
  mechanical job. Focused prompt in, focused answer out. No dream files.
- **Dreamers** — little versions of us, dispatched for substantive work
  (brainstorming, an increment, a review). They share our memories: pass
  them DREAMWORK.md, the relevant `.dreamwork/docs/`, recent dreams, the
  task's context, and **the active chain** — the task's goal, the
  session goal, and the DREAMWORK.md goal above them. A dreamer holds
  the same scope gate we do; without the chain it would have to invent
  the middle link, which the gate defines as the refusal. A dreamer that must
  **choose between rival options** is told to use IGC and is handed
  `<skill-dir>/igc-method.md` in its brief — it does not inherit this file's
  Guardrails, so the method is a dispatch-time hand-off, not an assumption
  (this is the highest-leverage site: most choosing now happens in lanes).
  When a dreamer finishes, if it had anything to say
  beyond its direct result — insights, surprises, out-of-scope ideas,
  warnings — it writes `.dreamwork/dreams/<date>-<time>-<slug>.md` (e.g.
  `2026-07-25-0140-export-panel-jank.md`). Nothing to say → no file; empty
  dreams are noise. If a dream contains an important lesson, its one-line
  distillation is also appended to `.dreamwork/lessons.md`. The coordinator
  reads new dreams and captures any ideas into the task list.

  **`lessons.md` is the coordinator's memory, not a lane's reading list**
  (#400, measured). It is thousands of lines; no lane reads it, and the
  measurement showed the lessons that actually reach a lane are the ones
  hand-copied into its brief — nothing else does. So **select the four to
  six that bear on this task and state them in the brief**, and cite an
  entry by what it says plus its line (`lessons.md:991`) when a lane needs
  the whole thing. Listing the file under "read, do not edit" implies a
  lane will find the relevant lesson itself, which is the one thing it
  cannot do. Survival was never the failing half of *"what it knew, it
  still knows"* — retrieval is.

  Retrieval has a tool (#349): `python3 <skill-dir>/dev/lessons_index.py
  --act <act>` prints, verbatim, the lessons governing the act you are
  about to do — `--acts` lists them (`red-proof` before an injection,
  `parsed-file` before writing a file a tool parses, `worktree-dispatch`
  before a dispatch). Consult it at the moment of the act, and select a
  brief's four to six from the slice it prints, not from the top of the
  file. It never summarises (the evidence half is why the format exists),
  and it reports what it could not classify rather than missing silently.

Delegation blocks files, not the loop. Record what a dispatched dreamer
owns (files/dirs) at dispatch; the coordinator stays off those. After
~10 minutes of a delegated task running, resume selection over
non-conflicting tasks. The invariant is disjointness: parallel
increments — the coordinator's own, or several dreamers' — only ever
touch disjoint files, so there is never a split brain over the same
files. The `parallelize` command is the explicit fan-out of this same
rule; the coordinator itself still works one inline increment at a
time. Disjoint files also means disjoint staging, and **`git add <path>`
is not enough — `git commit` commits the INDEX, not the paths you
added**, so a file another agent had already staged rides along in your
increment even though you never named it. Avoiding `git add -A` does not
prevent this; nothing about your own command hints at it. While anyone
else holds the tree, commit with **`git commit --only <paths> -m …`**,
which commits exactly those paths and leaves the rest of the index
staged and untouched. Measured, because the plausible version of this
rule is the wrong one: with a peer's file staged, `git add mine &&
git commit` produced a two-file commit; `git commit --only mine`
produced a one-file commit and left the peer's still staged. One edge:
`--only` does not see a NEW file until git knows the path: a directory
pathspec silently drops an untracked file inside it while the tracked file
commits, and a bare untracked pathspec errors. Run `git add -N <paths>`
first — intent-to-add, not `git add`, so nothing is staged into the index
the `--only` rule exists to protect (#684).

**`git config commit.cleanup scissors` once after a fresh clone** (#693):
commit subjects begin with `#NNN`, which is a `#` line, and an *unset*
`commit.cleanup` defaults to `strip` on the editor path — so
`git rebase --continue` silently deletes the id and the landing becomes
undiscoverable (#404). `scissors` keeps `#` lines and truncates only git's
own instruction comments; `lint.py` fails unless the value is one that
preserves them.

**Worktree is the default for any dreamer that writes files** (#405).
Dispatch into a git worktree under `../.worktrees/` (outside the repo) or the
harness's worktree isolation — not only when disjointness fails, and not
only for large or risky work. Shared-tree dispatch is the exception and
needs a reason; a read-only lane is the obvious legitimate one. Lifecycle
follows the human's standing worktree convention (CLAUDE.md): merge back
on acceptance, and never force-remove without
`git status --porcelain --ignored` first (untracked lane scratch is
exactly what lives in a worktree). **What it costs:** worktrees duplicate
build state, so where the toolchain has a shared cache (compiler cache,
shared target/store dirs), set it up; if the project lacks one, suggest it
(questions.md). Storage ballooning is real.

**At lane completion, look at the tree before treating the lane as done**
(#535, from the #423 audit): a lane that *worked but did not commit* is
invisible to every automated signal — `sweep` reads commit subjects, the
lane-containment registry sees only `wt/*` linked worktrees (a harness's
`spawn_subagent` isolation is an independent clone, not one), and
`status_sync` knows alive-or-gone, not gone-with-work-left-behind. So when
a lane's completion notice arrives (or is reconciled after compaction),
run `git -C <lane-tree> log --oneline` since dispatch and
`git -C <lane-tree> status --porcelain`: commits + clean → fold normally;
none + clean → it crashed before working, retire quietly; **none + dirty
→ worked-but-undelivered — commit or salvage on the lane's behalf and
record it** (the `gate2`/`da197b87` recovery was this case, found by
luck). One command at one step, at lane *exit* — not a tick-time probe.

**A lane rebases onto its base branch when the base moves, and it does so
BEFORE it hands off** (human-set 2026-07-31): *"subagents should rebase
against their worktree's base branch if it's updated so that merge conflicts
are solved before they get back to the main coordinator/orchestrator."* The
reasoning is whose context the conflict needs: the lane knows why its lines
are there and what its neighbours meant, while the coordinator meets the
conflict cold at merge time with several lanes in flight. **Measured the day
he set it** — `#655`'s lane branched 32 commits back, so its merge left
`client/dist` stale and needed a post-merge `just build-client` the
coordinator had to be told about by a reviewer; and `#667`'s merge hit a
diff3 conflict in `lessons.md` that the coordinator resolved by hand with
none of the lane's context.

So the dispatch brief tells the lane, and the coordinator carries its half:

- **State the base sha at dispatch** — the merge-base AND the current head of
  the base branch, never a commit count (`#672`). A lane cannot notice that
  its base moved if it was handed a number instead of a sha.
- **The lane re-checks before finishing**: if `git rev-list --count
  <base>..<base-branch>` is non-zero, rebase onto it and resolve there. Same
  repo, so no fetch — a worktree sees the base branch directly.
- **Order is load-bearing: rebase FIRST, report the sha SECOND.** A rebase
  rewrites every commit it moves, so a sha captured before the rebase names a
  commit that no longer exists on the branch — the coordinator would then
  fold work citing a sha the merge does not contain, which is `#590`'s
  folding-is-not-merging failure arriving by a new door. Land, rebase,
  *then* put the post-rebase sha in your inbox report (`#687`).
- **Append-only files conflict on almost every rebase** (`handoffs.md`,
  `lessons.md`, `questions.md`) because both sides grow at the same EOF. The
  resolution is nearly always keep-both, and after ANY hand resolution the
  lane greps for all four diff3 marker forms **line-anchored** —
  `grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` — note the `$`, which only the
  `=` arm carries and which is load-bearing: the other three markers are
  followed by a branch or base name so they cannot be anchored, while
  `=======` stands alone, and an unanchored `={7}` matches any rule-of-equals
  divider of seven characters or more (measured by lane-673tick against
  `test_chain_golden.py`, which false-positives under the unanchored form).
  Anchoring matters here because this repo's own files
  discuss conflict markers in prose and a substring test is wrong by
  construction (`lessons.md:3295`, and the coordinator tripped over exactly
  this resolving `#667`).
- **Safe here because lanes never push and never merge.** A rebase of
  unpublished work rewrites nothing anyone else has based on. The rule stops
  at the moment work is merged: after that, history is left alone (`#633`).

If the rebase turns out to be genuinely hard — a real semantic conflict
rather than two appends — the lane says so and hands back the analysis rather
than forcing a resolution it is unsure of. An honest "these two changes
disagree and here is why" is worth more than a merge that compiles.

**A worktree brief declares what it owns** (#465). The disjointness rule is
void the moment a lane edits the main checkout instead of its worktree —
and a brief cannot enforce it on its own, because the incident's brief
named the worktree twice and was ignored. So the brief carries a
machine-parseable `Lane-owns:` line (one or more, comma-separated repo
paths — `file-formats.md` for the shape), which the lane-containment guard
(`dev/lane_guard.py`) reads to refuse a main-checkout commit touching them.
`lint.check_brief_lane_owns` errors on a worktree brief that declares none,
so the omission is loud at dispatch rather than a silent no-op at commit.
**That guard is not write-time containment** (#450): on the harnesses the
loop dispatches (`ccc @grok` / `ccc @glm52`), a `Write` with an absolute path
is not interceptable before it lands — cwd, `git -C`, and the brief do not
stop it. The guard fails at first *commit* (and `#468`'s lint backstop when
the main tree is dirty); do not read either as a guarantee that a lane cannot
touch the main checkout. Ceiling per harness:
`.dreamwork/docs/plans/harness-containment.md`.

**A lane never runs `just test` or the full guard suite; the coordinator owns
both** (#424). The browser guards bind ports 39890-39899 and the recipe
hard-aborts if any port in the range is held, so with N lanes live at most one
process can ever run it — a brief that says *"then `just test`"* is
unsatisfiable at fan-out and has left lanes waiting fourteen minutes on a lock
nobody modelled. The convention that works: **a lane runs targeted pytest and
`lint.py` only** (plus its *own* guard, solo, via
`DREAMWORK_GUARDS=<name> DREAMWORK_HUB_GUARDS= just guards <port>` after
checking the range is free — never another lane's guard, never the suite), and
the coordinator verifies guards once on the merged tree before folding. This
matches who actually merges.

**Inbox paths given to a worktree lane are absolute.** A lane
in `../.worktrees/x` told to append to `.dreamwork/inbox.md` writes its own
copy, and the coordinator never sees it (`inbox.md` is often untracked, so
the path does not even exist at branch point). Give it as an absolute path
into the main checkout — repo-relative paths are silently wrong in a
worktree. (A lane no longer writes `.dreamwork/handoffs.md` at all — that is
single-writer durable shared state the coordinator owns; see `#687` /
`lessons.md:2704`. The absolute-path rule was for the inbox, and it stays.)

**A brief that asks the lane to read the ledger pastes the `--ledger` form
with the main checkout's absolute path** (#667). `ledger.sqlite3` is
gitignored (#294) so it never travels into a worktree, and the `tasks.md`
that does is the #458 shim — `python3 dev/ledger.py get <id>` came back
`#NNN not found` for every id. That does not read as "you invoked it wrong";
it reads as "that task is not in the ledger", and the next sentence of the
brief then routes the lane to `tasks.md.deprecated` to cite a stale entry
with confidence. lane-659attractor needed four ledger reads and got four
false not-founds. **"From the repo root" is not enough** — a lane told to
stay in its worktree reads that as *its* root. Paste the form:

    python3 dev/ledger.py get <id> --ledger <main-checkout>/.dreamwork/tasks.md

Every verb now refuses and names that form rather than answering from an
empty ledger, so a brief that forgets costs a round trip instead of a wrong
citation — but the brief is what saves the round trip.

**A brief states the base sha, and tells the lane to rebase before reporting
the sha.** Both halves of the rebase rule above live there: the merge-base and
the base branch's current head as **shas, never a commit count** (`#672`),
because a lane cannot notice its base moved if it was handed a number; and
the instruction to rebase and resolve in the lane, **before** putting the
sha in its inbox report, since a rebase rewrites the sha the report would
name (`#687`). Full statement and reasoning: the lane-rebase rule earlier
in this section.

**A brief that names a guard as evidence names the assertion that guard
would fail on** (`#672`) — a guard whose fixture cannot express the feature
PASSes before the work starts, true and uninformative.

**A "reuse X, do not reimplement it" demand names the check that binds the
reuse** (`#672`) — a correct reuse with no binding check is a hand-rolled
query away from drifting unnoticed.

**A brief that teaches the `cp`/`cmp` restore protocol
names a lane-private snapshot directory** (#652). Keep that clause on one
line — `lint.py` content-resolves its cutoff with `git log -S`, a literal
search that a line break defeats. The harness tells every agent its scratchpad is
"session-specific, isolated"; measured 2026-07-31, that is true of a *CLI
session* and false of a *lane*. Lanes are subagents of one CLI process and
inherit one `CLAUDE_CODE_SESSION_ID`, so **every concurrent lane resolves to the
same scratchpad directory** — same inode, verified by dispatching a probe
subagent. Two lanes snapshotting to the natural generic name (`router.js.orig`,
`style.css.bak`) means one lane's restore writes the other lane's bytes, and
*both* lanes' `cmp` checks still pass against the wrong baseline — the #349
safety protocol inverted into a silent corruption vector. Route the lane to
`dev/lane_scratch.py`, which derives a private directory from the worktree's own
identity so the lane never picks the path:
`S="$(dev/lane_scratch.py snap)"`, then `cp f "$S/f"` … `cp "$S/f" f` …
`cmp f "$S/f"`. It also lands the snapshot on `~/.cache` (btrfs) rather than
`/tmp` (tmpfs), which is the substrate half of #634. Never move the snapshot
*inside* the repo — that reintroduces the `git checkout` hazard #349 exists to
prevent.

Dreamers are batches, not careers. A long-lived dreamer's context grows
until fresh eyes are cheaper — bound its scope to the current batch,
retire it when the batch lands, and spawn fresh for new work (it
inherits the styleguide, docs, and lessons; that's the shared memory).

**Default to fresh. Reuse an incumbent only within ~4 minutes of its
last stop** (human-set 2026-07-25) — inside that window its context is
still cache-warm and respawning throws the cache away; outside it, a
fresh dreamer costs about the same and arrives with clean eyes. The
tight-follow-up exception (a bug in what it just built, a refinement of
its own motion language) lives inside that window, not beyond it.

**This is the coordinator's call, not the incumbent's.** A dreamer
saying "I have room" is evidence, not a decision — it is the party least
able to see its own context cost, and it will almost always say yes.
Ask instead: is this the same work, and did it stop moments ago? A
dreamer reached ~600k tokens here because its own assessment was
accepted three times running.

**Retiring one is not done when it says so — it is done when the harness
says it terminated.** An agent that acknowledges shutdown in prose and
stays alive looks identical to one that left, until it starts reporting
itself idle. Twice in one day here.

All subagents report to the coordinator **through a file**, and never use
`attn`. Give every one of them a path to write to and an inbox to ping —
a subagent's final message is a channel nobody reads back, and it has
silently swallowed deliverables here. Dreamers append to the coordinator
inbox, and that is still the right channel for judgement — so dispatch
utilities the same way rather than watching harder.

**The handshake is bundled, not assumed** (#466). Every dispatch prompt
carries the startup handshake from
`<skill-dir>/subagent-protocols-for-subagents.md` — the subagent's own
inbox, the startup message naming whether it can be reached mid-task,
id-prefixed append-only lines — and the coordinator side (its own inbox
monitor, what to put in the prompt, how to read the handshake) is
`<skill-dir>/subagent-protocols-for-coordinators.md`, with the
`watch-file.sh` monitor helper bundled beside them. Both are vendored
copies of the `subagent-protocols` skill with the upstream sha recorded
in each header, so a fresh install carries the channel rather than
depending on the host's skill set. A lane that never loaded the
handshake has no inbox — and the inbox is the coordinator's only
mid-task steering channel.

**But the inbox is not lossless, and this file used to claim it was.**
Measured across one four-lane batch: the **commit** arrived 4/4, the
hand-off line 4/4 written but only 3/4 in the right section, and the
inbox **3/4**. `#392a` landed real work, wrote a hand-off, and never
reported — its rejected alternatives and its stated uncertainties are
gone, recoverable only because the diff was small. *"Has never failed"*
was an absence of observation rather than a property, and its
counterexample looks exactly like a quiet lane, which is why nobody
rechecked it for months. **Exactly one channel cannot be skipped: a lane
cannot land work without committing.** So put what must survive in the
commit — the message, and any document the work produced — and treat the
inbox as where richer context *usually* arrives, never as where a
deliverable lives (#404).

**A landing leaves two records, not one** (#394; writers split by `#687` /
`lessons.md:2704`): the lane writes its report to the absolute `inbox.md`,
and the coordinator writes the hand-off line in `.dreamwork/handoffs.md`'s
`## Pending` from that report at merge. The split is an ownership call, not
a path preference — `handoffs.md` is durable shared state and wants a single
writer, so a lane appending to `## Pending` while the coordinator edits
`## Folded` conflicts on every merge (hit twice in twenty minutes,
`lessons.md:2704`). The lane's whole duty is the inbox report — say so in
its brief, because "the coordinator writes the hand-off" is not something a
lane can infer. The two records are still not redundant: the inbox carries
judgement and is read by a coordinator, in prose, once; the hand-off carries
the id and the sha and is read by `lint.py` and the dashboard, forever. So
an inbox report is durable only while a coordinator is alive to act on it —
and the case the hand-off exists for is exactly the other one, where the
work landed and nobody folded it (`#334` sat an hour, `#362` was found by
accident). The channel and both its readers were built by `#381`; what was
missing was a writer, so `## Pending` sat empty while two lanes landed. **A
channel nobody writes fails the same way as a channel nobody reads, and
looks just as finished** — and writing the hand-off is now the coordinator's
merge-time duty, not the lane's.

**A lane's inbox report ends with a dogfood section — required, not
optional** (#589, his 2026-07-31 steer: *"Subagents should be instructed
to always return a dogfood report section when finishing tasks so you get
good feedback."*). The section's value is not in restating the result; it
is in what the lane found **beyond** its direct task — friction with the
loop's own tooling, a premise the brief got wrong, a hazard a sibling
construct hides, an out-of-scope warning. Tonight's seven lanes proved it:
the highest-value findings were the ones that lived past the named defect,
and one — a predicted merge break — sat unread in an out-of-scope section
the coordinator never looked at. So the obligation is **on the lane to
write the section, and on the coordinator to read it**: a section a
coordinator does not know to look at is the same as one never written. **Blank
is a valid answer that is STATED** — *"no friction found"* is a real
answer; an omitted section is not, because it reads as "no friction" and is
indistinguishable from a lane that did not look (`#136`/`#671`: a zero that
examined nothing must not read as passing). Say so in the dispatch prompt
beside the hand-off obligation: both are duties a lane cannot infer.

**Put it in the dispatch prompt, not the relay** — measured, not assumed.
The first attempt relayed this obligation to three in-flight lanes; the one
that landed did not write a line and its report never mentions the relay. A
lane reads its brief and its prompt exactly once and reliably; it re-reads
the relay only *between increments*, and whether its task even has more
than one increment is decided by the lane, after dispatch, invisibly. So
**sort every steer by "what if this is never read": if the answer is "the
deliverable is incomplete", it belongs in the prompt.** The relay is for
refinements that are safe to miss — a ratification, a sharpened edge case.

**Steering an agent takes two acts: write, then wake.** The inbox is
durable but not delivered — a dreamer reads it *between increments*, so
one that has gone idle never sees it, and a batch written two minutes
after it went quiet sits unread indefinitely. Write with `relay.py`
(body from stdin, stamp from the clock, both for reasons in its
docstring), then send a message through the harness. A silent agent and
a silent channel look identical, so verify what READS a thing, never
just that it was written.

Subagents never stop or pause loop machinery — the heartbeat monitor, the
watch server, the loop itself; if one believes the loop should stop, it
says so in its report and the human (or the coordinator on the human's
instruction) decides. A report must always say what durable state
changed — dream file written, docs added or updated, with paths — change
notification is key and cheap. Everything else stays minimal: raw
results, no ceremony.

## Durable state — `.dreamwork/`

- `DREAMWORK.md` (repo root) — what the human wants; see Initialization.
- `.dreamwork/dreams/` — dream journals from dreamer subagents. Once a
  dream's ideas are tasks and its lessons are in `lessons.md`, move it to
  `dreams/archive/` — the journal stays lean, the memory survives. One
  exception worth keeping: **a dream stays active while the work it hands
  off to is unstarted**, so whoever picks that work up meets it without
  going looking. Archive it when its successor exists or the handoff is
  spent.
- `.dreamwork/lessons.md` — important lessons, each outliving the dream
  it came from. **Prune when a lesson has graduated into a guardrail or
  a check** — one now enforced by `lint.py` or a guard no longer has to
  persuade anyone. What a good entry looks like, and why its evidence
  half is load-bearing: `file-formats.md`.
- `.dreamwork/docs/` — living docs collaboratively added to and maintained
  by us, the dreamers: design notes, discovered conventions, gotchas,
  architecture understanding. Maintained means pruned and updated when
  stale, not append-only.
- **The ledger** — the queue's durable record, which everything else in
  this skill means by the word. On a backend whose list and ids survive
  a restart (`bl`) it *is* the backend, and there is no extra file. On a
  session-scoped backend (the native tools) it is
  `.dreamwork/tasks.md`: a literal `## Open` section, one entry each (id,
  title, priority/type, origin, owner or blocked-on, pointer to any
  plan), plus the next id to hand out — **and a literal `## Recently
  landed` section below it**, which is not optional bookkeeping. Both
  headings are matched verbatim: `watch.parse_ledger` returns the open
  and landed id sets from them, `lint.py` ERRORs when its own line-walk
  disagrees about where the split is (#304), the burndown's completions
  come from the landed section's git history, and #306's stale-ask check
  reads the landed set. A coordinator that trimmed the file to open
  tasks would break all four, quietly. From #216 every entry records
  who filed it — `origin: **human**` or `origin: **loop**`, with
  `**unknown**` reserved for what predates the convention; history is
  never guessed, the contract is in `file-formats.md`, and `lint.py`
  refuses a governed entry without exactly one marker. Either way ids are permanent and never
  reused, and everything that refers to a task — commits, docs,
  questions, dreams — uses them; a session-scoped backend's own numbers
  are local plumbing. The file version is rewritten as part of the
  increment that changes the queue, not on a separate beat, and **the
  coordinator is its only writer** — a dreamer reports a queue change
  instead: durable shared state wants a single writer, or the next
  fan-out races it (two dreamers mint the same id, and the ledger loses
  exactly what it exists to keep).
- `.dreamwork/answers.md` — questions from the human to the dreamer. On each
  tick, read `## Open` before selecting work. Answer by preserving the entire
  human-authored entry, prefixing its body with a loop-authored
  `→ answered (YYYY-MM-DD HH:MM): <resolution>`, and moving it intact under
  literal `## Answered`. Do not answer through a server endpoint. If an answer
  re-blocks or needs reopening, add a new Open entry naming the prior title;
  threaded chat lifecycle remains out of scope (#229). Exact shape:
  `file-formats.md`.
- `.dreamwork/questions.md` — open questions for the human: proposals
  awaiting a response, unclear-goals items, parked scope calls. Answers
  fold into DREAMWORK.md or tasks and the entry moves to a short Answered
  section (pruned in grooming). Entries thread: timestamped follow-ups
  accumulate inside an entry and folds move the whole thread, and a
  follow-up landing on an *Answered* entry is a potential amendment —
  re-evaluate the fold, it may reopen the question or redirect in-flight
  work. **An update must make the entry smaller, not longer** (human-set
  2026-07-29 00:54): when part of an ask stops mattering — refuted by a
  measurement, settled by an earlier answer — **strike it out or remove
  it** rather than appending a note that explains it away. Every line
  left standing is a line he must read to find the live question, so the
  correction that grows the entry has spent his attention to record our
  own reasoning. Keep the durable trail in the ledger, the plan, or
  `lessons.md`; leave only what is still his to decide. **Whose words they are is never in doubt**, which is why the
  author tags exist; their exact forms are in `file-formats.md`, because
  a parser reads them. **Its shape is a contract, not a style** —
  `watch.py` matches `## Open` and `## Answered` literally, and a file
  that misses them parses to nothing and renders as "nothing to answer",
  silently.
- **Formats.** Files the loop writes and a tool parses have required
  shapes, and getting one wrong fails silently rather than loudly — the
  reader cannot tell an unreadable file from an empty one.
  `file-formats.md` in this skill's directory states them; read it before
  writing one of those files for the first time, and follow the existing
  file's shape rather than inventing one when a format is not yet stated.
- `.dreamwork/review/` — rich review artifacts. **Every request for a
  review ships one** (human-set 2026-07-25): if you are asking him to
  read a plan, a design or an analysis and rule on it, it gets a
  self-contained HTML artifact (inline everything — charts, math,
  styles; offline-clean) as `<slug>.html`, paired with the questions.md
  entry that asks. When the ruling is a **choice between options**, the
  options are an IGC matrix — ideas down the side, goals across the top,
  the decisive error written under each ✘, no score column (see
  Guardrails) — because a choice he can only score is a choice he cannot
  actually make. Not "when it seems sizeable" — that judgement was
  the loop's and it got it wrong: dreamhub's stage-1 plan went to him
  as prose in a questions entry, and it was the largest design decision
  of the day. watch.py lists and serves them; archive alongside the
  answered question. **Do not hand-roll the page (#325).** Write only the
  words, as `.dreamwork/review/src/<slug>.html`, and build:
  `python3 <skill-dir>/review_artifact.py build .dreamwork/review/src/<slug>.html`
  — `review-artifact.template.html` owns the frame, palette and footer, you
  own the content, and `check` reports each artifact as current, stale or
  untemplated. Hand-rolling is what produced five font stacks and eight page
  backgrounds across twelve artifacts, all of it in the stylesheet nobody
  meant to author; the source lives under `src/` because watch.py's
  non-recursive listing would otherwise serve him a half-built page. Its
  shape, and what `build` refuses, are in `file-formats.md`.
- `.dreamwork/run-mode` — main-dreamer pace for this host (#290): one line,
  closed set (`lackadaisical` / `hot` / `assisted`), written by the
  dashboard after a 10s arm, dual-written with one `watch-events.log` line
  on change. Authoritative over any status mirror; machine-local /
  gitignored. See `file-formats.md`.
- `.dreamwork/posture` — five-axis posture override (#445 ratifies #443;
  delivery added by #342; orchestration by #510): `pace:` / `asking:` /
  `delegation:` / `delivery:` / `orchestration:`,
  one axis per line. Absent → pace/asking/delegation derive
  from run-mode via `lint.derive_posture` (no silent change); absent delivery
  → `instant` (pre-axis behaviour); absent orchestration → `hands-on`
  (pre-axis behaviour). Present → overrides any axis independently.
  Pace, asking, delivery and orchestration are closed sets; delegation
  is an average-concurrency target (steers, never gates). Machine-local /
  gitignored, re-read every tick like run-mode. See `file-formats.md`.
- `.dreamwork/status.json` — live loop status for the watch.py dashboard,
  rewritten each tick. Its timestamps come from the system clock, never
  from memory — a dashboard whose whole thesis is liveness must not
  render an invented time. It also carries the loop's **runtime state**:
  which dreamers are out, what files each owns, which monitors are
  armed, and how to deploy. That state dies with the session, so this
  ephemeral file is its right home — but it must survive *within* one,
  because a compacted coordinator that forgets a dreamer owns `foo.py`
  will edit `foo.py`. Gitignored, like `watch-events.log` — both describe
  a running process, so committing either would be a lie the moment it
  landed. The dashboard itself is `watch.py` in this
  skill's directory (loopback-only by default):
  `python3 <skill-dir>/watch.py --target . --open`; its port persists in
  `.dreamwork/watch-port`. Explicit trusted-LAN mode is opt-in and
  unauthenticated:
  `--bind 0.0.0.0 --allow-host xsm --allow-host 192.168.1.20 --url-host xsm`.
  Every request uses an exact Host allowlist and browser POSTs require matching
  HTTP Origin; these stop rebinding/CSRF, not another LAN client. A concrete
  bind address may be the default advertised URL only when that address is also
  allowlisted; otherwise pass an allowed `--url-host`. Public/WAN exposure is
  unsupported. IPv6 wildcard example:
  `--bind :: --allow-host xsm --allow-host ::1 --url-host xsm`.
- `.dreamwork/skill-version` — which skill version this target last ran
  under; init's update check reads it (`initialization.md`).
- All of it is committable project content, like CLAUDE.md.

## Task-list conventions

- Every task needs a permanent id, and wears it at the front of its
  subject (`#91 — …`) — the subject is the field every backend reads
  back. A backend that mints durable ids does that itself; where the
  ledger is a separate file, the coordinator takes its next id and bumps
  it.
- Every task also knows what it is *for*: a one-line `goal`, and the
  `parent` it serves (a session goal, or a DREAMWORK.md sub-goal by
  name). It states its chain when it starts — see the scope gate. One
  line, never a document; a chain that needs a paragraph is a sign the
  work does not belong to it.
- Every entry records `origin` at the moment it is filed —
  `**human**` when he asked, `**loop**` when we thought of it (contract:
  `file-formats.md`; `lint.py` ERRORs on a governed entry without exactly
  one marker). It is the one required field that the selection list below
  does not carry, because it is provenance rather than something triage
  reads — which is why filing from the Commands section alone used to mint
  an entry that failed lint on the next increment.
- The ledger carries what selection and triage read: `priority` (P1-P3),
  `type` (idea | task | bug | experiment | chore), `feasibility` (note
  from triage), the next-up mark (an event, not a column — set by `do next`,
  cleared on start, and it ranks `list` rather than merely tagging it),
  owner or blocked-on, and — once a task is scope-gated — its `goal` and
  `parent`. Mirror them into the backend's `metadata` where it surfaces
  them (Guardrails: never depend on a channel you have not read back).
- Work that arrives with a durable id upstream (a forge issue a plugin
  ingested) keeps that id and takes no loop id or ledger line until the
  loop actually starts on it — a poll re-derives the item, never the
  loop's progress on it. The rule and its edge cases live with the
  plugins that produce such work: `writing-plugins.md`.
- Dependencies recorded however the backend expresses them (Claude Code:
  `addBlockedBy` / `addBlocks`), and on the ledger line either way.
- Big features get a planning doc on disk (`.dreamwork/docs/plans/<slug>.md`
  or the repo's convention); the task itself is a thin pointer. Bulk stays
  out of the task list until it's actually time to implement.

## Commands

Most bare user messages map to one of these; when ambiguous, ask (via `attn`
if Max is away).

- `do now: <text>` — immediate. Park the current increment at a coherent
  point (commit it, or stash and split a remainder task), create the task
  as in_progress, and work it right away.
- `do next: <text>` — queue-jump. Create the task, then mark it with
  `ledger.py next-up <id> --why '<his words>'`; it gets picked as soon as the
  current task lands, ahead of priority order. Several next-ups: newest first
  — the human's latest steer wins. **Mark it in the same increment you file
  it**: the mark is the only durable home the steer has, and a steer left in
  session context is a cache, not a memory (#884). Bare `do next` (no text):
  just run the selection algorithm now.
- `add idea: <text>` — capture, then expand. Add to the task list slotted
  by priority (feasibility-triage if complex); doesn't jump the queue.
  Then briefly develop the idea in line with the project's philosophy and
  goals: clearly-aligned implications and subtasks enter the task list as
  normal tasks; unclear extras park in `.dreamwork/questions.md`; and
  since the human just typed this, a one-line consult now beats guessing.
  Generalized: any sensible `add <thing>:` matches (`add idea` stays
  canonical) — the thing becomes the task's `type`. `add bug:` captures
  richer detail (repro, expected vs actual, severity — ask one line if
  missing); `add task:` / `add chore:` / `add experiment:` map directly;
  `add question:` routes to questions.md instead of the task list;
  anything else sensible maps to the best-fit type.
- `maintenance` / `do maintenance` / `maintenance: <item>` — run the
  maintenance rotation now, regardless of backlog state; without an item
  named, `roll.py --no-backlog` can pick one.
- `parallelize` (or "parallel" and similar) — fan out dreamers across
  pending tasks with disjoint file ownership (Subagents has the test).
  Report what could not be, and why.
- `status` — current task, queue summary, recent completions, open
  questions from `.dreamwork/questions.md`.
- `pause` / `resume` — TaskStop the heartbeat monitor / re-arm it.
- `wrap up` — land the current increment cleanly, commit, summarize, and
  note any friction with the loop itself — fix small, file the rest.
  Check the queue is restorable — where the ledger is a separate file it
  should already match the backend; if it doesn't, an increment skipped
  its reflection. (A check, not the mechanism: the restart that cost
  eight tasks had no wrap-up.) Then look at the session goal: if it
  turned out to be something the project will keep wanting, promote it
  into DREAMWORK.md as a sub-goal.

## Guardrails

- Commit each increment. Never push or deploy unless DREAMWORK.md or the
  project's CLAUDE.md/config explicitly authorizes it.
- Mark maintenance commits `dreamwork(maintain:<item>): ...` — git is the
  maintenance ledger (roll.py reads it for staleness). A maintenance pass
  that changes nothing may record an `--allow-empty` marker commit.
- **A commit that changes what an existing install must do says so in a
  git trailer** (#194) — a final `Key: value` block, which
  `git log --format='%(trailers:key=Feature,valueonly=true)'` extracts
  with no parser:
  - `Migration: <migrations/ filename>` — this commit added a migration.
  - `Feature: <one line>` — a target gains something worth surfacing when
    it upgrades.
  - `Needs: config` or `Needs: consent` — that feature is not automatic.

  Only when true. A trailer on every commit is a trailer on none, and the
  upgrade pass would be back to reading everything. This is what lets it
  start from a candidate list instead — so it is worth writing on the day
  the commit is made, by whoever knows, rather than reconstructed later
  by someone who does not.
- Verification before completion: the project's verification passes
  (tests/lint, or its stated routine) before a task is marked completed.
- **A new check is not verification until it has been red.** Reintroduce
  the bug, watch the check fail, then fix it. A check that has never
  failed proves only that it ran — and checks fail quietly in ways that
  read as passing: watching a window long enough that something else
  produces the expected result, driving the route that was easy to
  automate rather than the one the human uses, or comparing nothing at
  all because the comparison errored and the error was swallowed. When a
  check and the code disagree, suspect the check.
- **Experiments are feature-gated, and the gate is a file.** An experiment
  ships **off by default** behind its own tracked `.dreamwork/<name>` file —
  the `watch-tint`/`run-mode` family, where **absent means off** — with a
  `file-formats.md` row and a `lint.py` check like every other member. One
  file per experiment, no registry, and turning it off is deleting a line:
  the human does it without waiting for the loop.
- **Judgement between rivals uses IGC.** Choosing between rival options —
  candidate tasks, designs, libraries, approaches, the options laid out in
  a review — is an IGC evaluation, not a score or a gut pick: ideas down
  the side, goals (binary, or a breakpoint of *enough*) across the top,
  ✔/✘/? per cell, an All column that rolls up, and the decisive error
  written under each ✘. The method is bundled at `<skill-dir>/igc-method.md`
  (depth on *why* binary beats scoring: `igc-concepts.md`), so an install
  without the separate `use-igcs` skill still has it — load it at the
  moment of the choice, not as background. **Buy:** a single decisive
  error refutes an option no matter how attractive it looks elsewhere,
  and scoring hides exactly that. **Cost:** a matrix on a trivial choice
  is waste, so scale it to the decision (a 2×2 in a sentence for a small
  one; lay the table out for a real fork) and skip it where the options
  are not rivals of each other. Zero survivors means fix the framing,
  not pick a refuted option; two means find the real differentiating
  goal, never break the tie by scoring.
- Compaction-safe: durable state lives in files — DREAMWORK.md,
  `.dreamwork/` (dreams, docs, plans), and commits — never only in
  conversation, and never only in a session-scoped task backend. When a
  compaction is announced, run the checklist in `compaction.md` before
  it happens; a notice is the only window for what only you know.
- Never let the loop depend on a channel you have not read back. Task
  backends accept metadata they may never surface (Claude Code's
  `TaskGet` returns subject, status, and description — no metadata), so
  anything selection or triage reads lives in the subject, the
  description, or the ledger.
- A symptom is not a diagnosis. When capturing a bug the human reports,
  record what they *saw*, in their words; any cause you propose is a
  hypothesis and gets labelled as one. A dreamer handed "the joiner is
  swallowing entries" will go and fix the joiner — and a confident wrong
  layer costs hours, where reproducing the input costs minutes. Reproduce
  before building. Two specific liars, both of which have cost time here:
  the human sees the **deployed** dashboard, which may be older than HEAD
  (`deployed.py --target .` says by how much, and the hub shows it per
  project — a fix sat undeployed and read as broken on #129); and the
  element whose re-render he can SEE gets blamed for what happens on
  every re-render (#179, #184).
- Mismatched signals mean something is wrong. When context disagrees with
  itself — e.g. the cwd doesn't match the work being discussed, the task
  list contradicts git — don't guess and don't proceed on the wrong
  assumption: ask the human.
- Every ask is recorded. Never propose something needing the human's
  response without writing it to `.dreamwork/questions.md` in the same
  breath — they may be afk or miss the message. Unclear goals park there
  too, instead of being guessed at.
- Scope gate — **name the chain**. Agent-initiated work that adds new
  surface area (a new file, section, or feature) or breaks the size
  norms has to state its chain out loud first: this task serves *that*
  session goal, which serves *that* goal in DREAMWORK.md. The chain
  ends at the highest goal that exists — two rungs is a chain. If you
  can't name it without inventing a link, that is the answer — park it
  in questions.md instead of doing it. If *nothing* can be named
  because DREAMWORK.md holds no goals yet, the gate is telling you
  about the goals and not the work: park one question asking for them,
  not one per task. Human-initiated steers are never gated. Defaults
  and silence may resolve *how* or *when* for already-authorized work
  — never *whether* to add new surface; parked scope questions stay
  parked until answered.
- Surface contradictions. When what the human says now conflicts with
  recorded state (DREAMWORK.md, docs, the implementation), say so plainly
  and presume they know how to resolve it — it's wavelength-matching, not
  fault-finding. Fold the resolution back into DREAMWORK.md. Restoring
  alignment is priority work, not deferred maintenance: small drift folds
  in immediately; bigger drift becomes a top-of-queue task.
- Communication: brief updates as you go; `attn` only for genuine blockers,
  questions, or notable milestones. Subagents never use `attn`. **Check
  that the push actually left** — `attn` exits non-zero when its backend
  refuses, and a failed push nobody noticed is worse than none, because
  the loop then believes it escalated. On failure use whatever the harness
  offers (Claude Code: `PushNotification`) and name the channel that
  carried it. Whatever happens, the ask is already in `questions.md`, so
  the dashboard remains the durable path and a dead pusher costs the pull,
  not the message.

## Wake mechanisms (variants)

The Monitor heartbeat (armed in `initialization.md`) is the default and
preferred mechanism; consider `/loop` where available. For harnesses with
hooks but no Monitor tool, a Stop-hook fallback exists — reference design
and caveats in `stop-hook-variant.md` in this skill's directory.
