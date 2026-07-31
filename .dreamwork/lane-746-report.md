# Lane #746 report — blocked-on title heuristic

## Verdict

Chose **(b): lower the claim to an intentionally noisy phrase heuristic**. The
regex remains `\bblocked on\b`; the docstring, warning, coverage row, and tests
now say exactly what it does and require a human to interpret the row.

The small IGC decision was:

| Idea | All | Preserve genuine stale warning | Describe observed behaviour truthfully | Evidence-proportionate scope |
|---|:---:|:---:|:---:|:---:|
| (a) English exceptions | ✘ | ✔ | ✘ | ✘ |
| (b) Honest phrase heuristic | ✔ | ✔ | ✔ | ✔ |

The decisive errors for (a): exceptions still cannot decide whether the phrase
is a present-tense self-claim, and the live population contains no negated form
to justify machinery. Option (b) preserves the useful signal and makes its
interpretive limit explicit.

## Measurement

The initial ledger read reported **177 open tasks**. A direct read-only scan of
the live store later in the lane saw **178 open records** (the ledger moved while
the lane ran). In that later snapshot:

- plain `\bblocked on\b`: **0**
- obvious negation (`not`, `never`, or `no longer` before `blocked on`): **0**
- quoted/code-span occurrences: **0**

Zero is a measured absence, not proof that these forms cannot occur. This is
why no negation carve-out was added.

## Changes

- `lint.py`: warning now says it is an “intentionally noisy phrase heuristic,”
  names negation/quotation/metacommentary as forms it cannot distinguish, and
  says a human must review before retitling or setting `blocked_on`.
- `test_lint.py`: added the three required cases — `not blocked on #614
  anymore`, `Explain why jobs are blocked on CI`, and ``Document the `blocked
  on` title lint`` — and pins their id, exact fragment, heuristic wording, and
  human-review wording.
- Corrected Direction 2's fixture from nonexistent blocker `#999` to the
  fixture's actually landed `#11`, with a read-only SQL precondition asserting
  `#11` is landed before asserting the check stays quiet.

Code/test commit after the final rebase onto local `master`: `7f80dfdd`.

## Red-proof

### Direction 1 — wording and behaviour cannot drift back into a grammar claim

`python3 dev/redproof.py begin lint.py` snapshotted the **fixed** file. I then
injected the old overclaim into the warning and ran the single discriminating
test. It failed with:

> `AssertionError: a title claiming 'blocked on' with no structured field must WARN, naming the id and fragment while admitting human review`

The emitted row still named `#1` and quoted `blocked on his ruling`, but lacked
`intentionally noisy phrase heuristic` and `a human must review the row`; the
failure was therefore on the intended contract rather than a count.

After restore, the required gate said:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

After the rebase it additionally reported:

> `history: examined 2 commit(s) since 82252c35dd55 (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.`

### Direction 2 — misleading ledger that still passes

Constructed an open title containing `blocked on`, populated its `blocked_on`
with `#11`, asserted from the store that `#11` is actually `landed`, and observed
no warning. This is a genuine false-green: the title and field agree with each
other while both are stale relative to the blocker's state.

**It should be filed as a focused follow-up.** The read-only search found no
open task whose title names a recurring stale-`blocked_on`/landed-blocker check.
#590 performed the valuable one-time audit, but a one-time re-rank does not
prevent recurrence. The follow-up should correlate non-empty numeric
`blocked_on` values with live blocker state; it should not widen this title
phrase heuristic.

## Verification

- Before: `python3 -m pytest test_lint.py` collected **534** tests and passed.
- Final post-rebase run: `python3 -m pytest test_lint.py` — **535 passed in
  77.31s**.
- After rebase: `python3 -m pytest test_lint.py::TestTitleBlockedClaim -q` —
  **13 passed in 1.10s**.
- `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` —
  **clean (2 warning(s))**, with no ERRORs. The two existing warnings were the
  unanswered-date row and the near-duplicate-lessons row.
- `git diff master...HEAD --check` — clean.

## Relied-on issue lines

- #746: “Two acceptable fixes and I do not want both (#440).”
- #707: “A non-zero count is a question, not a verdict (#590).”
- #725: “Direction 2 named and PINNED with a test that asserts the silence: a
  title claiming blocked-ness where blocked_on is non-empty but names an
  already-LANDED blocker passes quietly.”
- #590: “the state-audit found blocked_on stale for at least
  #276/#249/#368/#373/#254 (their named blockers already landed).”
- #731: “A title that still trips #725 is allowed, because the writer must not
  duplicate lint policy (#440) — which is what lets #746 be fixed in one place.”

## Rebase outcome

Local `master` first advanced by 13 commits, then by another 4 while the report
was being written. Both rebases completed without conflicts; the final base is
`82252c35dd5552e96aa2fd92bb6b0ccb435f18c7`, and the final post-rebase code/test
commit is `7f80dfdd`.

## DOGFOOD REPORT

Two concrete frictions:

1. The brief correctly distinguishes the interpreter path from its subject,
   but `lint.py` defaults `--target` to the current working directory. Running
   the main-checkout interpreter from this worktree therefore still linted the
   worktree and produced the expected “ledger absent” refusal. The reliable
   live-store form for a lane is the worktree-relative interpreter plus an
   explicit target: `python3 lint.py --target
   /home/xertrov/.llm-general/skills/ud-dreamwork`. Stating that exact form in
   future lint-editing briefs would avoid a false “live baseline” read.
2. #725's Direction 2 test claimed an already-landed blocker but used `#999`,
   which did not exist in its fixture. The silence was real, but its stated
   precondition was not. Requiring the fixture to read back `state=landed`
   turned the intended false-green into actual evidence.

No files outside `lint.py`, `test_lint.py`, and this report were changed. No
ledger mutation, browser guard, merge, push, or `attn` call was performed.
