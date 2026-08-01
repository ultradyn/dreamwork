# Landing-evidence adjudication — 2026-08-02

Ordered by confidence, most confident first. `COMPLETE` means recommend fold;
`CONTINUING` means retain the open entry with the stated remainder.

## #701 — COMPLETE

**Evidence read:** `dev/dispatch_lane.py:63-82` classifies stdout and refuses both
FIFO and socket peers before runner launch. The two live-process assertions are
`test_dispatch_lane.py::test_dispatch_refuses_pipe_before_short_reader_can_kill_runner`
and `test_dispatch_lane.py::test_dispatch_refuses_socket_before_peer_can_kill_runner`;
each requires the runner-start marker to remain absent.

**Recommendation:** fold. The original pipe member and #797's final socket
remainder are both unavailable in current master, so the entry's last stated
condition is discharged.

## #803 — COMPLETE

**Evidence read:** `dev/concurrent_tests.py:241-250` distinguishes absent
`MemAvailable` from healthy silence and rejects negative or above-total values as
impossible. The exact cases are bound by
`test_concurrent_tests.py::TestMemoryPressure::test_missing_memavailable_says_pressure_was_not_measured`,
`::test_negative_memavailable_is_reported_as_impossible`, and
`::test_memavailable_above_total_is_reported_as_impossible`.

**Recommendation:** fold. All three states named by the entry now produce an
honest non-health reading.

## #785 — COMPLETE

**Evidence read:** `dev/concurrent_tests.py:232-255` keys the advisory on low
available memory, never accumulated swap use, and avoids the unsupported
"memory-bound" diagnosis. The healthy high-swap control is
`test_concurrent_tests.py::TestMemoryPressure::test_high_swap_healthy_available_is_calm`;
the #803 tests cited above cover the only recorded remainder.

**Recommendation:** fold. The available-memory correction is present and the
entry's explicit wait-for-#803 condition has now been met.

## #738 — COMPLETE

**Evidence read:** `client/router.js:170-211` keeps `dw:draw-mode` browser-local,
applies the writer locally, and adopts the same key through the sibling tab's
`storage` event. `dev/capture/drawmode.mjs:72-99` exercises two already-open tabs
in both directions and requires exactly one application in writer and sibling.

**Recommendation:** fold. This is precisely the ruled scope: per browser,
shared across tabs, with no server-side tint-style persistence.

## #818 — COMPLETE

**Evidence read:** `watch.py:4689-4697` places `chat` beside `do-now` and
`do-next` in `PREEMPT_KINDS`, while `watch.py:4732-4752` makes those kinds wake
independently of delivery mode. The live channel distinction is bound by
`test_watch.py::TestDeliveryWakeRouting::test_chat_wakes_in_batched_after_receipt_commits`
and `::test_chat_reply_wakes_the_same_way_a_chat_send_does`, which separately
require the receipt and its wake line.

**Recommendation:** fold. Both a new chat and a reply now pre-empt in batched
mode; a receipt-only false green cannot satisfy either test.

## #820 — COMPLETE

**Evidence read:** `test_guard_argv.py:136-152` compares the complete derived
guard membership set, not a floor, so removing `wisp.mjs`'s import names that
member immediately. `test_dreamwork_db_import.py:338-356` binds each synthetic
question ordinal to its expected status rather than accepting the same count
with swapped identities.

**Recommendation:** fold. Both demonstrated count-for-membership false greens
now fail on the wrong member itself.

## #657 — COMPLETE

**Evidence read:** `client/views.js:795-815` emits one block container with a
stable chat id per row, so adjacent rows separate and a new row cannot inherit
the old row's client-owned turn text. The boundary is asserted by
`test_watch.py::TestCollector::test_chatlist_keeps_two_rows_in_separate_block_containers`;
the transient one-turn insertion is driven by `dev/capture/chatsurface.mjs:236-269`.
The related paragraph observation is also closed in current master:
`client/views.js:842-853` passes chat bodies through `mdRender` with soft breaks,
and `dev/capture/chatsurface.mjs:315-383` checks the rendered DOM's line and
paragraph boundaries.

**Recommendation:** fold. Master discharges both title defects and the related
paragraph-format question recorded in the entry.

## #814 — COMPLETE

**Evidence read:** `test_user_events_http.py:301-325` posts authored multiline
policy text through `/subagent-policy`, requires exactly one receipt, and compares
its exact payload bytes and decoded policy. `dev/reconcile_submissions.py:105-116`
also includes the route in the closed recovery population.

**Recommendation:** fold. The corrected meaning of this entry was the coverage
gap, not a missing production receipt; current master exercises and binds the
already-generic receipt path.

## #816 — COMPLETE

**Evidence read:** `dev/citation_audit.py::audit_briefs` increments an independent
`briefs_examined` count for every on-disk brief, and `::format_report` calls an
audit incomplete only when that count differs from the on-disk population. The
split-root proof is
`test_citation_audit.py::test_default_corpus_reaches_main_checkout_from_linked_worktree`:
it plants one known main-store citation and requires `UNRESOLVABLE: 0`; the
untracked-but-audited direction is
`::test_report_names_untracked_but_audited_corpus`.

**Recommendation:** fold. The coverage sentence now measures audit reach, and
the linked-worktree fixture can no longer pass over an empty/wrong store root.

## #811 — COMPLETE

**Evidence read:** `dev/repo_wide_guards.py:124-128` registers
`test_check_watch_citations.py::test_reviewed_watch_citation_population_is_still_resolved`
in the always-run set; that test also rejects a zero certified population.
`dev/apply_reanchors_i3.py:4-11` resolves the sibling decision: despite its old
name it is a read-only standing resolver, exercised over its anchor population by
`test_reanchor_citations.py`, not an unowned mutating one-shot script.

