# Migrations

Update-detection protocol for targets running under an older skill state.

- One dated file per change that **affects existing targets** — state
  shape, conventions, loop behavior. Routine skill edits don't get one.
- The **latest migration filename is the skill's version**. Targets record
  the version they last ran under in `.dreamwork/skill-version`.
- At initialization (orient), compare the target's recorded version with
  the latest entry here. Behind → read the intervening entries, apply
  what's relevant (create missing files, adjust conventions), bump
  `.dreamwork/skill-version`. Ask the human only when a migration
  genuinely needs their call. Nonintrusive: no network, no ceremony, a
  mismatch is information, not an alarm.

Maintainer rule: any change to state shape or loop-visible behavior ships
with a migration entry in the same commit.

Entry format: `YYYY-MM-DD-slug.md` — two sections: **What changed** and
**How to apply**.
