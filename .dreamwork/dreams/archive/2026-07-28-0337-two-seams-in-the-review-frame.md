# Two seams in the review artifact frame, both load-bearing for the next edit

dreamer on the #347/#372/#364 frame batch. Three tasks landed in one commit, and
two things worth keeping are not about the tasks themselves but about what the
frame resists when you change it.

## 1. The template and tasks-page.html are pinned selector-for-selector

`test_template_rules_match_the_reference_rule_for_rule` holds every selector the
template and `.dreamwork/review/tasks-page.html` SHARE to identical declarations,
and `DECLARATION_DIVERGENCES` (the one documented door for a deliberate
difference) is empty. So a CSS fix to a shared selector in
`review-artifact.template.html` — here, `white-space:nowrap` on `.topactions a`
and `min-width:max-content` on `table` — **fails the fidelity test unless the
identical edit is made to tasks-page.html too**. tasks-page.html is the hand-rolled
artifact the template was cut from (the human's named "good one"); it is
untemplated and is not rebuilt, so the coupling is manual and invisible until the
test reddens.

The brief's ownership list named `review-artifact.template.html` and "the built
`.dreamwork/review/*.html`" but not tasks-page.html (it is untemplated, so "built"
is arguable), and not `test_review_artifact.py`. Editing tasks-page.html identically
was the only path that kept `just test` green without touching a file outside the
ownership list. It is the right call — the reference should carry the fix too — but
the next person editing a shared template selector will hit the same wall and
should not have to rediscover which file holds the other half.

## 2. `getClientRects().length === 1` on an inline-flex element is hollow

This is in the #347 ledger already, but it is sharp enough and cost enough time to
earn a lessons.md line of its own. `.topactions a` is `display:inline-flex`, so its
box is **one rect** no matter how the text inside it wraps. The first instrument
anyone reaches for — "does the element's own box split into two?" — reported `1`
for four labels that were visibly broken ("measur/ed"). The instrument that
discriminates is a `Range` over each **word**: a word split mid-character spans two
lines and so produces two rects, while the box it sits in stays one. (Skip words
with `-` or `/`; breaking there is correct typography.)

This is a distinct member of the "instrument bugs outnumber feature bugs" family
already in lessons.md: the earlier entries are about `getBoundingClientRect`
including transforms and Range rects being per inline box. This one is the inverse
— the *container* reports stable geometry while its *contents* misbehave, which is
exactly the case where an end-state or box-level check passes over the defect.

## What landed

`review-artifact.template.html` + `tasks-page.html` carry the identical fix (nowrap
+ ellipsis on `.topactions a`; `min-width:max-content` on `table`); the four built
artifacts rebuilt; `dev/capture/artifactwrap.mjs` guards both with the word-Range
instrument at three widths; and `.dreamwork/review/src/task-store-schema.html` was
synced to the 01:23 ruling. Commit `9424468`.
