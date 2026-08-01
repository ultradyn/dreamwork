# #805 review lens C — contract drift

## Verdict

**CONCERNS — five real contract mismatches.** All five are statements about
behaviour that disagree with the behaviour they describe. I did not re-report
the already-filed citation-audit `--ledger`, bisect magic-word, MCP screenshot
cwd/fallback, or memory-value-validation defects.

Scope read: every first-parent merge and changed file in
`d45d964f..aadf579f`; module docstrings, argparse/help output, error prose,
changed tests and their assertion bodies, `just --list`, the doc map, README/
DREAMWORK, and the changed plans. The range contains 15 first-parent merges
and 46 commits total, despite the brief calling it sixteen changes.

## Findings

### 1. High — the loop's exactly-once instructions say wake lines have no receipt id, but they do

**Claim:** `SKILL.md:146-149` says *"the wake line carries no receipt id"* and
therefore tells the coordinator to recognise a later cursor receipt by content.
The nearby source description at `watch.py:4819-4822` also says a command
becomes a `watch-events.log` line and *"no file is written"*.

**Actual:** `watch.py:4859-4869` appends ` [receipt <id>]`; the `/command`
handler supplies the committed journal receipt at `watch.py:5712-5713`.
`.dreamwork/docs/plans/user-event-inbox.md:348-354`, merged in this range,
explicitly records that the wake id joins to the receipt and that the current
SKILL sentence is stale. The command also has two durable writes: the journal
receipt before dispatch and the `watch-events.log` line, so the sibling
*"no file is written"* comment is false literally and misleading historically.

**Observable sequence, both ways:** from the repo root:

```text
>>> watch.command_line('do-now', 'ship it', receipt_id='abc123')
'command via watch: do-now: ship it [receipt abc123]'
>>> watch.command_line('do-now', 'ship it')
'command via watch: do-now: ship it'
```

The first is the current journal-on path and contradicts SKILL. The second is
the documented legacy/no-journal branch, proving absence is a branch rather
than the current universal behaviour. A real `/command` POST makes the same id
observable in the HTTP receipt, journal `pending`, and wake line; the existing
`test_command_wake_line_carries_the_same_receipt_id_as_the_journal` exercises
that join.

**Why it matters:** the stale instruction makes the coordinator deduplicate by
content even though a stable identity is available. Two equal-text commands
with different receipt IDs are distinct actions; content matching can collapse
them. This is the highest-confidence finding: the owning plan already calls the
sentence stale, and ledger `#527` says, *"command_line gains a receipt-id suffix
... every /command wake-line now names the receipt the SAME POST committed."*

### 2. Medium — `citation_audit --quiet` is a no-op and the undocumented default is already quiet

**Claim:** `dev/citation_audit.py:27-32` documents `--quiet` as suppressing
per-citation detail. `format_report(..., quiet=False)` at lines 276-301 also
defines detailed output as the default. The usage prose does not list
`--verbose`.

**Actual:** argparse implements both flags at lines 326-335, but line 360 calls
`format_report(report, quiet=not args.verbose)` and never reads `args.quiet`.
Default output and `--quiet` are therefore byte-equivalent summaries;
`--verbose` is the actual detail switch.

**Observable sequence, both ways:** against the same live corpus and main
`.dreamwork` directory, default and `--quiet` each emitted 5 lines; `--verbose`
emitted 7. Removing `--quiet` does not restore the documented details, while
adding the prose-undocumented `--verbose` does. This is distinct from, but
should be handed to the existing lane fixing, the already-filed `--ledger`
mismatch in the same module.

**Doubt:** the compact default may be an intentional later UX choice. I found
no such decision in the owning module docstring or the relevant ledger entries.
If intentional, the defect is still the stale usage prose and dead `--quiet`
flag; if not, line 327 is the behavioural defect.

### 3. Medium — the concurrency advisory's headline docstring describes the trigger that was removed

**Claim:** `dev/concurrent_tests.py:6-10` says the advisory reports *"a
memory-pressure token when swap is heavily used."*

**Actual:** lines 179-187 and 232-255 deliberately key only on
`MemAvailable < 8 GiB`; the implementation comments explicitly say *"never on
swap-used"*. This was the point of the `#785` change.

**Observable inputs, both ways:** direct calls to `render()` produced:

```text
50 GiB swap used + 28 GiB available
=> concurrent tests: no other pytest suites; 0 browser/guard processes (advisory)

0 GiB swap used + 2 GiB available
=> ...; mem: 2G available of 60G (low available memory ...) (advisory)
```

Thus the documented trigger can occur with no token, and the token can occur
without the documented trigger. Ledger `#785` confirms the deliberate actual
contract: *"the advisory keys on available memory rather than swap-used."*
This is documentation drift, not a request to revert the correct implementation.

### 4. Medium — the doc map calls the migration shim the durable queue

**Claim:** `.dreamwork/docs/doc-map.md:33` says `.dreamwork/tasks.md` is *"The
queue's durable half: open tasks, permanent ids, next id"* and is kept current
with queue changes.

**Actual:** `.dreamwork/tasks.md:1-5` is only a migration notice. The durable
open/landed records and id sequence live in `.dreamwork/ledger.sqlite3` behind
the CLI. `SKILL.md` already describes this backend split correctly, and ledger
`#294` records the live cutover: *"tasks.md is a #458 shim"* and *"the burndown,
/tasks badge, status section, lint, and status_sync all read the store now."*

