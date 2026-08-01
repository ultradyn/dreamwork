# 2026-08-02 #934 — the hollow discriminator I wrote against my own test, and the two readings of "followable"

## The thing that surprised me

The brief warned me, in its "Direction-2 candidates" section, about tests that
derive their expected value from the same code that produces it (#852/#905/#909).
I read that warning carefully. Then I wrote a docstring test that asserted
`"redproof" in doc and "snap" in doc` — and **both tokens already appeared in the
pre-fix docstring** (line 30 names `redproof.py begin` for an unrelated reason;
the usage block shows `snap`). My first red-run on the *reverted* code came back
green for the docstring tests. The test agreed with the tool regardless of whether
the fix was in place — exactly the #852 shape, applied to my own discriminator.

The tell was that I ran direction 1 *immediately* after writing the tests, rather
than after I had convinced myself they were right by reading. The green-on-
sabotaged result was the finding. I rewrote the docstring test to key on `#934`
(the hazard's stable identity reference, absent from the pre-fix docstring), and
the discriminator became real.

The transferable half: **a test that checks whether a thing is *present* is only
a discriminator if the thing was *absent* before the fix.** Tokens that appear
incidentally (`redproof`, `snap` both have legitimate unrelated mentions) do not
discriminate. The cheap check is the one I should have run before committing the
test: grep the pre-fix artifact for the discriminator token. If it's already
there, the test is hollow.

## Two readings of "followable"

The brief's acceptance test is: *"an agent following the written procedure
verbatim must land on the right path without having to notice a discrepancy."*
There are two readings, and they set different bars:

1. **Mechanical followability.** The procedure names a tool, the tool prints a
   path, the agent uses that path. This is testable: begin prints a path, the
   path holds the original bytes. I wrote that test (the behavioural net).

2. **Cognitive followability.** An agent *reads* the procedure, forms an
   expectation, and that expectation matches what the tool does. This is NOT
   testable mechanically — it is a property of an agent's internal state. The
   best a code change can do is **state the distinction at the point of action**
   (begin's output line) so the agent does not have to *hold* the discrepancy in
   memory across two tool invocations.

My fix addresses (1) directly and (2) by making the discrepancy **stated rather
than discovered**. The irreducible residual (an agent misreads a well-formed
output) is not machine-checkable, and I said so honestly in the direction-2
section rather than claiming a false-green I did not construct. This is the
brief's explicit allowance for a presentation fix: *"state honestly how you
tested that, or that you could not."*

The deeper fix — rewriting the procedure text in `briefs/boilerplate.md` so it
stops naming one tool as though it were the whole workflow — is option 2 in the
brief, and it is coordinator-owned. I flagged it rather than fixing it, because
the tool-side fix reaches every dispatch (including ones with hand-retyped
boilerplate) and because editing the canonical standing contract is the #936
disease if a lane does it. The coordinator may land it alongside.

## Why I did not unify the roots

`redproof.py _snapshot_path` is `sha1(posix_path).hexdigest() + ".orig"` —
content-addressed by the target path. `lane_scratch.py snap` is a general subdir
with lane-chosen names. Unifying would mean either (a) redproof stops content-
addressing (breaking `check`/`restore`/`forget`'s deterministic lookup and the
concurrent-injection safety the docstring at redproof.py:318–322 documents), or
(b) lane_scratch adopts content-addressing (breaking its general-scratch
contract, where a lane picks the name). Both are worse than the friction. The
split exists for a reason, and the reason is load-bearing. The fix is to make
the split *stated*, not to remove it.
