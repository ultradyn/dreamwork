# Lane 752 report — source citation audit

## Verdict

The complete stated surface contains **846 citation occurrences naming 241
identifiers**: 684 occurrences in source comments and 162 in strings that are
printed, returned as diagnostics/help, or written into a user-facing generated
artifact. I excluded 660 docstring occurrences and one inert module-scope string
at `watch.py:2203`; neither is a source comment or a user-facing string.

Occurrence-level classification is **724 right, 18 wrong, 104 unclassified**.
The unclassified denominator is not a clean-looking remainder: 49 occurrences
name 17 ids that `ledger.py get` cannot resolve, 28 are syntax/data examples
rather than authority claims, and 27 are cross-domain applications of the
general `#136` / `#671` / `#702` reporting shapes that are arguable rather than
demonstrably wrong. I left every arguable occurrence unchanged.

The 18 wrong occurrences form five groups:

| Cited id | Occurrences | Claim being supported | What the entry actually supports | Disposition |
|---|---:|---|---|---|
| `#590` | 9 | a name/count/`+` is a question, not a verdict | backlog re-ranking; its nearest line says its numbers are recommendations | fix all 9 in `dev/ledger.py` and `lint.py` |
| `#126` | 3 | collapse newlines so human text cannot forge a line-oriented record | commands retain the page they came from | fix 2 in `dev/journal_consume.py`; report `watch.py:2685` only |
| `#440` | 3 | one supported lane-count accessor / positive runner identity | one supported ledger fold/parser path | repoint to the applied `#728` / `#729` tasks |
| `#576` | 1 | raw branch counts cannot distinguish patch-equivalent work | Pending hand-offs without Folded lines | repoint `dev/ledger.py:904` to `lessons.md:3302` plus `#676` |
| `#257` | 2 | persistent steering raises the authority of the next message | a visual danger/urgency treatment for `do-now` | `watch.py:334,338` are off-limits; report only |

This is more than a handful, so this report is the first landing and the source
corrections follow separately. The three wrong `watch.py` occurrences remain
untouched exactly as scoped.

## Method and denominator

1. Tokenise every top-level `dev/*.py`, plus `lint.py`, `watch.py`,
   `status_sync.py`, and `tick_line.py`; enumerate exact `#[0-9]+[a-z]?`
   occurrences in `COMMENT`, `STRING`, and `FSTRING_MIDDLE` tokens.
2. Exclude AST-recognised docstrings. Inspect every remaining string and exclude
   the one inert explanatory literal that is neither emitted nor written.
3. Run the required absolute-ledger `python3 dev/ledger.py get <id> --ledger
   /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md` for all
   241 identifiers. Result: 224 numeric ids resolved; 13 numeric ids and four
   suffix ids did not.
4. Judge every occurrence, not merely every unique id. Mixed uses matter:
   `#126` is right at `watch.py:4807 @ bf02e917` for page provenance and wrong at
   `watch.py:2685` for newline collapse; `#440` is right in the ledger tool and
   wrong when transferred to lane-process classification.

The unresolvable identifiers are `#3`, `#5`, `#6`, `#7`, `#8`, `#9`, `#31`,
`#96`, `#147`, `#199`, `#222`, `#223`, `#229`, `#392a`, `#399b`, `#402a`, and
`#402b`. They account for 49 occurrences and were not coerced to other ids or
looked up in stale files.

The 28 syntax/data examples include combined-id grammar such as
``**#250/#251**``, hand-off prose such as ``#565/#569, #583``, commit-subject
examples such as ``Merge #688`` / ``#700:``, and the observed malformed value
``"#696"``. They make no authority claim, so calling them right would be as
misleading as calling them wrong.

The 27 arguable occurrences apply a statement the entry really does contain to
a different subsystem: the three-zero-state distinction from `#136`, the
did-not-evaluate distinction from `#671`, and the report-don't-drop disposition
from `#702`. They are not the `#590` case—the claimed principle is present in
their entries—but the transfer is broader than the recorded instance. They are
reported here and deliberately left alone.

## Wrong-site inventory

- `dev/ledger.py`: `#590` at lines 254, 277, 858, 889, 900, 907, 970, and
  1016; `#576` at line 904.
- `lint.py`: `#590` at line 4968.
- `dev/journal_consume.py`: `#126` at lines 732 and 787.
- `dev/guard_preflight.py`: `#440` at line 135.
- `status_sync.py`: `#440` at lines 306 and 837.
- `watch.py` (off-limits): `#126` at line 2685 and `#257` at lines 334 and
  338.

## Should this be mechanical?

No useful semantic check exists here, and I am not building the existence-only
one.

An existence check would catch the 49 unresolvable occurrences but none of the
18 wrong ones: every wrong id resolves. A token/keyword similarity check is
actively non-discriminating for the live defect—`#590` is richly adjacent to
branch auditing because its lane is the lesson's example. Requiring a manually
curated claim beside every id merely moves the same human semantic judgement
into a second record that can repeat the mistake. An LLM/embedding check would
be a reviewer with unstable false-positive behaviour, not a deterministic lint
contract.

This matches the reasoning in `.dreamwork/lane-737-report.md`: a syntactic
heading check could distinguish neither honest reflection from a perfunctory
sentence nor the decision moment from a later artifact. Here too, the cheap
mechanism observes the token and misses whether it is evidence.

### Audit red-proof

**Direction 1:** the occurrence-level reading independently finds all nine
`#590` uses rather than only the three supplied sites. The discriminating
message is semantic: *“`#590` is a backlog re-rank; it does not state the
question-not-verdict principle.”* It also finds the sibling `#126` chain:
*“`#126` records page provenance; newline-collapse lives at
`lessons.md:283–291`.”*

