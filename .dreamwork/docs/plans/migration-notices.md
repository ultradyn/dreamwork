# Migration notices — a hot-path signal for stale agents (#458)

## The gap

Migrations apply **at initialization only** (`migrations/README.md`: orient
compares `.dreamwork/skill-version` to the latest entry). A long-running loop
that never re-initializes never sees a migration: its skill files are cold
(read once, hours ago); its **data files are hot** (read every tick). So the
data file is the only channel guaranteed to reach a stale agent.

His framing (2026-07-29 01:40): *"at the top of tasks.md we can have a comment
message that says, this is an archived copy … the migrate thing can put in
messages that mean that any agent that was still running the old protocol would
find those messages and then be able to update itself."*

The motivating case is **#294** (ledger → SQLite). The moment `tasks.md` stops
being authoritative, an old-protocol agent keeps writing to it and its work is
silently lost. This mechanism must land **before** that migration.

## Trust boundary

An instruction in a data file that an agent then follows is the shape of a
prompt injection. It is safe **here** because:

1. **Only a migration writes these** — the writer is our own repo's migration
   machinery, not a peer, not the human's free text, not a foreign session.
2. **They carry a declared marker** (`<!--dreamwork-migration-notice`).
3. An agent treats them as a **protocol notice from its own repo**, never as
   authority from a peer (peer messages remain data, per the standing rule).

## IGC

**Context:** build the notice mechanism + format contract for any migration that
changes a hot file's meaning. Do not perform #294. Do not write a notice into
the live ledger. Do not edit `watch.py`.

### Goals

| | Goal |
|---|---|
| **G1** | A human reading the raw file sees the notice and understands it is a protocol upgrade signal |
| **G2** | `lint.py` does not read the notice as a ledger entry (testable: id set identical with/without) |
| **G3** | `watch.parse_ledger` does not count the notice as a task (testable: same) |
| **G4** | The notice does not have to be rewritten when the migration's instructions change |
| **G5** | Retirement is a rule an agent can evaluate, not a step a human must remember |
| **G6** | The Nth migration does not leave N banners (shrink rule) |

### Q1 — Where the notice lives

| Idea | All | G1 | G2 | G3 | G5 | G6 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| **A. HTML comment block at byte 0** (`<!--dreamwork-migration-notice`, review-source family) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B. YAML front-matter on `tasks.md` | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ |
| C. Freeform first-line marker, no declared form | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ |
| D. Fake task entry under `## Open` | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ |
| E. Separate `notices.md` file | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |

Decisive errors:

- **B** — a second machine-readable header shape on a file that already has free
  prose header + `Next id:`. Competes with human header prose; not the "comment
  message" he named.
- **C** — without a declared marker, retirement is guesswork and freeform lines
  accrete (fails G5 and G6).
- **D** — `LEDGER_ENTRY` / `LEDGER_ID` match `^- \*\*#N` by construction; fails
  G2 and G3 immediately.
- **E** — the stale agent re-reads the *hot data file* (e.g. `tasks.md`), not a
  side channel. A separate file is invisible to the loop that never looks there
  (fails G1 for the motivating case).

**Survivor: A.** Same family as `<!--dreamwork-review-source`. Agents and
humans reading the raw file both see it; entry parsers ignore it because it is
not a `^- **#N**` line.

### Q2 — Distinguished from content

Binary and testable:

- `lint.LEDGER_ID.findall` over a file with a notice equals the same call over
  the file without it (both derived from the parser — no hand-written expected
  list).
- `watch.parse_ledger` open-id sets match the same way.

The format is **key: value only** inside the comment (no freeform body). Field
values that look like a ledger entry head (`- **#N…`) are **rejected at the
writer**, because `LEDGER_ID` is `re.M` over the whole file and a smuggled
head line would invent a phantom id.

### Q3 — Pointer vs instructions

| Idea | All | G4 | G1 |
|------|:---:|:--:|:--:|
| Full instructions inline | ✘ | ✘ | ✔ |
| **Pointer to the migration entry** (`migration:` required; optional `summary:`) | ✔ | ✔ | ✔ |

Decisive error for inline instructions: G4 — when the migration's "How to
apply" changes, every live notice would need a rewrite. A pointer keeps the
file small and survives instruction changes; the agent (or human) opens
`migrations/<name>` for the current text.

### Q4 — Retirement, and the shrink rule

| Idea | All | G5 | G6 |
|------|:---:|:--:|:--:|
| Human removes it by memory | ✘ | ✘ | ✘ |
| Auto-expire after N days | ✘ | ✔ | ? |
| **Retire when `skill-version` ≥ notice's `migration` (lexicographic)** | ✔ | ✔ | ✔ |
| **Single-slot write: insert replaces any existing notice** | ✔ | ✔ | ✔ |

Decisive errors:

- Human memory fails G5 by construction (and is how notices become permanent
  confusion).
- Time-based expiry can remove a notice while the migration is still unapplied
  (slow upgrade) or leave it after apply (fast upgrade) — not tied to the fact
  that makes it spent.

**Surviving pair:**

1. **Write is single-slot.** `insert_notice` strips any existing well-formed
   notice, then prepends the new one. The Nth migration leaves **one** banner.
2. **Retire when spent.** `skill-version` is a migration filename; versions
   order by plain lexicographic sort (`migrations/README.md`). A notice is
   spent when `skill-version >= migration`. Orient (or any agent that has
   applied the migration) runs `migration_notice.py retire`. A still-running
   agent that self-updates after reading the notice can retire it the same way.

## Mechanism

| Piece | Role |
|---|---|
| `migration_notice.py` | Writer, parser, retire, CLI |
| `file-formats.md` | Contract for the block shape |
| `migrations/README.md` | When a migration should leave a notice |
| `test_migration_notice.py` | Indifference (lint + parse_ledger), shrink, retire, red-proved lines |

```text
python3 migration_notice.py write  --path .dreamwork/tasks.md \
    --migration 2026-07-29-01-task-store.md \
    --summary "archived copy; live store is SQLite — read the migration"
python3 migration_notice.py retire --path .dreamwork/tasks.md \
    --skill-version-file .dreamwork/skill-version
```

**Not done here (and must not be):** writing a notice into the live
`.dreamwork/tasks.md`, performing #294, or editing `watch.py`. Indifference of
`watch.parse_ledger` is proved by calling the existing function; no watch.py
change was required.

## Trailer choice

**`Feature:`** — additive machinery in the skill tree. Existing targets gain
nothing until a later migration *uses* `write`. No target-side state shape
changes on pull, so this is not itself a `Migration:`.
