# Audit #703 — SKILL.md lane rules vs `briefs/boilerplate.md`

Reconciliation of the lane-facing rules in `SKILL.md` against
`briefs/boilerplate.md`. Premise (`#400`, relied-on line):

> **The lessons that reach a lane are the ones I hand-copy into its brief**, and
> nothing else does.

The same transmission path holds for `SKILL.md`'s lane rules: a rule stranded
in the coordinator's doc never reaches a lane. The known instance (`#652`,
lane-private snapshot) was already landed in the boilerplate; this audit
measures whether any others remain.

## How I drew the lane / coordinator split

- **LANE** = a dispatched dreamer/utility subagent doing one increment
  (usually in a worktree). It reads its brief (task head + boilerplate) and
  acts once.
- **COORDINATOR** = the main dreamer running the loop: dispatching, writing
  briefs, merging, owning the ledger and `handoffs.md`.

**Rule of separation:** a rule is *lane-facing* if it constrains an action the
lane itself performs inside its own task — committing, rebasing, reporting,
red-proofing, verifying — or forbids one (push, merge, `attn`, `just test`,
stopping loop machinery). It is *coordinator-facing* if it constrains
dispatch, fleet management, merge, the ledger, or brief-**writing**. Several
rules have **both halves** (e.g. rebase: the coordinator states the base sha,
the lane rebases); I extract the lane half and note the coordinator half only
for context, never counting it as a lane gap. Anything genuinely ambiguous
goes in List 4 rather than being forced.

I verified presence/absence by `grep` (not by memory) for every claim below;
each is anchored to a line range.

## List 1 — present in both (transmission works)

| Lane rule (SKILL.md) | Boilerplate |
|---|---|
| `git commit --only <paths>`; `git add -N` for new files (366-382) | 100-101 |
| Never `git commit -a`; never merge; never push (366-382, 884-886) | 100-102 |
| Lane rebases onto base **before** reporting; rebase FIRST, report sha SECOND (422-470) | 38-44 |
| Append-only conflicts → keep-both; grep diff3 markers **line-anchored** with the load-bearing `$` (445-460) | 46-52 |
| If the rebase is genuinely hard, hand back the analysis (466-470) | 52-54 |
| Lane never runs `just test`/the full guard suite; targeted pytest + `lint.py` + own guard solo (488-498) | 122-138 |
| Red-proof both directions; restore by `cp` outside the repo; never `git checkout` (542-562, 916-918) | 56-60 |
| Lane-**private** snapshot dir via `dev/lane_scratch.py` (`#652`) (542-562) | 62-72 |
| A guard/test named as evidence names the assertion that would fail (534-536) | 78-82 |
| Subagents report **through a file**; never use `attn` (588-590, 988-990) | 84, 116-118 |
| Lane does **not** write `handoffs.md`; writes the inbox report only; coordinator writes the hand-off (500-504, 622-648) | 24-32 |
| Issue citations opened + read, relied-on line quoted; the `--ledger` form from a worktree (506-524) | 84-90 |
| A new check is not verification until it has been red (916-918) | 56-72 |
| Choosing between rivals → IGC (`./igc-method.md` in your own worktree) (330, 924-940) | 96-98 |
| Lane re-checks its base before finishing; sha not a commit count (438-440, 526-532) | 16-22 |

The two headline failures this task exists for — `#652` (lane-private
snapshot) and `#687` (who writes `handoffs.md`) — are both **reconciled**:
each rule now reads the same way in both files. `#687`'s old contradiction is
gone; SKILL.md (500-504, 628-630) and the boilerplate (24-32) agree that the
lane writes the inbox report and the coordinator writes the hand-off.

## List 2 — in SKILL.md, missing from the boilerplate

For each, the verdict is **boilerplate / task head / nowhere**, with a reason.

1. **Subagents never stop or pause loop machinery; if it believes the loop
   should stop, it says so in its report (SKILL.md 662-666).**
   → **Nowhere (standing).** The dominant case is a *worktree* lane, and a
   worktree lane cannot reach the coordinator's heartbeat monitor or watch
   server — those live in a separate process/session the subagent has no
   handle to. The rule is real only for *shared-tree* lanes, which are the
   documented exception (394-406). Carrying it in the standing boilerplate
   would bind every lane against a thing most of them cannot do; a task head
   can re-state it on the rare shared-tree dispatch. Not added.

2. **The inbox is not lossless; put what must survive in the commit
   (SKILL.md 608-620, `#404`/`#392a`).**
   → **Boilerplate (one line).** This is the one genuine standing gap. The
   boilerplate already says *commit incrementally* (the code change survives)
   and *report to the coordinator*, but it never says the **deliverable
   itself** must live in the commit. For a lane whose work product is a
   document or analysis (this very task is one), a report that exists only in
   the inbox can be lost — `#392a` lost exactly that. The fix is one clause,
   measured backing, high value. **Added** (see change below).

3. **A commit that changes what an install must do carries a trailer —
   `Migration:` / `Feature:` / `Needs:` (`#194`, SKILL.md 906-914).**
   → **Task head (when relevant), not boilerplate.** The rule is explicitly
   conditional ("only when true"); ~95% of lane tasks add no migration or
   feature. Standing it in the boilerplate is noise that trains skipping
   (`#612`). The coordinator's task head already knows whether the work is a
   migration and should name the trailer there. Not added.

4. **`git config commit.cleanup scissors` once after a fresh clone (`#693`,
   SKILL.md 384-392).**
   → **Nowhere (lane-side).** This is a one-time *setup* action on the shared
   repo config; worktrees inherit it, a lane never clones, and `lint.py`
   already refuses unless the value preserves `#` lines. A lane neither
   performs nor can be bitten by it undetected. Not a lane rule; not added.

**Net for List 2:** one standing addition (#2). The rest are conditional
(task-head) or moot for worktree lanes. After `#652` and `#687` the
boilerplate is in good shape; the remaining gaps are few and mostly
conditional.

## List 3 — in the boilerplate, absent from or contradicted by SKILL.md

Split into **3a** (consistent — the boilerplate is the legitimate home for a
lane rule, so absence from SKILL.md is fine) and **3b** (a contradiction or an
unbacked invention — the `#687`-shape danger). **3b is empty**, and that is
the finding: I actively looked for contradictions and found none (what I
checked is named under 3b).

### 3a — consistent, boilerplate is the right home

- **"A defect site is an EXAMPLE, not the inventory — check the sibling
  constructs" (`#690`, boilerplate 20-28).** Absent from SKILL.md (verified:
  no match for `EXAMPLE|sibling|inventory`). A genuinely useful lane rule with
  no SKILL.md backing. Promotion to SKILL.md is *optional, not required*:
  the boilerplate **is** the lane-facing surface, it is version-controlled
  and corrected by dogfood on every report, so a rule living only there is
  durable. The only residual risk is loss on a future boilerplate rewrite —
  which is exactly what this audit rotation catches. Left as-is.
- **Volume: land the fewest lines (`#612`, boilerplate 92-94).** Absent from
  SKILL.md as a lane rule (verified: no match for `fewest lines|Volume`). A
  doc-craft rule born from `#612`; the boilerplate is its natural home. Fine.
- **Never bare `git stash`/`git stash pop` (boilerplate 102).** Absent from
  SKILL.md (the only `stash` there, line 856, is the *coordinator's* `do now`
  path — different actor). Consistent, not contradicted; the worktree-shared
  stash stack is a real lane hazard worth the standing line. Fine.
- **Operational specifics: ports `:35110`/`:35113`, 2-thread limit, measured
  load thresholds, the single-process static-probe authorisation
  (boilerplate 112-140).** Boilerplate-only operational guidance, all
  consistent with SKILL.md 488-498 (guard ports 39890-39899). Legitimate.

### 3b — contradictions / unbacked inventions (the dangerous kind)

**None found.** I checked specifically for `#687`-shape disagreements:
`handoffs.md` writer (now consistent), rebase target (local master vs
origin — consistent), the conflict-marker grep (identical, including the `$`),
the `attn` prohibition (consistent), and the snapshot/`checkout` rule
(consistent). Every boilerplate rule either agrees with SKILL.md or is a
legitimate 3a addition. The reconciliation this task's predecessors did
(`#687` at `dc3ac7c3`, `#652` at `e8e6afaa`) holds.

## List 4 — ambiguous lane / coordinator

- **Small-increment / ~15-20 min cap (SKILL.md 18-20, 62).** This is loop
  *philosophy* addressed to the coordinator's tick checkpoint, not an
  imperative to a lane. A lane *is* roughly one increment; the cap is
  principally a coordinator splitting concern. Not clearly lane-facing; left
  out of the boilerplate's standing rules (the "COMMIT INCREMENTALLY" clause
  carries the part a lane actually controls). Ambiguous → here, not forced.
