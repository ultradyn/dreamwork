# Lane 749 report

## Verdict

PASS. The #564 Q&A assembly-order harness now discovers `buildDashboard`'s
plain direct callees and bare `Array.map` callbacks, emits no-output sentinels
for declared neighbouring functions, and keeps the real functions (`label`,
`qSummary`, `qSection`) plus marker boundaries (`chatList`, `burnPanel`)
explicit. The decision on unclassified syntax is **fail the test**. Reporting
and continuing would let the harness silently examine less code while still
going green, the exact false-confidence shape this task forbids.

I improved the proposal in two ways. First, a discovered sentinel name must
also have a line-anchored function or const-arrow declaration in the assembled
page; this prevents an arbitrary misspelling from becoming a harmless stub.
Second, one-edit substitutions/insertions/deletions and adjacent
transpositions against the five protected names get a more specific likely-
typo error. The helper remains local because its refusal diagnostics use this
test's `self.fail`, its declaration inventory comes from this test's assembled
page, and making it a `dev/` API would widen a one-harness contract.

Commits after the first rebase onto local `master`:

- `471c636e` — `test(#749): discover dashboard harness sentinels fail-closed`
- `5ae7b6fc` — `fix(#749): refuse unclassified call syntax`
- `7f73982e` — `fix(#749): require discovered callees to be declared`

## Red-proof

Direction 1, the intended widening: I injected a new direct call to the
already-declared `activeBurnLimit()` immediately before `buildDashboard`'s
return. The harness discovered it, generated a no-output sentinel, and the
complete Q&A ordering test passed:

> `1 passed, 486 deselected in 0.44s`

That run includes all marker/precondition and relative-order assertions. An
earlier probe using `buildCurrent(d)` refused with `unknown direct callee
buildCurrent`; it is not in the assembled page's supported function/arrow
declaration inventory. This is the intended safe-side false red, and the
declared `activeBurnLimit` probe establishes the supported path.

The original assertion remains discriminating. Removing the real
`h += label('Q & A');` line failed after every other subject rendered:

> `AssertionError: '<div class="label">Q & A</div>' not found in '<div id="sections">...topic chats...class="qsec".../answers...burndown...</div>'`

Direction 2, misspelled real function: replacing the non-graded
`label('commits')` occurrence with the realistic one-edit `lable('commits')`
failed before Node evaluation:

> `AssertionError: buildDashboard dependency discovery: likely typo lable for protected label`

I also tried the two-edit `lxbal('commits')`, which is outside the similarity
diagnostic. The declaration gate still failed it:

> `AssertionError: buildDashboard dependency discovery: unknown direct callee lxbal`

Neither misspelling produced the proxy-style green run.

Direction 2, member expression: replacing `qSection(d)` with
`d.qSection(d)` failed before evaluation:

> `AssertionError: buildDashboard dependency discovery: unsupported member call qSection`

It did not disappear from discovery and did not reach a green run. The final
helper also self-checks these typo/member cases plus a tagged-template call on
every execution.

Final snapshot gate:

> `history: examined 3 commit(s) since 83d7d03c1527 (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.`
>
> `check: clean — 7 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Classifier limits

This is deliberately a narrow recognizer, not a JavaScript parser:

- It masks line/block comments and quoted strings; unterminated forms fail.
- Template text is masked. Interpolations may contain the current simple
  property/arithmetic expressions only; calls, nested braces, nested templates,
  and tagged templates fail.
- Plain identifier calls are discovered. A callee that is not a line-anchored
  function declaration or const-arrow declaration in the page fails rather
  than being stubbed.
- Bare callback identifiers passed to `.map(...)` are dependencies. The
  current single-parameter arrow callbacks are accepted and their direct calls
  are scanned normally. Other callback shapes fail.
- `.map`, `.join`, and `.slice` are the only classified member-call forms,
  with arguments constrained to the forms currently used by `buildDashboard`.
  Every other member/optional/computed/result call fails.
- Constructor calls, tagged-template calls, regex/division syntax, unbalanced
  calls, malformed bodies, zero dependencies, and zero generated sentinels all
  fail loudly. A legitimate future use of any unsupported syntax therefore
  requires reviewing and extending this recognizer; it cannot silently shrink.

The remaining semantic limit is intentional: sentinels return an empty string,
so this ordering test does not cover a neighbouring callee's behaviour. Its
marker and ordering preconditions cover only the stated Q&A assembly contract.

## Verification

- Before change, exact `python3 -m pytest test_watch.py`: **487 collected, 487
  passed in 67.99s**.
- After the first rebase, exact `python3 -m pytest test_watch.py`: **487
  collected, 487 passed in 68.82s**. A final post-report run is recorded below.
- `python3 lint.py`: `clean (6 warning(s))`; there were **NO ERRORs**. The six
  warnings are pre-existing worktree/ledger-state warnings, including the
  explicit “ledger checks examined nothing” refusal.
- No browser guards were run, as required for this non-UI lane.

## Relied-on lessons and issue lines

- #702: “Malformed task ids are KEPT and reported loudly rather than reaped as
  dead.” Applied here as fail-and-name, never silently discard.
- #671: “Zero entries now says `DID NOT REVIEW` rather than ‘nothing to
  review’.” Applied to both empty dependency and empty sentinel sets.
- #739: “the discovery rule must reject dynamic/member calls and syntax it
  cannot classify rather than guessing.” This is the direct design source.
- #707: “widening a pattern that feeds an automatic correlation makes FALSE
  ATTRIBUTION possible where before there was only silence.” This kept the
  member intrinsic inventory narrow and argument-constrained.
- #136: “present-but-unparseable is a fault and must look like one.” The
  classifier uses distinct malformed/unsupported/empty diagnostics.
- Current `lessons.md:3292` (the brief cited stale line 3280): “the header's
  claim-list is not the assertion-list: read the `ok()` calls, never the
  comment.” The helper docstring therefore states only what it recognizes and
  refuses, not a behavioural claim about generated sentinels.

## Rebase

Local `master` advanced from `7bd2c3cb` to `83d7d03c` while the lane was live,
including #751's separate `test_watch.py` class. `git rebase master` completed
without conflict. The final master check/rebase outcome and final commit sha
are appended after this report is committed.

## DOGFOOD REPORT

Two pieces of friction were found beyond the implementation. First, the brief's
`lessons.md:3280` pointer had moved to line 3292 by the time this lane rebased;
the quoted lesson was findable by text, but numeric line pointers in a heavily
appended file stale during live fan-out. Second, `python3
dev/lessons_index.py --act red-proof` returned **42 of 332 lessons** and over
500 output lines, which exceeded the tool output budget and truncated. The
act-index mechanism worked, but this slice is no longer a usable “consult at
the moment of the act” reading list without ranking or a bounded recent/core
view. The redproof snapshot/restore/check tool itself was clear and caught all
seven injections cleanly.
