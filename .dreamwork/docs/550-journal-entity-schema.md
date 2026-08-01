# #550 — the task_event journal's entity-schema decision: narrow, extend, or sidecar?

Findings and recommendation. **Design only — no production code, no tests.**
Every claim cites a file:line or a committed design document verified at HEAD
`b611361b`. Filed from the #460 merge gate: the round-trip falsifier
(`test_replay_events.py`) proved the `task_event` **chain** round-trips
completely (all 11 columns including recomputed `prev_hash`/`hash`) but the
task **entity** does not — 7 columns (`title`, `body`, `priority`, `origin`,
`type`, `blocked_on`, `body_digest`) are lost. The `.jsonl` contract
(`file-formats.md` § "The `task_event` journal `.jsonl`", `4161f0e1`)
documents this as *transitions-not-entities* and names this task as the owed
extend-or-narrow decision.

---

## Verdict (read this first)

**Narrow.** The journal is a lifecycle/transition log by design — that is not
a gap to close but a boundary the design drew on purpose, and the repo's own
documents settle what the journal is *for*. Extend and sidecar each recreate
the "second derived truth" the entire #264/#294 architecture exists to remove,
and extend cannot even deliver the full round-trip it promises (entity
mutations are not transitions). The `.jsonl` contract is **already honest**;
only the replay tool's own docstrings and CLI help overclaim, and narrowing
those is a small, migration-free follow-up.

**The decision does NOT need the human.** His #264 Q2 ruling `(c)` — *"a
machine-local gitignored `.jsonl` log for recovery and reprocessing"* — and
#264's design table (entity and transitions are *two separate AUTHORITATIVE
facts*, neither derived from the other) settle the journal's purpose
unambiguously. The choice does not turn on an unanswered question; it turns on
documents he already ruled on. No `questions.md` entry is drafted (§Human).

---

## 0. What the journal IS FOR (the documents settle it)

The brief asks whether the choice turns on "what replay is *for* (backup/
restore vs lifecycle audit)" and whether that purpose is derivable from the
repo's own documents. It is derivable, and the documents agree:

- **#264, his Q2 answer `(c)`** (`task-transition-boundary.md` §"What stays
  open" + the ledger plan's recap): *"a machine-local gitignored `.jsonl` log
  for **recovery and reprocessing**, and cross-clone history is a later
  deployment choice, not a v1 requirement."* Recovery and reprocessing **of
  the chain** — the canonical byte form was defined on day one specifically so
  *that* is a deployment choice rather than a schema change. He did not say
  "full entity backup."
- **#264's design table** (`task-transition-boundary.md` §"The shape"): both
  `task_event` and the entity tables (`task`, `entry`, `related`, `depends`)
  are marked **AUTHORITATIVE**. They are **two independent authoritative
  facts** — the entity is NOT derived from the transition log, and the
  transition log does not claim to reproduce the entity. #264's governing
  rule is *"a materialised row exists only where a writer must compare-and-swap
  against it; everything a reader wants is a query"* — the entity is a fact,
  not a projection of the events.
