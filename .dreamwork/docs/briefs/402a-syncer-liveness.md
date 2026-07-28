# Brief — #402a: the syncer overwrites a correct value with a derived wrong one

Repo: `ud-dreamwork`. Worktree: **`.worktrees/402a`**, branch **`wt/402a`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

Lane-owns: status_sync.py, test_status_sync.py

`status_sync.py` is 144 lines and you own all of them. This brief is long because the
**test** is the hard part here, not the fix: the natural way to test this change is
structurally incapable of failing, and that has already happened twice in this repo today.

## The bug, measured

`status_sync.live_tasks()` decides which lanes are running:

```python
ps = subprocess.run(["pgrep", "-af", "^ccc @"], capture_output=True, text=True).stdout
return sorted({d["task"] for d in dreamers if d.get("brief") and d["brief"] in ps})
```

Today every lane is dispatched as **`ccc --yolo @glm52 …`** — a flag sits between the binary
and the alias, so `^ccc @` matches **nothing**, `live` comes back `[]`, and the tool then
writes that `[]` over a correct hand-written `current_task_ids`. Measured at 12:52: it
recomputed `[331]` → `[]` **while the #331 lane was live**, and printed a clean sync line
doing it.

**This is worse than a field that merely rots.** The more carefully the coordinator writes
truth into `status.json`, the more of it this tool destroys. His dashboard reads
`current_task_ids`; for the whole duration of every flagged dispatch it said no task was
running.

The same liveness question decides a second field, and there the tool does nothing at all:
`dreamers` **only ever accumulates**. `#396` and `#398` were listed as owning
`review_artifact.py`, `file-formats.md`, `dev/capture/fixture/**`, `lint.py` and
`test_lint.py` hours after they landed. That error points the costly way: a stale entry
says a free file is *owned*, so a dispatch that could have happened does not.

## What to build

One liveness test, applied to both fields that depend on it, and a tool that says what it
does not own.

1. **A liveness test that does not encode argument order.** `^ccc @` silently means "no
   flags between the binary and the alias". Match the lane wherever its marker appears, or
   resolve it another way — but see the measurement below before you choose.

2. **`dreamers` is pruned by that same test.** A lane whose process is gone leaves the
   array. Nothing else about the entries changes.

3. **It never writes a derived value it could not derive.** If the liveness probe itself
   fails — `pgrep` missing, `OSError`, empty output when `dreamers` is non-empty and its
   processes *are* alive — leave the field alone and say so on stderr. The current code
   returns `[]` from the `OSError` branch, which is the same destroy-on-failure shape as
   the bug above. **"I could not tell" and "nothing is running" must not be the same
   return value.**

4. **A coverage statement on every run, including the no-change run.** The message
   *"already in sync (136 open, 1 live)"* was printed while three other fields were stale;
   it is scoped to a subset the reader cannot see. Print which fields were derived and
   which were left to their author. Derive the untouched list from the file's actual keys,
   never a literal — a field added next month must show up in it without anyone
   remembering to.

5. **Mixed id types must not crash it.** Existing entries carry `"task": 396` (int);
   writing `"task": "401"` makes `sorted()` raise
   `TypeError: '<' not supported between instances of 'str' and 'int'` and the whole sync
   exits 1. A live lane has also been `#392a`, which the int field cannot hold at all.
   Normalise, or accept both — your call, but **`watch.py` renders `current_task_ids`**, so
   if you change what that list contains, check the renderer and say what you found.

## The measurement to make FIRST, because two sources here contradict each other

`live_tasks`' docstring says lanes are matched by brief path **"rather than by pid, because
`ccc` re-execs its runner and the pid recorded at dispatch is the wrapper's, not the
survivor's."** The `#402` ledger entry recommends the opposite: *"resolve the lane from
`dreamers[].pid` with `kill -0`, which is exact and needs no pattern."* And `status.json`'s
own `#411` lane record carries `"liveness": "kill -0 <pid>"`, which the coordinator used
successfully during that run.

They cannot all be right. **Measure it**: start a process shaped like a real dispatch, note
its pid, and check both — does `kill -0` on the recorded pid still succeed once the runner
is up, and does the brief path still appear in some live process's argv? Report what you
found either way; if the docstring is stale, fix the docstring in the same commit as the
code. Do not pick between them by reading.

## The trap: the obvious test cannot fail

The natural test fakes `subprocess.run` and hands `live_tasks` a fabricated `ps` string.
**That test passes with the broken pattern still in place**, because the fake never runs
`pgrep` — the thing under test is the pattern, and a fake replaces it. This repo has two
green red-runs in one day from exactly this shape, both in tests that read as thorough.

