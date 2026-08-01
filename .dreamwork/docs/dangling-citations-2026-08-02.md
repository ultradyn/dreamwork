# Dangling documentation citations — census, classification, and guard ruling (#925)

**Census run against the main checkout** (`/home/xertrov/.llm-general/skills/ud-dreamwork`),
because gitignored-but-present files (`.dreamwork/status.json`, `.dreamwork/tasks.md`,
…) do not travel into a lane worktree, so a worktree run over-counts them as dangling.
Scanner: `dev/dangling_citations.py`. **SHA at classification: `c5e2b302` (== local
master at dispatch).**

**Post-rebase re-run at `d9b3afad` (master advanced 1 commit during the lane):** the
count moved, exactly as the brief predicted — `647` docs, `3985` citations, `232`
danging occurrences, `138` distinct paths (+1 doc, +4 distinct vs. the figures below).
The movement is entirely in the never-tracked bucket (sibling lanes editing docs); the
**STALE class is unchanged at 4 paths / 15 occurrences**, and the classification and
ruling below are not affected. The figures quoted in the census block and tables are the
`c5e2b302` snapshot; treat `d9b3afad` as +4 distinct of the same composition.

```
documents scanned: 646
citations seen:    3980
DANGLING:          228 occurrences, 134 distinct paths
```

The coordinator's brief reported 69 occurrences / 30 distinct at `439034fe` and said
*re-derive it; do not trust these numbers*. The re-derivation is broader and larger,
for two stated reasons: (1) the scanner's citation scope (below) is wider than the
coordinator's first instrument, and (2) the coordinator's 30 was evidently scoped to
code files under repo roots. **All seven of the coordinator's named offenders appear in
this census with identical counts** (`deprecated/watch.py` 9, `dev/apply_reanchors_i3.py`
7, `dev/relay.py` 6, `ds/index.js` 6, `dev/capture/tasks.mjs` 6, `dev/status_sync.py` 4,
`dev/capture/runmode.mjs` 3) — this census is a superset, not a disagreement.

## The instrument — citation scope and stated exclusions

**Citation scope** (stated, because a scanner with silent scope is the defect this task
exists to close — the coordinator's naive first scan reported 198 by silently counting
HTTP routes, gitignored-but-present files, and absolute paths into other machines):

> A citation is EITHER (a) a backtick-wrapped repo-relative file path, optionally with
> `:line` / `:line-line`; OR (b) a bare repo-relative file path immediately followed by
> `:line`.

**Exclusion rules** (each applied, each printed by the scanner on every run):

1. **REPO-RELATIVE ONLY.** A leading `/`, `~/` or `../` REJECTS the path as
   absolute/external (`/data.json` is an HTTP route; `/home/…` is another machine). A
   leading `./` is stripped. A bare name with no `/` (`status_sync.py`) is rejected — a
   name is not a path. This is the rule that turns 198 into an honest census.
2. **FILE-SHAPED.** The final component must carry an extension.
3. **ON-DISK-EXCLUDED.** A path present on disk is not dangling (gitignored-but-present
   like `.dreamwork/status.json`). *Caveat: run against the main checkout or this
   exclusion cannot bite — see above.*
4. **TRACKED-EXCLUDED.** A path tracked at `HEAD` is not dangling.

