# Attention modes — the four levels, reconciled with run-mode (#445)

Design only. **Build no mechanism.** No `watch.py` change, no new runtime
behaviour, no file the loop reads at tick time. This doc + the review artifact
(`445-attention-modes.html`) + the questions.md lines are the deliverable; he
rules, then the loop builds.

## Authority

His dictated text at `2026-07-28T23:40` in `.dreamwork/watch-events.log` is the
authority — read there in full. The `#445` ledger entry is a structuring of it,
not a replacement, and where the two differ his words win. (They do not differ;
the ledger is faithful.) `#443` (run modes conflate pace with delegation
posture) is the sibling this must reconcile with. `IGC` is defined in
`igc-method.md` + `igc-concepts.md` (vendored by `#447`).

## The reconciliation — one control or several? (the hard half)

`.dreamwork/run-mode` is one line from a closed set — `lackadaisical` / `hot` /
`assisted` — and `#443` says that single axis carries at least two independent
decisions: **how often the loop acts (pace)** and **whether it acts through
subagents (delegation)**. `assisted` is the only value that implies helpers, and
it also implies a pace, so *"lackadaisical but delegating"* is unexpressible.
Tonight's session was exactly that state, held in conversation rather than the
file (so it does not survive a restart). `#445` adds a third axis: **how much he
is asked (the four levels)**.

An IGC decides whether these are one control or several. Method: binary goals,
breakpoints not maximisation, decisive errors written out, never a score.

### Context

A single developer steers an autonomous dev loop through a machine-local,
gitignored file re-read every tick. He changes one thing at a time — pace, or
how much he is asked, or whether subagents are used — and each change must be
expressible without forcing the others. Tonight's session is the witness: low
pace **and** subagent delegation **and** a high asking level, none of which any
single `run-mode` value expressed.

### Goals (binary; each a breakpoint, not a maximum)

- **G1** — he can change how much he is asked **without** also changing how fast the loop runs.
- **G2** — he can change delegation posture (own-hands vs subagents) **without** it being implied by or coupled to pace. *(Tonight's session is direct evidence this coupling is real and costly: #443's filing reason.)*
- **G3** — the control lives in a tick-re-read, machine-local file (the only property that lets an on-disk change reach a running loop — `#426`/`#290`); it does not live in conversation.
- **G4** — preserves `run-mode`'s existing contract (one line, closed vocabulary, lint-checked, dashboard-settable behind the 10s arm, one events line on change). A grammar that widens `run-mode` carries a migration cost for existing installs; a sibling file carries none.

### Ideas

- **I1 — one combined enum.** A single value from a closed set bundles pace + asking + delegation into named modes (the four attention levels *are* the mode; pace is implicit).
- **I2 — two orthogonal axes: pace × asking.** Delegation is derived from one of the two.
- **I3 — three orthogonal axes: pace × asking × delegation.** Each independently settable.
- **I4 — asking as a per-task override on a global default.** A global asking default plus a per-task escalation/de-escalation.

### Matrix

| Idea | All | G1 | G2 | G3 | G4 |
|------|:---:|:--:|:--:|:--:|:--:|
| I1 · one combined enum | ✘ | ✘ | ✘ | ✔ | ✘ |
| I2 · two axes (pace × asking) | ✘ | ✔ | ✘ | ✔ | ✔ |
| I3 · three axes (pace × asking × delegation) | ✔ | ✔ | ✔ | ✔ | ✔ |
| I4 · per-task override on a global default | ✘ | ✔ | ✘ | ✔ | ✔ |

### Decisive errors (the ✘s)

- **I1 refuted on G1 and G2.** A combined enum forces the bundle: choosing a level moves pace and delegation with it. *"Near-automatic but slow"* and *"lackadaisical but delegating"* are both unexpressible — and the second is tonight's actual session (`#443`'s filing reason). His own words: *"we need ways to say, like, be lackadaisical, but also use sub-agents."* G4 also fails: it rewrites `run-mode`'s closed set (migration).
- **I2 refuted on G2.** Two axes cannot carry three independent decisions. If delegation is a function of pace, *"lackadaisical + subagents"* is unexpressible (the `#443` witness). If delegation is a function of asking, it still fails: asking (how much surfaces to him) and delegation (who does the work) are genuinely different — level 1 *"ask me everything"* says nothing about whether the coordinator works hands-on or via subagents, and level 4 *"full auto"* implies delegation without specifying pace. Decisive error: the two axes cannot express tonight's actual combination.
- **I4 refuted on G2** (as a *standalone* answer). A per-task asking override changes asking for one task without touching global pace — G1 passes — but pace and delegation remain global, so *"lackadaisical + subagents"* at the global level is still unexpressible. **I4 addresses granularity, not the pace×delegation conflation `#443` is about.** It is valuable *as an addition* (some tasks deserve more asking than the default) but it is not a substitute for the axis decision; it composes with I3 rather than rivaling it.

### Survivor

**I3 — three orthogonal axes: pace × asking × delegation.** Exactly one All-✔
idea. `#443`'s three current values decompose cleanly: `lackadaisical` → idle
pace; `hot` → hot pace + own-hands delegation; `assisted` → hot pace +
subagent delegation. The missing combination (idle pace + subagent delegation)
becomes expressible. Asking rides alongside as the third axis `#445` adds.

**Where the axes live is his call (Q2), not the IGC's.** Two honest shapes,
both preserving `run-mode`'s contract: (a) a sibling file —
`.dreamwork/attention-level` for asking, and splitting delegation out of
`run-mode` into its own field/file — adds axes without touching `run-mode`'s
closed set (no migration); (b) widening `run-mode` to a small multi-field file
carries a `Migration:` trailer. The brief forbids changing `run-mode`'s closed
set or `file-formats.md` before he rules, so this doc **proposes, does not
decide**.

## The four levels (what surfaces / is emitted / is logged / no-reply)

Two rules run through **all four** and are stated once here rather than repeated:
**(i) the escalation test is materiality against his goals, not difficulty** —
*"some choices where you have multiple good options … are not very material …
unless the user has specifically mentioned something"*; and **(ii) the IGC
evaluation happens at every level** — shown to him at 1, embedded in the emitted
doc at 2, logged unsurfaced at 3, applied silently at 4. "Stuck is a state you
earn" (research first — see L3) and the cooperation clause (see L4) likewise
apply everywhere; each level only changes how much *surfaces*.

### 1 · ask me everything

- **Surfaces:** every non-trivial design or architectural choice produces a review document **and he chooses** between the options. The IGC matrix is **always shown to him** (in the artifact). *"Probably a bit more than you've been asking me, but you do ask me a lot of stuff."*
- **Emitted:** a review artifact under `.dreamwork/review/` **plus** a `questions.md` `#ask`. The artifact carries the IGC.
- **Logged:** the `questions.md` entry is the durable record.
- **If he never responds:** the question stays open; work that depends on the choice is blocked and carries `blocked-on: human` (`#419`). He is the bottleneck **by design** at this level. When uncertain, ask about his **goals** rather than the immediate decision (see DREAMWORK.md wording below).

### 2 · keep me informed

- **Surfaces:** mostly automatic; each **material** choice emits **documentation rather than a question**. *"a review in the sense that it's for the human's review, but it's not asking them for a choice."* He put a number on it: **~10–20% of questions escalate** — a **soft estimate that steers, never a counter that gates** (his 01:17 "numbers steer and never measure" ruling, folded into DREAMWORK.md via `#421`).
- **Emitted:** a documentation artifact naming **what the choice was, why a choice was needed, the details, a brief note on the other options, and the IGC table** (embedded, not an ask). A `questions.md` ask is raised **only** where he is unsure, there are multiple good options, or there are no good options.
- **Logged:** the emitted document; plus a `questions.md` entry **only** for the ~10–20% that escalate.
- **If he never responds:** nothing parks on him — the document is not an ask, so work proceeds. Only the escalated minority blocks (and those behave like L1 for that one decision).

### 3 · near-automatic

