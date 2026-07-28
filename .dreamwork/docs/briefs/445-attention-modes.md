# Brief — #445: design the four attention levels, and reconcile them with `#443`'s run modes

Repo: `ud-dreamwork`. Worktree: **`.worktrees/attention`**, branch **`wt/attention`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/plans/attention-modes.md, .dreamwork/review/src/445-attention-modes.html, .dreamwork/docs/doc-map.md

**DESIGN ONLY. Build no mechanism.** No `watch.py` change, no new runtime behaviour, no file the loop reads at
tick time. The deliverable is a design plus a review artifact he can rule on.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[attention]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/attention-inbox.md` so I can steer you mid-task.

Report a line per milestone (**sources read**, **IGC done**, **spec drafted**, **artifact built**,
**committed**). Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added, and I will file the ask.

## The source of truth, and it is not this brief

**His dictated text at `2026-07-28T23:40` in `.dreamwork/watch-events.log` is the authority.** Read it there,
in full, first. `#445` in `.dreamwork/tasks.md` is a *structuring* of it by the coordinator, not a replacement,
and where the two differ **his words win** — say so if you find a divergence.

Then read `#443` (run modes conflate pace with delegation posture) and `#421` (answered `rec`: A+B+D, C
withdrawn) in the ledger, and `.dreamwork/run-mode`'s contract in `file-formats.md`.

## The four levels, as he named them

1. **ask me everything** — any non-trivial design or architectural choice produces a review document and **he**
   chooses. *"probably a bit more than you've been asking me, but you do ask me a lot of stuff"*.
2. **keep me informed** — mostly automatic, but each material choice emits **documentation rather than a
   question**: what the choice was, why a choice was needed, the details, a brief note on the other options,
   and the evaluation table. *"a review in the sense that it's for the human's review, but it's not asking them
   for a choice."* He put a number on it: **~10–20% of questions escalate**.
3. **near-automatic** — the evaluation still happens and is **logged to a journal folder** (ADR-shaped), but
   nothing surfaces unless it is genuinely big or the loop is stuck; *"it's too much in the noise to actually
   surface"*.
4. **full auto** — *"tasked with figure it out"*; every blocker is the loop's to solve, **never blocked on a
   reply**, and its cooperation clause must not be lost: *"you still want to cooperate with the user … but you
   never want to be blocked just because the user hasn't replied."*

## Four things that are load-bearing and easy to lose

- **"The evaluation table" means an IGC matrix, and IGC is now defined.** `igc-method.md` and
  `igc-concepts.md` are in the repo root (vendored tonight as `#447`): (Idea, Goal, Context), per-cell `✔`
  non-refuted / `✘` refuted **with the decisive error written out** / `?` a TODO, an `All` rollup, breakpoints
  instead of maximisation, and **never a score column**. Level 1 shows it to him, level 2 embeds it in the
  emitted document, level 3 logs it unsurfaced. **Read the method before you specify how it renders.**
- **The escalation test is materiality against his goals, not difficulty.** His words: *"some choices where you
  have multiple good options … are not very material. It doesn't really matter to the user's goals. You can
  just make a choice in that regard … unless the user has specifically mentioned something."* A design that
  escalates by *hardness* will escalate the wrong things. Note his ~10–20% figure is a **soft estimate**, not a
  gate — he ruled at 01:17 that numbers steer and never measure, so do not specify a counter that enforces it.
- **Stuck is a state you have to earn.** *"you should always use a subagent to research the question, see if
  anyone's solved it before, what the options are"* — before declaring a blocker at any level.
- **The deepest part, and it belongs in `DREAMWORK.md` regardless of what gets built:** when uncertain, **ask
  about his goals rather than about the immediate decision** — *"if you know about their goals, you can
  evaluate not just the current answer … but you can also do that for many other questions."* Uncertainty
  usually means the goals need to be more specific. Propose the exact `DREAMWORK.md` wording in your report;
  **do not edit `DREAMWORK.md` yourself** (the coordinator owns it).

## The reconciliation, which is the hard half

`.dreamwork/run-mode` already exists with three values — `lackadaisical` / `hot` / `assisted` — and `#443` says
those conflate **pace** with **delegation posture**. `#445` adds a third axis: **how much he is asked**.

