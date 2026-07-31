# Lane #755 report

## Verdict

Implemented in `status_sync.py`. This is the right home rather than `lint.py`: `status_sync` owns `status.json`, already resolves the authoritative ledger on every tick, and can reuse that one read for both derivation and the advisory audit. A `just lint`-only check would miss ticks. The prose remains author-owned; only its `#NNN` claims are checked.

The audit runs after the existing unreadable/empty/duplicate-ledger refusal gates and before liveness. It extracts every id occurrence from every queued line, reports landed and absent ids while quoting the whole line, reports id-less/non-text entries as unclassifiable, and always prints entries/id-references/questions/unclassifiable denominators. It never mutates `queued_dispatches`, never adds a finding to the derived `changes` list, and therefore leaves warning-only `--check` at exit 0. Real derived drift still exits 1 and writes nothing.

Commits after the final rebase:

- `f12d6b88` `test(#755): specify queued dispatch id questions`
- `4fd794ae` `feat(#755): warn on queued dispatch ledger contradictions`

## Red-proof

Before the change, the real `status_sync.main` over a fixture with open `#1` and landed `#2` returned `rc=0; queued-warning=False; stderr=''`. The all-open fixture was also silent. After adding the tests but before production code, all six new cases failed; the discriminating landed failure was:

> `AssertionError: assert 'WARN queued_dispatches: #2 is landed' in ''`

Direction 1 was then repeated through `dev/redproof.py`: the fixed `status_sync.py` was snapshotted lane-privately, landed handling was sabotaged to treat `landed` like `open`, and the named test failed on that same exact assertion. `restore` copied back the fixed file and verified it. Final gate:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

The negative control names only open ids and asserts no `WARN queued_dispatches`, while still requiring `checked 1 entry, 1 id reference; 0 state questions, 0 unclassifiable`. The parenthetical fixture `#641 subject (held behind #630 P2)` checks both references: landed `#641` warns, open `#630` does not.

Direction 2 remains deliberately open and is pinned: `#1 implementation already landed but still queued` passes when the ledger still calls `#1` open. Ledger state cannot judge prose truth. The id denominator proves it was examined rather than silently skipped. The id-less `the SSE transport` takes the other branch: it is WARNed as unclassifiable and counted, not presented as clean.

## Evidence and governing records

- `#725`: “Prefer (2) if only one is built” for the contradiction check; its landed note says it “chose the CHECK over the writer and measured why first.” This change uses that same report-not-repair shape.
- `#702`: the measured failure was that a malformed id was “dropped with the same message as a genuinely dead lane”; the landing keeps and reports what cannot be classified. Here an id-less queued line is likewise reported, never disappeared.
- `#707`: “widening a pattern that feeds an automatic correlation makes FALSE ATTRIBUTION possible”; its landing reports separate matches rather than guessing. Here every parenthetical/multi-id occurrence is checked and no subject id is inferred.
- `#671`: the fixed output accounts for “BOTH halves of the correlation”; a zero-entry case says `DID NOT REVIEW`. Here every run reports both entry and id-reference denominators.
- `#136`: “THREE zero-states, not one”; present-but-unparseable must not look genuinely empty. The audit distinguishes absent/empty, checked-open, and unclassifiable entries in its counts.
- `#752`: “IT JUDGED PER OCCURRENCE RATHER THAN PER ID.” The queued audit follows that rule and does not cite `#590` as authority.
- `.dreamwork/lessons.md:3302`: “a non-zero count is a question, not a verdict.” Accordingly the warning states a ledger fact and says the entry is unchanged; it does not label the prose stale.
- `#645`: “DESIGN LANDED, IMPLEMENTATION NOT STARTED — entry stays open.” This is the concrete proof that landed-looking prose and an intentionally open follow-up can coexist, so the audit cannot repair or fail the tick.

## Verification

- Baseline: `60 passed in 18.28s` for `test_status_sync.py test_status_derive.py`.
- Final after rebase: `67 passed in 18.30s` for the same requested files.
- `python3 lint.py`: `clean (6 warning(s))`, no ERRORs. Four extra warnings relative to the main checkout are explicit worktree refusals because the gitignored ledger/status do not travel.
- Store-mode fixture proves landed `#11` is read through the cut-over SQLite store; warning-only `--check` exits 0.
- Rebased cleanly onto local master `8561238f07697db18386d922caf2e2b0ab877877`; no conflicts.

The required live invocation was run read-only as `just status-sync --target /home/xertrov/.llm-general/skills/ud-dreamwork --check`, because ordinary mode rewrites `status.json` even when already in sync and the brief absolutely forbids this lane from writing the live file. It did not match the brief's 04:10 premise:

> `queued_dispatches: checked 4 entries, 11 id references; 2 state questions, 0 unclassifiable`

It named landed `#666` in the parenthetical “browser guards ... #666” and landed `#632` in the historical “#632 removed - it had LANDED” audit line, quoting both. The first run also found genuine derived drift (`dreamers prune 2 stale lane(s) (3 -> 1)`) and exited 1 without writing. Before final hand-off the coordinator changed the live dreamer state; the final identical `--check` returned 0 with no `stale:` line, while still reporting the two advisory state questions above. The coordinator must resolve those live author-owned lines; this lane did not.

## DOGFOOD REPORT

The brief's live-status premise had rotted before the lane reached its mandated verification. It says the stale `#632` entry was removed and all queued ids were open, but the current `queued_dispatches` still contains `#632` in a historical audit line and `#666` in a parenthetical. The task simultaneously requires extracting every `#NNN` and requires the healthy live file to be quiet; those are incompatible for the current live bytes. The new check correctly exposed the contradiction instead of special-casing “VERIFIED” prose or parentheticals, which would violate the task's own `#707` rule.

The brief also asks for ordinary `just status-sync` while absolutely forbidding live writes. The implementation writes atomically even when there are no derived changes, so the only compliant live verification is `--check`; future briefs should spell that form out. The read-only reviewer independently recommended the same `status_sync` placement and warning-only exit semantics. No other friction found.
