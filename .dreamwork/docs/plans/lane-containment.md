# Lane containment — #465

**Status:** design landed; the layered defence is complete. The **early-failing
half** (the pre-commit guard, R5) is built and red-proved. The **successor**
landed in two halves under #468: the **ambient backstop** (`lint.check_lane_containment_backstop`,
which ERRORs a lane-owned dirty path whenever `lint` runs, needs no hook) and the
**merge-time assertion** (R2, `dev/lane_guard.py pre-merge <branch>`, which refuses
the merge naming the reason and one action). Both reuse `lint.lane_owned_paths`,
the single lane-ownership reader — two callers, one definition.

## What happened, and the invariant

A lane dispatched into `.worktrees/superseded` on `wt/superseded` edited
`dev/capture/health.mjs`, `.dreamwork/docs/doc-map.md` and wrote a new plan file
**in the main checkout on `master`**. Its own worktree stayed clean. Two harms:
one realised (it aborted a verified `#263` merge that had been held for half an
hour, and the coordinator could not revert without destroying a live agent's
work); one unrealised and worse (a coordinator `git commit` would have swept the
lane's half-finished edits into a ledger commit under the wrong message — exactly
`12f47e3`, and `--only` does not protect you when the file is one the coordinator
is also touching).

The invariant at stake is the one the whole fan-out rests on: *parallel increments
only ever touch disjoint files, so there is never a split brain*. A worktree makes
that hold **by construction**, and the guarantee is void the moment a lane writes
outside it. A brief cannot enforce this — the incident's brief named the worktree
twice and was ignored. **Only a check can.**

## Two precondition findings that shape the design

1. **`status.json` does not carry file ownership.** The brief said it does
   ("`status.json` already records which lanes are out and what files each owns").
   It does not. The `dreamers` entry shape is `{"task", "pid", "brief"}` — the
   task id, the dispatch pid, and the brief's absolute path. **There is no `owns`
   field and no worktree path.** File ownership lives in the brief's prose
   ("Yours: … / Not yours: …"), in the coordinator's memory, and in
   `dispatch-shortlist.md` — none of them machine-structured. So **any mechanism
   that reads an ownership list out of `status.json` reads nothing**, and a check
   built on that assumption passes vacuously the day it ships and every day after.
   This is exactly the "assert the precondition at runtime" rule the brief named,
   found by asserting it: the brief's own premise had drifted from the file's shape.

2. **`core.hooksPath` is global** (`~/.config/git/hooks`) and is **shared across
   the main checkout and every linked worktree**. A pre-commit hook installed
   there runs on `master` *and* in `.worktrees/contain`. But `git rev-parse
   --git-dir` tells them apart: the main checkout's git-dir is `.git` (the common
   dir), a linked worktree's is `.git/worktrees/<name>`. So a hook can decide
   "is this commit landing in the main checkout?" and act only there. That is the
   seam a containment guard hangs on.

## The IGC — ideas × goals

**Context:** a dreamwork target with one main checkout (on `master`) and N
linked worktrees under `.worktrees/<name>` on `wt/<name>`, each a dispatched
lane. The coordinator commits the ledger constantly from the main checkout;
lanes commit from their worktrees. The defect is a lane's *file writes* landing
in the main checkout rather than its worktree.

**Goals (binary — each must have a fact of the matter):**

- **G1** — the coordinator never has to ask a subagent's permission to merge
  (refutes anything that only *warns* after the fact).
- **G2** — a lane writing outside its worktree fails at the **first write**, not
  at merge time.
- **G3** — the mechanism needs **no cooperation from the lane** (a rule a brief
  states is what already failed).
- **G4** — no false refusal when no lane is out: the ordinary solo case stays
  frictionless.

**Constraint C** (not a goal, a hard limit): *nothing may make the loop's own
commits harder.* The coordinator commits the ledger constantly; a hook that
prompts or blocks ordinary work is disabled within the hour and then protects
nothing.

| Idea | All | G1 | G2 | G3 | G4 | C |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| R1 pre-commit hook on main checkout, reads `status.json` ownership | ✘ | ✔ | ✘ | ✔ | ? | ? |
| R2 coordinator pre-merge assertion (main tree clean of lane paths) | ✘ | ✘ | ✘ | ✔ | ✔ | ✔ |
| R3 marker file in each worktree a lane must read+echo | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| R4 dispatch with explicit `git -C <worktree>` | ✘ | ✘ | ✘ | ✔ | ✔ | ✔ |
| **R5 pre-commit guard on main checkout, ownership from worktrees' own briefs** | ✔ | ✔ | ✔\* | ✔ | ✔ | ✔ |

