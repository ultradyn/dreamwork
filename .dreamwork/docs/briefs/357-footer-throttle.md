# Brief — lane-357throttle: record the Q5 ruling and settle the footer throttle (#357)

Lane-owns: `.dreamwork/docs/plans/cli-warning-layer.md` and NOTHING else.
Doc-only lane: no code, no `dev/ledger.py`, no `lint.py`, no tests, no
artifacts under `.dreamwork/review/`.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## What happened (your input)

Q5 (the one open call in the design's §"Open calls for him — one") was
answered by the human at 2026-07-30 03:11:

1. **rec taken — the footer prints on EVERY `dev/ledger.py` verb** (the
   literal reading of his word "tacked on"; the fork is closed).
2. **An amendment with reasoning that is his**: warnings should surface
   *early* in the loop so the dreamworker can plan them in. He sketched a
   throttle for the read verbs: print after every state-change verb always;
   for other verbs suppress ~70–80% of prints, but only while ALL of:
   the warning is unchanged AND time since last warning < heartbeat × 0.7
   AND warnings skipped since last print < 4 (every 5th call prints
   regardless). His words: "Something like that."
3. **His instruction**: evaluate the options with `/use-igcs` and surface
   any issues in a new question.

## The work

1. **Read first**: `.dreamwork/docs/plans/cli-warning-layer.md` (whole
   doc), `igc-method.md` + `igc-concepts.md` (repo root — the vendored IGC
   method), and the quiet rules section especially — the throttle must not
   violate them.
2. **Record the ruling** in the design doc: the §"Open calls for him" is
   settled — footer on every verb; update the contract section so the doc
   reads as settled, not asked. Keep the decision visible (what was asked,
   what he ruled, when) in the doc's own voice.
3. **Run a real IGC** (the vendored method: goals, ideas, grid, decisive
   criticisms) on how the every-verb footer should behave on READ verbs,
   with at least these ideas on the table:
   - **I1 plain every-verb** — no throttle; the quiet rules are the whole
     damper (zero counts absent; clean tree prints nothing extra).
   - **I2 his throttle sketch** as stated (suppress 70–80% on read verbs
     under the three conditions; every 5th prints regardless).
   - **I3 throttle variant you derive** if the IGC exposes a cleaner shape
     of the same intent (e.g. state carried where? the throttle needs
     *memory* — time since last warning, skip count — and `dev/ledger.py`
     is a stateless verb process; say where that memory lives and what it
     costs, or the idea dies on that fact).
   The grid must score against HIS stated goal (surface early so the
   dreamworker can plan them in) plus the design's own quiet rules.
4. **Settle or escalate**: if one idea is decisively better, write it into
   the design as the throttle contract (exact conditions, exact state
   source, exact behaviour on a clean tree). If the choice is genuinely
   his — or the IGC finds a real problem with all options (statefulness,
   complexity, a quiet-rules violation) — DO NOT pick; enumerate the
   issues precisely in your report so the coordinator can surface them as
   a new question (that is his explicit instruction).
5. **Doc-map**: if the doc's title/scope line changes, check
   `.dreamwork/docs/doc-map.md` for a stale row and fix it in the same
   commit.

## Constraints (hard)

- Small commits, `git commit --only <paths>` (new files `git add` first).
  NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899.
- The doc is a DESIGN doc: it authorises nothing by existing. Do not
  implement the throttle; do not touch `dev/ledger.py`.
- If the design doc and this brief disagree, PUSH BACK in the report.

## Acceptance criteria (measurable)

1. The doc records the Q5 ruling verbatim-summarised (every verb; his
   early-surfacing reasoning) where §"Open calls for him" was.
2. An IGC section exists with goals, ≥3 ideas, a comparison grid, and the
   decisive criticisms named — not a prose verdict wearing the label.
3. The read-verb behaviour is either settled as an exact contract
   (conditions + state source + clean-tree behaviour) or escalated with
   the issues enumerated for a question — one of the two, explicitly.
4. The throttle design, if settled, names where its memory lives and
   proves the quiet rules still hold on a clean tree.
5. `git diff master --stat` touches only `.dreamwork/docs/plans/cli-warning-layer.md`
   (plus `doc-map.md` if (5) above applied).

## Hand-off obligation (#398)

Your final report is data for the coordinator, who writes
`.dreamwork/handoffs.md` from it: the ruling as recorded, the IGC outcome
(settled contract OR escalated issues), and any pushback.
