# Brief — #554: the handoffs grammar check must reject conflict markers

**Task (verbatim from the store, #554, P2, origin loop):** handoffs grammar check
is blind to conflict markers: a diff3 base marker (`||||||| e2acedf5`) left in
`.dreamwork/handoffs.md` by a coordinator conflict resolver passed all 397
test_lint tests at the #548 merge — the #508 gate hit the same class and its
lesson did not become a check. The fold grammar test should reject any of
`<<<<<<<` / `=======` / `>>>>>>>` / `|||||||` at line start in handoffs.md (and
arguably every ledger doc a tool parses). Red-first: plant a marker line in the
fixture, watch the current check pass it.

**The live incident (proof the hole is real, not theoretical):** at the #548
merge gate (2026-07-30 ~20:35), the coordinator's python conflict resolver kept
the `||||||| e2acedf5` base marker line in `.dreamwork/handoffs.md` and the
merge commit passed the full `test_lint.py` suite (397/397) with it in place.
The #508 gate's Folded line records the same class from an earlier resolver
("left `|||||||` base markers + stale duplicated lines in handoffs.md") — the
lesson was recorded, the check never followed. This task makes the check.

**What to build:**
1. A lint.py check (extend the existing handoffs grammar check if that is the
   natural home — find it via `grep -n handoffs lint.py`; do not create a
   second check that re-reads the same file unless the existing one is
   structurally the wrong place) that ERRORs on any line in
   `.dreamwork/handoffs.md` beginning with `<<<<<<<`, `=======`, `>>>>>>>`, or
   `|||||||` (seven-char marker forms; `=======` exactly seven `=` at line
   start — do NOT flag markdown headings, hr rules, or `=` inside prose).
2. Decide and state, with a reason, whether the same rejection applies to the
   other ledger docs a tool parses (questions.md, tasks.md.deprecated, the
   briefs directory). Minimal scope is handoffs.md; a wider sweep must name
   each file it adds and why that file is parse-sensitive. Do not sweep
   watch-design.md / transitions.md / prose docs — conflict markers in prose
   are ugly but not parse hazards.
3. Tests in test_lint.py, red-first: plant each marker form in a fixture
   handoffs.md and watch the CURRENT suite pass it (that is the born-hollow
   demonstration — record it in your report), then the new check fails each.
   Include the negative fixtures: a markdown `---` hr, a `##` heading, and a
   prose line containing `=====` mid-line must all stay silent.

**Lane-owns:** `lint.py` (the handoffs check region only), `test_lint.py`.
Nothing else. Do not touch `watch.py`, `justfile`, `SKILL.md`, or
`.dreamwork/handoffs.md` itself except to append your own Pending line at the
end (see obligations).

**Verification:** `python3 -m pytest test_lint.py -q` full (397 today, + your
new tests). No browser, no ports, no guards. Red-proofs per the repo rule:
cp-snapshot → sabotage a NAMED production line (your new check) → the targeted
test FAILs → cp-restore byte-identical (cmp-verified, NEVER `git checkout`).
A green red-run is a finding, never a relief — if your sabotage passes,
the check is wrong; say so and fix the check.

**Obligations (#398):** when done, append ONE Pending line to the literal file
`.dreamwork/handoffs.md` under `## Pending` (append-only; the grammar is in
that file's head: `- **#554** · landed \`<sha>\` · 2026-07-30 · by lane-554markers — …`),
commit every file with `git commit --only <paths>` (a NEW file needs
`git add <file>` first), never `git add -A`, no `attn`, no `pkill -f`.
Report back: commits, the born-hollow demonstration, red-proof lines, and the
wider-scope decision with its reason.
