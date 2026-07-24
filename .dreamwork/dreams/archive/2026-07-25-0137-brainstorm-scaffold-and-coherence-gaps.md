# Dream — brainstorm dispatch, scaffold + coherence observations

Dispatched to brainstorm 3-6 candidate ideas. Beyond the idea list, three
things stood out while reading the skill:

1. **`.dreamwork/` does not exist yet.** `initialization.md` step 7 tells the
   loop to read `.dreamwork/docs/`, and the dream-file protocol has dreamers
   write `.dreamwork/dreams/<file>` — but nothing creates these directories.
   I had to `mkdir -p .dreamwork/dreams` just to drop this file. First-run
   friction that directly undercuts "leave it dreaming and it just works."
   (This feeds candidate idea A — scaffold `.dreamwork/`.)

2. **The whole skill is uncommitted.** Only an `init` commit exists; SKILL.md
   is modified and DREAMWORK.md / initialization.md / DREAMWORK.template.md are
   untracked. A real reconcile step (initialization #8) would flag this dirty
   tree as unfinished prior work before dreaming. Not my job to touch — noting
   it because the coordinator's first move after any brainstorm should be to
   reconcile/commit, not stack more changes on an uncommitted base.

3. **This target has no automated tests — its "test suite" is a coherence
   re-read.** DREAMWORK.md says so explicitly (Preferences & Routines), yet
   SKILL.md / initialization.md speak of "run the tests" and a "green
   baseline" as if automated. For this self-hosted target those instructions
   are aspirational; the loop should read "run the tests" as "coherence
   re-read of SKILL.md + initialization.md." Mild self-referential mismatch
   worth keeping in mind when judging what "verifiable increment" means here.

None of these are blockers; they're context for choosing/ordering the ideas.
