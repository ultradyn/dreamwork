# DREAMWORK.md — ud-dreamwork

## Goals

- Make "leave an agent dreaming on a project" a real workflow: the human
  can walk away and come back to steady, safe, well-chosen progress.
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
- Autonomy: commit each increment (the skill folder is its own git repo);
  push and deploy are not authorized.
- Routines: after structural edits, do a full coherence re-read of
  SKILL.md + initialization.md (this is the project's test suite).
  Periodically re-check this file against SKILL.md and recent decisions —
  goal alignment is maintenance, not a one-off. Groom
  `.dreamwork/questions.md` (fold answered entries). Keep any external
  index entries for this skill concise pointers — details live in the
  skill folder. Dogfood findings: fix immediately when small, file
  otherwise.
- watch.py webui: `watch-design.md` (skill root) is the authoritative
  styleguide — tokens, component idioms, the motion language (dream
  dissolve, mist filter, lifted-hero FLIP, reduced-motion + frame-continuity
  invariants), and copy voice. Read it before changing the page; keep it
  current in the same commit as the change.

## Plugins

- Load:
- Don't load: `ud-dreamwork-github` (2026-07-25) — this target has no
  GitHub remote/issues to watch; the plugin was *built* here (it ships
  from the sibling skill folder) but doesn't apply to dreaming on the
  skill itself. Revisit if the skill gains a forge presence.
