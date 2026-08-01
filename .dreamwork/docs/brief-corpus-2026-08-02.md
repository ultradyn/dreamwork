# Brief corpus tracking investigation — 2026-08-02

## Verdict

The apparent gap is real, but its unit was misnamed. At the latest frozen
snapshot below, the main checkout held **264 untracked directory entries**:
**132 exact dispatched prompts plus their 132 matching SHA-256 receipts**. It
did not hold 264 untracked briefs. Every pair verified, none was ignored, and
all were ordinary top-level regular files.

Under the latest explicit human ruling, **0 of those 264 entries should be
bulk-added to Git**. The separating rule is policy, not content or lane
outcome:

- leave the 372 already-tracked historical entries tracked; do not rewrite
  history;
- keep every currently untracked brief/receipt pair operator-local, including
  the 28 pairs that were still pending when the ruling arrived;
- keep future pairs operator-local unless the human explicitly reverses that
  ruling.

That answer is not derivable from the current implementation alone. The
repository still documents and supplies a coordinator-only route that stages
all pairs. Ledger **#867** records the later human decision that superseded the
tracked-file recommendation:

> “I think we do want to store them, but not in the project git itself. For
> now, i think just keeping them local is fine. typically the main dreamwork
> agent will run from the same machine so the briefs are there if needed. and
> realistically they aren't that important. not important enough to persist
> forever.”

The same entry says, “Do not rewrite history to purge already-tracked briefs;
untrack going forward.” Its implementation was refused and reverted off
master because the Git-history-scoped lint checks became vacuous or red. The
result is a split-brain contract: operator practice follows the later ruling,
while checked-in docs and tools still describe tracked persistence. That
contract split—not a distinct class of scratch briefs—is why a lane and the
main checkout cannot measure the same corpus.

## Measurements and conditions

All counts below name whether they are directory-present or Git-tracked, the
checkout, and the commit. `git ls-files` and `ls` both count directory entries,
including receipts; the `.md`/`.sha256` split is stated separately.

### Required first measurement

At 2026-08-02 06:30:43 AEST, before any deliverable edit:

| checkout condition | HEAD | tracked entries: `git ls-files .dreamwork/docs/briefs` | present entries: `ls .dreamwork/docs/briefs` |
|---|---|---:|---:|
| main checkout `/home/xertrov/.llm-general/skills/ud-dreamwork` | `bba00bf257bf0647f49d74dba809d1df7cf68e03` | 372 | 632 |
| linked lane worktree `/home/xertrov/.llm-general/skills/.worktrees/cx-944corpus` | `bba00bf257bf0647f49d74dba809d1df7cf68e03` | 372 | 372 |

Thus the same commit exposed **632 working-tree entries in main versus 372 in
the lane**. The lane's 372/372 reading was true and still omitted 260 main-only
entries.

### Later frozen main snapshot and trend

Master and the live operator-local corpus moved during the investigation. At
2026-08-02 06:42:14 AEST, one read-only process observed the same HEAD before
and after its census:

- main checkout HEAD:
  `1224d73b24da0eb1c418f33289e78f541f4fde0c`;
- tracked-only denominator: **372 entries = 295 `.md` briefs + 77
  `.sha256` receipts**;
- working-tree-present denominator: **636 entries = 427 `.md` briefs + 209
  `.sha256` receipts**;
- main-only/untracked denominator: **264 entries = 132 `.md` briefs + 132
  `.sha256` receipts**;
- ignored denominator: **0 entries**;
- structural denominator: **636/636 top-level regular files**, with 0
  directories, 0 symlinks, 0 hidden names, 0 names containing a newline, and
  0 tracked paths missing from disk.

The task record reported 372 tracked / 624 present on main at `217e6cbd`.
My first re-derivation was 372/632 at `bba00bf2`; ten minutes later it was
372/634 at `1224d73b`; ninety seconds after that the frozen census was
372/636 at the same `1224d73b`. This is a snapshot, not a stable rate, but it
does establish direction: **six new brief/receipt pairs appeared between the
task-record snapshot and the frozen census, and two appeared during this
investigation**. The gap is growing by two directory entries per dispatch
until a retention action changes it.

Ledger **#930** supplies the condition discipline relied on here:

> “Either way: state which sha AND which working directory your measurement
> describes. That pair, not the count, is the finding.”

Ledger **#943** records the concrete false conclusion this discipline prevents:

> “CORRECTION — MY MEASUREMENT WAS TAKEN IN THE WRONG TREE STATE AND THE
> HEADLINE CLAIM IS WRONG. This entry should not be read as filed.”

## What the 132 untracked briefs are

At the 06:42:14 snapshot:

- **132/132** untracked `.md` briefs had a sibling receipt whose recorded
  SHA-256 matched the exact brief bytes;
- `python3 dev/dispatch_lane.py --verify-pending`, run from this lane's
  interpreter against the main-checkout corpus, reported `brief integrity
  verified: 207 governed brief(s) matched receipts` before the last two live
  pairs appeared;
