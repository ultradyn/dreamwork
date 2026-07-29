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
squelch), not by remembering what it said last time.

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

## Open calls for him — one

His standing rule: if every call has one clearly-superior answer, there are no
open questions. Four of the five questions the brief posed have one clearly-
superior answer, so they are not open calls — they are settled here:

- **Q1 (footer contents)** — settled: his five counts + incomplete-data, nothing
  else. Superior answer, no fork.
- **Q2 (where it lives)** — settled: one function in `dev/ledger.py`, called by
  every verb at exit, on stderr. Superior answer, no fork.
- **Q3 (WARN never ERROR)** — settled: never changes an exit code, never blocks.
  Superior answer, no fork.
- **Q4 (quiet rules)** — settled: zeros absent, whole footer absent on all-zero,
  incomplete-data squelchable, five-counts never squelched. Superior answer, no
  fork.

One genuine fork remains, and it is his to rule:

> **Q5 — footer on EVERY verb, or only on verbs that change state?**
>
> His word was "tacked on," which reads as "every verb." But the footer's value
> is highest on the verbs that CHANGE state (`fold`, `file`, `note`) — because
> those are the ones that can CREATE the unfolded-answer situation the footer
> exists to catch (a `fold` that should have been a note, a `file` that splits
> an ask). The read verbs (`counts`, `sweep`) are the ones a human runs to
> LOOK, and tacking the footer onto them means every `counts` invocation prints
> a second line of warnings below the counts — which is either helpful (he sees
> the queue AND the warnings in one glance) or noisy (the counts ARE the queue;
> the warnings repeat the open-task count he just asked for).
>
> **This is genuinely his**, because both readings are defensible and the
> trade-off is about his reading habits, which are not measurable from the code.
>
> - **rec: every verb.** It is the literal reading of "tacked on," it is the
>   shape that can never miss a state-change verb, and the noise on `counts` is
>   bounded by rule 1 (zeros absent) — on a clean tree `counts` prints just its
>   counts and nothing else. The cost of "every verb" over "state-change only"
>   is one suppressed-absent line on the read verbs, which is the cheapest
>   possible cost.
> - **the alternative: state-change verbs only** (`fold`/`file`/`note`). Quieter
>   on the read verbs, at the cost of the footer not appearing on the one verb
>   (`counts`) he runs most often to check state — which is the verb whose whole
>   job is "tell me what is waiting."

The journal unconsumed-receipt count (fact 1's extra) is folded under Q5 rather
than its own call: if the footer is on every verb, it carries the unconsumed
count (it is cheap and it is the durable "something is waiting"); if it is on
state-change verbs only, the unconsumed count is less relevant (a `fold` does
not change what is unconsumed in the journal) and can be omitted.

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
