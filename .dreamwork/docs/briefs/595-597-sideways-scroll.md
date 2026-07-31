# Brief — #595 + #597: the page moves sideways when the styleguide says it never does

Lane-owns: `client/style.css`, `client/router.js`, `client/components.js`, `dev/capture/`, `watch-design.md`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

> **Widened 2026-07-31 16:21** at the lane's own ask: D1's `.fdir`-idiom fix and D2's `#506` tail-unit
> fix both have their build sites in `client/router.js` (`crumbsFor`) and `client/components.js`
> (`linkify`), and the original list would have forced a CSS-only fix that may not be the right one.
> No other live lane holds either file — `lane-592lint` owns `lint.py`/`test_lint.py` only. Take the
> correct fix at its real site rather than a CSS approximation of it; if a build-site fix and a CSS
> fix are genuinely equivalent, say which you took and why.

Worktree: `/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-595scroll` (branch `lane-595scroll`, from `d44070cc`)
Your inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-595scroll/inbox.md`
Coordinator inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`

## Chain

- **This task:** the page never scrolls sideways, and never jumps sideways — both as `watch-design.md` already claims.
- **Session goal:** close the two P1 defects a visual audit found where the page contradicts its own styleguide.
- **DREAMWORK.md goal:** the dashboard *"is worth looking at"* — and under his 2026-07-31 focus it is also the surface being extracted into a real frontend, so its layout contracts are what that extraction has to keep true.

## Source

Read `.dreamwork/docs/visual-audit-2026-07-31.md`, sections **D1**, **D2**, **D5** and **O7**, before starting — it has the measurements, the line citations and the screenshot names. Screenshots are at `~/served-html/ud-dreamwork-visual-audit-2026-07-31/` (browsable at `http://xsm:10435/ud-dreamwork-visual-audit-2026-07-31/`).

## #595 — sideways scroll at 390px

- `/` overflows by **28px**: the skill-version crumb is an arbitrary-length *filename* inside a `white-space: nowrap` `.crumb`. `style.css:65`'s own comment names `.fdir` as the **one** exception for unbounded text, and this crumb never got it.
- `/file?p=DREAMWORK.md` overflows by **32px**: a long inline `.mdfile` path plus its `#506` pip, `style.css:1823`, also `nowrap`.
- `/questions` and `/answers` escape **only by luck** — their long paths sit inside *closed* `<details>`. Do not treat them as passing; treat them as the next regression.

**Start with the guard, not the CSS.** `watch-design.md` states the page never scrolls sideways *"(asserted at desktop and at 390px)"*. A manual audit falsified that. So either the assertion does not exist, or it exists and does not catch this — and that is a more important finding than the two CSS fixes, because it is why nobody saw this. Find what asserts it, say plainly what it actually measures, and fix the gap. If the guard turns out not to exist at all, say so — the styleguide sentence is then the defect too.

## #597 — the 5px sideways snap

Every route change between a scrolling and a non-scrolling route shifts the whole page 5px. The audit traced 40 frames of `/` → `/answers`: `#htitle` visits exactly two x values (436.2, 441.2) while scrollbar width goes 10 → 0.

This is a **snap among drifts** on the page whose chrome was hoisted out of `#view` *precisely because* route changes "read as the elements jump around" — so it defeats the reason that hoist exists. `transitions.md` governs; read it (`python3 /home/xertrov/.claude-p/skills/ud-dreamwork/dev/lessons_index.py --act transition-motion` prints the lessons that bind here).

The proposed fix is one line — `html { scrollbar-gutter: stable }` — which also fixes **O7** (`#dreambg` is `100vw`, so ~10px of the shader field currently sits under the scrollbar). Verify that claim rather than trusting it: check it does not introduce a permanent gutter at 390px where there is no scrollbar to reserve, and check the shader field still covers.

**This needs a guard**, and it is the interesting part of the task: 5px is exactly the size nobody notices deliberately and everybody feels. Measure a chrome element's `x` across a route change and assert it does not move. Born-red.

## Verification

- Targeted `pytest` and `python3 /home/xertrov/.claude-p/skills/ud-dreamwork/lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-595scroll` — **absolute `--target` always**; bash cwd resets between calls here and a previous lane silently linted the wrong directory and got no output, which it nearly read as clean.
- **Your own guard, solo, only** — `DREAMWORK_GUARDS=<name> DREAMWORK_HUB_GUARDS= just guards <port>` after checking 39890-39899 is free. **Never `just test`, never the full suite**: the coordinator owns those and a gate run may be in flight on those ports. Check before you bind.
- **Red-proof every new assertion** on a named production line: `cp` backup first, inject, watch the discriminating failure, restore by `cp` (**never `git checkout`**), `cmp` byte-identical. A green red-run is a finding — report it, do not move on.
- Beware the audit's own trap, which will bite you if you write rect maths: **closed `<details>` still report non-zero `getBoundingClientRect()`**, so a naive overflow sweep reported ~150-300 false positives on this page. Filter on `Element.checkVisibility()` and confirm with a real `window.scrollTo(9999, 0)`.

## Styleguide obligation

`watch-design.md` is single-source and documents a change **in the same commit that makes it**. If you change what the layout guarantees, or discover its "asserted at 390px" claim was not true, the file moves with you.

## Delivery obligations

1. `git commit --only <paths>` on your branch; `git add` any new file first.
2. ONE `## Pending` line in `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md` naming `#595`/`#597` and your shas, **committed on `master` in the main checkout**.
3. Report to the coordinator inbox, every line prefixed `[lane-595scroll] `, handshake first, `DONE` report last.
4. **End with a `Dogfood report` section** — friction with the loop itself. "Nothing to report" is valid **if stated**; an omitted section reads as no friction, which is not the same as none found.
5. **No `attn`.** No merge, push or deploy. Do not stop the heartbeat, the watch server on :35110, or any loop machinery.
