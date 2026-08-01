# Lane 752 remainder report — citation roles restored

## Verdict

All four remaining citation sites are corrected without behavioural changes.
The ledger comment again names `#590` as the measured folded-but-unmerged
instance and names `lessons.md:3302` as the record of that instance. The three
`watch.py` comments now cite entries whose bodies contain the claims being
made: `#337` for sticky steering raising the next message's authority, and
`#504` for the measured chat-turn forgery and its `one_line` fix.

The `#751` merge moved the reported `watch.py:2685` occurrence to current line
2706; line 2685 is now the `entry = ...` assignment. I changed the cited
comment, not the stale coordinate. The correct `#126` page-provenance use is
still present at current `watch.py:4807 @ dd72dead` and was not touched.

Commit: `54bb368a` (`fix(#752): correct remaining citation roles`). The change
is five replaced comment lines across only `dev/ledger.py` and `watch.py`.

## Disposition by site and role

| Current site | Comment's claim | Entry evidence | Role decision and disposition |
|---|---|---|---|
| `dev/ledger.py:916-917` | A folded but never merged branch is invisible to sweep by construction; this happened to `#590`. | `#590` is titled **“Re-rank the open backlog against his 2026-07-31 focus”**. `lessons.md:3302` says: **“`#590`'s lane landed a 377-line backlog re-rank … The branch was never merged.”** | `#590` is the illustration/instance; the lesson is the evidentiary record and authority. Restored both roles in one parenthetical. |
| `watch.py:2706` | Newline-bearing chat text must not be able to forge a framed turn; `one_line` is one half of the measured fix. | `#126` is titled **“Composer commands carry the page they came from”** and says only **“the route is a hint, never an instruction.”** `#504` records: **“marker-bearing chat text parsed as a fabricated agent reply — one_line necessary not sufficient”**, then says it was fixed and bound. | `#126` was neither authority nor the local illustration. `#504` is the measured applied instance and implementation record, so it replaces `#126`. |
| `watch.py:334` | Persistent steering silently raises the authority of the next message. | `#257` is titled **“Give `do-now` a danger and urgency treatment”** and contains visual treatment decisions. `#337` states verbatim: **“a mode that persists silently raises the authority of his NEXT message.”** | The comment attributes reasoning, so it needs the entry that states the reasoning: replaced `#257` with authority `#337`. |
| `watch.py:338` | That authority rationale does not apply to a conversational channel. | The same `#257`/`#337` contrast above applies; `#337` also distinguishes steering decay from sticky modes in the feature that landed the `sticky` property. | This is an application of `#337`'s stated rationale, not `#257`'s visual treatment. Replaced `#257` with `#337`. |

No site was left uncited: exact supporting entries existed for all three
`watch.py` claims, and the ledger site deliberately names both the instance and
the record so a later audit cannot collapse those roles again.

## Red-proof

### Direction 1 — mismatch demonstrated from live ledger reads

The table above quotes the discriminating live `ledger.py get` text beside each
comment's claim. The visible mismatches are:

- `#126`: **page provenance / route-as-hint**, not newline-collapse or framed
  turn integrity. The replacement `#504` records the exact fabricated-turn
  failure and the `one_line` half of its fix.
- `#257`: **danger/urgency visual treatment**, not sticky-mode authority. The
  replacement `#337` contains the exact authority sentence.
- `#590`: its entry is the backlog-rerank instance, while
  `lessons.md:3302` supplies the measurement that its branch was folded and
  never merged. Replacing the instance with the lesson is visibly a role
  error, even though the lesson is the authority for the general rule.

This is a wording demonstration rather than a behavioural test: there is no
mechanical assertion whose red state can establish semantic citation roles.

### Direction 2 — the false-green a role-blind method misses

Construct the comment **“a non-zero count is a question, not a verdict
(`#590`)”**. It is genuinely wrong as an authority citation, but a thematic or
proximity audit can accept it because `#590` is the branch-audit lesson's
example. Reverse the sentence to **“`#590` is the measured folded-but-unmerged
instance”** and the same citation is right as an illustration even though the
entry itself does not state the general rule. A method that assigns one verdict
per id cannot distinguish these two inputs.

