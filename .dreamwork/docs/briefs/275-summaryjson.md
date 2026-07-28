# Brief — #275 Q5: the redacted `/summary.json`, which he has now authorised

Repo: `ud-dreamwork`. Worktree: **`.worktrees/summaryjson`**, branch **`wt/summaryjson`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/summaryjson.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[summaryjson]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/summaryjson-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead (the
rule is at the top of `.dreamwork/handoffs.md`). **Do not write `.dreamwork/handoffs.md`**,
`.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines you want added. **Report a line per
increment and commit as you go**; an external sweep killed four jobs here half an hour ago.

## What he authorised, and the one thing he did not

Read `#275` in `.dreamwork/tasks.md`, and `plans/hub-public-auth.md` §11 plus `plans/hub-ssh-auth.md` (which
both name this deliverable).

**Answered 2026-07-29 05:54. Q5: *"sure"*** — a redacted `/summary.json` may be designed and shipped as its
own task before any public serve. **It is the blocker**, measured: `collect()` (`watch.py:10900`) feeds
`/data.json` (`watch.py:11713`), which serves `questions.md`, `DREAMWORK.md` and `lessons.md` **in full**,
plus parsed entries, transcripts and `status.json`. That endpoint is unfit to expose and this is what replaces
it for any non-local consumer.

**Q3 in the same answer changed the target:** dreamhub is **read+write** and *"should entirely replace
watch.py for normal day-to-day use"*. So `/summary.json` is **not** a cut-down public teaser — it is a real
consumer surface. Design it as the thing dreamhub will actually read, not as a demo.

**What he did NOT authorise, and you must not do:** **public or WAN serving remains forbidden.** Do not add,
change or widen a bind address, a `--allow-host`, a tunnel, a proxy, a listener or a flag that reaches the
network. This lane adds an endpoint; where it may listen is a separate ruling he has not given. If your work
seems to need a bind change, stop and report — that is a finding, not a step.

## The actual design problem

**Redaction is a whitelist, never a blacklist.** A denylist over `collect()` is wrong by construction: the
next field someone adds is exposed by default, and nothing tells them. Build the summary by **naming the
fields that may leave**, and make the shape refuse an unknown key rather than pass it through.

Decisions that are yours, and each needs an argument in the report:

1. **What a summary actually needs to be useful** — counts, ids, titles, timestamps, states. Note that a
   **question title is his words** and a ledger title is often a description of his words; decide per field
   and say why. "Titles are fine" is a claim about content you should test against the real corpus, not an
   assumption.
2. **How the whitelist fails when `collect()` grows.** The interesting case is not today's fields, it is the
   field added in three weeks. A test that enumerates today's keys passes forever and protects nothing;
   something must **notice a new key** and refuse it. This is the heart of the task.
3. **Whether `status.json`'s runtime state belongs.** It carries dreamer names, owned file paths and deploy
   instructions — machine-local operational detail.
4. **Transcripts: out.** Say so explicitly and assert it.

## Verification

- **New guard `dev/capture/summaryjson.mjs`**, registered in `justfile`'s `DEFAULT_GUARDS` (**57** today) or
  it gates nothing. Take the port from `process.argv[3]`; if you serve your own target use `await freePort()`
  **only when argv[3] is absent**. **Do not hardcode an exclusive port** — `reviewdraft` does and `#471` is
  open because I cannot explain its behaviour under `just guards`.
- **The discriminating check is the leak check, and it must be derived.** Assert that no value in
  `/summary.json` contains content that only appears in the full documents — derive a distinctive string
  **from the fixture's `DREAMWORK.md`/`lessons.md`/`questions.md` at runtime** and assert its absence. A
  hand-written "secret" string planted by the test proves only that your planted string is absent.
- **Assert the precondition:** that the string you derived really is present in `/data.json`, or the absence
  assertion is vacuous. This exact hollowness (a fake returning `""` for the one input that would have
  reached the branch) cost this repo two green red-runs in one evening.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular.
- `/summary.json` is a shape a tool parses, so state it in **`file-formats.md`** — except that file is **not
  yours** (report the paragraph you want, and say so in your report; the coordinator will land it).
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — it is 15+ minutes at this machine's load.
- Bind nothing in 39880–39889; kill what you start by exact pid; check `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it. Never `pkill -f`.
- Trailer: `Feature:`. Add `Needs: consent` only if you believe something here needs his approval, and name it.

## Files

**Yours:** the four in `Lane-owns:` above, plus the `DEFAULT_GUARDS` line in `justfile` (that line only).

**Not yours:** `dreamhub.py` and `dreamhub-design.md` (the consumer side is a later increment — design for it,
do not build it), `file-formats.md`, `lint.py`, `test_lint.py`, `dev/lane_guard.py`, `review_artifact.py`,
`user_events/*`, `dev/capture/serve.mjs` and `report.mjs` (use, do not edit), `SKILL.md`, `DREAMWORK.md`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/summaryjson`.** Verify cwd and branch before every write — the pre-commit
  guard, `lint`'s backstop and the new `pre-merge` assertion will each name you by file and branch.
- ~25 minutes. **Commit before you finish**, and land the whitelist plus its leak check rather than nothing.
- **Push back with reasons.** If the honest conclusion is that no useful summary can be built without a field
  you judge unsafe, say which field and why — he authorised the endpoint, not any particular contents.

## Report

Say: the whitelist, field by field, with the argument for each (especially anything containing his words);
**how a newly added `collect()` key is refused rather than passed**, and the production line that enforces it;
the derived leak string and its precondition; for each check the production line whose change reds it and
confirmation no red needed a seam your diff introduced; the `file-formats.md` paragraph you want; the guard
count; confirmation you changed **no** bind address, host allowlist, flag or listener; and confirmation you
worked only in `.worktrees/summaryjson` (state the cwd and branch you verified), left nothing listening, never
touched :35110, and did not run the full `just test`.
