# Lane 769 report — the supported dispatch route claims a silence it does not have

**Verdict:** FIXED. Silenced the `just` recipe with `@` so the route matches the
wrapper's silence. One character in the justfile, plus a binding test.

**Post-rebase sha:** `a7ca603c` (rebased onto master `4db4a02e`).
**Base sha at dispatch:** `bc7aab6b` (verified).
**Lane bar:** 5 warnings at `bc7aab6b` — confirmed. Post-rebase, lint reports
5 ERRORs + 5 WARNs, all ERRORs pre-existing on master from commit `24b45a3f`
(see Out of scope).

---

## Before / after — the actual route output

The route was exercised with a harmless fake `ccc` runner (`echo` + exit 0), not
a real lane. `M = dev/lane_scratch.py measure` on btrfs.

### BEFORE (no `@` prefix) — healthy dispatch

```
$ PATH=<fakebin> just dispatch-lane <prompt> @cx-coder -y
python3 dev/dispatch_lane.py --prompt "/tmp/.../echoprobe-prompt.txt" -- ccc -y "@cx-coder"
RUNNER-RECEIVED-ARGC=3
RUNNER-RECEIVED-ARGV0=-y
RUNNER-RECEIVED-PROMPT-BYTES=9
ROUTE EXIT CODE = 0
```

The first line is **just's recipe echo**, not the wrapper. The wrapper itself is
silent — confirmed by `test_healthy_dispatch_is_silent_and_passes_prompt_as_one_argument`,
which runs the wrapper directly and asserts `stdout == ""` / `stderr == ""`.

### BEFORE — refused dispatch (Direction 2)

```
$ PATH=<fakebin> just dispatch-lane <bad-prompt> @cx-coder -y
python3 dev/dispatch_lane.py --prompt "/tmp/.../echoprobe-bad.txt" -- ccc -y "@cx-coder"
dispatch refused: standing contract from briefs/boilerplate.md is missing or altered; append that file verbatim to the prompt
error: Recipe `dispatch-lane` failed on line 30 with exit code 2
ROUTE EXIT CODE = 2
```

The recipe echo appears on the refused dispatch **too** — it fires before
validation, so it cannot distinguish "launched" from "attempted."

### AFTER (`@` prefix) — healthy dispatch

```
$ PATH=<fakebin> just dispatch-lane <prompt> @cx-coder -y
RUNNER-RECEIVED-ARGC=3
RUNNER-RECEIVED-ARGV0=-y
RUNNER-RECEIVED-PROMPT-BYTES=9
ROUTE EXIT CODE = 0
```

No recipe echo. The route is now genuinely silent at rc=0.

### AFTER — refused dispatch

```
$ PATH=<fakebin> just dispatch-lane <bad-prompt> @cx-coder -y
dispatch refused: standing contract from briefs/boilerplate.md is missing or altered; append that file verbatim to the prompt
error: Recipe `dispatch-lane` failed on line 34 with exit code 2
ROUTE EXIT CODE = 2
```

Only the wrapper's own stderr refusal. No recipe echo that could be mistaken
for a launch.

---

## The decision: `@` prefix, not a doc correction or a designed line

