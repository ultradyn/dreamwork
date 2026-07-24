# ud-dreamwork-github — first plugin (incubation plan)

Human-proposed 2026-07-25 (~04:47). The first real `ud-dreamwork-*`
plugin; it also validates the whole dormant plugin surface (init
discovery, DREAMWORK.md Load/Don't-load, wizard extension).

## Core shape

- **Skill**: `~/.llm-general/skills/ud-dreamwork-github/SKILL.md`,
  discovered by name at init like any plugin; loaded per DREAMWORK.md.
- **Process discovery (init extension)**: fairly general, works on most
  repos — `gh auth status`, remotes, `.github/workflows`, labels,
  PR/issue conventions, branch protection, release flow → documented as
  `.dreamwork/docs/github-processes.md` (living doc; doc-map entry).
- **Monitoring (loop extension)**: with a Monitor tool, a poll loop on
  `gh api` emits one line per new/changed issue or PR; without one, the
  tick loop checks. New items become typed tasks (label-informed:
  bug/task/chore) with `gh:` metadata, and join normal selection.
- **Progression**: work gh-sourced tasks as ordinary increments until
  blocked; blocked → questions.md, plus an issue comment when authorized.
  Commits reference issues per repo convention ("fixes #N").
- **Wizard extension**: which labels to watch; authority levels
  (comment / push / open PR / merge — each explicit in DREAMWORK.md);
  auto-progress on or off.

## Open design questions (need Max; recs inline)

1. Poll cadence and quota: rec 90s, one batched `gh api` call with a
   since-cursor — rate-trivial.
2. Default authority when DREAMWORK.md is silent: rec read-only — watch,
   capture, progress locally; never comment/push/PR until authorized.
3. Multi-repo: rec v1 is single repo (the target's origin) only.
4. GitHub cursors/etags state: rec `~/.config/dreamwork/github/<slug>/`
   (machine-local ephemera precedent).

## Build stages (post design review)

1. SKILL.md draft + the discovery-doc generator guidance.
2. Monitor wiring (poll loop + tick fallback + events into tasks).
3. Progression protocol (blocked handling, comment templates, authority
   checks).
4. Dogfood on a real repo with issues (candidate: hark or c2c).
5. install-symlinks + concise index entry.
