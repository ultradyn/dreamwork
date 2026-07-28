# Brief — the table on `421-question-options` is unreadable: two columns do not wrap

Repo: `ud-dreamwork`. **Work in the main checkout on master** — this is a single-artifact fix and no other lane
holds these files. **Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.
**Do not write `.dreamwork/handoffs.md`.**

## The defect — he reported it while reading the artifact, so this is urgent and real

His words, via the dashboard composer at 22:22 while on `/review?p=421-question-options.html`:

> *"get a subagent to fix the table on this review doc please, I can't read it (reduces and costs columns
> don't break text lines)"*

The **reduces** and **costs** columns do not wrap their text. He cannot read the table. He is reading it inside
an **iframe on the dashboard's `/review` route**, not as a bare file — so that is where it must be verified.

## What to do

1. **Look at it first.** You are the multimodal lane: render it and *see* the defect before changing anything.
   Serve the real target on an ephemeral port (`python3 watch.py --target . --port <free>`), load
   `/review?p=421-question-options.html`, and screenshot at **both** 1280x900 and 390x844. A fix for a
   rendering defect you have not seen is a guess.
2. **Fix the source, not the output.** Edit `.dreamwork/review/src/421-question-options.html`, then rebuild
   with `python3 review_artifact.py build`. **Never hand-edit the built file in `.dreamwork/review/`** — it is
   generated and your edit would be silently overwritten on the next build.
3. The likely cause is a `white-space: nowrap`, a missing `word-break`/`overflow-wrap`, a table layout that
   lets cells size to content, or a `min-width` on the cells. **Diagnose rather than shotgun**: name the
   declaration responsible in your report.
4. **Check the other artifacts.** If the cause is in the shared template
   (`review-artifact.template.html`) rather than this artifact's own markup, **stop and report** — touching the
   template re-stamps 23 artifacts and **12 cannot be rebuilt** because they have no `src/`. That is `#436`
   and it is not yours. A per-artifact fix is correct here even if it duplicates a rule.

## Done means all of these

1. **Both columns wrap** at 1280x900 and 390x844, verified **on the `/review` route in the iframe**, with
   screenshots taken before and after.
2. **The table still reads as a table** — wrapping it is not enough if the result is unreadable in a new way.
   This is a Web UI change and `CLAUDE.md`'s bar applies: **exceptional, not merely functional.** **Load the
   relevant design skills** rather than relying on frontend defaults, and follow `watch-design.md`, which is
   authoritative. On a 390px viewport a comparison table may need a different presentation, not just narrower
   cells — if so, say what you chose and why.
3. **The `#ask` is still above the fold.** Run `node dev/capture/above_fold.mjs .dreamwork/review/421-question-options.html`.
   As of tonight (`#432`) that tool **derives** the fold by measuring `#reviewframe` on the live route — so
   trust its number and print it. `421`'s ask was at `top=266` before this change; if your fix pushes it down,
   that is a regression and you must fix it, not report it as acceptable.
4. **`transitions.md` binds with no size floor.** Most likely you introduce no gesture — say so explicitly
   rather than leaving it unaddressed. If anything now appears, collapses or reflows, read that file and reuse
   the existing idiom.
5. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). **Do not run the
   full `just test`.**
6. **Do not touch :35110**, the heartbeat, the monitors, or the loop — use your own ephemeral port and stop it.
   Bind nothing in 39880–39899. `just deploy` now stops its server by port ownership (`#431`); do not
   reintroduce a pattern kill.

## Files

Yours: `.dreamwork/review/src/421-question-options.html` and its build output
`.dreamwork/review/421-question-options.html`.

**Not yours:** `review-artifact.template.html` (see above — report instead), `dev/capture/*` (**a live lane
holds `dom.mjs`, `confirmation.mjs`, `prominence.mjs`, `states.mjs`, `reviewsplit.mjs` for `#442`** — you may
*run* `above_fold.mjs`, not edit it), `watch.py` (**a live lane holds it for `#177`**), `lint.py`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md` — report exact lines instead.

## Practical

- `git commit --only .dreamwork/review/src/421-question-options.html .dreamwork/review/421-question-options.html -m 'fix(#421): the options table wraps so he can read it'`
  — **`--only`, never `git add -A`**: several agents are committing in this tree right now.
- **Commit before you finish.**
- **This should be quick.** He is blocked on reading it, so prefer a correct small fix over a redesign.
- **Push back with reasons if the diagnosis is wrong.** If the columns wrap fine and the real problem is
  something else (the iframe's width, a horizontal scroll, the font), **say what you actually measured** — he
  described a symptom, and the symptom is authoritative, not my guess at its cause.

## Report

Say: which model you are; the declaration responsible; what you changed and how it renders at both viewports
(describe the before/after you saw); the derived fold and the `#ask`'s top; whether the cause was per-artifact
or in the shared template; whether you introduced any gesture; and confirmation you did not hand-edit the
built file, run the full `just test`, or touch :35110.
