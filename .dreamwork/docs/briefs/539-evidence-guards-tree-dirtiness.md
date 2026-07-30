# Brief — #539: evidence-capture guards must not dirty the tree on a plain run

Lane: lane-539dirty (glm-5.2). Filed by the coordinator after restoring the same four
files for the third time.

## The defect

`dev/capture/mdquote.mjs` and `dev/capture/mdtable.mjs` are evidence-capture guards: each
run re-captures four COMMITTED PNGs in the repo:

- `screenshots/lane-521md/mdquote-desktop.png`
- `screenshots/lane-521md/mdquote-mobile-390.png`
- `screenshots/lane-525tables/mdtable-desktop.png`
- (verify the exact set — grep both guards for their screenshot paths)

Every full `just test` therefore dirties the working tree with byte-different re-captures
(headless rendering is not bit-stable across runs/loads), and the coordinator restores them
with `git show HEAD:path > path`. A guard whose passing run modifies the repo it measures
is a side effect in the wrong direction.

## The fix (recommended shape; you may improve)

- Plain run: capture to the guard's outdir (the `outdir(process.argv)` scratch every other
  guard uses), NEVER into `screenshots/`. The committed PNGs are refreshed only when an
  explicit opt-in env var is set (e.g. `DW_UPDATE_EVIDENCE=1`) — the same "evidence refresh
  is a deliberate act" shape as a snapshot-update flag.
- When the env var IS set, write the committed paths exactly as today (same filenames), and
  print a line naming each refreshed file.
- If the guards' PASS/FAIL currently depends on comparing against the committed PNGs, keep
  that comparison reading the committed bytes (read-only is fine) — only the WRITE moves
  behind the flag. If nothing reads them (pure evidence), say so in your report.
- Check whether any OTHER guard writes into `screenshots/` or anywhere outside its outdir
  on a plain run (grep dev/capture for `screenshots/`) — sweep any you find onto the same
  contract, and name each in your report.

## Binding check (red-first, the repo's rule)

Add a test (e.g. `test_guard_evidence.py`) that asserts the contract, with the precondition
asserted in the test:
- Derive the set of committed `screenshots/**/*.png` at runtime and assert it is non-empty
  (else the check is vacuous and must say so).
- Assert no `dev/capture/*.mjs` writes a `screenshots/` path unconditionally — i.e. every
  write to `screenshots/` in a guard is lexically guarded by the env flag (grep-shape check
  is fine: the env var name appears within N lines of the write, or the write lives in a
  function only called under the flag — pick a check that binds and say what it binds).
- Red-proof it: cp-snapshot one guard, remove the env gate around its screenshots write,
  watch the test FAIL, cp-restore byte-identical (never `git checkout`). A green red-run is
  a finding — report it.

## Constraints

- Lane-owns: dev/capture/mdquote.mjs, dev/capture/mdtable.mjs, any other guard found
  writing screenshots/, the new test file, screenshots/ (only under the flag — you should
  NOT need to refresh evidence in this lane).
- Do NOT run the full suite. Solo-verify the two guards via
  `DREAMWORK_GUARDS="mdquote mdtable" DREAMWORK_HUB_GUARDS= just guards 3989X` after
  `ss -ltn` shows the port free — and the tree must be CLEAN afterward (that is the point).
- NEVER read_file an image. Text-only verification.
- Commit `git commit --only <paths>` (new test: `git add` first). Append ONE line to
  `.dreamwork/handoffs.md` under `## Pending` before your last commit (#398 obligation).
  No attn, no pkill -f.
