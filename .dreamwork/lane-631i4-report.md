# #631 increment 4 — lane report (glm-631i4)

**Verdict: LANDED.** Incremental cursor and partial-tail equivalence, still dark.

Rebased onto `3d082c0d` (master moved from `7270566e` during the run). No
conflicts. Head: `20766f80`.

## What this decides for `scan_incremental == scan_complete(...)[cursor:]`

**It REDS — six tests go red under the tautological implementation.**

I sabotaged `scan_incremental` to `return scan_complete(text)` (ignoring the
frontier entirely) and ran the increment-4 test set. Five of the eight
cursor/tail tests red, plus the seq-continuation test:

| test | discriminating message |
|---|---|
| `test_scan_incremental_does_not_reread_bytes_before_cursor` | *"a genuine resume never reads bytes before the cursor — poisoning the prefix must not change the resumed events"* |
| `test_scan_incremental_cost_does_not_grow_with_prefix` | *"a resume emits fewer events as the cursor advances (15 vs 15); if equal the resume re-scanned the whole file"* |
| `test_split_mid_record_then_append_remainder_equals_one_shot` | *"concatenated scan must equal the one-shot scan byte-for-byte"* |
| `test_resume_does_not_replay_consumed_line` (injection 2) | *"duplicate node ids — replaying the prior complete line..."* |
| `test_resume_carries_open_tool_and_pairs_result_across_split` | *"the split-and-resume tool pairing must equal the one-shot pairing"* |
| `test_resume_continues_seq_numbering_no_duplicates` | *"the resume must continue seq numbering from the frontier"* (`assert 1 == (5 + 1)`) |

The corrupt-prefix test is the load-bearing discriminator: the bytes before
the cursor are poisoned with unparseable garbage, so a re-scan-from-zero
produces different events (seq starts from 1, not from `frontier.seq + 1`).
A genuine resume never touches the poisoned prefix and is unaffected.

## What changed and why

**`session_log/claude_code.py`** — the scanner now carries resume state:

- **`Frontier`** dataclass: the byte/line cursor plus the session/page/turn
  frontier, monotonic counters (`seq`, `bm`), and open tool-pairing state.
  `empty_frontier()` is the zero state (`#671`: counters at zero, ids `None`).
- **`scan_incremental(text, frontier)`**: the one supported way to resume
  (`#440`). Consumes only newline-terminated records from `frontier.byte`,
  carrying frontier state so the resume CONTINUES the tree (seq continues,
  open session/page reused, unpaired `tool_use` kept live) rather than
  restart it.
- **Shared `_scan_records` / `_process_record` core**: both `scan_complete`
  and `scan_incremental` exercise the same parser. `_iter_records` (the
  increment-3 record iterator) is replaced by a cursor-aware byte scan that
  stops before an unterminated trailing line.
- **`ScanResult.frontier`**: every scan returns a `Frontier` for the next
  resume.

**`test_session_log_claude_code.py`** — +12 collected tests (51 → 63):
equality proof with runtime-derived floor; corrupt-prefix discriminator;
cost-grows-with-prefix discriminator; tool-pairing boundary; seq/page
continuation; both named injections; empty-frontier and zero-state tests.

## The tool-pairing boundary decision

A resume across a `tool_use` → `tool_result` boundary continues the pairing,
because the open `tool_use` is carried in `frontier.open_tools`. The test
`test_resume_carries_open_tool_and_pairs_result_across_split` splits after a
`tool_use`, verifies the frontier carries it (`open_tools` non-empty), then
verifies the resumed `tool_result` pairs (emits an `update`, not an orphan).
The concatenation equals the one-shot result.

## Direction 1: both injections, discriminating messages quoted

**Injection 1** — cursor advances past the unterminated tail.

Sabotage: `_scan_records` sets `pos = len(text); break` instead of `break`
when no newline is found (the partial tail is consumed, cursor jumps past it).

Reds on: `AssertionError: completed tail record was lost` (`assert 0 >= 1`,
where 0 = events from the resume that started past the completed record).

**Injection 2** — cursor doesn't advance past consumed lines.

Sabotage: `_scan_records` returns `start_byte` instead of `pos` (the cursor
sits at zero; every resume replays everything).

