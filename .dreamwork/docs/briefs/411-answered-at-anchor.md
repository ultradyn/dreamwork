# Brief — #411: `answered_at` loses a date two entries own

Repo: `ud-dreamwork`. Worktree: **`.worktrees/411`**, branch **`wt/411`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

Lane-owns: watch.py, lint.py, test_watch.py, test_lint.py

This is a small task. It is briefed carefully because the obvious edit is a **no-op**, and because
the thing it must *not* do is the part that will bite.

## The bug

`watch.answered_at(body)` returns when a folded question was resolved, for the collapsed-row view.
It reads:

```python
RESOLVED_AT = re.compile(r"\A\s*→[^:]*?\((\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)")
...
m = RESOLVED_AT.match(body or "")
```

The marker is only found when it is the **first thing in the body**. Two answered entries put an
artifact link on the first line and the `→ answered (…)` marker on the **second**, so both lose a
date they plainly carry:

- `P1 · 2026-07-26 — #233 LAN binding…` → should be **2026-07-26 17:49**
- `P1 · 2026-07-26 — #229 threaded topic chats…` → should be **2026-07-26 17:11**

## The trap: `.match` → `.search` changes NOTHING

The pattern starts with **`\A`**, which anchors to the start of the string regardless of which
method calls it. I verified this on the live file: `RESOLVED_AT.search(body)` finds nothing for
either entry. **An edit that only swaps the method is a no-op that looks like a fix and passes any
test asserting "the date is still right for the 44 that work".**

The edit is the **anchor**: `\A` → `^` with **`re.M`**, then `.search`. Keep the rest of the pattern
exactly as it is.

## The harder half: five entries MUST keep returning `None`

`answered_at`'s docstring is the contract — *"a wrong date is worse than no date — so this never
guesses"*. After your change, **3 of 49** answered entries must still return `None`:

> **Corrected after the fact.** This section originally said *"5 of 49 must still return None"*,
> which flatly contradicts criterion 3 below (`None` count goes 5 → 3) in the same brief. It also
> said three entries predate the marker convention when only **one** does, and criterion 2 said 43
> dated entries when there are **44**. The lane caught all three, followed the measurable criteria,
> and reported the prose rather than guessing which half was authoritative — the right call, and
> every correction verified. Left visible rather than silently patched: a brief that states the
> same fact in prose and in criteria will drift, and the drift is invisible to its author.

- `#194` and the **dreamhub URL space** ask were ***withdrawn*** — decided by the loop, never
  answered, so there is no answer time to report. A date here would be a fabrication.
- **One** more (`Four early asks, all applied`) predates the marker convention.

**A change that gives any of these a date is a regression, not an improvement**, even though it
would make the dashboard look more complete. If you find yourself widening the pattern to catch a
date that appears anywhere in the body, stop — that is the failure mode this docstring exists to
prevent.

## Done means all of these, each measured

Numbers are the coordinator's at `563eb84`; derive your own and report the disagreement rather than
adjusting to match.

1. **The two recover**, with exactly those timestamps.
2. **All 44 entries that already have a date are byte-identical before and after.** Derive both
   sets at runtime and compare them as a whole — this is the check that makes the change safe, and
   it is the one that is easy not to think of.
3. **`None` count goes 5 → 3.** The remaining 3 are the withdrawn/pre-convention entries above and
   must stay `None`; assert at least the two withdrawn ones by name.
4. A test in `test_watch.py` for the second-line marker, and a test that a body with a date but
   **no `→` marker** still returns `None`.
5. **A derived lint count** (this is what the ledger entry asks for): `lint.py` reports how many
   answered entries have no resolution date, so a future fold that drops a marker is visible. Make
   the number derived, never a literal.
6. `python3 -m pytest test_watch.py test_lint.py -q -p no:randomly` passes.
7. **`just test`.** Do **not** pipe it — a pipeline returns the last command's status. Write to a
   file, read the file, quote the tail and the real exit code. **The suite should be fully green;
   if anything fails, it is worth your attention** (unlike earlier briefs today, which carried three
   known reds — those are fixed, in `7007d5b` and `e15b0c0`).
8. **Two red-proofs, opposite directions**, from `cp` snapshots, each grep- and `ast.parse`-confirmed
   before running:
   - Restore `\A` ⇒ your two-entry test fails.
   - Widen to find a date **anywhere** in the body (e.g. drop the `→` requirement) ⇒ your
     withdrawn-entries-stay-`None` test fails.

**A green red-run is a finding, not a relief.** If you reinstate a bug and the check still passes,
the check is wrong — say so.

## Files

Yours: `watch.py`, `lint.py`, `test_watch.py`, `test_lint.py`. Nothing else; `git status --porcelain`
proves it. Do not edit `.dreamwork/questions.md` — the data is correct; the reader is not.

## Practical

- 2 threads. `just test` takes ~15 minutes; budget for it.
- Commit with `git commit --only <paths> -m 'fix(#411): …'`. Commit the fix and its tests **first**.
- Push back with reasons if any of this is wrong.
- Then append one line to the **absolute** path
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`:
  `- **#411** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`, and commit it.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`.

Say: the real `just test` exit code and how you got it; both red-proofs with exact test names; the
before/after `None` count; and confirmation that the 44 existing dates are unchanged.
