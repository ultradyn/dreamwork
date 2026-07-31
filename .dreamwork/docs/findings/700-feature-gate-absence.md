# Findings — #700: is there a feature-gate mechanism in this repo?

**Lane:** `lane-700gate`. **Verdict: NO. Nothing in this repo implements a
feature gate, under that name or any other.** `SKILL.md:924` (`- Experiments are
feature-gated.`) and `SKILL.md:288` (`experiments are fine but must be
feature-gated`) are the only two statements of the rule; neither has a referent.

This is committed separately from the fix because establishing an **absence** is
the expensive half — `lane-691recap` spent roughly an hour reaching it, and
`#136`'s rule applies: "there is nothing to do" and "the mechanism is missing"
must not render identically. They did. This file makes the determination once so
the next lane reads it instead of re-deriving it.

## What a lane actually searches, and what it gets back on `master`

Both searches below were run at `50d4ac42` (tip of local `master`). Neither
answers the question, and the second is *actively misleading* — which is why the
absence takes an hour rather than five minutes to establish.

**Search A — the mechanism, by name:**

    git grep -nIiE 'feature[ _-]?(gate|flag)' -- '*.py' '*.js' 'justfile' '*.sh'
    client/shader.js:388:  // TIME_ELAPSED query. Feature-gated to WebGL2 + the disjoint-timer ext;

One hit in the whole codebase, and it is a WebGL2 capability probe in a shader —
browser feature detection, not a project gate. A lane that follows it learns
nothing and cannot tell whether it has finished looking.

**Search B — the contract, in `file-formats.md`:**

    grep -niE 'gate' file-formats.md

Returns `gate:` — which is the **questions.md blocking-gate field** (`file-formats.md:894`,
"`gate:` companion names where the ruling lives"), a wholly unrelated mechanism —
plus `file-formats.md:377`, which says of the posture axes that delegation
"carries a number that steers, **never gates**". So the one doc that would hold a
gate's contract contains the word `gate` seven times and none of them is this.

## The candidate that was proposed, and why it fails

`#691`'s design and `#700`'s brief both float `.dreamwork/run-mode` /
`.dreamwork/posture` as the existing idiom to reuse: gitignored files, re-read
every tick (`#426`), whose content changes behaviour without a code change.
Measured, they are **not** feature gates, on three independent counts:

1. **They gate the loop's operating mode, not a feature.** The whole vocabulary
   is `pace`, `asking`, `delegation`, `delivery`, `orchestration`
   (`lint.py:2748`) — how the dreamer works, not which capabilities exist. There
   is no axis whose value is a feature name and no room for one.
2. **They are closed sets that fail loud.** `check_posture` (`lint.py:2910`)
   ERRORs on a value outside `POSTURE_STOPS_*`, and `check_run_mode`
   (`lint.py:2866`) does the same for `RUN_MODES`. A gate has to admit a value
   nobody has enumerated yet — that is what a new experiment *is*. Adding one
   means editing `lint.py`, which is a code change, which is the thing a gate
   exists to avoid.
3. **`file-formats.md:377` says so outright**: delegation "carries a number that
   steers, **never gates**". The one axis that comes closest is documented as
   explicitly not this.

## What the repo *does* have, and it is not nothing

There is one real opt-in mechanism, and it is not the one that was proposed:
**`DREAMWORK.md`'s `## Plugins` section**, parsed by `plugin_resolver.py:32`
(`parse_declared_plugins` — `- Load: \`ud-dreamwork-<name>\``). It is tracked
rather than gitignored, per-target, and an unlisted plugin is not merely
inactive but is kept out of harness discovery entirely. That is a **capability**
opt-in — the right family — but its unit is a whole plugin package with its own
`SKILL.md`, not an experiment inside an existing surface. It is the nearest prior
art and the argument for closure 1 has to answer why it is not simply reused.

Also adjacent, and also not a gate: the `Needs: config` / `Needs: consent` commit
trailers (`SKILL.md:907`) *announce* that a feature is not automatic. They tell a
future upgrade pass to look; they switch nothing.

## Search log — what was swept, so nobody re-sweeps it

All over tracked files at `50d4ac42`:

| sweep | result |
|---|---|
| `feature[ _-]?(gate\|flag)` over all tracked files | 2 statements of the rule, 4 docs *about* its absence, 1 WebGL comment. No implementation |
| `\bgated\b\|\bgating\b` over `*.py` | all prose in comments/tests about unrelated conditionals; no gate registry, lookup or predicate |
| `os.environ` reads in `*.py` | 6 hits, all test/timeout overrides (`DREAMWORK_REAP_NEVER_KILL`, `DREAMWORK_LINT`, `DREAMWORK_LINT_TIMEOUT`, `DREAMWORK_HOOKS_CONFIG`, `DREAMWORK_REMIND_INBOX_DIR`, `CLAUDE_CONFIG_DIR`). None gates a feature |
| `def .*(enabled\|is_enabled\|feature)` over `*.py` | 1 hit: `roll.py:46`, a dice-roll constructor |
| `experiment` over all tracked files | 4 hits, all prose; `SKILL.md:833`/`872` make it a ledger **task type**, not a runtime concept |
| `gitignore.example` | enumerates every machine-local `.dreamwork/` control file. No gate file among them |

The task-type finding is worth stating on its own: **`experiment` already exists
in this repo as a `type:` on a ledger entry** (`SKILL.md:833`) and nowhere as a
thing that runs. That is the whole distance between the rule and reality.
