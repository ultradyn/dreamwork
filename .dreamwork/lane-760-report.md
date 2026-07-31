# Lane 760 report

## Outcome

`dev/reap.py` (invoked as `just reap-lane <path>`) classified each `git status`
entry into `untracked` / `ignored` / `tracked` and then **threw the distinction
away** at the only place a human reads: a single collapsed counter
`untracked-ignored=N`. So a lane holding an uncommitted deliverable and a lane
holding only `BRIEF.md` + `__pycache__/` printed byte-identical output and both
said "reap gate OK". That is `#136` inside the tool built to prevent exactly
that class of loss, and it had already reproduced twice on the night this task
was filed (#686's own report and #661's, both left untracked and committed by
hand).

This is a **reporting fix, not a gating one.** The gate stays tracked-only
(`#755`): `BRIEF.md` is untracked in every lane, so refusing on `untracked > 0`
would fire on every healthy lane — a gate people learn to `--force` past is
worse than no gate. The fix splits the counter and **names** the untracked
paths a coordinator needs to see.

What changed in `dev/reap.py`:

- `_summary` now prints `untracked=N ignored=M` separately, never collapsed.
  The denominators print on the clean run too (`#671`).
- A new `EXPECTED_UNTRACKED = frozenset({"BRIEF.md"})` literal names the one
  file genuinely present untracked in every lane (the coordinator writes it and
  never tracks it). Anything untracked **not** in this set is **named** on
  stderr via `_note_unexpected` — reporting only, never dropping (`#702`).
- `_note_unexpected` runs on every classified run, not only the clean one
  (`#671`): a deliverable left untracked alongside tracked dirt is no less
  about to be lost.
- `_unknown` and the `worktree remove` failure hint updated for the split
  signature; a leftover `scratch` variable reference in the remove-failure hint
  corrected to `untracked or ignored`.

### The two design decisions the brief asked for

