# Brief storage — keep the record tracked until a database requirement exists

## Verdict

**INFERRED — recommendation.** A brief is an immutable **dispatch record**, but
“record” does not imply “database row.” Keep the current corpus file-backed and
tracked; do not add `.dreamwork/docs/briefs/` to `.gitignore`, and do not copy
full prompts into the database now. Make the future `(role, prompt)` launch API
depend on a brief-store interface and strengthen the record envelope so its
receipt binds task, role, and exact prompt. A database cutover remains available
if a measured transactional, concurrency, privacy, or scale requirement later
refutes the file-backed store.

**INFERRED — storage consequence.** If a later cutover makes SQLite the one
authoritative home, stop treating per-brief files as writable peers. Either stop
emitting new files, or emit a deterministic Git-tracked export that is marked
derived, regenerable from the database, and loses on disagreement. A blanket
ignore rule is not a migration: applied now it would hide the only authority;
applied later to a deliberately tracked export it would remove that export's
purpose.

**VERIFIED — governing rule.** The repository's canonical rule requires exactly
one authoritative on-disk home per fact and permits another representation only
when it is derived, regenerable, and subordinate (`DREAMWORK.md:169-182`).

## What a brief is today

| Aspect | Measured fact |
|---|---|
| Meaning | **VERIFIED.** It is the exact validated prompt handed to the runner, not a summary or a later reconstruction (`dev/dispatch_lane.py:2-13`). |
| Input author | **VERIFIED.** The coordinator supplies a prompt file to `just dispatch-lane`; that recipe invokes the checked wrapper and supplies the separate `ccc` agent argument (`justfile:28-34`). |
| Record writer | **VERIFIED.** `dev/dispatch_lane.py::main` reads and validates the prompt, derives task and lane, persists it, and only then `exec`s the runner (`dev/dispatch_lane.py:436-481`). |
| Identity | **VERIFIED.** `_identity` parses task id from the first-level heading and requires one `Branch:` line; the path is `<task>-<lane>.md` (`dev/dispatch_lane.py:296-309`, `dev/dispatch_lane.py:351-359`). |
| Write semantics | **VERIFIED.** `persist_prompt` uses exclusive creation, refuses a colliding name with different content, and removes a half-created pair on failure (`dev/dispatch_lane.py:312-319`, `dev/dispatch_lane.py:351-385`). |
| Receipt | **VERIFIED.** The sibling `.sha256` names the brief and records SHA-256 over the exact prompt; `_verify_pair` distinguishes absent halves, malformed receipts, and changed content (`dev/dispatch_lane.py:322-348`). |
| Governance boundary | **VERIFIED.** `INTEGRITY_START_TASK = 766` grandfathers historical briefs without receipts; `verify_pending` also adds every present receipt's `.md`, so after #807 a receipt governs its brief regardless of task id (`dev/dispatch_lane.py:35-42`, `dev/dispatch_lane.py:388-401`; E4). |
| Dispatch ordering | **VERIFIED.** Persistence failure refuses launch; after persistence, the same prompt value is appended as one runner argv item (`dev/dispatch_lane.py:458-481`; `SKILL.md:356-379`). |
| Pending window | **VERIFIED.** The pair is intentionally uncommitted during the lane and is verified and committed at the merge gate (`dev/dispatch_lane.py:10-13`; `SKILL.md:370-380`). |
| Git state at this decision | **VERIFIED.** At base `3a7539f9`, `git ls-files` and `find` both counted **279** `.md` briefs and both counted **61** receipts; `git check-ignore --no-index` printed no matching rule. Evidence command E1 below. |
| Existing DB support | **VERIFIED.** The current task repository stores task fields and a chained task-event log, but no brief, prompt, dispatch, or role record exists (`dreamwork_db/tasks.py:58-115`, `dreamwork_db/tasks.py:177-220`; E2 returned no match). |

**INFERRED — classification.** Those properties make the file pair a record
serialization already: named identity, exact payload, create-once semantics,
pre-launch ordering, and an integrity receipt. Calling it “a file” describes its
medium; calling it “a record” describes its contract. The API should depend on
the contract.

## Who reads it, and what moving it would break

