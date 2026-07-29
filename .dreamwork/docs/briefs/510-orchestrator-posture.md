# Brief — #510: an 'Orchestrator' option in Posture — IGC the integration options (design lane)

Lane-owns: `.dreamwork/docs/plans/orchestrator-posture.md`, `.dreamwork/docs/doc-map.md` (one row), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

You are a design lane on the dreamwork skill repo. You touch nothing outside the
three paths above. **Design only — no code, no `watch.py`, no lint, no posture
file change.** The implementation is a later split (a subagent does the WebUI
impl, the coordinator does the docs impl) and happens only after he rules.

## His words (2026-07-30 04:54, verbatim — the task)

> Please have a subagent do the webui impl while you do any of the docs impl:
> We should have an 'Orchestrator' option somewhere in the Posture. I'm not sure
> exactly how best to integrate that, it doesn't feel to strictly match anything
> we already have. Please /use-igcs to evaluate options and present them to me
> in a question so I can choose between them.

## What to deliver

1. **`.dreamwork/docs/plans/orchestrator-posture.md`** — a design doc in house
   style (read `.dreamwork/docs/plans/delivery-modes.md` and
   `.dreamwork/docs/plans/attention-modes.md` for the shape: status line,
   authority, what it builds on, the IGC, the settled shape, open calls with
   recs, pushback, summary). Contents, in order:

   a. **The referent, investigated not assumed.** What is an 'Orchestrator'
      option *of*? Read the repo before answering: `.dreamwork/posture` (four
      axes today: pace, asking, delegation, delivery — the contracts are in
      `file-formats.md`), `.dreamwork/docs/plans/attention-modes.md` (#445: how
      the three axes were carved out of run-mode, his amendments),
      `.dreamwork/docs/plans/delivery-modes.md` (#342: how the fourth axis
      landed — lint closed-set + file-formats in the same commit), the run-mode
      history (#290, `hierarchical` shown-but-disabled), and the multi-agent
      material (`plugins/ud-dreamwork-worktrees/`, `subagent-defaults`,
      `ccc-runner-routing.md` if present, c2c peers). The strongest reading
      known to the coordinator: *which harness/model/persona orchestrates the
      loop* (the main dreamer identity — e.g. this Claude session vs a Grok
      session vs a ccc runner) — but he may mean an orchestration *mode*
      (solo coordinator vs orchestrating a fleet, adjacent to `delegation`),
      or something else. Name the interpretations, say which you designed
      against and why; if two readings are genuinely live, that is a fork for
      him (with a rec), not a coin you flip silently.

   b. **A real IGC** (the vendored method: `igc-method.md` + `igc-concepts.md`
      at repo root — #447; goals are binary and each can refute alone; ideas
      are rivals, at most one survives). The integration options are the
      ideas, e.g.: a fifth posture axis; a value folded onto an existing axis
      (which?); a sibling file like run-mode was; a control only, with no
      file. His own sentence is the load-bearing context: *"it doesn't feel to
      strictly match anything we already have"* — the IGC must take that
      seriously rather than forcing the nearest existing axis.

   c. **Open calls for him, each with a rec, never picked for him** — the
      question the coordinator will paste into `questions.md`. Also draft the
      question entry text itself (title + accepted answers + per-option recs +
      an if-you-say-nothing line), marked clearly as a DRAFT for the
      coordinator — you do **not** edit `questions.md` (coordinator-owned).

2. **A doc-map row** in `.dreamwork/docs/doc-map.md` matching its existing
   format.

3. **One `## Pending` line appended to `.dreamwork/handoffs.md`** (append-only;
   `## Folded` stays above `## Pending`; never rewrite the file).

## Acceptance criteria (measurable)

- The doc exists, names its status as **design only, no code authorised**, and
  quotes his verbatim ask.
- The IGC has ≥3 goal rows and ≥3 idea columns, each refutation is structural
  (not "prefer"), and the survivor/fork conclusion follows from the matrix.
- Every fork the doc cannot settle appears in the open-calls section **with a
  rec**; there is no third state between settled and escalated.
- The draft question entry declares sub-decisions in the house format
  (`**Sub-decisions:** \`Q1\`, …`) if there is more than one call.
- Factual claims about posture mechanics (file location, axis set, lint
  closed-set, picker UI) are checked against the repo, and the doc says what
  was checked.
- `python3 lint.py` stays clean (doc-map has a contract).
- Committed with `git commit --only <paths>` on your lane branch; new files
  get `git add <file>` first.

## Report back

Model is recorded from the dispatch record, not your self-report. Report: the
interpretation you designed against (and the rejected readings), the IGC
headline (survivor or fork + one-line why), the open calls with recs, the
draft question text, and anything that pushed back on his framing.