- **132/132** carried the standing boilerplate heading, so none is an
  unrelated Markdown scratch file that merely landed in the directory;
- **117/132** were associated with task ids currently marked landed, and
  **15/132** with task ids currently open; across unique task ids the split was
  105 landed / 9 open, 114 total;
- **31/132** belonged to 13 task ids with more than one lane name. That group
  includes retries, parallel increments, stopped attempts, and parked variants;
  the corpus is therefore not a winners-only collection;
- **78/132** carried a non-empty `Lane-owns:` declaration. The missing 54 are
  historical dispatch-shape drift, not evidence that their prompts are a
  different storage kind;
- untracked bytes totalled **4,472,331 bytes**; the 372 tracked entries
  totalled **3,798,655 bytes**. Bulk-adding is therefore a 264-file, roughly
  4.47 MB working-tree change before Git compression, not a bookkeeping-only
  act.

I opened a content sample of **24 briefs (11 tracked, 13 untracked)**, reading
their identity headers and task-specific sections. The sample deliberately
covered early and late task ids, landed and open tasks, repeated task ids,
design-only lanes, implementation lanes, and the generator/dispatcher work
itself. I also scanned all 132 untracked briefs structurally and verified every
receipt. The sampled tracked and untracked files contain the same kind of
substance: an authored task core plus the lane contract. Tracking status does
not separate “generated frames” from “hand-written cores.”

The set does cross the frame-generator cutover. Ledger **#936** records that
the launch path was changed so `launch_lane.py` “now CALLS brief.py build()
itself, so the canonical frame is generated at dispatch and never hand-typed.”
That merge landed at 06:14:13 AEST; six of the 132 untracked briefs had mtimes
at or after that merge in the frozen census. The rest predate the integrated
generator; the sampled earlier prompts exhibit the older assembled-frame
drift. Both groups are exact, receipted dispatch inputs and both are untracked.
The cutover changed how a brief is assembled, not whether it is added to Git.

### Time distribution

The task ids make the set look old and evenly spread; the filesystem mtimes do
not. They place all 132 untracked briefs between 2026-08-01 15:47:49 AEST and
2026-08-02 06:41:54 AEST, consistent with the writer's exclusive-create
semantics. The last commit that added corpus pairs ran at 15:44:42 AEST, three
minutes before the oldest current untracked brief.

- **28/132 briefs** were created after that last corpus-add commit and before
  the 19:49 operator-local ruling. Under the previous tracked-corpus contract,
  these are the direct manual-process leak.
- **104/132 briefs** were created at or after the 19:49 ruling. Their local-only
  state matches the human decision, even though the decision's code and docs
  have not landed.

This establishes a discontinuity in dispatch time, not task id. A recently
dispatched lane for an old task has an old numeric prefix and a new file. Task
id is not a safe proxy for when or why tracking stopped.

## Why they are untracked

There is no `.gitignore` rule for `.dreamwork/docs/briefs/`; `git check-ignore`
returned no match and Git reported every local-only entry as ordinary
untracked content.

The writer deliberately stops before Git:

- `dispatch_lane._briefs_dir()` resolves the **main checkout** even when the
  interpreter runs in a linked worktree (`dev/dispatch_lane.py:85`);
- `persist_prompt()` exclusively creates the exact `.md` prompt and its
  receipt, verifies the pair, and returns; it neither stages nor commits
  (`dev/dispatch_lane.py:510`);
- the module contract says the pair is “intentionally uncommitted” and “does
  not guarantee that a coordinator will preserve or commit it”
  (`dev/dispatch_lane.py:10`);
- the checked-in skill nevertheless says the coordinator verifies and commits
  both at the merge gate, including briefs for abandoned or never-started lanes
  (`SKILL.md:407`);
- `just commit-corpus` is the only staging route. It verifies all receipts,
  loops over every pair, calls `git add` on both halves, and still leaves the
  actual commit to a person (`justfile:666`).

So the initial hypothesis is correct for the old policy: **adding depended on
the coordinator remembering a separate batch command**. Git history confirms
two manual corpus batches on 2026-08-01, followed by immediate renewed growth.
The dispatch generator does not add its output and the merge gate does not make
the commit unavoidable.

After 19:49, however, “nobody ran `git add`” is no longer the whole diagnosis.
The human had ruled that new briefs should remain operator-local. The process
then followed that ruling while the repository contract remained unchanged
because the implementation branch was blocked. The current gap is therefore:

1. **28 prompt/receipt pairs leaked through a manual durability seam before
   the ruling**, and
2. **104 prompt/receipt pairs correctly remained local under the ruling but
   are still described by stale checked-in text as pending Git records**.

## Recommendation

### Corpus decision

Do not bulk-add or bulk-delete anything in this increment.

Treat the human's operator-local ruling as authoritative until explicitly
reversed: **0/264 current untracked entries to commit; 372/372 currently
tracked entries remain historical Git content.** Retain all local pairs,
including abandoned/stopped lane prompts, because the supported writer's
create-once receipt contract treats the requested dispatch—not its successful
landing—as the record.

