# Delivery modes — instant push vs batched queue (#342)

Design only. **Build no mechanism.** No `watch.py` change, no `user_events/`
change, no `file-formats.md` or `lint.py` edit, no migration. This doc is the
deliverable; he rules on the open calls, then the loop builds.

## Authority and what this builds on

His ask (#342): a mode toggle for delivery method — **instant push** (the agent
is woken the moment he sends something) vs **batched/queued delivery** (the agent
gets all pending updates at once, on its next tick). Batched is more efficient but
less responsive, so it suits orchestration-heavy phases. **His stated defaults:**
`add idea` / `add task` do **not** interrupt; `do now` **does** interrupt; answers
and notes on questions/reviews are *"the genuinely ambiguous class the toggle is
for."* The stated purpose, in his words: *"this should also help with the agent
being overwhelmed or forgetting to process some things."*

Both blockers cleared today:
- **#294 (store + CLI seam)** executed — `ledger_store.py` / `ledger_write.py` /
  `ud-dw-tasks-migrate` are the cutover; `tasks.md` is a shim, never a source.
- **#263 (user-event journal)** landed — `user_events/` (SQLite, WAL +
  `synchronous=FULL`, hash-chained events, a per-consumer read cursor) is the
  durable receipt store, and the **E3 cutover is in `watch.py`**: every write
  route commits a receipt *before* dispatch (`do_POST` → `_journal_receive` at
  `watch.py:13559`, `Handler._journal_receive` at `watch.py:13170`).

This task **consumes #263's cursor and adds the per-kind interrupt policy +
toggle on top.** Filing a second cursor would be the two-durable-truths failure
#263 exists to prevent; this design does not propose one.

## Two load-bearing facts, measured

**1 · `kind` reaches the wake channel as nothing but a string prefix — so no
consumer can tell urgency today.** `_handle_command` (`watch.py:13680`) builds
the wake line with `command_line(kind, text, source)` (`watch.py:13100`), which
formats `f"command via watch{from_hint(source)}: {kind}{body}"`. An `add-idea`
and a `do-now` are identical to the tail monitor: both append one line to
`watch-events.log`, both wake the coordinator exactly as hard. The journal
receipt carries the route (`/command`) and the exact body, but **`kind` is inside
the body, not a first-class field** — so the journal cannot route on urgency
either, today. Urgency is recoverable only by string-matching `kind` out of the
body. That is the seam delivery-modes routes through (§"What changes in
watch.py").

**2 · The command channel was push-only and not durable — but #263 made it
durable, and that is the half this toggle rides.** `SKILL.md:117-124` records the
pre-journal failure mode verbatim: *"a command he types into the dashboard
composer exists only as a line in that file… so if the tail monitor is not armed
(a resumed session, a compacted one, a `watch.py` started after init), his
`do now:` is lost with no error anywhere."* `watch-events.log` is best-effort
append (`log_event`, `watch.py:12874`) with `except OSError: pass`; an mtime change
says the file moved but tells no reader which lines are new, and **session memory
of the offset is exactly what compaction destroys.** #263 fixes the durable half:
every write route now commits a receipt with an ordinal in a hash-chained event
log, and a cursor records how far a consumer has read. **The cursor is the
delivery mechanism for batched mode; the wake line is the delivery mechanism for
instant mode.** The toggle chooses which one an item rides.

## Per-kind interrupt policy

The table is the contract. Each dashboard command kind maps to a default delivery
mode. **HIS** marks a default he stated; **PROPOSAL** marks one this design
offers for him to rule on or amend. The four built-in kinds are from `COMMANDS`
(`watch.py:307`): `add-idea`, `do-next`, `do-now`, `maintenance` (plus
dynamically-resolved plugin kinds).

| dashboard input | route / kind | default | source | rationale |
|---|---|---|---|---|
| `do now: …` | `/command` `do-now` | **instant** | **HIS** | he stated it interrupts; it is the explicit preemption |
| `do next: …` | `/command` `do-next` | **instant** | **PROPOSAL** | a queue-jump steer (`SKILL.md:622`) is the same gesture as `do-now`, just one rung less urgent; it names the *next* task, so acting on it promptly costs nothing. He did not name it — open if he disagrees |
| `add idea: …` / `add task: …` | `/command` `add-idea` | **batched** | **HIS** | he stated it does not interrupt; it parks a thought the loop picks up when it chooses next |
| `maintenance` | `/command` `maintenance` | **batched** | **PROPOSAL** | housekeeping is never a preemption; batching it onto the next tick is exactly its shape |
| plugin commands | `/command` `<plugin>` | **batched** | **PROPOSAL** | default to the least disruptive; a plugin that needs to interrupt opts in per-kind (see open Q3) |
| his answer to a question (`/answer`) | `/answer` | **instant** | **HIS (the class)** | *"answers… are the genuinely ambiguous class the toggle is for"* — see open Q1; the default this design *proposes* is instant, because an answer unblocks in-flight work, but he rules |
| his note on a question/review (`/comment`) | `/comment` | **batched** | **HIS (the class)** | same ambiguous class; a follow-up note amends rather than preempts, so batching is the less-disruptive default. He rules |
| his new question for the dreamer (`/ask`) | `/ask` | **batched** | **PROPOSAL** | his own question is not an interrupt *of him*; the dreamer folds it on the next tick. He rules if he wants it hotter |

Two rules run through the whole table and are stated once here:

- **Instant is always a *subset* of the loop's own reading.** An item delivered
  instantly still lands in the journal (the receipt commits in `do_POST` before
  dispatch, for every write route). Instant mode only adds the wake line on top;
  it never *replaces* the durable receipt. So nothing delivered instantly is
  invisible to the cursor, and nothing batched is lost if the monitor is off.
- **The toggle sets the mode; the table sets the per-kind default *under* the
  mode.** In instant mode, batched kinds are *still batched* (an `add-idea` does
  not interrupt even in instant mode). In batched mode, instant kinds are
  *demoted to batched* (a `do-now` rides the queue rather than pre-empting) —
  **or** the table's instant kinds stay instant regardless of mode. Which of
  those two readings "batched mode" means is open Q2; this design proposes the
  latter (the most-urgent kinds pre-empt even in batched mode), because
  *"forgot to process some things"* is the failure batched mode must never
  *cause*, and a `do-now` that does not pre-empt is a `do-now` that lied.
