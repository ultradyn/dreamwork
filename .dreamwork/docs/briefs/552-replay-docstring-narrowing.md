# Brief #552 — narrow the replay tool's docstring/CLI overclaim

**Task** (ledger #552, origin loop): the #550 design verdict (NARROW —
`.dreamwork/docs/550-journal-entity-schema.md`) found the `.jsonl`
contract already honest but the replay TOOL overclaiming:
`dev/replay_events.py:1` (*"replay the task_event journal, reconstruct
the store"*) and the `replay`/`export` subparser help (~`:312`/`:316`,
*"reconstruct a store from a .jsonl journal"*) read as fuller
reconstruction than the journal provides.

## Scope

One file: `dev/replay_events.py`. One commit. No migration, no format
change, no behaviour change.

1. Module docstring `:1` — "reconstruct the store" becomes the honest
   claim: reconstruct the **transition chain (lifecycle)**; entity
   columns are stubbed — see #294/#550.
2. `replay` and `export` subparser help — same narrowing.
3. Optionally cite #550 beside the `_REPLAY_*` stub constants
   (`:88-93`).
4. **§8 of the design doc has the exact proposed wording** — use it,
   adjusting only if a line number has drifted.

Deliberately excluded: any entity data, sidecar format, golden-vector
or `file-formats.md` edit, any test change.

## Hard contracts

- **Red-first here is the EXISTING falsifier, not a new test**: this is
  a docstring-only change, so the owed check is that
  `test_replay_events.py` — in particular
  `test_round_trip_task_state_matches_but_title_does_not_294_finding` —
  still holds AND still proves the stub divergence (run it; confirm it
  passes for the same reason it passed before: the entity really does
  not round-trip). Also run `test_chain_golden.py` and
  `python3 dev/replay_events.py --help` to eyeball the new help text.
  If you find yourself editing anything but docstrings/help/comments,
  stop — that is out of scope; report instead.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
- **ONE `.dreamwork/handoffs.md` `## Pending` line** before your final
  commit (#398 obligation): #552, sha, date 2026-07-30,
  lane-552wording, what landed, flags.
- **Commit with `git commit --only <paths>`**. Targeted pytest only
  (test_replay_events.py + test_chain_golden.py). Never `just test`;
  never attn; never `pkill -f`.

## Lane-owns declaration

You own: `dev/replay_events.py` docstrings/help/comments and your
handoffs line.
You do NOT own: `file-formats.md`, `ledger_store.py`, any test file,
`lint.py`.

**Fleet**: lane-551remind (watch.py posture region) and lane-548cap
(dev/capture/bdinput.mjs) are in flight — disjoint.

## Report shape

Final report: commit; the falsifier + golden pytest verdict lines; the
rendered `--help` excerpt showing the narrowed wording; any deviation
with the reason.
