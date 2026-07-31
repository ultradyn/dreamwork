# Lane #766b report — persist validated briefs in the dispatch wrapper

## Verdict

Shipped the handed design, with a dispatch-time SHA-256 receipt answering the
uncommitted integrity window.

`dev/dispatch_lane.py` now performs one ordered operation: validate the exact
prompt it will pass, derive `<task>-<lane>` from its first-level task heading and
unique `Branch:` line, write that exact string as
`.dreamwork/docs/briefs/<task>-<lane>.md` plus a sibling `.sha256` receipt, re-read
and verify the pair, then exec the runner.  Any failure before the re-read refuses
the launch and names what could not be persisted.  Distinct lanes dispatched for
the same task produce distinct files; an existing identical pair is idempotent,
while an occupied name with different content is refused rather than overwritten.

The coordinator runs `python3 dev/dispatch_lane.py --verify-pending` at the merge
gate and commits both files.  A matched check says how many governed pairs it
examined.  Changed content, a missing artifact, a missing receipt, an
unclassifiable receipt, and zero governed inputs all have distinct failing text.

This route escapes the **lane-side** remember-to-run problem: a lane that never
received its brief, died before its first commit, or was abandoned has no
persistence act to perform.  It does not make bypass impossible because external
`ccc` still exists; the remaining remember-to-run boundary is “use the one
documented `just dispatch-lane` route.”  That is the same honest limit the #768
wrapper already had for validation.

## The uncommitted window

The window matters because the artifact is primary evidence and is not protected
by git until merge.  The receipt records the hash before runner exec, so an
ordinary edit or one-sided deletion becomes loud at the gate rather than silently
changing history.  It is still weaker than the refused lane-first design's G2:
someone can delete or rewrite **both** uncommitted files.  No check whose only
inputs are that pair can prove they once existed.  Half A's growing corpus-reach
gap remains the indirect alarm for total loss; it cannot reconstruct the source.

The wrapper name and success silence therefore mean only “validated prompt was
recorded and matched immediately before exec.”  They do not mean the runner
ultimately received it, or that the coordinator later committed it.

## Preserved decision history

The prior lane's four-option IGC and measurements are carried into the corrected
`.dreamwork/lane-766-report.md`.  Its G5 catch remains correct: committing a brief
before worktree creation makes the brief's own branch-point SHA self-referential;
committing after creation means master is no longer the lane's tip at dispatch.
This implementation dissolves that circularity because it commits nothing at
dispatch.  The old verdict now says plainly that Half A shipped and its Half B was
refused.

## Corpus movement — exact four lines

Before this lane committed its own validated prompt:

```text
OK briefs 191 brief(s) in scope after hand-off obligation, 27 grandfathered (#398); HISTORICAL ONLY — newest numbered brief #595; task history reaches #768 (173-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 96 worktree-naming brief(s), 65 in scope after absolute-inbox rule, 31 grandfathered (#405); HISTORICAL ONLY — newest numbered brief #595; task history reaches #768 (173-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 42 restore-teaching brief(s), 0 in scope after lane-private snapshot rule, 42 grandfathered (#652); HISTORICAL ONLY — newest numbered brief #595; task history reaches #768 (173-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 96 worktree-naming brief(s), 76 in scope after lane-owns rule, 20 grandfathered (#465); HISTORICAL ONLY — newest numbered brief #595; task history reaches #768 (173-id gap; 3 unnumbered brief(s) cannot be ordered)
```

After:

```text
OK briefs 192 brief(s) in scope after hand-off obligation, 27 grandfathered (#398); HISTORICAL ONLY — newest numbered brief #766; task history reaches #768 (2-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 96 worktree-naming brief(s), 65 in scope after absolute-inbox rule, 31 grandfathered (#405); HISTORICAL ONLY — newest numbered brief #766; task history reaches #768 (2-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 43 restore-teaching brief(s), 1 in scope after lane-private snapshot rule, 42 grandfathered (#652); HISTORICAL ONLY — newest numbered brief #766; task history reaches #768 (2-id gap; 3 unnumbered brief(s) cannot be ordered)
OK briefs 96 worktree-naming brief(s), 76 in scope after lane-owns rule, 20 grandfathered (#465); HISTORICAL ONLY — newest numbered brief #766; task history reaches #768 (2-id gap; 3 unnumbered brief(s) cannot be ordered)
```

The first and third populations each gained one.  The absolute-inbox and
lane-owns populations did not: the validated prompt names a `Branch:` and carries
`Lane-owns:`, but its task-specific head does not carry the absolute `Worktree:`
metadata those checks use to classify a worktree brief.  The reach qualifier
still moved on all four rows because the filename's leading integer is #766.
That is the requested feature working, not a rounded count.

## Red-proof — both directions

### Direction 1: persistence failure must stop launch

The test constructs `.dreamwork/docs/briefs` as a regular file, so the artifact
cannot be created.  The wrapper exits 2 with a path-bearing refusal:

```text
dispatch refused: could not persist validated brief: could not create brief corpus …/.dreamwork/docs/briefs: [Errno 17] File exists
```

After `python3 dev/lessons_index.py --act red-proof`, I armed
`dev/dispatch_lane.py`, injected a `pass` in place of `persist_prompt(prompt)`,
and ran the single binding test.  It failed on the real consequence, not a count:

```text
AssertionError: assert 0 == 2
CompletedProcess(... returncode=0, stdout='', stderr='')
```

That is exactly the false-clean launch the test prevents.  `dev/redproof.py
restore` restored and byte-verified the fixed file.