Both denominators always print; a run that examined zero of either exits `2` with a
loud `ERROR vacuity` (a regex that silently stops matching reads identically to a clean
scan — #868 — and this whole instrument is one regex).

## Classification

Not all 134 are defects. The brief names three classes; the discriminator turns out to
be **git history** for one class and **prose intent** (which no regex reads) for the
rest.

### STALE — ever tracked at HEAD's history, now gone: **4 paths, 15 occurrences**

| path | occ | deleted by |
|---|---|---|
| `dev/apply_reanchors_i3.py` | 7 | #918 (`05dc5dca`, the citation-oracle retirement) |
| `.dreamwork/dreams/2026-07-28-0658-essential-marks-inc1.md` | 3 | a superseded dream |
| `dev/capture/runmode.mjs` | 3 | #547 (`bece3aa2`, run-mode picker removal) |
| `dev/capture/rundesc.mjs` | 2 | #547 (`bece3aa2`, same) |

**But even this cleanest class is not uniformly defective.** Most are present-tense
claims about a deleted file — real defects (`adjudication-2026-08-02.md:119` *"`dev/
apply_reanchors_i3.py:4-11` resolves the sibling decision"*; `briefs/789-…:69` *"`dev/
apply_reanchors_i3.py` is 143 lines … and is currently"*). Yet `watch-design.md:2416`
reads *"`(dev/capture/runmode.mjs`, `dev/capture/rundesc.mjs`) **are deleted**"* — past
tense, a correct historical record, **not** a defect. A guard keyed only on
"ever-tracked-and-now-gone" flags that correct sentence as a defect.

### The never-tracked 130 paths — forward / historical / external / runtime, irreducibly mixed

These were never in git history, so git cannot label them. Split by defensible
heuristics (path prefix + citing-document type):

| bucket | paths | occ | example | defect? |
|---|---|---|---|---|
| **EXTERNAL** (cross-project app) | 22 | 23 | `lib/pag_server/questionnaire/validator.ex`, `app/views/nodes/_ledger_peek_icon.html.erb`, `pages/settings/SettingsPage.tsx` | no — cited in `questionnaire-survey.md`/`session-log-view.md` discussing another project |
| **RUNTIME** (gitignored / transient) | 6 | 17 | `.git/index.lock`, `.dreamwork/session-index.sqlite3`, `.dreamwork/co-agent-claims.json` | no — runtime artefacts cited in lessons about them |
| **SCANNER-ARTIFACT** (over-match) | 8 | 10 | `14/http/server.py` (fragment of `/usr/lib/python3.14/http/server.py`), `SKILL_DIR/watch.py` (placeholder), `requestId/message.id` (JSON field), `nosuch/vanished.md` (fixture) | no — the scanner's own over-matches (see blind spots) |
| **REPO-INTERNAL** (forward / historical / doc-relative) | 94 | 163 | `deprecated/watch.py` 9, `dev/relay.py` 6, `ds/index.js` 6, `dev/suite_baseline.py` 1, `plans/hub-public-auth.md` 2, `references/cf-concepts.md` 3 | **mixed — and that is the finding** |

The REPO-INTERNAL 94 is where the brief's HISTORICAL and FORWARD classes live **on the
same paths**: `deprecated/watch.py` is HISTORICAL in the `migrate-watch-symlink.md`
brief and FORWARD as the #368 symlink target that has not landed; `references/
cf-concepts.md` is HISTORICAL (moved to `igc-concepts.md`) per the bundling doc;
`dev/suite_baseline.py` is FORWARD (#924 is building it); `dev/relay.py` / `ds/index.js`
are FORWARD or abandoned-plan references in design docs. **No automated signal separates
them** — the difference is whether the surrounding prose asserts a present-tense claim,
describes a past state, or names a not-yet-built file, and that is authorial intent a
regex cannot read.

## Ruling: a guard is possible only as a closed, pinned population — NOT as an open regex

**Do not build an open-corpus regex guard.** Over the 134 distinct paths, a guard would
be wrong on ≥120 of them (external, runtime, historical, forward, scanner-artifact) —
well over the "60% wrong is worse than none" bar the brief sets, and exactly the noise
that gets a checker turned off. The evidence:

1. **The STALE class** (the only one git history identifies) is itself polluted by
   past-tense historical references (`watch-design.md:2416` "are deleted"), so even
   "ever-tracked-and-now-gone" is noisy.
2. **The never-tracked 130** split into forward/historical/external/runtime on the *same
   path forms*, distinguishable only by prose the scanner does not parse.
3. **The one honest discriminator is enrollment, not detection**: a human asserts "this
   citation is a present-tense claim" at the moment it is pinned. That is the model
   already in `dev/check_watch_citations.py` — a curated `Counter[(doc, token)]` multiset
   each pinned to a resolvable revision, with a PASS line that reads *pinned, not
   verified against the pinned revision*. **This census is the raw input for enrolling
   such a population, not a guard.**

**Recommendation (a ruling for the coordinator, not an action):** if a guard is wanted,
the home is the closed-population pinned model in `dev/check_watch_citations.py`, NOT an
open regex. That file is owned by #921/#920 and was not edited. Enrolling the present-
tense STALE citations (e.g. the 7 `dev/apply_reanchors_i3.py` present-tense claims) into
a pinned population is the defensible next step — and it is #920's call, since #920 is
repairing those same citations right now.

## Blind spots (stated honestly — direction 2b)

The scanner **misses** three forms of genuinely-dangling citation (proven against a
fixture): a Markdown link target `[x](dev/missing.py)`; a bare un-backticked path
without `:line` (`see dev/missing.py`); and any path containing a space (`dev/with
space.py`). It also **over-matches** a handful: fragments of absolute system paths
(`/usr/lib/python3.14/http/server.py` → `14/http/server.py` when not backtick-wrapped),
placeholders (`SKILL_DIR/watch.py`), and dotted prose tokens (`requestId/message.id`).
The honest statement: the census is a defensible lower bound on backtick/coordinate
citations, not a complete inventory of every string that names a missing file.

## Red-proof (both directions)

- **Direction 1 (sharp, discriminating).** Broke the `normalise()` seam in
  `dev/dangling_citations.py` (rejected `dev/`-prefixed paths). Citations stayed seen
  (regex intact), but the dangling path was silently dropped, so the named test
  `test_dangling_citation_is_caught` failed on the path-naming assertion:
  `AssertionError: dangling citation 'dev/this_file_does_not_exist.py' not caught; saw []`.
  Expectation derived from the hand-written fixture literal in `test_dangling_citations.py`
  (independent of the scanner, #906). Restored via `redproof.py`; hand-off gate clean.
- **Direction 2a (loud, both halves).** Empty directory → `documents scanned: 0` →
  **exit 2** `ERROR vacuity`. Broken regex (dead extension) against the real repo →
  `citations seen is 0 across 646 document(s)` → **exit 2** `ERROR vacuity` — never a
  green "0 dangling".
- **Direction 2b.** The three missed forms above.
- `redproof.py check --require 1`: **3 injections registered, all restored and absent
  from the working tree and from this branch's commits.**

## What was assessed and deliberately NOT done

- **No `.md` document was edited** other than this one (the brief forbids it; #920 owns
  repairs). Where the analysis says a document should change (e.g. the present-tense
  `dev/apply_reanchors_i3.py` claims), it is written here, not applied.
- **`dev/check_watch_citations.py` was not edited** (#921/#920 own it). The
  recommendation that any guard live there is a ruling, not an action.
- **No open-corpus guard was built.** Building one would violate the ruling above.
- `test_dangling_citations.py` selection is kept **narrow** (3 tests) to avoid widening
  the flake surface of every gate it touches (#916).