The next implementation decision is not “which 132 are scratch?” There is no
evidenced content rule that divides them that way. It is to finish reconciling
the operator-local policy with its readers. The still-open decision on #867 is
how to handle old briefs that predate enforceable `Lane-owns:` metadata without
making lint red; it does not reopen whether new prompts belong in Git.

If the current task's “durable dispatch record” premise is intended as a human
reversal of #867, that reversal must be stated explicitly. Under that alternate
policy, **all 132 pairs should be committed**, not only landed lanes: every pair
is valid, content-equivalent in kind, and the existing checked-in contract
explicitly retains abandoned and never-started dispatches. A landed/open or
generated/hand-assembled split would falsify the record's stated identity.

### Precisely scoped later lint increment

Do not implement this here. A later lane should add one shared, read-only brief
population measurement and make every brief row name it. The measurement should
carry:

- target checkout path and target HEAD;
- checkout kind: main checkout or linked worktree;
- present `.md` count;
- Git-tracked `.md` count;
- present-but-untracked `.md` count;
- tracked-but-missing `.md` count;
- a stable population label consumed by each check.

The later output should make these two conditions impossible to conflate. Using
the frozen denominators as the example:

```text
main @ 1224d73b: brief population working-tree-present=427,
  tracked-index=295, operator-local-only=132, tracked-missing=0
lane @ bba00bf2: brief population working-tree-present=295,
  tracked-index=295, operator-local-only=0, tracked-missing=0;
  LINKED WORKTREE — the main checkout's operator-local corpus is not visible here
```

Then label the current consumers according to what they actually judge:

- dream-instruction contradiction and id reach: **working-tree-present**;
- hand-off obligation, absolute inbox, and lane-private scratch cutoffs:
  **Git-history-classified tracked population**, with the untracked skipped
  count printed;
- lane ownership: **mixed working-tree candidates / Git-history
  classification**, and explicitly state that the current implementation
  treats an untracked candidate as grandfathered. That behavior is the defect
  already analysed by #867; labelling must expose it, not silently bless it.

Do not silently redirect a lane's lint to the main checkout. The target remains
the subject. A linked-worktree run must instead state that its working-tree
population is only the tracked snapshot and that the operator-local authority
is unavailable there. A zero present population must say **DID NOT MEASURE**,
not OK.

The later tests should create one main-like target with one tracked and one
untracked brief, plus a linked worktree that can see only the tracked brief.
Each brief row must assert its population label and all four denominators. A
test that merely asserts the final defect count is unchanged is insufficient:
the false green under investigation preserves that count while changing the
population beneath it.

## Retirement proof and boundary

### Direction 1

No production seam was changed and no new check was added. This investigation
therefore owes no sabotage injection, and `dev/redproof.py check --require 1`
would manufacture evidence rather than verify the document. The production
seam inspected was the dispatch-to-corpus-to-Git path described above; it was
not modified.

### Direction 2

Four false-completion candidates were exercised:

1. **Lane-only census:** closed. The lane reported 372 tracked / 372 present at
   `bba00bf2`, while main at the same commit reported 372/632. The seemingly
   complete lane population was the false green.
2. **Structural `ls` discrepancy:** closed. At the frozen main snapshot all
   636 entries were top-level regular files; there were no subdirectories,
   symlinks, hidden names, newline names, or missing tracked paths. The gap was
   exactly 132 untracked `.md` files plus 132 receipts.
3. **Filename-only classification:** closed as far as kind, open as far as
   individual lane outcome. I read 24 task cores and scanned all 132 untracked
   structures/receipts. This establishes that they are governed exact prompts,
   not scratch, but it does not establish which specific repeated lane attempt
   produced the landing. Task state is not lane-attempt state.
4. **Single-point trend:** closed only for direction. The main population moved
   632 → 634 → 636 during the investigation, while tracked stayed 372. That
   proves growth, not a long-run rate; pruning, an explicit Git commit, a policy
   implementation, or concurrent dispatches would change the answer.

This document can establish the filesystem and Git populations at the named
times, the receipt integrity, the current ledger-task split, the writer/stager
seam, and the latest recorded human policy. It cannot establish whether the
human now wishes to reverse the operator-local ruling, whether any prompt
contains material inappropriate for Git, or the exact fate of every individual
attempt without a separate attempt-by-attempt audit.

## Named tests

None. This increment changes one investigation document and no executable
behavior. No test was added.

## Dispatch-contract contradiction and dogfood finding

There is no rule forbidding this deliverable: the task-specific head explicitly
authorizes this new document. The material contradiction is instead in the
task's premise. It says briefs are supposed to be a durable dispatch record in
the repository, while the still-current human ruling on #867 says they should
be local and “not important enough to persist forever.” The task did not name
that ruling or explicitly reverse it. Finding it changed the recommendation
from “commit every valid pair” to “commit none unless the ruling is reversed.”

The tooling also made the unit easy to misstate: both advertised commands count
directory entries, not briefs, and receipts now make the gap exactly twice the
brief count. A population label must therefore name both its tracking condition
and its artifact unit.
