# Review verdict — glm-1206shelleval round 1 (@cx-reviewer)
# Recovered from launcher stdout 2026-08-04 (#1214: no inbox heading, no review decision).

## Verdict: ANOTHER ROUND

Reviewed `05bc31580e1f58302e740998db8d0ee09aac7fb0`; it matches the checked-out branch tip.

## Spec / execution findings

- **P1 — `CCC_ARGS` is still a shell-injection path** at [justfile:63](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/justfile:63). Passing one literal tail argument, `--coordinator-title=$(id -u)`, through real `just 1.46.0` / `/usr/bin/bash` reached Python as `--coordinator-title=1000`, exit 0. The “trusted coordinator flags” distinction is not a safety boundary; a wrapper can derive a flag value from text and deliver it as an argv element. Replace the whole argv construction with:

  ```just
  @python3 dev/launch_lane.py "$@"
  ```

  I tested that shape in a scratch recipe: the same tail argument reached Python verbatim. It preserves all four required positionals and arbitrary tail flags.

- **P2 — the global setting lacks permanent compatibility coverage** at [justfile:9](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/justfile:9). The new tests only cover `launch-lane`. I found no runtime regression: `just pytest test_launch_lane.py` passed 36 tests; `just audit-styleguide HEAD 3` and `just reap --help` succeeded; `dispatch-lane`, `brief`, and `guards` rendered correctly in dry runs. `status-sync --check` reached its parser but refused because this attached review worktree lacks the ignored `.dreamwork` state—an expected checkout-state artifact. Add a focused unaffected-recipe regression before relying on this global flip.

## Standards

- **Standards — misleading Direction-2 label** at [test_launch_lane.py:823](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/test_launch_lane.py:823). This test makes a broken recipe fail, so it is a behavioral/Direction-1 regression test. It does not itself construct and demonstrate the false-green implementation required by the repository’s Direction-2 contract. Rename it, or add the explicit false-green construction.

## Execution evidence

The non-recursive-expansion claim is true for the four positional HEAD values in this exact environment. I passed a single hostile HEAD argument containing backticks, `$(id -u)`, `$HOME`, both quote styles, a newline, `;`, and a fenced `echo PWNED`; Python received identical UTF-8 bytes.

The committed fixture is less hostile: it has backticks, one `$VAR`, newlines, and a fence, but not `$(...)`, quotes, or `;`. My constructed stronger probe passed.

Against the exact pre-fix justfile from `6a7acec0`, that same probe exited **0** and silently rewrote the argument: both `id -u` forms became the actual uid, `$HOME` expanded, quotes changed, and the fenced command yielded `PWNED`. This confirms the dangerous Direction-2 false green, distinct from the known undefined-variable exit-127 case.

The head-path contract remains unchanged: `dev/launch_lane.py` is outside the diff and still calls `head_path.read_text()` at [dev/launch_lane.py:464](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/dev/launch_lane.py:464). In an isolated Git fixture, passing 400 bytes of content as the positional produced `[Errno 36] File name too long`.

The two known siblings are correctly untouched: [dispatch-lane](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/justfile:43) and [brief](/home/xertrov/.llm-general/skills/.worktrees/glm-1206shelleval-review-r1/justfile:49). I found no third direct `type=Path` parameter with the same quoted interpolation shape. For `#1217`, `brief` is a simple `$1`–`$4` swap; `dispatch-lane` needs a small POSIX `shift`/`"$@"` wrapper to preserve its tail flags safely, so it is not quite a one-line swap.
>> ccc:output-log >> /home/xertrov/.local/state/cc-p/ccc/runs/codex-1785799688833-1356561-0
