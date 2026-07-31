# Lane #726 report — `_to_posix` `lstrip("./")` mangling dotfile paths

## VERDICT (failure mode first — it sets the severity)

**FAILS LOUDLY.** A `begin` on `.dreamwork/lessons.md` returns exit 2 and
refuses at the read step:

```
begin: 'dreamwork/lessons.md' does not exist in the working tree
```

It never writes the registry — the mangled path `dreamwork/lessons.md` does
not exist in this repo, so `(root / "dreamwork/lessons.md").read_bytes()`
raises `FileNotFoundError`, and `begin` exits 2 before `_write_registry`.

This is the **small-bug** case, not the silent-mis-key case the brief feared.
No record is ever created under the mangled key, so there is nothing for
`#717`'s `(path, injected_sha)` lookup or `#710`'s history scan to match
against — they are never handed a key naming a nonexistent file. The
theoretical "#671 reads clean about a file it never examined" chain does not
fire, because the tool fails closed at `begin` rather than recording a bad
key and proceeding. **The bug blocks every dotfile/dotdir path (all of
`.dreamwork/`) from being red-proofed; it does not silently corrupt a gate.**

The brief's framing was conditional ("verify that chain before believing
this framing") — measured, and the loud-refusal arm is the one that holds.

## The fix (one line)

`dev/redproof.py:148` — `lstrip("./")` → `removeprefix("./")`:

```python
def _to_posix(path: str) -> str:
    # removeprefix, not lstrip: lstrip takes a CHARACTER SET, so lstrip("./")
    # eats every leading '.' or '/' and mangles dotfile/dotdir paths like
    # .dreamwork/lessons.md -> dreamwork/lessons.md (#726).
    return path.replace("\\", "/").removeprefix("./")
```

`removeprefix` (3.9+) strips the literal `"./"` prefix only. Chosen over
`normpath` because the function's job is "to posix + drop the optional `./`
leader", not full normalization (see Direction 2). The file already uses 3.9+
idioms (`str | None`, `from __future__ import annotations`).

Committed as `87da724d`.

## The deliverable — the test nobody wrote

`test_redproof.py`, new class `TestDottedPathRoundTrip` (3 tests):

1. **`test_to_posix_preserves_a_leading_dot_not_strips_a_charset`** — the
   unit-level pin. Asserts `"./watch.py" → "watch.py"` (the case that always
   passed) AND `".dreamwork/lessons.md" → ".dreamwork/lessons.md"` (the
   discriminating case). A test checking only `"./x"` passes today; this one
   cannot.
2. **`test_begin_on_a_dotted_path_records_the_correct_key`** — the registry
   key is the dotted path, not the mangled one. Asserts
   `armed[0]["path"] == ".dreamwork/lessons.md"` with a message naming the
   #671 consequence if it fails.
3. **`test_a_dotted_path_survives_the_full_round_trip`** — begin → sabotage →
   restore → check on `.dreamwork/notes.md`, exit 0, original byte-restored.

## Red-proof — both directions

### Direction 1 (test-level): revert fix, watch tests go red

Reverted `removeprefix` → `lstrip("./")`. All 3 new tests FAILED:

```
FAILED test_to_posix_preserves_a_leading_dot_not_strips_a_charset
  assert 'dreamwork/lessons.md' == '.dreamwork/lessons.md'   ← mangled key
FAILED test_begin_on_a_dotted_path_records_the_correct_key
  assert 2 == 0   ← begin refused (exit 2), loud failure
FAILED test_a_dotted_path_survives_the_full_round_trip
  assert 2 == 0   ← restore refused, begin never armed the path
```

The first failure quotes the **discriminating message** — the mangled key
`'dreamwork/lessons.md'` vs the expected `'.dreamwork/lessons.md'`. Restored
the fix; all 3 pass. **26 passed** total (23 original + 3 new).

### Direction 1 (dogfood, using the tool itself)

