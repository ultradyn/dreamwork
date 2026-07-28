# Brief — #177: the text boxes grow with what he types, then scroll

Repo: `ud-dreamwork`. Worktree: **`.worktrees/autogrow`**, branch **`wt/autogrow`**. Do not push, do not merge.
**Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time.

**He asked for this one by name tonight**, so it is a direct human steer, not loop-chosen work.

## The task, verbatim from the ledger

> `- **#177** — [plan: docs/plans/composer-row.md] Text boxes grow with what he types, then scroll · P2 ·
> idea · 30m · his numbers: composer 2-3 → 10-15, answer/note 2 → 6 · the different ceilings are right — a
> 15-line box inside a question card would shove the list for a ten-second sentence · **third time today**
> that growing something moves what is below it (#141, #169, now) — the growth and #104's travel are ONE
> gesture · the box's HEIGHT is now state, so #118's tick-survival applies to it · fires on every newline, so
> it is the most frequent animation on the page`

**Read the plan** at `docs/plans/composer-row.md` (or `.dreamwork/docs/plans/composer-row.md`) first; it is
cited by the entry. **His numbers are the contract**: composer starts 2–3 rows and grows to 10–15;
answer/note starts 2 and grows to 6. The asymmetry is deliberate — a 15-line box inside a question card would
shove the list for a ten-second sentence — so **do not unify the ceilings**.

## This is Web UI, so the bar is the bar

`CLAUDE.md`: **every contribution to the Web UI must be of EXCEPTIONAL quality** — merely functional is not
the bar. **Load the relevant design skills** before designing or implementing rather than relying on generic
frontend defaults.

**`transitions.md` is binding and has no size floor. Read it first — it opens with how to check motion, and an
end-state assertion cannot fail on a motion bug.** Three things it forces you to confront here:

1. **The growth moves what is below it.** The entry says the growth and `#104`'s travel are **ONE gesture** —
   this is the third task where growing something displaces what follows. Do not author a second idiom;
   find the one the page already uses and reuse it. `dev/capture/dom.mjs` exports `midFrames`/`midStates`,
   and `states.mjs`/`confirmation.mjs`/`prominence.mjs` are all now on the frame-rate-free
   `midFrames(...) >= 1` form (`#333`, `#414`) — that is the house idiom for checking it.
2. **The box's HEIGHT is now state**, so `#118`'s tick-survival applies: a tick must not reset it mid-typing.
3. **It fires on every newline** — the most frequent animation on the page. A gesture that is 20ms too slow
   here is felt constantly, and reduced-motion parity is not optional.

## Scope discipline — the collision list is long

The finder identified many open siblings on the same surface. **You own the growth behaviour only.** Do not
touch: `#241` (one composer mount contract — several tasks block on it and it is not yours), `#269` (durable
drafts), `#183`, `#170`, `#168`, `#167`, `#164`, `#162`, `#161`, `#99`, `#227`, `#230`, `#257`, `#259`,
`#265`, `#337`. If your change makes one of those easier or harder, **say so in the report** rather than
doing it.

## Done means all of these

1. Both boxes grow with content to their **own** ceilings (composer 2–3 → 10–15; answer/note 2 → 6) and
   **scroll** past them. Shrinking back is the same gesture in reverse, not a snap.
2. **A browser guard** covering: growth, the ceiling, scroll-past-ceiling, shrink, reduced-motion parity, and
   that the growth **carries what is below it** rather than teleporting it. Register it in the justfile's
   `DEFAULT_GUARDS` (a `.mjs` in `dev/capture/` registered in neither `DEFAULT_GUARDS` nor `lint.NOT_GUARDS`
   gates nothing, and `lint` will say so).
3. **Red-first, and name the production line.** Motion checks must fail on a snap. **A green red-run is a
   finding, never a relief** — if it stays green with the transition neutralised, the check is not reaching
   the motion, and that is the more valuable result. Distinguish *"the trace did not sample the window"* from
   *"it snapped"* with different FAIL lines — a lane is fixing exactly that ambiguity right now in `#442`, so
   do not add a new instance of it.
4. **Assert the precondition your check depends on**, derived at runtime. **No literal tuned to today's
   layout**: `#441` was filed tonight for a shared floor with a 3px margin. If a threshold covers two
   different boxes, split it or say why one value is right for both.
5. **Tick-survival**: a guard step proving a status tick does not reset the height mid-typing (`#118`).
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch); your guard passes
   via `DREAMWORK_GUARDS="<yourguard>" DREAMWORK_HUB_GUARDS= just guards 39892` (**space-separated** — a
   comma is read as one filename). **Do not run the full `just test`.**
7. **`watch-design.md` is authoritative and single-source** — document the two ceilings and the gesture in the
   same commit that makes them. `just audit-styleguide` measures whether that happened.
8. **Do not touch :35110**, the heartbeat, the monitors, or the loop. `just deploy` now stops its own server by
   port ownership (`#431`); do not reintroduce a pattern kill.

## Files

Yours: `watch.py` (the composer/answer client code and its CSS), `watch-design.md`, a new
`dev/capture/<name>.mjs` plus its `justfile` `DEFAULT_GUARDS` entry, and `test_watch.py` if you add a
server-side test.

**Not yours:** `dev/capture/dom.mjs`, `confirmation.mjs`, `prominence.mjs`, `states.mjs`, `reviewsplit.mjs`
(**a live lane holds these for `#442`** — you may *read and import* `dom.mjs`, not edit it), `lint.py`,
`dev/ledger.py`, `dev/deploy_state.py`, `transitions.md`, and `.dreamwork/tasks.md` / `questions.md` — the
coordinator is their only writer, so report exact lines.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'feat(#177): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree.
- **Commit before you finish.** A lane tonight did 24 turns of correct work and exited without committing.
- **This host is never idle** (~30–50 load from other agents' sessions), so do not write a check whose pass
  condition assumes a quiet machine — see `#428`.
- The entry estimates **30m**. If it grows past that, land the growth-and-ceiling half with its guard and say
  what you left.
- **Push back with reasons if any of this is wrong.** Lanes tonight that refuted their brief were right to.

## Report

Say: which model you are; the gesture you reused and where it already existed; both ceilings as implemented;
the exact production line whose change reds your motion check; how the two failure modes are distinguished;
the tick-survival step; what `watch-design.md` gained; whether any sibling task got easier or harder; and
confirmation you did not run the full `just test`, touch :35110, or edit the files the `#442` lane holds.
