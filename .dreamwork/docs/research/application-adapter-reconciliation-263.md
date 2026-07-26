# #263 · ApplicationAdapter crash-window reconciliation (narrow sanity review)

**Date:** 2026-07-26
**Agent:** grok-sugar-vesi-x6tv
**Scope:** Only the seam
`journal claim → domain mutation lands → process dies before journal finish`.
No broader lifecycle/UI review. No source edits.

**Sources:** `#263` ledger text; coordinator D1/C1 revisions (journal-authoritative `202`, shadow `submissions.log`, `prove_applied`); main `questions.md` (v2 gates name prove-applied); no separate full #263 design HTML yet.

---

## Verdict

| Claim | Result |
|-------|--------|
| Journal commit alone authorises HTTP **202** | **PASS** (must remain) |
| `submissions.log` best-effort shadow, never gates receipt | **PASS** |
| `prove_applied(receipt_id)` as a one-bit yes/no check is sufficient by itself | **FAIL** |
| `prove_applied` + **ternary proof** + **started intent** + **domain marker in same durable write as content** + **CAS finish** | **PASS** as Section-1 seam |

**Overall seam:** **CONDITIONAL PASS** — the revised C1 direction is the right fix class; the contract is not complete until the interface laws below are explicit. Implementation must not treat “call `prove_applied`” as a slogan without ternary outcomes and per-adapter markers.

---

## Crash window under test

```
claim(lease, token, revision)
  → [optional] prove_applied == yes? → finish(applied) and stop
  → journal: started / applying (intent, application_ref)
  → domain mutation (Markdown / chat / settings) WITH durable marker, fsynced
  → journal: finish(applied) CAS(token, revision)
```

**Kill process** after domain mutation is on disk, before `finish(applied)`.

| Naive design (pre-C1) | Failure |
|----------------------|---------|
| Journal is only truth of “applied” | Restart sees still `claimed`/`received` → **re-mutates** → duplicate answer/note/task |
| Dual-write “both stores must succeed” for 202 | Impossible partial: receipt without shadow or shadow without receipt; wrong gate for client |

---

## Is `prove_applied` sufficient?

### Necessary: yes

After crash, the journal **cannot** know whether the domain write landed. Only the **domain** (or an adapter-owned side file committed with the domain write) can.

### Sufficient as a bare boolean: no

| Proof return | If treated as… | Risk |
|--------------|----------------|------|
| **yes** | skip mutate, finish applied | Correct when marker present |
| **no** | mutate again | **Duplicate** if mutation landed but marker missing/unreadable/wrong parse |
| **unknown** | re-mutate or skip | Both wrong without a third recovery path |

Therefore `prove_applied` must be **ternary**:

```text
prove_applied(receipt_id) -> Applied | NotApplied | Unknown
```

- **Applied** → `finish(applied)` only; never mutate again.
- **NotApplied** → `idempotent_apply` once under claim; then finish.
- **Unknown** → **do not** mutate; enter `needs_human` / `recovering` with path + byte offset; loud lock beats silent second write.

A pure “journal applied-set” without domain proof **fails** this window by construction (prior C1 critique stands).

---

## Required interface laws

### L1 · 202 authority