Reds on: `AssertionError: duplicate node ids — replaying the prior complete
line re-emitted nodes the prefix scan already produced` (the replayed user
turn re-opens `u:u1`, colliding with the prefix's id).

`redproof.py check`: clean — 3 injections registered, all restored and
absent from the working tree and from this branch's commits.

## Direction 2: the false-green I found and closed

**The cost-grows-with-prefix test was a Direction-2 false-green.** The first
version scanned the same 2-line *remainder* from two different cursors:
both the genuine and the tautological implementation gave equal counts
(`n2 == n8`), so the assertion passed under both. Rewrote to scan the *full
text* from two cursors — a genuine resume emits fewer events as the cursor
advances (`n2 > n8`); re-scan-from-zero emits the full count from either
(`n2 == n8 == 15`), and `n2 > n8` reds.

No other Direction-2 false-greens found. The equality test's floor
assertion (`len(one.events) > 0`) prevents the vacuous empty-equals-empty
case. The corrupt-prefix test's poison is unparseable JSON, so any read of
the prefix changes the event stream. Both injection tests use content
records that always emit events, so a correct-looking replay can't hide.

## Cited issues, relied-on lines quoted

- **`#440`** — *"the coordinator hand-rolls a ledger split on every fold,
  and the unanchored form has now corrupted the file once"*. Relied on
  analogically: the one-resume-entry-point rule — a second unanchored form
  is the corruption vector. `scan_incremental` is the single supported way.
- **`#755`** — *"status.json's queued_dispatches names task ids that nothing
  verifies are still open"*. Relied on analogically for "silent on healthy
  input": suppressed chrome is skipped without emitting events.
- **`#671`** — *"examines zero ledger entries and says so confidently"*.
  `examined` counts every non-empty line parsed; zero for an empty
  transcript, positive for a real one. The equality test's floor asserts the
  one-shot scan produced nodes.
- **`#702`** — *"status.json records a dispatch in two places and only one
  is machine-readable"*. Relied on for: unclassifiable records are carried
  in diagnostics, never dropped. The classifier's three outcomes stay
  distinguishable through an incremental scan.
- **`#136`** — *"THREE zero-states, not one"*. The empty frontier (counters
  at zero, ids `None`) is distinct from a real frontier (counters positive,
  session/page open). `test_empty_frontier_is_the_zero_state` asserts this.
- **`#652`** — *"The agent scratchpad is SHARED between concurrent lanes"*
  — relved on for `dev/redproof.py` placing snapshots lane-privately on
  `~/.cache`.
- **`#349`** — *"Revert a deliberate RED injection with the inverse of the
  injection, never with `git checkout <file>`"*. Used `dev/redproof.py`
  for all snapshot/restore.
- **`#608`** — *"The red-proof recipe in every brief backs up the WRONG
  state"*. `redproof.py begin` snapshots the file before sabotage; `restore`
  returns it; the fix is never undone.

## Verification

- **Lint:** clean at 5 warnings (the lane bar). All five are the
  worktree-artifact `ledger checks examined NOTHING` row (`#611`).
- **Pytest:** `just pytest test_session_log_claude_code.py
  test_session_log_model.py` — 73 passed.
- **Collected:** 73 total (63 in `test_session_log_claude_code.py` + 10 in
  `test_session_log_model.py`). Before: 61 (51 + 10). **Delta: +12** in the
  focused file.
- **`redproof.py check`:** clean (3 injections, all restored).
- No browser guards, no port binding. Dark and server-only.

## Rebase outcome

Master moved from `7270566e` to `3d082c0d` during the run. Rebased cleanly,
no conflicts, no conflict markers. Tests green post-rebase. Head: `20766f80`.

## Out of scope (named, not fixed)

- Checked real Claude Code JSONL transcripts under `~/.claude-p/projects/`
  for record shapes §2 does not describe. **None found** — all types
  (`user`/`assistant`/`system` content, `mode`/`last-prompt`/etc. chrome),
  all subtypes (`compact_boundary`/`stop_hook_summary`/`turn_duration`), and
  all content block types (`tool_use`/`tool_result`/`text`/`thinking`/
  string) match §2's grammar.

---

## DOGFOOD REPORT

**The cost-discriminator test was born hollow and I caught it in Direction
2.** My first version scanned the same short remainder from two cursors and
asserted `n2 == n8` — trivially true under both the genuine and the
tautological implementation because both process the same 2-line text. The
Direction-2 protocol caught it: I asked "what if `scan_incremental` were
`scan_complete(...)[cursor:]`?" and the answer was "this test still passes."
Rewrote to scan the full text from two cursors, where the genuine resume
gives `n2 > n8` and the tautological gives `n2 == n8`. This is exactly the
false-green family the brief warned about.

**Brief issue citations are analogical, not literal.** `#440` is about
ledger-split anchoring; the brief uses it for "one supported way to resume."
`#755` is about stale dispatch ids; the brief uses it for "silent on healthy
input." Both principles are sound and established by increments 2–3, but the
cited issues themselves are about different subsystems. This didn't cost me
time — the principles were already clear from the prior increments' tests —
but a future lane that hasn't read the prior increments might chase the
wrong thread.

**No other friction found.** The `dev/redproof.py` tool worked flawlessly
across three injections: snapshot, sabotage, restore, check. The lane-private
scratch directory was clean. The rebase was conflict-free. The brief's
warning about the tautological implementation was the single most valuable
prompt — it forced me to build a check that is false under the natural
implementation, which is the whole point of this increment.
