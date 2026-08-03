# Review `glm-1206shelleval` — stopping a justfile recipe from executing agent-authored prose

Head `05bc3158`, rebased onto master `6a7acec0`. 2 commits, touching `justfile`,
`dev/launch_lane.py`'s test companion, and a new/extended `test_launch_lane.py`.

`just launch-lane` interpolated `{{HEAD}}` into an `sh` command inside double quotes, so `sh`
evaluated brief content as code. The fix: `set positional-arguments := true` plus passing the four
positionals as `$1..$4`, on the argument that POSIX variable expansion is non-recursive, so a `$N`
value is substituted verbatim and can never be re-evaluated. `CCC_ARGS` deliberately stays
`{{CCC_ARGS}}`.

## This is a code-execution defect, so review it as one

The lane did not merely reproduce mangling — **it reproduced execution**. A fixture brief containing
`` `id -u` ``, `$VAR` and a fenced command caused `sh` to RUN the fence (`echo PWNED` executed) and
substitute the real uid; a separate `$NO_SUCH_VAR_1206` fixture killed the recipe with
`sh: … unbound variable`, exit 127.

Briefs are agent-authored prose full of backticks, `$` and fenced commands, and they run on the
coordinator's machine against the main checkout. **Treat "does any input still reach a shell as
code?" as the review's primary question**, not a style point.

## The findings I most want you to construct

1. **Is the non-recursive-expansion claim actually true for THIS recipe, on this `just` and this
   `sh`?** The whole fix rests on it. Construct the adversarial input rather than reasoning about it:
   a HEAD value containing `` `id -u` ``, `$(id -u)`, `$HOME`, an embedded single quote, an embedded
   double quote, a newline, a `;`, and a fenced block — and assert the bytes python receives are
   **identical** to the file's bytes. The lane's own test
   (`test_launch_lane_recipe_passes_brief_head_verbatim_not_shell_evaluated`) asserts `MATCH`; check
   whether its fixture is as nasty as the ones above, and if not, make it so and report what happens.

2. **Does `CCC_ARGS` staying `{{CCC_ARGS}}` reintroduce the hazard?** The lane's justification is
   that it carries "trusted coordinator flags, not brief content". Judge that. It is *plausible* — I
   type those flags — but "trusted because of who supplies it" is exactly the reasoning that made the
   HEAD path unsafe, and a flag value can be derived from a task title or a branch name. Say whether
   the asymmetry is principled or merely untested, and if the latter, whether the same `$N` treatment
   is free here.

3. **Does the GLOBAL `set positional-arguments := true` break any other recipe?** It is a
   justfile-wide setting and the repo registers ~94 guards through this file. The lane claims G6
   (minimal, no other recipe broken). Verify by exercising recipes that take arguments, not by
   reading. A recipe that silently changes how it sees `$1` is the regression that would not show up
   in `test_launch_lane.py` at all.

## Also check

- **The two siblings the lane found and did NOT fix** — `dispatch-lane`'s `--prompt "{{prompt}}"`
  and `brief`'s `--core "{{CORE}}"`, both content-bearing `type=Path` parameters with the same
  shape. I filed them as `#1217`. Confirm the claim is right, and confirm the lane genuinely left
  them alone (scope discipline). If there is a THIRD such recipe it missed, that is the most valuable
  thing you can return.
- **The red-proof's direction 2 is the interesting half.** Before the fix the dispatch *appeared to
  succeed* with a silently rewritten brief — a false green, not a crash. Verify the "before" state
  really is a silent success and not merely the exit-127 crash, because those are different defects
  and only the silent one is dangerous.
- **`launch_lane.py`'s head-is-a-FILE-PATH contract must be unchanged.** Passing content instead of a
  path yields `[Errno 36] File name too long`. Confirm the diff did not soften it.

## What is already established — do not re-derive

