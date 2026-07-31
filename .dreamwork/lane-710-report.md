# Lane report — `#710`: an injection committed mid-branch survives a tree-only gate

## The decision, by IGC

**Context.** A lane works in a worktree on a branch cut from `master`, and the
boilerplate orders it to COMMIT INCREMENTALLY because four lanes were killed
mid-flight on 2026-07-31 with no error in any log. Red-proofing means the tree
is *deliberately broken* for minutes at a time, and that is exactly when a lane
has done expensive irreplaceable work. `dev/redproof.py check` — the hand-off
gate the boilerplate makes mandatory — inspects the **working tree**, so a lane
that injects, commits while sabotaged, restores and commits again hands back a
clean tree over a poisoned history. The coordinator merges without squashing
(`briefs/boilerplate.md`: *"the coordinator squashes nothing and reads your
history"*), so that commit becomes reachable from `master` permanently.

**Goals** (binary; each can refute on its own):

- **G1 — crash-safety survives.** A lane may commit at any moment, including
  mid-injection, without being told to wait. Nothing in the fix reduces the
  window the incremental-commit rule protects.
- **G2 — no injected state reachable from `master`.** After the branch is
  merged, no commit reachable from `master` holds the injected bytes.
- **G3 — enforced by something other than a lane's memory.** `#400` measured
  that lanes read what is in front of them and little else, so a rule whose
  only enforcer is a future lane remembering it is refuted.
- **G4 — the coordinator keeps the lane's increments.** It reads lane commit
  history at the gate deliberately, and `boilerplate.md` promises no squash.
- **G5 — a zero is distinguishable from "did not look."** `#671`/`#590`.
- **G6 — volume.** A fifth capability at most, no policy engine (`#612`).

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|:--:|
| **A** — history scan at the gate (extend `check`) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **B** — self-identifying injected commits (marker file / message trailer) | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ | ✔ |
| **C** — `restore` rewrites history (amend / autosquash) | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ | ✘ |
| **D** — squash-merge every lane branch | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ |
| **E** — a rule in `briefs/boilerplate.md` and nothing else | ✘ | ✔ | ✘ | ✘ | ✔ | ✘ | ✔ |

### The decisive errors

**B ✘ G2, ✘ G3 — nothing the tool controls is guaranteed to enter the commit.**
Lanes commit with `git commit --only <paths>` (boilerplate, and it is mandatory
because concurrent lanes share the index). A marker file written by `begin`
into the worktree is simply *not in* a `--only` commit unless the lane names it
in the pathspec — so the mark is absent from precisely the commit it exists to
mark, and its absence reads as "not sabotaged". Move the mark into the commit
*message* and it becomes a thing the lane must remember to type, which is `E`
with extra steps. B's attraction — "a scan is then trivial and reliable" — is
real, but reliability is the property it does not have.

**C ✘ G1 and ✘ G2 — the remedy only runs in the world where the crash did not
happen.** The whole reason the poisoned commit exists is that the lane might
die before restoring. A `restore` that rewrites history repairs the branch
*only if the lane survives to call `restore`* — in the crash case, which is the
case the commit was made for, C does nothing at all and the poison stands. And
the cost of the half that does run is a mid-lane `commit --amend`/rebase, which
rewrites commits the coordinator may already have read, and is the same hazard
class as `git checkout`-to-restore (`#349`): a rewrite that silently takes
neighbouring work with it. It buys nothing in the crash case and adds a hazard
in the healthy one.

**E ✘ G3 — `#400` is the measurement that refutes it.** *"The lessons that
reach a lane are the ones I hand-copy into its brief, and nothing else does."*
A prose rule about a state that is invisible at hand-off (the tree is clean —
that is the whole defect) is the weakest possible enforcer of the least visible
failure.

**D ✘ G4 — and this is the one I reject most reluctantly.** See below.

**A ✔ on all six**, and its G2 needs stating precisely, because a *detector*
does not by itself remove anything: the scan refuses the hand-off and **names
the commits**, and the remedy it prints is a targeted squash of that one
branch. That is the resolution of the brief's tension rather than a dodge —
detection converts D from a policy that costs every lane its history into a
remedy applied only to branches that provably need it.

### The option I reject most reluctantly: D, universal squash-merge

D is the human's own lean and it is the **only** candidate that passes G3
against the case none of the others touch: **a lane that injects by hand and
never calls `begin`.** A registry-driven scan cannot see an injection it was
never told about — `redproof.py`'s docstring already concedes this (*"A lane
that never calls `begin` is invisible to the tool"*), and my scan inherits the
limitation whole. D does not care: it removes the exposure at the merge
boundary for registered injections, unregistered injections, and every failure
mode nobody has thought of yet, because it never has to *detect* anything. That
is a categorically stronger kind of safety than detection, and I am giving it
up.

What refutes it is G4, and G4 is not a nicety. The coordinator reads lane
commit history at the gate; `boilerplate.md` tells every lane *"the coordinator
squashes nothing and reads your history"*, and lanes write their history for
that reader — a `WIP: measured X, Y still open` commit is explicitly named as a
deliverable in its own right. `#686` is the loop's standing evidence that
per-increment commits are load-bearing evidence, not bookkeeping: it exists
because a lane's *absence* of commits was the only signal that its work was
abandoned. Squashing every branch discards the intermediate states from
`master` permanently — and the intermediate states are what `git bisect` and
`git blame` are *for*, which is the same argument `#710` makes against leaving
the poison in. Paying for a poisoned-history problem with a
flattened-history problem is not obviously a trade at all; it is the same
currency.

So D survives as the **remedy** rather than the policy: when the scan refuses,
squashing that branch is the recommended fix, and the refusal message says so.
Universal squash stays refuted; targeted squash is what the check prescribes.
It also stays available if the unregistered-injection case ever bites for real
— at which point the argument reopens with evidence instead of a prediction.

## What changed

`dev/redproof.py` — `check` grows a history scan (`scan_history`), the only new
capability. For every entry that `restore` recorded, the scan reads the bytes
each commit on this branch actually holds for that path and compares the sha to
the recorded injected sha. An exact whole-file match is the signal, which is
neither a heuristic nor tunable: it is byte-identity with a state the tool
itself observed. That is also well matched to the protocol, because `restore`
records the working tree at restore time and copies the original back over it —
so in the sequence `#710` describes (commit while sabotaged, restore, commit
again) the committed blob *is* the recorded injected blob.

Range: `merge-base(<base>, HEAD)..HEAD`, base defaulting to `master` then
`main`, overridable with `--base`. Refusal names the commit, its subject, the
path, and the remedy.

Volume: +1 verb-less capability, no new registry fields, no new files.

## Both directions of the red-proof

(filled in below by the lane — see "Red-proof" section)
