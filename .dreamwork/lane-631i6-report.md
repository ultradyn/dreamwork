# Lane report — #631 increment 6: the cold SessionService, still dark

**Branch:** `glm-631i6` (rebased onto `ef909220` master)
**Verdict: LANDED.** HEAD `7b630d15` (+1 parent `41ab708a`). 23 new collected tests (0 → 23 in `test_session_log_service.py`); 63 passed combined with `test_session_source.py`. Lint clean at **5 warnings** (the worktree "ledger checks examined nothing" family, measured at base `4a569f24` and unchanged). redproof check clean (8 injections, all restored, zero in history).

## Headline: a client-supplied path is IMPOSSIBLE, not merely rejected

The shape built: **an id that can only ever select a source by being resolved through the catalogue.** No public method (`register`, `advance`, `snapshot`, `events`, `peek`) takes a `path`/`file`/`filename` parameter — asserted structurally by `inspect.signature` at test time. The resolved transcript path is the OUTPUT of `session_source.resolve`, called only AFTER `_discover` matches the caller's id against the catalogue's discovered uuid set. A path-shaped string is not a discovered uuid, so it never reaches a filesystem object named by the caller. There is no code path in which a caller's string becomes a filesystem path. Increment 5 closed the hole one level down (the wire `CatalogEntry` carries no path); this increment does not reopen it.

The gate lives in `_discover`: it raises `UnknownSessionId("only a discovered session id may select a source; …")`. Disabling the gate (Direction 1, injection 1) reds 3 security-boundary tests — they expect `UnknownSessionId` with that message and instead get `SessionGone` from a downstream `resolve` that can't match the path string to a uuid. That is the discriminating red: the gate's typed exception and message are the thing the test demands, and removing the gate removes them.

## What changed and why

