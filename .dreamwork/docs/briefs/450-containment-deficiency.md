# Brief — #450: write down the containment we do not have, and warn where it cannot exist

Repo: `ud-dreamwork`. **Work in the main checkout on master.** This is a docs increment; no worktree needed.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. Your **coordinator inbox is
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[deficiency]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/deficiency-inbox.md` so I can steer you.

Full report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

## The ruling this implements, verbatim

> *"don't do anything too expensive or time consuming. just plan for it and make sure the deficiency is noted.
> We are just going to be testing with our own trusted nodes first, so provided we can implement isolation
> layers later, then we can. Re claude code, we can have that kind of thing where we can't do tools or
> intercepts or whatever, we'll just have a warning next to it that it lacks certain protections. but i mean
> that's fine, if someone else is providing the api key then they can probably provide the harness, too."*
> — the human, 2026-07-29 00:50, answering `#288`'s contain-vs-detect question

**Read `#288` and `#450` in `.dreamwork/tasks.md`, plus
`.dreamwork/docs/plans/subagent-containment.md` (the design) and `dev/containment_falsify.py` (the working
prototype), before writing anything.**

## What this is, and what it explicitly is not

**Not** a mechanism. **Do not build isolation.** The `#288` lane already proved the namespace wall works (three
incident vectors held at ~22ms per contained process) and he ruled it stays **prototyped and unwired**. The
positive PID/health invariants are the defence. Your deliverable is *the written deficiency plus a warning
surface* — documentation this increment; the UI half waits for a lane that can hold `watch.py`.

**The framing that must survive into the doc**, because it is his and it is better than the loop's: *whoever
supplies the API key can supply the harness.* A protection that must live inside someone else's harness is
**not our seam** rather than our unbuilt work. So the doc should read as a boundary statement, **not as an
apology for missing work**. If your draft sounds like a TODO list, rewrite it.

## What to produce

**One doc.** Put it where a reader would find it — `.dreamwork/docs/` — and give it a `doc-map.md` row.
`doc-map.md` is contended (two lanes are live); on a conflict resolve as a union and verify the row against the
actual directory in both directions.

It must state:

1. **The per-harness capability table.** Which harnesses the loop dispatches into, and for each: can its tool
   calls be intercepted, can it be contained, and therefore **which protection is absent**. Derive this from
   what the repo actually does — the loop dispatches `ccc @grok` / `ccc @glm52` subagents and harness
   subagents; do not invent harnesses we do not use. Where you cannot determine a capability, write **unknown**
   rather than guessing; an invented ✔ here is worse than a gap.
2. **The trusted-nodes precondition, stated where someone would act on it.** *"We are just going to be testing
   with our own trusted nodes first"* is a live operating condition, not background. Say plainly what is safe
   today, and what specifically changes the day an untrusted node runs a lane.
3. **What keeps later isolation possible** — the one obligation his ruling creates. Name the seams that must
   not be closed off (the prototype, the invariants, the dispatch point) so a future lane can wire the wall
   without redesigning.
4. **What the warning next to a harness should say**, as *copy*, not as an implementation. One or two sentences
   a reader can act on, in `watch-design.md`'s voice (read its copy section for the register — but **do not
   edit `watch-design.md`**; a live lane holds it. Quote the copy in your doc and note where it belongs).

## Done means

1. The doc exists with all four sections and a `doc-map.md` row.
2. **No mechanism built**, no isolation wired, no new dependency, nothing on the host changed.
3. `python3 lint.py --target .` clean — you changed nothing else it checks, so a new failure means you touched
   more than you meant to.
4. Do not start a server, bind a port, or touch **:35110**. Do not run `just test`. Do not `pkill` anything —
   never `pkill -f`.
5. Report the ledger lines you would add for the **UI half** as a successor task, since it needs `watch.py`.

## Files

**Yours:** your new doc under `.dreamwork/docs/`, and `.dreamwork/docs/doc-map.md`.

**Not yours:** `watch.py`, `transitions.md`, `watch-design.md`, `justfile`, `test_watch.py`, `dev/capture/*`
(the `mistperf` lane), `review_artifact.py`, `review-artifact.template.html`, `.dreamwork/review/**` (the
`context` lane), `SKILL.md`, `lint.py`, `dev/ledger.py`, `dreamhub.py`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `dev/containment_falsify.py` (read it, do not change it).

## Practical

- `git add <newdoc>` then `git commit --only <newdoc> .dreamwork/docs/doc-map.md -m 'docs(#450): …'` —
  **`--only`, never `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their
  staged work into yours.
- **Commit before you finish.** **~15 minutes** — this is a page, not a report.
- Choosing between rival framings? Use **IGC** (`igc-method.md` in the repo root, vendored tonight as `#447`):
  binary goals, decisive errors written out, no scoring.
- **Push back with reasons if the doc is the wrong artifact** — e.g. if this belongs in
  `subagent-containment.md` as a section rather than as a new file. That is a legitimate answer; argue it
  rather than doing both.

## Report

Say: which model you are; the capability table as you determined it, with anything marked **unknown** and why;
the warning copy you propose and where it belongs; the successor-task lines for the UI half; and confirmation
you built no mechanism, changed nothing on the host, did not touch :35110, and did not run `just test`.
