# Brief — #555: extend conflict-marker rejection to the other tool-parsed ledger docs

**Task (verbatim from the store, #555, P3, origin loop):** the #554 lane closed
the handoffs.md hole and scoped the wider sweep: the same silent-corruption
class applies to every ledger doc a tool parses. `parse_handoffs` keys on `##`
heads and `- **#id**` entry heads, so a bare conflict-marker line falls through
to `continue` and renders as nothing — and the other parsers have the same
shape: `parse_ledger` keys on `## Open`/entry heads, `parse_questions` on its
own entry grammar, `classify_brief_handoff_scope` on brief structure. A
`<<<<<<<` / `=======` / `>>>>>>>` / `|||||||` line left by a merge in any of
them is the same reader-cannot-see-what-is-there defect the #548 gate shipped.

**What exists (do not rebuild):** `CONFLICT_MARKER_RE` at `lint.py:3806` is
module-level and shared-ready — exactly-seven at col 0 via negative lookaheads,
with the provenance comment. The #554 scan in `check_handoffs`
(`lint.py:3849-3877`) is the placement reference: raw-text scan at the TOP of
the check, BEFORE any parser-dependent early return, one ERROR per marker line
so each is named. Its docstring (`lint.py:3862-3868`) records this very sweep
as the wider-scope decision — you are that follow-up.

**What to build:**
1. Marker rejection (ERROR, one per line, naming the marker and line) in:
   - **`tasks.md` / `tasks.md.deprecated`** — the ledger text check
     (`check_ledger_sections`, `lint.py:1331`). Verify the call sites: if both
     files route through the one function, one scan inside it covers both;
     state that in your report. If only one routes through it, say where the
     other is read and cover it there.
   - **`questions.md`** — `check_questions` (`lint.py:189`), scan before any
     early return. The live server appends to this file; a marker ERROR fires
     at lint time (incl. the PostToolUse hook), never in the server's write
     path — that is the intended loudness, not a conflict.
   - **`briefs/*.md`** — the briefs check that consumes
     `classify_brief_handoff_scope` (`lint.py:3269` region): every brief file
     the check already walks gets the scan. Decide and state whether the scan
     lives in the check or the classifier, with a reason.
2. **Reuse `CONFLICT_MARKER_RE` — no second pattern.** If you find you need a
   different shape for one of these files, stop and report why instead of
   authoring a variant.
3. Tests in `test_lint.py`, red-first PER SURFACE: for each of the three doc
   families, plant each of the four marker forms in the fixture and watch the
   CURRENT checks pass them silently (the born-hollow demonstration — record it
   per surface), then the new scan ERRORs each. Negatives stay silent in every
   surface: a markdown `---` hr, a `##` heading, a setext `===` underline, and
   a prose line containing `=====` mid-line. Assert at runtime the precondition
   each check depends on (e.g. that the fixture really contains the marker
   line) — a literal tuned to today's fixture is a check with an expiry date.
4. The #554 decision record in `check_handoffs`' docstring is history — do NOT
   rewrite it. You may append one pointer line (`landed as #555`) if it reads
   stale; nothing more.

**Lane-owns:** `lint.py` (the three check regions named above + the existing
`CONFLICT_MARKER_RE` consumer sites), `test_lint.py`. Nothing else. Do not
touch `watch.py`, `justfile`, `SKILL.md`, any `.dreamwork` ledger file, or the
briefs directory content — `.dreamwork/handoffs.md` only to append your own
Pending line at the end (see obligations).

**Verification:** `python3 -m pytest test_lint.py -q` full (407 today, + your
new tests). No browser, no ports, no guards, NEVER `just test` or the guard
suite — browser lanes are in flight. Red-proofs per the repo rule: cp-snapshot
→ sabotage a NAMED production line (one of your new scans) → the targeted test
FAILs → cp-restore byte-identical (cmp-verified, NEVER `git checkout`). A green
red-run is a finding, never a relief — if your sabotage passes, the check is
wrong; say so and fix the check. Name the production line each red-proof
changed.

**Obligations (#398):** when done, append ONE Pending line to the literal file
`.dreamwork/handoffs.md` under `## Pending` (append-only; the grammar is in
that file's head: `- **#555** · landed \`<sha>\` · 2026-07-30 · by lane-555sweep — …`
— bare shas, no parentheticals), commit every file with
`git commit --only <paths>` (a NEW file needs `git add <file>` first), never
`git add -A`, no `attn`, no `pkill -f`. Report back: commits, the per-surface
born-hollow demonstrations, red-proof lines, the call-site coverage finding
(tasks.md vs tasks.md.deprecated), and the briefs scan-placement decision.
