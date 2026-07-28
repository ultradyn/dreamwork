# Harness write-containment — #450 (after #465)

> **Status:** boundary statement. No mechanism is proposed that needs kill,
> sandbox, or process-restriction authority (`#288` / `#290` grant none of
> those). The deliverable is an accurate ceiling: **where a lane's file
> writes can be intercepted before they land, and what remains when they
> cannot.** Related but different surfaces:
>
> - [containment-deficiency.md](../containment-deficiency.md) — process /
>   tool-call isolation vs trusted nodes (`#288` ruling).
> - [lane-containment.md](lane-containment.md) — `#465` pre-commit guard
>   design (fails at first *commit*).
> - `#468` — lint dirty-tree backstop (fails after the write, needs no hook).

## The gap, measured

**Some harnesses cannot intercept a subagent's file writes at all.**

Incident behind `#465`: a lane dispatched via `ccc` into `.worktrees/superseded`
on `wt/superseded` edited paths **in the main checkout on `master`**. Its
worktree stayed clean. The invocation used the worktree as cwd. A brief that
named the worktree twice did not constrain it. `git -C` does not constrain a
`Write` tool that takes an absolute path. So:

| lever people assume | what it actually constrains |
|---|---|
| brief / prompt ("work only in …") | nothing mechanical — cooperation |
| cwd at dispatch | relative paths only; absolute paths ignore it |
| `git -C <worktree>` | git operations only, not editor/tool writes |
| worktree registration | where *git* thinks the tree is, not where tools write |

Containment of **writes** is therefore **partial by construction** for every
harness the loop dispatches today. The `#465` / `#468` guards catch the defect
**after** the write (commit, or dirty main tree) — they are not write-time
interception, and they must not be read as such.

## Per-harness: can dreamwork intercept a write before it lands?

Only harnesses the loop actually dispatches (or can enable) are listed.
**Verified** means measured against this repo's incidents or against code that
ships here. **Unknown** means not measured; inventing a ✔ is worse than the gap.

| harness | write interceptable *before* land? | evidence | fallback when not |
|---|---|---|---|
| `ccc @grok` (loop's primary runner) | **no** | `#465` incident: `Write` + absolute path reached the main checkout; cwd and brief did not stop it | `#465` pre-commit guard (first *commit* in main checkout); `#468` lint dirty-tree backstop; `Lane-owns:` declaration |
| `ccc @glm52` (loop's other primary runner) | **no** | same dispatch path as `@grok` (`ccc` + a coding CLI that owns its own tool execution); no dreamwork wrapper sits between tool and filesystem | same |
| Claude Code native tools / Agent tool | **partial, post-write only, and not on the dispatch path** | `ud-dreamwork-hooks` ships `PostToolUse` ledger lint after Write/Edit — **after** the write; there is no PreToolUse path-block in this repo; native subagents are **not** currently dispatched (`DREAMWORK.md` CURRENT: `ccc @grok` / `ccc @glm52` only) | if re-enabled: same post-write guards; hooks do not protect `ccc` lanes |
| other `ccc` runners (codex, opencode, cursor, …) | **unknown** | not the loop's CURRENT dispatch set; not measured here | treat as **no** until measured; do not invent a capability matrix |

**Why "no" for `ccc` is a fact.** Dreamwork does not own the tool-execution
half of a `ccc` runner. The runner (or the CLI it wraps) makes the LLM call
*and* applies file tools in one process. There is no loop-owned seam that sees
a `Write` path before the bytes hit disk. A future PreToolUse-style hook inside
a *specific* runner would be **that harness's seam**, not dreamwork's — same
reframe as `#288`: *whoever supplies the API key can supply the harness.*

## What already covers the gap (no new authority)

These need no kill, sandbox, or process wall. They are the honest fallback
when interception is impossible:

1. **`Lane-owns:` in the brief** — machine-parseable ownership the guard can
   read. Enforced loud at brief-write time by `lint.check_brief_lane_owns`.
2. **`dev/lane_guard.py` (#465)** — refuses a **main-checkout commit** whose
   staged paths intersect a live lane's owned set. Ceiling: first *commit*, not
   first write. Machine-local (`core.hooksPath`); `Needs: config` to enable.
3. **`lint.check_lane_containment_backstop` (#468)** — ERRORs when a
   lane-owned path is **dirty in the main tree** while that lane is out. Needs
   no hook; protects every checkout that runs lint. Ceiling: after the write.

Together they are detect-and-refuse at the commit / pre-merge boundary — the
places the realised and unrealised harms were shaped. They do **not** make a
stray write impossible.

## What is deliberately not proposed

- **No process kill, sandbox, or namespace wall** for write paths. That authority
  is the human's (`#288`); run-mode / posture grant none of it (`#290` / `#445`).
- **No first-write guard that needs the lane's cooperation.** A marker the lane
  must read and honour is the rule that already failed (`#465` R3 ✘ G3).
- **No invented "runner X can intercept" row** without a measured seam.

## Conclusion

**No further mechanism is worth building for this gap under present authority.**
The right deliverable is this note plus a short warning where operators and
coordinators already read about `Lane-owns:` (`SKILL.md`), so `#465`'s guard is
never mistaken for write-time interception.

If a future harness exposes a real PreToolUse (or equivalent) path filter that
dreamwork can enable without new kill/sandbox rights, measure it, add one row
to the table above, and only then wire a check — red-proved on the production
line that would refuse the write. Until then: state the ceiling, keep the
post-write guards honest, keep dispatch single-seamed so a later wall can
attach once.

## Trailer decision

No `Migration:` / `Feature:` / `Needs: config|consent` — docs and a SKILL.md
warning only; no install step and no behaviour change on existing targets.