The IGC grid is recorded with six goals and the rejected rivals argued (single-quoting fails on an
embedded apostrophe; escaping is a blocklist over unbounded prose; stdin→tempfile over-engineers;
delete-and-document loses the wrapper, which is `#1177`'s "fix the wrong side"). The red-proof was
re-armed post-rebase and `check --require 1` unpiped gave `CHECK_EXIT=0`, caught 1 of 1, with the
discriminating failure `launch-lane shell-evaluated brief content (#1206): HEAD reached python
modified by sh`.

## Scope

**`justfile` and `test_launch_lane.py`.** `#1217`'s two siblings are deliberately out of scope; do
not mark the lane down for leaving them, and do say if the global setting makes fixing them riskier
rather than the one-line swap the lane predicts.

# Review frame — standing rules for every review dispatch

Concatenate this into every review prompt, the way `frame.md` is emitted into every lane brief.
It exists because the alternative — remembering to hand-write these rules per dispatch — measurably
fails: two false findings in one night (`#1109`), and a third the following review.

Review dispatch is governed by construction. `dev/brief.py --review BRANCH` appends this file
verbatim and persists a receipt under `.dreamwork/review-dispatches/`; `dev/dispatch_lane.py
--review-prompt` is the persist-only check and correctly refuses a runner. To launch, use the
distinct supported path:

    python3 dev/dispatch_lane.py --launch-review PROMPT --review-branch BRANCH --review-round ROUND -- ccc --permission-mode plan @cx-reviewer

That path pins the reviewed commit, creates an **attached review branch** and its own worktree,
records the launch attempt, launches with that worktree as cwd, and sets the reviewer role. Plan
mode is load-bearing: a reviewer reads and reports; it does not receive write permission.

---

## You are working in an attached review worktree. Three things are invisible or misleading here.

The supported launcher creates a review branch at the pinned commit and checks it out under the
sibling `.worktrees/` root. **The branch line is deliberate and load-bearing**: lane containment and
safe reaping can classify the checkout, while the separate cwd lets a review and a gate overlap.
Never replace it with `git worktree add --detach`.

The review worktree still does not make every live coordinator fact visible. Each of the following
has already produced a confidently-wrong finding:

1. **Your reviewer red-proof state is not the author's state.** The registry lives at
   `~/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/<lane>/lane-<lane>-<id>/redproof/registry.json`,
   keyed by lane identity and role. The launcher sets `DREAMWORK_LANE_ROLE=reviewer`, so a bare
   `redproof check` examines the reviewer's registry, not the author's. **Do not report that result
   as the author's red-proof verdict** — use `dev/lane_scratch.py --author-evidence` when the review
   needs the author's persisted evidence, and let the merge gate judge the author's registry.

2. **A sibling branch is not in your checked-out tree.** A search returning nothing proves the
   symbol is absent from **this tip**, and nothing more. Inspect a named sibling with `git show
   BRANCH:PATH`; do not treat the working-tree search as evidence about another branch.

3. **`python3 lint.py` is not necessarily clean in a review worktree, and some ERRORs are
   checkout-state artifacts** — the
   tracked `tasks.md` is a migration notice, the gitignored ledger store does not travel, and
   worktree-drain state is stale. Compare **WARN row SETS** against local `master`. Never report
   absolute warning counts, and label any review-worktree-state ERROR as such rather than as a
   branch defect.

**Report, do not suppress.** The instruction is to mark these **unverifiable-from-here with the
reason** — not to stay silent. A reviewer that reports nothing is worse than one that reports a
false FAULT. If something looks clone-shaped but you have direct evidence it is a real defect, say
both: what you saw, and why you believe it is not an artifact.

**Hash spaces are a related trap.** `redproof` pins `sha1(content)`. Git names a blob
`sha1("blob <len>\0" + content)`. They are different spaces; comparing one to the other proves
nothing, and `git cat-file -t <content-sha1>` failing is the expected result, not evidence of
corruption.

---

## Naming conventions that make a true search read as a phantom

In this repo a **PascalCase** name is a React wrapper under `dev/build/`, and its **camelCase**
counterpart is the builder under `client/`. `dev/build/wrapper-exports.js` states the mapping
outright (`QaCard.dwBuilder = 'qaCard'`). Searching one case in the other directory returns a true
"not found" that reads as "this symbol is fictional". Check the convention before concluding a
symbol is absent.

---

## Staleness is not a finding

The branch may sit on an older master than today's tip. Rebasing is the merge gate's job. **Judge
the diff**, not how far behind it is.

---

## What a finding must contain

Concrete, located, checkable. For each: the file and line, what is wrong, the evidence you actually
ran, and what would fix it. Distinguish **P1** (must fix before merge) from **P2** (should fix) from
**Standards** (nit). If you cannot substantiate something, say so plainly rather than softening it
into a claim.

End with one verdict: **MERGE**, **MERGE WITH FIXES**, or **ANOTHER ROUND**.

---

## Hard rules

- **Do NOT use `attn`.** Only the coordinator contacts the human.
- Do not write anything under `.dreamwork/`.
- **THE LEDGER HAS A SINGLE WRITER — THE COORDINATOR. Run no mutating `dev/ledger.py` verb**, including
  `file`, `note`, `fold`, `block`, `retitle` and `reprioritise`. This is the rule above restated as a
  verb, because that is how it gets broken: the store is `.dreamwork/ledger.sqlite3`, so filing a task
  *is* writing under `.dreamwork/` — but it does not feel like writing to a path, it feels like filing
  a follow-up, and a reviewer who would never touch that directory will run `ledger.py file` without
  noticing the rule applies. `#1071`'s round-2 review filed `#1186` exactly this way. Read-only verbs
  (`get`, `list`, `counts`) are fine.
- **Follow-ups belong in your report, not in the ledger.** Write the title and the body you would have
  filed; the coordinator files it. Nothing is lost by this and the concurrent-writer hazard goes away —
  the coordinator is writing that same sqlite store while you run.
- Do not commit, merge, or push. Your report is your stdout; the coordinator reads it.
