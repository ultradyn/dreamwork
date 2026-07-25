# Knowing which dreamwork you are, and what changed since (#194)

Human-proposed 2026-07-25 17:07, verbatim intent preserved below. This is
the plan; the task is a thin pointer.

## His design

- An executable **`ud-dw-githash`** in the skill folder (or
  `<skill-folder>/bin/`), called **every time ud-dreamwork is loaded**,
  including the second and later loads in one session.
- In a git checkout it returns the most recent hash **plus a dirty
  indicator and count**.
- **In the release pipeline the file is replaced** — GitHub CI swaps it
  for one that prints the hash being released, so the resulting zip
  carries a hardcoded version. Same interface, different implementation.
- At start, compare it against **DREAMWORK.md**, which stores the hash in
  **YAML frontmatter**.
- **No prior hash?** Estimate the install date from mtimes of dreamwork
  assets, use that to locate the oldest plausible hash for the installed
  version, and treat that as the prior version.
- Then dispatch a **cheap subagent** (sonnet 5 low, gpt-5.6-luna low,
  kimi k3 low) to read every commit between prior and current, looking
  for **anything requiring migration** or **new features that might be
  relevant**.
- And: **instruct dreamers to write commit messages** that make it easy
  to tell whether a migration is required, or a new feature needs
  configuration or consent.
- The init procedure needs updating to match.

(He wrote `ud-wd-githash`; reading it as `ud-dw-githash` to match
`ud-dw-generate`, the untracked executable already in this tree — same
prefix, so that one is very likely his too.)

## Why this is worth building

The loop currently knows its version as `.dreamwork/skill-version`: one
line naming the newest file in `migrations/`. That answers "which
migrations have run". It cannot answer "what code am I", and it says
nothing at all about features added between two migrations — which is
most of what changes. A target that has been dreaming for a month has no
way to discover that the skill it is running grew a linter, a compaction
protocol, or a plugin system.

## The split I recommend, and the one thing to confirm

**Keep both mechanisms. They answer different questions and one of them
must stay deterministic.**

- `migrations/` + `.dreamwork/skill-version` remain the **authoritative,
  deterministic** path for shape changes. A migration file exists or it
  does not; nobody has to interpret anything. That is
  impossible-by-construction and it should not be replaced by a model
  reading prose.
- The githash + commit-range pass becomes the **discovery** layer, for
  everything migrations cannot encode: a new feature that wants consent,
  a new config knob, a behavioural change worth knowing about. Its output
  is a *report to the human*, not an automatic action.

So the subagent never migrates. It reads, and it reports. Anything it
finds that needs a decision goes to `questions.md` like every other ask.

## Build order

1. **`bin/ud-dw-githash`** — the smallest piece and everything depends on
   it. Output shape must be fixed and identical in both worlds: the CI
   replacement prints a constant, so the format is the contract. Rec:
   `<sha> [+N dirty]`, sha short-but-unambiguous, N = changed files.
   It must **never fail loudly**: a skill that will not load because it
   cannot tell its own version is worse than one that says "unknown".
2. **DREAMWORK.md frontmatter.** New shape for a file the loop parses, so
   by this repo's own rule it lands with a `file-formats.md` row and a
   `lint.py` check in the same commit. Note DREAMWORK.md has no
   frontmatter today, so every existing target gains it on first upgrade
   — that is itself a migration.
3. **Commit-message convention**, and it is cheap enough to do first.
   Machine-findable trailers beat prose: `Migration: required` /
   `Config: <what needs setting>` / `Consent: <what to ask>`. A trailer
   is greppable without a model, which means the subagent starts from a
   candidate list rather than reading everything — cheaper and more
   reliable. Dreamers get told in SKILL.md's Guardrails, next to the
   existing `dreamwork(maintain:<item>)` rule.
4. **The init step** — read the hash, compare, dispatch on difference.
5. **The upgrade subagent** — cheap model, read-only, reports to the
   coordinator, never uses `attn`, never migrates.

## Open, and worth deciding before step 4

**A zip-installed target has no git history to diff against.** The whole
point of the CI replacement is that the zip carries a hash without
carrying the repo — so the commit range has to come from the remote, and
`git@github.com:ultradyn/dreamwork.git` is private. Either the upgrade
pass needs network plus auth, or the release has to ship its own
changelog (a generated `CHANGELOG` between tags, which the subagent could
read locally and which is useful to humans anyway).

Rec: **ship a generated changelog in the release**. It removes the auth
question entirely, works offline, is cheap in CI, and gives the subagent
better-structured input than raw commits. The git path stays available
for checkouts like this one, where history is right there.

**The mtime fallback is sound but narrow.** For both a zip unpack and a
git clone, asset mtimes really are install time, so the estimate is
reasonable. But "oldest plausible hash at that date" still needs history
or a changelog — the same dependency as above, so both fall out of the
same decision.

## What must not break

- **The loop still starts when the version is unknown.** Unknown is a
  normal state (fresh install, no frontmatter, no network) and must be
  quiet, not an error.
- **The check is cheap.** It runs on every load, including repeat loads
  in one session. That is a subprocess and a string compare; the
  *subagent* only fires when the hashes actually differ.
- **No automatic migration from prose.** See the split above.