**Direction 2 (open false-green):** this reading method can accept a citation
whose entry literally repeats the claim but whose note copied the same bad
attribution rather than recording independent evidence. `#676` demonstrates
the shape: it literally contains “#590's rule applies,” so citing `#676` for the
applied rule is defensible even though that sentence's own attribution is
wrong. A later note can therefore make semantic text agreement pass while the
authority chain remains circular. Only a reader checking provenance beyond the
entry catches that; this audit checked support, not independent authorship of
every supporting sentence.

## Relied-on ledger evidence

Every id below was opened through the live absolute-ledger command.

- `#590`: “every number is a recommendation and the lane wrote no priority to
  the store.” This is the nearest relevant line; it is not the claimed rule.
- `#676`: “**#590's rule applies: a non-zero count is a QUESTION, not a
  verdict.**” The sentence is present and the task applies the audit, so the
  `#676` half is defensible while its internal attribution is not.
- `#126`: “Composer commands carry the page they came from … the route is a
  hint, never an instruction.” No newline-collapse claim appears.
- `#440`: “a single supported way to fold an entry.” Its recorded scope is the
  ledger fold/parser, not lane-process identity.
- `#728`: “prefer a NAMED ACCESSOR on status_sync … over another positional
  unpack.” This is the exact lane-count accessor authority.
- `#729`: “prefer positive evidence over 'cwd is deleted'” and the landed task
  splits coordinator ancestry, known runners, and noise. This is the exact
  runner-identity authority.
- `#576`: “a Pending entry with no corresponding Folded line is never flagged.”
  It says nothing about `rev-list` or patch equivalence.
- `#257`: “Give `do-now` a danger and urgency treatment” with visual treatment
  details. It does not state the sticky-mode authority rationale.
- `#136`: “THREE zero-states, not one.” This is why broader applications were
  reported as arguable rather than called wrong without qualification.
- `#671`: sweep “examines zero ledger entries and says so confidently.” It
  records the did-not-evaluate reporting shape.
- `#702`: malformed ids are “KEPT and reported loudly rather than reaped as
  dead.” It records report-don't-drop in the status-sync application.
- `#531`: despite its unrelated burndown title, its body says “consume
  --through <ordinal> bounds the advance … to the pending read's head.” This is
  a title-mismatch that the full-body method correctly classifies as supported.
- `#707`: its landed note says the sweep report “splits verb-form from
  widened-form and says 'names' rather than 'names a landing for'.” This is the
  direct replacement for sweep's `#590` uses.

## Verification and landing

- Before changes: `python3 -m pytest test_lint.py` collected **535** and passed
  **535/535** in 74.29s.
- Before changes: `python3 lint.py` exited 0, `clean (6 warning(s))`, zero
  ERRORs. The warnings are the expected worktree/store and existing state/doc
  warnings.
- Audit-first commit after final rebase: `bf02e917` (`docs(#752): audit source
  citation authority`).
- Source-fix commit after final rebase: `e865b5bf` (`fix(#752): correct source
  citation authority`). It fixes 15 occurrences in five permitted files. The
  three demonstrated wrong `watch.py` occurrences remain untouched and are
  listed above.
- After changes and the final rebase: `python3 -m pytest test_lint.py`
  collected **535** and passed **535/535** in 74.53s. The requested before and
  after counts are therefore 535 and 535.
- Focused affected surface: `python3 -m pytest test_ledger.py
  test_journal_consume.py test_guard_preflight.py test_status_sync.py` passed
  **160/160** in 18.60s.
- `python3 lint.py`: exit 0, `clean (6 warning(s))`, zero ERRORs. The six are
  the same expected worktree/store and pre-existing state/doc warnings.
- `python3 -m py_compile dev/journal_consume.py dev/guard_preflight.py
  dev/ledger.py lint.py status_sync.py`: exit 0.
- `python3 dev/redproof.py check`: **“check: calm — no injections registered
  (opt-in discipline; nothing to evaluate).”** No mechanical check was built,
  so there was deliberately no direction-1 code injection; the audit's two
  directions are recorded above.
- No browser guard was run; this is non-UI tooling/comment/output work and the
  brief assigns the merged-tree guard gate to the coordinator.
- Rebased twice as local `master` moved during the gate. Both rebases were
  conflict-free. Final base at verification: `c4077866`; branch was two commits
  ahead and zero behind, and `git diff master..HEAD --check` was clean. The
  final diff contains only this report plus the five intended source files.

## DOGFOOD REPORT

The task's method was good enough to prevent the title-only false positive:
`#531` looks unrelated until its body is read, where the exact consume-bound
claim is present. That is a useful warning against automating this from titles.

Two durable surfaces outside the edit scope carry newly found propagation
problems. `watch.py:2685` repeats the `#126` example-as-authority mistake, and
the live `#658` ledger body itself says “#531 added the --through bound”; that
is supported today only because an unrelated `#531` task later acquired a note
about the commit. Neither may be fixed here: `watch.py` is occupied, and the
live ledger is read-only. The coordinator should route the first and decide
whether the second provenance anomaly deserves a separate ledger correction.

The tooling friction was the audit surface size. Graph search found 500 raw
matches and truncated; a tokenizer/AST census was required to preserve the
denominator and distinguish docstrings, comments, f-string literal text, and
one inert explanatory string. That fallback is deterministic, but it is an
audit method—not a semantic lint check.