**The `just` recipe echo is not an audit record — it is an attempt record.** It
fires before the wrapper validates, so it appears identically on a healthy
launch and a refused dispatch (Direction 2, measured above). A record that
cannot distinguish "launched" from "attempted" is worse than no record (#671,
#136): it reads as a launch when no launch happened.

**The audit record is the persisted brief (#766).** `persist_prompt()` writes
the byte-exact validated prompt to `.dreamwork/docs/briefs/<task>-<lane>.md`
with a sha256 receipt, before `os.execvp()`. That is the authoritative
pre-launch record — it carries the prompt content, the task id, and the lane
identity. The recipe echo carried only the command line (runner, agent, prompt
path), none of which is the prompt content. The runner/agent identity is also
recoverable from `status.json['lanes']` (#702) and the coordinator's own
dispatch procedure.

**Direction 2 closes it.** The brief said: "if your answer is keep the echo as
the audit record, then a dispatch that never happened must not produce a line
that looks like one that did." The pre-fix echo violated exactly that — the
refused-dispatch run above produces a recipe-echo line indistinguishable from a
healthy dispatch's. The `@` fix removes the echo entirely, so a refused
dispatch produces only the wrapper's stderr, which is unambiguously a fault.

### Where the silence claim lives

The brief attributes the silence claim to "SKILL.md's #768 section." I searched
SKILL.md: the dispatch section (lines 356–380) does not contain the word
"silent" and does not cite `#755`. The explicit claim lives in the **#768
ledger entry's merge note**: *"contract-appended is rc=0 and SILENT (#755)."*
That claim was always correct about the wrapper and wrong about the route. With
the `@` fix, the route is now also silent, so the ledger entry's claim becomes
true about the route. No SKILL.md text change was needed — the behavior changed
to match the claim, per #440 ("exactly one of the doc and the behaviour
changes").

### On #755's severity

#755's rule is about a **check firing on healthy input**. The recipe echo is
not a warning and does not read as a fault — it is `just`'s default behavior.
So the echo was never literally a #755 violation. The contradiction was real
(route claims silence, isn't silent), but the severity is lower than a #755
violation would imply: no reader would mistake the recipe echo for a fault
signal. The `@` fix still resolves the contradiction cleanly.

### Why not a designed one-liner (Option C)

A designed line (e.g. `@echo "dispatch → {{agent}}"`) would fire before
validation too, so it has the same Direction 2 defect as the raw echo — it
cannot distinguish attempt from launch. Making it fire after launch would
require `dispatch_lane.py` to print it, which touches the wrapper's output (the
brief warns: #766 persistence is newer than the silence claim). And a designed
line would make the #768 ledger's "SILENT" claim *more* wrong (the route would
print one line), while the `@` makes it *true*. Option C changes both the doc
and the behaviour, violating #440.

---

## What changed

**`justfile`** (1 recipe line + 3 comment lines): prefixed the `dispatch-lane`
recipe body with `@`, added a comment explaining why the `@` is load-bearing
and that the persisted brief (#766) is the audit record.

**`test_dispatch_lane.py`** (+1 test, 21 lines): `test_dispatch_lane_recipe_is_at_prefixed_so_the_route_is_silent`
asserts the recipe body's single `dispatch_lane.py` line starts with `@`. If
someone removes the `@`, the test fails on a named message.

`dev/dispatch_lane.py` was NOT touched — the wrapper's output is unchanged.
SKILL.md was NOT touched — its dispatch section never made the false claim.

---

## Red-proof

### Direction 1 — the check goes red on the discriminating message

1. `python3 dev/redproof.py begin justfile` — snapshot of the FIXED justfile.
2. Sabotage: removed the `@` prefix from the recipe body.
3. Ran `test_dispatch_lane_recipe_is_at_prefixed_so_the_route_is_silent`:

```
FAILED test_dispatch_lane.py::test_dispatch_lane_recipe_is_at_prefixed_so_the_route_is_silent
AssertionError: dispatch-lane recipe must be @-prefixed: without it just echoes
the expanded command on every dispatch, so the route is not silent (#769)
```

4. `python3 dev/redproof.py restore justfile` — restored the FIXED file.
5. Verified: `grep '@python3 dev/dispatch_lane.py' justfile` → present.

### Direction 2 — the open false-green

**For the test:** I cannot construct a false-green. The assertion finds exactly
one non-comment line containing `dispatch_lane.py` in the recipe body (asserts
`len == 1`) and checks its first non-whitespace character is `@`. Every evasion
I tried either fails the count (a second `@`-prefixed line alongside an
un-prefixed one → `len == 2`) or fails the prefix (renaming the recipe, putting
`@` on the signature line). The test is precise.

**For the route (the brief's Direction 2):** the pre-fix echo fired on refused
dispatches too (measured above — the "BEFORE — refused dispatch" output shows
the recipe echo line before the stderr refusal). A reader seeing that line
could not tell whether the dispatch succeeded. This is #671/#136: a record
that examined an attempt and rendered it as a launch. The `@` fix closes it —
no echo means no line that could be mistaken for a launch.

### Redproof check gate (quoted)

```
history: examined 1 commit(s) since 4db4a02eafd6 (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  justfile (sha 826115235712, hint: 'python3 dev/dispatch_lane.py --prompt "{{prompt}}" -- ccc {{CCC_ARGS}} "{{agent}}"')
```

---

## Cited issues — relied-on lines

- **#768** (landed): *"Landed 277f8d2c … contract-appended is rc=0 and SILENT
  (#755)."* — the silence claim, correct about the wrapper, now true about the
  route. Also: *"The wrapper asserts what it PASSES, not what the runner
  received; SKILL.md states that limit rather than letting the name imply more
  (#651)."*
- **#755** (landed): *"the unanchored form has now corrupted the file once"*
  — #755's rule is about a check firing on healthy input; the echo is not a
  warning, so not literally a #755 violation. Severity weakened; contradiction
  stands.
- **#607** (landed): *"That leading path is a SYMLINK into the main checkout,
  so it is the INTERPRETER, while --target is only the SUBJECT."* — the
  coordinator verified the subject (`dispatch_lane.py`) and asserted about the
  interpreter (the `just` recipe), which is #607's shape.
- **#440** (landed): *"a single supported way to fold an entry"* — exactly one
  of the doc and the behaviour changes so they agree. The behaviour changed
  (recipe silenced); the doc (SKILL.md) stayed as-is because it never made the
  false claim.
- **#671** (landed): *"examines zero ledger entries and says so confidently"* —
  the recipe echo examined an attempt and rendered it as a launch.
- **#136** (landed): *"A questions.md that parses to nothing must say so"* —
  broken and healthy must not render identically. The recipe echo rendered a
  refused dispatch identically to a healthy one.
- **#702** (landed): *"status.json records a dispatch in two places and only
  one is machine-readable"* — the runner/agent identity is recoverable from
  `status.json['lanes']`, so losing the recipe echo does not lose the only
  record of what was dispatched.
- **#766** (landed): *"persist_prompt does _write_exclusive(brief, prompt) and
  hashes the same string, so there is no transformation"* — the persisted brief
  is the byte-exact validated prompt; it is the audit record, not the recipe
  echo.

---

## Rebase outcome

- Dispatch base: `bc7aab6b`. Master at report time: `4db4a02e`.
- Rebased twice (master moved during work: `24b45a3f` → `4db4a02e`). Both clean,
  no conflicts. The only blocker was untracked brief artifacts
  (`.dreamwork/docs/briefs/769-glm-769echo.{md,sha256}`) that master came to
  carry — moved aside, rebased, master's copies are now in the tree.
- No conflict markers (`grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` → clean).
- Post-rebase sha: `a7ca603c`. One commit on top of master.

---

## Out of scope (named, not fixed)

1. **5 lint ERRORs pre-existing on master.** Commit `24b45a3f` ("docs(#766,#770):
   commit the first five genuine persisted briefs") committed brief artifacts
   for lanes 630, 631, 645, 765, 769 that fail the #405 check (worktree-naming
   brief without absolute `inbox.md` path). My change touches no briefs. These
   errors exist on master itself; the lane bar of "5 warnings" was measured at
   `bc7aab6b`, before this commit landed. The coordinator should either fix the
   briefs or grandfather them.

2. **The brief's premise: "SKILL.md's #768 section says the supported dispatch
   route is silent."** The word "silent" and the citation "#755" do not appear
   in SKILL.md's dispatch section. The claim lives in the #768 ledger entry's
   merge note. This is itself a mild #607-class error (asserting about SKILL.md
   while the claim is in the ledger). It did not change the fix — the
   contradiction is real either way — but the brief's attribution was off.

3. **`test_healthy_dispatch_is_silent_and_passes_prompt_as_one_argument` tests
   the wrapper, not the route.** The test name says "is silent" but it runs
   `python3 dev/dispatch_lane.py` directly, not `just dispatch-lane`. So the
   wrapper's silence is tested; the route's echo was never tested. My new test
   closes the route-level gap, but the existing test's name could mislead a
   reader into thinking the route's silence was already covered.

---

## DOGFOOD REPORT

**The brief's attribution was wrong, and it matters.** The brief says
"SKILL.md's #768 section says the supported dispatch route is silent on a
healthy dispatch, citing #755." Neither "silent" nor "#755" appears anywhere in
SKILL.md's dispatch section. The claim lives in the #768 ledger entry's merge
note. This is #607's shape one level up: the brief verified the route's
behaviour (ran it, saw the echo) but attributed the silence claim to the wrong
artifact (SKILL.md instead of the ledger). It did not change the outcome — the
contradiction is real and the fix is the same — but a lane that trusted the
attribution would search SKILL.md for a claim to correct, find nothing, and
either give up or invent a change. I almost did.

**Master moves fast enough to invalidate a lint baseline mid-task.** The lane
bar ("5 warnings") was measured at `bc7aab6b`. After rebasing onto the current
master (`4db4a02e`), lint reports 5 ERRORs from brief corpus artifacts the
coordinator committed at `24b45a3f`. A lane that compares its post-rebase lint
count to the brief's baseline would conclude it introduced 5 errors. It did
not — they're pre-existing — but nothing in the lint output distinguishes
"pre-existing on master" from "introduced by this branch." A lane-scoped lint
that reports only deltas from the merge-base would prevent this.

**The rebase blocked on untracked brief artifacts.** `.dreamwork/docs/briefs/
769-glm-769echo.{md,sha256}` were untracked in my worktree (written at dispatch
time by `persist_prompt`). When master came to carry them (via `24b45a3f`),
`git rebase` refused: "untracked working tree files would be overwritten." This
will happen to every lane whose brief the coordinator commits before the lane
rebases. A one-line note in the boilerplate ("if the rebase blocks on untracked
brief artifacts, `mv` them aside, rebase, then let master's copies stand")
would save each lane the diagnostic step.
