# Brief — #509: a phantom `question-updated` event for the answered #229 entry fires on EVERY questions.md rewrite

Lane-owns: `watch.py` (the question-signature/diff logic only — the smallest possible diff), `test_watch.py`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The defect (four witnesses, reproducible on demand)

Every time `questions.md` is rewritten, the server emits a spurious
`question-updated via watch: P1 · 2026-07-26 — #229 threaded topic chats: …`
line to `watch-events.log` — for the **answered** #229 entry, which has not
changed. Witnesses: 2026-07-29 ~23:4x, 2026-07-30 04:5x, 06:3x, and
2026-07-30 07:06 (immediately after the coordinator appended the #505 Open
entry). The wake channel is load-bearing (every line wakes the loop), so a
phantom event is a phantom wake AND a false signal that a human acted —
under batched delivery it also pollutes the event classification the
coordinator reasons about (#514 audits wake semantics in parallel; your
scopes do not overlap — you fix ONE emitter, it surveys ALL of them; do not
touch anything beyond the #229 phantom's mechanism).

The likely home is the question-signature diff: watch.py keeps per-question
signatures (`.dreamwork/question-sigs.json`, gitignored) and emits
`question-updated` when a signature changes between builds. The #229 entry
is the longest, weirdest entry in the file (nested tables, code fences,
~100 lines) — a prime suspect for a signature that is unstable across
identical content (truncation? a non-deterministic normalisation? a hash
input that includes derived/live data like an age string? a sig stored
under a key the rewrite re-derives differently?). **Investigate before
fixing: name the exact input that differs between two builds of unchanged
content.**

## Acceptance criteria

1. Root cause named with evidence: the two differing signature inputs (or
   the mechanism) captured, not hypothesised.
2. After the fix: two consecutive `questions.md` rewrites that do NOT touch
   the #229 entry emit **zero** `question-updated` events for it (test this
   at the unit level — the signature/diff function over realistic fixture
   content derived from the REAL #229 entry, not a hand-waved mini-entry:
   the fixture must carry the features that make #229 the trigger, and the
   test must assert that precondition — a fixture without them is the
   born-hollow shape).
3. A REAL update to a question entry still emits exactly one
   `question-updated` line (the channel keeps its teeth — prove with a
   fixture where an entry genuinely changes).
4. `python3 -m pytest -q test_watch.py` green; `python3 lint.py` clean.

**Red-proof every new check**: name the production line, sabotage it, watch
the test fail, restore byte-identical with `cp`. A green red-run is a
finding, never a relief. If your fixture hand-builds the signature instead
of calling the production function that computes it, you have built the
class of test that cannot fail — don't.

## Constraints

- Branch `lane-509sig` off master; `git commit --only <paths>`.
- **watch.py is a big shared file — the smallest possible diff.** You own
  the signature/diff logic and nothing else. Do not reformat, do not
  "improve" neighbouring code, do not touch the UI constants (STYLE/JS).
- Do NOT edit `.dreamwork/questions.md` or `question-sigs.json` (both are
  live state; the sigs file is machine-local and gitignored — tests build
  their own fixtures in tmp).
- A lane never runs `just test` or the guard suite. Targeted pytest +
  `python3 lint.py` only.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only;
  never rewrite; the literal path is `.dreamwork/handoffs.md`) and COMMIT it
  among your paths.

## Report back

The root cause (one paragraph with the captured evidence), the fix (diff
summary), the tests added with their red-proofs (production line named per
test, what failed, restore evidence), the pytest summary line, and whether
the same instability class could affect OTHER long entries (one line — if
yes, say which feature of the entry drives it).