### Direction 2: the path exists but the artifact is wrong or absent

After a healthy wrapper dispatch created the real `766-cx-766b` pair, I changed
only the artifact's `Branch:` line.  The merge-gate check refused it with both
hashes:

```text
brief integrity check failed: brief artifact 766-cx-766b.md changed after dispatch-time persistence (recorded c2ea65067b6d0c318919416be89fbbaec02e8307179b7b8c7f3ac3dbc6a12418, found c0284af6ce1ea34c78817de573352ca999ccb0dd592808a2e6ef0baf651fbf10)
```

The sibling absent-artifact test deletes the `.md` while leaving its receipt and
requires `has no governed brief artifact`.  A verifier over no governed pair
requires `DID NOT VERIFY`, so examining nothing cannot read as a pass.

The honest open false-green is deletion or coordinated rewriting of both pending
files.  A sidecar stored in the same uncommitted window cannot protect against
loss of itself.  The accepted scope detects accidents and ordinary one-sided
mutation; it is not an append-only audit log.

The hand-off gate after both live injections reported:

```text
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

## Verification

- Base and merge-base were both
  `9c62f384c5dcee7855efb3e7c19d1c78b43b2dae`, matching the dispatch.
- Local master remained that SHA; `git rebase master` reported already up to
  date before this report was written.
- Real healthy wrapper dispatch: exit 0, **0 bytes stdout, 0 bytes stderr**;
  exact prompt and receipt written.
- `python3 dev/dispatch_lane.py --verify-pending` — `brief integrity verified:
  1 governed brief(s) matched receipts`.
- `just pytest test_dispatch_lane.py` — **15 passed** (9 before, +6 tests).
- `python3 lint.py` — clean, exactly **6 warnings**, with the four lines above.
- `dev/lane_scratch.py measure` resolved to btrfs (`f_type=0x9123683e`); pytest
  temp state was routed there.
- `git diff --check` — clean.
- No browser guard, port binding, full suite, live-ledger write, merge, push,
  stash, `git checkout`, or `attn` invocation.

Commits before this report: `0722cc9e` (implementation and tests), `47f272e7`
(route contract plus persisted brief/receipt), `07795f60` (corrected prior
verdict), and `e733f828` (identity-binding test).

## Evidence from cited tasks

- **#136:** “present-but-unparseable is a fault and must look like one.” This
  is why matched, changed, missing, unclassifiable, and not-examined states differ.
- **#398:** “3 brief(s) in scope after hand-off obligation, 27
  grandfathered.” Its coverage-count idiom is preserved in the first row.
- **#405:** worktree prompts need “both channels as ABSOLUTE paths into the
  main checkout.” Its classifier population legitimately did not increase.
- **#440:** “a single supported way to fold an entry.” Applied here as one
  writer route, not a wrapper plus a lane habit.
- **#465:** “Ownership comes instead from the brief … as a machine-parseable
  `Lane-owns:` line.” The prompt carries it, though the worktree classifier's
  other precondition is absent.
- **#651:** “a guard's message must name a mode the guard can actually detect.”
  Both persistence and changed-content modes were constructed and named.
- **#652:** “The agent scratchpad is SHARED between concurrent lanes.” The
  lane-private helper, not a session scratchpad, held verification state.
- **#671:** “Zero entries now says `DID NOT REVIEW` rather than ‘nothing to
  review’.” The verifier's zero state is correspondingly `DID NOT VERIFY`.
- **#702:** “Malformed task ids are KEPT and reported loudly rather than reaped
  as dead.” Unclassifiable receipts are named, never dropped from the result.
- **#755:** “the check fires two warnings on the healthy live file.” That is
  why integrity verification is an invoked merge gate with a calm matched
  result, not a permanent warning over historical briefs.
- **#764:** “a citation must carry its own evidence.” The exact prompt, not a
  lane's paraphrase, is the source preserved here.
- **#766:** the adjudication says “a lane cannot persist a brief it never
  received … nor one it died before committing … nor one on a branch that gets
  abandoned.” Those three cases decide the writer boundary.
- **#768:** “THE FIX MUST BE OUT-OF-BAND … before the runner is exec'd.” The
  persistence action shares that already-mandatory boundary.

## DOGFOOD REPORT

1. **The in-tree `BRIEF.md` is not the validated dispatch prompt.** It contains
   only the task-specific head: no appended boilerplate and no `Branch:` line.
   My first “real” invocation correctly refused missing contract; concatenating
   the boilerplate then correctly refused the missing lane identity.  The
   successful dogfood prompt had to add `Branch: cx-766b` before the head.  The
   new contract is documented, but the coordinator's prompt-building procedure
   must actually emit that line; `just dispatch-lane` cannot invent it.
2. **The task's machine ownership list omitted a mandated deliverable.**
   `Lane-owns:` names `.dreamwork/lane-766b-report.md` but the task separately
   requires correcting `cx-766brief`'s `.dreamwork/lane-766-report.md`.  I treated
   the explicit deliverable as authority and changed only those two reports.
3. **The restore instructions conflict.** The task-specific head asks for manual
   `cp`/`cmp`; the appended standing contract says `dev/redproof.py` owns the
   protocol.  I followed the standing contradiction rule and used the tool,
   whose restore output explicitly says the original was restored and verified.
4. **The integrity receipt moves the hazard; it does not erase it.** It catches
   the likely uncommitted-window mutations, but dual deletion remains invisible
   to the pair itself.  The report states that limit beside the success path so
   the wrapper does not acquire a stronger name than its evidence supports.
