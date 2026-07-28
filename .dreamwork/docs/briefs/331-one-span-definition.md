# Brief — #331: one definition of "an ids-only bold span", consumed by every reader

Repo: `ud-dreamwork`. Worktree: **`.worktrees/331`**, branch **`wt/331`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

## What is wrong

The ledger writes a set of task ids as a bold span: `**#5**`, `**#138/#156**`, `**#121 #123**`,
`**#157 + #222 + #223**`. Four regexes across three files each decide what that means, and all four
were written independently:

| | pattern | flags |
|---|---|---|
| `watch.py:7540` `LEDGER_ENTRY` | `^- \*\*(#\d+(?:/#\d+)*)\*\*` | `re.M` |
| `lint.py:44` `LEDGER_ID` | `^- \*\*(#\d+(?:/#\d+)*)\*\*` | `re.M` |
| `status_sync.py:45` `LEDGER_HEAD` | `^- \*\*(#\d+(?:/#\d+)*)\*\*` | `re.M` |
| `watch.py:7568` `LEDGER_COMBINED_MENTION` | `\*\*(#\d+(?:/#\d+)*)\*\*` | — |

All four accept **`/` only**. The ledger also joins ids with a **space** and with **` + `**, so every
id in such a span is invisible to the landed reader. **19 ids are lost right now**:

```
#77 #102 #104 #106 #107 #108 #109 #110 #116 #121 #123 #132 #141 #149 #151 #154 #157 #222 #223
```

in seven space-joined spans (`**#121 #123**` `**#104 #77**` `**#109 #116**` `**#107 #108 #110**`
`**#102 #106**` `**#141 #149**` `**#132 #151 #154**`) and one `+`-joined span
(`**#157 + #222 + #223**`).

**This task is not "add `[ /+]` to the regex."** That has already been done twice — `#301` widened
the landed reader, `#315` widened the open readers and `LEDGER_ID` together — and each time the
defect simply moved to the next door. `status_sync.LEDGER_HEAD` is the third door and it arrived
*while this task sat open*: it is a copy nothing pins, and it matches the other two today only by
luck. The deliverable is **one definition of the span that every reader consumes**, so that a
fourth reader cannot be written wrong.

## The change

1. **One shared constant for the ids-only span core.** Something of the shape
   `IDS_ONLY_SPAN = r"#\d+(?:[ \t]*[/+][ \t]*#\d+|[ \t]+#\d+)*"`, defined **once**, with the two
   surface forms built from it:
   - head form: `^- \*\*(IDS_ONLY_SPAN)\*\*`, `re.M`
   - mention form: `\*\*(IDS_ONLY_SPAN)\*\*`
2. **`lint.py` and `status_sync.py` consume it** rather than restating it. Where they live relative
   to `watch.py` is your call — importing from `watch` is acceptable (`lint.py` already does
   `import watch`); a small shared module is also fine. Pick one and say why in your report.
3. **Extend the pinning test.** `test_watch.py:516`
   `test_ledger_entry_rule_has_exactly_one_copy` currently pins two patterns
   (`watch.LEDGER_ENTRY` vs `lint.LEDGER_ID`) by comparing `.pattern` and `.flags`. It must pin
   **all three heads** — including `status_sync.LEDGER_HEAD`, which is unpinned today — and assert
   that the mention form is built from the same core. Compare patterns, **never** "both find the
   same count on today's file": two different rules agree on most inputs, which is the reason that
   test exists at all.

**Use `[ \t]`, not `\s`.** `\s` matches a newline, and the ledger is line-structured; a span that can
run across a line break is a new bug in place of the old one. If you use `\s`, prove in your report
that it cannot cross a newline.

## The hazard, which is the whole difficulty

A span is **ids only, or it is prose.** Widening the joiner must not let the pattern swallow words.
These all appear in the live ledger and **every one must stay inert** — none of their ids may enter
the landed set through a span match:

```
**#96 stage 1**                      <- #331's named fixture; a section title, not two ids
**#392, #401, #405, #411, #412**     <- comma-joined prose list; #392/#401/#405/#411 are OPEN
**#388, #387 and #386**              <- comma + the word "and"
**#351 collides with this precisely**
**#346's artifact was deliberately NOT marked `language-sql`**
**#392a**                            <- a sub-id, not an id
**#501, #502**                       <- fictional ids quoted from a test fixture
```