| Reader | Current dependency | Consequence of an uncoordinated move |
|---|---|---|
| Dispatch verifier | **VERIFIED.** `_briefs_dir` resolves the main checkout's literal `.dreamwork/docs/briefs/`; `verify_pending` globs `.md` and `.sha256` and checks every pair (`dev/dispatch_lane.py:79-116`, `dev/dispatch_lane.py:388-422`). | **INFERRED.** DB-only storage would make dispatch or the merge gate refuse or examine nothing until this reader is replaced. |
| Corpus commit route | **VERIFIED.** `just commit-corpus` runs `--verify-pending`, then stages every receipt and its `.md` together (`justfile:645-670`). | **INFERRED.** The supported durability route disappears; ignoring first would recreate an invisible pending corpus. |
| Citation audit | **VERIFIED.** `corpus_coverage` compares on-disk and Git-tracked `.md` counts, and `audit_briefs` reads every brief's citations (`dev/citation_audit.py:129-144`, `dev/citation_audit.py:223-248`). | **INFERRED.** A DB move needs a repository reader and an equivalent completeness measure; merely pointing at a local DB would not prove a worktree saw the full population. |
| Lint corpus checks | **VERIFIED.** `lint.py` enumerates the directory for corpus reach, hand-off obligation, absolute inbox, lane scratch, and lane ownership (`lint.py:4051-4122`, `lint.py:4176-4748`, `lint.py:4950-5031`). | **INFERRED.** These checks would either go silent or report historical-only coverage until migrated together. |
| Containment guard | **VERIFIED.** `dev/lane_guard.py` scans main-checkout briefs for a lane and parses `Lane-owns:` as its ownership source (`dev/lane_guard.py:187-246`; `file-formats.md:2091-2118`). | **INFERRED.** Removing files before a DB-backed reader exists empties the ownership set and weakens the early commit guard. |
| Liveness/status | **VERIFIED.** Observable lanes use pid first and a brief path as fallback; unobservable `spawn_subagent` forms are deliberately carried and reaped by task state (`status_sync.py:231-269`, `status_sync.py:648-673`). | **INFERRED.** A direct Dreamhub launcher needs record/dispatch identity in status; it must not manufacture a path merely to satisfy the old fallback. |
| Humans, Git, and worktrees | **VERIFIED.** The tracked corpus is available in this worktree; the earlier worktree-only audit missed untracked prompts and reached the wrong conclusion (E3), while #807 records the corrected 279/279 tracked state (E4). | **INFERRED.** DB-only can be safe only if every worktree resolves the same authoritative store and the store has an explicit backup/export boundary. Gitignore by itself supplies neither. |

**INFERRED — migration boundary.** “Move briefs to the DB” therefore names a
multi-reader cutover, not a schema edit. The unit of change is the writer,
verification, audit, containment, status identity, and durability/export path.

## IGC judgement

**VERIFIED — method.** This judgement uses the worktree-local `./igc-method.md`:
each cell asks whether a known decisive error refutes an idea for a binary goal;
the `All` column is `✘` if any goal is refuted.

**INFERRED — context.** Today there is one coordinator-side writer, 279 tracked
immutable prompts, 61 receipts, several file readers, a machine-local task DB,
and a possible future Dreamhub API whose caller supplies `(role, prompt)` while
the dreamworker supplies the task.

**INFERRED — goals.** G1: exactly one authoritative home for each prompt. G2:
retain current integrity, audit, containment, and worktree visibility until
replacements judge the same cases. G3: persist the exact task/role/prompt record
before launch and launch those exact stored prompt bytes. G4: let Dreamhub call
one storage contract without parsing filenames or prose. G5: introduce a DB
migration only for a measured requirement the file-backed record cannot meet.
G6: keep one supported writer and verification path, with no permanent peer
dual-write.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I1 — tracked file-backed record behind a store interface | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| I2 — DB-only now; ignore/remove the corpus | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ | ✔ |
| I3 — write the full prompt independently to file and DB | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ |
| I4 — declare a staged DB cutover now, before its trigger exists | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ |

**INFERRED — I1 contested cells.** I1 satisfies G3 and G4 only if the API uses
an opaque brief-store operation and the receipt envelope gains structured task
and role fields. The present filename/prose parsing is an implementation detail,
not the proposed API. Exclusive file creation already supplies create-once
semantics; process launch is outside either a file or SQLite transaction.

**INFERRED — I2 decisive errors.** An immediate DB-only flip fails G2 because
the measured reader set is file-bound, and fails G5 because `(role, prompt)`
does not itself require relational queries or a transaction shared with task
state. It would spend the migration before its differentiating requirement is
known.

