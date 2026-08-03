# Review `cx-1179revproof` — does the rebase-tolerant history scan still catch a committed injection?

The branch changes `dev/redproof.py` and `test_redproof.py` only. Head `0cb73e53bd12`.

## What it claims to fix

The red-proof history scan refused a clean branch after a routine rebase: because rebasing
rewrites every commit SHA, `begun_head` stopped being reachable and pre-`begin` production code
started looking like an injection. The lane persisted the reproduction:
`AssertionError: rebase made pre-begin production code look like an injection`, `1 failed`,
`reproduction_exit=1`.

Its remedy, from the surviving IGC row: *"retain exact reachability while `begun_head` survives;
after rebase invalidates it, exclude only the leading branch prefix inheriting injection bytes
already at merge base. Once the path differs, later reintroduction is a hit."* The seam is
`dev/redproof.py::_history_match_is_armed`.

## The question this review exists to answer

**This code decides whether a committed red-proof injection is detected. A hole here does not
announce itself — it shows up as a clean `check` on a branch that committed sabotage.** The fix
makes the scan MORE permissive after a rebase, by construction. So the review question is not
"does the reported reproduction pass now" — the lane showed that. It is:

**Can you construct a genuinely committed injection that lands inside the excluded prefix and
therefore escapes?**

Build it. The lane's own separating pair puts a genuine injection AFTER the prefix
(`check_exit=1`, naming `wip(#1179): genuinely committed injection`). The adversarial case is
the one it did not build: injection bytes that are *at* or *reachable from* the merge base in a
way the prefix rule treats as inherited, but which this branch in fact introduced. If the rule
is sound, say why it is sound with a construction that tries and fails. If it is not, that is a
P1.

Related, and worth its own construction: the rule says *"once the path differs, later
reintroduction is a hit."* Test reintroduction — inject, revert, re-inject later on the same
path — and say whether the second one is caught.

## Also examine

- **`#942`'s retired records.** `forget` RETIRES a restored registration instead of erasing it,
  keeping `injected_sha` and the ORIGINAL `begun_head` in scope for the history scan alone. The
  lane's audit reports `retired: 1 withdrawn registration(s) were also searched for in history
  and found in no commit`. Does the new prefix exclusion narrow the window in which a retired
  record would be found? A retired record's `begun_head` is by definition older.
- **Fail-open vs fail-closed.** When the boundary cannot be resolved at all — no merge base, a
  detached state, an unreadable object — does `_history_match_is_armed` refuse or allow? The
  whole value of this check is that it fails closed.
- **No text-age exemption.** The lane states it added none. Verify that: an exemption keyed on
  commit age or author time would be rewriteable, and the IGC explicitly rejected the
  author-time row for that reason.
- **Whether the two rejected SHA-recording rows were rejected for the right reason.** "Exact
  `begun_head` only" and "record injection commit SHA" both die on rebase — confirm that is true
  rather than assumed, because if a recorded SHA *could* survive, it is a stronger design than a
  prefix heuristic.

## Do not report as findings

The reviewer/author red-proof registry mismatch that appears when you run the lane's tests from
an attached review checkout is a checkout-state artifact, not a defect — a prior round's
reviewer already excluded it. Note it and move on.

## Its own dogfood finding, which I have already acted on

The lane reported that my brief cited `lessons.md:430` when the file is `.dreamwork/lessons.md`.
That is my error, corrected in the briefs written since. No action needed from you.

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
