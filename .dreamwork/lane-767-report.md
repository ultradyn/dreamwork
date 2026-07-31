# Lane 767 report

Defining “resolved” as either a legacy arrow resolution head or a dated human
`Answer`/`Comment` record makes semantically empty, misattributed, or wrong-target
answer records invisible; this check verifies that resolution evidence was
recorded, not that the response actually resolves the ask.

## Verdict and definition

FIXED. A recorded resolution is now one of:

- the legacy, line-anchored `→ answered (…)` / `→ resolved (…)` head;
- a dated human follow parsed from an `Answer (via watch, …)` record; or
- a dated `Comment (via watch, …)` record.

`Folded (…)` alone is explicitly not a resolution: it proves coordinator
processing, not a human response. A dated record with any other marker is
reported as unclassifiable instead of guessed. A marker-free entry remains the
existing “no recorded human response” warning, because it may be withdrawn or
may have dropped its evidence.

## Measurement and reconciliation decision

I copied the live `questions.md` to the lane-private measurement directory on
measured `btrfs` and classified it through `watch.parse_answered`:

    total=67 legacy=64 newer_only=3 neither=0

The three newer-only entries are exactly `#572`, `#614`, and `#613`. All three
have dated parser-captured human follows; `#614` and `#613` also have dated
`Comment` records; all three have `Folded` records.

I did not reconcile the file. Rewriting 64/67 legacy, human-authored entries to
the three-entry vocabulary (or rewriting the three newer records backwards)
would alter history without improving the classifier. Tolerating the bounded
split costs two explicit recognition arms plus tests; unknown future arms remain
loud. That is acceptable compared with the `#440` cost of making a history
rewrite travel through the supported fold path and then defending the rewritten
record.

## Change

- `lint.py`: classify recognized human response evidence, `Folded`-only
  processing, unknown dated markers, and missing evidence separately.
- `test_lint.py`: bind both live vocabularies, `Folded`-only refusal, an unknown
  future marker, and fixture non-vacuity.
- No edit was made to live or worktree `.dreamwork/questions.md`.

## Live lint before and after

Before, the answered-entry line was verbatim:

    WARN  questions.md      3 of 67 answered entries have no resolution date — a withdrawn ask carries none by design, but a dropped `→ answered (…)` marker is a regression that otherwise hides: P2 · 2026-07-31 01:50 — #572: GitHub etiquette —; P1 · 2026-07-31 17:20 — #614 (blocks #641): webs; P1 · 2026-07-31 17:20 — #613 (blocks #631): the  (#411)

After, there is no answered-entry WARN line because all 67 classify. The
questions summary line is verbatim:

    OK    questions.md      5 open, 67 answered

The worktree result moved from `clean (6 warning(s))` to
`clean (5 warning(s))`; the three false names disappeared. The remaining five
are the worktree-relative ledger/status/lesson warnings documented by the lane
bar. The brief's literal “lane bar is 6 warnings” is therefore the pre-fix bar,
not the post-fix bar.

## Red-proof

### Direction 1 — restore the real defect

I ran `python3 dev/lessons_index.py --act red-proof`, then
`python3 dev/redproof.py begin lint.py`. I sabotaged the classification back to
legacy-only (`if watch.answered_at(body) is not None:`). The live check again
reported three findings and named `#572`, `#614`, and `#613`.

The binding test failed on the discriminating assertion, not merely the count:

    AssertionError: assert ['1 of 2 answ...ent`] (#767)'] == []
    Left contains 2 more items, first extra item: '1 of 2 answered entries have no recorded human response — a withdrawn ask carries none by design, but a dropped resolution marker is a regression that otherwise hides: Answered? (#411)'

`dev/redproof.py restore lint.py` restored and verified the snapshot. Final
handoff gate:

    check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits

This catches regression of the recognition path itself.

### Direction 2 — cases that widening must not eat

Constructed `Folded`-only answered entry, no answer from him:

    WARN questions.md 1 of 1 answered entries carry `Folded` but no recorded human response — `Folded` records processing, not a resolution: FOLDED_ONLY [`Folded`] (#767)

Constructed third format that does not exist yet:

    WARN questions.md 1 of 1 answered entries have a dated but unclassifiable resolution record — report the unknown marker instead of guessing: FUTURE_FORMAT [`Verdict`] (#767)

The two states do not render identically: the first says processing occurred
without response evidence; the second says the vocabulary could not be
classified.

Open false-green, deliberately named: this structurally valid record passes:

    - **Answer (via watch, 2026-07-31 19:16):** I saw this, but did not answer it.
    SEMANTIC_FALSE_GREEN: []

Closing that would require judging semantic adequacy or attribution, which a
regex/parser lint cannot do reliably. This is exactly what the lead sentence
says the definition makes invisible.

## Verification

- `just pytest test_lint.py::TestAnsweredResolutionDates` — `7 passed`.
- `just pytest test_lint.py` — post-rebase: `546 passed in 84.19s`.
- `python3 lint.py` — no errors, five worktree-relative warnings, answered-entry
  false warning absent.
- `python3 dev/redproof.py check` — clean; one injection restored and absent
  from commits.
- Base verification: the dispatched branch point was
  `9c62f384c5dcee7855efb3e7c19d1c78b43b2dae`. Local `master` advanced twice
  during final gates, reaching eight commits beyond the branch point at
  `d2f2f054839dc3fe2242b5dc6182681eaf819b01`; the lane rebased cleanly after
  each movement. Final post-rebase code head before this report: `aefe781d`.

## Relied-on ledger evidence

- `#767`: “The fix is not ‘ADD MORE PATTERNS’ … `Folded (…)` asserts that the
  coordinator processed the entry, which is not the same claim.”
- `#755`: its landed note records the failure mode directly: “the check fires
  two warnings on the healthy live file … Both are #707 false attribution.”
- `#707`: “widening a pattern that feeds an automatic correlation makes FALSE
  ATTRIBUTION possible where before there was only silence.”
- `#702`: its landing kept malformed ids and “reported loudly rather than
  reaped as dead”; that is the precedent for retaining unknown resolution
  vocabulary as a finding.
- `#136`: “THREE zero-states, not one … present-but-unparseable is a fault and
  must look like one”; genuinely empty is the distinct calm state.
- `#671`: the broken check had a real count while “the ‘nothing to review’ is
  false, and the two together read as a positive all-clear.”
- `#440`: “a single supported way to fold an entry” with anchored before/after
  assertions exists; that makes reconciliation possible, not worthwhile.
- `#761`: measurement found “the real defect” was a regex anchor that named
  injections but omitted the vocabulary of a hollow check; this is the sibling
  regex-lag case the brief pointed to.
- `#411`: “the silence is the actual defect” and the lint count must name
  unparseable resolution dates while distinguishing legitimate withdrawals.

## DOGFOOD REPORT

Two brief defects cost time:

1. The head calls six warnings the lane bar while also requiring the false
   warning to disappear and the count to move. Both cannot remain true after a
   correct fix; measured output is five warnings. Calling six the **pre-fix**
   bar would remove the contradiction.
2. The head prescribes manual `cp`/`cmp` restoration, while the standing
   boilerplate says `dev/redproof.py` owns snapshot/restore and explicitly
   requires its handoff check. The task-specific sentence does not declare an
   override, so I followed the standing contract. The brief should name
   `dev/redproof.py` too; two approved restoration protocols in one dispatch
   force a needless authority decision.

No out-of-scope code defect was found in the sibling marker-placement checks:
they police malformed placement of the legacy marker and do not claim that a
new-format response is unresolved.
