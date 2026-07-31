# Lane report — #737: measure dogfood-report compliance before enforcement

## Verdict

Build nothing mechanical and add no duplicate checklist wording.

At pinned `master` `3db7c26b1ba536e2f37645596d1f5d3a49a99961`, every
report that became tracked after #589 landed has a dogfood section: **12/12**.
One of those twelve is #589's report, recovered after its merge. Excluding that
repair leaves **11/11 genuinely later reports compliant**. The only six current
reports without a section all existed on mainline before the obligation landed.

This is evidence of one transition-time slip, not a recurring post-rule class.
The standing wording is paying for itself; it does not currently need a ledger
gate, a lint warning, or another copy of the same coordinator duty.

## Measurement

The census was independently run twice and pinned before counting because
`master` advanced during the first pass.

Method:

1. Pin `M=$(git rev-parse master)`; the reported snapshot is `3db7c26b`.
2. Enumerate the tracked blobs with `git ls-tree -r --name-only "$M" --
   .dreamwork`, restricted to `^\.dreamwork/lane-.*-report\.md$`.
3. Read each blob with `git show "$M:$file"`, not from the moving worktree.
4. Recognise only an anchored H2 matching
   `^##[[:space:]]+dogfood( report)?[[:space:]]*$`, case-insensitively.
5. Split the inventory by existence in `1d095ad3^1`, the mainline immediately
   before #589's merge. This avoids using author timestamps as a proxy for when
   a report became part of the coordinator's tree.
6. Extract each matched section through the next H2 and inspect its body, so a
   heading alone is not counted as a substantive answer.

| Cohort | Reports | With section | Without section |
|---|---:|---:|---:|
| Present before #589 landed | 22 | 16 | 6 |
| First tracked after #589 landed | 12 | 12 | 0 |
| Current total at `3db7c26b` | 34 | 28 | 6 |

The six pre-rule omissions are:

- `.dreamwork/lane-628-report.md`
- `.dreamwork/lane-675-report.md`
- `.dreamwork/lane-712-report.md`
- `.dreamwork/lane-721-report.md`
- `.dreamwork/lane-730-report.md`
- `.dreamwork/lane-733-report.md`

All 28 present sections have non-empty bodies. None is heading-only or `n/a`.
Some explicitly say “no friction found,” but each is still a stated answer;
several also carry concrete findings. A truthful explicit zero remains valid.

There is one provenance caveat: git cannot date bytes while they were
untracked. #589's recovered report may have been written before the rule, but
it was absent from both merge parents and the merge result. Treating it as a
repair rather than evidence of a newly dispatched compliant lane is why the
11/11 figure is reported separately.

## Direction 1 — independently recover #589's missing report

The method re-finds the original omission without trusting the task narrative:

```text
$ git cat-file -e 1d095ad3^1:.dreamwork/lane-589-report.md
missing
$ git cat-file -e 1d095ad3^2:.dreamwork/lane-589-report.md
missing
$ git cat-file -e 1d095ad3:.dreamwork/lane-589-report.md
missing
```

The report first becomes tracked at:

```text
43000fa8  2026-08-01T02:40:46+10:00
docs(#738, #589): point the draw-mode ask at an open task; land #589's lane report
```

That is 19 minutes after the obligation merged at `1d095ad3` (02:21:59
+10:00). The current 12/12 therefore does not erase the merge-time failure.

## Direction 2 — the tempting false-green

A check for a heading alone would accept both of the important counterexamples:

```markdown
## DOGFOOD
```

and:

```markdown
## DOGFOOD

n/a
```

Such a check should distinguish them from an explicit “no friction found.” It
could require a non-empty body, reject an `n/a`-only body, and accept the stated
zero. It still could not mechanically distinguish honest reflection from a
perfunctory sentence. No such syntactic check was added because the measured
post-rule population has neither false-green and the coordinator already reads
the actual section.

## IGC decision

