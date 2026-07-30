# Brief #387 — the ledger-lint hook's Bash/mtime path (repo side only)

**Task:** #387 (P2, dogfood) — the ledger-lint hook cannot see how the
coordinator actually edits the ledger. `~/.claude/settings.json` registers
`posttooluse_ledger_lint.py` under `PostToolUse` with matcher `"Write|Edit"`,
but structural ledger edits go through Bash heredocs, so the hook has not
fired on a single real ledger write since installation. The task body has
already done the design work — **read it first** (`python3 dev/ledger.py get
387`): option (a) (add `Bash` to the matcher) is measured *inert*, not merely
expensive — a Bash event's `tool_input` carries a command string, not a
`file_path`, so the hook would fire and immediately decline every time. The
surviving rec is **mtime, not the payload**: on a Bash event, ignore
`tool_input`, compare the two ledger files' mtimes against a small stored
state, and lint only when one moved. Robust to ANY writer (heredoc, sed, an
editor, another agent), at the cost of one `stat` per Bash call.

## Scope discipline (the consent boundary)

The matcher widening (`Write|Edit` → `Write|Edit|Bash` in
`~/.claude/settings.json`) is **install-side and behind #465's pending
consent — NOT your act**. Your branch is inert until that lands (the same
shape as #493's inert axis): implement it, test it by driving `run()` with
fabricated Bash payloads, and leave registration untouched. Do not edit
`~/.claude/settings.json`, do not run the plugin's `install.py`, do not
touch anything outside the repo.

## What to build

In `plugins/ud-dreamwork-hooks/hooks/posttooluse_ledger_lint.py`:

1. **Bash branch.** When `tool_input` has no `file_path` (a Bash event),
   resolve the target from the event's `cwd` (verify the real payload shape
   from `hookutil.py` and the plugin's tests/SKILL.md — decide from
   evidence, and if `cwd` is absent or not a dreamwork target, skip with a
   named reason). Skip unless `hookutil.dreamwork_loads_plugin(target)`.
2. **mtime state.** A small state file under the target's `.dreamwork/`
   (the `.status-keys` precedent: lint.py already owns one there; name
   yours distinctly, e.g. `.ledger-lint-mtimes.json`). Compare the current
   mtimes of `questions.md` + `tasks.md` against the stored values; lint
   only when one moved, then store the new values. A missing ledger file is
   not an error (a target may have only one). A missing STATE file: seed
   without linting — a write that happened before the hook first looked is
   not this hook's window (record this decision and its reason in the
   module docstring; if you measure a reason to lint-on-first-sight
   instead, say so and justify).
3. **Keep the existing contract.** Stdlib only; one JSON object on stdout;
   ALWAYS exit 0; bounded runtime (the mtime check is O(1) — the lint
   subprocess keeps its existing timeout); the Write/Edit `file_path` path
   behaves byte-for-byte as today.
4. **file-formats.md is coordinator-owned** — the state file is a
   loop-written/tool-parsed file, so its shape needs a contract line. Do
   NOT edit file-formats.md; flag the exact shape in your report and the
   coordinator lands it at the gate.

## Red-first requirements

- Extend `plugins/ud-dreamwork-hooks/tests/test_posttooluse_lint.py`
  (drive `run()` with fabricated payloads, the file's existing idiom).
  Tests born-red BEFORE the implementation: a Bash event with a moved
  ledger mtime triggers a lint; a Bash event with unmoved mtimes does not;
  a Bash event with no state file seeds silently; the Write/Edit path is
  unchanged.
- Runtime preconditions derived, not assumed (the companion rule): the
  fixture really moved the mtime; the fixture target really loads the
  plugin.
- Red-proof by sabotaging your production line (e.g. the mtime comparison)
  → the named test FAILs → `cp`-restore byte-identical (`cmp`), never
  `git checkout`.
- Run the plugin's whole test dir, plus `python3 -m pytest
  test_lint.py -q` to prove no core drift.

## Lane-owns

- `plugins/ud-dreamwork-hooks/hooks/posttooluse_ledger_lint.py`
- `plugins/ud-dreamwork-hooks/tests/test_posttooluse_lint.py`

**NOT** `~/.claude/settings.json` or any installed copy (consent boundary),
NOT `install.py`, NOT `hookutil.py` (read it; if it genuinely needs a seam,
flag it), NOT core `lint.py` / `ledger_parse.py` / `test_lint.py`
(lane-557projection owns those), NOT watch.py, NOT file-formats.md (flag).

## Hand-offs obligation (#398)

On completion append ONE line under `## Pending` in `.dreamwork/handoffs.md`
(that literal path): `- **#387** · landed \`<sha>\` · <date> · by
lane-387hook — <what>`. Bare shas, no parentheticals. Never claim a model
(#469 — a lane cannot know its own).

## Constraints

Never `just test`; no ports, no browser, no guards. `git commit --only
<paths>` (a NEW file needs `git add <file>` first). Never `read_file` an
image. No `attn`. Never `pkill -f`.
