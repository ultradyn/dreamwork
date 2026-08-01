# Brief #548 — bdinput guard: bind the cap to the production constant

**Task** (ledger #548, origin loop): filed from the #546 merge gate —
the coordinator's independent red-run reverted `BURN_LIMIT_CAP`
256→168 in `watch.py` and the `bdinput` guard PASSED. A green red-run
is a finding, never a relief. Root cause (read in source, confirmed):
`dev/capture/bdinput.mjs:159` derives its cap from the rendered page
itself —

```js
const CAP = Number(pre.max);   // the input's own max attribute
```

— so the guard is self-consistent at ANY cap value. The production
literal (`watch.py:3712 @ e2acedf5` `const BURN_LIMIT_CAP = 256;`, rendered into
`max=` at watch.py:3931 @ e2acedf5) is bound by nothing.

## Scope

One file: `dev/capture/bdinput.mjs`. No production code changes.

The guard must pin the rendered `max` to the production constant
instead of trusting it:

1. Read `watch.py` source (repo-root relative to the guard file;
   follow how sibling guards locate the repo root) and extract
   `BURN_LIMIT_CAP` with a regex over the `const BURN_LIMIT_CAP = <n>;`
   assignment. **Assert exactly one match** — zero matches (renamed
   constant) or two (a second assignment appeared) are both guard
   failures, loudly. This is the precondition assertion: the extraction
   the whole binding depends on.
2. Assert the rendered input's `max` attribute **equals the extracted
   constant** — this is the binding the guard lacked. Only then use the
   extracted value as `CAP` for the existing cap-dependent checks.
3. Keep every existing check intact otherwise; this is a binding
   addition, not a rewrite.

## Hard contracts

- **Red-first, and your red IS the finding's repro**: sabotage
  `watch.py:3712 @ e2acedf5` (256→168 — a pre-existing line you did NOT inject),
  run the guard, watch the new binding check FAIL by name. cp-restore
  byte-identical (verify with `cmp`), never `git checkout`. Also prove
  the extraction precondition reds: temporarily rename the constant in
  the sabotaged copy and confirm the guard fails on the extraction
  assertion, not with an obscure crash.
- **Solo guard runs only**: pin port **39895** —
  `ss -ltn | grep 39895` must show it free first (if occupied pick
  another in 39890-39899 and record which).
  `DREAMWORK_GUARDS="bdinput" DREAMWORK_HUB_GUARDS= just guards 39895`.
  bdinput is already in DEFAULT_GUARDS — no registration needed.
  Another lane (lane-551remind) may be running its own guard on a
  different port concurrently; the `ss` check is the handshake.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
- **ONE `.dreamwork/handoffs.md` `## Pending` line** before your final
  commit (#398 obligation): #548, sha, date 2026-07-30,
  lane-548cap, what landed, red proofs, flags.
- **Commit with `git commit --only <paths>`**. Targeted pytest only
  (nothing in pytest covers this guard — lint's guard-registry checks
  are the coordinator's gate). Never `just test`; never attn; never
  `pkill -f`.

## Lane-owns declaration

You own: `dev/capture/bdinput.mjs` and your handoffs line.
You do NOT own: `watch.py` (sabotage it for the red proof, restore it,
never commit it), `justfile`, `lint.py`, any other guard.

**Fleet**: lane-551remind is in flight on the posture region of
`watch.py` — disjoint from your guard file; no merge interaction.

## Report shape

Final report: commit(s); the two red proofs (cap revert → named FAIL;
constant rename → extraction FAIL) with restore verification; the green
solo-guard verdict lines; port used; any deviation with the reason.
