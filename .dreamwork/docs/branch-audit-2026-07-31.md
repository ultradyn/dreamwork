# Branch audit — 2026-07-31 (#676)

Classification only. **Nothing was deleted, merged, or rewritten** — a wrong
"abandoned" verdict is unrecoverable and the branches cost nothing to keep.

**Base state.** master head = merge-base = `3e44bc6f` (identical, branched
from tip). Two of the original fifteen (`lane-577reply`, `lane-583question`)
were already answered — content verified on master via cherry-pick — and are
excluded. **Thirteen classified below.**

Method: `git cherry master <branch>` (`-` = patch-id equivalent on master,
`+` = not on master) cross-checked against the cited landing sha's
reachability (`git merge-base --is-ancestor`) and, for one branch, a content
grep. Every issue number in a branch name was read from the ledger first.

## Verdicts

| Branch | Category | Evidence |
|---|---|---|
| `fix-271-noteprop-reduced-guard` (5) | cherry-picked | all 5 `-`; #271 landed `2c0652b`, ancestor of master |
| `fix/268-contextual-plugins` (1) | cherry-picked | `-`; #268 landed `ac4d57a`, ancestor; `hide_plugins.py` on master |
| `fix/271-cross-browser-note-propagation` (1) | cherry-picked | `-`; #271 landed; `dev/capture/noteprop.mjs` on master with `#271` marker |
| `fix/291-command-close` (1) | cherry-picked | `-`; #291 landed `26c4bee`, ancestor of master |
| `pi-agent-4bcf14a6-*` (1) | scratch (duplicate) | **identical sha** to `fix/271-cross-browser-note-propagation` (`7cb153ef`); `-` |
| `pi-agent-a1b2dfb7-*` (5) | scratch (duplicate) | **identical sha set** to `fix-271-noteprop-reduced-guard`; all `-` |
| `pi-agent-9f527dd0-*` (5) | scratch (duplicate + stale fixture) | 4 `-` (#271); 1 `+` = `6e86fd1e`, a 2-line test-fixture tweak for landed #271, not on master, not a finding |
| `pi-agent-b61f930b-*` (1) | scratch (duplicate) | `-`; #221 landed `b9159db`, ancestor |
| `pi-agent-00ae7236-*` (3) | scratch (duplicate) | **proper sha subset** of `prototype/279-jovian-final`; all `+` |
| `pi-agent-1a33ccb3-*` (3) | scratch (duplicate) | **identical sha set** to `prototype/279-jovian`; all `+` |
| `prototype/279-jovian` (3) | deliberately abandoned | all `+`; #279 failed prototype; superseded by `-final` |
| `prototype/279-jovian-final` (5) | deliberately abandoned (preserved source) | all `+`; #279 names this branch + tip `a1c180c` as the preserved throwaway |
| `spike/components` (4) | holding work — **already preserved** | all `+`, but the 228-line findings doc is on master (`dd7bab84`, byte-identical) and was consumed by #630 P2 |

**Tally:** cherry-picked 4 · scratch/duplicate 6 (all pi-agent) ·
deliberately abandoned 2 · holding-work-already-preserved 1.
**Live work: 0. Holding work worth a new citation: 0.**

## The pi-agent class — uniformly scratch, by construction

Five of the six `pi-agent-*` branches are **exact sha duplicates** of named
branches (verified by `diff` of sorted sha sets): `a1b2dfb7` =
`fix-271-noteprop-reduced-guard`, `4bcf14a6` = `fix/271-cross-browser`,
`1a33ccb3` = `prototype/279-jovian`, `00ae7236` ⊂ `prototype/279-jovian-final`,
`b61f930b` = #221's patch (on master). The sixth (`9f527dd0`) is four #271
duplicates plus one unique commit — a two-line addition to a *test fixture*
(`dev/capture/fixture/.dreamwork/questions.md`) for a bug that already
landed through a different route. None holds unique work worth referencing.
The brief's caution holds: they are scratch from another harness, and the
one with a unique commit is the least interesting commit in the audit.

## Holding work worth referencing — the answer is none new

The category that justifies the task. The live instance (`spike/components`)
is **resolved, not by this audit but before it**: the 228-line findings doc
(`2026-07-25-component-unification.md`) is on master at `dd7bab84`
(byte-identical to the branch copy), and #630's P2 lane read `9b54b4f0`,
took the durable rule (*"component identity here is `data-*` attributes
ONLY, never a class"*), and argued the delegating wrapper is immune to
Max's obstacle precisely because it rewrites no markup — an argument the
plan never made. So the measurement is no longer "sitting on a branch
uncited"; it is preserved as its own doc and consumed by the implementing
lane.

Every other branch with content genuinely not on master (the `+` arms) is
either a deliberately abandoned failed prototype whose conclusion was "no"
(#279), or a pi-agent duplicate of one. No branch holds an uncited
finding that a live doc or plan should reference. **The class of problem
the task exists to find has no remaining instance among the thirteen.**

## Should this audit be periodic? — yes, at the fold

The loop ran this audit today only because #590 bit first — a folded-but-
unmerged branch looked identical to a deliberately abandoned one, and the
ledger cannot raise the difference (lessons.md:3299: *"Run it when folding
a batch, because the ledger will never raise it"*). The state-audit earlier
today named the per-branch diff as *"the next-cheapest thing to check"* but
did not do it. Both are the same gap: the check has no home, so it runs
when someone remembers, which is after the damage.

**Yes, it should be periodic, and the trigger lives at the fold step.** A
fold is when branches are created and abandoned, so it is the moment a
reachability gap can appear. The check is the one #590 already names: for
every branch, `git rev-list --count master..<branch>`; anything non-zero is
a question (live work, cherry-picked, or a gap), never a verdict. It is the
branch-level twin of `dev/ledger.py sweep` (#671), which does the same job
for ledger entries — but sweep examines commit *subjects*, not *branches*,
so a folded-not-merged lane is invisible to it by construction.

A guard could raise it: a post-fold step that enumerates branches with
unreached commits and surfaces them for classification. **Filed as a task
to name, not build** (out of scope here): *post-fold branch-reachability
sweep* — the coordinator files it.

## Red-proof

**Direction 1 (cherry-picked claims name specific evidence).** For each
cherry-picked verdict the evidence is `git cherry master <branch>` → all
`-`, plus the cited landing sha verified as a master ancestor. The
discriminating signal is the `-` marker: the same command over
`prototype/279-jovian` returns `+` (genuinely not on master), so the method
separates cherry-picked from abandoned. Content grep re-confirmed for the
two most distinctive: `hide_plugins.py` exists on master (#268), and
`dev/capture/noteprop.mjs` carries the `#271` marker on master (#271). The
one apparent ambiguity — `fix/271`'s function name not grepping in
`watch.py` — reconciles to the content living in `dev/capture/noteprop.mjs`
(a guard file), which is on master; the patch-id equivalence and the
landed-task record agree.

**Direction 2 (where the classification could be wrong, expensively).** The
expensive error is calling something abandoned or cherry-picked when it
holds something. Three candidates, named honestly:

1. **`pi-agent-9f527dd0`'s unique commit `6e86fd1e`** — called scratch (a
   stale fixture line). It is *not* on master. What would change my mind: if
   the landed #271 guard were vacuous without that specific fixture entry.
   It is not — #271's ledger records a *"normal+reduced shared non-vacuous
   guard"* that passed independently — so the fixture line is scaffolding
   for a repair route that lost, not a missing test.
2. **`prototype/279-jovian-final`** — called deliberately abandoned. What
   would change my mind: if #280 (blocked on #279) were re-attempted and the
   closest shader variant here were a useful start. It stays blocked, and
   #279's recorded conclusion is a failed prototype; the branch is preserved
   (not deleted) precisely so it *can* be that start. The classification
   holds; the preservation is the safety net.
3. **`spike/components`'s code** (`watch.py` +556/-40, `qacard.mjs`) —
   called already-preserved (findings on master). What would change my mind:
   if the experimental code held an implementation insight beyond the
   findings doc. It does not — the findings doc is the distilled conclusion,
   the code is the throwaway experiment that produced it, and #630 P2 chose
   delegating wrappers (no markup rewrite) specifically to avoid the
   obstacle the spike measured.

The method's blind spot, stated: `git cherry`'s patch-id match can miss
content that landed **refactored** (same intent, different lines). I closed
this for #271 by content grep; for #268/#291/#221 the landing shas are
master ancestors and the task records confirm the content. If any of those
three had been substantially rewritten on master, patch-id `-` could still
hold while the *specific lines* diverged — but the task ledger's
description of what landed matches the branch's intent in each case.