Target: `dev/redproof.py` (a NON-dotted path, since the dotted case was the
broken one). Snapshot taken AFTER the fix was committed, so the snapshot
captures the FIXED state (#608 — the state I must end on).

```
begin dev/redproof.py    → snapshotted (31539 bytes), state=armed
[sabotage: lstrip("./") reintroduced]
check                    → REFUSED exit 1: "1 begun-but-unrestored injection(s): dev/redproof.py"
restore dev/redproof.py  → injected sha fa6dffcb3605 recorded; original restored & verified
check                    → CLEAN exit 0: "1 injection(s) registered, all restored"
```

Tree matches the committed fix after restore (`git diff --stat` empty). The
history scan examined 1 commit, 0 hits.

### Direction 2: the case the fix still gets wrong

Probed `_to_posix` against the brief's candidate inputs:

| input | `removeprefix` result | notes |
|-------|----------------------|-------|
| `./watch.py` | `watch.py` | intended ✓ |
| `.dreamwork/lessons.md` | `.dreamwork/lessons.md` | **fixed** ✓ |
| `.hidden` | `.hidden` | preserved ✓ |
| `./.hidden` | `.hidden` | correct ✓ |
| `../x/y.md` | `../x/y.md` | **resolves outside the repo** ⚠ |
| `.//double.md` | `/double.md` | leading-slash leak (malformed input) ⚠ |
| `.` | `.` | a directory; `read_bytes` fails (pre-existing) |

**Open false-green: `../x/y.md` (parent traversal).** `removeprefix` leaves
it unchanged (it is not the `"./"` prefix), and `Path(root) / "../x/y.md"`
resolves to a sibling of the worktree root — `begin` would snapshot/restore a
file *outside* the repo. This is **pre-existing**, not introduced by the fix:
the old `lstrip("./")` mangled it to `x/y.md` (also wrong, differently). It
is out of scope for a one-line `lstrip`→`removeprefix` fix — closing it needs
a normalization/sandboxing decision, and `_to_posix`'s contract is "posix +
drop `./` leader", not "normalize and confine". Named, not closed.

The `.//double.md` case produces a leading-slash path that Python's `Path`
treats as absolute (`/double.md` at filesystem root) — a malformed input
where `removeprefix`'s "strip one prefix" semantics differ from `lstrip`'s
"strip all matching chars". Also out of scope (the input is malformed), and
pre-existing in spirit.

## Existing mangled keys — NONE

Grepped every `registry.json` under `~/.cache/ud-dreamwork/lane-scratch`
(26 registries across all lanes). All recorded paths:

```
status_sync.py, probe.py, dev/ledger.py, dev/journal_consume.py, router.js,
ledger_write.py, dev/redproof.py, briefs/boilerplate.md, watch.py,
tick_line.py, test_watch.py, lint.py, dev/guard_preflight.py, client/command.js
```

**Every path is non-dotted** — no `dreamwork/...` entry that would indicate a
stripped leading dot. No lane ever successfully `begin`-ed a dotted path (the
bug refused them all loudly), so no mangled records exist to orphan. The fix
breaks nothing.

## `lstrip`/`rstrip`-as-prefix audit of `dev/` (and the tree)

Grepped `.(lstrip|rstrip)(` across all `.py` files. **Only one multi-char
misuse exists: `dev/redproof.py:148` (this fix).** The other multi-char
findings are correct usage:

- `dev/reaper.py:79` `is_dead_lane` → `cwd.endswith(" (deleted)")` — correct
  (uses `endswith`, not `rstrip`). The `rstrip(" (deleted)")` at
  `test_reaper.py:46` is a test-only precondition assertion; it holds (the
  character-set strip mangles `"some-lane"`→`"some-lan"`, which is indeed `!=`
  the dead cwd), and is not the production logic.
- `task_origins.py:119` `.lstrip(" —·")` — deliberate character-set strip of
  leading spaces/em-dashes/middle-dots (bullet markup). Correct.
- All other `.lstrip()`/`.rstrip()` calls take a single char, no args, or use
  `startswith`/`endswith`. No other prefix-as-charset bug.

## Cited issues — opened and read

- **#683** (landed `20cba828`): the tool and its four verbs. Relied-on line:
  *"Nothing verifies the restore actually happened before the lane commits
  and hands off."* — `_to_posix` is the gate every verb's path flows through.
- **#717** (landed): *"Registry keys by (path, injected_sha)"* — the key
  that consumes `_to_posix`'s output. A mangled key would name a nonexistent
  file; the loud failure means no key is ever recorded, so this consumer is
  never handed a bad path.
- **#710** (landed `4484dd04`): *"the scan compares each commit blob against
  each RECORDED injected sha"* — `scan_history` builds `paths` from
  `e["path"]`. A mangled path would make the scan read blobs for a path no
  commit holds (`missing` in `cat-file --batch`, skipped) and report clean.
  The loud `begin` failure prevents this.
- **#671** (landed `6b0ceced`): *"a check that examined nothing must not read
  as passing"* — the principle a silent mis-key would violate. Measured: it
  does not fire, because `begin` fails closed.
- **#612** (landed `cc08d4d9`): volume. One line + 3 tests + this report.

## Rebase outcome

Branch base `1ab60a3c8633` == local `master` (`git rev-parse master`).
Master has not moved since dispatch; no rebase needed. One commit:
`87da724d fix(#726): _to_posix uses removeprefix not lstrip…`.

## Verification

- `python3 -m pytest test_redproof.py -q` → **26 passed** (23 + 3 new).
- `python3 lint.py` → **clean, exit 0**, no ERRORs (6 expected WARNs for a
  lane worktree: markdown-mode ledger, near-duplicate lessons, etc.).
- No browser guards run (coordinator owns the suite; ports busy).

## Dogfood report

1. **The tool refused the dotted path loudly — and that is the correct
   outcome for the wrong reason.** `begin` fails at `read_bytes`, which is
   the file-not-found guard, not a path-validation guard. A future code path
   that created the mangled file (`dreamwork/lessons.md`) would let `begin`
   proceed and record a key for a file that is not the one the lane named.
   The fix removes the mangle, but the underlying "no path validation" is
   worth a thought — not a bug to fix here, just an observation.
2. **The brief's "measure it" instruction was the highest-value line.** The
   severity framing (silent mis-key → #671) was plausible and scary; measuring
   took one command and downgraded it to "annoying loud refusal." Every brief
   that says "verify before believing" should be read as load-bearing.
3. **No friction with the tooling itself.** `dev/redproof.py begin/restore/
   check` worked first try on a non-dotted path, the snapshot captured the
   fixed state, and `check` caught the live injection and then certified the
   restore. The dogfood loop is tight.
