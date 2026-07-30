# Brief — #423: dead-runner signal — audit under the CURRENT dispatch paths

**Task:** #423 (P2, loop-tooling/orchestration) — `ccc @grok` 401'd three
times in one day (05:52→14:50, ~16:50, 17:45), and `nohup ccc … &` exits 0
on a 401: a dead runner looks exactly like a fast lane. The filing asks for
a dispatch-time probe and a lane-failed recording. **But the dispatch
topology has since changed**: this session dispatches via the Grok
harness's `spawn_subagent` (which reports completion/failure itself),
while the repo still documents and may again use `ccc` dispatch. This lane
is an AUDIT FIRST: what is live, what is moot, what is the minimal true
fix. **No production code without a reported finding the coordinator
accepts.**

**Lane-owns:** `.dreamwork/docs/findings/423-dead-runner-audit.md` (new),
and READ-ONLY everything else. If — and only if — the audit finds a
live defect with a small mechanical fix, you may also own the file that
fix lands in, named in your report BEFORE you implement it (stop and
report first if it would touch `watch.py` — lane-534sig owns a region).

## Questions the audit must answer (each with file:line evidence)

1. **Under `spawn_subagent` (the current path):** can a lane die silently?
   The harness returns a completion notification and
   `get_command_or_subagent_output` reports exit state; the coordinator
   also sweeps worktree git logs (a lane cannot land work without
   committing — #404). Is there a residual blind spot (e.g. a lane that
   never commits AND whose completion notice is missed)? Check how
   completion notices survive compaction — the session's own notes say
   "completion notices arrive late — sweep worktree git logs".
2. **Under `ccc` (the documented legacy path):** is the 401-exits-0 mode
   still reachable? `ccc-runner-routing.md`, `status_sync`'s liveness
   (#402a: pid-primary kill -0 + brief-path fallback), and any dispatch
   wrapper. Does anything TODAY probe a runner before trusting it, or
   record a lane that exited without committing as FAILED?
3. **The minimal fix, if any:** for each live gap, the smallest mechanism
   that closes it, with the seam named (e.g. a dispatch-time PONG probe
   for ccc; a "lane exited, zero commits, zero inbox writes → recorded
   failed" rule and WHERE that recording would live). An IGC over fix
   options if more than one is plausible (igc-method.md, bundled).
4. **Mootness verdict:** if the answer is "the current path cannot lose a
   lane silently and the ccc path is disused", that IS the finding — say
   it with evidence, and the task folds as moot-with-reasons rather than
   growing a mechanism nobody needs.

## Rules

- Read-only except the findings doc (and a fix ONLY per the gate above).
  No servers, no ports, no commits outside the doc.
- Every claim cites a file:line verified while writing. If a claim comes
  from a prior doc, re-verify it against current code — line drift is
  normal here.
- Work only in your worktree; commit the findings doc with
  `git commit --only`. Never `attn`, never `pkill -f`.
- Report: coordinator inbox (path in your dispatch prompt) + ONE literal
  `## Pending` line in your worktree's `.dreamwork/handoffs.md` (grammar
  in the file's header), committed with
  `git commit --only .dreamwork/handoffs.md`.

## Done when

The findings doc answers Q1–Q4 with citations; any proposed fix is named
with its seam and an IGC if options compete; the report and Pending line
are committed.
