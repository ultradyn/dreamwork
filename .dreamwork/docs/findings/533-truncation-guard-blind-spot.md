# #575 — why the #533 truncation guard missed e061ce7c

## The regression

`e061ce7c` ("Fold #497 answer; server groom of the Answered archive",
2026-07-30 16:33) lost **152 lines** of `questions.md` (parent 3071 →
commit 2919). The #533 truncation guard (`check_questions_truncation`)
had landed at 10:03 the same day — six hours earlier — and was active.

The guard did not fire. **This doc explains why, and it is structural.**

## Root cause: the guard is post-commit-blind

`check_questions_truncation` compares **HEAD vs working tree**:

```python
head = _head_questions(dw)          # HEAD's questions.md
level, detail = questions_truncation_guard(
    head, path.read_text(), ...)    # working tree vs HEAD
```

This catches truncation **only in the pre-commit window** — when HEAD
holds the full version and the working tree holds the truncated version.
The net line-loss is positive, the guard ERRORs, and the coordinator is
told before committing.

**After the commit, the guard is structurally blind:**

| state             | HEAD          | working tree  | net loss | guard  |
|-------------------|---------------|---------------|----------|--------|
| pre-commit window | full (3071)   | truncated (2919) | 152   | ERROR  |
| post-commit       | truncated (2919) | truncated (2919) | **0** | silent |

Once the truncation commits, HEAD == working tree. The net loss reads
as 0. The guard cannot see what happened — it has no memory of the
pre-commit state.

## Why the pre-commit window was missed for e061ce7c

The guard lives in `lint.py`. Nothing enforces a lint run between a
file write and a `git commit`:

1. **No pre-commit hook.** The repo has no `core.hooksPath` pointing at
   a pre-commit that runs lint. (#465 is the open question about adding
   repo-local hooks; it has not landed.)

2. **The PostToolUse hook (#156) fires on Write/Edit tool calls only** —
   not on `git commit` via Bash, and not on file writes by non-Claude
   agents (ccc/grok lanes) or by the watch server itself. The e061ce7c
   commit was a coordinator commit; whether it went through a Write tool
   call or a Bash-driven write is unknowable from git history, but the
   point is the guard is not in the commit path regardless.

3. **The `groom:` escape hatch did not fire.** No prior commit touching
   `questions.md` carried `groom:` (verified by `git log --format=%s`),
   and e061ce7c's own message says "groom of" not `groom:`. So the
   escape hatch is not the cause.

The conclusion is simple: **the guard was never run in the pre-commit
window for this commit.** Whether lint was skipped entirely or run in a
`lint && commit` pipeline where the ERROR scrolled past (the #361
pattern), the result is the same — the commit proceeded, and the guard
became structurally unable to detect the loss.

## The fix: add a HEAD-vs-HEAD~1 retroactive check

The guard currently compares HEAD vs working tree only. Adding a
**second comparison — HEAD vs HEAD~1** — catches a just-committed
truncation on the next `lint.py` / `just test` run, even if lint was
never run pre-commit:

```python
# existing: working tree vs HEAD (catches pre-commit)
level, detail = questions_truncation_guard(head, path.read_text(), ...)

# NEW: HEAD vs HEAD~1 (catches post-commit, retroactively)
parent = _head_questions(dw, ref="HEAD~1")
if parent is not None:
    level2, detail2 = questions_truncation_guard(head, parent, ...)
    # head is the committed (possibly truncated) version;
    # parent is the pre-commit version
    # if head lost lines vs parent, that's the regression
```

This is a one-function addition to `check_questions_truncation`. It
does not replace the pre-commit check (which is still valuable when it
fires); it adds the retroactive coverage that closes the blind spot.

**Red-first proof:** revert questions.md to its pre-e061ce7c state
(a69e2f41's version), then `git commit` the truncated version without
running lint. Run `lint.py` — the existing guard is silent (HEAD ==
tree). Add the HEAD-vs-HEAD~1 check, run again — it ERRORs on the
152-line loss. This is the discriminating FAIL the current guard cannot
produce.

## What this does NOT fix

A truncation committed AND followed by another commit that changes the
file again would move the loss to HEAD~2, HEAD~3, etc. The retroactive
check catches the immediately-prior commit; deeper history would need a
scan. But the common case (the coordinator commits a truncation and
the next lint/test run catches it) is covered by HEAD-vs-HEAD~1.

The pre-commit-hook question (#465) is the other half of the defence —
enforcing the guard at commit time rather than catching it after. This
fix makes the guard useful without that hook; the hook would make it
preventive.
