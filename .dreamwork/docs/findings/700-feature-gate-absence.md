# Findings — #700: is there a feature-gate mechanism in this repo?

**Lane:** `lane-700gate`. **Verdict: NO. Nothing in this repo implements a
feature gate, under that name or any other.** Everything in this half of the file
describes `master` at `50d4ac42`, *before* the fix below: there, `SKILL.md:924`
(`- Experiments are feature-gated.`) and `SKILL.md:288` (`experiments are fine
but must be feature-gated`) are the only two statements of the rule, and neither
has a referent.

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

---

# The decision — IGC

**Context.** `SKILL.md` is a *shipped* skill: the rule is read by coordinators and
lanes on arbitrary target repos, not only this one. There is no gate today
(above). There is one live consumer, `#691`, whose design is merged and whose
implementation the human has gated on his own review — and his stated purpose is
verbatim: *"This should be feature gated so we can turn it off later of we change
our mind on it."* So the rule's job is **an off switch the human can throw
himself, without a code change and without waiting for the loop.** `#612` binds
volume. The repo has a documented six-member `.dreamwork/<knob>` file family —
`watch-port`, `watch-tint`, `run-mode`, `posture`, `subagent-policy`,
`skill-version` (`file-formats.md:374-381`) — every member *absent → a stated
default*, each with its own `lint.py` check, and **no registry**.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **I1** central `.dreamwork/features` registry | ✘ | ✔ | ✔ | ✘ | ✔ | ✘ |
| **I2** every experiment becomes a plugin (`DREAMWORK.md ## Plugins`) | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| **I3** downgrade the line to an aspiration | ✘ | ✔ | ✘ | ✔ | ✔ | ✔ |
| **I4** state the property, name the existing file family | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **I5** env-var convention (`DW_<FEATURE>=1`) | ✘ | ✔ | ✘ | ✔ | ✔ | ✔ |

- **G1** a lane that reads the line stops searching — the answer is *at* the line
- **G2** the human can turn the feature off himself, no code change, no loop
- **G3** adds no subsystem: no registry, no new parser, no new format (`#612`)
- **G4** works on an arbitrary target repo, not only this one
- **G5** nothing invented that has no consumer — true even if `#691` never lands

**The decisive errors.**

- **I1 fails G3**, and it is the expensive wrong turn this task exists to
  prevent. A registry is a new file format, a new parser, a new lint check and a
  naming namespace, for zero features today. Worse, it is the one thing the repo
  has consistently *declined* to build: six knob files, no index. Building the
  central thing a convention has six times refused is the subsystem `#612`
  forbids. (It also fails **G5**.)
- **I2 fails G3.** `plugin_resolver.py:18` requires
  `^ud-dreamwork-[a-z0-9]+(?:-[a-z0-9]+)*$`, so every experiment becomes a whole
  plugin package with its own `SKILL.md`, manifest and `migrations/`. `#691`'s
  design reached this independently and called it *"machinery for one script"*.
  The mechanism is real; forcing a one-file experiment through a package
  boundary is still a subsystem, just a pre-existing one applied where it does
  not fit.
- **I3 fails G2** — and this is the closure the brief offered that has to be
  refused. An aspiration gives the human no off switch, and the next experiment
  is *already designed and waiting*: `#691` would still have to invent one. So
  the honest-sounding option makes the real defect permanent — every experiment
  invents its own gate, and the human learns a different off switch per feature.
  It fixes the lane's wasted hour by paying it once per feature instead.
- **I5 fails G2.** An env var does not travel and cannot be seen: the human
  cannot tell what is on, and turning it off means finding whichever shell or
  unit file set it. `#691`'s design found the same thing — `DW_UPDATE_EVIDENCE`
  is this repo's only test-enforced default-off env gate and it *"cannot be
  seen"*.

**One survivor: I4.** And note what it is not. The brief posed two closures —
*implement a gate* or *downgrade to an aspiration* — and the survivor is
neither. It is **naming the gate that already exists**, which costs closure 2's
volume and buys closure 1's followability.

## The brief's hypothesis: right family, wrong reason — and the reason matters

The brief proposed `run-mode`/`posture` as the idiom, on the grounds that they
are re-read every tick (`#426`). **Half right, and the half that is wrong would
have produced a bad gate.** The load-bearing property is not the per-tick
re-read — it is **absent → a stated default**, which the whole family shares.
`run-mode` and `posture` are the *worst* two members to copy:

- both are **gitignored** (`gitignore.example`), so the decision does not travel
  and turning the experiment off on one machine leaves it on everywhere else;
- both enforce **closed value sets that ERROR on an unrecognised value**
  (`check_posture`, `lint.py:2910`; `check_run_mode`, `lint.py:2866`), so
  admitting a new experiment means editing `lint.py` — a code change, which is
  the thing a gate exists to avoid.

`watch-tint` and `watch-port` are the members to copy: **tracked**, so the
project records whether it wants the experiment, and absent means the default.
That is why the landed rule says *tracked* and names `watch-tint` first.

## What `#691` should now do

Its §8.2 recommendation — a **tracked** `.dreamwork/recap` file, default off,
closed key set, `lint.py` check — **is already what this rule requires.** It
needs no change; it now cites a rule instead of inventing one. Two adjustments,
both one line, for the coordinator to carry (this lane does not touch the design,
which is under the human's review):

1. §8.1's *"nothing in the codebase implements a thing called a feature gate"* is
   correct as written and should now point at `SKILL.md`'s Guardrails and this
   finding, so the next reader does not re-derive it.
2. `questions.md`'s **Q1 — "where does the feature gate live?"** is **answered**
   and can be retired without troubling the human. Its own `rec:` was *"a tracked
   `.dreamwork/recap` file"*, which is what the rule now mandates. The other two
   questions (cadence; whether it animates) are untouched and remain his.

## The case this still leaves ambiguous — reported, not closed

**An experiment whose surface is a file the dashboard reads, not a code path.**
The rule assumes the experiment has a runtime that can consult a file and decline
to act. An experiment that only changes what `watch.py` *renders* from data that
is written anyway — say a new column derived from `status.json` — has no process
to gate; the gate has to sit in the renderer, and "absent means off" then means a
branch in `collect()` rather than a process that never starts. The rule does not
say that, and a lane in that position will have to decide it. It is one
sentence's worth of extension if a second case appears; extending it now on one
hypothetical is exactly the speculative growth `#612` refuses.

Second, narrower: `file-formats.md` still answers a `grep gate` with
`questions.md`'s unrelated blocking field. The rule points *from* `SKILL.md` *to*
`file-formats.md`, which is the direction a lane actually travels; the reverse is
untouched.