- **`session_log/service.py`** (new, ~360 lines): `SessionService` resolves ids through the catalogue, runs `claude_code.scan_complete`/`scan_incremental`, owns the in-memory per-session event ring + frontier cursor, builds the snapshot skeleton fresh from the held ring on every call, and parses a bounded peek from a registered source range. One re-entrant lock serialises every mutation and read. Typed exceptions: `UnknownSessionId` (the gate), `SessionNotRegistered`, `SessionGone` (deleted-between-catalogue-and-read), `PeekOutOfBounds`. No watcher thread, no HTTP caller (increment 7+).
- **`test_session_log_service.py`** (new, ~470 lines): its only caller. 23 tests across 7 classes: security boundary, snapshot/events replay, unregistered-session faults, the three classifier outcomes staying distinct (#702), deleted-vs-empty (#136), snapshot/cursor consistency (Direction 2), bounded peek (re-derived length, not naive equality), thread safety (#651).

## The security boundary is the point of this increment

> a client-supplied path must be impossible at the API boundary. Replacing id lookup with `Path(id)` must red on "only a discovered session id may select a source".

Met. No public method accepts a path; the resolved path is always the output of `resolve` for a catalogue-validated uuid. A path string supplied as an id is refused at the gate before any filesystem object named by the caller is touched. No return value carries a resolved `Path` (walked recursively and asserted). See headline above.

## The other two hazards

**Thread safety (#651): stated plainly what tests do and do not establish.** Every public method holds one re-entrant lock (`self._lock`) around the held-state dict and every per-session mutation. `test_concurrent_reads_are_consistent` (8 threads × 200 reads) asserts snapshot/events cursor agreement, monotonicity, and a stable event stream under concurrent reads. `test_concurrent_advances_never_double_ingest` (8 threads racing one advance over 3 appended records) asserts exactly one advance ingests and the ring grew by exactly its event count. These establish serialisation. They do NOT establish lock-freedom, a specific scheduling, or absence of deadlock under arbitrary lock ordering — there is one lock, so there is no ordering to deadlock on, but the tests are a smoke test of serialisation, not a formal proof.

**A bounded peek over a registered source range (#645 i7 shape).** `peek(byte, length)` requires `byte` to be a registered record offset (the scan recorded it for a node) and `length ≤ registered length` and `length ≤ MAX_PEEK_LEN`. The happy-path test re-derives the expected record by `json.loads(text[byte:byte+length])` independently of the service — not a naive string equality. Direction 1 injection 3 (replacing `length > reg` with `length > reg + 1`) reds on `test_peek_rejects_a_length_above_the_registered_range` with *"DID NOT RAISE PeekOutOfBounds"* — the off-by-one admits a `length+1` peek, exactly the #645 i7 1-byte-short-span shape.

## Direction 2

**Snapshot/cursor cannot disagree — stated as a property, then the false-green that would hide a violation was caught.** Both the skeleton and the cursor are projections of one held event ring computed in one call (`_snapshot_from` walks `held.events` and reads `len(held.events)`). So they cannot disagree by construction. The brief asked to construct the case where the cursor advanced but the snapshot did not: a *cached* snapshot at register time would go stale after advance. `test_snapshot_advances_with_the_ring_not_a_stale_cache` reds if the snapshot were cached (it checks `snap1.cursor > snap0.cursor` and `len(snap1.bookmarks) > bm0`).

But Direction 2 found a **genuinely broken input that passed every test**: removing `held.text = text` from `_ingest` left all 22 tests green while a peek over a range an ADVANCE registered read stale text. The cursor advanced; the text the peek reads did not. This is the consistency violation the brief named, hiding one layer down. **Caught and closed**: `test_peek_after_advance_reads_the_grown_source_not_stale_text` re-derives offsets from the grown file and asserts the peeked record's content — it reds on `PeekOutOfBounds: read 0 of N requested units` when the text is stale (the new range is absent from the old text).

**Deleted vs empty (#136):** a present-but-empty file scans to zero events (calm, not a fault: `cursor == 0`, `session_node is None`); a file deleted between catalogue and read raises `SessionGone`. `test_deleted_and_empty_render_differently` asserts the two are different kinds of answer (a snapshot vs a typed exception). Direction 1 injection 2 (disabling the `except (FileNotFoundError, OSError)` handler) reds on *"DID NOT RAISE SessionGone"* — the deleted session renders as empty, collapsing the two states.

## Both directions of every red-proof

**Direction 1** (inject the real defect, watch it go red on the discriminating message):

| injection | sabotage | discriminating red |
|---|---|---|
| 1 — security gate | `if session_id not in ids: pass` (gate disabled) | `test_a_path_string_supplied_as_id_is_refused_at_the_gate` expects `UnknownSessionId` match "only a discovered session id may select a source"; gets `SessionGone` instead |
| 2 — deleted-vs-empty | `except (FileNotFoundError, OSError): text = ""` (handler returns empty, not a fault) | `test_a_session_deleted_between_catalogue_and_read_is_a_fault` → *"DID NOT RAISE SessionGone"* |
| 3 — peek off-by-one | `if length > reg + 1:` (admits `length+1`) | `test_peek_rejects_a_length_above_the_registered_range` → *"DID NOT RAISE PeekOutOfBounds"* |

**Direction 2** (construct broken-but-passing, report even if you close it):

| false-green | what's broken | what catches it |
|---|---|---|
| stale text on advance | `held.text = text` removed from `_ingest` — 22/22 tests green, peek-after-advance reads stale text | **Found and closed**: new guard `test_peek_after_advance_reads_the_grown_source_not_stale_text` reds on `PeekOutOfBounds`; re-proven by re-injection |

## Cited issues (every one opened and read)

- **#671** — *"a green sweep on a repo with known-open ids … is RED if the open-id source returns empty … The assertion must be that a planted landing IS NAMED."* Relied on: the empty-catalogue precondition assertions (`assert res.entries`, `assert cat`) and the "examined zero is honest" discipline (`snap.examined == 6`, not a vacuous pass).
- **#136** — *"present-but-unparseable is a fault and must look like one; genuinely empty is … calm grey … distinct nothings must not read the same."* Relied on: deleted-vs-empty (`SessionGone` vs `cursor == 0`), the three-outcomes distinction, and the `resolve` detail-naming discipline inherited from increment 5.
- **#702** — *"reports id-less and non-text entries as unclassifiable rather than dropping them."* Relied on: `TestThreeOutcomesDistinguishable` — exactly one diagnostic (the unclassifiable record), the suppressed record absent from both events and diagnostics.
- **#755** — *"a check that fires on a healthy input trains the reader to skip the line."* Relied on: the suppressed record is silent on healthy input (absent from diagnostics and events alike).
- **#440** — *"a single supported way to fold an entry."* Relied on: `scan_incremental` with `Frontier` is the one supported way to resume — `advance` calls it, no second resume path.
- **#651** — *"a guard's message must name a mode the guard can actually detect."* Relied on: the thread-safety docstring states what tests do and do NOT establish, rather than asserting "thread-safe" without evidence.
- **#645** — the increment-7 lane "found exactly this shape and closed it: a 1-byte-short span produced text that looked correct and passed a naive equality check, but failed a fresh re-derivation of the expected length." Relied on: peek re-derives the record by `json.loads` independently, and the off-by-one injection reds on the bound-rejection test.

## Rebase outcome

Master moved `4a569f24` → `ef909220` (the #645 increment-8 merge landed while I worked). Rebased cleanly, no conflicts, no conflict markers (grepped all four diff3 forms, anchored). Tests and redproof check re-verified post-rebase: 63 passed, check clean. HEAD `7b630d15`.

## Out of scope (named, not fixed)

1. **`_discover` re-runs the catalogue on every `register`.** The catalogue walks the filesystem; increment 7's watcher + the derived store (increment 10) will own the discovery cadence. The cold service re-discovering per register is correct but not cheap, and is not this increment's concern.
2. **`events()` never evicts the ring.** The ring grows unboundedly in this increment; increment 9 (registration routes) will need a bounded window or a generation token, because a long-lived session's ring is unbounded memory. Stated in the docstring; not fixed here.
3. **`advance` re-reads the whole file.** `scan_incremental` only parses from the frontier, but `read_text` reads the whole file. The watcher (increment 7) will own the read strategy. Correctness is unaffected; cost is.

## DOGFOOD REPORT

**The brief's security-boundary framing was exactly right and saved a real miss.** My first injection attempt (replacing `_discover`'s body with a path-accepting overload) broke the *legitimate* id path too, because `Path(uuid_string)` is a relative path to a non-existent file — so the test never reached the discriminating assertion. The brief's phrase "the way that happens is a convenience overload that accepts 'an id or a path'" named the exact hazard, and the clean injection (gate disabled, `resolve` kept) is the one that discriminates. A less specific brief would have let me ship a red-proof that reds for the wrong reason.

**One friction worth naming: `redproof.py begin`/`restore` re-arms on the same file, and the `check` output lists every prior injection cumulatively.** That is correct (the tool tracks the full history), but during a multi-injection session the `check` output grows to 8 entries and the "is one left unrestored?" question requires reading all of them. Not a bug — the tool refuses correctly — just a note that the cumulative list is denser than a single-injection lane would produce. No action needed.

**No friction found** with `dev/lane_scratch.py`, the slug rule, or the catalogue API. Increment 5's `CatalogEntry`-carries-no-path contract made the service's security boundary trivially correct at the wire level, which is the strongest argument for the increment ordering the design chose.
