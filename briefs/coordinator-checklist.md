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
  Remove contradictions within the task-specific head — **and between the head
  and the boilerplate it is composed with.** The head is read as an addition to
  the standing rules, not as a replacement for them, so a head that restates a
  rule differently is a contradiction the lane must resolve on its own. `#1171`
  round 2 reported this: the head cited
  `/home/xertrov/.claude-p/skills/ud-dreamwork/igc-method.md` while
  `boilerplate.md:315` says to use the worktree-local `./igc-method.md` and not
  to read under `~/.claude-p/`. The two copies happened to be byte-identical, so
  nothing was decided wrongly — but the lane had to establish that itself before
  it could proceed. **When the head needs to point at a resource the boilerplate
  already governs, cite it the boilerplate's way.**
- State a conditional deliverable conditionally at its first imperative.
- Derive scope and verification lists from the moved symbol's callers and
  caller fallout, not from expected diff ownership.
- Present observations as measurements, with the command or method that
  produced them. Never instruct a lane not to re-derive a measurement. Mark an
  unreproduced premise as unverified and make non-reproduction a valid result.
- **Before asserting that a file contains something, or that a tool behaves a
  certain way, OPEN IT.** On 2026-08-04 three briefs shipped in one day with a
  premise I had not measured: `#1177` said `reap.py` asks sha identity when it
  has called `git cherry` since `db6078e8`; `#1170` said `briefs/boilerplate.md`
  carries a bare `cat >> …inbox.md` recipe when it carries none; `#1175` round 3
  cited `#1153`'s identity split for a pair it does not describe (the redproof
  launch token vs its hashed registry directory — not a status entry's lane name
  vs the probe's, which do match). Every one was caught by a lane's premise-stop,
  each costing a dispatch. A one-line `grep` or `--check` run would have caught
  all three in seconds. **The tell is a sentence about the codebase written from
  memory rather than from a command** — those are the sentences to verify, and
  the cheapest moment is while composing, not after a lane stops.
- Keep the "if a premise here is false, STOP and report" clause in every brief,
  and scope it per-deliverable. It is what turns the mistake above from a wasted
  round into a ten-minute correction, and it is the single highest-value
  paragraph in the boilerplate. Where a stop was correct, **say so plainly in
  the next round's brief and name the error as yours** — a lane that is told its
  refusal was right refuses again when it should.
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