- **#264's boundary** (`ledger-sqlite.md` §"Write verbs", `task-transition-
  boundary.md` §"Why a task changes with no user event"): *"one event per task
  **transition**."* `note_task` is explicit precedent — a body edit is **not a
  transition** and writes **no** `task_event` row (`ledger_write.py:38`),
  `file-formats.md:2218`). So even an "extend" that snapshotted entities at
  first sight would miss every subsequent body edit, priority change, and
  note — the entity mutates *without* the journal ever seeing it.
- **The `.jsonl` contract** (`file-formats.md:2281`): *"The log narrates
  transitions, not entities."* It lists the 7 non-captured columns by name and
  calls the divergence *"the measured #294 finding at #460's gate."* The
  contract is **already honest**; it is not waiting to be corrected.
- **#294's architecture** (`ledger-sqlite.md` §"What the dependencies
  settled", M2-C refutation): the store is the **single source of truth**;
  the dual-write "shadow run" is refuted because it *"is the second derived
  truth #264 exists to remove."* An entity copy in the journal is that truth
  by another name.

So: the journal is for **chain integrity and lifecycle replay** (recovery and
reprocessing), not for **entity backup/restore**. That distinction is the
design's own, not an interpretation layered on after the fact.

---

## 1. The #294 finding, precisely

`test_replay_events.py:204-244` proves the asymmetry, with the preconditions
asserted at runtime so the finding is not vacuous:

- **The chain round-trips exactly.** A real-path store (`ledger_write` file +
  land), exported to `.jsonl` and replayed into a fresh store, holds
  IDENTICAL `task_event` rows — every column, including the recomputed
  `prev_hash`/`hash` (`test_round_trip_task_event_chain_is_identical`).
- **The entity does NOT round-trip.** `id` and `state` do (the journal
  captures the lifecycle); `title`, `body`, `priority`, `origin`, `type`,
  `blocked_on`, `body_digest` do not. `replay_into` stubs them
  (`dev/replay_events.py:88-93`: `_REPLAY_TITLE` / `_REPLAY_BODY`), and the
  test asserts the real titles differ from the stubs so the divergence is
  real, not NULL-vacuous.

This is a **finding about the journal, not a bug in the tool** — the tool's
own docstring says so (`dev/replay_events.py:18`). The tool that overclaims is
the *module docstring* (`dev/replay_events.py:1`: *"replay the task_event
journal, reconstruct the store"*) and the `replay` subparser help
(`dev/replay_events.py:312`: *"reconstruct a store from a .jsonl journal"*),
both of which read as fuller reconstruction than the journal provides.

---

## 2. The four criteria each option is judged against

| criterion | what it demands |
|---|---|
| **merge rule** | ONE deterministic total order `(at, task_id, arrival-rank, from_state, to_state, actor, detail)`, arg-order + shuffle invariant, no dedup (`dev/replay_events.py:242-278`). An added record kind must sort somewhere without breaking the totality. |
| **replay determinism** | byte-identical store from an empty image for an identical event sequence (`test_replay_is_byte_identical_across_two_runs`). |
| **`receipt_id` stored-not-hashed** | `receipt_id` rides the row but is excluded from `canonical_event_bytes` (`ledger_store.py:122-127`). The precedent: a *reference* (pointer to the authoritative receipt) can be unhashed; *content* cannot, or the chain stops protecting it. |
| **#549's pin** | `test_chain_golden.py` pins `canonical_event_bytes` byte-for-byte against an independent framing. Any change to the hashed field set is a deliberate format migration with a `file-formats.md` edit in the same commit (`test_chain_golden.py:26-32`). |

---

## 3. NARROW (recommended)

**The journal is a lifecycle log by design.** The tool's docstrings and CLI
help are narrowed to say so honestly; the `.jsonl` contract is already correct
and needs no change.

- **Merge rule:** untouched. The log carries only transition events; no new
  record kind enters the total order.
- **Replay determinism:** untouched. Determinism is a property of the chain,
  which is already complete; the entity stubs are deterministic by
  construction (`_REPLAY_TITLE` / `_REPLAY_BODY` are constants).
- **`receipt_id` stance:** untouched. The log stays references-only.
- **#549's pin:** untouched. The canonical byte form is unchanged; no hashed
  field is added or removed.
- **Cost:** one small follow-up lane narrows `dev/replay_events.py`'s module
  docstring and the `replay`/`export` subparser help from "reconstruct the
  store" to "reconstruct the transition chain (the lifecycle); entity columns
  are stubbed — see #294/#550." No migration, no schema change, no golden-
  vector edit. `file-formats.md` needs **no** edit (it is already honest at
  `:2281`).

**Why it is correct, not merely cheap:** the entity is an AUTHORITATIVE table
(#264's design table), not a projection of the events. A journal that
reproduced the entity would hold a *second* copy of an authoritative fact —
exactly the dual-write hazard #264/#294 refuse. The journal's job is chain
integrity and lifecycle replay; the entity's job is being the entity. Narrow
honours both boundaries.

---

## 4. EXTEND (entity-snapshot records) — not recommended

**Add entity data to the journal — e.g. an entity-snapshot record at first
sight (and/or on entity mutation) — so replay reconstructs the full row.**

This is a **format migration**, and it fails on the design boundary even
before it fails on the format. Two sub-shapes, both refuted:

### 4a. Snapshot hashed into the chain (entity fields in `canonical_event_bytes`)

- **#549:** BREAKS. The golden vector pins the 7-part canonical form
  byte-for-byte (`test_chain_golden.py:67-135`). Adding entity fields to the
  hash is a deliberate migration: the `test_chain_golden.py` head comment
  (`:26-32`) and `file-formats.md` both require a contract edit in the same
  commit. Every existing journal's chain would need re-derivation — old
  `.jsonl` files replay to a *different* chain than they were exported from.
  This is the heaviest possible change for the lightest possible benefit.

### 4b. Additive record kind, entity fields stored but NOT hashed (like `receipt_id`)

This is the backward-compatible sub-shape the brief asks analysed precisely.
**Verdict: chain-compatible, but broken on the design boundary and the
tamper-integrity it gives up.**

- **Chain compatibility (the factual question):** YES at the chain level.
  `canonical_event_bytes` (`ledger_store.py:122-127`) reads exactly 7 keys;
  `append_chained_event` (`ledger_store.py:184-199`) builds its hash from the
  explicit transition kwargs. Entity fields added to `EVENT_FIELDS`
  (`dev/replay_events.py:84-86`) and carried through `_normalise`
  (`dev/replay_events.py:104-123`) would be read, written, and replayed
  **without entering the hash**. An old journal without the fields replays to
  the same chain it always did (the fields are absent → default). So an
  additive, non-hashed record **does** keep old journals replayable. This was
  checked by reading the production paths, not by prototyping: `canonical_
  event_bytes` never touches a key outside its 7, and `append_chained_event`
  builds its event dict from the 7 transition kwargs, so a 9th field on the
  `.jsonl` line is invisible to both.
- **Why it is still wrong — three reasons, each decisive on its own:**

  1. **The entity fields are CONTENT, not a reference — the `receipt_id`
     precedent does not extend to them.** `receipt_id` is stored-not-hashed
     because it is a *pointer* to the authoritative receipt (which lives in
     the same SQLite file, chain-protected on its own chain). `title` and
     `body` are the *content itself*. Storing content unhashed while the
     authoritative copy lives in a gitignored, machine-local store is a
     tamperable second copy: the chain cannot detect a forged title, because
     the title was never hashed. The #549 pin exists precisely because chain
     integrity over the canonical fields matters; excluding the entity's
     defining fields from that protection makes the snapshot a decorative
     copy, not an honest one.

  2. **Two representations of one authoritative fact = the dual-write hazard.**
     #264 marks the entity table AUTHORITATIVE. A snapshot in the journal is a
     *second* authoritative claim about the same entity. If the snapshot is
     authoritative, there are two truths (the table and the journal) that can
     disagree — the exact failure #264's design table and #294's M2-C
     refutation exist to prevent. If the snapshot is *derived* (non-
     authoritative, best-effort), it can drift the moment `note_task` or a
     body edit lands without a journal event — and it will, because body
     edits are not transitions.

  3. **Full round-trip is UNACHIEVABLE without breaking #264's boundary.**
     An entity mutates without writing a `task_event` row: `note_task`
     appends to `body` and writes no event (`ledger_write.py:38`,
     `file-formats.md:2218`); a priority change, an origin reclassification, a
     `blocked_on` edit are all entity mutations that are not transitions. A
     snapshot at first sight reconstructs the *original* entity, not the
     *current* one. To reconstruct the current entity, the journal would have
     to start recording non-transitions — which dissolves the #264 boundary
     ("one event per task **transition**") the whole log is built on. So
     extend sells a promise (full entity round-trip) it cannot keep without
     destroying the boundary that gives the journal its meaning.

- **Merge rule:** an entity-snapshot "cause" would need a place in the total
  order. At first sight it shares `(at, task_id)` with the `filed` event, so
  it sorts adjacent — workable. But a snapshot on *mutation* has no natural
  rank among transitions (a note at 11:00 and a landed event at 11:00 collide
  on the coarse key), and the tie-break (`detail`) is itself entity content,
  so the order becomes a function of the very data the design says is not a
  transition. The merge rule works cleanly for transitions; it does not for
  entity states.
- **Cost:** a format migration (4a) or a schema-of-the-export widening plus
  replay logic to merge snapshots (4b), a golden-vector edit, a
  `file-formats.md` rewrite, and new tests — all to deliver a snapshot that is
  either tamperable, drift-prone, or stale.

---

## 5. SIDECAR / HYBRID — not recommended (deferred, not refused)

**Transitions stay canonical; an optional entity export rides beside the
journal (second file or a trailer section); replay merges it when present.**

- **Chain integrity:** preserved — the sidecar is outside the chain, so #549
  is untouched and the canonical byte form stays pure. This is sidecar's one
  real advantage over extend.
- **But it is the explicitly-deferred "cross-clone" question, not a new idea.**
  #264's open *"Git portability"* lists exactly three candidates: commit the
  DB, commit a deterministic text export of `task_event`, or accept machine-
  local for v1. His Q2 `(c)` chose machine-local for v1 and called cross-clone
  *"a later deployment choice."* A sidecar entity export IS that deferred
  cross-clone mechanism (a committed, mergeable projection of the entity for a
  fresh clone). It is #294's scope, not #550's, and he already ruled it
  *"later, not v1."*
- **The dual-write hazard returns the moment the sidecar is authoritative.**
  If the sidecar is the entity's portable copy and the store is its live copy,
  two truths exist and they drift on every `note_task` (the sidecar must be
  regenerated, and a regeneration that lags is a stale second truth — the
  #362 drift lesson). If the sidecar is best-effort, it is a cache, and a
  cache that a clone trusts for entity state is the silent-stale failure
  #264's "queries not tables" rule removes.
- **`receipt_id` stance:** sidecar is out of scope for the receipt question,
  but the same logic applies: an entity sidecar is content, not a reference.
- **Cost:** a second file format, an export verb, a merge path in replay, a
  `file-formats.md` section, and a regeneration trigger — all for the deferred
  cross-clone case. Narrowing costs none of this and forecloses none of it:
  if he later rules cross-clone in, the sidecar is still available as the
  committed projection #264 anticipated.

---

## 6. Recommendation: NARROW

**Narrow the journal to what it is — a lifecycle/transition log — and fix the
tool's overclaim.** Extend and sidecar each re-create the second-derived-truth
hazard the #264/#294 architecture was built to eliminate: extend by putting a
copy of an AUTHORITATIVE entity into the transition log (tamperable if
unhashed, a migration if hashed, and stale regardless because entity
mutations are not transitions); sidecar by introducing a portable second copy
that drifts on every body edit. Narrow costs one small docstring/help edit,
touches neither the chain nor the contract (both already honest), and leaves
the cross-clone question exactly where his Q2 `(c)` left it — open, deferred,
and unconstrained by anything this lane decides.

The one-paragraph justification: the entity table and the transition log are
two independent AUTHORITATIVE facts by #264's own design table — neither
derived from the other — so a journal that carried entity data would hold a
second representation of an authoritative fact, which is the dual-write hazard
the entire architecture refuses; and because entity mutations (`note_task`,
priority changes, body edits) are explicitly NOT transitions and write no
`task_event` row, no extension can achieve full entity round-trip without
dissolving the boundary that gives the journal its meaning. The contract is
already honest (`file-formats.md:2281`: *"the log narrates transitions, not
entities"*); the only dishonesty is the replay tool's docstring and CLI help,
which is a small, migration-free fix.

---

## 7. Does the decision need the human?

**No.** The choice turns on what the journal is *for*, and the repo's
documents answer that — in his own words, already ruled:

- **His #264 Q2 `(c)`** (`task-transition-boundary.md` §"What stays open";
  `ledger-sqlite.md` §"What the dependencies actually settled"): the journal
  is *"for recovery and reprocessing,"* machine-local for v1, cross-clone
  deferred. That is lifecycle/chain recovery, not entity backup.
- **#264's design table**: entity and transitions are both AUTHORITATIVE —
  two facts, not one derived from the other. The journal reproducing the
  entity would be a second truth about a fact that already has a home.
- **#264's boundary** (`file-formats.md:2218`, `ledger_write.py:38`): a body
  edit is not a transition. So "extend for full round-trip" is not a choice
  the human can make real by ruling yes — it is structurally unavailable
  without breaking the boundary.
- **`file-formats.md:2281`**: the contract already states the divergence as
  the measured finding, not a defect to repair.

The ambiguity was never in the design; it was in the replay tool's docstring
(*"reconstruct the store"*), which reads as fuller reconstruction than the
journal provides. Narrowing resolves the ambiguity by aligning the tool's
claim with the contract the tool rides. No `questions.md` entry is drafted.

**What IS open, and is NOT this lane's to close:** the cross-clone entity-
portability question (#264's *"Git portability"*, his Q2 `(c)` *"later"*). If
he later rules that a fresh clone must reconstruct entity state from a
committed export, the sidecar (§5) is the mechanism #264 anticipated — but it
is a deployment choice under #294's scope, and the narrow recommendation does
not foreclose it. This lane leaves that door exactly where he left it.

---

## 8. FLAG — contract-diff text

**None required for file-formats.md.** The `.jsonl` contract
(`file-formats.md:2259-2296`) is already honest: it states the log *"narrates
transitions, not entities,"* names the 7 non-captured columns, and calls the
divergence *"the measured #294 finding."* A narrow recommendation changes
nothing in the contract.

The narrowing belongs to the **tool** (`dev/replay_events.py`), which is the
follow-up implementation lane's file, not the coordinator-owned contract. For
completeness, the proposed tool-side wording (NOT a `file-formats.md` edit):

- Module docstring (`dev/replay_events.py:1`): *"replay the task_event
  journal, reconstruct the **transition chain** (lifecycle). The task **entity**
  (title/body/priority/origin/type/blocked_on/body_digest) is NOT in the
  journal and is stubbed on replay — see #294/#550. The store's task table is
  the authoritative home for the entity, not this log."*
- `replay` subparser help (`dev/replay_events.py:312`): *"reconstruct the
  transition chain from a .jsonl journal (entity columns stubbed — #294)"*

No `file-formats.md` edit, no golden-vector edit, no schema change, no
migration trailer.

---

## 9. Implementation-brief sketch (NARROW)

A follow-up lane can be briefed from this alone. **One file, one commit, no
migration.**

**Owned file:** `dev/replay_events.py` (docstrings + argparse help only).
**Does NOT own:** `file-formats.md`, `ledger_store.py`, `test_*`, `lint.py`.

**The change:**
1. Narrow the module docstring (`:1`) from *"reconstruct the store"* to
   *"reconstruct the transition chain (lifecycle); entity columns are stubbed
   (#294/#550)"*, keeping the determinism/round-trip/merge prose (those claims
   are about the chain, which is true).
2. Narrow the `replay` subparser help (`:312`) and the `export` subparser
   help (`:316`) to name what round-trips (the chain) and what does not (the
   entity), one line each.
3. Optionally, make the two `_REPLAY_*` stub constants' provenance comment
   (`:88-93`) cite #550 alongside #294, so the stub's reason is current.

**Red-first check (the one this lane would owe):** the existing
`test_round_trip_task_state_matches_but_title_does_not_294_finding`
(`test_replay_events.py:204`) already asserts the entity does NOT round-trip.
The follow-up lane's check is **not a new test** — it is the assertion that
the docstring/help narrowing does not change behaviour: a targeted pytest of
the existing replay suite passes unchanged, and the stubs still read as
stubs. State that no test was touched and why (docstring-only change; the
existing falsifier still holds the property).

**What this sketch deliberately does NOT include:** any entity data in the
journal, any sidecar format, any `file-formats.md` edit, any golden-vector
edit. Those are the extend/sidecar options this doc refutes (§4, §5).

---

## 10. Deviations from the brief

None. The brief was followed exactly: design-only, no production code, no
tests; `file-formats.md` untouched (any proposed contract-diff is a FLAG,
§8 — and there is none); the human-needed verdict is answered explicitly with
citations (§7); the additive-record backward-compatibility question is
analysed precisely (§4b) from the production paths rather than prototyped (the
factual answer — chain-compatible — is derivable from `canonical_event_bytes`
and `append_chained_event` never touching a key outside their 7, so a scratch
prototype would have confirmed what the code already states).

---

## SUMMARY

- **Recommendation: NARROW.** The journal is a lifecycle/transition log by
  design; the entity is a separate AUTHORITATIVE table (#264). Extend and
  sidecar both re-create the "second derived truth" the architecture refuses,
  and extend cannot deliver full round-trip because entity mutations are not
  transitions.
- **The decision does NOT need the human.** His #264 Q2 `(c)` ("recovery and
  reprocessing") and #264's design table (two AUTHORITATIVE facts) settle the
  journal's purpose; the contract is already honest. No `questions.md` entry.
- **No FLAG for file-formats.md** — it already states the divergence. The
  narrowing is to the tool's docstrings/CLI help, a migration-free one-file
  follow-up.
- **Extend (4b) is chain-compatible but broken on design + integrity:** entity
  fields stored-not-hashed are tamperable content (not a `receipt_id`-style
  reference), and body edits write no event, so any snapshot goes stale.
- **Sidecar is the deferred cross-clone question** (#264's "Git portability",
  his Q2 `(c)` "later"), not a v1 decision — and narrow forecloses none of it.
