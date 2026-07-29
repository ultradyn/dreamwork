# Brief — lane-506pip: PIP buttons on links inside question cards (#506, his do-next 2026-07-30 03:54)

Lane-owns: the question-card body rendering in `watch.py` (the mdB link
pipeline and the card markup it feeds), `dev/capture/` guard(s) for it,
`watch-design.md` (contract rows, same commit), and its justfile
registration. Nothing else. NOTE: lane-burndown2 concurrently owns the
burndown panel in the same file — stay out of the burndown panel
entirely.

**Model:** grok-4.5 · **Isolation:** worktree (coordinator merge-gates).

## His words (verbatim)

"get a subagent to complete this: links in questions like \"Full
reasoning: [.dreamwork/docs/plans/cli-warning-layer.md](...) §IGC.\"
should have a PIP button so that I can easily pop out referenced docs."

## What exists (find it before designing)

- `pipBtn(url, label)` in `watch.py` (~line 2324) — the existing pop-out
  affordance ("pop out — floats while you navigate", `data-pipurl`,
  `data-piplabel`, `PIP_SVG`). Where it is already used is the idiom to
  reuse; author NO second pop-out gesture.
- The `mdB` markdown pipeline renders question-card bodies and turns
  backticked/markdown links into anchors (there is a closed-set rule:
  internal targets become links only when the destination is known —
  find it and respect it: a pip on a link that 404s is a false promise).
- The popout mechanics (how a pip floats, its reduced-motion behaviour)
  already exist — this task is ATTACHING the affordance, not building it.

## The work

1. Question-card bodies (open + answered cards on `/questions` and the
   dashboard, wherever mdB renders a question body) render their links to
   INTERNAL docs/files with the pip button attached beside the link —
   visually subordinate (the link is the content; the pip is chrome).
   External links: his ask is about referenced docs; decide and document
   whether external links get pips (default: no — a pip floats a local
   view) unless the existing pip idiom says otherwise.
2. Placement must not break the card's copy flow (selecting text across a
   pip must not be a hazard — see #505, selections are already fragile;
   the pip is chrome that must not swallow clicks meant for the link or
   for text selection).
3. Only known-internal destinations get pips (the closed set the link
   rule already computes) — derive eligibility from the same decision,
   never a second list.
4. `transitions.md` governs the pip's arrival if it appears on
   hover/focus vs. always-on — pick one, document it in
   `watch-design.md` same commit, and keep reduced-motion parity. Reuse
   an existing reveal idiom if one exists for card chrome.

## Constraints (hard)

- Red-first: a `dev/capture/` guard (registered in the justfile) that
  asserts a question card with a known-internal doc link renders a pip
  with the right `data-pipurl`, and that an unknown/non-internal "link"
  renders none. Assert the runtime preconditions (the fixture question
  genuinely contains both link kinds — derive, don't assume).
- **A green red-run is a finding, never a relief**: name the production
  line (e.g. the pip-injection call in the link renderer), remove it,
  watch the guard fail, restore byte-identical with `cp`.
- Headless screenshots (desktop ~1280, mobile ~390) of a card with pips
  in rest and (if hover-reveal) hover states, saved for coordinator
  inspection. The bar is EXCEPTIONAL quality — the pip must read as the
  page's existing chrome, not a new element family.
- `python3 -m pytest test_watch.py` green; `python3 lint.py` no new
  findings vs master baseline.
- Small commits, `git commit --only <paths>` (new files `git add` first).
  NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899; leave no
  fixture server running. The worktree lacks the live store — copy the
  main checkout's `.dreamwork/ledger.sqlite3` (+ watermark if any) into a
  /tmp scratch target and serve with `--target`.
- Do NOT deploy. Work on a branch in your worktree.

## Acceptance criteria (measurable)

1. Known-internal doc links in question bodies carry a working pip (the
   popout floats the referenced doc); unknown/external links carry none.
2. Guard red-proved with the production line named; registered; full
   guard run PASS.
3. Text selection across a card body with pips still works (verified —
   this is the #505 fragility; do not make it worse).
4. Screenshots attached; `watch-design.md` updated same commit.
5. `git diff master --stat` touches only owned paths.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
what renders pips now, the eligibility rule reused, the arrival-idiom
choice, the red-proof, screenshot paths, and any pushback.