**INFERRED — I3 decisive errors.** Two independently writable prompt bodies are
two authorities for one fact. A hash in one home does not define which body wins
when writers or repairs disagree. This is the exact design class the one-home
rule refuses.

**INFERRED — I4 decisive error.** A careful cutover would preserve the present
system, but naming SQLite as the destination today still fails G5: it converts a
hypothetical launcher into an unmeasured storage requirement. I1 preserves that
option without pre-deciding it.

**INFERRED — decision.** I1 is the sole non-refuted idea in the measured
context. The result is tentative: the falsifiers below reopen the matrix.

## Contract needed by a `(role, prompt)` API

**INFERRED — caller boundary.** `role` and `prompt` may be the only required
caller parameters, but they are not the complete stored identity. At request
time the dreamworker must resolve exactly one task and pass its stable `task_id`
to the store; absence or ambiguity should refuse rather than extracting a task
from prompt prose.

**INFERRED — authoritative record.** The store should create one immutable
record with at least:

- **INFERRED:** opaque `brief_id`, independent of a branch or filename;
- **INFERRED:** `task_id`, supplied by the dreamworker;
- **INFERRED:** logical `role`, supplied by the API caller;
- **INFERRED:** exact prompt bytes (UTF-8, no normalization);
- **INFERRED:** creation time and writer identity;
- **INFERRED:** a versioned receipt over a length-delimited envelope containing
  `task_id`, `role`, and prompt bytes, not prompt alone.

**INFERRED — separate launch attempt.** Concrete transport and outcome belong
to a dispatch-attempt record keyed to `brief_id`: resolved runner/alias, attempt
time, pid or remote id when observable, and launched/refused/failed outcome.
This prevents a retry or a different launcher from rewriting the brief that
explains what was requested.

**INFERRED — order.** The store create and receipt verification commit first;
the launcher then reads the stored prompt and passes that value to `ccc`, a
direct CLI, or a future remote transport. A launch failure retains the record
and records a failed attempt. No launcher accepts an unpersisted prompt.

**INFERRED — interface.** The first API should depend on operations such as
`create(task_id, role, prompt) -> (brief_id, receipt)`, `get(brief_id)`,
`list(task_id=...)`, and `verify(brief_id)`. The initial implementation can
serialize records under the tracked corpus; a later DB implementation can
replace it without changing the launch API or its ordering.

**INFERRED — role semantics.** `role` should name a logical duty or policy, not
a concrete `ccc` alias or model. Resolution belongs to the dispatch attempt;
otherwise changing the installed alias map changes the meaning of historical
briefs.

## Staged path without two homes

1. **INFERRED — now:** keep `.dreamwork/docs/briefs/` tracked and authoritative.
   Add no ignore rule and no prompt column/table. Preserve the current merge-gate
   receipt and corpus commit route.
2. **INFERRED — API preparation:** define the brief-store contract and versioned
   task/role/prompt receipt. Implement it over the current tracked record
   serialization first. Repoint launch code to the interface, not to a path.
3. **INFERRED — reader consolidation:** make verification, citation audit,
   containment, lint, status, and any Dreamhub view consume the same repository
   interface. A replacement must retain each reader's current fail-closed or
   honest-silence boundary.
4. **INFERRED — conditional DB cutover:** only after a falsifier is measured,
   import and verify the full population, switch the writer and every reader in
   one cutover, and name SQLite as authority. Do not leave both stores writable.
5. **INFERRED — export choice:** if Git-alone review/recovery remains a goal,
   produce a deterministic tracked export with its derivation and freshness
   check stated. If it is not a goal, stop producing new corpus files; historical
   tracked files remain in Git history. Neither outcome needs a blanket ignore
   of the present corpus.

## What would falsify this recommendation

- **INFERRED — transactional falsifier:** one launch must atomically change task
  state and create its brief, with failure of either rolling back both. That is
  a real shared-DB requirement the file-backed store cannot meet without a
  cross-store protocol.
- **INFERRED — writer/concurrency falsifier:** multiple independent Dreamhub
  writers need serializable idempotency or queries that exclusive file creation
  and a bounded directory scan cannot satisfy. This must be demonstrated with a
  failing concurrency or latency breakpoint, not assumed from “API.”
