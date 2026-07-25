# #120 — SKILL.md fresh-eyes review

Reviewer: reviewer-skillmd (no prior context on this project).
Reviewed: `SKILL.md` @ 420 lines, md5 `d8939ef4fb60f9de17262ebcc4ffac29`, last
commit `d26ff3e` (11:41), clean tree. Both changes you flagged mid-review —
the lessons.md claim-plus-evidence bullet (203-211) and the Formats bullet
(248-253) — were already in the copy I read, so every line number below is
current.

Also read in full: `initialization.md`, `reflection.md`, `compaction.md`,
`file-formats.md`, `writing-plugins.md`, `stop-hook-variant.md`, `README.md`,
`DREAMWORK.md`, `.dreamwork/lessons.md` (59 entries). Verified against code
and repo state: `.gitignore`, `git ls-files .dreamwork/`, `justfile`,
`lint.py`, the `POST /command` path and `log_event` in `watch.py`, `roll.py`
argparse, the `TaskUpdate` tool schema, and the SKILL.md line-count history
across today's 30 commits.

Ranked by value.

---

## 5. Verdict on 420 — leading with it, because it frames everything else

**420 is not the problem. The rate is.** I would not reorganise to hit 200.

The 200/500 rule of thumb is written for skills that get skimmed once on load
and then ignored. This one is not that: it is the loop's operating manual,
re-read on reload, and it competes for context against almost nothing else in
the session. On that trade a line is cheaper than a pointer the loop might not
follow. Under-referencing is the failure you already paid for; over-trimming
this particular file would buy back tokens nobody is short of.

What *is* a problem is the slope. From today's history:

```
c5a7cd2 03:15  246 lines
93246fe 08:23  331
d2eeb69 09:17  380
2c8a7f2 10:54  406
d26ff3e 11:41  420
```

174 lines in about nine hours, because **every coherence finding lands as prose
in SKILL.md**. At that rate it clears 500 tomorrow and the trim gets
re-litigated weekly. The durable fix is a routing rule, and it is worth more
than any individual cut below:

> **A finding lands where its trigger lives.** Behaviour that must fire
> unprompted → SKILL.md. Shape of a file → `file-formats.md`. Procedure with a
> nameable trigger (init, compaction, worktrees, plugins) → that trigger's
> reference file.

About two thirds of what I propose moving is *misrouted* by that rule rather
than merely long. Target ≈ 360 lines — with one line **added**, not removed
(F1).

---

## 4. Missing, self-contradictory, or no longer true

You guessed right that this is the valuable part.

### F1. The dashboard composer's commands have no durable channel, and the tick flow never reads the one they do have

This is the same failure class that bit you this morning, live right now, on
the human's own input channel.

`POST /command` writes exactly one thing, and `watch.py:3097-3099` says so in
its own words:

> `# Accepted POST /command kinds, derived from the one vocabulary (COMMANDS,`
> `# top of file). Each becomes a source-tagged watch-events.log line the loop's`
> `# tail monitor wakes on (same transport as answers); no file is written.`

`log_event` is best-effort and swallows `OSError` silently (`watch.py:3082-3094`),
and `.dreamwork/watch-events.log` is gitignored (`.gitignore:3`).

