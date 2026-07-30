# Brief #460 — replay the task_event .jsonl, reconstruct the DB

**Task** (ledger #460, P3, origin **human**, his answer to #264 Q2):
*"write a tool to process this and reconstruct the DB. that way we know
it'll work + we can run tests against fixtures and ensure determinism,
etc. that will at least allow us to set a consistent rule for how to
merge event streams."*

**Why it exists (his words, and they are the acceptance bar):** *"that
way we know it'll work"* — a log nobody has replayed is a backup nobody
has restored. This tool is also the **falsifier for #264's "capture
enough detail"**: if replay cannot rebuild the DB from the live log
schema, that is a finding about #294's journal, not about your tool —
report it as such, do not patch around it silently.

## Scope

One tool + one test file, no watch.py, no browser, no guards.

1. **The replay tool** (`dev/replay_events.py`, stdlib-only like the
   rest of `dev/`): reads a `task_event` `.jsonl` log (the format is
   documented in `file-formats.md` — read that first; the writer is
   `user_events/`), applies the events in order, and reconstructs the
   SQLite store. Reuse `user_events/` primitives for the apply path —
   the #352 anti-duplication rule: ONE applier, and the replay tool
   rides it rather than restating event semantics. If a primitive gap
   exists (as #497 found in `ledger_parse`), fill it in `user_events/`
   and say so.
2. **Determinism**: same log → byte-identical DB. Test: replay the same
   fixture log twice, compare bytes. If SQLite internals make exact
   bytes infeasible even for identical operation sequences from an empty
   image, measure it, document precisely why, and assert the strongest
   honest invariant instead (logical dump equality) — but try bytes
   first; identical op sequences on an empty image should produce them.
3. **Round-trip fidelity (the falsifier)**: build a DB through the real
   `user_events` apply path on a fixture, take its journal, replay the
   journal into a fresh DB, assert the two DBs hold the same rows
   (logical comparison; byte comparison too if it holds). A failure here
   means the journal does not capture enough — name the missing field
   in your report as a #294 finding.
4. **The merge rule**: state ONE consistent rule for merging two event
   streams (the future dreamhub multi-agent case), as a documented
   function or a documented ordering the tool implements
   (`--merge a.jsonl b.jsonl` or similar). Deterministic total order,
   stated tie-break, tested on two interleaved fixture streams. Keep it
   minimal — this is a rule with a test, not a feature.

## Hard contracts

- **Red-first.** Every test names the production line that would have
  to change for it to fail; sabotage one (a line you did NOT inject is
  the coordinator's independent red — yours is the feature red), watch
  it fail, cp-restore byte-identical. Assert preconditions the check
  depends on (the fixture journal really contains ≥2 event kinds,
  really reconstructs N rows — derive at runtime).
- **Coordinator-owned, do not edit**: `file-formats.md`, `lint.py`,
  `watch.py`, `watch-design.md`, `transitions.md`, `justfile`. If
  `file-formats.md`'s journal contract is wrong or incomplete against
  the real writer, that is a FLAG in your report with the corrected
  text — the coordinator lands it.
- **No image reads** (glm-5.2 API 400 kills the lane). No browser work
  at all in this lane.
- **ONE `.dreamwork/handoffs.md` `## Pending` line** before your final commit (#398
  obligation). **`git commit --only <paths>`**; new files need
  `git add` first.
- Verification: your new tests green, full `python3 -m pytest test_lint.py -q`
  green, `python3 lint.py` clean (the fresh-clone tasks.md `Next id:`
  ERROR in a worktree is benign).

## Lane-owns

You own: `dev/replay_events.py` (new), `test_replay_events.py` (new),
any primitive gap-fill in `user_events/` (surgical, justified), your
handoffs line. Nothing else. Two other lanes are in flight in
`watch.py` (burndown, reviews) — you have no reason to touch that file;
if you find one, stop and report instead.

## Report shape

Commits; the determinism + fidelity evidence (hashes/counts); the merge
rule stated in one paragraph; red-proof evidence (sabotage, failing
check, restore hash); any #294 journal-schema finding (this is a
success outcome, not a failure); FLAGs for coordinator-owned files;
deviations with reasons.