- **Commit subjects begin with `#NNN`.** Never stated as a lane imperative in
  SKILL.md — only declaratively ("the commit convention puts the id in the
  subject by construction", 392) — and absent from the boilerplate. It is a
  real lane obligation (`sweep`/`#404` depend on it), but because it is
  declarative my method does not even recognise it as a SKILL.md lane rule.
  This is the direction-2 blind spot (below). Ambiguous → here.
- **"A report must say what durable state changed" (SKILL.md 676-678).**
  Arguably distinct from the boilerplate's deliverable list, arguably
  subsumed by it. Substantively covered; not added separately.

## The check question — argued before building

**Decision: no automated check.** Both files are unstructured prose, and the
unit of interest — "a *rule* is stated" — has no machine-detectable boundary.

A substring check is precisely the `#699` shape: it guarantees a string is
present *somewhere*, not that a rule is *stated*. It fails both ways here, and
both are measured in this repo (`lessons.md:336`, relied-on line):

> **A check is only as good as the distance between what it asserts and what
> it exercises.**

That distance is maximal for prose: the check would assert "token X present"
while exercising nothing about whether a lane receives the rule. Two concrete
failure modes —
- **False green:** the token appears incidentally (e.g. "snapshot" in both
  files for different reasons) while the rule is absent — exactly `#699`'s
  "unioned every parenthesised group" reporting mapped while the enumeration
  named it zero times.
- **False red:** the rule is present with different vocabulary (SKILL.md:
  "lane-private snapshot directory"; boilerplate: "LANE-PRIVATE, not merely
  outside the repo") and a reword breaks the check while the rule is intact.

A *curated* anchor list ("these N audited rules must appear") only shrinks the
set; it still binds the token, not the statement — remove a rule's meaning but
leave a token and it stays green. So even the scoped variant is not honest.

**What carries the obligation instead:** (a) the **maintenance rotation**
(SKILL.md 296-310) — this very task is that rotation firing, and judgement on
prose is exactly what it requires; and (b) a **one-line reminder in the
boilerplate's own header** that when `SKILL.md` gains a lane-facing rule the
same increment reflects it here. The brief names both as legitimate carriers
for the no-check case. **Both added** (see changes).

## Red-proof

I landed no check, so Direction 1 discharges against the **audit method**
itself: show it finds the known missing rule (`#652`).

### Direction 1 — the method rediscovers `#652`

Snapshot first (lane-private, `#652`/`#652`'s own rule applied to itself):

    S="$(dev/lane_scratch.py snap)"; cp briefs/boilerplate.md "$S/boilerplate.md"

Then **injure** the protected thing: delete the lane-private-snapshot clause
from the boilerplate (the `#652` sentences at lines 62-72) — recreating the
pre-`e8e6afaa` state the task was filed against. Re-run the classification
method on the injured file: the lane-private-snapshot rule (SKILL.md 542-562)
no longer matches any boilerplate line, so it falls out of List 1 into
**List 2 (missing)**. The method finds the known instance. Restore by `cp`
from the lane-private snapshot, verify with `cmp` (never `git checkout`,
`#349`).

### Direction 2 — a rule the method misses

**Commit subjects must begin with `#NNN`.** It is a real lane obligation
(`sweep` and `#404` both depend on the id being in the subject), but
SKILL.md states it only declaratively — "the commit convention puts the id in
the subject by construction" (392) — never as an imperative addressed to a
lane, and the boilerplate carries no such rule. My method scans for lane
*imperatives*; a declarative sentence is invisible to it, so the gap goes
unflagged in every list above. Construct the input: a lane that runs
`git commit -m "fix the joiner"` (no `#NNN`). The commit lands, `sweep`
cannot correlate it, the work sits done-but-open — and my audit reports the
boilerplate complete. **Reported openly; not closed** — closing it needs the
rule stated as a lane imperative somewhere, which is a coordinator decision
(not in this task's fix scope; named for filing).

## Cited issues — relied-on lines

- **`#400`** — *"The lessons that reach a lane are the ones I hand-copy into
  its brief, and nothing else does."* (Whole premise of the task.)
- **`#652`** — *"two lanes snapshotting the same file silently clobber each
  other's restore point"*; the lane-private-snapshot rule, and the List-2
  canary. Now landed in the boilerplate (62-72).
- **`#699`** — *"check_doc_map_plans unions every parenthesised group on the
  row, so a plan can be 'mapped' while the enumeration never names it."* The
  trap for the check half of this task.
- **`#612`** — volume as a constraint on the *fix* (not the audit): a correct
  change that triples a doc's length gets reverted. Keeps the additions to
  two one-liners.
- `#687` (handoffs.md single writer), `#349` (never `git checkout` to
  restore), `#392a`/`#404` (inbox not lossless), `#194` (commit trailers),
  `#690` (EXAMPLE-not-inventory) — each opened and read; relied-on lines
  quoted inline where used.
