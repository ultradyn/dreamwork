# #608 — the red-proof recipe backs up the WRONG state

Dogfood report and analysis for the red-proof snapshot/restore ordering bug.
Direction 1 and Direction 2 demos are reproducible shell scripts; the key
output lines are quoted below. The demos ran in `/tmp` (lane-private scratch,
outside the repo) and are re-runnable from the quoted scripts.

## Direction 1 — following the CURRENT wording loses a fix (cmp green)

The wording under test (lessons.md:757, echoed in the boilerplate):
> take a `cp` backup first, revert the production line, watch the test go red,
> restore by `cp`, confirm byte-identical with `cmp`

Read literally, the backup is taken BEFORE the fix is written, so restoring
returns the pre-fix file and the fix is silently undone. `cmp` then certifies
byte-identity with the wrong file.

Reproduced (the script is the one above, abridged to the verdict lines):

```
### STEP 1 — 'take a cp backup FIRST' (literal reading: before writing the fix)
backup captured. backup has the guard? 0 (expect 0 = pre-fix)

### STEP 4 — 'restore by cp' from the backup
guard present after restore? 0 (expect 0 = FIX LOST)

### STEP 5 — 'confirm byte-identical with cmp'
cmp: BYTE-IDENTICAL -> certified green

### RESULT — the verdict cmp just certified
ZeroDivisionError: division by zero
(exit 1)

cmp said GREEN, but the check now FAILS: the restore returned the PRE-FIX backup,
silently undoing the fix. A false green with a green cmp behind it (#608).
```

The discriminating signal: `cmp` reports `BYTE-IDENTICAL` while the check
throws `ZeroDivisionError`. A lane reading only the `cmp` line ships a no-op.

## Direction 2 — the NEW wording followed correctly, still fooled

The brief's candidate cases: (a) unrelated mid-session edit to the same file;
(b) a fix spanning two files where only one is snapshotted; (c) a snapshot
made stale by a rebase. Case (a) reproduces and is the sharpest:

```
### STEP 2 — snapshot the FIXED file (NEW wording: snapshot the fixed state)
snapshot has the fix? 1 (expect 1)

### STEP 3 — UNRELATED edit to the same file (a docstring, mid-session)
calc.py now has docstring? 1 (expect 1 = the unrelated edit is LIVE)

### STEP 5 — restore from the snapshot
fix present after restore? 1 (expect 1 = fix preserved)
docstring present after restore? 0 (expect 0 = UNRELATED EDIT LOST)

### STEP 6 — confirm byte-identical with cmp
cmp: BYTE-IDENTICAL -> certified green
```

The NEW wording fixes the ordering (the fix survives), but the snapshot is a
whole-file capture; restore returns the whole file, silently reverting the
unrelated docstring. `cmp` certifies identity with the snapshot, which never
knew about the docstring. **The recipe is silent on this**, and it cannot be
closed by rewording alone — it is a property of whole-file snapshot/restore.
Filed, not closed: a sentence in the recipe is the proportionate fix (#612),
not a mechanism.

Cases (b) and (c) are real but lower-hit-rate and belong to the same class:
the snapshot is of one moment of one file, and anything that diverges from
that moment in that file (or anything in a second file) is clobbered or
missed. Worth naming, not worth building for.

## Argument: point at `dev/redproof.py`, or keep the manual recipe?

The boilerplate **already** points at `dev/redproof.py` — the
`begin`/`restore`/`check` recipe is the front-and-center instruction. The
manual `cp`/`cmp` dance survives only as (a) the fallback sentence in the
boilerplate ("Never `git checkout`; `restore` copies from the snapshot and
verifies") and (b) the historical record in `lessons.md:757`.

`#440`'s one-supported-way rule argues for the tool as the single path, and
the tool cannot get the ordering wrong: `begin` snapshots whatever it is
called on, and the check verifies the working tree does not match the
recorded *injected* state — so a lane that `begin`s the fixed file, sabotages,
and restores ends on the fixed file by construction. The manual recipe has no
such guard; its correctness depends entirely on the lane reading "backup"
as "the fixed state", which is the reading the bug is made of.

**Conclusion: the manual recipe must stay documented, but only as what the
tool automates — not as an alternative.** It stays because (1) the coordinator
does inline red-proofs without the tool's registry, and (2) `lessons.md:757`
is the historical record of the `#349` incident and rewriting it would pretend
the manual dance never existed. Its wording is fixed so a lane following it
literally snapshots the FIXED file, not the pre-fix one.

## The fix (both places)

1. **`briefs/boilerplate.md`** — the `begin` comment now names the FIXED
   state ("snapshot the file in its FIXED state"), and one sentence states
   the ordering rule: snapshot what you intend to END on, then revert, then
   restore returns it.
2. **`lessons.md:757`** (the retrieval path) — the manual recipe now reads
   "snapshot the FIXED file, then revert, then restore from that snapshot"
   rather than "take a `cp` backup first". The `#349` narrative is preserved;
   only the prescription is corrected.

`SKILL.md:580` is about *where* to snapshot (lane-private dir), not *when*,
and does not carry the ordering bug — left untouched. The lint-pinned phrase
`names a lane-private snapshot directory` is kept contiguous.