**Recommendation:** fold. Both formerly inert files now have explicit, tested
homes appropriate to their different roles.

## #809 — COMPLETE

**Evidence read:** `.dreamwork/lane-809-report.md:27-53` fixes the sampling method
before candidate inspection: all 2,678 collected source functions received an
AST census, 75 deterministic node ids were read across three strata, and 12
production seams were mutated. `.dreamwork/lane-809-report.md:60-130` records two
whole-file survivors and one sibling-compensated survivor, naming
`test_guard_argv.py::test_outdir_sweep_count`,
`test_dreamwork_db_import.py::TestDatelessEntries::test_dateless_entries_imported`,
and the reach-count node; `.dreamwork/lane-809-report.md:198-222` states the
coverage ceiling rather than extrapolating it to the suite.

**Recommendation:** fold. The requested lens was the bounded audit, not repair
of every finding; master contains the reproducible sample, mutations, results,
and honest non-exhaustive conclusion. The two suite-level survivors were then
fixed by #820.

## #777 — COMPLETE

**Evidence read:** `lint.py:4257-4353` runs the living-document past-EOF check,
explicitly excludes historical records, and reports only "in range" because a
wrong in-range line remains outside its power. The permanent behavior is bound
by `test_lint.py::TestCitationRange`; the last three dead task-ledger line
citations are ID citations in
`.dreamwork/docs/research/contextual-review-annotations.md:20-26`.

**Recommendation:** fold. A current master lint read reports `OK citation range`
for 503 citations across 235 living documents, with no citation-range WARN; the
only standing near-duplicate WARN is the separately human-gated lesson row the
entry explicitly excluded from its terminal bar.

## #631 — CONTINUING

**Evidence read:** `.dreamwork/docs/plans/session-log-view.md:775-787` defines the
landed increment-6 state as a cold `SessionService` with no notification thread
or HTTP caller. The service is still test-only, as asserted by
`test_session_log_service.py`; the next production work begins at the
`SessionWatcher` increment in `.dreamwork/docs/plans/session-log-view.md:789-805`
and continues through routes, cache, client reducer/component, and final enable.

**What the id means now:** increments 1-6 have landed and remain dark. Keep the
entry for increments 7-15 that turn the cold service into the live, persisted,
reachable session-log view.

## #645 — CONTINUING

**Evidence read:** `.dreamwork/docs/cx-645-db-api-design.md:566-583` places the
landed CLI at increment 9 and still lists dark reads, dark writes, review UX,
live cutover, and deletion as increments 10-14. Current master still says at
`dev/ledger.py:1694-1744` that question writes refuse while `questions.md` is
authoritative; the canonical store composition in `dreamwork_db/store.py`
removes a duplicate API but does not set the migration watermark or delete
`questions.md`.

**What the id means now:** retain it for increments 10-14: route all production
question readers/writers through the repository, ship the linked-review UX,
perform and verify the live cutover, then delete the Markdown source and its
file-only machinery.

## #263 — CONTINUING

**Evidence read:** `.dreamwork/docs/plans/user-event-inbox.md:3-5` says the
landing is a settled design and that implementation, migration, purge, and
deployment are not authorised. Its authority gate at
`.dreamwork/docs/plans/user-event-inbox.md:366-372` requires a separately
authorised, red-first implementation increment and keeps lane G under Max's
separate ruling.

**What the id means now:** the inbox-as-a-view design has landed; the durable
inbox/replay implementation has not. Keep it open for separately authorised
implementation and the still-explicit crash, schema-v2 purge, migration, and
deployment acceptance work.

## #691 — CONTINUING

**Evidence read:** `.dreamwork/docs/plans/main-agent-recap.md:3-5` states that
nothing has been built, while `.dreamwork/docs/plans/main-agent-recap.md:17-27`
defines the absent-by-default runner, DB attempt log, and dashboard recap that
must exist. The three design calls are now folded in
`.dreamwork/questions.md:309-367`, so the design gate is resolved; master has no
recap runner, recap table/repository, or dashboard consumer.

**What the id means now:** build the approved feature: transcript digest,
attempt/result persistence, configurable scheduled cheap-model runner behind
`.dreamwork/recap`, and the recap-id-gated dashboard cross-dissolve. The design
landing alone does not discharge the feature request.

## #368 — CONTINUING

**Evidence read:** `.dreamwork/docs/plans/modularity-and-startup.md:102-136`
turns modularity and startup into decision breakpoints but selects a future
demand-driven seam rather than performing it. The concrete next extraction is
still prospective at `.dreamwork/docs/plans/modularity-and-startup.md:157-159`;
`test_startup_benchmark.py` binds the measurement instrument, not a module split.

**What the id means now:** reconcile the duplicate #124 initiative, then extract
the first operation a real `dreamhub` consumer needs behind a compatibility
facade and prove both adapters call the same core. The benchmark prerequisite
landed; the actual reusable modular breakup did not.

## #630 — CONTINUING

**Evidence read:** `.dreamwork/docs/plans/component-transition.md:321-326`
requires one `QaCard` wrapper to pass through the authenticated design tool
end-to-end before the rest of the starting wrapper set is authored. The same
plan still assigns the remaining surface conversions to P6…Pn at
`.dreamwork/docs/plans/component-transition.md:328-349`; the local wrapper and
path-independent bundle checks do not perform that external ingestion or those
flips.

**What the id means now:** keep it open for Max's authenticated design-tool run
that settles P5 stage 2, then for the remaining component conversions, including
the eventual coordinated `qaCard` family endgame. The plan and local bundle
infrastructure are prerequisites, not the completed component transition.
