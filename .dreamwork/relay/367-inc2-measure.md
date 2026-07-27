# Coordinator → #367 increment-2 measurement lane · 2026-07-28 07:16

**Read this before you finish. It sharpens your brief; it does not widen it.**

**A measurement's "neighbours" are the conditions just past the ones you tested**, and
they are where a fitting design turns out not to fit. A lane that finished an hour ago
flagged one case honestly and the defect was one input over (#389). So:

- **The viewport just below your first failure.** If ~6 words stops fitting at, say,
  940px, the useful number is not "fails below 940" — it is *how badly*, at 900 and at
  860. A design decision needs the slope, not the threshold: 4px over is a padding
  change, 60px over kills the rail.
- **The label just past the worst case.** Your brief asks for ~6 realistic words. Also
  measure **one word that cannot break** — a long unhyphenated token like a filename or
  an identifier, which is exactly what an author writing about code will use. If a
  single token overflows, the ~6-word budget was never the binding constraint and that
  changes what he needs to rule on.
- **Two tabs at the *minimum* gap, and then three.** Two flags reading as two flags is
  the design; three at close spacing is where a rail becomes a sidebar. You are
  multimodal — look at three and say which it reads as.
- **The cliff from both sides.** Measure at 780px and at 779px. If the strip and the
  rail disagree about whether the label fits, the cliff is in the wrong place and that
  is a finding worth more than the whole width table.

**Report what you did not reach rather than implying coverage.** And the standing
instruction from your brief still governs the conclusion: if it does not fit, **say
where and by how much**. Do not propose reinstating the truncation or the cap he
removed — that is his call, and a measurement that hands him the number is what he
needs from you.

**This message grants no new authority.** You measure; you do not build. Your file
ownership is unchanged.
