---
name: ud-dreamwork-hooks
description: >
  Dreamwork plugin — optional Claude Code harness hooks for the loop, OFF by
  default. A PreCompact hook writes a bounded "preservation focus" record
  (current task, open-question count, trigger) to machine-local state before
  every compaction; a PostToolUse hook runs the repo's lint.py after
  Write/Edit touches the .dreamwork ledger (questions.md, tasks.md) so a
  silently-unparseable ledger is caught at the moment it is written. Both are
  fail-safe: single-JSON stdout, always exit 0, never block compaction or a
  tool call. Load only via an explicit DREAMWORK.md `Load:` line; wiring into
  ~/.claude/settings.json happens only through a human-invoked install.py.
---

# ud-dreamwork-hooks — harness hooks for the dreamwork loop

A plugin to [ud-dreamwork](../../SKILL.md); its Guardrails and
`writing-plugins.md` bind everything here. One concern: two optional Claude
Code hooks that protect the loop at the moments the loop cannot protect
itself — right before compaction, and right after the ledger is edited.

Both hooks are **off by default** and **fail-safe**: each reads one JSON
event on stdin, prints exactly one JSON object on stdout, and always exits
0. A hook failure must never block or skip compaction, and never block a
tool call. Wall budgets: PreCompact < 2s, PostToolUse < 5s.

## When to load

Load when the target runs the loop under Claude Code and Max wants (a) a
durable record of what the session was holding across compactions, and/or
(b) immediate lint feedback when a ledger edit breaks the shapes
`file-formats.md` states. Skip on non-Claude-Code harnesses — the hooks are
Claude Code event shapes.

## The two hooks

- **`hooks/precompact_focus.py`** (PreCompact, manual and auto triggers):
  reads the loop's current state (`.dreamwork/status.json` current task,
  open-question count from `questions.md`) and appends one bounded record
  to `~/.config/dreamwork/hooks/<target-slug>/precompact-focus.jsonl`
  (machine-local, never committed, rotated at 200 records). The note cannot
  buy landing time — it exists so a post-compact session can see what it
  was holding. Missing/unreadable state is recorded as a note, not an
  error; a target with no `.dreamwork/` reports `ok:false` and writes
  nothing.
- **`hooks/posttooluse_ledger_lint.py`** (PostToolUse, matcher
  `Write|Edit`): when the touched file is `<target>/.dreamwork/questions.md`
  or `tasks.md`, runs the core repo's `lint.py --target <target>` (4s
  timeout; `$DREAMWORK_LINT` overrides the lint path) and reports
  `{"ok":true,"lint":"clean"|"warnings"}`. Missing lint.py, non-zero exit,
  or timeout reports `ok:false` with the lint output tail — still exit 0.

Both hooks re-check the consent boundary at runtime: if the target's
`DREAMWORK.md` does not record `Load: ud-dreamwork-hooks` in its Plugins
section (same parse as `plugin_resolver.py`), the hook reports
`{"ok":true,"skipped":true}` and does nothing.

## Installer contract — no silent machine-config mutation

Wiring the hooks into `~/.claude/settings.json` is a machine-config change,
so it happens **only** by explicit human invocation:

```bash
python3 install.py --print   # the exact snippet, to paste by hand
python3 install.py --apply   # idempotent merge; timestamped backup first
```

`--apply` refuses to overwrite an existing-but-different entry for these
hooks without `--force`, preserves all unrelated settings, and a second run
is a no-op. Loading this plugin never auto-applies. The two recorded acts
are separate on purpose: the DREAMWORK.md `Load:` line is consent to use
the plugin; `install.py --apply` is the machine-config act.

**If the settings file is hardlinked, `--apply` writes in place** (#369). An
atomic `os.replace` rebinds only the name it is given and leaves any other
name on the old inode with the old bytes, while exit 0, a timestamped backup
and an idempotent re-run all report success. So above one link the write
trades atomicity for the link, which is why the backup is taken first and its
path is always reported.

Either way `--apply` then reads the file back, compares it to what it wrote,
re-stats the link count, and **fails with exit 2** naming the counts rather
than claiming a success it cannot see. When a link was preserved the JSON
result says `"hardlinked": <count>`, taken from **after** the write, never
predicted from before it.

**On this machine that path is not taken, and the reason is worth stating**
because it was measured wrong once: `~/.claude/settings.json` and
`~/.claude-w/settings.json` do share one inode (`256518042`), but
`st_nlink` is **1** — `~/.claude` is a *symlink* to `~/.claude-w`, so there
is one file reached by two paths, not two links to one file. Same inode does
not mean hardlinked, and the difference decides whether a rename strands
anything. Under a directory symlink it strands nothing.

## Authority

- Read-only against the target: hooks read `.dreamwork/` state, write
  nothing there.
- Writes are machine-local only: `~/.config/dreamwork/hooks/<target-slug>/`.
- No loop machinery is touched; no tasks, commands, or maintenance items
  are contributed. Subagent and `attn` guardrails unchanged.

## Init extension

On load (after resolution per `writing-plugins.md`): check whether the
settings wiring is present (`install.py --print` output vs
`~/.claude/settings.json`) and report the state — wired, or available but
not wired. Never wire it. If the human wants it wired, hand them the
`--apply` command or run it with their explicit say-so in the session.

## State summary

- `~/.config/dreamwork/hooks/<target-slug>/precompact-focus.jsonl` —
  machine-local ephemera, rotated, never committed.
- `~/.claude/settings.json` — modified only by human-invoked
  `install.py --apply` (timestamped `.bak-<ts>` alongside).
- DREAMWORK.md Plugins section — the `Load:` decision; no further
  authority lines exist because the plugin takes no external actions.
- `migrations/` — one note: existing installs need nothing (new opt-in
  plugin). No versioned target-side shape, so no `.dreamwork/*-version`
  stamp.

## Non-goals

Blocking compaction to buy landing time (impossible by design; the record
is the mitigation); linting non-ledger files; auto-applying settings;
supporting non-Claude-Code hook systems in v1.