Note what this implies: **comma is NOT a joiner.** Only space, `/`, and `+` are. A comma-joined span
is prose and must remain inert at the *pattern* level — do not rely on the column-0 rule to save you,
because that is a second, independent guard and this one has to hold on its own.

## Done means all of these, each measured

Derive every number yourself against the live ledger
(`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md`). The figures below are the
coordinator's measurement at `97becd9` and are given so you can tell agreement from coincidence —
if yours differ, say so rather than adjusting to match.

1. **All 19 ids above are in the landed set.** Test per id with set membership, not by re-deriving
   the spans with a second regex — a previous attempt to re-collect them that way disagreed (it said
   9), and per-id membership is the authoritative test.
2. **`landed` goes 152 → 171; `open` stays 135.** Disjointness holds: `open ∩ landed == ∅`.
3. **Every span in the inert list above lands nothing.** Assert this at runtime in the test, with
   `**#96 stage 1**` as an explicit fixture, and include at least one comma-joined case.
4. **`#5`, `#501`, `#502` do not land** (prose/fictional ids the ledger documents as syntax examples).
5. **Exactly one definition exists.** `grep -rnF '#\d+(?:' watch.py lint.py status_sync.py` finds the
   core in exactly one place (it finds four today). The extended pinning test passes.
6. `python3 -m pytest test_watch.py test_lint.py -q -p no:randomly` passes.
7. **`just test`.** Run it, do **not** pipe it — a pipeline returns the last command's exit status and
   that is exactly how a red reached `master` here. Write to a file, read the file, quote the tail
   and the real exit code.
   **Three failures are known pre-existing on `master`: `qacard`, `docktarget`, `noteprop`.** You are
   not required to fix them. You *are* required to (a) confirm they are the only failures and (b)
   verify they fail on `master` too, and say so. **Do not claim green if it is not green** — report
   the real code.
8. **Two red-proofs, in opposite directions**, each from a `cp` snapshot (not `git checkout`), each
   confirmed to have reached the code with `grep` and `python3 -c "import ast;
   ast.parse(open('watch.py').read())"` before running — a syntax error means zero tests ran, which
   is not a red:
   - **Narrow it back** to `/`-only ⇒ your 19-id test fails.
   - **Widen it too far** — e.g. admit a comma, or use `[^*]*` — ⇒ your inert-span test fails.
   A widening that only passes the first direction is a pattern that is merely greedy.

**A green red-run is a finding, not a relief.** If you reinstate a bug and the check still passes,
the check is wrong — say so; do not conclude the code was fine.

## Two things that will waste your time

- **Do not edit `dev/capture/burndown.mjs`.** Its fixture is evidence, not scaffolding.
- **The historical burndown series is downstream of this.** `watch.ledger_series` walks ~295 old
  revisions of the ledger. `#331` records (reported by `#327`, not re-verified) that none of the 19
  was ever in a landed set at any revision, so ever-landed should move **117 → 136**. Check it if
  it is cheap; if it disagrees, report the disagreement rather than chasing it — it is not a
  blocker for this task.

## Files

Yours: `watch.py`, `lint.py`, `status_sync.py`, `test_watch.py`, `test_lint.py`, `file-formats.md`.
Nothing else; `git status --porcelain` proves it.

**`file-formats.md` must state the joined form.** It currently documents `**#N/#M**` and says history
packs several landings to a line — both true, so there is no lie to correct — but the space and `+`
forms can only be inferred. Name all three joiners explicitly, and name comma as *not* a joiner.
Same commit as the code.

## Practical

- 2 threads. `just test` runs browser guards and takes ~15 minutes; budget for it.
- Commit with `git commit --only <paths> -m 'fix(#331): …'`. **Commit the fix and its tests first**,
  before the red-proofs.
- Push back with reasons if any of this is wrong — the coordinator's brief for the last task on this
  parser recommended a fix that would have reintroduced the bug, and the lane was right to refuse it.
- Then append one line to the **absolute** path
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`:
  `- **#331** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`, and commit it.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md` — your worktree has no copy of
that file, and a relative path creates one nobody reads.

Say: where you put the shared definition and why; the real `just test` exit code and how you got it;
both red-proofs with exact test names; the landed/open numbers you derived; what you did about the
comma case; and anything you are unsure of.