- **INFERRED — trust falsifier:** the human rules that exact prompts are
  operator-private runtime data and must not enter Git, or a measured prompt
  contains material the repository's trust boundary cannot retain. Then tracked
  files fail the privacy goal and a local protected store plus backup policy is
  required.
- **INFERRED — scale falsifier:** measured corpus reads exceed the agreed launch,
  audit, or UI latency/memory breakpoint after indexing/caching options are
  exhausted.
- **INFERRED — topology falsifier:** the authoritative launcher and its readers
  must operate without access to the target checkout, while a shared database is
  already an accepted dependency and no tracked export is required.

## Ruling needed from him

**INFERRED — direct question, with recommendation.** “Should the exact prompt of
every subagent launch remain durable **project history reviewable and recoverable
from Git**, or should it be **operator-local runtime data that must stay out of
Git**? I recommend project history, with launch-time refusal when a prompt would
cross the repository's secret boundary; if you choose operator-local, that is
the decisive reason to move the authority to a protected DB and stop tracking
new briefs.”

**INFERRED — schema follow-up, with recommendation.** “Does `role` mean a logical
duty/policy (`reviewer`, `implementer`, and so on), or the concrete runner alias
or model used for this attempt? I recommend logical duty in the brief and the
resolved alias/model in the dispatch attempt.”

## Evidence receipts

**VERIFIED — E1, corpus and ignore state at base `3a7539f9`.** These commands
returned `279`, `279`, `61`, `61`, then no ignore match:

```text
git ls-files '.dreamwork/docs/briefs/*.md' | wc -l
find .dreamwork/docs/briefs -maxdepth 1 -type f -name '*.md' | wc -l
git ls-files '.dreamwork/docs/briefs/*.sha256' | wc -l
find .dreamwork/docs/briefs -maxdepth 1 -type f -name '*.sha256' | wc -l
git check-ignore --no-index -v .dreamwork/docs/briefs/825-cx-825briefs.md
```

**VERIFIED — E2, current schema search.** `rg -n
"brief|dispatch|prompt|role" dreamwork_db` exited 1 with no output. The positive
schema evidence is the task and event implementation cited above; E2 is only the
bounded negative claim that the current `dreamwork_db/` source contains none of
those four terms.

**VERIFIED — E3, #786 opened with the required worktree-aware ledger command.**
Relied-on lines: “the lane's central MEASUREMENT is wrong” and “The lane's
worktree could only ever see the tracked 219. So the corpus damage is real and
located, not ephemeral.” This is the observed cost of making audit reach depend
on tracked visibility without first checking corpus completeness.

**VERIFIED — E4, #807 opened with the required worktree-aware ledger command.**
Relied-on lines: “the WRITER receipts every brief regardless of id; the VERIFIER
governs only ids >= 766. Two sides of one contract, disagreeing,” and after the
fix, “the brief corpus is now 279 tracked / 279 on disk and
dev/citation_audit.py no longer prints 'AUDIT IS INCOMPLETE'.” This is the
current integrity and completeness baseline.

**VERIFIED — E5, #763 opened with the required worktree-aware ledger command.**
Relied-on lines: “#766 landed: dev/dispatch_lane.py now WRITES each brief to
.dreamwork/docs/briefs/<id>-<lane>.md with a .sha256 integrity receipt and
refuses a receiptless file,” and “before a brief calls something a defect, grep
the owning module's docstring for the decision.” The module docstring was read
at `dev/dispatch_lane.py:2-13`; the tracked record is a deliberate design, not an
accidental untracked directory.

**VERIFIED — E6, #440 opened with the required worktree-aware ledger command.**
Relied-on line: “dev/ledger.py is now the one supported path,” reusing the
production parser so “no sixth parser exists.” Applied here as the requirement
for one brief-store interface, not as a claim that the ledger and brief formats
are identical.

**VERIFIED — E7, #764 opened with the required worktree-aware ledger command.**
Relied-on lines: “a line number carries no evidence of what it points at” and “A
stale coordinate that lands on a different VALID lesson head still passes.”
This document therefore separates measured claims from judgement and quotes the
content relied upon rather than treating issue numbers as self-explanatory.

**VERIFIED — no new enforcement.** This task adds a decision document and its
doc-map registration only. It adds no check or guard, so production sabotage
red-proof directions are not applicable; the recommendation's falsification
conditions are stated above instead.
