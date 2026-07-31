# Lane #753 report

## Verdict

Fixed and verified. `open_section_text` now recognizes only column-0 Markdown
section headings, so an indented `## ` heading inside a projected task body no
longer deletes every later open entry. The change stays at the shared slice in
`ledger_parse.py`; none of the six consumers or any off-limits file changed.

Implementation commits after rebasing onto local `master` `564829abca337c18d3cea7b9699623c03cd96cf2`:

- `8eee0598d815c2fb296cbe0c5e2f90509083d8e1` — `test(#753): expose entries hidden by body headings`
- `4127677dd0bf616af7a5bf4399b100f1088ded91` — `fix(#753): anchor ledger sections at column zero`

The rebase was clean; no conflict resolution was needed.

## Change and projection verification

- Replaced `ln.strip().startswith("## ")` with `ln.startswith("## ")`, and the
  matching Open-heading equality with `ln == "## Open"`.
- Added a Markdown fixture whose final entry follows both ` ## What to build`
  and an indented literal ` ## Recently landed`; the assertion finds the final
  entry by ID, not by section length or substring.
- In the live store projection, the only real headings were column-0
  `## Open` and `## Recently landed`. All 17 body-heading lines were emitted
  with one leading space. Raw stored bodies can contain column-0 headings, but
  `lint.ledger_view`'s store projection indents every nonblank continuation.
- Before the fix: 170 store open IDs, 165 parsed, max parsed ID 736; missing
  `[738, 749, 751, 752, 753]`. After the fix: 170 parsed, max 753, missing `[]`.

## Red-proof

### Direction 1 — the measured deletion

Before the production change, and again after deliberately restoring the
`.strip()` defect under `dev/redproof.py`, the named test failed with:

> `AssertionError: #753, the fixture's last open entry, disappeared after #736's indented ## What to build body heading`
>
> `assert 753 in {736}`

After restoring the fixed file, the test passed. Final gate:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

### Direction 2 — the separate false-green that remains

I constructed a ledger where the Open section slices correctly and parses IDs
`[1, 2]`, but entry #1 contains column-0 prose before a later indented
`deadbeef` citation. `ledger_entries` still ends #1 at that column-0 prose, so
the consumer sees `entry_1_contains_deadbeef=False`. This is the distinct
column-0-prose starvation defect recorded at `lessons.md:3311`; #753 does not
fix it and this report does not imply otherwise.

The new fixture also carries the literal text ` ## Recently landed` inside a
body. It remains body content because it is indented; only the real column-0
heading ends the section.

## Verification

- Pre-change baseline: `python3 -m pytest test_ledger.py test_ledger_cli.py test_ledger_store.py` — **113 passed**.
- Post-change and post-rebase: the same command — **114 passed**.
- `python3 -m pytest test_lint.py` — **535 passed**.
- Worktree interpreter over the live shared subject:
  `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` —
  **clean (2 warnings)**, both pre-existing (`questions.md` resolution dates
  and the known `lessons.md` near-duplicate). The warning set did not change:
  the newly visible entries are clean under the three open-only checks.
- `python3 dev/ledger.py sweep --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md`
  examined 262 commits against 170 open IDs and reported only #753's two lane
  commits. **#751 no longer flags.**
- `python3 dev/redproof.py check` — clean; three branch commits inspected and no
  recorded injection present.

## Issue evidence read

- #753: “The `.strip()` makes INDENTATION IRRELEVANT.” This is the production
  line changed.
- #671: “Every tick since the store cutover has been getting a confident empty
  answer from the primary landing-discovery route.” This is why restoring IDs,
  rather than merely lengthening the section, is the acceptance condition.
- #404: “a sweep that finds nothing must be distinguishable from one that did
  not run.” The final live sweep names both examined commits and open IDs.
- #707: “This is the fifth measured failure mode of the #404 premise.” #753 is
  the next failure shape: the ID was absent from the correlation input.
- #440: “a single supported way to fold an entry.” The analogous one-supported-
  slice rule is preserved: no consumer-local slicer was added.
- #352: “rec: one module both import, so the pin becomes unnecessary rather
  than better.” The fix remains in the shared `ledger_parse.py` seam.
- #607: “The path you invoke is the INTERPRETER; `--target`/`--ledger` is only
  the SUBJECT.” All meaningful after-runs used the worktree interpreter with
  the shared live store as explicit subject.
- #136: “present-but-unparseable is a fault and must look like one.” The ID-
  presence assertion prevents a missing parsed entry from reading as a
  negative citation answer.

## Out of scope

- The column-0-prose `ledger_entries` starvation described above remains real.
  It was measured and reported, not widened into this fix.
- No live ledger mutation was performed. No off-limits file was edited. No port
  was bound, and neither `attn`, merge, nor push was used.

## DOGFOOD REPORT

The task's verification shorthand says to run bare `python3 lint.py` and
`python3 dev/ledger.py sweep` from the lane, but the lane's gitignored store
cannot travel: both commands correctly refuse or report that ledger checks did
not run. The standing boilerplate already contains the right #607/#667 rule,
so the actionable friction is in task-specific verification heads: when the
verification needs live store behavior, spell out the worktree interpreter
plus the shared checkout's explicit `--target`/`--ledger` subject. I followed
that form and obtained the meaningful clean lint and #751 sweep result above.