So the criteria below require **one test that spawns a real process** whose `argv` has the
shape of today's dispatch (a flag between the binary and the alias) and asserts the detector
finds it. That one cannot pass with a broken pattern. Fakes are fine *beside* it for the
branches a real process cannot reach.

> The rule this comes from, and apply it to everything you write here: **when a test
> patches, fakes or hand-builds anything, name the production line that would have to change
> for it to fail, then change that line and watch.** If you cannot name one, there isn't one.

## Done means all of these, each measured

Numbers are the coordinator's at `2792bc2`; derive your own and report the disagreement
rather than adjusting to match.

1. **The real-process test.** A process is spawned whose argv places a flag between the
   binary and the alias, and the live-lane detector finds its lane. Reverting the detector
   to `^ccc @` makes it fail. No fake anywhere in this one test.
2. **A dead lane is pruned from `dreamers`; a live one is not.** Assert the **precondition**
   at runtime — that the fixture really does contain at least one of each — or the test is
   vacuous on the day nothing is running. Derive both counts; do not write `2` and `1`.
3. **A failed probe changes nothing.** With the probe raising `OSError`, `current_task_ids`
   and `dreamers` come out **byte-identical** to their input, the exit code is non-zero or
   the message names the skip, and the run does **not** print a clean sync line.
4. **Mixed types and a sub-id both survive.** `dreamers` containing `396`, `"401"` and
   `"392a"` neither crashes nor drops the sub-id. State what `current_task_ids` now holds
   and whether `watch.py`'s renderer copes.
5. **The coverage statement lists the untouched fields, derived from the file's keys.**
   Add a junk key to a fixture `status.json` and assert it appears in the untouched list —
   that is what proves it is derived rather than a literal that happens to be complete
   today.
6. **`--check` keeps its contract**: exits 1 when stale, writes nothing, and now also
   reports staleness in `dreamers`.
7. `python3 -m pytest test_status_sync.py test_watch.py test_lint.py -q -p no:randomly`
   passes. If `test_status_sync.py` does not exist, create it.
8. **`just test`.** Do **not** pipe it — a pipeline returns the last command's status. Write
   to a file, read the file, quote the tail and the real exit code. **The suite should be
   fully green.** If `confirmation` fails, that is `#414` and it is the one failure you may
   report rather than fix; anything else is worth your attention.
9. **Three red-proofs**, from `cp` snapshots, each `grep`- and `ast.parse`-confirmed before
   running: restore `^ccc @` ⇒ criterion 1 fails; remove the prune ⇒ criterion 2 fails;
   make the failed probe return `[]` again ⇒ criterion 3 fails.

**A green red-run is a finding, not a relief.** If you reinstate a bug and the check still
passes, say so — the check is wrong, and that is the more valuable of the two results.

## Files

Yours: `status_sync.py`, `test_status_sync.py` (it does not exist yet — create it). Nothing
else at all: `just pytest` is a bare `python3 -m pytest -q`, so a new `test_*.py` is
discovered without registering it, and the `justfile` needs no edit.

**Not yours, deliberately:** `file-formats.md` and `lint.py`. The `dreamers` row and the
lint check it implies are a separate lane, so leave both alone even though `#402` names
them; the coordinator is holding them for `#402b`. `watch.py` is read-only for you — if the
renderer needs a change, report it, do not make it. `git status --porcelain` proves your
scope at the end.

## Practical

- 2 threads. `just test` takes ~15 minutes; budget for it. Guards bind ports 39890-39899 —
  if something else already holds them, say so rather than working around it.
- Commit with `git commit --only <paths> -m 'fix(#402a): …'`. **`--only`, never `git add -A`**:
  more than one agent commits in this tree, and a bare `git commit` sweeps up whatever
  another agent had staged. A **new** file needs `git add <file>` first.
- Push back with reasons if any of this is wrong. The last two lanes each found a real error
  in my brief, and both were right to report it rather than guess.
- Then append one line to the **absolute** path
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`:
  `- **#402a** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`, and commit it.
  If you land in two commits the grammar currently only accepts one sha (that is `#415`) —
  use the final sha and name the other in the prose.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`.

Say: the real `just test` exit code and how you got it; the three red-proofs with exact test
names; **what the liveness measurement showed** and which of the three contradictory claims
was right; and whether `watch.py`'s renderer copes with whatever `current_task_ids` now
holds.