- **Surfaces:** nothing, unless it is genuinely big or the loop is stuck. *"it's too much in the noise to actually surface."*
- **Emitted:** nothing to him routinely. The IGC evaluation **still happens** and is **logged to a journal folder** (ADR-shaped). One obviously-good option → just do it and log.
- **Logged:** an ADR-shaped journal (proposed home: `.dreamwork/docs/journal/` — confirm in Q3; `dreams/` is the wrong shape, being reflection not decision).
- **If he never responds:** nothing parks; proceed with everything possible. **Stuck is a state you earn:** before declaring a blocker, *use a subagent to research the question — has anyone solved it before, what are the options*. Only a genuinely-big or still-stuck-after-research item surfaces, and then like L1/L2.
- **The goals move (dictated here, generalised below):** at this level, if the dreamer is getting stuck, it should consider **asking about his goals** rather than the immediate decision — sharper goals resolve many future questions at once.

### 4 · full auto

- **Surfaces:** nothing routinely. *"tasked with figure it out."* A question reaches him **only** for a genuine unblocker he alone can resolve cheaply — *"do we have a domain?"* — raised **as early as possible**.
- **Emitted:** nothing to him unless it is that cheap unblocker.
- **Logged:** the journal, same as L3.
- **If he never responds:** **never blocked on a reply.** Every blocker is the loop's to solve; it keeps working on the unanswered question in the background and does **not** rabbit-hole while other work exists.
- **Cooperation clause (must not be lost):** *"you still want to cooperate with the user … but you never want to be blocked just because the user hasn't replied or because you don't have access to something."* And it must not contradict his goals — don't buy a domain for a project that already has one.

## Subagent target and policy (dictated shape)

The asking-axis configuration also carries subagent policy. His stated shape:
a **target number** of subagents **plus free text** for type, special rules,
when to use them and when not.

- **Target number:** integer. **`>= 1` valid; warn in the UI on `0`; hard-invalid below `0`.** Free text now; standardise later if ever.
- **Two consumers he named:** (a) sizing automatic task selection to the target; (b) **showing the subagent policy to the agent every time** — which makes it a **per-tick read like `run-mode`**, not a start-up read (`#426`).
- **Where it lives:** with the asking axis (same control). The number validates; the policy is prose the agent reads each tick.

## Proposed `DREAMWORK.md` wording (the ask-about-goals preference)

The coordinator owns `DREAMWORK.md`; this is the proposed wording, not an edit.
The dictation places the goals move at L3, but its reasoning generalises
(*"if you know about their goals, you can evaluate not just the current answer
… but … many other questions … uncertainty usually means the goals need to be
more specific"*), so it belongs in `DREAMWORK.md` as a durable preference that
applies at every asking level:

> **When uncertain, ask about goals, not just the immediate decision.**
> Uncertainty usually means the goals need to be more specific. Knowing his
> goals lets the loop evaluate not just the current choice but many future
> ones, so when stuck or torn, prefer a question that sharpens the goals over
> one that resolves only the immediate call.

## Open calls for him (filed by the coordinator)

One `questions.md` entry, declared form (`#421` B):

> **Sub-decisions:** `Q1`, `Q2`, `Q3`

- **Q1 — ratify three orthogonal axes (pace × asking × delegation)?** The IGC's survivor, refuting one-combined-enum and two-axes on tonight's session. Or collapse/combine differently.
- **Q2 — level names + where the asking axis lives.** Ratify his four names (*ask me everything / keep me informed / near-automatic / full auto*) as the closed set; and choose sibling file (no migration) vs widening `run-mode` (`Migration:` trailer).
- **Q3 — subagent target + policy shape.** Integer `>= 1` (warn on 0, hard-invalid below 0) + free text, per-tick read. Or amend.

The journal-folder home for L3/L4 logs is a minor shape call folded under Q2/Q3
rather than its own sub-decision.

## What this design does NOT do

- Builds no mechanism — no `watch.py`, no new tick-read file, no change to `.dreamwork/run-mode`'s closed set or `file-formats.md`.
- Does not touch `:35110`, the heartbeat, the monitors, or the loop.
- Does not edit `DREAMWORK.md` (proposes wording only).