**Decide with an IGC whether these are one control or several, and say why.** Rival ideas at minimum: one
combined mode enum; two orthogonal axes (pace × asking); three axes (pace × asking × delegation); asking-level
as a per-task override on top of a global default. Goals must be binary or breakpoints — e.g. *"he can change
how much he is asked without also changing how fast the loop runs"* is binary and refutes at least one rival.
His own evidence that these are tangled: he had to tell the coordinator its delegation posture **in prose**,
twice, because no control expressed it (that is `#443`'s filing reason).

**Also specify the subagent target and policy** he asked for: a target number of subagents and what to do when
reality differs — his stated shape was `>=1` valid, **warn on 0**, and hard-invalid below 0, plus free text.

## Deliverables

1. **A design doc** at `.dreamwork/docs/plans/attention-modes.md` — the four levels with, for each: what
   surfaces, what is emitted, where it is written, and **what happens if he never responds**. Include the
   reconciliation IGC and the axis decision. Add a **`doc-map.md` row** (contended: on conflict resolve as a
   union and verify the row against the directory in both directions).
2. **A review artifact** `.dreamwork/review/src/445-attention-modes.html`, built with
   `python3 review_artifact.py build <src>`. **Two build-time contracts now apply and will refuse your build if
   missed** — exactly one real `#ask` (`#436`) and a **what-happens-if-he-says-nothing** sentence (`#455`,
   production line `enforce_if_silent_contract`). Read `269-draft-durability.html` as the worked example and
   match its register. Put the four blocks he asked for on the `#263` artifact at the top of yours too: context
   paragraph, the problem, the IGC (goals, ideas, table), your recommendation. **Be concise** — a style
   instruction, not a measurement; no word counts.
3. **The open calls for him**, as questions.md lines in your report (I file them). Use the new declared form so
   `#421` B can check the fold: a bold `**Sub-decisions:** ` `Q1`, `Q2` … line naming each call.
4. **Table hygiene:** an IGC matrix in an artifact needs `min-width:0;width:100%;table-layout:fixed` and a
   **390px check** — a 4197px-wide table shipped tonight and he could not read it (`c19107a`).

## Done means

1. The doc, the artifact (built, not stale, both contracts satisfied), the doc-map row, the proposed
   `DREAMWORK.md` wording, and the questions.md lines.
2. The reconciliation IGC has **one survivor** or an explicit statement of why it has zero or several — no
   scoring, decisive errors written out.
3. `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
   `just test`.** Bind nothing in 39880–39899 or 39890–39899 except the ephemeral port `above_fold.mjs` serves
   itself on.
4. Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
   heartbeat, the monitors, or the loop. Never `pkill -f`.

## Files

**Yours:** `.dreamwork/docs/plans/attention-modes.md`, `.dreamwork/review/src/445-attention-modes.html` and its
built output, `.dreamwork/docs/doc-map.md`.

**Not yours:** `watch.py`, `test_watch.py`, `user_events/*`, `test_user_events_http.py` (**lane E holds those
and is mid-cutover**), `DREAMWORK.md`, `SKILL.md`, `file-formats.md`, `lint.py`, `review_artifact.py`,
`review-artifact.template.html`, `.dreamwork/run-mode`, `transitions.md`, `watch-design.md`, `justfile`,
`dev/capture/*`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`, and every other
artifact under `.dreamwork/review/`.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'design(#445): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree.
- **Commit before you finish.** **~20 minutes**; spend it on the reconciliation IGC and on *what surfaces at
  each level*, not on prose.
- **Push back with reasons.** If the honest finding is that four levels collapse to three, or that `#443` and
  `#445` are one control and my brief is wrong to hedge, say so and argue it — a refusal with evidence is a
  complete answer, and the most valuable lanes tonight refused what they were handed.

## Report

Say: which model you are; any place his dictation and the ledger entry diverge; the reconciliation IGC with
each decisive error and the surviving idea; what surfaces / is emitted / is logged at each of the four levels
and what happens on no reply; the subagent target-and-policy spec; the proposed `DREAMWORK.md` wording for the
ask-about-goals preference; the questions.md lines with the `**Sub-decisions:**` declaration; the measured fold
for your artifact and the 390px result; and confirmation you built no mechanism, did not touch :35110, and did
not run the full `just test`.
