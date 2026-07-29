# Brief — lane-500bridge: the matt-pocock bridge plugin, first slice (#500)

**Lane-owns:** `plugins/ud-dreamwork-matt-pocock-skills/` (new — all of it)
plus its test file (name per repo convention, e.g.
`test_matt_pocock_bridge.py` at repo root if that is where plugin tests
live — CHECK how `ud-dreamwork-hooks`/`ud-dreamwork-worktrees` tests are
laid out and follow that). Nothing else. Do NOT touch `dev/ledger.py`,
`watch.py`, `lint.py`, `file-formats.md`, `ledger_*.py`, or any existing
plugin.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## Authority

`.dreamwork/docs/plans/matt-pocock-skills-bridge.md` — READ IT FIRST; it is
settled and ruled (OQ1–OQ5, §14). Also read `writing-plugins.md` (the
plugin-authoring contract) and the layout of the two existing plugins.
Related fresh context: `.dreamwork/docs/plans/posture-autonomy-axis.md`
(the autonomy axis your later consumers will read — the scaffold does NOT
implement the gating, only names it in the SKILL.md authority section).

## The slice (build ONLY this)

1. **Plugin scaffold** — `plugin.json`/SKILL.md/structure per
   `writing-plugins.md` and the sibling plugins. The SKILL.md states the
   three invocation buckets (design §11) and the authority floor (§7):
   read-only, no elevated actions granted.
2. **The tracker-adapter (design §8)** — the bridge's one real spec. A
   small module (Python, inside the plugin dir) mapping suite operations
   to `dev/ledger.py` verb SUBPROCESS calls: create→`file`, close→`fold
   --note`, list-open→`counts`/`ledger_parse` read, needs-info→questions
   via `watch.human_block()` (import the production function, never
   hand-format the bullet — C2). It **shells out** to the verb; it never
   opens `.dreamwork/tasks.md` or `.dreamwork/ledger.sqlite3` (C1), and
   never branches on source-of-truth itself (the verb dispatches
   internally — design T2).
3. **The T1–T5 seam checks (design §12)** as pytest tests, each with its
   red line run and named in the commit/report: T1 adapter never opens the
   ledger (with the runtime precondition that the ledger path resolves);
   T2 markdown-vs-store byte-identical behaviour; T3 grill question lands
   via `human_block()` and parses through the REAL
   `watch.parse_open_questions`; T4 the bridge writes nothing new under
   `.dreamwork/`; T5 no invented author tag (whitelist imported from
   `watch.NOTE_TAGS`/`ANSWER_TAGS`, never restated).

## Explicitly NOT in this slice (the design's own deferrals)

- **No loading/activation on any target** (design §13 — grant-gated, his).
- **No `docs/agents/*.md` writes anywhere** — the adapter contract is
  code + tests here; writing the dial into a target is activation.
- **No tick flow, no poll, no commands menu** (A′ removals, §5).
- **No autonomy gating code** — the #493 axis is designed but has no
  consumer yet; the SKILL.md only names the floor.
- **No handoff adoption, no autonomous grilling** (§7 not-granted list).

## Constraints (hard)

- Red-first per test; small commits, `git commit --only <paths>` (new
  files `git add` first). NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899.
- Tests use tmp dirs and the REAL cutover path where a store is needed
  (see `TestStoreModeLint._cut_over` in test_lint.py for the idiom); never
  touch the main checkout's live `.dreamwork/`.
- If the design doc and the code disagree, PUSH BACK in the report — every
  lane that refuted its brief this week was right to.

## Acceptance criteria (measurable)

1. Plugin scaffold present and parseable (plugin.json valid; SKILL.md
   carries the authority floor + invocation buckets).
2. The adapter maps the §8 operation table; T1–T5 pass.
3. Each T-check's red line was run (report names the injection + the
   production line).
4. Full `pytest` on your new test file green; `python3 lint.py` no new
   findings vs a master baseline (worktree shim/store ERRORs are the
   documented trap — compare, don't fix).
5. `git diff master --stat` touches only your owned paths.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
what exists after the slice, the five red lines with their production
lines, the deferrals respected, and any design-doc pushback.
