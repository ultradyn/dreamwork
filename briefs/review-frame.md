# Review frame — standing rules for every review dispatch

Concatenate this into every review prompt, the way `frame.md` is emitted into every lane brief.
It exists because the alternative — remembering to hand-write these rules per dispatch — measurably
fails: two false findings in one night (`#1109`), and a third the following review.

`#1109` established that review briefs have **no generation path** (`dev/brief.py` builds lane
briefs only; there is no `--review` mode, no `review-frame` emitter, and review dispatches leave no
receipt in `.dreamwork/launch-attempts/`). So this file is a coordinator convention, not a
guarantee by construction. Its weakness is known and recorded on `#1112`.

---

## You are working in a clone. Three things are invisible or misleading here.

Reviewers are dispatched into `git clone -s` copies under `/tmp`. **That is deliberate and
correct**: a reviewer launched from the repo root holds the main checkout by cwd, and the merge gate
refuses to run while any `ccc`/`grok`/`codex` process does. The clone is what lets a review and a
gate overlap.

The cost is that a clone cannot see everything the repo contains. Each of the following has already
produced a confidently-wrong finding:

1. **Lane-scoped red-proof state does not exist here.** The registry lives at
   `~/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/<lane>/lane-<lane>-<id>/redproof/registry.json`,
   keyed by lane identity. A clone has no lane identity, so `redproof check` reports
   *"FAULT — no redproof registry could be located"*. **Do not report red-proof findings at all** —
   the merge gate verifies red-proof itself, in the real lane worktree, where the same command
   exits 0. (`#1033`'s review filed this FAULT as a "material hand-off failure"; it was an artifact
   of the reviewer's own environment.)

2. **Unlanded sibling branches are not in your clone.** A search returning nothing proves the symbol
   is absent from **this tip**, and nothing more. A claim about another branch is
   **unverifiable from here, not false**. (`#1094`'s review refuted a correct caveat with an empty
   `rg`; the symbol was on the unlanded `glm-1034clean`. The caveat was right and nearly got
   deleted.)

3. **`python3 lint.py` is not clean in a clone, and its ERRORs are clone-state artifacts** — the
   tracked `tasks.md` is a migration notice, the gitignored ledger store does not travel, and
   worktree-drain state is stale. Compare **WARN row SETS** against `origin/master`. Never report
   absolute warning counts, and label any clone-state ERROR as such rather than as a branch defect.

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
