# Brief — #440: one supported way to fold a ledger entry, because the hand-rolled split has now corrupted the file

Repo: `ud-dreamwork`. Worktree: **`.worktrees/ledgertool`**, branch **`wt/ledgertool`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time. Inbox and
hand-off paths for a worktree lane are absolute, per `SKILL.md` (#405).

## The defect, and it is mine rather than the code's

Read `#440` in `.dreamwork/tasks.md` for the full record. In short: `.dreamwork/tasks.md` has exactly one
`## Open` and one `## Recently landed`, but the string `## Recently landed` **also appears in the prose of an
open entry**. `t.split('## Recently landed', 1)` therefore splits at the mention. Twice on 2026-07-28 the
coordinator did this: once writing a file with **two** landed headings and 130 lines in the wrong half (lint
caught it only obliquely, as a *reciprocity* error about an unrelated pair), once counting 33 open entries
instead of 142.

**Five hand-rolled ledger parsers have now been wrong in this repo**, against a file whose production parser
was importable every time.

## What to build

`dev/ledger.py` — a small, importable module with a CLI, the single supported path for these operations:

1. **`fold <id> --note <text>`** — move the entry from `## Open` to the **top** of `## Recently landed`,
   appending `--note` as a `  · <text>` continuation line on the moved block. Preserve the block byte-exact
   otherwise.
2. **`counts`** — open and landed entry counts, printed with the expression that produced them.
3. Anything else you find the coordinator doing by hand is a candidate, but **do not sprawl** — those two
   plus a clean import surface is a complete increment.

**Non-negotiable internals:**

- **Anchored headings, asserted.** `re.search(r'^## Open$', t, re.M)` / `^## Recently landed$`, and assert
  **exactly one match each** and that Open precedes landed — **before** and **after** the write. The
  post-write assertion matters most: the symptom appeared far from the cause both times.
- **Never write a file that fails those assertions.** Build the new text, assert, then write. A partial
  write is the failure mode that cost the recovery.
- **Reuse the production parser** (`watch.parse_ledger` / `ledger_entries`) for anything it already answers,
  rather than adding a sixth parser. If it cannot answer something, say so in the report rather than
  quietly hand-rolling.
- Fold **must refuse** on: unknown id, id already in landed, id matching more than once.

## Done means all of these

1. `dev/ledger.py fold` and `counts` work on the real ledger (dry-run or a copy — **do not leave the real
   `.dreamwork/tasks.md` modified**; the coordinator is its only writer, and a lane editing it is the exact
   race the single-writer rule exists to stop).
2. **A test that reproduces the prose-mention trap**: a fixture ledger whose open section contains the
   literal text `## Recently landed` inside an entry's prose. Assert the fold puts the entry in the real
   landed section and the result still has exactly one of each heading. **Derive the trap's presence at
   runtime and assert it** — a fixture that lost the prose mention would make this test hollow and it would
   never say so.
3. **Red-first, and name the production line.** Replace your anchored search with the plain
   `split('## Recently landed', 1)` and watch the test fail. **A green red-run is a finding, never a
   relief** — if it stays green, the test is not reaching the split and that is the more valuable result.
4. `file-formats.md` states any shape this tool relies on that is not already stated (the two headings being
   unique and ordered is a contract worth writing down if it is not).
5. `python3 lint.py` clean and `python3 -m pytest -q -p no:randomly` passes (1067 at dispatch). **Do not run
   the full `just test`**; bind nothing in 39880–39899.
6. Do **not** touch :35110, the heartbeat, the monitors, or the loop.
7. Trailer if it changes what an install must do: `Migration:` / `Feature:` / `Needs: …`. A new dev tool is
   probably `Feature:` — decide.

## Files

Yours: `dev/ledger.py` (new), `test_ledger.py` (new), `file-formats.md`, and `.dreamwork/docs/doc-map.md`.

**Not yours:** `.dreamwork/tasks.md` (**never edit it** — read-only for you), `.dreamwork/questions.md`,
`watch.py`, `lint.py`, `justfile`, `dev/deploy_state.py`.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'feat(#440): …'` — **`--only`, never
  `git add -A`**.
- **Commit before you finish.**
- **Push back with reasons if any of this is wrong** — including if you think the right fix is to widen
  `watch.py`'s parser instead of adding a module. Argue it.

## Report

Say: which model you are; the module's surface; how the prose-mention test asserts its own trap is present;
the exact production line whose change reds it; whether `file-formats.md` needed the heading contract; the
trailer; and confirmation you never edited `.dreamwork/tasks.md`, ran the full `just test`, or touched :35110.
