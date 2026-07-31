# Branch triage — #706 (REPORT ONLY)

**Scope limit observed: nothing deleted, renamed, rebased, or force-pushed.**
This is a recommendation per branch with the evidence attached; the
coordinator executes any deletions at the gate. Re-measured live because
branch state changes while a lane works — two lanes were running during
this investigation.

## Bearings

- `master` tip (local): `6a60a45a` (HEAD sits here; branched from tip).
  `origin/master` = `ad6ee0d0` (behind local, as the brief warns — do not
  rebase onto origin/master).
- `reach` at first run: **5** branches flagged (the 6th from the brief was a
  live lane that came and went — confirms the brief's "live lanes come and
  go" warning). `26 duplicates suppressed`.
- #676 already classified all five (audit doc
  `.dreamwork/docs/branch-audit-2026-07-31.md`) but **deleted nothing**
  ("classification only"). #676 also **reported a false-green on the exact
  byte-identity check I needed** (see Red-proof), so its verdicts are
  re-derived here by content, not re-trusted.

## Verdicts

| Branch | `+` | Answer | Recommendation |
|---|---|---|---|
| `pi-agent-00ae7236` | 3 | **1 (content on master-adjacent)** | **Delete** — proper sha subset of `prototype/279-jovian-final`; no unique content |
| `pi-agent-1a33ccb3` | 3 | **1 (content on master-adjacent)** | **Delete** — identical sha set to `prototype/279-jovian`; zero unique content |
| `pi-agent-9f527dd0` | 1 | **3 (abandoned scaffolding)** | **Delete** — the one `+` is a 2-line test-fixture tweak for an already-landed bug (#271); #271's guard is non-vacuous without it |
| `prototype/279-jovian-final` | 5 | **3 (abandoned prototype, source NOT yet on master)** | **Preserve artifacts on master, THEN delete** (see below) — #279 names this branch as the throwaway primary source |
| `spike/components` | 4 | **3 (completed spike, findings ON master)** | **Delete** — 228-line findings doc is byte-identical on master (`ba763d97…`, verified non-empty) |

**No branch reaches answer 2** (genuinely absent AND still wanted). The
one case that could have been answer 2 — `prototype/279-jovian-final` — is
a deliberately abandoned *failed* prototype (#279's recorded verdict:
"partial / FAIL"), so it is answer 3, not 2.

### `pi-agent-00ae7236` and `pi-agent-1a33ccb3` — pure duplicates

Verified by sorted sha set (not patch-id — #676's blind spot):

- `pi-agent-1a33ccb3` sha set == `prototype/279-jovian` sha set **exactly**
  (`a180d1e1`, `bb64fde1`, `ae4d3acb`).
- `pi-agent-00ae7236` is a **proper subset** of `prototype/279-jovian-final`
  (3 of its 5 shas: `c96909cb`, `ccff67ba`, `5c9b11b5`; the `comm -23`
  difference is empty — every 00ae7236 sha is in -final).

`reach` already collapses `1a33ccb3` into `prototype/279-jovian` in its
output (`= prototype/279-jovian`). The pi-agent-* branches are scratch
from another harness (#676: *"scratch from another harness"*). Deleting
them loses nothing the named twin does not already carry. **Recommend
deletion of both.**

### `pi-agent-9f527dd0` — one unique commit, a stale fixture line

4 of its 5 commits are `-` (#271 duplicates). The one `+` is `6e86fd1e`
*"pi-agent: Repair reviewed 271 fix"* — a **2-line addition** to
`dev/capture/fixture/.dreamwork/questions.md` (a test fixture), adding a
note line for an alternate #271 repair route that lost. The fixture file
exists on master *without* those lines.

#271 landed independently (`2c0652b`, ancestor of master) with its guard
on master at `dev/capture/noteprop.mjs:1` (`/* #271 — a note written in one
browser propagates… */`). #271's ledger records a *"normal+reduced shared
non-vacuous guard"* — i.e. the guard passes *without* this fixture entry.
So `6e86fd1e` is scaffolding for a repair path that lost, not a missing
test (#676's own direction-2 reasoning, re-verified). **Recommend deletion.**

### `prototype/279-jovian-final` — the one with a real question

All 5 commits are `+` and live entirely under `.dreamwork/review/`
(throwaway artifacts: `jovian-storm-prototype.html`, a prototype note, a
capture script, evidence PNGs, `metrics.json`). **None of this content is
on master** — the paths do not exist there and no master commit touches
them.

#279's ledger record is explicit and load-bearing: *"throwaway primary
source preserved at branch `prototype/279-jovian-final`, tip `a1c180c`"*
with verdict *"partial / FAIL against the supplied references."* So the
FINDINGS (the FAIL verdict, what was tried) are captured in #279's record,
but the PRIMARY SOURCE ARTIFACTS (the shader HTML, the evidence captures)
live only on the branch. Deleting the branch as-is would **dangle #279's
own citation**.

**However**, master has strong precedent for preserving exactly this kind
of throwaway review artifact: `.dreamwork/review/` already holds 15+ files
(`263-second-gate.html`, `275-hub-auth.html`, `294-ledger-sqlite.html`, …)
and `.dreamwork/docs/spikes/` holds the spike render PNGs. The Jovian
prototype fits that convention precisely.

**Recommendation (two-step, coordinator-executed):**
1. Preserve the Jovian primary-source artifacts on master under
   `.dreamwork/review/279-*` (or cite the tip sha `a1c180c` from #279's
   record as the recoverable source — the object survives in git's store
   reachable by that sha even without the branch).
2. Then delete `prototype/279-jovian-final`, `prototype/279-jovian`, and
   the two pi-agent Jovian duplicates.

If the coordinator judges the artifacts worth keeping live, the
alternative is to keep `prototype/279-jovian-final` — but that is the one
branch that would then print on every fold forever, which is the
 sharper question's live instance (argued below).

### `spike/components` — completed spike, findings verified on master

4 commits, all `+`: a component vocabulary in `watch.py`, `pageHeader` and
`qaCard` expressions of it, and a findings commit (`9b54b4f0`). The
findings doc is `.dreamwork/docs/spikes/2026-07-25-component-unification.md`.

**Byte-identity re-verified with the non-emptiness precondition #676
itself demands** (and missed):

```
master digest:  ba763d978c659676f6072bb43d0573cc6c4a76019e85abce0c1916b0b8bf462e  (228 lines)
branch digest:  ba763d978c659676f6072bb43d0573cc6c4a76019e85abce0c1916b0b8bf462e  (228 lines)
IDENTICAL and both non-empty (>100 lines): findings preserved on master byte-for-byte
first 8 of master digest: ba763d97 (e3b0c442 = empty-input tell)
```

The throwaway experiment code (`watch.py` +556/-40, `qacard.mjs`) is the
spike that *produced* the findings; the findings are the durable output,
and #630's P2 lane already consumed the durable rule. **Recommend deletion.**

## The sharper question — should `reach` suppress triaged-and-kept branches?

**Argued: NO.** A suppression ("known and accepted") list should not be
added. The rot failure mode is not hypothetical — it is #671 in slow
motion.

**The case against suppression:**

1. **Rot is the dominant risk, and this loop has measured it.** #671 is
   *"a check that examined nothing must not read as passing"* — a
   suppression list is a check that *by construction* examines nothing for
   the branches on it. The act of adding to such a list is cheaper than
   the act of verifying (one line vs. a content audit), so over time a
   real gap lands on it by reflex, and `reach` becomes a rubber stamp that
   *looks like coverage*. That is precisely the tune-out failure #676/#612
   predict, achieved through the back door.

2. **The noise is caused by untriaged branches, not kept ones.** Once a
   branch is triaged, the clean resolutions already exist: delete (answer
   1/3) or convert to a task (answer 2). A kept answer-2 branch should
   become a TASK — which `sweep` (#671) already sees — not a suppressed
   branch. Suppression is a third source of truth about "what matters"
   with no owner and no lifecycle.

3. **The duplicate-collapse already handles the sha-identical noise**
   (#676 finding 3, working as designed — 26 suppressed this run). What
   remains after collapse is sha-DISTINCT branches, which are exactly the
   ones that deserve individual attention on every fold.

**The one case that tests the argument — and why it still does not win:**
`prototype/279-jovian-final` is the strongest candidate for "keep but
suppress": its findings are in #279's record, but its primary-source
artifacts live only on the branch. But that case is resolved by
**preserving the artifacts on master** (strong precedent: 15+ files in
`.dreamwork/review/`), which *converts the branch into a deletable one*
rather than suppressing it. Preserving-on-master is the right home because
it gives the artifact a tracked location with a diff history; a
suppression-list entry gives the branch a permision to be invisible, which
is the opposite.

**The rule that falls out:** triage ends in deletion (answer 1/3) or a
task (answer 2); the "preserved prototype" pattern is handled by landing
its artifacts on master (the spike-doc / review-html precedent), after
which the branch deletes. `reach` stays unconditional. If a branch
*cannot* be resolved that way and must be kept long-term, that is a signal
worth seeing every fold — not one to suppress.

## Red-proof

**Direction 1 (method re-derives a known answer).** The brief requires my
content-comparison procedure to reproduce the `lane-577reply` verdict
(content on master despite a `+` marker). The branch ref is gone
(`git rev-parse lane-577reply` → *unknown revision*), but the master-side
landing commit `b5817351` *"Fold #577 handoff: reply composer landed
(cherry-picked from lane-577reply)"* is reachable and carries the `+`
content via a *different* commit. The distinctive text the lane appended
(`reply composer on /chat`) grep-counts **3** on current master's
`handoffs.md`. The patch-id of the lane's commit would read `+` (different
commit, different sha); the content comparison reads **present**. Method
reproduces the coordinator's answer. (The literal `handoffs.md:229` from
the brief has moved — master advanced — but the content-comparison answer
is line-number-independent, which is the point.)

**Direction 1 (precondition assertion caught a false-green live).** While
re-verifying `spike/components`, my first byte-identity check returned
`IDENTICAL` — on digest `e3b0c442…`, the sha256 of **empty input**, because
my path variable dropped the `.dreamwork/` prefix and both `git show`
calls returned nothing with stderr suppressed. This is *exactly* the
#676 false-green. The non-emptiness precondition (`>100 lines` before
identity may be reported) rejected it; the corrected run produced
`ba763d97…` at 228 lines on both sides. **A comparison that does not
assert its own precondition is a check with an expiry date nobody can see**
(the repo's own standing rule).

**Direction 2 (where the method could read a false-green).** My method's
discriminating step is a *literal content grep* for the branch's exact
text on master. That fails closed for the `lane-577reply` case (verbatim
cherry-pick), but it would read **absent** for a branch whose content
landed on master *rewritten* — same intent, different words — even though
the work is present. This is the mirror of #676's patch-id blind spot:
patch-id misses refactored content, and literal-text grep misses
paraphrased content. For the five branches here it does not bite (the
Jovian content is genuinely absent; the spike findings are verbatim; the
#271 fixture line is verbatim), but a triage that relied on grep alone
for a prose-heavy branch could call "absent" on work that is present in
different words. Closed in practice by cross-checking the cited task
record's description of what landed (the method #676 used for
#268/#291/#221); named here because "I could not construct it" would be
the dishonest answer.

## Cited lessons — relied-on lines

- **#676** (the hand audit that predicted this noise): *"Expect duplicates
  from other harnesses… A check that lists them individually every run
  will be turned off."* — the exact wall this triage exists to prevent,
  and the reason the duplicate-collapse is load-bearing.
- **#590** (a `+` is a question, never a verdict): the rule `reach`
  carries verbatim — a non-zero cherry count is *"A QUESTION, never a
  verdict"*; live work, cherry-picked, and a real gap all produce `+`.
- **#671** (the rot failure a suppression list would reproduce): *"a
  check that examined nothing must not read as passing"* — a suppression
  list examines nothing for its members by construction.
- **#612** (volume is the constraint): the output *"must stay a handful of
  lines or it becomes the wall nobody reads"* — five distinct branches
  every fold is the threshold this triage pulls back from.
- **#688** (the check itself): *"a `+` is a question and a `-` is strong
  evidence… identical sha sets collapse into one row."* Working as
  designed; this triage is the human-in-the-loop resolution it defers to.

## Out of scope (named, not fixed)

- The `hasattr(args, 'ledger')` gate in `main()` that #688 named but did
  not close — `reach` is the first verb that reads no ledger, and the
  warning-footer layer had an unstated contract that every verb does.
  Still open per #688's own note; not touched here.