\* G2 for R5 is "fail at the first *commit*," not the first working-tree write —
see below for why that is the honest ceiling and why R3's stronger claim is
refuted by G3.

### Decisive errors

**R1 ✘ (G2):** a pre-commit hook fires at *commit* time, not at the first
working-tree write. The realised harm was a merge failing on dirty files; a
commit-time hook catches the *coordinator's* commit that would have swept the
lane's edits — but it does not catch a write that never commits. ✘ G2 in its
strongest reading. (And R1 as literally briefed is ✘ on its own premise: there
is no ownership list in `status.json` to read — finding #1.)

**R2 ✘ (G1, G2):** a pre-merge assertion only *warns* after the work has already
gone into the wrong tree, and the coordinator still has to decide what to do
with it — which on a live agent means asking the lane, exactly the state G1
forbids. ✘ G1 by construction; ✘ G2 (late). Cheap, and correct as a *backstop*,
but not the answer on its own.

**R3 ✘ (G3):** a marker file a lane must find in its cwd and assert needs the
lane to *do* something — read it, echo it, refuse to write otherwise. The
defect's own brief named the worktree twice and was ignored; a rule the lane
must obey is the rule that already failed. "It needs no cooperation from the
lane" (G3) is the brief's own statement of why, and R3 fails it. (R3 is the only
idea that truly fails at the *first write*, which is why G3 is the refutation
rather than a quibble — the strong early-fail and the no-cooperation requirement
are in direct tension, and R3 picks the one the brief said does not work.)

**R4 ✘ (G1, G2):** dispatching with `git -C <worktree>` only constrains the
lane's *git* operations. The incident's lane was invoked with the worktree as
cwd and its *editor/tool writes* still landed in the main checkout — `git -C`
does not reach a `Write` tool that takes an absolute path, or a `ccc` agent that
resolves a relative path against the wrong tree. So ✘ G2, and it does not catch
the realised incident at all.

**R5 ✔ — the survivor, and why each cell holds:**

- **G1 ✔:** the guard *refuses* the offending commit in the main checkout
  (non-zero exit), naming the lane and the contested paths. The coordinator never
  reaches a merge with a dirty main tree, so never has to ask a lane's permission.
- **G2 ✔\* (at first commit):** a lane's stray edit in the main checkout is
  caught the moment the coordinator (or the lane) tries to *commit* it there. It
  does not catch a write that is staged but never committed — but the realised and
  unrealised harms were both commit-shaped (a merge abort, a swept commit), so the
  commit boundary is the honest place this defect becomes dangerous. A
  working-tree-write guard with no lane cooperation is not achievable on this
  harness (R3 is the only candidate and it fails G3); R5 is the strongest
  no-cooperation early-fail available.
- **G3 ✔:** the guard reads ownership from the **worktrees themselves** (their
  registered path and their brief), never from a lane's compliance. A lane does
  nothing; the guard runs on the coordinator's commit and on any commit landing
  in the main checkout.
- **G4 ✔:** when no worktree is registered, the guard is a no-op. The ordinary
  solo case commits with zero added work.
- **C ✔:** the guard adds work only when a lane is actually out and a contested
  path is actually staged — the exact case the loop wants stopped. On every
  ordinary ledger commit it runs a handful of `git`/`stat` calls and exits 0.

**The honest caveat on G2:** R5 fails at *commit*, not at *first write*. The
brief's strongest G2 reading ("first write") is only achievable with lane
cooperation (R3), which G3 forbids. So R5 is the no-cooperation ceiling: it
catches the defect at the boundary where it becomes dangerous (commit / merge),
and the successor (R2, the pre-merge backstop) catches any edit that slips past
between commits. Together they are the layered pair the brief invited — R5
early, R2 as the cannot-be-bypassed backstop — and the brief says to build the
early half first, which is what shipped.

## What shipped (the early half)

`dev/lane_guard.py` — a pre-commit guard for the **main checkout only**. It:

1. **Detects it is in the main checkout** (`git rev-parse --git-dir` resolves to
   the common dir, i.e. the path contains no `/worktrees/` segment). In a linked
   worktree it exits 0 immediately — lanes commit freely from their own trees.
2. **Enumerates dispatched lanes** by walking the registered worktrees
   (`git worktree list --porcelain`), skipping the main entry and any worktree
   whose branch is not `wt/*`. This is the reliable lane registry — *not*
   `status.json`, which carries no worktree path (finding #1).
3. **Reads each lane's owned paths** from a declared ownership marker the lane's
   brief carries (`Lane-owns:` lines — see `file-formats.md`). The brief is the
   one document the lane was actually given, so it is the authoritative source of
   what the lane was told it owns. Ownership lives in the worktree's own brief,
   not in a central file the coordinator might forget to update.
4. **Intersects the staged paths** (from `git diff --cached --name-only`) with
   each live lane's owned set. On any overlap it **refuses** (exit 1), naming the
   lane (worktree + branch), the contested paths, and the remediation (commit
   from the worktree, or `--no-verify` only as a documented emergency escape).
5. **No-ops cleanly** when no lane is out, when the staged set is empty, or when
   the owned set is empty — the ordinary solo case costs a few `git` calls.

The guard is **machine-local** (`core.hooksPath` is not committed), so the
*script* is committed and *enabling* is a documented step (see §Enabling). An
un-enabled checkout gets the safety net the day it runs
`python3 dev/lane_guard.py --install`; before that, nothing changes.

### Why ownership from the brief, not a new registry

A new `owns` field in `status.json` would be a second writer the coordinator must
maintain, and `status.json` is gitignored ephemera that drifts (#402 measured it
drifting for hours). The brief is the document the lane was *actually handed*,
committed under `.dreamwork/docs/briefs/`, and already carries a "Yours: …" list
in every brief's prose. Declaring ownership as a machine-parseable
`Lane-owns:` line in the brief makes the brief the single source: what the lane
was told it owns is what the guard protects. No second store, no drift.

## The successor (now landed, in two halves)

**R2 — the coordinator-side pre-merge assertion — shipped under #468 as a layered
pair.** The IGC's design-time verdict (R2 ✘ G1/G2 as a *standalone* answer) still
holds, and is the reason R2 was not built first: a mechanism that only warns late
does not satisfy the early-fail goals on its own. What landed is the **backstop
layer** the design always said R2 would be, once the early half had bedded in.
It split into two halves, each closing the gap a different way:

1. **The ambient backstop** — `lint.check_lane_containment_backstop`. ERRORs when
   a path a live lane owns is dirty in the main checkout (staged, unstaged or
   untracked), which is the state that actually did the damage: the `#263` merge
   aborted on dirty files before any commit was attempted, so the pre-commit guard
   would never have fired. It is ambient — fires whenever `lint` runs, needs no
   hook, cannot be bypassed by `--no-verify`. Lanes come from git's own worktree
   registry, never `status.json`.

2. **The merge-time assertion** — `dev/lane_guard.py pre-merge <branch>`. The gate
   run in front of `git merge`, so the abort cause is named as a *reason and one
   action* rather than a bare file list (which read as a conflict). It is an
   explicit subcommand, not a `pre-merge-commit` hook, because that hook does not
   fire on a fast-forward (the common lane merge) and installing a hook is a
   separate consent ask whose own half (#465) is still un-granted. Its honest
   weakness — it must be remembered — is what the ambient backstop covers. It adds
   two dimensions the backstop cannot reach (the coordinator's *own* uncommitted
   tracked work, which no lane owns; and an untracked file the merge would clobber),
   refuses with one action, and moves no work (no stash/reset/checkout).

**Both reuse `lint.lane_owned_paths`** — the single lane-ownership reader extracted
so the backstop and the pre-merge assertion share one definition. Two callers, one
place the parsing can drift, not two. Each was red-proved against its own named
production line (the shared reader, the tracked-dirt branch, the clobber
intersection, the is-main-checkout gate, the branch-not-resolve None-source),
neighbours green for discrimination.

## How `status.json`'s absence / staleness is handled

The guard **does not read `status.json` at all.** Finding #1 is load-bearing:
there is no ownership list there to read, and the brief's claim that there was
is the drift the "assert the precondition at runtime" rule exists to catch. Lane
presence is derived from `git worktree list` (the registered worktrees on
`wt/*` branches), and ownership from each worktree's brief. So:

- **`status.json` absent** → the guard still works (it never depended on it).
- **`status.json` stale** (a dead lane still listed) → irrelevant; the guard
  keys off registered worktrees, not `dreamers`. A worktree whose lane died but
  whose tree still exists is still a live contention risk until the worktree is
  removed, so guarding it is *correct*, not a false positive.
- **A worktree removed but `dreamers` not pruned** → the guard no longer sees
  the lane (no registered worktree), which is correct: the lane is gone.

## Red-proof

Reproduced the incident in a **scratch clone** (never the real main checkout),
per the brief. The proof:

1. Made a scratch repo with a main checkout on `master` and a linked worktree
   `.worktrees/fake` on `wt/fake`.
2. Wrote a brief in the worktree declaring `Lane-owns: secret/lane.txt`.
3. Installed the guard as a pre-commit hook on the main checkout.
4. Created `secret/lane.txt` in the **main checkout** (the defect — a lane-owned
   path written to the wrong tree), staged it, and ran `git commit`.
5. **The guard refused** (exit 1), naming `wt/fake`, the path, and the
   remediation.

**The production line whose change reds the check:** `lane_guard.py`'s
`_owned_paths_for_lane` (the function that reads `Lane-owns:` from the brief).
Removing the intersection check (`contested = staged & owned`) makes the
refusal disappear and the commit land — so the check reaches the real decision,
not scaffolding. Confirmed the red did **not** need a seam the diff introduced:
the proof ran against a clone with only the guard script added; the worktree,
the brief and the `Lane-owns:` marker are all things a real dispatch creates, not
artefacts of the guard's own scaffolding.

**The green-red-run trap, checked:** the guard's refusal depends on the brief
*actually declaring* the owned path. A proof that wrote the file but never
declared it would pass vacuously — so the red fixture asserts the brief carries
the `Lane-owns:` line *before* staging the contested file, and the guard's own
precondition (`_owned_paths_for_lane` returning a non-empty set) is asserted in
the test. A guard over an empty ownership set is a no-op, and the test says so
out loud rather than reporting a silent pass.

## Enabling (manual — `Needs: config`)

`core.hooksPath` is machine-local and not committed, so enabling is a documented
step, not automatic. From the main checkout:

```bash
python3 dev/lane_guard.py --install
```

This symlinks `dev/lane_guard.py` into the configured `core.hooksPath`
(`~/.config/git/hooks/pre-commit` is the global path on this machine; the
install resolves the hook path from `git config core.hooksPath` so it works on a
machine with a different layout). It is idempotent and refuses to clobber a
non-lane-guard pre-commit. To uninstall: `python3 dev/lane_guard.py --uninstall`.

**What an un-enabled checkout gets:** nothing changes. The guard is inert until
installed. That is the honest cost of a machine-local hook: a fresh clone, or a
checkout that never runs `--install`, has no protection. The committed artefacts
that *do* protect every checkout regardless are the **brief convention**
(`Lane-owns:` lines, enforced by `lint`) and the **successor backstop**
(`lint.check_lane_containment_backstop`, #468) — neither of which depends on a
hook being wired.

**Trailer: `Needs: config`** — enabling is manual (a hook is machine-local
state), so the commit carries `Needs: config` per the repo convention. Not
`Feature:` because the guard does nothing until a human runs `--install`.

## Files

- `dev/lane_guard.py` — the guard + `--install` / `--uninstall` + the
  `pre-merge <branch>` subcommand (#468 R2, the merge-time assertion).
- `test_lint.py` / `lint.py` — `check_brief_lane_owns` (ERRORs a worktree brief
  that touches files but declares no `Lane-owns:`, so the guard always has a
  non-empty ownership set to protect), `check_lane_containment_backstop` (the
  ambient dirty-path ERROR, #468), and the shared `lane_owned_paths` reader, with
  the contract in `file-formats.md`.
- `file-formats.md` — the `Lane-owns:` line shape (same commit as the code that
  reads it).
- `SKILL.md` — the delegation paragraph gains one sentence stating the new
  obligation (a dispatched dreamer's brief carries a `Lane-owns:` line).
- `.dreamwork/docs/plans/lane-containment.md` — this design doc.
- `.dreamwork/docs/doc-map.md` — a row for this plan (added as a union; verified
  both ways against the directory).