Context: the obligation has just landed; its own lane was dispatched before
the standing text existed; every genuinely later tracked report is compliant;
and reports do not exist in a lane worktree at ordinary lint time.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| 1. Make `ledger.py fold` refuse | ✘ | ✔ | ✘ | ✔ | ✘ |
| 2. Warn from `lint.py` | ✘ | ✘ | ✔ | ✘ | ✘ |
| 3. Add merge-checklist wording | ✘ | ✔ | ✔ | ✔ | ✘ |
| 4. Keep the standing obligation; measure again on a new miss | ✔ | ✔ | ✔ | ✔ | ✔ |

- **G1:** inspect the actual report at a moment it exists.
- **G2:** never block folding otherwise-complete or non-lane work.
- **G3:** preserve an explicit “no friction found” as a valid third state.
- **G4:** add machinery or wording only for a measured post-rule failure class.

Decisive errors:

- **Option 1:** folding is ledger state reconciliation, not report-layout
  validation. Refusing the fold blocks the wrong completed artifact and invites
  bypass; it also fails proportionality when post-rule compliance is 11/11.
- **Option 2:** lane-worktree lint cannot inspect a report that has not landed.
  Main-checkout lint sees reports only after merge, while the six legitimate
  historical omissions force grandfathering logic or permanent noise. It
  therefore misses the decision moment and fails proportionality.
- **Option 3:** the existing standing text already says both “the lane writes”
  and “the coordinator reads.” Adding another checklist sentence creates no
  new observation or reminder site. Unlike posture drift, which recurs every
  tick and can be restated by the tick, a coordinator already has the report in
  hand at this one gate. The observed 11/11 says the current reminder is
  reaching that moment.
- **Option 4 survives:** it preserves the working obligation and defines the
  trigger for reconsideration: a newly dispatched post-rule lane whose report
  is absent, empty, or `n/a`-only.

## Relied-on ledger evidence

Every issue number used in the judgement was opened from the absolute live
ledger.

- **#737:** “MEASURE FIRST (#590): of the lane reports on master today, how
  many have a dogfood section? That number decides whether this is a real class
  or one lane's slip.”
- **#589:** “no lint check, because the obligation is on the lane's REPORT
  which does not exist at lint time, while a brief check would inspect the
  BRIEF - the wrong document.”
- **#513:** “Structural fix preferred over a manual refresh button: tick flow
  re-reads .dreamwork/posture and restates it.” This does not transfer to a
  duplicate checklist here: the tick is the posture observation site, while
  the already-read report is the dogfood observation site.
- **#707:** “The widening will multiply the class, not create it.” This is why
  the raw six missing headings were split by the obligation's landing instead
  of being attributed to the new rule.
- **#590:** the actual entry says the audit's “every number is a recommendation
  and the lane wrote no priority to the store.” That supports caution around
  audit numbers, but it does **not** literally state the brief's general phrase
  “a non-zero count is a question, not a verdict”; that attribution is only
  thematically adjacent.

## Changes and verification

No mechanism or standing wording changed. The only deliverable is this report.

- `python3 lint.py` — `clean (6 warning(s))`; the warnings are the expected
  worktree/store and existing documentation warnings, with no errors.
- No pytest file applies because no executable or governed source file changed.
- `python3 dev/redproof.py check` — `check: calm — no injections registered
  (opt-in discipline; nothing to evaluate).`
- Rebased successfully onto the latest local `master` before final handoff; no
  conflicts. The census remains deliberately pinned to `3db7c26b` so its
  denominator and counts are reproducible.

## DOGFOOD REPORT

One task-head citation is misleading in exactly the way the background warns
about. The head labels #590 as the authority for “a non-zero count is a
question, not a verdict,” but #590 is a backlog re-ranking entry and does not
state that general principle. Its narrower line says its audit numbers are
recommendations. #707 repeats the general phrase while citing #590, so the
principle is sensible but the authority chain is not literal. This cost a
required ledger lookup and should be corrected in future copies of this task
head; the scoped standing boilerplate was not edited because the bad citation
is not in it.

The other friction was useful rather than harmful: `master` moved during the
census, changing the denominator from 33 to 34. Pinning the tree before
enumeration made the two-thread counts reproducible and prevented a mixed-head
percentage.
