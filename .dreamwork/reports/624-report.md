# #624 report — `--only` does not isolate lanes on a SHARED path

**Verdict:** FIXED with option 1 (brief instruction in `briefs/boilerplate.md`).

## What I changed and why

Added a rule to the Mechanics section of `briefs/boilerplate.md` (where every lane reads it) explaining that `--only` commits the path's **full current content**, so another agent's uncommitted edit to the **same** file gets swept. The victim's own `--only` then reports `nothing to commit, working tree clean` — which reads as failure but means "your write was already committed by someone else." The instruction: **CHECK whether your content is already on master before re-appending — re-appending creates a DUPLICATE the coordinator folds twice.**

The rule also notes that for `handoffs.md` specifically this is moot: `#687` made the coordinator its single writer, so no lane writes to it.

Commit: `1be79ec18916090f0f363f02d5234b1489f126e3` (post-rebase).

## IGC decision — chose option 1, gave up structural impossibility

Full analysis: `.dreamwork/reports/624-igc-analysis.md`.

**The critical discovery:** `#687` (merged `dc3ac7c3`) already made the coordinator the single writer of `handoffs.md` — the file the #624 entry names as "the one file every lane writes on master." Verified: every commit touching `handoffs.md` since dc3ac7c3 is authored by the coordinator (Max Kaye), not by a lane. **`#687` IS option 3 applied to handoffs.md.** The collision site is already structurally removed.

Option 3's cost (reworking `ledger.py`'s fold path, sequenced behind #627) is not repaid because the collision site it removes no longer exists. Option 2 (a lock) is off-limits (code in `watch.py`/`dev/`) and also unnecessary for a single-writer file.

**What I gave up:** option 1 holds by convention, not by construction. A lane that doesn't read the boilerplate, or panics at `nothing to commit` before checking, could still re-append. But the residual risk is a lane writing to some OTHER shared file — a much narrower risk than the original handoffs.md collision, which is already structurally gone.

## Direction 1 red-proof (discriminating assertion = the DUPLICATE, not the sweep)

**Discriminating message:** `lane-B lines on master: 2` (count > 1 = DUPLICATE).

**RED state** (instruction removed via `dev/redproof.py begin/restore`):
- Two agents append to the same file; lane-A's `--only` sweeps lane-B's line
- Lane-B sees `nothing to commit, working tree clean`
- Lane-B re-appends blindly (no instruction to check)
- **DUPLICATE: count = 2**

**GREEN state** (instruction present):
- Same setup, but lane-B checks master before re-appending (per the instruction)
- Lane-B's line IS found on master (swept by lane-A's `--only`)
- Lane-B does NOT re-append
- **NO DUPLICATE: count = 1**

`dev/redproof.py check` output:
```
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  briefs/boilerplate.md (sha 5422d3087041, hint: "and you would pop another lane's work.")
```

## Direction 2 red-proof (false-green analysis)

**Candidate 1 — two lanes appending identical lines:** B's check finds the line, does not re-append. The duplicate (count=2) comes from A's sweep of B's identical line, not from B's re-append. B cannot distinguish "mine was swept" from "A's identical line is there," but for identical content one copy is the correct end state regardless of provenance. **True-green with indistinguishable provenance, not a false-green.** The check prevented a TRIPLE.

**Candidate 2 — append swept after check (TOCTOU):** **Not constructable through the `--only` mechanism alone.** `nothing to commit` is itself proof that the working tree matches HEAD for that path — someone already committed the exact bytes. The check operates in a window where the line is GUARANTEED to be on master. Demonstrated: if B tries `--only` before any sweep, the commit SUCCEEDS (exit 0); `nothing to commit` only fires after the sweep. No TOCTOU window exists in the normal flow.

**Conclusion: no false-green constructable through `--only` alone.** The "nothing to commit" message is itself proof the line is on master, making the check instruction redundant with the mechanism — it's belt-and-suspenders that prevents the panic-reappend.

## Cited issues with relied-on lines

- **#136** — "present-but-unparseable is a fault and must look like one": the same class as `nothing to commit` being a message that reads as failure but means something else.
- **#671** — "420 commits examined, 177 open ids never seen": a check that examines nothing confidently reading as a positive all-clear — the pattern `nothing to commit` follows.
- **#440** — "a single supported way to fold an entry": the one-supported-way rule; the fix is a mechanism, not a second convention.
- **#652** — "the agent scratchpad is SHARED between concurrent lanes": lane-private state is the shape option 3 generalises; #687 already applied it to handoffs.md.
- **#687** — "lanes write the report to the absolute inbox.md and nothing else. The coordinator writes the hand-off line, from the report, when it merges.": the ownership ruling that already removed the collision site.
- **#612** — "land your change as the fewest lines that carry the meaning": the instruction is 6 lines appended to an existing section.

## Rebase outcome

Master moved 6 commits since dispatch. Rebased cleanly, no conflicts. Post-rebase sha: `1be79ec18916090f0f363f02d5234b1489f126e3`. Lint passes (exit 0).

## Out of scope (not fixed, name it)

1. **`lint.py` has a briefs check that verifies briefs mention `.dreamwork/handoffs.md`** (`check_brief_handoff_obligation`). My boilerplate change already mentions it, so the check passes. But the check's substring test for "do not touch handoffs.md" is the kind of string-match that `#699` warns about — a token is not a statement. Worth verifying the check actually binds the ownership rule, not just the mention.

2. **The #624 entry itself still says "the one file every lane writes on master"** — that was true pre-#687 but is now stale. The entry's framing predates #687's ruling. Consider updating the entry's note to reflect that #687 already removed the collision site.

## Dogfood report

1. **The brief's IGC path was wrong for this harness.** It says read `/home/xertrov/.claude-p/skills/ud-dreamwork/igc-method.md`, but the boilerplate's own standing rule (line ~126) correctly says to use `./igc-method.md` in the worktree. The brief head and the boilerplate contradict each other on this path. The boilerplate is right; the brief head cost one wasted read.

2. **The brief's red-proof section references `dev/redproof.py` but the boilerplate's version is the canonical one** — the two are slightly different in wording. Not a real problem, but the duplication means future corrections have two places to update.

3. **The task entry (#624) is stale relative to #687.** It describes handoffs.md as "the one file every lane writes on master" and lists option 3 as "the only one that makes the collision impossible" — but #687 already did that. A lane that doesn't check #687's merge date would re-derive the pre-#687 world and might choose option 3 unnecessarily. The entry should note that #687 already removed the primary collision site.
