# Brief — #263 lane H (increments 34–35): the mixed-version gate must fail closed

Repo: `ud-dreamwork`. Worktree: **`.worktrees/mixedver`**, branch **`wt/mixedver`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: user_events, test_user_events_http.py, test_user_events_sqlite.py

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[mixedver]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/mixedver-inbox.md` so I can steer you mid-task — I do, and two
lanes tonight were corrected mid-flight by exactly that channel.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per milestone and commit as you go.** Two lanes were killed by an external sweep tonight with
everything uncommitted and their final reports lost to 0-byte files; the per-milestone inbox lines were the
only surviving record. Assume you may be stopped without warning.

**Eight lanes are running.** Touch only your `Lane-owns:` paths. `dev/lane_guard.py` and
`lint.check_lane_containment_backstop` will name you by file and branch if you edit the main checkout —
verify your cwd and branch before **every** write.

## Where this sits

Read `#263` in `.dreamwork/tasks.md` — it is long; the parts you need are the **lane H** increments (34–35,
*"mixed-version fail-closed"*) and what lanes A–E already landed. **His second gate is OPEN** (01:37, *"ack
good to go"*), so lanes E, G and H are authorised. **The payload purge and the PostgreSQL half remain
excluded by his separate Q4 ruling — do not build either.**

## The invariant lane H defends

Two processes of **different versions** may share one journal: a deployed snapshot serving the dashboard and a
freshly-updated one, or an old client mid-request while `just deploy` swaps the code underneath — which is now
reachable **by a click**, because the page can trigger `just deploy` as of tonight. So this is no longer
hypothetical.

**Fail closed means: an older reader that cannot understand a newer record must refuse, not guess.** A reader
that skips what it does not recognise silently loses events — and the whole point of `#263` is that a
registered envelope never disappears. Establish what the journal's version marker is today (read
`user_events/sqlite.py` and its schema), what a reader does with an unknown value **right now**, and whether
that is already fail-closed. **If it already is, say so and prove it** — "X is clean" and "I did not check X"
must stay distinguishable, and a clean bill with evidence is a complete result.

## The contracts you must not break

- **The 202 cutover:** the journal commit, not the handler, authorises the response. `_send_receipt` refuses
  to mint a 202 from a missing receipt (`send_error(503)`).
- **E5/E5b:** a body-validation failure answers `202 {"ok": false, "rejected": true, "reason": …}` with
  `REJECTION_REASONS` exactly three wide — `malformed_json`, `schema_invalid`, `domain_invalid`. **Do not
  widen that set.** A route needing finer copy adds an optional `detail`, which is the idiom landed tonight.
- `dev/capture/health.mjs` and `rejectwrite.mjs` guard the client half. You own neither — if a guard must
  change, report it.

**The trap this lane is most likely to fall into:** a fault-injection fake's pinned parameter is part of the
check's scope. `health.mjs` pinned `status: 409` and was therefore structurally blind to a live defect for
hours, which is `#413`. If you fake a version, drive **more than one** and assert the coverage at runtime.

## Verification — this repo's rules, and they are not optional

- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — when you reinstate a bug and the check
  passes, the check is wrong.
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular. A lane was rejected outright for that
  tonight.
- **Assert the precondition the check depends on, derived at runtime.** A check that examines nothing looks
  identical to one that found nothing — tonight a new check's coverage row silently never appeared because its
  parser saw no subjects. Put the count on the OK row.
- **Two values that must differ must be derived to differ.** A literal pair tuned to today's fixture is a
  check with an invisible expiry date; this repo has paid for that three times.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — eight lanes share this machine and the guard suite has documented load sensitivity (`#428`).
- Bind nothing in 39880–39899. Kill by exact pid; never `pkill -f`. Check `ss -ltnp` before finishing.
- **Never touch :35110, the heartbeat, the monitors, or the loop.** He is reading that dashboard.
- Trailer where it applies: `Migration:`, `Feature:`, `Needs: config|consent`. Decide and say why.
- 2 threads. **One commit per increment**: `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- ~20 minutes. **Commit before you finish**; land the smaller coherent half rather than nothing.
- **Push back with reasons.** A smaller honest result beats a larger one built on a premise you doubt — and
  two briefs tonight had premises that measurement refuted, so doubting mine is expected, not rude.