**Is the known-scratch set a literal (`BRIEF.md`), or "anything the gate was
told to expect"?** A literal of one filename. Used `igc-method.md` framing: the
goal is "surface untracked paths that may be work"; the ideas were (a) a
literal `{BRIEF.md}`, (b) a configurable expected-set. (b) is a derive risk
(`#596`'s family — a computed value restated and rotted) **and** a
feature-gate people tune until it silences the signal, which is the failure
this tool exists to prevent. (a) is a single fact about the lane model that
does not change unless the coordinator stops writing `BRIEF.md`, and a
one-line literal with a comment is the honest smaller thing (`#612`). If a
second expected-scratch filename ever appears, that is the moment to revisit —
not before.

**Should `.dreamwork/lane-*-report.md` be named explicitly?** Yes, by
**not** suppressing it. It is deliberately **not** in `EXPECTED_UNTRACKED`: it
is the lane deliverable, untracked until committed, and suppressing it would
hide the one signal this tool exists to surface. It is named like any other
unexpected untracked path. The tool does not pretend to classify work from
scratch beyond the `BRIEF.md` literal (`#702`); the path name speaks for
itself, and a coordinator reading `NOTE: untracked path beyond expected
scratch: .dreamwork/lane-NNN-report.md` knows exactly what it is.

## Commits

- `8aade1e9 feat(#760): split untracked/ignored counters and name unexpected
  untracked paths`

Rebased onto current `master` before reporting (master moved 4 commits: the
`#645` increment-2 migration landed). `git rev-list --count HEAD..master` = 0.

## Red proof

### Direction 1 — the collapsed counter hid a deliverable

Built a scratch repo with two linked worktrees that the **current** tool could
not distinguish:

```
----- DANGER lane (holds an uncommitted deliverable) -----
reap examined path=/tmp/reap760-pair/danger tracked-dirty=0 untracked-ignored=2 unmerged-commits=0
reap gate OK (check only)

----- SAFE lane (only expected scratch + cache) -----
reap examined path=/tmp/reap760-pair/safe tracked-dirty=0 untracked-ignored=2 unmerged-commits=0
reap gate OK (check only)
```

Both printed `untracked-ignored=2` and "reap gate OK". The deliverable was
invisible. Under the fix they separate:

```
DANGER: tracked-dirty=0 untracked=2 ignored=0  + NOTE: .dreamwork/lane-999-report.md
SAFE:   tracked-dirty=0 untracked=1 ignored=1  + (no NOTE)
```

The discriminating output **names the report path**, not just a changed count.

The deliberate production injection (`dev/redproof.py`) reintroduced the `#760`
bug in `dev/reap.py`: collapsed the counter back to
`untracked-ignored={untracked}` and dropped the `_note_unexpected(unexpected)`
call. Both new tests failed red at the discriminating assertion:

```text
E       AssertionError: assert 'untracked=2' in 'reap examined path=... tracked-dirty=0 untracked-ignored=2 unmerged-commits=0\n...'
```

`dev/redproof.py restore dev/reap.py` restored the fixed snapshot; the focused
tests then passed. The injection was verified to reach the code under test
(it changed `_summary`'s output string, which the tests read directly via the
CLI subprocess — no scaffolding stood in front of it).

### Direction 2 — where the split still loses work

Three residuals, all named rather than hidden:

1. **A deliverable that matches no pattern** (an ad-hoc `notes.md`). The tool
   names it (`NOTE: untracked path beyond expected scratch: notes.md`) but
   nothing marks it *as work*, so judgement still rests with the reader. This
   is correct: the tool cannot classify intent, and pretending to would be the
   `#702` drop in another form. Demonstrated:

   ```
   NOTE: untracked path beyond expected scratch: notes.md
   reap examined path=... tracked-dirty=0 untracked=2 ignored=0 unmerged-commits=0
   reap gate OK (check only)
   ```

2. **An ignored-but-valuable file** (`.dreamwork/applied.md` is gitignored and
   real). Ignored paths are counted (`ignored=1`) but **never named** on the
   clean/force path — only the `--force` discard lines name them. A reap here
   destroys the file with no path-level warning on the check path. This is a
   real gap. Naming every ignored path would drown the signal in `.pyc` noise,
   so the honest smaller thing is to leave it as a documented residual: the
   `.gitignore` policy (should `.dreamwork/applied.md` be ignored at all?) is
   the lever, not the reap tool.

3. **Large-worktree slowness/truncation.** `git status --porcelain -z
   --untracked-files=all --ignored` reads the whole tree; on a very large
   worktree this is slow. This is **unchanged** by the fix — the fetch already
   happened in `_status_paths`; my change only affects how the parsed rows are
   reported, not how they are fetched.

Final `python3 dev/redproof.py check --require 1` output, verbatim:

```text
history: examined 1 commit(s) since efbfcd5c64a8 (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dev/reap.py (sha 191d1471d72e, hint: 'f"untracked-ignored={untracked} unmerged-commits={unmerged}"')
```

## Verification

`test_reap.py` was 187 lines / 9 tests as landed. After: 243 lines / 11 tests
(2 new discriminating `#760` tests; the existing 9 updated to the split
counter format).

```text
python3 -m pytest test_reap.py -q -n 2
11 passed in 2.20s
```

`just reap-lane` exercised against a scratch worktree (never a live lane). The
deliverable lane names `.dreamwork/lane-777-report.md` on both `--check` and
`--force`; the clean lane reads `untracked=1 ignored=1` with no NOTE; real
`--force` removal succeeds end-to-end.

```text
python3 lint.py
clean (6 warning(s))
```

The six warnings are the expected worktree-only baseline (`#611`/`#667`: the
gitignored ledger store does not travel; `status.json` ephemera; pre-existing
`questions.md`/`lessons.md` content flags). No ERRORs. Inspected per-message,
not by total.

No browser guards were run and no ports were bound.

## DOGFOOD REPORT

- **The brief's two design questions were the right ones and were clearly
  framed.** The literal-vs-configurable choice and the report-naming choice
  were both genuine forks; stating the reasoning in the code comments was
  straightforward because the brief named the governing lessons (`#612`,
  `#596`, `#702`).
- **Master moved during the run** (the `#645` increment-2 landed, 4 commits).
  Rebased cleanly; no conflicts. The redproof history scan re-evaluated
  against the new base and stayed clean.
- **One self-inflicted snag worth recording:** on the first red-proof pass I
  applied a sloppy injection (relabeled the summary but left the value wrong),
  then used `forget` to discard it — and forgot that `forget` does not restore
  the working tree. The next `begin` snapshotted the sabotaged file. Caught it
  by grepping for `untracked-ignored` before re-beginning, hand-restored the
  `_summary` body, re-ran the full suite to confirm green, then re-began. The
  lesson: `forget` is tree-inert by design; verify the tree is the state you
  want before the next `begin`. No harm done, but it cost a few minutes.
- **`dev/redproof.py` was straightforward to use.** The `begin`/`restore`/`check`
  protocol and the `--require 1` gate made the restore discipline checkable
  rather than aspirational.
