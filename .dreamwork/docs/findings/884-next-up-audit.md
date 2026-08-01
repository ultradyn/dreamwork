# #884 — is the next-up mark stored anywhere? (audit, then the fork)

`SKILL.md` step 0 makes one promise above all the others: *"take any task
marked next-up … an explicit human steer outranks the agent's own ideas."*
`#874` reported second-hand that nothing stores it. This is the first-hand
check, against the **schema and the live rows**, not against the module
`SKILL.md` was written from.

## The denominator, asserted before any zero was believed

Every "0" below was read in the same session as these non-zero counts, from
the live store opened `?mode=ro`:

| population | count |
|---|---|
| `task` rows | **774** |
| `task_event` rows | **1372** |
| distinct causes actually emitted | **6** of 23 seeded |
| `related` / `depends` rows | 151 / 23 |
| non-null `task_event.detail` | 978 |
| TEXT cells scanned for a marker | **15 422** across all 22 tables; positive control `'ledger'` matched **310** |

So the store is populated and the scan reaches it. A zero here is a fact
about the feature, not about the query. (The `#667` refusal — a lane's own
`.dreamwork/` has no store — was left in place and read through `--ledger`,
never routed around.)

## Verification table — every candidate, including the ones it is not

| candidate | is it the mechanism? | evidence |
|---|---|---|
| **A `next_up` column** | **No** | `PRAGMA table_info(task)` = `id, state, title, body, priority, priority_uncertain, type, origin, blocked_on, body_digest, source_line`. No such column in **any** of the 22 tables. |
| **Priority / `P0`** | **No** | 5 P0 rows; **4 of them `origin='loop'`** — the loop assigns P0 to its own emergencies (`#370` truncation, `#713` red suite, `#814` lost receipts). Against 201 `origin='human'` tasks, 5 P0s cannot be carrying human steers. Decisive: `#269`'s body records the human doing **both acts separately** — *"ESCALATED to P0 **and** marked next-up by him, 2026-07-27 21:35"*. Two acts means two mechanisms. |
| **The journal (`do-next`, `PREEMPT_KINDS`, `EXPEDITE_KINDS`)** | **No — it is delivery, never ranking** | `watch.PREEMPT_KINDS = ("chat","do-now","do-next")` decides whether a wake line *interrupts*; `user_events/delivery.EXPEDITE_KINDS = ("do-next",)` decides whether the stop hook delivers it *at the next pause*. Both answer **when the agent hears it**, neither answers **what it picks next**. `dev/journal_consume.py` files no task and writes no `task_event` — it drains a cursor. And the drain is consume-once: `#519` is this loop losing a human steer to exactly that advance. |
| **`origin='human'`** | **No, and `SKILL.md` says so itself** | *"It is the one required field that the selection list below does not carry, because it is provenance rather than something triage reads."* |
| **Coordinator convention** | **Real, but prose only** | **22 task bodies carry a `**next-up**` marker**, 3 of them still open. No parser has ever read it: the repo-wide grep finds `next_up` in exactly one code file, and it is the seed list. `ledger_parse` never had a next-up grammar even in the markdown era. |
| **The cause seeds** | **Designed, installed, never wired** | `dreamwork_db/migrations/v001_legacy.py:15-16` seeds `next_up_set` / `next_up_cleared` into `task_cause`. Nothing else in the repo references either string. **0 of 1372 events** use them; the 6 causes that do appear are `migration_git` 643, `filed_from_command` 394, `landed` 317, `reprioritised` 7, `unblocked` 7, `reconciled` 4. |

## The failure, stated exactly

The mark was **never structural**. Pre-migration it was bolded prose in a
markdown line, and that was enough *because the agent read the same file
selection ran on* — the mark sat in the medium. Post-migration the agent
reads `dev/ledger.py list`, a **column projection**, and the prose stayed
behind in `task.body`. Nothing was deleted; the mark simply stopped being
in the thing selection looks at.

It is not hypothetical. `#254` is **open**, `origin: human`, and its body
says `**next-up**, queued behind the mistperf lane`. Here is the line
selection actually sees:

    #254  open  P1  human  — Render review notes and loop replies as threaded conversation

Indistinguishable from the other 27 open P1s, and sorted to position ~30 of
198 by id. The steer is in the store and cannot be acted on.

## The fork, argued

Goal **G**: a human steer outranks the agent's own ideas *and survives the
session that heard it*.

**Document what exists — refuted.** Nothing that exists satisfies G. The
journal is durable but consume-once and ranks nothing; P0 is a severity band
the loop assigns itself; `origin` is documented as unread by selection; the
convention is prose invisible to the projection. Writing that down would
document the defect rather than fix it, and `SKILL.md` would then promise
the loop a ranking mechanism it truthfully describes as absent.

**Build it — taken.** And the seeds decide the shape: the storage is
*already installed*. `next_up_set` / `next_up_cleared` are in `task_cause`
today, so the mark can be **derived state over the append-only event log**
— no column, and therefore **no migration**. That matters beyond elegance:
`#584` is landing a `user_setting` table in this same store, so a column
would race it up the migration ladder. An event is also strictly better for
this fact than a column would be: it records *who* steered and *when*, in a
hash-chained log, which is what a steer is.

**A landed task is never next-up.** The derivation is over `state='open'`
rows only. `SKILL.md` says the mark clears "on start", and there is no start
event to hang it on (`task_state` holds **0 rows** — ownership, leases and
holds are all unwired, and `hold_set`/`hold_cleared` are two more never-emitted
seeds). Scoping the derivation to open tasks makes a forgotten clear
self-heal at land instead of hoisting a finished task forever.

## Out of scope — named, not fixed

- **`task_state` is entirely unused** (0 rows) and with it 8 of 23 seeded
  causes: `claimed_by_agent`, `released`, `lease_expired`, `hold_set`,
  `hold_cleared`, `started_from_backlog`, `superseded`, `dropped`. The same
  designed-never-wired shape as this bug, one layer down.
- **`task.state` and `task_state_kind` disagree**: rows carry `open`/`landed`,
  the seed table says `pending`/`in_progress`/`landed`/`dropped`. Two
  vocabularies for one concept.
- **Backfilling the 3 open prose-marked tasks** (`#254`, `#269`) needs a write
  to the live store, which this lane is forbidden. The coordinator owns it.
