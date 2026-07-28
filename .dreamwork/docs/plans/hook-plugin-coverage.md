# Hook plugin coverage — #470 (what the hooks guarantee, and what is checked)

> **Status:** audit + one red-first integration test. The hooks' fail-safe
> contract is well-tested at the script level; the widest *testable* gap was
> that no test ran the **real** `lint.py` through the **real** hook
> subprocess against a genuinely broken ledger — the fake-lint tests proved
> the plumbing but passed over the integration. One test closes it. The one
> gap that cannot be closed without his harness running is stated as a
> ceiling, not faked.

## What each hook claims (source + SKILL.md)

All under `plugins/ud-dreamwork-hooks/`:

| component | the claim |
|---|---|
| `hooks/precompact_focus.py` | PreCompact: read loop state (`status.json` current task, `questions.md` open count), append one bounded record to machine-local `~/.config/dreamwork/hooks/<slug>/precompact-focus.jsonl`; always exit 0; <2s; rotate at 200; skip when plugin not loaded |
| `hooks/posttooluse_ledger_lint.py` | PostToolUse (`Write\|Edit`): when `questions.md`/`tasks.md` under `<target>/.dreamwork/` is touched in a loaded target, run `lint.py --target <target>`; report verdict; always exit 0; <5s |
| `install.py` | the ONLY path into `~/.claude/settings.json`; `--print`/`--apply`/`--force`; idempotent; timestamped backup; hardlink-aware in-place write (#369); reads back + verifies link count |
| `hooks/hookutil.py` | shared: stdin payload read (bounded), one-line JSON emit, consent gate, bounded values, machine-local config dir |

## Consent gate — no drift

`hookutil.dreamwork_loads_plugin` re-implements `plugin_resolver.parse_declared_plugins`'s heading + Load-line parse. The regexes are byte-identical (`_HEADING`/`_LOAD_LINE` vs `HEADING`/`LOAD_LINE`), casefolded `plugins` heading, backticked ID, bounded read. Both hooks gate on it and both are tested for the not-loaded → skipped path. **No drift.**

## Wiring into `just test` — NOT a #310 case

`just pytest` runs `python3 -m pytest -q` with no `testpaths`/`rootdir` scoping, so root collection picks up `plugins/ud-dreamwork-hooks/tests/`. Verified: `pytest --collect-only` lists all 32 hook test IDs; they run and pass (32 passed in 2.61s). The #310 failure mode ("doc said not-wired but it was") does not apply.

## Would a test fail if a hook stopped firing?

**In the real harness: no.** Every hook test invokes the script directly via
`subprocess.run([sys.executable, str(script)], ...)`. They prove the scripts
behave correctly *when called*; none go through the harness, so none would
notice if the harness stopped calling them. This is the fundamental,
untestable-without-his-harness gap, and per the brief it is a stated ceiling
rather than a faked test. The fake would synthesise a Claude Code dispatch so
completely it would test the synthesis.

What IS provably tested, per component, with named production lines:

- **PreCompact** — `run()` at `precompact_focus.py:88` (target derivation,
  consent gate, state read, bounded append, rotation). 10 tests.
- **PostToolUse** — `run()` at `posttooluse_ledger_lint.py:59` (file gate,
  consent gate, lint subprocess, verdict). 10 tests.
- **install.py** — `merge()`/`apply()`/`write_settings()`. 12 tests,
  including the `#369` hardlink class that asserts on the inode, not the file.

## The widest testable gap (now closed)

The PostToolUse fake-lint tests (`test_lint_nonzero_exit_reports_error…`,
`…_timeout…`, `…_warnings…`) substitute a throwaway script via
`$DREAMWORK_LINT`. They prove the hook's *plumbing* — nonzero exit →
`ok:False`, timeout → `ok:False`, `WARN` → `"warnings"`. They never run the
**real** `lint.py` against a **genuinely malformed** ledger. The one real-lint
test (`test_clean_ledger_reports_ok`) uses a valid fixture, so it only proves
clean→clean. A broken ledger written by an agent, flowing through the real
hook + real lint, was asserted by nothing.

**Closed:** `test_real_lint_catches_broken_ledger_through_hook` writes a
`questions.md` missing `## Open` (the ERROR `lint.py` flags at its
`check_questions`), asserts the precondition at runtime (real lint exits ≠0
on it), runs the real hook with no `$DREAMWORK_LINT` override, and asserts
`ok:False`.

Red-proof production lines (both nameable, neither circular — the test
introduces no seam; `subprocess` invocation and `$DREAMWORK_LINT` both
predate it):

1. `lint.py` `check_questions` — if lint stopped erroring on a missing
   `## Open`, the runtime precondition assert fires.
2. `posttooluse_ledger_lint.py` `subprocess.run` + returncode gate — if the
   hook stopped invoking lint, the broken ledger returns `ok:True` and the
   `ok:False` assert fires.

## The ceiling (stated, not faked)

Whether the harness actually fires these hooks after `install.py --apply`
wires them is not testable here. The install tests verify the snippet's
*shape* (commands, matchers, paths) and that it lands + reads back, but the
harness's dispatch is its own contract. A hook that silently stops firing
because the harness changed its event shape, or stopped reading
`settings.json`, is invisible to this suite by construction — the same
invisibility the loop lives with. The mitigation in place: the hooks are
fail-safe (their absence degrades, never blocks), and the install test
verifies the wiring shape against the file that was written.

## doc-map.md row wanted (not owned by this lane)

`test_this_repo_maps_its_own_plans` (test_lint.py) asserts the plans row
matches the directory, so this file needs the coordinator to union
`hook-plugin-coverage` into the alphabetical list in the
`.dreamwork/docs/plans/` row, same as `harness-containment` (#450) was. Until
then that one test WARN-fails; lint itself stays exit 0 (WARN, not ERROR).
