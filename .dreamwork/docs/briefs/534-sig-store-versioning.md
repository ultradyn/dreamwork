# Brief — #534: a digest-algorithm change fires a phantom question-updated burst on deploy

**Task:** #534 (P3, dogfood/tooling) — when `_entry_content_digest`'s
algorithm changes (the #509 `_sig_text` whitespace normalisation was the
live instance), the FIRST collect against a store written by the old
algorithm sees every stored digest differ and emits one `question-updated`
event per entry — ~21 phantom events at 09:43:31 on the 2026-07-30 deploy,
and a single phantom again at 10:06 when the coordinator edited
questions.md under the OLD deployed server (the deployed code predates the
normalisation; the file changed, so the old algo legitimately fired — but
the NEXT deploy of normalised code will fire a fresh burst over the same
entries, none of whose content changed).

**Lane-owns:** `watch.py` (the `track_question_updates` / sig-store region
only — `_entry_content_digest`, `_sig_text`, the `question-sigs.json`
read/write path), `test_watch.py` (the sig tests), and if useful
`dev/capture/` for a guard. Nothing else. Coordinator owns handoffs.md
grammar; you write exactly one Pending line (see below).

## The fix shape (rec — refine if the code says otherwise)

Version the sig store. `question-sigs.json` gains an `algo` field naming
the digest algorithm generation (e.g. `"sigtext-v1"` for the
whitespace-normalised one). On load in `track_question_updates`:

- `algo` matches the current generation → today's behaviour, unchanged.
- `algo` is absent or names an older generation → **silent re-seed**:
  recompute every entry's digest under the CURRENT algorithm, persist the
  store with the new `algo`, and emit **zero** events. The re-seed is the
  migration: content did not change, so no event may fire — an event says
  "his question file changed", and an algorithm upgrade is not that.
- The store keeps per-entry digests; entries present in the store but gone
  from the file are dropped on re-seed (today's behaviour for vanished
  entries, whatever it is — match it).

Keep the migration list explicit and append-only in code (`v0` = unmarked
store, `v1` = `_sig_text` normalised) so the NEXT algorithm change is a
one-line addition, not a re-discovery of this task.

## Evidence discipline (the repo rules, all load-bearing)

- **Red-first**: new tests in `test_watch.py` (the sig test class already
  exists — extend it). Fixture: a store written under the OLD algorithm
  (build it by calling the old digest path directly, or hand-construct it
  — but then assert at runtime that the old-algo digest of the fixture
  DIFFERS from the new-algo digest, or the fixture is vacuous). First
  collect against it must emit ZERO events and re-seed the store to the
  current algo. Second collect (unchanged content) also zero. A real
  content change after re-seed emits exactly ONE.
- **Every check red-proved**: snapshot with `cp` → sabotage the named
  production line (e.g. the algo-mismatch branch returning early WITHOUT
  re-seeding; the re-seed writing events anyway) → the named test FAILs →
  `cp` restore → `git status --porcelain` empty. Never `git checkout`.
- **A green red-run is a finding, never a relief** — three-shape triage in
  `.dreamwork/lessons.md` (search "green red-run"). This class has two
  recent instances (#509's own gate hit one).
- The #534 store in the LIVE target (`.dreamwork/question-sigs.json`)
  currently holds OLD-algo digests — after your fix deploys, the first
  collect must re-seed silently. Your tests are the proof that will
  happen; do not hand-edit the live store.
- `git commit --only <paths>`; new files need `git add` first. Never
  `attn`. Never `pkill -f`. Work only in your worktree.
- Targeted pytest + `python3 lint.py` only — never `just test`, never the
  guard suite (#424); your own guard (if you write one) solo on a free
  3989x port after checking the range (`just reap`).

## Report

Append your report to the coordinator inbox (path in your dispatch
prompt), and append ONE literal line to your worktree's
`.dreamwork/handoffs.md` under `## Pending` (grammar in the file's
header: `- **#534** · landed \`<sha>\` · <date> · by lane-534sig — <what>`),
committed with `git commit --only .dreamwork/handoffs.md`.

## Done when

The store is versioned; an old-algo store re-seeds silently (zero events)
and a real change still fires exactly one; the tests are red-proved;
`test_watch.py` green; the Pending line is committed.
