# Coordinator brief checklist

Use this before `just dispatch-lane`. The wrapper mechanically proves only the
base-state item; the remaining checks require coordinator judgement. They are a
checklist rather than semantic lint because wording proxies have already named
healthy briefs and cannot reliably distinguish instructions from evidence.

- Give the lane one `Base sha: <git revision>` line. Obtain it with
  `git merge-base master <branch>` at dispatch; never substitute a commit
  distance. The wrapper resolves the revision and refuses it unless it is the
  branch point of local `master` and the named branch.
- Name every standing-rule override explicitly and name the rule it replaces.
  Remove contradictions within the task-specific head.
- State a conditional deliverable conditionally at its first imperative.
- Derive scope and verification lists from the moved symbol's callers and
  caller fallout, not from expected diff ownership.
- Present observations as measurements, with the command or method that
  produced them. Never instruct a lane not to re-derive a measurement. Mark an
  unreproduced premise as unverified and make non-reproduction a valid result.
- Put the measurement instrument beside every numeric bar so a reader can
  audit how the number was obtained.

## Mechanism decision (IGC)

Context: persisted briefs exist from task 766 onward; the governed corpus has
one known bootstrap exception, while semantic wording proxies have produced
false attribution.

| Idea | All | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|
| Checklist only | ✘ | ✘ | ✔ | ✔ |
| Dispatch base gate only | ✘ | ✔ | ✔ | ✘ |
| Semantic dispatch lint | ✘ | ✔ | ✘ | ✘ |
| Base gate plus checklist | ✔ | ✔ | ✔ | ✔ |

- **G1:** a missing, unresolvable, or wrong base is refused before runner exec.
- **G2:** healthy governed briefs are not refused by wording proxies.
- **G3:** judgement failures have an honest coordinator-facing home.

The checklist-only idea cannot prevent dispatch. A base-only gate leaves the
other brief species structural only in memory. Semantic lint is refuted because
text shape cannot establish contradiction, scope completeness, or world truth.
