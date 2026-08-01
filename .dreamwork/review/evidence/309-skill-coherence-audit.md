# #309 — Coherence re-read of SKILL.md + initialization.md

Findings-only audit (no tracked file edited). Scope: do SKILL.md and
initialization.md still agree with each other, with `file-formats.md`,
and with what `lint.py` / `watch.py` now enforce — after #290 (run-mode),
#216 (origin markers), the worktrees plugin, #304 (parse_ledger section
split), #307 (doc-map plans row), and the lint checks those added.

Most severe first. `file:line` quotes are against the current tree
(`chore/309-skill-coherence`).

---

## CONFIRMED

### 1. SKILL.md says the ledger is "open tasks only"; it is open + landed, and the two-section split is now a load-bearing contract

- **Observed** — `SKILL.md:270-271`:
  > "On a session-scoped backend (the native tools) it is
  > `.dreamwork/tasks.md`: **open tasks only**, one line each (id, title,
  > priority/type/size, origin, owner or blocked-on, pointer to any
  > plan), plus the next id to hand out."

- **Why it is wrong.** The file has two sections, both real and both
  parsed:
  - `.dreamwork/tasks.md:29` is `## Open`; `.dreamwork/tasks.md:1178` is
    `## Recently landed`, and the landed entries are full entries (multi-
    line, origin-governed — e.g. `#307` carries `origin: **loop**`).
  - `watch.parse_ledger` (`watch.py:6006 @ 6199cf44`) returns `(open ids, landed
    ids)` and reads **both** sections via `LEDGER_SEC_OPEN` /
    `LEDGER_SEC_LANDED` (`watch.py:5935-5936 @ 6199cf44`). The docstring states the
    two-shape contract explicitly.
  - #304 (commit `1d089ad`) made the section split load-bearing:
    `check_ledger_sections` (`lint.py:349`) walks the lines itself and
    ERRORs when its open count disagrees with `watch.parse_ledger`.
  - The burndown series (`ledger_series`, `watch.py:6033 @ 6199cf44`) derives
    completions from the landed section's git history. A coordinator
    that believed "open tasks only" and stopped writing `## Recently
    landed` would silently break the burndown and the `landed` set that
    `check_landed_asks` (#306) reads.
  - This is not new drift: `3d6a643` (which introduced the phrase) already
    had a `## Recently landed` section in the file. #304 is what made
    ignoring it costly.
  - The file's own header (`tasks.md:14`) says the opposite of "open
    only" — "It is deliberately NOT every started task" — so SKILL.md
    and the file it describes disagree.

- **Smallest correction.** `SKILL.md:270-271`: replace "open tasks only,
  one line each" with "open tasks plus a `## Recently landed` section,
  one entry each" (and either drop "one line each" — entries wrap at
  ~72 cols — or keep it as "one entry each"). The `## Recently landed`
  heading is literal (the parser anchors on it), so name it verbatim.

### 2. SKILL.md's two ledger field-lists disagree on whether `origin` is a field

- **Observed** — same file, two enumerations of the ledger line:
  - `SKILL.md:271` (the durable-state entry) **includes** origin:
    > "one line each (id, title, priority/type/size, **origin**, owner
    > or blocked-on, pointer to any plan)"
  - `SKILL.md:366-372` (Task-list conventions) **omits** origin:
    > "The ledger carries what selection and triage read: `priority`
    > (P1-P3), `type` …, `size` …, `feasibility` …, the next-up mark …,
    > owner or blocked-on, and — once a task is scope-gated — its `goal`
    > and `parent`."

- **Why it is suspect.** `origin` is lint-enforced from #216
  (`check_task_origins`, `lint.py:395`, ERROR), and the contract is
  stated in `file-formats.md:222-261`. "Task-list conventions" is the
  natural section to learn a task's fields from, and it reads as
  exhaustive ("The ledger carries…"). The two lists may have different
  *intended* scopes (the second is "what selection and triage read", and
  origin is provenance, not selection) — but the header does not say
  "only what selection reads", so a reader is left to assume the list is
  complete and origin is optional. It is not.

- **Smallest correction.** Add `origin (human/loop/unknown, from #216)`
  to the list at `SKILL.md:366`, or reword the header to state the scope
  is selection-only and origin is covered above.

---

## SUSPECTED

