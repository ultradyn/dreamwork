# Review `glm-1072answers` — a route export whose own lane says nothing proves it renders

Head `a5ffb2dc`, which **I rebased onto master `44397ea6` myself just now** — the branch was 23
commits behind. The rebase was clean (rc=0, no conflicts, no working-tree dirt), but I did NOT
re-run anything after it, so **every measurement quoted below predates that rebase**. Treat them as
the lane's claims about an older base, not as current facts. 3 commits, 12 paths, 676 insertions.
Adds an
`Answers` wrapper export as a **delegate** — a call into `buildAnswers(data)` with no markup of
its own — plus the `Answers.{d.ts,fixture.json,prompt.md}` triad, a fixture-coverage test in
`test_client_dist.py`, three `DATA_SIBLINGS` entries in `watch.py`, and a rebuilt `client/dist`.

## The finding I most want you to try to construct

**Can the delegate ship broken and stay green?**

The lane says so itself, and named it as out of scope: *"no test compares the delegate's rendered
output to `buildAnswers`; the Reviews DOM mutation loop (`dev/build/ds-src/…`, `:528-549`) only
asserts mount + no-mutation, both met by an empty `<div>`."* If that is right, the export's whole
purpose — rendering the Answers surface — is unguarded, and the fixture test guards only the
fixture's shape.

**Construct it, do not take it on trust.** Replace the `Answers` delegate body with something
that mounts an empty element (or returns the wrong builder's output — `buildReviews`, say) and
run the full relevant suite. If everything stays green, quote the passing run: that is a P1-shaped
hole in a landing whose entire deliverable is the export. If something *does* catch it, name the
test — the lane will have been wrong about its own coverage, which is equally worth knowing.

Then say what the cheapest honest closure is. The lane names one (a DOM-equality mirror, ~90
lines, touching landed `#1071` Reviews code) and declined it on size and on "don't change #1071".
Judge that call: is there a closure that does **not** touch `#1071` — e.g. asserting the delegate's
output equals `buildAnswers(fixture)` directly, without going through the shared mutation loop?

## Also construct

- **The `DATA_SIBLINGS` trap, generalised.** The lane hit a red because `watch.py`'s
  `DATA_SIBLINGS` lists ds-src files individually with no glob, so every new component needs a
  3-line companion edit. Check whether the three new entries are correct and complete, and
  whether the deploy actually ships them (`dev/deploy_state.py`). Then answer the question the
  lane raised: **can the ds-src entries be derived from the manifest** the way the dist check
  already derives its inputs, so the next route-export lane cannot forget? If yes, that is a task
  worth filing, and say so — do not implement it.
- **Runtime headroom.** The lane measured `runtime_bytes 146462 → 146462` (unchanged) against
  `#1190`'s landed `RUNTIME_WEIGHT_BUDGET = 147_000`. That is **538 bytes** of headroom on a
  budget that exists to be tripped. Confirm the number independently and say plainly whether the
  next runtime-touching lane trips it. `COMPONENT_WEIGHT_BUDGET` is deliberately `None`
  (reported, not bounded) — that is Max's open question, not a defect; do not treat it as one.
- **The fixture's five cases.** `unreadable`, `empty`, `open`, `answered`, `askform`. The lane
  claims the test sweeps EVERY record rather than only `[0]`. Verify that, and check each case
  actually reaches the branch it names in `client/views.js` — particularly `unreadable`
  (`answers_health`) and `askform` (the always-rendered composer alongside real records).
- **Determinism.** `just build-client && git diff --exit-code -- client/dist/` must be clean on a
  fresh build. A committed `dist` that does not reproduce is a landing that cannot be verified
  again.
- **Its Direction 2 is an admitted open false-green** — a structurally valid but trivial fixture
  (`title="q1"`, `body="b"`) passes. The lane says Reviews and QaCard share this limit. Say
  whether that is an inherent property of shape guards (in which case it is honest and fine) or
  whether the assertion could cheaply demand something the trivial fixture cannot satisfy.

## A correction of MINE that bears on how you read this lane

**This lane's brief inherited a stale citation from me** — the second-truth/render-rule claim I
got wrong on `#1069`. The rule was **relaxed** on 2026-07-31 answering `#614`; what survives is a
**cost**, not a refusal, and `#505` G2 reads per-surface with a *derived* surface not counting as a
second authority.

Two consequences for your review:

1. **Do not accept a report that repeats my citation as if it were verified.** If the lane's
   reasoning leans on the rule as a prohibition anywhere, flag it.
2. **The lane's delegate-not-markup direction is still correct** under `#630`'s derived-wrapper
   plan — that plan is what makes a call-into-the-builder export the right shape, independent of
   the rule I miscited. Do not mark the lane down for following it.

## What is already established — do not re-derive

Its premise verification is sound and I have checked it: `buildAnswers` is at `client/views.js:1213`,
**not** the task body's `:1198`, and the lane verified this before building. No pre-existing Answers
export. `buildAnswers(d)` is pure with respect to its argument; the data shape comes from
`watch.py:3925-3927`.

Its red-proof is sound and specific: subject the fixture guard, expectation source tracked
`test_client_dist.py`, direction 1 hollowed the `open` record giving
`AssertionError: Answers open fixture props do not exercise a real question`, restore green.
`check --require 1` unpiped `EXIT_CODE=0`, reach `caught 1 of 1`. `handoff` derived
`1 injection(s) owed`, `12 changed path(s), 12 binding, 0 inert doc`, `HANDOFF_EXIT=0`.

Its FIRST rebase (master `6d91f7f4` → `0ea95d68`) touched only `lessons.md` / `questions.md` /
`coordinator-checklist.md` with no code overlap, and it re-armed the red-proof in full afterwards.
That much is established.

**What is NOT established is the state after MY rebase onto `44397ea6`.** Those 23 commits landed
`#1197`, `#1069`, `#644`, `#1179` and more, changing `dev/brief.py`, `dev/redproof.py`,
`dev/land_lane.py`, `lint.py` and `client/` among others. So three things the earlier rounds settled
are open again, and they are the first things to check:

1. **Is the committed `client/dist` still reproducible on this base?** `just build-client &&
   git diff --exit-code -- client/dist/` — a rebase does not rebuild it. This is the single most
   likely thing to be broken and the cheapest to check, so do it FIRST.
2. **Is the red-proof still armed and still discriminating on the new base?** `#993` requires a full
   re-arm after every rebase, and I performed the rebase, not the lane.
3. **Does the runtime-weight headroom claim still hold?** It was 538 bytes on the old base; landings
   since then touched the runtime.

If any of those three is broken, that is the finding and it outranks the constructions below —
report it and stop rather than spending the round on a branch that cannot land.

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
