# 881 — what part of a lane brief is mechanical, measured

Sample: the **40 most recent briefs** in `.dreamwork/docs/briefs/` by task id
(tasks 835–889 at this reading). Every one of them carries
`briefs/boilerplate.md` verbatim, so the head/boilerplate split is exact rather
than estimated. Script: `dev/brief_corpus_stats.py` — rerun it rather than
trusting these figures, because the corpus grows under the reader; the shares
below moved by ~0.1 pt between two runs twenty minutes apart.

## The byte split — and why the headline framing is wrong

| Part | Bytes | Share |
|---|---:|---:|
| `briefs/boilerplate.md`, appended verbatim | 973,876 | **73.7 %** |
| Task-specific head | 347,272 | 26.3 % |

Mean head: 8,682 bytes. Inside the head:

| Part of the head | Bytes | Share of head | Share of a whole brief |
|---|---:|---:|---:|
| Frame — required fields + the recurring closing sections | 96,451 | 27.8 % | **7.3 %** |
| Authored | 250,821 | 72.2 % | 19.0 % |

**So the mechanical-but-hand-typed part is 7.3 % of a brief's bytes, not "the
large majority".** The majority *is* mechanical, but it is already automated:
the boilerplate is one file concatenation that `dispatch_lane.py` validates
byte-for-byte. A generator saves essentially no typing there.

## Where the value actually is: the block never repeats, the rules do

| Section | Occurrences | **Distinct bodies** |
|---|---:|---:|
| `## Standing rules` | 33 | **32** |
| `## Live-state prohibitions — absolute` | 31 | **30** |
| `## What to report back` | 33 | **32** |

Retyped 33 times, never twice the same. The individual *rules* are stable — it
is the *block* that drifts:

| Rule | Present in |
|---|---:|
| `You never merge and you never push.` | 33/33 |
| `Do not use attn` — report to the coordinator | 31/33 |
| `Limit builds and tests to 2 threads.` | 29/33 |
| `git commit --only <paths>`, never `-a` | 27/33 |
| Compare the lint **WARN ROW SET**, not the count (`#794`) | 14/33 |
| REBASE onto master before reporting | 9/33 |
| Run `dev/repo_wide_guards.py list` too | 8/33 |
| harness scratchpad is NOT lane-private (`#652`) | 25/31 |
| do not write ledger/status/questions/handoffs/chats | 21/31 |
| do not bind `:35110` / `:35113` | 14/31 |
| never `pkill -f` a shared pattern — kill by pid | 7/31 |

**The generator's value is completeness and consistency, not typing volume.** A
lane dispatched last night had a 6-in-33 chance of being told to rebase before
reporting. Measured completeness gaps in the corpus:

- `ledger.py get <id> --ledger <abs>` — the form SKILL.md (#667) says a brief
  must paste, or the lane gets four false `not found`s: **18/40**.
- `Lane-owns:` — mandatory per SKILL.md (#465), a lint **ERROR** when absent:
  **2/40**. See below.

## The four fields that are always right, and why

| Field | Present |
|---|---:|
| `# Task #<id> …` heading | 40/40 |
| `Worktree:` | 40/40 |
| `Branch:` | 40/40 |
| `Base sha:` | 40/40 |
| `Repo root:` | 40/40 |
| `Coordinator inbox — ABSOLUTE path…` | 40/40 |
| `inbox.md`, NOT `handoffs.md` parenthetical | 40/40 |

These are 40/40 because `dev/dispatch_lane.py` **refuses** without them. That is
the pattern worth copying: the fields a machine checks are the fields that are
never wrong. Every field it does not check drifts.

Their *values* vary and must be derived, never templated: `Base sha:` is written
8-hex in 16 briefs and 40-hex in 24; `Worktree:` moved from
`ud-dreamwork/.worktrees/` (14 briefs) to `skills/.worktrees/` (26) when #846
landed.

## `Lane-owns:` — mandatory, absent, and unenforced

SKILL.md: a worktree brief carries a machine-parseable `Lane-owns:` line, and
`lint.check_brief_lane_owns` **ERRORs** without one. Measured: **2 of the last
40 briefs carry it**, and `lint.py` reports **0 ERRORs**.

The enforcement is a no-op for a reason that is worth writing down.
`check_brief_lane_owns` grandfathers a brief whose `_brief_commit_time` is
`None` — and a brief is uncommitted for its whole life, by design
(`dispatch_lane.py`: *"The corpus copy and its hash receipt are intentionally
uncommitted"*). **37 of the last 40 briefs are untracked**, so the check cannot
date them and passes over them. It is not broken; it is aimed at a population
that is empty at the moment it matters.

Consequence for the storage question: if briefs become permanently untracked,
this ERROR becomes permanently unreachable rather than merely late.

## The authored side does not repeat, at all

- Distinct authored blocks: **40/40**.
- Briefs carrying a direction-2 construction: **40/40**; distinct openings
  **39/40**.

40/40 is why `dev/brief.py` requires a direction-2 section rather than
suggesting one — the invariant is measured, not assumed.

## One finding that changed the design

The only two placeholder-token hits in 40 heads (`TODO`, `<describe …>`) are
both in **#881's own brief**, which discusses placeholders in prose. A
token-level `contains("TODO")` refusal would reject the brief that commissioned
it. Placeholder detection is therefore **line-shaped**: a line is a placeholder
only when its entire content, after stripping bullets and markdown decoration,
is fill-in material. A sentence that mentions `TODO` is a sentence.
