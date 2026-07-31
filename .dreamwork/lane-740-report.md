# Lane 740 report — redproof worktree confinement

## Verdict

Fixed. `begin`, `restore`, and `forget` now resolve their input against the
resolved worktree root and refuse any candidate outside it. The same helper is
used by `_read_wt`, so `check` fails closed on unsafe paths left in a legacy or
tampered registry. `restore` resolves again immediately before its copy, and
`.dreamwork/lessons.md` still survives the complete begin → restore → check
round trip with its leading dot intact.

Commits after rebasing onto local `master`:

- `9bba61a4` — `test(#740): pin worktree path confinement`
- `29030329` — `fix(#740): confine redproof paths to worktree`
- `a05d69b5` — `test(#740): prove outside bytes stay untouched`

## Design call

I chose resolve-and-contain, not lexical normalisation. `_worktree_path` uses
`root.resolve(strict=True)`, resolves the candidate with `strict=False`, and
requires `candidate.relative_to(root)` to succeed. It returns the canonical
repo-relative key and the resolved I/O path.

That choice earns two properties lexical normalisation does not: an in-tree
symlink pointing outside is refused, and a legal file replaced by such a
symlink between `begin` and `restore` is refused when `restore` revalidates it.
`strict=False` deliberately preserves the existing distinction between a
missing contained file (`does not exist in the working tree`) and an escape
(`outside the worktree`). Canonical keys also keep `..` out of snapshot paths
and make in-tree symlink aliases refer to the bytes actually operated on.

This is not claimed to defeat an active filesystem race between the final
resolve and `shutil.copyfile`; closing that stronger TOCTOU threat requires
descriptor-relative I/O such as `openat2`, which would exceed this containment
fix's narrow scope.

## Red-proof

Direction 1 used the worktree's own tool:

1. `python3 dev/redproof.py begin dev/redproof.py`
2. Injected `relative = Path(posix)`, making containment accept the escape.
3. Ran the exact parent-escape test. It failed at the discriminating assertion:
   `assert 0 == 2` in
   `test_every_path_entry_point_names_and_refuses_an_escape[parent-begin]`.
4. `python3 dev/redproof.py restore dev/redproof.py` restored the fixed snapshot
   and verified byte identity.

The fixed live refusal names both the path and reason:

> `begin: REFUSED — path '../victim.txt' resolves outside the worktree (...)`

Direction 2 constructed both bypass candidates rather than reasoning from the
helper: `link.txt` is an in-worktree symlink to an outside sentinel, and
`router.js` is legal at `begin` then replaced by an outside symlink before
`restore`. Both are refused with `outside the worktree`, and sentinel bytes are
asserted unchanged. A seeded legacy registry path `../victim.txt` also makes
`check` exit 2 with the same discriminating reason. No deterministic confined
input remained false-green; the concurrent symlink-swap race described above
is the honest residual.

The required hand-off gate said:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:`

## Verification

- `python3 -m pytest test_redproof.py` — **36 passed** in 3.34s after the
  required rebase.
- `python3 lint.py` — **clean (6 warning(s))**. The warnings are the expected
  worktree/store and pre-existing questions/lessons warnings; there were no
  ERRORs.
- Rebased cleanly onto local `master` after it advanced by seven commits; no
  conflicts.

## Issue evidence read

- #740: “Prefer the resolve-and-contain form — it is the one that survives
  symlinks.” This is the design criterion the implementation binds.
- #726: “`str.lstrip` takes a CHARACTER SET, not a prefix”; therefore
  `_to_posix(...).removeprefix("./")` remains unchanged, and the explicit
  `.dreamwork/lessons.md` round trip guards it.
- #136: “present-but-unparseable is a fault and must look like one”; the new
  unsafe-registry test similarly requires exit 2 and an escape-specific message.
- #671: a tool that examined nothing and reported an all-clear was “the worst
  of both”; refusal tests therefore assert the path and reason, not only a code.
- #349: “Revert a deliberate RED injection with the inverse of the injection,
  never with `git checkout <file>`”; `redproof restore` performed the copy and
  byte verification.
- #425 discusses symlink-target-relative resolution (`__file__` can see the
  symlink target's directory), but does not literally state an
  “abspath/realpath distinction.” I did not rely on that stronger paraphrase;
  the symlink tests directly justify resolve-and-contain.

## Out of scope

- The final resolve-to-copy TOCTOU window remains as described above. It is an
  active-adversary hardening problem, not the confirmed accidental escape.
- No browser guards were run, per the lane brief and #666 load constraint.

## DOGFOOD REPORT

One brief-evidence mismatch cost a small verification pass: #425 supports
symlink-aware path resolution, but the ledger text does not literally establish
the stated “abspath/realpath distinction.” The implementation decision was still
clear from the confirmed reproduction and symlink red-proof. Otherwise no
friction found: the absolute ledger command, worktree-local redproof command,
snapshot/restore gate, two-thread instruction, and expected lint-warning bar
were all precise and usable.
