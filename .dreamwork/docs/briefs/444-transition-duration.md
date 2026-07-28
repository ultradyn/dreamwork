# Brief — #444: the snap detector proves a transition exists, not that it lasts

Repo: `ud-dreamwork`. Worktree: **`.worktrees/duration`**, branch **`wt/duration`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

**Read `transitions.md` first** — binding, no size floor, opens with how to check motion.

## The gap, which is the price of a fix that was right

`#442` (landed `9edb3f7`) proved that **rAF runs on the main thread while opacity/transform transitions run on
the compositor**, so under load the compositor animates perfectly while zero rAF callbacks fire inside the
window — `midFrames` read 0 over a flawless animation. It correctly made `transitionstart` the
load-independent gate. Read its entry (`#442`) and the new `transitions.md` bullet.

**But `transitionRan` is a boolean about existence.** A transition shortened to `1ms` still fires
`transitionstart`, so it passes. Between *"the CSS says animate"* and *"it animated for the duration the
styleguide specifies"* there is now no check on this path.

## The question before the work — this may be a refusal

The events already captured carry the answer: `transitionWindow` (new in `dev/capture/dom.mjs`) returns the
window, so its **width is measurable with no rAF sampling at all** — load-independent by the same argument
that motivated `#442`.

**But decide first whether asserting it earns its runtime.** If the assertion just reads the declared duration
out of the CSS and checks the browser honoured it, **that is a check that restates the thing it reads**, and
the honest answer may be *"existence plus the styleguide's single-source rule is enough"*. **A refusal with a
measurement is a complete and welcome answer here** — a lane tonight refused what it was handed after
measuring four alleged defects and that was the most valuable result of the evening.

If you do assert it: **derive the expectation from the declaration** (the `CARD_TRAVEL` / `.cmdmsg` transition
values in `watch.py`'s STYLE constant), never a literal, with a tolerance you justify — a transition observed
under load finishes late, and `#442` measured windows of 289–665ms for the same gesture. A tolerance too tight
reintroduces exactly the flakiness `#442` removed. **Say what you measured across several runs before
choosing it.**

## Done means

1. A decision, argued from measurement: assert the duration, or refuse with the reason stated.
2. If asserting: it passes **twice in a row including two concurrent suites** (`#442`'s reproduction recipe:
   `DREAMWORK_GUARDS="confirmation prominence states" DREAMWORK_HUB_GUARDS= just guards <port>` — **space
   separated**, a comma is read as one filename), with the loads recorded. A single pass proves nothing here;
   that is what made `#414` look fixed.
3. If asserting: **red-first, and name the production line.** Shorten the real declared duration and watch it
   fail; **a green red-run is a finding, never a relief.** Distinguish *"ran too briefly"* from *"did not run"*.
4. If refusing: **red-prove the refusal** — leave a test or comment such that someone rebuilding the check
   fails it, the way `#419`'s lane did.
5. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078). **Do not run the full
   `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.
6. `transitions.md` and `watch-design.md` are single-source: document any rule you add in the same commit.

## Files

Yours: `dev/capture/dom.mjs`, `dev/capture/confirmation.mjs`, `transitions.md`.

**Not yours:** `watch.py` and `justfile` (**a live lane holds both for `#177`** — you may read `watch.py` to
find the declared durations, **not edit it**), `dev/capture/states.mjs`, `prominence.mjs`, `reviewsplit.mjs`,
`lint.py`, `dev/ledger.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` — report exact lines.

## Practical

2 threads. `git commit --only <paths>` — **never `git add -A`**. **Commit before you finish.** This host is
never idle (~25–50 load from other sessions), so design for the loaded case — see `#428`.

## Report

Which model you are; the decision and the measurements behind it; the tolerance and how you derived it; the
production line whose change reds it (or how you red-proved the refusal); the two concurrent runs with loads;
what the docs gained; and confirmation you did not run the full `just test`, touch :35110, or edit `watch.py`.
