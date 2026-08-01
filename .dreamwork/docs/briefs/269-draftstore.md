# Brief — #269/#459: extract the DraftStore module and give the two uncovered boxes persistence

Repo: `ud-dreamwork`. Worktree: **`.worktrees/draftstore`**, branch **`wt/draftstore`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/reviewdraft.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[draftstore]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/draftstore-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per increment as it lands, and commit as you go.** Two lanes were killed by an external
sweep last night with everything uncommitted and their final reports lost; the per-milestone inbox lines
were the only surviving record. Assume you may be stopped without warning.

## He granted the build, and he attached a condition you must honour

Read `#269` and `#459` in `.dreamwork/tasks.md` — the whole of `#269`, which is long because it has been
wrong twice and records both corrections. The design landed at `e7d0b24`; his C1/C2 rulings landed
2026-07-29 01:12; the build grant is **2026-07-29 01:43, conditional**: *"yes, provided no good reasons not
to."*

**There is one good reason, and it changes the shape rather than the answer.** The shipped `localStorage`
write is **synchronous and cannot fail mid-keystroke**. IndexedDB is async, and a wedged store is a real
hazard this code already races against a timeout (`watch.py:2300`). A straight swap would make the
**acute** path — the one he actually lost work on — worse than it is today.

**So the IndexedDB migration is OUT of this brief.** What is in:

1. **Extract the `DraftStore` module** from the three hardcoded call sites, still `localStorage`-backed,
   with **dual-read of the old keys** so no draft in his browser right now is orphaned by the extraction.
   The design's logical id is `kind:scopeKey` inside a `data.target` partition.
2. **Bind the two boxes that have no persistence at all**: `#askbox` (~`watch.py:2514`) and the popout
   `#ptext` (`watch.py:7435 @ 91a6ad40`). These are `#459` and they are the cheapest consumers — they are the proof
   the module is a module and not a rename.

If your measurement says the extraction cannot be done without a behaviour change to the shipped path,
**stop and report that** rather than shipping the change. The acute fix is live and he is using it.

## The rules the module must carry across, verbatim from what shipped

These are not yours to redesign — they were measured empirically at `6a6ddff`
(`.dreamwork/docs/draft-durability-status.md`), **not read off comments**, and the extraction must preserve
every one:

- **Write on every input event, no debounce** (`watch.py` 4660, 5448-5458, 6824-6828). There is no lossy
  tail window today and there must not be one after you.
- **Clear only on durable success** (3527/3571/6915); a **failed send keeps the draft**. Route this through
  the design's pluggable `isDurable(response)` — `res.ok` today. **`#263`'s receipt gate is NOT yours**: a
  202 does not mean the write landed, and `writeVerdict` already exists for that; do not re-decide it here.
- **The live box outranks storage** (`#118`).
- **`try/catch` around every storage call.** A wedged or full store must degrade to no-persistence, never
  to a broken box.
- **Restore only into a mounted element that declares its id — no fuzzy title match.** Restoring into the
  wrong box is worse than losing the text, and that is a design ruling, not a preference.
- **Keyed on the question title, not a positional index** — the title survives a re-render, a re-sort and
  the re-index between Open and Answered; the index does not.

Cross-tab (**C1 = R1**, offer *"updated in another tab — load?"*, never swap text under him) and the
**30-day idle GC** are ruled but are **not in this brief** — they need the store, and the store is deferred.
Leave the seam, do not build behind it.

## Web UI bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality.* **Load the relevant design
skills** and read **`watch-design.md`** and **`transitions.md`** before designing. If restoring a draft
makes anything appear — a restored-text affordance, a hint, a cleared state — that is an **arrival** and
`transitions.md` has no size floor. Its opening section is *how to check*: an end-state assertion cannot
fail on a motion bug and neither can "did it move" — **sample**. Reduced-motion parity is part of the work.

## Verification

- **Extend `dev/capture/reviewdraft.mjs`** (in `DEFAULT_GUARDS`) rather than adding a rival guard. If you
  add one, register it in `justfile`'s `DEFAULT_GUARDS` (**57** today) or it gates nothing.
- **The discriminating check for this increment is the two NEW consumers.** A check that only re-proves the
  review dock passes identically before and after your diff and therefore proves nothing about the
  extraction. Prove `#askbox` and `#ptext` survive a **real reload** — the mode he reported was the full
  reload, not the re-render, and the entry records the coordinator getting that backwards.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — twice in two hours here a red run came
  back green because the test's own scaffolding stood in front of the injection.
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular — a lane was rejected for exactly that.
- **Assert the precondition the check depends on, derived at runtime.** A dual-read check needs an old-key
  draft to actually exist; write one and assert it is there in the old shape before asserting it is read.
- Use `dev/capture/serve.mjs`'s `serveVerified` — **do not spawn-and-sleep**. `watch.py` has **no
  `--no-open` flag** and no `--host` (`--bind`); passing one kills your server on an argparse error and your
  request silently reaches a stranger.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889; kill what you start by exact pid; check `ss -ltnp` before
  finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it. Never `pkill -f`. Do
  not touch the heartbeat, the monitors, or the loop.
- Trailer: `Feature:` — and say whether any existing install's stored drafts change shape (if the dual-read
  is doing its job, the answer is no, and that is worth stating).

## Files

**Yours:** the four in `Lane-owns:` above.

**Not yours:** `lint.py`, `test_lint.py`, `file-formats.md`, `dev/lane_guard.py`, `review_artifact.py`,
`user_events/*`, `dev/capture/serve.mjs` and `report.mjs` (use, do not edit), `SKILL.md`, `DREAMWORK.md`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/draftstore`.** Verify cwd and branch before every write. A lane that edited
  the main checkout aborted a held merge and produced `#465`; its guard and the lint backstop would now both
  catch you, and the backstop names the file and the lane.
- ~25 minutes, two increments: the extraction, then the two consumers. **Commit before you finish**, and
  land the extraction alone rather than nothing.
- **Push back with reasons.** The IndexedDB deferral above is itself a pushback the coordinator made on his
  conditional grant; if your measurement says the deferral is wrong, argue it with the measurement.

## Report

Say: which model you are; the module's surface and what each of the four call sites now passes it; how the
dual-read of old keys is proved (with the old-key precondition asserted at runtime); that every rule in the
list above survives, naming the line for each; what `#askbox` and `#ptext` now do on a real reload and how
you drove that reload; any transition you added and its sampled check plus reduced-motion parity; for each
check the production line whose change reds it and confirmation no red needed a seam your diff introduced;
the guard count; the trailer; and confirmation you worked only in `.worktrees/draftstore` (state the cwd and
branch you verified), left nothing listening, never touched :35110, and did not run the full `just test`.
