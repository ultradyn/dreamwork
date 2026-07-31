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

## Direction 1 — the exposure, then the same branch refused

Built on a **fixture branch** in a throwaway repo under the lane-private
scratch (`#652`), never a live lane branch and never master: `begin` →
`return true` becomes `return false` → **commit while sabotaged** → `restore` →
commit the real fix. Byte-exact, not asserted:

    blob at the poisoned commit:  export function route() { return false; }
    sha1 of that blob:            6c8321936fc23bc6504ce40caf149822a10c326a
    recorded injected_sha:        6c8321936fc23bc6504ce40caf149822a10c326a

**Pre-fix `check`, on that branch, working tree clean:**

    check: clean — 1 injection(s) registered, all restored and absent from the working tree.
    exit=0

**Post-fix `check`, same branch, same registry:**

    check: REFUSED — the working tree is clean, but 1 commit(s) on this branch
    still hold a recorded injection:
      a08aab1bc747 router.js — 'wip(#710): mid red-proof'
        (hint: 'export function route() { return false; }')
    Committing mid-injection is correct — COMMIT INCREMENTALLY exists because
    lanes get killed without warning — but the branch cannot merge as it stands
    … Tell the coordinator to SQUASH this branch at merge … #710
    history: examined 2 commit(s) since 12bebfc9ece8 (master) against 1 injected
    path(s); read 2 blob(s), 1 holding a recorded injection.
    exit=1

Then three injections into the fix itself, via `dev/redproof.py`, each restored
and verified (`git diff --stat dev/redproof.py` empty after each):

