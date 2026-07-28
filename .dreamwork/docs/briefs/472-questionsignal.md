# Brief — #472 + #473: he cannot reach the artifact, and cannot tell a question changed

Repo: `ud-dreamwork`. Worktree: **`.worktrees/qsignal`**, branch **`wt/qsignal`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/qsignal.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[qsignal]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/qsignal-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the
lines you want added. **Commit each increment as it lands**, and report a line per milestone.

## Two tasks, both his, filed 2026-07-29 06:21 in one breath

Read `#472` and `#473` in `.dreamwork/tasks.md`. His words:

> *"the link to the review artifact does not work (doesn't render as a link even)"*
>
> *"it was not obvious that this question had updated, we should show the updated ago or something as well as
> having an event get posted to the user (for notifications) that a question was updated. Add tasks for these."*

They are one brief because they are one experience: he is reading `/questions` and the page is not telling him
things. Do `#472` first — it is smaller, it is strictly a bug, and it blocks every review ask.

## `#472` — measure before you change anything

The `#417` entry writes `[`417-burndown-commits.html`](../review/417-burndown-commits.html)`. `watch.py` has
`linkify` (~2049), `linkifyReview` (~2062), `mdInline` and `mdSpans` (~2138-2140) and they **compose**, so
find which one is meant to handle `[text](url)` before editing. **There may be two defects, not one:** the
markdown link may not be rendered at all, *and* the relative `../review/` path may be wrong for the route the
questions view is served at. A link that renders but 404s is still broken from where he sits.

**Second half, and do not skip it: settle ONE way of writing it.** `#294` and `#445` write
`` `.dreamwork/review/x.html` `` backticked and unlinked; `#417` writes a markdown link. The corpus is
inconsistent, so the next ask is a coin flip. Pick the shape, make it work, and **report the
`file-formats.md` paragraph you want** (that file is not yours). Prefer supporting what the corpus already
mostly does over a migration nobody asked for — and say which you chose and why.

## `#473` — the hard part is the definition, not the display

Two deliverables: **(a)** an updated-ago on the entry, beside the existing date and age; **(b)** an event
posted so he learns about a change without looking.

**What counts as "updated" is the whole problem, and it is NOT the file mtime.** Entries thread: a follow-up,
a shrink, a rewritten `rec`, a new sub-decision are all edits to one entry — while an unrelated entry being
answered rewrites the same file. So this is **per-entry**, and nothing currently records when an entry last
changed. `#463` faced exactly this shape (created vs modified) and its lesson applies: the timestamp has to
come from somewhere real, and an exact-inequality test on near-identical times produced 24 false positives on
28 artifacts there — so decide what granularity is *honest* and suppress a distinction the eye cannot use.

**Where the timestamp can come from is yours to decide and to argue.** Candidates include a stored per-entry
digest, git history of `questions.md`, or a written marker. Each has a real cost: a digest needs somewhere to
live, git needs the file committed (and the coordinator commits it minutes after writing), a marker changes a
parsed format. **Say what you rejected and why.**

**For (b), reuse `watch-events.log`** rather than inventing a second channel — and state its limit honestly:
that channel is **best-effort and lossy by design**, so an event may never arrive. If your measurement says
(b) cannot be made reliable on that channel, **say so and land (a) alone**; the loop already knows about this
weakness and half a truthful feature beats a notification he cannot trust.

## Web UI bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality.* **Load the relevant design
skills**, read **`watch-design.md`** and **`transitions.md`**. An updated-ago that appears is an **arrival**,
and `transitions.md` has no size floor — its opening section is *how to check*, and an end-state assertion
cannot fail on a motion bug, so **sample**. Reduced-motion parity is part of the work.

**`#456` is prior art for the age display** (` · ` between date and age, dim pad zero) — reuse that idiom
rather than authoring a second one, and note `ages()` rewrites this text every second as a pure text update
with no transition, so an updated-ago that animates every second would be a defect, not polish.

## Verification

- **New guard `dev/capture/qsignal.mjs`**. **Own-server guards must take `await freePort()` and IGNORE
  `argv[3]`** — `#461` did the opposite and silently stopped eight guards from executing for three and a half
  hours (`#471`, fixed at `80ac4b5`). **Do not register it in `justfile`** — guard registration is centralised
  at merge after two lanes were granted that one line; run it directly and **report the name**.
- **The discriminating check for `#472` is that the link WORKS, not that an `<a>` exists.** Assert the href
  resolves to a real artifact — fetch it and check the status — because a rendered link to a 404 is the defect
  he reported wearing a fix's clothes.
- **For `#473`, derive the precondition:** an entry must actually have been updated after it was created, and
  the two times must differ by more than your chosen granularity. **Derive both at runtime and assert the
  gap** — a literal tuned to today's fixture is a check with an expiry date nobody can see, and this repo has
  paid for that three times.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — and if a red comes back green, **suspect
  your injection before the test**: confirm you edited the line the check names (that cost the coordinator a
  near-miss tonight).
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889; kill what you start by exact pid; `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it, and it is the page these
  two tasks are about, so the temptation is real. Never `pkill -f`.
- Trailer: `fix:` for `#472`, `Feature:` for `#473`.

## Files

**Yours:** the four in `Lane-owns:` above.

**Not yours:** `justfile`, `lint.py`, `test_lint.py`, `file-formats.md`, `dev/lane_guard.py`,
`review_artifact.py`, `ledger_store.py`, `dreamhub.py`, `user_events/*`, `dev/capture/serve.mjs` and
`report.mjs` (use, do not edit), every other `dev/capture/*.mjs`, `SKILL.md`, `DREAMWORK.md`, and everything
under `.dreamwork/`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**.
- **Work only inside `.worktrees/qsignal`.** Verify cwd and branch before every write.
- ~30 minutes for both. **Land `#472` on its own commit first** — it is a P1 bug blocking every review ask,
  and if you run out of time it must not be stuck behind `#473`.
- **Push back with reasons.** Particularly on `#473`(b): if the event channel cannot carry a notification he
  can rely on, that is a finding worth more than a feature that lies.

## Report

Say: for `#472`, which function in the compose chain was at fault, whether the path was **also** wrong, the
shape you settled on and the `file-formats.md` paragraph you want; for `#473`, what you decided "updated"
means, where the timestamp comes from, **what you rejected and why**, the granularity and why it is honest,
and whether (b) is reliable or was cut; the transition checks you sampled and reduced-motion parity; for each
check the production line whose change reds it and confirmation no red needed a seam your diff introduced; the
derived preconditions; the guard name for me to register; and confirmation you worked only in
`.worktrees/qsignal` (state cwd and branch), edited no `justfile`, left nothing listening, never touched
:35110, and did not run the full `just test`.
