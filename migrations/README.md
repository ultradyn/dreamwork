# Migrations

Update-detection protocol for targets running under an older skill state.

- One dated file per change that **affects existing targets** — state
  shape, conventions, loop behavior. Routine skill edits don't get one.
- The **latest migration filename is the skill's version** — latest by
  plain lexicographic sort, which the naming scheme makes chronological:
  same-day entries carry a two-digit ordinal (`YYYY-MM-DD-NN-slug.md`).
  Targets record the version they last ran under in
  `.dreamwork/skill-version`; that recorded filename is authoritative
  for where a target stands. (Pre-ordinal version files may hold an old
  `YYYY-MM-DD-slug.md` name — match it by slug to find its position.)
- At initialization (orient), compare the target's recorded version with
  the latest entry here. Behind → read the intervening entries, apply
  what's relevant (create missing files, adjust conventions), bump
  `.dreamwork/skill-version`. Ask the human only when a migration
  genuinely needs their call. Nonintrusive: no network, no ceremony, a
  mismatch is information, not an alarm.

Maintainer rule: any change to state shape or loop-visible behavior ships
with a migration entry in the same commit.

Entry format: `YYYY-MM-DD-NN-slug.md` (NN = same-day ordinal, 01-first) —
two sections: **What changed** and **How to apply**.