### 3. The filing instructions never mention `origin` at the point of filing

- **Observed.** None of the places a dreamer actually creates a task say
  to record origin: the Commands (`do now` / `add idea` / etc.,
  `SKILL.md:384-425`), the Task-list conventions, and
  `initialization.md` step 10 (Seed, `initialization.md:210-214` — "as
  pending tasks with priority/size metadata"). The rule is stated only
  as a property of entries (`SKILL.md:273` "From #216 every entry
  records who filed it") and in `file-formats.md`.
- **Why suspect.** A dreamer filing from the Commands section alone
  would mint a task without `origin` and produce a lint ERROR on the
  next increment. It fails loud (lint), so the cost is low — but the
  instruction-to-file and the rule-that-governs live in different
  sections than the act they bound, which is the exact shape this repo
  keeps rediscovering.
- **Smallest correction.** One phrase in Task-list conventions or the
  Commands intro: "file with `origin: **human**` / `**loop**` per who
  asked (contract: file-formats.md)."

---

## Growth (the lean check the task asked for)

### 4. The Subagents section is the one closest to "procedure"

`SKILL.md:156-246` (~90 lines) is the longest non-algorithmic section.
Most of it is load-bearing — nearly every paragraph traces a named
failure (the 600k-token dreamer, the twice-in-one-day shutdown, the
swallowed deliverables) — so this is **borderline, not a bug**. The
clearest procedure-as-prose is the steering mechanics: the write-then-
wake dance and `relay.py` usage (`SKILL.md:231-238`), and the lifecycle
timing rules (the ~4-min reuse window, the ~10-min resume-selection
threshold). If the section grows further, that steering block is the
natural candidate to become a one-line pointer to a reference file
(alongside `reflection.md` / `compaction.md`). No correction needed now;
flag for the next lean pass.

---

## Genuinely coherent (one line each, no work invented)

- **run-mode (#290):** consistent across `SKILL.md:89-98`, the durable
  entry `SKILL.md:323-327`, `initialization.md:122-127`,
  `file-formats.md:355-388`, and `lint.py:577` (closed set read from
  `watch.RUN_MODES`, never restated). `hierarchical` is consistently
  excluded as a file value.
- **origin markers (#216):** contract consistent across `SKILL.md:273`,
  `file-formats.md:222-261`, `lint.py:395` (cutoff 216, vocabulary
  human/loop/unknown, forward-only). Only the field-list omission in
  finding 2.
- **worktrees plugin:** `SKILL.md:189-198` states the disjointness/
  worktree principle; `DREAMWORK.md:123` loads `ud-dreamwork-worktrees`;
  no contradiction between principle and plugin.
- **doc-map plans (#307):** `file-formats.md:504-528`, `lint.py:878`
  agree; `initialization.md:142-145` seeding description ("seed
  doc-map.md") is still accurate — #307 made a row checkable, it did not
  change how the map is first created.
- **plugin resolution / plugin-commands.json:** `initialization.md:18-66`
  matches `plugin_resolver.py`'s actual flags (`--target`, `--path
  ID=SKILL.md`, `--root`) and the write-whole rule; `file-formats.md:446`
  and `lint.py:628` agree.
- **#306 cross-check** (`check_landed_asks`) is undocumented in
  `file-formats.md`, but legitimately so — it is a cross-file consistency
  rule, not a file shape; its contract lives in its `lint.py:304`
  docstring. Not a gap.
- **No stale references.** Every file/tool/flag named in
  `initialization.md` and `SKILL.md` exists (`plugin_resolver.py`,
  `heartbeat.py`, `relay.py`, `roll.py`, `reflection.md`,
  `compaction.md`, `stop-hook-variant.md`, `writing-plugins.md`,
  `DREAMWORK.template.md`, `bin/ud-dw-githash`, the migrations named in
  `file-formats.md`).
- **Init step list matches.** `SKILL.md:43-49`'s 11-step summary matches
  `initialization.md`'s 11 numbered steps, in order.

---

**Net:** one real contract bug (finding 1), one internal inconsistency
in the same file (finding 2), one procedural gap that lint catches loud
(finding 3), one growth observation (finding 4). The recent structural
edits (#290, #216, #304, #307, the worktrees plugin) are otherwise
coherent across SKILL.md / initialization.md / file-formats.md / lint.py.
