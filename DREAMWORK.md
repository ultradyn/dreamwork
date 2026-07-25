---
dreamwork-version: 5853e1789929
---
# DREAMWORK.md — ud-dreamwork

## Goals

- Make "leave an agent dreaming on a project" a real workflow: the human
  can walk away and come back to steady, safe, well-chosen progress.
  - The loop's memory survives anything that ends a session — restart,
    compaction, a fresh agent. What it knew, it still knows.
  - The dashboard is how you check on it and steer it without a chat
    turn, and it is worth looking at.
  - **Nothing fails quietly** (folded 2026-07-25 from what the loop
    learned, not from a stated ask — say if you disagree). "Safe" turns
    out to mean legible: on one day this loop found a questions.md that
    parsed to nothing and rendered as "nothing to answer", a command
    channel nothing read, a refused write that reported success, an
    enter animation that had never once run under a matrix documenting
    it, and several checks that passed on their own bug. Every one of
    them looked fine. So the loop prefers a loud wrong state to a quiet
    one, and prefers removing the opportunity for a mistake over
    restating the rule against it.
  - **One human, several dreaming agents** (approved 2026-07-25, #96):
    the workflow scales past one session — a hub aggregates them, and
    managing an agent's lifecycle (spawning, steering, compacting,
    retiring) becomes something the system does deliberately rather
    than something the human improvises per client.
- The loop stays cheap (cache-warm heartbeat), never gets stuck or bored,
  and is always steerable in a few words (`do now` / `do next` /
  `add idea`).
- The loop gets on the human's wavelength over time: goals and
  preferences accrete here so questions get answered once and asking
  trends down, not up.

## Philosophy

- Small verified increments are the error-catching mechanism.
- Ideas are never lost.
- Know what the human wants so we make what the human needs.
- Reflection over momentum.
- The loop should feel like a colleague pottering productively — not
  runaway automation: no make-work, no ungated experiments, no pivots;
  scope expansion defers to the human.
- Unclear is a goals problem: every needed conversation with the human is
  also a moment to sharpen this file; contradictions between this file
  and what the human says now get surfaced, and the human resolves them.
- Durable over ephemeral: asks, decisions, and memory live in files
  (questions.md, dreams, docs) — never only in chat.
- The skill itself stays lean: principle-level lines over procedure
  bloat; reference files over SKILL.md growth.

## Preferences & Routines

- Cadence & comms: brief updates; `attn` (TTS) only for blockers,
  questions, and notable milestones.
- Autonomy: commit each increment (the skill folder is its own git repo).
  Push at session wrap and whenever asked — not per increment
  (2026-07-25). Deploy is not authorized.
- Detail is ranked, never withheld (2026-07-25, his words): "in general
  we always want to present the user with more details if there are more
  details and users might want them." A thing that exists must be
  reachable — the page's job is to order it, not to decide he cannot
  have it. This is the same commitment the loop reached from the code's
  side as "nothing is dropped, only demoted" (#130), and it makes a fold
  a promise: what is inside is still there, and the summary says what.
- Subagent lifecycle (2026-07-25): **prefer fresh subagents; reuse an
  existing one only if it stopped less than ~4 minutes ago.** Retire
  idle dreamers rather than leaving them parked. A dreamer here reached
  ~600k tokens because the coordinator accepted its own "I have room"
  three times — the incumbent is the party least able to judge its own
  context cost, so the call is the coordinator's.
- Routines: after structural edits, do a full coherence re-read of
  SKILL.md + initialization.md (this is the project's test suite).
  Periodically re-check this file against SKILL.md and recent decisions —
  goal alignment is maintenance, not a one-off. Groom
  `.dreamwork/questions.md` (fold answered entries). Keep any external
  index entries for this skill concise pointers — details live in the
  skill folder. Dogfood findings: fix immediately when small, file
  otherwise.
- Common tasks live in the `justfile`: `just test` (the verification
  every increment runs — there is no CI), `just watch`, and
  `just audit-styleguide`, which fails if any commit changed the page
  without updating the styleguide. The rule was already recorded; now it
  is checkable rather than remembered.
- watch.py webui: `watch-design.md` (skill root) is the authoritative
  styleguide — tokens, component idioms, and copy voice — and
  **`transitions.md` is the single source for how the page moves**
  (2026-07-25, his ask): every transition obeys it, appear/disappear/
  expand/collapse/state/movement alike, and the gist is that they are
  atmospherically suitable, like the transitions between pages. Read both
  before changing the page; keep them current in the same commit as the
  change. `CLAUDE.md` at the skill root carries the rule for anyone
  working on this repo.

## Plugins

- Load: `ud-dreamwork-github` (2026-07-25) — the skill gained a forge
  presence (`git@github.com:ultradyn/dreamwork.git`, private), which was
  the recorded condition for revisiting. Its settings:
  - Watch: all open issues and PRs (the repo has neither yet).
  - Authority lines: none granted, so read-only — watch, capture, and
    progress locally; never touch the remote. Grant `comment`, `push`,
    `open-pr`, or `merge` by naming them here.
  - Auto-progress: on. gh-sourced items join normal selection like any
    other task; nothing about them is a private queue.
- Don't load:
