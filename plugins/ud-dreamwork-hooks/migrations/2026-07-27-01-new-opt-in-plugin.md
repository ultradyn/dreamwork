# 2026-07-27 — ud-dreamwork-hooks: nothing to migrate

## What changed

`ud-dreamwork-hooks` is a new, opt-in plugin. It owns no durable
target-side shape: its only writes are machine-local
(`~/.config/dreamwork/hooks/<target-slug>/`) and a human-invoked
`install.py --apply` against `~/.claude/settings.json`.

## How to apply

Nothing. Existing installs need no migration. Targets that want the
plugin record `Load: ud-dreamwork-hooks` in DREAMWORK.md and,
separately, run `install.py --apply` if they want the hooks wired into
Claude Code settings.

## Consent

Needs: none. Both acts (Load line, --apply) are explicit and recorded by
the human at the time.