At the four sites I distinguished the roles from the grammar and evidence:

- “`#590` is the measured instance” identifies an entity; the lesson explicitly
  measures that entity, so illustration is the intended role.
- “the `#126` rule” claimed authority, but the entry states a different rule;
  `#504` records this exact measured implementation failure.
- “`#257`'s reasoning” and “`#257` authority rationale” explicitly claimed
  authority; `#257` is at most thematically adjacent, while `#337` states the
  reasoning verbatim.

The independent review also produced a second false-green shape: `#612` can be
a valid illustration for “a report nobody can skim is a report nobody reads,”
but it would be a wrong authority for the nearby verb-form versus widened-form
classification, whose authority is `#707`. Nearby semantic overlap is not a
role check.

`python3 dev/redproof.py check` output after the edits:

> `check: calm — no injections registered (opt-in discipline; nothing to evaluate).`

## Relied-on task evidence

Every id relied on here was read with the live absolute-ledger invocation.

- `#752`: the landed audit remains open for exactly **“the three watch.py
  occurrences the fence prevented plus one over-correction … to reverse.”**
- `#590`: backlog re-rank; its lane is the instance named and measured by
  `lessons.md:3302`, not the authority for question-not-verdict.
- `#337`: **“a mode that persists silently raises the authority of his NEXT
  message.”**
- `#504`: **“marker-bearing chat text parsed as a fabricated agent reply —
  one_line necessary not sufficient.”**
- `#126`: **“Composer commands carry the page they came from … the route is a
  hint, never an instruction.”**
- `#257`: **“Give `do-now` a danger and urgency treatment”**; its entry is
  visual/UI treatment, not sticky-mode authority.
- `#751`: its landed note says the first production React surface conversion
  included `watch.py` page assembly. That landing explains the current line
  drift and why the former fence is now free.
- `#146`: **“A newline in a note forges a whole QUESTION.”** It is a real but
  broader questions-channel instance, not the exact chat-turn record used here.
- `#748`: a self-contained principle needs no manufactured authority; a
  citation adds a way to be wrong. No citation was retained merely for shape.
- `#707`: widening attribution multiplies false positives; its landed note says
  the report splits verb-form from widened-form and says “names,” not “names a
  landing for.” I did not reach for an approximate replacement.
- `#702`: malformed/unresolved ids are kept and reported rather than silently
  reaped. No unresolved replacement was forced.
- `#612`: its actual scope is fold-prompt output volume. The edit stays at four
  logical comment sites rather than adding a new explanatory section in code.

## Verification and rebase

- Before: `PYTEST_ADDOPTS='-n 2' python3 -m pytest test_watch.py` collected
  **489** and passed **489/489** in 39.04s.
- After: the same command collected **489** and passed **489/489** in 40.10s.
  The count did not move.
- `python3 lint.py`: exit 0, **`clean (6 warning(s))`**, zero ERRORs. These are
  the expected worktree/store and existing state/doc warnings named in the
  brief; none was chased.
- `python3 dev/redproof.py check`: calm, no injections registered, nothing to
  evaluate.
- `git diff --check`: clean before the source commit.
- Local `master` remained `8561238f`; the branch was one commit ahead and zero
  behind, so no rebase was required before writing this report.
- No browser guard was run: these are comments only. No ports were bound.

## Out of scope

None found beyond the stale line coordinate noted below. No live-ledger verb
other than `get` was run, and no off-limits file was edited.

## DOGFOOD REPORT

The task's `watch.py:2685` coordinate was stale after the explicitly mentioned
`#751` merge: the cited occurrence is now line 2706. The claim text made it
recoverable, but a line-only instruction would have pointed at an unrelated
assignment. Future remainder briefs should pair volatile line numbers with the
exact cited phrase, as this one fortunately did.

The strongest replacement entries were not the nearest thematic ones. `#337`
contains the authority sentence verbatim, and `#504` records the exact local
turn-forgery measurement. Reading candidate bodies prevented both removing
useful provenance and substituting the broader `#146` questions-channel
instance. No further tooling or brief friction found.
