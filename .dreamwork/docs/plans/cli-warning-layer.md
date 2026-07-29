# CLI warning layer — a footer every `dev/ledger.py` verb emits (#357)

> **DESIGN ONLY. No code.** This document changes no `.py` file, no
> `file-formats.md`, no `lint.py`, no running loop. It is prose plus measured
> facts plus one open call, written to be ruled on or built. The footer does
> not exist yet; this is the design for it.

Origin: **human** (task #357, two says on 2026-07-28). On #346 S4 (01:23): *"with
these kinds of things we can have an automated warning layer in cli calls that
raises issues where data is incomplete or whatever. Also things like unchecked
message count, new task count, new question count, unanswered question count,
unfolded-in answer count, etc."* — and on #264 (02:45), in the same hour he saw
his own answer sit unfolded for sixty-four minutes: *"proper tooling will prevent
that!"* The #366 check that exists today (`lint.check_unfolded_answers`) opens its
own docstring by quoting him verbatim and naming itself *"only #357's interim
half — it fires when someone runs `lint.py`, whereas he wants the count tacked
onto every invocation, which is ambient rather than opt-in."* This doc is that
ambient half.

**The shape is settled by his word "tacked on":** a footer every verb emits, not
a verb you have to remember to run. It rides output the human already sees.

---

## Two load-bearing facts, measured READ-ONLY

All measurements taken against the live main checkout (`24d560f3`, 2026-07-30)
under `file:.dreamwork/ledger.sqlite3?mode=ro` (uri=True), the questions/answers
parsers, and the journal — the same READ-ONLY posture the brief mandated
(worktrees lack the store; only the main checkout has it).

### 1 · Every count the footer needs is queryable today, and the whole suite runs in single-digit milliseconds

The five counts he named plus the incomplete-data warnings map onto EXISTING
readers with no new parsing. Measured live, the **full footer suite — all five
counts plus the two incomplete-data counts — completes in 8.19 ms**, against a
budget of 50 ms (the verbs run interactively; the footer must never be the thing
that makes a `fold` feel slow):

| his count | source (reuse, never rebuild) | live value | measured cost |
|---|---|---|---|
| unchecked messages | `answers.md` `## Open` — `watch.parse_open_answers` | **0** | (folded into the 3.25 ms questions/answers parse below) |
| new task count | the store — `task WHERE state='open'` (or `ledger_parse.store_ids_by_state`, the projection `counts` already uses) | **120** | 0.20 ms (3-count suite, warm) |
| new question count | `questions.md` `## Open` — `watch.parse_open_questions` | **2** | (within the 3.25 ms parse) |
| unanswered question count | `questions.md` `## Open` — **the same set** as "new questions"; an open question IS an unanswered one | **2** | (free — same parse) |
| unfolded-in answer count | `lint.check_unfolded_answers` (`lint.py:732`) — it already computes exactly this and reports the AGE; the footer only counts its rows | **0** | 0.63 ms |

Plus the incomplete-data warnings (his "data is incomplete or whatever"):

| warning | source | live value | measured cost |
|---|---|---|---|
| `task.type` is NULL | the store — `type` column, NULL means "never classified" | **234 of 383** | 0.11 ms |
| `task.origin` is NULL | the store — `origin` column, NULL predates the cutoff (#213, < #216) | **107 of 383** | (same query) |

The store timing is dominated by the FIRST connection open on a cold process
(84.7 ms the first query; 0.2 ms every query after). The footer opens once and
reuses the connection, so the warm figure is the honest one — and even the cold
figure is under budget because `counts` already pays that open. The
questions/answers parse is the heavier half (3.25 ms) because it walks the whole
file through `watch._parse_entries`; it is still 6% of the budget.

**The journal has a count he did not name but the footer can carry cheaply:**
`head_ordinal - coordinator_cursor.scanned_through` = unconsumed receipts. Live:
head **25**, coordinator cursor **absent** (never created — the E3 cutover wrote
receipts but no consumer has advanced past them), so **25 unconsumed**. This is
the durable "something is waiting" signal; the wake line is best-effort and dies
on compaction (`SKILL.md:117`). The count is one indexed read (0.97 ms). Whether
it belongs in the footer is the open call below — it is not one of his five.

### 2 · The seam the footer rides already exists, and every verb returns through it

`dev/ledger.py:main` dispatches on `args.cmd` and every branch ends in
`return 0` (or `return 1`/`return 2` on a refusal). The footer is one function
called at exit, before that `return 0`, that writes to **stderr** (so it never
corrupts a verb's stdout — `counts` is parsed, `fold --dry-run` writes the file
text, and piping either through `head` must keep working). The verbs that change
state (`fold`, `file`, `note`) and the read verbs (`counts`, `sweep`) all pass
through `main`'s tail, so one call site covers all five verbs. The footer is not
a sixth verb; it is a tail on the five that exist.

---

## The contract

### What the footer contains — his five counts plus incomplete-data warnings, and nothing else

One line per non-zero count, in his order. Nothing the loop is doing, nothing
about agents or posture or deploy — those belong to `status.json` and the
dashboard, which is a different surface with a different reader. The footer is
the narrowest possible answer to *"what is not folded in etc."*:

```
warnings: 120 open tasks · 2 unanswered questions · 234 untyped · 107 missing origin · 25 unconsumed receipts
```

The five counts and the incomplete-data warnings are the whole content. The
shape is deliberately a single dense line (not a table, not a box) because this
rides output the human already scrolled to — a footer that takes three lines of
terminal teaches him to scroll past it, which is the failure this design exists
to prevent.

**"New question count" and "unanswered question count" are the same number.** An
open question in `questions.md` IS an unanswered question — there is no second
state between "asked" and "answered." Measuring it twice would be a second
reader of one fact, which is the dual-write failure this repo refuses. So the
footer emits one count for both, and the doc records the collapse so a future
reader does not "restore" a number that was always the same number.

### Where it lives — one function in `dev/ledger.py`, called by every verb at exit

A single function — proposed name `emit_warnings(dw_dir)` — in `dev/ledger.py`
(or a sibling module it imports, if the function grows). Every verb's success
path calls it before `return 0`. It is:

- **not a new verb** (his word was "tacked on," not "run");
- **not opt-in** (the failure it prevents is an unfolded answer nobody noticed
  for an hour — an opt-in footer is exactly `lint.py`, which is the interim half
  that already exists and that he asked to supersede);
- **on stderr**, so it never touches a verb's machine-readable output.

The function reuses, never rebuilds: it calls `watch.parse_open_answers` /
`watch.parse_open_questions` (the production readers the dashboard uses),
`ledger_parse.store_ids_by_state` (the projection `counts` already uses, so the
footer's "new task count" and the `counts` verb's "open ids" are the SAME number
from the SAME reader), and `lint.check_unfolded_answers` (the function that
already computes the unfolded-answer count and its age). A second implementation
of any of these is the defect the doc must not propose — and it does not.

### WARN, never ERROR — the footer never changes an exit code and never blocks

Every line is a WARN. The footer:

- **never changes the exit code** — a `fold` that succeeded returns 0 and the
  footer's warnings ride alongside, not instead of;
- **never blocks a verb** — a warning that blocks is a verb, and the brief's
  settled shape is "tacked on," not "gated on."

The reason is not politeness; it is correctness. `counts` is a read verb whose
stdout may be piped; `fold --dry-run` writes the file text to stdout; `sweep` is
advisory (exit 0 always, by #404 design). A footer that could non-zero the exit
would break `fold --dry-run | head` and make `sweep` non-advisory, both of which
are regressions of invariants this repo has already paid to establish. WARN on
stderr is the only level that says "here is something" without saying "and
therefore stop."

### Quiet rules — designed against footer fatigue

A footer that always says the same thing teaches him to not read it, and a
footer he does not read is worse than no footer (it costs a read he never
spends). Three quiet rules, in increasing strength:

1. **A count at zero is absent from the line.** The footer never prints
   "0 unanswered questions." A zero is the success state and printing it spends
   the line's credibility on nothing. This is why the live footer today would
   read `120 open tasks · 234 untyped · 107 missing origin · 25 unconsumed
   receipts` (the zero-counts — unchecked messages, unanswered questions,
   unfolded answers — are simply not there). Measured: of the five named counts,
   **three are zero live**, so the line is already shorter than its worst case.

2. **The whole footer suppresses when every count is zero.** If there is nothing
   to warn about, the footer emits nothing — not "no warnings," which is the same
   fatigue in a different font. A clean tree prints exactly what it prints today.

3. **A `.dreamwork/` opt-out for the incomplete-data half only.** The two
   incomplete-data counts (`type` NULL, `origin` NULL) are the noisiest — 234
   and 107 live, and both are LEGITIMATEly NULL for pre-cutoff tasks (origin is
   forward-only from #213/#216, so 107 NULL origins are the honest "never
   recorded," not a defect). A footer that warns on every call over 107 rows
   that are correct-by-design is the textbook fatigue case. So the incomplete-
   data warnings are individually suppressible via a gitignored, tick-re-read
   marker (proposed shape: `.dreamwork/squelch` carrying the warning kinds to
   quiet, same closed-set discipline as `posture`/`run-mode`). The five named
   counts are NEVER squelched — they are the whole point.

**What this design does NOT propose: a "changed since last call" suppress.**
That would require the footer to persist its last-seen counts, which is a
second store of truth that drifts from the real counts (the exact failure
`#362` was filed over: two files holding two halves of one fact). The footer is
stateless: it reads the live counts every call and prints the non-zero ones.
Fatigue is held by rule 1 (zeros absent) and rule 3 (legitimate-noise
squelch), not by remembering what it said last time. **(He later sketched
exactly such a suppress-throttle for the read verbs; the IGC in the rulings
section evaluates it and refutes it decisively — on this invariant (G1), plus
never-suppress-unseen (G2) and surface-early (G3a). It is not on the table.)**

---

## What this design does NOT authorise

A design gets read as a licence. It is not one. This doc is the deliverable; it
authorises **no code.** Specifically, it does not authorise:

- **any `dev/ledger.py` change** — not the `emit_warnings` function, not the
  call site at each verb's exit, not a stderr/stdout split. Those land in
  `#357`'s implementation increment, with their own red-first checks.
- **any `lint.py` change** — the footer *calls* `check_unfolded_answers`; it
  does not move, widen, or duplicate it. (Calling it means a `Report` object
  crosses into `dev/ledger.py`; that is the seam, not a second copy of the
  count.)
- **any `watch.py` change** — the parsers are imported and called as-is.
- **any `ledger_parse.py` or `ledger_store.py` change** — the store read
  projections (`store_ids_by_state`, the NULL-count query) are reused; the
  footer adds no projection and no query path of its own.
- **any `file-formats.md` or schema change** — the `.dreamwork/squelch` marker,
  if he rules it in, lands its closed-set and lint in the implementation commit,
  not here.
- **no migration, no deployment, no change to a running loop or live target.**

---

## Rulings — Q5 settled (every verb); one fork escalated (2026-07-30)

Q5 is **closed: the footer prints on EVERY `dev/ledger.py` verb** — the literal
reading of his word "tacked on," ruled at 2026-07-30 03:11. The "state-change
verbs only" alternative is dropped. (Q1–Q4 below are unchanged from the prior
draft: each had one clearly-superior answer, so none was a fork.)

He ruled with an amendment whose reasoning is **his**, not this doc's: warnings
should surface **EARLY** in the loop so the dreamworker can plan them in. To
that end he sketched a throttle for the READ verbs (`counts`, `sweep`): print
always after a state-change verb (`fold`/`file`/`note`); on the read verbs
suppress ~70–80% of prints, but only while ALL of — the warning is unchanged AND
time since last warning < heartbeat × 0.7 AND warnings skipped since last print
< 4 (every 5th call prints regardless). His words: "Something like that." His
instruction: evaluate it with the vendored IGC method, and surface any issues as
a new question.

That IGC follows. It **settles** one part (the suppress-throttle is refuted —
not his to over-rule; it breaks invariants already paid for) and **escalates**
one genuine fork that IS his.

### Q1–Q4 — settled (unchanged)

- **Q1 (footer contents)** — his five counts + incomplete-data, nothing else.
- **Q2 (where it lives)** — one function in `dev/ledger.py`, called by every
  verb at exit, on stderr.
- **Q3 (WARN never ERROR)** — never changes an exit code, never blocks.
- **Q4 (quiet rules)** — zeros absent, whole footer absent on all-zero,
  incomplete-data squelchable, five-counts never squelched.

## IGC — the read-verb throttle (evaluated per `igc-method.md`)

**Context (the C).** The footer prints on every verb (Q5, settled). Verbs split
into state-change (`fold`/`file`/`note`) and read (`counts`, `sweep`).
`dev/ledger.py` is a **stateless verb process** — each `counts` is a fresh
process with no memory of what it printed last call. The throttle sketch needs
three pieces of memory (last-seen warning, last-print time, skip-count) that a
fresh process does not hold. His goal: warnings surface early so the dreamworker
can plan them in. The design's quiet rules (1: zeros absent; 2: all-zero absent;
3: incomplete-data squelchable) are stateless and must keep holding on a clean
tree.

**Goals (binary; decisive-only — excess-capacity factors omitted).**

- **G1 — Stateless.** The footer writes no persistent state between invocations
  (the sworn invariant in the quiet-rules section: "The footer is stateless; it
  reads the live counts every call").
- **G2 — Never suppresses an unseen warning.** A warning the reader has not yet
  seen always appears; no drift-state can hide one indefinitely.
- **G3a — Surfaces early (presence).** A new warning is visible on the next read
  verb, within the planning/heartbeat window — never delayed past it.
- **G3b — Carries content to plan in.** The read-verb emission carries enough
  that the dreamworker can plan the warning in without a second action (it shows
  WHAT the warning is, not merely that one exists).
- **G4 — Dampens read-verb repeat-fatigue.** The identical full warning line
  does not repeat on consecutive read-verb calls while counts are unchanged.

**Ideas.**

- **I1 — plain every-verb, no throttle.** Every verb prints the full footer
  (zeros absent, all-zero absent). The quiet rules are the whole damper.
- **I2 — his suppress-throttle sketch**, as stated: suppress ~70–80% on read
  verbs under the three conditions; every 5th call prints regardless.
- **I3 — verbosity-split.** Read verbs emit a TERSE hint when any non-zero
  warning exists (presence + magnitude, e.g. `⚠ N warnings — lint.py`);
  state-change verbs emit the full line. Stateless — it decides on verb type
  only, no memory. (A content-preserving variant — full line minus the count
  redundant with the verb — still repeats the rest, so it dampens nothing and
  collapses back to I1; only the terse form actually meets G4.)

**The grid.**

| Idea | All | G1 | G2 | G3a | G3b | G4 |
|------|:---:|:--:|:--:|:---:|:---:|:--:|
| **I1** plain every-verb | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **I2** his suppress-throttle | ✘ | ✘ | ✘ | ✘ | ✔ | ✔ |
| **I3** terse hint on reads | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ |

**Why each ✘ (the decisive errors — the grid is the index, these are the
reasoning).**

- **I2 · G1 (statelessness):** the three conditions each need memory a fresh
  process lacks. The only candidate home is a new `.dreamwork/footer-state` file
  — which is (a) new loop-written, tool-parsed state the design swore off ("The
  footer is stateless"), (b) a new `file-formats.md`/`lint.py` burden, (c)
  contended under concurrent lanes (several verbs in flight write the same
  file), (d) drift-prone on a killed lane. The store is no home either: worktrees
  lack it, and writing on `counts` turns a read verb into a write and breaks the
  read-only posture. The "every 5th prints" safety valve needs the SAME banned
  state, so it cannot rescue the idea.
- **I2 · G2 (never-suppress-unseen):** the "unchanged" comparison reads the
  throttle's own stored last-seen warning; under concurrent lanes or a killed
  write that store drifts, and the throttle suppresses a warning the reader never
  saw — the suppress-forever failure. A stateless footer cannot have this
  failure; a stateful one cannot avoid it on the only state available to it.
- **I2 · G3a (surface early):** a throttle is definitionally a delay device. His
  stated goal is "surface early." On the read verbs — the verbs the dreamworker
  runs to LOOK — the throttle's job is to NOT print, so it can only delay a
  warning past the window, never hasten it. His two wants (surface early +
  suppress on the looking-verbs) are rivals on the read verbs.
- **I1 · G4 (repeat-fatigue):** it prints the identical full line on every
  read-verb call while counts are unchanged — maximal repeat-fatigue, the very
  fatigue the throttle was sketched to address (and on `counts` specifically it
  repeats the open-task count the verb's own output just showed).
- **I3 · G3b (content to plan in):** the terse hint carries presence and
  magnitude but not content; the dreamworker must take a second action (run
  `lint.py`, or hit the next state-change verb) to see WHAT the warnings are
  before it can plan them in.

**Zero survivors — and why that is the answer, not a failure.** G3b (content on
reads) and G4 (no repeat on reads) are **rivals**: the full line carries content
but repeats; the terse hint does not repeat but drops content. No footer shape
on the read verbs has both — that is a fact about read verbs, not a goal that is
wrong or too strict, so brainstorming will not conjure a survivor. Per the
method, zero survivors means: do not pick a refuted option; resolve by dropping a
goal — and which of G3b/G4 to drop is the human's reading-habit call, not the
code's. **I2 is settled as refuted** (G1/G2/G3a are none of them his to relax:
statelessness is a sworn invariant, never-suppress-unseen is correctness,
surface-early is his own stated goal). **I1 vs I3 is the escalated fork.**

The journal unconsumed-receipt count (fact 1's extra) carries on every verb
under the Q5 ruling: it is cheap, and it is the durable "something is waiting"
signal. (It had been held under Q5 only because the state-change-only
alternative would have made it less relevant — a `fold` does not change what is
unconsumed in the journal. That alternative is dropped, so the count carries.)

## Open call for him — one (escalated from the IGC)

> **Q6 — on the read verbs, full line every time (I1) or terse hint (I3)?**
>
> Both are stateless (G1 ✔), both surface immediately and never suppress an
> unseen warning (G2/G3a ✔), and on a clean tree both print exactly what the
> verb prints today (quiet rules 1–2 hold identically — no memory, so no drift).
> They differ on one axis, and it is his:
>
> - **I1 (full line every verb).** The read verb carries the full warning
>   breakdown every call, so the dreamworker can plan them in from a `counts`
>   alone (G3b ✔). Cost: the identical line repeats on every read-verb call while
>   counts are unchanged (G4 ✘) — and on `counts` the open-task count repeats a
>   number the verb's own output just showed.
> - **I3 (terse hint on reads).** The read verb emits `⚠ N warnings` (presence +
>   magnitude) instead of the full line, so no identical repeat (G4 ✔) and no
>   redundancy with `counts`. Cost: the dreamworker sees THAT warnings exist, not
>   WHAT they are, and must run `lint.py` (or hit the next state-change verb) to
>   plan them in (G3b ✘).
>
> This is genuinely his: it trades content-on-the-looking-verb against
> repeat-fatigue on the looking-verb — a reading-habit and workflow judgment the
> code cannot measure (the same class of call Q5 was). The suppress-throttle he
> sketched (I2) is NOT on the table: it is refuted above, and the fatigue it
> targeted is addressable only by I3's terse shape (which he may or may not
> prefer to I1's full shape).
>
> - **rec: I1.** His stated reason for the throttle was "surface early so the
>   dreamworker can plan them in," and on that goal I1 strictly dominates I3 — it
>   shows content every read-verb, so planning needs no second action. The
>   fatigue I1 costs is bounded by rule 1 (zeros absent): the repeating line is
>   short, and on a clean tree it is absent entirely. I3 buys less fatigue at the
>   price of the very thing he said he wanted (content to plan in). If the
>   repeat-fatigue bites in practice, I3 is a stateless drop-in ruleable later
>   with no migration — so the cheaper-to-reverse choice is to start at I1.

---

## Verification — how each claim would be checked

House rule: a new check is not verification until it has been red. This section
names, for each load-bearing claim, how the implementation increment would check
it and which check could be red.

- **The footer never touches stdout.** Check: run each verb, capture stdout and
  stderr separately, assert the footer's line is in stderr and stdout is
  byte-identical to the verb-without-footer. **Red:** make the footer write to
  stdout and watch `fold --dry-run | head` lose its tail / `counts` gain a
  second line. (The production line: the stream the footer writes to.)
- **The footer never changes an exit code.** Check: run each verb with and
  without the footer, assert `return 0` in both. **Red:** make a WARN-branch
  `return 1` and watch a `fold` that succeeded exit non-zero. (The production
  line: the `return` value after `emit_warnings`.)
- **The footer reuses `check_unfolded_answers`, not a second count.** Check:
  name the production line in `lint.py` whose change would red the footer's
  unfolded count (it is the `rep.add(WARN, … "#366")` call completing at
  `lint.py:841`). **Red:** make that line skip and watch the footer's count drop
  to zero while the file still holds an unfolded answer. (The structural-red
  guard from `lessons.md`: the test must call the real `check_unfolded_answers`,
  not a fixture that hand-builds the count.)
- **The footer reuses `store_ids_by_state`, not a second query.** Check: assert
  the footer's "open tasks" count equals `len(store_ids_by_state(dw_dir)[0])`,
  and that changing the store's open set changes both. **Red:** make the footer
  query `task` directly with a different WHERE and watch the two diverge.
- **The full suite is under 50 ms.** Check: a timing test that runs
  `emit_warnings` and asserts `< 50 ms`. **Red:** the measured live figure is
  8.19 ms, so a regression to 50 ms is a ~6× slowdown — assert the budget, and
  the check catches a future reader that adds a second file-walk or a git call.
  (The precondition the check depends on: the suite actually touches all the
  sources — derived at runtime by asserting each source was read, never a
  literal "8 ms" that an empty suite would also pass.)
- **Zeros are absent.** Check: with a clean fixture (all five counts zero),
  assert the footer emits nothing. **Red:** make it print "0 unanswered" and
  watch the check fail. (The precondition: the fixture genuinely has a zero for
  each count — derived, never trusted from layout.)

---

## Primary sources reached

- **the store** (`file:.dreamwork/ledger.sqlite3?mode=ro`, uri=True, main
  checkout `24d560f3`): schema v2, cut over (`ledger_cut_over =
  2026-07-29T12:11:44Z`); **383 tasks** (120 open, 263 landed); **234 NULL
  `type`**, **107 NULL `origin`** (forward-only from #213/#216, so NULL is the
  honest "never recorded," not a defect); the open/landed/NULL counts all
  queryable in < 1 ms warm.
- **`questions.md`** (via `watch.parse_open_questions` / `watch.parse_answered`):
  **2 open**, 67 answered. Parse: 3.25 ms.
- **`answers.md`** (via `watch.parse_open_answers`): **0 open** (his unanswered
  messages to the dreamer), 9 answered.
- **`lint.check_unfolded_answers`** (`lint.py:732`): **0** unfolded-answer
  warnings live. 0.63 ms. The function the footer calls, not duplicates.
- **the journal** (`file:.dreamwork/user-events.sqlite3?mode=ro`): head_ordinal
  **25**, coordinator cursor **absent** (never created), so **25 unconsumed**
  receipts, all in `received` state. 0.97 ms.
- **the full suite, timed end-to-end:** **8.19 ms** for all five counts plus the
  two incomplete-data counts plus the journal unconsumed count — 16% of the
  50 ms budget.
- **`dev/ledger.py:main`** (`dev/ledger.py:523`): the dispatch seam — every verb
  returns through one tail, so one call site covers all five verbs.
- **`delivery-modes.md` / `attention-modes.md`**: the house style this doc
  follows (measured facts first, the contract, what it does NOT authorise, open
  calls only where a fork is genuinely his, verification section, primary
  sources).
- **`#366` / `lint.check_unfolded_answers` docstring**: the interim half this
  design supersedes, and the verbatim quote ("*only #357's interim half … he
  wants the count tacked onto every invocation, which is ambient rather than
  opt-in*") that defines this task's shape.