Now grep SKILL.md for `watch-events`: **zero hits.** The string appears only in
`initialization.md:98-101` ("also arm a tail … Without a Monitor tool, check
that file's mtime in the tick loop") and `compaction.md:60-62`.

Meanwhile SKILL.md:78-81 explicitly re-checks the *other* channel on every tick:

> `And if questions.md changed since your last look, check for new`
> `human-authored blocks (Note (human, via …)) — fold them first`

So the asymmetry is: **answers are durable** (they land in `questions.md`, which
the tick re-reads) **and commands are not**. A `do now:` typed into the composer
is lost with no error anywhere whenever the tail monitor is not armed — a
resumed session, a post-compaction session that skipped the far-side check in
`compaction.md:59-63`, or any session where `watch.py` was started after init
ran. Compare `lessons.md:133-136`: *"Nothing surfaces a silent write failure on
the human's own input channel."*

The fix is one line, in the tick flow, beside the questions.md check — not in a
reference file, because there is no trigger that would make the loop go look:

> `Same for .dreamwork/watch-events.log — dashboard commands exist only as a`
> `line in it, so if the tail monitor is not armed, its mtime is the only thing`
> `that will tell you he steered.`

I would land this before any cut on this page.

### F2. SKILL.md:267-268 is factually false

> `The one .dreamwork/ file that is **gitignored**: it's ephemera, not history.`

`.gitignore` ignores two of them: `.dreamwork/status.json` (line 2) and
`.dreamwork/watch-events.log` (line 3). Separately, `.dreamwork/watch-port` is
**tracked** — it shows in `git ls-files .dreamwork/` — so a live localhost port
number is committed as project history, which is exactly what SKILL.md:277
(`All of it is committable project content, like CLAUDE.md`) endorses. Those two
sentences already disagree with each other ten lines apart; the `.gitignore`
makes the first one false as well.

Cut 267-268 rather than repair it. The `.gitignore` is the fact, and prose about
a fact drifts — `lessons.md:224-230` is precisely this lesson, about this file.

### F3. `lint.py` is invisible to SKILL.md and to the per-increment loop on every target but this one

`lint.py` is named once in SKILL.md, at line 210, and only as an example of a
lesson that has graduated. The places it actually runs:

- `initialization.md:175-182` — once, at init.
- `justfile:7` (`test: pytest lint guards`) and `justfile:16-17` — here, this repo.
- `reflection.md` — the checklist run after **every change** — never.

On a target project, "the project's verification passes" (SKILL.md:366) means
the *target's* tests, which will never invoke dreamwork's linter. So off this
repo, the detection window for an unreadable `questions.md` is *next session*.
`file-formats.md:91` already asserts the loop is closed — "**`lint.py` is the
enforcement**" — and off this repo it is not.

One line in `reflection.md` step 3 closes it: *if the increment touched
`.dreamwork/`, run `python3 <skill-dir>/lint.py --target .`*.

(Task #137 — which I flagged as stale mid-review — has since been closed with
the wiring noted. No action.)

### F4. Philosophy has acquired an implementation, and it is the wrong one

SKILL.md:26-29:

> `**Ideas always go in the task list.** No idea is lost, and no work happens`
> `that isn't a task. The list is the loop's brain; the ledger`
> `(.dreamwork/tasks.md) is what makes it durable — a backend that`
> `forgets on restart is a cache, not a memory.`

On a `bl` target there is no `.dreamwork/tasks.md` — SKILL.md:216-220 says so
explicitly ("On a backend whose list and ids survive a restart (`bl`) it *is*
the backend, and there is no extra file"). So the Philosophy section states as a
principle something the skill's own Durable-state section contradicts.

This is `lessons.md:83-86` verbatim — *"A fix stated in terms of its own
implementation breaks the other implementation"* — and it is the one line the
ledger-as-concept pass (`3d6a643`, 08:42) missed. Revert 26-29 to the principle
alone; the durability mechanism belongs at 216-230 and nowhere else. This is a
correctness fix, not a length one.

### F5. Goal alignment sits at both ends of the selection algorithm

- Step 0, SKILL.md:88-90: `any known goal/philosophy misalignment (DREAMWORK.md stale or contradicted) outranks everything below`
- Step 4, SKILL.md:120-122: `goal alignment first — does DREAMWORK.md still reflect what the human wants and what the loop has learned?`

The distinction is real — step 0 is a finding you already hold, step 4 is the
periodic check that *produces* findings — but it is stated nowhere. Read cold,
step 0 licenses auditing DREAMWORK.md before every single selection, which is
the make-work gradient (`lessons.md:11-13`). Three words fix it: *"a
misalignment **you already know about**"*.

### F6. One backend-specific leftover in a deliberately backend-neutral section

SKILL.md:309: `Dependencies via addBlockedBy / addBlocks.`

Those are Claude Code `TaskUpdate` parameters — I checked the schema, they are
real, and they are Claude-Code-only; `bl` has no such verbs. Lines 216-230 went
to considerable trouble to stop naming an implementation. This line is the
survivor of that pass. Same family, lower stakes: SKILL.md:249's "read it before
writing one of those files **for the first time**" is ambiguous across actors —
a freshly spawned dreamer has never written one, so the rule is per-actor and
should say so.

---

## 1. What must stay, and the behaviour that breaks if it is a click away

1. **The tick flow, 59-81, entire.** Above all 60-61:
   `Ticks are monitor events, not user input — never treat one as a reply or an approval.`
   This is needed at the one moment the loop has no reason to look anything up —
   it has just woken, mid-nothing. Its failure mode is converting silence into
   consent, which is the exact thing the scope gate at 393-405 exists to forbid,
   and it is unrecoverable after the fact (work gets done that nobody
   authorised). Highest stakes per line in the file.

2. **The selection algorithm, 83-132.** The idle branch is by definition the
   branch where no other trigger fires; a pointer here would be followed only by
   a loop that already knew what it was looking for. Step 2's dot line (97-99)
   only functions *in front of the reader* — "explicit thinking time" behind a
   link gets read past, not performed. On #119's proposed `selection.md`: I would
   argue against it for steps 0-3. The maintenance rotation (119-131) is the one
   movable part and it is 13 lines, which does not justify a fourth reference
   file.

3. **The scope gate, 393-405.** Fires precisely when the loop is most confident
   it should act, i.e. when it is least inclined to consult anything. Its failure
   mode is agent-initiated surface area, which is DREAMWORK.md:29-31's named
   anti-goal ("not runaway automation … no make-work, no ungated experiments").

4. **Disjointness and the staging rule, 155-165**, especially
   `git add -A sweeps up their half-finished work and buries it in your increment.`
   Silent, no error, and it actually happened (`lessons.md:68-70`). It fires
   while committing, which is not a moment anyone stops to look up delegation
   rules.

5. **"Every ask is recorded", 389-392**, together with the questions.md tick
   check at 78-81. The channel to the human; the whole point of the ask
   discipline is that it binds when the loop thinks the conversation was enough.

6. **Philosophy, 19-43** (with F4 fixed). This is the value function consulted
   when no specific rule fires — the thing that decides what "productive" means
   at 3am. It is also the section a naive trimmer attacks first, because it reads
   as prose rather than procedure. Do not touch it.

7. **The `wrap up` ledger check, 352-355** — *including* the parenthetical
   `(A check, not the mechanism: the restart that cost eight tasks had no wrap-up.)`
   The evidence is what makes the check get run rather than ticked. This is the
   model for how a war story earns SKILL.md space; see M1.

---

## 2. What should move, where, with the pointer drafted

The rule I applied for war stories, since several of these are one:
**a war story stays in SKILL.md only when it has been compressed into the clause
it justifies.** Once it needs a date, an incident, or a second sentence, it
belongs in `lessons.md`. 354-355 is the good form (seven words, at the point of
use). 209-210 is the bad form.

### M1. lessons.md craft guidance, 205-211 (7 lines) → the `lessons.md` row in `file-formats.md`

This is your 11:41 change and the strongest single move. It is the best-written
prose on the page, which is exactly why it goes first. Its trigger is nameable
("about to write a lesson"), nothing parses it (`file-formats.md:80` says "prose
only"), and a miss degrades to a slightly worse lesson rather than a silent
failure. The offending passage:

> `— "test your tests" persuades nobody, while "the serial-poll`
> `test built its own thread pool and passed on a serial implementation"`
> `cannot be argued with.`

That incident is already at `lessons.md:231-239`, in its proper habitat,
alongside the two sibling cases that make it a pattern rather than an anecdote.
Quoting it in full in SKILL.md to make a style point is the thing the rule
above forbids.

Keep the *behaviour* half (pruning during grooming) in SKILL.md; move the craft
half. Pointer:

> `- .dreamwork/lessons.md — important lessons, each outliving the dream it`
> `  came from: a claim you could read on its own, then the concrete case that`
> `  earned it. Prune when a lesson graduates into a guardrail or a check.`
> `  What a good entry looks like, and why the evidence half is load-bearing:`
> `  file-formats.md.`

### M2. status.json, 259-272 (14 lines) → ~6

Lines 263-268 (runtime state, dreamer ownership, why it must survive within a
session) are substantively duplicated by `compaction.md:37-42`, which is the
file that fires at the precise moment the content matters. Keep in SKILL.md:
timestamps from the system clock never memory (an anti-hallucination rule, and
cheap), gitignored, and the `python3 <skill-dir>/watch.py --target . --open`
invocation with `.dreamwork/watch-port` — that last one is a command a human may
ask for by name. Cut the duplicate of 75-78. Pointer:

> `…it also carries the loop's runtime state — which dreamers are out, what`
> `files each owns, which monitors are armed. That state dies with the session`
> `but must survive within one, because a compacted coordinator that forgets a`
> `dreamer owns foo.py will edit foo.py; what to write and when: compaction.md.`

### M3. questions.md, 231-247 (17 lines) → ~7

The single largest bullet in the file. Cut the author-tag syntax (240-243): it
is duplicated, and more precisely, at `file-formats.md:36-37` and `57-61`, which
is where the parser's closed set belongs. Cut 234-236 (see §3). Keep what it is
for, the threading and re-fold semantics at 243-245 (behaviour, not shape), and
245-247 — which is **already the best pointer in the file** and should be the
template for every other one, because it tells the loop *whether* it needs to
look:

> `**Its shape is a contract, not a style** — watch.py matches ## Open and`
> `## Answered literally, and a file that misses them parses to nothing and`
> `renders as "nothing to answer", silently. See file-formats.md.`

Your new Formats bullet (248-253) is the same good form. Keep it verbatim.

### M4. Worktree lifecycle, 167-177 (11 lines) → ~4

> `merge back to the parent branch on acceptance and clean up the worktree —`
> `checking first for valuable untracked files (scratch, reports), which move`
> `out before removal, never get force-deleted`

is a near-verbatim restatement of the global `CLAUDE.md` Worktrees section,
which is loaded into every session regardless of this skill. Keep the rule
(when disjointness cannot be arranged, isolate by construction) and the
shared-build-cache caveat — that one is *not* in CLAUDE.md and is a real storage
cost.

### M5. Upstream-id rule, 300-308 (9 lines) → 2

Its only producer is a plugin, and `writing-plugins.md`'s Tasks extension point
states it at greater length and better, including the candidate → started
transition. Pointer:

> `Work that arrives with a durable id upstream keeps it, and takes no loop id`
> `or ledger line until the loop actually starts on it — the rule and its edge`
> `cases live with the plugins that produce such work: writing-plugins.md.`

### M6. `skill-version`, 273-276 (4 lines) → one line in the file list

Pure duplication of `initialization.md:147-151`, and init's update check is the
only thing that ever reads it. Nothing at tick time touches it.

### M7. `parallelize`, 342-346 (5 lines) → 2

Restates the disjointness test already given at 155-165.

> `parallelize — fan out dreamers across pending tasks with disjoint file`
> `ownership (Subagents has the test). Report what could not be, and why.`

### M8. 296-299 → a cross-reference

> `because the scope gate asks every actor to name a chain and a link no one`
> `can read is a link no one can name` … `but never depend on that unread`

restates Guardrail 374-378 eighty lines later. Keep the Guardrail — it is the
general form and cites the verifiable `TaskGet` fact — and trim 296-299 to
"mirror them into the backend's `metadata` where it surfaces them (Guardrails:
never depend on a channel you have not read back)".

### Explicitly leave alone

"Dreamers are batches, not careers" (179-186). It is an explicit human steer
(`fc8dfca`, "human steer 2026-07-25"), and human steers should stay where the
human can see they were honoured. Compress to ~5 lines if you like; do not move
it behind a pointer.

---

## 3. What to cut entirely, quoted

- **15-17** — the opening paragraph:
  > `Long-running, free-flowing development. Not the most direct or fastest path,`
  > `but efficient, sustained, and never stuck or bored — built for ongoing`
  > `open-ended improvement of a project.`

  This is the frontmatter description in better clothes, and the frontmatter is
  what actually gets read when deciding whether to load the skill. True, well
  written, inert.

- **234-236** —
  > `Chat is not durable — every user-facing ask gets an entry here when made,`
  > `with enough context to answer cold.`

  Restated as a Guardrail at 389-392.

- **240-243** — the author tags and the legacy forms:
  > `a human's note is tagged - **Note (human, via <channel>, <ts>):**, the`
  > `loop's own is - **Follow-up (loop, <ts>):**. … Older entries may read`
  > `(via <channel>, …), which was a human, or (in-session, …), which was the loop.`

  In `file-formats.md:57-61`, where the parser is. Note the *rule* it serves —
  "**Whose words they are is never in doubt**" (240) — stays; it is the
  behaviour. Only the syntax goes.

- **273-276** — the `skill-version` bullet. In `initialization.md:147-151`.

- **267-268** — `The one .dreamwork/ file that is **gitignored**: it's ephemera,
  not history.` Cut because it is false (F2), not because it is long.

- One of **75-78** / **259-261** — status.json "rewritten each tick", stated twice.

Net: ≈ 58 lines out, 1-2 in. Lands around 360.

---

## On the counter-pressure

You noted several trims were rejected today because the removed clause was
load-bearing for a case that had just bitten. Sorting my proposals by that
exposure, so you can spend your judgement where it matters:

- **No exposure** — M6 and every cut in §3. In each case the surviving copy
  already sits at the firing site, or the line is false.
- **Low** — M1, M4, M5, M7, M8. Trigger is nameable and the drafted pointer
  names the stakes.
- **Expect pushback, and concede cheaply if you feel it** — M2 and M3. Both were
  written in direct response to today's failures, which is the exact profile of
  a clause that gets defended. My argument is that in both cases the full text
  lands in a file with a *harder* trigger than SKILL.md has: `compaction.md`
  fires on a notice, `file-formats.md` fires on "about to write this file", and
  SKILL.md fires on nothing in particular. If that argument does not land for
  you, keep them — the cost is twenty lines, and neither is a principle worth
  arguing over.

**F1 has no such defence available, because it is not a trim.** Nothing in
SKILL.md reads the channel the dashboard composer writes to, and a human's
`do now:` is lost silently whenever the tail monitor is not armed. That edit is
+1 line and I would land it first.

---

## Housekeeping

Task #120 left `in_progress`. The single-writer rule I spent this review
defending applies to me too, and closing it here would put the backend ahead of
the ledger you own — call it when you fold this in.

Unrelated, noticed in passing: `bug-report-ezfb-01.tmp.md` (167 lines) is
sitting in the skill root. It is gitignored by the `*.tmp.*` rule, so it is
invisible to `git status` and will outlive whatever needed it.


---

## Coordinator's disposition, 2026-07-25 (added after the review)

**Landed:** F1 (the live one), F2, F4, F5, F6 in `6827daa`; F3 into
`reflection.md` in the same commit. The routing rule is in the doc-map.

**M2 and M3 are KEPT, deliberately** — recorded because the reviewer
correctly pointed out that silence makes them unmarked exceptions to a
rule this repo has now adopted, and the next fresh reader would
otherwise re-derive the whole argument.

The reason is the one its own risk-sort predicted: both were written in
direct response to failures the same day, and both describe behaviour
the loop must get right *unprompted*. `status.json`'s runtime state
(M2) is what a compacted coordinator reads before it knows a compaction
happened; `questions.md`'s threading semantics (M3) bind at the moment
the loop decides whether an answer reopens a question. Neither has a
trigger that would make the loop go and look. That is the routing rule
applied, not waived — SKILL.md is where a thing goes when its trigger is
"nothing in particular".

The author-tag SYNTAX inside M3 did move, to `file-formats.md`, which is
the half that had a trigger.

**The rule's fourth bucket, unresolved:** the reviewer noted that
routing has three destinations (unprompted behaviour, file shapes,
trigger-named procedures) and no home for CRAFT. M1's lessons.md
claim-plus-evidence guidance went to `file-formats.md`, which is a
forced fit since nothing parses `lessons.md`. Acceptable for one rule.
**A second craft rule is the signal to split it out** rather than keep
widening that file's remit. Tracked in #145.