| Injection | What broke | Discriminating red |
|---|---|---|
| `rev-list base..base` (an empty range — the brief's named trap) | scan examines nothing | `assert rep["commits"] == 2` → `AssertionError: {…'blobs_read': 0, 'commits': 0…}`; and the clean-branch test's `assert "examined 1 commit" in out` |
| drop `sha == e["injected_sha"]` from the match | every blob counts as a hit | clean branch refused (`assert exit == 0` → `1 == 0`), and the refusal names the *clean* commit too: `assert '336c0d2bdf92' not in …` |
| `_resolve_base` returns HEAD instead of raising | a scan with no range reads as a pass | only failure in the suite: `assert exit == 2, err` → `assert 0 == 2` |

The first is the important one: **the precondition assertions caught it, not the
verdict.** A scan of an empty range produces no refusal *and* no false
refusal — exactly the shape that reads as a clean branch — so the tests derive
`commits` and `blobs_read` at runtime and assert both.

## Direction 2 — two branches the check still gets wrong, both executable

Kept as *passing tests asserting the wrong answer*, so that closing either one
fails loudly instead of quietly (`TestKnownHole`):

1. **A fork point moved past the injection.** The range is
   `merge-base(base, HEAD)..HEAD`. If the branch is merged and the lane keeps
   working on it, the poisoned commit sits behind the new merge-base: the scan
   sees only the newer commits and passes, while the test asserts
   `git merge-base --is-ancestor <poisoned> master` succeeds — master already
   holds it. `--base <ref>` widens the range by hand; nothing widens it
   automatically. This is the brief's own predicted candidate and it is real.
2. **Edits between the sabotaged commit and `restore`.** The comparison is
   whole-file byte-identity with the state `restore` observed, so a lane that
   keeps editing the file after the sabotaged commit makes `restore` record
   bytes no commit holds. The test asserts the defect *is* in the commit
   (`"return false" in <blob>`) while `rep["hits"] == []`. Mitigated by the
   protocol rather than by the code: `restore` copies the original over the
   file, so those edits would be destroyed anyway.

Not closed, and named rather than hidden: **a lane that never calls `begin` is
invisible**, inherited whole from `#683`'s opt-in design. That is the gap `D`
(universal squash) would have covered, which is why rejecting it was
reluctant.

## Verification

`python3 -m pytest -q -p no:randomly test_redproof.py test_lane_scratch.py`,
output written to a file and counted from the file rather than from a reported
exit code: **`37 passed`**, `0` lines matching `^(FAILED|ERROR)`. 20 of those
are `test_redproof.py` (14 pre-existing, 6 new). `python3 lint.py` → `clean
(6 warning(s))`, all six the standing lane-worktree ledger-store warnings
(`#611`). No browser guards: non-UI change (`#666`).

Hand-off gate, after the rebase:

    history: examined 4 commit(s) since 40ed9667d028 (master) against 1 injected
    path(s); read 4 blob(s), 0 holding a recorded injection.
    check: clean — 1 injection(s) registered, all restored and absent from the
    working tree and from this branch's commits.

## Cited issues, with the line relied on

- **`#683`** — *"A lane that never calls `begin` is invisible to the tool
  (point 3). The check is opt-in by design"* (`dev/redproof.py` docstring, and
  the entry's landing note). The limitation the scan inherits.
- **`#671`** — *"the count is real (420 commits WERE examined), the 'nothing to
  review' is false, and the two together read as a positive all-clear."* Why
  the scan FAULTs on an unresolvable base instead of reporting an empty range.
- **`#590`** — I read the entry and it is a backlog re-rank; the rule the brief
  attributes to it lives in `#671`'s account of it: *"`#590`
  (folded-but-unmerged, found by hand this session) is what the gap looks like
  when it bites"*, and *"`#590`'s landing subject is the bare `#N:` form, which
  `SWEEP_SUBJECT` cannot match at all — so sweep could never have found it for
  a different reason than I gave."* That is the zero that meant "did not look",
  and it is what the scan's examined-counts exist to prevent. Flagged because
  a future reader chasing `#590` for it will not find it there.
- **`#652`** — *"EVERY lane brief in this repo tells the lane to snapshot files
  OUTSIDE the repo … If two concurrent lanes snapshot with colliding names …
  one lane's restore can write ANOTHER lane's content over its file."* The
  fixture repo and its registry both live under `dev/lane_scratch.py`'s derived
  private dir.
- **`#612`** — *"land your change as the fewest lines that carry the meaning"*
  (boilerplate). One capability, no new verb, no new registry field, no new
  file.
- **`#349`** — *"Revert a deliberate RED injection with the inverse of the
  injection, never with `git checkout <file>`"* (`lessons.md:757`). Used
  literally once tonight, see the dogfood report.
- **`#400`** — *"The lessons that reach a lane are the ones I hand-copy into
  its brief, and nothing else does."* Why `E` (prose only) is refuted and why
  the boilerplate paragraph describes the tool's refusal rather than asking for
  a habit.
- **`#686`** — *"a lane that commits nothing is invisible to `sweep`"*; the
  standing evidence that per-increment commits are load-bearing, which is half
  of G4's argument against universal squash.

## Out of scope, found not fixed

- **`begin` cannot tell an armed file from an already-sabotaged one.** If a
  lane sabotages first and calls `begin` second, the "original" snapshot *is*
  the sabotage, and `restore` will faithfully restore the defect while printing
  a success line. I did this to myself tonight (dogfood below). A `begin` that
  warned when the file already differs from `HEAD` would have caught it in one
  line — but that is a fifth behaviour on a tool the brief scoped to a fifth
  *capability*, so it is named here rather than built.
- The `#611` lane-worktree ledger warnings (six of them) fire on every lane
  lint and are pure noise from a worktree; unrelated to this task.

## DOGFOOD REPORT

**1. `redproof.py begin` has no idea whether the file is already sabotaged, and
I fell in.** Doing my second injection I ran the sabotage edit *before*
`begin`, so `begin` snapshotted the sabotaged file as the "original" and
printed its normal success line. Had I then run `restore`, it would have
restored the defect, verified it byte-for-byte, printed
`original restored & verified`, and `check` would have passed — the tool
turned into a machine for installing the injection permanently, with a green
receipt. I caught it only because I re-read my own shell block. I recovered
with the `#349` inverse edit and `git diff --stat` (empty), then `forget` to
drop the poisoned snapshot. This is the `#704` sequencing failure wearing a new
hat: `#704` was "snapshotted too early", this is "snapshotted too late", and
the tool's docstring argues it cannot make the `#704` mistake *by
construction* — which is true and does not cover this direction. One line in
`begin` comparing the file to `HEAD` and warning when it already differs would
have caught it. Named in "out of scope" above; worth filing.

**2. The boilerplate's red-proof block shows the protocol as four lines in
order, and the order is the only thing protecting you.** `begin` before the
sabotage is load-bearing in a way nothing on the page says out loud — it reads
as bookkeeping. Consider one clause: *"`begin` first: it snapshots what is
there now, so a `begin` after the sabotage snapshots the sabotage."*

**3. The brief was right about the trap and it earned its place.** "A history
scan that finds no injections because it looked at the wrong commit range is
indistinguishable from a clean branch unless you make it distinguishable" is
exactly what injection 1 reproduced, and the precondition assertions are the
only reason it went red. Without that sentence I would probably have asserted
the refusal and stopped.

**4. Small: `lint.py` from a lane worktree prints six WARNs about ledger checks
that examined nothing, every run.** Correct behaviour (`#611`) and correct
wording, but as a lane I cannot act on any of them, and after the third run I
was skimming past the whole tail — which is the `#592`/`#612` tune-out failure
arriving by repetition rather than by size. A one-line "in a worktree; lint the
main checkout" summary in place of six rows would keep the signal.

**5. `just pytest -q <files>` does not work** — the recipe takes no arguments,
so `just pytest -q test_redproof.py` fails with
`error: Justfile does not contain recipe '-q'`. The boilerplate names that
exact invocation as a lane's verification. I used
`python3 -m pytest -q -p no:randomly <files>` instead. Either the recipe should
forward `+ARGS` or the boilerplate should stop naming a form that cannot run.