- `receive` returns **202 only after** journal adapter durable commit (receipt identity + exact payload + file+directory durability as #263 requires).
- Application outcome is **not** required for 202.
- Client may clear draft on 202 (receipt), not on applied.

### L2 · Shadow log

- `submissions.log` (or successor shadow) is **best-effort** after or beside journal commit.
- Shadow failure → transition/health `shadow_failed`; **never** fails the receipt.
- Cutover: stop requiring shadow; never scan shadow as apply queue.

### L3 · Claim before mutate

- Application runs only under an exclusive **claim** (`lease_token` + `revision`).
- Expired lease is reclaimable; reclaim **must** run `prove_applied` before any mutate.
- `finish` / `release` are **CAS** on `(receipt_id, token, revision)`.

### L4 · Started intent before domain write

Order is load-bearing:

1. CAS transition → `applying` (or `started`) with `application_ref` / adapter name.
2. Domain write **including marker**, fsync.
3. CAS `finish(applied, application_ref)`.

Without (1), a crash mid-mutate is indistinguishable from “never started” only if proof is perfect; (1) makes “in progress” observable for ops and for adapters that need multi-step apply.

### L5 · Domain marker co-committed with content

Each Markdown (or other) adapter **must**:

| Law | Requirement |
|-----|-------------|
| **Marker** | Durable, greppable token keyed by `receipt_id` (or stable hash of receipt_id) inside the **same** atomic domain object as the human-visible effect |
| **Atomicity** | One replace/append unit: either full-file write+fsync or append framed block+fsync; **no** “write body then later write marker” |
| **Idempotent apply** | If marker present → no-op success with same `application_ref` |
| **Search scope** | All places the effect can live (e.g. questions Open **and** Answered after fold) |
| **No silent repair** | Torn/partial files → `Unknown`, preserve bytes, do not drop tail |

Suggested marker shapes (adapter-local, not global UUID-in-every-prose mandate):

- **questions answer/note:** structured HTML comment or sub-bullet metadata line carrying `receipt_id=…` adjacent to the human_block (human-visible text remains human_block-safe).
- **answers.md ask:** same.
- **tasks.md:** ledger field `receipt: <id>` on the created/updated task line.
- **settings/tint:** settings object key or sibling `.receipts` map entry written in the same atomic replace as the value.
- **topic chat:** already receipt-scoped application_ref in chat/run state; transcript turn metadata names `receipt_id` / `request_id`.

Embedding raw UUIDs in free prose is **not** required if the adapter’s structured margin holds the id.

### L6 · Replay table (exact)

| After crash, reclaimer sees journal phase | prove_applied | Action |
|------------------------------------------|---------------|--------|
| `received` / `claimed` / `applying` | **Applied** | CAS finish applied; release lease; **no** domain write |
| same | **NotApplied** | idempotent_apply once; if success CAS finish applied; if apply fails → failed/retryable with reason |
| same | **Unknown** | CAS needs_human/recovering; **no** domain write; surface path + offset |
| already `applied` | any | no-op (idempotent) |
| `rejected` / terminal fail | — | no apply |

Two reclaimers: only one CAS finish wins; loser observes applied/terminal and exits.

### L7 · At-least-once application, exactly-once effect

- Delivery to domain is **at-least-once**.
- **Effect** is exactly-once **iff** marker + idempotent_apply hold.
- Journal “applied” is a **projection of successful finish**, not a substitute for the marker.

---

## Minimal failure fixtures (red-first)

1. **Crash after domain fsync, before finish**
   Domain contains marker; journal still `applying`.
   **Expect:** one human-visible effect; finish → applied; second apply no-op.

2. **Crash after started, before any domain write**
   **Expect:** prove NotApplied → single apply → one effect.

3. **Crash mid-file (torn write)**
   **Expect:** Unknown; no second append; loud recovery; bytes retained.

4. **prove false-negative simulation** (marker stripped in test double while body present)
   **Expect:** either Unknown path or duplicate prevention fails the test — documents why ternary + co-commit are mandatory.

5. **Two processes reclaim same receipt**
   **Expect:** one apply effect; one finish winner; other no-ops.

6. **202 without shadow**
   Force shadow OSError.
   **Expect:** still 202; health shadow_failed; receipt durable.

7. **202 requires journal fail**
   Force journal fsync fail.
   **Expect:** no 202; client attempt retained (#269).

8. **Same client UUID + same digest** concurrent receive
   **Expect:** one receipt.

9. **Same UUID + different bytes**
   **Expect:** 409; no second receipt.

---

## Interaction with leased claim / CAS (summary)

```
claim ──► applying (CAS) ──► domain+marker fsync ──► applied (CAS)
              │                      │
              │                      └─ crash: prove decides
              └─ lease expiry: reclaim must prove before mutate
```

PID death without lease expiry: monitor/reconcile treats as reclaim candidate; still prove-first.

---

## Residual risks (not automatic FAIL of the seam)

1. **No full #263 design artifact yet** — laws above should be copied into Section 1 when written.
2. **Marker grammar vs `human_block()`** — markers must not reopen bullet-forging; put them in structured margins the parser already owns.
3. **Fold-by-complement** moves answers across sections — search both, or re-key marker before fold in the same apply.
4. **Postgres later** — proof is domain-side; journal CAS maps to row version / `SKIP LOCKED`; no change to ternary proof.

---

## Bottom line

- **D1 (202 + shadow):** keep.
- **C1 (`prove_applied`):** keep as the core of crash safety, but specify **ternary proof**, **started intent**, **co-committed domain markers**, and **CAS finish**.
- Bare “check journal applied set” remains **rejected**.
- With the interface laws and fixtures above, the Section-1 contract for this crash window is **PASS-ready**.

No source, tasks, questions, or status edits beyond this research file.
