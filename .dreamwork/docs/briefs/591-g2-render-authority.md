# Brief — #591: does claude-design compatibility cost us the single render authority?

Lane-owns: `.dreamwork/review/src/505-g2-render-authority.html`, `.dreamwork/review/505-g2-render-authority.html`, `.dreamwork/docs/plans/render-architecture.md`, `.dreamwork/docs/plans/g2-question-draft.md`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

Worktree: `/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-591g2` (branch `lane-591g2`, from `2509ccda`)
Your inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-591g2/inbox.md`
Coordinator inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`

**You are not implementing anything.** You are producing the artifact that lets Max rule on one question. Write no production code.

## Chain

- **This task:** get `#505` G2 ruled before the bundle step can decide it by accident.
- **Session goal:** his 2026-07-31 focus is the modular `watch.py` + built frontend; this is the one open call on its critical path.
- **DREAMWORK.md goal:** dreamhub replaces `watch.py` for daily use, by *extraction* not reimplementation — because *"two renderers only agree on the day they are written"* (`dreamhub-design.md:197`).

## Why this is live now, precisely

`.dreamwork/docs/plans/render-architecture.md` already states the goals and already ran the IGC. Read lines ~110-200 first. Its verdict:

> **I3 (full vdom — React/preact/uhtml) ✘ on G2 and G4.**

Two things have changed since.

**1. G4 has expired.** G4 was *"single-file deploy unchanged (no build step)"*, and the doc itself hedged it: *"this goal prices it as decisive unless he rules otherwise (open call Q2)."* **He ruled otherwise on 2026-07-30** (`#505` Q2, commit `0f97df03`): *"we don't have a no-build single-file constraint. We had a python stdlib constraint, but otherwise building the webui bundle and breaking up watch.py into modules are good and reasonable things."* So half of I3's refutation is void. **Your first job is to say so in the plan doc** — an IGC carrying a refutation on a retired goal is actively misleading, and this one has been misleading readers for a day.

**2. A goal has appeared that the IGC never had.** His 2026-07-31 focus makes the extracted frontend *"compatible with claude design"* a stated goal. That is a new binary column, and **I4 — the survivor, keyed reconciliation over the string builders — may fail it.** If it does, the matrix has zero survivors, and the repo's own rule is explicit: *zero survivors means fix the framing, not pick a refuted option.*

So the question is no longer "should we adopt a vdom". It is: **when a new goal refutes the incumbent survivor and an expired goal un-refutes its rival, which goal actually gives?**

## What you must establish, not assume

**What claude.ai/design actually consumes.** Do not guess, and do not take my summary as fact — verify it. What I believe, for you to check: it ingests a *compiled component bundle* exposing real components on a global, plus per-component `.d.ts` prop types and usage docs, and it builds designs by composing those actual components. Its own stated core principle is *"ship what the customer already built — the bundle is their compiled `dist/`, never a reimplementation."* If that is right, two things follow and both matter: the design tool needs genuinely renderable components with typed props (so a string-builder surface may not satisfy it), **and** its own philosophy is anti-second-truth, which is a point of agreement with G2, not conflict. That tension is the most interesting thing in this task — chase it.

**Whether a derived surface is possible.** The option the original IGC never considered, because the goal did not exist: keep the string builders as the one authority and *derive* the component surface from them — generated, not hand-maintained. Is that real or is it wishful? A derived component that is generated from the single authority is not a second truth by the rule's own logic (the rule refuses two things *maintained* in parallel). Establish whether the current `client/components.js` shape can support this, and what it would cost. If it cannot, say so plainly — a refuted option honestly refuted is worth more than a survivor you had to squint at.

**What the extraction actually gave us.** `#397` landed: `client/` now holds eight real files (`style.css`, `app_body.html`, `components.js`, `views.js`, `favicon.js`, `router.js`, `command.js`, `shader.js`), read at import by `_read_client()`. Read `components.js` in particular — it is the closest thing to a component library that exists today, and how close it is materially changes the answer.

## The deliverable

**1. Update `render-architecture.md`** to record that G4 is retired (cite his ruling and its date/sha) and that its I3 row's `✘ G4` no longer stands. Do not re-run the whole IGC in the plan doc — the artifact is where the new decision lives.

**2. A review artifact.** Write only the words, as `.dreamwork/review/src/505-g2-render-authority.html`, then build it:

```
python3 /home/xertrov/.claude-p/skills/ud-dreamwork/review_artifact.py build .dreamwork/review/src/505-g2-render-authority.html
```

**Do not hand-roll the page.** `review-artifact.template.html` owns the frame, palette and footer; you own the content. Hand-rolling is what produced five font stacks across twelve artifacts. Self-contained, offline-clean, inline everything.

It must carry an **IGC matrix**: ideas down the side, goals across the top, ✔/✘/? per cell, an **All** column, **the decisive error written under each ✘**, and **no score column**. A choice he can only score is a choice he cannot make. Scale it honestly — this is a real fork, so lay the table out.

Candidate ideas to start from, not to be limited by: keep string builders + keyed reconcile (today's I4/I5); derive a component surface from the string builders; migrate wholly to a component tree as the *one* authority; run both (what G2 refuses — include it so the refutation is visible rather than assumed); decline claude-design compatibility. **Find the ones I have not listed** — that is the part of this a fresh reading is for.

Goals across the top should include at minimum: one render authority (G2); claude-design consumable; gestures preserved (G1 — `transitions.md` is a hard contract and a path that turns a travel into a teleport is refuted); server stays stdlib-Python-only (this constraint did **not** expire); incremental and reversible; the dashboard keeps working throughout.

**3. A draft question**, as `.dreamwork/docs/plans/g2-question-draft.md` — the text I will place into `questions.md` myself, since the coordinator is that file's single writer. Follow the house style: a `rec` he can accept in one word, the alternatives with their costs, and an explicit **"If you say nothing:"** line. His standing rule applies — *a decision with one clearly superior answer is not an ask*. If your analysis lands on a clear winner, say so and make the ask small; if it genuinely forks, that is what earns his attention.

## Standards

State what you verified versus what you inferred, every time. Where a claim rests on a file, cite it by line. If you conclude the question is less open than it looks, say that — the honest outcome of an IGC can be "this did not need asking", and that is a better result than a manufactured fork.

## Delivery obligations

1. `git commit --only <paths>` on your branch; `git add` new files first.
2. ONE `## Pending` line in `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md` naming `#591` and your sha, **committed on `master` in the main checkout**.
3. Report to the coordinator inbox, every line prefixed `[lane-591g2] `, handshake first, `DONE` last — including your recommendation and your confidence in it.
4. **End with a `Dogfood report` section** — friction with the loop itself. "Nothing to report" is valid **if stated**; an omitted section reads as no friction, which is not the same as none found.
5. **No `attn`.** No merge, push or deploy. Do not stop the heartbeat, the watch server on :35110, or any loop machinery.
