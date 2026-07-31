# Lane-607 report — INTERPRETER vs SUBJECT wording in briefs/boilerplate.md

## Verdict

**DONE.** Added one standing rule (7 lines) to `briefs/boilerplate.md` that states the
INTERPRETER/SUBJECT distinction. The rule names the default (invoke the worktree's copy),
the trap (the skill-dir path is a symlink into main), and the one legitimate exception
(the pre-fix baseline), citing `#592` and `#607`.

## The decision: I chose the DISTINCTION (the rule), not the by-construction removal

**Should the boilerplate stop citing absolute skill-dir paths and say `python3 dev/<tool>.py`
throughout?** I agree with `#440`'s lean — and I measured that **the boilerplate already does
this.** Before my change:

    grep -n "python3 /" briefs/boilerplate.md   →  (empty — zero absolute interpreter paths)

Every tool invocation in the boilerplate is already worktree-relative (`python3 dev/ledger.py
get`, `python3 dev/redproof.py begin`, etc.). The only absolute path is `--ledger
/home/…/.dreamwork/tasks.md`, which is the **SUBJECT** (data file), not the interpreter —
exactly as it should be, because the store does not travel into a worktree (`#667`).

**The trap does not live in the boilerplate.** It lives in the brief **heads** the
coordinator writes (like my own BRIEF.md head: `python3 /home/…/skills/ud-dreamwork/lint.py
--target <worktree>`). The boilerplate cannot edit the heads it is concatenated after — so the
by-construction option has nothing to remove from this file. What the boilerplate *can* do is
give the lane a rule that makes it immune to a head that still cites the old form. That rule
is the distinction, and it is the marginal fix that remains.

**The argument against by-construction is weak for tracked tools** (a worktree branches from
master and has all of master's files), **but the exception is real**: the skill-dir path is
the correct pre-fix BASELINE (`#592`), and a blanket ban would forbid the right technique
along with the wrong one. The rule names both.

## What I changed

One paragraph inserted at `briefs/boilerplate.md:122-129`, immediately after the `--ledger`
SUBJECT block (the natural companion — that block covers the data path, this one covers the
interpreter path):

> **The path you invoke is the INTERPRETER; `--target`/`--ledger` is only the SUBJECT.** A
> brief head may cite a tool by its skill-dir path (`python3 /home/…/skills/ud-dreamwork/
> <tool>.py`) — that is a symlink into the MAIN checkout, so it runs the code you have NOT
> fixed. If your task edits a tool the brief tells you to run, invoke the WORKTREE'S copy
> (`python3 dev/<tool>.py`), which runs your fix. The one legitimate use of the skill-dir
> path is the pre-fix BASELINE — running the unfixed tool deliberately to capture the before
> state (`#592`, `#607`). That is a technique, not a mistake; a rule that bans the skill-dir
> path would forbid it.

It states the **distinction** (not a list of tool paths — a list rots the moment a new tool
appears, which is the brief's explicit instruction).

## Red-proof — Direction 1 (the inversion, demonstrated concretely)

**Reproducible, not narrated.** I snapshotted `dev/lessons_index.py` (the FIXED file, per
`#608`), sabotaged it with a `print("LESSONS_INDEX_607_DEMO_MARKER")` injection, and ran the
tool both ways:

```
========== WORKTREE path (python3 dev/lessons_index.py) ==========
LESSONS_INDEX_607_DEMO_MARKER                    ← edit is LIVE
# act: red-proof — 42 of 327 lessons ...

========== SKILL-DIR path (the symlink — what briefs cite today) ==========
# act: red-proof — 42 of 327 lessons ...          ← NO marker
lessons.md:157
```

**The two disagree.** The worktree path runs the fix; the skill-dir path runs main's unfixed
copy. A lane that edits a tool and verifies via the skill-dir path sees the error persist and
concludes its fix failed — the inversion the brief describes, reproduced with one print
statement and two invocations. Restored from snapshot, verified marker-free, byte-identical
to the pre-sabotage file.

`dev/redproof.py check` output:
```
check: clean — 1 injection(s) registered, all restored and absent from the working tree
and from this branch's commits:
  dev/lessons_index.py (sha 6633a98a4e31, hint: 'print("LESSONS_INDEX_607_DEMO_MARKER") …')
```

## Red-proof — Direction 2 (the sys.path question the brief expected to bite)

**Candidate:** does `python3 dev/ledger.py` in a worktree import the worktree's
`ledger_write.py` / `watch.py` / `lint.py`, or the main checkout's? A lane could follow the
new rule perfectly — invoke the worktree's entry script — and still be fooled if the sibling
modules load from main.

**Result: does NOT bite, and the reason is constructional.** `dev/ledger.py:74` does:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`Path(__file__).resolve()` **chases the symlink**, so `sys.path[0]` follows the invocation
path. Measured with a probe that imports `watch`, `ledger_parse`, and `lint`:

```
=== WORKTREE path ===
sys.path[0] inserted: …/lane-607interp
watch imported from:        …/lane-607interp/watch.py
ledger_parse imported from: …/lane-607interp/ledger_parse.py
lint imported from:         …/lane-607interp/lint.py

=== SKILL-DIR path (symlink) ===
sys.path[0] inserted: …/ud-dreamwork   (main, resolved through symlink)
watch imported from:        …/ud-dreamwork/watch.py
ledger_parse imported from: …/ud-dreamwork/ledger_parse.py
lint imported from:         …/ud-dreamwork/lint.py
```

**The entire import graph follows the invocation path, not just the entry script.** The
second-module false-green cannot occur for any tool using this idiom (`dev/ledger.py:74`,
`dev/journal_consume.py:163`, `dev/redproof.py:118`). The only Direction 2 residual is the
data-file case (`#667`/`#611`: the store does not travel into a worktree), which is already
known and already handled by the `--ledger` SUBJECT rule above this one.

## Cited issues — relied-on lines

- **#607** (this task): *"That leading path is a SYMLINK into the main checkout, so it is the
  INTERPRETER, while `--target` is only the SUBJECT. For every lane so far that distinction
  was invisible and harmless. For a lane that edits `lint.py` itself it inverts the result."*
- **#592** (lane-592lint, the correct baseline use): *"This lane spotted it and used the
  skill-dir copy deliberately as the pre-fix BASELINE, running the worktree's own `lint.py`
  for the after — but it should not have had to notice."* — the relied-on line the rule must
  not forbid.
- **#440** (one-supported-way): *"so: a single supported way to fold an entry … `lint` cannot
  police a throwaway script, so the check that matters is that the tool exists and is the only
  path"* — the argument for by-construction; measured as already realized in the boilerplate.
- **#611/#667** (what doesn't travel into a worktree): *"`ledger.sqlite3` is gitignored so it
  does not travel to a worktree"* (#667); *"the gitignored store cannot travel"* (#611). The
  data-file half of this problem is solved; the interpreter half is what I fixed.
- **#400** (a lane reads what is in front of it): *"the lessons that reach a lane are the ones
  I hand-copy into its brief"* — the boilerplate IS in front of every lane, which is why it is
  the right file for this rule.
- **#612** (volume): *"land your change as the fewest lines that carry the meaning"* — the rule
  is 7 lines; I resisted expanding it into a list of tool paths.

## I considered mass-editing historical briefs — and did not

`#398`/`#405` established grandfathering (the brief checks grandfather 27+65+42+20 old briefs);
`#587` upheld it tonight: *"Grandfathering upheld with an argument rather than on my say-so:
the 4 fake-path briefs stay, harmless under the fixed regex, against 91+47+~40 real
citations."* The brief heads that cite the skill-dir interpreter path are history — they were
written before this rule, they are harmless under it (a lane reading the boilerplate now
translates any skill-dir path it sees into the worktree-relative form), and editing them would
touch ~190 files for zero structural gain. The rule is forward-only, which is the same posture
`#400` took for the `lessons.md` reading fix.

## Verification

- `python3 lint.py` — clean (no ERRORs; 6 store WARNs expected in a worktree, `#611`).
- `python3 -m pytest test_lint.py -q -k brief` — **46 passed, 476 deselected** (no test checks
  boilerplate prose; the brief checks cover file structure, not wording).
- `python3 dev/redproof.py check` — clean (quoted above).
- No browser guards run (non-UI lane, ports busy).

## Rebase

Rebased onto `master` at `1ab60a3c` — branch was already at tip, zero commits to replay, no
conflicts. Reported sha will be captured after commit.

## Out of scope (not fixed — named)

- **`review_artifact.py` lives at the repo ROOT, not `dev/`.** `#607`'s entry and the brief
  both name it among the tools invoked by skill-dir path; it is at `./review_artifact.py`, not
  `dev/review_artifact.py`. A lane told to run `python3 dev/review_artifact.py` would get
  "No such file." Not my file to fix (not in scope), but the brief's enumeration is slightly
  wrong about its location.
- **The brief head itself still cites the skill-dir interpreter path** (`python3
  /home/…/skills/ud-dreamwork/lint.py --target <worktree>` at the top of my own BRIEF.md).
  The rule I added protects a lane reading it; the coordinator could stop emitting the
  absolute interpreter path in future heads, which is the forward-only version of
  by-construction. That is a coordinator-side change, not a boilerplate one.

## Dogfood report

1. **The brief's own `--target <worktree>` example at the top is itself the trap.** My BRIEF.md
   head describes the defect as a thing that happens when a brief says `python3
   /home/…/skills/ud-dreamwork/lint.py --target <worktree>` — and then the boilerplate appended
   below it already never cites that form. The brief head and the boilerplate disagree, and the
   brief head is the one with the bug. The fix has to be a rule (immunity) precisely because the
   boilerplate cannot fix the heads.
2. **`review_artifact.py` is mislocated in the entry.** Cost me one wasted `ls dev/review_artifact.py`
   before I found it at the root. Minor, but the entry's enumeration should say where the file is.
