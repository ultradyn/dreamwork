# Brief — lane-501consume: the thin consume CLI over the journal cursor (#501)

Lane-owns: ONE new CLI file under `dev/` (name it `dev/journal_consume.py`
unless a clearly better home exists — check how `dev/ledger.py` is
structured first and follow that idiom) plus its test file (repo-root
`test_journal_consume.py`, following `test_lint.py`/`test_user_events_http.py`
conventions). Nothing else. Do NOT touch `SKILL.md` (the coordinator writes
the tick-flow habit text at merge), `watch.py`, `user_events/` internals,
or `dev/ledger.py`.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## Context (read first)

- #342 lanes A+B landed: `Journal.events_since_cursor(consumer)` (read
  projection, in `user_events/sqlite.py`) and `advance_cursor(consumer,
  expected)` with the exact_payload_bytes/event_hash verification. FIND
  these and read their signatures and tests before designing anything.
- What is MISSING (this task): the loop has no mechanical way to drain
  the journal on a tick. The coordinator's heartbeat wakes it, but
  nothing enumerates what arrived since the last tick — batched delivery
  is lossy until this exists. The durable backstop for when the wake
  monitor is off or compaction ate the offset.
- The consumer name is the literal string `'coordinator'`.

## The work

A thin CLI with two subcommands (names yours to propose within the
`dev/ledger.py` idiom — e.g.):

1. **`pending`** — print the events since the coordinator cursor
   (kind, route, receipt id, timestamp, payload preview), ordered,
   to stdout. READ-ONLY: never advances the cursor, never writes.
   Exit 0 with zero events printing nothing extra (the quiet rule).
2. **`consume`** — advance the coordinator cursor to the current head
   using the verification `advance_cursor` expects (expected hash/payload
   bytes derived from a fresh `events_since_cursor` read in the SAME
   invocation — read-then-advance as one act, so a crash between them
   cannot skip events). Print what was consumed (count + receipt ids).
   Exit non-zero with a clear message if verification fails (the journal
   changed underfoot — the caller re-reads next tick; NEVER force).

Both take the store path the same way `dev/ledger.py` verbs take
`--ledger` — follow that idiom (default path, overridable flag for
tests). Human-readable output; machine-stable enough that the
coordinator can parse receipt ids (one per line is fine).

## Constraints (hard)

- Red-first tests: tmp-dir store, real Journal, no mocking of the thing
  under test. Cover at minimum: empty journal prints nothing and exits 0;
  pending lists exactly the events in (cursor, head]; pending does NOT
  advance (two `pending` runs see the same events); consume advances and
  a second `pending` is empty; consume with a journal write between read
  and advance refuses (exit non-zero, cursor unmoved) — if that race is
  not inducible through the real API, say so and test the refusal at the
  seam the API does expose, naming the gap.
- Assert runtime preconditions in the tests (the fixture genuinely has N
  events before you assert what pending prints — derive N, never assume).
- **A green red-run is a finding, never a relief**: for the key tests,
  name the production line that would have to change for the test to
  fail, change it, watch it fail, restore byte-identical with `cp`.
- Small commits, `git commit --only <paths>` (new files `git add` first).
  NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899. Work
  only in tmp dirs — NEVER against the main checkout's live store.
- If `file-formats.md` needs a row for a new machine-parsed output,
  propose the row in your report — do NOT edit `file-formats.md`
  (coordinator-owned).

## Acceptance criteria (measurable)

1. The two subcommands exist and behave as specified, store path
   overridable, quiet on empty.
2. Tests cover the five behaviours above; each red line run and named
   (injection + production line).
3. `python3 -m pytest test_journal_consume.py` green; `python3 lint.py`
   no new findings vs a master baseline.
4. `git diff master --stat` touches only the two owned files.
5. Report includes: the exact command lines the coordinator's tick will
   run, and any seam where read-then-advance is not atomic (named, not
   hidden).

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
the CLI surface, the five behaviours with their red-proofs, the atomicity
seam statement, the proposed tick command lines, and any pushback.
