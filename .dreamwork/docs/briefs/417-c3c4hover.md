# Brief — #417: c3 + c4 with a per-column hover, because he ruled and he answered the objection

Repo: `ud-dreamwork`. Worktree: **`.worktrees/burndown`**, branch **`wt/burndown`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/burndown.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[burndown]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/burndown-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the
lines you want added. **Commit each increment as it lands.**

## He ruled. Read the ruling before the options, because it overrode the recommendation.

Read `#417` in `.dreamwork/tasks.md` and its (now Answered) entry in `.dreamwork/questions.md`. The artifact
`.dreamwork/review/417-burndown-commits.html` has real renders of every option including a five-up comparison.

**His answer, 2026-07-29 06:23, verbatim:**

> *"I think c3 + c4. I like the chunkyness of the line. granted it's not that intuitively connected to the
> number of tasks (which I think is what the line is, right?) but yeah. it shows density of action still which
> is kind of nice. with regards to: 'Encodes a third fact (commits) into the level line's cap weight (2–6px).
> The mapping is learned, not obvious.' in the review doc: we should show exact numbers for each column on
> hover of that column. then it's very easy to learn."*

So: **`c3` (commits in the level line's cap weight, 2–6px) AND `c4` (the copy figure line) AND a per-column
hover showing exact numbers.** The rec was `c4` alone and the coordinator's visual verdict **rejected `c3`** as
an unlearnable mapping — he overruled both, and his hover is a better answer than the rejection was, because it
makes the mapping learnable instead of arguing about it.

**Three things that are settled and are not yours to revisit:** `c3` is in, `c4` is in, and the hover exists.
If you believe one of them is wrong, say so in the report and **build it anyway** — he has seen the renders.

## The details that decide whether this is good

1. **The hover shows ALL THREE facts, not just commits.** He asked *"which I think is what the line is,
   right?"* — the answer is nearly: the level line is **how many were OPEN** at that period, not completions.
   The panel runs **two tracks over one set of columns**: the level (open count) above, the flow below
   (arrivals up, completions down about a hairline). `c3` makes the level line carry a **second** meaning, and
   that ambiguity is the entire reason the hover matters. A hover showing only commits would leave the thing he
   was unsure about still unexplained.
2. **`c4`'s copy must not ellipsise. That is his condition, not a preference.** As rendered it truncated to
   *"16 median ledger commits per period · 59 peak · 3 periods with n…"*, and the verdict was that an ellipsis
   reads as broken rather than terse. **Shorten the copy so it fits.** The head is deliberately one
   ellipsised line (`#151`'s mechanism) because a head that wraps changes the panel's height.
3. **EVERY HEIGHT IN `.bd` IS FIXED, and that is load-bearing** (`watch.py` ~729). The panel is a constant so
   fresh data changes bars and never moves the page — which is what lets the bars animate on a data change
   without dragging four panels with them. So **neither the hover affordance nor the copy line may change the
   panel's height**, and `c4`'s measured `+19px` must be a deliberate one-time allowance in the fixed layout,
   not a growth. Say how you kept it constant.
4. **The weight mapping must be honest at the edges.** 2–6px across the real range: say what happens at zero
   commits and at the peak, and make sure a period with no commits is distinguishable from a period with one
   rather than both rendering as the floor.

## Web UI bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality.* **Load the relevant design
skills** and read **`watch-design.md`** and **`transitions.md`** before designing.

**A hover readout is an arrival** — it appears and departs, and `transitions.md` has **no size floor**. Its
opening section is *how to check*, and the reason is specific: an end-state assertion cannot fail on a motion
bug, and neither can "did it move" — **sample intermediate frames**. Reduced-motion parity is part of the work,
not a follow-up. **Reuse an existing idiom** rather than authoring a second one; this panel and its neighbours
already have gestures for appearing detail.

Also: the accent is deliberately **not** spent in this panel, because nothing here is waiting on him
(`watch.py` ~732). Do not introduce it for the hover.

## Verification

- **Extend `dev/capture/burndown.mjs`** rather than adding a rival guard — it already asserts the panel's
  constant-height premise, which your change is most likely to break.
- **Own-server guards take `await freePort()` and IGNORE `argv[3]`.** `#461` did the opposite and silently
  stopped eight guards executing for three and a half hours (`#471`, fixed `80ac4b5`). **Do not register
  anything in `justfile`** — registration is centralised at merge, and another lane owns that file right now.
  Report the guard name if you add one.
- **The constant-height check is the one that matters and it must be derived:** capture the panel's height
  before and after a data change **at runtime** and assert equality; do not compare against a literal pixel
  value tuned to today's fixture, which is a check with an expiry date nobody can see.
- **The hover check must assert the NUMBERS, not that a tooltip appeared.** Derive the expected figures from
  the served data at runtime and assert the readout matches — a tooltip showing the wrong column's numbers
  passes any "is it visible" test, and that is exactly the failure his hover exists to prevent.
- **Sample the transition**, do not assert its end state.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — and if a red comes back green, **suspect
  your injection before the test**: confirm you edited the line the check names.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** A full `just test` is in flight in the MAIN checkout from ~07:19 and
  holds **39899**; run your guard with an explicit different port (`just guards 39893`, or
  `node dev/capture/burndown.mjs <out> <port>` — check `ss -ltnp` first) and do not wait on it. Bind nothing in 39880–39889; kill by exact pid; `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it. Never `pkill -f`.
- **The artifact is now decided, so do not rebuild it** — but if the built page still presents `c3` as
  rejected, that is stale against his ruling; **report it** rather than editing (it is not yours).
- Trailer: `Feature:`.

## Files

**Yours:** the four in `Lane-owns:` above.

**Not yours:** `justfile` (a lane owns it), `lint.py`, `test_lint.py`, `file-formats.md`, `dev/lane_guard.py`,
`review_artifact.py`, `.dreamwork/review/*`, `ledger_store.py`, `dreamhub.py`, `user_events/*`,
`dev/capture/serve.mjs` and `report.mjs` (use, do not edit), every other `dev/capture/*.mjs`, `SKILL.md`,
`DREAMWORK.md`, everything under `.dreamwork/`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**.
- **Work only inside `.worktrees/burndown`.** Verify cwd and branch before every write.
- ~30 minutes, and a sensible split is `c4` + shortened copy first (smallest, and it carries the figures he
  wants), then `c3`, then the hover. **Commit before you finish.**
- **Push back with reasons** — on the mapping, the copy, or the hover's shape. Not on whether `c3` is in.

## Report

Say: how the hover presents all three facts and how you avoided implying the level line means only one thing;
the shortened `c4` copy, and proof it does not ellipsise at both widths; **how the panel's height stayed
constant**, measured before and after a data change; the weight mapping including its zero and peak behaviour;
the transition idiom you reused and where it is documented, with sampled evidence and reduced-motion parity;
for each check the production line whose change reds it and confirmation no red needed a seam your diff
introduced; the derived preconditions; whether the built artifact is now stale against his ruling; and
confirmation you worked only in `.worktrees/burndown` (state cwd and branch), edited no `justfile`, left
nothing listening, never touched :35110, and did not run the full `just test`.
