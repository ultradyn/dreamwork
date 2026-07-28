# Brief — #436 remainder: 12 artifacts have no source, so two contracts cannot reach half the corpus

Repo: `ud-dreamwork`. Worktree: **`.worktrees/srcless`**, branch **`wt/srcless`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[srcless]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/srcless-inbox.md` so I can steer you mid-task.

Report a line per milestone (**counted**, **decision made**, **implemented**, **committed**). Full report goes
**once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are**
at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` —
report the lines you want added.

## The problem, stated once

Two build-time contracts landed tonight, both enforced in `review_artifact.py`:

- **`#436`** — an artifact must carry exactly one real `#ask`, not none, not two, not a decoy; exemption by
  declaration (`<meta name="dreamwork-review-ask" content="ask|exempt: <reason>">`).
- **`#455`** — an artifact must say **what happens if he says nothing**; same mechanism
  (`dreamwork-review-if-silent`), refused on **absence**, never on length.

Both are enforced **at build**, and **a build only happens for an artifact that has a source under
`.dreamwork/review/src/`**. The last count was **27 built artifacts, 15 with sources, 12 without** — derive the
current numbers yourself and show the expression; do not quote mine.

So **the contracts reach a bit over half the corpus, and the half they miss is invisible**. `#436` deliberately
left its walking guard **unregistered** for this reason: a guard that silently passes over 12 of 27 artifacts
would report success while checking nothing, which is the failure mode this repo has paid for most often.

## Your job: close that, and the decision is the deliverable

For each source-less artifact, decide **one** of:

1. **Reconstruct a source** — the built file exists, and the template's own build comment says which template
   version produced it. If a faithful source can be recovered mechanically, the artifact rejoins the contract.
2. **Declare it exempt in a side-file the checker reads** — a legacy artifact that predates the contracts, or a
   fixture like `tasks-page.html` (the reference the template was built to match), may be legitimately outside
   them. Then the checker's coverage is **explicit and countable** rather than silent.
3. **Retire it** — if an artifact is superseded and nobody would open it, say so; do not delete it on your own
   judgement, list it and let the coordinator decide.

**Choose per artifact with an IGC, not per feeling** — `igc-method.md` in the repo root (vendored tonight,
`#447`): binary goals or breakpoints, `✔` non-refuted / `✘` refuted with the decisive error written out, `?` a
TODO. One matrix over the *classes* of artifact is better than 12 matrices; say which class each falls in.

Goals worth stating binary: every built artifact is either **checked** or **explicitly exempt with a reason**
(no third state); a reconstruction is **faithful** (the rebuild is byte-identical, or the difference is stated
and justified — do not silently rewrite his artifacts); and the guard, once registered, **cannot pass over an
unaccounted artifact**.

## Then register the guard — that is the point of the task

`#436`'s walking guard is written and unregistered. Once coverage is explicit, register it in `justfile`'s
`DEFAULT_GUARDS` (52 today, each needing its file), so both contracts are enforced on the whole corpus.

**Red-proof it**: strip an `#ask` from one artifact, watch the guard fail, and **name the exact production line
whose change reds it**. **A green red-run is a finding, never a relief** — if it passes with an ask removed, the
guard is wrong. **Assert the guard's own precondition at runtime**: that the number of artifacts it examined plus
the number explicitly exempt **equals the number of built artifacts**. Derive all three; a literal is wrong the
day after it is written. That equation is the whole defence against the silent-pass failure, so make it an
assertion, not a comment.

## Constraints

- **Do not hand-edit a built artifact.** Build from source (`python3 review_artifact.py build <src>`) — a stale
  or hand-edited artifact is caught by `#329` and was caught tonight.
- **Do not change `review_artifact.py`'s contract logic** beyond what registering coverage requires. `#436` and
  `#455` are settled; you are extending reach, not renegotiating rules. If you believe a rule is wrong, say so
  and argue it rather than editing it.
- **Do not invent a decoy ask or a decoy if-silent sentence** to make a checker pass. That is the exact thing
  `#436` refuses. Use the declared exemption.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. Guards you run bind
  **39890–39899**; nothing in 39880–39889. **Do not run the full `just test`.**
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (pid 1542866 — he is reading it). Do not
  touch the heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: a newly registered guard changes what an install's `just test` does — `Feature:` is likely; decide.

## Done means

1. Every built artifact is **checked or explicitly exempt with a stated reason**, counted, with the counts
   derived and the expression shown.
2. The walking guard is **registered** and red-proved, with the coverage equation asserted at runtime.
3. Reconstructed sources rebuild to byte-identical output, or every difference is listed and justified.
4. Lint and pytest clean as above.

## Files

**Yours:** `.dreamwork/review/**` (sources, built files, and any exemption side-file), `justfile`'s
`DEFAULT_GUARDS`, `dev/capture/<the walking guard>.mjs`, `review_artifact.py` **only** where coverage requires,
and `test_review_artifact.py`.

**Not yours:** `watch.py`, `test_watch.py`, `user_events/*`, `test_user_events_http.py` (**lane E holds those
and is mid-cutover**), `lint.py`, `test_lint.py`, `file-formats.md` (**the `subdec` lane holds those three**),
`transitions.md`, `watch-design.md`, `dev/ledger.py`, `dreamhub.py`, `SKILL.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'feat(#436): …'` — **`--only`, never
  `git add -A`**: a lane's staged file was once swept into an unrelated commit (`12f47e3`) exactly this way, and
  `--only <dir>` silently skips untracked files.
- **Commit before you finish.** **~15–20 minutes.** If reconstruction turns into a project, land the
  **exemption-plus-registration** half — that alone closes the silent-pass hole — and report reconstruction as
  the successor.
- **Push back with reasons** if the honest answer is that most of the 12 should be exempt and reconstruction
  buys nothing. That is a complete answer and a cheaper one.

## Report

Say: which model you are; the derived counts and their expression; the IGC over artifact classes with each
decisive error; which artifacts you reconstructed, exempted (with reasons) and listed for retirement; the
production line whose change reds the guard and the coverage equation you asserted; the trailer you chose; and
confirmation you hand-edited no built file, invented no decoy ask, did not touch :35110, and did not run the full
`just test`.