**Observable sequence, both ways:** reading the tracked file yields five notice
lines and zero task entries or next id; `python3 dev/ledger.py counts --ledger
/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md` resolves the
sibling store and reports the live nonzero open/landed population. The file the
row names contains none of the state the row claims, while the state exists in
the unmentioned store.

**Why it matters:** this is the exact stale-tree class `#793` was meant to sweep.
A docs-freshness reader following this row is directed to maintain a frozen shim
instead of the source of truth.

### 5. Low/medium — the startup benchmark calls a minimal path an upper bound

**Claim:** `dev/startup_benchmark.py:2-7` says the fresh-process result is *"an
upper bound for a future version verb with the same import graph."*

**Actual:** `_TARGET_CODE` at lines 29-34 performs only import, one
`module.__name__` lookup, and sentinel printing. Any future verb with the same
import graph plus nonzero version computation/formatting has that measured cost
**plus** its work. Holding environment/import graph constant, the minimal probe
is a floor (or an estimate of a deliberately negligible-work verb), not an
upper bound.

**Observable sequence, both ways:** compare the timed target
`python -c 'import M; print(sentinel)'` with
`python -c 'import M; compute_version(); print(version)'` for the same `M`.
When `compute_version()` takes positive time, the future path is slower than
the claimed upper bound. If `compute_version()` is the same trivial name lookup,
the two approximate one another; that is the narrower model stated correctly
in `.dreamwork/docs/plans/modularity-and-startup.md:50-55` (*"useful work is
negligible"*), not an upper-bound guarantee.

**Doubt:** this is probably terminology drift rather than a bad benchmark. The
plan uses the measurements responsibly and names uncontrolled noise. A small
wording fix ("estimate/floor for a negligible-work version path") closes it.

## Lens rules verified before judging

I opened the selected ledger entries and resolved each exact bolded lesson title
to one head before relying on it:

- **A guard's message must name a mode the guard can actually detect, and the
  way to know is to construct that mode and watch it fail.** Ledger `#651` gives
  the discriminating instance: the unterminated brace walk passed in exactly
  the mode its message named. I used two-way observable inputs above rather than
  trusting prose or test names.
- **A tool that answers out of a store which did not resolve manufactures the
  confident wrong citation the brief exists to prevent.** Ledger `#671` records
  the governing zero-case: *"Zero entries now says DID NOT REVIEW rather than
  'nothing to review'."* The initial bare `get 805` correctly refused, and the
  main-ledger invocation supplied the evidence used here.
- **An unanchored split on `## Recently landed` hit a PROSE mention of the
  heading, not the heading.** Ledger `#440` says the landed tool is *"the one
  supported path"* and anchors/asserts both headings. I treated the store-aware
  CLI, not a hand-parsed prose projection, as ledger authority.
- **A citation must carry its own evidence, and a line number carries none —
  the fix for two miscitation findings had the same disease as the disease.**
  Ledger `#764` chose exact bolded lesson titles because they self-verify; each
  title above resolved exactly once. File coordinates in findings are current
  reproduction sites, not authority citations.

## Verification and red-proof accounting

This was a read lens and changed no production code or checks, so there was no
injection-style red-proof to run. Each finding instead carries both observable
directions: the claimed state that the implementation rejects/ignores and the
implemented state that the claim omits. No browser guard or full suite was run,
as required by the lane brief.

After the report commit, local `master` advanced repeatedly. The branch rebased
cleanly each time; no conflict resolution was needed. The exact final base/head
pair is recorded in the coordinator-inbox completion correction. Final checks
on the rebased state:

- `python3 dev/redproof.py check` — `check: calm — no injections registered
  (role: reviewer; opt-in discipline; nothing to evaluate).`
- `python3 lint.py` — clean with the same five-WARN row set named by the brief:
  worktree ledger absent, status absent, zero related-marker entries,
  pre-existing lesson near-duplicate, and seven ledger checks examined nothing.
- `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` —
  clean with the same single main-checkout WARN row: the pre-existing lesson
  near-duplicate.
- `just pytest $(python3 dev/repo_wide_guards.py list)` — the two listed
  assertions passed (`test_no_raw_connect` and the ledger verb-map coverage),
  2 passed in 0.34s. No browser process was started.

## Outside lens

Nothing new pursued. I explicitly set aside the correctness, cleanup, and
resource-management defects already filed by the earlier lenses.

## DOGFOOD REPORT

- The head says *"Sixteen changes"* but its own requested range contains 15
  first-parent merges (`git rev-list --first-parent --count` = 15; 46 commits
  total). Including the excluded lower endpoint `d45d964f` would make sixteen,
  but `d45d964f..aadf579f` does not include it. The inventory instruction and
  count therefore disagree.
- The task-specific head says bare `python3 dev/ledger.py get 805`; the appended
  contract says that exact form refuses in a worktree and supplies the
  `--ledger` form. The bare call did refuse at exit 2, then the documented main
  invocation succeeded. This cost one intentionally doomed call and is the same
  contract shape this review is looking for.
- The repository's AGENTS instructions require graph-first code discovery, but
  the graph service has no indexed project for this repository. It returned
  `project not found or not indexed`, so this lane had to use the permitted
  scoped-diff/source fallback. No result was lost, but the advertised primary
  discovery route was unavailable.
- The standing brief says `dev/repo_wide_guards.py list` *"today ... (37 tests,
  ~0.4s)"*. On the final rebased tree it listed two node ids and pytest collected
  exactly 2 tests, not 37. Both assertions are useful and passed; only the
  embedded count has drifted. A generated count or omission is safer than a
  number copied into every lane brief.
